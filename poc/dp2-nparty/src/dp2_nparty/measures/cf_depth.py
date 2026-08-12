"""[24 §7] 1:1 협상 대비 노출 배수 m — 깊이 2축과 e₂ 앵커 (2026-08-12 지표 개정).

정의 (핸드북 §7.2-7.3):
- 노출 깊이 e(o,v): 관찰자 o가 피해자 v의 선호를 어디까지 복원할 수 있는가 (0-1).
  A **순위표 노출 비율**: o에게 귀속으로 보이는 v의 제안 고유 후보 수 ÷ D_v
    (공격자 규칙과 무관한 정보론적 상한)
  B **접두 복원 깊이**: 바퀴 1의 "라운드 = 순위" 신호로 순서까지 정확히 복원한
    연속 접두 길이 ÷ D_v (실측 검증 — 실제 순위표와 대조해 일치한 깊이만 인정)
  D_v = v의 제출 가능 후보 수 = |{c : utility(c) ≥ initial threshold}| (바닥선 위 전부)
- e₂ (1:1 기준 노출량): N=2 세션에서 상대방이 도달하는 깊이의 중앙값.
  2인 협상에서는 상대의 제출이 곧 나에게 온 제안이므로 **전체 로그 가시**로 계산한다
  (Blackboard 시뮬레이션의 "참여자는 자기 것만" 필터는 2인에서는 비현실 — 필연 교환).
- 노출 배수 m(v) = Σ_{o≠v} e(o,v) ÷ e₂ — 표본·피해자에 대한 중앙값으로 보고.
  병기: 최대 단일 관찰자 깊이 max_o e(o,v) (노출 집중도 — 담당자·루트).

별점 (잠정 — PL 조율 예정): 참조점 0(무노출)·1(1:1 등가)·N−1(전면)의 2배 사다리.
"""
from __future__ import annotations

import statistics

from ..domain import Profile, SessionResult
from .confidentiality import _visible_events


def _visible_subs(session: SessionResult, observer: str, coordinator: str) -> dict:
    """관찰자에게 귀속으로 보이는 피해자별 제안 목록 {pid: [(sweep, rank_or_round, cand)]}."""
    subs: dict[str, list] = {}
    for ev in _visible_events(session, observer, coordinator):
        if ev.get("t") == "round":
            for pid, c in ev.get("submitted", {}).items():
                subs.setdefault(pid, []).append((ev["sweep"], ev["k"], c))
        elif ev.get("t") == "batch":
            for pid, items in ev.get("submitted", {}).items():
                for rank, c in items:
                    subs.setdefault(pid, []).append((ev["sweep"], rank, c))
    return subs


def _all_subs(session: SessionResult) -> dict:
    """전체 로그 가시(무필터) — e₂ 계산용."""
    subs: dict[str, list] = {}
    for ev in session.log:
        if ev.get("t") == "round":
            for pid, c in ev.get("submitted", {}).items():
                subs.setdefault(pid, []).append((ev["sweep"], ev["k"], c))
        elif ev.get("t") == "batch":
            for pid, items in ev.get("submitted", {}).items():
                for rank, c in items:
                    subs.setdefault(pid, []).append((ev["sweep"], rank, c))
    return subs


def _d_v(profile: Profile) -> int:
    return max(1, sum(1 for c in profile.utilities if profile.utility(c) >= profile.initial_threshold))


def depth_a(v_subs: list, d_v: int) -> float:
    """A 순위표 노출 비율 — 귀속 노출된 고유 후보 수 비율."""
    return min(1.0, len({c for _s, _k, c in v_subs}) / d_v)


def depth_b(v_subs: list, victim: Profile, first_round_of_sweep1: int = 1) -> float:
    """B 접두 복원 깊이 — 바퀴 1의 라운드 번호 = 순위 신호로 복원, 실제 순위표와 대조."""
    d = _d_v(victim)
    by_rank = {}
    for sweep, k, c in v_subs:
        if sweep == 1:
            by_rank.setdefault(k, c)
    ranked = victim.ranked()
    depth = 0
    for r in range(1, d + 1):
        if r in by_rank and r <= len(ranked) and by_rank[r] == ranked[r - 1]:
            depth = r
        else:
            break
    return depth / d


def e2_anchor(cases: list, plan_cls, samples: int = 30) -> dict:
    """N=2 세션 실측 앵커 — 각 케이스의 앞 2인 프로파일로 양자 협상을 돌려
    상대방(전체 로그 가시)이 도달하는 깊이의 중앙값을 얻는다."""
    e2a, e2b = [], []
    for case in cases[:samples]:
        pair = case.profiles[:2]
        s = plan_cls(pair).run()
        subs = _all_subs(s)
        victim = pair[1]
        v_subs = subs.get(victim.pid, [])
        e2a.append(depth_a(v_subs, _d_v(victim)))
        e2b.append(depth_b(v_subs, victim))
    return {"A": max(1e-9, statistics.median(e2a)), "B": max(1e-9, statistics.median(e2b)),
            "samples": len(e2a)}


def stars_m(m: float) -> int:
    """잠정 사다리 (PL 조율 예정): 3점 경계 = 1:1 등가."""
    for stars, hi in ((5, 0.25), (4, 0.5), (3, 1.0), (2, 2.0), (1, 4.0)):
        if m <= hi:
            return stars
    return 0


def exposure_multiple(
    runs: list[tuple[SessionResult, list[Profile]]], e2: dict
) -> dict:
    """세션들에 대해 피해자별 노출 배수 m(깊이 2축)과 최대 단일 관찰자 깊이를 집계."""
    m_a, m_b, single_a = [], [], []
    for session, profiles in runs:
        coordinator = profiles[0].pid
        pid_prof = {p.pid: p for p in profiles}
        per_obs = {p.pid: _visible_subs(session, p.pid, coordinator) for p in profiles}
        for v in profiles:
            sum_a = sum_b = best_a = 0.0
            d = _d_v(v)
            for o in profiles:
                if o.pid == v.pid:
                    continue
                v_subs = per_obs[o.pid].get(v.pid, [])
                ea = depth_a(v_subs, d)
                eb = depth_b(v_subs, pid_prof[v.pid])
                sum_a += ea
                sum_b += eb
                best_a = max(best_a, ea)
            m_a.append(sum_a / e2["A"])
            m_b.append(sum_b / e2["B"])
            single_a.append(best_a)
    med_a = statistics.median(m_a)
    med_b = statistics.median(m_b)
    return {
        "m_A": round(med_a, 3), "m_B": round(med_b, 3),
        "stars_m_A": stars_m(med_a), "stars_m_B": stars_m(med_b),
        "max_single_depth_A": round(statistics.median(single_a), 3),
    }
