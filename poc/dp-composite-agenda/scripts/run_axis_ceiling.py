"""Scalability(의제 수) — "몇 의제(축)까지 가능한가"를 자원 예산으로 측정.

c(메모리 지수) 대신, 더 직관적인 **최대 지원 축 수**로 확장성을 잰다. 축 수를 2→24로
키우며(축당 값 5 고정) 전략별 **피크 메모리**와 **wall time**을 따로 기록하고, 자원 예산
(메모리·시간 지연) 안에 드는 최대 축 수를 구한다.

- 10축 초과분은 S11에 없으므로 독립 축(numbered, 값 5)을 합성해 붙인다 — 축 '수'의 스트레스지
  구조가 아니므로 의존성은 앞 10축에만 있다.
- full은 전수순회라 시간이 급증(결정적)하므로 seed 1회. pool/seq는 seed 여러 개로 합의율도 병기.
- 예산 초과(시간/메모리)한 전략은 더 큰 축에서 측정 중단.

사용:  .venv/bin/python scripts/run_axis_ceiling.py [--seeds 3] [--perfect]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpca.common.generators import Value  # noqa: E402
from dpca.common.scenario import Axis, load_scenario  # noqa: E402
from dpca.harness.runner import run_one  # noqa: E402

AXIS_LEVELS = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24]
VALS_PER_AXIS = 5
STOP_TIME_S = 60.0        # 이 시간 넘긴 전략은 더 큰 축에서 중단
STOP_MEM_MB = 1200.0      # 이 메모리 넘긴 전략은 더 큰 축에서 중단
MEM_BUDGETS_MB = [10, 100, 1000]     # 최대 축 수 판정 메모리 예산
TIME_BUDGETS_S = [1, 10, 60]         # 최대 축 수 판정 시간 예산
S11 = ROOT / "scenarios" / "S11-축수스윕.yaml"
PERFECT = "--perfect" in sys.argv


def build(n_axes: int, seed: int | None = None):
    sc = load_scenario(S11, n_axes=min(n_axes, 10))
    for i in range(10, n_axes):
        sc.axes.append(Axis(f"x{i}", "numbered",
                            [Value(f"x{i}_v{j}") for j in range(VALS_PER_AXIS)]))
    if seed is not None:
        sc.participants["profile_seed"] = seed
    if PERFECT:
        sc.agent_view = {"score_dropout": 0.0}
    return sc


def main() -> int:
    n_seeds = int(sys.argv[sys.argv.index("--seeds") + 1]) if "--seeds" in sys.argv else 3
    print(f"[정보 전제: {'완벽(뷰=진실)' if PERFECT else '부분(뷰 노이즈 有)'}]  "
          f"축당 값 {VALS_PER_AXIS}, seed {n_seeds}")

    # 워밍업
    for st in ("full", "pool", "seq"):
        run_one(build(4), st)

    strategies = ("full", "pool", "seq")
    stopped = {st: False for st in strategies}
    # curve[st] = list of {n, mem_mb, time_s, agree_rate}
    curve = {st: [] for st in strategies}
    rows: list[dict] = []
    base_seed = build(4).profile_seed

    for n in AXIS_LEVELS:
        for st in strategies:
            if stopped[st]:
                continue
            reps = 1 if st == "full" else n_seeds   # full은 결정적 → 1회
            peaks, times, agrees = [], [], []
            for s in range(reps):
                sc = build(n, seed=base_seed + s)
                r = run_one(sc, st)
                peaks.append(r.peak_kib / 1024)      # MB
                times.append(r.wall_ms / 1000)       # s
                agrees.append(1 if r.agreement else 0)
            mem, tm = median(peaks), median(times)
            ar = sum(agrees) / len(agrees)
            curve[st].append({"n": n, "mem_mb": mem, "time_s": tm, "agree_rate": ar})
            rows.append({"strategy": st, "n": n, "vals": VALS_PER_AXIS,
                         "mem_mb": round(mem, 2), "time_s": round(tm, 3), "agree_rate": ar})
            if tm > STOP_TIME_S or mem > STOP_MEM_MB:
                stopped[st] = True
        print(f"  {n:>2}축 완료 " + " ".join(
            f"{st}:{curve[st][-1]['mem_mb']:.0f}MB/{curve[st][-1]['time_s']:.1f}s"
            for st in strategies if curve[st] and curve[st][-1]['n'] == n))

    out = ROOT / "results" / ("axis_ceiling_perfect.jsonl" if PERFECT else "axis_ceiling.jsonl")
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # --- 곡선 ---
    print("\n=== 축 수별 피크 메모리 (MB) ===")
    print(f"{'축':>4}" + "".join(f"{st:>12}" for st in strategies))
    for n in AXIS_LEVELS:
        cells = []
        for st in strategies:
            hit = next((c for c in curve[st] if c["n"] == n), None)
            cells.append(f"{hit['mem_mb']:>12.1f}" if hit else f"{'—':>12}")
        print(f"{n:>4}" + "".join(cells))

    print("\n=== 축 수별 wall time (s) ===")
    print(f"{'축':>4}" + "".join(f"{st:>12}" for st in strategies))
    for n in AXIS_LEVELS:
        cells = []
        for st in strategies:
            hit = next((c for c in curve[st] if c["n"] == n), None)
            cells.append(f"{hit['time_s']:>12.2f}" if hit else f"{'—':>12}")
        print(f"{n:>4}" + "".join(cells))

    print("\n=== 합의율 (자원 천장과 별개 — seq 신뢰성) ===")
    print(f"{'축':>4}" + "".join(f"{st:>12}" for st in strategies))
    for n in AXIS_LEVELS:
        cells = []
        for st in strategies:
            hit = next((c for c in curve[st] if c["n"] == n), None)
            cells.append(f"{hit['agree_rate']:>12.0%}" if hit else f"{'—':>12}")
        print(f"{n:>4}" + "".join(cells))

    # --- 최대 지원 축 수 (예산별) ---
    def max_axes(st, mem_budget=None, time_budget=None) -> str:
        best = None
        for c in curve[st]:
            if mem_budget is not None and c["mem_mb"] > mem_budget:
                continue
            if time_budget is not None and c["time_s"] > time_budget:
                continue
            best = c["n"]
        if best is None:
            return "<2"
        # 스윕 상한까지 예산 안이면 ">=상한"으로 표기(실제 천장은 더 높을 수 있음)
        last = curve[st][-1]
        within_last = ((mem_budget is None or last["mem_mb"] <= mem_budget)
                       and (time_budget is None or last["time_s"] <= time_budget))
        return (f"≥{best}" if best == AXIS_LEVELS[-1] and within_last and not
                any(cc["n"] > best for cc in curve[st]) else str(best))

    print("\n=== 최대 지원 축 수 (메모리 예산) ===")
    print(f"{'예산':>10}" + "".join(f"{st:>10}" for st in strategies))
    for b in MEM_BUDGETS_MB:
        print(f"{b:>8}MB" + "".join(f"{max_axes(st, mem_budget=b):>10}" for st in strategies))

    print("\n=== 최대 지원 축 수 (시간 예산) ===")
    print(f"{'예산':>10}" + "".join(f"{st:>10}" for st in strategies))
    for b in TIME_BUDGETS_S:
        print(f"{b:>7}s " + "".join(f"{max_axes(st, time_budget=b):>10}" for st in strategies))

    print(f"\n{len(rows)} rows → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
