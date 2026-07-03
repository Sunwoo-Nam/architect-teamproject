from __future__ import annotations

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

    state = mechanism.run()
    agreement_tuple = mechanism.agreement or getattr(state, "agreement", None)
    agreement = to_dict(agreement_tuple, scenario.issues) if agreement_tuple else None
    utility_a = utility(scenario.agents[0].private_profile, agreement) if agreement else None
    utility_b = utility(scenario.agents[1].private_profile, agreement) if agreement else None
    joint_utility = (utility_a + utility_b) / 2 if utility_a is not None and utility_b is not None else None
    pareto_dominated, pareto_joint_gap = pareto_metrics(scenario, agreement)
    failures = _failure_reasons(scenario, agreement, constraint_hint_enabled, context)
    success = not failures and agreement is not None
    rounds = len(mechanism.offers) if success else None
    return RunResult(
        run_id=f"{config.experiment_group.value}__{scenario.scenario_id}__{config.repeat_id}",
        experiment_group=config.experiment_group,
        scenario_id=scenario.scenario_id,
        repeat_id=config.repeat_id,
        agreement_success=success,
        agreement_outcome=agreement,
        rounds_to_agreement=rounds,
        atomic_actions_to_agreement=len(context.events),
        utility_a=utility_a,
        utility_b=utility_b,
        joint_utility=joint_utility,
        pareto_dominated=pareto_dominated,
        pareto_joint_gap=pareto_joint_gap,
        constraint_hint_message_count=len(context.sent_constraint_hints),
        constraint_hint_sensitivity_score=context_constraint_hint_sensitivity(context),
        failure_reasons=tuple(failures),
        events=tuple(context.events),
    )


def _constraint_hint_enabled_for(scenario: Scenario, group: ExperimentGroup) -> bool:
    if group in {ExperimentGroup.A1_DET_OFFER_ONLY, ExperimentGroup.A3_DET_FALLBACK}:
        return False
    first, second = scenario.agents
    return (
        scenario.privacy_labels.external_constraint_hint_allowed
        and constraint_hints_supported(first, second)
        and constraint_hints_supported(second, first)
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
