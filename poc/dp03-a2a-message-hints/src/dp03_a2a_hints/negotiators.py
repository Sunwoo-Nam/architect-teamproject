from __future__ import annotations

from dataclasses import dataclass, field

from negmas.outcomes.common import ExtendedOutcome
from negmas.sao import ResponseType, SAONegotiator, SAOState

from .hints import (
    build_constraint_hint,
    constraint_hint_from_data,
    constraint_hint_sensitivity_score,
    constraint_hints_supported,
    opponent_constraint_hint_fit,
)
from .models import AgentSpec, ConstraintHintMessage, EventLog, OutcomeDict, OutcomeTuple, Scenario
from .outcome_space import enumerate_outcomes, to_dict
from .utility import is_acceptable, threshold, utility, violates_hard_constraint
from .validators import validate_constraint_hint, validate_outcome_tuple


@dataclass
class NegotiationContext:
    scenario: Scenario
    n_steps: int
    constraint_hint_enabled: bool
    constraint_hint_weight: float = 0.15
    constraint_hints_by_actor: dict[str, ConstraintHintMessage] = field(default_factory=dict)
    last_offer_by_actor: dict[str, OutcomeDict] = field(default_factory=dict)
    sent_constraint_hints: list[ConstraintHintMessage] = field(default_factory=list)
    events: list[EventLog] = field(default_factory=list)

    def opponent_of(self, actor_id: str) -> AgentSpec:
        for agent in self.scenario.agents:
            if agent.id != actor_id:
                return agent
        raise ValueError(f"No opponent found for {actor_id}")

    def record_event(
        self,
        *,
        step: int,
        actor: str,
        event_type: str,
        outcome: OutcomeDict | None,
        response_type: str | None,
        constraint_hint: ConstraintHintMessage | None,
        validator: dict,
    ) -> None:
        self.events.append(
            EventLog(
                step=step,
                actor=actor,
                event_type=event_type,
                outcome=outcome,
                response_type=response_type,
                constraint_hint=constraint_hint.as_dict() if constraint_hint else None,
                validator=validator,
            )
        )


