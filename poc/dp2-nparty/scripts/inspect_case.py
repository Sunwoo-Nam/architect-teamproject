"""Conformance fixture 설계용 검사 도구 — 케이스 JSON을 두 방안으로 돌려 동작을 보여준다.

사용:
    .venv/bin/python scripts/inspect_case.py data/benchmark/fixtures/conformance/C-001-common-top.json
    .venv/bin/python scripts/inspect_case.py <경로> --robust    # tactic 9조합 견고성까지

이 스크립트는 fixture를 설계할 때 "의도한 코드 경로가 실제로 밟히는가"를 확인하기 위한 것이다.
평가 통계와는 무관하다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dp2_nparty.benchmark import load_case
from dp2_nparty.domain import NO_DEAL
from dp2_nparty.measures import fc
from dp2_nparty.protocol import Plan1Vote, Plan2Cumulative
from dp2_nparty.threshold import SweepThreshold

PLANS = (Plan1Vote, Plan2Cumulative)


def show(path: Path, robust: bool = False) -> None:
    case = load_case(path)
    profs, cands = case.profiles, case.candidates

    print(f"# {case.case_id}   ({case.meta.get('scenario_type')})")
    print(f"  후보: {cands}")
    for p in profs:
        ranked = p.ranked()
        order = " > ".join(f"{c}({p.utility(c):.2f})" for c in ranked)
        print(f"  {p.pid}  th={p.initial_threshold:.2f}  순위: {order}")

    feasible = case.feasible()
    star = fc.score(NO_DEAL, cands, profs)
    print(f"  실후보(전원 바닥선 이상): {feasible}   x* = {star.optimal}")

    print("  바퀴별 revised threshold (boulware, 5바퀴):")
    for p in profs:
        th = SweepThreshold(p.initial_threshold, 5, "boulware", max_utility=p.utility(p.ranked()[0]))
        print(f"    {p.pid}: " + " ".join(f"{th.at_sweep(s):.3f}" for s in range(1, 6)))

    print("  실행:")
    for cls in PLANS:
        r = cls(profs).run()
        s = fc.score(r.outcome, cands, profs)
        print(
            f"    {cls.plan_name}: 결과={r.outcome!s:10s} 바퀴={r.sweeps} 라운드={r.rounds:3d} "
            f"메시지={r.messages:4d} phase={r.phases:3d} 동률해소={r.tie_break_used} "
            f"달성률={s.ratio:.3f}"
        )

    if robust:
        print("  tactic 견고성 (결과가 전부 같아야 fixture로 쓸 수 있다):")
        for asp in ("boulware", "linear", "conceder"):
            row = []
            for ms in (3, 5, 8):
                outs = [cls(profs, max_sweeps=ms, aspiration_type=asp).run().outcome for cls in PLANS]
                row.append(f"{ms}바퀴:{outs[0]}/{outs[1]}")
            print(f"    {asp:9s} " + "  ".join(map(str, row)))


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    robust = "--robust" in sys.argv
    if not args:
        raise SystemExit(__doc__)
    for a in args:
        show(Path(a), robust)
        print()


if __name__ == "__main__":
    main()
