"""교차 검산 — `total/qa/fc.py` 와 벤더링 `_vendor/measures/fc.py` 가 같은 값을 내는가.

`poc/total`은 "두 PoC가 같은 자로 잰다"는 전제로 만들어졌는데, nparty 원지표 리포트
(`experiments/nparty_1a_vs_2_raw.py`)는 벤더링본 채점기를, QA 별점 리포트
(`experiments/nparty_1a_vs_2.py`)는 `total/qa/` 채점기를 쓴다. **채점기가 두 벌**이므로
한쪽만 고치면 두 리포트가 같은 케이스에 다른 달성률을 내게 된다.

이 테스트가 그것을 잡는다. 실패하면 두 구현 중 하나가 바뀐 것이므로, 어느 쪽이 맞는지
정하고 양쪽을 맞춰야 한다 — 테스트를 느슨하게 고치는 것으로 넘기지 말 것.

대조 항목: 유효 후보 집합·총효용·달성률·기준선(R̄)·s·최적해.
결렬(NO_DEAL/NO_AGREEMENT) 표현이 서로 다르므로 그 부분만 이름을 맞춰 비교한다.

**의도된 차이가 딱 한 곳 있다** — R̄ = 1인데 유효 후보 밖으로 간 경우의 s (24 §1.4,
2026-08-13 개정). `is_known_s_divergence()`가 그 조건을 이름 붙여 판별하고,
`TestKnownSDivergence`가 차이 자체를 값으로 못박는다. 그 외의 불일치는 전부 이식 버그다.
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


def is_known_s_divergence(q) -> bool:
    """**의도된 정의 차이** 한 곳 — R̄ = 1인데 유효 후보 밖으로 간 경우 (24 §1.4).

    24 §1.4는 2026-08-13에 R̄ = 1 규칙을 도달 결과에 따라 둘로 쪼갰다: 유효 후보에
    도달했으면 `s = 1`(0/0 관례), **도달하지 못했으면 분자가 음수 고정이라 극한이 −∞로
    확정되므로 `s = 0`(0점)**. 개정 전에는 무조건 `s = 1`이라 "결렬이 정답인 시나리오에서
    억지 합의를 만든" 프로토콜이 판정 지표에서 만점을 받았다.

    `qa/fc.py`는 개정된 규칙을, `_vendor/measures/fc.py`는 **개정 전 규칙을 그대로** 쓴다
    — 벤더링본의 목적은 dp2 발표 수치의 재현이라 값을 바꾸면 그 목적이 깨지기 때문이다.
    따라서 이 한 분기는 갈리는 것이 **정상**이고, 그래서 여기 이름을 붙여 둔다.

    이 함수가 True를 내는 것은 정의 차이일 때뿐이다. 나머지는 전부 이식 버그로 본다.
    """
    return q.baseline >= 1.0 - TOL and q.achieved < 1.0 - TOL


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
    if is_known_s_divergence(q):
        # 아래 TestKnownSDivergence가 이 분기를 따로 못박는다. 여기서 그냥 비교하면
        # "구현이 어긋났다"와 "의도된 정의 차이"가 뒤섞인다
        assert v.s == pytest.approx(1.0, abs=TOL) and q.s == pytest.approx(0.0, abs=TOL), (
            f"{case.case_id}/{plan_cls.plan_name}: 알려진 차이의 값이 예상과 다르다 "
            f"(벤더링 {v.s!r} · qa {q.s!r})"
        )
    else:
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


class TestKnownSDivergence:
    """알려진 정의 차이 1건을 **양쪽 다** 못박는다 (24 §1.4, 2026-08-13 개정).

    위 `test_two_fc_implementations_agree`가 이 분기를 예외 처리하므로, 그 예외가
    "언젠가 아무도 모르게 사라지는" 것을 막으려면 차이 자체에 테스트가 있어야 한다.
    개정 전 규칙(벤더링)이 억지 합의에 만점을 준다는 사실도 여기 남는다.
    """

    #: 유효 후보가 결렬뿐이고, "b"는 바닥선 밑이라 유효 후보 밖
    PROFILES = (Profile("P0", {"a": 0.1, "b": 0.5}, 0.9),)
    CANDIDATES = ("a", "b")

    def qa_case(self):
        return NpartyCase("degenerate", list(self.PROFILES))

    def test_setup_is_actually_degenerate(self):
        q = qa_fc.score(self.qa_case(), qa_fc.NO_AGREEMENT)
        assert q.baseline == pytest.approx(1.0, abs=TOL)
        assert qa_fc.valid_candidates(self.qa_case()) == [qa_fc.NO_AGREEMENT]

    def test_both_agree_when_the_valid_candidate_is_reached(self):
        # 차이는 "못 맞췄을 때"에만 난다 — 맞췄으면 두 구현이 같아야 한다
        v = vendor_fc.score(vendor_fc.NO_DEAL, self.CANDIDATES, list(self.PROFILES))
        q = qa_fc.score(self.qa_case(), qa_fc.NO_AGREEMENT)
        assert v.s == pytest.approx(q.s, abs=TOL) == pytest.approx(1.0, abs=TOL)

    def test_they_diverge_when_it_is_missed(self):
        v = vendor_fc.score("b", self.CANDIDATES, list(self.PROFILES))
        q = qa_fc.score(self.qa_case(), "b")
        assert v.ratio == pytest.approx(q.achieved, abs=TOL), "달성률까지 갈리면 이식 버그다"
        assert v.s == pytest.approx(1.0, abs=TOL), "벤더링은 개정 전 규칙(무조건 만점)"
        assert q.s == pytest.approx(0.0, abs=TOL), "qa는 개정 규칙(극한 −∞ → 0점)"

    def test_the_helper_recognises_exactly_this_case(self):
        assert is_known_s_divergence(qa_fc.score(self.qa_case(), "b"))
        assert not is_known_s_divergence(qa_fc.score(self.qa_case(), qa_fc.NO_AGREEMENT))

    def test_helper_does_not_fire_on_ordinary_cases(self):
        # R̄ < 1인 평범한 케이스는 예외 처리 대상이 아니다 — 예외가 번지면 대조가 무의미해진다
        ordinary = NpartyCase("ordinary", [Profile("P0", {"a": 1.0, "b": 0.5}, 0.0)])
        assert not is_known_s_divergence(qa_fc.score(ordinary, "b"))
