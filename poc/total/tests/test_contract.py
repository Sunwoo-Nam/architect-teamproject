"""공통 계약 — 측정기가 실험 도메인을 모르게 하는 경계.

여기서 고정하는 것은 "측정기가 무엇에 의존해도 되는가"다. 계약에 없는 필드를
측정기가 읽기 시작하면 도메인이 새어 들어온 것이고, 그 순간 공통 라이브러리가 아니다.
"""
from __future__ import annotations

import pytest

from total.qa.contract import (
    NO_AGREEMENT,
    Dataset,
    ObservationEvent,
    SessionResult,
    SweepPoint,
    TableCase,
    TablePreference,
)


class TestTablePreference:
    """테스트·단순 도메인용 표 기반 선호. Preference 프로토콜의 참조 구현."""

    def test_utility_lookup(self):
        p = TablePreference(pid="P0", table={"a": 0.9, "b": 0.4}, initial_threshold=0.5)
        assert p.utility("a") == 0.9
        assert p.utility("b") == 0.4

    def test_unknown_outcome_is_zero(self):
        p = TablePreference(pid="P0", table={"a": 0.9}, initial_threshold=0.5)
        assert p.utility("zzz") == 0.0

    def test_ranked_is_descending_by_utility(self):
        p = TablePreference(pid="P0", table={"a": 0.2, "b": 0.9, "c": 0.5},
                            initial_threshold=0.0)
        assert p.ranked() == ["b", "c", "a"]

    def test_ranked_is_deterministic_on_ties(self):
        # 같은 효용이면 후보 표현의 사전순 — 시드가 같으면 결과가 같아야 한다
        p = TablePreference(pid="P0", table={"b": 0.5, "a": 0.5}, initial_threshold=0.0)
        assert p.ranked() == ["a", "b"]

    def test_rank_of(self):
        p = TablePreference(pid="P0", table={"a": 0.2, "b": 0.9}, initial_threshold=0.0)
        assert p.rank_of("b") == 1
        assert p.rank_of("a") == 2
        assert p.rank_of("nope") is None


class TestObservationEvent:
    """가시성은 이벤트가 선언한다 — 측정기가 방안별 규칙을 알 필요가 없다."""

    def test_audience_controls_visibility(self):
        e = ObservationEvent(sweep=1, round=1, actor="P1", kind="submit",
                             outcome="a", audience=("P0",))
        assert e.visible_to("P0")
        assert not e.visible_to("P2")

    def test_actor_always_sees_own_event(self):
        # 자기 행동은 자기가 안다 — audience에 빠져 있어도 보인다
        e = ObservationEvent(sweep=1, round=1, actor="P1", kind="submit",
                             outcome="a", audience=("P0",))
        assert e.visible_to("P1")

    def test_is_hashable_and_frozen(self):
        e = ObservationEvent(sweep=1, round=1, actor="P1", kind="submit",
                             outcome="a", audience=("P0",))
        assert hash(e) is not None
        with pytest.raises(Exception):
            e.round = 2  # type: ignore[misc]

    def test_rejects_unknown_kind(self):
        with pytest.raises(ValueError):
            ObservationEvent(sweep=1, round=1, actor="P1", kind="teleport",
                             outcome="a", audience=())


class TestSessionResult:
    def _mk(self, **kw):
        base = dict(plan="planX", participants=["P0", "P1"], agreement="a",
                    rounds=3, sweeps=1, phases=6, messages=4, bytes=100, eval_calls=20)
        base.update(kw)
        return SessionResult(**base)

    def test_agreed_true_on_outcome(self):
        assert self._mk().agreed is True

    def test_agreed_false_on_no_agreement(self):
        assert self._mk(agreement=NO_AGREEMENT).agreed is False

    def test_n_derives_from_participants(self):
        assert self._mk().n == 2

    def test_events_default_empty(self):
        assert self._mk().events == []

    def test_peak_and_base_default_zero(self):
        r = self._mk()
        assert r.peak_bytes == 0 and r.base_bytes == 0

    def test_total_device_bytes_is_base_plus_peak(self):
        # 24 §2.8 단서 — 단말 총 점유 = 공통 기저 + 프로토콜 상태
        r = self._mk(peak_bytes=2000, base_bytes=8000)
        assert r.total_device_bytes == 10000

    def test_rejects_negative_counters(self):
        with pytest.raises(ValueError):
            self._mk(phases=-1)

    def test_rejects_empty_participants(self):
        with pytest.raises(ValueError):
            self._mk(participants=[])

    def test_visible_events_filters_by_audience(self):
        ev = [
            ObservationEvent(1, 1, "P1", "submit", "a", ("P0",)),
            ObservationEvent(1, 1, "P0", "submit", "b", ("P0",)),
            ObservationEvent(1, 2, "P1", "announce", "c", ("P0", "P1")),
        ]
        r = self._mk(events=ev)
        assert len(r.visible_events("P0")) == 3   # 2건 audience + 자기 1건
        assert len(r.visible_events("P1")) == 2   # 자기 2건 + announce


