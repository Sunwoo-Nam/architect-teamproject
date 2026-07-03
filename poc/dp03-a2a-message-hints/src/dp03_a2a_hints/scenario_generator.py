from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Any

import yaml

TASK_FAMILIES = ("schedule_coordination", "venue_reservation", "group_purchase", "service_visit")
COMPLEXITY_LEVELS = ("issue_3", "issue_4", "issue_5")
TENSION_PATTERNS = (
    "aligned_preferences",
    "one_hard_constraint",
    "mutual_hard_constraint_conflict",
    "budget_quality_tradeoff",
    "time_location_tradeoff",
)
VARIANTS = ("v01", "v02", "v03")

ISSUE_CATALOG: dict[str, tuple[dict[str, Any], ...]] = {
    "schedule_coordination": (
        {"name": "slot", "type": "enum", "values": ("weekday_evening", "saturday_lunch", "sunday_evening")},
        {"name": "duration_band", "type": "bucket", "values": ("short", "standard", "extended")},
        {"name": "notice_period", "type": "bucket", "values": ("same_day", "one_day", "three_days")},
        {"name": "location_band", "type": "enum", "values": ("near_home", "midpoint", "near_office")},
        {"name": "budget_band", "type": "bucket", "values": ("low", "medium", "high")},
    ),
    "venue_reservation": (
        {"name": "slot", "type": "enum", "values": ("weekday_evening", "saturday_lunch", "sunday_evening")},
        {"name": "area", "type": "enum", "values": ("near_home", "midpoint", "near_office")},
        {"name": "budget_band", "type": "bucket", "values": ("low", "medium", "high")},
        {"name": "crowding_level", "type": "bucket", "values": ("low", "medium", "high")},
        {"name": "option_level", "type": "ordinal", "values": ("basic", "standard", "premium")},
    ),
    "group_purchase": (
        {"name": "price_band", "type": "bucket", "values": ("low", "medium", "high")},
        {"name": "quality_tier", "type": "ordinal", "values": ("basic", "standard", "premium")},
        {"name": "delivery_window", "type": "bucket", "values": ("express", "standard", "flexible")},
        {"name": "warranty_level", "type": "ordinal", "values": ("none", "basic", "extended")},
        {"name": "privacy_option", "type": "ordinal", "values": ("minimal", "standard", "enhanced")},
    ),
    "service_visit": (
        {"name": "visit_window", "type": "enum", "values": ("morning", "afternoon", "evening")},
        {"name": "service_scope", "type": "ordinal", "values": ("basic", "standard", "extended")},
        {"name": "access_method", "type": "enum", "values": ("remote", "supervised", "unattended")},
        {"name": "notice_period", "type": "bucket", "values": ("same_day", "one_day", "three_days")},
        {"name": "cost_band", "type": "bucket", "values": ("low", "medium", "high")},
    ),
}

TIME_HINTS = ("slot", "visit_window", "delivery_window", "notice_period")
LOCATION_HINTS = ("area", "location_band", "access_method")
BUDGET_HINTS = ("budget_band", "price_band", "cost_band")
QUALITY_HINTS = (
    "quality_tier",
    "option_level",
    "service_scope",
    "duration_band",
    "warranty_level",
    "privacy_option",
)


def generate_scenarios(variant_count: int = 2) -> list[dict[str, Any]]:
    if variant_count not in {2, 3}:
        raise ValueError("variant_count must be 2 for 120 scenarios or 3 for 180 scenarios")

    scenarios = []
    sequence = 1
    for task_family, complexity_level, tension_pattern, variant_id in product(
        TASK_FAMILIES,
        COMPLEXITY_LEVELS,
        TENSION_PATTERNS,
        VARIANTS[:variant_count],
    ):
        scenario = build_scenario(
            scenario_id=f"S{sequence:03d}",
            task_family=task_family,
            complexity_level=complexity_level,
            tension_pattern=tension_pattern,
            variant_id=variant_id,
            seed=200000 + sequence,
        )
        scenarios.append(scenario)
        sequence += 1
    return scenarios


def build_scenario(
    *,
    scenario_id: str,
    task_family: str,
    complexity_level: str,
    tension_pattern: str,
    variant_id: str,
    seed: int,
) -> dict[str, Any]:
    issue_count = int(complexity_level.split("_")[1])
    issues = [_issue(raw) for raw in ISSUE_CATALOG[task_family][:issue_count]]
    agent_a, agent_b = _agent_profiles(issues, tension_pattern, variant_id)
    _tune_reservations(issues, agent_a["private_profile"], agent_b["private_profile"])
    return {
        "schema_version": "scenario.v1",
        "scenario_id": scenario_id,
        "task_family": task_family,
        "complexity_level": complexity_level,
        "tension_pattern": tension_pattern,
        "variant_id": variant_id,
        "domain": {"issues": issues},
        "agents": (agent_a, agent_b),
        "privacy_labels": {
            "pii_raw": False,
            "sensitive_reason_present": False,
            "exact_value_present": False,
            "constraint_hint_accumulation_risk": _risk_for(tension_pattern),
            "external_constraint_hint_allowed": True,
        },
        "expected_checks": {
            "has_agreement_region": True,
            "expected_fallback": False,
            "expected_timeout_possible": tension_pattern == "mutual_hard_constraint_conflict",
            "min_valid_outcomes": 3,
            "min_pareto_candidates": 1,
            "llm_schema_required": True,
        },
        "generation_meta": {
            "generator_version": "gen.v2",
            "seed": seed,
            "source": "synthetic_matrix",
            "created_from_legacy_poc": False,
        },
    }


