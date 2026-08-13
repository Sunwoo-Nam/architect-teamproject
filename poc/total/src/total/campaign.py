"""실험 공통 캠페인 — 방안별 세션 묶음을 받아 QA 5종을 재고 결과를 조립한다.

실험(어느 도메인·어느 데이터셋)과 측정(QA 정의)을 가르는 층이다. 실험 스크립트는
"무엇을 몇 번 돌릴지"만 정하고, 여기서부터는 계약 타입만 다룬다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .qa import cf, fc, ru, sc_issue, tb
from .qa.constants import RU_CEILING_BYTES
from .qa.contract import Case, SessionResult, SweepPoint


@dataclass
class PlanRuns:
    """방안 1개의 실행 묶음."""

    plan: str
    label: str
    runs: list[tuple[SessionResult, Case]] = field(default_factory=list)
    #: 어댑터가 도메인 규칙으로 찾아낸 위반 (계약 밖 정보)
    violations: list[list[str]] = field(default_factory=list)
    #: SC-의제 스윕 — 규모를 바꿔가며 잰 점들
    sweep: list[SweepPoint] = field(default_factory=list)

    def add(self, session: SessionResult, case: Case, violations: Sequence[str] = ()) -> None:
        self.runs.append((session, case))
        self.violations.append(list(violations))


def measure(
    plans: Sequence[PlanRuns],
    *,
    e2: cf.E2Anchor | None,
    viewpoints: Sequence[cf.Viewpoint],
    d: int,
    ceiling_bytes: int = RU_CEILING_BYTES,
    tb_baselines: dict | None = None,
) -> tuple[dict, list[dict]]:
    """QA 5종 집계와 케이스별 행을 만든다. 반환 (raw, cases).

    측정할 자료가 없는 QA는 **조용히 0으로 채우지 않고 섹션을 비운다** — 리포트에서
    "안 쟀다"와 "0이다"가 구분되어야 한다.
    """
    raw: dict[str, dict] = {}
    rows: list[dict] = []

    for pr in plans:
        if not pr.runs:
            continue
        scores = [
            fc.score(case, session.agreement, extra_violations=v)
            for (session, case), v in zip(pr.runs, pr.violations)
        ]
        raw.setdefault("fc", {})[pr.plan] = fc.aggregate(scores)

        times = [tb.synth_time(s) for s, _ in pr.runs]
        raw.setdefault("tb", {})[pr.plan] = tb.aggregate(times)
        if tb_baselines:
            rhos = []
            for (session, case), t in zip(pr.runs, times):
                b = tb_baselines.get(getattr(case, "case_id", None))
                if b:
                    rhos.append(tb.rho(t.total_ms, b["T_ms"], b.get("capped", False)))
            if rhos:
                raw["tb"][pr.plan].update(tb.aggregate_rho(rhos))

        mems = [ru.measure(s, ceiling_bytes) for s, _ in pr.runs]
        raw.setdefault("ru", {})[pr.plan] = ru.aggregate(mems)

        if e2 is not None:
            raw.setdefault("cf", {})[pr.plan] = _flatten_cf(
                cf.evaluate(pr.runs, e2, viewpoints))

        if len(pr.sweep) >= 3 and len({p.scale for p in pr.sweep}) >= 3:
            raw.setdefault("sc_issue", {})[pr.plan] = _flatten_sc(
                sc_issue.evaluate(pr.sweep, d=d, memory_limit_bytes=ceiling_bytes))

        for (session, case), score, t, m in zip(pr.runs, scores, times, mems):
            rows.append({
                "plan": pr.plan,
                "case_id": getattr(case, "case_id", "?"),
                "n_participants": session.n,
                "n_issues": getattr(case, "n_issues", None),
                "agreed": session.agreed,
                "achieved": round(score.achieved, 6),
                "stars_achieved": score.stars_achieved,
                "s": round(score.s, 6),
                "fr_violations": score.fr_violations,
                "rounds": session.rounds,
                "phases": session.phases,
                "messages": session.messages,
                "bytes": session.bytes,
                "synth_ms": round(t.total_ms, 3),
                "dominant": t.dominant,
                "peak_mb": round(m.peak_mb, 4),
                "base_mb": round(m.base_mb, 4),
                "total_mb": round(m.total_mb, 4),
            })
    return raw, rows


def _flatten_cf(out: dict) -> dict:
    """리포트 표가 읽는 평평한 형태로. 원지표를 전부 보존한다."""
    flat = dict(out["multiple"])
    for name, vp in out["viewpoints"].items():
        for k, v in vp.items():
            flat[f"{name}_{k}"] = v
    flat["e2"] = out["e2"]
    flat["attacker"] = out["attacker"]
    return flat


def _flatten_sc(out: dict) -> dict:
    e, m, g = out["elasticity"], out["max_issues"], out["gate"]
    return {
        "c": e["c"], "ci_low": e["ci_low"], "ci_high": e["ci_high"], "r2": e["r2"],
        "stars_c": e["stars"], "ci_spans_three_grades": e["ci_spans_three_grades"],
        "max_issues": m["max_issues"], "stars_max_issues": m["stars"],
        "censored": m["censored"],
        "gate_ok": g["ok"], "gate_rate_small": g["rate_small"],
        "gate_rate_large": g["rate_large"],
        "defect": out["defect"], "d": out["d"],
        "bands": {"c": e["band"], "max_issues": m["band"]},
    }
