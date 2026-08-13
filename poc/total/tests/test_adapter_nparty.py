"""nparty 어댑터 — dp2 도메인을 계약으로 옮긴다.

어댑터의 책임은 **도메인 지식을 여기서 끝내는 것**이다. 특히 "이 방안에서 누가 무엇을
보는가"는 프로토콜이 아는 사실이므로 어댑터가 `audience`로 선언하고, 측정기는 모른다.
"""
from __future__ import annotations

import pytest

from total.adapters.nparty import PLANS, NpartyCase, NpartyPreference, run_session
from total.adapters.nparty._vendor.domain import Profile
from total.qa.contract import NO_AGREEMENT


def profiles(n=3, cands=("a", "b", "c", "d"), threshold=0.2):
    out = []
    for i in range(n):
        table = {c: round(max(0.05, 0.9 - 0.1 * i - 0.2 * j), 3)
                 for j, c in enumerate(cands)}
        out.append(Profile(f"P{i}", table, threshold))
    return out


class TestNpartyPreference:
    def test_wraps_utility(self):
        p = NpartyPreference(Profile("P0", {"a": 0.9}, 0.1))
        assert p.utility("a") == 0.9
        assert p.pid == "P0"

    def test_unknown_candidate_is_zero_not_keyerror(self):
        # 원본 Profile.utility는 KeyError를 낸다 — 계약은 0.0을 요구한다
        p = NpartyPreference(Profile("P0", {"a": 0.9}, 0.1))
        assert p.utility("ghost") == 0.0

    def test_ranked_and_rank_of(self):
        p = NpartyPreference(Profile("P0", {"a": 0.9, "b": 0.5}, 0.1))
        assert p.ranked() == ["a", "b"]
        assert p.rank_of("b") == 2
        assert p.rank_of("ghost") is None

    def test_threshold_passthrough(self):
        assert NpartyPreference(Profile("P0", {"a": 0.9}, 0.42)).initial_threshold == 0.42


class TestNpartyCase:
    def test_candidates_from_profiles(self):
        c = NpartyCase("c1", profiles())
        assert sorted(c.candidates()) == ["a", "b", "c", "d"]

    def test_n_issues_defaults_to_one(self):
        assert NpartyCase("c1", profiles()).n_issues == 1

    def test_preferences_are_contract_type(self):
        c = NpartyCase("c1", profiles())
        assert all(hasattr(p, "rank_of") for p in c.preferences)


class TestRunSession:
    @pytest.mark.parametrize("plan", ["plan1a", "plan2"])
    def test_returns_contract_session(self, plan):
        s, _case = run_session(profiles(), plan)
        assert s.plan == plan
        assert s.n == 3
        assert s.phases > 0 and s.messages > 0

    @pytest.mark.parametrize("plan", ["plan1a", "plan2"])
    def test_counters_are_nonnegative(self, plan):
        s, _ = run_session(profiles(), plan)
        assert s.bytes >= 0 and s.eval_calls >= 0 and s.rounds >= 1

    def test_agreement_maps_to_contract_sentinel(self):
        # 전원 바닥선이 높아 성립 불가 → NO_AGREEMENT
        hopeless = [Profile(f"P{i}", {"a": 0.1, "b": 0.05}, 0.99) for i in range(3)]
        s, _ = run_session(hopeless, "plan2")
        assert s.agreement == NO_AGREEMENT
        assert s.agreed is False

    def test_peak_and_base_measured(self):
        s, _ = run_session(profiles(), "plan2")
        assert s.peak_bytes > 0
        assert s.base_bytes > 0    # 공통 기저 — 효용 표·순위표

    def test_base_is_plan_independent(self):
        # 공통 기저는 방안 선택으로 줄일 수 없는 하한이다
        a, _ = run_session(profiles(), "plan1a")
        b, _ = run_session(profiles(), "plan2")
        assert a.base_bytes == b.base_bytes

    def test_deterministic(self):
        a, _ = run_session(profiles(), "plan2")
        b, _ = run_session(profiles(), "plan2")
        assert (a.rounds, a.messages, a.phases, a.agreement) == \
               (b.rounds, b.messages, b.phases, b.agreement)

    def test_unknown_plan_rejected(self):
        with pytest.raises(KeyError):
            run_session(profiles(), "plan-does-not-exist")


class TestEventVisibility:
    """계약의 핵심 — 방안별 가시 규칙이 audience로 선언된다."""

    def test_submissions_go_to_coordinator_only(self):
        s, _ = run_session(profiles(), "plan2")
        subs = [e for e in s.events if e.kind == "submit"]
        assert subs
        for e in subs:
            assert e.audience == ("P0",)

    def test_participant_sees_no_other_submissions(self):
        s, _ = run_session(profiles(), "plan2")
        seen = [e for e in s.visible_events("P1") if e.kind == "submit" and e.actor != "P1"]
        assert seen == []

    def test_coordinator_sees_all_submissions(self):
        s, _ = run_session(profiles(), "plan2")
        seen = [e for e in s.visible_events("P0") if e.kind == "submit"]
        actors = {e.actor for e in seen}
        assert actors == {"P0", "P1", "P2"}

    def test_plan1a_announce_is_anonymous(self):
        # 배포는 담당자가 actor라 원제안자에게 귀속되지 않는다 — 참여자 노출 0의 근거
        s, _ = run_session(profiles(), "plan1a")
        ann = [e for e in s.events if e.kind == "announce"]
        assert ann
        assert all(e.actor == "P0" for e in ann)

    def test_plan1a_votes_go_to_coordinator(self):
        s, _ = run_session(profiles(), "plan1a")
        votes = [e for e in s.events if e.kind == "vote"]
        assert votes
        assert all(e.audience == ("P0",) for e in votes)

    def test_plan2_has_no_votes(self):
        s, _ = run_session(profiles(), "plan2")
        assert [e for e in s.events if e.kind == "vote"] == []

    def test_event_rounds_match_submission_rank(self):
        # "라운드 k = 순위 k" — 51 §2의 제출 규칙이 이벤트에 그대로 반영되는지
        s, _ = run_session(profiles(), "plan2")
        first = [e for e in s.events if e.kind == "submit" and e.round == 1]
        for e in first:
            pref = next(p for p in _prefs(s) if p.pid == e.actor)
            assert e.outcome == pref.ranked()[0]


def _prefs(session):
    return [NpartyPreference(p) for p in session.extra["profiles"]]


class TestPlansRegistry:
    def test_contains_the_two_compared_plans(self):
        assert "plan1a" in PLANS and "plan2" in PLANS

    def test_labels_present(self):
        assert PLANS["plan1a"].label
        assert PLANS["plan2"].label
