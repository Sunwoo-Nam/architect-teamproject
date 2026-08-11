"""revised threshold — 바퀴(sweep) 단위 인하, NegMAS 양보 곡선 재사용.

PL 결정(2026-08-11): threshold는 한 바퀴를 다 돌고 결론이 없을 때 내린다.
인하 "폭"은 고정값이 아니라 NegMAS의 PolyAspiration 곡선을 쓴다 — 기본 boulware
(끝까지 버티다 후반에 크게 양보), 'linear'/'conceder'로 교체 가능. 하한은 initial threshold.
"""
from __future__ import annotations

from negmas.negotiators.helpers import PolyAspiration


class SweepThreshold:
    """revised_threshold(sweep) = initial + (1 - initial) × aspiration(t),
    t = (sweep - 1) / max_sweeps  (1바퀴째 t=0 → aspiration 1.0 → threshold 1.0에서 시작)
    """

    def __init__(
        self,
        initial_threshold: float,
        max_sweeps: int = 5,
        aspiration_type: str | float = "boulware",
    ):
        self.initial = initial_threshold
        self.max_sweeps = max_sweeps
        self._asp = PolyAspiration(max_aspiration=1.0, aspiration_type=aspiration_type)

    def at_sweep(self, sweep: int) -> float:
        """sweep은 1-기반. 곡선값을 initial-1.0 구간으로 사상하고 initial을 하한으로 보장."""
        t = min(1.0, max(0.0, (sweep - 1) / self.max_sweeps))
        frac = self._asp.utility_at(t)
        return max(self.initial, self.initial + (1.0 - self.initial) * frac)
