"""정답 프로파일(판정기 전용·봉인)과 에이전트 뷰(부분 정보) 생성.

- 수치(가중치·값 점수)는 profile_seed로 결정론 생성, 구조(제약·의존성)는 TC 고정.
- 충돌 강도는 P1 점수와 P2 점수의 상관(conflict_rho)으로 통제한다.
- 순환 판정 차단(21.3-1): 판정은 정답 프로파일로, 에이전트는 agent_view 파생 정보만 받는다.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .generators import REGIONS
from .rules import Outcome, SoftRule
from .scenario import Scenario

_STYLE_ALPHA = {"default": 1.0, "focused": 0.3, "indifferent": 5.0}
_STYLE_SCORE_RANGE = {"default": (0.0, 1.0), "focused": (0.0, 1.0), "indifferent": (0.4, 0.6)}


@dataclass
class TruthProfile:
    weights: dict[str, float]              # 축 -> 가중치 (합 1)
    scores: dict[str, dict[str, float]]    # 축 -> {값: 점수 0..1}
    home_region: str
    initial_threshold: float               # 위임 시점 바닥선 — 결렬 시 얻는 utility (24.2)

    def base_utility(self, outcome: Outcome) -> float:
        return sum(self.weights[a] * self.scores[a][v.name] for a, v in outcome.items())


@dataclass
class AgentView:
    """에이전트에 주어지는 부분 정보 — 양자화 가중치 + 점수 일부 마스킹."""
    weights: dict[str, float]
    scores: dict[str, dict[str, float]]


def _dirichlet(rng: random.Random, n: int, alpha: float) -> list[float]:
    xs = [rng.gammavariate(alpha, 1.0) for _ in range(n)]
    total = sum(xs) or 1.0
    return [x / total for x in xs]


def _normalize(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def build_truth_profiles(scenario: Scenario) -> list[TruthProfile]:
    seed = scenario.profile_seed
    styles = scenario.participants.get("styles", ["default"] * scenario.n_participants)
    rho = float(scenario.meta.get("conflict_rho", 0.0))
    thresholds = scenario.participants.get("initial_threshold", [0.4] * scenario.n_participants)
    if isinstance(thresholds, (int, float)):
        thresholds = [float(thresholds)] * scenario.n_participants
    profiles: list[TruthProfile] = []
    p1_scores: dict[str, list[float]] = {}

    for p in range(scenario.n_participants):
        rng = random.Random(f"{scenario.id}-truth-{seed}-p{p}")
        alpha = _STYLE_ALPHA[styles[p]]
        lo, hi = _STYLE_SCORE_RANGE[styles[p]]
        raw_weights = _dirichlet(rng, len(scenario.axes), alpha)
        weights = {ax.name: w for ax, w in zip(scenario.axes, raw_weights)}

        scores: dict[str, dict[str, float]] = {}
        for ax in scenario.axes:
            n = len(ax.values)
            if p == 0:
                vals = [rng.random() for _ in range(n)]
                p1_scores[ax.name] = vals
            else:
                # P2 점수 = rho·P1 + sqrt(1-rho²)·noise → 정규화. 충돌 강도(상관) 통제.
                base = p1_scores[ax.name]
                noise = [rng.random() for _ in range(n)]
                mixed = [rho * b + math.sqrt(max(0.0, 1 - rho * rho)) * z for b, z in zip(base, noise)]
                vals = _normalize(mixed)
            vals = [lo + v * (hi - lo) for v in vals]
            scores[ax.name] = {value.name: s for value, s in zip(ax.values, vals)}

        home = REGIONS[rng.randrange(len(REGIONS))]
        profiles.append(
            TruthProfile(
                weights=weights,
                scores=scores,
                home_region=home,
                initial_threshold=float(thresholds[p]),
            )
        )
    return profiles


def truth_utility(profile: TruthProfile, p_idx: int, outcome: Outcome, soft_rules: list[SoftRule]) -> float:
    penalty = sum(rule(p_idx, outcome) for rule in soft_rules)
    return max(0.0, profile.base_utility(outcome) - penalty)


def derive_agent_view(scenario: Scenario, truth: TruthProfile, p_idx: int) -> AgentView:
    spec = scenario.agent_view
    rng = random.Random(f"{scenario.id}-view-{scenario.profile_seed}-p{p_idx}")

    weights = dict(truth.weights)
    if spec.get("weights") == "quantized3":
        ranked = sorted(weights, key=weights.get, reverse=True)
        n = len(ranked)
        levels = {}
        for i, axis in enumerate(ranked):
            levels[axis] = 3.0 if i < max(1, n // 3) else (2.0 if i < max(2, 2 * n // 3) else 1.0)
        total = sum(levels.values())
        weights = {a: v / total for a, v in levels.items()}

    dropout = float(spec.get("score_dropout", 0.0))
    scores = {
        axis: {
            name: (0.5 if rng.random() < dropout else s)
            for name, s in per_axis.items()
        }
        for axis, per_axis in truth.scores.items()
    }
    return AgentView(weights=weights, scores=scores)
