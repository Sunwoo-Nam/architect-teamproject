"""방안 1-A(SAO 투표형·무BB) vs 방안 2(누적형·BB) — 전체 벤치마크 2자 비교 실험.

이 스크립트만 두 방안을 4개 트랙(functional / scalability / issue-space A / issue-space B)
전부에 돌리고, 트랙·의제 수·참여자 수·조합 수로 분해한 대시보드를 낸다.

핵심 질문 (실험 가설):
    "전원 수락 가능 조합의 비율이 낮으면(A 트랙 ~0.5%) 두 방안의 1인 최대 메모리가 같아지고,
     비율이 높으면(B 트랙 ~5%) 갈린다."
분해 표로 이 가설을 검증한다 (맞든 틀리든 결과 그대로 싣는다).

사용:
    .venv/bin/python scripts/experiment_1a_vs_2.py                 # 전체 (수 시간·단일 프로세스)
    .venv/bin/python scripts/experiment_1a_vs_2.py --estimate      # 소요 추정만 (2건 시범)
    .venv/bin/python scripts/experiment_1a_vs_2.py --reps 3        # issue-space 반복 3개씩만

    # 코어 분산 실행 (측정값은 결정론이라 분할해도 동일 — 벽시계만 짧아진다)
    .venv/bin/python scripts/experiment_1a_vs_2.py --prepare --out results/exp-...
    .venv/bin/python scripts/experiment_1a_vs_2.py --shard 0/6 --out results/exp-...   # ×6 병렬
    .venv/bin/python scripts/experiment_1a_vs_2.py --report-only results/exp-...

출력: results/exp-1a-vs-2-<KST>/ 에 cases*.jsonl · raw.json · report.md · report.html

성능 주의 (실측 근거):
- holder_sizes()는 deep_size가 상태 전체를 재귀 순회하므로 **세션 종료 후 1회만** 호출한다.
  라운드마다 부르면 조합 6만 개에서 10분을 넘긴다.
- expand()는 케이스당 1회만 하고 두 방안이 결과를 공유한다.
- fc.score는 유효 후보 계산(후보 × 참여자 전수)을 매번 다시 한다. 그 부분은 케이스당 1회
  계산해 두 방안이 공유한다 — 동일성은 작은 트랙 전건에서 fc.score와 대조해 검증한다.
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
import tracemalloc
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dp2_nparty.benchmark import CASES_DIR, BenchmarkCase, JsonBenchmarkLoader  # noqa: E402
from dp2_nparty.domain import NO_DEAL  # noqa: E402
from dp2_nparty.html_report import _CSS, _stars  # noqa: E402
from dp2_nparty.issue_space import IssueSpaceLoader, expand  # noqa: E402
from dp2_nparty.measures import fc as fcmod  # noqa: E402
from dp2_nparty.measures import tb as tbmod  # noqa: E402
from dp2_nparty.measures.ru_person import holder_sizes  # noqa: E402
from dp2_nparty.protocol import PLAN_LABELS, all_plans  # noqa: E402

KST = timezone(timedelta(hours=9))

PLANS = ("plan1a", "plan2")
PLAN_CLS = {name: cls for name, cls in all_plans() if name in PLANS}
assert set(PLAN_CLS) == set(PLANS), f"방안 클래스를 찾지 못했다: {sorted(set(PLANS) - set(PLAN_CLS))}"

TRACKS = ("functional", "scalability", "issue_space_a", "issue_space_b")
TRACK_LABELS = {
    "functional": "functional (기능)",
    "scalability": "scalability (참여자 수)",
    "issue_space_a": "issue-space A (실후보 ~0.5%)",
    "issue_space_b": "issue-space B (실후보 ~5%)",
}

# 프로세스 피크(tracemalloc)는 실행을 2-4배 느리게 만든다. 큰 트랙에서는 셀당 앞 N건만 잰다.
PROC_PEAK_PER_CELL = 2


# ---------------------------------------------------------------- 케이스 수집


def _kst_now() -> datetime:
    return datetime.now(KST)


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, timeout=10,
                              cwd=ROOT).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


class CaseRef:
    """실행 전의 케이스 참조 — 무거운 전개는 run 직전에 한다."""

    def __init__(self, track: str, case_id: str, path: Path, dims: dict, rep: int):
        self.track = track
        self.case_id = case_id
        self.path = path
        self.dims = dims  # participants / issues / candidates / common_feasible / feasible_ratio
        self.rep = rep

    @property
    def cell(self) -> str:
        return f"{self.track}|p{self.dims['participants']}|i{self.dims['issues']}"

    def load(self) -> BenchmarkCase:
        if self.track in ("functional", "scalability"):
            from dp2_nparty.benchmark import load_case

            return load_case(self.path)
        from dp2_nparty.issue_space import load_issue_case

        return expand(load_issue_case(self.path))


def _flat_refs() -> list[CaseRef]:
    """작은 트랙 케이스 참조 — 검증은 로더에 맡기고 치수만 뽑는다."""
    refs: list[CaseRef] = []
    for track, root in (("functional", CASES_DIR / "functional"),
                        ("scalability", CASES_DIR / "scalability" / "participants")):
        for case in sorted(JsonBenchmarkLoader(roots=root, track=track).cases(),
                           key=lambda c: c.case_id):
            cf = case.meta.get("common_feasible_count")
            if cf is None:
                cf = len(case.feasible())
            n_cand = len(case.candidates)
            refs.append(CaseRef(
                track, case.case_id, root / f"{case.case_id}.json",
                {"participants": len(case.profiles), "issues": 1, "candidates": n_cand,
                 "common_feasible": cf, "feasible_ratio": cf / n_cand,
                 "family_id": case.family_id},
                rep=0,
            ))
    return refs


def _issue_refs() -> list[CaseRef]:
    """issue-space A·B 참조. 반복 번호(파일명 끝 3자리) 순으로 정렬해 두면 중단 시에도
    A·B·전 셀에 고르게 표본이 남는다."""
    refs: list[CaseRef] = []
    for track, folder in (("issue_space_a", "issue-space"), ("issue_space_b", "issue-space-b")):
        loader = IssueSpaceLoader(root=CASES_DIR / folder)
        for path in loader.paths():
            raw = json.loads(path.read_text(encoding="utf-8"))
            meta = raw["meta"]
            n_cand = int(meta["combination_count"])
            cf = int(meta["common_feasible_count"])
            tags = {t.split(":", 1)[0]: t.split(":", 1)[1] for t in (meta.get("tags") or [])
                    if ":" in t}
            refs.append(CaseRef(
                track, raw["case_id"], path,
                {"participants": int(tags.get("participants", len(raw["participants"]))),
                 "issues": int(tags.get("issues", len(raw["issues"]))),
                 "candidates": n_cand, "common_feasible": cf,
                 "feasible_ratio": float(tags.get("feasible_ratio", cf / n_cand)),
                 "family_id": None},
                rep=int(path.stem.rsplit("-", 1)[-1]),
            ))
    # 반복 번호 → 트랙 → 참여자 → 조합 순. 앞에서부터 잘라도 균형이 유지된다.
    refs.sort(key=lambda r: (r.rep, r.track, r.dims["participants"], r.dims["candidates"]))
    return refs


# ---------------------------------------------------------------- 측정


def fc_context(case: BenchmarkCase) -> dict:
    """fc.score의 케이스 의존 부분(유효 후보·x*·R̄)을 1회만 계산한다.

    fc.score(outcome, ...)는 호출마다 후보 × 참여자 전수를 다시 훑는다. 조합 13만 · 20인이면
    한 번에 260만 회다. 두 방안이 같은 케이스를 보므로 여기서 한 번 만들어 공유한다.
    """
    profiles = case.profiles
    valid = fcmod.valid_candidates(case.candidates, profiles)
    utils = {c: fcmod.total_utility(c, profiles) for c in valid}
    u_star_c = max(valid, key=lambda c: (utils[c], repr(c)))
    u_star = utils[u_star_c]
    baseline = sum(utils.values()) / len(valid) / u_star
    return {"u_star_c": u_star_c, "u_star": u_star, "baseline": baseline,
            "valid_count": len(valid)}


def fc_apply(ctx: dict, outcome, profiles) -> dict:
    ratio = fcmod.total_utility(outcome, profiles) / ctx["u_star"]
    b = ctx["baseline"]
    s = (ratio - b) / (1.0 - b) if b < 1.0 else 1.0
    return {"ratio": ratio, "baseline": b, "s": s, "stars": fcmod.stars_from_s(s),
            "optimal_hit": outcome == ctx["u_star_c"]}


def measure(plan_name: str, case: BenchmarkCase, ctx: dict, proc_peak: bool) -> dict:
    cls = PLAN_CLS[plan_name]
    for prof in case.profiles:
        prof.clear_caches()  # 두 방안이 순위표 구축 비용을 동일하게 지불하도록
    t0 = time.perf_counter()
    if proc_peak:
        tracemalloc.start()
        tracemalloc.reset_peak()
        base, _ = tracemalloc.get_traced_memory()
        plan = cls(case.profiles, collect_log=False)
        session = plan.run()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        proc_bytes = max(0, peak - base)
    else:
        plan = cls(case.profiles, collect_log=False)
        session = plan.run()
        proc_bytes = None
    wall = time.perf_counter() - t0
    sizes = holder_sizes(plan)  # 종료 후 1회 — 상태 누적분이 곧 최대치
    st = tbmod.synth_time(session)
    f = fc_apply(ctx, session.outcome, case.profiles)
    return {
        "agreed": bool(session.agreed),
        "ratio": round(f["ratio"], 6), "baseline": round(f["baseline"], 6),
        "s": round(f["s"], 6), "stars": f["stars"], "optimal_hit": bool(f["optimal_hit"]),
        "nodeal_correct": bool(session.outcome == NO_DEAL and ctx["u_star_c"] == NO_DEAL),
        "nodeal_wrong": bool(session.outcome == NO_DEAL and ctx["u_star_c"] != NO_DEAL),
        "tie_break_used": bool(session.tie_break_used),
        "rounds": session.rounds, "sweeps": session.sweeps,
        "messages": session.messages, "bytes": session.bytes,
        "phases": session.phases, "eval_calls": session.eval_calls,
        "person_peak_bytes": max(sizes) if sizes else 0,
        "total_logical_bytes": sum(sizes),
        "proc_peak_bytes": proc_bytes,
        "synth_ms": round(st.total_ms, 3), "synth_rtt_ms": round(st.rtt_ms, 3),
        "synth_eval_ms": round(st.eval_ms, 3), "synth_transfer_ms": round(st.transfer_ms, 3),
        "synth_dominant": st.dominant,
        "wall_s": round(wall, 3),
    }


def run_case(ref: CaseRef, proc_peak: bool, verify_fc: bool) -> dict:
    case = ref.load()
    ctx = fc_context(case)
    rec = {"case_id": ref.case_id, "track": ref.track, "rep": ref.rep,
           "dims": dict(ref.dims), "valid_count": ctx["valid_count"],
           "u_star_is_nodeal": ctx["u_star_c"] == NO_DEAL, "plans": {}}
    for name in PLANS:
        rec["plans"][name] = measure(name, case, ctx, proc_peak)
    if verify_fc:  # 공유 컨텍스트가 fc.score와 같은 값을 내는지 실제로 대조 (작은 트랙 전건)
        for name in PLANS:
            plan = PLAN_CLS[name](case.profiles, collect_log=False)
            s = plan.run()
            ref_score = fcmod.score(s.outcome, case.candidates, case.profiles)
            got = rec["plans"][name]
            # 기록값은 6자리 반올림 — 같은 반올림을 적용해 정확히 대조한다
            assert round(ref_score.ratio, 6) == got["ratio"], (
                ref.case_id, name, "ratio", ref_score.ratio, got["ratio"])
            assert round(ref_score.baseline, 6) == got["baseline"], (
                ref.case_id, name, "R̄", ref_score.baseline, got["baseline"])
            assert (s.outcome == ref_score.optimal) == got["optimal_hit"], (ref.case_id, name)
        rec["fc_verified"] = True
    return rec


# ---------------------------------------------------------------- 집계


def _med(xs):
    return statistics.median(xs) if xs else None


def _mean(xs):
    return statistics.mean(xs) if xs else None


def summarize(records: list[dict]) -> dict:
    """방안별 지표 묶음 — 트랙/셀 어디에나 같은 형태로 쓴다."""
    out: dict = {"cases": len(records)}
    for name in PLANS:
        rs = [r["plans"][name] for r in records if name in r["plans"]]
        if not rs:
            out[name] = None
            continue
        mr = _mean([x["ratio"] for x in rs])
        mb = _mean([x["baseline"] for x in rs])
        sv = (mr - mb) / (1 - mb) if mb is not None and mb < 1 else 1.0
        procs = [x["proc_peak_bytes"] for x in rs if x["proc_peak_bytes"] is not None]
        out[name] = {
            "cases": len(rs),
            "mean_ratio": round(mr, 6), "mean_baseline": round(mb, 6),
            "s": round(sv, 6), "stars": fcmod.stars_from_s(sv),
            "agreed": sum(x["agreed"] for x in rs),
            "optimal_hit": sum(x["optimal_hit"] for x in rs),
            "nodeal_correct": sum(x["nodeal_correct"] for x in rs),
            "nodeal_wrong": sum(x["nodeal_wrong"] for x in rs),
            "tie_break_used": sum(x["tie_break_used"] for x in rs),
            "median_rounds": _med([x["rounds"] for x in rs]),
            "median_sweeps": _med([x["sweeps"] for x in rs]),
            "median_messages": _med([x["messages"] for x in rs]),
            "median_bytes": _med([x["bytes"] for x in rs]),
            "median_phases": _med([x["phases"] for x in rs]),
            "median_eval_calls": _med([x["eval_calls"] for x in rs]),
            "median_person_peak_bytes": _med([x["person_peak_bytes"] for x in rs]),
            "max_person_peak_bytes": max(x["person_peak_bytes"] for x in rs),
            "median_total_logical_bytes": _med([x["total_logical_bytes"] for x in rs]),
            "median_proc_peak_bytes": _med(procs),
            "proc_peak_samples": len(procs),
            "median_synth_ms": _med([x["synth_ms"] for x in rs]),
            "median_synth_rtt_ms": _med([x["synth_rtt_ms"] for x in rs]),
            "median_synth_eval_ms": _med([x["synth_eval_ms"] for x in rs]),
            "median_synth_transfer_ms": _med([x["synth_transfer_ms"] for x in rs]),
            "dominant": statistics.mode([x["synth_dominant"] for x in rs]),
            "median_wall_s": _med([x["wall_s"] for x in rs]),
        }
    # 두 방안의 1인 최대 메모리가 케이스별로 완전히 같은 비율 (핵심 질문의 직접 증거)
    pair = [r for r in records if all(p in r["plans"] for p in PLANS)]
    same = sum(1 for r in pair
               if r["plans"]["plan1a"]["person_peak_bytes"] == r["plans"]["plan2"]["person_peak_bytes"])
    out["person_peak_identical"] = {"same": same, "of": len(pair)}
    ratios = [r["plans"]["plan2"]["person_peak_bytes"] / r["plans"]["plan1a"]["person_peak_bytes"]
              for r in pair if r["plans"]["plan1a"]["person_peak_bytes"] > 0]
    out["person_peak_ratio_2_over_1a"] = round(_med(ratios), 4) if ratios else None
    r_rounds = [r["plans"]["plan2"]["rounds"] / r["plans"]["plan1a"]["rounds"]
                for r in pair if r["plans"]["plan1a"]["rounds"] > 0]
    out["rounds_ratio_2_over_1a"] = round(_med(r_rounds), 4) if r_rounds else None
    return out


def group_by(records: list[dict], keyfn) -> dict:
    g: dict = {}
    for r in records:
        g.setdefault(keyfn(r), []).append(r)
    return {k: summarize(v) for k, v in sorted(g.items(), key=lambda kv: kv[0])}


def build_raw(records: list[dict], meta: dict, skipped: dict) -> dict:
    by_track = {t: [r for r in records if r["track"] == t] for t in TRACKS}
    raw: dict = {
        "meta": meta,
        "skipped": skipped,
        "overall": summarize(records),
        "by_track": {t: summarize(rs) for t, rs in by_track.items() if rs},
        "issue_by_issues": {},
        "issue_by_participants": {},
        "issue_by_combinations": {},
        "small_by_participants": {},
    }
    for t in ("issue_space_a", "issue_space_b"):
        rs = by_track.get(t) or []
        if not rs:
            continue
        raw["issue_by_issues"][t] = {
            str(k): v for k, v in group_by(rs, lambda r: r["dims"]["issues"]).items()}
        raw["issue_by_participants"][t] = {
            str(k): v for k, v in group_by(rs, lambda r: r["dims"]["participants"]).items()}
        raw["issue_by_combinations"][t] = {
            str(k): v for k, v in group_by(rs, lambda r: r["dims"]["candidates"]).items()}
    for t in ("functional", "scalability"):
        rs = by_track.get(t) or []
        if rs:
            raw["small_by_participants"][t] = {
                str(k): v for k, v in group_by(rs, lambda r: r["dims"]["participants"]).items()}
    return raw


# ---------------------------------------------------------------- 렌더 (HTML)


def _kib(v):
    return "-" if v is None else f"{v/1024:,.1f}"


def _mib(v):
    return "-" if v is None else f"{v/1048576:,.2f}"


def _n(v, d=0):
    return "-" if v is None else f"{v:,.{d}f}"


def _cmp_cells(vals: list, fmt, better: str) -> str:
    """두 방안 값을 나란히 놓고 더 나은 쪽에 win 클래스. better='low'|'high'|'none'."""
    defined = [v for v in vals if v is not None]
    win_idx = set()
    if better != "none" and len(defined) == len(vals) and len(set(defined)) > 1:
        target = min(defined) if better == "low" else max(defined)
        win_idx = {i for i, v in enumerate(vals) if v == target}
    return "".join(
        f'<td{" class=\"win\"" if i in win_idx else ""}><span class="num">{fmt(v)}</span></td>'
        for i, v in enumerate(vals))


def _row(label: str, vals: list, fmt, better: str, note: str = "") -> str:
    return f"<tr><td>{label}</td>{_cmp_cells(vals, fmt, better)}<td class='tie'>{note}</td></tr>"


def _pair_table(sections: list[tuple[str, list, object, str, str]]) -> str:
    head = "".join(f"<th>{PLAN_LABELS[p]}</th>" for p in PLANS)
    body = "".join(_row(*s) for s in sections)
    return f"<table><tr><th>지표</th>{head}<th>참고</th></tr>{body}</table>"


def _tbl(headers, rows) -> str:
    h = "".join(f"<th>{x}</th>" for x in headers)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><tr>{h}</tr>{b}</table>"


def _card(title, badge, badge_cls, sub, inner) -> str:
    return (f'<div class="card"><h2>{title}<span class="badge {badge_cls}">{badge}</span></h2>'
            f'<div class="sub">{sub}</div><div class="scroll">{inner}</div></div>')


def _g(sec, plan, key):
    d = (sec or {}).get(plan) or {}
    return d.get(key)


def render_html(raw: dict) -> str:
    m, sk = raw["meta"], raw["skipped"]
    bt = raw["by_track"]
    tracks = [t for t in TRACKS if t in bt]

    # ---- 카드 1: 종합
    rows = []
    for t in tracks:
        s = bt[t]
        rows.append(
            f"<tr><td><b>{TRACK_LABELS[t]}</b><br><span class='tie'>{s['cases']}건</span></td>"
            + _cmp_cells([_g(s, p, "mean_ratio") for p in PLANS], lambda v: _n(v, 4), "high")
            + _cmp_cells([_g(s, p, "median_person_peak_bytes") for p in PLANS], _kib, "low")
            + _cmp_cells([_g(s, p, "median_rounds") for p in PLANS], _n, "low")
            + _cmp_cells([_g(s, p, "median_synth_ms") for p in PLANS],
                         lambda v: "-" if v is None else f"{v/1000:,.1f}", "low")
            + "</tr>")
    ph = "".join(f"<th>{PLAN_LABELS[p]}</th>" for p in PLANS)
    summary = (f"<table><tr><th rowspan=2>트랙</th><th colspan=2>FC 달성률 (평균)</th>"
               f"<th colspan=2>1인 최대 메모리 (KiB·중앙)</th><th colspan=2>라운드 (중앙)</th>"
               f"<th colspan=2>합성 시간 (초·중앙)</th></tr><tr>{ph}{ph}{ph}{ph}</tr>"
               + "".join(rows) + "</table>")

    cards = [_card(
        "종합 — 트랙 4개 × 방안 2개 ", "초록 = 더 나은 쪽", "core",
        "달성률은 높을수록·나머지는 낮을수록 좋다. 값이 같으면 강조하지 않는다(= 차이 없음).",
        summary)]

    # ---- 카드 2: 트랙별 상세
    for t in tracks:
        s = bt[t]
        secs = [
            ("FC 달성률 평균", [_g(s, p, "mean_ratio") for p in PLANS], lambda v: _n(v, 4), "high",
             f"R̄ {_n(_g(s, PLANS[0], 'mean_baseline'), 4)}"),
            ("FC 개선비율 s · 별점", [_g(s, p, "s") for p in PLANS], lambda v: _n(v, 4), "high",
             " / ".join(_stars(_g(s, p, "stars") or 0) for p in PLANS)),
            ("x* 도달", [_g(s, p, "optimal_hit") for p in PLANS], _n, "high", f"/{s['cases']}건"),
            ("합의 성립", [_g(s, p, "agreed") for p in PLANS], _n, "high",
             "결렬 정답/오답 " + " · ".join(
                 f"{_g(s,p,'nodeal_correct')}/{_g(s,p,'nodeal_wrong')}" for p in PLANS)),
            ("동률 해소 사용", [_g(s, p, "tie_break_used") for p in PLANS], _n, "none", "건"),
            ("1인 최대 메모리 (KiB)", [_g(s, p, "median_person_peak_bytes") for p in PLANS],
             _kib, "low", "논리 상태 귀속 · 세션 종료 시점"),
            ("전원 합계 메모리 (KiB)", [_g(s, p, "median_total_logical_bytes") for p in PLANS],
             _kib, "low", "두 방안 모두 담당자 1인 보유 모델 → 1인 최대와 동일"),
            ("프로세스 피크 (KiB·참고)", [_g(s, p, "median_proc_peak_bytes") for p in PLANS],
             _kib, "low",
             f"tracemalloc 대체 측정 · 표본 {_g(s, PLANS[0], 'proc_peak_samples')}건"),
            ("라운드 수", [_g(s, p, "median_rounds") for p in PLANS], _n, "low", ""),
            ("바퀴(sweep) 수", [_g(s, p, "median_sweeps") for p in PLANS], _n, "low", ""),
            ("메시지 건수", [_g(s, p, "median_messages") for p in PLANS], _n, "low", ""),
            ("전송 바이트 (KiB)", [_g(s, p, "median_bytes") for p in PLANS], _kib, "low", ""),
            ("phase 수", [_g(s, p, "median_phases") for p in PLANS], _n, "low", ""),
            ("효용 평가 호출", [_g(s, p, "median_eval_calls") for p in PLANS], _n, "low", ""),
            ("합성 시간 (초)", [_g(s, p, "median_synth_ms") for p in PLANS],
             lambda v: "-" if v is None else f"{v/1000:,.2f}", "low",
             "지배 항 " + " / ".join(str(_g(s, p, "dominant")) for p in PLANS)),
            ("　└ 통신 / 평가 / 전송 (초)", [None, None], lambda v: "", "none",
             " · ".join(f"{PLAN_LABELS[p]}: "
                        f"{(_g(s,p,'median_synth_rtt_ms') or 0)/1000:.2f} / "
                        f"{(_g(s,p,'median_synth_eval_ms') or 0)/1000:.2f} / "
                        f"{(_g(s,p,'median_synth_transfer_ms') or 0)/1000:.3f}" for p in PLANS)),
            ("실행 벽시계 (초·참고)", [_g(s, p, "median_wall_s") for p in PLANS],
             lambda v: _n(v, 2), "none", "시뮬레이터 실행 시간 — 제품 성능 아님"),
        ]
        ident = s["person_peak_identical"]
        cards.append(_card(
            f"트랙 상세 — {TRACK_LABELS[t]}", f"{s['cases']}건", "aux",
            f"1인 최대 메모리가 케이스별로 <b>완전히 같은 경우 {ident['same']}/{ident['of']}건</b>"
            f" · 방안2÷방안1-A 메모리 비 중앙값 {s['person_peak_ratio_2_over_1a']}"
            f" · 라운드 비 중앙값 {s['rounds_ratio_2_over_1a']}",
            _pair_table(secs)))

    # ---- 카드 3: A vs B 대조 (핵심 질문)
    if "issue_space_a" in bt and "issue_space_b" in bt:
        A, B = bt["issue_space_a"], bt["issue_space_b"]
        metrics = [
            ("FC 달성률 평균", "mean_ratio", lambda v: _n(v, 4)),
            ("x* 도달 비율", "optimal_hit", lambda v: _n(v, 0)),
            ("1인 최대 메모리 (KiB)", "median_person_peak_bytes", _kib),
            ("라운드 수 (중앙)", "median_rounds", _n),
            ("메시지 건수 (중앙)", "median_messages", _n),
            ("phase 수 (중앙)", "median_phases", _n),
            ("합성 시간 (초·중앙)", "median_synth_ms", lambda v: "-" if v is None else f"{v/1000:,.2f}"),
        ]
        rows = []
        for label, key, fmt in metrics:
            a1, a2 = _g(A, "plan1a", key), _g(A, "plan2", key)
            b1, b2 = _g(B, "plan1a", key), _g(B, "plan2", key)

            def gap(x, y):
                if x in (None, 0) or y is None:
                    return "-"
                return f"{y/x:.2f}배"
            rows.append([label, fmt(a1), fmt(a2), gap(a1, a2), fmt(b1), fmt(b2), gap(b1, b2)])
        gap_tbl = _tbl(
            ["지표", f"A · {PLAN_LABELS['plan1a']}", f"A · {PLAN_LABELS['plan2']}", "A 배율(2÷1-A)",
             f"B · {PLAN_LABELS['plan1a']}", f"B · {PLAN_LABELS['plan2']}", "B 배율(2÷1-A)"],
            rows)
        idA, idB = A["person_peak_identical"], B["person_peak_identical"]
        verdict = raw["meta"].get("hypothesis_verdict", "")
        cards.append(_card(
            "A 트랙 대 B 트랙 — 난이도에 따라 갈리는가", "핵심 질문", "core",
            "가설: 전원 수락 가능 비율이 낮은 A에서는 두 방안의 메모리가 같아지고(점진형도 거의 전 조합을 훑으므로), "
            "비율이 높은 B에서는 갈린다.",
            f"<div class='caveat'>{verdict}</div>" + gap_tbl
            + "<h3>1인 최대 메모리가 두 방안에서 완전히 일치한 케이스</h3>"
            + _tbl(["트랙", "일치 건수", "메모리 비(2÷1-A) 중앙값", "라운드 비 중앙값"],
                   [["A (~0.5%)", f"{idA['same']}/{idA['of']}", A["person_peak_ratio_2_over_1a"],
                     A["rounds_ratio_2_over_1a"]],
                    ["B (~5%)", f"{idB['same']}/{idB['of']}", B["person_peak_ratio_2_over_1a"],
                     B["rounds_ratio_2_over_1a"]]])))

    # ---- 카드 4: 분해
    for title, key, axis in (("의제 수별", "issue_by_issues", "의제"),
                             ("참여자 수별", "issue_by_participants", "참여자"),
                             ("조합 수별", "issue_by_combinations", "조합")):
        blocks = []
        for t in ("issue_space_a", "issue_space_b"):
            grp = raw[key].get(t)
            if not grp:
                continue
            keys = sorted(grp, key=lambda k: int(k))
            rows = []
            for metric, mkey, fmt, better in (
                    ("FC 달성률", "mean_ratio", lambda v: _n(v, 4), "high"),
                    ("1인 최대 메모리 (KiB)", "median_person_peak_bytes", _kib, "low"),
                    ("라운드", "median_rounds", _n, "low"),
                    ("메시지", "median_messages", _n, "low"),
                    ("합성 시간(초)", "median_synth_ms",
                     lambda v: "-" if v is None else f"{v/1000:,.1f}", "low")):
                for p in PLANS:
                    rows.append([f"{metric} · {PLAN_LABELS[p]}"]
                                + [fmt(_g(grp[k], p, mkey)) for k in keys])
            blocks.append(f"<h3>{TRACK_LABELS[t]}</h3>"
                          + _tbl(["지표"] + [f"{axis} {k}" for k in keys], rows))
        if blocks:
            cards.append(_card(f"분해 — {title}", "issue-space", "aux",
                               "같은 지표를 축별로 갈라 추세를 본다.", "".join(blocks)))

    # ---- 카드 5: functional · scalability
    blocks = []
    for t in ("functional", "scalability"):
        grp = raw["small_by_participants"].get(t)
        if not grp:
            continue
        keys = sorted(grp, key=lambda k: int(k))
        rows = []
        for metric, mkey, fmt in (
                ("FC 달성률", "mean_ratio", lambda v: _n(v, 4)),
                ("x* 도달", "optimal_hit", _n),
                ("1인 최대 메모리 (KiB)", "median_person_peak_bytes", _kib),
                ("라운드", "median_rounds", _n),
                ("메시지", "median_messages", _n),
                ("phase", "median_phases", _n),
                ("바이트 (KiB)", "median_bytes", _kib),
                ("합성 시간(초)", "median_synth_ms",
                 lambda v: "-" if v is None else f"{v/1000:,.2f}")):
            for p in PLANS:
                rows.append([f"{metric} · {PLAN_LABELS[p]}"]
                            + [fmt(_g(grp[k], p, mkey)) for k in keys])
        blocks.append(f"<h3>{TRACK_LABELS[t]} (케이스 수: "
                      + " · ".join(f"N={k} {grp[k]['cases']}건" for k in keys) + ")</h3>"
                      + _tbl(["지표"] + [f"N={k}" for k in keys], rows))
    if blocks:
        cards.append(_card("functional · scalability — 참여자 수 3~50 추세", "소규모 트랙", "aux",
                           "후보 수는 참여자 1인당 4개(scalability) · functional은 12개 고정.",
                           "".join(blocks)))

    # ---- 카드 6: 실행 범위·건너뛴 것
    sk_rows = [[k, v] for k, v in sk.get("detail", {}).items()]
    cards.append(_card(
        "실행 범위와 건너뛴 케이스", "정직성", "sub",
        "조용히 빼지 않는다 — 계획 대비 실행/미실행을 전부 적는다.",
        _tbl(["트랙", "계획", "실행", "미실행", "사유"],
             [[TRACK_LABELS.get(t, t), sk["planned"].get(t, 0), sk["ran"].get(t, 0),
               sk["planned"].get(t, 0) - sk["ran"].get(t, 0),
               sk["reason"].get(t, "-")] for t in TRACKS])
        + ("<h3>기타</h3>" + _tbl(["항목", "내용"], sk_rows) if sk_rows else "")))

    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>방안 1-A vs 방안 2 — {m['run_id']}</title><style>{_CSS}</style></head><body><div class="wrap">
<h1>2자 비교 실험 — {PLAN_LABELS['plan1a']} vs {PLAN_LABELS['plan2']}</h1>
<div class="meta">실행 {m['timestamp']} · run_id <b>{m['run_id']}</b> · commit {m['git_commit']}
· python {m['python']} · negmas {m['negmas_version']}<br>
입력: 정적 벤치마크 {m['total_cases']}건 (functional {sk['ran'].get('functional',0)} ·
scalability {sk['ran'].get('scalability',0)} · issue-space A {sk['ran'].get('issue_space_a',0)} ·
issue-space B {sk['ran'].get('issue_space_b',0)}) · 총 실행 {m['elapsed_s']/60:.1f}분</div>
<div class="caveat">⚠ {m['caveat']}</div>
{''.join(cards)}
<footer>측정 정의: docs/changbae/24-QA-측정-핸드북.md · 원자료: raw.json · 케이스별 원시값: cases.jsonl · 자동 생성 문서</footer>
</div></body></html>"""


