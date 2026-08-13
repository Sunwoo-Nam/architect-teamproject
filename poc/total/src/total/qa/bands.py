"""별점 밴드 — QA별 등급 경계를 한 곳에서 정의한다.

24 핸드북은 QA마다 다른 부등호를 쓴다. 그 차이를 코드로 고정해 두지 않으면
이식할 때마다 경계가 한 칸씩 밀린다:

- `at_most`      — 낮을수록 좋음, 경계 포함 (§4.3 탄력성 c, §7.3 노출 배수 m, §2.8 사용률 r)
- `at_least`     — 높을수록 좋음, 경계 포함 (FC 달성률 밴드, SC 최대 축 수)
- `greater_than` — 낮을수록 나쁨, 경계 **제외** (§1.4 개선 비율 s)

밴드는 값만 내지 않고 `Band`로 정의째 들고 다닌다 — 리포트가 "왜 이 별점인지"를
출력하려면 임계값과 출처가 함께 있어야 하기 때문이다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

STAR_LEVELS = 5


def _check(thresholds: list[float], ascending: bool) -> None:
    if len(thresholds) != STAR_LEVELS:
        raise ValueError(f"임계값은 {STAR_LEVELS}개여야 한다 (5점→1점): {thresholds}")
    pairs = list(zip(thresholds, thresholds[1:]))
    ok = all(a <= b for a, b in pairs) if ascending else all(a >= b for a, b in pairs)
    if not ok:
        order = "오름차순" if ascending else "내림차순"
        raise ValueError(f"임계값은 {order}이어야 한다: {thresholds}")


def stars_at_most(value: float, thresholds: list[float]) -> int:
    """낮을수록 좋음 · 경계 포함. thresholds는 오름차순 [5점, 4점, 3점, 2점, 1점]."""
    _check(thresholds, ascending=True)
    for stars, hi in zip(range(STAR_LEVELS, 0, -1), thresholds):
        if value <= hi:
            return stars
    return 0


def stars_at_least(value: float, thresholds: list[float]) -> int:
    """높을수록 좋음 · 경계 포함. thresholds는 내림차순 [5점, 4점, 3점, 2점, 1점]."""
    _check(thresholds, ascending=False)
    for stars, lo in zip(range(STAR_LEVELS, 0, -1), thresholds):
        if value >= lo:
            return stars
    return 0


def stars_greater_than(value: float, thresholds: list[float]) -> int:
    """높을수록 좋음 · 경계 **제외**. 24 §1.4의 s 판정이 `s > 0.8`처럼 strict다."""
    _check(thresholds, ascending=False)
    for stars, lo in zip(range(STAR_LEVELS, 0, -1), thresholds):
        if value > lo:
            return stars
    return 0


def even_bands_between(best: float, worst: float) -> list[float]:
    """두 참조점 사이를 5등분한 오름차순 임계값.

    24 §5.3: 전체 열거(c=1)와 이론 이상값(c=1/d) 사이를 5등분한다.
    d가 바뀌면 하계와 폭이 함께 바뀌므로 계산으로 얻어야 한다 — 상수 하드코딩 금지.
    """
    if not worst > best:
        raise ValueError(f"worst({worst})는 best({best})보다 커야 한다")
    width = (worst - best) / STAR_LEVELS
    return [best + width * i for i in range(1, STAR_LEVELS + 1)]


def fraction_bands(step: float) -> list[float]:
    """한도 대비 비율의 등분 임계값 (오름차순).

    24 §2.8: 한도 이내를 15%p 폭으로 등분하고 마지막 구간을 넘으면 0점.
    step=0.2면 한도 전체를 5등분한 것이 된다.
    """
    if step <= 0:
        raise ValueError(f"step은 양수여야 한다: {step}")
    return [step * i for i in range(1, STAR_LEVELS + 1)]


_DIRECTIONS = {
    "at_most": stars_at_most,
    "at_least": stars_at_least,
    "greater_than": stars_greater_than,
}


@dataclass(frozen=True)
class Band:
    """별점 밴드 정의 — 값·방향·출처를 함께 들고 다닌다."""

    name: str
    thresholds: list[float]
    direction: str
    note: str = field(default="")

    def __post_init__(self) -> None:
        if self.direction not in _DIRECTIONS:
            raise ValueError(
                f"direction은 {sorted(_DIRECTIONS)} 중 하나여야 한다: {self.direction}"
            )
        _DIRECTIONS[self.direction](self.thresholds[0], self.thresholds)  # 형식 검증

    def stars(self, value: float) -> int:
        return _DIRECTIONS[self.direction](value, self.thresholds)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "thresholds": list(self.thresholds),
            "direction": self.direction,
            "note": self.note,
        }
