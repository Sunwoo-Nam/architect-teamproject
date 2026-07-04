from __future__ import annotations

from copy import deepcopy
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
AUGMENTATION_KINDS = ("baseline", "agent_swap", "policy_difficulty")
ORTHOGONAL_AUGMENTATION_KINDS = (
    "baseline",
    "agent_swap",
    "value_reverse",
    "agent_swap_value_reverse",
    "issue_rotate",
)
UTILITY_SCORE_SHAPES = ("linear", "sharp", "flat", "near_tie", "plateau")
DIFFICULTY_STRATA = ("easy", "medium", "hard", "borderline", "no_agreement")
HINT_POLICY_STRATA = ("full", "fixed_only", "relaxable_only", "sparse", "disabled")
FIXED_ONLY_PATTERNS = (
    "ppa_a_only",
    "ppa_b_only",
    "both_agents_same_issue",
    "both_agents_different_issue",
    "none_control",
)
FIXED_ONLY_DIFFICULTY_STRATA = ("easy", "medium", "hard", "no_agreement")
FIXED_ONLY_VARIANTS = ("f01", "f02")
FIXED_ONLY_TENSION_BY_PATTERN = {
    "ppa_a_only": "one_hard_constraint",
    "ppa_b_only": "one_hard_constraint",
    "both_agents_same_issue": "mutual_hard_constraint_conflict",
    "both_agents_different_issue": "mutual_hard_constraint_conflict",
    "none_control": "aligned_preferences",
}
FIXED_HIGH_COMPLEXITY_LEVELS = ("issue_4", "issue_5")
FIXED_HIGH_COMPLEXITY_DIFFICULTY_STRATA = ("medium", "hard", "borderline", "no_agreement")
FIXED_HIGH_COMPLEXITY_PAIR_PATTERNS = (
    "time_location",
    "time_budget",
    "budget_quality",
    "location_quality",
    "time_quality",
)
FIXED_HIGH_COMPLEXITY_ROLE_MODES = ("ppa_a_dominant", "ppa_b_dominant")
FIXED_THREE_PARTY_LEVELS = ("issue_4", "issue_5")
FIXED_THREE_PARTY_PARTICIPATION_PATTERNS = (
    "two_agents_fixed",
    "all_agents_fixed",
    "single_bottleneck",
)
FIXED_THREE_PARTY_DIFFICULTY_STRATA = ("medium", "hard", "borderline", "no_agreement")
FIXED_FOUR_PARTY_LEVELS = ("issue_4", "issue_5")
FIXED_FOUR_PARTY_TOPOLOGIES = (
    "single_bottleneck",
    "two_pairs_fixed",
    "three_fixed_one_flexible",
    "all_agents_fixed",
    "same_issue_collision",
)
FIXED_FOUR_PARTY_DIFFICULTY_STRATA = ("medium", "hard", "borderline", "no_agreement")

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


def generate_augmented_scenarios() -> list[dict[str, Any]]:
    base_scenarios = generate_scenarios(variant_count=2)
    augmented = []
    sequence = 1
    for index, base in enumerate(base_scenarios):
        for kind_index, kind in enumerate(AUGMENTATION_KINDS):
            scenario = deepcopy(base)
            shape = UTILITY_SCORE_SHAPES[(index + kind_index) % len(UTILITY_SCORE_SHAPES)]
            difficulty = DIFFICULTY_STRATA[(index + kind_index) % len(DIFFICULTY_STRATA)]
            hint_policy = HINT_POLICY_STRATA[(index + kind_index) % len(HINT_POLICY_STRATA)]

            if kind == "agent_swap" or (kind == "policy_difficulty" and index % 2 == 1):
                _swap_agent_profiles(scenario)
            if kind == "policy_difficulty":
                _reverse_issue_value_order(scenario)

            _apply_utility_score_shape(scenario, shape)
            _apply_hint_policy(scenario, hint_policy)
            _apply_difficulty_stratum(scenario, difficulty)
            _refresh_generation_meta(
                scenario,
                scenario_id=f"V3S{sequence:03d}",
                seed=300000 + sequence,
                variant_suffix=f"{kind}_{shape}_{difficulty}_{hint_policy}",
            )
            augmented.append(scenario)
            sequence += 1
    return augmented


