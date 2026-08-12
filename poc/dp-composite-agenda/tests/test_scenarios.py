"""TC 스모크 — 로드·결정론·oracle 기대 결과."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest

from dpca.common.oracle import analyze
from dpca.common.profiles import build_truth_profiles, derive_agent_view
from dpca.common.scenario import load_scenario

SCENARIOS = sorted((ROOT / "scenarios").glob("S*.yaml"))


def test_all_scenarios_load():
    assert len(SCENARIOS) == 12
    for path in SCENARIOS:
        scenario = load_scenario(path, n_axes=4)
        assert scenario.n_participants == 2
        assert len(scenario.axes) == 4


def test_profiles_deterministic():
    s1 = load_scenario(ROOT / "scenarios" / "S01-기준.yaml")
    s2 = load_scenario(ROOT / "scenarios" / "S01-기준.yaml")
    p1, p2 = build_truth_profiles(s1), build_truth_profiles(s2)
    assert p1[0].weights == p2[0].weights
    assert p1[1].scores == p2[1].scores


def test_agent_view_differs_from_truth():
    scenario = load_scenario(ROOT / "scenarios" / "S01-기준.yaml")
    truth = build_truth_profiles(scenario)[0]
    view = derive_agent_view(scenario, truth, 0)
    assert view.weights != truth.weights  # 양자화됨
    masked = sum(
        1 for axis in truth.scores for name in truth.scores[axis]
        if view.scores[axis][name] == 0.5 and truth.scores[axis][name] != 0.5
    )
    assert masked > 0  # 일부 점수가 마스킹됨


def test_s08_breakdown_is_answer():
    """S08 — 하드 교집합 공집합이라 x* = 결렬 (24 정본: 결렬이 정답이면 결렬이 만점)."""
    scenario = load_scenario(ROOT / "scenarios" / "S08-합의불가.yaml")
    report = analyze(scenario)
    assert report.feasible_count == 0
    assert report.xstar_is_breakdown
    assert report.u_xstar == report.breakdown_total


@pytest.mark.parametrize("path", [p for p in SCENARIOS if "S08" not in p.name and "S11" not in p.name])
def test_agreement_scenarios_have_valid_xstar(path):
    """합의가 정답인 TC — 유효 후보가 존재하고 x*는 결렬이 아니어야 한다 (24.3)."""
    scenario = load_scenario(path)
    report = analyze(scenario)
    if report.skipped:
        pytest.skip(f"{scenario.id}: 공간이 오라클 한도 초과 — 전수열거 검증 생략(exact_xstar로 별도 검증)")
    assert report.valid_count > 0, f"{scenario.id}: 유효 후보 없음"
    assert not report.xstar_is_breakdown, f"{scenario.id}: x*가 결렬"
    assert 0.0 < report.r_bar <= 1.0


def test_s11_prefix_safety():
    for n in (4, 6):
        scenario = load_scenario(ROOT / "scenarios" / "S11-축수스윕.yaml", n_axes=n)
        assert len(scenario.axes) == n
        for dep in scenario.active_dependencies():
            pass  # 범위 밖 축 참조가 없어야 active_dependencies가 예외 없이 동작
        report = analyze(scenario)
        assert report.valid_count > 0 and not report.xstar_is_breakdown


def test_s08_infeasible_even_when_scaled():
    """속성 기반 제약 회귀 테스트 — date를 2주(14일)로 키워도 '주말만 vs 평일만'이라 결렬 유지."""
    scenario = load_scenario(
        ROOT / "scenarios" / "S08-합의불가.yaml", count_overrides={"date": 14}
    )
    names = [v.name for v in scenario.axis("date").values]
    assert "sat2" in names and "sun2" in names  # 둘째 주가 실제로 생성됨
    report = analyze(scenario)
    assert report.feasible_count == 0