class TestDataset:
    """참여자 수·의제 수는 코드가 아니라 데이터셋이 정한다."""

    def _mk(self, **kw):
        base = dict(name="ds", n_participants=3, n_issues=4,
                    issue_value_counts=[2, 3, 4, 5], seed=1)
        base.update(kw)
        return Dataset(**base)

    def test_n_candidates_is_product(self):
        assert self._mk().n_candidates == 2 * 3 * 4 * 5

    def test_n_issues_must_match_value_counts(self):
        with pytest.raises(ValueError):
            self._mk(n_issues=3, issue_value_counts=[2, 3, 4, 5])

    def test_d_alias_is_n_issues(self):
        # 24 §4.3의 d = 의제 수. 별점 하계 1/d 계산에 쓴다
        assert self._mk().d == 4

    def test_rejects_zero_participants(self):
        with pytest.raises(ValueError):
            self._mk(n_participants=0)

    def test_rejects_empty_issues(self):
        with pytest.raises(ValueError):
            self._mk(n_issues=0, issue_value_counts=[])

    def test_as_dict_roundtrip(self):
        d = self._mk().as_dict()
        assert d["n_participants"] == 3 and d["n_issues"] == 4
        assert d["n_candidates"] == 120


class TestTableCase:
    def test_candidates_from_preferences(self):
        prefs = [
            TablePreference("P0", {"a": 0.9, "b": 0.1}, 0.0),
            TablePreference("P1", {"a": 0.2, "b": 0.8}, 0.0),
        ]
        c = TableCase(case_id="c1", preferences=prefs, n_issues=1)
        assert sorted(c.candidates()) == ["a", "b"]

    def test_candidates_is_reiterable(self):
        # 측정기가 두 번 순회해도 같아야 한다 (generator 소진 버그 방지)
        prefs = [TablePreference("P0", {"a": 0.9, "b": 0.1}, 0.0)]
        c = TableCase(case_id="c1", preferences=prefs, n_issues=1)
        assert list(c.candidates()) == list(c.candidates())

    def test_pids(self):
        prefs = [TablePreference("P0", {"a": 1.0}, 0.0), TablePreference("P1", {"a": 1.0}, 0.0)]
        assert TableCase("c", prefs, 1).pids == ["P0", "P1"]


class TestSweepPoint:
    """SC-의제 스윕의 한 점 — (규모 S, 피크, 완결 여부)."""

    def test_holds_scale_and_peak(self):
        p = SweepPoint(scale=1000, peak_bytes=4096, agreed=True, n_issues=4)
        assert p.scale == 1000 and p.peak_bytes == 4096 and p.agreed

    def test_rejects_nonpositive_scale(self):
        with pytest.raises(ValueError):
            SweepPoint(scale=0, peak_bytes=1, agreed=True, n_issues=4)

    def test_total_bytes_includes_base(self):
        p = SweepPoint(scale=1000, peak_bytes=4096, agreed=True, n_issues=4, base_bytes=1024)
        assert p.total_bytes == 5120

    def test_base_defaults_zero(self):
        assert SweepPoint(scale=10, peak_bytes=1, agreed=True, n_issues=1).total_bytes == 1

    def test_rejects_negative_base(self):
        with pytest.raises(ValueError):
            SweepPoint(scale=10, peak_bytes=1, agreed=True, n_issues=1, base_bytes=-1)
