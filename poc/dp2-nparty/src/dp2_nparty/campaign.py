"""측정 캠페인 — 핸드북(docs/changbae/24)의 전 측정 항목을 실행해 raw dict를 만든다.

원칙: 실행(여기)과 정리(report.py)를 분리한다. 측정값의 정본 위치는 results/ 다.
"""
from __future__ import annotations

import random
import statistics
import subprocess
import sys
import tracemalloc
from datetime import datetime, timezone

from .domain import NO_DEAL
from .faults import FaultInjector
from .harness import Experiment, multi_issue_sweep, participants_sweep
from .measures import fc as fcmod
from .measures import ft as ftmod
from .measures import rec as recmod
from .measures import tb as tbmod
from .measures.confidentiality import exposure_rate, measure_gain, stars_exposure
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


def _base_profiles(seed: int, i: int, n: int = 3, m: int = 12):
    rng = random.Random((seed, n, m, i).__hash__())
    cands = [f"slot{j:02d}" for j in range(m)]
    return cands, TableUfun().build_profiles(cands, n, rng)


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
            "median_bytes": statistics.median(r.session.bytes for r in recs),
        }
    return sec


def _ru_section(seed: int, runs: int) -> dict:
    """[§2 대체] 순수 협상 상태의 피크·평균 메모리 (로그 제외, 라운드 경계 표집)."""
    peaks: dict[str, list[int]] = {p: [] for p, _ in PLANS}
    avgs: dict[str, list[float]] = {p: [] for p, _ in PLANS}
    for i in range(runs):
        _c, profiles = _base_profiles(seed, i)
        for name, cls in PLANS:
            tracemalloc.start()
            tracemalloc.reset_peak()
            base, _ = tracemalloc.get_traced_memory()
            samples: list[int] = []
            cls(profiles, collect_log=False).run(
                on_round_end=lambda: samples.append(tracemalloc.get_traced_memory()[0] - base)
            )
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peaks[name].append(max(0, peak - base))
            avgs[name].append(statistics.mean(samples) if samples else 0.0)
    return {
        "config": {"n": 3, "candidates": 12, "runs": runs,
                   "note": "관찰 로그 제외 · 평균은 라운드 경계 표집 — Peak/Average RSS의 ENV-A 대체"},
        **{
            p: {
                "median_peak_bytes": int(statistics.median(peaks[p])),
                "median_avg_bytes": int(statistics.median(avgs[p])),
            }
            for p, _ in PLANS
        },
    }


