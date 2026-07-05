from __future__ import annotations

from typing import Any, Mapping

from .models import AgentSpec, ConstraintHintMessage, OutcomeDict, Scenario

CONSTRAINT_HINT_SCHEMA = "constraint_hint.v1"
CONSTRAINT_HINT_VALUES = {"fixed", "relaxable"}
RISK_MULTIPLIERS = {"low": 1.0, "medium": 1.5, "high": 2.0}


def constraint_hints_supported(local: AgentSpec, remote: AgentSpec) -> bool:
    return (
        local.capability.constraint_hint
        and remote.capability.constraint_hint
        and local.capability.constraint_hint_schema_version == CONSTRAINT_HINT_SCHEMA
        and remote.capability.constraint_hint_schema_version == CONSTRAINT_HINT_SCHEMA
    )


def build_constraint_hint(
    agent: AgentSpec,
    offered_outcome: OutcomeDict | None,
) -> ConstraintHintMessage | None:
    policy = agent.allowed_constraint_hint
    issue_constraints: dict[str, str] = {}

    for issue, constraint in policy.issue_constraints.items():
        if constraint == "fixed" and not _fixed_anchor_valid(agent, issue, offered_outcome):
            continue
        issue_constraints[issue] = constraint

    if not issue_constraints:
        return None
    return ConstraintHintMessage(
        schema_version=policy.schema_version,
        anchor=policy.anchor,
        issue_constraints=issue_constraints,
    )


def constraint_hint_from_data(data: Mapping[str, Any] | None) -> ConstraintHintMessage | None:
    if not data or "constraint_hint" not in data:
        return None
    raw = data["constraint_hint"]
    if not isinstance(raw, Mapping):
        return None
    return ConstraintHintMessage(
        schema_version=str(raw.get("schema_version")),
        anchor=str(raw.get("anchor")),
        issue_constraints=dict(raw.get("issue_constraints") or {}),
    )


def constraint_hint_valid(hint: ConstraintHintMessage, scenario: Scenario) -> bool:
    if hint.schema_version != CONSTRAINT_HINT_SCHEMA:
        return False
    if hint.anchor != "offered_outcome":
        return False
    issues_by_name = {issue.name: issue for issue in scenario.issues}
    if not set(hint.issue_constraints).issubset(issues_by_name):
        return False
    if any(not issues_by_name[issue].constraint_hintable for issue in hint.issue_constraints):
        return False
    if any(value not in CONSTRAINT_HINT_VALUES for value in hint.issue_constraints.values()):
        return False
    return True


def constraint_hint_sensitivity_score(
    hints: tuple[ConstraintHintMessage, ...],
    risk: str,
) -> float:
    multiplier = RISK_MULTIPLIERS[risk]
    total = 0.0
    for hint in hints:
        for constraint in hint.issue_constraints.values():
            if constraint == "fixed":
                total += 3.0
            elif constraint == "relaxable":
                total += 1.0
    return total * multiplier


def opponent_constraint_hint_fit(
    candidate: OutcomeDict,
    opponent_last_offer: OutcomeDict | None,
    hint: ConstraintHintMessage | None,
) -> float:
    if hint is None or opponent_last_offer is None:
        return 0.0

    score = 0.0
    for issue, constraint in hint.issue_constraints.items():
        if issue not in candidate or issue not in opponent_last_offer:
            continue
        same_value = candidate[issue] == opponent_last_offer[issue]
        if constraint == "fixed":
            score += 3.0 if same_value else -3.0
        elif constraint == "relaxable" and not same_value:
            score += 0.5
    return score


def _fixed_anchor_valid(
    agent: AgentSpec,
    issue: str,
    offered_outcome: OutcomeDict | None,
) -> bool:
    if offered_outcome is None or issue not in offered_outcome:
        return False
    for constraint in agent.private_profile.hard_constraints:
        if constraint.issue == issue:
            return offered_outcome[issue] in constraint.allowed_values
    return False
