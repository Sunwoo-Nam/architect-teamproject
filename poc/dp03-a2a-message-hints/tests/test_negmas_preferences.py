from math import isinf

from dp03_a2a_hints.negmas_preferences import (
    make_hard_constraint_predicate,
    make_negmas_base_ufun,
    make_negmas_constrained_ufun,
)
from dp03_a2a_hints.outcome_space import to_tuple
from dp03_a2a_hints.scenario_loader import load_scenario
from dp03_a2a_hints.utility import utility


def test_negmas_base_ufun_matches_internal_utility():
    scenario = load_scenario("scenarios/samples/S001-normal.yaml")
    agent = scenario.agents[0]
    outcome = {
        "slot": "saturday_lunch",
        "area": "near_home",
        "budget_band": "low",
        "notice_period": "three_days",
    }
    outcome_tuple = to_tuple(outcome, scenario.issues)

    negmas_ufun = make_negmas_base_ufun(agent.private_profile, scenario.issues)

    assert negmas_ufun(outcome_tuple) == utility(agent.private_profile, outcome)


def test_negmas_constraint_adapter_rejects_hard_constraint_violation():
    scenario = load_scenario("scenarios/samples/S001-normal.yaml")
    agent = scenario.agents[0]
    valid = {
        "slot": "saturday_lunch",
        "area": "near_home",
        "budget_band": "low",
        "notice_period": "three_days",
    }
    invalid = dict(valid, slot="weekday_evening")

    constrained_ufun = make_negmas_constrained_ufun(agent.private_profile, scenario.issues)

    assert constrained_ufun(to_tuple(valid, scenario.issues)) == utility(agent.private_profile, valid)
    assert isinf(constrained_ufun(to_tuple(invalid, scenario.issues)))
    assert constrained_ufun(to_tuple(invalid, scenario.issues)) < 0
    assert constrained_ufun(None) == agent.private_profile.reservation_value


def test_hard_constraint_predicate_uses_private_profile_not_public_hint():
    scenario = load_scenario("scenarios/samples/S001-normal.yaml")
    agent = scenario.agents[0]
    valid = {
        "slot": "saturday_lunch",
        "area": "near_home",
        "budget_band": "low",
        "notice_period": "three_days",
    }
    invalid = dict(valid, slot="weekday_evening")
    predicate = make_hard_constraint_predicate(agent.private_profile, scenario.issues)

    assert predicate(to_tuple(valid, scenario.issues))
    assert not predicate(to_tuple(invalid, scenario.issues))
