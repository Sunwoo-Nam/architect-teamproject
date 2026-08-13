"""composite 어댑터 + dpca 회귀 안전망.

기준: `poc/dp-composite-agenda/results/` — `fc_benchmark.jsonl`(FC·phase·message)와
`P3-c-결과.md`(탄력성 c).

**(a) 재현되어야 하는 것** — 24와 정의가 같은 항목 (FC 달성률·s·phase·message·피크)
**(b) 바뀌는 것** — 정의 교체 항목은 `TestIntentionalChanges` 참조
"""
from __future__ import annotations

import pytest

from total.adapters.composite import (
    PLANS,
    CompositeCase,
    load,
    run_session,
    scenario_paths,
)
from total.qa import fc
from total.qa.contract import NO_AGREEMENT

TOL = 5e-4


@pytest.fixture(scope="module")
def s01():
    return load("S01")


@pytest.fixture(scope="module")
def s01_case(s01):
    return CompositeCase(s01.id, s01)


class TestDatasetIntegrity:
    def test_scenarios_present(self):
        names = [p.stem for p in scenario_paths()]
        assert len(names) == 12
        assert any(n.startswith("S01") for n in names)
        assert any(n.startswith("S12") for n in names)

    def test_s01_shape(self, s01):
        assert len(s01.axes) == 4
        assert s01.space_size() == 1680


class TestCompositePreference:
    def test_utility_is_nonzero(self, s01_case):
        # Value 객체 변환을 빠뜨리면 조용히 0이 된다 — 그 회귀를 막는 테스트
        p = s01_case.preferences[0]
        best = p.ranked()[0]
        assert p.utility(best) > 0

    def test_ranked_is_descending(self, s01_case):
        p = s01_case.preferences[0]
        r = p.ranked()[:20]
        utils = [p.utility(o) for o in r]
        assert utils == sorted(utils, reverse=True)

    def test_unknown_outcome_is_zero(self, s01_case):
        assert s01_case.preferences[0].utility((("nope", "nope"),)) == 0.0

    def test_rank_of_roundtrip(self, s01_case):
        p = s01_case.preferences[0]
        assert p.rank_of(p.ranked()[4]) == 5

    def test_two_participants(self, s01_case):
        assert s01_case.pids == ["P0", "P1"]


class TestCompositeCase:
    def test_candidate_count_matches_space(self, s01_case):
        assert len(list(s01_case.candidates())) == 1680

    def test_candidates_reiterable(self, s01_case):
        assert list(s01_case.candidates()) == list(s01_case.candidates())

    def test_n_issues_from_scenario(self, s01_case):
        assert s01_case.n_issues == 4

    def test_enumeration_limit_refuses_silently_sampling(self, s01):
        # 표본으로 바꾸면 달성률이 틀린 값이 된다 — 조용히 넘어가면 안 된다
        c = CompositeCase(s01.id, s01, enumeration_limit=10)
        with pytest.raises(ValueError, match="열거 한도"):
            list(c.candidates())

    def test_hard_violations_clean_on_valid(self, s01_case):
        assert s01_case.hard_violations(s01_case.preferences[0].ranked()[0]) == []

    def test_hard_violations_empty_on_no_agreement(self, s01_case):
        assert s01_case.hard_violations(NO_AGREEMENT) == []


class TestRunSession:
    @pytest.mark.parametrize("plan", sorted(PLANS))
    def test_all_plans_run(self, s01, s01_case, plan):
        s, _ = run_session(s01, plan, case=s01_case)
        assert s.plan == plan and s.phases > 0

    def test_byte_counting_is_new_and_nonzero(self, s01, s01_case):
        # 원본 dpca에는 바이트 계측이 없었다 — 신설분이 실제로 세는지 확인
        s, _ = run_session(s01, "pool", case=s01_case)
        assert s.bytes > 0

    def test_observations_recorded(self, s01, s01_case):
        s, _ = run_session(s01, "pool", case=s01_case)
        assert [e for e in s.events if e.kind == "submit"]

    def test_audience_is_the_counterpart(self, s01, s01_case):
        s, _ = run_session(s01, "pool", case=s01_case)
        for e in s.events:
            assert e.actor not in e.audience
            assert len(e.audience) == 1     # 2인 교대 제안

    def test_base_bytes_plan_independent(self, s01, s01_case):
        a, _ = run_session(s01, "seq2", case=s01_case)
        b, _ = run_session(s01, "pool", case=s01_case)
        assert a.base_bytes == b.base_bytes

    def test_peak_comes_from_vendor_runner(self, s01, s01_case):
        # 밖에서 tracemalloc을 겹쳐 감싸면 내부 stop()이 추적을 꺼 0이 된다
        s, _ = run_session(s01, "pool", case=s01_case)
        assert s.peak_bytes > 0

    def test_wall_ms_kept_as_reference_only(self, s01, s01_case):
        s, _ = run_session(s01, "pool", case=s01_case)
        assert "wall_ms" in s.extra      # 판정에는 안 쓰고 참고로만 남긴다

    def test_unknown_plan_rejected(self, s01):
        with pytest.raises(KeyError):
            run_session(s01, "nope")


