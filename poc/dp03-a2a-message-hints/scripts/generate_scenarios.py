from __future__ import annotations

import argparse
import json
from pathlib import Path

from dp03_a2a_hints.scenario_generator import (
    generate_augmented_scenarios,
    generate_fixed_high_complexity_scenarios,
    generate_fixed_only_scenarios,
    generate_fixed_three_party_scenarios,
    generate_orthogonal_augmented_scenarios,
    generate_scenarios,
    write_scenarios,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate DP03 synthetic scenario matrix.")
    parser.add_argument("--count", type=int, choices=(120, 180, 360, 480, 600, 640), default=120)
    parser.add_argument(
        "--preset",
        choices=("fixed_three_party",),
        default=None,
        help="Generate a named scenario preset instead of the count-based matrix.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
    )
    parser.add_argument("--no-clean", action="store_true", help="Do not delete existing YAML files first.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    if args.preset == "fixed_three_party":
        output_name = "scenarios/generated_fixed_three_party_v1"
        scenarios = generate_fixed_three_party_scenarios()
    else:
        output_name = {
            120: "scenarios/generated",
            180: "scenarios/generated",
            360: "scenarios/generated_v3",
            480: "scenarios/generated_fixed_only_v1",
            600: "scenarios/generated_v4",
            640: "scenarios/generated_fixed_high_complexity_v1",
        }[args.count]
        if args.count == 640:
            scenarios = generate_fixed_high_complexity_scenarios()
        elif args.count == 600:
            scenarios = generate_orthogonal_augmented_scenarios()
        elif args.count == 480:
            scenarios = generate_fixed_only_scenarios()
        elif args.count == 360:
            scenarios = generate_augmented_scenarios()
        else:
            variant_count = 2 if args.count == 120 else 3
            scenarios = generate_scenarios(variant_count=variant_count)
    output_dir = args.output_dir or root / output_name
    write_scenarios(scenarios, output_dir, clean=not args.no_clean)
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
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
