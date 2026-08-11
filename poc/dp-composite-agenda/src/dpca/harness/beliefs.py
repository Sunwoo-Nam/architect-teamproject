"""에이전트 신념(beliefs) — 각 에이전트가 실제로 아는 것만 담는다.

- agent_view(양자화 가중치 + 마스킹 점수): 정답 프로파일의 부분 정보 (순환 판정 차단)
- 자기 initial_threshold(위임 바닥선)와 자기 home_region
- 자기 참여자 하드 제약 (상대 캘린더는 모른다)
- 공유 세계 규칙: 축 간 의존성(상영표·소속·soft 규칙)은 공개 정보
"""
from __future__ import annotations

from dataclasses import dataclass

from dpca.common.profiles import build_truth_profiles, derive_agent_view
from dpca.common.rules import (
    HardRule,
    Outcome,
    SoftRule,
    build_hard_rules,
    build_participant_hard_for,
    build_soft_rules,
)
from dpca.common.scenario import Scenario


@dataclass
class AgentBeliefs:
    idx: int
    weights: dict[str, float]
    scores: dict[str, dict[str, float]]
    home_region: str
    initial_threshold: float
    shared_hard: list[HardRule]
    own_hard: list[HardRule]
    soft: list[SoftRule]

    def utility(self, outcome: Outcome) -> float:
        base = sum(self.weights[a] * self.scores[a][v.name] for a, v in outcome.items())
        penalty = sum(rule(self.idx, outcome) for rule in self.soft)
        return max(0.0, base - penalty)

    def feasible(self, outcome: Outcome) -> bool:
        return all(r(outcome) for r in self.shared_hard) and all(r(outcome) for r in self.own_hard)


def build_beliefs(scenario: Scenario) -> list[AgentBeliefs]:
    truths = build_truth_profiles(scenario)
    homes = [t.home_region for t in truths]
    shared_hard = build_hard_rules(scenario)
    soft = build_soft_rules(scenario, homes)
    beliefs = []
    for p, truth in enumerate(truths):
        view = derive_agent_view(scenario, truth, p)
        beliefs.append(
            AgentBeliefs(
                idx=p,
                weights=view.weights,
                scores=view.scores,
                home_region=truth.home_region,
                initial_threshold=truth.initial_threshold,
                shared_hard=shared_hard,
                own_hard=build_participant_hard_for(scenario, p),
                soft=soft,
            )
        )
    return beliefs
