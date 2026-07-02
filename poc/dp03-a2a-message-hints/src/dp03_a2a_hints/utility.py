from __future__ import annotations

from .models import OutcomeDict, PrivateProfile


def utility(profile: PrivateProfile, outcome: OutcomeDict) -> float:
    if profile.utility_model != "linear_additive":
        raise ValueError(f"Unsupported utility model: {profile.utility_model}")
    total = 0.0
    for issue, weight in profile.utility_weights.items():
        value = outcome[issue]
        total += weight * profile.value_scores[issue][value]
    return total


def violates_hard_constraint(profile: PrivateProfile, outcome: OutcomeDict) -> bool:
    for constraint in profile.hard_constraints:
        if outcome[constraint.issue] not in constraint.allowed_values:
            return True
    return False


def threshold(profile: PrivateProfile, step: int, max_steps: int) -> float:
    policy = profile.concession_policy
    if policy.type != "linear":
        raise ValueError(f"Unsupported concession policy: {policy.type}")
    denominator = max(max_steps - 1, 1)
    progress = min(max(step, 0) / denominator, 1.0)
    value = policy.start_threshold - progress * (policy.start_threshold - policy.end_threshold)
    return max(value, profile.reservation_value)


def is_acceptable(profile: PrivateProfile, outcome: OutcomeDict, threshold_value: float) -> bool:
    if violates_hard_constraint(profile, outcome):
        return False
    return utility(profile, outcome) >= threshold_value


def reservation_margin(profile: PrivateProfile, outcome: OutcomeDict) -> float:
    return utility(profile, outcome) - profile.reservation_value
