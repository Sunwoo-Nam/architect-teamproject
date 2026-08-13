"""에이전트 신념(beliefs) — 각 에이전트가 실제로 아는 것만 담는다.

- agent_view(양자화 가중치 + 마스킹 점수): 정답 프로파일의 부분 정보 (순환 판정 차단)
- 자기 initial_threshold(위임 바닥선)와 자기 home_region
- 자기 참여자 하드 제약 (상대 캘린더는 모른다)
- 공유 세계 규칙: 축 간 의존성(상영표·소속·soft 규칙)은 공개 정보
"""
from __future__ import annotations

from dataclasses import dataclass

from total.adapters.composite._vendor.common.profiles import build_truth_profiles, derive_agent_view
from total.adapters.composite._vendor.common.rules import (
    HardRule,
    Outcome,
    SoftRule,
    build_hard_rules,
    build_participant_hard_for,
    build_soft_rules,
)
from total.adapters.composite._vendor.common.scenario import Scenario


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
    #: [이식 시 신설] 효용 평가 호출 수 — 24 §6.4-a의 eval 항 입력.
    #: 원본 dpca에는 계측이 없어 어댑터가 `참여자 수 × 후보 수` 공식으로 추정했는데,
    #: 그 값은 방안에 의존하지 않아 방안을 구분하지 못했다. nparty 쪽은 처음부터
    #: 실측 카운트라, 같은 항의 입력을 두 시나리오가 다른 방법으로 만들고 있었다.
    evals: int = 0

    def note_eval(self) -> None:
        """효용 평가 1회 계상.

        `utility()`를 거치지 않고 `weights`·`scores`를 직접 읽어 효용값을 만드는
        곳이 있다 (1안 `sequential.py`의 `_optimistic`·`_score`). 그쪽도 평가는
        평가이므로 같은 계수기로 세야 한다 — `utility()` 호출만 세면 1안이
        실제보다 세 자릿수 적게 잡힌다 (S01에서 2회 대 수천 회).

        **알려진 보수성**: 1안의 축 단위 평가는 전체 조합 1건 평가보다 싸다.
        합성 시간 모델은 `t_eval` 상수 하나를 모든 호출에 똑같이 곱하므로,
        1안의 eval 항은 **상한**으로 봐야 한다 (24 §6.4-a의 단일 상수 가정).
        """
        self.evals += 1

    def utility(self, outcome: Outcome) -> float:
        self.evals += 1
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
