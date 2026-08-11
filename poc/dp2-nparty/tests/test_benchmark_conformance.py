"""Conformance fixture의 프로토콜 동작 검증.

단언 규칙 (계획서 §5.3): **결과(outcome)와 방안 간 관계만 단언한다.**
라운드 수·바퀴 번호의 절댓값은 단언하지 않는다 — 그 값들은 양보 곡선과 최대 바퀴 설정을
그대로 따라 움직이므로, tactic 기본값이 바뀌면 전 fixture가 깨진다.
(boulware/linear/conceder × 최대바퀴 3/5/8 의 9조합에서 outcome은 동일하고 바퀴 번호만
움직인다는 것을 12건 전부에 대해 2026-08-11에 실측 확인했다 — 계획서 §3.2)
"""
import json
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dp2_nparty.benchmark import JsonBenchmarkLoader
from dp2_nparty.domain import NO_DEAL, Profile
from dp2_nparty.measures import fc
from dp2_nparty.protocol import Plan1Vote, Plan2Cumulative
from dp2_nparty.tiebreak import RankSumThenStdThenRunoff

PLANS = (Plan1Vote, Plan2Cumulative)

# 두 방안이 **같은** 결과를 내는 fixture
EXPECTED_OUTCOME = {
    "C-001-common-top": "A",
    "C-002-threshold-boundary": "A",
    "C-003-no-deal": NO_DEAL,
    "C-005-plan2-late-intersection": "A",
    "C-006-multiple-winners": "A",
    "C-007-tie-rank-sum": "B",
    "C-009-tie-runoff": "B",
    "C-010-late-threshold-release": "COMPROMISE",
    "C-011-asymmetric-exhaustion": "S5",
    "C-012-utility-ties": "A-omega",
}

# 두 방안이 **갈리는** fixture — 이 두 건이 설계 후보 비교의 판별력을 담보한다.
# C-004: 방안 1이 남의 제안에 O를 주고 한 라운드 먼저 닫히면서 x*(B)를 놓친다.
# C-008: 방안 2의 순위 표준편차 해소가 방안 1의 결선투표와 다른 후보를 고른다.
EXPECTED_PER_PLAN = {
    "C-004-plan1-early-accept": {"plan1": "A", "plan2": "B"},
    "C-008-tie-rank-stdev": {"plan1": "A", "plan2": "C"},
}

# 방안 2의 동률 해소가 몇 단계에서 결판나는지 — (동률 후보, 승자, 추가 메시지 수)
# 추가 메시지 0 = 1·2단계(담당자 로컬 계산), 2(N-1) = 3단계 결선투표까지 감
TIE_BREAK_STAGES = {
    "C-007-tie-rank-sum": (["A", "B", "C"], "B", 0),
    "C-008-tie-rank-stdev": (["A", "C"], "C", 0),
    "C-009-tie-runoff": (["A", "B"], "B", 4),
}


def conformance_cases():
    return list(JsonBenchmarkLoader(track="conformance").cases())


def case_ids():
    return [c.case_id for c in conformance_cases()]


def by_id(case_id):
    return next(c for c in conformance_cases() if c.case_id == case_id)


def expected_for(case_id, plan_name):
    if case_id in EXPECTED_PER_PLAN:
        return EXPECTED_PER_PLAN[case_id][plan_name]
    return EXPECTED_OUTCOME[case_id]


# ---------------------------------------------------------------- 전 fixture 공통 불변조건


@pytest.mark.parametrize("case_id", case_ids())
@pytest.mark.parametrize("plan_cls", PLANS, ids=lambda c: c.plan_name)
def test_runs_and_respects_delegation_bound(case_id, plan_cls):
    """FR 경계 (24 §24.7): 어떤 참여자의 initial threshold 미만인 후보로 성립하지 않는다.

    이 조건이 지켜져야 달성률이 1을 넘는 일이 없다.
    """
    case = by_id(case_id)
    r = plan_cls(case.profiles).run()
    assert r.outcome == NO_DEAL or r.outcome in case.candidates
    if r.outcome != NO_DEAL:
        for p in case.profiles:
            assert p.utility(r.outcome) >= p.initial_threshold, (
                f"{case_id}/{plan_cls.plan_name}: {p.pid} 의 바닥선 미만 후보로 성립했다"
            )
    score = fc.score(r.outcome, case.candidates, case.profiles)
    assert 0.0 < score.ratio <= 1.0


