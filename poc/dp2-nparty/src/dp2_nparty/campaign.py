"""측정 캠페인 — 전 QA 측정을 실행해 raw 결과(dict)를 만든다.

원칙: 실행(여기)과 정리(report.py)를 분리한다 — raw.json만 있으면 리포트를
언제든 다시 만들 수 있고, 측정값의 정본 위치는 문서가 아니라 results/ 다.
"""
from __future__ import annotations

import random
import statistics
import subprocess
import sys
from datetime import datetime, timezone

from .domain import NO_DEAL
from .harness import Experiment, multi_issue_sweep, participants_sweep
from .measures import fc as fcmod
from .measures.confidentiality import exposure_rate, measure_gain, stars_exposure
from .measures.ru_memory import peak_memory_bytes
from .measures.scaling import (
    ci_spans_grades,
    completion_gate,
    loglog_fit,
    stars_b_msg,
    stars_c,
)
from .protocol import Plan1Vote, Plan2Cumulative
from .ufun_provider import TableUfun

PLANS = (("plan1", Plan1Vote), ("plan2", Plan2Cumulative))


def _meta(seed: int) -> dict:
    def _git(*args):
        try:
            return subprocess.run(
                ["git", *args], capture_output=True, text=True, timeout=10
            ).stdout.strip()
        except Exception:
            return "unknown"

    import negmas

    return {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": seed,
        "git_commit": _git("rev-parse", "--short", "HEAD"),
        "negmas_version": negmas.__version__,
        "python": sys.version.split()[0],
        "provider": "TableUfun/ControlledTableUfun/MultiIssueTableUfun (개발용 임시)",
        "caveat": "무작위 생성 프로파일 — 절대값은 잠정, 방안 간 상대 비교만 유효. 벤치마크 셋 도착 시 재실행.",
    }


def _fc_section(seed: int, runs: int) -> dict:
    out = Experiment(n_participants=3, n_candidates=12, runs=runs, seed=seed).run()
    sec: dict = {"config": {"n": 3, "candidates": 12, "runs": runs}}
    for plan, recs in out.items():
        mean_ratio = statistics.mean(r.fc.ratio for r in recs)
        mean_base = statistics.mean(r.fc.baseline for r in recs)
        s = (mean_ratio - mean_base) / (1 - mean_base) if mean_base < 1 else 1.0
        sec[plan] = {
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
            "ratios": [round(r.fc.ratio, 4) for r in recs],
        }
    return sec


def _ru_section(seed: int, runs: int) -> dict:
    """로그 수집을 끈 순수 협상 상태의 피크 메모리 — 기준 시나리오."""
    provider = TableUfun()
    peaks: dict[str, list[int]] = {p: [] for p, _ in PLANS}
    for i in range(runs):
        rng = random.Random((seed, 3, 12, i).__hash__())
        cands = [f"slot{j:02d}" for j in range(12)]
        profiles = provider.build_profiles(cands, 3, rng)
        for name, cls in PLANS:
            _, peak = peak_memory_bytes(lambda c=cls: c(profiles, collect_log=False).run())
            peaks[name].append(peak)
    return {
        "config": {"n": 3, "candidates": 12, "runs": runs, "note": "관찰 로그 제외(collect_log=False)"},
        **{
            p: {"median_peak_bytes": int(statistics.median(v)), "peaks": v}
            for p, v in peaks.items()
        },
    }