def generate_orthogonal_augmented_scenarios() -> list[dict[str, Any]]:
    base_scenarios = generate_scenarios(variant_count=2)
    augmented = []
    sequence = 1
    for index, base in enumerate(base_scenarios):
        base_mod = index % len(HINT_POLICY_STRATA)
        for repeat, kind in enumerate(ORTHOGONAL_AUGMENTATION_KINDS):
            scenario = deepcopy(base)
            shape = UTILITY_SCORE_SHAPES[(base_mod + repeat) % len(UTILITY_SCORE_SHAPES)]
            difficulty = DIFFICULTY_STRATA[(base_mod + 2 * repeat) % len(DIFFICULTY_STRATA)]
            hint_policy = HINT_POLICY_STRATA[(base_mod + 3 * repeat) % len(HINT_POLICY_STRATA)]

            if kind in {"agent_swap", "agent_swap_value_reverse"}:
                _swap_agent_profiles(scenario)
            if kind in {"value_reverse", "agent_swap_value_reverse"}:
                _reverse_issue_value_order(scenario)
            if kind == "issue_rotate":
                if scenario["tension_pattern"] == "one_hard_constraint" and index % 2 == 0:
                    _swap_agent_profiles(scenario)
                _rotate_issue_order(scenario, amount=(index % max(len(scenario["domain"]["issues"]), 1)) + 1)

            _apply_utility_score_shape(scenario, shape)
            _apply_hint_policy(scenario, hint_policy)
            _apply_difficulty_stratum(scenario, difficulty)
            _refresh_generation_meta(
                scenario,
                scenario_id=f"V4S{sequence:03d}",
                seed=400000 + sequence,
                variant_suffix=f"{kind}_{shape}_{difficulty}_{hint_policy}",
                generator_version="gen.v4",
                source="synthetic_orthogonal_augmented_matrix",
            )
            scenario["generation_meta"].update(
                {
                    "augmentation_kind": kind,
                    "utility_shape": shape,
                    "difficulty_stratum": difficulty,
                    "hint_policy": hint_policy,
                }
            )
            augmented.append(scenario)
            sequence += 1
    return augmented


def generate_fixed_only_scenarios() -> list[dict[str, Any]]:
    scenarios = []
    sequence = 1
    for task_family, complexity_level, fixed_pattern, difficulty, fixed_variant in product(
        TASK_FAMILIES,
        COMPLEXITY_LEVELS,
        FIXED_ONLY_PATTERNS,
        FIXED_ONLY_DIFFICULTY_STRATA,
        FIXED_ONLY_VARIANTS,
    ):
        pattern_index = FIXED_ONLY_PATTERNS.index(fixed_pattern)
        difficulty_index = FIXED_ONLY_DIFFICULTY_STRATA.index(difficulty)
        variant_index = FIXED_ONLY_VARIANTS.index(fixed_variant)
        utility_shape = UTILITY_SCORE_SHAPES[
            (pattern_index + difficulty_index + variant_index) % len(UTILITY_SCORE_SHAPES)
        ]
        fixed_strength = ((pattern_index + difficulty_index + variant_index) % 2) + 1

        scenario = build_scenario(
            scenario_id=f"F1S{sequence:03d}",
            task_family=task_family,
            complexity_level=complexity_level,
            tension_pattern=FIXED_ONLY_TENSION_BY_PATTERN[fixed_pattern],
            variant_id=VARIANTS[variant_index],
            seed=500000 + sequence,
        )
        _apply_utility_score_shape(scenario, utility_shape)
        _apply_fixed_only_pattern(
            scenario,
            fixed_pattern=fixed_pattern,
            variant_index=variant_index,
            fixed_strength=fixed_strength,
        )
        _apply_difficulty_stratum(scenario, difficulty)
        _refresh_generation_meta(
            scenario,
            scenario_id=f"F1S{sequence:03d}",
            seed=500000 + sequence,
            variant_suffix=f"{fixed_variant}_{fixed_pattern}_{difficulty}_{utility_shape}_s{fixed_strength}",
            generator_version="gen.fixed_only.v1",
            source="synthetic_fixed_only_matrix",
        )
        scenario["generation_meta"].update(
            {
                "fixed_pattern": fixed_pattern,
                "difficulty_stratum": difficulty,
                "utility_shape": utility_shape,
                "fixed_strength": fixed_strength,
            }
        )
        scenarios.append(scenario)
        sequence += 1
    return scenarios


def generate_fixed_high_complexity_scenarios() -> list[dict[str, Any]]:
    scenarios = []
    sequence = 1
    for task_family, complexity_level, issue_pair_pattern, difficulty, fixed_strength, role_mode in product(
        TASK_FAMILIES,
        FIXED_HIGH_COMPLEXITY_LEVELS,
        FIXED_HIGH_COMPLEXITY_PAIR_PATTERNS,
        FIXED_HIGH_COMPLEXITY_DIFFICULTY_STRATA,
        (1, 2),
        FIXED_HIGH_COMPLEXITY_ROLE_MODES,
    ):
        task_index = TASK_FAMILIES.index(task_family)
        complexity_index = FIXED_HIGH_COMPLEXITY_LEVELS.index(complexity_level)
        pair_index = FIXED_HIGH_COMPLEXITY_PAIR_PATTERNS.index(issue_pair_pattern)
        difficulty_index = FIXED_HIGH_COMPLEXITY_DIFFICULTY_STRATA.index(difficulty)
        strength_index = fixed_strength - 1
        role_index = FIXED_HIGH_COMPLEXITY_ROLE_MODES.index(role_mode)
        utility_shape = UTILITY_SCORE_SHAPES[
            (task_index + complexity_index + pair_index + difficulty_index + strength_index + role_index)
            % len(UTILITY_SCORE_SHAPES)
        ]
        variant_index = (pair_index + role_index) % len(VARIANTS)

        scenario = build_scenario(
            scenario_id=f"H1S{sequence:03d}",
            task_family=task_family,
            complexity_level=complexity_level,
            tension_pattern="mutual_hard_constraint_conflict",
            variant_id=VARIANTS[variant_index],
            seed=600000 + sequence,
        )
        _apply_utility_score_shape(scenario, utility_shape)
        constraint_issues = _apply_fixed_high_complexity_pattern(
            scenario,
            issue_pair_pattern=issue_pair_pattern,
            fixed_strength=fixed_strength,
            role_mode=role_mode,
            fallback_offset=pair_index + role_index,
        )
        _apply_difficulty_stratum(scenario, difficulty)
        _refresh_generation_meta(
            scenario,
            scenario_id=f"H1S{sequence:03d}",
            seed=600000 + sequence,
            variant_suffix=(
                f"hc01_{issue_pair_pattern}_{difficulty}_{utility_shape}_s{fixed_strength}_{role_mode}"
            ),
            generator_version="gen.fixed_high_complexity.v1",
            source="synthetic_fixed_high_complexity_matrix",
        )
        scenario["generation_meta"].update(
            {
                "fixed_pattern": "both_agents_different_issue",
                "difficulty_stratum": difficulty,
                "utility_shape": utility_shape,
                "fixed_strength": fixed_strength,
                "issue_pair_pattern": issue_pair_pattern,
                "role_mode": role_mode,
                "constraint_issues": constraint_issues,
                "complexity_focus": "high",
            }
        )
        scenarios.append(scenario)
        sequence += 1
    return scenarios


