"""리포트 렌더러 — 캠페인의 raw dict를 사람이 읽는 markdown으로 정리한다.

raw.json만 있으면 언제든 재생성 가능하다. 별점 척도는 핸드북(docs/changbae/24)의 것을 쓴다.
"""
from __future__ import annotations

from .protocol import PLAN_NAMES


def _stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n) + f" ({n}점)"


def _kib(b) -> str:
    return f"{b / 1024:.1f} KiB"


def _mem(b) -> str:
    return f"{b / 1024:.0f} KiB" if b < 1024 * 1024 else f"{b / 1024 / 1024:.1f} MiB"


def _dur(s) -> str:
    return f"{s:.1f}초" if s < 60 else f"{s / 60:.1f}분"


def render_markdown(raw: dict) -> str:
    m = raw["meta"]
    P = [p for p in PLAN_NAMES if p in raw["fc"]]  # 부분 실행(--plans) 대응
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
    for p in P:
        d = fc[p]
        A(
            f"| {p} | {d['mean_ratio']:.3f} | {d['mean_baseline']:.3f} | {d['s']:.3f} | {_stars(d['stars'])}"
            f" | {d['optimal_hit']}/{fc_total} | {d['agreed']}/{fc_total} | {d['nodeal_correct']}/{d['nodeal_wrong']}"
            f" | {d['median_rounds']:.0f} / {d['median_phases']:.0f} / {d['median_messages']:.0f} / {d['median_bytes']:.0f} |"
        )
    A("")
    if "by_participants" in fc[P[0]]:
        ns = sorted(fc[P[0]]["by_participants"], key=int)
        counts = {n: fc[P[0]]["by_participants"][n]["cases"] for n in ns}
        A("**참여자 수별 분해** (판정은 위 통합 기준 · 표본 "
          + " · ".join(f"{n}인 {counts[n]}건" for n in ns) + "):")
        A("")
        A("| 방안 | " + " | ".join(f"{n}인 달성률 / s" for n in ns) + " |")
        A("|---" * (len(ns) + 1) + "|")
        for p in P:
            bp = fc[p]["by_participants"]
            A("| " + p + " | " + " | ".join(
                f"{bp[n]['mean_ratio']:.3f} / {bp[n]['s']:.3f}" for n in ns) + " |")
        A("")

    ru = raw["ru_memory"]
    A("## [§2] Resource Utilization-메모리 (ENV-A 대체 측정)")
    A("")
    A(f"조건: {ru['config']['note']}. 정본(Peak/Average RSS·L_state 판정)은 실기기 소관 — 여기서는 상대 비교만.")
    A("")
    A("| 방안 | 최대 부하 단말 순간 피크 (판정) | 프로세스 피크 (참고) | 프로세스 평균 (참고) |")
    A("|---|---|---|---|")
    for p in P:
        A(f"| {p} | {_kib(ru[p].get('median_person_peak_bytes', 0))}"
          f" | {_kib(ru[p]['median_peak_bytes'])} | {_kib(ru[p]['median_avg_bytes'])} |")
    A("")
    A(f"귀속 모델: {ru['config'].get('person_note', '')}")
    A("")

    sp = raw["sc_participants"]
    A("## [§3] Scalability-참여자 수 — N별 관측값")
    A("")
    A(f"조건: N ∈ {sp['config']['levels']} · 각 {sp['config']['runs']}건의 중앙값 · {sp['config']['provider']}"
      " · 후보 수는 4N (참여자 1인당 4개, 기준 시나리오 3인·12개에서 도출)")
    A("")
    A("완결률 게이트: " + " · ".join(f"{p} {'통과' if sp[p]['gate_ok'] else '위반'}" for p in P))
    A("")
    if sp[P[0]].get("n_max") is not None:
        A("**판정 (경계 잠정 — 핸드북 §3.3)**:")
        A("")
        A("| 방안 | ① N_max | 별점 | ② b_mem [95% CI] | 별점 |")
        A("|---|---|---|---|---|")
        for p in P:
            A(f"| {p} | {sp[p]['n_max']}명 | {_stars(sp[p]['stars_n_max'])}"
              f" | {sp[p]['b_mem']:.3f} [{sp[p]['b_mem_ci'][0]:.2f}, {sp[p]['b_mem_ci'][1]:.2f}]"
              f" | {_stars(sp[p]['stars_b_mem'])} |")
    A("")
    A("> 확장 지수(b_msg)는 표에서 제외했다 — 지수만으로는 해석이 어렵고, 메시지를 물리 전송"
      " 건수로 세는 정의상 별점 5점이 도달 불가능하다. 근거와 이론 기준선 대조는"
      " [`01-SC-참여자수-측정-해설.md`](../01-SC-참여자수-측정-해설.md). 원자료(raw.json)에는 남아 있다.")
    A("")
    levels = [str(n) for n in sp["config"]["levels"]]
    for title, key, scale, unit in (
        ("라운드 수", "median_rounds_by_n", 1, ""),
        ("메시지 전송 건수", "median_messages_by_n", 1, ""),
        ("피크 추가 메모리 (KiB)", "median_peak_bytes_by_n", 1024, ""),
        ("최대 부하 단말 피크 P_N (KiB) — 판정 ② 입력", "median_person_peak_by_n", 1024, ""),
        ("합성 지연시간 (초) — 상수 잠정", "median_time_ms_by_n", 1000, ""),
    ):
        A(f"### {title}")
        A("")
        A("| 방안 | " + " | ".join(f"N={n}" for n in levels) + " |")
        A("|---" * (len(levels) + 1) + "|")
        for p in P:
            vals = sp[p].get(key, {})
            cells = []
            for n in levels:
                v = vals.get(n)
                cells.append("-" if v is None else (f"{v:.0f}" if scale == 1 else f"{v/scale:.1f}{unit}"))
            A(f"| {p} | " + " | ".join(cells) + " |")
        A("")

    si = raw["sc_issues"]
    A("## [§4] Scalability-의제 수 — 조합-메모리 탄력성 c")
    A("")
    A(f"조건: 조합 수준 {si['config']['levels']} · 각 {si['config']['runs']}회 · {si['config']['note']}")
    A("")
    A("| 방안 | 합의 | c [95% CI] | R² | 별점 | 피크 메모리 (S별, KiB) |")
    A("|---|---|---|---|---|---|")
    for p in P:
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
        for p in P:
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
    for p in P:
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
    for p in P:
        d = rc[p]
        A(
            f"| {p} | {d['trials']} | {d['fr_failures']} | {d['median_ratio']}"
            f" | {d['restart_cost_R']:g} | {_stars(d['stars'])} |"
        )
    A("")

    cf = raw["confidentiality"]
    A("## [§7] Confidentiality — 정규화 노출률 (핵심 5위)")
    A("")
    cfc = cf["config"]
    cf_n = cfc.get("cases") or cfc.get("runs")
    A(f"조건: 표본 {cf_n}건 · 후보 {cfc['candidates']} · frequency 공격자(고정 규칙) · {cfc.get('input', '개발용 무작위')}")
    A("")
    if "multiple" in cf[P[0]]:
        A(f"**판정 — 1:1 대비 노출 배수 m** (e₂: A {cf['config']['e2']['A']:.2f} / B {cf['config']['e2']['B']:.2f},"
          " N=2 실측 앵커 · 별점 사다리 잠정 · m=1 = 1:1 등가):")
        A("")
        A("| 방안 | m (A 순위표 노출) | 별점 | m (B 접두 복원) | 별점 | 최대 단일 관찰자 깊이 |")
        A("|---|---|---|---|---|---|")
        for p in P:
            d = cf[p]["multiple"]
            A(f"| {p} | {d['m_A']:.2f} | {_stars(d['stars_m_A'])} | {d['m_B']:.2f}"
              f" | {_stars(d['stars_m_B'])} | {d['max_single_depth_A']:.2f} |")
        A("")
    A("| 방안 | 관점 | 정확도 | 이득 | 노출률 | 별점 |")
    A("|---|---|---|---|---|---|")
    for p in P:
        for vp in ("participant", "coordinator"):
            d = cf[p][vp]
            A(
                f"| {p} | {'일반 참여자' if vp == 'participant' else 'Blackboard 담당자'}"
                f" | {d['accuracy'] * 100:.1f}% | {d['gain_pp']:+.1f}%p | {d['exposure_rate']:.2f} | {_stars(d['stars'])} |"
            )
    A("")
    if "by_n" in cf[P[0]]:
        ns = sorted(cf[P[0]]["by_n"], key=int)
        A(f"**N별 노출률** ({cfc.get('by_n_input', '')} · 각 {cfc.get('by_n_runs')}건 · {cfc.get('viewpoints', '')}):")
        A("")
        for vp, label in (("participant", "일반 참여자 관점"), ("coordinator", "담당자·루트 관점")):
            A(f"_{label}_")
            A("")
            A("| 방안 | " + " | ".join(f"N={n}" for n in ns) + " |")
            A("|---" * (len(ns) + 1) + "|")
            for p in P:
                bn = cf[p]["by_n"]
                A("| " + p + " | " + " | ".join(
                    f"{bn[n][vp]['exposure_rate']:.2f} (★{bn[n][vp]['stars']})" for n in ns) + " |")
            A("")

    isec = raw.get("issue_space")
    if isec:
        A("## [§10] 의제 조합(issue-space) — A·B 트랙")
        A("")
        labels = isec["config"]["track_labels"]
        counts = isec["config"]["tracks"]
        A(f"조건: {isec['config']['note']}")
        A("")
        A(
            "- **A 트랙** ("
            + labels.get("a", "A")
            + f", {counts.get('a', 0)}건): 전원 수락 가능한 조합이 드물어 합의안이 각자 순위표의 "
            "깊은 곳에 있다 — 검토 범위가 좁으면 좋은 안을 놓친다. **정확도**가 갈리는 조건."
        )
        A(
            "- **B 트랙** ("
            + labels.get("b", "B")
            + f", {counts.get('b', 0)}건): 전원 수락 가능한 조합이 흔해 합의안이 얕다 — 좁게 봐도 "
            "쉽게 찾는다. 대신 점진형이 일찍 멈춰 **1인 최대 메모리**가 낮아질 것으로 예상되는 조건."
        )
        A("")
        c = isec["config"].get("constants", {})
        A(f"시간 = 협상 1건(시작~합의)의 추정 소요. 합성 시간(통신 {c.get('t_rtt_ms', 0):.0f}ms/phase ·"
          f" 평가 {c.get('t_eval_ms', 0)*1000:.0f}µs/건 ÷N 병렬 보정 ·"
          f" 대역 {c.get('bw_bytes_per_s', 0)/1000:.0f}kB/s) + 프로토콜 계산 실측(PoC 벽시계, K=1).")
        A("**상수는 잠정 — 절대값이 아니라 방안 간 상대 비교용이다.**")
        A("")
        for track in ("a", "b"):
            A(f"### {track.upper()} 트랙 — {labels.get(track, track.upper())}")
            A("")
            A("| 조합 수 | 방안 | 건수 | 달성률(s) | 협상 1건 시간 min/평균/중앙/max |"
              " 단말 총 점유 | 프로토콜 상태 | 라운드 | phase |")
            A("|---|---|---|---|---|---|---|---|---|")
            levels = sorted({int(s) for p in P for s in isec.get(p, {}).get(track, {}).get("by_s", {})})
            for S in levels:
                for p in P:
                    v = isec.get(p, {}).get(track, {}).get("by_s", {}).get(str(S))
                    if not v:
                        continue
                    t = v["t_total_s"]
                    A(f"| {S:,} | {p} | {v['cases']} | {v['mean_ratio']:.3f} (s{v['s']:.2f})"
                      f" | {t['min']:.1f} / {t['mean']:.1f} / {t['median']:.1f} / {t['max']:.1f} s"
                      f" | {v['median_device_bytes']/1024/1024:.2f} MB"
                      f" | {_kib(v['median_protocol_bytes'])}"
                      f" | {v['median_rounds']:,} | {v['median_phases']:,} |")
            A("")
            base_note = []
            for S in levels:
                for p in P:
                    v = isec.get(p, {}).get(track, {}).get("by_s", {}).get(str(S))
                    if v:
                        base_note.append(f"S={S:,} → {v['median_base_bytes']/1024/1024:.2f} MB")
                        break
            A("> **단말 총 점유 = 공통 기저 + 프로토콜 상태.** 공통 기저(효용 테이블·순위표·"
              "역인덱스)는 방안과 무관하게 조합 수에만 비례한다 — " + " · ".join(base_note) + ". "
              "방안 선택으로 줄일 수 없는 하한이므로, 조합 공간 규모 상한은 이 값으로 판단한다. "
              "프로토콜 상태(holder_sizes 1인 최대)가 방안 간 차이가 나는 부분이다. "
              "전송 바이트는 점유량이 아니므로 이 축에서 제외했다 (통신 시간 항으로만 계상).")
            A("")
        A("> 시간의 항별 내역(통신·전송·평가·계산)은 raw.json의 `t_parts_median_s` 참조. "
          "규모를 섞은 대표값 하나로는 오해를 부르므로 조합 수(S)별로 나눠 싣는다 — "
          "같은 규모 안에서도 케이스 편차가 커서 min/max를 병기한다.")
        A("")

    isn = raw.get("issue_space_n")
    if isn:
        A("## [§11] 의제 조합 — 참여자 수(N)별 상세")
        A("")
        nc = isn["config"]
        NP = [p for p in PLAN_NAMES if p in isn]  # config 외의 키가 방안이다
        ns = [str(n) for n in nc["participants"]]
        A(f"조건: {nc['track_label']} 트랙 · 조합 수 "
          + " · ".join(f"{S:,}" for S in nc["combos"])
          + f" × 참여자 {nc['participants']} · 셀당 {nc['cases_per_cell']}건.")
        A(nc["note"])
        knc = nc.get("constants", {})
        if knc:
            A(f"합성 시간 상수: 통신 {knc.get('t_rtt_ms', 0):.0f}ms/phase ·"
              f" 평가 {knc.get('t_eval_ms', 0)*1000:.0f}µs/건 ÷N 병렬 보정 ·"
              f" 대역 {knc.get('bw_bytes_per_s', 0)/1000:.0f}kB/s. **상수는 잠정 — 방안 간 상대 비교용이다.**")
        A("")
        for title, fmt in (
            ("정확도 (s)", lambda v: f"{v['s']:.3f}"),
            ("달성률 (x\\* 대비)", lambda v: f"{v['mean_ratio']:.3f}"),
            ("협상 1건 시간 (중앙값)", lambda v: _dur(v["median_time_s"])),
            ("라운드 / phase", lambda v: f"{v['median_rounds']:,.0f} / {v['median_phases']:,.0f}"),
            ("단말 총 점유 메모리 (중앙값)", lambda v: _mem(v["median_device_bytes"])),
        ):
            A(f"**{title}**")
            A("")
            A("| 방안 · 조합 수 | " + " | ".join(f"N={n}" for n in ns) + " |")
            A("|---" * (len(ns) + 1) + "|")
            for p in NP:
                for S in nc["combos"]:
                    by_n = isn[p].get(str(S), {})  # 미측정 셀은 키가 없다
                    A(f"| {p} · S={S:,} | " + " | ".join(
                        fmt(by_n[n]) if n in by_n else "—" for n in ns) + " |")
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
    A("| QA | " + " | ".join(P) + " |")
    A("|---" * (len(P) + 1) + "|")
    A("| §1 Functional Correctness (핵심 1위) | " + " | ".join(_stars(fc[p]["stars"]) for p in P) + " |")
    A("| §2 RU-메모리 (핵심 2위) | " + " | ".join("상대 비교" for _ in P) + " |")
    A("| §3 SC-참여자 수 (핵심 3위) | "
      + " | ".join(
          f"N=10 라운드 {sp[p]['median_rounds_by_n'].get('10') or 0:.0f}"
          f" · 메시지 {sp[p]['median_messages_by_n'].get('10') or 0:.0f}"
          f" · {(sp[p].get('median_peak_bytes_by_n', {}).get('10') or 0)/1024:.0f}KiB"
          f" · {(sp[p].get('median_time_ms_by_n', {}).get('10') or 0)/1000:.0f}s"
          for p in P)
      + " |")
    A("| §4 SC-의제 수 (핵심 4위) | " + " | ".join(_stars(si[p]["stars"]) for p in P) + " |")
    A(
        "| §5 FT & REC (비핵심, min 통합) | "
        + " | ".join(
            f"{_stars(min(ft[p]['stars'], rc[p]['stars']))} (FT {ft[p]['stars']}·REC {rc[p]['stars']})"
            for p in P
        )
        + " |"
    )
    A(
        "| §7 Confidentiality (핵심 5위 — 참여자 관찰자) | "
        + " | ".join(_stars(cf[p]["participant"]["stars"]) for p in P)
        + " |"
    )
    A("")
    A(f"> 주의: {m['caveat']}")
    A("")
    return "\n".join(L)
