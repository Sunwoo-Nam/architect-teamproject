"""통합 캠페인 — 확정 벤치마크 셋 기준으로 핸드북 전 항목을 한 실행·한 timestamp로 측정.

입력:
- §1 FC · §2 RU · §5 FT/REC · §6 TB · §7 CF → 정적 벤치마크 functional 트랙
- §3 SC-참여자 → 정적 벤치마크 scalability family 트랙
- §4 SC-의제 → 벤치마크 보류 상태라 개발용 multi-issue 생성으로 대체 (라벨 명시)

출력 raw dict의 키 구조는 campaign과 동일 — report.render_markdown·build_index가 그대로 동작한다.
"""
from __future__ import annotations

import statistics
from datetime import datetime

from .benchmark import BenchmarkCase, JsonBenchmarkLoader
from .campaign import KST, _meta, _sc_issues_section
from .domain import NO_DEAL
from .faults import FaultInjector
from .measures import fc as fcmod
from .measures import ft as ftmod
from .measures import rec as recmod
from .measures import tb as tbmod
from .measures.confidentiality import exposure_rate, measure_gain, stars_exposure
from .measures.ru_memory import peak_memory_bytes
from .measures.scaling import ci_spans_grades, completion_gate, loglog_fit, stars_b_msg
from .protocol import Plan1Vote, Plan2Cumulative, Plan20Batch

from .protocol import all_plans

PLANS = all_plans()


def _functional_cases() -> list[BenchmarkCase]:
    return sorted(JsonBenchmarkLoader(track="functional").cases(), key=lambda c: c.case_id)


def _scalability_cases() -> list[BenchmarkCase]:
    return sorted(JsonBenchmarkLoader(track="scalability").cases(), key=lambda c: c.case_id)


def _fc_section(cases: list[BenchmarkCase]) -> dict:
    sec: dict = {"config": {"cases": len(cases), "input": "벤치마크 functional",
                            "participants": sorted({len(c.profiles) for c in cases})}}
    for name, cls in PLANS:
        ratios, baselines = [], []
        agreed = opt = nd_ok = nd_bad = ties = 0
        rounds, phases, msgs, byts = [], [], [], []
        grp: dict[int, dict] = {}  # 참여자 수별 분해
        for case in cases:
            s = cls(case.profiles).run()
            f = fcmod.score(s.outcome, case.candidates, case.profiles)
            ratios.append(f.ratio)
            baselines.append(f.baseline)
            agreed += s.agreed
            opt += s.outcome == f.optimal
            nd_ok += s.outcome == NO_DEAL and f.optimal == NO_DEAL
            nd_bad += s.outcome == NO_DEAL and f.optimal != NO_DEAL
            ties += s.tie_break_used
            rounds.append(s.rounds); phases.append(s.phases)
            msgs.append(s.messages); byts.append(s.bytes)
            g = grp.setdefault(len(case.profiles), {"ratios": [], "baselines": [],
                                                    "agreed": 0, "opt": 0})
            g["ratios"].append(f.ratio); g["baselines"].append(f.baseline)
            g["agreed"] += s.agreed; g["opt"] += s.outcome == f.optimal
        mr, mb = statistics.mean(ratios), statistics.mean(baselines)
        sv = (mr - mb) / (1 - mb) if mb < 1 else 1.0
        by_p = {}
        for np_ in sorted(grp):
            g = grp[np_]
            gmr, gmb = statistics.mean(g["ratios"]), statistics.mean(g["baselines"])
            gs = (gmr - gmb) / (1 - gmb) if gmb < 1 else 1.0
            by_p[str(np_)] = {"cases": len(g["ratios"]), "mean_ratio": round(gmr, 4),
                              "mean_baseline": round(gmb, 4), "s": round(gs, 4),
                              "stars": fcmod.stars_from_s(gs),
                              "agreed": g["agreed"], "optimal_hit": g["opt"]}
        sec[name] = {
            "by_participants": by_p,
            "mean_ratio": round(mr, 4), "mean_baseline": round(mb, 4),
            "s": round(sv, 4), "stars": fcmod.stars_from_s(sv),
            "agreed": agreed, "optimal_hit": opt,
            "nodeal_correct": nd_ok, "nodeal_wrong": nd_bad, "tie_break_used": ties,
            "median_rounds": statistics.median(rounds),
            "median_phases": statistics.median(phases),
            "median_messages": statistics.median(msgs),
            "median_bytes": statistics.median(byts),
        }
    return sec


