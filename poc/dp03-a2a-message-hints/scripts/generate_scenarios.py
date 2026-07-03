from __future__ import annotations

import argparse
import json
from pathlib import Path

from dp03_a2a_hints.scenario_generator import generate_scenarios, write_scenarios


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate DP03 synthetic scenario matrix.")
    parser.add_argument("--count", type=int, choices=(120, 180), default=120)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "scenarios/generated",
    )
    parser.add_argument("--no-clean", action="store_true", help="Do not delete existing YAML files first.")
    args = parser.parse_args()

    variant_count = 2 if args.count == 120 else 3
    scenarios = generate_scenarios(variant_count=variant_count)
    write_scenarios(scenarios, args.output_dir, clean=not args.no_clean)
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "scenario_count": len(scenarios),
                "first_scenario_id": scenarios[0]["scenario_id"],
                "last_scenario_id": scenarios[-1]["scenario_id"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
