"""[24 §4] Scalability-의제 — 탄력성 c와 최대 의제 수, 지표 2종.

c는 **구조 특성**(조합이 늘 때 메모리가 어떻게 늘어나는가)이고,
최대 의제 수는 **수용 한계**(한도 안에서 몇 개까지 되는가)다. 서로 다른 질문이라 병행한다.
"""
from __future__ import annotations

import pytest

from total.qa.contract import SweepPoint
from total.qa.ru import MB
from total.qa.sc_issue import (
    completion_gate,
    elasticity,
    evaluate,
    loglog_fit,
    max_issues,
)


def pts(pairs, agreed=True, n_issues=4, base=0):
    return [SweepPoint(scale=s, peak_bytes=p, agreed=agreed, n_issues=n_issues,
                       base_bytes=base) for s, p in pairs]


class TestLoglogFit:
    def test_perfect_linear_slope_one(self):
        # peak ∝ S^1
        f = loglog_fit(pts([(10, 10), (100, 100), (1000, 1000), (10000, 10000)]))
        assert f.slope == pytest.approx(1.0, abs=1e-6)
        assert f.r2 == pytest.approx(1.0, abs=1e-6)

    def test_flat_slope_zero(self):
        f = loglog_fit(pts([(10, 50), (100, 50), (1000, 50), (10000, 50)]))
        assert f.slope == pytest.approx(0.0, abs=1e-6)

    def test_sqrt_slope_half(self):
        f = loglog_fit(pts([(100, 10), (10000, 100), (1000000, 1000)]))
        assert f.slope == pytest.approx(0.5, abs=1e-6)

    def test_confidence_interval_brackets_slope(self):
        f = loglog_fit(pts([(10, 11), (100, 98), (1000, 1020), (10000, 9800)]))
        assert f.ci_low <= f.slope <= f.ci_high

    def test_requires_three_points(self):
        with pytest.raises(ValueError):
            loglog_fit(pts([(10, 10), (100, 100)]))

    def test_groups_repeats_by_scale(self):
        # 같은 S를 여러 번 재면 중앙값으로 묶는다
        p = pts([(10, 10), (10, 30), (100, 100), (1000, 1000), (10000, 10000)])
        f = loglog_fit(p)
        assert f.n_levels == 4

    def test_zero_peak_does_not_crash(self):
        f = loglog_fit(pts([(10, 0), (100, 100), (1000, 1000), (10000, 10000)]))
        assert f.slope > 0


class TestElasticity:
    def test_stars_use_dataset_d(self):
        # d=4 → 0.40 이하가 5점
        p = pts([(10, 50), (100, 50), (1000, 50), (10000, 50)])
        assert elasticity(p, d=4).stars == 5

    def test_full_enumeration_is_one_star(self):
        p = pts([(10, 10), (100, 100), (1000, 1000), (10000, 10000)])
        assert elasticity(p, d=4).stars == 1

    def test_worse_than_full_enumeration_is_zero(self):
        p = pts([(10, 10), (100, 1000), (1000, 100000), (10000, 10000000)])
        e = elasticity(p, d=4)
        assert e.c > 1.0 and e.stars == 0

    def test_d_changes_boundary(self):
        # 같은 c라도 d가 크면 이론 이상값이 낮아져 등급이 짜진다
        p = pts([(10, 30), (100, 55), (1000, 100), (10000, 180)])
        e4, e10 = elasticity(p, d=4), elasticity(p, d=10)
        assert e4.band.thresholds[0] > e10.band.thresholds[0]

    def test_reports_ci_spanning_grades(self):
        # 24 §4.3 — 구간이 3개 이상 등급에 걸치면 재측정 신호
        p = pts([(10, 5), (100, 400), (1000, 100), (10000, 9000)])
        e = elasticity(p, d=4)
        assert isinstance(e.ci_spans_three_grades, bool)

    def test_as_dict(self):
        p = pts([(10, 50), (100, 50), (1000, 50), (10000, 50)])
        d = elasticity(p, d=4).as_dict()
        assert set(d) >= {"c", "ci_low", "ci_high", "r2", "stars", "band"}

    def test_uses_peak_only_base_excluded(self):
        # 24 §4 (2026-08-13) — 보조 관측 c는 프로토콜 상태만 회귀한다: 기저(설계로 못
        # 줄이는 하한)를 넣으면 전 방안이 c≈1로 수렴해 변별이 죽는다. 판정(최대 의제 수)이
        # 총 점유를 쓰므로 기저는 그쪽에서 반영된다.
        flat_peak = [(10, 50), (100, 50), (1000, 50), (10000, 50)]
        with_base = [SweepPoint(scale=s, peak_bytes=p, agreed=True, n_issues=4,
                                base_bytes=s * 10) for s, p in flat_peak]
        assert elasticity(with_base, d=4).c == elasticity(pts(flat_peak), d=4).c


