"""정적 벤치마크 케이스의 정합성 검증 — data/benchmark/README.md 의 '정합성 검증' 목록.

여기서 보는 것은 **데이터가 계약을 지키는가**이지, 프로토콜이 옳게 도는가가 아니다.
프로토콜 동작의 기대 결과는 test_benchmark_conformance.py 가 맡는다.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dp2_nparty.benchmark import (
    DATA_DIR,
    FIXTURES_DIR,
    SCHEMA_VERSION,
    BenchmarkValidationError,
    JsonBenchmarkLoader,
    case_from_dict,
    validate_case,
    validate_set,
)

SCHEMA_PATH = DATA_DIR / "schema" / "benchmark-case-v1.schema.json"


def all_cases():
    return list(JsonBenchmarkLoader().cases())


def test_fixtures_exist():
    paths = JsonBenchmarkLoader().paths()
    assert paths, f"{DATA_DIR} 아래에 케이스 JSON이 하나도 없다"


def test_every_case_loads_and_validates():
    """개별 케이스 검증 — 로더가 통과시키면 계약을 지킨 것이다."""
    cases = all_cases()
    assert cases
    for c in cases:
        assert c.meta["schema_version"] == SCHEMA_VERSION
        assert len(c.profiles) >= 3
        for p in c.profiles:
            assert set(p.utilities) == set(c.candidates)


def test_case_set_invariants():
    """집합 수준 검증 — case_id 유일성, family 불변조건."""
    assert validate_set(all_cases()) == []


def test_case_id_matches_filename():
    for path in JsonBenchmarkLoader().paths():
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["case_id"] == path.stem, f"{path.name}: case_id와 파일명이 다르다"


def test_expected_no_deal_matches_computation():
    """meta.expected_no_deal 은 채점기에 주는 정답이 아니라 데이터 오류 검출용 분류표다."""
    for c in all_cases():
        assert c.meta["expected_no_deal"] == (len(c.feasible()) == 0), c.case_id


def test_track_directory_agrees_with_meta():
    """fixtures/ 는 conformance 전용 — 통계 표본과 섞이면 안 된다 (계획서 §2)."""
    for path in JsonBenchmarkLoader().paths():
        raw = json.loads(path.read_text(encoding="utf-8"))
        in_fixtures = FIXTURES_DIR in path.parents
        if in_fixtures:
            assert raw["meta"]["track"] == "conformance", f"{path.name}: fixtures/ 인데 track이 다르다"
        else:
            assert raw["meta"]["track"] != "conformance", f"{path.name}: conformance는 fixtures/ 로 간다"


def test_loader_order_is_deterministic():
    """같은 입력이면 같은 순서 — 재현성의 전제."""
    a = [c.case_id for c in JsonBenchmarkLoader().cases()]
    b = [c.case_id for c in JsonBenchmarkLoader().cases()]
    assert a == b == sorted(a)


def test_track_filter():
    conformance = list(JsonBenchmarkLoader(track="conformance").cases())
    assert conformance
    assert all(c.track == "conformance" for c in conformance)


# ---------------------------------------------------------------- 검증기 자체의 검증


def _valid_raw():
    return {
        "case_id": "T-000-sample",
        "candidates": ["A", "B"],
        "profiles": [
            {"pid": f"P{i}", "utilities": {"A": 0.9, "B": 0.5}, "initial_threshold": 0.4}
            for i in range(3)
        ],
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "track": "conformance",
            "scenario_type": "sample",
            "expected_no_deal": False,
            "description": "검증기 테스트용 표본",
        },
    }


def test_validator_accepts_valid_case():
    assert validate_case(_valid_raw()) == []


@pytest.mark.parametrize(
    "mutate, expect",
    [
        (lambda r: r["profiles"].pop(), "3명 이상"),
        (lambda r: r["candidates"].append("A"), "중복"),
        (lambda r: r["candidates"].append("NO_DEAL"), "예약어"),
        (lambda r: r["profiles"][0]["utilities"].pop("B"), "candidates와 다르다"),
        (lambda r: r["profiles"][0]["utilities"].update({"A": 1.5}), "0-1 범위"),
        (lambda r: r["profiles"][1].update({"pid": "P0"}), "중복"),
        (lambda r: r["meta"].update({"track": "unknown"}), "track"),
        (lambda r: r["meta"].update({"schema_version": "v2"}), "schema_version"),
        (lambda r: r["meta"].update({"expected_no_deal": True}), "expected_no_deal"),
        (lambda r: r["meta"].update({"common_feasible_count": 99}), "common_feasible_count"),
        (lambda r: r["meta"].update({"typo_field": 1}), "정의되지 않은 meta"),
    ],
)
def test_validator_rejects_broken_case(mutate, expect):
    raw = _valid_raw()
    mutate(raw)
    errors = validate_case(raw)
    assert errors, f"검출되어야 할 오류가 통과했다 ({expect})"
    assert any(expect in msg for msg in errors), f"{expect} 가 오류 메시지에 없다: {errors}"


def test_case_from_dict_raises_on_invalid():
    raw = _valid_raw()
    raw["profiles"][0]["initial_threshold"] = 2.0
    with pytest.raises(BenchmarkValidationError):
        case_from_dict(raw)


# ---------------------------------------------------------------- JSON Schema 대조 (선택)


def test_cases_conform_to_json_schema():
    """외부 계약(schema/*.json)과의 대조 — jsonschema 미설치 환경에서는 건너뛴다.

    본 저장소의 실제 게이트는 benchmark.validate_case 다. 이 테스트는 스키마 파일이
    구현과 어긋나지 않았는지 확인하는 보조 장치다.
    """
    jsonschema = pytest.importorskip("jsonschema", reason="jsonschema 미설치 — 선택 검증")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    for path in JsonBenchmarkLoader().paths():
        jsonschema.validate(json.loads(path.read_text(encoding="utf-8")), schema)
