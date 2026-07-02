from dp03_a2a_hints.hints import build_hint, hint_sensitivity_score, hints_supported
from dp03_a2a_hints.scenario_loader import load_scenario


def test_hint_support_and_score():
    scenario = load_scenario("scenarios/samples/S001-normal.yaml")
    first, second = scenario.agents

    assert hints_supported(first, second)
    hint = build_hint(first, "early")
    assert hint.concession_phase == "early"
    assert hint_sensitivity_score((hint,), scenario.privacy_labels.hint_accumulation_risk) > 0


def test_hint_support_false_for_fallback_case():
    scenario = load_scenario("scenarios/samples/S099-fallback.yaml")
    first, second = scenario.agents

    assert not hints_supported(first, second)
