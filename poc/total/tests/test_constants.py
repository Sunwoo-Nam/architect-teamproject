"""측정 상수와 별점 밴드 정의 — 24 핸드북과의 동기화 지점.

상수가 바뀌면 결과가 바뀐다. 여기 값들은 24의 어느 절에서 왔는지를 코드가 들고 있어야
하고, 테스트가 그 값을 고정해 "모르는 사이에 바뀌는 것"을 막는다.
"""
from __future__ import annotations

import pytest

from total.qa.constants import (
    BAND_CF_M,
    BAND_FC_S,
    BAND_SC_MAX_ISSUES,
    RU_CEILING_BYTES,
    RU_STEP,
    SYNTH_TIME,
    band_ru_usage,
    band_sc_elasticity,
)


class TestSynthTimeConstants:
    """24 §4.4 — 합성 시간 모델의 세 상수."""

    def test_t_phase_is_75ms_one_way(self):
        # 24 §4.4-d: LTE 클라우드 릴레이 구간 분해 → 75ms (편도)
        assert SYNTH_TIME.t_phase_ms == 75.0

    def test_t_eval_is_measured_1p4us(self):
        # 24 §4.4-b: PoC 실측 1.394µs → 3µs 반올림
        assert SYNTH_TIME.t_eval_ms == 0.0014  # 실측 1.394µs 채택 — 24 §4.4-b (2026-08-13)

    def test_bw_is_20mbps(self):
        # 24 §4.4-c: LTE 20 Mbps
        assert SYNTH_TIME.bw_bytes_per_s == 2_500_000.0

    def test_bandwidth_delay_product(self):
        # t_phase × bw = BDP. 24 §4.4-c가 방안 우열을 가르는 양으로 지목한 값
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

    def test_achieved_is_the_fc_verdict_band(self):
        # 판정 = 달성률 (PL 확정 2026-08-13 재개정) — s는 보조로 유지된다
        from total.qa.constants import BAND_FC_ACHIEVED
        assert BAND_FC_ACHIEVED.stars(0.9142) == 4   # 구 functional 방안 1-A 실측 달성률
        assert BAND_FC_ACHIEVED.stars(0.95) == 5     # at_least — 경계 포함
        assert BAND_FC_ACHIEVED.stars(0.699) == 0
        assert BAND_FC_S.stars(0.3086) == 2          # 보조 s 밴드는 유지

    def test_bands_carry_source_note(self):
        assert "24" in BAND_FC_S.note


class TestCfBand:
    """24 §3.3 — 판정 = 노출률, 실측 앵커 사다리 (PL 확정 2026-08-14 3차), m은 보조."""

    def test_exposure_ladder(self):
        from total.qa.constants import BAND_CF_EXPOSURE
        # 앵커 2점 실측 등분 (2026-08-14 3차): naive SAOP 66% = ★2 · 1:1 30% = ★4, 18%p 간격
        assert BAND_CF_EXPOSURE.thresholds == [0.12, 0.30, 0.48, 0.66, 0.84]
        assert BAND_CF_EXPOSURE.direction == "at_most"   # 경계 포함 — TB/RU와 통일
        assert BAND_CF_EXPOSURE.stars(0.30) == 4         # 앵커: 1:1 협상 실측 (ext2 e₂ 0.2917)
        assert BAND_CF_EXPOSURE.stars(0.656) == 2        # 앵커: naive SAOP 유도 실측 65.6%
        assert BAND_CF_EXPOSURE.stars(0.317) == 3        # ext2 방안 1-A 실측 — ★4 경계 1.7%p 밖
        assert BAND_CF_EXPOSURE.stars(0.483) == 2        # ext2 방안 2 실측 — ★3 경계 0.3%p 밖
        assert BAND_CF_EXPOSURE.stars(0.079) == 5        # ext2 방안 2+ 실측
        assert BAND_CF_EXPOSURE.stars(0.85) == 0         # >84% — 사실상 전량 공개

    def test_full_exposure_is_zero_stars(self):
        # 전량 공개(100%)는 ★0 — 앵커 사다리에서는 >84% ★0에 자연 포섭 (별도 규칙 불요)
        from total.qa.cf import stars_exposure
        assert stars_exposure(1.0) == 0
        assert stars_exposure(0.999) == 0     # 3차 개정: ★1은 ≤84%까지만
        assert stars_exposure(0.84) == 1
        assert stars_exposure(0.12) == 5

    def test_aux_m_ladder(self):
        assert BAND_CF_M.thresholds == [0.25, 0.5, 1.0, 2.0, 4.0]
        assert BAND_CF_M.direction == "at_most"
        assert BAND_CF_M.stars(1.0) == 3          # 1:1 등가
        assert "보조" in BAND_CF_M.note


class TestScBands:
    """SC-의제도 지표 2개 — 탄력성 c(구조 특성)와 최대 의제 수(수용 한계)."""

    def test_elasticity_band_depends_on_d(self):
        # 24 §5.3: 하계 1/d. d가 바뀌면 경계가 바뀐다 — 하드코딩 금지
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
        # 24 §5.3 (2026-08-13) — [요구 4, 실사용 최대 12] 로그 등분
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

    def test_step_kept_for_20pp_reference(self):
        assert RU_STEP == 0.20   # 구 20%p 등분의 폭 — band_ru_usage_20pp 이력용

    def test_band_from_ceiling(self):
        # [1%,100%] 로그 4등분 — 2026-08-14 최종 확정 (20%p에서 복귀, PL):
        # ★5 경계 1% = 실사용 최대(≈10축)까지의 성장(약 100배, 실측 ×2.1/축) 여유
        b = band_ru_usage()
        assert b.thresholds == pytest.approx([1e-2, 10 ** -1.5, 1e-1, 10 ** -0.5, 1.0])
        assert b.direction == "at_most"

    def test_usage_stars(self):
        b = band_ru_usage()
        assert b.stars(0.003) == 5    # seq2 P95 0.30% — 실사용 최대까지 여유 = 만점
        assert b.stars(0.014) == 4    # FIN2 seq2 r 최대 1.4% — ★4 (1-3.2%)
        assert b.stars(0.0486) == 3   # FIN2 P6 r 최대 4.86% — ★3 (3.2-10%)
        assert b.stars(0.413) == 1    # FIN2 pool P95 41.3% — ★1 (32-100%)
        assert b.stars(2.2) == 0      # 한도 초과 — 즉시 결함

    def test_custom_ceiling_changes_nothing_in_band(self):
        # 밴드는 비율이므로 한도가 바뀌어도 경계는 같다 — 바뀌는 것은 r의 분모
        assert band_ru_usage().thresholds == band_ru_usage(step=0.20).thresholds

    def test_20pp_band_kept_for_reference(self):
        # 구 20%p 등분 — 한때 확정 후 변별 상실(FIN2 보고)로 로그 복귀. 이력 보존
        from total.qa.constants import band_ru_usage_20pp

        b = band_ru_usage_20pp()
        assert b.thresholds == pytest.approx([0.2, 0.4, 0.6, 0.8, 1.0])

    def test_linear_band_kept_for_reference(self):
        from total.qa.constants import band_ru_usage_linear

        b = band_ru_usage_linear(step=0.2)
        assert b.thresholds == pytest.approx([0.2, 0.4, 0.6, 0.8, 1.0])
