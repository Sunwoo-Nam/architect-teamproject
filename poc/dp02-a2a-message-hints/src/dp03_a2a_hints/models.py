from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple

OutcomeTuple = Tuple[str, ...]
OutcomeDict = Dict[str, str]


class ExperimentGroup(str, Enum):
    A1_DET_OFFER_ONLY = "A1_DET_OFFER_ONLY"
    A2_DET_HINT_AWARE = "A2_DET_HINT_AWARE"
    A3_DET_FALLBACK = "A3_DET_FALLBACK"


@dataclass(frozen=True)
class IssueSpec:
    name: str
    type: str
    values: Tuple[str, ...]
    public: bool = True
    outcome_space: bool = True
    constraint_hintable: bool = True
    order: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Capability:
    constraint_hint: bool
    constraint_hint_schema_version: Optional[str]


@dataclass(frozen=True)
class HardConstraint:
    issue: str
    allowed_values: Tuple[str, ...]


@dataclass(frozen=True)
class ConcessionPolicy:
    type: str
    start_threshold: float
    end_threshold: float


@dataclass(frozen=True)
class PrivateProfile:
    utility_model: str
    utility_weights: Dict[str, float]
    value_scores: Dict[str, Dict[str, float]]
    hard_constraints: Tuple[HardConstraint, ...]
    reservation_value: float
    concession_policy: ConcessionPolicy


@dataclass(frozen=True)
class ConstraintHintPolicy:
    schema_version: str
    anchor: str
    issue_constraints: Dict[str, str]


@dataclass(frozen=True)
class AgentSpec:
    id: str
    role: str
    capability: Capability
    private_profile: PrivateProfile
    allowed_constraint_hint: ConstraintHintPolicy


@dataclass(frozen=True)
class PrivacyLabels:
    pii_raw: bool
    sensitive_reason_present: bool
    exact_value_present: bool
    constraint_hint_accumulation_risk: str
    external_constraint_hint_allowed: bool


@dataclass(frozen=True)
class ExpectedChecks:
    has_agreement_region: bool
    expected_fallback: bool
    expected_timeout_possible: bool
    min_valid_outcomes: int
    min_pareto_candidates: int
    llm_schema_required: bool


@dataclass(frozen=True)
class GenerationMeta:
    generator_version: str
    seed: int
    source: str
    created_from_legacy_poc: bool
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    schema_version: str
    scenario_id: str
    task_family: str
    complexity_level: str
    tension_pattern: str
    variant_id: str
    issues: Tuple[IssueSpec, ...]
    agents: Tuple[AgentSpec, ...]
    privacy_labels: PrivacyLabels
    expected_checks: ExpectedChecks
    generation_meta: GenerationMeta

    @property
    def issue_names(self) -> Tuple[str, ...]:
        return tuple(issue.name for issue in self.issues)


@dataclass(frozen=True)
class RunConfig:
    experiment_group: ExperimentGroup
    n_steps: int = 30
    concession_steps: Optional[int] = None
    repeat_id: str = "r01"
    constraint_hint_weight: float = 0.15


@dataclass(frozen=True)
class AgentRuntime:
    spec: AgentSpec
    offered: Tuple[OutcomeTuple, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ConstraintHintMessage:
    schema_version: str
    anchor: str
    issue_constraints: Dict[str, str]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "anchor": self.anchor,
            "issue_constraints": dict(self.issue_constraints),
        }


@dataclass(frozen=True)
class EventLog:
    step: int
    actor: str
    event_type: str
    outcome: Optional[OutcomeDict]
    response_type: Optional[str]
    constraint_hint: Optional[Dict[str, Any]]
    validator: Dict[str, Any]


@dataclass(frozen=True)
class RunResult:
    run_id: str
    experiment_group: ExperimentGroup
    scenario_id: str
    repeat_id: str
    agreement_success: bool
    agreement_outcome: Optional[OutcomeDict]
    wall_clock_ms: float
    wall_clock_ms_to_agreement: Optional[float]
    steps_to_agreement: Optional[int]
    offer_count_to_agreement: Optional[int]
    rounds_to_agreement: Optional[int]
    atomic_actions_to_agreement: int
    candidate_evaluation_count: int
    hint_fit_evaluation_count: int
    utility_a: Optional[float]
    utility_b: Optional[float]
    joint_utility: Optional[float]
    utilities: Dict[str, float]
    min_utility: Optional[float]
    utility_spread: Optional[float]
    pareto_dominated: Optional[bool]
    pareto_joint_gap: Optional[float]
    constraint_hint_message_count: int
    hint_attached_offer_count: int
    constraint_hint_sensitivity_score: float
    failure_reasons: Tuple[str, ...]
    events: Tuple[EventLog, ...]