def _ru_section(cases: list[BenchmarkCase]) -> dict:
    import tracemalloc

    from .measures.ru_person import holder_sizes

    sec: dict = {"config": {"cases": len(cases), "input": "벤치마크 functional (3인)",
                            "note": "관찰 로그 제외 · 평균은 라운드 경계 표집 — Peak/Average RSS의 ENV-A 대체",
                            "person_note": "1인당·합계는 논리 상태의 귀속 계상(ru_person 모델) — "
                                           "복제 구조(mesh 등)의 비용을 반영. 프로세스 피크는 참고치"}}
    for name, cls in PLANS:
        peaks, avgs, person_peaks, total_peaks = [], [], [], []
        for case in cases:
            for prof in case.profiles:
                prof.clear_caches()
            tracemalloc.start(); tracemalloc.reset_peak()
            base, _ = tracemalloc.get_traced_memory()
            samples: list[int] = []
            cls(case.profiles, collect_log=False).run(
                on_round_end=lambda: samples.append(tracemalloc.get_traced_memory()[0] - base)
            )
            _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
            peaks.append(max(0, peak - base))
            avgs.append(statistics.mean(samples) if samples else 0.0)
            # 2차 실행(결정론 동일): 논리 상태의 1인당 귀속 표집 — tracemalloc 오염 방지 분리
            plan = cls(case.profiles, collect_log=False)
            pmax = [0] * len(case.profiles)
            tmax = [0]

            def _cb(plan=plan, pmax=pmax, tmax=tmax):
                sizes = holder_sizes(plan)
                tmax[0] = max(tmax[0], sum(sizes))
                for i, s in enumerate(sizes):
                    pmax[i] = max(pmax[i], s)

            plan.run(on_round_end=_cb)
            person_peaks.append(max(pmax) if pmax else 0)
            total_peaks.append(tmax[0])
        sec[name] = {"median_peak_bytes": int(statistics.median(peaks)),
                     "median_avg_bytes": int(statistics.median(avgs)),
                     "median_person_peak_bytes": int(statistics.median(person_peaks)),
                     "median_total_logical_bytes": int(statistics.median(total_peaks))}
    return sec


def _tb_section(cases: list[BenchmarkCase], constants: dict | None = None) -> dict:
    c = {**tbmod.DEFAULT_CONSTANTS, **(constants or {})}
    sec: dict = {"config": {"cases": len(cases), "constants": c, "input": "벤치마크 functional (3인)",
                            "note": "상수 3종은 잠정(분석자 제안) — ENV-B 실측 대체 예정. 상대 비교·지배 항 파악용"}}
    for name, cls in PLANS:
        ts = [tbmod.synth_time(cls(case.profiles, collect_log=False).run(), c) for case in cases]
        sec[name] = {
            "median_total_ms": round(statistics.median(t.total_ms for t in ts), 1),
            "median_rtt_ms": round(statistics.median(t.rtt_ms for t in ts), 1),
            "median_eval_ms": round(statistics.median(t.eval_ms for t in ts), 1),
            "median_transfer_ms": round(statistics.median(t.transfer_ms for t in ts), 1),
            "dominant": statistics.mode(t.dominant for t in ts),
        }
    return sec


def _ft_section(cases: list[BenchmarkCase], seed: int, p_env: float = 0.01) -> dict:
    multiples = [1, 2, 5, 10, 20, 50]
    sec: dict = {"config": {"p_env": p_env, "p_env_note": "잠정 (ENV-B 실측 대체 전)",
                            "multiples": multiples, "runs_base": len(cases), "runs_each": len(cases),
                            "input": "벤치마크 functional (3인)"}}
    for name, cls in PLANS:
        base_agreed = sum(cls(c.profiles, collect_log=False).run().agreed for c in cases)
        per: dict[float, tuple[int, int]] = {}
        for mlt in multiples:
            agreed = 0
            for i, case in enumerate(cases):
                inj = FaultInjector(p_env * mlt, (seed, name, mlt, i).__hash__())
                agreed += cls(case.profiles, collect_log=False).run(injector=inj).agreed
            per[mlt] = (agreed, len(cases))
        r = ftmod.evaluate(base_agreed, len(cases), per, p_env)
        sec[name] = {
            "baseline_agree_rate": round(base_agreed / len(cases), 4),
            "agree_rates": {str(k): round(v, 4) for k, v in r.agree_rates.items()},
            "critical_multiple": r.critical_multiple, "margin": r.margin, "stars": r.stars,
        }
    return sec


