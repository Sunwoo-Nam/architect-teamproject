from __future__ import annotations

import argparse
import json
from pathlib import Path

from dp03_a2a_hints.batch_runner import run_scenario_matrix, write_batch_outputs


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run Track A over generated DP03 scenarios.")
    parser.add_argument(
        "--scenario-dir",
        type=Path,
        default=root / "scenarios/generated",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "results/track_a_generated",
    )
    parser.add_argument("--n-steps", type=int, default=30)
    parser.add_argument(
        "--concession-steps",
        type=int,
        default=None,
        help="Step count used for concession threshold. Defaults to --n-steps.",
    )
    parser.add_argument("--constraint-hint-weight", type=float, default=0.15)
    args = parser.parse_args()

    records, comparisons = run_scenario_matrix(
        scenario_dir=args.scenario_dir,
        n_steps=args.n_steps,
        concession_steps=args.concession_steps,
        constraint_hint_weight=args.constraint_hint_weight,
    )
    output = write_batch_outputs(records, comparisons, args.output_dir)
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
