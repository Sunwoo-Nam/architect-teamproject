#!/usr/bin/env python3
"""실험 — 1안(의제별 순차) vs 2안(개인별 후보군 압축 후 복합).

`docs/07-DP후보안/sunwoo/DP-복합의제-협상방식.md`의 두 안을 통합 QA 측정기로 비교한다.
nparty 실험과는 **독립 실행**이다 — 두 실험의 별점을 서로 비교하지 않는다.

기본 비교 대상은 최종 문서와 같이 **1안 = seq2 · 2안 = pool**이고, 정본 seq와
개선 시도 pool2는 `--plans`로 함께 볼 수 있다.

    .venv/bin/python experiments/composite_1_vs_2.py [--plans seq2,pool] [--sweep-axes 4,6,8]
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from total.adapters.composite import (  # noqa: E402
    E2_REFERENCE_PLAN,
    PLANS,
    CompositeCase,
    load,
    run_session,
    scenario_paths,
)
from total.adapters.composite._vendor.common.scenario import load_scenario  # noqa: E402
from total.campaign import PlanRuns, measure  # noqa: E402
from total.qa import cf  # noqa: E402
from total.qa.contract import SweepPoint  # noqa: E402
from total.qa.report import RunMeta, make_run_id, now_stamp, write_run  # noqa: E402

EXPERIMENT = "composite-1-vs-2"
DEFAULT_PLANS = ("seq2", "pool")
SWEEP_SCENARIO = "S11"           # 축 수 스윕 전용 TC
E2_SAMPLES = 8


def _viewpoints():
    """dpca는 2인 교대 제안이라 담당자가 곧 상대다 — 관점 1개만 낸다."""
    return [cf.worst_participant()]


def e2_anchor(scenarios, cases):
    """1:1 기준 노출량 — 전체 조합을 그대로 교환하는 참조 프로토콜(full)로 잰다."""
    runs = []
    for sc, case in list(zip(scenarios, cases))[:E2_SAMPLES]:
        session, c = run_session(sc, E2_REFERENCE_PLAN, case=case)
        runs.append((session, c))
    return cf.e2_anchor(runs)


def _sweep_points(plan: str, axes_levels: list[int]) -> list[SweepPoint]:
    """축 수를 키우며 규모별 피크를 잰다 — 탄력성 c와 최대 의제 수의 입력."""
    path = next(p for p in scenario_paths() if p.stem.startswith(SWEEP_SCENARIO))
    out: list[SweepPoint] = []
    for n_axes in axes_levels:
        sc = load_scenario(path, n_axes=n_axes)
        case = CompositeCase(f"{sc.id}-{n_axes}axes", sc, enumeration_limit=10 ** 9)
        try:
            session, _ = run_session(sc, plan, case=case)
        except Exception as exc:               # 규모가 커 실패하면 그 자체가 관측이다
            print(f"    {plan} {n_axes}축: 실행 실패 ({type(exc).__name__}) — 건너뜀")
            continue
        out.append(SweepPoint(
            scale=max(1, sc.space_size()),
            peak_bytes=session.peak_bytes,
            base_bytes=0,      # 스윕은 프로토콜 피크만 본다 — 기저는 전 방안 공통
            agreed=session.agreed,
            n_issues=n_axes,
        ))
        print(f"    {plan} {n_axes}축: 조합 {sc.space_size():,} · "
              f"피크 {session.peak_bytes / 1024 / 1024:.2f}MB · 합의 {session.agreed}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plans", default=",".join(DEFAULT_PLANS))
    ap.add_argument("--sweep-axes", default="4,6,8,10,12,14,16")
    ap.add_argument("--scenarios", type=int, default=None, help="시나리오 상한")
    ap.add_argument("--results", default=str(ROOT / "results"))
    args = ap.parse_args()

    plan_names = [p.strip() for p in args.plans.split(",") if p.strip()]
    axes_levels = [int(x) for x in args.sweep_axes.split(",") if x.strip()]

    paths = scenario_paths()[: args.scenarios] if args.scenarios else scenario_paths()
    scenarios, cases = [], []
    for p in paths:
        sc = load(p)
        if sc.space_size() > 200_000:          # FC는 전수 열거가 필요하다
            print(f"  {p.stem}: 조합 {sc.space_size():,} — FC 열거 한도 초과, 건너뜀")
            continue
        scenarios.append(sc)
        cases.append(CompositeCase(sc.id, sc))
    print(f"시나리오 {len(scenarios)}건 · 방안 {plan_names}")

    anchor = e2_anchor(scenarios, cases)
    print(f"e₂ 앵커 (참조 {E2_REFERENCE_PLAN}, {anchor.samples}표본): "
          f"A={anchor.depth_a:.4f} B={anchor.depth_b:.4f}")

    plans: list[PlanRuns] = []
    for name in plan_names:
        pr = PlanRuns(name, PLANS[name].label)
        for sc, case in zip(scenarios, cases):
            session, c = run_session(sc, name, case=case)
            pr.add(session, c, c.hard_violations(session.agreement))
        print(f"  {name}: 세션 {len(pr.runs)}")
        pr.sweep = _sweep_points(name, axes_levels)
        plans.append(pr)

    issue_counts = sorted(p.n_issues for pr in plans for p in pr.sweep)
    d = statistics.median_low(issue_counts) if issue_counts else 4

    raw, rows = measure(plans, e2=anchor, d=d, viewpoints=_viewpoints())

    meta = RunMeta(
        run_id=make_run_id(EXPERIMENT, now_stamp()),
        experiment=EXPERIMENT,
        seed=scenarios[0].profile_seed if scenarios else 0,
        dataset={"name": "composite scenarios", "n_participants": 2,
                 "n_issues": d, "scenarios": len(scenarios),
                 "sweep_axes": axes_levels},
        plans=plan_names,
        note="1안(seq2) vs 2안(pool). 2인 교대 제안이라 CF 관점은 1개다. "
             "1안은 축값을, 2안은 전체 조합을 교환하므로 조합 공간 기준 노출 깊이는 "
             "granularity가 다르다 — adapters/composite 모듈 docstring의 한계 설명 참조.",
    )
    out = write_run(Path(args.results), meta, raw, rows)
    print(f"\n저장: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
