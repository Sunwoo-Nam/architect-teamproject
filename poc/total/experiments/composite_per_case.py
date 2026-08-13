#!/usr/bin/env python3
"""실험 — composite 벤치마크 **개별 케이스**의 QA 수치 (S01~S12 · fixtures).

`composite_1_vs_2.py`가 시나리오 전체를 하나로 집계하는 것과 달리, 여기서는
**시나리오/fixture 1건마다 별도 실행 폴더**를 만들어 그 케이스의 QA 수치를 낸다 —
"어느 시나리오에서 두 방안이 갈리는가"를 케이스 단위로 볼 수 있다.

- 대상: `datasets/composite/scenarios/*.yaml` 12종 + `datasets/composite/fixtures/*.json`
- 산출: `results/composite-per-case/composite-per-case-<ID>-<stamp>/` (meta·raw·cases·report)
  + 대상 전체 요약표 `results/composite-per-case/SUMMARY-<stamp>.md`
- e₂ 앵커는 **케이스별**로 잰다 — 같은 케이스의 full(전수 교환) 실행이 참조 2인 협상이다.
- 조합 수가 열거 한도를 넘는 대상(S11 977만 등)은 **표본으로 대체하지 않고 제외**하며
  (24 정본 FC는 전수 열거 전제), 제외 사실과 사유를 요약표에 남긴다.

    .venv/bin/python experiments/composite_per_case.py [--plans seq2,pool]
        [--targets S01,S03,fix-hi-04] [--enumeration-limit 300000]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from total import pyversion  # noqa: E402
from total.adapters.composite import (  # noqa: E402
    DATASETS,
    E2_REFERENCE_PLAN,
    PLANS,
    CompositeCase,
    load,
    run_session,
    scenario_paths,
)
from total.adapters.composite._vendor.common.generators import Value  # noqa: E402
from total.adapters.composite._vendor.common.scenario import Axis, Scenario  # noqa: E402
from total.adapters.composite.baseline import baseline_t  # noqa: E402
from total.campaign import PlanRuns, measure  # noqa: E402
from total.qa import cf  # noqa: E402
from total.qa.contract import Dataset  # noqa: E402
from total.qa.report import RunMeta, now_stamp, write_run  # noqa: E402

EXPERIMENT = "composite-per-case"
DEFAULT_PLANS = ("seq2", "pool")
FIXTURES = DATASETS / "fixtures"


def load_fixture(path: Path) -> Scenario:
    """fixture JSON → `Scenario`.

    시나리오 yaml은 축을 (generator, count)로 정의하지만 fixture는 **값이 실체화**되어
    있다 (`make_fixtures.py`가 생성). 값을 그대로 복원하므로 생성기를 다시 돌리지 않고,
    fixture가 만들어질 때의 공간이 정확히 재현된다.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    axes = [
        Axis(a["name"], a.get("generator", ""),
             [Value(v["name"], dict(v.get("attrs", {}))) for v in a["values"]])
        for a in raw["axes"]
    ]
    return Scenario(
        meta=raw["meta"],
        axes=axes,
        dependencies=raw.get("dependencies", []),
        participants=raw["participants"],
        agent_view=raw.get("agent_view", {}),
        judge=raw.get("judge", {"expected": raw["meta"].get("expected", "agreement")}),
    )


def targets_all() -> list[tuple[str, Scenario]]:
    """(표시 이름, 시나리오) 목록 — 시나리오 12종 + fixture 전부."""
    paths = [(p.stem.split("-")[0], p) for p in scenario_paths()]
    paths += [(p.stem, p) for p in sorted(FIXTURES.glob("*.json"))]
    return [(name, load_fixture(p) if p.suffix == ".json" else load(p))
            for name, p in paths]


