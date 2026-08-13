"""실행 러너 — 동일 하니스·동일 TC에 전략만 교체해 1회 협상을 돌리고 관측값을 수집한다.

관측: 합의(또는 결렬), 라운드·제안 수(Time 프록시), 협상 구간 피크 메모리(tracemalloc — ENV-A 프록시),
deepening(2안)·백트랙(1안) 횟수. FC 점수는 Judge가 별도 산출.
"""
from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass, field

from negmas.sao import SAOMechanism

from total.adapters.composite._vendor.common.scenario import Scenario
from total.adapters.composite._vendor.harness.beliefs import build_beliefs
from total.adapters.composite._vendor.harness.comms import Comms
from total.adapters.composite._vendor.harness.eventlog import EventLog
from total.adapters.composite._vendor.harness.negmas_bridge import TupleCodec, make_outcome_space
from total.adapters.composite._vendor.strategies.baseline_full import FullEnumNegotiator
from total.adapters.composite._vendor.strategies.pool import PoolNegotiator
from total.adapters.composite._vendor.strategies.pool2 import run_pool2
from total.adapters.composite._vendor.strategies.sequential import run_sequential

STRATEGIES = ("full", "pool", "seq")


@dataclass
class RunResult:
    strategy: str
    scenario_id: str
    agreement: dict[str, str] | None
    rounds: int          # 원자료(참고용) — 방안별 구성이 달라 직접 비교 금지, phase로 비교 (B1)
    proposals: int
    phases: int          # 직렬 통신 단계 수 (24 §9.3)
    messages: int        # 물리 전송 건수 (24 §9.1)
    peak_kib: float
    wall_ms: float
    bytes: int = 0       # [이식 시 신설] 페이로드 바이트 (24 §9.2)
    eval_calls: int = 0  # [이식 시 신설] 효용 평가 호출 수 — 전 참여자 합 (24 §6.4-a)
    observations: list = field(default_factory=list)  # [이식 시 신설] CF 측정용 관찰 기록
    extra: dict = field(default_factory=dict)
    log: EventLog | None = None


def run_one(scenario: Scenario, strategy: str, n_steps: int = 200, with_log: bool = False) -> RunResult:
    beliefs = build_beliefs(scenario)
    comms = Comms(n_participants=len(beliefs))
    log = EventLog(meta={
        "scenario": scenario.id,
        "strategy": strategy,
        "profile_seed": scenario.profile_seed,
        "n_axes": len(scenario.axes),
        "space_size": scenario.space_size(),
        "initial_thresholds": [b.initial_threshold for b in beliefs],
    }) if with_log else None
    tracemalloc.start()
    tracemalloc.reset_peak()
    start = time.perf_counter()

    if strategy in ("seq", "seq2"):
        # seq2 = 1안 개선판: T1(프리픽스-소프트 반영) + T3(최종확인 백트랙) + 백트랙 상한 상향
        # (T3 재협상이 축막힘에 걸리지 않도록 백트랙 예산을 축 수만큼 준다)
        kw = (dict(soft_aware=True, final_confirm_retries=6, max_backtracks=max(2, len(scenario.axes)))
              if strategy == "seq2" else {})
        result = run_sequential(scenario, beliefs, log=log, comms=comms, **kw)
        agreement, rounds, proposals = result.agreement, result.rounds, result.proposals
        extra = {"backtracks": result.backtracks, "axis_rounds": result.axis_rounds,
                 "trace": result.trace}
    elif strategy == "pool2":
        # 2안 개선판: 유효-only 조건부 확장 + k 고정 + 충돌 축 교체 재협상
        agreement, rounds, proposals, p2extra = run_pool2(scenario, beliefs, n_steps=n_steps,
                                                          log=log, comms=comms)
        extra = p2extra
    elif strategy in ("full", "pool"):
        codec = TupleCodec(scenario.axes)
        mechanism = SAOMechanism(outcome_space=make_outcome_space(scenario.axes), n_steps=n_steps)
        negotiators = []
        for b in beliefs:
            if strategy == "full":
                negotiators.append(FullEnumNegotiator(scenario, b, codec, n_steps, log=log, comms=comms))
            else:
                negotiators.append(PoolNegotiator(scenario, b, codec, n_steps, log=log, comms=comms))
        for negotiator in negotiators:
            mechanism.add(negotiator)
        state = mechanism.run()
        rounds = int(getattr(state, "step", 0))
        proposals = sum(n.proposal_count for n in negotiators)
        if mechanism.agreement:
            names = tuple(mechanism.agreement)
            agreement = {ax.name: name for ax, name in zip(scenario.axes, names)}
        else:
            agreement = None
        extra = (
            {"deepening": sum(getattr(n, "deepening_count", 0) for n in negotiators),
             "final_k": [getattr(n, "k", None) for n in negotiators]}
            if strategy == "pool" else {}
        )
    else:
        raise ValueError(f"알 수 없는 전략: {strategy}")

    wall_ms = (time.perf_counter() - start) * 1000
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if log is not None:
        log.log("session_end", agreement=agreement, rounds=rounds, proposals=proposals,
                phases=comms.phases, messages=comms.messages)
    return RunResult(
        strategy=strategy,
        scenario_id=scenario.id,
        agreement=agreement,
        rounds=rounds,
        proposals=proposals,
        phases=comms.phases,
        messages=comms.messages,
        bytes=comms.bytes,
        # 전 참여자의 효용 평가 호출 합. beliefs는 이 실행에서 새로 만든 객체라
        # 세션 간에 누적되지 않는다 (전역 카운터였다면 두 번째 실행이 더 크게 나온다)
        eval_calls=sum(b.evals for b in beliefs),
        observations=list(comms.observations),
        peak_kib=peak / 1024,
        wall_ms=wall_ms,
        extra=extra,
        log=log,
    )
