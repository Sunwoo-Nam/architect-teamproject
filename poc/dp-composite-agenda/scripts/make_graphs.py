"""scaling_raw.jsonl에서 그래프 3종 생성 — 메모리·시간·FC (축 수 x축, 1안 vs 2안).

산출: results/mem_scaling.svg, time_scaling.svg, fc_scaling.svg
사용:  .venv/bin/python scripts/make_graphs.py
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
COLORS = {"1안": "#2c7fb8", "2안": "#d95f0e"}
SUB = {"1안": "seq2", "2안": "pool"}


def line_svg(curves, title, ylab, log_y, path, yfmt):
    W, H, L, R, T, B = 720, 440, 78, 150, 34, 52
    xs = sorted({x for pts in curves.values() for x, _ in pts})
    xmin, xmax = min(xs), max(xs)
    ys = [y for pts in curves.values() for _, y in pts if (y > 0 or not log_y)]
    ymin, ymax = min(ys), max(ys)
    if log_y:
        lymin, lymax = math.log10(max(ymin, 1e-6)), math.log10(max(ymax, ymin * 10))
        ymap = lambda v: (lymax - math.log10(max(v, 1e-6))) / (lymax - lymin)
    else:
        lo = min(ymin, 0); hi = ymax * 1.05
        ymap = lambda v: (hi - v) / (hi - lo)

    def px(x): return L + (x - xmin) / (xmax - xmin) * (W - L - R)
    def py(v): return T + ymap(v) * (H - T - B)

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif">']
    s.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    s.append(f'<text x="{W/2}" y="20" font-size="15" text-anchor="middle" font-weight="bold">{title}</text>')
    # y 격자
    if log_y:
        for k in range(math.floor(lymin), math.ceil(lymax) + 1):
            v = 10 ** k
            if v < ymin / 2 or v > ymax * 2:
                continue
            y = py(v)
            s.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W-R}" y2="{y:.1f}" stroke="#eee"/>')
            s.append(f'<text x="{L-8}" y="{y+4:.1f}" font-size="11" text-anchor="end" fill="#555">{yfmt(v)}</text>')
    else:
        for i in range(6):
            v = ymax * 1.05 * i / 5
            y = py(v)
            s.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W-R}" y2="{y:.1f}" stroke="#eee"/>')
            s.append(f'<text x="{L-8}" y="{y+4:.1f}" font-size="11" text-anchor="end" fill="#555">{yfmt(v)}</text>')
    for x in xs:
        s.append(f'<text x="{px(x):.1f}" y="{H-B+18}" font-size="11" text-anchor="middle" fill="#555">{x}</text>')
    s.append(f'<text x="{(L+W-R)/2:.0f}" y="{H-10}" font-size="12" text-anchor="middle">축 개수</text>')
    s.append(f'<text x="16" y="{(T+H-B)/2:.0f}" font-size="12" text-anchor="middle" '
             f'transform="rotate(-90 16 {(T+H-B)/2:.0f})">{ylab}</text>')
    for label, pts in curves.items():
        pts = sorted(pts)
        c = COLORS[label]
        d = " ".join(f'{px(x):.1f},{py(y):.1f}' for x, y in pts)
        s.append(f'<polyline points="{d}" fill="none" stroke="{c}" stroke-width="2.5"/>')
        for x, y in pts:
            s.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="3.2" fill="{c}"/>')
        lx, ly = pts[-1]
        s.append(f'<text x="{px(lx)+8:.1f}" y="{py(ly)+4:.1f}" font-size="12" fill="{c}" '
                 f'font-weight="bold">{label} ({SUB[label]})</text>')
    s.append('</svg>')
    path.write_text("\n".join(s), encoding="utf-8")
    print(f"  → {path.name}")


def main() -> int:
    rows = [json.loads(l) for l in (ROOT / "results" / "scaling_raw.jsonl").open(encoding="utf-8")]
    mem = defaultdict(list); tim = defaultdict(list); fc = defaultdict(list)
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by[(r["label"], r["axes"])]["mem"].append(r["peak_mb"])
        by[(r["label"], r["axes"])]["time"].append(r["wall_ms"])
        if r["achieved"] is not None:
            by[(r["label"], r["axes"])]["fc"].append(r["achieved"])
    for (label, n), d in by.items():
        mem[label].append((n, median(d["mem"])))
        tim[label].append((n, median(d["time"]) / 1000))
        if d["fc"]:
            fc[label].append((n, mean(d["fc"]) * 100))

    out = ROOT / "results"
    print("그래프 생성:")
    line_svg(mem, "축 수별 피크 메모리 — 1안 vs 2안", "피크 메모리(로그)", True,
             out / "mem_scaling.svg", lambda v: f"{v:.0f}MB" if v >= 1 else f"{v*1024:.0f}KB")
    line_svg(tim, "축 수별 협상 시간 — 1안 vs 2안", "wall time(로그)", True,
             out / "time_scaling.svg", lambda v: f"{v:.0f}s" if v >= 1 else f"{v*1000:.0f}ms")
    line_svg(fc, "축 수별 FC 달성률 — 1안 vs 2안", "FC 달성률(%)", False,
             out / "fc_scaling.svg", lambda v: f"{v:.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
