r"""[24 §4] Scalability-의제 — 지표 2종을 병행한다.

| 지표 | 질문 | 성격 |
|---|---|---|
| **탄력성 c** | 조합 수가 늘 때 메모리가 어떻게 늘어나는가 | 구조 특성 |
| **최대 의제 수** | 메모리 한도 안에서 몇 개까지 되는가 | 수용 한계 |

둘은 다른 질문이다 — c가 좋아도(증가가 완만해도) 절대 수준이 이미 높으면 몇 개 못 넣고,
c가 나빠도 시작이 작으면 꽤 넣을 수 있다. 그래서 둘 다 낸다 (사용자 지시 2026-08-12).

**메모리는 단말 총 점유(공통 기저 + 프로토콜 상태)로 본다** — 24 §2.8 단서. 공통 기저가
조합 수에 비례하므로, 기저를 빼면 "조합이 늘어도 메모리가 안 는다"는 틀린 그림이 나온다.

**완결률 게이트** (24 §4.4): S가 커질 때 빨리 결렬해 버리면 깊은 라운드에 도달하지 않아
메모리가 적게 나온다 — "많이 실패해서 탄력성이 좋아지는" 왜곡이다. 최소 S와 최대 S의
완결률을 비율 차 검정(95%)으로 비교해, 유의하게 떨어지면 **c와 무관하게 0점 + 결함 보고**.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

from scipy import stats

from .bands import Band
from .constants import BAND_SC_MAX_ISSUES, RU_CEILING_BYTES, band_sc_elasticity
from .contract import SweepPoint

MIN_LEVELS = 3


@dataclass(frozen=True)
class FitResult:
    slope: float
    ci_low: float
    ci_high: float
    r2: float
    n_levels: int


def _by_scale(points: Sequence[SweepPoint]) -> dict[int, list[SweepPoint]]:
    grouped: dict[int, list[SweepPoint]] = defaultdict(list)
    for p in points:
        grouped[p.scale].append(p)
    return dict(grouped)


def loglog_fit(points: Sequence[SweepPoint]) -> FitResult:
    """log(총 점유)를 log(S)에 회귀한 기울기와 95% 신뢰구간.

    같은 S를 여러 번 잰 경우 중앙값으로 묶는다 — 반복 실행의 분산이 기울기를
    흔들지 않도록.
    """
    grouped = _by_scale(points)
    if len(grouped) < MIN_LEVELS:
        raise ValueError(f"회귀에는 서로 다른 S가 {MIN_LEVELS}개 이상 필요하다: {len(grouped)}")

    xs, ys = [], []
    for scale in sorted(grouped):
        med = statistics.median(p.total_bytes for p in grouped[scale])
        xs.append(math.log(scale))
        ys.append(math.log(max(med, 1e-9)))   # 0 바이트 방어 — log(0) 회피

    res = stats.linregress(xs, ys)
    dof = max(1, len(xs) - 2)
    t = stats.t.ppf(0.975, dof)
    return FitResult(
        slope=float(res.slope),
        ci_low=float(res.slope - t * res.stderr),
        ci_high=float(res.slope + t * res.stderr),
        r2=float(res.rvalue ** 2),
        n_levels=len(xs),
    )


@dataclass(frozen=True)
class Elasticity:
    c: float
    ci_low: float
    ci_high: float
    r2: float
    n_levels: int
    stars: int
    band: Band
    ci_spans_three_grades: bool

    def as_dict(self) -> dict:
        return {
            "c": round(self.c, 4),
            "ci_low": round(self.ci_low, 4),
            "ci_high": round(self.ci_high, 4),
            "r2": round(self.r2, 4),
            "n_levels": self.n_levels,
            "stars": self.stars,
            "ci_spans_three_grades": self.ci_spans_three_grades,
            "band": self.band.as_dict(),
        }


def elasticity(points: Sequence[SweepPoint], d: int) -> Elasticity:
    """탄력성 c와 별점. `d`는 데이터셋의 의제 수 — 별점 하계 1/d를 정한다."""
    fit = loglog_fit(points)
    band = band_sc_elasticity(d)
    grades = {band.stars(v) for v in (fit.ci_low, fit.slope, fit.ci_high)}
    return Elasticity(
        c=fit.slope,
        ci_low=fit.ci_low,
        ci_high=fit.ci_high,
        r2=fit.r2,
        n_levels=fit.n_levels,
        stars=band.stars(fit.slope),
        band=band,
        ci_spans_three_grades=len(grades) >= 3,
    )


@dataclass(frozen=True)
class GateResult:
    ok: bool
    rate_small: float
    rate_large: float
    scale_small: int
    scale_large: int
    z: float

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "rate_small": round(self.rate_small, 4),
            "rate_large": round(self.rate_large, 4),
            "scale_small": self.scale_small,
            "scale_large": self.scale_large,
            "z": round(self.z, 4),
            "note": "24 §4.4 — 최소 S 대비 최대 S의 완결률이 유의하게 떨어지면 실패",
        }


def completion_gate(points: Sequence[SweepPoint]) -> GateResult:
    """완결률 게이트 (24 §4.4). 단측 비율 차 검정 95%.

    **저하만** 본다 — 큰 S에서 완결률이 오히려 오르는 것은 왜곡이 아니다.
    """
    grouped = _by_scale(points)
    if len(grouped) < 2:
        raise ValueError(f"게이트에는 서로 다른 S가 2개 이상 필요하다: {len(grouped)}")

    lo, hi = min(grouped), max(grouped)
    small, large = grouped[lo], grouped[hi]
    n1, n2 = len(small), len(large)
    x1 = sum(1 for p in small if p.agreed)
    x2 = sum(1 for p in large if p.agreed)
    p1, p2 = x1 / n1, x2 / n2

    pooled = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    z = 0.0 if se == 0 else (p1 - p2) / se
    return GateResult(
        ok=bool(z < stats.norm.ppf(0.95)),
        rate_small=p1, rate_large=p2, scale_small=lo, scale_large=hi, z=z,
    )


@dataclass(frozen=True)
class MaxIssues:
    max_issues: int
    stars: int
    memory_limit_bytes: int
    censored: bool          # 스윕이 한도에 도달하지 못함 → 값은 하한일 뿐
    band: Band

    def as_dict(self) -> dict:
        return {
            "max_issues": self.max_issues,
            "stars": self.stars,
            "memory_limit_bytes": self.memory_limit_bytes,
            "censored": self.censored,
            "band": self.band.as_dict(),
            "note": "한도 안에서 정상 완결한 최대 의제 수. censored=true면 스윕이 한도에 "
                    "닿지 못해 실제 최대는 이보다 클 수 있다",
        }


def max_issues(
    points: Sequence[SweepPoint],
    memory_limit_bytes: int = RU_CEILING_BYTES,
) -> MaxIssues:
    """한도 안에서 **정상 완결**한 최대 의제 수.

    결렬한 실행은 세지 않는다 — 메모리를 덜 썼더라도 "처리 가능"의 증거가 아니다.
    """
    if not points:
        raise ValueError("측정점이 없다")

    by_issues: dict[int, list[SweepPoint]] = defaultdict(list)
    for p in points:
        by_issues[p.n_issues].append(p)

    fits: list[int] = []
    exceeded = False
    for k in sorted(by_issues):
        agreed = [p for p in by_issues[k] if p.agreed]
        if not agreed:
            exceeded = True
            continue
        med = statistics.median(p.total_bytes for p in agreed)
        if med <= memory_limit_bytes:
            fits.append(k)
        else:
            exceeded = True

    best = max(fits) if fits else 0
    return MaxIssues(
        max_issues=best,
        stars=BAND_SC_MAX_ISSUES.stars(best),
        memory_limit_bytes=memory_limit_bytes,
        censored=(not exceeded),
        band=BAND_SC_MAX_ISSUES,
    )


def evaluate(
    points: Sequence[SweepPoint],
    d: int,
    memory_limit_bytes: int = RU_CEILING_BYTES,
) -> dict:
    """두 지표 + 완결률 게이트를 한 번에.

    게이트가 실패하면 탄력성 별점을 0으로 덮고 `defect=True`로 보고한다 (24 §4.4).
    최대 의제 수는 완결한 실행만 세므로 게이트와 독립이라 덮지 않는다.
    """
    e = elasticity(points, d)
    m = max_issues(points, memory_limit_bytes)
    gate = completion_gate(points)

    e_dict = e.as_dict()
    if not gate.ok:
        e_dict["stars"] = 0
        e_dict["stars_overridden_by_gate"] = True

    return {
        "elasticity": e_dict,
        "max_issues": m.as_dict(),
        "gate": gate.as_dict(),
        "defect": not gate.ok,
        "d": d,
    }
