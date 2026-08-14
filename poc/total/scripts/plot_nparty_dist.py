#!/usr/bin/env python3
"""60·62 보고서 그림 — nparty TB(ρ) 전체 분포 ECDF + 밀도(PDF 추정) (PL 지시 2026-08-14).

composite의 `plot_composite_final_dist.py`(63 그림)와 동일 설계를 nparty에 적용한다:
판정이 P95(분위수)인 항목은 전체 분포를 함께 공개한다 — nparty에서 P95 판정 항목은
TB의 ρ 하나다 (FC = 평균, CF = 평균 — 24 §0).

산출물 (정본 run cases.jsonl에서 — 재시뮬레이션 없음):
- figures/60/fig-tb-rho-ecdf.{tex,png} · fig-tb-rho-hist.{tex,png}
  — 정본 비교 (방안 1-A vs 방안 2, 480건/방안)
- figures/62/fig-tb-rho-plus-ecdf.{tex,png} · fig-tb-rho-plus-hist.{tex,png}
  — 택틱 효과 (방안 2 vs 방안 2+, 480건/방안)

설계 규약 (63과 동일): ECDF는 x 로그축 + y=0.95 판정선 + 경계선(x=1, naive 등가);
밀도는 로그 등간격(십진 자릿수당 4구간) 히스토그램의 구간당 케이스 비율(%).
.tex는 standalone pgfplots(논문용, 그림 내 라벨 영문), .png는 md 삽입용 300dpi.
색·선 이중 부호화: 기준 방안 #D5484A 파선, 대조 방안 #3A6FE0 실선.

사용: .venv/bin/python scripts/plot_nparty_dist.py <run_dir> <figures_root>
  예: scripts/plot_nparty_dist.py results/nparty-tracks/nparty-tracks-20260814T001421Z \
      ../../docs/changbae/figures
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

P95 = 0.95

#: 그림별 (시리즈: (색 hex, 색 이름, 선 스타일, 라벨)) — 순서 = 그리기 순서
FIGSETS = {
    "60": {
        "stem": "fig-tb-rho",
        "series": {
            "plan1a": ("3A6FE0", "planblue", "solid", "plan 1-A (vote)"),
            "plan2": ("D5484A", "planred", "dashed", "plan 2 (rank-collect)"),
        },
    },
    "62": {
        "stem": "fig-tb-rho-plus",
        "series": {
            "plan2plusx": ("3A6FE0", "planblue", "solid", "plan 2+ (tactics)"),
            "plan2": ("D5484A", "planred", "dashed", "plan 2 (base)"),
        },
    },
}
XLABEL = r"time ratio $\rho$ = T(design) / T(naive)"
BOUNDARY = "naive parity"


def ecdf(values):
    xs = sorted(values)
    n = len(xs)
    return [(x, (i + 1) / n) for i, x in enumerate(xs)]


def p95(values):
    xs = sorted(values)
    return xs[min(len(xs) - 1, int(P95 * len(xs)))]


def log_bins(values_all, per_decade=4):
    lo = min(v for v in values_all if v > 0)
    hi = max(values_all)
    e0 = math.floor(math.log10(lo) * per_decade) / per_decade
    e1 = math.ceil(math.log10(hi) * per_decade) / per_decade
    n = int(round((e1 - e0) * per_decade))
    return [10 ** (e0 + i / per_decade) for i in range(n + 1)]


def hist_pct(values, edges):
    counts = [0] * (len(edges) - 1)
    for v in values:
        for i in range(len(counts)):
            if edges[i] <= v < edges[i + 1] or (i == len(counts) - 1 and v == edges[-1]):
                counts[i] += 1
                break
    n = len(values)
    return [100.0 * c / n for c in counts]


TEX_HEAD = r"""% 자동 생성: scripts/plot_nparty_dist.py — 수정은 스크립트에서
% 데이터: {run} cases.jsonl ({note})
\documentclass[tikz,border=2pt]{{standalone}}
\usepackage{{pgfplots}}
\pgfplotsset{{compat=1.18}}
{colordefs}\begin{{document}}
\begin{{tikzpicture}}
\begin{{axis}}[
  width=11cm, height=7cm,
  xmode=log,
  xlabel={{{xlabel}}},
  ylabel={{cumulative fraction of cases}},
  ymin=0, ymax=1.02,
  grid=major, grid style={{gray!20}},
  axis line style={{gray!60}},
  tick label style={{font=\small}},
  label style={{font=\small}},
  legend style={{at={{(0.03,0.97)}}, anchor=north west, font=\small,
                 draw=gray!40, fill=white, fill opacity=0.9, text opacity=1}},
  legend cell align=left,
]
\addplot[gray!70, dashed, thin, domain={dom}] {{0.95}};
\draw[gray!70, thin] (axis cs:1,0) -- (axis cs:1,1.02);
\node[gray!50!black, font=\scriptsize, anchor=south west, rotate=90]
  at (axis cs:1,0.02) {{{boundary}}};
