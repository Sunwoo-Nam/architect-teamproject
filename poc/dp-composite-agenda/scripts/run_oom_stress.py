"""P5 — full이 OOM하는 규모에서 seq vs pool 비교.

full은 조합 공간을 전수 물질화하므로 수백만 조합 이상에서 사실상 OOM이다(P3에서 실증).
이 측정은 그 규모(최대 10축×10값 = 100억 조합)에서 seq·pool이 살아남는지, 그리고
그 규모에서 어느 쪽이 더 좋은 합의를 내는지 비교한다.

FC 달성률(U(r)/U(x*))은 이 규모에서 못 쓴다 — x*를 구하려면 전수열거가 필요하고
그게 바로 여기서 불가능한 것이기 때문이다(oracle 한도 200,000). 대신 각 전략이 낸
**합의 하나의 진짜 전체 효용**을 판정기의 봉인 프로파일로 직접 계산해, 같은 시드에서
seq와 pool을 짝지어 비교한다. 정규화용 x*만 빠질 뿐, 우열과 격차는 정확히 잰다.

규모는 S11(하루 풀 플랜)을 n_axes·count_scale로 키워 만든다:
  (6,×1)=15,625  (8,×1)=390,625  (10,×1)=9.77M  (10,×1.5)=~1.07e9  (10,×2)=1e10
full은 실측 가능한 하한(≤ FULL_ATTEMPT_LIMIT)에서만 돌리고, 그 위는 외삽으로 예상 메모리를 적는다.

사용:  .venv/bin/python scripts/run_oom_stress.py [--seeds 20]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from statistics import median, pstdev

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpca.common.profiles import build_truth_profiles, truth_utility  # noqa: E402
from dpca.common.rules import (  # noqa: E402
    build_hard_rules,
    build_participant_hard,
    build_soft_rules,
)
from dpca.common.scenario import load_scenario  # noqa: E402
from dpca.harness.runner import run_one  # noqa: E402

FULL_ATTEMPT_LIMIT = 10_000_000  # 이 조합 수 이하에서만 full 실측. 초과는 외삽(시간 ∝ S).
FULL_REPS = 1                    # full 977만점은 ~100s라 1회만 (전수순회는 결정적, 반복 무의미)
S11 = ROOT / "scenarios" / "S11-축수스윕.yaml"
PERFECT = False                  # --perfect: 에이전트가 진짜 선호를 정확히 앎(뷰 노이즈 0)

# (라벨, n_axes, count_scale)
SIZES = [
    ("6축×5", 6, 1.0),
    ("8축×5", 8, 1.0),
    ("10축×5", 10, 1.0),
    ("10축×8", 10, 1.5),
    ("10축×10", 10, 2.0),
]


def make(n_axes: int, scale: float, seed: int | None = None):
    sc = load_scenario(S11, n_axes=n_axes, count_scale=scale)
    if seed is not None:
        sc.participants["profile_seed"] = seed
    if PERFECT:
        # 뷰 = 진실: 가중치 양자화·점수 드롭아웃 없음 → 에이전트 효용 = 판정기 진짜 효용
        sc.agent_view = {"score_dropout": 0.0}
    return sc


def true_eval(scenario, agreement: dict[str, str]) -> tuple[bool, list[float]]:
    """합의 하나의 진짜 참여자별 효용 — 판정기 봉인 프로파일로 점 하나만 평가(전수열거 아님)."""
    truths = build_truth_profiles(scenario)
    homes = [t.home_region for t in truths]
    soft = build_soft_rules(scenario, homes)
    hard = build_hard_rules(scenario) + build_participant_hard(scenario)
    outcome = {
        ax.name: next(v for v in ax.values if v.name == agreement[ax.name])
        for ax in scenario.axes
    }
    feasible = all(rule(outcome) for rule in hard)
    utils = [truth_utility(t, p, outcome, soft) for p, t in enumerate(truths)]
    return feasible, utils


def fr_below_floor(scenario, utils: list[float]) -> bool:
    truths = build_truth_profiles(scenario)
    return any(u < t.initial_threshold - 1e-9 for u, t in zip(utils, truths))


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def ci95(xs: list[float]) -> tuple[float, float]:
    if len(xs) < 2:
        return (0.0, 0.0)
    m = mean(xs)
    half = 1.96 * pstdev(xs) / (len(xs) ** 0.5)
    return (m - half, m + half)


def main() -> int:
    global PERFECT
    n_seeds = int(sys.argv[sys.argv.index("--seeds") + 1]) if "--seeds" in sys.argv else 20
    PERFECT = "--perfect" in sys.argv
    print(f"[정보 전제: {'완벽(뷰=진실, 노이즈 0)' if PERFECT else '부분(뷰 노이즈 有)'}]")

    # 워밍업 (tracemalloc 첫 실행 오염 방지)
    warm = make(6, 1.0)
    for st in ("full", "pool", "seq"):
        run_one(warm, st)

    rows: list[dict] = []
    full_points: list[tuple[float, float]] = []  # (S, peak_kib) 실측 → 외삽용

    for label, n_axes, scale in SIZES:
        base = make(n_axes, scale)
        S = base.space_size()
        base_seed = base.profile_seed

        # --- full: 실측 가능 하한에서만 ---
        if S <= FULL_ATTEMPT_LIMIT:
            runs = [run_one(make(n_axes, scale), "full") for _ in range(FULL_REPS)]
            fpk = median(r.peak_kib for r in runs)
            fms = median(r.wall_ms for r in runs)
            full_points.append((S, fpk, fms))
            rows.append({"size": label, "S": S, "strategy": "full",
                         "peak_kib": round(fpk, 1), "wall_ms": round(fms, 1), "measured": True})
            full_cell = f"{fpk/1024:,.1f}MB / {fms/1000:,.1f}s (실측)"
        else:
            full_cell = "실행 불가(외삽)"
            rows.append({"size": label, "S": S, "strategy": "full",
                         "peak_kib": None, "measured": False, "note": "전수순회 시간·메모리 초과 — 외삽"})

        # --- pool / seq: 시드별 짝비교 ---
        per = {"pool": [], "seq": []}
        for s in range(n_seeds):
            seed = base_seed + s
            sc = make(n_axes, scale, seed)
            for st in ("pool", "seq"):
                r = run_one(sc, st)
                agreed = r.agreement is not None
                feasible, utils = (True, [0.0, 0.0])
                total = mn = None
                fr = False
                if agreed:
                    feasible, utils = true_eval(sc, r.agreement)
                    total, mn = sum(utils), min(utils)
                    fr = fr_below_floor(sc, utils)
                per[st].append({
                    "seed": seed, "agreed": agreed, "feasible": feasible,
                    "total": total, "min": mn, "peak_kib": r.peak_kib,
                    "wall_ms": r.wall_ms, "phases": r.phases, "messages": r.messages,
                    "fr": fr,
                    "final_k": r.extra.get("final_k"), "deepening": r.extra.get("deepening"),
                    "backtracks": r.extra.get("backtracks"),
                })
                rows.append({
                    "size": label, "S": S, "strategy": st, "seed": seed,
                    "agreed": agreed, "feasible": feasible,
                    "true_total": round(total, 4) if total is not None else None,
                    "true_min": round(mn, 4) if mn is not None else None,
                    "peak_kib": round(r.peak_kib, 1), "wall_ms": round(r.wall_ms, 1),
                    "phases": r.phases, "messages": r.messages, "fr": fr,
                    "final_k": r.extra.get("final_k"), "deepening": r.extra.get("deepening"),
                    "backtracks": r.extra.get("backtracks"),
                })

        # 집계 (이 규모)
        def agg(st):
            xs = per[st]
            ag = [x for x in xs if x["agreed"]]
            return {
                "peak_med": median([x["peak_kib"] for x in xs]),
                "agree_rate": len(ag) / len(xs),
                "total_mean": mean([x["total"] for x in ag]) if ag else 0.0,
                "min_mean": mean([x["min"] for x in ag]) if ag else 0.0,
                "wall_med": median([x["wall_ms"] for x in xs]),
                "fr_rate": sum(x["fr"] for x in xs) / len(xs),
            }
        gp, gq = agg("pool"), agg("seq")
        # 짝비교 (양쪽 다 합의한 시드만)
        paired = [(p["total"], q["total"]) for p, q in zip(per["pool"], per["seq"])
                  if p["agreed"] and q["agreed"]]
        diffs = [pt - qt for pt, qt in paired]
        pool_wins = sum(d > 1e-9 for d in diffs)
        lo, hi = ci95(diffs)

        print(f"\n=== {label}  (S={S:,})  full: {full_cell} ===")
        print(f"{'':6}{'peak중앙':>12}{'합의율':>8}{'진짜효용합µ':>12}{'최소효용µ':>11}{'시간중앙ms':>11}")
        for st, g in (("pool", gp), ("seq", gq)):
            print(f"{st:<6}{g['peak_med']:>10.0f}KiB{g['agree_rate']:>8.0%}"
                  f"{g['total_mean']:>12.3f}{g['min_mean']:>11.3f}{g['wall_med']:>11.1f}")
        if paired:
            print(f"      짝비교(pool−seq 진짜효용합): 평균 {mean(diffs):+.3f} "
                  f"[95% {lo:+.3f}, {hi:+.3f}]  pool승 {pool_wins}/{len(paired)}")

    # full 외삽 — 시간은 O(S) 전수순회라 S에 정비례(깔끔), 메모리는 유효후보 비율 의존(근사).
    if full_points:
        big = max(full_points, key=lambda t: t[0])  # 가장 큰 실측점 기준으로 비례 확대
        Sb, pkb, msb = big
        print(f"\n--- full 외삽 (기준 실측점 S={Sb:,}: {pkb/1024:.1f}MB / {msb/1000:.1f}s) ---")
        print("    시간은 전수순회라 S에 정비례. 메모리는 유효후보 수 의존이라 근사.")
        for label, n_axes, scale in SIZES:
            S = make(n_axes, scale).space_size()
            if S > FULL_ATTEMPT_LIMIT:
                factor = S / Sb
                hours = msb / 1000 * factor / 3600
                gb = pkb / 1024 / 1024 * factor
                print(f"  {label:<9} S={S:>16,}  시간≈{hours:,.1f}시간  메모리≈{gb:,.0f}GB(근사)")

    out = ROOT / "results" / ("oom_stress_perfect.jsonl" if PERFECT else "oom_stress.jsonl")
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\n{len(rows)} rows → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