class TestCompletionGate:
    """24 §4.4 — S가 커질 때 빨리 결렬해 메모리가 적게 나오는 왜곡을 잡는다."""

    def test_passes_when_completion_stable(self):
        p = pts([(10, 10)] * 10 + [(10000, 100)] * 10)
        assert completion_gate(p).ok is True

    def test_fails_when_completion_drops(self):
        small = [SweepPoint(10, 10, True, 4) for _ in range(30)]
        large = [SweepPoint(10000, 100, i < 5, 4) for i in range(30)]
        g = completion_gate(small + large)
        assert g.ok is False

    def test_reports_rates(self):
        small = [SweepPoint(10, 10, True, 4) for _ in range(10)]
        large = [SweepPoint(10000, 100, i < 5, 4) for i in range(10)]
        g = completion_gate(small + large)
        assert g.rate_small == pytest.approx(1.0)
        assert g.rate_large == pytest.approx(0.5)

    def test_needs_two_scales(self):
        with pytest.raises(ValueError):
            completion_gate(pts([(10, 10)]))

    def test_improvement_does_not_fail_gate(self):
        small = [SweepPoint(10, 10, i < 5, 4) for i in range(10)]
        large = [SweepPoint(10000, 100, True, 4) for _ in range(10)]
        assert completion_gate(small + large).ok is True


class TestMaxIssues:
    def test_finds_largest_within_limit(self):
        p = [SweepPoint(10 ** k, int(mb * MB), True, k)
             for k, mb in [(4, 0.1), (8, 1.0), (12, 40.0), (16, 300.0)]]
        r = max_issues(p, memory_limit_bytes=100 * MB)
        assert r.max_issues == 12

    def test_stars_from_band(self):
        p = [SweepPoint(10 ** k, int(mb * MB), True, k)
             for k, mb in [(10, 1.0), (20, 5.0), (30, 40.0)]]
        assert max_issues(p, memory_limit_bytes=100 * MB).stars == 5

    def test_zero_when_smallest_exceeds(self):
        p = [SweepPoint(100, 500 * MB, True, 4)]
        r = max_issues(p, memory_limit_bytes=100 * MB)
        assert r.max_issues == 0 and r.stars == 0

    def test_censored_when_nothing_exceeds(self):
        # 스윕이 한도에 도달하지 못했으면 max는 하한일 뿐이다 — 정직하게 표시
        p = [SweepPoint(10 ** k, MB, True, k) for k in (4, 8, 12)]
        r = max_issues(p, memory_limit_bytes=100 * MB)
        assert r.max_issues == 12 and r.censored is True

    def test_not_censored_when_limit_crossed(self):
        p = [SweepPoint(10 ** k, int(mb * MB), True, k)
             for k, mb in [(4, 1.0), (8, 300.0)]]
        assert max_issues(p, memory_limit_bytes=100 * MB).censored is False

    def test_uses_total_bytes(self):
        p = [SweepPoint(100, 50 * MB, True, 8, base_bytes=80 * MB)]
        assert max_issues(p, memory_limit_bytes=100 * MB).max_issues == 0

    def test_unagreed_points_excluded(self):
        # 결렬한 실행의 메모리는 "처리 가능"의 증거가 아니다
        p = [SweepPoint(10 ** k, MB, k < 12, k) for k in (4, 8, 12)]
        assert max_issues(p, memory_limit_bytes=100 * MB).max_issues == 8

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            max_issues([], memory_limit_bytes=MB)


class TestEvaluate:
    """두 지표 + 게이트를 한 번에."""

    def test_combines_both_metrics(self):
        p = [SweepPoint(10 ** k, int(0.1 * MB), True, k) for k in (4, 6, 8, 10)]
        r = evaluate(p, d=4, memory_limit_bytes=100 * MB)
        assert "elasticity" in r and "max_issues" in r and "gate" in r

    def test_gate_failure_zeroes_elasticity_stars(self):
        # 24 §4 (2026-08-13) — 게이트 위반은 보조 관측 c의 별점만 0으로 덮는다.
        # 판정(최대 의제 수)은 완결 실행만 세므로 defect는 서지 않는다.
        small = [SweepPoint(10, int(0.1 * MB), True, 4) for _ in range(30)]
        mid = [SweepPoint(1000, int(0.1 * MB), True, 8) for _ in range(30)]
        large = [SweepPoint(100000, int(0.1 * MB), i < 3, 12) for i in range(30)]
        r = evaluate(small + mid + large, d=4, memory_limit_bytes=100 * MB)
        assert r["gate"]["ok"] is False
        assert r["elasticity"]["stars"] == 0
        assert r["elasticity"]["auxiliary"] is True
        assert r["defect"] is False        # 12축까지 완결 실행 존재 — 요구 미달 아님
        assert r["max_issues"]["stars"] == 5

    def test_defect_only_on_requirement_miss(self):
        # defect = 요구 미달(최대 의제 수 < 4축)일 때만 (PL 확정 2026-08-13)
        only3 = ([SweepPoint(10, int(0.1 * MB), True, 3) for _ in range(30)]
                 + [SweepPoint(100, int(0.1 * MB), False, 4) for _ in range(30)]
                 + [SweepPoint(1000, int(0.1 * MB), False, 5) for _ in range(30)])
        r = evaluate(only3, d=4, memory_limit_bytes=100 * MB)
        assert r["max_issues"]["max_issues"] == 3
        assert r["defect"] is True

    def test_gate_pass_keeps_stars(self):
        p = [SweepPoint(10 ** k, int(0.1 * MB), True, k) for k in (4, 6, 8, 10)] * 5
        r = evaluate(p, d=4, memory_limit_bytes=100 * MB)
        assert r["defect"] is False
        assert r["elasticity"]["stars"] == 5
