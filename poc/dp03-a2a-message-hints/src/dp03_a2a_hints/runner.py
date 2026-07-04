from __future__ import annotations

import time

from negmas.sao import SAOMechanism

from .hints import constraint_hints_supported
from .models import ExperimentGroup, RunConfig, RunResult, Scenario
from .negotiators import (
    HintAwareNegotiator,
    NegotiationContext,
    OfferOnlyNegotiator,
    context_constraint_hint_sensitivity,
)
from .outcome_space import make_negmas_outcome_space, to_dict
from .utility import utility, violates_hard_constraint
from .validators import pareto_metrics, validate_scenario


def run_scenario(scenario: Scenario, config: RunConfig) -> RunResult:
    validate_scenario(scenario)
    constraint_hint_enabled = _constraint_hint_enabled_for(scenario, config.experiment_group)
    concession_steps = config.concession_steps or config.n_steps
    context = NegotiationContext(
        scenario=scenario,
        n_steps=config.n_steps,
        concession_steps=concession_steps,
        constraint_hint_enabled=constraint_hint_enabled,
        constraint_hint_weight=config.constraint_hint_weight,
    )
    mechanism = SAOMechanism(
        outcome_space=make_negmas_outcome_space(scenario.issues),
        n_steps=config.n_steps,
    )
    for agent in scenario.agents:
        negotiator_cls = HintAwareNegotiator if constraint_hint_enabled else OfferOnlyNegotiator
        mechanism.add(negotiator_cls(agent=agent, context=context))

    start = time.perf_counter()
    state = mechanism.run()
    wall_clock_ms = (time.perf_counter() - start) * 1000
    agreement_tuple = mechanism.agreement or getattr(state, "agreement", None)
    agreement = to_dict(agreement_tuple, scenario.issues) if agreement_tuple else None
    utilities = (
        {
            agent.id: utility(agent.private_profile, agreement)
            for agent in scenario.agents
        }
        if agreement
        else {}
    )
    utility_a = utilities.get(scenario.agents[0].id)
    utility_b = utilities.get(scenario.agents[1].id)
    joint_utility = sum(utilities.values()) / len(utilities) if utilities else None
    min_utility = min(utilities.values()) if utilities else None
    utility_spread = max(utilities.values()) - min(utilities.values()) if utilities else None
    pareto_dominated, pareto_joint_gap = pareto_metrics(scenario, agreement)
    failures = _failure_reasons(scenario, agreement, constraint_hint_enabled, context)
    success = not failures and agreement is not None
    steps = int(getattr(state, "step", 0)) if success else None
    offer_count = len(mechanism.offers) if success else None
    hint_attached_offer_count = len(context.sent_constraint_hints)
    return RunResult(
        run_id=f"{config.experiment_group.value}__{scenario.scenario_id}__{config.repeat_id}",
        experiment_group=config.experiment_group,
        scenario_id=scenario.scenario_id,
        repeat_id=config.repeat_id,
        agreement_success=success,
        agreement_outcome=agreement,
        wall_clock_ms=wall_clock_ms,
        wall_clock_ms_to_agreement=wall_clock_ms if success else None,
        steps_to_agreement=steps,
        offer_count_to_agreement=offer_count,
        rounds_to_agreement=offer_count,
        atomic_actions_to_agreement=len(context.events),
        candidate_evaluation_count=context.candidate_evaluation_count,
        hint_fit_evaluation_count=context.hint_fit_evaluation_count,
        utility_a=utility_a,
        utility_b=utility_b,
        joint_utility=joint_utility,
        utilities=utilities,
        min_utility=min_utility,
        utility_spread=utility_spread,
        pareto_dominated=pareto_dominated,
        pareto_joint_gap=pareto_joint_gap,
        constraint_hint_message_count=len(context.sent_constraint_hints),
        hint_attached_offer_count=hint_attached_offer_count,
        constraint_hint_sensitivity_score=context_constraint_hint_sensitivity(context),
        failure_reasons=tuple(failures),
        events=tuple(context.events),
    )


def _constraint_hint_enabled_for(scenario: Scenario, group: ExperimentGroup) -> bool:
    if group in {ExperimentGroup.A1_DET_OFFER_ONLY, ExperimentGroup.A3_DET_FALLBACK}:
        return False
    return (
        scenario.privacy_labels.external_constraint_hint_allowed
        and all(
            constraint_hints_supported(local, remote)
            for local in scenario.agents
            for remote in scenario.agents
            if local.id != remote.id
        )
    )


def _failure_reasons(
    scenario: Scenario,
    agreement: dict[str, str] | None,
    constraint_hint_enabled: bool,
    context: NegotiationContext,
) -> list[str]:
    failures = []
    if agreement is None:
        failures.append("no_agreement")
    else:
        for agent in scenario.agents:
            profile = agent.private_profile
            if violates_hard_constraint(profile, agreement):
                failures.append("hard_constraint_violation")
            if utility(profile, agreement) < profile.reservation_value:
                failures.append("reservation_violation")

    if not constraint_hint_enabled and context.sent_constraint_hints:
        failures.append("fallback_violation")
    if scenario.expected_checks.expected_fallback and context.sent_constraint_hints:
        failures.append("fallback_violation")
    return sorted(set(failures))
