"""[24 §1] Functional Correctness — 달성률·개선 비율 s·별점 2종.

정의의 미묘한 지점을 테스트로 못박는다:
- 결렬 후보는 **항상** 유효 후보 집합에 있다 (24 §1.3)
- R̄는 표본 추출이 아니라 **기대값 정확 계산**
- s는 무작위 대비 개선이라 음수가 될 수 있다
"""
from __future__ import annotations

import pytest

from total.qa.contract import NO_AGREEMENT, TableCase, TablePreference
from total.qa.fc import FcScore, no_agreement_utility, score, total_utility, valid_candidates


def mk_case(tables, thresholds, case_id="c"):
    prefs = [TablePreference(f"P{i}", t, th)
             for i, (t, th) in enumerate(zip(tables, thresholds))]
    return TableCase(case_id=case_id, preferences=prefs, n_issues=1)


class TestTotalUtility:
    def test_sums_over_participants(self):
        c = mk_case([{"a": 0.6}, {"a": 0.3}], [0.0, 0.0])
        assert total_utility("a", c.preferences) == pytest.approx(0.9)

    def test_no_agreement_is_sum_of_thresholds(self):
        # 24 §1.3 — 결렬 후보 = 전원이 자기 initial threshold를 얻는 후보
        c = mk_case([{"a": 0.6}, {"a": 0.3}], [0.4, 0.2])
        assert total_utility(NO_AGREEMENT, c.preferences) == pytest.approx(0.6)
        assert no_agreement_utility(c.preferences) == pytest.approx(0.6)


class TestValidCandidates:
    def test_filters_below_threshold(self):
        c = mk_case([{"a": 0.9, "b": 0.1}, {"a": 0.9, "b": 0.9}], [0.5, 0.5])
        v = valid_candidates(c)
        assert "a" in v and "b" not in v      # b는 P0의 바닥선 미달

    def test_no_agreement_always_included(self):
        c = mk_case([{"a": 0.1}, {"a": 0.1}], [0.9, 0.9])
        v = valid_candidates(c)
        assert v == [NO_AGREEMENT]            # 성립 가능한 후보가 없어도 결렬은 있다

    def test_threshold_boundary_is_inclusive(self):
        c = mk_case([{"a": 0.5}], [0.5])
        assert "a" in valid_candidates(c)

    def test_order_is_deterministic(self):
        c = mk_case([{"b": 0.9, "a": 0.9}], [0.0])
        assert valid_candidates(c) == valid_candidates(c)


class TestScore:
    def test_perfect_agreement_is_full_achievement(self):
        c = mk_case([{"a": 1.0, "b": 0.6}, {"a": 1.0, "b": 0.6}], [0.0, 0.0])
        s = score(c, "a")
        assert s.achieved == pytest.approx(1.0)
        assert s.optimal == "a"
        assert s.stars_achieved == 5

    def test_suboptimal_agreement(self):
        c = mk_case([{"a": 1.0, "b": 0.5}, {"a": 1.0, "b": 0.5}], [0.0, 0.0])
        s = score(c, "b")
        assert s.achieved == pytest.approx(0.5)

    def test_baseline_is_exact_mean_not_sampled(self):
        # 유효 후보 = a(2.0), b(1.0), 결렬(0.0) → 달성률 1.0, 0.5, 0.0 → R̄ = 0.5
        c = mk_case([{"a": 1.0, "b": 0.5}, {"a": 1.0, "b": 0.5}], [0.0, 0.0])
        s = score(c, "a")
        assert s.baseline == pytest.approx(0.5)

    def test_s_normalises_against_baseline(self):
        c = mk_case([{"a": 1.0, "b": 0.5}, {"a": 1.0, "b": 0.5}], [0.0, 0.0])
        s = score(c, "a")
        assert s.s == pytest.approx((1.0 - 0.5) / (1.0 - 0.5))
        assert s.stars_s == 5

    def test_s_can_be_negative_when_worse_than_random(self):
        c = mk_case([{"a": 1.0, "b": 0.5}, {"a": 1.0, "b": 0.5}], [0.0, 0.0])
        s = score(c, NO_AGREEMENT)
        assert s.achieved == pytest.approx(0.0)
        assert s.s < 0
        assert s.stars_s == 0

    def test_no_agreement_result(self):
        c = mk_case([{"a": 1.0}, {"a": 1.0}], [0.0, 0.0])
        s = score(c, NO_AGREEMENT)
        assert s.agreed is False

    def test_optimal_may_be_no_agreement(self):
        # 어떤 후보도 양쪽 바닥선을 못 넘으면 x*가 결렬이다
        c = mk_case([{"a": 0.1}, {"a": 0.1}], [0.9, 0.9])
        s = score(c, NO_AGREEMENT)
        assert s.optimal_is_no_agreement is True
        assert s.achieved == pytest.approx(1.0)   # 결렬이 최선이면 결렬 달성률은 1

    def test_two_star_bands_are_independent(self):
        c = mk_case([{"a": 1.0, "b": 0.9}, {"a": 1.0, "b": 0.9}], [0.0, 0.0])
        s = score(c, "b")
        assert s.stars_achieved == 4      # 달성률 0.9
        assert isinstance(s.stars_s, int)


