"""[24 §7] 1:1 협상 대비 노출 배수 m — 노출 깊이와 e₂ 앵커 (2026-08-13 개정 반영).

정의 (핸드북 §7.2-7.3):
- 노출 깊이 e(o,v) = **순위표 노출 비율**: o에게 귀속으로 보이는 v의 제안 고유 후보 수
  ÷ D_v (공격자 규칙과 무관한 정보론적 상한).
  D_v = v의 제출 가능 후보 수 = |{c : utility(c) ≥ initial threshold}| (바닥선 위 전부)
- e₂ (1:1 기준 노출량): N=2 세션에서 상대방이 도달하는 깊이의 중앙값.
  2인 협상에서는 상대의 제출이 곧 나에게 온 제안이므로 **전체 로그 가시**로 계산한다
  (Blackboard 시뮬레이션의 "참여자는 자기 것만" 필터는 2인에서는 비현실 — 필연 교환).
- 노출 배수 m(v) = Σ_{o≠v} e(o,v) ÷ e₂ — 표본·피해자에 대한 중앙값으로 보고.
  병기: 최대 단일 관찰자 깊이 max_o e(o,v) (노출 집중도 — 담당자·루트).

구 B축(접두 복원 깊이)은 24 §7.3 개정(2026-08-13, PL 지시)으로 제거했다 —
"라운드 = 순위" 제출 규칙에서 B는 A와 항상 일치해 별도 정보가 없다.

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


def depth(v_subs: list, d_v: int) -> float:
    """노출 깊이 e — 귀속 노출된 고유 후보 수 ÷ 제출 가능 후보 수 (순위표 노출 비율)."""
    return min(1.0, len({c for _s, _k, c in v_subs}) / d_v)


def e2_anchor(cases: list, plan_cls, samples: int = 30) -> dict:
    """N=2 세션 실측 앵커 — 각 케이스의 앞 2인 프로파일로 양자 협상을 돌려
    상대방(전체 로그 가시)이 도달하는 깊이의 중앙값을 얻는다."""
    vals = []
    for case in cases[:samples]:
        pair = case.profiles[:2]
        s = plan_cls(pair).run()
        subs = _all_subs(s)
        victim = pair[1]
        v_subs = subs.get(victim.pid, [])
        vals.append(depth(v_subs, _d_v(victim)))
    return {"depth": max(1e-9, statistics.median(vals)), "samples": len(vals)}


def stars_m(m: float) -> int:
    """잠정 사다리 (PL 조율 예정): 3점 경계 = 1:1 등가."""
    for stars, hi in ((5, 0.25), (4, 0.5), (3, 1.0), (2, 2.0), (1, 4.0)):
        if m <= hi:
            return stars
    return 0


def exposure_multiple(
    runs: list[tuple[SessionResult, list[Profile]]], e2: dict
) -> dict:
    """세션들에 대해 피해자별 노출 배수 m과 최대 단일 관찰자 깊이를 집계."""
    multiples, single = [], []
    for session, profiles in runs:
        coordinator = profiles[0].pid
        per_obs = {p.pid: _visible_subs(session, p.pid, coordinator) for p in profiles}
        for v in profiles:
            total = best = 0.0
            d = _d_v(v)
            for o in profiles:
                if o.pid == v.pid:
                    continue
                e = depth(per_obs[o.pid].get(v.pid, []), d)
                total += e
                best = max(best, e)
            multiples.append(total / e2["depth"])
            single.append(best)
    med = statistics.median(multiples)
    return {
        "m": round(med, 3), "stars_m": stars_m(med),
        "max_single_depth": round(statistics.median(single), 3),
    }