# ---------------------------------------------------------------- 렌더 (Markdown)


def render_markdown(raw: dict) -> str:
    m, sk, bt = raw["meta"], raw["skipped"], raw["by_track"]
    tracks = [t for t in TRACKS if t in bt]
    L = [f"# 2자 비교 실험 — {PLAN_LABELS['plan1a']} vs {PLAN_LABELS['plan2']}", "",
         f"- 실행: {m['timestamp']} · run_id `{m['run_id']}` · commit `{m['git_commit']}`",
         f"- 환경: python {m['python']} · negmas {m['negmas_version']} · 총 {m['elapsed_s']/60:.1f}분",
         f"- 입력: 정적 벤치마크 {m['total_cases']}건 (conformance 12건은 경계 사례라 제외)",
         f"- **주의**: {m['caveat']}", ""]

    L += ["## 종합 — 트랙 × 방안", "",
          "| 트랙 | 건수 | 방안 | FC 달성률 | 1인 최대 메모리 | 라운드 | 합성 시간 |",
          "|---|---|---|---|---|---|---|"]
    for t in tracks:
        s = bt[t]
        for p in PLANS:
            L.append(f"| {TRACK_LABELS[t]} | {s['cases']} | {PLAN_LABELS[p]} | "
                     f"{_n(_g(s,p,'mean_ratio'),4)} | {_kib(_g(s,p,'median_person_peak_bytes'))} KiB | "
                     f"{_n(_g(s,p,'median_rounds'))} | "
                     f"{(_g(s,p,'median_synth_ms') or 0)/1000:,.2f}s |")
    L.append("")

    for t in tracks:
        s = bt[t]
        ident = s["person_peak_identical"]
        L += [f"## 트랙 상세 — {TRACK_LABELS[t]} ({s['cases']}건)", "",
              f"1인 최대 메모리 완전 일치 {ident['same']}/{ident['of']}건 · "
              f"메모리 비(2÷1-A) {s['person_peak_ratio_2_over_1a']} · "
              f"라운드 비 {s['rounds_ratio_2_over_1a']}", "",
              "| 지표 | " + " | ".join(PLAN_LABELS[p] for p in PLANS) + " |",
              "|---|" + "---|" * len(PLANS)]
        for label, key, fmt in (
                ("FC 달성률 평균", "mean_ratio", lambda v: _n(v, 4)),
                ("R̄ (무작위 베이스라인)", "mean_baseline", lambda v: _n(v, 4)),
                ("개선비율 s", "s", lambda v: _n(v, 4)),
                ("별점", "stars", lambda v: "★" * int(v or 0) + "☆" * (5 - int(v or 0))),
                ("x* 도달", "optimal_hit", _n),
                ("합의 성립", "agreed", _n),
                ("결렬 정답", "nodeal_correct", _n),
                ("결렬 오답", "nodeal_wrong", _n),
                ("동률 해소 사용", "tie_break_used", _n),
                ("1인 최대 메모리 (KiB)", "median_person_peak_bytes", _kib),
                ("전원 합계 메모리 (KiB)", "median_total_logical_bytes", _kib),
                ("프로세스 피크 (KiB·참고)", "median_proc_peak_bytes", _kib),
                ("라운드 (중앙)", "median_rounds", _n),
                ("바퀴 (중앙)", "median_sweeps", _n),
                ("메시지 (중앙)", "median_messages", _n),
                ("바이트 KiB (중앙)", "median_bytes", _kib),
                ("phase (중앙)", "median_phases", _n),
                ("효용 평가 호출 (중앙)", "median_eval_calls", _n),
                ("합성 시간 초 (중앙)", "median_synth_ms",
                 lambda v: "-" if v is None else f"{v/1000:,.2f}"),
                ("지배 항", "dominant", lambda v: str(v)),
        ):
            L.append(f"| {label} | " + " | ".join(fmt(_g(s, p, key)) for p in PLANS) + " |")
        L.append("")

    if "issue_space_a" in bt and "issue_space_b" in bt:
        A, B = bt["issue_space_a"], bt["issue_space_b"]
        L += ["## A 트랙 대 B 트랙 — 핵심 질문", "",
              m.get("hypothesis_verdict", ""), "",
              "| 지표 | A·1-A | A·2 | A 배율 | B·1-A | B·2 | B 배율 |", "|---|---|---|---|---|---|---|"]
        for label, key, fmt in (
                ("FC 달성률", "mean_ratio", lambda v: _n(v, 4)),
                ("1인 최대 메모리 KiB", "median_person_peak_bytes", _kib),
                ("라운드", "median_rounds", _n),
                ("메시지", "median_messages", _n),
                ("phase", "median_phases", _n),
                ("합성 시간 초", "median_synth_ms",
                 lambda v: "-" if v is None else f"{v/1000:,.2f}")):
            a1, a2 = _g(A, "plan1a", key), _g(A, "plan2", key)
            b1, b2 = _g(B, "plan1a", key), _g(B, "plan2", key)
            r = lambda x, y: "-" if not x or y is None else f"{y/x:.2f}배"  # noqa: E731
            L.append(f"| {label} | {fmt(a1)} | {fmt(a2)} | {r(a1,a2)} | "
                     f"{fmt(b1)} | {fmt(b2)} | {r(b1,b2)} |")
        L.append("")

    for title, key, axis in (("의제 수별", "issue_by_issues", "의제"),
                             ("참여자 수별", "issue_by_participants", "참여자"),
                             ("조합 수별", "issue_by_combinations", "조합")):
        for t in ("issue_space_a", "issue_space_b"):
            grp = raw[key].get(t)
            if not grp:
                continue
            keys = sorted(grp, key=lambda k: int(k))
            L += [f"### 분해 {title} — {TRACK_LABELS[t]}", "",
                  "| 지표 | " + " | ".join(f"{axis} {k}" for k in keys) + " |",
                  "|---|" + "---|" * len(keys)]
            for metric, mkey, fmt in (
                    ("FC 달성률", "mean_ratio", lambda v: _n(v, 4)),
                    ("1인 최대 메모리 KiB", "median_person_peak_bytes", _kib),
                    ("라운드", "median_rounds", _n),
                    ("메시지", "median_messages", _n),
                    ("합성 시간 초", "median_synth_ms",
                     lambda v: "-" if v is None else f"{v/1000:,.1f}")):
                for p in PLANS:
                    L.append(f"| {metric} · {PLAN_LABELS[p]} | "
                             + " | ".join(fmt(_g(grp[k], p, mkey)) for k in keys) + " |")
            L.append("")

    for t in ("functional", "scalability"):
        grp = raw["small_by_participants"].get(t)
        if not grp:
            continue
        keys = sorted(grp, key=lambda k: int(k))
        L += [f"### {TRACK_LABELS[t]} — 참여자 수별", "",
              "| 지표 | " + " | ".join(f"N={k}" for k in keys) + " |",
              "|---|" + "---|" * len(keys)]
        for metric, mkey, fmt in (
                ("FC 달성률", "mean_ratio", lambda v: _n(v, 4)),
                ("1인 최대 메모리 KiB", "median_person_peak_bytes", _kib),
                ("라운드", "median_rounds", _n),
                ("메시지", "median_messages", _n),
                ("phase", "median_phases", _n),
                ("합성 시간 초", "median_synth_ms",
                 lambda v: "-" if v is None else f"{v/1000:,.2f}")):
            for p in PLANS:
                L.append(f"| {metric} · {PLAN_LABELS[p]} | "
                         + " | ".join(fmt(_g(grp[k], p, mkey)) for k in keys) + " |")
        L.append("")

    L += ["## 실행 범위와 건너뛴 케이스", "",
          "| 트랙 | 계획 | 실행 | 미실행 | 사유 |", "|---|---|---|---|---|"]
    for t in TRACKS:
        L.append(f"| {TRACK_LABELS[t]} | {sk['planned'].get(t,0)} | {sk['ran'].get(t,0)} | "
                 f"{sk['planned'].get(t,0)-sk['ran'].get(t,0)} | {sk['reason'].get(t,'-')} |")
    for k, v in sk.get("detail", {}).items():
        L.append("")
        L.append(f"- **{k}**: {v}")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------- 가설 판정


