"""[24] Functional Correctness — Total Utility 달성률과 별점.

정의는 24번 문서 그대로:
- 결렬 후보 = 전원이 자신의 initial threshold 값을 얻는 후보 (항상 후보 집합에 포함)
- 유효 후보 = 전원 utility ≥ initial threshold (결렬은 항상 유효)
- x* = 유효 후보 중 total utility 최대 (항상 Pareto frontier 위)
- 달성률 = U(r) ÷ U(x*)
- 무작위 베이스라인 R̄ = 유효 후보 중 하나를 무작위로 고르는 전략의 평균 달성률
  (표본 추출 대신 기대값을 정확 계산한다 — 유효 후보 달성률의 산술 평균)
- 개선 비율 s = (달성률 − R̄) ÷ (1 − R̄) → 별점 0-5
"""
from __future__ import annotations

from dataclasses import dataclass

from ..domain import NO_DEAL, Candidate, Profile


def total_utility(c: Candidate | str, profiles: list[Profile]) -> float:
    if c == NO_DEAL:
        return sum(p.initial_threshold for p in profiles)
    return sum(p.utility(c) for p in profiles)


def valid_candidates(candidates: list[Candidate], profiles: list[Profile]) -> list[Candidate | str]:
    """유효 후보 (결렬 포함)."""
    valid: list[Candidate | str] = [
        c for c in candidates if all(p.utility(c) >= p.initial_threshold for p in profiles)
    ]
    valid.append(NO_DEAL)
    return valid


@dataclass(frozen=True)
class FcScore:
    ratio: float  # 달성률 U(r)/U(x*)
    baseline: float  # R̄
    s: float  # 개선 비율
    stars: int  # 별점 0-5 (s ≤ 0이면 0점 — 즉시 결함 취급은 호출 측 책임)
    optimal: Candidate | str  # x*


def stars_from_s(s: float) -> int:
    for stars, lo in ((5, 0.8), (4, 0.6), (3, 0.4), (2, 0.2), (1, 0.0)):
        if s > lo:
            return stars
    return 0


def score(outcome: Candidate | str, candidates: list[Candidate], profiles: list[Profile]) -> FcScore:
    valid = valid_candidates(candidates, profiles)
    u_star_c = max(valid, key=lambda c: (total_utility(c, profiles), repr(c)))
    u_star = total_utility(u_star_c, profiles)
    ratio = total_utility(outcome, profiles) / u_star
    baseline = sum(total_utility(c, profiles) for c in valid) / len(valid) / u_star
    s = (ratio - baseline) / (1.0 - baseline) if baseline < 1.0 else 1.0
    return FcScore(ratio, baseline, s, stars_from_s(s), u_star_c)