class OfferOnlyNegotiator(SAONegotiator):
    def __init__(self, agent: AgentSpec, context: NegotiationContext, **kwargs):
        super().__init__(name=agent.id, **kwargs)
        self.agent = agent
        self.context = context
        self._offered: set[OutcomeTuple] = set()

    def propose(self, state: SAOState, dest: str | None = None) -> OutcomeTuple | ExtendedOutcome | None:
        offer = self._select_offer(state)
        outcome_dict = to_dict(offer, self.context.scenario.issues) if offer else None
        constraint_hint = self._maybe_publish_constraint_hint(outcome_dict)
        if offer:
            self._offered.add(offer)
            self.context.last_offer_by_actor[self.agent.id] = outcome_dict or {}
        self.context.record_event(
            step=state.step,
            actor=self.agent.id,
            event_type="offer" if offer else "no_offer",
            outcome=outcome_dict,
            response_type=None,
            constraint_hint=constraint_hint,
            validator={
                "outcome_valid": bool(offer and validate_outcome_tuple(offer, self.context.scenario)),
                "constraint_hint_valid": (
                    True
                    if constraint_hint is None
                    else validate_constraint_hint(constraint_hint, self.context.scenario)
                ),
                "prohibited_content": False,
            },
        )
        if offer and constraint_hint:
            return ExtendedOutcome(
                outcome=offer,
                data={"constraint_hint": constraint_hint.as_dict()},
            )
        return offer

    def respond(self, state: SAOState, source: str | None = None) -> ResponseType:
        current_offer = state.current_offer
        inbound_constraint_hint = constraint_hint_from_data(state.current_data)
        response = self._response_for_offer(current_offer, state.step)
        outcome = (
            to_dict(current_offer, self.context.scenario.issues)
            if current_offer and validate_outcome_tuple(current_offer, self.context.scenario)
            else None
        )
        opponent = self.context.opponent_of(self.agent.id)
        if outcome:
            self.context.last_offer_by_actor[opponent.id] = outcome
        constraint_hint_valid = (
            True
            if inbound_constraint_hint is None
            else validate_constraint_hint(inbound_constraint_hint, self.context.scenario)
        )
        if inbound_constraint_hint and constraint_hint_valid:
            self.context.constraint_hints_by_actor[opponent.id] = inbound_constraint_hint
        self.context.record_event(
            step=state.step,
            actor=self.agent.id,
            event_type="response",
            outcome=outcome,
            response_type=response.name,
            constraint_hint=inbound_constraint_hint,
            validator={
                "outcome_valid": outcome is not None,
                "hard_constraint_violation": bool(
                    outcome and violates_hard_constraint(self.agent.private_profile, outcome)
                ),
                "constraint_hint_valid": constraint_hint_valid,
                "prohibited_content": False,
            },
        )
        return response

    def _select_offer(self, state: SAOState) -> OutcomeTuple | None:
        candidates = self._candidate_outcomes(state.step)
        if not candidates:
            return None
        return candidates[0][1]

    def _candidate_outcomes(self, step: int) -> list[tuple[float, OutcomeTuple]]:
        profile = self.agent.private_profile
        threshold_value = threshold(profile, step, self.context.n_steps)
        outcomes = []
        fallback_outcomes = []
        for outcome_tuple in enumerate_outcomes(self.context.scenario.issues):
            outcome = to_dict(outcome_tuple, self.context.scenario.issues)
            if violates_hard_constraint(profile, outcome):
                continue
            score = utility(profile, outcome)
            scored = (self._proposal_score(outcome_tuple, outcome, score), outcome_tuple)
            if score >= threshold_value:
                outcomes.append(scored)
            elif score >= profile.reservation_value:
                fallback_outcomes.append(scored)
        target = outcomes or fallback_outcomes
        target.sort(key=lambda item: (-item[0], item[1]))
        return target

    def _proposal_score(self, outcome_tuple: OutcomeTuple, outcome: OutcomeDict, own_utility: float) -> float:
        penalty = -2.0 if outcome_tuple in self._offered else 0.0
        return own_utility + penalty

    def _response_for_offer(self, offer: OutcomeTuple | None, step: int) -> ResponseType:
        if offer is None or not validate_outcome_tuple(offer, self.context.scenario):
            return ResponseType.REJECT_OFFER
        outcome = to_dict(offer, self.context.scenario.issues)
        threshold_value = threshold(self.agent.private_profile, step, self.context.n_steps)
        if is_acceptable(self.agent.private_profile, outcome, threshold_value):
            return ResponseType.ACCEPT_OFFER
        last_step = step >= self.context.n_steps - 2
        if last_step and is_acceptable(
            self.agent.private_profile,
            outcome,
            self.agent.private_profile.reservation_value,
        ):
            return ResponseType.ACCEPT_OFFER
        return ResponseType.REJECT_OFFER

    def _maybe_publish_constraint_hint(self, outcome: OutcomeDict | None) -> ConstraintHintMessage | None:
        return None


class HintAwareNegotiator(OfferOnlyNegotiator):
    def _proposal_score(self, outcome_tuple: OutcomeTuple, outcome: OutcomeDict, own_utility: float) -> float:
        score = super()._proposal_score(outcome_tuple, outcome, own_utility)
        if not self.context.constraint_hint_enabled:
            return score
        opponent = self.context.opponent_of(self.agent.id)
        opponent_hint = self.context.constraint_hints_by_actor.get(opponent.id)
        opponent_last_offer = self.context.last_offer_by_actor.get(opponent.id)
        fit = opponent_constraint_hint_fit(outcome, opponent_last_offer, opponent_hint)
        return score + self.context.constraint_hint_weight * fit

    def _maybe_publish_constraint_hint(self, outcome: OutcomeDict | None) -> ConstraintHintMessage | None:
        opponent = self.context.opponent_of(self.agent.id)
        if not self.context.constraint_hint_enabled or not constraint_hints_supported(self.agent, opponent):
            return None
        hint = build_constraint_hint(self.agent, outcome)
        if hint is None:
            return None
        self.context.sent_constraint_hints.append(hint)
        return hint


def context_constraint_hint_sensitivity(context: NegotiationContext) -> float:
    return constraint_hint_sensitivity_score(
        tuple(context.sent_constraint_hints),
        context.scenario.privacy_labels.constraint_hint_accumulation_risk,
    )
