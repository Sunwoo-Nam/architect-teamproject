"""실행 러너 — 동일 하니스·동일 TC에 전략만 교체해 1회 협상을 돌리고 관측값을 수집한다.

관측: 합의(또는 결렬), 라운드·제안 수(Time 프록시), 협상 구간 피크 메모리(tracemalloc — ENV-A 프록시),
deepening(2안)·백트랙(1안) 횟수. FC 점수는 Judge가 별도 산출.
"""
from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass, field

from negmas.sao import SAOMechanism

from dpca.common.scenario import Scenario
from dpca.harness.beliefs import build_beliefs
from dpca.harness.eventlog import EventLog
from dpca.harness.negmas_bridge import TupleCodec, make_outcome_space
from dpca.strategies.baseline_full import FullEnumNegotiator
from dpca.strategies.pool import PoolNegotiator
from dpca.strategies.sequential import run_sequential

STRATEGIES = ("full", "pool", "seq")


@dataclass
class RunResult:
    strategy: str
    scenario_id: str
    agreement: dict[str, str] | None
    rounds: int
    proposals: int
    peak_kib: float
    wall_ms: float
    extra: dict = field(default_factory=dict)
    log: EventLog | None = None


def run_one(scenario: Scenario, strategy: str, n_steps: int = 200, with_log: bool = False) -> RunResult:
    beliefs = build_beliefs(scenario)
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

    if strategy == "seq":
        result = run_sequential(scenario, beliefs, log=log)
        agreement, rounds, proposals = result.agreement, result.rounds, result.proposals
        extra = {"backtracks": result.backtracks, "trace": result.trace}
    elif strategy in ("full", "pool"):
        codec = TupleCodec(scenario.axes)
        mechanism = SAOMechanism(outcome_space=make_outcome_space(scenario.axes), n_steps=n_steps)
        negotiators = []
        for b in beliefs:
            if strategy == "full":
                negotiators.append(FullEnumNegotiator(scenario, b, codec, n_steps, log=log))
            else:
                negotiators.append(PoolNegotiator(scenario, b, codec, n_steps, log=log))
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
        log.log("session_end", agreement=agreement, rounds=rounds, proposals=proposals)
    return RunResult(
        strategy=strategy,
        scenario_id=scenario.id,
        agreement=agreement,
        rounds=rounds,
        proposals=proposals,
        peak_kib=peak / 1024,
        wall_ms=wall_ms,
        extra=extra,
        log=log,
    )
