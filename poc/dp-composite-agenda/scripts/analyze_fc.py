"""P2 분석 — FC 결정 실험 집계 + 짝비교(1안 seq vs 2안 pool).

29-1 A1: 별점은 s의 평균으로 정하고 95% CI 병기. 여기에 더해 본 DP의 결정 질문
"1안의 Pareto 손실이 정합을 얼마나 깎는가"를 **같은 (TC,시드) 짝**의 달성률 차이로
답한다 — 공통 노이즈(시나리오·프로파일)가 상쇄되어 구조 차이만 남는다.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def mean_ci(xs: list[float]) -> tuple[float, float, float]:
    n = len(xs)
    if n == 0:
        return (0.0, 0.0, 0.0)
    m = sum(xs) / n
    if n < 2:
        return (m, m, m)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    half = 1.96 * sd / math.sqrt(n)
    return (m, m - half, m + half)


def stars_from_s(s: float) -> int:
    for bound, star in ((0.8, 5), (0.6, 4), (0.4, 3), (0.2, 2), (0.0, 1)):
        if s > bound:
            return star
    return 0


def main() -> int:
    fname = sys.argv[1] if len(sys.argv) > 1 else "fc_benchmark.jsonl"
    rows = load(ROOT / "results" / fname)
    print(f"[원자료: {fname}]")
    strategies = ("full", "seq", "pool")

    # --- 전략별 전체 집계 ---
    print("=== 전략별 FC 집계 (전 TC × 전 시드) ===")
    print(f"{'전략':<6}{'달성률(95%CI)':<26}{'s평균':>8}{'별점':>5}{'FR위반':>8}{'phase중앙':>10}{'peak중앙KiB':>12}")
    by_strategy = defaultdict(list)
    for row in rows:
        by_strategy[row["strategy"]].append(row)
    for st in strategies:
        rs = by_strategy[st]
        ach = [r["achieved"] for r in rs]
        s_vals = [r["s"] for r in rs]
        m, lo, hi = mean_ci(ach)
        sm, _, _ = mean_ci(s_vals)
        fr = sum(1 for r in rs if r["fr_violations"])
        phases = sorted(r["phases"] for r in rs)
        peaks = sorted(r["peak_kib"] for r in rs)
        med = lambda xs: xs[len(xs) // 2]
        print(f"{st:<6}{f'{m:.3f} [{lo:.3f}, {hi:.3f}]':<26}{sm:>8.3f}"
              f"{stars_from_s(sm):>5}{fr:>8}{med(phases):>10}{med(peaks):>12.0f}")

    # --- 짝비교: pool - seq, pool - full, seq - full (같은 TC·시드) ---
    print("\n=== 짝비교 (같은 TC·시드 달성률 차이, 95% CI) ===")
    keyed = defaultdict(dict)
    for row in rows:
        keyed[(row["tc"], row["seed"])][row["strategy"]] = row
    pairs = {("pool", "seq"): [], ("pool", "full"): [], ("seq", "full"): []}
    for cell in keyed.values():
        if all(st in cell for st in strategies):
            for (a, b) in pairs:
                pairs[(a, b)].append(cell[a]["achieved"] - cell[b]["achieved"])
    for (a, b), diffs in pairs.items():
        m, lo, hi = mean_ci(diffs)
        wins = sum(1 for d in diffs if d > 1e-9)
        losses = sum(1 for d in diffs if d < -1e-9)
        verdict = "우세" if lo > 0 else ("열세" if hi < 0 else "차이 불확실")
        print(f"{a} − {b}: {m:+.4f} [{lo:+.4f}, {hi:+.4f}]  "
              f"({a} 승 {wins} / 패 {losses} / 무 {len(diffs) - wins - losses})  → {a} {verdict}")

    # --- TC별 pool vs seq (구조 차이가 큰 TC 식별) ---
    print("\n=== TC별 pool − seq (달성률) ===")
    print(f"{'TC':<5}{'pool평균':>9}{'seq평균':>9}{'차이':>9}{'주목'}")
    by_tc = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_tc[row["tc"]][row["strategy"]].append(row["achieved"])
    for tc in sorted(by_tc):
        p = sum(by_tc[tc]["pool"]) / len(by_tc[tc]["pool"])
        s = sum(by_tc[tc]["seq"]) / len(by_tc[tc]["seq"])
        note = ""
        if p - s > 0.05:
            note = "← pool 우세 (seq 구조 손실)"
        elif s - p > 0.05:
            note = "← seq 우세"
        print(f"{tc:<5}{p:>9.3f}{s:>9.3f}{p - s:>+9.3f}  {note}")

    # --- FR 위반 요약 ---
    fr_rows = [r for r in rows if r["fr_violations"]]
    if fr_rows:
        print(f"\n=== FR 위반(바닥선 밑 수락 등) {len(fr_rows)}건 — 부분정보 손실(L1) 진단 ===")
        by = defaultdict(int)
        for r in fr_rows:
            by[(r["tc"], r["strategy"])] += 1
        for (tc, st), c in sorted(by.items()):
            print(f"  {tc}/{st}: {c}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
