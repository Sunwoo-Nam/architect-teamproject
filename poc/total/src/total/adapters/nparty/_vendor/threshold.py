"""revised threshold — 바퀴(sweep) 단위 인하, NegMAS 양보 곡선 재사용.

PL 결정(2026-08-11): threshold는 한 바퀴를 다 돌고 결론이 없을 때 내린다.
인하 "폭"은 고정값이 아니라 NegMAS의 PolyAspiration 곡선을 쓴다 — 기본 boulware
(끝까지 버티다 후반에 크게 양보), 'linear'/'conceder'로 교체 가능.

곡선의 사상 구간은 NegMAS 관행대로 [initial threshold, 자기 최고 utility]다:
- 첫 바퀴(t=0): threshold = 자기 최고 utility → 자기 1순위만 제출 가능
- 마지막 바퀴(t=1): threshold = initial threshold → 바닥선 위 전부 제출 가능
"""
from __future__ import annotations

from negmas.negotiators.helpers import PolyAspiration


class SweepThreshold:
    """revised_threshold(sweep) = initial + (own_max - initial) × aspiration(t),
    t = (sweep - 1) / (max_sweeps - 1). 하한은 initial threshold."""

    def __init__(
        self,
        initial_threshold: float,
        max_sweeps: int = 5,
        aspiration_type: str | float = "boulware",
        max_utility: float = 1.0,
    ):
        self.initial = initial_threshold
        self.max_sweeps = max_sweeps
        self.max_utility = max(max_utility, initial_threshold)
        self._asp = PolyAspiration(max_aspiration=1.0, aspiration_type=aspiration_type)

    def at_sweep(self, sweep: int) -> float:
        if self.max_sweeps <= 1:
            return self.initial
        t = min(1.0, max(0.0, (sweep - 1) / (self.max_sweeps - 1)))
        frac = self._asp.utility_at(t)
        return max(self.initial, self.initial + (self.max_utility - self.initial) * frac)