def generate_fixed_three_party_scenarios() -> list[dict[str, Any]]:
    scenarios = []
    sequence = 1
    for task_family, complexity_level, issue_pair_pattern, participation_pattern in product(
        TASK_FAMILIES,
        FIXED_THREE_PARTY_LEVELS,
        FIXED_HIGH_COMPLEXITY_PAIR_PATTERNS,
        FIXED_THREE_PARTY_PARTICIPATION_PATTERNS,
    ):
        task_index = TASK_FAMILIES.index(task_family)
        complexity_index = FIXED_THREE_PARTY_LEVELS.index(complexity_level)
        pair_index = FIXED_HIGH_COMPLEXITY_PAIR_PATTERNS.index(issue_pair_pattern)
        participation_index = FIXED_THREE_PARTY_PARTICIPATION_PATTERNS.index(participation_pattern)
        difficulty = FIXED_THREE_PARTY_DIFFICULTY_STRATA[
            (task_index + complexity_index + pair_index + participation_index)
            % len(FIXED_THREE_PARTY_DIFFICULTY_STRATA)
        ]
        utility_shape = UTILITY_SCORE_SHAPES[
            (task_index + 2 * complexity_index + pair_index + participation_index)
            % len(UTILITY_SCORE_SHAPES)
        ]
        fixed_strength = ((task_index + pair_index + participation_index) % 2) + 1
        variant_index = (pair_index + participation_index) % len(VARIANTS)

        scenario = build_scenario(
            scenario_id=f"TP1S{sequence:03d}",
            task_family=task_family,
            complexity_level=complexity_level,
            tension_pattern="three_party_fixed_constraint",
            variant_id=VARIANTS[variant_index],
            seed=700000 + sequence,
        )
        _add_third_party_agent(scenario, variant_index=variant_index)
        _apply_utility_score_shape(scenario, utility_shape)
        constraint_issues = _apply_fixed_three_party_pattern(
            scenario,
            issue_pair_pattern=issue_pair_pattern,
            participation_pattern=participation_pattern,
            fixed_strength=fixed_strength,
            fallback_offset=pair_index + participation_index,
        )
        _apply_difficulty_stratum(scenario, difficulty)
        _refresh_generation_meta(
            scenario,
            scenario_id=f"TP1S{sequence:03d}",
            seed=700000 + sequence,
            variant_suffix=(
                f"tp01_{issue_pair_pattern}_{participation_pattern}_"
                f"{difficulty}_{utility_shape}_s{fixed_strength}"
            ),
            generator_version="gen.fixed_three_party.v1",
            source="synthetic_fixed_three_party_matrix",
        )
        scenario["generation_meta"].update(
            {
                "party_count": 3,
                "fixed_pattern": "three_party_fixed",
                "participation_pattern": participation_pattern,
                "difficulty_stratum": difficulty,
                "utility_shape": utility_shape,
                "fixed_strength": fixed_strength,
                "issue_pair_pattern": issue_pair_pattern,
                "constraint_issues": constraint_issues,
                "complexity_focus": "high",
            }
        )
        scenarios.append(scenario)
        sequence += 1
    return scenarios


