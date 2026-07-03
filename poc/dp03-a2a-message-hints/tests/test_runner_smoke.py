from dp03_a2a_hints import ExperimentGroup, RunConfig, run_scenario
from dp03_a2a_hints.metrics import summarize
from dp03_a2a_hints.scenario_loader import load_scenario


def test_runner_executes_a1_and_a2():
    scenario = load_scenario("scenarios/samples/S001-normal.yaml")

    a1 = run_scenario(scenario, RunConfig(ExperimentGroup.A1_DET_OFFER_ONLY))
    a2 = run_scenario(scenario, RunConfig(ExperimentGroup.A2_DET_HINT_AWARE))

    assert a1.agreement_success
    assert a2.agreement_success
    assert a1.constraint_hint_message_count == 0
    assert a2.constraint_hint_message_count > 0
    assert any(event.event_type == "response" and event.constraint_hint for event in a2.events)
    assert not a1.failure_reasons
    assert not a2.failure_reasons


def test_runner_fallback_sends_no_hints():
    scenario = load_scenario("scenarios/samples/S099-fallback.yaml")

    result = run_scenario(scenario, RunConfig(ExperimentGroup.A3_DET_FALLBACK))

    assert result.agreement_success
    assert result.constraint_hint_message_count == 0
    assert result.constraint_hint_sensitivity_score == 0
    assert not result.failure_reasons


def test_summary_groups_results():
    scenario = load_scenario("scenarios/samples/S001-normal.yaml")
    results = [
        run_scenario(scenario, RunConfig(ExperimentGroup.A1_DET_OFFER_ONLY)),
        run_scenario(scenario, RunConfig(ExperimentGroup.A2_DET_HINT_AWARE)),
    ]

    summary = summarize(results)

    assert summary["A1_DET_OFFER_ONLY"]["agreement_rate"] == 1
    assert summary["A2_DET_HINT_AWARE"]["constraint_hint_message_count"] > 0
