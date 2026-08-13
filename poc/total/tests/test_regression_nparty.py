"""회귀 안전망 — 통합 라이브러리가 dp2 기존 실행과 같은 수치를 내는가.

기준: `poc/dp2-nparty/results/full-20260812T171034KST`
(t_phase 75ms · t_eval 3µs · bw 20 Mbps, 틱 계수 반영)

**이 파일이 없으면 "통합했더니 결과가 달라졌다"를 설명할 수 없다.** 값이 어긋나면
이식 버그이고, 의도적으로 정의를 바꾼 항목은 아래 `TestIntentionalChanges`에 명시한다.
"""
from __future__ import annotations

import collections
import statistics

import pytest

from total.adapters.nparty import NpartyCase, run_session
from total.adapters.nparty._vendor.benchmark import JsonBenchmarkLoader
from total.adapters.nparty._vendor.domain import Profile
from total.qa import cf, fc

TOL = 5e-4


def _cases(track: str, limit: int | None = None):
    cs = sorted(JsonBenchmarkLoader(track=track).cases(), key=lambda c: c.case_id)
    return cs[:limit] if limit else cs


def _mkcase(bc) -> NpartyCase:
    return NpartyCase(bc.case_id,
                      [Profile(p.pid, dict(p.utilities), p.initial_threshold)
                       for p in bc.profiles])


@pytest.fixture(scope="module")
def functional():
    return _cases("functional")


@pytest.fixture(scope="module")
def fc_scores(functional):
    out: dict[str, list] = {}
    for plan in ("plan1a", "plan2"):
        rows = []
        for bc in functional:
            session, _ = run_session(bc.profiles, plan)
            rows.append((len(bc.profiles), fc.score(_mkcase(bc), session.agreement)))
        out[plan] = rows
    return out


class TestBenchmarkIntegrity:
    """데이터셋이 옮겨오면서 빠지지 않았는지부터 확인한다."""

    def test_functional_case_count(self, functional):
        assert len(functional) == 160

    def test_scalability_case_count(self):
        assert len(_cases("scalability")) == 300

    def test_participant_mix(self, functional):
        mix = collections.Counter(len(c.profiles) for c in functional)
        assert dict(mix) == {3: 100, 5: 30, 7: 30}


class TestFcRegression:
    """FC 달성률 — 8개 값 전부 기준과 일치해야 한다."""

    @pytest.mark.parametrize("plan,expected", [("plan1a", 0.9142), ("plan2", 0.9679)])
    def test_overall_mean(self, fc_scores, plan, expected):
        got = statistics.fmean(s.achieved for _n, s in fc_scores[plan])
        assert got == pytest.approx(expected, abs=TOL)

    @pytest.mark.parametrize("plan,n,expected", [
        ("plan1a", 3, 0.9299), ("plan1a", 5, 0.8982), ("plan1a", 7, 0.8777),
        ("plan2", 3, 0.9716), ("plan2", 5, 0.9646), ("plan2", 7, 0.9588),
    ])
    def test_by_participants(self, fc_scores, plan, n, expected):
        rows = [s.achieved for m, s in fc_scores[plan] if m == n]
        assert statistics.fmean(rows) == pytest.approx(expected, abs=TOL)

    def test_plan2_beats_plan1a(self, fc_scores):
        # 실측 결론 — FC는 방안 2가 이긴다
        a = statistics.fmean(s.achieved for _n, s in fc_scores["plan1a"])
        b = statistics.fmean(s.achieved for _n, s in fc_scores["plan2"])
        assert b > a

    def test_plan1a_degrades_with_n(self, fc_scores):
        # 요약표에 가려져 있던 열화 — 3인 → 7인에서 방안 1-A만 떨어진다
        by = {n: statistics.fmean(s.achieved for m, s in fc_scores["plan1a"] if m == n)
              for n in (3, 5, 7)}
        assert by[3] > by[5] > by[7]


