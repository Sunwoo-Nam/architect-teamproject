"""REC — 복구 시간 비율 (29-1 A5-2)의 구조 모델.

핵심 전제(명시적 모델링 가정): 크래시에도 살아남는 것은 **일관된 커밋 상태**뿐이다.
협상 중의 offer는 제안일 뿐 결과가 아니므로, 커밋되지 않은 진행분은 재개 시 재실행해야 한다.

- seq(1안): 축이 닫힐 때마다 양측 합의(일관된 커밋)가 생긴다 → 커밋 경계가 축마다 존재.
  크래시 시 재실행 대상 = 진행 중이던 그 축 세션의 라운드뿐. 앞선 축은 durable.
- pool/full: 최종 합의 전에는 커밋 지점이 없다 → 크래시 시 세션 처음부터 재실행.

복구 시간 비율 = 재실행해야 하는 라운드 수 ÷ 정상 라운드 1회(=1). 크래시 시점을 라운드에
균일 분포로 두고 기대값을 구한다. 별점 기준선 R = 그 전략의 정상 세션 총 라운드(재시작 비용).
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class RecReport:
    strategy: str
    total_rounds: int             # R — 재시작 비용(전량 재실행)
    commit_segments: list[int]    # 커밋 경계로 나뉜 구간별 라운드
    expected_recovery: float      # 균일 크래시 시 기대 재실행 라운드
    max_recovery: int             # 최악의 크래시(구간 끝 직전)
    ratio: float                  # expected_recovery / 1
    stars: int


def _segments(strategy: str, total_rounds: int, axis_rounds: list[int] | None) -> list[int]:
    """커밋 경계로 나뉜 구간. seq는 축별, pool/full은 통째로 한 구간(커밋 없음)."""
    if strategy == "seq" and axis_rounds:
        return [r for r in axis_rounds if r > 0]
    return [total_rounds] if total_rounds > 0 else []


def _stars(ratio: float, R: int) -> int:
    # 29-1 A5-2: 5점 = 1 이하, 0점 = R 초과. 1~R 구간을 로그 4등분.
    if R <= 1:
        return 5 if ratio <= 1 else 0
    if ratio <= 1:
        return 5
    if ratio > R:
        return 0
    bounds = [R ** (i / 4) for i in (1, 2, 3, 4)]  # R^.25, R^.5, R^.75, R
    for i, b in enumerate(bounds):
        if ratio <= b:
            return 4 - i
    return 0


def analyze_recovery(strategy: str, total_rounds: int, axis_rounds: list[int] | None) -> RecReport:
    segments = _segments(strategy, total_rounds, axis_rounds)
    R = sum(segments)
    if R == 0:
        return RecReport(strategy, 0, [], 0.0, 0, 0.0, 5)
    # 균일 크래시: 어느 구간의 몇 번째 라운드에서 죽나. 그 구간 처음부터 재실행 → 재실행 = 구간 내 위치.
    # 한 구간(길이 L) 내 기대 재실행 = (1+2+...+L)/L 을 라운드로 가중 → Σ_L Σ_{x=1..L} x / R
    total_recovery = sum(L * (L + 1) / 2 for L in segments)
    expected = total_recovery / R
    max_recovery = max(segments)
    ratio = expected  # 분모 = 정상 라운드 1회 = 1
    return RecReport(strategy, R, segments, round(expected, 2), max_recovery,
                     round(ratio, 2), _stars(ratio, R))
