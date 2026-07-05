from dp03_a2a_hints.outcome_space import to_dict
from dp03_a2a_hints.scenario_loader import load_scenario
from dp03_a2a_hints.utility import threshold, utility, violates_hard_constraint


def test_utility_and_hard_constraint():
    scenario = load_scenario("scenarios/samples/S001-normal.yaml")
    agent = scenario.agents[0]
    outcome = {
        "slot": "weekday_evening",
        "area": "near_home",
        "budget_band": "low",
        "notice_period": "three_days",
    }

    assert violates_hard_constraint(agent.private_profile, outcome)

    valid_outcome = dict(outcome, slot="saturday_lunch")
    assert utility(agent.private_profile, valid_outcome) > agent.private_profile.reservation_value
    assert not violates_hard_constraint(agent.private_profile, valid_outcome)


def test_linear_threshold_reaches_reservation():
    scenario = load_scenario("scenarios/samples/S001-normal.yaml")
    profile = scenario.agents[0].private_profile

    assert threshold(profile, 0, 30) == profile.concession_policy.start_threshold
    assert threshold(profile, 29, 30) == profile.reservation_value
