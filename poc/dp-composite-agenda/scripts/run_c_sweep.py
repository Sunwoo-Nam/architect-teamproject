"""P3 — 조합-메모리 탄력성 c 측정 (29-1 A4).

피크 메모리 ∝ S^c 의 log-log 회귀 기울기 c. 관찰 로그 OFF(하니스 부가 할당 제외),
수준당 5회 중앙값. 두 방향을 따로 잰다 (DP 문서 미결질문 2):
  - values: S04(의존성 없음) 축값을 키워 S 증가 (d=4 고정)
  - axes:   S11 축 수를 4→10으로 키워 S 증가 (축당 값 5 고정) — pool의 kⁿ 약점 직격

full은 S가 크면 전수 나열이 사실상 OOM이므로 상한 초과 시 건너뛴다(그 자체가 c≈1의 실증).
c 판정: 별점(24.4 A4 척도) — 전체 열거 1 ~ 이론이상 1/d(=0.25) 5등분. 목표 CI 상한 < 1.

사용:  .venv/bin/python scripts/run_c_sweep.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpca.common.scenario import load_scenario  # noqa: E402
from dpca.harness.runner import STRATEGIES, run_one  # noqa: E402

FULL_SKIP_ABOVE = 300_000  # 이 조합 수 초과에서 full(전수)은 측정 생략 (OOM 실증)
REPS = 5
T_TABLE = {2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571}  # t_{0.975, df}


def peak_median(scenario, strategy: str) -> float:
    return median(run_one(scenario, strategy).peak_kib for _ in range(REPS))


def regress(log_s: list[float], log_m: list[float]) -> dict:
    n = len(log_s)
    xbar, ybar = sum(log_s) / n, sum(log_m) / n
    sxx = sum((x - xbar) ** 2 for x in log_s)
    sxy = sum((x - xbar) * (y - ybar) for x, y in zip(log_s, log_m))
    c = sxy / sxx
    b = ybar - c * xbar
    resid = [y - (c * x + b) for x, y in zip(log_s, log_m)]
    sse = sum(r * r for r in resid)
    sst = sum((y - ybar) ** 2 for y in log_m)
    r2 = 1 - sse / sst if sst > 0 else 1.0
    se = math.sqrt((sse / (n - 2)) / sxx) if n > 2 else 0.0
    t = T_TABLE.get(n - 2, 2.776)
    return {"c": c, "ci_lo": c - t * se, "ci_hi": c + t * se, "r2": r2, "n": n}


def stars_c(c: float, d: int = 4) -> int:
    lo = 1.0 / d  # 이론 이상값
    width = (1.0 - lo) / 5
    bounds = [lo + width * i for i in range(1, 6)]  # 0.40 0.55 0.70 0.85 1.00 (d=4)
    for i, bound in enumerate(bounds):
        if c <= bound:
            return 5 - i
    return 0


def run_sweep(name: str, levels: list[dict]) -> dict:
    """levels: [{'S': int, 'load': callable() -> scenario}]"""
    rows = []
    series: dict[str, tuple[list[float], list[float]]] = {st: ([], []) for st in STRATEGIES}
    for lv in levels:
        scenario = lv["load"]()
        S = scenario.space_size()
        for st in STRATEGIES:
            if st == "full" and S > FULL_SKIP_ABOVE:
                rows.append({"sweep": name, "S": S, "strategy": st, "peak_kib": None,
                             "note": "OOM 위험 — 측정 생략"})
                continue
            pk = peak_median(scenario, st)
            rows.append({"sweep": name, "S": S, "strategy": st, "peak_kib": round(pk, 1)})
            series[st][0].append(math.log(S))
            series[st][1].append(math.log(max(pk, 1e-6)))
    fits = {st: regress(*series[st]) for st in STRATEGIES if len(series[st][0]) >= 3}
    return {"rows": rows, "fits": fits}


def main() -> int:
    # 워밍업
    warm = load_scenario(ROOT / "scenarios" / "S01-기준.yaml")
    for st in STRATEGIES:
        run_one(warm, st)

    values_scales = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
    values_levels = [
        {"load": (lambda sc=sc: load_scenario(ROOT / "scenarios" / "S04-독립축.yaml", count_scale=sc))}
        for sc in values_scales
    ]
    axes_levels = [
        {"load": (lambda n=n: load_scenario(ROOT / "scenarios" / "S11-축수스윕.yaml", n_axes=n))}
        for n in (4, 6, 8, 10)
    ]

    print("=== values 방향 (S04, 축값 증가 · d=4 고정) ===")
    v = run_sweep("values", values_levels)
    print("=== axes 방향 (S11, 축 수 4→10 · 축당 값 5) ===")
    a = run_sweep("axes", axes_levels)

    out = ROOT / "results" / "c_sweep.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for row in v["rows"] + a["rows"]:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    for label, res in (("values", v), ("axes", a)):
        print(f"\n--- {label} 방향 피크 메모리(KiB, 중앙값) ---")
        Ss = sorted({r["S"] for r in res["rows"]})
        print(f"{'전략':<6}" + "".join(f"{s:>10}" for s in Ss))
        for st in STRATEGIES:
            cells = {r["S"]: r["peak_kib"] for r in res["rows"] if r["strategy"] == st}
            print(f"{st:<6}" + "".join(
                f"{(f'{cells[s]:.0f}' if cells.get(s) is not None else 'skip'):>10}" for s in Ss))
        print(f"{'':6}탄력성 c (95% CI, R², 별점):")
        for st in STRATEGIES:
            fit = res["fits"].get(st)
            if fit:
                verdict = "전체열거 기각" if fit["ci_hi"] < 1.0 else "전체열거 배제 못함"
                print(f"{'':6}  {st:<5} c={fit['c']:.3f} "
                      f"[{fit['ci_lo']:.3f}, {fit['ci_hi']:.3f}]  R²={fit['r2']:.3f}  "
                      f"★{stars_c(fit['c'])}  {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
