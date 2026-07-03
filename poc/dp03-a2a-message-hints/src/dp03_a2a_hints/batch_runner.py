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


def run_scenario_matrix(
    scenario_dir: Path,
    groups: tuple[ExperimentGroup, ...] = TRACK_A_GROUPS,
    n_steps: int = 30,
    concession_steps: int | None = None,
    constraint_hint_weight: float = 0.15,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    scenarios: dict[str, Scenario] = {}
    for path in sorted(scenario_dir.glob("*.yaml")):
        scenario = load_scenario(path)
        scenarios[scenario.scenario_id] = scenario
        for group in groups:
            result = run_scenario(
                scenario,
                RunConfig(
                    experiment_group=group,
                    n_steps=n_steps,
                    concession_steps=concession_steps,
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
        "scenario_count": len(comparisons),
    }


def result_record(result: RunResult, scenario: Scenario, path: Path) -> dict[str, Any]:
    return {
        "run_id": result.run_id,
        "scenario_file": path.name,
        "scenario_id": result.scenario_id,
        "task_family": scenario.task_family,
        "complexity_level": scenario.complexity_level,
        "tension_pattern": scenario.tension_pattern,
        "variant_id": scenario.variant_id,
        "experiment_group": result.experiment_group.value,
        "agreement_success": result.agreement_success,
        "rounds_to_agreement": result.rounds_to_agreement,
        "atomic_actions_to_agreement": result.atomic_actions_to_agreement,
        "agreement_outcome": result.agreement_outcome,
        "utility_a": result.utility_a,
        "utility_b": result.utility_b,
        "joint_utility": result.joint_utility,
        "pareto_dominated": result.pareto_dominated,
        "pareto_joint_gap": result.pareto_joint_gap,
        "constraint_hint_message_count": result.constraint_hint_message_count,
        "constraint_hint_sensitivity_score": result.constraint_hint_sensitivity_score,
        "failure_reasons": list(result.failure_reasons),
    }


def scenario_comparisons(
    records: list[dict[str, Any]],
    scenarios: dict[str, Scenario],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record["scenario_id"], {})[record["experiment_group"]] = record

    comparisons = []
    for scenario_id, group_records in sorted(grouped.items()):
        a1 = group_records.get(ExperimentGroup.A1_DET_OFFER_ONLY.value)
        a2 = group_records.get(ExperimentGroup.A2_DET_HINT_AWARE.value)
        if a1 is None or a2 is None:
            continue
        scenario = scenarios[scenario_id]
        comparisons.append(
            {
                "scenario_id": scenario_id,
                "task_family": scenario.task_family,
                "complexity_level": scenario.complexity_level,
                "tension_pattern": scenario.tension_pattern,
                "variant_id": scenario.variant_id,
                "a1_success": a1["agreement_success"],
                "a2_success": a2["agreement_success"],
                "round_delta_a2_minus_a1": _delta(a2["rounds_to_agreement"], a1["rounds_to_agreement"]),
                "joint_utility_delta_a2_minus_a1": _delta(a2["joint_utility"], a1["joint_utility"]),
                "pareto_joint_gap_delta_a2_minus_a1": _delta(
                    a2["pareto_joint_gap"],
                    a1["pareto_joint_gap"],
                ),
                "a2_constraint_hint_message_count": a2["constraint_hint_message_count"],
                "a2_constraint_hint_sensitivity_score": a2["constraint_hint_sensitivity_score"],
                "a1_failure_reasons": a1["failure_reasons"],
                "a2_failure_reasons": a2["failure_reasons"],
            }
        )
    return comparisons


def batch_summary(records: list[dict[str, Any]], comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    synthetic_results = [_record_to_result(record) for record in records]
    round_deltas = [
        item["round_delta_a2_minus_a1"]
        for item in comparisons
        if item["round_delta_a2_minus_a1"] is not None
    ]
    utility_deltas = [
        item["joint_utility_delta_a2_minus_a1"]
        for item in comparisons
        if item["joint_utility_delta_a2_minus_a1"] is not None
    ]
    return {
        "group_summary": summarize(synthetic_results),
        "comparison_summary": {
            "scenario_count": len(comparisons),
            "a2_faster_count": sum(1 for value in round_deltas if value < 0),
            "a2_slower_count": sum(1 for value in round_deltas if value > 0),
            "a2_same_round_count": sum(1 for value in round_deltas if value == 0),
            "mean_round_delta_a2_minus_a1": mean(round_deltas) if round_deltas else None,
            "median_round_delta_a2_minus_a1": median(round_deltas) if round_deltas else None,
            "mean_joint_utility_delta_a2_minus_a1": mean(utility_deltas) if utility_deltas else None,
            "median_joint_utility_delta_a2_minus_a1": median(utility_deltas) if utility_deltas else None,
        },
        "breakdown_by": {
            "task_family": _breakdown(comparisons, "task_family"),
            "complexity_level": _breakdown(comparisons, "complexity_level"),
            "tension_pattern": _breakdown(comparisons, "tension_pattern"),
        },
    }


def _breakdown(comparisons: list[dict[str, Any]], axis: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in comparisons:
        grouped.setdefault(str(item[axis]), []).append(item)

    summary: dict[str, dict[str, Any]] = {}
    for value, items in sorted(grouped.items()):
        round_deltas = [
            item["round_delta_a2_minus_a1"]
            for item in items
            if item["round_delta_a2_minus_a1"] is not None
        ]
        utility_deltas = [
            item["joint_utility_delta_a2_minus_a1"]
            for item in items
            if item["joint_utility_delta_a2_minus_a1"] is not None
        ]
        summary[value] = {
            "scenario_count": len(items),
            "a2_faster_count": sum(1 for delta in round_deltas if delta < 0),
            "a2_slower_count": sum(1 for delta in round_deltas if delta > 0),
            "a2_same_round_count": sum(1 for delta in round_deltas if delta == 0),
            "mean_round_delta_a2_minus_a1": mean(round_deltas) if round_deltas else None,
            "median_round_delta_a2_minus_a1": median(round_deltas) if round_deltas else None,
            "mean_joint_utility_delta_a2_minus_a1": mean(utility_deltas) if utility_deltas else None,
            "mean_a2_constraint_hint_message_count": mean(
                item["a2_constraint_hint_message_count"] for item in items
            ),
            "mean_a2_constraint_hint_sensitivity_score": mean(
                item["a2_constraint_hint_sensitivity_score"] for item in items
            ),
        }
    return summary


def _record_to_result(record: dict[str, Any]) -> RunResult:
    return RunResult(
        run_id=record["run_id"],
        experiment_group=ExperimentGroup(record["experiment_group"]),
        scenario_id=record["scenario_id"],
        repeat_id="r01",
        agreement_success=record["agreement_success"],
        agreement_outcome=record["agreement_outcome"],
        rounds_to_agreement=record["rounds_to_agreement"],
        atomic_actions_to_agreement=record["atomic_actions_to_agreement"],
        utility_a=record["utility_a"],
        utility_b=record["utility_b"],
        joint_utility=record["joint_utility"],
        pareto_dominated=record["pareto_dominated"],
        pareto_joint_gap=record["pareto_joint_gap"],
        constraint_hint_message_count=record["constraint_hint_message_count"],
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
