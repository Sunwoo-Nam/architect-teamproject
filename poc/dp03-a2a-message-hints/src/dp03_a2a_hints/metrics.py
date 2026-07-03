from __future__ import annotations

from collections import defaultdict
from statistics import mean, median
from typing import Iterable

from .models import RunResult


def summarize(results: Iterable[RunResult]) -> dict[str, dict[str, float | int | None]]:
    grouped: dict[str, list[RunResult]] = defaultdict(list)
    for result in results:
        grouped[result.experiment_group.value].append(result)

    summary: dict[str, dict[str, float | int | None]] = {}
    for group, items in grouped.items():
        successful = [item for item in items if item.agreement_success]
        rounds = [item.rounds_to_agreement for item in successful if item.rounds_to_agreement is not None]
        joint = [item.joint_utility for item in successful if item.joint_utility is not None]
        summary[group] = {
            "run_count": len(items),
            "agreement_rate": len(successful) / len(items) if items else None,
            "median_rounds": median(rounds) if rounds else None,
            "mean_joint_utility": mean(joint) if joint else None,
            "constraint_hint_message_count": sum(item.constraint_hint_message_count for item in items),
            "mean_constraint_hint_sensitivity_score": (
                mean(item.constraint_hint_sensitivity_score for item in items) if items else None
            ),
            "failure_count": sum(1 for item in items if item.failure_reasons),
        }
    return summary
