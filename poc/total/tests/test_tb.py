"""[24 §6] Time Behaviour — 합성 시간 모델.

T = phase×t_phase + (eval÷N)×t_eval + bytes÷bw

세 가지를 못박는다:
- t_phase는 **편도** (phase는 수집·배포·회신 각각 1회이고 모두 한 방향)
- 평가 항은 **÷N 병렬 보정** (참여자가 각자 자기 단말에서 동시에 평가)
- 전송 항은 **나누지 않는다** (담당자 링크를 전원이 공유)
"""
from __future__ import annotations

import pytest

from total.qa.constants import SynthTimeConstants
from total.qa.contract import SessionResult
from total.qa.tb import aggregate, synth_time


def mk(**kw) -> SessionResult:
    base = dict(plan="p", participants=["P0", "P1", "P2"], agreement="a",
                rounds=1, sweeps=1, phases=10, messages=6, bytes=1000, eval_calls=300)
    base.update(kw)
    return SessionResult(**base)


class TestSynthTime:
    def test_phase_term(self):
        t = synth_time(mk(phases=10, eval_calls=0, bytes=0))
        assert t.phase_ms == pytest.approx(10 * 75.0)

    def test_eval_term_is_divided_by_n(self):
        # 24 §6.4-a — eval_calls는 전 참여자 합. 실제로는 N대가 동시에 한다
        t = synth_time(mk(phases=0, bytes=0, eval_calls=300, participants=["a", "b", "c"]))
        assert t.eval_ms == pytest.approx(300 / 3 * 0.0014)

    def test_transfer_term_is_not_divided(self):
        t = synth_time(mk(phases=0, eval_calls=0, bytes=2_500_000))
        assert t.transfer_ms == pytest.approx(1000.0)   # 20 Mbps로 2.5MB = 1초

    def test_total_is_sum(self):
        t = synth_time(mk())
        assert t.total_ms == pytest.approx(t.phase_ms + t.eval_ms + t.transfer_ms)

    def test_dominant_phase(self):
        t = synth_time(mk(phases=100, eval_calls=1, bytes=1))
        assert t.dominant == "phase"

    def test_dominant_transfer(self):
        t = synth_time(mk(phases=1, eval_calls=1, bytes=10_000_000))
        assert t.dominant == "transfer"

    def test_dominant_eval(self):
        t = synth_time(mk(phases=0, bytes=0, eval_calls=10_000_000))
        assert t.dominant == "eval"

    def test_custom_constants(self):
        c = SynthTimeConstants(t_phase_ms=50.0, t_eval_ms=0.003, bw_bytes_per_s=125_000.0)
        t = synth_time(mk(phases=10, eval_calls=0, bytes=0), c)
        assert t.phase_ms == pytest.approx(500.0)

    def test_zero_session(self):
        t = synth_time(mk(phases=0, eval_calls=0, bytes=0))
        assert t.total_ms == 0.0

    def test_single_participant_no_division_error(self):
        t = synth_time(mk(participants=["only"], eval_calls=10, phases=0, bytes=0))
        assert t.eval_ms == pytest.approx(10 * 0.0014)  # t_eval 실측 1.4µs (24 §6.4-b, 2026-08-13)

    def test_as_dict(self):
        d = synth_time(mk()).as_dict()
        assert set(d) >= {"total_ms", "phase_ms", "eval_ms", "transfer_ms", "dominant"}


class TestRegression:
    """실측 기준값 재현 — dp2 full-20260812T171034KST의 TB 항별 분해."""

    def test_nparty_plan1a_n3(self):
        # 기준값 재현 (t_eval 1.4µs 개정 반영, 2026-08-13): 평가 = 100÷3×0.0014ms
        t = synth_time(mk(participants=["P0", "P1", "P2"], phases=26,
                          eval_calls=100, bytes=1750))
        assert t.phase_ms == pytest.approx(1950.0)
        assert t.eval_ms == pytest.approx(100 / 3 * 0.0014)
        assert t.transfer_ms == pytest.approx(0.7)
        assert t.dominant == "phase"


class TestAggregate:
    def test_median_of_sessions(self):
        rows = [synth_time(mk(phases=p, eval_calls=0, bytes=0)) for p in (10, 20, 30)]
        agg = aggregate(rows)
        assert agg["median_total_ms"] == pytest.approx(20 * 75.0)
        assert agg["sessions"] == 3

    def test_reports_dominant_of_median_session(self):
        rows = [synth_time(mk(phases=10, eval_calls=0, bytes=0))]
        assert aggregate(rows)["dominant"] == "phase"

    def test_includes_constants_for_provenance(self):
        agg = aggregate([synth_time(mk())])
        assert agg["constants"]["t_phase_ms"] == 75.0

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            aggregate([])
