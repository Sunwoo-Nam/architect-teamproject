"""end-to-end 스모크 — 개발용 TableUfun으로 두 방안이 돌고 측정이 계산되는지."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dp2_nparty.domain import NO_DEAL, Profile
from dp2_nparty.harness import Experiment
from dp2_nparty.measures import fc
from dp2_nparty.measures.scaling import loglog_fit, stars_b_msg
from dp2_nparty.protocol import Plan1Vote, Plan2Cumulative
from dp2_nparty.threshold import SweepThreshold


def test_threshold_sweeps_down_to_initial():
    th = SweepThreshold(initial_threshold=0.4, max_sweeps=5, max_utility=0.9)
    values = [th.at_sweep(s) for s in range(1, 6)]
    assert values[0] == 0.9  # 첫 바퀴 = 자기 최고 utility (1순위만 제출 가능)
    assert all(a >= b for a, b in zip(values, values[1:]))  # 단조 하강
    assert abs(values[-1] - 0.4) < 1e-9  # 마지막 바퀴 = initial threshold까지 개방


def test_both_plans_agree_on_obvious_case():
    # 전원에게 utility 0.9인 공통 최애 후보가 있으면 두 방안 다 그 후보로 성립해야 한다
    cands = ["A", "B", "C"]
    profiles = [
        Profile(f"P{i}", {"A": 0.9, "B": 0.5 + i * 0.01, "C": 0.2}, 0.4) for i in range(3)
    ]
    for cls in (Plan1Vote, Plan2Cumulative):
        r = cls(profiles).run()
        assert r.outcome == "A", (cls.__name__, r)
        assert r.messages > 0


def test_no_deal_when_infeasible():
    # 서로의 상위 후보가 상대 threshold 미달 — 유효 후보 없음 → 결렬이 정답
    profiles = [
        Profile("P0", {"A": 0.9, "B": 0.1}, 0.4),
        Profile("P1", {"A": 0.1, "B": 0.9}, 0.4),
        Profile("P2", {"A": 0.1, "B": 0.1}, 0.4),
    ]
    for cls in (Plan1Vote, Plan2Cumulative):
        r = cls(profiles).run()
        assert r.outcome == NO_DEAL
        s = fc.score(r.outcome, ["A", "B"], profiles)
        assert s.ratio == 1.0  # 정답이 결렬이므로 만점


def test_experiment_and_fc_scoring():
    out = Experiment(n_participants=3, n_candidates=10, runs=5).run()
    for plan, records in out.items():
        assert len(records) == 5
        for rec in records:
            assert 0.0 < rec.fc.ratio <= 1.0
            assert 0 <= rec.fc.stars <= 5
            assert rec.session.messages > 0
    # 동일 프로파일 원칙: 같은 회차의 두 방안은 같은 x*를 봐야 한다
    for r1, r2 in zip(out["plan1"], out["plan2"]):
        assert r1.fc.optimal == r2.fc.optimal


def test_loglog_fit_and_stars():
    xs = [3, 4, 5, 6, 8, 10]
    ys = [x**1.5 * 7 for x in xs]  # 지수 1.5를 심어 두면
    fit = loglog_fit(xs, ys)
    assert abs(fit.b - 1.5) < 1e-6  # 회귀가 그대로 찾아야 한다
    assert stars_b_msg(fit.b) == 2  # 1.4 초과 - 1.6 이하 → 2점
    assert stars_b_msg(0.97) == 5 and stars_b_msg(1.05) == 4 and stars_b_msg(1.9) == 0


def test_confidentiality_viewpoints():
    from dp2_nparty.measures.confidentiality import measure_gain
    from dp2_nparty.ufun_provider import TableUfun

    rng = random.Random(7)
    cands = [f"s{j}" for j in range(10)]
    profiles = TableUfun().build_profiles(cands, 3, rng)
    runs1 = [(Plan1Vote(profiles).run(), profiles)]
    runs2 = [(Plan2Cumulative(profiles).run(), profiles)]
    # 방안 2의 일반 참여자 관찰자는 아무 신호도 못 봐 무작위 수준이어야 한다
    g2p = measure_gain(runs2, 10, viewpoint="participant")
    assert abs(g2p.gain_pp) < 1e-9
    # 방안 1의 일반 참여자는 1라운드 공지로 1순위를 그대로 본다 — 이득이 커야 한다
    g1p = measure_gain(runs1, 10, viewpoint="participant")
    assert g1p.gain_pp > 50
    # phase 지표: 방안 1은 라운드당 4단계라 방안 2보다 직렬 단계가 많다
    assert runs1[0][0].phases > runs2[0][0].phases
