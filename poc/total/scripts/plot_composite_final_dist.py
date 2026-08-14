#!/usr/bin/env python3
"""63 보고서 그림 — TB(ρ)·RU(r) 전체 분포 ECDF (PL 지시 2026-08-14).

분포 표현은 ECDF — 누적분포에서 판정 통계(TB = P95, RU = 최대값; 24 §0,
RU는 2026-08-14 재개정)를 직접 읽을 수 있고, 값이 십진 자릿수 여러 개를
넘나드는 꼬리 분포라 x는 로그축이다.

산출물 (케이스×방안 원값 cases.jsonl에서 — 재시뮬레이션 없음):
- fig-{tb-rho,ru-r}-ecdf.{tex,png} — 누적분포(ECDF). 판정 통계를 직접 읽는 그림
  (ρ는 P95 마커, r는 P95·최대 2케이스 마커 병행 — 24 §2.8 3차)
- fig-{tb-rho,ru-r}-hist.{tex,png} — 밀도(PDF) 추정: 로그 등간격 히스토그램,
  y = 구간당 케이스 비율(%). 연속 측정값이라 PMF가 아니라 PDF의 추정이 맞고,
  x 로그축과 정합하도록 십진 자릿수당 4구간의 로그 구간을 쓴다
- .tex는 standalone pgfplots (논문 삽입용, pdflatex 컴파일 가능. 한글 의존을
  피하려고 그림 내 라벨은 영문), .png는 동일 설계의 래스터 (md 삽입용, 300dpi)

색: seq2 #3A6FE0(실선) / pool #D5484A(파선) — dataviz 검증기 6종 통과
(라이트 표면, CVD ΔE 23.4). 선 스타일 이중 부호화로 흑백 인쇄에서도 구분된다.

사용: .venv/bin/python scripts/plot_composite_final_dist.py <run_dir> <out_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

COLORS = {"seq2": "#3A6FE0", "pool": "#D5484A"}
DASHES = {"seq2": "solid", "pool": "dashed"}
P95 = 0.95


def ecdf(values):
    xs = sorted(values)
    n = len(xs)
    return [(x, (i + 1) / n) for i, x in enumerate(xs)]


def p95(values):
    xs = sorted(values)
    return xs[min(len(xs) - 1, int(P95 * len(xs)))]


def log_bins(values_all, per_decade=4):
    """전 방안 공통의 로그 등간격 구간 — 두 방안이 같은 구간을 써야 비교된다."""
    import math
    lo = min(v for v in values_all if v > 0)
    hi = max(values_all)
    e0 = math.floor(math.log10(lo) * per_decade) / per_decade
    e1 = math.ceil(math.log10(hi) * per_decade) / per_decade
    n = int(round((e1 - e0) * per_decade))
    return [10 ** (e0 + i / per_decade) for i in range(n + 1)]


def hist_pct(values, edges):
    """구간당 케이스 비율(%) — 밀도(PDF) 추정의 로그축 표현."""
    counts = [0] * (len(edges) - 1)
    for v in values:
        for i in range(len(counts)):
            if edges[i] <= v < edges[i + 1] or (i == len(counts) - 1 and v == edges[-1]):
                counts[i] += 1
                break
    n = len(values)
    return [100.0 * c / n for c in counts]


def load(run_dir: Path):
    rows = [json.loads(l) for l in open(run_dir / "cases.jsonl")]
    rho = {p: [r["rho"] for r in rows if r["plan"] == p and r.get("rho") is not None]
           for p in ("seq2", "pool")}
    rt = {p: [r["r_total"] for r in rows if r["plan"] == p] for p in ("seq2", "pool")}
    return rho, rt


# ---------------------------------------------------------------------------------------
# pgfplots (.tex) — standalone, 논문 삽입용
# ---------------------------------------------------------------------------------------

TEX_HEAD = r"""% 자동 생성: scripts/plot_composite_final_dist.py — 수정은 스크립트에서
% 데이터: {run} cases.jsonl ({note})
\documentclass[tikz,border=2pt]{{standalone}}
\usepackage{{pgfplots}}
\pgfplotsset{{compat=1.18}}
\definecolor{{seqblue}}{{HTML}}{{3A6FE0}}
\definecolor{{poolred}}{{HTML}}{{D5484A}}
\begin{{document}}
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
% 판정 통계선(있으면)과 경계선
{statline}\draw[black!65, line width=0.9pt] (axis cs:1,0) -- (axis cs:1,1.02);
\node[gray!50!black, font=\scriptsize, anchor=south west, rotate=90]
  at (axis cs:1,0.02) {{{boundary}}};
