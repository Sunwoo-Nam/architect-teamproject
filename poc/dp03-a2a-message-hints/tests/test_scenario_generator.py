from dp03_a2a_hints.scenario_generator import (
    COMPLEXITY_LEVELS,
    DIFFICULTY_STRATA,
    FIXED_HIGH_COMPLEXITY_DIFFICULTY_STRATA,
    FIXED_HIGH_COMPLEXITY_LEVELS,
    FIXED_HIGH_COMPLEXITY_PAIR_PATTERNS,
    FIXED_HIGH_COMPLEXITY_ROLE_MODES,
    FIXED_ONLY_DIFFICULTY_STRATA,
    FIXED_ONLY_PATTERNS,
    HINT_POLICY_STRATA,
    TASK_FAMILIES,
    TENSION_PATTERNS,
    UTILITY_SCORE_SHAPES,
    generate_augmented_scenarios,
    generate_fixed_high_complexity_scenarios,
    generate_fixed_only_scenarios,
    generate_orthogonal_augmented_scenarios,
    generate_scenarios,
)
from dp03_a2a_hints.scenario_loader import scenario_from_dict
from dp03_a2a_hints.validators import agreement_region, validate_scenario, valid_outcomes


def test_base_scenario_matrix_generates_120_valid_scenarios():
    scenarios = generate_scenarios(variant_count=2)

    assert len(scenarios) == 120
    assert len(_matrix_keys(scenarios)) == 120
    assert {scenario["task_family"] for scenario in scenarios} == set(TASK_FAMILIES)
    assert {scenario["complexity_level"] for scenario in scenarios} == set(COMPLEXITY_LEVELS)
    assert {scenario["tension_pattern"] for scenario in scenarios} == set(TENSION_PATTERNS)

    for raw in scenarios:
        scenario = scenario_from_dict(raw)
        validate_scenario(scenario)
        assert len(valid_outcomes(scenario)) >= scenario.expected_checks.min_valid_outcomes
        assert agreement_region(scenario)
        assert not scenario.generation_meta.created_from_legacy_poc


def test_extended_scenario_matrix_generates_180_unique_scenarios():
    scenarios = generate_scenarios(variant_count=3)

    assert len(scenarios) == 180
    assert len(_matrix_keys(scenarios)) == 180
    assert scenarios[0]["scenario_id"] == "S001"
    assert scenarios[-1]["scenario_id"] == "S180"


def test_generated_hint_policy_uses_fixed_only_for_hard_constraints():
    for raw in generate_scenarios(variant_count=2):
        scenario = scenario_from_dict(raw)
        for agent in scenario.agents:
            hard_constraint_issues = {constraint.issue for constraint in agent.private_profile.hard_constraints}
            fixed_hint_issues = {
                issue
                for issue, constraint in agent.allowed_constraint_hint.issue_constraints.items()
                if constraint == "fixed"
            }

            assert fixed_hint_issues.issubset(hard_constraint_issues)


def test_augmented_scenario_matrix_adds_counterfactual_and_control_cases():
    scenarios = generate_augmented_scenarios()

    assert len(scenarios) == 360
    assert {scenario["generation_meta"]["generator_version"] for scenario in scenarios} == {"gen.v3"}
    assert any(not scenario["privacy_labels"]["external_constraint_hint_allowed"] for scenario in scenarios)
    assert any(not scenario["expected_checks"]["has_agreement_region"] for scenario in scenarios)

    hard_constraint_by_agent = {"ppa_a": 0, "ppa_b": 0}
    score_shapes = set()
    for raw in scenarios:
        scenario = scenario_from_dict(raw)
        validate_scenario(scenario)
        if scenario.expected_checks.has_agreement_region:
            assert agreement_region(scenario)
        else:
            assert not agreement_region(scenario)
        assert len(valid_outcomes(scenario)) >= scenario.expected_checks.min_valid_outcomes
        for agent in scenario.agents:
            hard_constraint_by_agent[agent.id] += len(agent.private_profile.hard_constraints)
            for scores in agent.private_profile.value_scores.values():
                score_shapes.add(tuple(sorted(scores.values(), reverse=True)))

    assert abs(hard_constraint_by_agent["ppa_a"] - hard_constraint_by_agent["ppa_b"]) <= 1
    assert len(score_shapes) > 2


def test_orthogonal_augmented_scenario_matrix_decouples_policy_difficulty_and_shape():
    scenarios = generate_orthogonal_augmented_scenarios()

    assert len(scenarios) == 600
    assert {scenario["generation_meta"]["generator_version"] for scenario in scenarios} == {"gen.v4"}

    hint_policy_counts = _meta_counts(scenarios, "hint_policy")
    difficulty_counts = _meta_counts(scenarios, "difficulty_stratum")
    shape_counts = _meta_counts(scenarios, "utility_shape")

    assert hint_policy_counts == {policy: 120 for policy in HINT_POLICY_STRATA}
    assert difficulty_counts == {difficulty: 120 for difficulty in DIFFICULTY_STRATA}
    assert shape_counts == {shape: 120 for shape in UTILITY_SCORE_SHAPES}

    policy_difficulty_pairs = {
        (
            scenario["generation_meta"]["hint_policy"],
            scenario["generation_meta"]["difficulty_stratum"],
        )
        for scenario in scenarios
    }
    assert len(policy_difficulty_pairs) == len(HINT_POLICY_STRATA) * len(DIFFICULTY_STRATA)

    hard_constraint_by_agent = {"ppa_a": 0, "ppa_b": 0}
    no_agreement_count = 0
    for raw in scenarios:
        scenario = scenario_from_dict(raw)
        validate_scenario(scenario)
        if scenario.expected_checks.has_agreement_region:
            assert agreement_region(scenario)
        else:
            no_agreement_count += 1
            assert not agreement_region(scenario)
        for agent in scenario.agents:
            hard_constraint_by_agent[agent.id] += len(agent.private_profile.hard_constraints)

    assert no_agreement_count == 120
    assert abs(hard_constraint_by_agent["ppa_a"] - hard_constraint_by_agent["ppa_b"]) <= 1