class TestFcRegression:
    """`fc_benchmark.jsonl` S01 시드 1201 행과 대조."""

    @pytest.mark.parametrize("plan,achieved,s_val", [
        ("full", 0.9698, 0.9068),
        ("pool", 1.0000, 1.0000),
        ("seq", 0.7539, 0.2400),
    ])
    def test_achieved_and_s(self, s01, s01_case, plan, achieved, s_val):
        session, case = run_session(s01, plan, case=s01_case)
        score = fc.score(case, session.agreement,
                         extra_violations=case.hard_violations(session.agreement))
        assert score.achieved == pytest.approx(achieved, abs=TOL)
        assert score.s == pytest.approx(s_val, abs=TOL)

    @pytest.mark.parametrize("plan,phases,messages", [
        ("full", 81, 82), ("pool", 85, 86), ("seq", 79, 83),
    ])
    def test_phase_and_message_counts(self, s01, s01_case, plan, phases, messages):
        session, _ = run_session(s01, plan, case=s01_case)
        assert session.phases == phases
        assert session.messages == messages

    def test_no_fr_violations_on_s01(self, s01, s01_case):
        for plan in ("full", "pool", "seq", "seq2"):
            session, case = run_session(s01, plan, case=s01_case)
            score = fc.score(case, session.agreement,
                             extra_violations=case.hard_violations(session.agreement))
            assert score.fr_violations == [], plan


class TestIntentionalChanges:
    """정의를 **의도적으로** 바꾼 항목 — 기존 dpca 수치와 다른 것이 정상이다."""

    def test_fc_stars_now_use_s_band(self, s01, s01_case):
        """dpca `최종-QA-비교.md` §0은 달성률 직접 밴드(≥.95/.90/…)로 별점을 냈다.

        통합본은 24 §1.4의 `s` 기반 5등분을 정본으로 하고, 달성률 밴드는 **병행 지표**로
        함께 낸다. 두 별점이 어긋날 수 있는 것이 정상이다 — 절대 수준과 베이스라인 대비
        개선은 다른 질문이기 때문이다.
        """
        session, case = run_session(s01, "full", case=s01_case)
        score = fc.score(case, session.agreement)
        assert score.stars_achieved == 5      # 달성률 0.9698 → ≥.95
        assert score.stars_s == 5             # s 0.9068 → >0.8
        assert isinstance(score.stars_s, int) and isinstance(score.stars_achieved, int)

    def test_time_uses_synth_model_not_wall_clock(self, s01, s01_case):
        """dpca는 `wall_ms` 절대 초 밴드로 시간 별점을 냈다.

        실행 머신 성능에 의존해 재현성이 없으므로 통합본은 24 §6.4 합성 시간 모델을
        쓰고 `wall_ms`는 참고 관측으로만 남긴다.
        """
        from total.qa.tb import synth_time

        session, _ = run_session(s01, "pool", case=s01_case)
        t = synth_time(session)
        assert t.total_ms > 0
        assert t.dominant in ("phase", "eval", "transfer")
        assert session.extra["wall_ms"] > 0     # 남기되 판정에는 안 쓴다


class TestBeliefVersusTruth:
    """dpca 고유 속성 — 에이전트가 자기 선호를 부분적으로만 안다.

    시나리오의 `agent_view`(예: S01은 `score_dropout: 0.3`)가 에이전트의 자기 뷰를
    흐린다. 그래도 노출 깊이(순위표 노출 비율 — 어떤 후보가 귀속으로 드러났는가)는
    정상 작동하며 방안 간 변별도 된다.
    """

    def test_agent_view_is_lossy(self, s01):
        assert s01.agent_view.get("score_dropout", 0) > 0

    def test_depth_discriminates_plans(self, s01, s01_case):
        from total.qa.cf import depth, observed_subs, valid_ranked

        depths = {}
        for plan in ("full", "pool", "seq2"):
            session, case = run_session(s01, plan, case=s01_case)
            victim = case.preferences[1]
            d = len(valid_ranked(case, victim))
            depths[plan] = depth(observed_subs(session, "P0", "P1"), d)
        assert depths["full"] > depths["pool"] > depths["seq2"]

    def test_ranked_excludes_hard_infeasible(self, s01_case):
        # 제안 불가 조합이 순위표에 있으면 유효 후보(깊이의 분모)가 부풀어 과소평가된다
        p = s01_case.preferences[0]
        assert len(p.ranked()) < len(list(s01_case.candidates()))
        assert all(s01_case.hard_violations(o) == [] for o in p.ranked()[:20])


