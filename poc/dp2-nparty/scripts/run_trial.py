"""임시 샘플(개발용 Ufun)로 두 방안을 돌려 QA 측정 결과를 뽑는 시험 실행.

주의: 프로파일이 무작위 생성이므로 절대 수치는 벤치마크 셋 도착 후 달라진다.
의미 있는 것은 **두 방안의 상대 비교**다.
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dp2_nparty.domain import NO_DEAL
from dp2_nparty.harness import Experiment, multi_issue_sweep, participants_sweep
from dp2_nparty.measures.confidentiality import measure_gain
from dp2_nparty.measures.fc import stars_from_s
from dp2_nparty.protocol import Plan1Vote, Plan2Cumulative
from dp2_nparty.ufun_provider import TableUfun
from dp2_nparty.measures.scaling import (
    ci_spans_grades,
    completion_gate,
    loglog_fit,
    stars_b_msg,
)

SEED = 20260811


def fmt(x, nd=3):
    return f"{x:.{nd}f}"


def section_fc():
    print("=" * 72)
    print("[1] Functional Correctness (24) — 3인·12후보·100회, 무통제 무작위 프로파일")
    print("=" * 72)
    out = Experiment(n_participants=3, n_candidates=12, runs=100, seed=SEED).run()
    for plan, recs in out.items():
        ratios = [r.fc.ratio for r in recs]
        baselines = [r.fc.baseline for r in recs]
        mean_ratio, mean_base = statistics.mean(ratios), statistics.mean(baselines)
        s_agg = (mean_ratio - mean_base) / (1 - mean_base) if mean_base < 1 else 1.0
        agreed = sum(r.session.agreed for r in recs)
        nodeal_correct = sum(
            1 for r in recs if r.session.outcome == NO_DEAL and r.fc.optimal == NO_DEAL
        )
        nodeal_wrong = sum(
            1 for r in recs if r.session.outcome == NO_DEAL and r.fc.optimal != NO_DEAL
        )
        ties = sum(r.session.tie_break_used for r in recs)
        optimal_hit = sum(1 for r in recs if r.session.outcome == r.fc.optimal)
        print(
            f"  {plan}: 달성률 평균 {fmt(mean_ratio)} (R̄ {fmt(mean_base)}) → s {fmt(s_agg)}"
            f" → 별점 {stars_from_s(s_agg)}점"
        )
        print(
            f"        합의 {agreed}/100 · x* 정확 도달 {optimal_hit}회 · 결렬(정답) {nodeal_correct}회"
            f" · 결렬(오답) {nodeal_wrong}회 · 동률해소 사용 {ties}회"
        )
        print(
            f"        라운드 중앙값 {statistics.median(r.session.rounds for r in recs):.0f}"
            f" · 직렬단계(phase) 중앙값 {statistics.median(r.session.phases for r in recs):.0f}"
            f" · 메시지 중앙값 {statistics.median(r.session.messages for r in recs):.0f}"
            f" · 피크메모리 중앙값 {statistics.median(r.peak_mem_bytes for r in recs)/1024:.1f} KiB"
        )
    return out


def section_scaling():
    print("=" * 72)
    print("[2] Scalability-참여자 수 (25) — N∈{3,4,5,6,8,10}·30회, 교락 통제(k=3) 프로파일")
    print("=" * 72)
    sweep = participants_sweep(seed=SEED, runs=30)
    ns = sorted(sweep)
    for plan in ("plan1", "plan2"):
        agreed_by_n = {n: sum(r.session.agreed for r in sweep[n][plan]) for n in ns}
        med_msgs = {}
        for n in ns:
            done = [r.session.messages for r in sweep[n][plan] if r.session.agreed]
            med_msgs[n] = statistics.median(done) if done else float("nan")
        gate_ok = completion_gate(agreed_by_n[3], 30, agreed_by_n[10], 30)
        xs = [n for n in ns if med_msgs[n] == med_msgs[n]]
        fit = loglog_fit(xs, [med_msgs[n] for n in xs])
        stars = stars_b_msg(fit.b) if gate_ok else 0
        print(f"  {plan}: 완결률 " + " ".join(f"N{n}:{agreed_by_n[n]}/30" for n in ns))
        print("        메시지 중앙값 " + " ".join(f"N{n}:{med_msgs[n]:.0f}" for n in ns))
        print(
            f"        게이트 {'통과' if gate_ok else '위반(0점)'}"
            f" · b_msg {fmt(fit.b)} [95% CI {fmt(fit.ci_low)}, {fmt(fit.ci_high)}]"
            f" R²={fmt(fit.r2)} → 별점 {stars}점"
            + (" (CI가 3등급 이상 — 표본 확대 필요)" if ci_spans_grades(fit) else "")
        )
    return sweep


def section_issues():
    print("=" * 72)
    print("[3] Scalability-의제 수 (21 §21.3-5) — 복합의제(multi-issue) 스윕, 3인·5회")
    print("    후보 = 의제 값 튜플의 곱집합 · utility = 의제별 점수 가중합(개발용 임시)")
    print("    의제 수 d 2→5, 조합 수 S 100→32,768 · 관찰 로그 제외한 순수 협상 메모리")
    print("=" * 72)
    sweep = multi_issue_sweep(seed=SEED, runs=5)
    configs = list(sweep)
    import math as _math

    ss = [int(_math.prod(sizes)) for sizes in configs]
    for plan in ("plan1", "plan2"):
        med_mem, agreed, med_rounds = {}, 0, {}
        total = 0
        for sizes in configs:
            pairs = sweep[sizes][plan]
            med_mem[sizes] = statistics.median(peak for _s, peak in pairs)
            med_rounds[sizes] = statistics.median(s.rounds for s, _p in pairs)
            agreed += sum(s.agreed for s, _p in pairs)
            total += len(pairs)
        fit = loglog_fit(ss, [med_mem[sizes] for sizes in configs])
        print(
            "  " + plan + ": 합의 " + f"{agreed}/{total}" + " · 피크메모리 중앙값(KiB) "
            + " ".join(
                f"d{len(sz)}/S{int(_math.prod(sz))}:{med_mem[sz]/1024:.0f}" for sz in configs
            )
        )
        print(
            "        라운드 중앙값 "
            + " ".join(f"S{int(_math.prod(sz))}:{med_rounds[sz]:.0f}" for sz in configs)
        )
        print(
            f"        탄력성 c {fmt(fit.b)} [95% CI {fmt(fit.ci_low)}, {fmt(fit.ci_high)}]"
            f" R²={fmt(fit.r2)} — 현 구조(순위표 전체 생성=전체 열거)의 베이스라인 기대값은 c≈1"
        )
    return sweep


def section_cf(runs: int = 100, n_candidates: int = 12):
    print("=" * 72)
    print("[5] Confidentiality (21 §21.3-9) — frequency 공격자, 3인·12후보·100회")
    print("    지표: 1순위 추정 정확도 − 무작위 기준선(1/12 = 8.3%) = 이득(%p)")
    print("=" * 72)
    import random as _random

    provider = TableUfun()
    sessions = {"plan1": [], "plan2": []}
    for i in range(runs):
        rng = _random.Random((SEED, "cf", i).__hash__())
        cands = [f"slot{j:02d}" for j in range(n_candidates)]
        profiles = provider.build_profiles(cands, 3, rng)
        for name, cls in (("plan1", Plan1Vote), ("plan2", Plan2Cumulative)):
            sessions[name].append((cls(profiles).run(), profiles))
    for name in ("plan1", "plan2"):
        for vp in ("participant", "coordinator"):
            g = measure_gain(sessions[name], n_candidates, viewpoint=vp)
            print(
                f"  {name} / 관찰자={vp:<11}: 정확도 {g.accuracy*100:5.1f}%"
                f"  이득 {g.gain_pp:+6.1f}%p  (21 목표선 참고: ≤ +10%p)"
            )


if __name__ == "__main__":
    print("시험 실행 — 개발용 무작위 Ufun (벤치마크 대체 전). seed =", SEED)
    print("[4] RU-메모리는 [1]의 피크메모리(프로세스 대체 측정)로 갈음한다.\n")
    section_fc()
    print()
    section_scaling()
    print()
    section_issues()
    print()
    section_cf()
