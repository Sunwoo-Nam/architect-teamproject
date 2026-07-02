from dp03_a2a_hints.outcome_space import enumerate_outcomes, to_dict, to_tuple
from dp03_a2a_hints.scenario_loader import load_scenario


def test_outcome_space_round_trip():
    scenario = load_scenario("scenarios/samples/S099-fallback.yaml")
    outcomes = enumerate_outcomes(scenario.issues)

    assert len(outcomes) == 27
    outcome_dict = to_dict(outcomes[0], scenario.issues)
    assert to_tuple(outcome_dict, scenario.issues) == outcomes[0]
