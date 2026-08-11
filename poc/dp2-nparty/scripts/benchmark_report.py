"""벤치마크 셋 기준 QA 측정 리포트 — 정적 케이스를 입력으로 두 방안을 측정한다.

사용:
    .venv/bin/python scripts/benchmark_report.py
    .venv/bin/python scripts/benchmark_report.py --compare results/20260811T050518Z
    .venv/bin/python scripts/benchmark_report.py --track functional --out results/

기존 `run_measurements.py`(→ `campaign.run_all`)와의 차이는 **입력뿐**이다. 그쪽은 개발용
무작위 프로파일 생성기(`TableUfun` 계열)를 쓰고, 이 스크립트는 `data/benchmark/`의 정적
케이스를 쓴다. 계산식·집계 방식·출력 키 구조는 `campaign.py`의 것을 그대로 따랐다 —
두 결과를 같은 자로 나란히 놓아야 `--compare` 대조가 성립하기 때문이다.

측정 범위:
    [1] Functional Correctness (24)      — 주 산출물. 참여자 수별·시나리오 유형별 분해 포함
    [2] Confidentiality (29)             — 벤치마크 프로파일 위에서 역추론 이득/정규화 노출률
    [3] Resource Utilization-메모리 (26) — 보조 관측 (후보 수 12 고정 표본이라 절대 비교 불가)

Scalability 2축(참여자 수·의제 수)은 **측정하지 않는다** — 벤치마크 셋에 N 스윕 family와
의제 조합 케이스가 없어 입력 자체가 존재하지 않는다 (`data/benchmark/01-...확장-계획.md` §7·§8
"착수 보류"). 해당 축은 생성기 기반 측정(`run_measurements.py`) 결과를 참조한다.

벤치마크 셋과 프로토콜은 둘 다 결정론적이므로 같은 입력이면 항상 같은 결과가 나온다.
`--seed`는 `meta` 기록용이며 측정값을 바꾸지 않는다 (공격자도 고정 규칙이라 난수를 쓰지 않는다).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dp2_nparty.benchmark import (  # noqa: E402
    CASES_DIR,
    FIXTURES_DIR,
    TRACKS,
    BenchmarkCase,
    BenchmarkValidationError,
    JsonBenchmarkLoader,
)
from dp2_nparty.campaign import _meta  # noqa: E402  — meta 생성 방식을 재사용(git/버전 수집 포함)
from dp2_nparty.domain import NO_DEAL, SessionResult  # noqa: E402
from dp2_nparty.measures import fc as fcmod  # noqa: E402
from dp2_nparty.measures.confidentiality import (  # noqa: E402
    exposure_rate,
    measure_gain,
    stars_exposure,
)
from dp2_nparty.measures.ru_memory import peak_memory_bytes  # noqa: E402
from dp2_nparty.protocol import Plan1Vote, Plan2Cumulative  # noqa: E402
from dp2_nparty.report import _stars as stars_text  # noqa: E402  — 별점 표기를 기존 리포트와 일치

PLANS: tuple[tuple[str, Any], ...] = (("plan1", Plan1Vote), ("plan2", Plan2Cumulative))
PLAN_NAMES = tuple(name for name, _ in PLANS)
EPS = 1e-9

VIEWPOINT_LABEL = {"participant": "일반 참여자", "coordinator": "Blackboard 담당자"}


# ---------------------------------------------------------------- 실행 레코드


@dataclass(frozen=True)
class PlanRun:
    session: SessionResult
    fc: fcmod.FcScore


@dataclass(frozen=True)
class CaseRow:
    case: BenchmarkCase
    runs: dict[str, PlanRun]

    @property
    def participants(self) -> int:
        return len(self.case.profiles)

    @property
    def n_candidates(self) -> int:
        return len(self.case.candidates)

    @property
    def scenario_type(self) -> str:
        return str(self.case.meta.get("scenario_type", "(미지정)"))

    @property
    def outcome_differs(self) -> bool:
        return self.runs["plan1"].session.outcome != self.runs["plan2"].session.outcome

    @property
    def both_ceiling(self) -> bool:
        return all(self.runs[p].fc.ratio >= 1.0 - EPS for p in PLAN_NAMES)


def _progress(done: int, total: int, label: str, every: int = 20) -> None:
    if total and (done % every == 0 or done == total):
        print(f"\r  {label}: {done}/{total}", end="" if done < total else "\n", file=sys.stderr)


def run_cases(cases: list[BenchmarkCase]) -> list[CaseRow]:
    """케이스마다 두 방안을 1회씩 실행한다 (관찰 로그 수집 — Confidentiality 입력).

    두 방안에 동일한 `BenchmarkCase`를 변경 없이 전달한다 (확장 계획 §6.3 통제 조건).
    """
    rows: list[CaseRow] = []
    for i, case in enumerate(cases, 1):
        runs: dict[str, PlanRun] = {}
        for name, cls in PLANS:
            session = cls(case.profiles, collect_log=True).run()
            runs[name] = PlanRun(session, fcmod.score(session.outcome, case.candidates, case.profiles))
        rows.append(CaseRow(case, runs))
        _progress(i, len(cases), "협상 실행")
    return rows


# ---------------------------------------------------------------- [1] FC


def _fc_stats(rows: list[CaseRow], plan: str, with_ratios: bool = False) -> dict | None:
    """campaign._fc_section 과 같은 집계 — 키 이름·반올림 자리수까지 맞춘다."""
    if not rows:
        return None
    recs = [r.runs[plan] for r in rows]
    mean_ratio = statistics.mean(r.fc.ratio for r in recs)
    mean_base = statistics.mean(r.fc.baseline for r in recs)
    s = (mean_ratio - mean_base) / (1 - mean_base) if mean_base < 1 else 1.0
    out = {
        "n": len(recs),
        "mean_ratio": round(mean_ratio, 4),
        "mean_baseline": round(mean_base, 4),
        "s": round(s, 4),
        "stars": fcmod.stars_from_s(s),
        "agreed": sum(r.session.agreed for r in recs),
        "optimal_hit": sum(1 for r in recs if r.session.outcome == r.fc.optimal),
        "nodeal_correct": sum(
            1 for r in recs if r.session.outcome == NO_DEAL and r.fc.optimal == NO_DEAL
        ),
        "nodeal_wrong": sum(
            1 for r in recs if r.session.outcome == NO_DEAL and r.fc.optimal != NO_DEAL
        ),
        "tie_break_used": sum(r.session.tie_break_used for r in recs),
        "median_rounds": statistics.median(r.session.rounds for r in recs),
        "median_phases": statistics.median(r.session.phases for r in recs),
        "median_messages": statistics.median(r.session.messages for r in recs),
    }
    if with_ratios:
        out["ratios"] = [round(r.fc.ratio, 4) for r in recs]
    return out


def _group_block(rows: list[CaseRow]) -> dict:
    """한 그룹(참여자 수·시나리오 유형)의 방안별 집계 + 두 방안 갈림 지표."""
    block: dict = {
        "n": len(rows),
        "outcome_differs": sum(1 for r in rows if r.outcome_differs),
        "both_ceiling": sum(1 for r in rows if r.both_ceiling),
    }
    for plan in PLAN_NAMES:
        block[plan] = _fc_stats(rows, plan)
    return block


def fc_section(rows: list[CaseRow]) -> dict:
    sec: dict = {
        "config": {
            "cases": len(rows),
            "candidates": sorted({r.n_candidates for r in rows}),
            "participants": sorted({r.participants for r in rows}),
            "runs_per_case": 1,
            "note": "케이스별 두 방안 1회씩 · 동일 입력 · 결정론적",
        },
        "outcome_differs": sum(1 for r in rows if r.outcome_differs),
        "both_ceiling": sum(1 for r in rows if r.both_ceiling),
    }
    for plan in PLAN_NAMES:
        sec[plan] = _fc_stats(rows, plan, with_ratios=True)

    by_n: dict[int, list[CaseRow]] = defaultdict(list)
    by_type: dict[str, list[CaseRow]] = defaultdict(list)
    for r in rows:
        by_n[r.participants].append(r)
        by_type[r.scenario_type].append(r)
    sec["by_participants"] = {str(n): _group_block(by_n[n]) for n in sorted(by_n)}
    sec["by_scenario_type"] = {t: _group_block(by_type[t]) for t in sorted(by_type)}

    # meta.tags 의 participants:N 과 len(profiles) 가 어긋나면 표본 라벨을 믿을 수 없다
    mismatched = [
        r.case.case_id
        for r in rows
        if any(
            str(t).startswith("participants:") and str(t) != f"participants:{r.participants}"
            for t in r.case.meta.get("tags", []) or []
        )
    ]
    sec["tag_participant_mismatch"] = mismatched
    return sec


# ---------------------------------------------------------------- [2] Confidentiality


def cf_section(rows: list[CaseRow]) -> dict:
    """campaign._cf_section 과 같은 계산을 벤치마크 케이스 위에서 수행한다.

    `measure_gain`은 (SessionResult, profiles) 쌍의 목록과 **후보 수 M 하나**를 받는다
    (무작위 기준선 1/M 계산에 쓰인다). 벤치마크 셋은 후보 수가 케이스마다 다를 수 있으므로
    M별로 그룹을 나눠 따로 계산한다 — 서로 다른 M의 정확도를 한 평균에 섞으면 기준선이
    깨진다. Functional 트랙은 후보 12개 고정(§6.3)이라 실제로는 그룹이 1개다.
    """
    by_m: dict[int, list[CaseRow]] = defaultdict(list)
    for r in rows:
        by_m[r.n_candidates].append(r)

    groups: list[dict] = []
    for m in sorted(by_m):
        grp_rows = by_m[m]
        entry: dict = {"n_candidates": m, "n_cases": len(grp_rows)}
        for plan in PLAN_NAMES:
            runs = [(r.runs[plan].session, r.case.profiles) for r in grp_rows]
            entry[plan] = {}
            for vp in ("participant", "coordinator"):
                g = measure_gain(runs, m, viewpoint=vp)
                rate = exposure_rate(g, m)
                gain = round(g.gain_pp, 2)
                entry[plan][vp] = {
                    "accuracy": round(g.accuracy, 4),
                    "baseline": round(g.random_baseline, 4),
                    "gain_pp": gain if gain else 0.0,  # 부동소수 -0.0 을 0.0 으로 정규화
                    "exposure_rate": round(rate, 4),
                    "stars": stars_exposure(rate),
                }
        groups.append(entry)

    sec: dict = {
        "config": {
            "cases": len(rows),
            "candidate_levels": sorted(by_m),
            "attacker": "frequency 고정 규칙 (29 §29.4) — 난수 없음",
            "note": "관찰 로그 수집(collect_log=True) 세션 기준",
        },
        "groups": groups,
    }
    # 그룹이 1개면 campaign._cf_section 과 같은 최상위 형태로도 노출한다 (--compare 대조용)
    if len(groups) == 1:
        for plan in PLAN_NAMES:
            sec[plan] = groups[0][plan]
    return sec


# ---------------------------------------------------------------- [3] RU-메모리


def ru_section(cases: list[BenchmarkCase]) -> dict:
    """벤치마크 케이스에서 방안별 피크 추가 메모리 중앙값 (collect_log=False)."""
    peaks: dict[str, list[int]] = {p: [] for p in PLAN_NAMES}
    for i, case in enumerate(cases, 1):
        for name, cls in PLANS:
            _, peak = peak_memory_bytes(
                lambda c=cls, p=case.profiles: c(p, collect_log=False).run()
            )
            peaks[name].append(peak)
        _progress(i, len(cases), "메모리 측정")
    sec: dict = {
        "config": {
            "cases": len(cases),
            "note": "관찰 로그 제외(collect_log=False)",
            "caveat": "보조 관측 — 후보 수 12 고정 표본이라 절대 수준 비교용이 아니다",
        }
    }
    for p in PLAN_NAMES:
        v = peaks[p]
        sec[p] = {
            "median_peak_bytes": int(statistics.median(v)) if v else None,
            "peaks": v,
        }
    return sec


# ---------------------------------------------------------------- --compare


def _num(x: Any) -> float | None:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _get(raw: dict, *path: str) -> Any:
    cur: Any = raw
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _fc_denominator(raw: dict, plan: str) -> float | None:
    """FC 표본 크기 — 벤치마크 쪽은 fc[plan].n, 생성기 쪽은 fc.config.runs."""
    return _num(_get(raw, "fc", plan, "n")) or _num(_get(raw, "fc", "config", "runs"))


def _rate(raw: dict, plan: str, key: str) -> float | None:
    top, bottom = _num(_get(raw, "fc", plan, key)), _fc_denominator(raw, plan)
    return top / bottom if top is not None and bottom else None


COMPARE_METRICS: list[tuple[str, Callable[[dict, str], Any], Callable[[float], str]]] = [
    ("FC 평균 달성률", lambda raw, p: _num(_get(raw, "fc", p, "mean_ratio")), lambda v: f"{v:.3f}"),
    ("FC 무작위 베이스라인 R̄", lambda raw, p: _num(_get(raw, "fc", p, "mean_baseline")), lambda v: f"{v:.3f}"),
    ("FC 개선 비율 s", lambda raw, p: _num(_get(raw, "fc", p, "s")), lambda v: f"{v:.3f}"),
    ("FC 별점", lambda raw, p: _num(_get(raw, "fc", p, "stars")), lambda v: stars_text(int(v))),
    ("FC 합의 비율", lambda raw, p: _rate(raw, p, "agreed"), lambda v: f"{v * 100:.1f}%"),
    ("FC x* 도달 비율", lambda raw, p: _rate(raw, p, "optimal_hit"), lambda v: f"{v * 100:.1f}%"),
    (
        "노출률 (일반 참여자)",
        lambda raw, p: _num(_get(raw, "confidentiality", p, "participant", "exposure_rate")),
        lambda v: f"{v:.2f}",
    ),
    (
        "피크 메모리 중앙값",
        lambda raw, p: _num(_get(raw, "ru_memory", p, "median_peak_bytes")),
        lambda v: f"{v / 1024:.1f} KiB",
    ),
]


def load_compare(arg: str) -> tuple[dict | None, str, str | None]:
    """대조용 raw.json 로드. 반환: (raw, 표시용 라벨, 오류 메시지)."""
    path = Path(arg)
    if not path.is_absolute() and not path.exists():
        path = ROOT / arg
    if path.is_dir():
        path = path / "raw.json"
    if not path.is_file():
        return None, arg, f"raw.json을 찾을 수 없다: {path}"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, arg, f"raw.json을 읽을 수 없다: {path} ({exc})"
    if not isinstance(raw, dict):
        return None, arg, f"raw.json 최상위가 object가 아니다: {path}"
    label = str(_get(raw, "meta", "run_id") or path.parent.name)
    return raw, label, None


def compare_section(bench_raw: dict, arg: str) -> dict:
    other, label, error = load_compare(arg)
    sec: dict = {"source": arg, "run_id": label, "error": error, "rows": []}
    if other is None:
        return sec
    sec["source_meta"] = {
        k: _get(other, "meta", k)
        for k in ("timestamp_utc", "seed", "git_commit", "python", "negmas_version", "provider")
    }
    for name, getter, fmt in COMPARE_METRICS:
        for plan in PLAN_NAMES:
            a, b = getter(bench_raw, plan), getter(other, plan)
            sec["rows"].append(
                {
                    "metric": name,
                    "plan": plan,
                    "benchmark": fmt(a) if a is not None else "(키 없음)",
                    "reference": fmt(b) if b is not None else "(키 없음)",
                    "delta": round(a - b, 4) if a is not None and b is not None else None,
                }
            )
    return sec


# ---------------------------------------------------------------- 리포트 렌더링


def _fmt_med(v: Any) -> str:
    return f"{v:.0f}" if isinstance(v, (int, float)) else "-"


def _fc_row(plan: str, d: dict | None) -> str:
    if d is None:
        return f"| {plan} | (케이스 없음) | | | | | | | |"
    return (
        f"| {plan} | {d['mean_ratio']:.3f} | {d['mean_baseline']:.3f} | {d['s']:.3f}"
        f" | {stars_text(d['stars'])} | {d['optimal_hit']}/{d['agreed']}"
        f" | {d['nodeal_correct']}/{d['nodeal_wrong']} | {d['tie_break_used']}"
        f" | {_fmt_med(d['median_rounds'])} / {_fmt_med(d['median_phases'])}"
        f" / {_fmt_med(d['median_messages'])} |"
    )


def _group_rows(blocks: dict, key_label: str) -> list[str]:
    lines = [
        f"| {key_label} | 케이스 | 방안 1 달성률 / s / 별점 | 방안 2 달성률 / s / 별점 "
        "| 결과 상이 | 두 방안 만점 |",
        "|---|---|---|---|---|---|",
    ]
    for key, blk in blocks.items():
        n = blk.get("n", 0)
        if not n:
            lines.append(f"| {key} | 0 | (없음) | (없음) | - | - |")
            continue
        cells = []
        for plan in PLAN_NAMES:
            d = blk.get(plan)
            cells.append(
                f"{d['mean_ratio']:.3f} / {d['s']:.3f} / {d['stars']}점" if d else "(없음)"
            )
        differs, ceiling = blk.get("outcome_differs", 0), blk.get("both_ceiling", 0)
        lines.append(
            f"| {key} | {n} | {cells[0]} | {cells[1]}"
            f" | {differs} ({100.0 * differs / n:.1f}%)"
            f" | {ceiling} ({100.0 * ceiling / n:.1f}%) |"
        )
    return lines


def render_markdown(raw: dict) -> str:
    m, bench = raw["meta"], raw["benchmark"]
    L: list[str] = []
    A = L.append

    A("# 벤치마크 셋 기준 측정 리포트 — 설계 후보 1 (방안 1 전원동의 투표형 vs 방안 2 누적 공통제안형)")
    A("")
    A(f"- 실행: {m['timestamp_utc']} · run_id `{m['run_id']}` · commit `{m['git_commit']}`")
    A(f"- 환경: python {m['python']} · negmas {m['negmas_version']}")
    A(
        f"- **입력: 정적 벤치마크 셋** (무작위 생성 프로파일이 아니다) —"
        f" `{'`, `'.join(bench['roots'])}` 에서 파일 {bench['files_loaded']}건 로드,"
        f" 트랙 필터 `{bench['track']}` 적용 후 **{bench['cases_used']}건** 측정"
        + (f" (`--limit {bench['limit']}` 적용)" if bench.get("limit") else "")
    )
    A(f"- 셋 전체 구성(트랙별): {bench['track_census'] or '(집계 실패)'}")
    A(
        f"- 표본 구성: 참여자 수 {bench['by_participants']} · 시나리오 유형 {bench['by_scenario_type']}"
        f" · 결렬 정답(실후보 0개) {bench['no_feasible']}건"
    )
    A(f"- 프로파일: {m['provider']}")
    A(f"- 결정론: {m['determinism']}")
    A(f"- **주의**: {m['caveat']}")
    A("")

    cmp_sec = raw.get("compare")
    if cmp_sec:
        A("## [0] 대조 — 벤치마크 셋 기준 vs 무작위 프로파일 기준")
        A("")
        if cmp_sec.get("error"):
            A(f"> 대조 실패: {cmp_sec['error']} — 이번 실행 결과만 아래에 싣는다.")
            A("")
        else:
            src = cmp_sec.get("source_meta") or {}
            A(
                f"대조 대상: `{cmp_sec['run_id']}` ({src.get('timestamp_utc', '?')}"
                f" · commit `{src.get('git_commit', '?')}` · seed {src.get('seed', '?')})"
            )
            A(f"대조 대상의 입력: {src.get('provider', '(불명)')}")
            A("")
            A("| 지표 | 방안 | 벤치마크 셋 (이번) | 무작위 프로파일 (대조) | 차이 |")
            A("|---|---|---|---|---|")
            for row in cmp_sec["rows"]:
                delta = row["delta"]
                d = f"{delta:+.3f}" if isinstance(delta, (int, float)) else "-"
                A(
                    f"| {row['metric']} | {row['plan']} | {row['benchmark']}"
                    f" | {row['reference']} | {d} |"
                )
            A("")
            A(
                "> 차이 열은 (벤치마크 − 대조)의 원시 값 차다. 두 측정은 **입력 표본이 다르므로**"
                " 같은 모집단의 재측정이 아니다 — 우열이 아니라 '표본이 무엇을 드러내는가'의 차이로 읽는다."
            )
            A("")

    fc = raw["fc"]
    A("## [1] Functional Correctness — Total Utility 달성률 (24)")
    A("")
    if fc[PLAN_NAMES[0]] is None:
        A("측정 불가 — 케이스 0건.")
        A("")
    else:
        A(
            f"조건: 정적 케이스 {fc['config']['cases']}건 · 케이스당 두 방안 1회씩(동일 입력) ·"
            f" 후보 수 {fc['config']['candidates']} · 참여자 수 {fc['config']['participants']}"
        )
        A("")
        A(
            "| 방안 | 달성률 평균 | R̄ | 개선 비율 s | 별점 | x\\* 도달/합의 | 결렬 정답/오답"
            " | 동률 사용 | 라운드/phase/메시지 중앙값 |"
        )
        A("|---|---|---|---|---|---|---|---|---|")
        for p in PLAN_NAMES:
            A(_fc_row(p, fc[p]))
        A("")
        A(
            "> 집계식·열 구성은 `campaign._fc_section`과 같다. `x\\* 도달`은 결렬이 정답인 케이스"
            "(결렬 정답 열)의 일치까지 포함하므로 합의 건수를 넘을 수 있다."
        )
        A("")
        n = fc["config"]["cases"]
        A(
            f"두 방안의 결과가 갈린 케이스: {fc['outcome_differs']}/{n}"
            f" ({100.0 * fc['outcome_differs'] / n:.1f}%) · 두 방안 모두 만점: {fc['both_ceiling']}/{n}"
            f" ({100.0 * fc['both_ceiling'] / n:.1f}%)"
        )
        A("")
        A("### [1-1] 참여자 수별 (24 §24.5-4 — 3인 기준 표본 · 5·7인 보조 보고)")
        A("")
        L.extend(_group_rows(fc["by_participants"], "참여자 수"))
        A("")
        A("### [1-2] 시나리오 유형별")
        A("")
        L.extend(_group_rows(fc["by_scenario_type"], "시나리오 유형"))
        A("")
        if fc.get("tag_participant_mismatch"):
            A(
                f"> ⚠ `meta.tags`의 participants 라벨과 실제 프로파일 수가 어긋난 케이스:"
                f" {fc['tag_participant_mismatch']}"
            )
            A("")

    cf = raw["confidentiality"]
    A("## [2] Confidentiality — 정규화 노출률 (29, 비핵심·보조 관측)")
    A("")
    if not cf["groups"]:
        A("측정 불가 — 케이스 0건.")
        A("")
    else:
        A(
            f"조건: 정적 케이스 {cf['config']['cases']}건 · 후보 수 {cf['config']['candidate_levels']}"
            f" · {cf['config']['attacker']} · {cf['config']['note']}"
        )
        A("")
        multi = len(cf["groups"]) > 1
        head = "| 후보 수 | 방안 | 관점 | 정확도 | 이득 | 노출률 | 별점 |" if multi else (
            "| 방안 | 관점 | 정확도 | 이득 | 노출률 | 별점 |"
        )
        A(head)
        A("|---|---|---|---|---|---|---|" if multi else "|---|---|---|---|---|---|")
        for grp in cf["groups"]:
            prefix = f"| M={grp['n_candidates']} ({grp['n_cases']}건) |" if multi else "|"
            for p in PLAN_NAMES:
                for vp in ("participant", "coordinator"):
                    d = grp[p][vp]
                    A(
                        f"{prefix} {p} | {VIEWPOINT_LABEL[vp]} | {d['accuracy'] * 100:.1f}%"
                        f" | {d['gain_pp']:+.1f}%p | {d['exposure_rate']:.2f} | {stars_text(d['stars'])} |"
                    )
        A("")

    ru = raw["ru_memory"]
    A("## [3] Resource Utilization-메모리 (26 — ENV-A 대체 측정, **보조 관측**)")
    A("")
    A(
        f"조건: 정적 케이스 {ru['config']['cases']}건 · {ru['config']['note']}."
        f" **{ru['config']['caveat']}** — 정본 측정(Peak/Average RSS)은 실기기 소관이고,"
        " 여기 값은 같은 표본 안에서의 방안 간 상대 크기만 뜻한다."
    )
    A("")
    A("| 방안 | 피크 추가 메모리 중앙값 |")
    A("|---|---|")
    for p in PLAN_NAMES:
        v = ru[p]["median_peak_bytes"]
        A(f"| {p} | {v / 1024:.1f} KiB |" if v is not None else f"| {p} | (케이스 없음) |")
    A("")

    A("## 측정하지 않는 축")
    A("")
    A(f"- {raw['not_measured']['reason']}")
    A("")

    A("## 종합 — 별점 요약 (벤치마크 셋 기준)")
    A("")
    A("| QA | 방안 1 | 방안 2 |")
    A("|---|---|---|")
    if fc[PLAN_NAMES[0]] is not None:
        A(
            f"| Functional Correctness (핵심 1위) | {stars_text(fc['plan1']['stars'])}"
            f" | {stars_text(fc['plan2']['stars'])} |"
        )
    else:
        A("| Functional Correctness (핵심 1위) | (케이스 없음) | 〃 |")
    A("| RU-메모리 (핵심 2위) | 상대 비교만 (별점 척도는 26 확정 대기) | 〃 |")
    A("| SC-참여자 수 (핵심 3위) | 미측정 — '측정하지 않는 축' 참조 | 〃 |")
    A("| SC-의제 수 (핵심 4위) | 미측정 — '측정하지 않는 축' 참조 | 〃 |")
    A("| FT & REC (핵심 5위) | 미측정 (장애 주입·kill-resume 하니스 필요) | 〃 |")
    if cf["groups"]:
        g = cf["groups"][0]
        A(
            f"| Confidentiality (비핵심 — 참여자 관찰자 기준) | {stars_text(g['plan1']['participant']['stars'])}"
            f" | {stars_text(g['plan2']['participant']['stars'])} |"
        )
    else:
        A("| Confidentiality (비핵심) | (케이스 없음) | 〃 |")
    A("")
    A(f"> 주의: {m['caveat']}")
    A("")
    return "\n".join(L)


# ---------------------------------------------------------------- 조립·실행


def track_census(roots: list[Path]) -> dict[str, int] | None:
    """트랙 필터 없이 셋 전체 구성을 센다 (리포트 머리말·미측정 축 판단용).

    측정 경로와 달리 교차 검증을 걸지 않는다 — 여기서 알고 싶은 것은 '무엇이 들어 있는가'
    뿐이고, 다른 트랙의 정합성 문제로 이번 측정을 막을 이유가 없기 때문이다.
    """
    try:
        cases = list(JsonBenchmarkLoader(roots=roots, track=None, validate=False).cases())
    except Exception:  # 셋이 갱신 중이거나 깨져 있어도 측정은 계속한다
        return None
    census: dict[str, int] = {}
    for c in cases:
        key = c.track or "(미지정)"
        census[key] = census.get(key, 0) + 1
    return {k: census[k] for k in sorted(census)}


def not_measured_note(census: dict[str, int] | None) -> str:
    """Scalability 2축을 왜 싣지 않는지 — 셋의 실제 구성에 맞춰 문구를 고른다."""
    tail = "이 두 축은 기존 생성기 기반 측정(`scripts/run_measurements.py` 결과)을 참조한다."
    n_scal = (census or {}).get("scalability", 0)
    if n_scal:
        return (
            f"Scalability-참여자 수(25)와 Scalability-의제 수(27)는 이 리포트의 측정 대상이 아니다 "
            f"— 벤치마크 셋에 scalability 트랙 {n_scal}건이 있으나 본 스크립트는 "
            f"FC·Confidentiality·RU 3축만 다루고, 의제 조합(S 스윕) 케이스는 여전히 셋에 없다. {tail}"
        )
    return (
        "Scalability-참여자 수(25)와 Scalability-의제 수(27)는 벤치마크 셋 미보유로 측정 대상이 아니다 "
        "— 셋에 N 스윕 family와 의제 조합 케이스가 없어 입력 자체가 없다(확장 계획 §7·§8 착수 보류). "
        + tail
    )


def build_raw(
    rows: list[CaseRow],
    cases: list[BenchmarkCase],
    roots: list[Path],
    track: str | None,
    files_loaded: int,
    limit: int | None,
    seed: int,
) -> dict:
    meta = dict(_meta(seed))  # git commit·negmas/python 버전 수집 방식을 campaign 과 공유
    meta["run_id"] = f"benchmark-{meta['run_id']}"
    meta["provider"] = "정적 벤치마크 셋 (JsonBenchmarkLoader — data/benchmark)"
    meta["determinism"] = (
        "정적 입력 + 난수 없는 프로토콜/공격자 → 같은 입력이면 항상 같은 결과. "
        "seed는 meta 기록용이며 측정값에 영향이 없다."
    )
    meta["caveat"] = (
        "입력이 정적 벤치마크 셋이다 — 개발용 무작위 프로파일 기준 결과와 값이 다른 것이 정상이며, "
        "두 결과를 한 표에 합산하지 않는다 (확장 계획 §11: 표본을 서로의 통계에 섞지 않는다)."
    )

    by_participants: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for c in cases:
        k = str(len(c.profiles))
        by_participants[k] = by_participants.get(k, 0) + 1
        t = str(c.meta.get("scenario_type", "(미지정)"))
        by_type[t] = by_type.get(t, 0) + 1

    census = track_census(roots)
    bench = {
        "roots": [str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p) for p in roots],
        "track": track or "(전체)",
        "track_census": census,
        "files_loaded": files_loaded,
        "cases_used": len(cases),
        "limit": limit,
        "by_participants": {k: by_participants[k] for k in sorted(by_participants, key=int)},
        "by_scenario_type": {k: by_type[k] for k in sorted(by_type)},
        "no_feasible": sum(1 for c in cases if not c.feasible()),
        "case_ids": [c.case_id for c in cases],
    }

    return {
        "meta": meta,
        "benchmark": bench,
        "fc": fc_section(rows),
        "confidentiality": cf_section(rows),
        "ru_memory": ru_section(cases),
        "not_measured": {
            "sc_participants": "이 리포트 범위 밖",
            "sc_issues": "벤치마크 셋 미보유",
            "reason": not_measured_note(census),
        },
    }


def unique_run_dir(base_dir: Path, name: str) -> Path:
    """run_measurements.py 와 같은 접미사 유일성 — 같은 초에 재실행돼도 덮어쓰지 않는다."""
    base = base_dir / name
    run_dir, n = base, 2
    while run_dir.exists():
        run_dir = base.with_name(f"{base.name}-{n}")
        n += 1
    return run_dir


def main() -> int:
    ap = argparse.ArgumentParser(
        description="정적 벤치마크 셋을 입력으로 QA를 측정하고 리포트를 낸다."
    )
    ap.add_argument(
        "--track",
        default="functional",
        choices=[*TRACKS, "all"],
        help="사용할 트랙 (기본 functional — FC 기준 표본 160건)",
    )
    ap.add_argument("--limit", type=int, default=None, help="앞 N건만 실행 (스모크용)")
    ap.add_argument("--compare", default=None, help="대조할 results/<run_id> 또는 raw.json 경로")
    ap.add_argument("--out", default=None, help="산출물 상위 디렉터리 (기본 results/)")
    ap.add_argument("--seed", type=int, default=20260811, help="meta 기록용 (측정값 불변)")
    ap.add_argument("--no-validate", action="store_true", help="케이스 집합 교차 검증 생략")
    args = ap.parse_args()

    track = None if args.track == "all" else args.track
    roots = [FIXTURES_DIR, CASES_DIR]
    loader = JsonBenchmarkLoader(roots=roots, track=track, validate=not args.no_validate)
    files_loaded = len(loader.paths())
    try:
        cases = list(loader.cases())
    except BenchmarkValidationError as exc:
        print(f"벤치마크 셋 검증 실패 — 측정을 중단한다:\n{exc}", file=sys.stderr)
        return 2

    if args.limit is not None:
        if args.limit <= 0:
            print("--limit 은 1 이상이어야 한다.", file=sys.stderr)
            return 2
        cases = cases[: args.limit]

    print(
        f"벤치마크 로드: 파일 {files_loaded}건 → 트랙 '{args.track}' 필터 후 {len(cases)}건 실행",
        file=sys.stderr,
    )
    if not cases:
        print("⚠ 케이스 0건 — 측정 섹션은 비어 있는 채로 리포트만 생성한다.", file=sys.stderr)

    rows = run_cases(cases)
    raw = build_raw(rows, cases, roots, track, files_loaded, args.limit, args.seed)
    if args.compare:
        raw["compare"] = compare_section(raw, args.compare)
        if raw["compare"].get("error"):
            print(f"⚠ 대조 불가: {raw['compare']['error']}", file=sys.stderr)

    out_base = Path(args.out) if args.out else ROOT / "results"
    if not out_base.is_absolute():
        out_base = ROOT / out_base
    run_dir = unique_run_dir(out_base, raw["meta"]["run_id"])
    raw["meta"]["run_id"] = run_dir.name
    run_dir.mkdir(parents=True)
    (run_dir / "raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    report = render_markdown(raw)
    (run_dir / "report.md").write_text(report, encoding="utf-8")

    print(report)
    print(f"저장: {run_dir}/raw.json · {run_dir}/report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
