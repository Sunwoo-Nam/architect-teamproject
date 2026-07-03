from __future__ import annotations

import argparse
import json
from pathlib import Path

from dp03_a2a_hints.bias_audit import audit_scenario_bias, write_bias_audit


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Audit bias in generated DP03 scenarios.")
    parser.add_argument(
        "--scenario-dir",
        type=Path,
        default=root / "scenarios/generated",
    )
    parser.add_argument(
        "--comparison-jsonl",
        type=Path,
        default=root / "results/track_a_generated/scenario_comparison.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "results/track_a_generated/bias_audit.json",
    )
    args = parser.parse_args()

    audit = audit_scenario_bias(args.scenario_dir, args.comparison_jsonl)
    write_bias_audit(audit, args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "scenario_count": audit["scenario_count"],
                "warning_count": len(audit["bias_warnings"]),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
