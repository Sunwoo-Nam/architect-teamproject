from dp03_a2a_hints.scenario_generator import (
    COMPLEXITY_LEVELS,
    TASK_FAMILIES,
    TENSION_PATTERNS,
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
