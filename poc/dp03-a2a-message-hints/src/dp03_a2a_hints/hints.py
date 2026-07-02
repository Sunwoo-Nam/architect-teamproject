from __future__ import annotations

from .models import AgentSpec, HintMessage, OutcomeDict, Scenario

HINT_VALUES = {"high", "medium", "low"}
RISK_MULTIPLIERS = {"low": 1.0, "medium": 1.5, "high": 2.0}


def hints_supported(local: AgentSpec, remote: AgentSpec) -> bool:
    return (
        local.capability.preference_hint
        and remote.capability.preference_hint
        and local.capability.hint_schema_version is not None
        and local.capability.hint_schema_version == remote.capability.hint_schema_version
    )


def build_hint(agent: AgentSpec, concession_phase: str | None = "normal") -> HintMessage:
    projection = agent.allowed_hint_projection
    phase = concession_phase if projection.concession_phase_allowed else None
    return HintMessage(
        schema_version=projection.schema_version,
        issue_preferences=dict(projection.issue_preferences),
        issue_flexibility=dict(projection.issue_flexibility),
        hard_constraints=projection.hard_constraints,
        concession_phase=phase,
    )


def hint_valid(hint: HintMessage, scenario: Scenario) -> bool:
    issue_names = set(scenario.issue_names)
    if hint.schema_version != "hint.v1":
        return False
    if not set(hint.issue_preferences).issubset(issue_names):
        return False
    if not set(hint.issue_flexibility).issubset(issue_names):
        return False
    if not set(hint.hard_constraints).issubset(issue_names):
        return False
    if any(value not in HINT_VALUES for value in hint.issue_preferences.values()):
        return False
    if any(value not in HINT_VALUES for value in hint.issue_flexibility.values()):
        return False
    if hint.concession_phase not in {None, "early", "normal", "final"}:
        return False
    return True


def hint_sensitivity_score(hints: tuple[HintMessage, ...], risk: str) -> float:
    multiplier = RISK_MULTIPLIERS[risk]
    total = 0.0
    for hint in hints:
        total += len(hint.issue_preferences)
        total += len(hint.issue_flexibility)
        total += 3 * len(hint.hard_constraints)
        if hint.concession_phase is not None:
            total += 1
    return total * multiplier


def opponent_hint_fit(
    candidate: OutcomeDict,
    opponent_last_offer: OutcomeDict | None,
    hint: HintMessage | None,
) -> float:
    if hint is None or opponent_last_offer is None:
        return 0.0

    score = 0.0
    for issue, preference in hint.issue_preferences.items():
        if candidate.get(issue) != opponent_last_offer.get(issue):
            continue
        if preference == "high":
            score += 1.0
        elif preference == "medium":
            score += 0.5

    for issue, flexibility in hint.issue_flexibility.items():
        if candidate.get(issue) == opponent_last_offer.get(issue):
            if flexibility == "low":
                score += 1.0
            elif flexibility == "medium":
                score += 0.5

    for issue in hint.hard_constraints:
        if candidate.get(issue) == opponent_last_offer.get(issue):
            score += 2.0
    return score
