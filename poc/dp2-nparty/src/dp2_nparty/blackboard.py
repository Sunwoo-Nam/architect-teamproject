"""Blackboard 상태 + 메시지 카운터.

메시지는 25번 정의대로 '물리 전송 건수'로 센다 (README의 매핑 v1).
담당자(coordinator) = 참여자 0번. 담당자 자신의 제출·투표는 로컬이라 0건.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .domain import Candidate


@dataclass
class MessageCounter:
    total: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)

    def add(self, kind: str, count: int) -> None:
        if count <= 0:
            return
        self.total += count
        self.by_kind[kind] = self.by_kind.get(kind, 0) + count


@dataclass
class Blackboard:
    """공유 상태 — 담당자 단말에 있다고 가정한다."""

    n: int  # 참여자 수
    phases: int = 0  # 직렬 통신 단계 수 — Time Behaviour의 ENV-A 대체 지표 (단계 수 × 왕복 지연 ≈ 시간)
    counter: MessageCounter = field(default_factory=MessageCounter)
    # 방안 2용: 참여자별 누적 제안 집합
    proposed_by: dict[str, set[Candidate]] = field(default_factory=dict)
    # 노드별 처리 건수 (보조 관측 — 부하 편중 추세)
    load: dict[str, int] = field(default_factory=dict)

    def submit(self, pid: str, is_coordinator: bool) -> None:
        self.counter.add("submit", 0 if is_coordinator else 1)
        self.load[pid] = self.load.get(pid, 0) + 1

    def announce_candidates(self) -> None:  # 방안 1만 — 투표를 위해 배포 필요
        self.counter.add("announce", self.n - 1)

    def vote(self, pid: str, is_coordinator: bool) -> None:  # 방안 1만 — 라운드당 번들 1건
        self.counter.add("vote", 0 if is_coordinator else 1)
        self.load[pid] = self.load.get(pid, 0) + 1

    def round_result(self) -> None:  # 방안 1만
        self.counter.add("round_result", self.n - 1)

    def final_notice(self) -> None:  # 성립/결렬 통지 — 두 방안 공통, 1회
        self.counter.add("final", self.n - 1)

    def tie_break_messages(self, count: int) -> None:
        self.counter.add("tiebreak", count)
        if count > 0:
            self.phases += 2  # 결선 공지 + 표 회신

    def phase(self) -> None:
        self.phases += 1