class TestSweepIntegrity:
    """스윕이 거짓 데이터를 만들지 않는지 — 조용히 같은 실행을 반복하면 c가 왜곡된다."""

    def test_scenario_axis_cap_is_real(self):
        from total.adapters.composite._vendor.common.scenario import load_scenario

        path = next(p for p in scenario_paths() if p.stem.startswith("S11"))
        full = load_scenario(path)
        # 정의된 축보다 많이 요구하면 load_scenario는 조용히 전체를 준다
        over = load_scenario(path, n_axes=len(full.axes) + 5)
        assert len(over.axes) == len(full.axes)

    def test_sweep_point_is_lightweight(self):
        """스윕은 후보 공간을 열거하지 않아야 한다 — 10축이면 900만 조합이라 죽는다."""
        from total.adapters.composite import run_sweep_point
        from total.adapters.composite._vendor.common.scenario import load_scenario

        path = next(p for p in scenario_paths() if p.stem.startswith("S11"))
        sc = load_scenario(path)
        point = run_sweep_point(sc, "pool", len(sc.axes))
        assert point.scale == sc.space_size()
        assert point.peak_bytes > 0


class TestEvalCallsAreCounted:
    """`eval_calls`는 **실측 카운트**여야 한다 — 공식 추정이면 방안을 구분하지 못한다.

    이식 초판은 `len(pids) * len(space)`라는 공식을 썼다. `plan` 인자가 없으므로
    방안이 무엇이든 같은 값이 나왔고, 실제로 seq2와 pool의 `median_eval_ms`가
    똑같이 5.04ms로 찍혔다. 반면 nparty 쪽(`_vendor/protocol.py`)은 순위표 구축
    + 방안별 재평가를 실제로 센다. **같은 QA 항의 입력을 두 시나리오가 다른
    방법으로 만들고 있었다** — 24 §6.4-a의 eval 항이 요구하는 것은 호출 수다.

    이제 `AgentBeliefs.utility()` 호출을 직접 센다. 두 도메인 모두 "효용 함수가
    실제로 몇 번 불렸나"로 통일된다.
    """

    def test_eval_calls_positive(self, s01, s01_case):
        s, _ = run_session(s01, "pool", case=s01_case)
        assert s.eval_calls > 0

    def test_eval_calls_differ_by_plan(self, s01, s01_case):
        # 핵심 회귀 — 공식으로 되돌아가면 두 값이 같아진다
        seq = run_session(s01, "seq2", case=s01_case)[0].eval_calls
        pool = run_session(s01, "pool", case=s01_case)[0].eval_calls
        assert seq != pool, (
            f"방안이 달라도 eval_calls가 같다 — 공식 추정으로 되돌아갔다 "
            f"(seq2 {seq} · pool {pool})"
        )

    def test_eval_calls_is_not_the_old_formula(self, s01, s01_case):
        old = len(s01_case.pids) * len(s01_case._space_list())
        got = {p: run_session(s01, p, case=s01_case)[0].eval_calls
               for p in ("seq2", "pool")}
        assert not all(v == old for v in got.values()), f"옛 공식값 {old}과 같다: {got}"

    def test_eval_calls_reproducible(self, s01, s01_case):
        # 계수기가 세션 간에 새지 않는지 — 전역 카운터면 두 번째가 더 크게 나온다
        a = run_session(s01, "pool", case=s01_case)[0].eval_calls
        b = run_session(s01, "pool", case=s01_case)[0].eval_calls
        assert a == b, f"세션마다 값이 달라진다 ({a} → {b}) — 계수기가 누적되고 있다"

    def test_compression_plans_evaluate_less_than_full_enumeration(self, s01, s01_case):
        # 후보군을 압축하는 방안이 전수 열거보다 적게 평가해야 한다 — 그게 설계 의도다
        full = run_session(s01, "full", case=s01_case)[0].eval_calls
        pool = run_session(s01, "pool", case=s01_case)[0].eval_calls
        assert pool < full, f"압축 방안이 전수 열거보다 많이 평가한다 (pool {pool} · full {full})"

    def test_sequential_evaluations_are_not_bypassed(self):
        """1안은 `utility()`를 거치지 않고 `weights`·`scores`를 직접 읽는다.

        `utility()` 호출만 세면 1안이 세 자릿수 적게 잡힌다 — S01에서 2회로
        나왔었다. `_optimistic`·`_score`도 같은 계수기로 세야 한다.
        """
        from total.adapters.composite._vendor.harness.beliefs import AgentBeliefs
        import inspect
        src = inspect.getsource(AgentBeliefs)
        assert "def note_eval" in src, "우회 경로용 계수 진입점이 사라졌다"

        sc = load("S01")
        case = CompositeCase(sc.id, sc)
        seq = run_session(sc, "seq2", case=case)[0].eval_calls
        assert seq > 100, (
            f"1안 eval_calls가 {seq}회 — 축 단위 평가가 계수에서 빠졌다 "
            f"(_optimistic·_score의 note_eval() 호출을 확인할 것)"
        )
