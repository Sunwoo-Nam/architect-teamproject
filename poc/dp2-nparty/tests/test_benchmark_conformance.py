"""Conformance fixture의 프로토콜 동작 검증.

단언 규칙 (계획서 §5.3): **결과(outcome)와 방안 간 관계만 단언한다.**
라운드 수·바퀴 번호의 절댓값은 단언하지 않는다 — 그 값들은 양보 곡선과 최대 바퀴 설정을
그대로 따라 움직이므로, tactic 기본값이 바뀌면 전 fixture가 깨진다.
(boulware/linear/conceder × 최대바퀴 3/5/8 의 9조합에서 outcome은 동일하고 바퀴 번호만
움직인다는 것을 2026-08-11에 실측 확인했다 — 계획서 §3.2)
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dp2_nparty.benchmark import JsonBenchmarkLoader
from dp2_nparty.domain import NO_DEAL
from dp2_nparty.measures import fc
from dp2_nparty.protocol import Plan1Vote, Plan2Cumulative

PLANS = (Plan1Vote, Plan2Cumulative)

# case_id -> 두 방안이 공통으로 내야 하는 결과. 방안별로 결과가 갈리는 fixture는
# EXPECTED_PER_PLAN 에 적고 여기서는 뺀다.
EXPECTED_OUTCOME = {
    "C-001-common-top": "A",
    "C-002-threshold-boundary": "A",
    "C-003-no-deal": NO_DEAL,
}


def conformance_cases():
    return list(JsonBenchmarkLoader(track="conformance").cases())


def case_ids():
    return [c.case_id for c in conformance_cases()]


def by_id(case_id):
    return next(c for c in conformance_cases() if c.case_id == case_id)


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


@pytest.mark.parametrize("case_id", sorted(EXPECTED_OUTCOME))
@pytest.mark.parametrize("plan_cls", PLANS, ids=lambda c: c.plan_name)
def test_expected_outcome(case_id, plan_cls):
    case = by_id(case_id)
    r = plan_cls(case.profiles).run()
    assert r.outcome == EXPECTED_OUTCOME[case_id]


@pytest.mark.parametrize("case_id", sorted(EXPECTED_OUTCOME))
def test_expected_outcome_is_tactic_robust(case_id):
    """기대 결과가 양보 곡선·최대 바퀴 설정에 흔들리지 않아야 fixture로 쓸 수 있다."""
    case = by_id(case_id)
    for aspiration in ("boulware", "linear", "conceder"):
        for max_sweeps in (3, 5, 8):
            for plan_cls in PLANS:
                r = plan_cls(
                    case.profiles, max_sweeps=max_sweeps, aspiration_type=aspiration
                ).run()
                assert r.outcome == EXPECTED_OUTCOME[case_id], (
                    f"{case_id}/{plan_cls.plan_name}: {aspiration}·{max_sweeps}바퀴에서 결과가 바뀐다"
                )


def test_no_deal_case_scores_full_marks():
    """결렬이 정답인 사례에서 결렬은 만점이다 (24 §24.4)."""
    case = by_id("C-003-no-deal")
    for plan_cls in PLANS:
        r = plan_cls(case.profiles).run()
        score = fc.score(r.outcome, case.candidates, case.profiles)
        assert score.optimal == NO_DEAL
        assert score.ratio == 1.0
