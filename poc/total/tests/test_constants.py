"""측정 상수와 별점 밴드 정의 — 24 핸드북과의 동기화 지점.

상수가 바뀌면 결과가 바뀐다. 여기 값들은 24의 어느 절에서 왔는지를 코드가 들고 있어야
하고, 테스트가 그 값을 고정해 "모르는 사이에 바뀌는 것"을 막는다.
"""
from __future__ import annotations

import pytest

from total.qa.constants import (
    BAND_CF_M,
    BAND_FC_ACHIEVED,
    BAND_FC_S,
    BAND_SC_MAX_ISSUES,
    RU_CEILING_BYTES,
    RU_STEP,
    SYNTH_TIME,
    band_ru_usage,
    band_sc_elasticity,
)


class TestSynthTimeConstants:
    """24 §6.4 — 합성 시간 모델의 세 상수."""

    def test_t_phase_is_75ms_one_way(self):
        # 24 §6.4-d: LTE 클라우드 릴레이 구간 분해 → 75ms (편도)
        assert SYNTH_TIME.t_phase_ms == 75.0

    def test_t_eval_is_measured_1p4us(self):
        # 24 §6.4-b: PoC 실측 1.394µs → 3µs 반올림
        assert SYNTH_TIME.t_eval_ms == 0.0014  # 실측 1.394µs 채택 — 24 §6.4-b (2026-08-13)

    def test_bw_is_20mbps(self):
        # 24 §6.4-c: LTE 20 Mbps
        assert SYNTH_TIME.bw_bytes_per_s == 2_500_000.0

    def test_bandwidth_delay_product(self):
        # t_phase × bw = BDP. 24 §6.4-c가 방안 우열을 가르는 양으로 지목한 값
        assert SYNTH_TIME.bdp_bytes == pytest.approx(0.075 * 2_500_000)

    def test_as_dict_for_report(self):
        d = SYNTH_TIME.as_dict()
        assert d["t_phase_ms"] == 75.0 and d["bw_bytes_per_s"] == 2_500_000.0

    def test_is_frozen(self):
        with pytest.raises(Exception):
            SYNTH_TIME.t_phase_ms = 50.0  # type: ignore[misc]


class TestFcBands:
    """FC는 지표 2개를 병행한다 — 달성률(절대)과 개선 비율 s(베이스라인 정규화)."""

    def test_s_band_matches_handbook(self):
        # 24 §1.4 — strict > 경계
        assert BAND_FC_S.direction == "greater_than"
        assert BAND_FC_S.thresholds == [0.8, 0.6, 0.4, 0.2, 0.0]

    def test_s_band_boundary_is_strict(self):
        assert BAND_FC_S.stars(0.8) == 4      # 경계는 아래 등급
        assert BAND_FC_S.stars(0.81) == 5
        assert BAND_FC_S.stars(0.0) == 0

    def test_achieved_band_is_absolute(self):
        assert BAND_FC_ACHIEVED.direction == "at_least"
        assert BAND_FC_ACHIEVED.thresholds == [0.95, 0.90, 0.85, 0.80, 0.70]

    def test_achieved_band_values(self):
        assert BAND_FC_ACHIEVED.stars(0.9679) == 5   # dp2 방안 2 실측
        assert BAND_FC_ACHIEVED.stars(0.9142) == 4   # dp2 방안 1-A 실측
        assert BAND_FC_ACHIEVED.stars(0.69) == 0

    def test_two_bands_can_disagree(self):
        # 두 지표를 병행하는 이유 — 절대 달성률은 높은데 베이스라인 대비 개선은 작을 수 있다
        assert BAND_FC_ACHIEVED.stars(0.9142) == 4
        assert BAND_FC_S.stars(0.3086) == 2

    def test_bands_carry_source_note(self):
        assert "24" in BAND_FC_S.note
        assert BAND_FC_ACHIEVED.note


