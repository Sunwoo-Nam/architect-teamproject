"""end-to-end 스모크 — 개발용 TableUfun으로 두 방안이 돌고 측정이 계산되는지."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dp2_nparty.domain import NO_DEAL, Profile
from dp2_nparty.harness import Experiment
from dp2_nparty.measures import fc
from dp2_nparty.measures.scaling import loglog_fit, stars_b_msg
from dp2_nparty.protocol import Plan1Vote, Plan2Cumulative, Plan20Batch
from dp2_nparty.protocol_styles import (
    Plan1aSao, Plan3Mesh, Plan4Ring, Plan5Gossip, Plan6ITree, Plan7RotCollect,
    Plan8Hypercube, Plan9Psi, Plan10Shard, Plan21Tree, Plan22Rotate,
)
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
    for cls in (Plan1Vote, Plan1aSao, Plan2Cumulative, Plan3Mesh, Plan4Ring, Plan5Gossip,
                Plan6ITree, Plan20Batch, Plan21Tree, Plan22Rotate):
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
    for cls in (Plan1Vote, Plan1aSao, Plan2Cumulative, Plan3Mesh, Plan4Ring, Plan5Gossip,
                Plan6ITree, Plan20Batch, Plan21Tree, Plan22Rotate):
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


def test_plan20batch_batch_properties():
    from dp2_nparty.measures import fc as fcmod

    rng = random.Random(21)
    cands = [f"s{j}" for j in range(12)]
    profiles = TableUfun().build_profiles(cands, 3, rng)
    r2 = Plan2Cumulative(profiles).run()
    r3 = Plan20Batch(profiles).run()
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
    base = {cls.plan_name: cls(profiles).run()
            for cls in (Plan3Mesh, Plan4Ring, Plan6ITree, Plan21Tree)}
    # 결과 정합: 스타일들 모두 같은 만장일치 규칙이므로 방안 2 계열과 동일 결과에 도달해야 한다
    r2 = Plan2Cumulative(profiles).run()
    assert base["plan3mesh"].outcome == r2.outcome  # mesh = 분산판 방안 2
    assert base["plan6itree"].outcome == r2.outcome  # 계층 교집합 = 트리판 방안 2 (FC 동일)
    assert base["plan6itree"].rounds == r2.rounds  # 라운드 단위 판정 동일
    # 통신 구조 성질
    assert base["plan3mesh"].messages > r2.messages  # 방송 N-1배
    assert base["plan6itree"].messages <= base["plan3mesh"].messages  # 트리 간선 ≤ 방송
    assert base["plan4ring"].phases >= base["plan3mesh"].phases  # 직렬 홉 > 병렬 라운드
    assert base["plan21tree"].phases <= base["plan4ring"].phases  # 트리 log 병합
    # 유실 주입에도 종결
    for cls in (Plan3Mesh, Plan4Ring, Plan6ITree, Plan21Tree):
        r = cls(profiles).run(injector=FaultInjector(0.3, 7))
        assert r.rounds >= 1
    # kill-resume FR 정합
    for cls in (Plan3Mesh, Plan6ITree, Plan21Tree):
        tr = trial(cls, profiles, "mid_round", 1)
        assert tr.fr_ok, cls.plan_name


def test_gossip_and_rotate_properties():
    from dp2_nparty.faults import FaultInjector
    from dp2_nparty.measures.rec import trial

    rng = random.Random(41)
    cands = [f"s{j}" for j in range(12)]
    profiles = TableUfun().build_profiles(cands, 3, rng)
    g = Plan5Gossip(profiles).run()
    m = Plan3Mesh(profiles).run()
    r8 = Plan22Rotate(profiles).run()
    r3 = Plan20Batch(profiles).run()
    assert g.outcome == m.outcome  # 가십도 같은 만장일치 결과에 도달
    # 가십의 선형 이득은 N이 커야 발현 — N=8에서 총 전송이 mesh보다 적어야 한다
    big = TableUfun().build_profiles(cands, 8, random.Random(42))
    assert Plan5Gossip(big).run().messages < Plan3Mesh(big).run().messages
    assert r8.outcome == r3.outcome  # 순환 담당은 3-A와 동일 판정 (담당자만 교대)
    for cls in (Plan5Gossip, Plan22Rotate):
        r = cls(profiles).run(injector=FaultInjector(0.3, 9))
        assert r.rounds >= 1
        tr = trial(cls, profiles, "mid_round", 1)
        assert tr.fr_ok, cls.plan_name


def test_ru_person_attribution():
    from dp2_nparty.measures.ru_person import holder_sizes
    from dp2_nparty.protocol import Plan2Cumulative
    from dp2_nparty.protocol_styles import Plan3Mesh, Plan6ITree

    rng = random.Random(51)
    cands = [f"s{j}" for j in range(12)]
    profiles = TableUfun().build_profiles(cands, 4, rng)
    seen = {}
    for cls in (Plan2Cumulative, Plan3Mesh, Plan6ITree):
        plan = cls(profiles, collect_log=False)
        peaks = [0] * 4
        def cb(plan=plan, peaks=peaks):
            for i, s in enumerate(holder_sizes(plan)):
                peaks[i] = max(peaks[i], s)
        plan.run(on_round_end=cb)
        seen[plan.plan_name] = peaks
    # BB: 담당자만 부하, mesh: 전원 동일(복제), itree: root ≥ 내부 ≥ 리프
    assert seen["plan2"][0] > 0 and all(v == 0 for v in seen["plan2"][1:])
    assert len(set(seen["plan3mesh"])) == 1 and seen["plan3mesh"][0] > 0
    it = seen["plan6itree"]
    assert it[0] >= it[1] >= it[3] and it[3] > 0  # root ≥ P1(부모) ≥ P3(리프, 자기 것만)
    # mesh 전원 합계 = 1부의 N배 성질
    assert sum(seen["plan3mesh"]) == 4 * seen["plan3mesh"][0]


def test_new_incremental_steelmen_match_plan2():
    from dp2_nparty.faults import FaultInjector
    from dp2_nparty.measures.rec import trial

    rng = random.Random(61)
    cands = [f"s{j}" for j in range(12)]
    profiles = TableUfun().build_profiles(cands, 5, rng)
    r2 = Plan2Cumulative(profiles).run()
    runs = {cls.plan_name: cls(profiles).run()
            for cls in (Plan7RotCollect, Plan8Hypercube, Plan9Psi, Plan10Shard)}
    for name, r in runs.items():
        assert r.outcome == r2.outcome, name   # 같은 합의 규칙 → 결과 동일
        assert r.rounds == r2.rounds, name     # 판정 시점도 라운드 단위 동일
    # 구조 성질: 샤딩은 방안 2와 같은 라운드당 1 phase 수준, PSI는 메시지 최다
    assert runs["plan10shard"].phases <= r2.phases + 2
    assert runs["plan9psi"].messages > runs["plan8hcube"].messages
    assert runs["plan9psi"].bytes > r2.bytes  # 블라인딩 blob 비용
    # 유실·복구 내성
    for cls in (Plan7RotCollect, Plan8Hypercube, Plan9Psi, Plan10Shard):
        r = cls(profiles).run(injector=FaultInjector(0.3, 17))
        assert r.rounds >= 1
        tr = trial(cls, profiles, "mid_round", 1)
        assert tr.fr_ok, cls.plan_name


def test_plan1a_sao_matches_plan1_and_cuts_cost():
    """방안 1-A — 방안 1의 판정을 그대로 두고 게시판만 제거한 SAO 사설 메시지판."""
    from dp2_nparty.faults import FaultInjector
    from dp2_nparty.measures.confidentiality import measure_gain
    from dp2_nparty.measures.rec import trial
    from dp2_nparty.measures.ru_person import holder_sizes

    cands = [f"s{j}" for j in range(15)]
    for n in (3, 5, 8):
        profiles = TableUfun().build_profiles(cands, n, random.Random(81 + n))
        r1, ra = Plan1Vote(profiles).run(), Plan1aSao(profiles).run()
        # 라운드 k의 판정 후보 집합이 "전원의 k순위"로 방안 1과 같다 → FC·라운드 수 동일
        assert ra.outcome == r1.outcome, n
        assert ra.rounds == r1.rounds, n
        # 라운드당 4 phase·4(N-1)건 → 2 phase·2(N-1)건 (O/X와 다음 후보를 한 메시지로 병합)
        assert ra.phases < r1.phases, n
        assert ra.messages < r1.messages, n

    cands20 = [f"s{j}" for j in range(20)]
    profiles = TableUfun().build_profiles(cands20, 5, random.Random(82))
    runs_a = [(Plan1aSao(profiles).run(), profiles)]
    runs_1 = [(Plan1Vote(profiles).run(), profiles)]
    # 노출: 익명 재배포 + O/X 결과 공지 없음 → 일반 참여자는 방안 2와 같은 무신호
    assert abs(measure_gain(runs_a, 20, viewpoint="participant").gain_pp) < 1e-9
    assert measure_gain(runs_1, 20, viewpoint="participant").gain_pp > 50
    # 대가: 담당자 1인에게는 방안 1과 똑같이 전량이 모인다
    assert abs(measure_gain(runs_a, 20, viewpoint="coordinator").gain_pp
               - measure_gain(runs_1, 20, viewpoint="coordinator").gain_pp) < 1e-9
    # RU 귀속: 게시판이 없어도 제출이 전부 담당자에게 가므로 보유 구조가 방안 1과 같다
    plan = Plan1aSao(profiles, collect_log=False)
    peaks = [0] * 5
    def cb(plan=plan, peaks=peaks):
        for i, s in enumerate(holder_sizes(plan)):
            peaks[i] = max(peaks[i], s)
    plan.run(on_round_end=cb)
    assert peaks[0] > 0 and all(v == 0 for v in peaks[1:])
    # 유실 내성: O/X와 다음 후보가 한 메시지에 결합돼도(1건 유실 = 둘 다 손실) 종결한다
    assert Plan1aSao(profiles).run(injector=FaultInjector(0.3, 17)).rounds >= runs_a[0][0].rounds
    # 중단-복구: 배포 직후·회신 직후·확정 직전 3지점 모두 무중단 실행과 같은 결과로 재개
    for point in ("mid_round", "post_votes", "pre_final"):
        assert trial(Plan1aSao, profiles, point, 2).fr_ok, point


def test_new_plans_cf_visibility():
    from dp2_nparty.measures.confidentiality import measure_gain

    rng = random.Random(71)
    cands = [f"s{j}" for j in range(20)]
    profiles = TableUfun().build_profiles(cands, 8, rng)
    # PSI: 어떤 관점도 아무 신호를 못 봐 이득 0이어야 한다
    runs = [(Plan9Psi(profiles).run(), profiles)]
    for vp in ("participant", "coordinator"):
        assert abs(measure_gain(runs, 20, viewpoint=vp).gain_pp) < 1e-9, vp
    # 샤딩: 관찰자가 보는 남의 제출은 전체의 일부여야 한다 (전량 노출 아님)
    from dp2_nparty.measures.confidentiality import _visible_events
    s = Plan10Shard(profiles).run()
    pids = [p.pid for p in profiles]
    seen = _visible_events(s, pids[1], pids[0])
    seen_others = sum(1 for ev in seen for p in ev["submitted"] if p != pids[1])
    total_others = sum(1 for ev in s.log if ev["t"] == "round"
                       for p in ev["submitted"] if p != pids[1])
    assert 0 <= seen_others < total_others