def test_every_fixture_has_expected_outcome():
    """새 fixture를 넣고 기대값 등록을 잊는 것을 막는다."""
    registered = set(EXPECTED_OUTCOME) | set(EXPECTED_PER_PLAN)
    missing = sorted(set(case_ids()) - registered)
    assert not missing, f"기대 결과가 등록되지 않은 fixture: {missing}"


# ---------------------------------------------------------------- 기대 결과


@pytest.mark.parametrize("case_id", sorted(set(EXPECTED_OUTCOME) | set(EXPECTED_PER_PLAN)))
@pytest.mark.parametrize("plan_cls", PLANS, ids=lambda c: c.plan_name)
def test_expected_outcome(case_id, plan_cls):
    case = by_id(case_id)
    r = plan_cls(case.profiles).run()
    assert r.outcome == expected_for(case_id, plan_cls.plan_name)


@pytest.mark.parametrize("case_id", sorted(set(EXPECTED_OUTCOME) | set(EXPECTED_PER_PLAN)))
def test_expected_outcome_is_tactic_robust(case_id):
    """기대 결과가 양보 곡선·최대 바퀴 설정에 흔들리지 않아야 fixture로 쓸 수 있다."""
    case = by_id(case_id)
    for aspiration in ("boulware", "linear", "conceder"):
        for max_sweeps in (3, 5, 8):
            for plan_cls in PLANS:
                r = plan_cls(
                    case.profiles, max_sweeps=max_sweeps, aspiration_type=aspiration
                ).run()
                assert r.outcome == expected_for(case_id, plan_cls.plan_name), (
                    f"{case_id}/{plan_cls.plan_name}: {aspiration}·{max_sweeps}바퀴에서 결과가 바뀐다"
                )


def test_two_plans_are_distinguishable():
    """표본이 두 방안을 구분하지 못하면 비교 자체가 무의미하다 — 판별 fixture가 있어야 한다."""
    assert EXPECTED_PER_PLAN, "두 방안의 결과가 갈리는 fixture가 하나도 없다"


# ---------------------------------------------------------------- 사례별 성질


def test_no_deal_case_scores_full_marks():
    """결렬이 정답인 사례에서 결렬은 만점이다 (24 §24.4)."""
    case = by_id("C-003-no-deal")
    for plan_cls in PLANS:
        r = plan_cls(case.profiles).run()
        score = fc.score(r.outcome, case.candidates, case.profiles)
        assert score.optimal == NO_DEAL
        assert score.ratio == 1.0


def test_plan1_closes_earlier_than_plan2():
    """C-004·C-005: 방안 1은 남의 제안에 O만 주면 되고, 방안 2는 전원이 직접 낼 때까지 기다린다."""
    for case_id in ("C-004-plan1-early-accept", "C-005-plan2-late-intersection"):
        case = by_id(case_id)
        r1 = Plan1Vote(case.profiles).run()
        r2 = Plan2Cumulative(case.profiles).run()
        assert r1.rounds < r2.rounds, f"{case_id}: 방안 1이 더 이르지 않다"


def test_plan1_early_close_costs_optimality():
    """C-004: 방안 1의 빠른 성립이 x*를 놓치는 사례 — 24번이 묻는 trade-off의 재현."""
    case = by_id("C-004-plan1-early-accept")
    r1 = Plan1Vote(case.profiles).run()
    r2 = Plan2Cumulative(case.profiles).run()
    s1 = fc.score(r1.outcome, case.candidates, case.profiles)
    s2 = fc.score(r2.outcome, case.candidates, case.profiles)
    assert s1.ratio < s2.ratio
    assert r2.outcome == s2.optimal  # 방안 2는 x*에 도달


