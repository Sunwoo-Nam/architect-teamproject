"""의제 조합 케이스(issue-space-case.v1)의 계산·검증 테스트.

여기서 보는 것은 **형식이 계약을 지키는가**와 **utility 계산이 정의대로인가**다.
프로토콜 동작은 기존 테스트가 맡는다.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dp2_nparty.benchmark import BenchmarkValidationError
from dp2_nparty.issue_space import (
    ISSUE_SPACE_DIR,
    SCHEMA_VERSION,
    IssueSpaceLoader,
    all_combinations,
    case_from_dict,
    expand,
    feasible_count,
    utility_of,
    validate_issue_case,
)


def sample_raw():
    """조합 3×2×2×2 = 24개. 손으로 검산할 수 있는 크기."""
    return {
        "case_id": "T-issue-sample",
        "issues": [
            {"id": "date", "name": "날짜", "values": ["11-15", "11-16", "11-17"]},
            {"id": "time", "name": "시간", "values": ["18:00", "19:00"]},
            {"id": "venue", "name": "영화관", "values": ["강남", "홍대"]},
            {"id": "movie", "name": "영화", "values": ["A", "B"]},
        ],
        "participants": [
            {
                "pid": f"P{i}",
                "initial_threshold": 0.40,
                "weights": {"date": 0.40, "time": 0.30, "venue": 0.10, "movie": 0.20},
                "scores": {
                    "date": {"11-15": 0.9, "11-16": 0.5, "11-17": 0.1},
                    "time": {"18:00": 0.8, "19:00": 0.4},
                    "venue": {"강남": 0.7, "홍대": 0.3},
                    "movie": {"A": 0.6, "B": 0.9},
                },
            }
            for i in range(3)
        ],
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "track": "issue_space",
            "scenario_type": "movie_appointment",
            "combination_count": 24,
            "issue_sizes": [3, 2, 2, 2],
            "common_feasible_count": 0,  # 아래에서 실제 값으로 채운다
            "expected_no_deal": True,
            "description": "테스트용 표본",
        },
    }


def fixed_sample():
    """meta의 계산 항목을 실제 값으로 맞춘 표본."""
    raw = sample_raw()
    from dp2_nparty.issue_space import IssueSpaceCase

    n = feasible_count(IssueSpaceCase(raw["case_id"], raw["issues"], raw["participants"], raw["meta"]))
    raw["meta"]["common_feasible_count"] = n
    raw["meta"]["expected_no_deal"] = n == 0
    return raw


# ---------------------------------------------------------------- 계산


def test_utility_matches_hand_calculation():
    """utility = Σ 가중치 × 의제별 점수 — 정의 그대로인지 손계산과 대조."""
    raw = fixed_sample()
    p, issues = raw["participants"][0], raw["issues"]
    combo = ("11-15", "18:00", "강남", "B")
    expected = 0.40 * 0.9 + 0.30 * 0.8 + 0.10 * 0.7 + 0.20 * 0.9
    assert utility_of(p, combo, issues) == pytest.approx(expected)
    assert expected == pytest.approx(0.36 + 0.24 + 0.07 + 0.18)


def test_utility_stays_in_unit_range():
    """가중치 합 1 · 점수 0-1 이면 utility도 0-1 — 이것이 형식의 안전장치다."""
    case = case_from_dict(fixed_sample())
    bc = expand(case)
    for prof in bc.profiles:
        for u in prof.utilities.values():
            assert 0.0 <= u <= 1.0


def test_expand_produces_full_product():
    case = case_from_dict(fixed_sample())
    bc = expand(case)
    assert len(bc.candidates) == case.meta["combination_count"] == 24
    assert len(set(bc.candidates)) == 24
    for prof in bc.profiles:
        assert set(prof.utilities) == set(bc.candidates)


def test_expand_order_matches_itertools_product():
    """전개 순서가 product와 같아야 누적 계산이 후보와 어긋나지 않는다."""
    case = case_from_dict(fixed_sample())
    bc = expand(case)
    assert bc.candidates == all_combinations(case)
    p, issues = case.participants[0], case.issues
    prof = bc.profiles[0]
    for combo in bc.candidates:
        assert prof.utilities[combo] == pytest.approx(utility_of(p, combo, issues))


def test_feasible_count_matches_direct_check():
    case = case_from_dict(fixed_sample())
    bc = expand(case)
    direct = sum(
        1 for c in bc.candidates
        if all(p.utility(c) >= p.initial_threshold for p in bc.profiles)
    )
    assert feasible_count(case) == direct == case.meta["common_feasible_count"]


# ---------------------------------------------------------------- 검증기


def test_validator_accepts_valid_case():
    assert validate_issue_case(fixed_sample()) == []


@pytest.mark.parametrize(
    "mutate, expect",
    [
        (lambda r: r["participants"][0]["weights"].update({"date": 0.9}), "합이 1이 아니다"),
        (lambda r: r["participants"][0]["weights"].pop("movie"), "weights 키가 의제 id와 다르다"),
        (lambda r: r["participants"][0]["scores"]["date"].pop("11-17"), "키가 그 의제의 values와 다르다"),
        (lambda r: r["participants"][0]["scores"]["time"].update({"18:00": 1.5}), "0-1 범위"),
        (lambda r: r["participants"][0].update({"initial_threshold": 2.0}), "initial_threshold"),
        (lambda r: r["participants"].pop(), "3명 이상"),
        (lambda r: r["participants"][1].update({"pid": "P0"}), "pid가 케이스 안에서 중복"),
        (lambda r: r["issues"][0]["values"].append("11-15"), "중복이 있다"),
        (lambda r: r["meta"].update({"combination_count": 999}), "combination_count"),
        (lambda r: r["meta"].update({"issue_sizes": [1, 1, 1, 1]}), "issue_sizes"),
        (lambda r: r["meta"].update({"common_feasible_count": 999}), "common_feasible_count"),
        (lambda r: r["meta"].update({"schema_version": "v2"}), "schema_version"),
        (lambda r: r["meta"].update({"track": "functional"}), "track"),
        (lambda r: r["meta"].update({"typo": 1}), "정의되지 않은 meta"),
    ],
)
def test_validator_rejects_broken_case(mutate, expect):
    raw = fixed_sample()
    mutate(raw)
    errors = validate_issue_case(raw)
    assert errors, f"검출되어야 할 오류가 통과했다 ({expect})"
    assert any(expect in m for m in errors), f"{expect} 가 오류 메시지에 없다: {errors}"


def test_case_from_dict_raises_on_invalid():
    raw = fixed_sample()
    raw["meta"]["combination_count"] = 1
    with pytest.raises(BenchmarkValidationError):
        case_from_dict(raw)


def test_expected_no_deal_flag_is_consistent():
    raw = fixed_sample()
    raw["meta"]["expected_no_deal"] = not raw["meta"]["expected_no_deal"]
    assert any("expected_no_deal" in m for m in validate_issue_case(raw))


# ---------------------------------------------------------------- 로더


def test_loader_reads_written_case(tmp_path):
    raw = fixed_sample()
    (tmp_path / f"{raw['case_id']}.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    loader = IssueSpaceLoader(root=tmp_path)
    got = list(loader.issue_cases())
    assert [c.case_id for c in got] == [raw["case_id"]]
    assert len(list(loader.cases())[0].candidates) == 24


def test_loader_rejects_case_id_filename_mismatch(tmp_path):
    raw = fixed_sample()
    (tmp_path / "wrong-name.json").write_text(
        json.dumps(raw, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(BenchmarkValidationError):
        list(IssueSpaceLoader(root=tmp_path).issue_cases())


def test_loader_on_missing_dir_is_empty(tmp_path):
    assert list(IssueSpaceLoader(root=tmp_path / "없음").issue_cases()) == []


def test_real_cases_if_present():
    """실제 케이스가 들어오면 전부 검증 — 아직 없으면 건너뛴다."""
    loader = IssueSpaceLoader()
    if not loader.paths():
        pytest.skip(f"{ISSUE_SPACE_DIR} 에 케이스가 아직 없다")
    cases = list(loader.issue_cases())
    assert cases
    for c in cases:
        assert c.meta["schema_version"] == SCHEMA_VERSION
        assert c.combination_count == c.meta["combination_count"]
