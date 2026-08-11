"""P1 하니스 스모크 — 전략 3종이 동일 TC에서 완주하고 채점이 일관되는지."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest

from dpca.common.oracle import analyze
from dpca.common.scenario import load_scenario
from dpca.harness.judge import Judge
from dpca.harness.runner import STRATEGIES, run_one


@pytest.fixture(scope="module")
def s01():
    return load_scenario(ROOT / "scenarios" / "S01-기준.yaml")


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_strategies_complete_s01(s01, strategy):
    result = run_one(s01, strategy)
    assert result.agreement is not None, f"{strategy}: S01은 합의가 정답"
    score = Judge(s01, analyze(s01)).score(result.agreement)
    assert 0.0 < score.achieved_rate <= 1.0
    assert not score.fr_violations, f"{strategy}: {score.fr_violations}"


def test_deterministic_same_scenario(s01):
    r1, r2 = run_one(s01, "pool"), run_one(s01, "pool")
    assert r1.agreement == r2.agreement
    assert r1.rounds == r2.rounds


def test_s08_all_strategies_break_down():
    scenario = load_scenario(ROOT / "scenarios" / "S08-합의불가.yaml")
    judge = Judge(scenario, analyze(scenario))
    for strategy in STRATEGIES:
        result = run_one(scenario, strategy)
        score = judge.score(result.agreement)
        assert result.agreement is None, f"{strategy}: 결렬이 정답인데 합의함"
        assert score.stars == 5  # 결렬이 정답이면 결렬 = 만점 (24.4)


def test_pool_memory_below_full_on_s09():
    """2안의 존재 이유 — 6축(10만 조합)에서 전수 대비 메모리가 한 차수 이상 작아야 한다."""
    scenario = load_scenario(ROOT / "scenarios" / "S09-6축확장.yaml")
    run_one(scenario, "seq")  # 워밍업 (라이브러리 초기화 할당 제거)
    full = run_one(scenario, "full")
    pool = run_one(scenario, "pool")
    assert pool.peak_kib * 10 < full.peak_kib, f"pool={pool.peak_kib:.0f} full={full.peak_kib:.0f}"


def test_eventlog_completeness(s01):
    """기록 완전성(FR CFR-H2 취지) — 모든 제안·응답에 offer·효용/점수·양보선·사유가 기록된다."""
    for strategy in STRATEGIES:
        result = run_one(s01, strategy, with_log=True)
        events = result.log.events
        proposes = [e for e in events if e["kind"] == "propose"]
        responds = [e for e in events if e["kind"] == "respond"]
        assert proposes and responds, f"{strategy}: 제안/응답 이벤트 없음"
        for e in proposes + responds:
            assert "reason" in e and "threshold" in e, f"{strategy}: 사유/양보선 누락 {e}"
        accepts = [e for e in responds if e.get("decision") == "ACCEPT"]
        assert accepts, f"{strategy}: 수락 이벤트 없음 (S01은 합의 TC)"
        assert any(e["kind"] == "session_end" for e in events) or strategy == "seq"


def test_eventlog_deterministic_replay(s01):
    """같은 시드 → 같은 로그 (결정론 재현)."""
    e1 = run_one(s01, "pool", with_log=True).log.events
    e2 = run_one(s01, "pool", with_log=True).log.events
    assert e1 == e2
