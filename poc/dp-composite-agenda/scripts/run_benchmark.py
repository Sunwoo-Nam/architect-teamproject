"""P2 본 측정 — FC 결정 실험 (29-1 A1).

각 TC × 시드(base..base+29) × 전략(full/seq/pool)을 동일 하니스로 1회씩 돌려
FC 달성률·별점·phase·message·peak를 results/fc_benchmark.jsonl에 기록한다.
같은 (TC, 시드)를 세 전략이 공유하므로 짝비교(analyze_fc.py)로 구조 차이만 분리할 수 있다.

사용:  .venv/bin/python scripts/run_benchmark.py [--seeds 30]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpca.common.oracle import analyze  # noqa: E402
from dpca.common.scenario import load_scenario  # noqa: E402
from dpca.harness.judge import Judge  # noqa: E402
from dpca.harness.runner import STRATEGIES, run_one  # noqa: E402


def main() -> int:
    n_seeds = int(sys.argv[sys.argv.index("--seeds") + 1]) if "--seeds" in sys.argv else 30
    perfect = "--perfect" in sys.argv
    print(f"[정보 전제: {'완벽(뷰=진실)' if perfect else '부분(뷰 노이즈 有)'}]")
    paths = sorted((ROOT / "scenarios").glob("S*.yaml"))
    out_path = ROOT / "results" / ("fc_benchmark_perfect.jsonl" if perfect else "fc_benchmark.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 워밍업 (측정 오염 방지)
    warm = load_scenario(ROOT / "scenarios" / "S01-기준.yaml")
    for st in STRATEGIES:
        run_one(warm, st)

    rows: list[dict] = []
    t0 = time.perf_counter()
    for path in paths:
        n_axes = 4 if "S11" in path.name else None
        base = load_scenario(path, n_axes=n_axes)
        base_seed = base.profile_seed
        for s in range(n_seeds):
            seed = base_seed + s
            scenario = load_scenario(path, n_axes=n_axes)
            scenario.participants["profile_seed"] = seed
            if perfect:
                scenario.agent_view = {"score_dropout": 0.0}  # 뷰=진실
            report = analyze(scenario)          # 이 (TC,시드)의 x*·U(x*)·R̄
            judge = Judge(scenario, report)
            for strategy in STRATEGIES:
                r = run_one(scenario, strategy)
                score = judge.score(r.agreement)
                rows.append({
                    "tc": scenario.id, "seed": seed, "strategy": strategy,
                    "space": scenario.space_size(),
                    "expected": scenario.meta["expected"],
                    "xstar_breakdown": report.xstar_is_breakdown,
                    "result": "breakdown" if r.agreement is None else "agreement",
                    "achieved": round(score.achieved_rate, 4),
                    "s": round(score.improvement_s, 4),
                    "stars": score.stars,
                    "fr_violations": score.fr_violations,
                    "phases": r.phases, "messages": r.messages,
                    "peak_kib": round(r.peak_kib, 1),
                    "deepening": r.extra.get("deepening"),
                    "backtracks": r.extra.get("backtracks"),
                })
        print(f"  {base.id}: {n_seeds} seeds done ({time.perf_counter() - t0:.0f}s 누적)")

    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\n{len(rows)} rows → {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
