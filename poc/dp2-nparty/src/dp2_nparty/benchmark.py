"""벤치마크 셋 로더 — 정적 JSON 케이스를 BenchmarkCase로 읽는다.

계약 (data/benchmark/README.md 규격 참조):
- 벤치마크 케이스 1건 = JSON 파일 1개 = 후보 목록 + 참여자별 Profile + 분류 메타데이터
- 로더는 케이스들을 순회 가능하게 제공한다. 하니스는 케이스 단위로 두 방안을 동일 조건 실행한다.

검증은 두 층이다:
- `schema/benchmark-case-v1.schema.json` — 외부 계약(자료형·범위·필수 필드). jsonschema 패키지가
  있을 때만 테스트에서 대조한다.
- 본 모듈의 `validate_case`/`validate_set` — 실행 가능한 계약. JSON Schema로 표현할 수 없는
  교차 필드 규칙(utility key와 candidates 일치, expected_no_deal 계산 일치, family 불변조건 등)까지
  본다. 데이터가 스키마를 만족해도 의미가 틀릴 수 있으므로 이쪽이 실제 게이트다.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from .domain import NO_DEAL, Candidate, Profile

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "benchmark"
FIXTURES_DIR = DATA_DIR / "fixtures"
CASES_DIR = DATA_DIR / "cases"

SCHEMA_VERSION = "benchmark-case.v1"
TRACKS = ("conformance", "functional", "scalability")

# meta의 필수/선택 필드 — schema/benchmark-case-v1.schema.json 과 같은 목록이어야 한다
META_REQUIRED = ("schema_version", "track", "scenario_type", "expected_no_deal", "description")
META_OPTIONAL = ("family_id", "common_feasible_count", "tags")


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    candidates: list[Candidate]
    profiles: list[Profile]
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def track(self) -> str:
        return str(self.meta.get("track", ""))

    @property
    def family_id(self) -> str | None:
        fid = self.meta.get("family_id")
        return str(fid) if fid is not None else None

    def feasible(self) -> list[Candidate]:
        """전원의 initial threshold 이상인 실후보 — 결렬(NO_DEAL)은 포함하지 않는다.

        24 §24.2의 '유효 후보'에서 결렬을 뺀 것이다. 결렬은 항상 유효하므로 데이터 검증에는
        의미가 없고, 여기서 보려는 것은 '합의로 갈 수 있는 실후보가 있는가'다.
        """
        return [
            c for c in self.candidates if all(p.utility(c) >= p.initial_threshold for p in self.profiles)
        ]


class BenchmarkLoader(ABC):
    @abstractmethod
    def cases(self) -> Iterator[BenchmarkCase]: ...


# ---------------------------------------------------------------- 검증


def _is_unit(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and 0.0 <= float(x) <= 1.0


def validate_case(raw: Any, source: str = "<memory>") -> list[str]:
    """케이스 1건의 정합성을 검사하고 오류 메시지 목록을 돌려준다 (빈 목록 = 통과)."""
    e: list[str] = []
    if not isinstance(raw, dict):
        return [f"{source}: 최상위가 object가 아니다"]

    unknown = set(raw) - {"case_id", "candidates", "profiles", "meta"}
    if unknown:
        e.append(f"{source}: 정의되지 않은 최상위 필드 {sorted(unknown)}")

    case_id = raw.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        e.append(f"{source}: case_id 누락 또는 비문자열")

    # 후보 목록
    candidates = raw.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        e.append(f"{source}: candidates 누락 또는 빈 배열")
        candidates = []
    else:
        if not all(isinstance(c, str) and c for c in candidates):
            e.append(f"{source}: candidates 항목은 비어 있지 않은 문자열이어야 한다")
        if len(set(candidates)) != len(candidates):
            e.append(f"{source}: candidates에 중복이 있다")
        if NO_DEAL in candidates:
            e.append(f"{source}: candidates에 예약어 {NO_DEAL} 을 넣을 수 없다")

    # 참여자 프로파일
    profiles = raw.get("profiles")
    if not isinstance(profiles, list) or len(profiles) < 3:
        e.append(f"{source}: profiles는 3명 이상이어야 한다")
        profiles = profiles if isinstance(profiles, list) else []
    pids: list[str] = []
    cand_set = set(candidates)
    for i, p in enumerate(profiles):
        at = f"{source}: profiles[{i}]"
        if not isinstance(p, dict):
            e.append(f"{at} 가 object가 아니다")
            continue
        pid = p.get("pid")
        if not isinstance(pid, str) or not pid:
            e.append(f"{at}.pid 누락 또는 비문자열")
        else:
            pids.append(pid)
        util = p.get("utilities")
        if not isinstance(util, dict):
            e.append(f"{at}.utilities 누락 또는 object가 아니다")
        else:
            if set(util) != cand_set:
                missing = sorted(cand_set - set(util))
                extra = sorted(set(util) - cand_set)
                e.append(f"{at}.utilities 키가 candidates와 다르다 (누락 {missing} / 잉여 {extra})")
            bad = sorted(k for k, v in util.items() if not _is_unit(v))
            if bad:
                e.append(f"{at}.utilities 값이 0-1 범위를 벗어났다: {bad}")
        if not _is_unit(p.get("initial_threshold")):
            e.append(f"{at}.initial_threshold 가 0-1 범위의 수가 아니다")
    if len(set(pids)) != len(pids):
        e.append(f"{source}: pid가 케이스 안에서 중복된다")

    # 메타데이터
    meta = raw.get("meta")
    if not isinstance(meta, dict):
        e.append(f"{source}: meta 누락 또는 object가 아니다")
        return e
    for key in META_REQUIRED:
        if key not in meta:
            e.append(f"{source}: meta.{key} 누락")
    unknown_meta = set(meta) - set(META_REQUIRED) - set(META_OPTIONAL)
    if unknown_meta:
        e.append(f"{source}: 정의되지 않은 meta 필드 {sorted(unknown_meta)}")
    if meta.get("schema_version") != SCHEMA_VERSION:
        e.append(f"{source}: meta.schema_version 은 '{SCHEMA_VERSION}' 이어야 한다")
    if meta.get("track") not in TRACKS:
        e.append(f"{source}: meta.track 은 {list(TRACKS)} 중 하나여야 한다")
    if not isinstance(meta.get("description"), str) or not meta.get("description"):
        e.append(f"{source}: meta.description 은 비어 있지 않은 문자열이어야 한다")

    # 교차 필드 — JSON Schema로 표현할 수 없는 규칙
    if e:  # 구조가 깨진 상태에서 계산 검증을 하면 오류가 번진다
        return e
    profs = [Profile(p["pid"], dict(p["utilities"]), float(p["initial_threshold"])) for p in profiles]
    feasible = [c for c in candidates if all(pr.utility(c) >= pr.initial_threshold for pr in profs)]
    if isinstance(meta.get("expected_no_deal"), bool):
        if meta["expected_no_deal"] != (len(feasible) == 0):
            e.append(
                f"{source}: meta.expected_no_deal={meta['expected_no_deal']} 이지만 "
                f"실제 실후보는 {len(feasible)}개다 {feasible}"
            )
    else:
        e.append(f"{source}: meta.expected_no_deal 은 boolean이어야 한다")
    if "common_feasible_count" in meta:
        if meta["common_feasible_count"] != len(feasible):
            e.append(
                f"{source}: meta.common_feasible_count={meta['common_feasible_count']} 이지만 "
                f"실제 실후보는 {len(feasible)}개다"
            )
    return e


def validate_set(cases: Iterable[BenchmarkCase]) -> list[str]:
    """케이스 집합 전체의 정합성 — 개별 케이스만으로는 볼 수 없는 규칙."""
    e: list[str] = []
    cases = list(cases)

    seen: dict[str, int] = {}
    for c in cases:
        seen[c.case_id] = seen.get(c.case_id, 0) + 1
    for cid, n in sorted(seen.items()):
        if n > 1:
            e.append(f"case_id 중복: {cid} ({n}건)")

    # Scalability family 불변조건.
    #
    # 참여자 수가 늘 때 달라져도 되는 것은 **참여자와 후보의 추가**뿐이다.
    # 기준 시나리오가 3인·후보 12개이므로 1인당 후보 4개 비율을 유지해 후보도 함께 늘리는데,
    # 그래도 다음 세 가지는 고정되어야 참여자 수 외의 조건이 통제된 것이다:
    #   ① 작은 N의 후보 목록이 큰 N의 앞부분과 정확히 일치 (후보는 뒤에만 추가된다)
    #   ② 기존 참여자의 기존 후보에 대한 utility와 수락 기준값이 그대로
    #   ③ 전원이 수락 가능한 후보 수(k)가 N에 무관하게 동일
    families: dict[str, list[BenchmarkCase]] = {}
    for c in cases:
        if c.family_id:
            families.setdefault(c.family_id, []).append(c)
    for fid, members in sorted(families.items()):
        members.sort(key=lambda c: len(c.profiles))
        base = members[0]
        for m in members[1:]:
            if m.candidates[: len(base.candidates)] != base.candidates:
                e.append(
                    f"family {fid}: {m.case_id} 의 후보 목록 앞부분이 {base.case_id} 와 다르다 "
                    "— 후보는 뒤에만 추가되어야 한다"
                )
            if len(m.candidates) < len(base.candidates):
                e.append(f"family {fid}: {m.case_id} 의 후보가 {base.case_id} 보다 적다")
            if len(m.profiles) <= len(base.profiles):
                e.append(f"family {fid}: 참여자 수가 서로 달라야 한다 ({base.case_id}, {m.case_id})")
            for a, b in zip(base.profiles, m.profiles):
                if a.pid != b.pid or a.initial_threshold != b.initial_threshold:
                    e.append(f"family {fid}: 기존 참여자 {a.pid} 가 {m.case_id} 에서 바뀌었다")
                    break
                if any(a.utilities[c] != b.utilities[c] for c in base.candidates):
                    e.append(
                        f"family {fid}: 기존 참여자 {a.pid} 의 기존 후보 utility가 "
                        f"{m.case_id} 에서 바뀌었다"
                    )
                    break
        counts = {m.meta.get("common_feasible_count") for m in members}
        if len(counts) > 1:
            e.append(f"family {fid}: common_feasible_count 가 N에 따라 달라진다 {sorted(counts, key=str)}")
    return e


class BenchmarkValidationError(ValueError):
    """정적 케이스가 계약을 위반했을 때 — 조용히 건너뛰지 않고 실패시킨다."""


# ---------------------------------------------------------------- 로더


def case_from_dict(raw: dict[str, Any], source: str = "<memory>") -> BenchmarkCase:
    errors = validate_case(raw, source)
    if errors:
        raise BenchmarkValidationError("\n".join(errors))
    return BenchmarkCase(
        case_id=raw["case_id"],
        candidates=list(raw["candidates"]),
        profiles=[
            Profile(p["pid"], dict(p["utilities"]), float(p["initial_threshold"]))
            for p in raw["profiles"]
        ],
        meta=dict(raw["meta"]),
    )


def load_case(path: Path) -> BenchmarkCase:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    case = case_from_dict(raw, source=Path(path).name)
    if case.case_id != Path(path).stem:
        raise BenchmarkValidationError(
            f"{path.name}: case_id('{case.case_id}')와 파일명이 다르다 — 추적을 위해 일치시킨다"
        )
    return case


class JsonBenchmarkLoader(BenchmarkLoader):
    """정적 JSON 케이스 로더.

    roots 아래의 모든 *.json을 읽는다. 순회 순서는 case_id 사전순으로 고정한다 —
    실행 순서가 결과에 영향을 주지 않아야 재현이 성립하기 때문이다.
    """

    def __init__(
        self,
        roots: Iterable[Path] | Path | None = None,
        track: str | None = None,
        validate: bool = True,
    ):
        if roots is None:
            roots = [FIXTURES_DIR, CASES_DIR]
        elif isinstance(roots, Path):
            roots = [roots]
        self.roots = [Path(r) for r in roots]
        self.track = track
        self.validate = validate

    def paths(self) -> list[Path]:
        found: list[Path] = []
        for root in self.roots:
            if root.exists():
                found.extend(sorted(root.rglob("*.json")))
        return found

    def cases(self) -> Iterator[BenchmarkCase]:
        loaded = [load_case(p) for p in self.paths()]
        if self.track is not None:
            loaded = [c for c in loaded if c.track == self.track]
        loaded.sort(key=lambda c: c.case_id)
        if self.validate:
            errors = validate_set(loaded)
            if errors:
                raise BenchmarkValidationError("\n".join(errors))
        yield from loaded


class NotReadyLoader(BenchmarkLoader):
    """자리 표시 — 지정한 트랙의 케이스가 아직 없을 때."""

    def cases(self) -> Iterator[BenchmarkCase]:
        raise NotImplementedError(
            f"벤치마크 셋이 아직 없다 — {DATA_DIR} 에 데이터가 오면 JsonBenchmarkLoader 를 쓴다."
        )
