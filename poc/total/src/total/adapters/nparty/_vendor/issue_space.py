"""의제 조합 케이스 — 조합을 펼치지 않고 의제별 점수만 저장하는 형식의 로더·검증기.

왜 별도 형식인가. 기존 `benchmark-case.v1`은 후보마다 utility를 하나씩 적어 둔다.
실제 문제는 날짜 × 시간 × 영화관 × 영화의 조합이라 후보가 수천~수만 개이고, 그걸 전부
JSON에 펼치면 케이스 하나가 수 MB가 된다 (조합 10만 · 참여자 10명이면 100만 개 값).

그래서 **의제별 점수만 저장하고 조합은 읽을 때 계산한다**:

    utility(조합) = Σ_j 가중치[의제_j] × 점수[의제_j][값_j]

파일 크기가 `참여자 수 × 의제별 값 개수의 합`이라 조합 수와 무관하다 — 조합이 10만 개여도
파일은 수 KB다. 가중치 합이 1이고 점수가 0-1이므로 utility도 0-1이 보장된다.

`expand()`가 이것을 기존 `BenchmarkCase`로 전개하므로, 프로토콜·측정기는 손대지 않아도 된다.

규격: data/benchmark/schema/issue-space-case-v1.schema.json
"""
from __future__ import annotations

import itertools
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .benchmark import CASES_DIR, BenchmarkCase, BenchmarkLoader, BenchmarkValidationError
from .domain import Profile

SCHEMA_VERSION = "issue-space-case.v1"
ISSUE_SPACE_DIR = CASES_DIR / "issue-space"

META_REQUIRED = (
    "schema_version", "track", "scenario_type", "combination_count",
    "issue_sizes", "common_feasible_count", "expected_no_deal", "description",
)
META_OPTIONAL = ("tags",)
WEIGHT_TOL = 1e-9


@dataclass(frozen=True)
class IssueSpaceCase:
    case_id: str
    issues: list[dict[str, Any]]  # [{"id":..., "name":..., "values":[...]}]
    participants: list[dict[str, Any]]  # 원시 dict — pid/initial_threshold/weights/scores
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def issue_ids(self) -> list[str]:
        return [i["id"] for i in self.issues]

    @property
    def issue_values(self) -> list[list[str]]:
        return [list(i["values"]) for i in self.issues]

    @property
    def combination_count(self) -> int:
        n = 1
        for vs in self.issue_values:
            n *= len(vs)
        return n


# ---------------------------------------------------------------- utility 계산


def _contrib_table(participant: dict, issues: list[dict]) -> list[dict[str, float]]:
    """의제별 `가중치 × 점수` 를 미리 곱해 둔다 — 조합마다 다시 곱하지 않기 위해."""
    w, sc = participant["weights"], participant["scores"]
    return [{v: w[i["id"]] * sc[i["id"]][v] for v in i["values"]} for i in issues]


def utility_of(participant: dict, combo: tuple, issues: list[dict]) -> float:
    """조합 하나의 utility. 조합은 의제 순서대로의 값 튜플."""
    w, sc = participant["weights"], participant["scores"]
    return sum(w[i["id"]] * sc[i["id"]][v] for i, v in zip(issues, combo))


def _utilities_in_product_order(participant: dict, issues: list[dict]) -> list[float]:
    """전 조합의 utility를 itertools.product 와 같은 순서로 한 번에 만든다.

    의제를 하나씩 더해 가며 누적한다 — 조합마다 의제 수만큼 곱셈하는 대신
    덧셈만 하게 되어 큰 공간에서 눈에 띄게 빠르다.
    """
    contrib = _contrib_table(participant, issues)
    acc = [0.0]
    for i, table in zip(issues, contrib):
        vals = [table[v] for v in i["values"]]
        acc = [a + b for a in acc for b in vals]  # 마지막 의제가 가장 빨리 변한다 = product 순서
    return acc


def all_combinations(case: IssueSpaceCase) -> list[tuple]:
    return list(itertools.product(*case.issue_values))


def feasible_count(case: IssueSpaceCase) -> int:
    """모든 참여자가 수락 가능한(각자 initial_threshold 이상) 조합의 수."""
    cols = [_utilities_in_product_order(p, case.issues) for p in case.participants]
    ths = [float(p["initial_threshold"]) for p in case.participants]
    return sum(
        1 for vals in zip(*cols) if all(u >= t for u, t in zip(vals, ths))
    )


