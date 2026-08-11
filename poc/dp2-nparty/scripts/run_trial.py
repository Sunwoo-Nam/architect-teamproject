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
from dp2_nparty.harness import Experiment, issues_sweep, participants_sweep
from dp2_nparty.measures.fc import stars_from_s
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
    print("[3] Scalability-의제 수 대체 스윕 (21 §21.3-5) — 후보 수 {8..128}·3인·10회")
    print("    (의제 조합 구조는 벤치마크 셋 도착 후 — 여기서는 후보 수 확장의 메모리 탄력성)")
    print("=" * 72)
    sweep = issues_sweep(seed=SEED, runs=10)
    ms = sorted(sweep)
    for plan in ("plan1", "plan2"):
        med_mem = {m: statistics.median(r.peak_mem_bytes for r in sweep[m][plan]) for m in ms}
        fit = loglog_fit(ms, [med_mem[m] for m in ms])
        print("  " + plan + ": 피크메모리 중앙값(KiB) " + " ".join(f"M{m}:{med_mem[m]/1024:.0f}" for m in ms))
        print(
            f"        탄력성 c {fmt(fit.b)} [95% CI {fmt(fit.ci_low)}, {fmt(fit.ci_high)}]"
            f" R²={fmt(fit.r2)} (판정 기준: CI 상한 < 1 — 전체 열거 기각)"
        )
    return sweep


if __name__ == "__main__":
    print("시험 실행 — 개발용 무작위 Ufun (벤치마크 대체 전). seed =", SEED)
    print("[4] RU-메모리는 [1]의 피크메모리(프로세스 대체 측정), [5] Confidentiality는 공격자 미구현.\n")
    section_fc()
    print()
    section_scaling()
    print()
    section_issues()
