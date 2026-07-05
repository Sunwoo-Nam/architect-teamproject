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
        wall_clock_all = [item.wall_clock_ms for item in items]
        wall_clock_to_agreement = [
            item.wall_clock_ms_to_agreement
            for item in successful
            if item.wall_clock_ms_to_agreement is not None
        ]
        steps = [item.steps_to_agreement for item in successful if item.steps_to_agreement is not None]
        offers = [
            item.offer_count_to_agreement
            for item in successful
            if item.offer_count_to_agreement is not None
        ]
        rounds = [item.rounds_to_agreement for item in successful if item.rounds_to_agreement is not None]
        actions = [item.atomic_actions_to_agreement for item in successful]
        candidates = [item.candidate_evaluation_count for item in successful]
        hint_fits = [item.hint_fit_evaluation_count for item in successful]
        joint = [item.joint_utility for item in successful if item.joint_utility is not None]
        minimums = [item.min_utility for item in successful if item.min_utility is not None]
        spreads = [item.utility_spread for item in successful if item.utility_spread is not None]
        summary[group] = {
            "run_count": len(items),
            "agreement_rate": len(successful) / len(items) if items else None,
            "mean_wall_clock_ms": mean(wall_clock_all) if wall_clock_all else None,
            "median_wall_clock_ms_to_agreement": (
                median(wall_clock_to_agreement) if wall_clock_to_agreement else None
            ),
            "median_steps": median(steps) if steps else None,
            "median_offer_count": median(offers) if offers else None,
            "median_rounds": median(rounds) if rounds else None,
            "median_atomic_actions": median(actions) if actions else None,
            "median_candidate_evaluation_count": median(candidates) if candidates else None,
            "median_hint_fit_evaluation_count": median(hint_fits) if hint_fits else None,
            "mean_joint_utility": mean(joint) if joint else None,
            "mean_min_utility": mean(minimums) if minimums else None,
            "mean_utility_spread": mean(spreads) if spreads else None,
            "constraint_hint_message_count": sum(item.constraint_hint_message_count for item in items),
            "hint_attached_offer_count": sum(item.hint_attached_offer_count for item in items),
            "mean_constraint_hint_sensitivity_score": (
                mean(item.constraint_hint_sensitivity_score for item in items) if items else None
            ),
            "failure_count": sum(1 for item in items if item.failure_reasons),
        }
    return summary
