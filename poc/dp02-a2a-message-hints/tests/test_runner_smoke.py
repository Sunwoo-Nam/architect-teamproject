from dp03_a2a_hints import ExperimentGroup, RunConfig, run_scenario
from dp03_a2a_hints.metrics import summarize
from dp03_a2a_hints.scenario_generator import (
    generate_fixed_four_party_scenarios,
    generate_fixed_three_party_scenarios,
)
from dp03_a2a_hints.scenario_loader import load_scenario
from dp03_a2a_hints.scenario_loader import scenario_from_dict


def test_runner_executes_a1_and_a2():
    scenario = load_scenario("scenarios/samples/S001-normal.yaml")

    a1 = run_scenario(scenario, RunConfig(ExperimentGroup.A1_DET_OFFER_ONLY))
    a2 = run_scenario(scenario, RunConfig(ExperimentGroup.A2_DET_HINT_AWARE))

    assert a1.agreement_success
    assert a2.agreement_success
    assert a1.wall_clock_ms > 0
    assert a1.wall_clock_ms_to_agreement is not None
    assert a1.offer_count_to_agreement == a1.rounds_to_agreement
    assert a1.candidate_evaluation_count > 0
    assert a1.constraint_hint_message_count == 0
    assert a2.constraint_hint_message_count > 0
    assert a2.hint_attached_offer_count == a2.constraint_hint_message_count
    assert a2.hint_fit_evaluation_count > 0
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
    assert summary["A1_DET_OFFER_ONLY"]["median_offer_count"] is not None
    assert summary["A1_DET_OFFER_ONLY"]["median_wall_clock_ms_to_agreement"] is not None
    assert summary["A2_DET_HINT_AWARE"]["constraint_hint_message_count"] > 0


def test_runner_can_extend_deadline_without_slowing_concession():
    scenario = load_scenario(
        "scenarios/generated_fixed_only_v1/"
        "F1S070-schedule_coordination-issue_4-mutual_hard_constraint_conflict-"
        "v02_f02_both_agents_different_issue_hard_sharp_s1.yaml"
    )

    baseline = run_scenario(
        scenario,
        RunConfig(
            ExperimentGroup.A1_DET_OFFER_ONLY,
            n_steps=30,
            concession_steps=30,
        ),
    )
    extended = run_scenario(
        scenario,
        RunConfig(
            ExperimentGroup.A1_DET_OFFER_ONLY,
            n_steps=100,
            concession_steps=30,
        ),
    )

    assert not baseline.agreement_success
    assert extended.agreement_success


def test_runner_handles_three_party_constraint_hint_scenario():
    scenario = scenario_from_dict(generate_fixed_three_party_scenarios()[0])

    result = run_scenario(
        scenario,
        RunConfig(
            ExperimentGroup.A2_DET_HINT_AWARE,
            n_steps=100,
            concession_steps=30,
        ),
    )

    assert len(scenario.agents) == 3
    assert result.agreement_success
    assert set(result.utilities) == {"ppa_a", "ppa_b", "ppa_c"}
    assert result.min_utility is not None
    assert result.utility_spread is not None


def test_runner_handles_four_party_constraint_hint_scenario():
    scenario = scenario_from_dict(generate_fixed_four_party_scenarios()[0])

    result = run_scenario(
        scenario,
        RunConfig(
            ExperimentGroup.A2_DET_HINT_AWARE,
            n_steps=100,
            concession_steps=30,
        ),
    )

    assert len(scenario.agents) == 4
    assert result.agreement_success
    assert set(result.utilities) == {"ppa_a", "ppa_b", "ppa_c", "ppa_d"}
    assert result.min_utility is not None
    assert result.utility_spread is not None