def test_fixed_only_scenario_matrix_is_balanced_and_uses_only_fixed_hints():
    scenarios = generate_fixed_only_scenarios()

    assert len(scenarios) == 480
    assert {scenario["generation_meta"]["generator_version"] for scenario in scenarios} == {
        "gen.fixed_only.v1"
    }
    assert _meta_counts(scenarios, "fixed_pattern") == {pattern: 96 for pattern in FIXED_ONLY_PATTERNS}
    assert _meta_counts(scenarios, "difficulty_stratum") == {
        difficulty: 120 for difficulty in FIXED_ONLY_DIFFICULTY_STRATA
    }
    assert _meta_counts(scenarios, "fixed_strength") == {1: 240, 2: 240}

    no_agreement_count = 0
    fixed_hint_count = 0
    for raw in scenarios:
        scenario = scenario_from_dict(raw)
        validate_scenario(scenario)
        if scenario.expected_checks.has_agreement_region:
            assert agreement_region(scenario)
        else:
            no_agreement_count += 1
            assert not agreement_region(scenario)
        assert len(valid_outcomes(scenario)) >= scenario.expected_checks.min_valid_outcomes

        for agent in scenario.agents:
            constraints = agent.allowed_constraint_hint.issue_constraints
            assert set(constraints.values()).issubset({"fixed"})
            hard_constraint_issues = {constraint.issue for constraint in agent.private_profile.hard_constraints}
            assert set(constraints).issubset(hard_constraint_issues)
            fixed_hint_count += len(constraints)

    assert no_agreement_count == 120
    assert fixed_hint_count > 0


def test_fixed_high_complexity_scenario_matrix_focuses_on_different_issue_constraints():
    scenarios = generate_fixed_high_complexity_scenarios()

    assert len(scenarios) == 640
    assert {scenario["generation_meta"]["generator_version"] for scenario in scenarios} == {
        "gen.fixed_high_complexity.v1"
    }
    assert _meta_counts(scenarios, "complexity_focus") == {"high": 640}
    assert _meta_counts(scenarios, "fixed_pattern") == {"both_agents_different_issue": 640}
    assert _meta_counts(scenarios, "difficulty_stratum") == {
        difficulty: 160 for difficulty in FIXED_HIGH_COMPLEXITY_DIFFICULTY_STRATA
    }
    assert _meta_counts(scenarios, "issue_pair_pattern") == {
        pattern: 128 for pattern in FIXED_HIGH_COMPLEXITY_PAIR_PATTERNS
    }
    assert _meta_counts(scenarios, "role_mode") == {
        role_mode: 320 for role_mode in FIXED_HIGH_COMPLEXITY_ROLE_MODES
    }
    assert _meta_counts(scenarios, "fixed_strength") == {1: 320, 2: 320}
    assert {scenario["complexity_level"] for scenario in scenarios} == set(FIXED_HIGH_COMPLEXITY_LEVELS)

    no_agreement_count = 0
    for raw in scenarios:
        scenario = scenario_from_dict(raw)
        validate_scenario(scenario)
        assert len(raw["domain"]["issues"]) in {4, 5}
        assert raw["privacy_labels"]["external_constraint_hint_allowed"]
        assert raw["privacy_labels"]["constraint_hint_accumulation_risk"] == "high"
        assert len(valid_outcomes(scenario)) >= scenario.expected_checks.min_valid_outcomes
        if scenario.expected_checks.has_agreement_region:
            assert agreement_region(scenario)
        else:
            no_agreement_count += 1
            assert not agreement_region(scenario)

        hard_issues_by_agent = []
        for agent in raw["agents"]:
            hard_constraints = agent["private_profile"]["hard_constraints"]
            hints = agent["allowed_constraint_hint"]["issue_constraints"]
            weights = agent["private_profile"]["utility_weights"]
            assert len(hard_constraints) == 1
            assert hints == {hard_constraints[0]["issue"]: "fixed"}
            assert abs(sum(weights.values()) - 1.0) < 0.0002
            hard_issues_by_agent.append(hard_constraints[0]["issue"])

        assert hard_issues_by_agent[0] != hard_issues_by_agent[1]
        assert raw["generation_meta"]["constraint_issues"] == {
            "ppa_a": hard_issues_by_agent[0],
            "ppa_b": hard_issues_by_agent[1],
        }

    assert no_agreement_count == 160


def _meta_counts(scenarios: list[dict], key: str) -> dict[str, int]:
    return {
        value: sum(1 for scenario in scenarios if scenario["generation_meta"][key] == value)
        for value in {scenario["generation_meta"][key] for scenario in scenarios}
    }


def _matrix_keys(scenarios: list[dict]) -> set[tuple[str, str, str, str]]:
    return {
        (
            scenario["task_family"],
            scenario["complexity_level"],
            scenario["tension_pattern"],
            scenario["variant_id"],
        )
        for scenario in scenarios
    }
