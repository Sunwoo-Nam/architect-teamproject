"""HTML 대시보드 렌더러 — raw dict를 자기완결 단일 HTML로 (N개 방안 비교).

원칙: 요약표는 전 QA 종류 × 실측값 + 별점의 집결표 — 압축 요약이 아니다.
"""
from __future__ import annotations

from .protocol import PLAN_LABELS, PLAN_NAMES

_CSS = """
body{font-family:-apple-system,'Malgun Gothic','Noto Sans KR',sans-serif;margin:0;background:#f5f6f8;color:#1c1e21}
.wrap{max-width:1180px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.4rem;margin:8px 0 4px}
.meta{color:#5f6368;font-size:.85rem;line-height:1.6;margin-bottom:16px}
.caveat{background:#fff4e5;border-left:4px solid #f5a623;padding:10px 14px;border-radius:6px;font-size:.85rem;margin:12px 0 24px}
.card{background:#fff;border:1px solid #e3e5e8;border-radius:10px;padding:18px 20px;margin-bottom:18px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
.card h2{font-size:1.05rem;margin:0 0 4px}
.card .sub{color:#5f6368;font-size:.8rem;margin-bottom:12px}
.card h3{font-size:.85rem;margin:16px 0 6px;color:#0b57d0}
table{border-collapse:collapse;width:100%;font-size:.87rem}
th,td{border-bottom:1px solid #eceef1;padding:7px 10px;text-align:left;white-space:nowrap}
th{color:#5f6368;font-weight:600;font-size:.78rem}
.num{font-variant-numeric:tabular-nums}
.stars{letter-spacing:1px}
td.win{background:#e8f5e9;border-radius:6px;font-weight:700}
.tie{color:#5f6368}
.badge{display:inline-block;border-radius:10px;padding:1px 9px;font-size:.75rem;margin-left:6px;vertical-align:1px}
.badge.core{background:#e3f2fd;color:#0b57d0}.badge.aux{background:#f1f3f4;color:#5f6368}.badge.sub{background:#fff4e5;color:#a15c00}
.scroll{overflow-x:auto}
footer{color:#8a8f98;font-size:.75rem;margin-top:28px}
"""


def _stars(n: int) -> str:
    return f'<span class="stars">{"★" * n}{"☆" * (5 - n)}</span> {n}점'


