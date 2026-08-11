"""Scalability-참여자 수 (b_msg) — 정적 벤치마크 family 기준 측정 (25 §25.3-§25.6).

기존 campaign.py 의 `_sc_participants_section` 은 무작위 생성기(ControlledTableUfun)로
N 수준마다 프로파일을 새로 뽑는다. 이 스크립트는 같은 계산·같은 출력 키 구조를 쓰되,
입력만 정적 벤치마크 family(`data/benchmark/cases/scalability/participants/`)로 바꾼다.
family 안에서는 N이 늘어도 기존 참여자의 프로파일과 후보 목록이 그대로 유지되므로
(benchmark.validate_set 의 family 불변조건이 이를 강제한다) N 사이의 분산이 작다.

사용:
    .venv/bin/python scripts/scalability_report.py
    .venv/bin/python scripts/scalability_report.py --by-k
    .venv/bin/python scripts/scalability_report.py --root <케이스 디렉터리>
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dp2_nparty.benchmark import (  # noqa: E402
    BenchmarkCase,
    BenchmarkValidationError,
    JsonBenchmarkLoader,
)
from dp2_nparty.measures.scaling import (  # noqa: E402
    ci_spans_grades,
    completion_gate,
    loglog_fit,
    stars_b_msg,
)
from dp2_nparty.protocol import Plan1Vote, Plan2Cumulative  # noqa: E402

PLANS = (("plan1", Plan1Vote), ("plan2", Plan2Cumulative))
PLAN_NAMES = ("plan1", "plan2")
DEFAULT_ROOT = ROOT / "data" / "benchmark" / "cases" / "scalability" / "participants"
TRACK = "scalability"
SCENARIO = "participants_sweep"
MIN_FIT_POINTS = 3  # loglog_fit 은 dof = n-2 이므로 2점이면 신뢰구간이 무한대가 된다


# ---------------------------------------------------------------- 실행


def case_k(case: BenchmarkCase) -> int | None:
    """family의 공통 실후보 수 k — meta 우선, 없으면 tags의 `k:<k>`."""
    k = case.meta.get("common_feasible_count")
    if isinstance(k, int):
        return k
    for tag in case.meta.get("tags", []) or []:
        if isinstance(tag, str) and tag.startswith("k:"):
            try:
                return int(tag[2:])
            except ValueError:
                return None
    return None


def run_case(case: BenchmarkCase) -> list[dict[str, Any]]:
    """케이스 1건에 두 방안을 1회씩 실행 (메모리 측정 불필요 → collect_log=False)."""
    rows = []
    for plan, cls in PLANS:
        r = cls(case.profiles, collect_log=False).run()
        rows.append(
            {
                "case_id": case.case_id,
                "family_id": case.family_id,
                "k": case_k(case),
                "n": len(case.profiles),
                "plan": plan,
                "outcome": str(r.outcome),
                "agreed": bool(r.agreed),
                "messages": r.messages,
                "rounds": r.rounds,
                "sweeps": r.sweeps,
                "phases": r.phases,
                "tie_break_used": bool(r.tie_break_used),
            }
        )
    return rows


# ---------------------------------------------------------------- 분석 (25 §25.5)


def _median(values: list[float | int]) -> float | None:
    return statistics.median(values) if values else None


def analyse(records: list[dict[str, Any]]) -> dict[str, Any]:
    """한 방안·한 그룹의 실행 기록 → 25 §25.5 절차 (게이트 → 중앙값 → 회귀 → 별점).

    출력 키는 campaign._sc_participants_section 과 같은 구조를 따른다.
    """
    ns = sorted({r["n"] for r in records})
    by_n = {n: [r for r in records if r["n"] == n] for n in ns}
    total = {n: len(by_n[n]) for n in ns}
    agreed = {n: sum(r["agreed"] for r in by_n[n]) for n in ns}

    med_msg: dict[int, float | None] = {}
    med_rounds: dict[int, float | None] = {}
    med_phases: dict[int, float | None] = {}
    for n in ns:
        done = [r for r in by_n[n] if r["agreed"]]  # 정상 완결(AGREED) 세션만 집계
        med_msg[n] = _median([r["messages"] for r in done])
        med_rounds[n] = _median([r["rounds"] for r in done])
        med_phases[n] = _median([r["phases"] for r in done])

    # 2. 완결률 게이트 먼저 — 최소 N vs 최대 N (§25.4)
    gate = completion_gate(agreed[ns[0]], total[ns[0]], agreed[ns[-1]], total[ns[-1]])

    out: dict[str, Any] = {
        "levels": ns,
        "cases_by_n": {str(n): total[n] for n in ns},
        "agreed_by_n": {str(n): agreed[n] for n in ns},
        "completion_rate_by_n": {str(n): round(agreed[n] / total[n], 4) for n in ns},
        "median_messages_by_n": {str(n): med_msg[n] for n in ns},
        "median_rounds_by_n": {str(n): med_rounds[n] for n in ns},
        "median_phases_by_n": {str(n): med_phases[n] for n in ns},
        "gate_ok": gate,
        "gate_detail": (
            f"N={ns[0]} {agreed[ns[0]]}/{total[ns[0]]} vs "
            f"N={ns[-1]} {agreed[ns[-1]]}/{total[ns[-1]]}"
        ),
    }

    # 3-4. 정상 완결 세션의 M_N → log-log 회귀
    xs = [n for n in ns if med_msg[n] is not None]
    if len(xs) < MIN_FIT_POINTS:
        out.update(
            b_msg=None, ci=None, r2=None, stars=0, ci_spans_3_grades=None,
            note=f"회귀 불가 — 완결 세션이 있는 N 수준이 {len(xs)}개뿐 (최소 {MIN_FIT_POINTS})",
        )
        return out
    fit = loglog_fit(xs, [float(med_msg[n]) for n in xs])  # type: ignore[arg-type]
    out.update(
        b_msg=round(fit.b, 4),
        ci=[round(fit.ci_low, 4), round(fit.ci_high, 4)],
        r2=round(fit.r2, 4),
        stars=stars_b_msg(fit.b) if gate else 0,  # 게이트 위반이면 b_msg와 무관하게 0점
        ci_spans_3_grades=ci_spans_grades(fit),
        fit_points=len(xs),
    )
    return out


def analyse_all(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {p: analyse([r for r in records if r["plan"] == p]) for p in PLAN_NAMES}


def generator_reference() -> dict[str, Any] | None:
    """비교용 — 기존 생성기 기반 측정(run_measurements.py)의 sc_participants 결과."""
    for path in sorted((ROOT / "results").glob("*/raw.json"), reverse=True):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        sp = raw.get("sc_participants")
        if isinstance(sp, dict) and "plan1" in sp:
            return {
                "run_id": raw.get("meta", {}).get("run_id", path.parent.name),
                "provider": sp.get("config", {}).get("provider", "?"),
                **{
                    p: {
                        "b_msg": sp[p]["b_msg"],
                        "ci": sp[p]["ci"],
                        "r2": sp[p]["r2"],
                        "stars": sp[p]["stars"],
                        "ci_spans_3_grades": sp[p]["ci_spans_3_grades"],
                    }
                    for p in PLAN_NAMES
                    if p in sp
                },
            }
    return None


# ---------------------------------------------------------------- 리포트


def _stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n) + f" ({n}점)"


def _fit_cell(d: dict[str, Any]) -> str:
    if d["b_msg"] is None:
        return "산출 불가"
    warn = " ⚠CI 3등급" if d["ci_spans_3_grades"] else ""
    return f"{d['b_msg']:.3f} [{d['ci'][0]:.2f}, {d['ci'][1]:.2f}]{warn}"


def _msgs_cell(d: dict[str, Any]) -> str:
    return " ".join(f"N{n}:{v:.0f}" for n, v in d["median_messages_by_n"].items() if v)


def _gate_cell(d: dict[str, Any]) -> str:
    return ("통과" if d["gate_ok"] else "**위반(0점)**") + f" {d['gate_detail']}"


def _num(v: float | None, digits: int = 3) -> str:
    return "-" if v is None else f"{v:.{digits}f}"


def render(raw: dict[str, Any]) -> str:
    m = raw["meta"]
    L: list[str] = []
    A = L.append

    A("# Scalability-참여자 수 — 메시지 확장 지수 b_msg (25) · 정적 벤치마크 family 기준")
    A("")
    A(f"- 실행: {m.get('timestamp') or m.get('timestamp_utc')} · run_id `{m['run_id']}`")
    A(f"- 입력: **정적 벤치마크 family** `{m['cases_root']}` — 무작위 생성기가 아니다")
    k_dist = " · ".join(f"{k} {v}" for k, v in m["k_distribution"].items())
    A(
        f"- 표본: 케이스 {m['n_cases']}건 · family {m['n_families']}개 · "
        f"N ∈ {m['levels']} · k 분포 {k_dist}"
    )
    A(f"- 실행: 케이스마다 두 방안 각 1회 (`collect_log=False`) · 세션 {m['n_sessions']}건")
    A(f"- 환경: python {m['python']} · negmas {m['negmas_version']}")
    A(
        "- 설계 근거: family는 N이 늘어도 **기존 참여자 프로파일과 후보 목록이 그대로 유지**되고 "
        "공통 실후보 수 k가 N과 무관하게 고정된다 (25 §25.5 난이도 교락 통제)"
    )
    A("")

    A("## [1] 전체 — b_msg (k=1/2/3 통합)")
    A("")
    A("| 방안 | 완결률 게이트 | b_msg [95% CI] | R² | 별점 | 메시지 중앙값 (N별) |")
    A("|---|---|---|---|---|---|")
    for p in PLAN_NAMES:
        d = raw["overall"][p]
        A(
            f"| {p} | {_gate_cell(d)} | {_fit_cell(d)} | {_num(d['r2'])} "
            f"| {_stars(d['stars'])} | {_msgs_cell(d)} |"
        )
    A("")

    if raw.get("by_k"):
        A("## [2] k별 — 사전 실험 (25 §25.5의 'k는 사전 실험으로 정해 고정' 요구에 대응)")
        A("")
        A(
            "25 §25.5는 난이도 교락 통제용 공통 실후보 수 k를 사전 실험으로 정해 실험 설계서에 "
            "고정하라고 요구하지만, 그 사전 실험은 수행된 적이 없다. **아래 표가 그 사전 실험이다** "
            "— k를 바꾸면 b_msg 별점이 몇 등급 움직이는지가 산출물이다."
        )
        A("")
        A("| 방안 | k | 케이스 | 완결률 게이트 | b_msg [95% CI] | R² | 별점 | 메시지 중앙값 (N별) |")
        A("|---|---|---|---|---|---|---|---|")
        for p in PLAN_NAMES:
            for k in raw["by_k"]["order"]:
                d = raw["by_k"][p][str(k)]
                n_cases = sum(d["cases_by_n"].values())
                r2 = "-" if d["r2"] is None else f"{d['r2']:.3f}"
                A(
                    f"| {p} | k={k} | {n_cases} | {_gate_cell(d)} | {_fit_cell(d)} | {r2} "
                    f"| {_stars(d['stars'])} | {_msgs_cell(d)} |"
                )
        A("")
        A("**k 민감도 — 별점 이동 폭**")
        A("")
        A("| 방안 | k별 별점 | 별점 이동 | k별 b_msg | b_msg 폭 |")
        A("|---|---|---|---|---|")
        for p in PLAN_NAMES:
            s = raw["by_k"]["sensitivity"][p]
            stars_txt = " / ".join(f"k{k}:{v}점" for k, v in s["stars_by_k"].items())
            b_txt = " / ".join(f"k{k}:{_num(v)}" for k, v in s["b_by_k"].items())
            A(
                f"| {p} | {stars_txt} | **{s['star_span']}등급** | {b_txt} "
                f"| {_num(s['b_span'])} |"
            )
        A("")
        A(
            f"> 해석: 별점 이동 폭이 0등급이면 k 선택이 판정에 영향을 주지 않으므로 실험 설계서에 "
            f"어떤 k를 고정해도 무방하다. 1등급 이상이면 k를 고정하지 않은 측정은 등급을 신뢰할 수 없다."
        )
        A("")

    A("## [3] 보조 관측 (25 §25.6 — 판정에는 쓰지 않음)")
    A("")
    A("| 방안 | R² | 라운드 중앙값 (N별) | phase 중앙값 (N별) |")
    A("|---|---|---|---|")
    for p in PLAN_NAMES:
        d = raw["overall"][p]
        rounds = " ".join(f"N{n}:{v:.0f}" for n, v in d["median_rounds_by_n"].items() if v)
        phases = " ".join(f"N{n}:{v:.0f}" for n, v in d["median_phases_by_n"].items() if v)
        r2 = "-" if d["r2"] is None else f"{d['r2']:.3f}"
        A(f"| {p} | {r2} | {rounds} | {phases} |")
    A("")
    A(f"- **부하 편중(최대÷평균)**: {raw['meta']['load_skew_note']}")
    A("- R² < 0.9면 멱 모형 부적합 신호 (§25.6) — 위 표의 R²로 확인한다.")
    A("")

    A("## [4] 기존 생성기 기반 측정과의 비교")
    A("")
    A(
        "기존 생성기 기반 측정은 N 수준마다 프로파일을 통째로 새로 뽑아 N 사이에 "
        "'문제 자체가 달라지는' 분산이 섞여 들어갔고, 신뢰구간이 3등급에 걸쳤다. 이 family 설계는 "
        "**N이 늘어도 기존 참여자 프로파일이 그대로 유지**되므로 N 사이의 차이가 참여자 추가분으로만 "
        "생긴다 — 두 결과를 비교하면 그 효과가 보인다."
    )
    A("")
    ref = raw.get("generator_reference")
    if not ref:
        A("> 비교 대상 생성기 결과(results/*/raw.json 의 sc_participants)를 찾지 못했다.")
        A("")
        return "\n".join(L)

    A("| 방안 | 입력 | b_msg [95% CI] | CI 폭 | R² | 별점 | CI 3등급 |")
    A("|---|---|---|---|---|---|---|")
    widths: dict[str, tuple[float | None, float | None]] = {}
    for p in PLAN_NAMES:
        g = ref.get(p)
        gw = (g["ci"][1] - g["ci"][0]) if g else None
        d = raw["overall"][p]
        fw = (d["ci"][1] - d["ci"][0]) if d["ci"] else None
        widths[p] = (gw, fw)
        if g:
            A(
                f"| {p} | 생성기 `{ref['run_id']}` ({ref['provider']}) | "
                f"{g['b_msg']:.3f} [{g['ci'][0]:.2f}, {g['ci'][1]:.2f}] | {_num(gw)} | {g['r2']:.3f} "
                f"| {_stars(g['stars'])} | {'예' if g['ci_spans_3_grades'] else '아니오'} |"
            )
        A(
            f"| {p} | **정적 family (본 측정)** | {_fit_cell(d)} | {_num(fw)} | {_num(d['r2'])} "
            f"| {_stars(d['stars'])} | {'예' if d['ci_spans_3_grades'] else '아니오'} |"
        )
    A("")

    # 관측된 값으로 검증한다 — 위 설계 논리가 실제로 CI를 좁혔는지는 데이터가 판단한다.
    verdicts = []
    for p in PLAN_NAMES:
        gw, fw = widths[p]
        if gw is None or fw is None:
            continue
        direction = "축소" if fw < gw - 1e-9 else ("확대" if fw > gw + 1e-9 else "동일")
        verdicts.append(f"{p} {gw:.3f} → {fw:.3f} ({direction})")
    if verdicts:
        A(f"**관측된 CI 폭 변화**: {' · '.join(verdicts)}")
        A("")
        narrowed = all(
            w[1] is not None and w[0] is not None and w[1] < w[0] - 1e-9 for w in widths.values()
        )
        if narrowed:
            A("> 두 방안 모두 CI가 좁아졌다 — family 설계의 분산 축소 효과가 관측됐다.")
        else:
            A(
                "> **주의 — 위 설계 논리가 이번 데이터에서는 확인되지 않았다.** family 입력에서도 CI가 "
                "좁아지지 않았고 CI는 여전히 3등급에 걸친다. 즉 CI 폭을 지배하는 것은 N 사이의 프로파일 "
                "변동이 아니라 **N 수준이 6개뿐이라 회귀 자유도가 4**라는 점이다(loglog_fit 은 N 수준별 "
                "중앙값 1점씩만 적합한다 — family를 늘려도 회귀점 수는 그대로다). 등급 확정에는 N 수준 "
                "추가가 필요하며, family 설계의 값어치는 CI 폭이 아니라 **난이도 교락이 제거된 b_msg "
                "점추정의 타당성**에서 찾아야 한다."
            )
        A("")
    A("")
    return "\n".join(L)


# ---------------------------------------------------------------- 진입점


def out_dir() -> Path:
    from dp2_nparty.campaign import KST
    stamp = datetime.now(KST).strftime("%Y%m%dT%H%M%S") + "KST"
    base = ROOT / "results" / f"scalability-{stamp}"
    path, i = base, 2
    while path.exists():  # 같은 초에 재실행돼도 덮어쓰지 않는다 (run_measurements.py 방식)
        path = base.with_name(f"{base.name}-{i}")
        i += 1
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="정적 벤치마크 family 기준 b_msg 측정 (25)")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="케이스 디렉터리")
    ap.add_argument("--by-k", action="store_true", help="공통 실후보 수 k별로 나눠 산출")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists() or not list(root.rglob("*.json")):
        print(f"[대기] 정적 케이스가 아직 없다: {root}")
        print("       다른 작업자가 생성 중인 participants family 180건이 도착하면 재실행한다.")
        return 0

    try:
        cases = [
            c
            for c in JsonBenchmarkLoader(roots=[root], track=TRACK, validate=True).cases()
            if c.meta.get("scenario_type") == SCENARIO
        ]
    except BenchmarkValidationError as e:
        print(f"[중단] 벤치마크 검증 실패:\n{e}")
        return 1
    if not cases:
        print(f"[대기] {root} 에 track={TRACK} · scenario_type={SCENARIO} 케이스가 없다.")
        return 0

    records: list[dict[str, Any]] = []
    for case in cases:
        records.extend(run_case(case))

    import negmas

    ks = sorted({r["k"] for r in records if r["k"] is not None})
    families = sorted({c.family_id for c in cases if c.family_id})
    k_dist = {
        str(k): len({r["family_id"] for r in records if r["k"] == k}) for k in ks
    }
    raw: dict[str, Any] = {
        "meta": {
            "run_id": "",  # 저장 직전에 채운다
            "timestamp": datetime.now(KST).isoformat(timespec="seconds"),
            "measure": "Scalability-참여자 수 b_msg (25 §25.3-§25.6)",
            "input_kind": "static_benchmark_family",
            "cases_root": str(root.relative_to(ROOT) if root.is_relative_to(ROOT) else root),
            "n_cases": len(cases),
            "n_families": len(families),
            "n_sessions": len(records),
            "levels": sorted({r["n"] for r in records}),
            "k_distribution": {f"k={k}": f"family {v}개" for k, v in k_dist.items()},
            "python": sys.version.split()[0],
            "negmas_version": negmas.__version__,
            "load_skew_note": (
                "생략 — 노드별 처리 건수는 Blackboard.load 에만 있고 SessionResult 로 전달되지 "
                "않는다(protocol.py 의 run() 이 Blackboard 를 로컬로 유지). src 수정 없이는 "
                "얻을 수 없어 이번 측정에서는 산출하지 않았다."
            ),
            "caveat": (
                "케이스당 1회 실행 — 무작위성이 없는 결정론적 프로토콜이므로 반복은 같은 값을 준다. "
                "N 수준별 표본 수는 family 수와 같다."
            ),
        },
        "overall": analyse_all(records),
        "records": records,
    }

    if args.by_k:
        by_k: dict[str, Any] = {"order": ks}
        for p in PLAN_NAMES:
            by_k[p] = {
                str(k): analyse([r for r in records if r["plan"] == p and r["k"] == k]) for k in ks
            }
        sens: dict[str, Any] = {}
        for p in PLAN_NAMES:
            stars_by_k = {str(k): by_k[p][str(k)]["stars"] for k in ks}
            b_by_k = {str(k): by_k[p][str(k)]["b_msg"] for k in ks}
            bs = [v for v in b_by_k.values() if v is not None]
            sens[p] = {
                "stars_by_k": stars_by_k,
                "star_span": max(stars_by_k.values()) - min(stars_by_k.values()),
                "b_by_k": b_by_k,
                "b_span": round(max(bs) - min(bs), 4) if len(bs) > 1 else None,
            }
        by_k["sensitivity"] = sens
        raw["by_k"] = by_k

    raw["generator_reference"] = generator_reference()

    run_dir = out_dir()
    raw["meta"]["run_id"] = run_dir.name
    report = render(raw)
    run_dir.mkdir(parents=True)
    (run_dir / "raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    (run_dir / "report.md").write_text(report, encoding="utf-8")

    print(report)
    print(f"저장: {run_dir}/raw.json · {run_dir}/report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
