"""P4 — REC(복구 시간 비율) 측정 (29-1 A5-2).

각 TC × 시드에서 정상 협상의 라운드 구조(seq는 축별 커밋 경계)를 얻어, 균일 크래시 시
기대 재실행 라운드 ÷ 정상 라운드 1회 = 복구 비율을 구한다. 별점은 각 전략 자신의
정상 총 라운드 R을 재시작 기준선으로 삼는다.

FT는 본 PoC에서 별도 판정하지 않는다 — 일시 오류 흡수는 재시도/타임아웃 계층의 문제이고
그 계층은 1안·2안 어느 쪽에도 동일하게 얹히므로 두 안을 구별하지 못한다(핸드북 A5-1은
transport 계층 소관). 구조가 갈리는 것은 크래시 복구(REC)뿐이라 REC에 집중한다.

사용:  .venv/bin/python scripts/run_rec.py [--seeds 20]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpca.common.scenario import load_scenario  # noqa: E402
from dpca.harness.recovery import analyze_recovery  # noqa: E402
from dpca.harness.runner import STRATEGIES, run_one  # noqa: E402


def main() -> int:
    n_seeds = int(sys.argv[sys.argv.index("--seeds") + 1]) if "--seeds" in sys.argv else 20
    paths = sorted((ROOT / "scenarios").glob("S*.yaml"))
    rows: list[dict] = []

    for path in paths:
        n_axes = 4 if "S11" in path.name else None
        base = load_scenario(path, n_axes=n_axes)
        base_seed = base.profile_seed
        for s in range(n_seeds):
            scenario = load_scenario(path, n_axes=n_axes)
            scenario.participants["profile_seed"] = base_seed + s
            for strategy in STRATEGIES:
                r = run_one(scenario, strategy)
                if r.agreement is None:      # 결렬 세션은 복구 대상 아님 (재개할 합의가 없음)
                    continue
                rec = analyze_recovery(strategy, r.rounds, r.extra.get("axis_rounds"))
                rows.append({
                    "tc": scenario.id, "seed": base_seed + s, "strategy": strategy,
                    "total_rounds": rec.total_rounds, "segments": rec.commit_segments,
                    "expected_recovery": rec.expected_recovery, "max_recovery": rec.max_recovery,
                    "ratio": rec.ratio, "stars": rec.stars,
                })

    out = ROOT / "results" / "rec.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # 집계
    print(f"{'전략':<6}{'복구비율 중앙':>12}{'별점중앙':>9}{'재시작R 중앙':>12}{'복구/재시작':>12}")
    for st in STRATEGIES:
        rs = [r for r in rows if r["strategy"] == st]
        if not rs:
            continue
        ratios = sorted(r["ratio"] for r in rs)
        stars = sorted(r["stars"] for r in rs)
        Rs = sorted(r["total_rounds"] for r in rs)
        mr, mR = median(ratios), median(Rs)
        print(f"{st:<6}{mr:>12.2f}{median(stars):>9}{mR:>12.0f}{mr / mR if mR else 0:>12.1%}")

    print(f"\n{len(rows)} rows → {out}")
    print("\n=== TC별 복구 비율 중앙값 (낮을수록 복구 저렴) ===")
    print(f"{'TC':<5}{'seq':>8}{'pool':>8}{'full':>8}  seq 이점")
    tcs = sorted({r["tc"] for r in rows})
    for tc in tcs:
        cells = {}
        for st in STRATEGIES:
            vals = [r["ratio"] for r in rows if r["tc"] == tc and r["strategy"] == st]
            cells[st] = median(sorted(vals)) if vals else None
        row = f"{tc:<5}"
        for st in ("seq", "pool", "full"):
            row += f"{cells[st]:>8.1f}" if cells.get(st) is not None else f"{'—':>8}"
        if cells.get("seq") and cells.get("pool"):
            row += f"  {cells['pool'] / cells['seq']:.1f}배 저렴" if cells["seq"] < cells["pool"] else "  없음"
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
