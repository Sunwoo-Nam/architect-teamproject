"""HTML 대시보드 렌더러 — raw dict를 자기완결 단일 HTML로.

용도: 한 실행의 전 QA 결과를 한 화면에서 보기 (브라우저/IDE 미리보기로 열람).
GitHub는 HTML을 소스로 보여주므로, GitHub에서는 report.md를 본다.
"""
from __future__ import annotations

_CSS = """
body{font-family:-apple-system,'Malgun Gothic','Noto Sans KR',sans-serif;margin:0;background:#f5f6f8;color:#1c1e21}
.wrap{max-width:1080px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.4rem;margin:8px 0 4px}
.meta{color:#5f6368;font-size:.85rem;line-height:1.6;margin-bottom:16px}
.caveat{background:#fff4e5;border-left:4px solid #f5a623;padding:10px 14px;border-radius:6px;font-size:.85rem;margin:12px 0 24px}
.card{background:#fff;border:1px solid #e3e5e8;border-radius:10px;padding:18px 20px;margin-bottom:18px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
.card h2{font-size:1.05rem;margin:0 0 4px}
.card .sub{color:#5f6368;font-size:.8rem;margin-bottom:12px}
table{border-collapse:collapse;width:100%;font-size:.88rem}
th,td{border-bottom:1px solid #eceef1;padding:7px 10px;text-align:left;white-space:nowrap}
th{color:#5f6368;font-weight:600;font-size:.8rem}
td.num{font-variant-numeric:tabular-nums}
.stars{letter-spacing:1px}
.win{background:#e8f5e9;border-radius:6px;font-weight:700}
.tie{color:#5f6368}
.badge{display:inline-block;border-radius:10px;padding:1px 9px;font-size:.75rem;margin-left:6px;vertical-align:1px}
.badge.core{background:#e3f2fd;color:#0b57d0}.badge.aux{background:#f1f3f4;color:#5f6368}.badge.sub{background:#fff4e5;color:#a15c00}
.scroll{overflow-x:auto}
footer{color:#8a8f98;font-size:.75rem;margin-top:28px}
"""


def _stars(n: int) -> str:
    return f'<span class="stars">{"★" * n}{"☆" * (5 - n)}</span> {n}점'


def _pair_cells(v1: int, v2: int) -> str:
    c1 = c2 = ""
    if v1 > v2:
        c1 = ' class="win"'
    elif v2 > v1:
        c2 = ' class="win"'
    return f"<td{c1}>{_stars(v1)}</td><td{c2}>{_stars(v2)}</td>"