class TestFrViolations:
    """FR 위반은 점수와 분리해 플래그로 보고한다 (dpca judge.py의 좋은 점)."""

    def test_below_floor_acceptance_flagged(self):
        c = mk_case([{"a": 0.9, "b": 0.1}, {"a": 0.9, "b": 0.9}], [0.5, 0.5])
        s = score(c, "b")
        assert any("바닥선" in v for v in s.fr_violations)

    def test_clean_agreement_has_no_violation(self):
        c = mk_case([{"a": 0.9}, {"a": 0.9}], [0.5, 0.5])
        assert score(c, "a").fr_violations == []

    def test_extra_violations_are_appended(self):
        c = mk_case([{"a": 0.9}, {"a": 0.9}], [0.5, 0.5])
        s = score(c, "a", extra_violations=["하드 제약 위반 합의"])
        assert "하드 제약 위반 합의" in s.fr_violations

    def test_violation_does_not_change_score(self):
        # 24 §1.7 — FR 경계는 달성률과 무관하게 지켜야 하는 것. 점수를 깎지 않는다
        c = mk_case([{"a": 0.9, "b": 0.1}, {"a": 0.9, "b": 0.9}], [0.5, 0.5])
        with_v = score(c, "b")
        assert with_v.achieved == pytest.approx(
            total_utility("b", c.preferences) / with_v.u_optimal)


class TestEdgeCases:
    def test_zero_optimal_utility(self):
        c = mk_case([{"a": 0.0}], [0.0])
        s = score(c, "a")
        assert s.achieved == 0.0 and s.s == 0.0 and s.stars_s == 0

    def test_baseline_equals_one(self):
        # 유효 후보가 결렬 하나뿐이면 R̄ = 1 — 0 나눗셈을 피해야 한다
        c = mk_case([{"a": 0.1}], [0.9])
        s = score(c, NO_AGREEMENT)
        assert s.baseline == pytest.approx(1.0)
        assert s.s == pytest.approx(1.0)

    def test_unknown_agreement_outcome_is_zero_utility(self):
        c = mk_case([{"a": 1.0}], [0.0])
        s = score(c, "ghost")
        assert s.achieved == pytest.approx(0.0)

    def test_score_is_serialisable(self):
        c = mk_case([{"a": 1.0}], [0.0])
        d = score(c, "a").as_dict()
        assert set(d) >= {"achieved", "baseline", "s", "stars_s", "stars_achieved",
                          "agreed", "fr_violations"}


class TestAggregate:
    """케이스 여러 건의 집계 — 실험은 항상 여러 케이스를 돈다."""

    def test_aggregate_means(self):
        from total.qa.fc import aggregate

        c1 = mk_case([{"a": 1.0, "b": 0.5}, {"a": 1.0, "b": 0.5}], [0.0, 0.0], "c1")
        c2 = mk_case([{"a": 1.0, "b": 0.5}, {"a": 1.0, "b": 0.5}], [0.0, 0.0], "c2")
        agg = aggregate([score(c1, "a"), score(c2, "b")])
        assert agg["mean_achieved"] == pytest.approx(0.75)
        assert agg["cases"] == 2
        assert agg["agreed"] == 2

    def test_aggregate_stars_from_mean(self):
        from total.qa.fc import aggregate

        c = mk_case([{"a": 1.0, "b": 0.5}, {"a": 1.0, "b": 0.5}], [0.0, 0.0])
        agg = aggregate([score(c, "a")])
        assert agg["stars_achieved"] == 5

    def test_aggregate_counts_violations(self):
        from total.qa.fc import aggregate

        c = mk_case([{"a": 0.9, "b": 0.1}, {"a": 0.9, "b": 0.9}], [0.5, 0.5])
        agg = aggregate([score(c, "b"), score(c, "a")])
        assert agg["fr_violation_cases"] == 1

    def test_aggregate_empty_raises(self):
        from total.qa.fc import aggregate

        with pytest.raises(ValueError):
            aggregate([])
