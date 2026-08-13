"""[24 §3] Confidentiality — 노출 깊이·e₂ 앵커·노출 배수 m·정규화 노출률.

이 모듈의 존재 이유 중 절반은 **방안별 가시 규칙이 사라졌다**는 것이다.
기존 dp2 `confidentiality._visible_events()`는 방안 12종의 if-else 체인이었다.
여기서는 `ObservationEvent.audience`만 보므로 측정기가 방안을 몰라도 된다.
"""
from __future__ import annotations

import pytest

from total.qa.cf import (
    COORDINATOR_FIRST,
    E2Anchor,
    Viewpoint,
    depth,
    e2_anchor,
    estimate_top1,
    evaluate,
    exposure_multiple,
    inference_gain,
    observed_subs,
    valid_count,
    worst_participant,
)
from total.qa.contract import ObservationEvent, SessionResult, TableCase, TablePreference

# 후보 4개, 순위 a > b > c > d (P1 기준)
P0 = TablePreference("P0", {"a": 0.9, "b": 0.7, "c": 0.5, "d": 0.3}, 0.0)
P1 = TablePreference("P1", {"a": 0.8, "b": 0.6, "c": 0.4, "d": 0.2}, 0.0)
P2 = TablePreference("P2", {"a": 0.7, "b": 0.5, "c": 0.3, "d": 0.1}, 0.0)


def case(prefs=(P0, P1)):
    return TableCase("c1", list(prefs), n_issues=1)


def sess(events, prefs=(P0, P1), plan="p", agreement="a"):
    return SessionResult(plan=plan, participants=[p.pid for p in prefs],
                         agreement=agreement, rounds=1, sweeps=1, phases=1,
                         messages=1, bytes=1, eval_calls=1, events=list(events))


def sub(sweep, rnd, actor, outcome, audience):
    return ObservationEvent(sweep, rnd, actor, "submit", outcome, tuple(audience))


class TestValidCount:
    def test_counts_above_threshold(self):
        v = TablePreference("V", {"a": 0.9, "b": 0.7, "c": 0.1}, 0.5)
        assert valid_count(case((v,)), v) == 2

    def test_never_zero(self):
        v = TablePreference("V", {"a": 0.1}, 0.9)
        assert valid_count(case((v,)), v) == 1   # 0 나눗셈 방어


class TestObservedSubs:
    def test_only_visible_events(self):
        s = sess([sub(1, 1, "P1", "a", ["P0"]), sub(1, 2, "P1", "b", [])])
        assert len(observed_subs(s, "P0", "P1")) == 1

    def test_only_victims_events(self):
        s = sess([sub(1, 1, "P1", "a", ["P0"]), sub(1, 1, "P0", "z", ["P0"])])
        got = observed_subs(s, "P0", "P1")
        assert [o for _s, _r, o in got] == ["a"]

    def test_anonymous_broadcast_not_attributed(self):
        # 담당자가 익명 목록으로 재배포하면 actor가 담당자라 피해자 귀속이 안 된다
        s = sess([ObservationEvent(1, 1, "P0", "announce", "a", ("P1", "P2"))],
                 prefs=(P0, P1, P2))
        assert observed_subs(s, "P1", "P2") == []

    def test_sorted_by_sweep_then_round(self):
        s = sess([sub(2, 1, "P1", "c", ["P0"]), sub(1, 2, "P1", "b", ["P0"]),
                  sub(1, 1, "P1", "a", ["P0"])])
        assert [o for _s, _r, o in observed_subs(s, "P0", "P1")] == ["a", "b", "c"]

    def test_duplicates_keep_earliest(self):
        s = sess([sub(1, 1, "P1", "a", ["P0"]), sub(2, 5, "P1", "a", ["P0"])])
        got = observed_subs(s, "P0", "P1")
        assert len(got) == 1 and got[0][0] == 1


class TestDepth:
    """노출 깊이 e — 귀속 노출된 고유 후보 수 ÷ 유효 후보 수 (순위표 노출 비율)."""

    def test_all_exposed(self):
        subs = [(1, i, o) for i, o in enumerate("abcd", 1)]
        assert depth(subs, 4) == pytest.approx(1.0)

    def test_half_exposed(self):
        assert depth([(1, 1, "a"), (1, 2, "b")], 4) == pytest.approx(0.5)

    def test_nothing_exposed(self):
        assert depth([], 4) == 0.0

    def test_capped_at_one(self):
        subs = [(1, i, o) for i, o in enumerate("abcdef", 1)]
        assert depth(subs, 4) == pytest.approx(1.0)

    def test_duplicates_counted_once(self):
        assert depth([(1, 1, "a"), (1, 2, "a")], 4) == pytest.approx(0.25)

    def test_order_does_not_matter(self):
        # 순서와 무관한 집합 지표다 — 구 B축(순서 복원)은 24 §3.3 개정으로 제거
        shuffled = [(1, 1, "b"), (1, 2, "a"), (1, 3, "c"), (1, 4, "d")]
        assert depth(shuffled, 4) == pytest.approx(1.0)


