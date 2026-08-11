"""[핸드북 §5-1] Fault Tolerance — 내성 여유 배수 (ENV-A 강도 스윕).

임계 강도 = 완결률이 무주입 베이스라인 대비 유의하게(단측 95%) 저하되기 시작하는
최소 주입 강도. 여유 배수 = 임계 강도 ÷ 실환경 오류율(p_env).

p_env는 정본으로는 ENV-B 실기기에서 실측하는 앵커다 — PoC(ENV-A)에서는 잠정값을
파라미터로 받으며 잠정임을 결과에 명시한다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from scipy import stats


@dataclass(frozen=True)
class FtResult:
    p_env: float
    multiples: list[float]
    agree_rates: dict[float, float]  # 배수 -> 완결률 (0.0 = 베이스라인)
    critical_multiple: float | None  # 첫 유의 저하 배수 (None = 최대 강도까지 저하 없음)
    margin: float  # 여유 배수 (임계 배수; 저하 없으면 max 초과로 처리)
    stars: int


def stars_ft(margin: float) -> int:
    """핸드북 §5-2 별점 — 앵커 1배(최소선)·10배(차수 안전 계수), 로그 등분."""
    if margin < 1.0:
        return 0
    if margin >= 10.0:
        return 5
    return min(4, max(1, 1 + int(math.log10(margin) / 0.25)))


def significant_drop(agreed_base: int, n_base: int, agreed: int, n: int) -> bool:
    """단측 두 비율 검정(95%) — 주입군 완결률이 베이스라인보다 유의하게 낮은가."""
    p1, p2 = agreed_base / n_base, agreed / n
    p = (agreed_base + agreed) / (n_base + n)
    se = math.sqrt(p * (1 - p) * (1 / n_base + 1 / n))
    if se == 0:
        return False
    return (p1 - p2) / se > stats.norm.ppf(0.95)


def evaluate(
    baseline_agreed: int,
    baseline_n: int,
    per_multiple: dict[float, tuple[int, int]],  # 배수 -> (완결 수, 표본 수)
    p_env: float,
) -> FtResult:
    multiples = sorted(per_multiple)
    rates = {0.0: baseline_agreed / baseline_n}
    critical = None
    for m in multiples:
        agreed, n = per_multiple[m]
        rates[m] = agreed / n
        if critical is None and significant_drop(baseline_agreed, baseline_n, agreed, n):
            critical = m
    margin = critical if critical is not None else multiples[-1] * 2  # 최대 강도 무저하 → 그 이상
    return FtResult(p_env, multiples, rates, critical, margin, stars_ft(margin))
