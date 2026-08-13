#!/usr/bin/env python3
"""실험 — 방안 1-A(순차 SAO 투표형) vs 방안 2(누적 공통제안형).

`docs/changbae/51-설계후보1-다자-합의-프로토콜.md` §3-1·§4의 두 방안을 통합 QA
측정기로 비교한다. composite 실험과는 **독립 실행**이다 — 공유하는 것은 측정기와
결과 형식뿐이고, 두 실험의 별점을 서로 비교하지 않는다.

    .venv/bin/python experiments/nparty_1a_vs_2.py [--cases N] [--sweep-cases N]
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from total import pyversion  # noqa: E402
from total.adapters.nparty import PLANS, NpartyCase, run_session  # noqa: E402
from total.adapters.nparty._vendor import issue_space  # noqa: E402
from total.adapters.nparty._vendor.benchmark import (  # noqa: E402
    CASES_DIR,
    JsonBenchmarkLoader,
)
from total.adapters.nparty._vendor.domain import Profile  # noqa: E402
from total.campaign import PlanRuns, measure  # noqa: E402
from total.qa import cf  # noqa: E402
from total.qa.contract import Dataset, SweepPoint  # noqa: E402
from total.qa.report import RunMeta, make_run_id, now_stamp, write_run  # noqa: E402

EXPERIMENT = "nparty-1a-vs-2"
E2_REFERENCE_PLAN = "plan2"      # 참조 양자 프로토콜 (dp2 관례와 동일)
E2_SAMPLES = 30


def _fit_counts(counts: list[int], d: int) -> list[int]:
    """Dataset은 의제 수와 값 개수 목록의 길이가 같아야 한다 — 기준 구성에 맞춰 자른다."""
    counts = [c for c in counts if c > 0][:d]
    return counts + [2] * (d - len(counts))


def _mkcase(bc) -> NpartyCase:
    return NpartyCase(bc.case_id,
                      [Profile(p.pid, dict(p.utilities), p.initial_threshold)
                       for p in bc.profiles])


def _functional(limit: int | None):
    cs = sorted(JsonBenchmarkLoader(track="functional").cases(), key=lambda c: c.case_id)
    return cs[:limit] if limit else cs


def _issue_space_cases(limit: int | None):
    """SC-의제 스윕 소스 — 조합 수가 다른 케이스들."""
    out = []
    for track_dir in ("issue-space", "issue-space-b"):
        root = CASES_DIR / track_dir
        if not root.exists():
            continue
        for path in sorted(root.glob("*.json")):
            try:
                out.append(issue_space.load_issue_case(path))
            except Exception:
                continue
    return out[:limit] if limit else out


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
    ap.add_argument("--sweep-cases", type=int, default=None, help="의제 조합 케이스 상한")
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--allow-python-mismatch", action="store_true",
                    help="3.14 고정 검사 우회 (수치는 판정에 쓰지 말 것)")
    args = ap.parse_args()
    pyversion.require(args.allow_python_mismatch)

    functional = _functional(args.cases)
    sweep_cases = _issue_space_cases(args.sweep_cases)
    print(f"functional {len(functional)}건 · 의제 조합 {len(sweep_cases)}건")

    anchor = e2_anchor(functional)
    print(f"e₂ 앵커 (참조 {E2_REFERENCE_PLAN}, {anchor.samples}표본): "
          f"깊이={anchor.depth:.4f}")

    plans: list[PlanRuns] = []
    for name in ("plan1a", "plan2"):
        pr = PlanRuns(name, PLANS[name].label)
        for bc in functional:
            session, _ = run_session(bc.profiles, name)
            pr.add(session, _mkcase(bc))
        for isc in sweep_cases:
            expanded = issue_space.expand(isc)
            session, _ = run_session(expanded.profiles, name)
            pr.sweep.append(SweepPoint(
                scale=max(1, len(expanded.profiles[0].utilities)),
                peak_bytes=session.peak_bytes,
                base_bytes=session.base_bytes,
                agreed=session.agreed,
                n_issues=len(isc.issues),
            ))
        plans.append(pr)
        print(f"  {name}: 세션 {len(pr.runs)} · 스윕 {len(pr.sweep)}")

    # 24 §5.3의 d — 탄력성 별점의 하계 1/d. 스윕이 의제 수 3·6·10을 섞으므로
    # 기준 시나리오를 중앙값으로 잡고, 실제 쓴 값을 결과에 기록한다 (raw.sc_issue.d).
    issue_counts = sorted(p.n_issues for pr in plans for p in pr.sweep)
    d = statistics.median_low(issue_counts) if issue_counts else 4
    raw, rows = measure(plans, e2=anchor, d=d,
                        viewpoints=[cf.COORDINATOR_FIRST, cf.worst_participant()])

    base = sweep_cases[len(sweep_cases) // 2] if sweep_cases else None
    dataset = Dataset(
        name="nparty benchmark",
        n_participants=min((len(c.profiles) for c in functional), default=3),
        n_issues=d,
        issue_value_counts=_fit_counts(
            list(base.meta.get("issue_sizes", [])) if base else [], d),
        seed=0,
        note=f"기준 구성에서 스윕: 참여자 3·5·7 (functional {len(functional)}건) · "
             f"의제 조합 {len(sweep_cases)}건 (의제 수 3·6·10)",
    )
    meta = RunMeta(
        run_id=make_run_id(EXPERIMENT, now_stamp()),
        experiment=EXPERIMENT,
        seed=dataset.seed,
        dataset=dataset.as_dict(),
        plans=["plan1a", "plan2"],
        note="방안 1-A vs 방안 2. 입력은 확정 벤치마크 셋(결정론) — 같은 입력이면 같은 결과.",
    )
    out = write_run(Path(args.results), meta, raw, rows)
    print(f"\n저장: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