def test_multiple_winners_trigger_tie_break():
    """C-006: 같은 라운드에 성립 후보가 2개 이상 — 두 방안 모두 동률 해소가 발동한다."""
    case = by_id("C-006-multiple-winners")
    for plan_cls in PLANS:
        r = plan_cls(case.profiles).run()
        assert r.tie_break_used is True, f"{plan_cls.plan_name}: 동률 해소가 발동하지 않았다"


@pytest.mark.parametrize("case_id", sorted(TIE_BREAK_STAGES))
def test_plan2_tie_break_resolves_at_expected_stage(case_id):
    """방안 2의 3단계 해소(순위 합 → 표준편차 → 결선투표)가 의도한 단계에서 결판나는지.

    추가 메시지 수가 단계의 증거다 — 0이면 담당자 로컬 계산(1·2단계),
    2(N-1)이면 결선투표 공지·회신이 발생한 것(3단계).
    """
    tied, winner, extra = TIE_BREAK_STAGES[case_id]
    case = by_id(case_id)
    assert RankSumThenStdThenRunoff().pick(tied, case.profiles) == (winner, extra)
    assert Plan2Cumulative(case.profiles).run().tie_break_used is True


def test_late_threshold_release_needs_more_than_one_sweep():
    """C-010: 유일 실후보가 전원의 5순위라 첫 바퀴에는 제출조차 되지 않는다."""
    case = by_id("C-010-late-threshold-release")
    for p in case.profiles:
        assert p.rank_of("COMPROMISE") == 5
    for plan_cls in PLANS:
        assert plan_cls(case.profiles).run().sweeps >= 2


def test_asymmetric_exhaustion_has_unequal_submission_capacity():
    """C-011: 바닥선이 달라 참여자별 제출 가능 후보 수가 전부 다르다."""
    case = by_id("C-011-asymmetric-exhaustion")
    counts = [
        sum(1 for c in case.candidates if p.utility(c) >= p.initial_threshold)
        for p in case.profiles
    ]
    assert len(set(counts)) == len(counts), f"소진 시점이 비대칭이 아니다: {counts}"


def test_utility_ties_order_by_repr_deterministically():
    """C-012: utility가 정확히 같으면 후보 repr 사전순으로 순위가 고정된다."""
    case = by_id("C-012-utility-ties")
    tied = ["A-omega", "M-beta", "Z-alpha"]
    for p in case.profiles:
        assert p.ranked()[2:5] == tied
        assert len({p.utility(c) for c in tied}) == 1  # 정말 동점인지

    # 입력 dict의 키 순서가 결과를 바꾸지 않아야 한다
    rng = random.Random(0)
    for _ in range(5):
        shuffled = []
        for p in case.profiles:
            items = list(p.utilities.items())
            rng.shuffle(items)
            shuffled.append(Profile(p.pid, dict(items), p.initial_threshold))
        for plan_cls in PLANS:
            assert plan_cls(shuffled).run().outcome == "A-omega"


def test_fixture_diversity():
    """conformance 12건이 한 가지 모양으로 쏠려 있지 않은지 — 편향 최소 점검.

    통계 표본이 아니므로 분포를 맞출 필요는 없지만, 후보 수·참여자 수가 전부 같으면
    경계 사례 모음으로서의 의미가 약해진다.
    """
    cases = conformance_cases()
    assert len({len(c.candidates) for c in cases}) >= 3, "후보 수가 다양하지 않다"
    assert len({len(c.profiles) for c in cases}) >= 2, "참여자 수가 다양하지 않다"
    assert any(c.meta["expected_no_deal"] for c in cases), "결렬 사례가 없다"
    assert len({tuple(sorted(p.initial_threshold for p in c.profiles)) for c in cases}) >= 4, (
        "바닥선 구성이 다양하지 않다"
    )
