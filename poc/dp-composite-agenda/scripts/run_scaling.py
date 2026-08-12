"""축 수 확장성 종합 측정 — 1안(seq2) vs 2안(pool).

각 축 개수를 여러 인스턴스(시드)로 반복 측정한다. 정확한 x*(성긴 구조 이용)로 절대 달성률,
피크 메모리, 시간, 합의 여부를 기록하고, RAW 데이터(모든 실행) + 축 개수별 요약을 낸다.
메모리가 예산을 넘긴 안은 더 큰 축에서 중단 → 그 지점이 최대 지원 축 수.

표기: 1안 = seq2(T1+T3 개선), 2안 = pool. 완벽 정보(뷰=진실).

산출:
  - results/scaling_raw.jsonl : 모든 실행 raw
  - results/mem_scaling.svg   : 축 수(x) vs 피크 메모리(y, 로그) 안별 그래프

사용:  .venv/bin/python scripts/run_scaling.py [--seeds 4]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpca.common.exact import exact_xstar  # noqa: E402
from dpca.common.generators import Value  # noqa: E402
from dpca.common.profiles import build_truth_profiles, truth_utility  # noqa: E402
from dpca.common.rules import build_soft_rules  # noqa: E402
from dpca.common.scenario import Axis, load_scenario  # noqa: E402
from dpca.harness.runner import run_one  # noqa: E402

STRATS = [("1안", "seq2"), ("2안", "pool")]   # 표기 → 내부 전략
COUNTS = [4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32]
MEM_STOP_MB = 600.0      # 이 메모리 넘긴 안은 더 큰 축에서 중단(=최대 지원 축 근처)
TIME_STOP_S = 60.0
MEM_BUDGETS = [10, 100, 1000]     # 최대 축 수 판정용 메모리 예산(MB)
TIME_BUDGETS = [1, 10, 60]        # 시간 예산(s)
S11 = ROOT / "scenarios" / "S11-축수스윕.yaml"


def build(n_axes: int, seed: int):
    sc = load_scenario(S11, n_axes=min(n_axes, 10))
    for i in range(10, n_axes):
        sc.axes.append(Axis(f"x{i}", "numbered", [Value(f"x{i}_v{j}") for j in range(5)]))
    sc.participants["profile_seed"] = seed
    sc.agent_view = {"score_dropout": 0.0}
    return sc


def uofr(sc, agreement) -> float:
    ts = build_truth_profiles(sc)
    soft = build_soft_rules(sc, [t.home_region for t in ts])
    out = {ax.name: next(v for v in ax.values if v.name == agreement[ax.name]) for ax in sc.axes}
    return sum(truth_utility(ts[p], p, out, soft) for p in range(len(ts)))


def svg_mem_graph(curve: dict, path: Path):
    """축 수(x, 선형) vs 피크 메모리(y, 로그10 MB) 안별 라인 그래프."""
    W, H, L, R, T, B = 720, 440, 70, 160, 30, 50
    xs_all = sorted({n for pts in curve.values() for n, _ in pts})
    xmin, xmax = min(xs_all), max(xs_all)
    ys_all = [m for pts in curve.values() for _, m in pts if m > 0]
    ymin, ymax = min(ys_all), max(ys_all)
    lymin, lymax = math.log10(ymin), math.log10(max(ymax, ymin * 10))

    def px(n): return L + (n - xmin) / (xmax - xmin) * (W - L - R)
    def py(m): return T + (lymax - math.log10(m)) / (lymax - lymin) * (H - T - B)

    colors = {"1안": "#2c7fb8", "2안": "#d95f0e"}
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif">']
    s.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    s.append(f'<text x="{W/2}" y="18" font-size="15" text-anchor="middle" font-weight="bold">'
             f'축 수별 피크 메모리 — 1안(seq2) vs 2안(pool)</text>')
    # y 격자(로그 10^k)
    k0, k1 = math.floor(lymin), math.ceil(lymax)
    for k in range(k0, k1 + 1):
        m = 10 ** k
        if m < ymin / 2 or m > ymax * 2:
            continue
        y = py(m)
        s.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W-R}" y2="{y:.1f}" stroke="#eee"/>')
        lab = f'{m:.0f}MB' if m >= 1 else f'{m*1024:.0f}KB'
        s.append(f'<text x="{L-8}" y="{y+4:.1f}" font-size="11" text-anchor="end" fill="#555">{lab}</text>')
    # x 눈금
    for n in xs_all:
        x = px(n)
        s.append(f'<text x="{x:.1f}" y="{H-B+18}" font-size="11" text-anchor="middle" fill="#555">{n}</text>')
    s.append(f'<text x="{(L+W-R)/2:.0f}" y="{H-8}" font-size="12" text-anchor="middle">축 개수</text>')
    # 라인
    for label, pts in curve.items():
        pts = sorted(pts)
        d = " ".join(f'{px(n):.1f},{py(max(m,ymin)):.1f}' for n, m in pts)
        c = colors.get(label, "#333")
        s.append(f'<polyline points="{d}" fill="none" stroke="{c}" stroke-width="2.5"/>')
        for n, m in pts:
            s.append(f'<circle cx="{px(n):.1f}" cy="{py(max(m,ymin)):.1f}" r="3.2" fill="{c}"/>')
        lx, ly = pts[-1]
        s.append(f'<text x="{px(lx)+8:.1f}" y="{py(max(ly,ymin))+4:.1f}" font-size="12" '
                 f'fill="{c}" font-weight="bold">{label} ({dict(STRATS)[label]})</text>')
    s.append('</svg>')
    path.write_text("\n".join(s), encoding="utf-8")


def main() -> int:
    n_seeds = int(sys.argv[sys.argv.index("--seeds") + 1]) if "--seeds" in sys.argv else 4
    base = load_scenario(S11, n_axes=4).profile_seed
    # 워밍업
    for _, st in STRATS:
        run_one(build(4, base), st)

    rows = []
    curve = {label: [] for label, _ in STRATS}          # 메모리 그래프용 (축, MB 중앙값)
    summary = {label: {} for label, _ in STRATS}         # 축별 요약
    stopped = {label: False for label, _ in STRATS}

    for n in COUNTS:
        # 이 축의 시드별 x* (정확한 것만 FC 집계)
        seeds_valid = []
        for s in range(n_seeds):
            xs = exact_xstar(build(n, base + s))
            seeds_valid.append((base + s, xs["u_xstar"], xs["unconstrained_valid"]))
        for label, st in STRATS:
            if stopped[label]:
                continue
            peaks, times, achs, agrees = [], [], [], []
            for seed, uxs, valid in seeds_valid:
                sc = build(n, seed)
                r = run_one(sc, st)
                agreed = r.agreement is not None
                ach = (uofr(sc, r.agreement) / uxs) if (agreed and valid) else None
                peaks.append(r.peak_kib / 1024)
                times.append(r.wall_ms)
                agrees.append(agreed)
                if ach is not None:
                    achs.append(ach)
                rows.append({"axes": n, "seed": seed, "label": label, "strategy": st,
                             "achieved": round(ach, 4) if ach is not None else None,
                             "agreed": agreed, "peak_mb": round(r.peak_kib / 1024, 3),
                             "wall_ms": round(r.wall_ms, 1), "u_xstar": round(uxs, 4),
                             "exact_valid": valid})
            memmed, timemed = median(peaks), median(times)
            curve[label].append((n, memmed))
            summary[label][n] = {"fc": mean(achs) if achs else None,
                                 "agree": sum(agrees) / len(agrees),
                                 "mem_mb": memmed, "time_ms": timemed, "n": len(agrees)}
            fc_s = f"{mean(achs):.1%}" if achs else "—"
            print(f"  {n:>2}축 {label}({st}): FC {fc_s:>7} "
                  f"합의 {sum(agrees)}/{len(agrees)} 메모리 {memmed:>7.1f}MB 시간 {timemed:>6.0f}ms")
            if memmed > MEM_STOP_MB or timemed / 1000 > TIME_STOP_S:
                stopped[label] = True
                print(f"     → {label} 예산 초과, 이후 축 중단(최대 지원 축 ≈ {n})")

    # RAW 저장
    out = ROOT / "results" / "scaling_raw.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # 메모리 그래프
    svg = ROOT / "results" / "mem_scaling.svg"
    svg_mem_graph(curve, svg)

    # 축별 요약표
    print("\n=== 축 개수별 요약 (FC 달성률µ / 합의율 / 메모리MB / 시간ms) ===")
    all_counts = sorted({n for label, _ in STRATS for n in summary[label]})
    for label, st in STRATS:
        print(f"\n[{label} = {st}]")
        print(f"{'축':>3}{'FC':>8}{'합의':>7}{'메모리MB':>11}{'시간ms':>9}")
        for n in all_counts:
            d = summary[label].get(n)
            if not d:
                print(f"{n:>3}{'—(중단)':>8}")
                continue
            fc = f"{d['fc']:.1%}" if d["fc"] is not None else "—"
            ag = f"{d['agree']:.0%}"
            print(f"{n:>3}{fc:>8}{ag:>7}{d['mem_mb']:>11.2f}{d['time_ms']:>9.0f}")

    # 최대 지원 축 수 (예산별)
    def max_axes(label, mem_b=None, time_b=None):
        best = None
        for n in sorted(summary[label]):
            d = summary[label][n]
            if mem_b is not None and d["mem_mb"] > mem_b:
                continue
            if time_b is not None and d["time_ms"] / 1000 > time_b:
                continue
            best = n
        top = max(summary[label]) if summary[label] else 0
        return f"≥{best}" if best == top and not stopped[label] else (str(best) if best else "<4")

    print("\n=== 최대 지원 축 수 (예산별) ===")
    print(f"{'예산':>10}" + "".join(f"{label:>10}" for label, _ in STRATS))
    for b in MEM_BUDGETS:
        print(f"{b:>7}MB " + "".join(f"{max_axes(label, mem_b=b):>10}" for label, _ in STRATS))
    for b in TIME_BUDGETS:
        print(f"{b:>7}s  " + "".join(f"{max_axes(label, time_b=b):>10}" for label, _ in STRATS))

    print(f"\n{len(rows)} rows → {out}")
    print(f"메모리 그래프 → {svg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
