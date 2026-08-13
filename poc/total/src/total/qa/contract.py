"""공통 계약 — 측정기와 실험 도메인의 경계.

`poc/dp2-nparty`와 `poc/dp-composite-agenda`는 도메인이 다르다:

| | dp2-nparty | dp-composite-agenda |
|---|---|---|
| 후보 | 단일 튜플 | 축×값의 곱집합 |
| 선호 | 효용 표 | 진실 프로파일 + soft/hard 규칙 |

측정기가 두 도메인을 모두 알면 공통 라이브러리가 아니다. 그래서 측정기는 **이 파일의
타입에만** 의존하고, 각 실험이 어댑터로 자기 도메인을 여기에 맞춘다.

핵심 설계 두 가지:

1. **가시성은 이벤트가 선언한다** (`ObservationEvent.audience`).
   기존 dp2 `cf_depth._visible_subs()`는 방안별 가시 규칙을 측정기가 알고 있어,
   방안이 늘 때마다 측정기를 고쳐야 했고 dpca 도메인에는 맞지도 않았다.
   "이 메시지를 누가 보는가"는 프로토콜이 아는 사실이므로 프로토콜이 채운다.

2. **후보 열거는 재순회 가능해야 한다** (`Case.candidates()`).
   dpca는 곱집합이라 전수 리스트가 메모리에 안 들어갈 수 있어 generator를 허용하되,
   측정기가 두 번 순회해도 같은 결과를 봐야 하므로 매번 새 iterator를 만든다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Hashable, Iterable, Iterator, Protocol, Sequence, runtime_checkable

# 후보 1건. dp2 = 후보 튜플 / dpca = frozenset((축, 값), ...)
Outcome = Hashable

# 결렬 — 24 §1.3의 "결렬 후보"(전원이 자기 initial threshold를 얻음)와 같은 자리를 가리킨다.
NO_AGREEMENT: str = "__NO_AGREEMENT__"

# 프로토콜이 낼 수 있는 관찰 이벤트 종류. 새 종류는 여기 등록해야 한다 —
# 오타로 만든 kind가 조용히 CF 측정에서 빠지는 것을 막는다.
EVENT_KINDS = frozenset({"submit", "vote", "announce", "notify", "tick"})


@runtime_checkable
class Preference(Protocol):
    """참여자 1인의 선호. 측정기가 선호에 대해 아는 것은 이것뿐이다."""

    pid: str
    initial_threshold: float

    def utility(self, outcome: Outcome) -> float: ...
    def ranked(self) -> list[Outcome]: ...
    def rank_of(self, outcome: Outcome) -> int | None: ...


@dataclass
class TablePreference:
    """표 기반 선호 — Preference의 참조 구현이자 테스트용.

    동률은 후보 표현의 사전순으로 깬다. 시드가 같으면 순위표도 같아야 하기 때문이다
    (dict 순서에 기대면 재현성이 깨진다).
    """

    pid: str
    table: dict[Outcome, float]
    initial_threshold: float
    _ranked: list[Outcome] | None = field(default=None, init=False, repr=False)

    def utility(self, outcome: Outcome) -> float:
        return float(self.table.get(outcome, 0.0))

    def ranked(self) -> list[Outcome]:
        if self._ranked is None:
            self._ranked = sorted(self.table, key=lambda o: (-self.table[o], repr(o)))
        return list(self._ranked)

    def rank_of(self, outcome: Outcome) -> int | None:
        try:
            return self.ranked().index(outcome) + 1
        except ValueError:
            return None


@dataclass(frozen=True)
class ObservationEvent:
    """관찰 가능한 프로토콜 사건 1건.

    `audience`는 이 사건을 **정당하게** 볼 수 있는 pid 목록이다 — 도청이 아니라
    프로토콜이 그 사람에게 보내거나 공개한 것. 행위자 자신은 항상 본다.
    """

    sweep: int
    round: int
    actor: str
    kind: str
    outcome: Outcome | None
    audience: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.kind not in EVENT_KINDS:
            raise ValueError(f"알 수 없는 kind: {self.kind} (등록: {sorted(EVENT_KINDS)})")

    def visible_to(self, observer: str) -> bool:
        return observer == self.actor or observer in self.audience


@dataclass
class SessionResult:
    """협상 1회의 결과와 계측값. 측정기 전체의 입력이다."""

    plan: str
    participants: list[str]
    agreement: Outcome | str  # NO_AGREEMENT면 결렬
    rounds: int
    sweeps: int
    phases: int          # 직렬 통신 단계 — **편도** (24 §4.3)
    messages: int        # 물리 전송 건수 (24 §8.1)
    bytes: int           # 페이로드 바이트 (24 §8.2)
    eval_calls: int      # 효용 평가 호출 수 — 전 참여자 합 (24 §4.4)
    events: list[ObservationEvent] = field(default_factory=list)
    peak_bytes: int = 0  # 협상 구간 tracemalloc 피크 (runner가 채움)
    base_bytes: int = 0  # 공통 기저 — 협상 전 보유분 (nparty: 효용표·순위표 / composite: 축 정의+선호 표현)
    #: 방안이 협상 중 실물화한 후보 구조의 최대 크기 — RU B안 (PL 확정 2026-08-13).
    #: peak_bytes 안에 포함되는 부분의 내역이므로 총점유에 다시 더하지 않는다 (병기 전용)
    materialized_bytes: int = 0
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.participants:
            raise ValueError("participants가 비어 있다")
        for name in ("rounds", "sweeps", "phases", "messages", "bytes",
                     "eval_calls", "peak_bytes", "base_bytes"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name}는 음수일 수 없다: {getattr(self, name)}")

    @property
    def agreed(self) -> bool:
        return self.agreement != NO_AGREEMENT

    @property
    def n(self) -> int:
        return len(self.participants)

    @property
    def total_device_bytes(self) -> int:
        """단말 총 점유 = 공통 기저 + 프로토콜 상태 (24 §2.8 단서)."""
        return self.base_bytes + self.peak_bytes

    def visible_events(self, observer: str) -> list[ObservationEvent]:
        return [e for e in self.events if e.visible_to(observer)]


@dataclass(frozen=True)
class Dataset:
    """측정 입력의 **기준 구성**. 참여자 수·의제 수는 코드가 아니라 여기서 온다.

    `n_issues`는 24 §5.3의 `d`이기도 하다 — 탄력성 c의 별점 하계가 1/d이므로
    데이터셋이 바뀌면 별점 경계도 따라 바뀐다.

    스윕(참여자 3-50, 의제 3-10 등)은 이 기준에서 **변형**되는 것이고, 기준 자체는
    하나다. 스윕 범위는 `note`에 적어 결과만 보고도 무엇을 흔들었는지 알 수 있게 한다.
    """

    name: str
    n_participants: int
    n_issues: int
    issue_value_counts: list[int]
    seed: int
    note: str = ""

    def __post_init__(self) -> None:
        if self.n_participants < 1:
            raise ValueError(f"n_participants는 1 이상: {self.n_participants}")
        if self.n_issues < 1:
            raise ValueError(f"n_issues는 1 이상: {self.n_issues}")
        if len(self.issue_value_counts) != self.n_issues:
            raise ValueError(
                f"issue_value_counts 길이({len(self.issue_value_counts)})가 "
                f"n_issues({self.n_issues})와 다르다"
            )

    @property
    def d(self) -> int:
        """24 §5.3의 의제 수 d — 탄력성 c 별점의 하계 1/d."""
        return self.n_issues

    @property
    def n_candidates(self) -> int:
        return math.prod(self.issue_value_counts)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "n_participants": self.n_participants,
            "n_issues": self.n_issues,
            "issue_value_counts": list(self.issue_value_counts),
            "n_candidates": self.n_candidates,
            "seed": self.seed,
            "note": self.note,
        }


@runtime_checkable
class Case(Protocol):
    """측정 케이스 1건 — 선호 집합과 후보 공간."""

    case_id: str
    preferences: Sequence[Preference]
    n_issues: int

    def candidates(self) -> Iterable[Outcome]: ...


@dataclass
class TableCase:
    """표 기반 케이스 — 후보 공간을 선호 표의 키 합집합으로 본다."""

    case_id: str
    preferences: Sequence[Preference]
    n_issues: int
    meta: dict = field(default_factory=dict)

    def candidates(self) -> Iterator[Outcome]:
        seen: dict[Outcome, None] = {}
        for p in self.preferences:
            for o in p.ranked():
                seen.setdefault(o, None)
        return iter(sorted(seen, key=repr))

    @property
    def pids(self) -> list[str]:
        return [p.pid for p in self.preferences]


@dataclass(frozen=True)
class SweepPoint:
    """SC-의제 스윕의 한 점 — 규모 S에서의 피크와 완결 여부.

    `agreed`는 24 §5.4의 완결률 게이트에 쓴다 — S가 커질 때 빨리 결렬해 버려
    메모리가 적게 나오는 왜곡("많이 실패해서 탄력성이 좋아짐")을 잡기 위함이다.
    """

    scale: int       # 조합 수 S
    peak_bytes: int
    agreed: bool
    n_issues: int
    base_bytes: int = 0   # 공통 기저 — SessionResult와 같은 의미

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError(f"scale은 양수여야 한다: {self.scale}")
        for name in ("peak_bytes", "base_bytes"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name}는 음수일 수 없다: {getattr(self, name)}")

    @property
    def total_bytes(self) -> int:
        """단말 총 점유 = 공통 기저 + 프로토콜 상태 (24 §2.8 단서)."""
        return self.base_bytes + self.peak_bytes
