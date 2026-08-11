"""리포트 렌더러 — 캠페인의 raw dict를 사람이 읽는 markdown으로 정리한다.

raw.json만 있으면 언제든 재생성 가능하다 (측정 재실행 불필요).
별점 척도는 각 측정 정의 문서(24·25·27·28·29)의 것을 그대로 쓴다.
"""
from __future__ import annotations


def _stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n) + f" ({n}점)"


def render_markdown(raw: dict) -> str:
    m = raw["meta"]
    L: list[str] = []
    A = L.append
    A("# 측정 리포트 — 설계 후보 1 (방안 1 전원동의 투표형 vs 방안 2 누적 공통제안형)")
    A("")
    A(f"- 실행: {m['timestamp_utc']} · run_id `{m['run_id']}` · seed {m['seed']} · commit `{m['git_commit']}`")
    A(f"- 환경: python {m['python']} · negmas {m['negmas_version']}")
    A(f"- 프로파일: {m['provider']}")
    A(f"- **주의**: {m['caveat']}")
    A("")

    fc = raw["fc"]
    A("## [1] Functional Correctness — Total Utility 달성률 (24)")
    A("")
    A(f"조건: {fc['config']['n']}인 · 후보 {fc['config']['candidates']} · {fc['config']['runs']}회, 두 방안 동일 프로파일")
    A("")
    A("| 방안 | 달성률 평균 | R̄ | 개선 비율 s | 별점 | x\\* 도달/합의 | 결렬 정답/오답 | 동률 사용 | 라운드/phase/메시지 중앙값 |")
    A("|---|---|---|---|---|---|---|---|---|")
    for p in ("plan1", "plan2"):
        d = fc[p]
        A(
            f"| {p} | {d['mean_ratio']:.3f} | {d['mean_baseline']:.3f} | {d['s']:.3f} | {_stars(d['stars'])}"
            f" | {d['optimal_hit']}/{d['agreed']} | {d['nodeal_correct']}/{d['nodeal_wrong']}"
            f" | {d['tie_break_used']} | {d['median_rounds']:.0f} / {d['median_phases']:.0f} / {d['median_messages']:.0f} |"
        )
    A("")

    ru = raw["ru_memory"]
    A("## [2] Resource Utilization-메모리 (26 — ENV-A 대체 측정)")
    A("")
    A(f"조건: 기준 시나리오, {ru['config']['note']}. 정본 측정(Peak/Average RSS)은 실기기 소관 — 여기서는 방안 간 상대 비교만.")
    A("")
    A("| 방안 | 피크 추가 메모리 중앙값 |")
    A("|---|---|")
    for p in ("plan1", "plan2"):
        A(f"| {p} | {ru[p]['median_peak_bytes'] / 1024:.1f} KiB |")
    A("")

    sp = raw["sc_participants"]
    A("## [3] Scalability-참여자 수 — 메시지 확장 지수 b_msg (25)")
    A("")
    A(f"조건: N ∈ {sp['config']['levels']} · 각 {sp['config']['runs']}회 · {sp['config']['provider']} (교락 통제)")
    A("")
    A("| 방안 | 게이트 | b_msg [95% CI] | R² | 별점 | 메시지 중앙값 (N별) |")
    A("|---|---|---|---|---|---|")
    for p in ("plan1", "plan2"):
        d = sp[p]
        msgs = " ".join(f"N{n}:{v:.0f}" for n, v in d["median_messages_by_n"].items() if v)
        warn = " ⚠CI 3등급" if d["ci_spans_3_grades"] else ""
        A(
            f"| {p} | {'통과' if d['gate_ok'] else '위반(0점)'} | {d['b_msg']:.3f} [{d['ci'][0]:.2f}, {d['ci'][1]:.2f}]{warn}"
            f" | {d['r2']:.3f} | {_stars(d['stars'])} | {msgs} |"
        )
    A("")

    si = raw["sc_issues"]
    A("## [4] Scalability-의제 수 — 조합-메모리 탄력성 c (27)")
    A("")
    A(f"조건: 조합 수준 {si['config']['levels']} · 각 {si['config']['runs']}회 · {si['config']['note']}")
    A("")
    A("| 방안 | 합의 | c [95% CI] | R² | 별점 | 피크 메모리 (S별, KiB) |")
    A("|---|---|---|---|---|---|")
    for p in ("plan1", "plan2"):
        d = si[p]
        mem = " ".join(f"S{s}:{int(v) // 1024}" for s, v in d["median_peak_by_S"].items())
        A(
            f"| {p} | {d['agreed']} | {d['c']:.3f} [{d['ci'][0]:.2f}, {d['ci'][1]:.2f}] | {d['r2']:.3f}"
            f" | {_stars(d['stars'])} | {mem} |"
        )
    A("")

    cf = raw["confidentiality"]
    A("## [5] Confidentiality — 정규화 노출률 (29, 비핵심·보조 관측)")
    A("")
    A(f"조건: {cf['config']['n']}인 · 후보 {cf['config']['candidates']} · {cf['config']['runs']}회 · frequency 공격자(고정 규칙)")
    A("")
    A("| 방안 | 관점 | 정확도 | 이득 | 노출률 | 별점 |")
    A("|---|---|---|---|---|---|")
    for p in ("plan1", "plan2"):
        for vp in ("participant", "coordinator"):
            d = cf[p][vp]
            A(
                f"| {p} | {'일반 참여자' if vp == 'participant' else 'Blackboard 담당자'}"
                f" | {d['accuracy'] * 100:.1f}% | {d['gain_pp']:+.1f}%p | {d['exposure_rate']:.2f} | {_stars(d['stars'])} |"
            )
    A("")

    A("## 종합 — 별점 요약 (판정 기준 관점만)")
    A("")
    A("| QA | 방안 1 | 방안 2 |")
    A("|---|---|---|")
    A(f"| Functional Correctness (핵심 1위) | {_stars(fc['plan1']['stars'])} | {_stars(fc['plan2']['stars'])} |")
    A("| RU-메모리 (핵심 2위) | 상대 비교만 (별점 척도는 26 확정 대기) | 〃 |")
    A(f"| SC-참여자 수 (핵심 3위) | {_stars(sp['plan1']['stars'])} | {_stars(sp['plan2']['stars'])} |")
    A(f"| SC-의제 수 (핵심 4위) | {_stars(si['plan1']['stars'])} | {_stars(si['plan2']['stars'])} |")
    A("| FT & REC (핵심 5위) | 미측정 (장애 주입·kill-resume 하니스 필요) | 〃 |")
    A(
        f"| Confidentiality (비핵심 — 참여자 관찰자 기준) | {_stars(cf['plan1']['participant']['stars'])}"
        f" | {_stars(cf['plan2']['participant']['stars'])} |"
    )
    A("")
    A(f"> 주의: {m['caveat']}")
    A("")
    return "\n".join(L)
