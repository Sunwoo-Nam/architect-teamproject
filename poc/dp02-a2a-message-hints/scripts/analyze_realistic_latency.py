"""현실적 지연·성공률 후처리 분석 (재실행 없이 기존 run_results.jsonl 사용).

두 가지를 모델링한다.
1) 라운드당 비용 스윕 지연: total_time = rounds * per_round_cost (+ B는 힌트 계산 오버헤드).
   - per_round_cost = t_llm + t_net. 실측 hint 계산 오버헤드는 상수로 반영해 break-even도 계산.
2) 시간 제한(deadline) 하 성공률: success(D) = 합의 AND rounds <= D.

가정값은 모두 상단 상수로 노출한다(스윕). 결정론 Track A 데이터 기준.
"""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

# ── 가정 파라미터 (스윕) ────────────────────────────────────────────────
PER_ROUND_COSTS_S = [0.05, 0.1, 0.3, 0.5, 1.0, 2.0]   # t_llm + t_net (초/라운드)
HINT_COMPUTE_OVERHEAD_S = 0.003   # B의 협상당 힌트-fit 계산 오버헤드(초). repeat10 실측 median≈3ms
DEADLINES_ROUNDS = [10, 20, 30, 40, 50, 60, 80, 100]

GROUP_A = "A1_DET_OFFER_ONLY"      # 후보 A (순수 NegMAS)
GROUP_B = "A2_DET_HINT_AWARE"      # 후보 B (제약 힌트)

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
# 대표 결과셋 (있는 것만 처리)
DATASETS = {
    "2자(fixed n100)": "track_a_fixed_only_v1_n100",
    "3자": "track_a_fixed_three_party_v1_max100_concession30",
    "4자": "track_a_fixed_four_party_v1_max100_concession30",
    "고복잡도": "track_a_fixed_high_complexity_v1_max100_concession30",
    "생성 v4(현실적)": "track_a_generated_v4",
}


def load_runs(path: Path) -> dict[str, list[tuple[bool, int | None]]]:
    groups: dict[str, list[tuple[bool, int | None]]] = {GROUP_A: [], GROUP_B: []}
    with path.open() as fh:
        for line in fh:
            r = json.loads(line)
            g = r.get("experiment_group")
            if g in groups:
                rd = r.get("rounds_to_agreement")
                groups[g].append((bool(r["agreement_success"]), int(rd) if rd is not None else None))
    return groups


def modeled_time(rounds: int, cost: float, is_b: bool) -> float:
    return rounds * cost + (HINT_COMPUTE_OVERHEAD_S if is_b else 0.0)


def median_rounds(runs: list[tuple[bool, int | None]]) -> float:
    vals = [rd for ok, rd in runs if ok and rd is not None]
    return st.median(vals) if vals else float("nan")


def deadline_success(runs: list[tuple[bool, int | None]], d: int) -> float:
    n = len(runs)
    return sum(1 for ok, rd in runs if ok and rd is not None and rd <= d) / n if n else float("nan")


def break_even_cost(a: list[tuple[bool, int]], b: list[tuple[bool, int]]) -> float | None:
    """B가 A보다 빨라지는 최소 per_round_cost (초/라운드). 라운드 절감분으로 오버헤드를 상쇄."""
    da = median_rounds(a) - median_rounds(b)  # B가 줄인 라운드 수(>0이면 B 유리)
    if da <= 0:
        return None
    return HINT_COMPUTE_OVERHEAD_S / da


def analyze(name: str, groups: dict[str, list[tuple[bool, int]]]) -> list[str]:
    a, b = groups[GROUP_A], groups[GROUP_B]
    out: list[str] = []
    out.append(f"### {name}  (A n={len(a)}, B n={len(b)})\n")
    out.append(f"- 무제한 합의율: A {deadline_success(a, 10**9):.3f} / B {deadline_success(b, 10**9):.3f}")
    out.append(f"- median 라운드(합의): A {median_rounds(a):.1f} / B {median_rounds(b):.1f}")
    be = break_even_cost(a, b)
    out.append(f"- B가 빨라지는 break-even per_round_cost: "
               + (f"{be*1000:.2f} ms/round 이상" if be else "해당 없음(중앙 라운드 B≥A)") + "\n")

    # 지연 스윕
    out.append("| per_round_cost | A median time | B median time | B−A |")
    out.append("|---|---|---|---|")
    for c in PER_ROUND_COSTS_S:
        ta = st.median([modeled_time(rd, c, False) for ok, rd in a if ok and rd is not None])
        tb = st.median([modeled_time(rd, c, True) for ok, rd in b if ok and rd is not None])
        out.append(f"| {c:g}s | {ta:.2f}s | {tb:.2f}s | {tb-ta:+.2f}s |")
    out.append("")

    # deadline 성공률 스윕
    out.append("| deadline(rounds) | A success | B success | Δ(B−A) |")
    out.append("|---|---|---|---|")
    best = (None, -1.0)
    for d in DEADLINES_ROUNDS:
        sa, sb = deadline_success(a, d), deadline_success(b, d)
        if sb - sa > best[1]:
            best = (d, sb - sa)
        out.append(f"| {d} | {sa:.3f} | {sb:.3f} | {sb-sa:+.3f} |")
    out.append(f"\n- 성공률 격차 최대 지점: deadline≈{best[0]} 라운드에서 Δ={best[1]:+.3f}\n")
    return out


def main() -> None:
    lines: list[str] = [
        "# DP02 PoC — 현실적 지연·성공률 후처리 분석\n",
        "> 재실행 없이 기존 `run_results.jsonl`을 후처리. 결정론 Track A.",
        f"> 가정: per_round_cost(t_llm+t_net) 스윕 {PER_ROUND_COSTS_S}초, "
        f"힌트 계산 오버헤드 {HINT_COMPUTE_OVERHEAD_S*1000:.0f}ms(실측), deadline {DEADLINES_ROUNDS} 라운드.\n",
    ]
    for name, sub in DATASETS.items():
        path = RESULTS / sub / "run_results.jsonl"
        if not path.exists():
            continue
        lines += analyze(name, load_runs(path))
    report = "\n".join(lines)
    out_path = RESULTS / "analysis-realistic-latency-deadline.md"
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n[written] {out_path}")


if __name__ == "__main__":
    main()
