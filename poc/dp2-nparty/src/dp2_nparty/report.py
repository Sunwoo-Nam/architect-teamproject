"""리포트 렌더러 — 캠페인의 raw dict를 사람이 읽는 markdown으로 정리한다.

raw.json만 있으면 언제든 재생성 가능하다. 별점 척도는 핸드북(docs/changbae/24)의 것을 쓴다.
"""
from __future__ import annotations

from .protocol import PLAN_NAMES


def _stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n) + f" ({n}점)"


def _kib(b) -> str:
    return f"{b / 1024:.1f} KiB"


def render_markdown(raw: dict) -> str:
    m = raw["meta"]
    L: list[str] = []
    A = L.append
    A("# 측정 리포트 — 설계 후보 1 (방안 1 전원동의 투표형 vs 방안 2 누적 공통제안형)")
    A("")
    A(f"- 실행: {m.get('timestamp') or m.get('timestamp_utc')} · run_id `{m['run_id']}` · seed {m['seed']} · commit `{m['git_commit']}`")
    A(f"- 환경: python {m['python']} · negmas {m['negmas_version']} · 프로파일: {m['provider']}")
    A(f"- **주의**: {m['caveat']}")
    A("- 측정 정의: [`docs/changbae/24-QA-측정-핸드북.md`](../../../../docs/changbae/24-QA-측정-핸드북.md)")
    A("")

    fc = raw["fc"]
    A("## [§1] Functional Correctness — Total Utility 달성률")
    A("")
    fcc = fc["config"]
    if "cases" in fcc:
        A(f"조건: {fcc['input']} {fcc['cases']}건 · 참여자 {fcc.get('participants')} · 두 방안 동일 케이스")
    else:
        A(f"조건: {fcc['n']}인 · 후보 {fcc['candidates']} · {fcc['runs']}회, 두 방안 동일 프로파일")
    A("")
    fc_total = fcc.get("cases") or fcc.get("runs")
    A("| 방안 | 달성률 평균 | R̄ | s | 별점 | x\\* 도달 | 합의 | 결렬 정답/오답 | 라운드/phase/메시지/바이트 중앙값 |")
    A("|---|---|---|---|---|---|---|---|---|")
    for p in PLAN_NAMES:
        d = fc[p]
        A(
            f"| {p} | {d['mean_ratio']:.3f} | {d['mean_baseline']:.3f} | {d['s']:.3f} | {_stars(d['stars'])}"
            f" | {d['optimal_hit']}/{fc_total} | {d['agreed']}/{fc_total} | {d['nodeal_correct']}/{d['nodeal_wrong']}"
            f" | {d['median_rounds']:.0f} / {d['median_phases']:.0f} / {d['median_messages']:.0f} / {d['median_bytes']:.0f} |"
        )
    A("")

    ru = raw["ru_memory"]
    A("## [§2] Resource Utilization-메모리 (ENV-A 대체 측정)")
    A("")
    A(f"조건: {ru['config']['note']}. 정본(Peak/Average RSS·L_state 판정)은 실기기 소관 — 여기서는 상대 비교만.")
    A("")
    A("| 방안 | 피크 증가분 중앙값 | 평균 증가분 중앙값 |")
    A("|---|---|---|")
    for p in PLAN_NAMES:
        A(f"| {p} | {_kib(ru[p]['median_peak_bytes'])} | {_kib(ru[p]['median_avg_bytes'])} |")
    A("")

    sp = raw["sc_participants"]
    A("## [§3] Scalability-참여자 수 — 메시지 확장 지수 b_msg")
    A("")
    A(f"조건: N ∈ {sp['config']['levels']} · 각 {sp['config']['runs']}회 · {sp['config']['provider']} (교락 통제)")
    A("")
    A("| 방안 | 게이트 | b_msg [95% CI] | R² | 별점 | 메시지 중앙값 (N별) | 바이트 중앙값 (N별) |")
    A("|---|---|---|---|---|---|---|")
    for p in PLAN_NAMES:
        d = sp[p]
        msgs = " ".join(f"N{n}:{v:.0f}" for n, v in d["median_messages_by_n"].items() if v)
        byt = " ".join(f"N{n}:{v/1024:.1f}K" for n, v in d["median_bytes_by_n"].items() if v)
        warn = " ⚠CI 3등급" if d["ci_spans_3_grades"] else ""
        A(
            f"| {p} | {'통과' if d['gate_ok'] else '위반(0점)'} | {d['b_msg']:.3f} [{d['ci'][0]:.2f}, {d['ci'][1]:.2f}]{warn}"
            f" | {d['r2']:.3f} | {_stars(d['stars'])} | {msgs} | {byt} |"
        )
    A("")

    si = raw["sc_issues"]
    A("## [§4] Scalability-의제 수 — 조합-메모리 탄력성 c")
    A("")
    A(f"조건: 조합 수준 {si['config']['levels']} · 각 {si['config']['runs']}회 · {si['config']['note']}")
    A("")
    A("| 방안 | 합의 | c [95% CI] | R² | 별점 | 피크 메모리 (S별, KiB) |")
    A("|---|---|---|---|---|---|")
    for p in PLAN_NAMES:
        d = si[p]
        mem = " ".join(f"S{s}:{int(v) // 1024}" for s, v in d["median_peak_by_S"].items())
        A(
            f"| {p} | {d['agreed']} | {d['c']:.3f} [{d['ci'][0]:.2f}, {d['ci'][1]:.2f}] | {d['r2']:.3f}"
            f" | {_stars(d['stars'])} | {mem} |"
        )
    A("")

    tb = raw.get("tb")
    if tb:
        A("## [§6] Time Behaviour — 합성 시간 (ENV-A, 상수 잠정)")
        A("")
        cst = tb["config"]["constants"]
        A(
            f"모델: T = phase×{cst['t_rtt_ms']:g}ms + 평가×{cst['t_eval_ms']:g}ms + bytes÷{cst['bw_bytes_per_s']:g}B/s"
            f" — {tb['config']['note']}"
        )
        A("")
        A("| 방안 | 합성 시간 중앙값 | 통신(RTT) | 평가 | 전송 | 지배 항 |")
        A("|---|---|---|---|---|---|")
        for p in PLAN_NAMES:
            d = tb[p]
            A(
                f"| {p} | **{d['median_total_ms'] / 1000:.2f}s** | {d['median_rtt_ms'] / 1000:.2f}s"
                f" | {d['median_eval_ms'] / 1000:.2f}s | {d['median_transfer_ms'] / 1000:.3f}s | {d['dominant']} |"
            )
        A("")

    ft = raw["ft"]
    A("## [§5-1] Fault Tolerance — 내성 여유 배수")
    A("")
    A(
        f"조건: p_env {ft['config']['p_env']} ({ft['config']['p_env_note']}) · 강도 {ft['config']['multiples']}배"
        f" · 베이스라인 {ft['config']['runs_base']}회 · 강도별 {ft['config']['runs_each']}회"
    )
    A("")
    A("| 방안 | 베이스라인 완결률 | 강도별 완결률 | 임계 배수 | 여유 배수 | 별점 |")
    A("|---|---|---|---|---|---|")
    for p in PLAN_NAMES:
        d = ft[p]
        rates = " ".join(f"{k}x:{v:.2f}" for k, v in d["agree_rates"].items() if k != "0.0")
        crit = d["critical_multiple"] if d["critical_multiple"] is not None else "없음(최대 강도까지)"
        A(
            f"| {p} | {d['baseline_agree_rate']:.2f} | {rates} | {crit} | {d['margin']:g} | {_stars(d['stars'])} |"
        )
    A("")

    rc = raw["rec"]
    A("## [§5-2] Recoverability — 복구 시간 비율 (phase 비용 대체)")
    A("")
    A(f"조건: 기준 세션 {rc['config']['sessions']}개 × 중단 지점 그리드 · {rc['config']['note']}")
    A("")
    A("| 방안 | 시도 | FR 실패(재개·일치) | 복구 비율 중앙값 | 재시작 비용 R | 별점 |")
    A("|---|---|---|---|---|---|")
    for p in PLAN_NAMES:
        d = rc[p]
        A(
            f"| {p} | {d['trials']} | {d['fr_failures']} | {d['median_ratio']}"
            f" | {d['restart_cost_R']:g} | {_stars(d['stars'])} |"
        )
    A("")

    cf = raw["confidentiality"]
    A("## [§7] Confidentiality — 정규화 노출률 (비핵심·보조 관측)")
    A("")
    cfc = cf["config"]
    cf_n = cfc.get("cases") or cfc.get("runs")
    A(f"조건: 표본 {cf_n}건 · 후보 {cfc['candidates']} · frequency 공격자(고정 규칙) · {cfc.get('input', '개발용 무작위')}")
    A("")
    A("| 방안 | 관점 | 정확도 | 이득 | 노출률 | 별점 |")
    A("|---|---|---|---|---|---|")
    for p in PLAN_NAMES:
        for vp in ("participant", "coordinator"):
            d = cf[p][vp]
            A(
                f"| {p} | {'일반 참여자' if vp == 'participant' else 'Blackboard 담당자'}"
                f" | {d['accuracy'] * 100:.1f}% | {d['gain_pp']:+.1f}%p | {d['exposure_rate']:.2f} | {_stars(d['stars'])} |"
            )
    A("")

    if "an_kit" in raw:
        A("## [§8] Analysability — 진단 실험 킷")
        A("")
        A(
            f"사람 진단 실험용 킷 생성: 케이스 {raw['an_kit']['cases']}건 → `{raw['an_kit']['dir']}`"
            " (cases/ = 진단자용 로그, sealed/ = 봉인 정답 — 블라인드 유지). 성공률은 진단 후 grade()로 채점."
        )
        A("")

    A("## 종합 — 별점 요약 (판정 기준 관점만)")
    A("")
    A("| QA | " + " | ".join(PLAN_NAMES) + " |")
    A("|---" * (len(PLAN_NAMES) + 1) + "|")
    A("| §1 Functional Correctness (핵심 1위) | " + " | ".join(_stars(fc[p]["stars"]) for p in PLAN_NAMES) + " |")
    A("| §2 RU-메모리 (핵심 2위) | " + " | ".join("상대 비교" for _ in PLAN_NAMES) + " |")
    A("| §3 SC-참여자 수 (핵심 3위) | " + " | ".join(_stars(sp[p]["stars"]) for p in PLAN_NAMES) + " |")
    A("| §4 SC-의제 수 (핵심 4위) | " + " | ".join(_stars(si[p]["stars"]) for p in PLAN_NAMES) + " |")
    A(
        "| §5 FT & REC (핵심 5위, min 통합) | "
        + " | ".join(
            f"{_stars(min(ft[p]['stars'], rc[p]['stars']))} (FT {ft[p]['stars']}·REC {rc[p]['stars']})"
            for p in PLAN_NAMES
        )
        + " |"
    )
    A(
        "| §7 Confidentiality (비핵심 — 참여자 관찰자) | "
        + " | ".join(_stars(cf[p]["participant"]["stars"]) for p in PLAN_NAMES)
        + " |"
    )
    A("")
    A(f"> 주의: {m['caveat']}")
    A("")
    return "\n".join(L)
