from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

from .metrics import summarize
from .models import ExperimentGroup, RunConfig, RunResult, Scenario
from .runner import run_scenario
from .scenario_loader import load_scenario

TRACK_A_GROUPS = (
    ExperimentGroup.A1_DET_OFFER_ONLY,
    ExperimentGroup.A2_DET_HINT_AWARE,
)
META_BREAKDOWN_AXES = (
    "party_count",
    "fixed_pattern",
    "participation_pattern",
    "constraint_topology",
    "difficulty_stratum",
    "utility_shape",
    "issue_pair_pattern",
    "complexity_focus",
)


def run_scenario_matrix(
    scenario_dir: Path,
    groups: tuple[ExperimentGroup, ...] = TRACK_A_GROUPS,
    n_steps: int = 30,
    concession_steps: int | None = None,
    constraint_hint_weight: float = 0.15,
    repeat_count: int = 1,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    scenarios: dict[str, Scenario] = {}
    for path in sorted(scenario_dir.glob("*.yaml")):
        scenario = load_scenario(path)
        scenarios[scenario.scenario_id] = scenario
        for repeat_index in range(repeat_count):
            repeat_id = f"r{repeat_index + 1:02d}"
            for group in groups:
                result = run_scenario(
                    scenario,
                    RunConfig(
                        experiment_group=group,
                        n_steps=n_steps,
                        concession_steps=concession_steps,
                        repeat_id=repeat_id,
                        constraint_hint_weight=constraint_hint_weight,
                    ),
                )
                records.append(result_record(result, scenario, path))
    comparisons = scenario_comparisons(records, scenarios)
    return records, comparisons


def write_batch_outputs(
    records: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "run_results.jsonl"
    comparison_path = output_dir / "scenario_comparison.jsonl"
    summary_path = output_dir / "metric_summary.json"

    result_path.write_text(_jsonl(records), encoding="utf-8")
    comparison_path.write_text(_jsonl(comparisons), encoding="utf-8")
    summary = batch_summary(records, comparisons)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    return {
        "run_results": str(result_path),
        "scenario_comparison": str(comparison_path),
        "metric_summary": str(summary_path),
        "run_count": len(records),
        "scenario_count": len({record["scenario_id"] for record in records}),
        "comparison_count": len(comparisons),
        "repeat_count": len({record.get("repeat_id", "r01") for record in records}),
    }


def result_record(result: RunResult, scenario: Scenario, path: Path) -> dict[str, Any]:
    record = {
        "run_id": result.run_id,
        "scenario_file": path.name,
        "scenario_id": result.scenario_id,
        "repeat_id": result.repeat_id,
        "task_family": scenario.task_family,
        "complexity_level": scenario.complexity_level,
        "tension_pattern": scenario.tension_pattern,
        "variant_id": scenario.variant_id,
        "experiment_group": result.experiment_group.value,
        "agreement_success": result.agreement_success,
        "wall_clock_ms": result.wall_clock_ms,
        "wall_clock_ms_to_agreement": result.wall_clock_ms_to_agreement,
        "steps_to_agreement": result.steps_to_agreement,
        "offer_count_to_agreement": result.offer_count_to_agreement,
        "rounds_to_agreement": result.rounds_to_agreement,
        "atomic_actions_to_agreement": result.atomic_actions_to_agreement,
        "candidate_evaluation_count": result.candidate_evaluation_count,
        "hint_fit_evaluation_count": result.hint_fit_evaluation_count,
        "agreement_outcome": result.agreement_outcome,
        "utility_a": result.utility_a,
        "utility_b": result.utility_b,
        "joint_utility": result.joint_utility,
        "utilities": result.utilities,
        "min_utility": result.min_utility,
        "utility_spread": result.utility_spread,
        "pareto_dominated": result.pareto_dominated,
        "pareto_joint_gap": result.pareto_joint_gap,
        "constraint_hint_message_count": result.constraint_hint_message_count,
        "hint_attached_offer_count": result.hint_attached_offer_count,
        "constraint_hint_sensitivity_score": result.constraint_hint_sensitivity_score,
        "failure_reasons": list(result.failure_reasons),
    }
    record.update(scenario.generation_meta.extra)
    return record


def scenario_comparisons(
    records: list[dict[str, Any]],
    scenarios: dict[str, Scenario],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for record in records:
        key = (record["scenario_id"], record.get("repeat_id", "r01"))
        grouped.setdefault(key, {})[record["experiment_group"]] = record

    comparisons = []
    for (scenario_id, repeat_id), group_records in sorted(grouped.items()):
        a1 = group_records.get(ExperimentGroup.A1_DET_OFFER_ONLY.value)
        a2 = group_records.get(ExperimentGroup.A2_DET_HINT_AWARE.value)
        if a1 is None or a2 is None:
            continue
        scenario = scenarios[scenario_id]
        comparisons.append(
            _with_generation_meta(
                {
                    "scenario_id": scenario_id,
                    "repeat_id": repeat_id,
                    "task_family": scenario.task_family,
                    "complexity_level": scenario.complexity_level,
                    "tension_pattern": scenario.tension_pattern,
                    "variant_id": scenario.variant_id,
                    "a1_success": a1["agreement_success"],
                    "a2_success": a2["agreement_success"],
                    "wall_clock_ms_delta_a2_minus_a1": _delta(a2["wall_clock_ms"], a1["wall_clock_ms"]),
                    "wall_clock_ms_to_agreement_delta_a2_minus_a1": _delta(
                        a2["wall_clock_ms_to_agreement"],
                        a1["wall_clock_ms_to_agreement"],
                    ),
                    "step_delta_a2_minus_a1": _delta(a2["steps_to_agreement"], a1["steps_to_agreement"]),
                    "offer_count_delta_a2_minus_a1": _delta(
                        a2["offer_count_to_agreement"],
                        a1["offer_count_to_agreement"],
                    ),
                    "round_delta_a2_minus_a1": _delta(a2["rounds_to_agreement"], a1["rounds_to_agreement"]),
                    "atomic_actions_delta_a2_minus_a1": _delta(
                        a2["atomic_actions_to_agreement"],
                        a1["atomic_actions_to_agreement"],
                    ),
                    "candidate_evaluation_count_delta_a2_minus_a1": _delta(
                        a2["candidate_evaluation_count"],
                        a1["candidate_evaluation_count"],
                    ),
                    "hint_fit_evaluation_count_delta_a2_minus_a1": _delta(
                        a2["hint_fit_evaluation_count"],
                        a1["hint_fit_evaluation_count"],
                    ),
                    "hint_attached_offer_count_delta_a2_minus_a1": _delta(
                        a2["hint_attached_offer_count"],
                        a1["hint_attached_offer_count"],
                    ),
                    "joint_utility_delta_a2_minus_a1": _delta(a2["joint_utility"], a1["joint_utility"]),
                    "min_utility_delta_a2_minus_a1": _delta(a2["min_utility"], a1["min_utility"]),
                    "utility_spread_delta_a2_minus_a1": _delta(
                        a2["utility_spread"],
                        a1["utility_spread"],
                    ),
                    "pareto_joint_gap_delta_a2_minus_a1": _delta(
                        a2["pareto_joint_gap"],
                        a1["pareto_joint_gap"],
                    ),
                    "a2_constraint_hint_message_count": a2["constraint_hint_message_count"],
                    "a2_constraint_hint_sensitivity_score": a2["constraint_hint_sensitivity_score"],
                    "a1_failure_reasons": a1["failure_reasons"],
                    "a2_failure_reasons": a2["failure_reasons"],
                },
                scenario,
            )
        )
    return comparisons


def batch_summary(records: list[dict[str, Any]], comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    synthetic_results = [_record_to_result(record) for record in records]
    wall_clock_deltas = _deltas(comparisons, "wall_clock_ms_delta_a2_minus_a1")
    wall_clock_agreement_deltas = _deltas(comparisons, "wall_clock_ms_to_agreement_delta_a2_minus_a1")
    round_deltas = [
        item["round_delta_a2_minus_a1"]
        for item in comparisons
        if item["round_delta_a2_minus_a1"] is not None
    ]
    offer_deltas = _deltas(comparisons, "offer_count_delta_a2_minus_a1")
    step_deltas = [
        item["step_delta_a2_minus_a1"]
        for item in comparisons
        if item["step_delta_a2_minus_a1"] is not None
    ]
    atomic_action_deltas = _deltas(comparisons, "atomic_actions_delta_a2_minus_a1")
    candidate_deltas = _deltas(comparisons, "candidate_evaluation_count_delta_a2_minus_a1")
    hint_fit_deltas = _deltas(comparisons, "hint_fit_evaluation_count_delta_a2_minus_a1")
    hint_attached_deltas = _deltas(comparisons, "hint_attached_offer_count_delta_a2_minus_a1")
    utility_deltas = [
        item["joint_utility_delta_a2_minus_a1"]
        for item in comparisons
        if item["joint_utility_delta_a2_minus_a1"] is not None
    ]
    min_utility_deltas = [
        item["min_utility_delta_a2_minus_a1"]
        for item in comparisons
        if item["min_utility_delta_a2_minus_a1"] is not None
    ]
    spread_deltas = [
        item["utility_spread_delta_a2_minus_a1"]
        for item in comparisons
        if item["utility_spread_delta_a2_minus_a1"] is not None
    ]
    return {
        "group_summary": summarize(synthetic_results),
        "comparison_summary": {
            "scenario_count": len({item["scenario_id"] for item in comparisons}),
            "comparison_count": len(comparisons),
            "repeat_count": len({item.get("repeat_id", "r01") for item in comparisons}),
            "a2_faster_wall_clock_count": sum(1 for value in wall_clock_agreement_deltas if value < 0),
            "a2_slower_wall_clock_count": sum(1 for value in wall_clock_agreement_deltas if value > 0),
            "a2_same_wall_clock_count": sum(1 for value in wall_clock_agreement_deltas if value == 0),
            "a2_faster_count": sum(1 for value in round_deltas if value < 0),
            "a2_slower_count": sum(1 for value in round_deltas if value > 0),
            "a2_same_round_count": sum(1 for value in round_deltas if value == 0),
            "a2_faster_offer_count": sum(1 for value in offer_deltas if value < 0),
            "a2_slower_offer_count": sum(1 for value in offer_deltas if value > 0),
            "a2_same_offer_count": sum(1 for value in offer_deltas if value == 0),
            "a2_faster_step_count": sum(1 for value in step_deltas if value < 0),
            "a2_slower_step_count": sum(1 for value in step_deltas if value > 0),
            "a2_same_step_count": sum(1 for value in step_deltas if value == 0),
            "mean_wall_clock_ms_delta_a2_minus_a1": mean(wall_clock_deltas) if wall_clock_deltas else None,
            "median_wall_clock_ms_delta_a2_minus_a1": median(wall_clock_deltas) if wall_clock_deltas else None,
            "mean_wall_clock_ms_to_agreement_delta_a2_minus_a1": (
                mean(wall_clock_agreement_deltas) if wall_clock_agreement_deltas else None
            ),
            "median_wall_clock_ms_to_agreement_delta_a2_minus_a1": (
                median(wall_clock_agreement_deltas) if wall_clock_agreement_deltas else None
            ),
            "mean_step_delta_a2_minus_a1": mean(step_deltas) if step_deltas else None,
            "median_step_delta_a2_minus_a1": median(step_deltas) if step_deltas else None,
            "mean_offer_count_delta_a2_minus_a1": mean(offer_deltas) if offer_deltas else None,
            "median_offer_count_delta_a2_minus_a1": median(offer_deltas) if offer_deltas else None,
            "mean_round_delta_a2_minus_a1": mean(round_deltas) if round_deltas else None,
            "median_round_delta_a2_minus_a1": median(round_deltas) if round_deltas else None,
            "mean_atomic_actions_delta_a2_minus_a1": (
                mean(atomic_action_deltas) if atomic_action_deltas else None
            ),
            "median_atomic_actions_delta_a2_minus_a1": (
                median(atomic_action_deltas) if atomic_action_deltas else None
            ),
            "mean_candidate_evaluation_count_delta_a2_minus_a1": (
                mean(candidate_deltas) if candidate_deltas else None
            ),
            "median_candidate_evaluation_count_delta_a2_minus_a1": (
                median(candidate_deltas) if candidate_deltas else None
            ),
            "mean_hint_fit_evaluation_count_delta_a2_minus_a1": (
                mean(hint_fit_deltas) if hint_fit_deltas else None
            ),
            "median_hint_fit_evaluation_count_delta_a2_minus_a1": (
                median(hint_fit_deltas) if hint_fit_deltas else None
            ),
            "mean_hint_attached_offer_count_delta_a2_minus_a1": (
                mean(hint_attached_deltas) if hint_attached_deltas else None
            ),
            "median_hint_attached_offer_count_delta_a2_minus_a1": (
                median(hint_attached_deltas) if hint_attached_deltas else None
            ),
            "mean_joint_utility_delta_a2_minus_a1": mean(utility_deltas) if utility_deltas else None,
            "median_joint_utility_delta_a2_minus_a1": median(utility_deltas) if utility_deltas else None,
            "mean_min_utility_delta_a2_minus_a1": mean(min_utility_deltas) if min_utility_deltas else None,
            "median_min_utility_delta_a2_minus_a1": median(min_utility_deltas) if min_utility_deltas else None,
            "mean_utility_spread_delta_a2_minus_a1": mean(spread_deltas) if spread_deltas else None,
            "median_utility_spread_delta_a2_minus_a1": median(spread_deltas) if spread_deltas else None,
        },
        "breakdown_by": {
            "task_family": _breakdown(comparisons, "task_family"),
            "complexity_level": _breakdown(comparisons, "complexity_level"),
            "tension_pattern": _breakdown(comparisons, "tension_pattern"),
            **{
                axis: _breakdown(comparisons, axis)
                for axis in META_BREAKDOWN_AXES
                if any(axis in item for item in comparisons)
            },
        },
    }


def _breakdown(comparisons: list[dict[str, Any]], axis: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in comparisons:
        if axis not in item:
            continue
        grouped.setdefault(str(item[axis]), []).append(item)

    summary: dict[str, dict[str, Any]] = {}
    for value, items in sorted(grouped.items()):
        wall_clock_deltas = _deltas(items, "wall_clock_ms_delta_a2_minus_a1")
        wall_clock_agreement_deltas = _deltas(items, "wall_clock_ms_to_agreement_delta_a2_minus_a1")
        round_deltas = [
            item["round_delta_a2_minus_a1"]
            for item in items
            if item["round_delta_a2_minus_a1"] is not None
        ]
        offer_deltas = _deltas(items, "offer_count_delta_a2_minus_a1")
        step_deltas = [
            item["step_delta_a2_minus_a1"]
            for item in items
            if item["step_delta_a2_minus_a1"] is not None
        ]
        atomic_action_deltas = _deltas(items, "atomic_actions_delta_a2_minus_a1")
        candidate_deltas = _deltas(items, "candidate_evaluation_count_delta_a2_minus_a1")
        hint_fit_deltas = _deltas(items, "hint_fit_evaluation_count_delta_a2_minus_a1")
        hint_attached_deltas = _deltas(items, "hint_attached_offer_count_delta_a2_minus_a1")
        utility_deltas = [
            item["joint_utility_delta_a2_minus_a1"]
            for item in items
            if item["joint_utility_delta_a2_minus_a1"] is not None
        ]
        min_utility_deltas = [
            item["min_utility_delta_a2_minus_a1"]
            for item in items
            if item["min_utility_delta_a2_minus_a1"] is not None
        ]
        spread_deltas = [
            item["utility_spread_delta_a2_minus_a1"]
            for item in items
            if item["utility_spread_delta_a2_minus_a1"] is not None
        ]
        summary[value] = {
            "scenario_count": len({item["scenario_id"] for item in items}),
            "comparison_count": len(items),
            "a2_faster_wall_clock_count": sum(1 for delta in wall_clock_agreement_deltas if delta < 0),
            "a2_slower_wall_clock_count": sum(1 for delta in wall_clock_agreement_deltas if delta > 0),
            "a2_same_wall_clock_count": sum(1 for delta in wall_clock_agreement_deltas if delta == 0),
            "a2_faster_count": sum(1 for delta in round_deltas if delta < 0),
            "a2_slower_count": sum(1 for delta in round_deltas if delta > 0),
            "a2_same_round_count": sum(1 for delta in round_deltas if delta == 0),
            "a2_faster_offer_count": sum(1 for delta in offer_deltas if delta < 0),
            "a2_slower_offer_count": sum(1 for delta in offer_deltas if delta > 0),
            "a2_same_offer_count": sum(1 for delta in offer_deltas if delta == 0),
            "a2_faster_step_count": sum(1 for delta in step_deltas if delta < 0),
            "a2_slower_step_count": sum(1 for delta in step_deltas if delta > 0),
            "a2_same_step_count": sum(1 for delta in step_deltas if delta == 0),
            "mean_wall_clock_ms_delta_a2_minus_a1": mean(wall_clock_deltas) if wall_clock_deltas else None,
            "median_wall_clock_ms_delta_a2_minus_a1": median(wall_clock_deltas) if wall_clock_deltas else None,
            "mean_wall_clock_ms_to_agreement_delta_a2_minus_a1": (
                mean(wall_clock_agreement_deltas) if wall_clock_agreement_deltas else None
            ),
            "median_wall_clock_ms_to_agreement_delta_a2_minus_a1": (
                median(wall_clock_agreement_deltas) if wall_clock_agreement_deltas else None
            ),
            "mean_step_delta_a2_minus_a1": mean(step_deltas) if step_deltas else None,
            "median_step_delta_a2_minus_a1": median(step_deltas) if step_deltas else None,
            "mean_offer_count_delta_a2_minus_a1": mean(offer_deltas) if offer_deltas else None,
            "median_offer_count_delta_a2_minus_a1": median(offer_deltas) if offer_deltas else None,
            "mean_round_delta_a2_minus_a1": mean(round_deltas) if round_deltas else None,
            "median_round_delta_a2_minus_a1": median(round_deltas) if round_deltas else None,
            "mean_atomic_actions_delta_a2_minus_a1": (
                mean(atomic_action_deltas) if atomic_action_deltas else None
            ),
            "median_atomic_actions_delta_a2_minus_a1": (
                median(atomic_action_deltas) if atomic_action_deltas else None
            ),
            "mean_candidate_evaluation_count_delta_a2_minus_a1": (
                mean(candidate_deltas) if candidate_deltas else None
            ),
            "median_candidate_evaluation_count_delta_a2_minus_a1": (
                median(candidate_deltas) if candidate_deltas else None
            ),
            "mean_hint_fit_evaluation_count_delta_a2_minus_a1": (
                mean(hint_fit_deltas) if hint_fit_deltas else None
            ),
            "median_hint_fit_evaluation_count_delta_a2_minus_a1": (
                median(hint_fit_deltas) if hint_fit_deltas else None
            ),
            "mean_hint_attached_offer_count_delta_a2_minus_a1": (
                mean(hint_attached_deltas) if hint_attached_deltas else None
            ),
            "median_hint_attached_offer_count_delta_a2_minus_a1": (
                median(hint_attached_deltas) if hint_attached_deltas else None
            ),
            "mean_joint_utility_delta_a2_minus_a1": mean(utility_deltas) if utility_deltas else None,
            "mean_min_utility_delta_a2_minus_a1": mean(min_utility_deltas) if min_utility_deltas else None,
            "mean_utility_spread_delta_a2_minus_a1": mean(spread_deltas) if spread_deltas else None,
            "mean_a2_constraint_hint_message_count": mean(
                item["a2_constraint_hint_message_count"] for item in items
            ),
            "mean_a2_constraint_hint_sensitivity_score": mean(
                item["a2_constraint_hint_sensitivity_score"] for item in items
            ),
        }
    return summary


def _record_to_result(record: dict[str, Any]) -> RunResult:
    offer_count = record.get("offer_count_to_agreement", record.get("rounds_to_agreement"))
    hint_attached_count = record.get(
        "hint_attached_offer_count",
        record.get("constraint_hint_message_count", 0),
    )
    return RunResult(
        run_id=record["run_id"],
        experiment_group=ExperimentGroup(record["experiment_group"]),
        scenario_id=record["scenario_id"],
        repeat_id=record.get("repeat_id", "r01"),
        agreement_success=record["agreement_success"],
        agreement_outcome=record["agreement_outcome"],
        wall_clock_ms=float(record.get("wall_clock_ms") or 0.0),
        wall_clock_ms_to_agreement=record.get("wall_clock_ms_to_agreement"),
        steps_to_agreement=record.get("steps_to_agreement"),
        offer_count_to_agreement=offer_count,
        rounds_to_agreement=record["rounds_to_agreement"],
        atomic_actions_to_agreement=record["atomic_actions_to_agreement"],
        candidate_evaluation_count=int(record.get("candidate_evaluation_count") or 0),
        hint_fit_evaluation_count=int(record.get("hint_fit_evaluation_count") or 0),
        utility_a=record["utility_a"],
        utility_b=record["utility_b"],
        joint_utility=record["joint_utility"],
        utilities=record.get("utilities") or {},
        min_utility=record.get("min_utility"),
        utility_spread=record.get("utility_spread"),
        pareto_dominated=record["pareto_dominated"],
        pareto_joint_gap=record["pareto_joint_gap"],
        constraint_hint_message_count=record["constraint_hint_message_count"],
        hint_attached_offer_count=hint_attached_count,
        constraint_hint_sensitivity_score=record["constraint_hint_sensitivity_score"],
        failure_reasons=tuple(record["failure_reasons"]),
        events=(),
    )


def _jsonl(records: Iterable[dict[str, Any]]) -> str:
    return "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)


def _delta(left: float | int | None, right: float | int | None) -> float | int | None:
    if left is None or right is None:
        return None
    return left - right


def _deltas(items: list[dict[str, Any]], key: str) -> list[float | int]:
    return [item[key] for item in items if item.get(key) is not None]


def _with_generation_meta(record: dict[str, Any], scenario: Scenario) -> dict[str, Any]:
    record.update(scenario.generation_meta.extra)
    return record
