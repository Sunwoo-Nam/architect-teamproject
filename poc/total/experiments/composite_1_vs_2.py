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

from total import pyversion  # noqa: E402
from total.adapters.composite import (  # noqa: E402
    E2_REFERENCE_PLAN,
    PLANS,
    CompositeCase,
    load,
    run_session,
    run_sweep_point,
    scenario_paths,
)
from total.adapters.composite._vendor.common.scenario import load_scenario  # noqa: E402
from total.campaign import PlanRuns, measure  # noqa: E402
from total.qa import cf  # noqa: E402
from total.qa.contract import Dataset, SweepPoint  # noqa: E402,F401
from total.qa.report import RunMeta, make_run_id, now_stamp, write_run  # noqa: E402

EXPERIMENT = "composite-1-vs-2"
DEFAULT_PLANS = ("seq2", "pool")
SWEEP_SCENARIO = "S11"           # 축 수 스윕 전용 TC
E2_SAMPLES = 8


def _fit_counts(counts: list[int], d: int) -> list[int]:
    """Dataset은 의제 수와 값 개수 목록의 길이가 같아야 한다 — 기준 구성에 맞춰 자른다."""
    counts = [c for c in counts if c > 0][:d]
    return counts + [2] * (d - len(counts))


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
    available = len(load_scenario(path).axes)
    usable = [n for n in axes_levels if n <= available]
    dropped = [n for n in axes_levels if n > available]
    if dropped:
        # 시나리오에 정의된 축보다 많이 요구하면 load_scenario가 조용히 전체를 준다 —
        # 그러면 12·14·16축이 전부 같은 10축 실행이 되어 스윕이 거짓이 된다.
        print(f"    [주의] {SWEEP_SCENARIO}의 축은 {available}개뿐 — "
              f"{dropped} 수준은 제외한다 (조용히 중복 실행되는 것을 막는다)")
    out: list[SweepPoint] = []
    for n_axes in usable:
        sc = load_scenario(path, n_axes=n_axes)
        try:
            point = run_sweep_point(sc, plan, n_axes)
        except Exception as exc:               # 규모가 커 실패하면 그 자체가 관측이다
            print(f"    {plan} {n_axes}축: 실행 실패 ({type(exc).__name__}) — 건너뜀")
            continue
        out.append(point)
        print(f"    {plan} {n_axes}축: 조합 {sc.space_size():,} · "
              f"피크 {point.peak_bytes / 1024 / 1024:.2f}MB · 합의 {point.agreed}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plans", default=",".join(DEFAULT_PLANS))
    ap.add_argument("--sweep-axes", default="4,6,8,10,12,14,16")
    ap.add_argument("--scenarios", type=int, default=None, help="시나리오 상한")
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--allow-python-mismatch", action="store_true",
                    help="3.14 고정 검사 우회 (수치는 판정에 쓰지 말 것)")
    args = ap.parse_args()
    pyversion.require(args.allow_python_mismatch)

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
          f"깊이={anchor.depth:.4f}")

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

    base = scenarios[0]
    dataset = Dataset(
        name="composite scenarios",
        n_participants=base.n_participants,
        n_issues=d,
        issue_value_counts=_fit_counts([len(a.values) for a in base.axes], d),
        seed=base.profile_seed,
        note=f"기준 구성 {base.id}에서 스윕: 시나리오 {len(scenarios)}건 · "
             f"축 수 {axes_levels}",
    )
    meta = RunMeta(
        run_id=make_run_id(EXPERIMENT, now_stamp()),
        experiment=EXPERIMENT,
        seed=dataset.seed,
        dataset=dataset.as_dict(),
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