class TestCfRegression:
    """CF — A축 노출 배수와 관점별 노출률."""

    @pytest.fixture(scope="class")
    @staticmethod
    def anchor():
        runs = []
        for bc in _cases("functional", 30):
            pair = bc.profiles[:2]
            s, _ = run_session(pair, "plan2")
            runs.append((s, NpartyCase(
                bc.case_id,
                [Profile(p.pid, dict(p.utilities), p.initial_threshold) for p in pair])))
        return cf.e2_anchor(runs)

    @pytest.fixture(scope="class")
    @staticmethod
    def evaluated(anchor):
        out = {}
        for plan in ("plan1a", "plan2"):
            runs = []
            for bc in _cases("functional", 100):
                s, _ = run_session(bc.profiles, plan)
                runs.append((s, _mkcase(bc)))
            out[plan] = cf.evaluate(
                runs, anchor, viewpoints=[cf.COORDINATOR_FIRST, cf.worst_participant()])
        return out

    def test_e2_anchor_a_axis(self, anchor):
        assert anchor.depth_a == pytest.approx(0.6333, abs=1e-3)

    @pytest.mark.parametrize("plan,expected", [("plan1a", 0.677), ("plan2", 1.184)])
    def test_exposure_multiple_a(self, evaluated, plan, expected):
        assert evaluated[plan]["multiple"]["m_A"] == pytest.approx(expected, abs=1e-3)

    @pytest.mark.parametrize("plan,expected", [("plan1a", 0.429), ("plan2", 0.75)])
    def test_max_single_depth(self, evaluated, plan, expected):
        assert evaluated[plan]["multiple"]["max_single_depth_A"] == pytest.approx(
            expected, abs=1e-3)

    @pytest.mark.parametrize("plan", ["plan1a", "plan2"])
    def test_participant_sees_nothing(self, evaluated, plan):
        assert evaluated[plan]["viewpoints"]["participant"]["exposure_rate"] == 0.0

    @pytest.mark.parametrize("plan", ["plan1a", "plan2"])
    def test_coordinator_sees_everything(self, evaluated, plan):
        assert evaluated[plan]["viewpoints"]["coordinator"]["exposure_rate"] == 1.0

    def test_plan1a_leaks_less(self, evaluated):
        # 실측 결론 — 노출 배수는 방안 1-A가 이긴다
        assert evaluated["plan1a"]["multiple"]["m_A"] < evaluated["plan2"]["multiple"]["m_A"]

    def test_stars_reflect_one_to_one_boundary(self, evaluated):
        assert evaluated["plan1a"]["multiple"]["stars_m_A"] == 3   # m ≤ 1 → 1:1 이하
        assert evaluated["plan2"]["multiple"]["stars_m_A"] == 2    # m > 1 → 1:1 초과


class TestIntentionalChanges:
    """정의를 **의도적으로** 바꾼 항목 — 기존 수치와 다른 것이 정상이다."""

    def test_depth_b_now_spans_all_sweeps(self):
        """B축(접두 복원 깊이)이 바퀴 1 제한에서 전 바퀴로 넓어졌다.

        기존 dp2 `cf_depth.depth_b`는 바퀴 1의 라운드 번호를 순위로 읽어(`라운드 k = 순위 k`)
        해당 프로토콜에만 통하는 강한 가정을 썼다. 24 §7.4 규칙 ①은 "가장 이른
        **(바퀴, 라운드)**"라고 명시하므로 전 바퀴를 보는 것이 정의에 맞고, 라운드 번호가
        순위와 무관한 도메인(dpca 축별 순차)에도 적용된다.

        결과: 이 프로토콜에서는 참여자가 순위 순서대로 제출하므로 B가 A와 거의 같아진다.
        B의 변별력은 관찰 순서가 순위 순서와 다른 구조에서 나온다 — 그 자체가 옳은 결과다.
        """
        from total.qa.cf import depth_a, depth_b

        ranked = ["a", "b", "c", "d"]
        in_order = [(1, 1, "a"), (2, 1, "b")]          # 바퀴를 넘어 순위 순서 유지
        assert depth_b(in_order, ranked, 4) == pytest.approx(0.5)

        shuffled = [(1, 1, "b"), (1, 2, "a")]           # 순서가 어긋나면 B만 떨어진다
        assert depth_a(shuffled, 4) == pytest.approx(0.5)
        assert depth_b(shuffled, ranked, 4) == 0.0
