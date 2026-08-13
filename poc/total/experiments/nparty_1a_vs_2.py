#!/usr/bin/env python3
"""실험 — 방안 1-A(순차 SAO 투표형) vs 방안 2(누적 공통제안형).

`docs/changbae/51-설계후보1-다자-합의-프로토콜.md` §3-1·§4의 두 방안을 통합 QA
측정기로 비교한다. composite 실험과는 **독립 실행**이다 — 공유하는 것은 측정기와
결과 형식뿐이고, 두 실험의 별점을 서로 비교하지 않는다.

**측정 범위는 FC·CF·TB** (PL 지시 2026-08-13 — `campaign.QA_NPARTY`). 다자 프로토콜
DP의 변별축은 품질·노출·시간이다. RU는 이 규모(kB 수준)에서 포화해 변별이 없고,
의제 조합(RU·조합 폭발)은 composite DP 소관이다 — SC-의제 스윕도 함께 제거했다.

    .venv/bin/python experiments/nparty_1a_vs_2.py [--cases N]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from total import pyversion  # noqa: E402
from total.adapters.nparty import PLANS, NpartyCase, run_session  # noqa: E402
from total.adapters.nparty._vendor.benchmark import JsonBenchmarkLoader  # noqa: E402
from total.adapters.nparty._vendor.domain import Profile  # noqa: E402
from total.adapters.nparty.baseline import baseline_t  # noqa: E402
from total.campaign import QA_NPARTY, PlanRuns, measure  # noqa: E402
from total.qa import cf  # noqa: E402
from total.qa.contract import Dataset  # noqa: E402
from total.qa.report import RunMeta, make_run_id, now_stamp, write_run  # noqa: E402

EXPERIMENT = "nparty-1a-vs-2"
E2_REFERENCE_PLAN = "plan2"      # 참조 양자 프로토콜 (dp2 관례와 동일)
E2_SAMPLES = 30


def _mkcase(bc) -> NpartyCase:
    return NpartyCase(bc.case_id,
                      [Profile(p.pid, dict(p.utilities), p.initial_threshold)
                       for p in bc.profiles])


def _functional(limit: int | None):
    cs = sorted(JsonBenchmarkLoader(track="functional").cases(), key=lambda c: c.case_id)
    return cs[:limit] if limit else cs


def e2_anchor(cases):
    """1:1 기준 노출량 — 참조 프로토콜을 각 케이스의 앞 2인으로 돌린다."""
    runs = []
    for bc in cases[:E2_SAMPLES]:
        pair = bc.profiles[:2]
        session, _ = run_session(pair, E2_REFERENCE_PLAN)
        runs.append((session, NpartyCase(
            bc.case_id,
            [Profile(p.pid, dict(p.utilities), p.initial_threshold) for p in pair])))
    return cf.e2_anchor(runs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=int, default=None, help="functional 케이스 상한")
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--allow-python-mismatch", action="store_true",
                    help="3.14 고정 검사 우회 (수치는 판정에 쓰지 말 것)")
    args = ap.parse_args()
    pyversion.require(args.allow_python_mismatch)

    functional = _functional(args.cases)
    print(f"functional {len(functional)}건 · 측정 범위 {list(QA_NPARTY)}")

    anchor = e2_anchor(functional)
    print(f"e₂ 앵커 (참조 {E2_REFERENCE_PLAN}, {anchor.samples}표본): "
          f"깊이={anchor.depth:.4f}")

    plans: list[PlanRuns] = []
    for name in ("plan1a", "plan2"):
        pr = PlanRuns(name, PLANS[name].label)
        for bc in functional:
            session, _ = run_session(bc.profiles, name)
            pr.add(session, _mkcase(bc))
        plans.append(pr)
        print(f"  {name}: 세션 {len(pr.runs)}")

    # TB 판정 ρ의 분모 — naive SAOP-RR baseline (24 §4.3, 결정론·케이스별 1회)
    tb_baselines = {bc.case_id: baseline_t(bc.profiles, bc.candidates)
                    for bc in functional}

    raw, rows = measure(plans, e2=anchor, tb_baselines=tb_baselines, qa=QA_NPARTY,
                        viewpoints=[cf.COORDINATOR_FIRST, cf.worst_participant()])

    n_cands = len(functional[0].candidates) if functional else 0
    dataset = Dataset(
        name="nparty benchmark",
        n_participants=min((len(c.profiles) for c in functional), default=3),
        n_issues=1,
        issue_value_counts=[max(1, n_cands)],
        seed=0,
        note=f"functional {len(functional)}건 (참여자 3·5·7, 단일 의제 후보 {n_cands}개)",
    )
    meta = RunMeta(
        run_id=make_run_id(EXPERIMENT, now_stamp()),
        experiment=EXPERIMENT,
        seed=dataset.seed,
        dataset=dataset.as_dict(),
        plans=["plan1a", "plan2"],
        note="방안 1-A vs 방안 2. 측정 범위 FC·CF·TB (campaign.QA_NPARTY — PL 지시 "
             "2026-08-13). 입력은 확정 벤치마크 셋(결정론) — 같은 입력이면 같은 결과.",
    )
    out = write_run(Path(args.results), meta, raw, rows)
    print(f"\n저장: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
