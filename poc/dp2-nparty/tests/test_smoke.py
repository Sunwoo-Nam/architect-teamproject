"""end-to-end 스모크 — 개발용 TableUfun으로 두 방안이 돌고 측정이 계산되는지."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dp2_nparty.domain import NO_DEAL, Profile
from dp2_nparty.harness import Experiment
from dp2_nparty.measures import fc
from dp2_nparty.measures.scaling import loglog_fit, stars_b_msg
from dp2_nparty.protocol import Plan1Vote, Plan2Cumulative, Plan3Batch
from dp2_nparty.protocol_styles import Plan4Mesh, Plan5Ring, Plan6Tree, Plan7Gossip, Plan8Rotate
from dp2_nparty.threshold import SweepThreshold
from dp2_nparty.ufun_provider import TableUfun


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
    for cls in (Plan1Vote, Plan2Cumulative, Plan3Batch, Plan4Mesh, Plan5Ring, Plan6Tree, Plan7Gossip, Plan8Rotate):
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
    for cls in (Plan1Vote, Plan2Cumulative, Plan3Batch, Plan4Mesh, Plan5Ring, Plan6Tree, Plan7Gossip, Plan8Rotate):
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


def test_ft_injection_degrades_and_recovers_grading():
    from dp2_nparty.faults import FaultInjector
    from dp2_nparty.measures.ft import evaluate, stars_ft
    from dp2_nparty.ufun_provider import TableUfun

    # 유실 주입 시 세션이 여전히 종결되고(무한 루프 없음), 재시도로 라운드가 늘어난다
    rng = random.Random(11)
    cands = [f"s{j}" for j in range(10)]
    profiles = TableUfun().build_profiles(cands, 3, rng)
    clean = Plan2Cumulative(profiles).run()
    noisy = Plan2Cumulative(profiles).run(injector=FaultInjector(0.3, 42))
    assert noisy.rounds >= clean.rounds
    # 별점 경계
    assert stars_ft(0.5) == 0 and stars_ft(1.0) == 1 and stars_ft(10) == 5 and stars_ft(5.7) == 4
    r = evaluate(95, 100, {1: (47, 50), 5: (45, 50), 10: (30, 50)}, 0.01)
    assert r.critical_multiple == 10 and r.margin == 10 and r.stars == 5


def test_rec_kill_resume_consistency():
    from dp2_nparty.measures.rec import stars_rec, trial

    rng = random.Random(12)
    cands = [f"s{j}" for j in range(10)]
    profiles = TableUfun().build_profiles(cands, 3, rng)
    for cls, point in ((Plan1Vote, "post_votes"), (Plan2Cumulative, "mid_round")):
        t = trial(cls, profiles, point, 2)
        assert t.fr_ok, (cls.__name__, point)  # 복구 후 결과가 무중단 실행과 동일 (FR)
        if t.ratio is not None:
            assert t.ratio > 0
    assert stars_rec(0.9, 16) == 5 and stars_rec(17, 16) == 0 and stars_rec(3.9, 16) == 3


def test_bytes_counted():
    rng = random.Random(13)
    cands = [f"s{j}" for j in range(10)]
    profiles = TableUfun().build_profiles(cands, 3, rng)
    r1, r2 = Plan1Vote(profiles).run(), Plan2Cumulative(profiles).run()
    assert r1.bytes > 0 and r2.bytes > 0
    assert r1.bytes > r2.bytes  # 방안 1은 공지·투표·결과 페이로드가 추가된다


def test_plan3a_batch_properties():
    from dp2_nparty.measures import fc as fcmod

    rng = random.Random(21)
    cands = [f"s{j}" for j in range(12)]
    profiles = TableUfun().build_profiles(cands, 3, rng)
    r2 = Plan2Cumulative(profiles).run()
    r3 = Plan3Batch(profiles).run()
    # 3-A는 라운드 반복이 없어 phase가 방안 2 이하이고, 배치라 전송 건수도 적다
    assert r3.phases <= r2.phases
    assert r3.messages <= r2.messages
    # 교집합 "첫" 후보가 아니라 "최선(순위합 최소)"을 고르므로 달성률이 방안 2 이상이어야 한다
    f2 = fcmod.score(r2.outcome, cands, profiles)
    f3 = fcmod.score(r3.outcome, cands, profiles)
    assert f3.ratio >= f2.ratio - 1e-9


def test_style_plans_properties():
    from dp2_nparty.faults import FaultInjector
    from dp2_nparty.measures.rec import trial

    rng = random.Random(31)
    cands = [f"s{j}" for j in range(12)]
    profiles = TableUfun().build_profiles(cands, 3, rng)
    base = {cls.plan_name: cls(profiles).run() for cls in (Plan4Mesh, Plan5Ring, Plan6Tree)}
    # 결과 정합: 세 스타일 모두 같은 만장일치 규칙이므로 방안 2 계열과 동일 결과에 도달해야 한다
    r2 = Plan2Cumulative(profiles).run()
    assert base["plan4mesh"].outcome == r2.outcome  # mesh = 분산판 방안 2
    # 통신 구조 성질
    assert base["plan4mesh"].messages > r2.messages  # 방송 N-1배
    assert base["plan5ring"].phases >= base["plan4mesh"].phases  # 직렬 홉 > 병렬 라운드
    assert base["plan6tree"].phases <= base["plan5ring"].phases  # 트리 log 병합
    # 유실 주입에도 종결
    for cls in (Plan4Mesh, Plan5Ring, Plan6Tree):
        r = cls(profiles).run(injector=FaultInjector(0.3, 7))
        assert r.rounds >= 1
    # kill-resume FR 정합
    for cls in (Plan4Mesh, Plan6Tree):
        tr = trial(cls, profiles, "mid_round", 1)
        assert tr.fr_ok, cls.plan_name


def test_gossip_and_rotate_properties():
    from dp2_nparty.faults import FaultInjector
    from dp2_nparty.measures.rec import trial

    rng = random.Random(41)
    cands = [f"s{j}" for j in range(12)]
    profiles = TableUfun().build_profiles(cands, 3, rng)
    g = Plan7Gossip(profiles).run()
    m = Plan4Mesh(profiles).run()
    r8 = Plan8Rotate(profiles).run()
    r3 = Plan3Batch(profiles).run()
    assert g.outcome == m.outcome  # 가십도 같은 만장일치 결과에 도달
    # 가십의 선형 이득은 N이 커야 발현 — N=8에서 총 전송이 mesh보다 적어야 한다
    big = TableUfun().build_profiles(cands, 8, random.Random(42))
    assert Plan7Gossip(big).run().messages < Plan4Mesh(big).run().messages
    assert r8.outcome == r3.outcome  # 순환 담당은 3-A와 동일 판정 (담당자만 교대)
    for cls in (Plan7Gossip, Plan8Rotate):
        r = cls(profiles).run(injector=FaultInjector(0.3, 9))
        assert r.rounds >= 1
        tr = trial(cls, profiles, "mid_round", 1)
        assert tr.fr_ok, cls.plan_name
