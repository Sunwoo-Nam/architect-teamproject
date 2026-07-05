from dp03_a2a_hints.hints import (
    build_constraint_hint,
    constraint_hint_sensitivity_score,
    constraint_hints_supported,
)
from dp03_a2a_hints.scenario_loader import load_scenario


def test_constraint_hint_support_and_score():
    scenario = load_scenario("scenarios/samples/S001-normal.yaml")
    first, second = scenario.agents

    assert constraint_hints_supported(first, second)
    hint = build_constraint_hint(
        first,
        {
            "slot": "saturday_lunch",
            "area": "midpoint",
            "budget_band": "medium",
            "notice_period": "same_day",
        },
    )

    assert hint is not None
    assert hint.issue_constraints == {"slot": "fixed", "notice_period": "relaxable"}
    assert (
        constraint_hint_sensitivity_score(
            (hint,),
            scenario.privacy_labels.constraint_hint_accumulation_risk,
        )
        > 0
    )


def test_constraint_hint_support_false_for_fallback_case():
    scenario = load_scenario("scenarios/samples/S099-fallback.yaml")
    first, second = scenario.agents

    assert not constraint_hints_supported(first, second)
