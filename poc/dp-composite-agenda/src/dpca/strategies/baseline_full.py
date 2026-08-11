"""baseline — 현행 PoC 방식의 전수 나열 (c ≈ 1 앵커·대조군).

전체 카테시안 곱을 물질화해 자기 기준 유효 후보를 전부 점수화·정렬한다.
의도적으로 메모리를 조합 수에 비례해 쓴다 — 개선 전략들의 비교 기준선.
"""
from __future__ import annotations

import itertools

from dpca.common.scenario import Scenario
from dpca.harness.beliefs import AgentBeliefs
from dpca.harness.negmas_bridge import TupleCodec

from .negotiator_base import CandidateNegotiator


class FullEnumNegotiator(CandidateNegotiator):
    def __init__(self, scenario: Scenario, beliefs: AgentBeliefs, codec: TupleCodec, n_steps: int):
        super().__init__(beliefs, codec, n_steps, name=f"full-{beliefs.idx}")
        self.scenario = scenario

    def _build_candidates(self) -> list[tuple[float, tuple]]:
        axis_names = self.scenario.axis_names()
        out: list[tuple[float, tuple]] = []
        for combo in itertools.product(*[ax.values for ax in self.scenario.axes]):
            outcome = dict(zip(axis_names, combo))
            if not self.beliefs.feasible(outcome):
                continue
            utility = self.beliefs.utility(outcome)
            if utility >= self.beliefs.initial_threshold:
                out.append((utility, tuple(v.name for v in combo)))
        out.sort(key=lambda item: (-item[0], item[1]))
        return out