def _sc_participants_section(seed: int, runs: int) -> dict:
    sweep = participants_sweep(seed=seed, runs=runs)
    ns = sorted(sweep)
    sec: dict = {"config": {"levels": ns, "runs": runs, "provider": "ControlledTableUfun(k=3)"}}
    for plan in ("plan1", "plan2"):
        agreed = {n: sum(r.session.agreed for r in sweep[n][plan]) for n in ns}
        med, med_b = {}, {}
        for n in ns:
            done = [r.session for r in sweep[n][plan] if r.session.agreed]
            med[n] = statistics.median(s.messages for s in done) if done else None
            med_b[n] = statistics.median(s.bytes for s in done) if done else None
        gate = completion_gate(agreed[ns[0]], runs, agreed[ns[-1]], runs)
        xs = [n for n in ns if med[n] is not None]
        fit = loglog_fit(xs, [med[n] for n in xs])
        sec[plan] = {
            "agreed_by_n": {str(n): agreed[n] for n in ns},
            "median_messages_by_n": {str(n): med[n] for n in ns},
            "median_bytes_by_n": {str(n): med_b[n] for n in ns},
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
            "note": "복합의제 튜플 곱집합 · 로그 제외 메모리 · 별점 기준 d=4 (핸드북 §4.3)",
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


def _ft_section(seed: int, runs_base: int, runs_each: int, p_env: float = 0.01) -> dict:
    """[§5-1] 강도 스윕 — p_env는 ENV-B 실측 앵커 자리의 잠정값."""
    multiples = [1, 2, 5, 10, 20, 50]
    sec: dict = {"config": {"p_env": p_env, "p_env_note": "잠정 (ENV-B 실측 대체 전)",
                            "multiples": multiples, "runs_base": runs_base, "runs_each": runs_each}}
    for name, cls in PLANS:
        base_agreed = 0
        for i in range(runs_base):
            _c, profiles = _base_profiles(seed, i)
            base_agreed += cls(profiles, collect_log=False).run().agreed
        per: dict[float, tuple[int, int]] = {}
        for m in multiples:
            agreed = 0
            for i in range(runs_each):
                _c, profiles = _base_profiles(seed, i)
                inj = FaultInjector(p_env * m, (seed, name, m, i).__hash__())
                agreed += cls(profiles, collect_log=False).run(injector=inj).agreed
            per[m] = (agreed, runs_each)
        r = ftmod.evaluate(base_agreed, runs_base, per, p_env)
        sec[name] = {
            "baseline_agree_rate": round(base_agreed / runs_base, 4),
            "agree_rates": {str(k): round(v, 4) for k, v in r.agree_rates.items()},
            "critical_multiple": r.critical_multiple,
            "margin": r.margin,
            "stars": r.stars,
        }
    return sec


def _rec_section(seed: int, sessions: int) -> dict:
    """[§5-2] 중단-복구 그리드 — phase 비용 기반 대체 측정."""
    sec: dict = {"config": {"sessions": sessions,
                            "note": "시간 대체 = phase 비용. 중단 유형(프로세스/네트워크)은 ENV-A에서 동일 취급"}}
    for name, cls in PLANS:
        points = ["mid_round", "pre_final"] + (["post_votes"] if name == "plan1" else [])
        ratios, fr_fail, invalid = [], 0, 0
        ref_rounds = []
        for i in range(sessions):
            _c, profiles = _base_profiles(seed, i)
            ref = cls(profiles).run()
            ref_rounds.append(ref.rounds)
            for point in points:
                for round_no in {2, max(1, ref.rounds // 2), ref.rounds}:
                    t = recmod.trial(cls, profiles, point, round_no)
                    if not t.fr_ok:
                        fr_fail += 1
                    elif t.ratio is None:
                        invalid += 1
                    else:
                        ratios.append(t.ratio)
        restart_cost = statistics.median(ref_rounds) if ref_rounds else 1.0
        med = statistics.median(ratios) if ratios else None
        sec[name] = {
            "trials": len(ratios) + fr_fail + invalid,
            "fr_failures": fr_fail,
            "invalid_trials": invalid,
            "median_ratio": round(med, 3) if med is not None else None,
            "restart_cost_R": restart_cost,
            "stars": recmod.stars_rec(med, restart_cost) if med is not None else 0,
        }
    return sec


def _tb_section(seed: int, runs: int, constants: dict | None = None) -> dict:
    """[§6] 합성 시간 — T = phase×t_rtt + 평가×t_eval + bytes÷bw. 상수는 잠정(실측 대체 자리)."""
    c = {**tbmod.DEFAULT_CONSTANTS, **(constants or {})}
    sec: dict = {"config": {"n": 3, "candidates": 12, "runs": runs, "constants": c,
                            "note": "상수 3종은 잠정(분석자 제안) — ENV-B 실측으로 대체 예정. 절대값 아님, 상대 비교·지배 항 파악용"}}
    for name, cls in PLANS:
        times = []
        for i in range(runs):
            _cands, profiles = _base_profiles(seed, i)
            st = tbmod.synth_time(cls(profiles, collect_log=False).run(), c)
            times.append(st)
        med = statistics.median(t.total_ms for t in times)
        sec[name] = {
            "median_total_ms": round(med, 1),
            "median_rtt_ms": round(statistics.median(t.rtt_ms for t in times), 1),
            "median_eval_ms": round(statistics.median(t.eval_ms for t in times), 1),
            "median_transfer_ms": round(statistics.median(t.transfer_ms for t in times), 1),
            "dominant": statistics.mode(t.dominant for t in times),
        }
    return sec


def _cf_section(seed: int, runs: int, n_candidates: int = 12) -> dict:
    sessions: dict[str, list] = {p: [] for p, _ in PLANS}
    for i in range(runs):
        rng = random.Random((seed, "cf", i).__hash__())
        cands = [f"slot{j:02d}" for j in range(n_candidates)]
        profiles = TableUfun().build_profiles(cands, 3, rng)
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
                "gain_pp": round(g.gain_pp, 2),
                "exposure_rate": round(rate, 4),
                "stars": stars_exposure(rate),
            }
    return sec


def run_all(seed: int = 20260811, scale: float = 1.0) -> dict:
    """전 측정 실행 → raw dict. scale로 표본 크기를 일괄 축소(스모크용)."""
    n = lambda base: max(3, int(base * scale))
    return {
        "meta": _meta(seed),
        "fc": _fc_section(seed, n(100)),
        "ru_memory": _ru_section(seed, n(100)),
        "sc_participants": _sc_participants_section(seed, n(30)),
        "sc_issues": _sc_issues_section(seed, max(2, int(5 * scale))),
        "tb": _tb_section(seed, n(100)),
        "ft": _ft_section(seed, n(100), n(50)),
        "rec": _rec_section(seed, n(10)),
        "confidentiality": _cf_section(seed, n(100)),
    }
