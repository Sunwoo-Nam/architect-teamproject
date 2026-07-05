from dp03_a2a_hints.scenario_loader import load_scenario
from dp03_a2a_hints.validators import agreement_region, validate_scenario


def test_sample_scenarios_are_valid():
    normal = load_scenario("scenarios/samples/S001-normal.yaml")
    fallback = load_scenario("scenarios/samples/S099-fallback.yaml")

    validate_scenario(normal)
    validate_scenario(fallback)
    assert agreement_region(normal)
    assert agreement_region(fallback)