def expand(case: IssueSpaceCase) -> BenchmarkCase:
    """조합을 전개해 기존 BenchmarkCase 로 만든다 — 프로토콜·측정기가 그대로 쓴다."""
    combos = all_combinations(case)
    profiles = [
        Profile(
            pid=p["pid"],
            utilities=dict(zip(combos, _utilities_in_product_order(p, case.issues))),
            initial_threshold=float(p["initial_threshold"]),
        )
        for p in case.participants
    ]
    return BenchmarkCase(
        case_id=case.case_id, candidates=combos, profiles=profiles, meta=dict(case.meta)
    )


# ---------------------------------------------------------------- 검증


def _is_unit(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and 0.0 <= float(x) <= 1.0


def validate_issue_case(raw: Any, source: str = "<memory>") -> list[str]:
    """케이스 1건의 정합성을 검사하고 오류 메시지 목록을 돌려준다 (빈 목록 = 통과)."""
    e: list[str] = []
    if not isinstance(raw, dict):
        return [f"{source}: 최상위가 object가 아니다"]

    unknown = set(raw) - {"case_id", "issues", "participants", "meta"}
    if unknown:
        e.append(f"{source}: 정의되지 않은 최상위 필드 {sorted(unknown)}")
    if not isinstance(raw.get("case_id"), str) or not raw.get("case_id"):
        e.append(f"{source}: case_id 누락 또는 비문자열")

    # 의제
    issues = raw.get("issues")
    if not isinstance(issues, list) or not issues:
        return e + [f"{source}: issues 누락 또는 빈 배열"]
    ids: list[str] = []
    for k, i in enumerate(issues):
        at = f"{source}: issues[{k}]"
        if not isinstance(i, dict):
            e.append(f"{at} 가 object가 아니다")
            continue
        iid = i.get("id")
        if not isinstance(iid, str) or not iid:
            e.append(f"{at}.id 누락 또는 비문자열")
        else:
            ids.append(iid)
        vs = i.get("values")
        if not isinstance(vs, list) or not vs:
            e.append(f"{at}.values 누락 또는 빈 배열")
        elif len(set(vs)) != len(vs):
            e.append(f"{at}.values 에 중복이 있다")
        elif not all(isinstance(v, str) and v for v in vs):
            e.append(f"{at}.values 항목은 비어 있지 않은 문자열이어야 한다")
    if len(set(ids)) != len(ids):
        e.append(f"{source}: 의제 id가 중복된다")
    if e:
        return e
    id_set = set(ids)

    # 참여자
    parts = raw.get("participants")
    if not isinstance(parts, list) or len(parts) < 3:
        e.append(f"{source}: participants 는 3명 이상이어야 한다")
        parts = parts if isinstance(parts, list) else []
    pids: list[str] = []
    for k, p in enumerate(parts):
        at = f"{source}: participants[{k}]"
        if not isinstance(p, dict):
            e.append(f"{at} 가 object가 아니다")
            continue
        pid = p.get("pid")
        if not isinstance(pid, str) or not pid:
            e.append(f"{at}.pid 누락 또는 비문자열")
        else:
            pids.append(pid)
        if not _is_unit(p.get("initial_threshold")):
            e.append(f"{at}.initial_threshold 가 0-1 범위의 수가 아니다")

        w = p.get("weights")
        if not isinstance(w, dict):
            e.append(f"{at}.weights 누락 또는 object가 아니다")
        elif set(w) != id_set:
            e.append(f"{at}.weights 키가 의제 id와 다르다 (기대 {sorted(id_set)}, 실제 {sorted(w)})")
        elif not all(_is_unit(v) for v in w.values()):
            e.append(f"{at}.weights 값이 0-1 범위를 벗어났다")
        elif abs(sum(w.values()) - 1.0) > WEIGHT_TOL:
            e.append(f"{at}.weights 합이 1이 아니다 ({sum(w.values())!r})")

        sc = p.get("scores")
        if not isinstance(sc, dict):
            e.append(f"{at}.scores 누락 또는 object가 아니다")
        elif set(sc) != id_set:
            e.append(f"{at}.scores 키가 의제 id와 다르다 (기대 {sorted(id_set)}, 실제 {sorted(sc)})")
        else:
            for i in issues:
                tab = sc.get(i["id"])
                if not isinstance(tab, dict):
                    e.append(f"{at}.scores.{i['id']} 가 object가 아니다")
                    continue
                if set(tab) != set(i["values"]):
                    e.append(
                        f"{at}.scores.{i['id']} 의 키가 그 의제의 values와 다르다 "
                        f"(누락 {sorted(set(i['values']) - set(tab))} / 잉여 {sorted(set(tab) - set(i['values']))})"
                    )
                elif not all(_is_unit(v) for v in tab.values()):
                    e.append(f"{at}.scores.{i['id']} 값이 0-1 범위를 벗어났다")
    if len(set(pids)) != len(pids):
        e.append(f"{source}: pid가 케이스 안에서 중복된다")

    # 메타
    meta = raw.get("meta")
    if not isinstance(meta, dict):
        return e + [f"{source}: meta 누락 또는 object가 아니다"]
    for key in META_REQUIRED:
        if key not in meta:
            e.append(f"{source}: meta.{key} 누락")
    unknown_meta = set(meta) - set(META_REQUIRED) - set(META_OPTIONAL)
    if unknown_meta:
        e.append(f"{source}: 정의되지 않은 meta 필드 {sorted(unknown_meta)}")
    if meta.get("schema_version") != SCHEMA_VERSION:
        e.append(f"{source}: meta.schema_version 은 '{SCHEMA_VERSION}' 이어야 한다")
    if meta.get("track") != "issue_space":
        e.append(f"{source}: meta.track 은 'issue_space' 여야 한다")
    if e:  # 구조가 깨진 상태에서 계산 검증을 하면 오류가 번진다
        return e

    # 교차 검산 — 기록된 값이 실제 계산과 맞는지
    case = IssueSpaceCase(raw["case_id"], list(issues), list(parts), dict(meta))
    sizes = [len(i["values"]) for i in issues]
    if list(meta.get("issue_sizes", [])) != sizes:
        e.append(f"{source}: meta.issue_sizes={meta.get('issue_sizes')} 이지만 실제는 {sizes}")
    if meta.get("combination_count") != case.combination_count:
        e.append(
            f"{source}: meta.combination_count={meta.get('combination_count')} 이지만 "
            f"실제 조합 수는 {case.combination_count}"
        )
    actual = feasible_count(case)
    if meta.get("common_feasible_count") != actual:
        e.append(
            f"{source}: meta.common_feasible_count={meta.get('common_feasible_count')} 이지만 "
            f"실제는 {actual}"
        )
    if not isinstance(meta.get("expected_no_deal"), bool):
        e.append(f"{source}: meta.expected_no_deal 은 boolean이어야 한다")
    elif meta["expected_no_deal"] != (actual == 0):
        e.append(
            f"{source}: meta.expected_no_deal={meta['expected_no_deal']} 이지만 "
            f"실제 실후보는 {actual}개다"
        )
    return e


def case_from_dict(raw: dict[str, Any], source: str = "<memory>") -> IssueSpaceCase:
    errors = validate_issue_case(raw, source)
    if errors:
        raise BenchmarkValidationError("\n".join(errors))
    return IssueSpaceCase(
        case_id=raw["case_id"],
        issues=list(raw["issues"]),
        participants=list(raw["participants"]),
        meta=dict(raw["meta"]),
    )


def load_issue_case(path: Path) -> IssueSpaceCase:
    path = Path(path)
    case = case_from_dict(json.loads(path.read_text(encoding="utf-8")), source=path.name)
    if case.case_id != path.stem:
        raise BenchmarkValidationError(
            f"{path.name}: case_id('{case.case_id}')와 파일명이 다르다 — 추적을 위해 일치시킨다"
        )
    return case


class IssueSpaceLoader(BenchmarkLoader):
    """의제 조합 케이스 로더.

    `cases()`는 전개된 BenchmarkCase 를 낸다 (기존 하니스가 그대로 쓸 수 있게).
    `issue_cases()`는 전개 전 원본을 낸다 (의제 구조를 봐야 할 때).
    순회 순서는 case_id 사전순으로 고정한다 — 실행 순서가 결과에 영향을 주지 않아야 하므로.
    """

    def __init__(self, root: Path | None = None, validate: bool = True):
        self.root = Path(root) if root is not None else ISSUE_SPACE_DIR
        self.validate = validate

    def paths(self) -> list[Path]:
        return sorted(self.root.rglob("*.json")) if self.root.exists() else []

    def issue_cases(self) -> Iterator[IssueSpaceCase]:
        loaded = [load_issue_case(p) for p in self.paths()]
        loaded.sort(key=lambda c: c.case_id)
        yield from loaded

    def cases(self) -> Iterator[BenchmarkCase]:
        for c in self.issue_cases():
            yield expand(c)
