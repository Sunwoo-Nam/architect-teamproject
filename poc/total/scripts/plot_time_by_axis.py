#!/usr/bin/env python3
"""70·71 보고서 그림 — 축 수별 실제 시간(합성 T) 그래프 (PL 지시 2026-08-14).

축 수준별로 설계안(seq2·pool·poolka)과 naive 기준선의 합성 시간을 로그 y축에
그린다 — 중앙값은 실선+마커, P95는 같은 색의 점선. naive T는 방안 무관(케이스의
성질)이라 한 선이다. 12축은 CR/RS 표본 성질이 달라 트랙별 패널로 분리한다.

사용: .venv/bin/python scripts/plot_time_by_axis.py <main_run> <p6_run> <out_dir>
출력: <out_dir>/fig-time-by-axis.png (300dpi)
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

COLORS = {"naive": "0.45", "seq2": "#3A6FE0", "pool": "#D5484A", "poolka": "#E8A33D"}
LABELS = {"naive": "naive baseline", "seq2": "plan 1 (seq2)",
          "pool": "plan 2 (pool)", "poolka": "plan 2 + P6 (poolka)"}


def q95(vals):
    v = sorted(vals)
    return v[min(len(v) - 1, int(0.95 * len(v)))]


def series(rows, plan, track, levels, key="T_ms"):
    med, p95 = [], []
    for n in levels:
        sel = [r[key] for r in rows
               if r["plan"] == plan and r["track"] == track and r["n_issues"] == n
               and r.get(key) is not None]
        med.append(statistics.median(sel) / 1000 if sel else None)
        p95.append(q95(sel) / 1000 if sel else None)
    return med, p95


def main():
    main_run, p6_run, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in (main_run / "cases.jsonl").read_text().splitlines()]
    p6 = [json.loads(l) for l in (p6_run / "cases.jsonl").read_text().splitlines()]

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), dpi=300, sharey=True)
    panels = (("cr", list(range(4, 13)), "CR track (4-12 axes, oracle)"),
              ("rs", [12, 14, 16, 18, 20], "RS track (12-20 axes, scale stress)"))
    for ax, (track, levels, title) in zip(axes, panels):
        # naive — 방안 무관 (seq2 행의 baseline 열에서)
        med, p95 = series(rows, "seq2", track, levels, key="T_baseline_ms")
        ax.plot(levels, med, "-o", color=COLORS["naive"], linewidth=1.8, markersize=4,
                label=LABELS["naive"])
        ax.plot(levels, p95, ":", color=COLORS["naive"], linewidth=1.2)
        for plan, src in (("seq2", rows), ("pool", rows), ("poolka", p6)):
            med, p95 = series(src, plan, track, levels)
            dash = (0, (5, 2.2)) if plan == "poolka" else "-"
            ax.plot(levels, med, linestyle=dash, marker="o", color=COLORS[plan],
                    linewidth=1.6, markersize=4, label=LABELS[plan])
            ax.plot(levels, p95, ":", color=COLORS[plan], linewidth=1.1)
        ax.set_yscale("log")
        ax.set_xticks(levels)
        ax.set_xlabel("number of issues (axes)", fontsize=10)
        ax.set_title(title, fontsize=10.5)
        ax.grid(True, which="major", color="0.90", linewidth=0.7)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color("0.55")
        ax.tick_params(labelsize=9)
    axes[0].set_ylabel("synthetic time T (seconds, log)", fontsize=10)
    axes[0].legend(loc="upper left", fontsize=8.5, framealpha=0.9, edgecolor="0.75")
    axes[1].text(0.02, 0.02, "solid+marker = median · dotted = P95",
                 transform=axes[1].transAxes, fontsize=8, color="0.35")
    fig.tight_layout()
    fig.savefig(out / "fig-time-by-axis.png")
    print(f"저장: {out}/fig-time-by-axis.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
