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

    @pytest.mark.parametrize("plan,base,s,stars", [
        ("plan1a", 0.8759, 0.3086, 2),
        ("plan2",  0.8759, 0.7411, 4),
    ])
    def test_pooled_s_matches_dp2(self, fc_scores, plan, base, s, stars):
        """개선 비율 s의 집계 — dp2 원본 `raw.json`의 발표값과 일치해야 한다.

        dp2 `campaign.py:73`·`full_campaign.py:349`는 처음부터 24 §1.4대로
        달성률 평균과 R̄ 평균을 먼저 낸 뒤 한 번 환산했다. 이식 초판이 세션별 s를
        평균 내면서 plan1a ★3·plan2 ★5로 한 칸씩 부풀었다 (§13-R7).

        R̄가 두 방안에서 같은 것은 정상이다 — R̄는 후보 공간에만 의존하고
        어떤 프로토콜을 돌렸는지와 무관하다.
        """
        agg = fc.aggregate([sc for _n, sc in fc_scores[plan]])
        assert agg["mean_baseline"] == pytest.approx(base, abs=TOL)
        assert agg["mean_s"] == pytest.approx(s, abs=TOL)
        assert agg["stars_s"] == stars

    def test_baseline_is_plan_independent(self, fc_scores):
        # 같은 케이스 표본을 돌렸으므로 R̄는 방안과 무관하게 같아야 한다
        a = fc.aggregate([s for _n, s in fc_scores["plan1a"]])["mean_baseline"]
        b = fc.aggregate([s for _n, s in fc_scores["plan2"]])["mean_baseline"]
        assert a == pytest.approx(b, abs=TOL)

    def test_plan1a_degrades_with_n(self, fc_scores):
        # 요약표에 가려져 있던 열화 — 3인 → 7인에서 방안 1-A만 떨어진다
        by = {n: statistics.fmean(s.achieved for m, s in fc_scores["plan1a"] if m == n)
              for n in (3, 5, 7)}
        assert by[3] > by[5] > by[7]


class TestCfRegression:
    """CF — 후보안 노출률(판정, 2026-08-14 재개정)·노출 배수 m(보조). 분모 = 전체 후보, 모수 = 합의 세션,
    대표값 = 평균 (PL 확정 2026-08-13 — 격자 스냅 회피)."""

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

    def test_e2_anchor_depth(self, anchor):
        # 분모 = 전체 후보 (2026-08-13 재개정) — 2인 세션에서 상대가 12개 중 3개를 봄
        assert anchor.depth == pytest.approx(0.25, abs=1e-3)

    @pytest.mark.parametrize("plan,expected", [("plan1a", 0.7611), ("plan2", 1.1319)])
    def test_exposure_multiple(self, evaluated, plan, expected):
        assert evaluated[plan]["multiple"]["m"] == pytest.approx(expected, abs=1e-3)

    @pytest.mark.parametrize("plan,expected", [("plan1a", 0.1903), ("plan2", 0.283)])
    def test_max_single_depth(self, evaluated, plan, expected):
        assert evaluated[plan]["multiple"]["max_single_depth"] == pytest.approx(
            expected, abs=1e-3)

    @pytest.mark.parametrize("plan", ["plan1a", "plan2"])
    def test_participant_sees_nothing(self, evaluated, plan):
        assert evaluated[plan]["viewpoints"]["participant"]["exposure_rate"] == 0.0

    @pytest.mark.parametrize("plan", ["plan1a", "plan2"])
    def test_coordinator_sees_everything(self, evaluated, plan):
        assert evaluated[plan]["viewpoints"]["coordinator"]["exposure_rate"] == 1.0

    def test_plan1a_leaks_less(self, evaluated):
        # 실측 결론 — 노출 배수는 방안 1-A가 이긴다
        assert evaluated["plan1a"]["multiple"]["m"] < evaluated["plan2"]["multiple"]["m"]

    def test_exposure_verdict_discriminates(self, evaluated):
        # 판정 = 노출률 (2026-08-14 재개정, 평균 대표값) — functional 3인 표본에서 한 등급 차.
        # 구 잔여 비밀률 판정(1-A ★5 / 2 ★4)과 동치인지도 함께 고정한다.
        assert evaluated["plan1a"]["multiple"]["stars_exposure"] == 5   # 노출 0.1903 ≤ 0.2
        assert evaluated["plan2"]["multiple"]["stars_exposure"] == 4    # 노출 0.283 ≤ 0.4
        assert evaluated["plan1a"]["multiple"]["exposure"] < evaluated["plan2"]["multiple"]["exposure"]


class TestIntentionalChanges:
    """정의를 **의도적으로** 바꾼 항목 — 기존 수치와 다른 것이 정상이다."""

    def test_depth_b_removed_by_handbook_revision(self):
        """B축(접두 복원 깊이)은 24 §3.3 개정(2026-08-13, PL 지시)으로 제거됐다.

        근거: "라운드 = 순위" 제출 규칙(51 §2) 아래에서는 귀속 관찰이 존재하면 순서도
        자동으로 노출되어 B가 A와 항상 일치하고(별도 정보 없음), 복합 의제 도메인에서는
        참조 프로토콜에서조차 순서 복원이 일어나지 않아 분모가 퇴화한다. 남은 깊이는
        **순위표 노출 비율 하나**이고, 순서와 무관한 집합 지표다.
        """
        from total import qa

        assert not hasattr(qa.cf, "depth_b")

        shuffled = [(1, 1, "b"), (1, 2, "a")]           # 순서가 달라도 깊이는 같다
        in_order = [(1, 1, "a"), (1, 2, "b")]
        assert qa.cf.depth(shuffled, 4) == qa.cf.depth(in_order, 4) == pytest.approx(0.5)
