from __future__ import annotations

from itertools import combinations
from math import isclose

from .models import ConstraintHintMessage, OutcomeDict, OutcomeTuple, Scenario
from .outcome_space import enumerate_outcomes, to_dict
from .utility import utility, violates_hard_constraint


def validate_scenario(scenario: Scenario) -> None:
    expected_count = int(scenario.complexity_level.split("_")[1])
    if len(scenario.issues) != expected_count:
        raise ValueError("complexity_level does not match issue count")
    if scenario.privacy_labels.pii_raw:
        raise ValueError("pii_raw must be false")
    if scenario.privacy_labels.sensitive_reason_present:
        raise ValueError("sensitive_reason_present must be false")
    if scenario.privacy_labels.exact_value_present:
        raise ValueError("exact_value_present must be false")
    if scenario.generation_meta.created_from_legacy_poc:
        raise ValueError("legacy PoC data must not be used")

    issue_names = set(scenario.issue_names)
    issues_by_name = {issue.name: issue for issue in scenario.issues}
    for agent in scenario.agents:
        weights = agent.private_profile.utility_weights
        if set(weights) != issue_names:
            raise ValueError(f"{agent.id}: utility_weights issue mismatch")
        if not isclose(sum(weights.values()), 1.0, abs_tol=1e-6):
            raise ValueError(f"{agent.id}: utility_weights must sum to 1.0")
        for issue in scenario.issues:
            scores = agent.private_profile.value_scores.get(issue.name)
            if scores is None or set(scores) != set(issue.values):
                raise ValueError(f"{agent.id}: value_scores mismatch for {issue.name}")
            if any(score < 0.0 or score > 1.0 for score in scores.values()):
                raise ValueError(f"{agent.id}: value_scores out of range")
        for constraint in agent.private_profile.hard_constraints:
            if constraint.issue not in issue_names:
                raise ValueError(f"{agent.id}: unknown hard constraint issue")
            values = next(issue.values for issue in scenario.issues if issue.name == constraint.issue)
            if not set(constraint.allowed_values).issubset(values):
                raise ValueError(f"{agent.id}: invalid hard constraint values")
        hard_constraint_issues = {constraint.issue for constraint in agent.private_profile.hard_constraints}
        policy = agent.allowed_constraint_hint
        if policy.schema_version != "constraint_hint.v1":
            raise ValueError(f"{agent.id}: unsupported constraint hint schema")
        if policy.anchor != "offered_outcome":
            raise ValueError(f"{agent.id}: unsupported constraint hint anchor")
        for issue, constraint in policy.issue_constraints.items():
            if issue not in issue_names:
                raise ValueError(f"{agent.id}: unknown constraint hint issue")
            if not issues_by_name[issue].constraint_hintable:
                raise ValueError(f"{agent.id}: non-hintable constraint hint issue")
            if constraint not in {"fixed", "relaxable"}:
                raise ValueError(f"{agent.id}: invalid constraint hint value")
            if constraint == "fixed" and issue not in hard_constraint_issues:
                raise ValueError(f"{agent.id}: fixed constraint hint without hard constraint")

    valid = valid_outcomes(scenario)
    if len(valid) < scenario.expected_checks.min_valid_outcomes:
        raise ValueError("not enough valid outcomes")
    if scenario.expected_checks.has_agreement_region and not agreement_region(scenario):
        raise ValueError("expected agreement region is empty")


def valid_outcomes(scenario: Scenario) -> tuple[OutcomeDict, ...]:
    outcomes = []
    for outcome_tuple in enumerate_outcomes(scenario.issues):
        outcome = to_dict(outcome_tuple, scenario.issues)
        if all(not violates_hard_constraint(agent.private_profile, outcome) for agent in scenario.agents):
            outcomes.append(outcome)
    return tuple(outcomes)


def agreement_region(scenario: Scenario) -> tuple[OutcomeDict, ...]:
    outcomes = []
    for outcome in valid_outcomes(scenario):
        if all(
            utility(agent.private_profile, outcome) >= agent.private_profile.reservation_value
            for agent in scenario.agents
        ):
            outcomes.append(outcome)
    return tuple(outcomes)


def validate_outcome_tuple(outcome: OutcomeTuple, scenario: Scenario) -> bool:
    return outcome in enumerate_outcomes(scenario.issues)


def validate_constraint_hint(hint: ConstraintHintMessage, scenario: Scenario) -> bool:
    from .hints import constraint_hint_valid

    return constraint_hint_valid(hint, scenario)


def pareto_frontier(scenario: Scenario) -> tuple[OutcomeDict, ...]:
    candidates = valid_outcomes(scenario)
    frontier = []
    for candidate in candidates:
        candidate_utilities = tuple(utility(agent.private_profile, candidate) for agent in scenario.agents)
        dominated = False
        for other in candidates:
            other_utilities = tuple(utility(agent.private_profile, other) for agent in scenario.agents)
            if all(o >= c for o, c in zip(other_utilities, candidate_utilities)) and any(
                o > c for o, c in zip(other_utilities, candidate_utilities)
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return tuple(frontier)


def pareto_metrics(scenario: Scenario, agreement: OutcomeDict | None) -> tuple[bool | None, float | None]:
    if agreement is None:
        return None, None
    frontier = pareto_frontier(scenario)
    agreement_joint = _joint_utility(scenario, agreement)
    max_joint = max(_joint_utility(scenario, outcome) for outcome in frontier)
    dominated = agreement not in frontier
    return dominated, max_joint - agreement_joint


def _joint_utility(scenario: Scenario, outcome: OutcomeDict) -> float:
    return sum(utility(agent.private_profile, outcome) for agent in scenario.agents) / len(scenario.agents)
