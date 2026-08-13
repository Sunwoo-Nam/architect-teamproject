#!/usr/bin/env python3
"""TB baseline 프로브 — 정식 구현은 `total.adapters.composite.baseline` (2026-08-13 승격).

사용: .venv/bin/python scripts/tb_baseline_probe.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from total.adapters.composite.baseline import baseline_t  # noqa: E402


def main() -> int:
    sdir = ROOT / "datasets" / "composite" / "scenarios"
    paths = sorted(sdir.glob("*.yaml")) + sorted(sdir.glob("*.yml")) + sorted(sdir.glob("*.json"))
    rows = []
    for p in paths:
        try:
            rows.append(baseline_t(p))
        except RuntimeError as e:
            print(f"!! {p.stem}: {e}")
    rows.sort(key=lambda r: r["S"])
    print(f"{'시나리오':28s} {'축':>3s} {'조합 S':>14s} {'합의':>5s} {'k*':>5s} {'팝':>7s} {'T(s)':>10s}")
    for r in rows:
        print(f"{r['scenario']:28s} {r['axes']:>3d} {r['S']:>14,d} "
              f"{('≥' if r['capped'] else '') + str(r['agreed']):>5s} "
              f"{r['proposals_k*']:>5d} {r['lazy_pops']:>7d} {r['T_ms']/1000:>10.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
