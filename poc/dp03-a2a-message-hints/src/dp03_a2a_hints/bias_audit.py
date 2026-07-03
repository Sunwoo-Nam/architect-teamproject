from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from .models import Scenario
from .scenario_loader import load_scenario
from .validators import agreement_region, pareto_frontier, valid_outcomes


def audit_scenario_bias(
    scenario_dir: Path,
    comparison_path: Path | None = None,
) -> dict[str, Any]:
    scenarios = [load_scenario(path) for path in sorted(scenario_dir.glob("*.yaml"))]
    comparisons = _load_jsonl(comparison_path) if comparison_path and comparison_path.exists() else []
    audit = {
        "scenario_count": len(scenarios),
        "matrix_distribution": _matrix_distribution(scenarios),
        "domain_distribution": _domain_distribution(scenarios),
        "profile_distribution": _profile_distribution(scenarios),
        "difficulty_distribution": _difficulty_distribution(scenarios),
        "result_correlation": _result_correlation(comparisons),
    }
    audit["bias_warnings"] = _bias_warnings(audit)
    audit["augmentation_recommendations"] = _augmentation_recommendations(audit)
    return audit


def write_bias_audit(audit: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(audit, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )


def _matrix_distribution(scenarios: list[Scenario]) -> dict[str, Any]:
    return {
        "task_family": _counter(s.task_family for s in scenarios),
        "complexity_level": _counter(s.complexity_level for s in scenarios),
        "tension_pattern": _counter(s.tension_pattern for s in scenarios),
        "variant_id": _counter(s.variant_id for s in scenarios),
        "privacy_risk": _counter(s.privacy_labels.constraint_hint_accumulation_risk for s in scenarios),
        "external_constraint_hint_allowed": _counter(
            str(s.privacy_labels.external_constraint_hint_allowed).lower() for s in scenarios
        ),
    }


def _domain_distribution(scenarios: list[Scenario]) -> dict[str, Any]:
    issue_occurrences = Counter()
    issue_positions = Counter()
    issue_type_occurrences = Counter()
    outcome_counts = []
    for scenario in scenarios:
        count = 1
        for position, issue in enumerate(scenario.issues):
            issue_occurrences[issue.name] += 1
            issue_positions[f"{position + 1}:{issue.name}"] += 1
            issue_type_occurrences[issue.type] += 1
            count *= len(issue.values)
        outcome_counts.append(count)
    return {
        "issue_occurrences": dict(sorted(issue_occurrences.items())),
        "issue_position_occurrences": dict(sorted(issue_positions.items())),
        "issue_type_occurrences": dict(sorted(issue_type_occurrences.items())),
        "outcome_count": _numeric_summary(outcome_counts),
    }


def _profile_distribution(scenarios: list[Scenario]) -> dict[str, Any]:
    hard_constraint_count = []
    fixed_hint_count = []
    relaxable_hint_count = []
    hard_constraint_by_agent = Counter()
    hard_constraint_by_issue = Counter()
    hard_constraint_by_tension = Counter()
    fixed_hint_by_issue = Counter()
    relaxable_hint_by_issue = Counter()
    reservation_values = []
    weight_shapes = Counter()
    score_shapes = Counter()
    max_weight_issues = Counter()

    for scenario in scenarios:
        scenario_hard_count = 0
        scenario_fixed_count = 0
        scenario_relaxable_count = 0
        for agent in scenario.agents:
            profile = agent.private_profile
            scenario_hard_count += len(profile.hard_constraints)
            hard_constraint_by_agent[agent.id] += len(profile.hard_constraints)
            for constraint in profile.hard_constraints:
                hard_constraint_by_issue[constraint.issue] += 1
                hard_constraint_by_tension[scenario.tension_pattern] += 1

            for issue, hint in agent.allowed_constraint_hint.issue_constraints.items():
                if hint == "fixed":
                    scenario_fixed_count += 1
                    fixed_hint_by_issue[issue] += 1
                elif hint == "relaxable":
                    scenario_relaxable_count += 1
                    relaxable_hint_by_issue[issue] += 1

            reservation_values.append(profile.reservation_value)
            weights = tuple(sorted(round(value, 4) for value in profile.utility_weights.values()))
            weight_shapes[str(weights)] += 1
            max_weight = max(profile.utility_weights.values())
            for issue, weight in profile.utility_weights.items():
                if weight == max_weight:
                    max_weight_issues[issue] += 1
            for scores in profile.value_scores.values():
                score_shapes[str(tuple(sorted(scores.values(), reverse=True)))] += 1

        hard_constraint_count.append(scenario_hard_count)
        fixed_hint_count.append(scenario_fixed_count)
        relaxable_hint_count.append(scenario_relaxable_count)

    return {
        "hard_constraint_count_per_scenario": _numeric_summary(hard_constraint_count),
        "hard_constraint_by_agent": dict(sorted(hard_constraint_by_agent.items())),
        "hard_constraint_by_issue": dict(sorted(hard_constraint_by_issue.items())),
        "hard_constraint_by_tension": dict(sorted(hard_constraint_by_tension.items())),
        "fixed_hint_count_per_scenario": _numeric_summary(fixed_hint_count),
        "relaxable_hint_count_per_scenario": _numeric_summary(relaxable_hint_count),
        "fixed_hint_by_issue": dict(sorted(fixed_hint_by_issue.items())),
        "relaxable_hint_by_issue": dict(sorted(relaxable_hint_by_issue.items())),
        "reservation_value": _numeric_summary(reservation_values),
        "unique_weight_shape_count": len(weight_shapes),
        "top_weight_shapes": _top(weight_shapes, 8),
        "unique_score_shape_count": len(score_shapes),
        "top_score_shapes": _top(score_shapes, 8),
        "max_weight_issue_occurrences": dict(sorted(max_weight_issues.items())),
    }


def _difficulty_distribution(scenarios: list[Scenario]) -> dict[str, Any]:
    valid_counts = []
    agreement_counts = []
    agreement_ratios = []
    pareto_counts = []
    bins = Counter()
    for scenario in scenarios:
        outcome_count = 1
        for issue in scenario.issues:
            outcome_count *= len(issue.values)
        valid_count = len(valid_outcomes(scenario))
        agreement_count = len(agreement_region(scenario))
        ratio = agreement_count / outcome_count if outcome_count else 0.0
        valid_counts.append(valid_count)
        agreement_counts.append(agreement_count)
        agreement_ratios.append(ratio)
        pareto_counts.append(len(pareto_frontier(scenario)))
        bins[_agreement_ratio_bin(ratio)] += 1
    return {
        "valid_outcome_count": _numeric_summary(valid_counts),
        "agreement_region_count": _numeric_summary(agreement_counts),
        "agreement_region_ratio": _numeric_summary(agreement_ratios),
        "agreement_region_ratio_bins": dict(sorted(bins.items())),
        "pareto_candidate_count": _numeric_summary(pareto_counts),
    }


def _result_correlation(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    if not comparisons:
        return {}
    return {
        "scenario_count": len(comparisons),
        "round_outcome": _round_outcome_distribution(comparisons),
        "by_task_family": _comparison_breakdown(comparisons, "task_family"),
        "by_complexity_level": _comparison_breakdown(comparisons, "complexity_level"),
        "by_tension_pattern": _comparison_breakdown(comparisons, "tension_pattern"),
        "slower_top": _top_round_cases(comparisons, reverse=True),
        "faster_top": _top_round_cases(comparisons, reverse=False),
    }


def _round_outcome_distribution(comparisons: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for item in comparisons:
        delta = item["round_delta_a2_minus_a1"]
        if delta is None:
            counts["unknown"] += 1
        elif delta < 0:
            counts["a2_faster"] += 1
        elif delta > 0:
            counts["a2_slower"] += 1
        else:
            counts["same"] += 1
    return dict(sorted(counts.items()))


def _comparison_breakdown(comparisons: list[dict[str, Any]], axis: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in comparisons:
        grouped[str(item[axis])].append(item)

    result = {}
    for value, items in sorted(grouped.items()):
        round_deltas = [item["round_delta_a2_minus_a1"] for item in items if item["round_delta_a2_minus_a1"] is not None]
        utility_deltas = [
            item["joint_utility_delta_a2_minus_a1"]
            for item in items
            if item["joint_utility_delta_a2_minus_a1"] is not None
        ]
        result[value] = {
            "scenario_count": len(items),
            "a2_faster_count": sum(1 for delta in round_deltas if delta < 0),
            "a2_slower_count": sum(1 for delta in round_deltas if delta > 0),
            "a2_same_count": sum(1 for delta in round_deltas if delta == 0),
            "mean_round_delta_a2_minus_a1": mean(round_deltas) if round_deltas else None,
            "mean_joint_utility_delta_a2_minus_a1": mean(utility_deltas) if utility_deltas else None,
            "mean_a2_hint_count": mean(item["a2_constraint_hint_message_count"] for item in items),
            "mean_a2_sensitivity": mean(item["a2_constraint_hint_sensitivity_score"] for item in items),
        }
    return result


def _top_round_cases(comparisons: list[dict[str, Any]], reverse: bool) -> list[dict[str, Any]]:
    items = [
        item
        for item in comparisons
        if item["round_delta_a2_minus_a1"] is not None
        and ((item["round_delta_a2_minus_a1"] > 0) if reverse else (item["round_delta_a2_minus_a1"] < 0))
    ]
    sorted_items = sorted(items, key=lambda item: item["round_delta_a2_minus_a1"], reverse=reverse)
    fields = (
        "scenario_id",
        "task_family",
        "complexity_level",
        "tension_pattern",
        "variant_id",
        "round_delta_a2_minus_a1",
        "joint_utility_delta_a2_minus_a1",
        "a2_constraint_hint_message_count",
        "a2_constraint_hint_sensitivity_score",
    )
    return [{field: item[field] for field in fields} for item in sorted_items[:10]]


def _bias_warnings(audit: dict[str, Any]) -> list[dict[str, str]]:
    warnings = []
    profile = audit["profile_distribution"]
    matrix = audit["matrix_distribution"]
    difficulty = audit["difficulty_distribution"]
    result = audit["result_correlation"]

    if profile["unique_score_shape_count"] <= 3:
        warnings.append(
            {
                "code": "low_score_shape_diversity",
                "message": "value_scores 형태가 소수 패턴에 집중되어 utility profile 다양성이 낮다.",
            }
        )
    if profile["unique_weight_shape_count"] <= 6:
        warnings.append(
            {
                "code": "low_weight_shape_diversity",
                "message": "utility weight 형태가 제한되어 특정 협상 전략에 유리한 패턴이 반복될 수 있다.",
            }
        )
    if matrix["external_constraint_hint_allowed"].get("true") == audit["scenario_count"]:
        warnings.append(
            {
                "code": "no_hint_policy_negative_control",
                "message": "모든 generated scenario에서 external constraint hint가 허용되어 hint 정책 통제군이 없다.",
            }
        )
    if difficulty["agreement_region_ratio"]["min"] > 0:
        warnings.append(
            {
                "code": "no_impossible_or_empty_agreement_control",
                "message": "합의 불가능 또는 agreement region이 빈 통제군이 없다.",
            }
        )
    if result:
        budget = result["by_tension_pattern"].get("budget_quality_tradeoff")
        if budget and budget["a2_slower_count"] > budget["a2_faster_count"]:
            warnings.append(
                {
                    "code": "tension_pattern_specific_regression",
                    "message": "budget_quality_tradeoff에서 A2 slower가 faster보다 많아 tension 생성 규칙 편향 가능성이 있다.",
                }
            )
    return warnings


def _augmentation_recommendations(audit: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "code": "counterfactual_pairs",
            "message": "각 scenario에 ppa_a/ppa_b swap, issue order shuffle, value order reverse counterfactual을 추가한다.",
        },
        {
            "code": "difficulty_strata",
            "message": "agreement region ratio를 easy/medium/hard/borderline/no-agreement 층으로 나누어 quota를 맞춘다.",
        },
        {
            "code": "hint_policy_strata",
            "message": "no_hint, fixed_only, relaxable_only, fixed_plus_relaxable, first_offer_only, repeated 정책 축을 추가한다.",
        },
        {
            "code": "utility_shape_strata",
            "message": "sharp/flat/single-dominant/two-issue/asymmetric/near-tie utility shape을 별도 축으로 생성한다.",
        },
        {
            "code": "hard_constraint_balance",
            "message": "hard constraint 주체, 개수, issue, allowed_values 크기가 균등하게 나오도록 quota를 둔다.",
        },
    ]


def _numeric_summary(values: list[float | int]) -> dict[str, float | int | None]:
    if not values:
        return {"min": None, "max": None, "mean": None}
    return {
        "min": min(values),
        "max": max(values),
        "mean": mean(values),
    }


def _agreement_ratio_bin(value: float) -> str:
    if value == 0:
        return "empty"
    if value < 0.1:
        return "borderline"
    if value < 0.25:
        return "hard"
    if value < 0.5:
        return "medium"
    return "easy"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _counter(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _top(counter: Counter[str], limit: int) -> dict[str, int]:
    return dict(counter.most_common(limit))