class TestEstimateTop1:
    """24 §3.4 고정 공격자 규칙 3개."""

    def test_rule1_earliest_proposal(self):
        s = sess([sub(1, 2, "P1", "b", ["P0"]), sub(1, 1, "P1", "a", ["P0"])])
        assert estimate_top1(s, "P0", "P1") == "a"

    def test_rule1_uses_sweep_before_round(self):
        s = sess([sub(1, 9, "P1", "z", ["P0"]), sub(2, 1, "P1", "a", ["P0"])])
        assert estimate_top1(s, "P0", "P1") == "z"

    def test_rule2_falls_back_to_approval(self):
        s = sess([ObservationEvent(1, 1, "P1", "vote", "b", ("P0",))])
        assert estimate_top1(s, "P0", "P1") == "b"

    def test_rule2_earliest_sweep_then_lexicographic(self):
        s = sess([ObservationEvent(1, 1, "P1", "vote", "z", ("P0",)),
                  ObservationEvent(1, 1, "P1", "vote", "b", ("P0",))])
        assert estimate_top1(s, "P0", "P1") == "b"

    def test_rule3_no_signal_is_none(self):
        s = sess([sub(1, 1, "P1", "a", [])])
        assert estimate_top1(s, "P0", "P1") is None

    def test_proposal_beats_vote(self):
        s = sess([ObservationEvent(1, 1, "P1", "vote", "d", ("P0",)),
                  sub(1, 5, "P1", "c", ["P0"])])
        assert estimate_top1(s, "P0", "P1") == "c"


class TestViewpoints:
    def test_coordinator_is_first_participant(self):
        s = sess([], prefs=(P0, P1, P2))
        assert COORDINATOR_FIRST.pick(s) == "P0"

    def test_worst_participant_sees_most(self):
        # P2가 P1보다 많이 본다 → 보수적으로 P2를 관찰자로 잡는다 (24 §3.5)
        s = sess([sub(1, 1, "P0", "a", ["P2"]), sub(1, 2, "P0", "b", ["P2"]),
                  sub(1, 3, "P0", "c", ["P1"])], prefs=(P0, P1, P2))
        assert worst_participant().pick(s) == "P2"

    def test_worst_participant_excludes_coordinator(self):
        s = sess([sub(1, 1, "P1", "a", ["P0"])], prefs=(P0, P1, P2))
        assert worst_participant().pick(s) != "P0"

    def test_single_participant_returns_it(self):
        s = sess([], prefs=(P0,))
        assert worst_participant().pick(s) == "P0"

    def test_custom_viewpoint(self):
        vp = Viewpoint("last", lambda s: s.participants[-1])
        assert vp.pick(sess([], prefs=(P0, P1, P2))) == "P2"


class TestInferenceGain:
    def test_full_exposure(self):
        s = sess([sub(1, 1, "P1", "a", ["P0"])])
        g = inference_gain([(s, case())], COORDINATOR_FIRST)
        assert g.accuracy == pytest.approx(1.0)
        assert g.exposure_rate == pytest.approx(1.0)

    def test_no_signal_is_random_baseline(self):
        s = sess([sub(1, 1, "P1", "a", [])])
        g = inference_gain([(s, case())], COORDINATOR_FIRST)
        assert g.accuracy == pytest.approx(g.random_baseline)
        assert g.exposure_rate == pytest.approx(0.0)
        assert g.stars == 5

    def test_wrong_guess_is_zero_accuracy(self):
        s = sess([sub(1, 1, "P1", "d", ["P0"])])
        g = inference_gain([(s, case())], COORDINATOR_FIRST)
        assert g.accuracy == 0.0

    def test_gain_pp_reported(self):
        s = sess([sub(1, 1, "P1", "a", ["P0"])])
        g = inference_gain([(s, case())], COORDINATOR_FIRST)
        assert g.gain_pp == pytest.approx(75.0)   # 1.0 - 1/4

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            inference_gain([], COORDINATOR_FIRST)


class TestE2Anchor:
    """1:1 기준 노출량 — 참조 양자 프로토콜에서 상대 1인이 도달하는 깊이."""

    def test_measures_counterpart_depth(self):
        s = sess([sub(1, i, "P1", o, ["P0"]) for i, o in enumerate("abcd", 1)])
        a = e2_anchor([(s, case())])
        assert a.depth == pytest.approx(1.0)

    def test_never_zero(self):
        # m의 분모라 0이면 안 된다
        s = sess([sub(1, 1, "P1", "a", [])])
        a = e2_anchor([(s, case())])
        assert a.depth > 0
        assert a.degenerate   # 다만 퇴화 신호는 남긴다 — 조용히 넘기지 않는다

    def test_requires_two_participants(self):
        s = sess([], prefs=(P0,))
        with pytest.raises(ValueError):
            e2_anchor([(s, case((P0,)))])

    def test_median_over_samples(self):
        runs = [(sess([sub(1, i, "P1", o, ["P0"]) for i, o in enumerate("ab", 1)]), case())
                for _ in range(3)]
        assert e2_anchor(runs).depth == pytest.approx(0.5)


