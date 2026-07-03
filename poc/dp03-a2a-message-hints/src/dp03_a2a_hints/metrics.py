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
        steps = [item.steps_to_agreement for item in successful if item.steps_to_agreement is not None]
        rounds = [item.rounds_to_agreement for item in successful if item.rounds_to_agreement is not None]
        joint = [item.joint_utility for item in successful if item.joint_utility is not None]
        minimums = [item.min_utility for item in successful if item.min_utility is not None]
        spreads = [item.utility_spread for item in successful if item.utility_spread is not None]
        summary[group] = {
            "run_count": len(items),
            "agreement_rate": len(successful) / len(items) if items else None,
            "median_steps": median(steps) if steps else None,
            "median_rounds": median(rounds) if rounds else None,
            "mean_joint_utility": mean(joint) if joint else None,
            "mean_min_utility": mean(minimums) if minimums else None,
            "mean_utility_spread": mean(spreads) if spreads else None,
            "constraint_hint_message_count": sum(item.constraint_hint_message_count for item in items),
            "mean_constraint_hint_sensitivity_score": (
                mean(item.constraint_hint_sensitivity_score for item in items) if items else None
            ),
            "failure_count": sum(1 for item in items if item.failure_reasons),
        }
    return summary