def render_html(raw: dict) -> str:
    m = raw["meta"]
    fc, ru = raw["fc"], raw["ru_memory"]
    sp, si = raw["sc_participants"], raw["sc_issues"]
    tb, ft, rc, cf = raw.get("tb"), raw["ft"], raw["rec"], raw["confidentiality"]
    ft1, ft2 = ft["plan1"]["stars"], ft["plan2"]["stars"]
    rc1, rc2 = rc["plan1"]["stars"], rc["plan2"]["stars"]

    def sec(title, badge, badge_cls, sub, table_html):
        return (
            f'<div class="card"><h2>{title}<span class="badge {badge_cls}">{badge}</span></h2>'
            f'<div class="sub">{sub}</div><div class="scroll">{table_html}</div></div>'
        )

    def tbl(headers, rows):
        h = "".join(f"<th>{x}</th>" for x in headers)
        b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
        return f"<table><tr>{h}</tr>{b}</table>"

    # 종합 — 전 QA 종류 × 실측값 + 별점 (압축이 아니라 집결)
    def cell(value: str, stars: int | None, win: bool) -> str:
        badge = f' &nbsp;{_stars(stars)}' if stars is not None else ""
        cls = ' class="win"' if win else ""
        return f"<td{cls}><span class=\"num\">{value}</span>{badge}</td>"

    def row(label, v1, s1, v2, s2, note=""):
        w1 = s1 is not None and s2 is not None and s1 > s2
        w2 = s1 is not None and s2 is not None and s2 > s1
        return (f"<tr><td>{label}</td>{cell(v1, s1, w1)}{cell(v2, s2, w2)}"
                f"<td class=\"tie\">{note}</td></tr>")

    rows = []
    rows.append(row(
        '§1 Functional Correctness — Total Utility 달성률 <span class="badge core">핵심 1위</span>',
        f"달성률 {fc['plan1']['mean_ratio']:.3f} · s {fc['plan1']['s']:.3f} · x* {fc['plan1']['optimal_hit']}/{fc['plan1']['agreed']}", fc['plan1']['stars'],
        f"달성률 {fc['plan2']['mean_ratio']:.3f} · s {fc['plan2']['s']:.3f} · x* {fc['plan2']['optimal_hit']}/{fc['plan2']['agreed']}", fc['plan2']['stars'],
        f"R̄ {fc['plan1']['mean_baseline']:.3f} · 결렬 오답 {fc['plan1']['nodeal_wrong']}/{fc['plan2']['nodeal_wrong']}"))
    rows.append(row(
        '§2 RU-메모리 — 피크/평균 증가분 <span class="badge core">핵심 2위</span>',
        f"{ru['plan1']['median_peak_bytes']/1024:.1f} / {ru['plan1']['median_avg_bytes']/1024:.1f} KiB", None,
        f"{ru['plan2']['median_peak_bytes']/1024:.1f} / {ru['plan2']['median_avg_bytes']/1024:.1f} KiB", None,
        "별점 미확정 (핸드북 §2) — ENV-A 대체, 정본은 실기기 RSS"))
    rows.append(row(
        '§3 SC-참여자 수 — b_msg <span class="badge core">핵심 3위</span>',
        f"{sp['plan1']['b_msg']:.3f} [{sp['plan1']['ci'][0]:.2f}, {sp['plan1']['ci'][1]:.2f}]", sp['plan1']['stars'],
        f"{sp['plan2']['b_msg']:.3f} [{sp['plan2']['ci'][0]:.2f}, {sp['plan2']['ci'][1]:.2f}]", sp['plan2']['stars'],
        f"게이트 {'통과' if sp['plan1']['gate_ok'] and sp['plan2']['gate_ok'] else '위반'} · N=10 메시지 {sp['plan1']['median_messages_by_n'].get('10', 0):.0f} vs {sp['plan2']['median_messages_by_n'].get('10', 0):.0f}건"))
    rows.append(row(
        '§4 SC-의제 수 — 탄력성 c <span class="badge sub">대체 측정</span>',
        f"{si['plan1']['c']:.3f} [{si['plan1']['ci'][0]:.2f}, {si['plan1']['ci'][1]:.2f}]", si['plan1']['stars'],
        f"{si['plan2']['c']:.3f} [{si['plan2']['ci'][0]:.2f}, {si['plan2']['ci'][1]:.2f}]", si['plan2']['stars'],
        "벤치마크 보류 — 개발용 multi-issue 생성 (전체 열거 베이스라인)"))
    rows.append(row(
        '§5-1 Fault Tolerance — 내성 여유 배수 <span class="badge core">핵심 5위</span>',
        f"{ft['plan1']['margin']:g}배 (임계 {ft['plan1']['critical_multiple'] or '없음'})", ft1,
        f"{ft['plan2']['margin']:g}배 (임계 {ft['plan2']['critical_multiple'] or '없음'})", ft2,
        f"베이스라인 완결률 {ft['plan1']['baseline_agree_rate']:.2f} · p_env 잠정"))
    rows.append(row(
        '§5-2 Recoverability — 복구 시간 비율 <span class="badge core">핵심 5위</span>',
        f"{rc['plan1']['median_ratio']} (R {rc['plan1']['restart_cost_R']:g})", rc1,
        f"{rc['plan2']['median_ratio']} (R {rc['plan2']['restart_cost_R']:g})", rc2,
        f"FR 실패 {rc['plan1']['fr_failures']}/{rc['plan2']['fr_failures']}건 · phase 비용 대체"))
    rows.append(row(
        '§5 FT &amp; REC 통합 (약한 고리 min)',
        f"min({ft1}, {rc1})", min(ft1, rc1), f"min({ft2}, {rc2})", min(ft2, rc2), ""))
    rows.append(row(
        '§6 Time Behaviour — 합성 시간 <span class="badge aux">비핵심</span>',
        f"{tb['plan1']['median_total_ms']/1000:.2f}s (지배: {tb['plan1']['dominant']})", None,
        f"{tb['plan2']['median_total_ms']/1000:.2f}s (지배: {tb['plan2']['dominant']})", None,
        "상수 잠정 — 절대값 아님, 상대 비교용"))
    rows.append(row(
        '§7 Confidentiality — 노출률 (참여자 관찰자) <span class="badge aux">비핵심</span>',
        f"{cf['plan1']['participant']['exposure_rate']:.2f} (이득 {cf['plan1']['participant']['gain_pp']:+.1f}%p)", cf['plan1']['participant']['stars'],
        f"{cf['plan2']['participant']['exposure_rate']:.2f} (이득 {cf['plan2']['participant']['gain_pp']:+.1f}%p)", cf['plan2']['participant']['stars'],
        f"담당자 관점 {cf['plan1']['coordinator']['exposure_rate']:.2f} / {cf['plan2']['coordinator']['exposure_rate']:.2f} (집중 노출 감시)"))
    if raw.get("an_kit"):
        rows.append(row(
            '§8 Analysability — 진단 실험 킷 <span class="badge aux">비핵심</span>',
            f"킷 {raw['an_kit']['cases']}건 생성", None, "동일 킷 공유", None,
            "사람 진단 실험 대기 — 성공률은 진단 후 grade()로 채점"))
    rows.append(row(
        '§9 관측량 — 메시지 횟수 / 크기 / phase (세션 중앙값)',
        f"{fc['plan1']['median_messages']:.0f}건 / {fc['plan1']['median_bytes']/1024:.1f}KiB / {fc['plan1']['median_phases']:.0f}", None,
        f"{fc['plan2']['median_messages']:.0f}건 / {fc['plan2']['median_bytes']/1024:.1f}KiB / {fc['plan2']['median_phases']:.0f}", None,
        "횟수=배터리 · 크기=대역 · phase=체감 시간"))

    summary = ('<table><tr><th>QA · 지표</th><th>방안 1 전원동의 투표형</th>'
               '<th>방안 2 누적 공통제안형</th><th>참고</th></tr>' + "".join(rows) + "</table>")

    details = []
    details.append(sec(
        "§1 Functional Correctness — Total Utility 달성률", "핵심 1위", "core",
        f"벤치마크 functional {fc['config']['cases']}건 · 참여자 {fc['config']['participants']}",
        tbl(["방안", "달성률", "R̄", "s", "별점", "x* 도달/합의", "결렬 정답/오답", "라운드/phase/메시지/바이트"],
            [[p, f"{fc[p]['mean_ratio']:.3f}", f"{fc[p]['mean_baseline']:.3f}", f"{fc[p]['s']:.3f}",
              _stars(fc[p]["stars"]), f"{fc[p]['optimal_hit']}/{fc[p]['agreed']}",
              f"{fc[p]['nodeal_correct']}/{fc[p]['nodeal_wrong']}",
              f"{fc[p]['median_rounds']:.0f} / {fc[p]['median_phases']:.0f} / {fc[p]['median_messages']:.0f} / {fc[p]['median_bytes']:.0f}"]
             for p in ("plan1", "plan2")])))
    details.append(sec(
        "§3 SC-참여자 수 — b_msg", "핵심 3위", "core",
        f"scalability family · N {sp['config']['levels']}",
        tbl(["방안", "게이트", "b_msg [95% CI]", "R²", "별점", "메시지 중앙값"],
            [[p, "통과" if sp[p]["gate_ok"] else "위반(0점)",
              f"{sp[p]['b_msg']:.3f} [{sp[p]['ci'][0]:.2f}, {sp[p]['ci'][1]:.2f}]" + (" ⚠CI 3등급" if sp[p]["ci_spans_3_grades"] else ""),
              f"{sp[p]['r2']:.3f}", _stars(sp[p]["stars"]),
              " ".join(f"N{n}:{v:.0f}" for n, v in sp[p]["median_messages_by_n"].items() if v)]
             for p in ("plan1", "plan2")])))
    details.append(sec(
        "§5-1 Fault Tolerance — 내성 여유 배수", "핵심 5위", "core",
        f"p_env {ft['config']['p_env']} (잠정) · 강도 {ft['config']['multiples']}배 · 표본 {ft['config']['runs_base']}",
        tbl(["방안", "베이스라인 완결률", "강도별 완결률", "임계", "여유 배수", "별점"],
            [[p, f"{ft[p]['baseline_agree_rate']:.2f}",
              " ".join(f"{k}x:{v:.2f}" for k, v in ft[p]["agree_rates"].items() if k != "0.0"),
              ft[p]["critical_multiple"] or "없음", f"{ft[p]['margin']:g}", _stars(ft[p]["stars"])]
             for p in ("plan1", "plan2")])))
    details.append(sec(
        "§5-2 Recoverability — 복구 시간 비율", "핵심 5위", "core",
        f"기준 세션 {rc['config']['sessions']}개 × 중단 그리드 (phase 비용 대체)",
        tbl(["방안", "시도", "FR 실패", "복구 비율 중앙값", "재시작 비용 R", "별점"],
            [[p, rc[p]["trials"], rc[p]["fr_failures"], rc[p]["median_ratio"],
              f"{rc[p]['restart_cost_R']:g}", _stars(rc[p]["stars"])]
             for p in ("plan1", "plan2")])))
    details.append(sec(
        "§6 Time Behaviour — 합성 시간", "비핵심", "aux",
        f"T = phase×{tb['config']['constants']['t_rtt_ms']:g}ms + 평가×{tb['config']['constants']['t_eval_ms']:g}ms + bytes÷대역 (상수 잠정)",
        tbl(["방안", "합성 시간", "통신", "평가", "전송", "지배 항"],
            [[p, f"{tb[p]['median_total_ms']/1000:.2f}s", f"{tb[p]['median_rtt_ms']/1000:.2f}s",
              f"{tb[p]['median_eval_ms']/1000:.2f}s", f"{tb[p]['median_transfer_ms']/1000:.3f}s", tb[p]["dominant"]]
             for p in ("plan1", "plan2")])))
    details.append(sec(
        "§7 Confidentiality — 정규화 노출률", "비핵심·보조", "aux",
        f"frequency 공격자 (고정 규칙) · functional {cf['config']['cases']}건",
        tbl(["방안", "관점", "정확도", "이득", "노출률", "별점"],
            [[p, "일반 참여자" if vp == "participant" else "담당자",
              f"{cf[p][vp]['accuracy']*100:.1f}%", f"{cf[p][vp]['gain_pp']:+.1f}%p",
              f"{cf[p][vp]['exposure_rate']:.2f}", _stars(cf[p][vp]["stars"])]
             for p in ("plan1", "plan2") for vp in ("participant", "coordinator")])))
    details.append(sec(
        "§2 RU-메모리 / §4 SC-의제 (대체 측정)", "보조", "sub",
        "RU: 정본 Peak/Average RSS·L_state 판정은 실기기 소관 · SC-의제: 벤치마크 보류 — 개발용 생성",
        tbl(["항목", "방안 1", "방안 2"],
            [["RU 피크/평균 (KiB)",
              f"{ru['plan1']['median_peak_bytes']/1024:.1f} / {ru['plan1']['median_avg_bytes']/1024:.1f}",
              f"{ru['plan2']['median_peak_bytes']/1024:.1f} / {ru['plan2']['median_avg_bytes']/1024:.1f}"],
             ["SC-의제 c [CI]",
              f"{si['plan1']['c']:.2f} [{si['plan1']['ci'][0]:.2f}, {si['plan1']['ci'][1]:.2f}] {_stars(si['plan1']['stars'])}",
              f"{si['plan2']['c']:.2f} [{si['plan2']['ci'][0]:.2f}, {si['plan2']['ci'][1]:.2f}] {_stars(si['plan2']['stars'])}"]])))

    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>측정 대시보드 {m['run_id']}</title><style>{_CSS}</style></head><body><div class="wrap">
<h1>측정 대시보드 — 설계 후보 1 (방안 1 vs 방안 2)</h1>
<div class="meta">실행 {m.get('timestamp') or m.get('timestamp_utc')} · run_id <b>{m['run_id']}</b> · seed {m['seed']} · commit {m['git_commit']} · negmas {m['negmas_version']}<br>입력: {m['provider']}</div>
<div class="caveat">⚠ {m['caveat']}</div>
<div class="card"><h2>종합 — 별점 요약 <span class="badge core">초록 = 등급 우위</span></h2><div class="scroll">{summary}</div></div>
{''.join(details)}
<footer>별점 척도·게이트 정의: docs/changbae/24-QA-측정-핸드북.md · 원자료: raw.json (같은 폴더) · 자동 생성 문서</footer>
</div></body></html>"""
