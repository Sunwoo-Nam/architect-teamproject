from __future__ import annotations

from collections.abc import Callable
from typing import Any

from negmas.preferences import LinearAdditiveUtilityFunction, UFunConstraint

from .models import IssueSpec, OutcomeDict, PrivateProfile
from .outcome_space import make_negmas_outcome_space, to_dict
from .utility import violates_hard_constraint


def make_negmas_base_ufun(profile: PrivateProfile, issues: tuple[IssueSpec, ...]):
    if profile.utility_model != "linear_additive":
        raise ValueError(f"Unsupported utility model: {profile.utility_model}")
    return LinearAdditiveUtilityFunction(
        values=profile.value_scores,
        weights=profile.utility_weights,
        outcome_space=make_negmas_outcome_space(issues),
        reserved_value=profile.reservation_value,
    )


def make_hard_constraint_predicate(
    profile: PrivateProfile,
    issues: tuple[IssueSpec, ...],
) -> Callable[[Any], bool]:
    def predicate(outcome: Any) -> bool:
        return not violates_hard_constraint(profile, _to_outcome_dict(outcome, issues))

    return predicate


def make_negmas_constrained_ufun(profile: PrivateProfile, issues: tuple[IssueSpec, ...]):
    base_ufun = make_negmas_base_ufun(profile, issues)
    return UFunConstraint(
        ufun=base_ufun,
        constraint=make_hard_constraint_predicate(profile, issues),
        outcome_space=base_ufun.outcome_space,
        reserved_value=profile.reservation_value,
    )


def _to_outcome_dict(outcome: Any, issues: tuple[IssueSpec, ...]) -> OutcomeDict:
    if isinstance(outcome, dict):
        return {str(key): str(value) for key, value in outcome.items()}
    return to_dict(tuple(outcome), issues)
