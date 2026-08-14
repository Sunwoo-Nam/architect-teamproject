"""[24 §2] Resource Utilization-메모리 — 프로세스 피크와 공통 기저를 각각.

두 값을 분리해 보는 이유: 공통 기저는 방안 선택으로 줄일 수 없는 하한이라
"설계로 어쩔 수 있는 부분"과 "구조적 하한"을 섞으면 안 된다 (24 §2.8 단서).
"""
from __future__ import annotations

import pytest

from total.qa.contract import SessionResult
from total.qa.ru import MB, aggregate, deep_size, measure, measure_peak


def mk(**kw) -> SessionResult:
    base = dict(plan="p", participants=["P0", "P1"], agreement="a",
                rounds=1, sweeps=1, phases=2, messages=2, bytes=10, eval_calls=4)
    base.update(kw)
    return SessionResult(**base)


class TestDeepSize:
    """공통 기저 계산용 — 중첩 컨테이너의 실제 바이트."""

    def test_counts_nested_containers(self):
        small = deep_size({"a": [1, 2]})
        big = deep_size({"a": [1, 2, 3, 4, 5, 6, 7, 8]})
        assert big > small

    def test_shared_object_counted_once(self):
        shared = [1, 2, 3]
        both = deep_size({"x": shared, "y": shared})
        assert both < deep_size({"x": [1, 2, 3], "y": [4, 5, 6]})

    def test_handles_cycles(self):
        a: list = [1]
        a.append(a)
        assert deep_size(a) > 0     # 무한 재귀하지 않는다

    def test_scalar(self):
        assert deep_size(1) > 0


class TestMeasurePeak:
    """tracemalloc 래퍼 — 협상 구간의 피크 증가분."""

    def test_returns_result_and_peak(self):
        out, peak = measure_peak(lambda: [0] * 100_000)
        assert len(out) == 100_000
        assert peak > 100_000

    def test_trivial_call_is_small(self):
        _, peak = measure_peak(lambda: None)
        assert peak < 100_000

    def test_propagates_exception_and_stops_tracing(self):
        import tracemalloc

        with pytest.raises(RuntimeError):
            measure_peak(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        assert not tracemalloc.is_tracing()   # finally로 반드시 끈다


class TestMeasure:
    def test_reports_peak_and_base_separately(self):
        m = measure(mk(peak_bytes=2 * MB, base_bytes=8 * MB))
        assert m.peak_bytes == 2 * MB
        assert m.base_bytes == 8 * MB

    def test_total_is_sum(self):
        m = measure(mk(peak_bytes=2 * MB, base_bytes=8 * MB))
        assert m.total_bytes == 10 * MB

    def test_mb_views(self):
        m = measure(mk(peak_bytes=2 * MB, base_bytes=8 * MB))
        assert m.peak_mb == pytest.approx(2.0)
        assert m.total_mb == pytest.approx(10.0)

    def test_usage_is_total_over_ceiling(self):
        # 24 §2.8 단서 — r 판정은 단말 총 점유 기준
        m = measure(mk(peak_bytes=2 * MB, base_bytes=8 * MB), ceiling_bytes=100 * MB)
        assert m.r_total == pytest.approx(0.10)

    def test_peak_usage_reported_too(self):
        m = measure(mk(peak_bytes=2 * MB, base_bytes=8 * MB), ceiling_bytes=100 * MB)
        assert m.r_peak == pytest.approx(0.02)

    def test_stars_from_total_usage(self):
        # r=0.10 → [1%,100%] 로그 4등분(최종 확정)에서 ≤10% → 3점
        m = measure(mk(peak_bytes=2 * MB, base_bytes=8 * MB), ceiling_bytes=100 * MB)
        assert m.stars == 3

    def test_stars_zero_over_ceiling(self):
        m = measure(mk(peak_bytes=200 * MB, base_bytes=0), ceiling_bytes=100 * MB)
        assert m.stars == 0

    def test_over_ceiling_flagged(self):
        m = measure(mk(peak_bytes=200 * MB, base_bytes=0), ceiling_bytes=100 * MB)
        assert m.over_ceiling is True

    def test_within_ceiling_not_flagged(self):
        m = measure(mk(peak_bytes=10 * MB, base_bytes=0), ceiling_bytes=100 * MB)
        assert m.over_ceiling is False

    def test_rejects_nonpositive_ceiling(self):
        with pytest.raises(ValueError):
            measure(mk(), ceiling_bytes=0)

    def test_as_dict_carries_ceiling_and_band(self):
        d = measure(mk(peak_bytes=MB, base_bytes=MB), ceiling_bytes=100 * MB).as_dict()
        assert d["ceiling_bytes"] == 100 * MB
        assert "band" in d and d["band"]["direction"] == "at_most"


class TestRealDataRegression:
    """dpca 실측(scaling_raw.jsonl)으로 밴드가 실제로 변별하는지 확인."""

    @pytest.mark.parametrize("peak_mb,expected_stars", [
        # [1%,100%] 로그 4등분 (최종 확정 — 20%p에서 복귀: 선형은 0.18과 8.23을
        # 같은 ★5로 뭉갰다. 46배 차이를 로그 사다리가 변별한다 — 24 §2.8 기록).
        (0.18, 5),     # seq2 16축 — r 0.14% (실사용 최대까지 여유 = 만점)
        (8.23, 3),     # pool 16축 — r 6.4% (★3: 3.2-10%)
        (70.0, 1),     # 합성 지점 — r 54.7% (★1: 32-100%)
        (136.43, 0),   # pool 20축 — 107%: 협상 몫 한도(128MB)에서 즉시 결함
        (563.44, 0),   # pool 22축 — 한도 초과
    ])
    def test_dpca_scaling_points(self, peak_mb, expected_stars):
        m = measure(mk(peak_bytes=int(peak_mb * MB)))
        assert m.stars == expected_stars


class TestAggregate:
    def test_verdict_is_max_based(self):
        # 표본 별점 = P95·최대 2케이스 병행, 단일 인용 대표 = 최대 (24 §2.8 3차)
        rows = [measure(mk(peak_bytes=p * MB)) for p in (1, 1, 60)]
        agg = aggregate(rows)
        assert agg["stars_max"] == 1      # 60/128 = 46.9% — 최악 케이스의 등급 (로그 ★1)
        assert agg["stars_median"] == 5   # 1/128 = 0.78% — 전형은 병기

    def test_median_across_sessions(self):
        rows = [measure(mk(peak_bytes=p * MB)) for p in (1, 5, 9)]
        agg = aggregate(rows)
        assert agg["median_peak_mb"] == pytest.approx(5.0)

    def test_reports_max_for_worst_case(self):
        rows = [measure(mk(peak_bytes=p * MB)) for p in (1, 5, 9)]
        assert aggregate(rows)["max_total_mb"] == pytest.approx(9.0)

    def test_counts_over_ceiling(self):
        rows = [measure(mk(peak_bytes=p * MB), ceiling_bytes=4 * MB) for p in (1, 5, 9)]
        assert aggregate(rows)["over_ceiling_sessions"] == 2

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            aggregate([])
