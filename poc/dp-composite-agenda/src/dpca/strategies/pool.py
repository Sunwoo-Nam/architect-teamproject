"""2안 — 개인별 후보군 압축 후 복합 협상.

각 에이전트가 로컬에서 축별 top-k(선언 순서로 조건부 필터)를 뽑아 자기 후보풀(kⁿ)을
만들고, 원본 OutcomeSpace 위 한 세션에서 풀의 후보만 제안한다. 압축 결과는 공유하지 않는다.
양보선 이상의 새 제안이 소진되면 k를 늘려 재압축한다(deepening — 세션 내 로컬, 프로토콜 무영향).
"""
from __future__ import annotations

import itertools

from dpca.common.generators import Value
from dpca.common.rules import build_hard_rules
from dpca.common.scenario import Scenario
from dpca.harness.beliefs import AgentBeliefs
from dpca.harness.eventlog import EventLog
from dpca.harness.negmas_bridge import TupleCodec

from .negotiator_base import CandidateNegotiator


class PoolNegotiator(CandidateNegotiator):
    def __init__(
        self,
        scenario: Scenario,
        beliefs: AgentBeliefs,
        codec: TupleCodec,
        n_steps: int,
        k_start: int = 2,
        log: EventLog | None = None,
    ):
        super().__init__(beliefs, codec, n_steps, name=f"pool-{beliefs.idx}", log=log)
        self.scenario = scenario
        self.k = k_start
        self.k_max = max(len(ax.values) for ax in scenario.axes)
        self.deepening_count = 0
        # 하드 의존성 (스펙, 검사기) 쌍 — build_hard_rules는 active_dependencies의 hard를
        # 순서대로 하나씩 만들므로 인덱스가 정렬된다. 압축 시 짝 단위 양립 검사에 쓴다.
        hard_specs = [d for d in scenario.active_dependencies() if d["type"] == "hard"]
        self._hard_pairs = list(zip(hard_specs, build_hard_rules(scenario)))

    def _marginal(self, axis: str, value: Value) -> float:
        return self.beliefs.weights[axis] * self.beliefs.scores[axis][value.name]

    def _compress(self) -> dict[str, list[Value]]:
        """축별 top-k — 선언 순서로 진행하며 앞 축의 선택과 양립하는 값을 우선한다."""
        selected: dict[str, list[Value]] = {}
        for ax in self.scenario.axes:
            ranked = sorted(ax.values, key=lambda v: -self._marginal(ax.name, v))
            compatible = [v for v in ranked if self._compatible(ax.name, v, selected)]
            pick = compatible[: self.k]
            if len(pick) < self.k:  # 양립 후보 부족 시 비양립까지 채움 (풀 필터가 최종 방어)
                pick += [v for v in ranked if v not in pick][: self.k - len(pick)]
            selected[ax.name] = pick
        return selected

    def _compatible(self, axis: str, value: Value, selected: dict[str, list[Value]]) -> bool:
        """앞서 선택된 축들과의 짝 단위 양립 — membership·availability는 두 축만 보므로 충분하다."""
        for dep, check in self._hard_pairs:
            if dep["rule"] == "membership" and dep["subject"] == axis and dep["region_axis"] in selected:
                regions = {v.name for v in selected[dep["region_axis"]]}
                if value.attrs.get("region") not in regions:
                    return False
            elif dep["rule"] == "availability" and dep["subject"] == axis and dep["over"] in selected:
                if not any(
                    check({axis: value, dep["over"]: over_value})
                    for over_value in selected[dep["over"]]
                ):
                    return False
        return True

    def _build_candidates(self) -> list[tuple[float, tuple]]:
        selected = self._compress()
        axis_names = self.scenario.axis_names()
        out: list[tuple[float, tuple]] = []
        for combo in itertools.product(*[selected[name] for name in axis_names]):
            outcome = dict(zip(axis_names, combo))
            if not self.beliefs.feasible(outcome):
                continue
            utility = self.beliefs.utility(outcome)
            if utility >= self.beliefs.initial_threshold:
                out.append((utility, tuple(v.name for v in combo)))
        out.sort(key=lambda item: (-item[0], item[1]))
        return out

    def _replenish(self) -> bool:
        if self.k >= self.k_max:
            self._log("deepening_exhausted", k=self.k, reason="k가 축 최대 크기에 도달")
            return False
        self.k += 1
        self.deepening_count += 1
        self._candidates = None  # 재압축
        self._log("deepening", k=self.k, reason="양보선이 풀 하한 아래로 — k 확장 재압축")
        return True
