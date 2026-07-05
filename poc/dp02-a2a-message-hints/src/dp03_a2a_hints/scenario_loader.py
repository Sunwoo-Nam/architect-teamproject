from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from .models import (
    AgentSpec,
    Capability,
    ConcessionPolicy,
    ConstraintHintPolicy,
    ExpectedChecks,
    GenerationMeta,
    HardConstraint,
    IssueSpec,
    PrivacyLabels,
    PrivateProfile,
    Scenario,
)


def load_scenario(path: str | Path) -> Scenario:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return scenario_from_dict(data)


def scenario_from_dict(data: Mapping[str, Any]) -> Scenario:
    issues = tuple(_issue_from_dict(raw) for raw in data["domain"]["issues"])
    agents = tuple(_agent_from_dict(raw) for raw in data["agents"])
    if len(agents) < 2:
        raise ValueError("Track A expects at least two agents")
    return Scenario(
        schema_version=data["schema_version"],
        scenario_id=data["scenario_id"],
        task_family=data["task_family"],
        complexity_level=data["complexity_level"],
        tension_pattern=data["tension_pattern"],
        variant_id=data["variant_id"],
        issues=issues,
        agents=agents,
        privacy_labels=_privacy_from_dict(data["privacy_labels"]),
        expected_checks=_expected_from_dict(data["expected_checks"]),
        generation_meta=_generation_meta_from_dict(data["generation_meta"]),
    )


def _issue_from_dict(data: Mapping[str, Any]) -> IssueSpec:
    return IssueSpec(
        name=data["name"],
        type=data["type"],
        values=tuple(data["values"]),
        public=bool(data["public"]),
        outcome_space=bool(data["outcome_space"]),
        constraint_hintable=bool(data["constraint_hintable"]),
        order=tuple(data.get("order") or ()),
    )


def _agent_from_dict(data: Mapping[str, Any]) -> AgentSpec:
    capability = Capability(
        constraint_hint=bool(data["capability"]["constraint_hint"]),
        constraint_hint_schema_version=data["capability"]["constraint_hint_schema_version"],
    )
    private_profile = data["private_profile"]
    constraints = tuple(
        HardConstraint(issue=raw["issue"], allowed_values=tuple(raw["allowed_values"]))
        for raw in private_profile["hard_constraints"]
    )
    policy = ConcessionPolicy(
        type=private_profile["concession_policy"]["type"],
        start_threshold=float(private_profile["concession_policy"]["start_threshold"]),
        end_threshold=float(private_profile["concession_policy"]["end_threshold"]),
    )
    profile = PrivateProfile(
        utility_model=private_profile["utility_model"],
        utility_weights={k: float(v) for k, v in private_profile["utility_weights"].items()},
        value_scores={
            issue: {value: float(score) for value, score in scores.items()}
            for issue, scores in private_profile["value_scores"].items()
        },
        hard_constraints=constraints,
        reservation_value=float(private_profile["reservation_value"]),
        concession_policy=policy,
    )
    projection = data["allowed_constraint_hint"]
    constraint_hint_policy = ConstraintHintPolicy(
        schema_version=projection["schema_version"],
        anchor=projection["anchor"],
        issue_constraints=dict(projection["issue_constraints"]),
    )
    return AgentSpec(
        id=data["id"],
        role=data["role"],
        capability=capability,
        private_profile=profile,
        allowed_constraint_hint=constraint_hint_policy,
    )


def _privacy_from_dict(data: Mapping[str, Any]) -> PrivacyLabels:
    return PrivacyLabels(
        pii_raw=bool(data["pii_raw"]),
        sensitive_reason_present=bool(data["sensitive_reason_present"]),
        exact_value_present=bool(data["exact_value_present"]),
        constraint_hint_accumulation_risk=data["constraint_hint_accumulation_risk"],
        external_constraint_hint_allowed=bool(data["external_constraint_hint_allowed"]),
    )


def _expected_from_dict(data: Mapping[str, Any]) -> ExpectedChecks:
    return ExpectedChecks(
        has_agreement_region=bool(data["has_agreement_region"]),
        expected_fallback=bool(data["expected_fallback"]),
        expected_timeout_possible=bool(data["expected_timeout_possible"]),
        min_valid_outcomes=int(data["min_valid_outcomes"]),
        min_pareto_candidates=int(data["min_pareto_candidates"]),
        llm_schema_required=bool(data["llm_schema_required"]),
    )


def _generation_meta_from_dict(data: Mapping[str, Any]) -> GenerationMeta:
    known_keys = {"generator_version", "seed", "source", "created_from_legacy_poc"}
    return GenerationMeta(
        generator_version=data["generator_version"],
        seed=int(data["seed"]),
        source=data["source"],
        created_from_legacy_poc=bool(data["created_from_legacy_poc"]),
        extra={key: value for key, value in data.items() if key not in known_keys},
    )
