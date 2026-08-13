"""교차 검산 — `total/qa/fc.py` 와 벤더링 `_vendor/measures/fc.py` 가 같은 값을 내는가.

`poc/total`은 "두 PoC가 같은 자로 잰다"는 전제로 만들어졌는데, nparty 원지표 리포트
(`experiments/nparty_1a_vs_2_raw.py`)는 벤더링본 채점기를, QA 별점 리포트
(`experiments/nparty_1a_vs_2.py`)는 `total/qa/` 채점기를 쓴다. **채점기가 두 벌**이므로
한쪽만 고치면 두 리포트가 같은 케이스에 다른 달성률을 내게 된다.

이 테스트가 그것을 잡는다. 실패하면 두 구현 중 하나가 바뀐 것이므로, 어느 쪽이 맞는지
정하고 양쪽을 맞춰야 한다 — 테스트를 느슨하게 고치는 것으로 넘기지 말 것.

대조 항목: 유효 후보 집합·총효용·달성률·기준선(R̄)·s·최적해.
결렬(NO_DEAL/NO_AGREEMENT) 표현이 서로 다르므로 그 부분만 이름을 맞춰 비교한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from total.adapters.nparty._vendor.benchmark import JsonBenchmarkLoader  # noqa: E402
from total.adapters.nparty._vendor.measures import fc as vendor_fc  # noqa: E402
from total.adapters.nparty._vendor.protocol import Plan1Vote, Plan2Cumulative  # noqa: E402
from total.adapters.nparty import NpartyCase  # noqa: E402
from total.adapters.nparty._vendor.domain import Profile  # noqa: E402
from total.qa import fc as qa_fc  # noqa: E402

PLANS = (Plan1Vote, Plan2Cumulative)
TOL = 1e-12


def _cases(limit: int = 12):
    """functional 트랙 앞쪽 일부 — 전량은 느리고, 구현 차이는 소수 건에서도 드러난다."""
    got = sorted(JsonBenchmarkLoader(track="functional").cases(), key=lambda c: c.case_id)
    return got[:limit]


def _as_qa_case(bc) -> NpartyCase:
    """벤더링 BenchmarkCase → qa 계약 Case.

    `experiments/nparty_1a_vs_2.py`의 `_mkcase()`와 같은 변환을 쓴다 — 별점 리포트가
    실제로 채점에 넘기는 것과 같은 객체여야 이 대조가 의미를 갖는다.
    """
    return NpartyCase(
        bc.case_id,
        [Profile(p.pid, dict(p.utilities), p.initial_threshold) for p in bc.profiles],
    )


def _norm(outcome, qa_no_deal, vendor_no_deal):
    """결렬 표현을 한쪽 이름으로 통일한다 — 대조용."""
    return "__NO_DEAL__" if outcome in (qa_no_deal, vendor_no_deal) else outcome


def _to_qa_outcome(outcome):
    """벤더링 결과를 qa 채점기에 넘길 수 있는 표현으로 바꾼다.

    결렬 표식이 서로 다르다 (`'NO_DEAL'` vs `'__NO_AGREEMENT__'`). 그대로 넘기면 qa 쪽이
    결렬을 일반 후보로 보고 효용 0을 매겨, 결렬이 최적인 케이스에서 달성률이 1.0 대 0.0으로
    갈린다 — 구현 차이가 아니라 표식 차이다.
    """
    return qa_fc.NO_AGREEMENT if outcome == vendor_fc.NO_DEAL else outcome


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c.case_id)
@pytest.mark.parametrize("plan_cls", PLANS, ids=lambda c: c.plan_name)
def test_two_fc_implementations_agree(case, plan_cls):
    outcome = plan_cls(case.profiles).run().outcome

    v = vendor_fc.score(outcome, case.candidates, case.profiles)
    q = qa_fc.score(_as_qa_case(case), _to_qa_outcome(outcome))

    assert v.ratio == pytest.approx(q.achieved, abs=TOL), (
        f"{case.case_id}/{plan_cls.plan_name}: 달성률이 갈린다 "
        f"(벤더링 {v.ratio!r} · qa {q.achieved!r})"
    )
    assert v.baseline == pytest.approx(q.baseline, abs=TOL), (
        f"{case.case_id}/{plan_cls.plan_name}: 기준선 R̄가 갈린다 "
        f"(벤더링 {v.baseline!r} · qa {q.baseline!r})"
    )
    assert v.s == pytest.approx(q.s, abs=TOL), (
        f"{case.case_id}/{plan_cls.plan_name}: s가 갈린다 (벤더링 {v.s!r} · qa {q.s!r})"
    )
    assert _norm(v.optimal, qa_fc.NO_AGREEMENT, vendor_fc.NO_DEAL) == _norm(
        q.optimal, qa_fc.NO_AGREEMENT, vendor_fc.NO_DEAL
    ), f"{case.case_id}/{plan_cls.plan_name}: 최적해 x*가 갈린다"


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c.case_id)
def test_valid_candidate_sets_agree(case):
    """유효 후보 판정이 갈리면 기준선과 최적해가 함께 어긋난다 — 원인 지점을 따로 잡는다."""
    v = set(vendor_fc.valid_candidates(case.candidates, case.profiles))
    q = set(qa_fc.valid_candidates(_as_qa_case(case)))
    vn = {_norm(o, qa_fc.NO_AGREEMENT, vendor_fc.NO_DEAL) for o in v}
    qn = {_norm(o, qa_fc.NO_AGREEMENT, vendor_fc.NO_DEAL) for o in q}
    assert vn == qn, (
        f"{case.case_id}: 유효 후보가 갈린다 — 벤더링만 {sorted(vn - qn)} · qa만 {sorted(qn - vn)}"
    )


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c.case_id)
def test_total_utility_agrees(case):
    """총효용 합산이 갈리면 x* 선택이 뒤집힌다 — 부동소수점 합산 순서 차이로 실제 발생한 적이 있다."""
    for cand in case.candidates:
        assert vendor_fc.total_utility(cand, case.profiles) == pytest.approx(
            qa_fc.total_utility(cand, case.profiles), abs=TOL
        ), f"{case.case_id}/{cand!r}: 총효용이 갈린다"