def bilateral(prefs=(P0, P1)):
    """전원이 자기 순위대로 제출하고 담당자(P0)가 전부 보는 세션 — 실제 세션의 최소 형태."""
    pids = [p.pid for p in prefs]
    ev = []
    for p in prefs:
        for i, o in enumerate(p.ranked(), 1):
            audience = [q for q in pids if q != p.pid] if p.pid == pids[0] else [pids[0]]
            ev.append(sub(1, i, p.pid, o, audience))
    return sess(ev, prefs=prefs)


class TestExposureMultiple:
    def test_two_party_reference_is_one(self):
        # 참조 프로토콜 자신을 재면 m = 1 (정의상 1:1 등가)
        s = bilateral()
        anchor = e2_anchor([(s, case())])
        r = exposure_multiple([(s, case())], anchor)
        assert r.m == pytest.approx(1.0)

    def test_more_observers_raise_m(self):
        # 전원이 서로 보면 관찰자가 늘어 m이 커진다
        anchor = e2_anchor([(bilateral(), case())])
        pids = ["P0", "P1", "P2"]
        ev = [sub(1, i, p.pid, o, [q for q in pids if q != p.pid])
              for p in (P0, P1, P2) for i, o in enumerate(p.ranked(), 1)]
        s3 = sess(ev, prefs=(P0, P1, P2))
        r = exposure_multiple([(s3, case((P0, P1, P2)))], anchor)
        assert r.m > 1.0

    def test_no_exposure_is_zero(self):
        anchor = e2_anchor([(bilateral(), case())])
        silent = sess([sub(1, 1, "P1", "a", []), sub(1, 1, "P0", "a", [])])
        assert exposure_multiple([(silent, case())], anchor).m == pytest.approx(0.0)

    def test_max_single_depth_tracks_concentration(self):
        # 담당자만 전량을 본다 → 최대 단일 깊이는 1이지만 m은 1:1 수준에 머문다
        anchor = e2_anchor([(bilateral(), case())])
        s3 = bilateral(prefs=(P0, P1, P2))
        r = exposure_multiple([(s3, case((P0, P1, P2)))], anchor)
        assert r.max_single_depth == pytest.approx(1.0)

    def test_concentration_does_not_inflate_m_much(self):
        # 담당자 집중형은 관찰자가 1명뿐이라 m이 1:1 근처에 남는다 — 방안 1-A/2의 구조
        anchor = e2_anchor([(bilateral(), case())])
        r = exposure_multiple([(bilateral(prefs=(P0, P1, P2)), case((P0, P1, P2)))], anchor)
        assert r.m <= 1.5

    def test_stars_from_band(self):
        s = bilateral()
        anchor = e2_anchor([(s, case())])
        r = exposure_multiple([(s, case())], anchor)
        assert r.stars_m == 3     # m=1 → 1:1 등가 → 3점

    def test_degenerate_anchor_reports_none_with_reason(self):
        # 앵커가 퇴화하면 큰 수 대신 None + 사유 — "안 쟀다"와 "0이다"는 다르다
        r = exposure_multiple([(bilateral(), case())], E2Anchor(depth=1e-9, samples=1))
        assert r.m is None and r.stars_m is None
        assert r.note


class TestEvaluate:
    def test_combines_viewpoints_and_multiple(self):
        s = sess([sub(1, i, "P1", o, ["P0"]) for i, o in enumerate("abcd", 1)])
        anchor = e2_anchor([(s, case())])
        out = evaluate([(s, case())], anchor,
                       viewpoints=[COORDINATOR_FIRST, worst_participant()])
        assert "coordinator" in out["viewpoints"]
        assert "participant" in out["viewpoints"]
        assert "multiple" in out

    def test_raw_metrics_always_present(self):
        # 잠정 사다리이므로 별점만 남기지 않는다 (사용자 지시 2026-08-12)
        s = sess([sub(1, i, "P1", o, ["P0"]) for i, o in enumerate("abcd", 1)])
        anchor = e2_anchor([(s, case())])
        out = evaluate([(s, case())], anchor, viewpoints=[COORDINATOR_FIRST])
        m = out["multiple"]
        assert {"m", "stars_m", "max_single_depth"} <= set(m)
        vp = out["viewpoints"]["coordinator"]
        assert {"accuracy", "gain_pp", "exposure_rate"} <= set(vp)

    def test_records_e2_provenance(self):
        s = sess([sub(1, 1, "P1", "a", ["P0"])])
        anchor = e2_anchor([(s, case())])
        out = evaluate([(s, case())], anchor, viewpoints=[COORDINATOR_FIRST])
        assert out["e2"]["samples"] == 1
