#!/usr/bin/env python3
"""63 보고서 그림 — TB(ρ)·RU(r) 전체 분포 ECDF (PL 지시 2026-08-14).

판정이 P95(분위수)이므로 분포 표현은 ECDF를 쓴다 — 누적분포에서 P95를 직접
읽을 수 있고, 값이 십진 자릿수 여러 개를 넘나드는 꼬리 분포라 x는 로그축이다.

산출물 (케이스×방안 원값 cases.jsonl에서 — 재시뮬레이션 없음):
- fig-tb-rho-ecdf.tex / fig-ru-r-ecdf.tex — standalone pgfplots (논문 삽입용,
  pdflatex 컴파일 가능. 한글 의존을 피하려고 그림 내 라벨은 영문)
- fig-tb-rho-ecdf.png / fig-ru-r-ecdf.png — 동일 설계의 래스터 (md 삽입용, 300dpi)

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
% P95 판정선과 경계선
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
\node[{color}, font=\scriptsize, anchor=north west, xshift=3pt, yshift=-3pt] at (axis cs:{px},0.95) {{{ptxt}}};
"""

TEX_TAIL = "\\end{axis}\n\\end{tikzpicture}\n\\end{document}\n"


def write_tex(path: Path, run: str, series: dict, xlabel: str, boundary: str,
              dom: str, note: str):
    parts = [TEX_HEAD.format(run=run, xlabel=xlabel, boundary=boundary,
                             dom=dom, note=note)]
    for plan, vals in series.items():
        pairs = [f"({x:.6g},{y:.4f})" for x, y in ecdf(vals)]
        # 줄바꿈은 좌표쌍 경계에서만 (5쌍/줄)
        wrapped = "\n".join("".join(pairs[i:i + 5]) for i in range(0, len(pairs), 5))
        px = p95(vals)
        parts.append(TEX_SERIES.format(
            color="seqblue" if plan == "seq2" else "poolred",
            dash=DASHES[plan], coords=wrapped,
            label=f"plan 1 (seq2)" if plan == "seq2" else "plan 2 (pool)",
            px=f"{px:.6g}",
            ptxt=f"P95={px:.3g}"))
    parts.append(TEX_TAIL)
    path.write_text("".join(parts))


# ---------------------------------------------------------------------------------------
# matplotlib (.png) — md 삽입용, 동일 설계
# ---------------------------------------------------------------------------------------

def write_png(path: Path, series: dict, xlabel: str, boundary: str):
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
        px = p95(vals)
        ax.plot([px], [P95], "o", color=COLORS[plan], markersize=4.5, zorder=5)
        # 주석은 점의 우하단 — 두 그림 모두 ECDF가 P95 위로 지나가 이 영역이 빈다
        ax.annotate(f"P95={px:.3g}", (px, P95), textcoords="offset points",
                    xytext=(7, -15), ha="left", fontsize=8.5,
                    color=COLORS[plan])
    ax.set_xscale("log")
    ax.axhline(P95, color="0.62", linewidth=0.8, linestyle="--", zorder=1)
    ax.text(0.99, P95 + 0.008, "P95", transform=ax.get_yaxis_transform(),
            ha="right", va="bottom", fontsize=8, color="0.35")
    ax.axvline(1.0, color="0.62", linewidth=0.8, zorder=1)
    ax.text(1.0, 0.02, " " + boundary, rotation=90, va="bottom", ha="left",
            fontsize=8, color="0.35")
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

    n_rt = {p: len(v) for p, v in rt.items()}
    write_tex(out / "fig-ru-r-ecdf.tex", run, rt,
              xlabel=r"memory usage ratio $r$ = device footprint / 128\,MB",
              boundary=r"$r=1$ (ceiling)",
              dom="0.00005:50", note=f"r_total, n={n_rt}")
    write_png(out / "fig-ru-r-ecdf.png", rt,
              xlabel=r"memory usage ratio  $r$ = device footprint / 128 MB",
              boundary=r"$r$=1 (ceiling)")

    for p in ("seq2", "pool"):
        print(f"{p}: ρ n={n_rho[p]} P95={p95(rho[p]):.4f} · r n={n_rt[p]} P95={p95(rt[p]):.6f}")
    print(f"저장: {out}/fig-{{tb-rho,ru-r}}-ecdf.{{tex,png}}")


if __name__ == "__main__":
    main()