def hypothesis_verdict(raw: dict) -> str:
    bt = raw["by_track"]
    if "issue_space_a" not in bt or "issue_space_b" not in bt:
        return "A·B 트랙 중 하나가 실행되지 않아 핵심 질문을 판정할 수 없다."
    A, B = bt["issue_space_a"], bt["issue_space_b"]
    ra, rb = A["person_peak_ratio_2_over_1a"], B["person_peak_ratio_2_over_1a"]
    ia, ib = A["person_peak_identical"], B["person_peak_identical"]
    same_a = ia["same"] / ia["of"] if ia["of"] else 0.0
    same_b = ib["same"] / ib["of"] if ib["of"] else 0.0
    if ra is None or rb is None:
        return "메모리 비를 계산할 표본이 없어 판정 불가."
    lead = (f"가설: 실후보 비율이 낮은 A에서는 두 방안의 1인 최대 메모리가 같아지고, 높은 B에서는 갈린다. "
            f"실측 — A 트랙 메모리 비(방안2÷방안1-A) 중앙값 <b>{ra}배</b> "
            f"(두 방안 값이 완전히 같은 케이스 {ia['same']}/{ia['of']}건), "
            f"B 트랙 <b>{rb}배</b> (완전 일치 {ib['same']}/{ib['of']}건). ")
    a_same = abs(ra - 1.0) <= 0.05 and same_a >= 0.8
    b_split = rb >= 1.5 or same_b <= 0.2
    if a_same and b_split:
        tail = ("→ <b>가설 성립</b>. A에서는 두 방안의 1인 최대 메모리가 사실상 같고, B에서 갈렸다.")
    elif a_same and not b_split:
        tail = ("→ <b>가설 절반만 성립</b>. A에서는 예상대로 같아졌으나, B에서도 기대만큼 갈리지 않았다.")
    elif not a_same and b_split:
        direction = ("A가 B보다 격차가 <b>더 크다</b>" if ra > rb else
                     "B가 A보다 격차가 더 크다" if rb > ra else "두 트랙의 격차가 같다")
        tail = (f"→ <b>가설 기각</b>. A에서도 두 방안의 메모리는 같아지지 않았다 — 두 트랙 모두 "
                f"방안 2가 방안 1-A보다 크게 많이 들고 있으며, {direction}. "
                "즉 실후보 비율이 낮아진다고 두 방안이 수렴하지 않는다: 방안 1-A는 "
                "라운드마다 <b>그 라운드의 후보 집합만</b> 판정하고 담당자에게 남는 누적이 작은 반면, "
                "방안 2는 교집합 판정을 위해 전원의 제안을 계속 누적하기 때문이다.")
    else:
        tail = ("→ <b>가설 기각</b>. A에서도 같아지지 않았고 B에서도 갈리지 않았다 — "
                "난이도(실후보 비율)는 두 방안의 메모리 관계를 뒤집지 못한다.")
    return lead + tail


