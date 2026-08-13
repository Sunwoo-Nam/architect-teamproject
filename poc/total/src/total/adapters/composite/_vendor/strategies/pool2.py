"""2안 개선판 pool2 — 유효-only 조건부 확장 + k 고정 + 충돌 축 교체 재협상.

현행 pool의 두 약점을 겨냥한다:
  (1) 곱 물질화가 무효 조합을 대량 생성(엇갈린 지역×식당) → 낭비 + 커버리지 얇음.
  (2) 막히면 deepening(k↑)뿐인데 k^n이 폭발.

pool2:
  (1) **조건부 확장**: 빈 부분조합에서 축을 하나씩 이어붙이되, 각 부분조합에 대해 그 축의
      '유효한' 값만 top-k로 붙인다. 그래서 만들어지는 후보는 **전부 유효**(무효 조합 0).
      region=강남 부분조합엔 강남 식당만 붙으므로 엇갈림이 없다.
  (2) **k 고정 + 충돌 축 교체**: deepening 안 함. 결렬 시 두 에이전트가 가장 합의 못 한 축을
      찾아 그 축의 현재 top-k를 제외하고(다음 값으로 교체) 재협상. 메모리는 라운드마다 일정.
"""
from __future__ import annotations

from negmas.sao import SAOMechanism

from total.adapters.composite._vendor.common.scenario import Scenario
from total.adapters.composite._vendor.harness.beliefs import AgentBeliefs
from total.adapters.composite._vendor.harness.comms import Comms
from total.adapters.composite._vendor.harness.eventlog import EventLog
from total.adapters.composite._vendor.harness.negmas_bridge import TupleCodec, make_outcome_space

from .negotiator_base import CandidateNegotiator


def _partial_hard_ok(hard_rules, partial) -> bool:
    """부분조합에 적용 가능한 하드 규칙만 검사(참조 축 없으면 통과)."""
    for rule in hard_rules:
        try:
            if not rule(partial):
                return False
        except KeyError:
            continue
    return True


def build_valid_candidates(scenario: Scenario, beliefs: AgentBeliefs, k: int,
                           excluded: dict[str, set[str]]) -> list[tuple[float, tuple]]:
    """조건부 확장 — 전부 유효한 후보만 생성(무효 조합 0). k^n 근처까지 커질 수 있다."""
    hard = list(beliefs.shared_hard) + list(beliefs.own_hard)
    axes = scenario.axes
    partials: list[dict] = [{}]
    for ax in axes:
        vals = [v for v in ax.values if v.name not in excluded.get(ax.name, set())]
        vals.sort(key=lambda v: -(beliefs.weights[ax.name] * beliefs.scores[ax.name][v.name]))
        new_partials: list[dict] = []
        for partial in partials:
            picked = 0
            for v in vals:
                trial = {**partial, ax.name: v}
                if _partial_hard_ok(hard, trial):     # 이 부분조합과 유효한 값만
                    new_partials.append(trial)
                    picked += 1
                    if picked >= k:
                        break
            # picked==0이면 이 부분조합은 죽는다(이어붙일 유효 값 없음)
        partials = new_partials
        if not partials:
            return []
    out: list[tuple[float, tuple]] = []
    for assign in partials:
        u = beliefs.utility(assign)
        if u >= beliefs.initial_threshold:
            out.append((u, tuple(assign[ax.name].name for ax in axes)))
    out.sort(key=lambda item: (-item[0], item[1]))
    return out


class Pool2Negotiator(CandidateNegotiator):
    """유효-only 후보 + k 고정(deepening 없음). 교체는 오케스트레이터가 excluded로 제어."""

    def __init__(self, scenario, beliefs, codec, n_steps, k=2, excluded=None,
                 log=None, comms=None):
        super().__init__(beliefs, codec, n_steps, name=f"pool2-{beliefs.idx}", log=log, comms=comms)
        self.scenario = scenario
        self.k = k
        self.excluded = excluded if excluded is not None else {}

    def _build_candidates(self):
        return build_valid_candidates(self.scenario, self.beliefs, self.k, self.excluded)

    def _replenish(self) -> bool:
        return False   # k 고정 — deepening 안 함(교체는 오케스트레이터 소관)


def _conflict_axis(scenario, beliefs, excluded, k) -> str | None:
    """두 에이전트가 가장 합의 못 한 축 = 각자 top-k(자기 선호)의 겹침이 가장 적은 축.
       이미 소진된(남은 값 ≤ k) 축은 제외."""
    best_axis, best_overlap = None, None
    for ax in scenario.axes:
        remaining = [v for v in ax.values if v.name not in excluded.get(ax.name, set())]
        if len(remaining) <= k:      # 더 교체할 값 없음
            continue
        tops = []
        for b in beliefs:
            r = sorted(remaining, key=lambda v: -(b.weights[ax.name] * b.scores[ax.name][v.name]))
            tops.append({v.name for v in r[:k]})
        overlap = len(tops[0] & tops[1])
        if best_overlap is None or overlap < best_overlap:
            best_overlap, best_axis = overlap, ax.name
    return best_axis


def run_pool2(scenario: Scenario, beliefs: list[AgentBeliefs], n_steps: int = 200,
              k: int = 2, max_swaps: int = 6, log: EventLog | None = None,
              comms: Comms | None = None):
    """k 고정 + 충돌 축 교체 재협상. 반환: (agreement|None, rounds, proposals, extra)."""
    comms = comms if comms is not None else Comms(n_participants=len(beliefs))
    codec = TupleCodec(scenario.axes)
    excluded: dict[str, set[str]] = {ax.name: set() for ax in scenario.axes}
    total_rounds = total_props = swaps = 0
    trace: list[str] = []

    for attempt in range(max_swaps + 1):
        mechanism = SAOMechanism(outcome_space=make_outcome_space(scenario.axes), n_steps=n_steps)
        negs = [Pool2Negotiator(scenario, b, codec, n_steps, k=k,
                                excluded=excluded, log=log, comms=comms) for b in beliefs]
        # 후보가 하나도 없는 에이전트가 있으면 이 라운드는 진행 불가
        if any(not n._ensure() for n in negs):
            trace.append(f"라운드 {attempt}: 유효 후보 없음")
        else:
            for n in negs:
                mechanism.add(n)
            state = mechanism.run()
            total_rounds += int(getattr(state, "step", 0))
            total_props += sum(n.proposal_count for n in negs)
            if mechanism.agreement:
                names = tuple(mechanism.agreement)
                agreement = {ax.name: nm for ax, nm in zip(scenario.axes, names)}
                trace.append(f"라운드 {attempt}: 합의")
                return agreement, total_rounds, total_props, {"swaps": swaps, "trace": trace}
            trace.append(f"라운드 {attempt}: 결렬")

        # 결렬 → 충돌 축의 현재 top-k를 제외(교체), k는 그대로
        caxis = _conflict_axis(scenario, beliefs, excluded, k)
        if caxis is None:
            trace.append("교체할 충돌 축 없음 → 결렬")
            break
        remaining = [v for v in scenario.axis(caxis).values if v.name not in excluded[caxis]]
        # 두 에이전트의 현재 top-k 합집합을 제외 → 다음 값으로 교체
        drop: set[str] = set()
        for b in beliefs:
            r = sorted(remaining, key=lambda v: -(b.weights[caxis] * b.scores[caxis][v.name]))
            drop |= {v.name for v in r[:k]}
        excluded[caxis] |= drop
        swaps += 1
        trace.append(f"충돌 축 '{caxis}' top-k 교체(제외 {sorted(drop)})")

    return None, total_rounds, total_props, {"swaps": swaps, "trace": trace}