def run_one(name: str, sc: Scenario, plan_names: list[str], limit: int,
            results_root: Path, stamp: str) -> dict:
    """케이스 1건: e₂ 앵커(full) + 방안별 실행 → 실행 폴더 1개. 요약 행을 돌려준다."""
    case = CompositeCase(sc.id, sc, enumeration_limit=limit)
    tb_baselines = {sc.id: baseline_t(sc)}

    anchor_session, _ = run_session(sc, E2_REFERENCE_PLAN, case=case)
    anchor = cf.e2_anchor([(anchor_session, case)])

    plans: list[PlanRuns] = []
    for pname in plan_names:
        pr = PlanRuns(pname, PLANS[pname].label)
        session, _ = run_session(sc, pname, case=case)
        pr.add(session, case, case.hard_violations(session.agreement))
        plans.append(pr)

    cf_note = ""
    try:
        raw, rows = measure(plans, e2=anchor, d=len(sc.axes),
                            viewpoints=[cf.worst_participant()],
                            tb_baselines=tb_baselines)
    except ValueError as err:
        if "합의 완료 세션" not in str(err):
            raise
        # 합의율 0 표본(S08처럼 결렬이 정답) — 24 §3 규정: CF는 "판정 불가"로 보고.
        # 결렬 노출은 모수에서 빠지므로 CF만 비우고 나머지 QA는 그대로 측정한다.
        raw, rows = measure(plans, e2=None, d=len(sc.axes),
                            viewpoints=[cf.worst_participant()],
                            tb_baselines=tb_baselines)
        cf_note = "합의 완료 세션 0건 — CF 판정 불가 (결렬 노출은 모수 제외, 24 §3)"

    dataset = Dataset(
        name=f"composite {name}",
        n_participants=sc.n_participants,
        n_issues=len(sc.axes),
        issue_value_counts=[len(ax.values) for ax in sc.axes],
        seed=sc.profile_seed,
        note=f"{sc.meta.get('name', '')} — 조합 {sc.space_size():,} · "
             f"{sc.meta.get('conflict_level', '?')}/{sc.meta.get('expected', '?')}",
    )
    meta = RunMeta(
        run_id=f"{EXPERIMENT}-{name}-{stamp}",
        experiment=EXPERIMENT,
        seed=dataset.seed,
        dataset=dataset.as_dict(),
        plans=plan_names,
        note=f"개별 케이스 측정 ({name}). e₂ 앵커는 이 케이스의 "
             f"{E2_REFERENCE_PLAN}(전수 교환) 실행 1건 — 케이스별 참조라 표본 1개다. "
             "SC-의제 스윕은 케이스 단위에서 정의되지 않아 비운다."
             + (f" [{cf_note}]" if cf_note else ""),
    )
    out = write_run(results_root, meta, raw, rows)
    print(f"  {name}: 저장 {out.name}")

    row = {"name": name, "space": sc.space_size(),
           "label": sc.meta.get("conflict_level", "?"),
           "expected": sc.meta.get("expected", "?"), "cf_note": cf_note}
    for p in plan_names:
        fc_, cf_, tb_, ru_ = (raw.get(k, {}).get(p, {}) for k in ("fc", "cf", "tb", "ru"))
        row[p] = {
            "achieved": fc_.get("mean_achieved"), "stars_achieved": fc_.get("stars_achieved"),
            "s": fc_.get("mean_s"), "fr": fc_.get("fr_violation_cases"),
            "secret": cf_.get("secret"), "stars_secret": cf_.get("stars_secret"),
            "m": cf_.get("m"), "stars_m": cf_.get("stars_m"),
            "rho": tb_.get("median_rho"), "stars_rho": tb_.get("stars"),
            "total_mb": ru_.get("median_total_mb"),
        }
    return row


def summary_md(rows: list[dict], skipped: list[tuple[str, str]],
               plan_names: list[str], stamp: str, limit: int) -> str:
    L = [f"# composite 개별 케이스 요약 — {stamp}", "",
         f"방안 {list(plan_names)} · 열거 한도 {limit:,} · 각 케이스의 상세는 "
         f"`composite-per-case-<ID>-{stamp}/report.md`", ""]
    for p in plan_names:
        L += [f"## {p}", "",
              "| 케이스 | 조합 | 성격 | 달성률 | 달성★ | s(보조) | FR위반 "
              "| 잔여비밀률 | 비밀★ | m(보조) | ρ | ρ★ | 총점유MB |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            d = r[p]
            fmt = lambda v, n=4: "—" if v is None else (f"{v:.{n}f}" if isinstance(v, float) else str(v))
            L.append(f"| {r['name']} | {r['space']:,} | {r['label']}/{r['expected']} "
                     f"| {fmt(d['achieved'])} | {d['stars_achieved']} | {fmt(d['s'])} | {d['fr']} "
                     f"| {fmt(d['secret'], 3)} | {d['stars_secret']} | {fmt(d['m'], 3)} "
                     f"| {fmt(d['rho'], 3)} | {d['stars_rho']} "
                     f"| {fmt(d['total_mb'])} |")
        L.append("")
    notes = [(r["name"], r["cf_note"]) for r in rows if r.get("cf_note")]
    if notes:
        L += ["## 비고", ""] + [f"- **{n}**: {why}" for n, why in notes] + [""]
    if skipped:
        L += ["## 제외 (측정하지 않음 — 0이 아니다)", ""]
        L += [f"- **{n}**: {why}" for n, why in skipped]
        L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plans", default=",".join(DEFAULT_PLANS))
    ap.add_argument("--targets", default=None,
                    help="쉼표 구분 접두 필터 (예: 'S01,S08,fix-hi-04') — 생략 시 전부")
    ap.add_argument("--enumeration-limit", type=int, default=200_000,
                    help="FC 전수 열거 한도 — 넘는 케이스는 표본 대체 없이 제외")
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--allow-python-mismatch", action="store_true",
                    help="3.14 고정 검사 우회 (수치는 판정에 쓰지 말 것)")
    args = ap.parse_args()
    pyversion.require(args.allow_python_mismatch)

    plan_names = [p.strip() for p in args.plans.split(",") if p.strip()]
    wanted = ([t.strip() for t in args.targets.split(",") if t.strip()]
              if args.targets else None)
    stamp = now_stamp()
    results_root = Path(args.results)

    rows, skipped = [], []
    for name, sc in targets_all():
        if wanted and not any(name.startswith(w) for w in wanted):
            continue
        if sc.space_size() > args.enumeration_limit:
            skipped.append((name, f"조합 {sc.space_size():,} > 열거 한도 "
                                  f"{args.enumeration_limit:,} — FC 전수 원칙상 제외"))
            print(f"  {name}: 제외 (조합 {sc.space_size():,})")
            continue
        rows.append(run_one(name, sc, plan_names, args.enumeration_limit,
                            results_root, stamp))

    md = summary_md(rows, skipped, plan_names, stamp, args.enumeration_limit)
    summary_path = results_root / EXPERIMENT / f"SUMMARY-{stamp}.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(md, encoding="utf-8")
    print(f"\n측정 {len(rows)}건 · 제외 {len(skipped)}건")
    print(f"요약: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
