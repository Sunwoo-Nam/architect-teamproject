"""최종 QA 측정 — 정의된 시나리오(S01~S12)에서 1안(seq2) vs 2안(pool)의 FC·REC.

완벽 정보. FC = U(합의)/U(x*) (정확한 x*, exact_xstar; 바닥선 비조임 시드만).
REC = 복구 시간 비율(29-1 A5-2). seq2는 축별 커밋 경계, pool은 단일 세션.
raw는 results/final_fc_rec.jsonl.

사용:  .venv/bin/python scripts/run_final_fc_rec.py [--seeds 12]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpca.common.exact import exact_xstar  # noqa: E402
from dpca.common.profiles import build_truth_profiles, truth_utility  # noqa: E402
from dpca.common.rules import build_soft_rules  # noqa: E402
from dpca.common.scenario import load_scenario  # noqa: E402
from dpca.harness.recovery import analyze_recovery  # noqa: E402
from dpca.harness.runner import run_one  # noqa: E402

STRATS = [("1안-정본", "seq"), ("1안-개선", "seq2"),
          ("2안-정본", "pool"), ("2안-개선", "pool2")]


def true_total(sc, agreement) -> float:
    ts = build_truth_profiles(sc)
    soft = build_soft_rules(sc, [t.home_region for t in ts])
    out = {ax.name: next(v for v in ax.values if v.name == agreement[ax.name]) for ax in sc.axes}
    return sum(truth_utility(ts[p], p, out, soft) for p in range(len(ts)))


def main() -> int:
    n_seeds = int(sys.argv[sys.argv.index("--seeds") + 1]) if "--seeds" in sys.argv else 12
    paths = sorted((ROOT / "scenarios").glob("S*.yaml"))
    rows = []
    agg = {label: {"fc": [], "rec": [], "rec_star": [], "ag": 0, "n": 0} for label, _ in STRATS}

    for path in paths:
        base = load_scenario(path)
        # S11/S12는 축을 잘라 exact 검증 범위로 (S11=4축 스윕 TC, S12는 6축 그대로)
        n_axes = 4 if "S11" in path.name else None
        base_seed = base.profile_seed
        for s in range(n_seeds):
            sc = load_scenario(path, n_axes=n_axes)
            sc.participants["profile_seed"] = base_seed + s
            sc.agent_view = {"score_dropout": 0.0}   # 완벽 정보
            xs = exact_xstar(sc)
            if not xs["unconstrained_valid"]:
                continue                             # x* 부정확(바닥선 조임) → 제외
            uxs = xs["u_xstar"]
            for label, st in STRATS:
                r = run_one(sc, st)
                agg[label]["n"] += 1
                fc = None
                if r.agreement:
                    agg[label]["ag"] += 1
                    fc = true_total(sc, r.agreement) / uxs
                    agg[label]["fc"].append(fc)
                    # REC — seq2는 축별 커밋(axis_rounds), pool은 단일 세션
                    rec_strategy = "seq" if st == "seq2" else st
                    rec = analyze_recovery(rec_strategy, r.rounds, r.extra.get("axis_rounds"))
                    agg[label]["rec"].append(rec.ratio)
                    agg[label]["rec_star"].append(rec.stars)
                rows.append({"tc": sc.id, "seed": base_seed + s, "label": label, "strategy": st,
                             "u_xstar": round(uxs, 4),
                             "fc": round(fc, 4) if fc is not None else None,
                             "agreed": r.agreement is not None,
                             "rec_ratio": rec.ratio if r.agreement else None,
                             "rec_star": rec.stars if r.agreement else None})

    out = ROOT / "results" / "final_fc_rec.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("=== 정의 시나리오(S01~S12) FC·REC — 완벽 정보 ===")
    print(f"{'전략':<16}{'FC 달성률µ':>11}{'합의율':>8}{'REC 비율 중앙':>13}{'REC 별점 중앙':>13}")
    for label, st in STRATS:
        a = agg[label]
        print(f"{label}({st})".ljust(16)
              + f"{mean(a['fc']) if a['fc'] else 0:>11.1%}"
              + f"{a['ag']/a['n'] if a['n'] else 0:>8.0%}"
              + f"{median(a['rec']) if a['rec'] else 0:>13.2f}"
              + f"{median(a['rec_star']) if a['rec_star'] else 0:>13.0f}")
    print(f"\n{len(rows)} rows → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
