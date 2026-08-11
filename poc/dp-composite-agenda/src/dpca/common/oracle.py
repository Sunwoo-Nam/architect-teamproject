"""oracle — 기본 크기에서 전수 열거로 TC를 검증하고 FC 채점 기준을 산출한다.

FC 정본(docs/changbae/24-Functional-Correctness-정의-측정.md)을 따른다:
  - 유효 후보 = 하드 제약 통과 ∧ 전원 utility ≥ 각자 initial threshold. 결렬 후보(전원이
    자기 threshold를 얻음)는 항상 유효 후보에 포함된다.
  - x* = 유효 후보 중 total utility 최대 — "도달할 수 있었던 가장 좋은 결과".
  - 달성률 = U(r) ÷ U(x*). 무작위 베이스라인 R̄ = 유효 후보 무작위 선택의 평균 달성률.
  - 유효 후보가 결렬뿐이면 x* = 결렬 — "결렬이 정답"이 자동 처리된다.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

from .profiles import build_truth_profiles, truth_utility
from .rules import Outcome, build_hard_rules, build_participant_hard, build_soft_rules
from .scenario import Scenario


@dataclass
class OracleReport:
    scenario_id: str
    space_size: int
    feasible_count: int        # 하드 제약(의존성 + 참여자) 통과 후보 수
    valid_count: int           # 유효 후보 수 (결렬 제외 — 전원 threshold 이상)
    xstar_is_breakdown: bool   # x*가 결렬 후보인가 ("결렬이 정답" 여부)
    u_xstar: float             # U(x*) — 달성률의 분모
    breakdown_total: float     # 결렬 후보의 total utility (= 전원 threshold 합)
    r_bar: float               # 무작위 베이스라인 — 유효 후보(결렬 포함) 무작위 선택의 평균 달성률
    utility_corr: float | None # 정답 효용 상관 (충돌 라벨 검증용)
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


def analyze(scenario: Scenario, enumeration_limit: int = 200_000) -> OracleReport:
    size = scenario.space_size()
    if size > enumeration_limit:
        return OracleReport(scenario.id, size, -1, -1, False, 0.0, 0.0, 0.0, None, -1,
                            skipped=True, notes=[f"공간 {size} > 한도 {enumeration_limit}, oracle 생략"])

    truths = build_truth_profiles(scenario)
    hard = build_hard_rules(scenario) + build_participant_hard(scenario)
    soft = build_soft_rules(scenario, [t.home_region for t in truths])
    thresholds = [t.initial_threshold for t in truths]
    breakdown_total = sum(thresholds)

    axis_names = scenario.axis_names()
    utils: list[list[float]] = [[] for _ in truths]
    for combo in itertools.product(*[ax.values for ax in scenario.axes]):
        outcome: Outcome = dict(zip(axis_names, combo))
        if not all(rule(outcome) for rule in hard):
            continue
        for p, truth in enumerate(truths):
            utils[p].append(truth_utility(truth, p, outcome, soft))

    feasible_count = len(utils[0])
    corr = _pearson(utils[0], utils[1]) if len(truths) >= 2 and feasible_count >= 3 else None

    # 유효 후보(결렬 제외): 전원이 각자 threshold 이상
    valid_totals = [
        sum(utils[p][i] for p in range(len(truths)))
        for i in range(feasible_count)
        if all(utils[p][i] >= thresholds[p] for p in range(len(truths)))
    ]

    # x* 선정 — 결렬 후보는 항상 유효 후보에 포함된다 (24.2/24.3)
    candidate_totals = valid_totals + [breakdown_total]
    u_xstar = max(candidate_totals)
    xstar_is_breakdown = not valid_totals or breakdown_total >= max(valid_totals)

    r_bar = (sum(candidate_totals) / len(candidate_totals)) / u_xstar if u_xstar > 0 else 0.0

    pareto = _pareto_count(utils) if feasible_count else 0
    return OracleReport(
        scenario.id, size, feasible_count, len(valid_totals),
        xstar_is_breakdown, u_xstar, breakdown_total, r_bar, corr, pareto,
    )


def _pareto_count(utils: list[list[float]]) -> int:
    points = list(zip(*utils))
    points_sorted = sorted(set(points), key=lambda t: (-t[0], -t[1]))
    count, best_u2 = 0, -1.0
    for u1, u2 in points_sorted:
        if u2 > best_u2:
            count += 1
            best_u2 = u2
    return count