def _rec_section(cases: list[BenchmarkCase]) -> dict:
    sec: dict = {"config": {"sessions": len(cases), "input": "벤치마크 functional (3인) 선두 표본",
                            "note": "시간 대체 = phase 비용. 중단 유형(프로세스/네트워크)은 ENV-A에서 동일 취급"}}
    for name, cls in PLANS:
        points = ["mid_round", "pre_final"] + (["post_votes"] if name in ("plan1", "plan1a") else [])
        ratios, fr_fail, invalid, ref_rounds = [], 0, 0, []
        for case in cases:
            ref = cls(case.profiles).run()
            ref_rounds.append(ref.rounds)
            for point in points:
                for round_no in {2, max(1, ref.rounds // 2), ref.rounds}:
                    t = recmod.trial(cls, case.profiles, point, round_no)
                    if not t.fr_ok:
                        fr_fail += 1
                    elif t.ratio is None:
                        invalid += 1
                    else:
                        ratios.append(t.ratio)
        restart = statistics.median(ref_rounds) if ref_rounds else 1.0
        med = statistics.median(ratios) if ratios else None
        sec[name] = {
            "trials": len(ratios) + fr_fail + invalid, "fr_failures": fr_fail,
            "invalid_trials": invalid,
            "median_ratio": round(med, 3) if med is not None else None,
            "restart_cost_R": restart,
            "stars": recmod.stars_rec(med, restart) if med is not None else 0,
        }
    return sec


def _cf_section(cases: list[BenchmarkCase], scal_cases: list[BenchmarkCase]) -> dict:
    """CF — functional 3인 100건(정밀) + scalability 전 N(구조 차이 발현 구간).

    관점 정의: participant = P1 (트리 구조에서는 자식을 둔 내부 노드 — 비루트 최악 관찰자의
    보수적 대표), coordinator = P0 (담당자·루트·문서 시작점).
    """
    from .measures.cf_depth import e2_anchor, exposure_multiple

    n_cands = len(cases[0].candidates)
    by_n_groups: dict[int, list[BenchmarkCase]] = {}
    for c in scal_cases:
        by_n_groups.setdefault(len(c.profiles), []).append(c)
    e2 = e2_anchor(cases, Plan2Cumulative)  # 1:1 기준 노출량 — N=2 실측 앵커 (방안 무관 공통)
    sec: dict = {"config": {
        "e2": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in e2.items()},
        "m_note": "노출 배수 m = Σ관찰자 깊이 ÷ e₂ (핸드북 §7.3 — 별점 사다리는 잠정)",
        "cases": len(cases), "candidates": n_cands, "input": "벤치마크 functional (3인)",
        "by_n_levels": sorted(by_n_groups), "by_n_runs": len(next(iter(by_n_groups.values()))),
        "by_n_input": "벤치마크 scalability family (후보 4N)",
        "viewpoints": "participant=P1(트리에선 내부 노드 — 비루트 최악 관찰자) · coordinator=P0(담당자·루트)",
    }}
    for name, cls in PLANS:
        runs = [(cls(c.profiles).run(), c.profiles) for c in cases]
        sec[name] = {}
        for vp in ("participant", "coordinator"):
            g = measure_gain(runs, n_cands, viewpoint=vp)
            rate = exposure_rate(g, n_cands)
            sec[name][vp] = {"accuracy": round(g.accuracy, 4), "gain_pp": round(g.gain_pp, 2),
                             "exposure_rate": round(rate, 4), "stars": stars_exposure(rate)}
        sec[name]["multiple"] = exposure_multiple(runs, e2)  # 판정 지표 m (3인 정밀)
        by_n = {}
        for n in sorted(by_n_groups):
            grp = by_n_groups[n]
            nc = len(grp[0].candidates)
            gruns = [(cls(c.profiles).run(), c.profiles) for c in grp]
            entry = {}
            for vp in ("participant", "coordinator"):
                g = measure_gain(gruns, nc, viewpoint=vp)
                rate = exposure_rate(g, nc)
                entry[vp] = {"gain_pp": round(g.gain_pp, 2),
                             "exposure_rate": round(rate, 4), "stars": stars_exposure(rate)}
            entry["multiple"] = exposure_multiple(gruns, e2)
            by_n[str(n)] = entry
        sec[name]["by_n"] = by_n
    return sec


def _sc_participants_section(cases: list[BenchmarkCase]) -> dict:
    by_n: dict[int, list[BenchmarkCase]] = {}
    for c in cases:
        by_n.setdefault(len(c.profiles), []).append(c)
    ns = sorted(by_n)
    sec: dict = {"config": {"levels": ns, "runs": len(by_n[ns[0]]),
                            "provider": "정적 벤치마크 scalability family"}}
    from .measures.ru_person import holder_sizes
    from .measures.scaling import stars_b_mem, stars_n_max

    for name, cls in PLANS:
        agreed, med, med_b = {}, {}, {}
        med_r, med_mem, med_t = {}, {}, {}  # 라운드 · 피크 메모리 · 합성 지연시간
        med_person, fc_ratio = {}, {}  # 최대 부하 단말 피크(P_N) · FC 달성률 평균
        for n in ns:
            done, peaks, persons, ratios = [], [], [], []
            for c in by_n[n]:
                plan = cls(c.profiles, collect_log=False)
                s, peak = peak_memory_bytes(plan.run)
                done.append(s)
                peaks.append(peak)
                # P_N: 세션 종료 시점 상태로 근사 — 누적 구조(교집합·지식 집합)는 단조
                # 증가라 정확하고, 라운드 국소 구조는 근사 (핸드북 §3.3 명시)
                persons.append(max(holder_sizes(plan)))
                ratios.append(fcmod.score(s.outcome, c.candidates, c.profiles).ratio)
            agreed[n] = sum(s.agreed for s in done)
            fc_ratio[n] = statistics.mean(ratios)
            ok = [(s, pk, pp) for s, pk, pp in zip(done, peaks, persons) if s.agreed]
            med[n] = statistics.median(s.messages for s, _, _ in ok) if ok else None
            med_b[n] = statistics.median(s.bytes for s, _, _ in ok) if ok else None
            med_r[n] = statistics.median(s.rounds for s, _, _ in ok) if ok else None
            med_mem[n] = statistics.median(pk for _, pk, _ in ok) if ok else None
            med_person[n] = statistics.median(pp for _, _, pp in ok) if ok else None
            med_t[n] = statistics.median(tbmod.synth_time(s).total_ms for s, _, _ in ok) if ok else None
        gate = completion_gate(agreed[ns[0]], len(by_n[ns[0]]), agreed[ns[-1]], len(by_n[ns[-1]]))
        xs = [n for n in ns if med[n] is not None]
        fit = loglog_fit(xs, [med[n] for n in xs])
        # 판정 ② b_mem: P_N의 로그-로그 회귀 (핸드북 §3.3 — 완결률 게이트 준용)
        xm = [n for n in ns if med_person[n]]
        fit_mem = loglog_fit(xm, [med_person[n] for n in xm])
        # 판정 ① N_max: 오름차순 게이트 검사 — 완결률(N=3 대비) + FC 유지(하락 ≤ 0.05 잠정).
        # 자원 게이트(피크 ≤ 한도)는 실기기(ENV-B) 소관 — PoC 미적용 명시 (핸드북 §3.3).
        n_max = ns[0] if agreed[ns[0]] else 0
        for n in ns[1:]:
            comp_ok = completion_gate(agreed[ns[0]], len(by_n[ns[0]]), agreed[n], len(by_n[n]))
            fc_ok = fc_ratio[n] >= fc_ratio[ns[0]] - 0.05
            if comp_ok and fc_ok:
                n_max = n
            else:
                break
        sec[name] = {
            "agreed_by_n": {str(n): agreed[n] for n in ns},
            "median_messages_by_n": {str(n): med[n] for n in ns},
            "median_bytes_by_n": {str(n): med_b[n] for n in ns},
            "median_rounds_by_n": {str(n): med_r[n] for n in ns},
            "median_peak_bytes_by_n": {str(n): med_mem[n] for n in ns},
            "median_person_peak_by_n": {str(n): med_person[n] for n in ns},
            "median_time_ms_by_n": {str(n): med_t[n] for n in ns},
            "fc_ratio_by_n": {str(n): round(fc_ratio[n], 4) for n in ns},
            # b_msg는 보조 관측 (2026-08-12 강등 — 핸드북 §3.3-보조). 원자료 유지.
            "gate_ok": gate, "b_msg": round(fit.b, 4),
            "ci": [round(fit.ci_low, 4), round(fit.ci_high, 4)],
            "r2": round(fit.r2, 4),
            "stars": stars_b_msg(fit.b) if gate else 0,
            "ci_spans_3_grades": ci_spans_grades(fit),
            # 판정 2축 (경계 잠정 — 핸드북 §3.3)
            "n_max": n_max, "stars_n_max": stars_n_max(n_max),
            "b_mem": round(fit_mem.b, 4),
            "b_mem_ci": [round(fit_mem.ci_low, 4), round(fit_mem.ci_high, 4)],
            "b_mem_r2": round(fit_mem.r2, 4),
            "stars_b_mem": stars_b_mem(fit_mem.b) if gate else 0,
        }
    return sec


def resolve_plans(spec: str | None) -> list[str]:
    """--plans 인자 해석 — 방안 번호("2,6,10") 또는 내부 이름("plan2,plan6itree") 혼용 허용."""
    from .protocol import PLAN_NAMES

    if not spec:
        return list(PLAN_NAMES)
    by_number = {}
    for name in PLAN_NAMES:
        rest = name[4:]
        num = ""
        for ch in rest:
            if not ch.isdigit():
                break
            num += ch
        suffix = rest[len(num):]
        key = num + suffix if len(suffix) == 1 else num  # plan1a → "1a" (plan1과 구분)
        by_number[key] = name
    out = []
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        name = by_number.get(tok) or (tok if tok in PLAN_NAMES else None)
        if name is None:
            raise SystemExit(f"알 수 없는 방안: {tok!r} — 번호({', '.join(sorted(by_number, key=int))}) "
                             f"또는 이름({', '.join(PLAN_NAMES)}) 사용")
        if name not in out:
            out.append(name)
    return out


def run_full(seed: int = 20260811, plans: list[str] | None = None) -> dict:
    from . import campaign as _campaign

    selected = tuple((n, c) for n, c in all_plans() if plans is None or n in plans)
    # 부분 실행: 섹션들이 참조하는 모듈 전역을 실행 동안 치환 (단일 스레드 전제)
    global PLANS
    saved = (PLANS, _campaign.PLANS, _campaign.PLAN_NAMES)
    PLANS = selected
    _campaign.PLANS = selected
    _campaign.PLAN_NAMES = tuple(n for n, _c in selected)
    try:
        return _run_full_inner(seed, selected)
    finally:
        PLANS, _campaign.PLANS, _campaign.PLAN_NAMES = saved


def _run_full_inner(seed: int, selected) -> dict:
    functional = _functional_cases()
    f3 = [c for c in functional if len(c.profiles) == 3]
    scal = _scalability_cases()
    meta = _meta(seed)
    meta["run_id"] = "full-" + datetime.now(KST).strftime("%Y%m%dT%H%M%S") + "KST"
    meta["provider"] = "정적 벤치마크 셋 (functional·scalability) — §4 SC-의제만 개발용 대체"
    meta["plans"] = [n for n, _c in selected]
    if len(selected) != len(all_plans()):
        meta["caveat_plans"] = "부분 실행 — 선택된 방안만 측정됨 (--plans)"
    meta["caveat"] = (
        "입력은 확정 벤치마크 셋 (결정론 — 같은 입력이면 같은 결과). "
        "예외: §4 SC-의제는 벤치마크 보류 상태라 개발용 multi-issue 생성으로 대체 측정 (잠정), "
        "§5-1의 p_env·§6의 상수는 ENV-B 실측 대체 전의 잠정값."
    )
    return {
        "meta": meta,
        "fc": _fc_section(functional),
        "ru_memory": _ru_section(f3),
        "sc_participants": _sc_participants_section(scal),
        "sc_issues": _sc_issues_section(seed, 5),  # 벤치마크 보류 — 개발용 대체 (config note 참조)
        "tb": _tb_section(f3),
        "ft": _ft_section(f3, seed),
        "rec": _rec_section(f3[:10]),
        "confidentiality": _cf_section(f3, scal),
    }