def write_scenarios(scenarios: list[dict[str, Any]], output_dir: Path, clean: bool = True) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if clean:
        for path in output_dir.glob("*.yaml"):
            path.unlink()
    for scenario in scenarios:
        filename = "-".join(
            (
                scenario["scenario_id"],
                scenario["task_family"],
                scenario["complexity_level"],
                scenario["tension_pattern"],
                scenario["variant_id"],
            )
        )
        path = output_dir / f"{filename}.yaml"
        path.write_text(
            yaml.safe_dump(scenario, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


def _issue(raw: dict[str, Any]) -> dict[str, Any]:
    issue = {
        "name": raw["name"],
        "type": raw["type"],
        "values": list(raw["values"]),
        "public": True,
        "outcome_space": True,
        "constraint_hintable": True,
    }
    if raw["type"] in {"ordinal", "bucket"}:
        issue["order"] = list(raw["values"])
    return issue


def _agent_profiles(
    issues: list[dict[str, Any]],
    tension_pattern: str,
    variant_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    variant_index = VARIANTS.index(variant_id)
    names = [issue["name"] for issue in issues]
    time_axis = _find_axis(names, TIME_HINTS, 0)
    location_axis = _find_axis(names, LOCATION_HINTS, min(1, len(names) - 1))
    budget_axis = _find_axis(names, BUDGET_HINTS, len(names) - 1)
    quality_axis = _find_axis(names, QUALITY_HINTS, min(1, len(names) - 1))
    primary_axis = names[variant_index % len(names)]
    secondary_axis = names[(variant_index + 1) % len(names)]

    preferences_a = {name: (idx + variant_index) % 3 for idx, name in enumerate(names)}
    preferences_b = {name: (idx + variant_index + 1) % 3 for idx, name in enumerate(names)}
    emphasis_a: tuple[str, ...] = ()
    emphasis_b: tuple[str, ...] = ()
    hard_a: dict[str, int] = {}
    hard_b: dict[str, int] = {}

    if tension_pattern == "aligned_preferences":
        preferences_b = dict(preferences_a)
    elif tension_pattern == "one_hard_constraint":
        hard_a[primary_axis] = preferences_a[primary_axis]
        preferences_b[primary_axis] = _opposite(preferences_a[primary_axis])
        emphasis_a = (primary_axis,)
    elif tension_pattern == "mutual_hard_constraint_conflict":
        hard_a[primary_axis] = preferences_a[primary_axis]
        hard_b[secondary_axis] = preferences_b[secondary_axis]
        preferences_b[primary_axis] = _opposite(preferences_a[primary_axis])
        preferences_a[secondary_axis] = _opposite(preferences_b[secondary_axis])
        emphasis_a = (primary_axis,)
        emphasis_b = (secondary_axis,)
    elif tension_pattern == "budget_quality_tradeoff":
        preferences_a[budget_axis] = 0
        preferences_b[budget_axis] = 2
        preferences_a[quality_axis] = 0
        preferences_b[quality_axis] = 2
        emphasis_a = (budget_axis,)
        emphasis_b = (quality_axis,)
    elif tension_pattern == "time_location_tradeoff":
        preferences_a[time_axis] = variant_index % 3
        preferences_b[time_axis] = _opposite(preferences_a[time_axis])
        preferences_a[location_axis] = (variant_index + 1) % 3
        preferences_b[location_axis] = _opposite(preferences_a[location_axis])
        emphasis_a = (time_axis,)
        emphasis_b = (location_axis,)

    profile_a = _profile(issues, preferences_a, emphasis_a, hard_a)
    profile_b = _profile(issues, preferences_b, emphasis_b, hard_b)
    return (
        _agent("ppa_a", "initiator", profile_a, _allowed_constraint_hint(names, profile_a, preferences_a)),
        _agent("ppa_b", "responder", profile_b, _allowed_constraint_hint(names, profile_b, preferences_b)),
    )


def _agent(
    agent_id: str,
    role: str,
    profile: dict[str, Any],
    allowed_constraint_hint: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": agent_id,
        "role": role,
        "capability": {
            "constraint_hint": True,
            "constraint_hint_schema_version": "constraint_hint.v1",
        },
        "private_profile": profile,
        "allowed_constraint_hint": allowed_constraint_hint,
    }


def _profile(
    issues: list[dict[str, Any]],
    preferences: dict[str, int],
    emphasis: tuple[str, ...],
    hard_constraints: dict[str, int],
) -> dict[str, Any]:
    weights = _weights([issue["name"] for issue in issues], emphasis)
    return {
        "utility_model": "linear_additive",
        "utility_weights": weights,
        "value_scores": {
            issue["name"]: _scores(issue["values"], preferences[issue["name"]])
            for issue in issues
        },
        "hard_constraints": [
            {
                "issue": issue_name,
                "allowed_values": _allowed_values_for_preference(
                    _values_for(issues, issue_name),
                    preferred_index,
                ),
            }
            for issue_name, preferred_index in hard_constraints.items()
        ],
        "reservation_value": 0.58,
        "concession_policy": {
            "type": "linear",
            "start_threshold": 0.9,
            "end_threshold": 0.58,
        },
    }


def _weights(issue_names: list[str], emphasis: tuple[str, ...]) -> dict[str, float]:
    units = {name: 2 for name in issue_names}
    for name in emphasis:
        units[name] += 3
    total = sum(units.values())
    weights = {name: round(units[name] / total, 4) for name in issue_names}
    last = issue_names[-1]
    weights[last] = round(1.0 - sum(weights[name] for name in issue_names[:-1]), 4)
    return weights


def _scores(values: list[str], preferred_index: int) -> dict[str, float]:
    return {
        value: round(max(0.25, 1.0 - 0.35 * abs(index - preferred_index)), 2)
        for index, value in enumerate(values)
    }


def _allowed_constraint_hint(
    issue_names: list[str],
    profile: dict[str, Any],
    preferences: dict[str, int],
) -> dict[str, Any]:
    hard_issues = {constraint["issue"] for constraint in profile["hard_constraints"]}
    issue_constraints = {issue: "fixed" for issue in issue_names if issue in hard_issues}
    flexible = sorted(
        (issue for issue in issue_names if issue not in hard_issues),
        key=lambda issue: (profile["utility_weights"][issue], preferences[issue], issue),
    )
    for issue in flexible[:2]:
        issue_constraints[issue] = "relaxable"
    return {
        "schema_version": "constraint_hint.v1",
        "anchor": "offered_outcome",
        "issue_constraints": issue_constraints,
    }


def _tune_reservations(
    issues: list[dict[str, Any]],
    profile_a: dict[str, Any],
    profile_b: dict[str, Any],
) -> None:
    feasible = [
        outcome
        for outcome in _enumerate_outcomes(issues)
        if _satisfies_hard_constraints(profile_a, outcome)
        and _satisfies_hard_constraints(profile_b, outcome)
    ]
    if not feasible:
        raise ValueError("Generated profile has no feasible outcome")
    max_min_utility = max(min(_utility(profile_a, outcome), _utility(profile_b, outcome)) for outcome in feasible)
    reservation = round(max(0.45, min(0.62, max_min_utility - 0.03)), 2)
    for profile in (profile_a, profile_b):
        profile["reservation_value"] = reservation
        profile["concession_policy"]["end_threshold"] = reservation
        profile["concession_policy"]["start_threshold"] = round(min(0.95, reservation + 0.32), 2)


def _enumerate_outcomes(issues: list[dict[str, Any]]) -> list[dict[str, str]]:
    names = [issue["name"] for issue in issues]
    value_lists = [issue["values"] for issue in issues]
    return [dict(zip(names, values)) for values in product(*value_lists)]


def _utility(profile: dict[str, Any], outcome: dict[str, str]) -> float:
    return sum(
        profile["utility_weights"][issue] * profile["value_scores"][issue][value]
        for issue, value in outcome.items()
    )


def _satisfies_hard_constraints(profile: dict[str, Any], outcome: dict[str, str]) -> bool:
    return all(
        outcome[constraint["issue"]] in constraint["allowed_values"]
        for constraint in profile["hard_constraints"]
    )


def _allowed_values_for_preference(values: list[str], preferred_index: int) -> list[str]:
    alternate_index = 1 if preferred_index != 1 else 2
    return [values[preferred_index], values[alternate_index]]


def _values_for(issues: list[dict[str, Any]], issue_name: str) -> list[str]:
    for issue in issues:
        if issue["name"] == issue_name:
            return issue["values"]
    raise KeyError(issue_name)


def _find_axis(issue_names: list[str], candidates: tuple[str, ...], fallback_index: int) -> str:
    for candidate in candidates:
        if candidate in issue_names:
            return candidate
    return issue_names[fallback_index]


def _opposite(index: int) -> int:
    return 2 - index


def _risk_for(tension_pattern: str) -> str:
    if tension_pattern == "aligned_preferences":
        return "low"
    if tension_pattern in {"one_hard_constraint", "mutual_hard_constraint_conflict"}:
        return "high"
    return "medium"