def _sc_participants_section(seed: int, runs: int) -> dict:
    sweep = participants_sweep(seed=seed, runs=runs)
    ns = sorted(sweep)
    sec: dict = {"config": {"levels": ns, "runs": runs, "provider": "ControlledTableUfun(k=3)"}}
    for plan in ("plan1", "plan2"):
        agreed = {n: sum(r.session.agreed for r in sweep[n][plan]) for n in ns}
        med = {}
        for n in ns:
            done = [r.session.messages for r in sweep[n][plan] if r.session.agreed]
            med[n] = statistics.median(done) if done else None
        gate = completion_gate(agreed[ns[0]], runs, agreed[ns[-1]], runs)
        xs = [n for n in ns if med[n] is not None]
        fit = loglog_fit(xs, [med[n] for n in xs])
        sec[plan] = {
            "agreed_by_n": {str(n): agreed[n] for n in ns},
            "median_messages_by_n": {str(n): med[n] for n in ns},
            "gate_ok": gate,
            "b_msg": round(fit.b, 4),
            "ci": [round(fit.ci_low, 4), round(fit.ci_high, 4)],
            "r2": round(fit.r2, 4),
            "stars": stars_b_msg(fit.b) if gate else 0,
            "ci_spans_3_grades": ci_spans_grades(fit),
        }
    return sec


def _sc_issues_section(seed: int, runs: int) -> dict:
    sweep = multi_issue_sweep(seed=seed, runs=runs)
    configs = list(sweep)
    import math

    sec: dict = {
        "config": {
            "levels": ["x".join(map(str, s)) for s in configs],
            "runs": runs,
            "note": "복합의제 튜플 곱집합 · 로그 제외 메모리 · 별점 기준 d=4 (27 §27.3)",
        }
    }
    ss = [int(math.prod(s)) for s in configs]
    for plan in ("plan1", "plan2"):
        med = {s: statistics.median(peak for _r, peak in sweep[s][plan]) for s in configs}
        agreed = sum(r.agreed for s in configs for r, _p in sweep[s][plan])
        total = sum(len(sweep[s][plan]) for s in configs)
        gate = completion_gate(
            sum(r.agreed for r, _p in sweep[configs[0]][plan]), len(sweep[configs[0]][plan]),
            sum(r.agreed for r, _p in sweep[configs[-1]][plan]), len(sweep[configs[-1]][plan]),
        )
        fit = loglog_fit(ss, [med[s] for s in configs])
        sec[plan] = {
            "median_peak_by_S": {str(int(math.prod(s))): int(med[s]) for s in configs},
            "agreed": f"{agreed}/{total}",
            "gate_ok": gate,
            "c": round(fit.b, 4),
            "ci": [round(fit.ci_low, 4), round(fit.ci_high, 4)],
            "r2": round(fit.r2, 4),
            "stars": stars_c(fit.b, d=4) if gate else 0,
        }
    return sec


def _cf_section(seed: int, runs: int, n_candidates: int = 12) -> dict:
    provider = TableUfun()
    sessions: dict[str, list] = {p: [] for p, _ in PLANS}
    for i in range(runs):
        rng = random.Random((seed, "cf", i).__hash__())
        cands = [f"slot{j:02d}" for j in range(n_candidates)]
        profiles = provider.build_profiles(cands, 3, rng)
        for name, cls in PLANS:
            sessions[name].append((cls(profiles).run(), profiles))
    sec: dict = {"config": {"n": 3, "candidates": n_candidates, "runs": runs}}
    for name in sessions:
        sec[name] = {}
        for vp in ("participant", "coordinator"):
            g = measure_gain(sessions[name], n_candidates, viewpoint=vp)
            rate = exposure_rate(g, n_candidates)
            sec[name][vp] = {
                "accuracy": round(g.accuracy, 4),
                "baseline": round(g.random_baseline, 4),
                "gain_pp": round(g.gain_pp, 2),
                "exposure_rate": round(rate, 4),
                "stars": stars_exposure(rate),
            }
    return sec


def run_all(seed: int = 20260811, scale: float = 1.0) -> dict:
    """전 QA 측정 실행 → raw dict. scale로 표본 크기를 일괄 축소(스모크용)할 수 있다."""
    n = lambda base: max(3, int(base * scale))
    return {
        "meta": _meta(seed),
        "fc": _fc_section(seed, n(100)),
        "ru_memory": _ru_section(seed, n(100)),
        "sc_participants": _sc_participants_section(seed, n(30)),
        "sc_issues": _sc_issues_section(seed, max(2, int(5 * scale))),
        "confidentiality": _cf_section(seed, n(100)),
    }
