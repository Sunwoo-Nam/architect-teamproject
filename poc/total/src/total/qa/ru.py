"""[24 §2] Resource Utilization-메모리 — 프로세스 피크와 공통 기저.

**두 값을 각각 보고한다** (사용자 지시 2026-08-12):

| 값 | 뜻 | 방안 의존 |
|---|---|---|
| 프로세스 피크 | 협상 실행 구간의 tracemalloc 피크 증가분 | 있음 |
| 공통 기저 | 각자의 효용 표·순위표 — 협상 전에 이미 존재 | **없음** (조합 수에만 비례) |

섞으면 안 되는 이유: 공통 기저는 방안 선택으로 줄일 수 없는 **하한**이다. 합쳐서
하나로 보면 "설계로 어쩔 수 있는 부분"이 하한에 묻힌다. 반대로 기저를 빼고 프로토콜
상태만 보면 단말이 실제로 얼마를 쓰는지를 놓친다 — 그래서 **둘 다** 낸다.

**별점은 단말 총 점유(기저 + 피크) 기준**이다. 24 §2.8 단서가 "한도 대비 r 판정은
단말 총 점유로 해야 한다"고 명시했다. 한도는 ART 힙 상한 256MB를 기본으로 하되
실험에서 바꿀 수 있다 (ENV-B 실측이 오면 교체하는 자리).

한계를 정직하게: PoC(ENV-A)의 논리 크기와 실기기 RSS는 단위가 달라, 작은 규모에서는
별점이 5점으로 포화한다. 큰 조합 규모에서만 변별력이 생긴다 — 그래서 **별점과 함께
절대 MB를 항상 병기**한다.
"""
from __future__ import annotations

import statistics
import sys
import tracemalloc
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .constants import RU_CEILING_BYTES, band_ru_usage
from .contract import SessionResult

MB = 1024 * 1024


def deep_size(obj: Any, _seen: set[int] | None = None) -> int:
    """중첩 컨테이너의 실제 바이트. 같은 객체는 한 번만 센다 (공유 구조·순환 대응)."""
    if _seen is None:
        _seen = set()
    oid = id(obj)
    if oid in _seen:
        return 0
    _seen.add(oid)
    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        for k, v in obj.items():
            size += deep_size(k, _seen) + deep_size(v, _seen)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for item in obj:
            size += deep_size(item, _seen)
    return size


def measure_peak(run: Callable[[], Any]) -> tuple[Any, int]:
    """`run()`을 실행하며 피크 추가 할당(바이트)을 잰다. 반환 (결과, 피크 증가분).

    예외가 나도 tracemalloc을 반드시 끈다 — 켜진 채로 남으면 이후 측정이 전부 오염된다.
    """
    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        base, _ = tracemalloc.get_traced_memory()
        result = run()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, max(0, peak - base)


@dataclass(frozen=True)
class RuMeasure:
    peak_bytes: int      # 협상 구간 프로토콜 상태
    base_bytes: int      # 공통 기저 (방안 무관)
    ceiling_bytes: int
    r_total: float       # 단말 총 점유 ÷ 한도 — **판정 기준**
    r_peak: float        # 프로토콜 상태만 ÷ 한도 — 참고
    stars: int
    over_ceiling: bool
    #: 실물화 후보 구조 (RU B안) — peak에 포함된 내역의 병기. 0이면 계측 없음
    materialized_bytes: int = 0

    @property
    def total_bytes(self) -> int:
        return self.base_bytes + self.peak_bytes

    @property
    def peak_mb(self) -> float:
        return self.peak_bytes / MB

    @property
    def base_mb(self) -> float:
        return self.base_bytes / MB

    @property
    def total_mb(self) -> float:
        return self.total_bytes / MB

    def as_dict(self) -> dict:
        return {
            "peak_mb": round(self.peak_mb, 4),
            "base_mb": round(self.base_mb, 4),
            "total_mb": round(self.total_mb, 4),
            "peak_bytes": self.peak_bytes,
            "base_bytes": self.base_bytes,
            "ceiling_bytes": self.ceiling_bytes,
            "r_total": round(self.r_total, 6),
            "r_peak": round(self.r_peak, 6),
            "stars": self.stars,
            "over_ceiling": self.over_ceiling,
            "band": band_ru_usage().as_dict(),
        }


def measure(
    session: SessionResult,
    ceiling_bytes: int = RU_CEILING_BYTES,
) -> RuMeasure:
    if ceiling_bytes <= 0:
        raise ValueError(f"ceiling_bytes는 양수여야 한다: {ceiling_bytes}")
    total = session.total_device_bytes
    r_total = total / ceiling_bytes
    return RuMeasure(
        peak_bytes=session.peak_bytes,
        base_bytes=session.base_bytes,
        ceiling_bytes=ceiling_bytes,
        r_total=r_total,
        r_peak=session.peak_bytes / ceiling_bytes,
        materialized_bytes=session.materialized_bytes,
        stars=band_ru_usage().stars(r_total),
        over_ceiling=total > ceiling_bytes,
    )


def aggregate(measures: Sequence[RuMeasure]) -> dict:
    """세션 여러 건의 집계.

    중앙값과 **최댓값을 함께** 낸다 — OS는 평균이 아니라 "한 순간의 최악"으로 죽이므로
    (24 §2.6) 최댓값이 위험을 말해 준다.
    """
    if not measures:
        raise ValueError("집계할 측정이 없다")
    med_total = statistics.median(m.total_bytes for m in measures)
    max_total = max(m.total_bytes for m in measures)
    ceiling = measures[0].ceiling_bytes
    return {
        "sessions": len(measures),
        "median_peak_mb": round(statistics.median(m.peak_bytes for m in measures) / MB, 4),
        "median_base_mb": round(statistics.median(m.base_bytes for m in measures) / MB, 4),
        # 실물화 후보 구조 (RU B안) — 계측이 없는 도메인(nparty)은 None으로 비운다
        "median_materialized_mb": (
            round(statistics.median(m.materialized_bytes for m in measures) / MB, 4)
            if any(m.materialized_bytes for m in measures) else None),
        "median_total_mb": round(med_total / MB, 4),
        "max_total_mb": round(max_total / MB, 4),
        "ceiling_bytes": ceiling,
        "median_r_total": round(med_total / ceiling, 6),
        "max_r_total": round(max_total / ceiling, 6),
        "stars_median": band_ru_usage().stars(med_total / ceiling),
        "stars_max": band_ru_usage().stars(max_total / ceiling),
        "over_ceiling_sessions": sum(1 for m in measures if m.over_ceiling),
        "band": band_ru_usage().as_dict(),
        "note": "별점은 단말 총 점유(공통 기저 + 프로토콜 상태) 기준 (24 §2.8 단서). "
                "작은 규모에서는 포화하므로 절대 MB를 함께 읽어야 한다",
    }
