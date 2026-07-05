from __future__ import annotations

from itertools import product

from negmas import make_issue, make_os

from .models import IssueSpec, OutcomeDict, OutcomeTuple


def enumerate_outcomes(issues: tuple[IssueSpec, ...]) -> tuple[OutcomeTuple, ...]:
    value_lists = [issue.values for issue in issues if issue.outcome_space]
    return tuple(tuple(values) for values in product(*value_lists))


def to_tuple(outcome: OutcomeDict, issues: tuple[IssueSpec, ...]) -> OutcomeTuple:
    return tuple(outcome[issue.name] for issue in issues if issue.outcome_space)


def to_dict(outcome: OutcomeTuple, issues: tuple[IssueSpec, ...]) -> OutcomeDict:
    names = [issue.name for issue in issues if issue.outcome_space]
    return dict(zip(names, outcome))


def make_negmas_outcome_space(issues: tuple[IssueSpec, ...]):
    negmas_issues = [make_issue(list(issue.values), name=issue.name) for issue in issues]
    return make_os(issues=negmas_issues)
