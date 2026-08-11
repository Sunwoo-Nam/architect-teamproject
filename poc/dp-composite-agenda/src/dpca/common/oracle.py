"""oracle — 기본 크기에서 전수 열거로 TC 자체를 검증한다.

산출: 실행 가능 후보 수, 정답 효용 상관(충돌 라벨 검증), 상호 수락 가능해 존재(수용선 분위수 기준),
Pareto frontier. FC 판정의 수용선(floor)과 Pareto 거리의 기준값도 여기서 나온다.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

from .profiles import TruthProfile, build_truth_profiles, truth_utility
from .rules import Outcome, build_hard_rules, build_participant_hard, build_soft_rules
from .scenario import Scenario


@dataclass
class OracleReport:
    scenario_id: str
    space_size: int
    feasible_count: int
    utility_corr: float | None
    floors: list[float]
    mutual_count: int          # 전원 수용선 이상인 후보 수 (0이면 합의 가능해 부재)
    pareto_count: int
    skipped: bool = False
    notes: list[str] = field(default_factory=list)


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    vy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if vx < 1e-12 or vy < 1e-12:
        return None
    return cov / (vx * vy)


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, round(q * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


def analyze(scenario: Scenario, enumeration_limit: int = 200_000) -> OracleReport:
    size = scenario.space_size()
    if size > enumeration_limit:
        return OracleReport(scenario.id, size, -1, None, [], -1, -1, skipped=True,
                            notes=[f"공간 {size} > 한도 {enumeration_limit}, oracle 생략"])

    truths = build_truth_profiles(scenario)
    hard = build_hard_rules(scenario) + build_participant_hard(scenario)
    soft = build_soft_rules(scenario, [t.home_region for t in truths])

    axis_names = scenario.axis_names()
    feasible: list[Outcome] = []
    utils: list[list[float]] = [[] for _ in truths]
    for combo in itertools.product(*[ax.values for ax in scenario.axes]):
        outcome: Outcome = dict(zip(axis_names, combo))
        if not all(rule(outcome) for rule in hard):
            continue
        feasible.append(outcome)
        for p, truth in enumerate(truths):
            utils[p].append(truth_utility(truth, p, outcome, soft))

    if not feasible:
        return OracleReport(scenario.id, size, 0, None, [], 0, 0)

    corr = _pearson(utils[0], utils[1]) if len(truths) >= 2 else None

    quantiles = scenario.judge.get("floor_quantile", [0.7] * len(truths))
    if isinstance(quantiles, (int, float)):
        quantiles = [float(quantiles)] * len(truths)
    floors = [_quantile(sorted(utils[p]), float(quantiles[p])) for p in range(len(truths))]

    mutual = sum(
        1 for i in range(len(feasible))
        if all(utils[p][i] >= floors[p] for p in range(len(truths)))
    )

    pareto = _pareto_count(utils)
    return OracleReport(scenario.id, size, len(feasible), corr, floors, mutual, pareto)


def _pareto_count(utils: list[list[float]]) -> int:
    points = list(zip(*utils))
    points_sorted = sorted(set(points), key=lambda t: (-t[0], -t[1]))
    count, best_u2 = 0, -1.0
    for u1, u2 in points_sorted:
        if u2 > best_u2:
            count += 1
            best_u2 = u2
    return count