"""

TEX_SERIES = r"""\addplot[{color}, {dash}, line width=1.1pt] coordinates {{
{coords}}};
\addlegendentry{{{label}}}
{marks}"""

SERIES_MARK = r"""\addplot[{color}, mark=*, mark size=1.6pt, only marks] coordinates {{({px},{py})}};
\node[{color}, font=\scriptsize, anchor=north west, xshift=3pt, yshift=-3pt] at (axis cs:{px},{py}) {{{ptxt}}};
"""

TEX_TAIL = "\\end{axis}\n\\end{tikzpicture}\n\\end{document}\n"

TEX_HIST_HEAD = r"""% 자동 생성: scripts/plot_composite_final_dist.py — 수정은 스크립트에서
% 데이터: {run} cases.jsonl ({note})
\documentclass[tikz,border=2pt]{{standalone}}
\usepackage{{pgfplots}}
\pgfplotsset{{compat=1.18}}
\definecolor{{seqblue}}{{HTML}}{{3A6FE0}}
\definecolor{{poolred}}{{HTML}}{{D5484A}}
\begin{{document}}
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
\draw[black!65, line width=0.9pt] (axis cs:1,0) -- (axis cs:1,\pgfkeysvalueof{{/pgfplots/ymax}});
\node[gray!50!black, font=\scriptsize, anchor=south west, rotate=90]
  at (axis cs:1,0.3) {{{boundary}}};