def render_html(raw: dict) -> str:
    m = raw["meta"]
    fc, ru = raw["fc"], raw["ru_memory"]
    sp, si = raw["sc_participants"], raw["sc_issues"]
    tb, ft, rc, cf = raw.get("tb"), raw["ft"], raw["rec"], raw["confidentiality"]
    P = [p for p in PLAN_NAMES if p in fc]

    def cells(values: list, stars: list) -> str:
        defined = [s for s in stars if s is not None]
        best = max(defined) if defined else None
        out = []
        for v, s in zip(values, stars):
            badge = f" &nbsp;{_stars(s)}" if s is not None else ""
            win = (
                ' class="win"'
                if s is not None and best is not None and s == best
                and len(defined) == len(stars) and len(set(defined)) > 1
                else ""
            )
            out.append(f'<td{win}><span class="num">{v}</span>{badge}</td>')
        return "".join(out)

    def row(label: str, values: list, stars: list, note: str = "") -> str:
        return f'<tr><td>{label}</td>{cells(values, stars)}<td class="tie">{note}</td></tr>'

    fc_total = fc["config"].get("cases") or fc["config"].get("runs")
    rows = []
    rows.append(row(
        '§1 FC — Total Utility 달성률 <span class="badge core">핵심 1위</span>',
        [f"달성률 {fc[p]['mean_ratio']:.3f} · s {fc[p]['s']:.3f} · x* {fc[p]['optimal_hit']}/{fc_total}" for p in P],
        [fc[p]["stars"] for p in P],
        f"x* 도달은 올바른 결렬 포함 · R̄ {fc[P[0]]['mean_baseline']:.3f} · 결렬 오답 " + "/".join(str(fc[p]["nodeal_wrong"]) for p in P)))
    rows.append(row(
        '§2 RU-메모리 — 피크/평균 증가분 <span class="badge core">핵심 2위</span>',
        [f"{ru[p]['median_peak_bytes']/1024:.1f} / {ru[p]['median_avg_bytes']/1024:.1f} KiB" for p in P],
        [None] * len(P),
        "별점 미확정 (핸드북 §2) — ENV-A 대체, 정본은 실기기 RSS"))
    rows.append(row(
        '§3 SC-참여자 수 — N=10 관측값 <span class="badge core">핵심 3위</span>',
        [(f"라운드 {sp[p]['median_rounds_by_n'].get('10') or 0:.0f}"
          f" · 메시지 {sp[p]['median_messages_by_n'].get('10') or 0:.0f}건"
          f" · 메모리 {(sp[p].get('median_peak_bytes_by_n', {}).get('10') or 0)/1024:.1f} KiB"
          f" · 지연 {(sp[p].get('median_time_ms_by_n', {}).get('10') or 0)/1000:.2f}s") for p in P],
        [None] * len(P),
        "확장 지수(b_msg)는 표에서 제외 — results/01-SC-참여자수-측정-해설.md 참조"))
    rows.append(row(
        '§4 SC-의제 수 — 탄력성 c <span class="badge sub">대체 측정</span>',
        [f"{si[p]['c']:.3f} [{si[p]['ci'][0]:.2f}, {si[p]['ci'][1]:.2f}]" for p in P],
        [si[p]["stars"] for p in P],
        "벤치마크 보류 — 개발용 multi-issue 생성"))
    rows.append(row(
        '§5-1 FT — 내성 여유 배수 <span class="badge core">핵심 5위</span>',
        [f"{ft[p]['margin']:g}배 (임계 {ft[p]['critical_multiple'] or '없음'})" for p in P],
        [ft[p]["stars"] for p in P],
        "베이스라인 완결률 " + " / ".join(f"{ft[p]['baseline_agree_rate']:.2f}" for p in P) + " · p_env 잠정"))
    rows.append(row(
        '§5-2 REC — 복구 시간 비율 <span class="badge core">핵심 5위</span>',
        [f"{rc[p]['median_ratio']} (R {rc[p]['restart_cost_R']:g})" for p in P],
        [rc[p]["stars"] for p in P],
        "FR 실패 " + "/".join(str(rc[p]["fr_failures"]) for p in P) + "건 · phase 비용 대체"))
    rows.append(row(
        "§5 FT &amp; REC 통합 (약한 고리 min)",
        [f"min({ft[p]['stars']}, {rc[p]['stars']})" for p in P],
        [min(ft[p]["stars"], rc[p]["stars"]) for p in P]))
    rows.append(row(
        '§6 TB — 합성 시간 <span class="badge aux">비핵심</span>',
        [f"{tb[p]['median_total_ms']/1000:.2f}s (지배: {tb[p]['dominant']})" for p in P],
        [None] * len(P),
        "상수 잠정 — 절대값 아님, 상대 비교용"))
    rows.append(row(
        '§7 CF — 노출률 (참여자 관찰자) <span class="badge aux">비핵심</span>',
        [f"{cf[p]['participant']['exposure_rate']:.2f} (이득 {cf[p]['participant']['gain_pp']:+.1f}%p)" for p in P],
        [cf[p]["participant"]["stars"] for p in P],
        "담당자 관점 " + " / ".join(f"{cf[p]['coordinator']['exposure_rate']:.2f}" for p in P)))
    if raw.get("an_kit"):
        rows.append(row(
            '§8 AN — 진단 실험 킷 <span class="badge aux">비핵심</span>',
            [f"킷 {raw['an_kit']['cases']}건 공유"] + ["〃"] * (len(P) - 1),
            [None] * len(P),
            "사람 진단 실험 대기 — grade()로 채점"))
    rows.append(row(
        "§9 관측량 — 메시지 / 바이트 / phase (중앙값)",
        [f"{fc[p]['median_messages']:.0f}건 / {fc[p]['median_bytes']/1024:.1f}KiB / {fc[p]['median_phases']:.0f}" for p in P],
        [None] * len(P),
        "횟수=배터리 · 크기=대역 · phase=체감 시간"))

    header = "".join(f"<th>{PLAN_LABELS.get(p, p)}</th>" for p in P)
    summary = f'<table><tr><th>QA · 지표</th>{header}<th>참고</th></tr>{"".join(rows)}</table>'

    def sec(title, badge, badge_cls, sub, table_html):
        return (f'<div class="card"><h2>{title}<span class="badge {badge_cls}">{badge}</span></h2>'
                f'<div class="sub">{sub}</div><div class="scroll">{table_html}</div></div>')

    def tbl(headers, data_rows):
        h = "".join(f"<th>{x}</th>" for x in headers)
        b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in data_rows)
        return f"<table><tr>{h}</tr>{b}</table>"

    details = []
    details.append(sec(
        "§1 FC — 상세", "핵심 1위", "core",
        f"벤치마크 functional {fc['config'].get('cases', fc['config'].get('runs'))}건 · 동일 케이스에 방안만 교체",
        tbl(["방안", "달성률", "R̄", "s", "별점", "x* 도달(올바른 결렬 포함)", "합의", "결렬 정답/오답", "동률 사용", "라운드/phase/메시지/바이트"],
            [[PLAN_LABELS.get(p, p), f"{fc[p]['mean_ratio']:.3f}", f"{fc[p]['mean_baseline']:.3f}", f"{fc[p]['s']:.3f}",
              _stars(fc[p]["stars"]), f"{fc[p]['optimal_hit']}/{fc_total}", f"{fc[p]['agreed']}/{fc_total}",
              f"{fc[p]['nodeal_correct']}/{fc[p]['nodeal_wrong']}", fc[p]["tie_break_used"],
              f"{fc[p]['median_rounds']:.0f} / {fc[p]['median_phases']:.0f} / {fc[p]['median_messages']:.0f} / {fc[p]['median_bytes']:.0f}"]
             for p in P])))
    # §3 상세 — 지표별 표 4개. N을 열로 두어 방안 간 같은 N을 나란히 비교한다.
    levels = [str(n) for n in sp["config"]["levels"]]

    def by_n_table(key: str, fmt) -> str:
        return tbl(
            ["방안"] + [f"N={n}" for n in levels],
            [[PLAN_LABELS.get(p, p)]
             + [fmt(sp[p].get(key, {}).get(n)) for n in levels] for p in P])

    def f_int(v):
        return "-" if v is None else f"{v:.0f}"

    def f_kib(v):
        return "-" if v is None else f"{v/1024:.1f}"

    def f_sec(v):
        return "-" if v is None else f"{v/1000:.2f}"

    details.append(sec(
        "§3 SC-참여자 수 — 상세", "핵심 3위", "core",
        f"scalability family · N {sp['config']['levels']} · 각 수준 {sp['config']['runs']}건의 중앙값"
        " · 후보 수는 4N (참여자 1인당 4개)",
        "<div class='sub'>완결률 게이트: "
        + " · ".join(f"{PLAN_LABELS.get(p, p)} {'통과' if sp[p]['gate_ok'] else '위반'}" for p in P)
        + "</div>"
        + "<h3>라운드 수</h3>" + by_n_table("median_rounds_by_n", f_int)
        + "<h3>메시지 전송 건수</h3>" + by_n_table("median_messages_by_n", f_int)
        + "<h3>피크 추가 메모리 (KiB)</h3>" + by_n_table("median_peak_bytes_by_n", f_kib)
        + "<h3>합성 지연시간 (초) — 상수 잠정</h3>" + by_n_table("median_time_ms_by_n", f_sec)))
    details.append(sec(
        "§5-1 FT — 상세", "핵심 5위", "core",
        f"p_env {ft['config']['p_env']} (잠정) · 강도 {ft['config']['multiples']}배 · 표본 {ft['config']['runs_base']}",
        tbl(["방안", "베이스라인 완결률", "강도별 완결률", "임계", "여유 배수", "별점"],
            [[PLAN_LABELS.get(p, p), f"{ft[p]['baseline_agree_rate']:.2f}",
              " ".join(f"{k}x:{v:.2f}" for k, v in ft[p]["agree_rates"].items() if k != "0.0"),
              ft[p]["critical_multiple"] or "없음", f"{ft[p]['margin']:g}", _stars(ft[p]["stars"])]
             for p in P])))
    details.append(sec(
        "§5-2 REC — 상세", "핵심 5위", "core",
        f"기준 세션 {rc['config']['sessions']}개 × 중단 그리드 (phase 비용 대체)",
        tbl(["방안", "시도", "FR 실패", "복구 비율 중앙값", "재시작 비용 R", "별점"],
            [[PLAN_LABELS.get(p, p), rc[p]["trials"], rc[p]["fr_failures"], rc[p]["median_ratio"],
              f"{rc[p]['restart_cost_R']:g}", _stars(rc[p]["stars"])]
             for p in P])))
    details.append(sec(
        "§6 TB — 합성 시간 상세", "비핵심", "aux",
        f"T = phase×{tb['config']['constants']['t_rtt_ms']:g}ms + 평가×{tb['config']['constants']['t_eval_ms']:g}ms + bytes÷대역 (상수 잠정)",
        tbl(["방안", "합성 시간", "통신", "평가", "전송", "지배 항"],
            [[PLAN_LABELS.get(p, p), f"{tb[p]['median_total_ms']/1000:.2f}s", f"{tb[p]['median_rtt_ms']/1000:.2f}s",
              f"{tb[p]['median_eval_ms']/1000:.2f}s", f"{tb[p]['median_transfer_ms']/1000:.3f}s", tb[p]["dominant"]]
             for p in P])))
    details.append(sec(
        "§7 CF — 상세", "비핵심·보조", "aux",
        "frequency 공격자 (고정 규칙) · 관점 2개",
        tbl(["방안", "관점", "정확도", "이득", "노출률", "별점"],
            [[PLAN_LABELS.get(p, p), "일반 참여자" if vp == "participant" else "담당자",
              f"{cf[p][vp]['accuracy']*100:.1f}%", f"{cf[p][vp]['gain_pp']:+.1f}%p",
              f"{cf[p][vp]['exposure_rate']:.2f}", _stars(cf[p][vp]["stars"])]
             for p in P for vp in ("participant", "coordinator")])))
    details.append(sec(
        "§2 RU / §4 SC-의제 — 상세 (대체 측정)", "보조", "sub",
        "RU 정본(RSS·L_state 판정)은 실기기 소관 · SC-의제는 벤치마크 보류",
        tbl(["항목"] + [PLAN_LABELS.get(p, p) for p in P],
            [["RU 피크/평균 (KiB)"] + [f"{ru[p]['median_peak_bytes']/1024:.1f} / {ru[p]['median_avg_bytes']/1024:.1f}" for p in P],
             ["SC-의제 c [CI] · 별점"] + [f"{si[p]['c']:.2f} [{si[p]['ci'][0]:.2f}, {si[p]['ci'][1]:.2f}] · {_stars(si[p]['stars'])}" for p in P]])))

    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>측정 대시보드 {m['run_id']}</title><style>{_CSS}</style></head><body><div class="wrap">
<h1>측정 대시보드 — 설계 후보 1 ({' vs '.join(PLAN_LABELS.get(p, p) for p in P)})</h1>
<div class="meta">실행 {m.get('timestamp') or m.get('timestamp_utc')} · run_id <b>{m['run_id']}</b> · seed {m['seed']} · commit {m['git_commit']} · negmas {m['negmas_version']}<br>입력: {m['provider']}</div>
<div class="caveat">⚠ {m['caveat']}</div>
<div class="card"><h2>종합 — 전 QA × 실측값 + 별점 <span class="badge core">초록 = 최고 등급 (등급이 갈릴 때만)</span></h2><div class="scroll">{summary}</div></div>
{''.join(details)}
<footer>별점 척도·게이트 정의: docs/changbae/24-QA-측정-핸드북.md · 원자료: raw.json (같은 폴더) · 자동 생성 문서</footer>
</div></body></html>"""