# ---------------------------------------------------------------- 메인


def main() -> None:
    ap = argparse.ArgumentParser(description="방안 1-A vs 방안 2 전체 벤치마크 비교")
    ap.add_argument("--reps", type=int, default=10,
                    help="issue-space 셀당 반복 케이스 수 (기본 10 = 전건)")
    ap.add_argument("--estimate", action="store_true",
                    help="시범 2건으로 전체 소요를 추정하고 종료")
    ap.add_argument("--skip-small", action="store_true", help="functional·scalability 건너뜀")
    ap.add_argument("--skip-issue", action="store_true", help="issue-space 건너뜀")
    ap.add_argument("--out", default=None, help="출력 폴더 (기본: results/exp-1a-vs-2-<KST>)")
    ap.add_argument("--report-only", default=None,
                    help="지정 폴더의 cases*.jsonl 을 합쳐 다시 집계해 리포트를 낸다")
    ap.add_argument("--prepare", action="store_true",
                    help="폴더와 _runmeta.json만 만들고 종료 (분산 실행 준비)")
    ap.add_argument("--shard", default=None,
                    help="'i/k' — 전체 케이스를 k등분한 i번째만 실행. 결과는 cases-shard<i>.jsonl")
    args = ap.parse_args()

    if args.report_only:
        out = Path(args.report_only)
        recs, seen = [], set()
        for f in sorted(out.glob("cases*.jsonl")):
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                if (r["track"], r["case_id"]) in seen:
                    continue
                seen.add((r["track"], r["case_id"]))
                recs.append(r)
        recs.sort(key=lambda r: (TRACKS.index(r["track"]), r["case_id"]))
        finish(out, recs, json.loads((out / "_runmeta.json").read_text(encoding="utf-8")))
        return

    small = [] if args.skip_small else _flat_refs()
    issue = [] if args.skip_issue else [r for r in _issue_refs() if r.rep <= args.reps]
    planned_all = _flat_refs() if not args.skip_small else []
    planned_issue_all = _issue_refs() if not args.skip_issue else []

    if args.estimate:
        estimate(small, issue)
        return

    stamp = _kst_now()
    out = Path(args.out) if args.out else ROOT / "results" / (
        "exp-1a-vs-2-" + stamp.strftime("%Y%m%dT%H%M%S") + "KST")
    out.mkdir(parents=True, exist_ok=True)

    meta_path = out / "_runmeta.json"
    if meta_path.exists():
        runmeta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        import negmas

        runmeta = {
            "run_id": out.name, "timestamp": stamp.isoformat(timespec="seconds"),
            "git_commit": _git("rev-parse", "--short", "HEAD"),
            "python": sys.version.split()[0], "negmas_version": negmas.__version__,
            "planned": {t: sum(1 for r in (planned_all + planned_issue_all) if r.track == t)
                        for t in TRACKS},
            "reps": args.reps,
        }
        meta_path.write_text(json.dumps(runmeta, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.prepare:
        print(f"[준비] {out}", file=sys.stderr, flush=True)
        return

    refs = small + issue
    tag = ""
    if args.shard:
        i, k = (int(x) for x in args.shard.split("/"))
        # 정렬이 (반복, 트랙, 참여자, 조합) 순이라 나머지 분할이면 각 샤드에 비싼/싼 케이스가 고루 섞인다
        refs = [r for j, r in enumerate(refs) if j % k == i]
        tag = f"-shard{i}"
    jsonl = out / f"cases{tag}.jsonl"
    jsonl.write_text("", encoding="utf-8")

    print(f"[시작{tag}] {len(refs)}건 · 출력 {out}", file=sys.stderr, flush=True)
    t_start = time.perf_counter()
    records: list[dict] = []
    with jsonl.open("a", encoding="utf-8") as fh:
        for i, ref in enumerate(refs, 1):
            big = ref.track.startswith("issue_space")
            # 반복 번호로 고르므로 샤드를 몇 개로 쪼개든 셀당 표본 수가 같다
            proc_peak = (not big) or ref.rep <= PROC_PEAK_PER_CELL
            rec = run_case(ref, proc_peak=proc_peak, verify_fc=not big)
            records.append(rec)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            el = time.perf_counter() - t_start
            if i % 20 == 0 or big or i == len(refs):
                eta = el / i * (len(refs) - i)
                print(f"  [{i}/{len(refs)}] {ref.case_id} ({ref.track}) "
                      f"1a={rec['plans']['plan1a']['wall_s']:.1f}s "
                      f"2={rec['plans']['plan2']['wall_s']:.1f}s | "
                      f"경과 {el/60:.1f}분 · 잔여 추정 {eta/60:.1f}분",
                      file=sys.stderr, flush=True)
    el = round(time.perf_counter() - t_start, 1)
    print(f"[끝{tag}] {len(records)}건 · {el/60:.1f}분", file=sys.stderr, flush=True)
    if args.shard:  # 샤드는 집계하지 않는다 — 끝난 뒤 --report-only 로 합친다
        (out / f"_elapsed{tag}.json").write_text(json.dumps({"elapsed_s": el}), encoding="utf-8")
        return
    runmeta["elapsed_s"] = el
    (out / "_runmeta.json").write_text(json.dumps(runmeta, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    finish(out, records, runmeta)


def estimate(small: list[CaseRef], issue: list[CaseRef]) -> None:
    """시범 실행으로 전체 소요를 추정해 stderr에 낸다 (실행 전 필수 절차).

    issue-space 비용은 참여자 수와 조합 수에 따라 자릿수가 달라진다. 그래서 A 트랙의
    네 모서리 셀(참여자 10·20 × 조합 최소·최대)만 1건씩 재고 cost = C·p^α·s^β 를
    정확 적합해 나머지 셀에 외삽한다 (2×2 설계 = 미지수 3개 + 검산 1점).
    """
    import math

    print("[추정] 시범 실행으로 케이스당 비용을 재고 전체를 외삽한다.", file=sys.stderr, flush=True)
    t_small = 0.0
    for ref in small[:2]:
        t0 = time.perf_counter()
        run_case(ref, proc_peak=True, verify_fc=True)
        dt = time.perf_counter() - t0
        t_small = max(t_small, dt)
        print(f"  {ref.case_id} ({ref.track}) {dt:.3f}s", file=sys.stderr, flush=True)

    a = [r for r in issue if r.track == "issue_space_a"]
    if not a:
        print("[추정] issue-space 표본 없음", file=sys.stderr, flush=True)
        return
    ps = sorted({r.dims["participants"] for r in a})
    ss = sorted({r.dims["candidates"] for r in a})
    corners = [(ps[0], ss[0]), (ps[0], ss[-1]), (ps[-1], ss[0]), (ps[-1], ss[-1])]
    obs: dict[tuple, float] = {}
    for p, s in corners:
        ref = next(r for r in a if r.dims["participants"] == p and r.dims["candidates"] == s)
        t0 = time.perf_counter()
        run_case(ref, proc_peak=False, verify_fc=False)
        obs[(p, s)] = time.perf_counter() - t0
        print(f"  {ref.case_id} (p={p}, 조합={s:,}) {obs[(p,s)]:.1f}s", file=sys.stderr, flush=True)

    lp = math.log(ps[-1] / ps[0])
    lsz = math.log(ss[-1] / ss[0])
    alpha = (math.log(obs[(ps[-1], ss[0])] / obs[(ps[0], ss[0])])
             + math.log(obs[(ps[-1], ss[-1])] / obs[(ps[0], ss[-1])])) / (2 * lp)
    beta = (math.log(obs[(ps[0], ss[-1])] / obs[(ps[0], ss[0])])
            + math.log(obs[(ps[-1], ss[-1])] / obs[(ps[-1], ss[0])])) / (2 * lsz)
    C = statistics.mean(v / (p ** alpha * s ** beta) for (p, s), v in obs.items())
    print(f"  적합: 비용 ≈ {C:.3g} · 참여자^{alpha:.2f} · 조합^{beta:.2f}", file=sys.stderr, flush=True)

    total = t_small * len(small)
    print(f"  → 소규모 트랙 {len(small)}건 × ~{t_small:.2f}s ≈ {total/60:.1f}분",
          file=sys.stderr, flush=True)
    cells: dict[tuple, int] = {}
    for r in issue:
        cells[(r.track, r.dims["participants"], r.dims["candidates"])] = \
            cells.get((r.track, r.dims["participants"], r.dims["candidates"]), 0) + 1
    for (tr, p, s), n in sorted(cells.items()):
        c = C * p ** alpha * s ** beta
        total += c * n
        print(f"  → {tr} p={p} 조합={s:,}: {n}건 × {c:.0f}s ≈ {c*n/60:.1f}분",
              file=sys.stderr, flush=True)
    print(f"[추정] 단일 프로세스 전체 ≈ {total/60:.0f}분 "
          f"(6샤드 병렬이면 벽시계 ≈ {total/60/6:.0f}분 + tracemalloc 표본 추가분)",
          file=sys.stderr, flush=True)


def finish(out: Path, records: list[dict], runmeta: dict) -> None:
    if "elapsed_s" not in runmeta:  # 분산 실행 — 벽시계는 가장 늦게 끝난 샤드, CPU 시간은 합
        els = [json.loads(p.read_text())["elapsed_s"] for p in out.glob("_elapsed*.json")]
        runmeta["elapsed_s"] = max(els) if els else 0.0
        runmeta["cpu_elapsed_s"] = round(sum(els), 1)
        runmeta["shards"] = len(els)
    ran = {t: sum(1 for r in records if r["track"] == t) for t in TRACKS}
    planned = runmeta.get("planned", ran)
    reason = {}
    for t in TRACKS:
        miss = planned.get(t, 0) - ran.get(t, 0)
        reason[t] = "없음 (전건 실행)" if miss == 0 else (
            f"시간 예산 — 셀당 반복 {runmeta.get('reps')}건까지만 실행 "
            f"(반복 번호 순으로 A·B·전 셀 균형 유지)")
    skipped = {
        "planned": planned, "ran": ran, "reason": reason,
        "detail": {
            "conformance 트랙 12건": "지시대로 제외 — 경계 사례 모음이라 통계 표본이 아니다.",
            "프로세스 피크(tracemalloc)": (
                f"issue-space는 셀당 앞 {PROC_PEAK_PER_CELL}건만 측정 "
                "(tracemalloc이 실행을 수 배 느리게 만들어 전건은 예산을 초과한다). "
                "functional·scalability는 전건 측정. 1인 최대·전원 합계(holder_sizes)는 전건 측정."),
            "FC 공유 계산": (
                "유효 후보·x*·R̄는 케이스당 1회 계산해 두 방안이 공유한다. "
                "동일성은 functional·scalability 전건에서 fc.score와 값 대조로 검증했다."),
            "분해 축의 출처": (
                "B 트랙은 meta.tags(track/issues/participants/feasible_ratio)를 그대로 썼다. "
                "A 트랙은 meta.tags가 전건 null이라 케이스 본문에서 같은 값을 계산했다 — "
                "의제 수 = len(issues), 참여자 수 = len(participants), "
                "실후보 비율 = meta.common_feasible_count ÷ meta.combination_count."),
            "1인 최대 = 전원 합계인 이유": (
                "ru_person의 귀속 모델에서 plan1a·plan2 모두 '담당자 P0가 누적 전체 보유, "
                "일반 참여자 ≈ 0'이다. 복제 구조가 없으므로 두 값이 같게 나온다 — 측정 오류가 아니다."),
        },
    }
    raw = build_raw(records, {
        **runmeta,
        "total_cases": len(records),
        "plans": list(PLANS),
        "caveat": ("합성 시간은 잠정 상수(RTT 50ms · 평가 20ms · 1Mbps)의 상대 비교용이다. "
                   "메모리는 논리 상태의 귀속 계상(ru_person 모델)이며 실기기 RSS가 아니다. "
                   "두 방안 모두 담당자 1인 보유 모델이라 1인 최대와 전원 합계가 같다."),
        "elapsed_s": runmeta.get("elapsed_s", 0.0),
    }, skipped)
    raw["meta"]["hypothesis_verdict"] = hypothesis_verdict(raw)
    (out / "raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "report.md").write_text(render_markdown(raw), encoding="utf-8")
    (out / "report.html").write_text(render_html(raw), encoding="utf-8")
    print(f"[완료] {out}/raw.json · report.md · report.html", file=sys.stderr, flush=True)
    print(raw["meta"]["hypothesis_verdict"], file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