\node[gray!50!black, font=\scriptsize, anchor=south east]
  at (rel axis cs:0.99,0.955) {{P95}};
"""

TEX_SERIES = r"""\addplot[{color}, {dash}, line width=1.1pt] coordinates {{
{coords}}};
\addlegendentry{{{label}}}
\addplot[{color}, mark=*, mark size=1.6pt, only marks] coordinates {{({px},0.95)}};
\node[{color}, font=\scriptsize, anchor=north west, xshift=3pt, yshift={yshift}pt] at (axis cs:{px},0.95) {{{ptxt}}};
"""

TEX_TAIL = "\\end{axis}\n\\end{tikzpicture}\n\\end{document}\n"

TEX_HIST_HEAD = r"""% 자동 생성: scripts/plot_nparty_dist.py — 수정은 스크립트에서
% 데이터: {run} cases.jsonl ({note})
\documentclass[tikz,border=2pt]{{standalone}}
\usepackage{{pgfplots}}
\pgfplotsset{{compat=1.18}}
{colordefs}\begin{{document}}
\begin{{tikzpicture}}
\begin{{axis}}[
  width=11cm, height=7cm,
  xmode=log,
  xlabel={{{xlabel}}},
  ylabel={{share of cases per bin (\%)}},
  ymin=0,
  grid=major, grid style={{gray!20}},
  axis line style={{gray!60}},
  tick label style={{font=\small}},
  label style={{font=\small}},
  legend style={{at={{(0.03,0.97)}}, anchor=north west, font=\small,
                 draw=gray!40, fill=white, fill opacity=0.9, text opacity=1}},
  legend cell align=left,
]
\draw[gray!70, thin] (axis cs:1,0) -- (axis cs:1,\pgfkeysvalueof{{/pgfplots/ymax}});
\node[gray!50!black, font=\scriptsize, anchor=south west, rotate=90]
  at (axis cs:1,0.3) {{{boundary}}};
