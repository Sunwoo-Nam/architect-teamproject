"""[25 / 21 §21.3-5] 확장 지수 회귀 — 참여자 수(b_msg)·의제 수(c) 공용.

log y = a + b·log x 최소제곱 회귀로 지수 b와 95% 신뢰구간, R²를 구하고,
25번 별점 척도(선형 1 - 제곱 2 구간 5등분)로 등급을 낸다.
완결률 게이트(§25.4): 최소 N vs 최대 N 완결률의 비율 차 검정(95%) — 저하 확인 시 0점.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class FitResult:
    b: float
    ci_low: float
    ci_high: float
    r2: float
    n_points: int


def loglog_fit(xs: list[float], ys: list[float]) -> FitResult:
    lx, ly = np.log(np.asarray(xs, float)), np.log(np.asarray(ys, float))
    res = stats.linregress(lx, ly)
    dof = len(xs) - 2
    t = stats.t.ppf(0.975, dof)
    return FitResult(
        b=float(res.slope),
        ci_low=float(res.slope - t * res.stderr),
        ci_high=float(res.slope + t * res.stderr),
        r2=float(res.rvalue**2),
        n_points=len(xs),
    )


def stars_b_msg(b: float) -> int:
    """25번 §25.3 — 선형(1)-제곱(2) 구간을 폭 0.2로 등분."""
    if b <= 1.0:
        return 5
    if b > 1.8:
        return 0
    return 5 - math.ceil(round((b - 1.0), 10) / 0.2)


def ci_spans_grades(fit: FitResult) -> bool:
    """신뢰구간이 3개 이상 등급에 걸치면 표본 확대 신호 (§25.3 통계 처리)."""
    grades = {stars_b_msg(v) for v in (fit.ci_low, fit.b, fit.ci_high)}
    return len(grades) >= 3


def completion_gate(agreed_small: int, n_small: int, agreed_large: int, n_large: int) -> bool:
    """완결률 게이트 — 최대 N의 완결률이 최소 N 대비 유의하게(단측 95%) 낮으면 False(게이트 위반)."""
    p1, p2 = agreed_small / n_small, agreed_large / n_large
    p = (agreed_small + agreed_large) / (n_small + n_large)
    se = math.sqrt(p * (1 - p) * (1 / n_small + 1 / n_large))
    if se == 0:
        return True
    z = (p1 - p2) / se
    return z < stats.norm.ppf(0.95)  # 저하가 유의하면 z가 커진다


def stars_c(c: float, d: int = 4) -> int:
    """27 §27.3 — 전체 열거(1)와 이론 이상(1/d) 사이 5등분. c > 1이면 0점."""
    lo = 1.0 / d
    if c > 1.0:
        return 0
    if c <= lo + (1.0 - lo) / 5:
        return 5
    width = (1.0 - lo) / 5
    return max(1, 5 - math.ceil(round((c - lo) / width, 10)) + 1)


def stars_n_max(n_max: int) -> int:
    """판정 ① N_max 별점 — [7, 50] 로그 등분 반올림 경계 (잠정, 핸드북 §3.3).
    7명 미만 = 요구(참여자 3-7명) 미달 — 즉시 결함(0점)."""
    for stars, lo in ((5, 34), (4, 23), (3, 16), (2, 11), (1, 7)):
        if n_max >= lo:
            return stars
    return 0


def stars_b_mem(b: float) -> int:
    """판정 ② b_mem 별점 — 무증가(0)-선형(1) 5등분 (잠정, 핸드북 §3.3)."""
    for stars, hi in ((5, 0.2), (4, 0.4), (3, 0.6), (2, 0.8), (1, 1.0)):
        if b <= hi:
            return stars
    return 0
