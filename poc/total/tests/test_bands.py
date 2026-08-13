"""별점 밴드 유틸 — 경계값 동작을 고정한다.

밴드는 QA마다 방향(높을수록 좋음/낮을수록 좋음)과 경계 포함 여부(≥, ≤, >)가 다르다.
24 핸드북의 각 절이 쓰는 부등호를 그대로 재현하는 것이 이 모듈의 계약이다.
"""
from __future__ import annotations

import pytest

from total.qa.bands import (
    Band,
    even_bands_between,
    fraction_bands,
    stars_at_least,
    stars_at_most,
    stars_greater_than,
)


class TestStarsAtMost:
    """낮을수록 좋음 · 경계 포함 (24 §4.3 c, §7.3 m, §2.8 r)."""

    T = [0.40, 0.55, 0.70, 0.85, 1.00]  # 24 §4.3 d=4

    @pytest.mark.parametrize("value,expected", [
        (0.0, 5), (0.24, 5), (0.40, 5),      # 경계 포함
        (0.4001, 4), (0.55, 4),
        (0.5501, 3), (0.70, 3),
        (0.7001, 2), (0.85, 2),
        (0.8501, 1), (1.00, 1),
        (1.0001, 0), (99.0, 0),
    ])
    def test_boundaries(self, value, expected):
        assert stars_at_most(value, self.T) == expected

    def test_negative_is_best(self):
        # c는 음수가 나올 수 있다 (메모리가 S에 반비례) — 최상 등급이어야 한다
        assert stars_at_most(-0.5, self.T) == 5

    def test_thresholds_must_be_ascending(self):
        with pytest.raises(ValueError):
            stars_at_most(0.5, [0.5, 0.4, 0.3, 0.2, 0.1])

    def test_thresholds_must_be_five(self):
        with pytest.raises(ValueError):
            stars_at_most(0.5, [0.1, 0.2, 0.3])


class TestStarsAtLeast:
    """높을수록 좋음 · 경계 포함 (FC 달성률 밴드, SC 최대 축 수)."""

    T = [0.95, 0.90, 0.85, 0.80, 0.70]

    @pytest.mark.parametrize("value,expected", [
        (1.0, 5), (0.95, 5),
        (0.9499, 4), (0.90, 4),
        (0.8999, 3), (0.85, 3),
        (0.8499, 2), (0.80, 2),
        (0.7999, 1), (0.70, 1),
        (0.6999, 0), (0.0, 0),
    ])
    def test_boundaries(self, value, expected):
        assert stars_at_least(value, self.T) == expected

    def test_integer_thresholds(self):
        # 최대 축 수처럼 정수 지표에도 쓴다
        t = [12, 9, 7, 5, 4]  # 24 §4.3 — [4,12] 로그 등분 (2026-08-13)
        assert stars_at_least(32, t) == 5
        assert stars_at_least(12, t) == 5
        assert stars_at_least(10, t) == 4
        assert stars_at_least(8, t) == 3
        assert stars_at_least(6, t) == 2
        assert stars_at_least(4, t) == 1
        assert stars_at_least(3, t) == 0

    def test_thresholds_must_be_descending(self):
        with pytest.raises(ValueError):
            stars_at_least(0.9, [0.70, 0.80, 0.85, 0.90, 0.95])


class TestStarsGreaterThan:
    """낮을수록 나쁨 · 경계 제외 (24 §1.4 개선 비율 s — dp2 fc.stars_from_s와 동일)."""

    T = [0.8, 0.6, 0.4, 0.2, 0.0]

    @pytest.mark.parametrize("value,expected", [
        (1.0, 5), (0.81, 5),
        (0.80, 4),                            # 경계는 아래 등급 (strict >)
        (0.61, 4), (0.60, 3),
        (0.41, 3), (0.40, 2),
        (0.21, 2), (0.20, 1),
        (0.01, 1), (0.0, 0), (-1.0, 0),      # s ≤ 0 = 무작위만 못함
    ])
    def test_boundaries(self, value, expected):
        assert stars_greater_than(value, self.T) == expected


class TestEvenBandsBetween:
    """두 참조점 사이 5등분 (24 §4.3 — 이론 이상 1/d 와 전체 열거 1.0)."""

    def test_d4_matches_handbook(self):
        # 24 §4.3 표: 0.40 / 0.55 / 0.70 / 0.85 / 1.00
        assert even_bands_between(0.25, 1.0) == pytest.approx([0.40, 0.55, 0.70, 0.85, 1.00])

    def test_d10_recomputes(self):
        # "기준 시나리오의 의제 수 d가 바뀌면 하계 1/d와 구간 폭을 갱신한다" (24 §4.3)
        b = even_bands_between(0.1, 1.0)
        assert b[0] == pytest.approx(0.28)
        assert b[-1] == pytest.approx(1.0)
        assert len(b) == 5

    def test_widths_are_equal(self):
        b = even_bands_between(0.25, 1.0)
        widths = [b[i + 1] - b[i] for i in range(len(b) - 1)]
        assert all(w == pytest.approx(widths[0]) for w in widths)

    def test_rejects_inverted_range(self):
        with pytest.raises(ValueError):
            even_bands_between(1.0, 0.25)


class TestFractionBands:
    """한도 대비 비율 등분 (24 §2.8 — 15%p 폭 5구간, 초과는 0점)."""

    def test_handbook_default(self):
        assert fraction_bands(0.15) == pytest.approx([0.15, 0.30, 0.45, 0.60, 0.75])

    def test_full_ceiling_split(self):
        # 한도 전체를 5등분하고 싶을 때 (step=0.2)
        assert fraction_bands(0.2) == pytest.approx([0.2, 0.4, 0.6, 0.8, 1.0])

    def test_rejects_nonpositive_step(self):
        with pytest.raises(ValueError):
            fraction_bands(0.0)


class TestBand:
    """Band는 밴드 정의를 값과 함께 들고 다닌다 — 리포트가 근거를 출력하려면 필요."""

    def test_carries_definition(self):
        b = Band(name="c", thresholds=[0.4, 0.55, 0.7, 0.85, 1.0], direction="at_most",
                 note="24 §4.3 d=4")
        assert b.stars(0.3) == 5
        assert b.stars(1.5) == 0
        assert "24 §4.3" in b.note

    def test_direction_at_least(self):
        b = Band(name="달성률", thresholds=[0.95, 0.9, 0.85, 0.8, 0.7], direction="at_least")
        assert b.stars(0.96) == 5
        assert b.stars(0.5) == 0

    def test_direction_greater_than(self):
        b = Band(name="s", thresholds=[0.8, 0.6, 0.4, 0.2, 0.0], direction="greater_than")
        assert b.stars(0.8) == 4

    def test_unknown_direction_rejected(self):
        with pytest.raises(ValueError):
            Band(name="x", thresholds=[1, 2, 3, 4, 5], direction="sideways")

    def test_serialises_for_report(self):
        b = Band(name="c", thresholds=[0.4, 0.55, 0.7, 0.85, 1.0], direction="at_most",
                 note="24 §4.3")
        d = b.as_dict()
        assert d["name"] == "c"
        assert d["direction"] == "at_most"
        assert d["thresholds"] == [0.4, 0.55, 0.7, 0.85, 1.0]
        assert d["note"] == "24 §4.3"