class TestCfBand:
    """24 §7.3 — 노출 배수 m. 3점 경계가 1:1 등가."""

    def test_ladder(self):
        assert BAND_CF_M.thresholds == [0.25, 0.5, 1.0, 2.0, 4.0]
        assert BAND_CF_M.direction == "at_most"

    def test_one_to_one_equivalence_is_three_stars(self):
        assert BAND_CF_M.stars(1.0) == 3

    def test_real_values(self):
        assert BAND_CF_M.stars(0.677) == 3    # dp2 방안 1-A 실측
        assert BAND_CF_M.stars(1.184) == 2    # dp2 방안 2 실측

    def test_note_marks_provisional(self):
        # 24 §7.3이 "잠정 — PL 조율 예정"이라고 명시한 상태다
        assert "잠정" in BAND_CF_M.note


class TestScBands:
    """SC-의제도 지표 2개 — 탄력성 c(구조 특성)와 최대 의제 수(수용 한계)."""

    def test_elasticity_band_depends_on_d(self):
        # 24 §4.3: 하계 1/d. d가 바뀌면 경계가 바뀐다 — 하드코딩 금지
        b4 = band_sc_elasticity(d=4)
        assert b4.thresholds == pytest.approx([0.40, 0.55, 0.70, 0.85, 1.00])

    def test_elasticity_band_d10(self):
        b10 = band_sc_elasticity(d=10)
        assert b10.thresholds[0] == pytest.approx(0.28)
        assert b10.thresholds[-1] == pytest.approx(1.0)

    def test_elasticity_stars(self):
        b = band_sc_elasticity(d=4)
        assert b.stars(0.024) == 5     # dpca pool 실측
        assert b.stars(0.943) == 1     # dpca full 실측
        assert b.stars(1.85) == 0      # dp2 방안 2 b_mem 수준

    def test_elasticity_rejects_bad_d(self):
        with pytest.raises(ValueError):
            band_sc_elasticity(d=0)
        with pytest.raises(ValueError):
            band_sc_elasticity(d=1)   # 1/d = 1 이면 등분 구간이 없다

    def test_max_issues_band(self):
        assert BAND_SC_MAX_ISSUES.direction == "at_least"
        assert BAND_SC_MAX_ISSUES.thresholds == [12, 9, 7, 5, 4]  # [4,12] 로그 등분 (2026-08-13)

    def test_max_issues_stars(self):
        # 24 §4.3 (2026-08-13) — [요구 4, 실사용 최대 12] 로그 등분
        assert BAND_SC_MAX_ISSUES.stars(12) == 5   # 실사용 최대 커버 = 만점
        assert BAND_SC_MAX_ISSUES.stars(9) == 4
        assert BAND_SC_MAX_ISSUES.stars(7) == 3
        assert BAND_SC_MAX_ISSUES.stars(5) == 2
        assert BAND_SC_MAX_ISSUES.stars(4) == 1    # 요구(기준 시나리오 4축) 딱 충족
        assert BAND_SC_MAX_ISSUES.stars(3) == 0    # 요구 미달 — 즉시 결함


class TestRuBand:
    """RU는 절대 MB를 한도로 나눈 사용률 r로 판정한다 (24 §2.8)."""

    def test_ceiling_is_documented(self):
        # 협상 몫 한도 = 256MB × 75%(GC 여유) − 64MB(앱 기본, 잠정) = 128MB — 24 §2.8 (2026-08-13)
        assert RU_CEILING_BYTES == 128 * 1024 * 1024

    def test_step_is_handbook_15pp(self):
        assert RU_STEP == 0.15

    def test_band_from_ceiling(self):
        b = band_ru_usage()
        assert b.thresholds == pytest.approx([0.15, 0.30, 0.45, 0.60, 0.75])
        assert b.direction == "at_most"

    def test_usage_stars(self):
        b = band_ru_usage()
        assert b.stars(0.03) == 5     # dpca pool 16축 8.23MB / 256MB
        assert b.stars(0.53) == 2     # dpca pool 20축 136MB / 256MB
        assert b.stars(2.2) == 0      # dpca pool 22축 563MB / 256MB — 한도 초과

    def test_custom_ceiling_changes_nothing_in_band(self):
        # 밴드는 비율이므로 한도가 바뀌어도 경계는 같다 — 바뀌는 것은 r의 분모
        assert band_ru_usage().thresholds == band_ru_usage(step=0.15).thresholds

    def test_custom_step_splits_full_ceiling(self):
        b = band_ru_usage(step=0.2)
        assert b.thresholds == pytest.approx([0.2, 0.4, 0.6, 0.8, 1.0])