def generate_fixed_four_party_scenarios() -> list[dict[str, Any]]:
    scenarios = []
    sequence = 1
    for task_family, complexity_level, constraint_topology, difficulty in product(
        TASK_FAMILIES,
        FIXED_FOUR_PARTY_LEVELS,
        FIXED_FOUR_PARTY_TOPOLOGIES,
        FIXED_FOUR_PARTY_DIFFICULTY_STRATA,
    ):
        task_index = TASK_FAMILIES.index(task_family)
        complexity_index = FIXED_FOUR_PARTY_LEVELS.index(complexity_level)
        topology_index = FIXED_FOUR_PARTY_TOPOLOGIES.index(constraint_topology)
        difficulty_index = FIXED_FOUR_PARTY_DIFFICULTY_STRATA.index(difficulty)
        utility_shape = UTILITY_SCORE_SHAPES[
            (task_index + 2 * complexity_index + topology_index + difficulty_index)
            % len(UTILITY_SCORE_SHAPES)
        ]
        fixed_strength = ((task_index + topology_index + difficulty_index) % 2) + 1
        if constraint_topology == "same_issue_collision":
            fixed_strength = 2
        variant_index = (topology_index + difficulty_index) % len(VARIANTS)

        scenario = build_scenario(
            scenario_id=f"QP1S{sequence:03d}",
            task_family=task_family,
            complexity_level=complexity_level,
            tension_pattern="four_party_fixed_constraint",
            variant_id=VARIANTS[variant_index],
            seed=800000 + sequence,
        )
        _add_third_party_agent(scenario, variant_index=variant_index)
        _add_fourth_party_agent(scenario, variant_index=variant_index)
        _apply_utility_score_shape(scenario, utility_shape)
        constraint_issues = _apply_fixed_four_party_topology(
            scenario,
            constraint_topology=constraint_topology,
            fixed_strength=fixed_strength,
            fallback_offset=task_index + complexity_index + topology_index + difficulty_index,
        )
        _apply_difficulty_stratum(scenario, difficulty)
        _refresh_generation_meta(
            scenario,
            scenario_id=f"QP1S{sequence:03d}",
            seed=800000 + sequence,
            variant_suffix=(
                f"qp01_{constraint_topology}_{difficulty}_{utility_shape}_s{fixed_strength}"
            ),
            generator_version="gen.fixed_four_party.v1",
            source="synthetic_fixed_four_party_matrix",
        )
        scenario["generation_meta"].update(
            {
                "party_count": 4,
                "fixed_pattern": "four_party_fixed",
                "constraint_topology": constraint_topology,
                "difficulty_stratum": difficulty,
                "utility_shape": utility_shape,
                "fixed_strength": fixed_strength,
                "fixed_agent_count": len(constraint_issues),
                "constraint_issues": constraint_issues,
                "complexity_focus": "high",
            }
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


def _swap_agent_profiles(scenario: dict[str, Any]) -> None:
    first, second = scenario["agents"]
    fields = ("capability", "private_profile", "allowed_constraint_hint")
    for field in fields:
        first[field], second[field] = deepcopy(second[field]), deepcopy(first[field])


def _reverse_issue_value_order(scenario: dict[str, Any]) -> None:
    for issue in scenario["domain"]["issues"]:
        issue["values"] = list(reversed(issue["values"]))
        if "order" in issue:
            issue["order"] = list(reversed(issue["order"]))


def _rotate_issue_order(scenario: dict[str, Any], amount: int) -> None:
    issues = scenario["domain"]["issues"]
    if not issues:
        return
    amount = amount % len(issues)
    scenario["domain"]["issues"] = issues[amount:] + issues[:amount]


def _apply_utility_score_shape(scenario: dict[str, Any], shape: str) -> None:
    for agent in scenario["agents"]:
        value_scores = agent["private_profile"]["value_scores"]
        for issue in scenario["domain"]["issues"]:
            scores = value_scores[issue["name"]]
            preferred_value = max(scores, key=scores.get)
            preferred_index = issue["values"].index(preferred_value)
            scores.update(_score_shape(issue["values"], preferred_index, shape))


def _score_shape(values: list[str], preferred_index: int, shape: str) -> dict[str, float]:
    by_distance = {
        "linear": (1.0, 0.65, 0.3),
        "sharp": (1.0, 0.45, 0.1),
        "flat": (1.0, 0.9, 0.8),
        "near_tie": (1.0, 0.96, 0.92),
        "plateau": (1.0, 0.95, 0.45),
    }[shape]
    return {
        value: by_distance[min(abs(index - preferred_index), len(by_distance) - 1)]
        for index, value in enumerate(values)
    }


def _apply_hint_policy(scenario: dict[str, Any], policy: str) -> None:
    if policy == "disabled":
        scenario["privacy_labels"]["external_constraint_hint_allowed"] = False
        for agent in scenario["agents"]:
            agent["capability"]["constraint_hint"] = False
            agent["capability"]["constraint_hint_schema_version"] = None
            agent["allowed_constraint_hint"]["issue_constraints"] = {}
        return

    scenario["privacy_labels"]["external_constraint_hint_allowed"] = True
    for agent in scenario["agents"]:
        constraints = agent["allowed_constraint_hint"]["issue_constraints"]
        if policy == "fixed_only":
            agent["allowed_constraint_hint"]["issue_constraints"] = {
                issue: value for issue, value in constraints.items() if value == "fixed"
            }
        elif policy == "relaxable_only":
            agent["allowed_constraint_hint"]["issue_constraints"] = {
                issue: value for issue, value in constraints.items() if value == "relaxable"
            }
        elif policy == "sparse":
            if constraints:
                issue = sorted(constraints)[0]
                agent["allowed_constraint_hint"]["issue_constraints"] = {issue: constraints[issue]}


def _apply_fixed_only_pattern(
    scenario: dict[str, Any],
    *,
    fixed_pattern: str,
    variant_index: int,
    fixed_strength: int,
) -> None:
    issues = scenario["domain"]["issues"]
    issue_names = [issue["name"] for issue in issues]
    primary_issue = issue_names[variant_index % len(issue_names)]
    secondary_issue = issue_names[(variant_index + 1) % len(issue_names)]
    same_issue = primary_issue

    scenario["privacy_labels"]["external_constraint_hint_allowed"] = fixed_pattern != "none_control"
    scenario["privacy_labels"]["constraint_hint_accumulation_risk"] = (
        "low" if fixed_pattern == "none_control" else "high"
    )

    for agent in scenario["agents"]:
        agent["capability"]["constraint_hint"] = fixed_pattern != "none_control"
        agent["capability"]["constraint_hint_schema_version"] = (
            "constraint_hint.v1" if fixed_pattern != "none_control" else None
        )
        agent["private_profile"]["hard_constraints"] = []
        agent["allowed_constraint_hint"]["issue_constraints"] = {}

    if fixed_pattern == "none_control":
        return

    if fixed_pattern == "ppa_a_only":
        _add_fixed_constraint(scenario["agents"][0], issues, primary_issue, fixed_strength)
    elif fixed_pattern == "ppa_b_only":
        _add_fixed_constraint(scenario["agents"][1], issues, secondary_issue, fixed_strength)
    elif fixed_pattern == "both_agents_same_issue":
        common_value = _values_for(issues, same_issue)[(variant_index + 1) % 3]
        _add_fixed_constraint(
            scenario["agents"][0],
            issues,
            same_issue,
            fixed_strength,
            common_value=common_value,
        )
        _add_fixed_constraint(
            scenario["agents"][1],
            issues,
            same_issue,
            fixed_strength,
            common_value=common_value,
        )
    elif fixed_pattern == "both_agents_different_issue":
        _add_fixed_constraint(scenario["agents"][0], issues, primary_issue, fixed_strength)
        _add_fixed_constraint(scenario["agents"][1], issues, secondary_issue, fixed_strength)
    else:
        raise ValueError(f"Unsupported fixed-only pattern: {fixed_pattern}")


def _add_third_party_agent(scenario: dict[str, Any], *, variant_index: int) -> None:
    issues = scenario["domain"]["issues"]
    issue_names = [issue["name"] for issue in issues]
    preferences = {
        name: (index + variant_index + 2) % 3
        for index, name in enumerate(issue_names)
    }
    emphasis = (issue_names[(variant_index + 2) % len(issue_names)],)
    profile = _profile(issues, preferences, emphasis, hard_constraints={})
    ppa_c = _agent(
        "ppa_c",
        "participant",
        profile,
        _allowed_constraint_hint(issue_names, profile, preferences),
    )
    scenario["agents"] = tuple(list(scenario["agents"]) + [ppa_c])


def _add_fourth_party_agent(scenario: dict[str, Any], *, variant_index: int) -> None:
    issues = scenario["domain"]["issues"]
    issue_names = [issue["name"] for issue in issues]
    preferences = {
        name: (2 * index + variant_index + 1) % 3
        for index, name in enumerate(issue_names)
    }
    emphasis = (issue_names[(variant_index + 3) % len(issue_names)],)
    profile = _profile(issues, preferences, emphasis, hard_constraints={})
    ppa_d = _agent(
        "ppa_d",
        "participant",
        profile,
        _allowed_constraint_hint(issue_names, profile, preferences),
    )
    scenario["agents"] = tuple(list(scenario["agents"]) + [ppa_d])


def _apply_fixed_three_party_pattern(
    scenario: dict[str, Any],
    *,
    issue_pair_pattern: str,
    participation_pattern: str,
    fixed_strength: int,
    fallback_offset: int,
) -> dict[str, str]:
    issues = scenario["domain"]["issues"]
    issue_names = [issue["name"] for issue in issues]
    ppa_a_issue, ppa_b_issue, ppa_c_issue = _three_party_constraint_issues(
        issue_names,
        issue_pair_pattern,
        fallback_offset=fallback_offset,
    )
    agents_by_id = {agent["id"]: agent for agent in scenario["agents"]}

    scenario["privacy_labels"]["external_constraint_hint_allowed"] = True
    scenario["privacy_labels"]["constraint_hint_accumulation_risk"] = "high"

    for agent in scenario["agents"]:
        agent["capability"]["constraint_hint"] = True
        agent["capability"]["constraint_hint_schema_version"] = "constraint_hint.v1"
        agent["private_profile"]["hard_constraints"] = []
        agent["allowed_constraint_hint"]["issue_constraints"] = {}

    constraint_issues: dict[str, str] = {}
    if participation_pattern == "two_agents_fixed":
        _add_fixed_constraint(agents_by_id["ppa_a"], issues, ppa_a_issue, fixed_strength)
        _add_fixed_constraint(agents_by_id["ppa_b"], issues, ppa_b_issue, fixed_strength)
        _set_issue_weight(agents_by_id["ppa_a"]["private_profile"], ppa_a_issue, target_weight=0.42)
        _set_issue_weight(agents_by_id["ppa_b"]["private_profile"], ppa_b_issue, target_weight=0.42)
        constraint_issues = {"ppa_a": ppa_a_issue, "ppa_b": ppa_b_issue}
    elif participation_pattern == "all_agents_fixed":
        _add_fixed_constraint(agents_by_id["ppa_a"], issues, ppa_a_issue, fixed_strength)
        _add_fixed_constraint(agents_by_id["ppa_b"], issues, ppa_b_issue, fixed_strength)
        _add_fixed_constraint(agents_by_id["ppa_c"], issues, ppa_c_issue, fixed_strength)
        _set_issue_weight(agents_by_id["ppa_a"]["private_profile"], ppa_a_issue, target_weight=0.38)
        _set_issue_weight(agents_by_id["ppa_b"]["private_profile"], ppa_b_issue, target_weight=0.38)
        _set_issue_weight(agents_by_id["ppa_c"]["private_profile"], ppa_c_issue, target_weight=0.38)
        constraint_issues = {"ppa_a": ppa_a_issue, "ppa_b": ppa_b_issue, "ppa_c": ppa_c_issue}
    elif participation_pattern == "single_bottleneck":
        _add_fixed_constraint(agents_by_id["ppa_c"], issues, ppa_c_issue, fixed_strength)
        _set_issue_weight(agents_by_id["ppa_c"]["private_profile"], ppa_c_issue, target_weight=0.52)
        constraint_issues = {"ppa_c": ppa_c_issue}
    else:
        raise ValueError(f"Unsupported three-party participation pattern: {participation_pattern}")
    return constraint_issues


def _three_party_constraint_issues(
    issue_names: list[str],
    issue_pair_pattern: str,
    *,
    fallback_offset: int,
) -> tuple[str, str, str]:
    ppa_a_issue, ppa_b_issue = _high_complexity_issue_pair(
        issue_names,
        issue_pair_pattern,
        fallback_offset=fallback_offset,
    )
    ppa_c_issue = _find_axis_or_fallback(
        issue_names,
        TIME_HINTS + LOCATION_HINTS + BUDGET_HINTS + QUALITY_HINTS,
        fallback_offset + 2,
        exclude=(ppa_a_issue, ppa_b_issue),
    )
    return ppa_a_issue, ppa_b_issue, ppa_c_issue


def _apply_fixed_four_party_topology(
    scenario: dict[str, Any],
    *,
    constraint_topology: str,
    fixed_strength: int,
    fallback_offset: int,
) -> dict[str, str]:
    issues = scenario["domain"]["issues"]
    issue_names = [issue["name"] for issue in issues]
    agents_by_id = {agent["id"]: agent for agent in scenario["agents"]}
    ordered_issues = _four_party_constraint_issues(issue_names, fallback_offset=fallback_offset)

    scenario["privacy_labels"]["external_constraint_hint_allowed"] = True
    scenario["privacy_labels"]["constraint_hint_accumulation_risk"] = "high"

    for agent in scenario["agents"]:
        agent["capability"]["constraint_hint"] = True
        agent["capability"]["constraint_hint_schema_version"] = "constraint_hint.v1"
        agent["private_profile"]["hard_constraints"] = []
        agent["allowed_constraint_hint"]["issue_constraints"] = {}

    constraint_issues: dict[str, str] = {}
    if constraint_topology == "single_bottleneck":
        issue = ordered_issues[3]
        _add_fixed_constraint(agents_by_id["ppa_d"], issues, issue, fixed_strength)
        _set_issue_weight(agents_by_id["ppa_d"]["private_profile"], issue, target_weight=0.52)
        constraint_issues = {"ppa_d": issue}
    elif constraint_topology == "two_pairs_fixed":
        first_issue, second_issue = ordered_issues[0], ordered_issues[1]
        first_common = _values_for(issues, first_issue)[fallback_offset % 3]
        second_common = _values_for(issues, second_issue)[(fallback_offset + 1) % 3]
        for agent_id in ("ppa_a", "ppa_b"):
            _add_fixed_constraint(
                agents_by_id[agent_id],
                issues,
                first_issue,
                fixed_strength,
                common_value=first_common,
            )
            _set_issue_weight(agents_by_id[agent_id]["private_profile"], first_issue, target_weight=0.34)
            constraint_issues[agent_id] = first_issue
        for agent_id in ("ppa_c", "ppa_d"):
            _add_fixed_constraint(
                agents_by_id[agent_id],
                issues,
                second_issue,
                fixed_strength,
                common_value=second_common,
            )
            _set_issue_weight(agents_by_id[agent_id]["private_profile"], second_issue, target_weight=0.34)
            constraint_issues[agent_id] = second_issue
    elif constraint_topology == "three_fixed_one_flexible":
        for agent_id, issue in zip(("ppa_a", "ppa_b", "ppa_c"), ordered_issues):
            _add_fixed_constraint(agents_by_id[agent_id], issues, issue, fixed_strength)
            _set_issue_weight(agents_by_id[agent_id]["private_profile"], issue, target_weight=0.36)
            constraint_issues[agent_id] = issue
    elif constraint_topology == "all_agents_fixed":
        for agent_id, issue in zip(("ppa_a", "ppa_b", "ppa_c", "ppa_d"), ordered_issues):
            _add_fixed_constraint(agents_by_id[agent_id], issues, issue, fixed_strength)
            _set_issue_weight(agents_by_id[agent_id]["private_profile"], issue, target_weight=0.32)
            constraint_issues[agent_id] = issue
    elif constraint_topology == "same_issue_collision":
        issue = ordered_issues[0]
        common_value = _values_for(issues, issue)[fallback_offset % 3]
        for agent_id in ("ppa_a", "ppa_b", "ppa_c", "ppa_d"):
            _add_fixed_constraint(
                agents_by_id[agent_id],
                issues,
                issue,
                fixed_strength,
                common_value=common_value,
            )
            _set_issue_weight(agents_by_id[agent_id]["private_profile"], issue, target_weight=0.36)
            constraint_issues[agent_id] = issue
    else:
        raise ValueError(f"Unsupported four-party constraint topology: {constraint_topology}")
    return constraint_issues


def _four_party_constraint_issues(issue_names: list[str], *, fallback_offset: int) -> tuple[str, str, str, str]:
    ordered = []
    for axis in (TIME_HINTS, LOCATION_HINTS, BUDGET_HINTS, QUALITY_HINTS):
        ordered.append(
            _find_axis_or_fallback(
                issue_names,
                axis,
                fallback_offset + len(ordered),
                exclude=tuple(ordered),
            )
        )
    return tuple(ordered)


def _apply_fixed_high_complexity_pattern(
    scenario: dict[str, Any],
    *,
    issue_pair_pattern: str,
    fixed_strength: int,
    role_mode: str,
    fallback_offset: int,
) -> dict[str, str]:
    issues = scenario["domain"]["issues"]
    issue_names = [issue["name"] for issue in issues]
    ppa_a_issue, ppa_b_issue = _high_complexity_issue_pair(
        issue_names,
        issue_pair_pattern,
        fallback_offset=fallback_offset,
    )

    scenario["privacy_labels"]["external_constraint_hint_allowed"] = True
    scenario["privacy_labels"]["constraint_hint_accumulation_risk"] = "high"

    for agent in scenario["agents"]:
        agent["capability"]["constraint_hint"] = True
        agent["capability"]["constraint_hint_schema_version"] = "constraint_hint.v1"
        agent["private_profile"]["hard_constraints"] = []
        agent["allowed_constraint_hint"]["issue_constraints"] = {}

    _add_fixed_constraint(scenario["agents"][0], issues, ppa_a_issue, fixed_strength)
    _add_fixed_constraint(scenario["agents"][1], issues, ppa_b_issue, fixed_strength)
    _emphasize_high_complexity_weights(
        scenario["agents"][0],
        scenario["agents"][1],
        ppa_a_issue=ppa_a_issue,
        ppa_b_issue=ppa_b_issue,
        role_mode=role_mode,
    )
    return {"ppa_a": ppa_a_issue, "ppa_b": ppa_b_issue}


def _high_complexity_issue_pair(
    issue_names: list[str],
    issue_pair_pattern: str,
    *,
    fallback_offset: int,
) -> tuple[str, str]:
    if issue_pair_pattern == "time_location":
        ppa_a_issue = _find_axis_or_fallback(issue_names, TIME_HINTS, fallback_offset)
        ppa_b_issue = _find_axis_or_fallback(
            issue_names,
            LOCATION_HINTS,
            fallback_offset + 1,
            exclude=(ppa_a_issue,),
        )
    elif issue_pair_pattern == "time_budget":
        ppa_a_issue = _find_axis_or_fallback(issue_names, TIME_HINTS, fallback_offset)
        ppa_b_issue = _find_axis_or_fallback(
            issue_names,
            BUDGET_HINTS,
            fallback_offset + 1,
            exclude=(ppa_a_issue,),
        )
    elif issue_pair_pattern == "budget_quality":
        ppa_a_issue = _find_axis_or_fallback(issue_names, BUDGET_HINTS, fallback_offset)
        ppa_b_issue = _find_axis_or_fallback(
            issue_names,
            QUALITY_HINTS,
            fallback_offset + 1,
            exclude=(ppa_a_issue,),
        )
    elif issue_pair_pattern == "location_quality":
        ppa_a_issue = _find_axis_or_fallback(issue_names, LOCATION_HINTS, fallback_offset)
        ppa_b_issue = _find_axis_or_fallback(
            issue_names,
            QUALITY_HINTS,
            fallback_offset + 1,
            exclude=(ppa_a_issue,),
        )
    elif issue_pair_pattern == "time_quality":
        ppa_a_issue = _find_axis_or_fallback(issue_names, TIME_HINTS, fallback_offset)
        ppa_b_issue = _find_axis_or_fallback(
            issue_names,
            QUALITY_HINTS,
            fallback_offset + 1,
            exclude=(ppa_a_issue,),
        )
    else:
        raise ValueError(f"Unsupported high-complexity issue pair pattern: {issue_pair_pattern}")
    return ppa_a_issue, ppa_b_issue


def _find_axis_or_fallback(
    issue_names: list[str],
    candidates: tuple[str, ...],
    fallback_offset: int,
    *,
    exclude: tuple[str, ...] = (),
) -> str:
    excluded = set(exclude)
    for candidate in candidates:
        if candidate in issue_names and candidate not in excluded:
            return candidate
    for index in range(len(issue_names)):
        candidate = issue_names[(fallback_offset + index) % len(issue_names)]
        if candidate not in excluded:
            return candidate
    raise ValueError("No issue is available for high-complexity fixed constraint pairing")


def _emphasize_high_complexity_weights(
    ppa_a: dict[str, Any],
    ppa_b: dict[str, Any],
    *,
    ppa_a_issue: str,
    ppa_b_issue: str,
    role_mode: str,
) -> None:
    if role_mode == "ppa_a_dominant":
        _set_issue_weight(ppa_a["private_profile"], ppa_a_issue, target_weight=0.48)
        _set_issue_weight(ppa_b["private_profile"], ppa_b_issue, target_weight=0.34)
    elif role_mode == "ppa_b_dominant":
        _set_issue_weight(ppa_a["private_profile"], ppa_a_issue, target_weight=0.34)
        _set_issue_weight(ppa_b["private_profile"], ppa_b_issue, target_weight=0.48)
    else:
        raise ValueError(f"Unsupported high-complexity role mode: {role_mode}")


def _set_issue_weight(profile: dict[str, Any], issue_name: str, *, target_weight: float) -> None:
    weights = profile["utility_weights"]
    if issue_name not in weights:
        raise KeyError(issue_name)
    other_issues = [name for name in weights if name != issue_name]
    if not other_issues:
        weights[issue_name] = 1.0
        return

    other_total = sum(weights[name] for name in other_issues)
    remaining_weight = round(1.0 - target_weight, 4)
    weights[issue_name] = round(target_weight, 4)
    if other_total <= 0:
        equal_weight = round(remaining_weight / len(other_issues), 4)
        for name in other_issues[:-1]:
            weights[name] = equal_weight
    else:
        for name in other_issues[:-1]:
            weights[name] = round(weights[name] / other_total * remaining_weight, 4)

    last = other_issues[-1]
    weights[last] = round(1.0 - sum(weights[name] for name in weights if name != last), 4)


def _add_fixed_constraint(
    agent: dict[str, Any],
    issues: list[dict[str, Any]],
    issue_name: str,
    fixed_strength: int,
    *,
    common_value: str | None = None,
) -> None:
    values = _values_for(issues, issue_name)
    scores = agent["private_profile"]["value_scores"][issue_name]
    preferred_value = max(scores, key=scores.get)
    allowed_values = _fixed_allowed_values(
        values,
        preferred_value,
        fixed_strength,
        common_value=common_value,
    )
    agent["private_profile"]["hard_constraints"].append(
        {
            "issue": issue_name,
            "allowed_values": allowed_values,
        }
    )
    agent["allowed_constraint_hint"]["issue_constraints"][issue_name] = "fixed"


def _fixed_allowed_values(
    values: list[str],
    preferred_value: str,
    fixed_strength: int,
    *,
    common_value: str | None = None,
) -> list[str]:
    if fixed_strength not in {1, 2}:
        raise ValueError("fixed_strength must be 1 or 2")
    anchor_value = common_value or preferred_value
    ordered = [anchor_value]
    if preferred_value not in ordered:
        ordered.append(preferred_value)
    ordered.extend(value for value in values if value not in ordered)
    return ordered[:fixed_strength]


def _apply_difficulty_stratum(scenario: dict[str, Any], difficulty: str) -> None:
    issues = scenario["domain"]["issues"]
    profiles = [agent["private_profile"] for agent in scenario["agents"]]
    if difficulty == "no_agreement":
        for scores in profiles[1]["value_scores"].values():
            for value, score in list(scores.items()):
                scores[value] = round(score * 0.95, 4)
    feasible = [
        outcome
        for outcome in _enumerate_outcomes(issues)
        if all(_satisfies_hard_constraints(profile, outcome) for profile in profiles)
    ]
    max_min_utility = max(min(_utility(profile, outcome) for profile in profiles) for outcome in feasible)
    if difficulty == "no_agreement":
        reservation = round(min(0.99, max_min_utility + 0.03), 3)
        expected_agreement = False
    else:
        offsets = {
            "easy": -0.25,
            "medium": -0.12,
            "hard": -0.04,
            "borderline": -0.005,
        }
        reservation = round(max(0.35, min(0.99, max_min_utility + offsets[difficulty])), 3)
        expected_agreement = True

    for profile in profiles:
        profile["reservation_value"] = reservation
        profile["concession_policy"]["end_threshold"] = reservation
        profile["concession_policy"]["start_threshold"] = round(min(0.99, reservation + 0.32), 3)

    scenario["expected_checks"]["has_agreement_region"] = expected_agreement
    scenario["expected_checks"]["expected_timeout_possible"] = not expected_agreement or difficulty in {
        "borderline",
        "no_agreement",
    }
    scenario["expected_checks"]["min_valid_outcomes"] = min(
        scenario["expected_checks"]["min_valid_outcomes"],
        len(feasible),
    )


def _refresh_generation_meta(
    scenario: dict[str, Any],
    *,
    scenario_id: str,
    seed: int,
    variant_suffix: str,
    generator_version: str = "gen.v3",
    source: str = "synthetic_augmented_matrix",
) -> None:
    scenario["scenario_id"] = scenario_id
    scenario["variant_id"] = f"{scenario['variant_id']}_{variant_suffix}"
    scenario["generation_meta"] = {
        "generator_version": generator_version,
        "seed": seed,
        "source": source,
        "created_from_legacy_poc": False,
    }
