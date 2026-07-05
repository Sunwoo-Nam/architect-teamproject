from __future__ import annotations

import json
from pathlib import Path

from dp03_a2a_hints import ExperimentGroup, RunConfig, run_scenario
from dp03_a2a_hints.metrics import summarize
from dp03_a2a_hints.scenario_loader import load_scenario


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    normal = load_scenario(root / "scenarios/samples/S001-normal.yaml")
    fallback = load_scenario(root / "scenarios/samples/S099-fallback.yaml")

    results = [
        run_scenario(normal, RunConfig(ExperimentGroup.A1_DET_OFFER_ONLY)),
        run_scenario(normal, RunConfig(ExperimentGroup.A2_DET_HINT_AWARE)),
        run_scenario(fallback, RunConfig(ExperimentGroup.A3_DET_FALLBACK)),
    ]

    for result in results:
        print(
            json.dumps(
                {
                    "run_id": result.run_id,
                    "agreement_success": result.agreement_success,
                    "rounds_to_agreement": result.rounds_to_agreement,
                    "agreement_outcome": result.agreement_outcome,
                    "joint_utility": result.joint_utility,
                    "constraint_hint_message_count": result.constraint_hint_message_count,
                    "constraint_hint_sensitivity_score": result.constraint_hint_sensitivity_score,
                    "failure_reasons": result.failure_reasons,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )

    print(json.dumps(summarize(results), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
