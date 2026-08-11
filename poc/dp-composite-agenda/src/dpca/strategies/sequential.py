"""1안 — 의제별 순차 협상.

축마다 그 축 하나짜리 OutcomeSpace로 별도 SAO 세션을 연다(offer = 단일 축 값, 임시값 없음).
앞 세션 합의값은 각자 로컬에서 다음 축 후보를 좁히는 데만 쓰인다(힌트 전송 없음).

- 축 순서: TC 선언 순서 (의존성 방향과 일치하도록 TC가 선언 — 위상 정렬의 구체화)
- 바닥선 보호: 값 v 수락 전에 낙관적 완성 효용(합의된 prefix + v + 남은 축 최선값 가정)이
  자기 initial_threshold 이상인지 확인 — 바닥선 밑 조립을 사전 차단
- 백트랙: 어느 축에서 진행 불가(후보 없음/세션 결렬)면 직전 축 합의를 금지 목록에 넣고 재협상 (상한 있음)
- 최종 확인: 전 축 조립 후 각자 전체 효용 ≥ 바닥선 재검(잠정 합의의 확정 단계)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from negmas import make_issue, make_os
from negmas.sao import ResponseType, SAOMechanism, SAONegotiator, SAOState

from dpca.common.generators import Value
from dpca.common.rules import Outcome
from dpca.common.scenario import Axis, Scenario
from dpca.harness.beliefs import AgentBeliefs
from dpca.harness.comms import Comms
from dpca.harness.eventlog import EventLog
from dpca.harness.negmas_bridge import aspiration


@dataclass
class SequentialResult:
    agreement: dict[str, str] | None
    rounds: int
    proposals: int
    backtracks: int
    comms: Comms | None = None
    trace: list[str] = field(default_factory=list)


class AxisNegotiator(SAONegotiator):
    """단일 축 세션용 협상자 — 값 점수(0..1)로 제안·수락, 낙관적 완성 하한으로 바닥선 보호."""

    def __init__(
        self,
        beliefs: AgentBeliefs,
        scenario: Scenario,
        axis: Axis,
        values: list[Value],
        agreed: dict[str, Value],
        n_steps: int,
        log: EventLog | None = None,
        comms: Comms | None = None,
    ):
        super().__init__(name=f"seq-{beliefs.idx}-{axis.name}")
        self.eventlog = log
        self.comms = comms
        self.beliefs = beliefs
        self.scenario = scenario
        self.axis = axis
        self.agreed = agreed
        self.n_steps = n_steps
        self.proposal_count = 0
        # 자기 기준 실행 가능 값만 (자기 하드 + 공유 규칙은 세션 공간에서 이미 걸러짐)
        self.mine = [v for v in values if self._own_ok(v) and self._optimistic(v) >= beliefs.initial_threshold]
        self.mine.sort(key=lambda v: -beliefs.scores[axis.name][v.name])
        self._by_name = {v.name: v for v in values}
        self._offered: set[str] = set()

    def _own_ok(self, value: Value) -> bool:
        partial: Outcome = {**self.agreed, self.axis.name: value}
        return all(
            rule(partial) for rule in self.beliefs.own_hard if _covers(rule, partial)
        )

    def _optimistic(self, value: Value) -> float:
        """합의 prefix + v + 남은 축은 최선값이라는 낙관 가정의 효용 상한."""
        total = 0.0
        for ax in self.scenario.axes:
            weight = self.beliefs.weights[ax.name]
            if ax.name in self.agreed:
                total += weight * self.beliefs.scores[ax.name][self.agreed[ax.name].name]
            elif ax.name == self.axis.name:
                total += weight * self.beliefs.scores[ax.name][value.name]
            else:
                total += weight * max(self.beliefs.scores[ax.name].values())
        return total  # soft 감점은 낙관 가정상 0으로 둔다 (상한이므로)

    def _score(self, value: Value) -> float:
        return self.beliefs.scores[self.axis.name][value.name]

    def _log(self, kind: str, **fields) -> None:
        if self.eventlog is not None:
            self.eventlog.log(kind, agent=self.beliefs.idx, axis=self.axis.name, **fields)

    def propose(self, state: SAOState, dest: str | None = None):
        self.proposal_count += 1
        thr = aspiration(state.step, self.n_steps, 0.0)
        for v in self.mine:
            if self._score(v) >= thr and v.name not in self._offered:
                self._offered.add(v.name)
                if self.comms:
                    self.comms.proposal_sent()
                self._log("propose", step=state.step, offer=v.name,
                          my_score=round(self._score(v), 4), threshold=round(thr, 4),
                          reason="양보선 이상 미제안 값 중 최선")
                return (v.name,)
        if self.mine:
            best = self.mine[0]
            if self.comms:
                self.comms.proposal_sent()
            self._log("propose", step=state.step, offer=best.name,
                      my_score=round(self._score(best), 4), threshold=round(thr, 4),
                      reason="새 값 없음 — 최선값 반복 제안")
            return (best.name,)
        self._log("propose", step=state.step, offer=None, reason="제안 가능 값 없음")
        return None

    def respond(self, state: SAOState, source: str | None = None) -> ResponseType:
        offer = state.current_offer
        if offer is None:
            return ResponseType.REJECT_OFFER
        thr = aspiration(state.step, self.n_steps, 0.0)
        value = self._by_name.get(offer[0])
        if value is None or not self._own_ok(value):
            self._log("respond", step=state.step, offer=offer[0], decision="REJECT",
                      threshold=round(thr, 4), reason="내 하드 제약 위반")
            return ResponseType.REJECT_OFFER
        optimistic = self._optimistic(value)
        if optimistic < self.beliefs.initial_threshold:
            self._log("respond", step=state.step, offer=offer[0], decision="REJECT",
                      optimistic=round(optimistic, 4), threshold=round(thr, 4),
                      reason="낙관적 완성 효용이 바닥선 미달 — 받으면 바닥선 도달 불가")
            return ResponseType.REJECT_OFFER
        if self._score(value) >= thr:
            if self.comms:
                self.comms.accept_sent()
            self._log("respond", step=state.step, offer=offer[0], decision="ACCEPT",
                      my_score=round(self._score(value), 4), optimistic=round(optimistic, 4),
                      threshold=round(thr, 4), reason="값 점수 ≥ 양보선, 낙관 하한 통과")
            return ResponseType.ACCEPT_OFFER
        self._log("respond", step=state.step, offer=offer[0], decision="REJECT",
                  my_score=round(self._score(value), 4), threshold=round(thr, 4),
                  reason="값 점수 < 양보선")
        return ResponseType.REJECT_OFFER


def _covers(rule, partial: Outcome) -> bool:
    """부분 outcome에 규칙을 적용할 수 있는지 — 참조 축이 없으면 KeyError 대신 통과 처리."""
    try:
        rule(partial)
        return True
    except KeyError:
        return False


def run_sequential(
    scenario: Scenario,
    beliefs: list[AgentBeliefs],
    n_steps_per_axis: int = 60,
    max_backtracks: int = 2,
    log: EventLog | None = None,
    comms: Comms | None = None,
) -> SequentialResult:
    comms = comms if comms is not None else Comms(n_participants=len(beliefs))

    def orch_log(kind: str, **fields) -> None:
        if log is not None:
            log.log(kind, **fields)

    agreed: dict[str, Value] = {}
    forbidden: dict[str, set[str]] = {ax.name: set() for ax in scenario.axes}
    rounds = proposals = backtracks = 0
    trace: list[str] = []
    shared_hard = beliefs[0].shared_hard  # 공유 규칙은 전원 동일

    i = 0
    while i < len(scenario.axes):
        axis = scenario.axes[i]
        # 세션 공간: 공유 규칙과 prefix에 일관 + 금지 목록 제외 (양측이 같은 공간을 본다)
        space_values = [
            v for v in axis.values
            if v.name not in forbidden[axis.name]
            and all(r({**agreed, axis.name: v}) for r in shared_hard if _covers(r, {**agreed, axis.name: v}))
        ]
        negotiators = [
            AxisNegotiator(b, scenario, axis, space_values, agreed, n_steps_per_axis, log=log, comms=comms)
            for b in beliefs
        ] if space_values else []
        orch_log("axis_session_start", axis=axis.name,
                 space=[v.name for v in space_values],
                 agreed_prefix={k: v.name for k, v in agreed.items()})

        if not space_values or any(not n.mine for n in negotiators):
            agreement_name = None
        else:
            mechanism = SAOMechanism(
                outcome_space=make_os(issues=[make_issue([v.name for v in space_values], name=axis.name)]),
                n_steps=n_steps_per_axis,
            )
            for negotiator in negotiators:
                mechanism.add(negotiator)
            state = mechanism.run()
            rounds += int(getattr(state, "step", 0))
            proposals += sum(n.proposal_count for n in negotiators)
            agreement_name = mechanism.agreement[0] if mechanism.agreement else None

        if agreement_name is None:
            # 백트랙 — 직전 축 합의를 금지하고 재협상
            if i == 0 or backtracks >= max_backtracks:
                trace.append(f"{axis.name}: 진행 불가, 백트랙 소진 → 결렬")
                orch_log("sequential_breakdown", axis=axis.name, backtracks=backtracks,
                         reason="진행 불가 상태에서 백트랙 상한 소진")
                return SequentialResult(None, rounds, proposals, backtracks, comms=comms, trace=trace)
            prev = scenario.axes[i - 1]
            forbidden[prev.name].add(agreed[prev.name].name)
            trace.append(f"{axis.name}: 진행 불가 → {prev.name}={agreed[prev.name].name} 금지 후 백트랙")
            orch_log("backtrack", stuck_axis=axis.name, forbid_axis=prev.name,
                     forbid_value=agreed[prev.name].name,
                     reason="현재 축 세션 진행 불가(후보 없음/결렬)")
            del agreed[prev.name]
            backtracks += 1
            i -= 1
            continue

        agreed[axis.name] = next(v for v in space_values if v.name == agreement_name)
        trace.append(f"{axis.name} = {agreement_name}")
        orch_log("axis_agreed", axis=axis.name, value=agreement_name)
        i += 1

    # 최종 확인 — 잠정 합의를 각자 전체 효용으로 재검 (바닥선 미달이면 결렬)
    outcome: Outcome = dict(agreed)
    for b in beliefs:
        if not b.feasible(outcome) or b.utility(outcome) < b.initial_threshold:
            trace.append(f"최종 확인 실패 (참여자 {b.idx}) → 결렬")
            orch_log("final_confirm_failed", agent=b.idx,
                     utility=round(b.utility(outcome), 4), floor=b.initial_threshold,
                     reason="조립된 전체 합의가 이 참여자의 바닥선 미달")
            return SequentialResult(None, rounds, proposals, backtracks, comms=comms, trace=trace)
    orch_log("final_confirmed", agreement={k: v.name for k, v in agreed.items()})
    return SequentialResult(
        {name: value.name for name, value in agreed.items()}, rounds, proposals, backtracks,
        comms=comms, trace=trace,
    )
