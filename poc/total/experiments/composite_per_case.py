#!/usr/bin/env python3
"""실험 — composite 벤치마크 **개별 케이스**의 QA 수치 (S01~S12 · fixtures).

`composite_1_vs_2.py`가 시나리오 전체를 하나로 집계하는 것과 달리, 여기서는
**시나리오/fixture 1건마다 별도 실행 폴더**를 만들어 그 케이스의 QA 수치를 낸다 —
"어느 시나리오에서 두 방안이 갈리는가"를 케이스 단위로 볼 수 있다.

**측정 범위는 FC·RU·TB** (PL 지시 2026-08-13 — `campaign.QA_COMPOSITE`). 복합 의제
DP의 본질은 조합 폭발이라 RU가 핵심 변별축이다. CF는 잔여 비밀률의 분모(전체 후보)가
조합적으로 거대해 퇴화하므로 nparty 담당 (`qa/cf.py` 참조).

- 대상: `datasets/composite/scenarios/*.yaml` 12종 + `datasets/composite/fixtures/*.json`
- 산출: `results/composite-per-case/composite-per-case-<ID>-<stamp>/` (meta·raw·cases·report)
  + 대상 전체 요약표 `results/composite-per-case/SUMMARY-<stamp>.md`
- 조합 수가 열거 한도를 넘는 대상(S11 977만 등)은 **표본으로 대체하지 않고 제외**하며
  (24 정본 FC는 전수 열거 전제), 제외 사실과 사유를 요약표에 남긴다.

    .venv/bin/python experiments/composite_per_case.py [--plans seq2,pool]
        [--targets S01,S03,fix-hi-04] [--enumeration-limit 300000]
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from total import pyversion  # noqa: E402
from total.adapters.composite import (  # noqa: E402
    DATASETS,
    PLANS,
    CompositeCase,
    load,
    run_session,
    scenario_paths,
)
from total.adapters.composite._vendor.common.generators import Value  # noqa: E402
from total.adapters.composite._vendor.common.scenario import Axis, Scenario  # noqa: E402
from total.adapters.composite.baseline import baseline_t  # noqa: E402
from total.campaign import QA_COMPOSITE, PlanRuns, measure  # noqa: E402
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


@contextmanager
def _deadline(seconds: int):
    """방안 1회 실행의 벽시계 상한 — 대형 fixture에서 풀 확장이 폭주하면 그 사실을
    측정 실패로 기록하고 다음 대상으로 넘어간다 (조용히 매달리지 않는다)."""

    def _handler(signum, frame):
        raise TimeoutError(f"{seconds}s 초과")

    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def run_one(name: str, sc: Scenario, plan_names: list[str], limit: int,
            results_root: Path, stamp: str, light: bool = False,
            timeout_s: int = 900) -> tuple[dict | None, list[tuple[str, str]]]:
    """케이스 1건: 방안별 실행 → 실행 폴더 1개. (요약 행, 실패 목록)을 돌려준다.

    `light=True`(조합이 열거 한도 초과): FC 오라클 없이 RU·TB만 잰다 — pool의 압축
    풀이 큰 축 수에서 어디까지 크는지가 이 경로의 존재 이유다.
    """
    case = CompositeCase(sc.id, sc, enumeration_limit=limit)
    failures: list[tuple[str, str]] = []
    qa = ("ru", "tb") if light else QA_COMPOSITE

    try:
        with _deadline(timeout_s):
            tb_baselines = {sc.id: baseline_t(sc)}
    except Exception as exc:
        failures.append((f"{name}/baseline", f"{type(exc).__name__}: {exc}"))
        tb_baselines = None

    plans: list[PlanRuns] = []
    for pname in plan_names:
        try:
            with _deadline(timeout_s):
                session, _ = run_session(sc, pname, case=case, light=light)
        except Exception as exc:
            failures.append((f"{name}/{pname}", f"{type(exc).__name__}: {exc}"))
            continue
        pr = PlanRuns(pname, PLANS[pname].label)
        violations = () if light else case.hard_violations(session.agreement)
        pr.add(session, case, violations)
        plans.append(pr)

    if not plans:
        return None, failures

    raw, rows = measure(plans, tb_baselines=tb_baselines, qa=qa)

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
        plans=[pr.plan for pr in plans],
        note=f"개별 케이스 측정 ({name}). 측정 범위 {list(qa)} "
             "(campaign.QA_COMPOSITE — PL 지시 2026-08-13, CF는 nparty 담당)."
             + (" 경량 실행 — 조합이 열거 한도를 넘어 FC(전수 채점) 제외, RU·TB만."
                if light else ""),
    )
    out = write_run(results_root, meta, raw, rows)
    print(f"  {name}: 저장 {out.name}" + (" [경량 RU·TB]" if light else ""))

    row = {"name": name, "space": sc.space_size(),
           "label": sc.meta.get("conflict_level", "?"),
           "expected": sc.meta.get("expected", "?"), "light": light}
    for p in plan_names:
        fc_, ru_, tb_ = (raw.get(k, {}).get(p, {}) for k in ("fc", "ru", "tb"))
        row[p] = {
            "achieved": fc_.get("mean_achieved"), "stars_achieved": fc_.get("stars_achieved"),
            "s": fc_.get("mean_s"), "fr": fc_.get("fr_violation_cases"),
            "total_mb": ru_.get("median_total_mb"), "stars_ru": ru_.get("stars_median"),
            "materialized_mb": ru_.get("median_materialized_mb"),
            "over_ceiling": ru_.get("over_ceiling_sessions"),
            "rho": tb_.get("median_rho"), "stars_rho": tb_.get("stars"),
        }
    return row, failures


def summary_md(rows: list[dict], skipped: list[tuple[str, str]],
               plan_names: list[str], stamp: str, limit: int) -> str:
    L = [f"# composite 개별 케이스 요약 — {stamp}", "",
         f"방안 {list(plan_names)} · 측정 범위 {list(QA_COMPOSITE)} · "
         f"열거 한도 {limit:,} · 각 케이스의 상세는 "
         f"`composite-per-case-<ID>-{stamp}/report.md`", ""]
    for p in plan_names:
        L += [f"## {p}", "",
              "| 케이스 | 조합 | 성격 | 달성률 | 달성★ | s(보조) | FR위반 "
              "| 총점유MB | 실물화MB | RU★ | 한도초과 | ρ | ρ★ |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            d = r[p]
            fmt = lambda v, n=4: "—" if v is None else (f"{v:.{n}f}" if isinstance(v, float) else str(v))
            tag = " ⚡" if r.get("light") else ""
            L.append(f"| {r['name']}{tag} | {r['space']:,} | {r['label']}/{r['expected']} "
                     f"| {fmt(d['achieved'])} | {d['stars_achieved']} | {fmt(d['s'])} | {d['fr']} "
                     f"| {fmt(d['total_mb'])} | {fmt(d['materialized_mb'])} "
                     f"| {d['stars_ru']} | {d['over_ceiling']} "
                     f"| {fmt(d['rho'], 3)} | {d['stars_rho']} |")
        L.append("")
    if any(r.get("light") for r in rows):
        L += ["> ⚡ = 경량 실행 — 조합이 열거 한도를 넘어 FC(전수 채점)는 정의상 불가, "
              "RU·TB만 측정. 표본 채점으로 대체하지 않는다 (24 §1 전수 원칙).", ""]
    if skipped:
        L += ["## 측정 실패 (기록 — 0이 아니다)", ""]
        L += [f"- **{n}**: {why}" for n, why in skipped]
        L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plans", default=",".join(DEFAULT_PLANS))
    ap.add_argument("--targets", default=None,
                    help="쉼표 구분 접두 필터 (예: 'S01,S08,fix-hi-04') — 생략 시 전부")
    ap.add_argument("--enumeration-limit", type=int, default=200_000,
                    help="FC 전수 열거 한도 — 넘는 케이스는 경량(RU·TB) 실행으로 전환")
    ap.add_argument("--per-plan-timeout", type=int, default=900,
                    help="방안 1회 실행의 벽시계 상한(초) — 초과 시 실패로 기록")
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
        light = sc.space_size() > args.enumeration_limit
        if light:
            print(f"  {name}: 조합 {sc.space_size():,} > 한도 — 경량(RU·TB) 실행")
        row, failures = run_one(name, sc, plan_names, args.enumeration_limit,
                                results_root, stamp, light=light,
                                timeout_s=args.per_plan_timeout)
        if row is not None:
            rows.append(row)
        skipped.extend(failures)

    md = summary_md(rows, skipped, plan_names, stamp, args.enumeration_limit)
    summary_path = results_root / EXPERIMENT / f"SUMMARY-{stamp}.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(md, encoding="utf-8")
    print(f"\n측정 {len(rows)}건 · 제외 {len(skipped)}건")
    print(f"요약: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
