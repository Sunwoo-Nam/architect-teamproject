#!/usr/bin/env python3
"""실험 — 1안(의제별 순차) vs 2안(개인별 후보군 압축 후 복합).

`docs/07-DP후보안/sunwoo/DP-복합의제-협상방식.md`의 두 안을 통합 QA 측정기로 비교한다.
nparty 실험과는 **독립 실행**이다 — 두 실험의 별점을 서로 비교하지 않는다.

**측정 범위는 FC·RU·TB** (PL 지시 2026-08-13 — `campaign.QA_COMPOSITE`). 복합 의제
DP의 본질은 조합 폭발이라 RU가 핵심 변별축이다. CF는 잔여 비밀률의 분모(전체 후보)가
조합적으로 거대해 어느 방안이든 ★5로 퇴화하므로 측정하지 않는다 — CF는 nparty 담당
(`qa/cf.py` 참조). SC-의제 스윕도 범위 밖으로 제거했다 (조합 규모 영향은 RU가 잰다).

기본 비교 대상은 최종 문서와 같이 **1안 = seq2 · 2안 = pool**이고, 정본 seq와
개선 시도 pool2는 `--plans`로 함께 볼 수 있다.

    .venv/bin/python experiments/composite_1_vs_2.py [--plans seq2,pool]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from total import pyversion  # noqa: E402
from total.adapters.composite import (  # noqa: E402
    PLANS,
    CompositeCase,
    load,
    run_session,
    scenario_paths,
)
from total.adapters.composite.baseline import baseline_t  # noqa: E402
from total.campaign import QA_COMPOSITE, PlanRuns, measure  # noqa: E402
from total.qa.contract import Dataset  # noqa: E402
from total.qa.report import RunMeta, make_run_id, now_stamp, write_run  # noqa: E402

EXPERIMENT = "composite-1-vs-2"
DEFAULT_PLANS = ("seq2", "pool")


def _fit_counts(counts: list[int], d: int) -> list[int]:
    """Dataset은 의제 수와 값 개수 목록의 길이가 같아야 한다 — 기준 구성에 맞춰 자른다."""
    counts = [c for c in counts if c > 0][:d]
    return counts + [2] * (d - len(counts))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plans", default=",".join(DEFAULT_PLANS))
    ap.add_argument("--scenarios", type=int, default=None, help="시나리오 상한")
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--allow-python-mismatch", action="store_true",
                    help="3.14 고정 검사 우회 (수치는 판정에 쓰지 말 것)")
    args = ap.parse_args()
    pyversion.require(args.allow_python_mismatch)

    plan_names = [p.strip() for p in args.plans.split(",") if p.strip()]

    paths = scenario_paths()[: args.scenarios] if args.scenarios else scenario_paths()
    scenarios, cases = [], []
    for p in paths:
        sc = load(p)
        if sc.space_size() > 200_000:          # FC는 전수 열거가 필요하다
            print(f"  {p.stem}: 조합 {sc.space_size():,} — FC 열거 한도 초과, 건너뜀")
            continue
        scenarios.append(sc)
        cases.append(CompositeCase(sc.id, sc))
    print(f"시나리오 {len(scenarios)}건 · 방안 {plan_names} · "
          f"측정 범위 {list(QA_COMPOSITE)}")

    tb_baselines = {}
    for sc in scenarios:
        b = baseline_t(sc)
        tb_baselines[sc.id] = b
        print(f"  TB baseline {sc.id}: k*={b['proposals_k*']} T={b['T_ms']/1000:.1f}s"
              + (" (하한)" if b["capped"] else ""))

    plans: list[PlanRuns] = []
    for name in plan_names:
        pr = PlanRuns(name, PLANS[name].label)
        for sc, case in zip(scenarios, cases):
            session, c = run_session(sc, name, case=case)
            pr.add(session, c, c.hard_violations(session.agreement))
        print(f"  {name}: 세션 {len(pr.runs)}")
        plans.append(pr)

    raw, rows = measure(plans, tb_baselines=tb_baselines, qa=QA_COMPOSITE)

    base = scenarios[0]
    d = len(base.axes)
    dataset = Dataset(
        name="composite scenarios",
        n_participants=base.n_participants,
        n_issues=d,
        issue_value_counts=_fit_counts([len(a.values) for a in base.axes], d),
        seed=base.profile_seed,
        note=f"기준 구성 {base.id} · 시나리오 {len(scenarios)}건",
    )
    meta = RunMeta(
        run_id=make_run_id(EXPERIMENT, now_stamp()),
        experiment=EXPERIMENT,
        seed=dataset.seed,
        dataset=dataset.as_dict(),
        plans=plan_names,
        note="1안(seq2) vs 2안(pool). 측정 범위 FC·RU·TB (campaign.QA_COMPOSITE — "
             "PL 지시 2026-08-13). CF는 잔여 비밀률 분모(전체 후보)가 조합적으로 "
             "거대해 퇴화하므로 nparty 담당.",
    )
    out = write_run(Path(args.results), meta, raw, rows)
    print(f"\n저장: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
