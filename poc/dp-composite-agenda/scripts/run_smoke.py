"""P1 스모크 — TC × 전략 3종(full/pool/seq)을 돌려 관측값과 FC 점수를 표로 출력한다.

사용:  .venv/bin/python scripts/run_smoke.py [--all]
  기본은 S01만, --all이면 전 TC(기본 크기, S11은 n=4).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpca.common.oracle import analyze
from dpca.common.scenario import load_scenario
from dpca.harness.judge import Judge
from dpca.harness.runner import STRATEGIES, run_one


def main() -> int:
    run_all = "--all" in sys.argv
    paths = sorted((ROOT / "scenarios").glob("S*.yaml")) if run_all else [ROOT / "scenarios" / "S01-기준.yaml"]

    # 워밍업 — 첫 세션의 라이브러리 초기화 할당이 피크 측정에 섞이는 것을 방지
    warmup = load_scenario(ROOT / "scenarios" / "S01-기준.yaml")
    for strategy in STRATEGIES:
        run_one(warmup, strategy)

    header = f"{'TC':<5}{'전략':<6}{'결과':<5}{'달성률':>7}{'s':>7}{'별점':>5}{'라운드':>7}{'제안':>6}{'피크KiB':>9}{'ms':>7}  비고"
    print(header)
    print("-" * len(header))
    for path in paths:
        n_axes = 4 if "S11" in path.name else None
        scenario = load_scenario(path, n_axes=n_axes)
        report = analyze(scenario)
        judge = Judge(scenario, report)
        for strategy in STRATEGIES:
            result = run_one(scenario, strategy)
            score = judge.score(result.agreement)
            note = []
            if result.extra.get("deepening"):
                note.append(f"deepen={result.extra['deepening']}")
            if result.extra.get("backtracks"):
                note.append(f"backtrack={result.extra['backtracks']}")
            if score.fr_violations:
                note.append("FR위반: " + "; ".join(score.fr_violations))
            outcome = "결렬" if result.agreement is None else "합의"
            print(
                f"{scenario.id:<5}{strategy:<6}{outcome:<5}"
                f"{score.achieved_rate:>7.3f}{score.improvement_s:>7.2f}{score.stars:>5}"
                f"{result.rounds:>7}{result.proposals:>6}{result.peak_kib:>9.0f}{result.wall_ms:>7.0f}  {' '.join(note)}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