"""

TEX_HIST_SERIES = r"""\addplot[{color}, {dash}, line width=1.1pt, const plot,
  fill={color}, fill opacity=0.10, draw opacity=1] coordinates {{
{coords}}} \closedcycle;
\addlegendentry{{{label}}}
"""


def _colordefs(series):
    return "".join(f"\\definecolor{{{cname}}}{{HTML}}{{{chex}}}\n"
                   for chex, cname, _d, _l in series.values())


def write_ecdf_tex(path, run, series, data, note):
    all_vals = [v for vals in data.values() for v in vals]
    dom = f"{min(all_vals):.6g}:{max(max(all_vals), 1.05):.6g}"
    parts = [TEX_HEAD.format(run=run, xlabel=XLABEL, boundary=BOUNDARY, dom=dom,
                             note=note, colordefs=_colordefs(series))]
    for idx, (plan, (chex, cname, dash, label)) in enumerate(series.items()):
        pairs = [f"({x:.6g},{y:.4f})" for x, y in ecdf(data[plan])]
        wrapped = "\n".join("".join(pairs[i:i + 5]) for i in range(0, len(pairs), 5))
        px = p95(data[plan])
        parts.append(TEX_SERIES.format(color=cname, dash=dash, coords=wrapped,
                                       label=label, px=f"{px:.6g}",
                                       yshift=-3 - 13 * idx,  # 라벨 겹침 방지 — 시리즈별 단차
                                       ptxt=f"P95={px:.3g}"))
    parts.append(TEX_TAIL)
    path.write_text("".join(parts))


def write_hist_tex(path, run, series, data, note):
    edges = log_bins([v for vals in data.values() for v in vals])
    parts = [TEX_HIST_HEAD.format(run=run, xlabel=XLABEL, boundary=BOUNDARY,
                                  note=note, colordefs=_colordefs(series))]
    for plan, (chex, cname, dash, label) in series.items():
        pct = hist_pct(data[plan], edges)
        pairs = [f"({edges[i]:.6g},{pct[i]:.3f})" for i in range(len(pct))]
        pairs.append(f"({edges[-1]:.6g},{pct[-1]:.3f})")
        wrapped = "\n".join("".join(pairs[i:i + 5]) for i in range(0, len(pairs), 5))
        parts.append(TEX_HIST_SERIES.format(color=cname, dash=dash, coords=wrapped,
                                            label=label))
    parts.append(TEX_TAIL)
    path.write_text("".join(parts))


def _style(dash):
    return "-" if dash == "solid" else (0, (5, 2.2))


def write_ecdf_png(path, series, data):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=300)
    for idx, (plan, (chex, _cn, dash, label)) in enumerate(series.items()):
        xs, ys = zip(*ecdf(data[plan]))
        ax.step(xs, ys, where="post", color="#" + chex, linestyle=_style(dash),
                linewidth=1.6, label=label)
        px = p95(data[plan])
        ax.plot([px], [0.95], marker="o", color="#" + chex, markersize=4.5)
        ax.annotate(f"P95={px:.3g}", (px, 0.95), textcoords="offset points",
                    xytext=(4, -11 - 13 * idx), fontsize=8, color="#" + chex)
    ax.axhline(0.95, color="0.62", linewidth=0.8, linestyle=(0, (4, 3)), zorder=1)
    ax.text(0.99, 0.955, "P95", transform=ax.get_yaxis_transform(),
            ha="right", fontsize=8, color="0.35")
    ax.axvline(1.0, color="0.62", linewidth=0.8, zorder=1)
    ax.text(1.0, 0.03, " " + BOUNDARY, rotation=90, va="bottom", ha="left",
            fontsize=8, color="0.35")
    ax.set_xscale("log")
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("time ratio ρ = T(design) / T(naive)", fontsize=10)
    ax.set_ylabel("cumulative fraction of cases", fontsize=10)
    ax.grid(True, which="major", color="0.90", linewidth=0.7)
    ax.tick_params(labelsize=9)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("0.55")
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9, edgecolor="0.75")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def write_hist_png(path, series, data):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    edges = log_bins([v for vals in data.values() for v in vals])
    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=300)
    for plan, (chex, _cn, dash, label) in series.items():
        pct = hist_pct(data[plan], edges)
        xs, ys = [], []
        for i, h in enumerate(pct):
            xs += [edges[i], edges[i + 1]]
            ys += [h, h]
        ax.fill_between(xs, ys, color="#" + chex, alpha=0.10)
        ax.plot(xs, ys, color="#" + chex, linewidth=1.5, linestyle=_style(dash),
                label=label)
    ax.set_xscale("log")
    ax.axvline(1.0, color="0.62", linewidth=0.8, zorder=1)
    ax.text(1.0, 0.4, " " + BOUNDARY, rotation=90, va="bottom", ha="left",
            fontsize=8, color="0.35")
    ax.set_ylim(bottom=0)
    ax.set_xlabel("time ratio ρ = T(design) / T(naive)", fontsize=10)
    ax.set_ylabel("share of cases per bin (%)", fontsize=10)
    ax.grid(True, which="major", color="0.90", linewidth=0.7)
    ax.tick_params(labelsize=9)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("0.55")
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9, edgecolor="0.75")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> int:
    run_dir = Path(sys.argv[1])
    fig_root = Path(sys.argv[2])
    rows = [json.loads(l) for l in open(run_dir / "cases.jsonl")]
    note = "functional-ext2 정본 — 전 480케이스/방안 (결렬 포함, 24 §4 모수)"

    for doc, spec in FIGSETS.items():
        data = {p: [r["rho"] for r in rows if r["plan"] == p and r.get("rho") is not None]
                for p in spec["series"]}
        for p, vals in data.items():
            assert vals, f"{p} 데이터 없음 — run에 해당 방안이 포함됐는지 확인"
        out = fig_root / doc
        out.mkdir(parents=True, exist_ok=True)
        stem = spec["stem"]
        write_ecdf_tex(out / f"{stem}-ecdf.tex", run_dir.name, spec["series"], data, note)
        write_hist_tex(out / f"{stem}-hist.tex", run_dir.name, spec["series"], data, note)
        write_ecdf_png(out / f"{stem}-ecdf.png", spec["series"], data)
        write_hist_png(out / f"{stem}-hist.png", spec["series"], data)
        print(f"{doc}: {stem}-{{ecdf,hist}}.{{tex,png}} → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