"""

TEX_HIST_SERIES = r"""\addplot[{color}, {dash}, line width=1.1pt, const plot,
  fill={color}, fill opacity=0.10, draw opacity=1] coordinates {{
{coords}}} \closedcycle;
\addlegendentry{{{label}}}
"""


def write_hist_tex(path: Path, run: str, series: dict, xlabel: str, boundary: str,
                   note: str):
    edges = log_bins([v for vals in series.values() for v in vals])
    parts = [TEX_HIST_HEAD.format(run=run, xlabel=xlabel, boundary=boundary, note=note)]
    for plan, vals in series.items():
        pct = hist_pct(vals, edges)
        pairs = [f"({edges[i]:.6g},{pct[i]:.3f})" for i in range(len(pct))]
        pairs.append(f"({edges[-1]:.6g},{pct[-1]:.3f})")
        wrapped = "\n".join("".join(pairs[i:i + 5]) for i in range(0, len(pairs), 5))
        parts.append(TEX_HIST_SERIES.format(
            color="seqblue" if plan == "seq2" else "poolred",
            dash=DASHES[plan], coords=wrapped,
            label="plan 1 (seq2)" if plan == "seq2" else "plan 2 (pool)"))
    parts.append(TEX_TAIL)
    path.write_text("".join(parts))


def write_hist_png(path: Path, series: dict, xlabel: str, boundary: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    edges = log_bins([v for vals in series.values() for v in vals])
    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=300)
    for plan, vals in series.items():
        pct = hist_pct(vals, edges)
        xs, ys = [], []
        for i, h in enumerate(pct):
            xs += [edges[i], edges[i + 1]]
            ys += [h, h]
        ax.fill_between(xs, ys, step=None, color=COLORS[plan], alpha=0.10)
        ax.plot(xs, ys, color=COLORS[plan], linewidth=1.5,
                linestyle="-" if DASHES[plan] == "solid" else (0, (5, 2.2)),
                label="plan 1 (seq2)" if plan == "seq2" else "plan 2 (pool)")
    ax.set_xscale("log")
    ax.axvline(1.0, color="0.30", linewidth=1.2, zorder=1)
    ax.text(1.0, 0.4, " " + boundary, rotation=90, va="bottom", ha="left",
            fontsize=8, color="0.25")
    ax.set_ylim(bottom=0)
    ax.set_xlabel(xlabel, fontsize=10)
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


def write_tex(path: Path, run: str, series: dict, xlabel: str, boundary: str,
              dom: str, note: str, stat: str = "p95"):
    # stat: 표기할 통계 — TB는 "p95", RU는 "both" (P95·최대 2케이스 병행, 24 §2.8 3차)
    marks = ("p95", "max") if stat == "both" else (stat,)
    statline = ("\\addplot[gray!70, dashed, thin, domain=%s] {0.95};\n"
                "\\node[gray!50!black, font=\\scriptsize, anchor=south east]\n"
                "  at (rel axis cs:0.99,0.955) {P95};\n" % dom) if "p95" in marks else ""
    parts = [TEX_HEAD.format(run=run, xlabel=xlabel, boundary=boundary,
                             statline=statline, note=note)]
    for plan, vals in series.items():
        pairs = [f"({x:.6g},{y:.4f})" for x, y in ecdf(vals)]
        # 줄바꿈은 좌표쌍 경계에서만 (5쌍/줄)
        wrapped = "\n".join("".join(pairs[i:i + 5]) for i in range(0, len(pairs), 5))
        marker_tex = []
        for m in marks:
            px = p95(vals) if m == "p95" else max(vals)
            py = "0.95" if m == "p95" else "1.0"
            marker_tex.append(SERIES_MARK.format(
                color="seqblue" if plan == "seq2" else "poolred",
                px=f"{px:.6g}", py=py,
                ptxt=f"{'P95' if m == 'p95' else 'max'}={px:.3g}"))
        parts.append(TEX_SERIES.format(
            color="seqblue" if plan == "seq2" else "poolred",
            dash=DASHES[plan], coords=wrapped,
            label=f"plan 1 (seq2)" if plan == "seq2" else "plan 2 (pool)",
            marks="".join(marker_tex)))
    parts.append(TEX_TAIL)
    path.write_text("".join(parts))


# ---------------------------------------------------------------------------------------
# matplotlib (.png) — md 삽입용, 동일 설계
# ---------------------------------------------------------------------------------------

def write_png(path: Path, series: dict, xlabel: str, boundary: str, stat: str = "p95"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=300)
    for plan, vals in series.items():
        pts = ecdf(vals)
        xs, ys = zip(*pts)
        ax.step(xs, ys, where="post", color=COLORS[plan],
                linestyle="-" if DASHES[plan] == "solid" else (0, (5, 2.2)),
                linewidth=1.6,
                label="plan 1 (seq2)" if plan == "seq2" else "plan 2 (pool)")
        marks = ("p95", "max") if stat == "both" else (stat,)
        for m in marks:
            if m == "p95":
                px, py = p95(vals), P95
                txt, xy, ha = f"P95={px:.3g}", (8, -17), "left"   # 우하단 — ECDF가 P95 위로 지나 빈 영역
            else:
                px, py = max(vals), 1.0
                txt, xy, ha = f"max={px:.3g}", (-6, -14), "right"  # 상단 끝점 — 좌하단으로 빼서 겹침 회피
            ax.plot([px], [py], "o", color=COLORS[plan], markersize=4.5, zorder=5)
            ax.annotate(txt, (px, py), textcoords="offset points",
                        xytext=xy, ha=ha, fontsize=8.5, color=COLORS[plan])
    ax.set_xscale("log")
    if stat in ("p95", "both"):
        ax.axhline(P95, color="0.62", linewidth=0.8, linestyle="--", zorder=1)
        # both 모드에서는 우측 상단(max 주석)·좌측 상단(범례)을 피해 중앙에 둔다
        lx, lha = (0.50, "center") if stat == "both" else (0.99, "right")
        ax.text(lx, P95 + 0.008, "P95", transform=ax.get_yaxis_transform(),
                ha=lha, va="bottom", fontsize=8, color="0.35")
    ax.axvline(1.0, color="0.30", linewidth=1.2, zorder=1)
    ax.text(1.0, 0.02, " " + boundary, rotation=90, va="bottom", ha="left",
            fontsize=8, color="0.25")
    ax.set_ylim(0, 1.02)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel("cumulative fraction of cases", fontsize=10)
    ax.grid(True, which="major", color="0.90", linewidth=0.7)
    ax.tick_params(labelsize=9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("0.55")
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9, edgecolor="0.75")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    run_dir = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    rho, rt = load(run_dir)
    run = run_dir.name

    n_rho = {p: len(v) for p, v in rho.items()}
    write_tex(out / "fig-tb-rho-ecdf.tex", run, rho,
              xlabel=r"time ratio $\rho = T_{\mathrm{design}} / T_{\mathrm{naive}}$",
              boundary=r"$\rho=1$ (defect boundary)",
              dom="0.0005:20", note=f"rho, n={n_rho}")
    write_png(out / "fig-tb-rho-ecdf.png", rho,
              xlabel=r"time ratio  $\rho = T_\mathrm{design}\,/\,T_\mathrm{naive}$",
              boundary=r"$\rho$=1 (defect boundary)")
    write_hist_tex(out / "fig-tb-rho-hist.tex", run, rho,
                   xlabel=r"time ratio $\rho = T_{\mathrm{design}} / T_{\mathrm{naive}}$",
                   boundary=r"$\rho=1$ (defect boundary)", note=f"rho, n={n_rho}")
    write_hist_png(out / "fig-tb-rho-hist.png", rho,
                   xlabel=r"time ratio  $\rho = T_\mathrm{design}\,/\,T_\mathrm{naive}$",
                   boundary=r"$\rho$=1 (defect boundary)")

    n_rt = {p: len(v) for p, v in rt.items()}
    write_tex(out / "fig-ru-r-ecdf.tex", run, rt,
              xlabel=r"memory usage ratio $r$ = device footprint / 128\,MB",
              boundary=r"$r=1$ (ceiling)",
              dom="0.00005:50", note=f"r_total, n={n_rt}", stat="both")
    write_png(out / "fig-ru-r-ecdf.png", rt,
              xlabel=r"memory usage ratio  $r$ = device footprint / 128 MB",
              boundary=r"$r$=1 (ceiling)", stat="both")
    write_hist_tex(out / "fig-ru-r-hist.tex", run, rt,
                   xlabel=r"memory usage ratio $r$ = device footprint / 128\,MB",
                   boundary=r"$r=1$ (ceiling)", note=f"r_total, n={n_rt}")
    write_hist_png(out / "fig-ru-r-hist.png", rt,
                   xlabel=r"memory usage ratio  $r$ = device footprint / 128 MB",
                   boundary=r"$r$=1 (ceiling)")

    for p in ("seq2", "pool"):
        print(f"{p}: ρ n={n_rho[p]} P95={p95(rho[p]):.4f} · r n={n_rt[p]} P95={p95(rt[p]):.6f}")
    print(f"저장: {out}/fig-{{tb-rho,ru-r}}-{{ecdf,hist}}.{{tex,png}}")


if __name__ == "__main__":
    main()
