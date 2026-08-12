"""Blackboard 상태 + 통신 계측 (핸드북 §9 관측량의 구현).

- 전송 횟수(§9.1): 물리 전송 건수 — 브로드캐스트 1회 = 수신 단말 수. 담당자 로컬 = 0건.
- 전송 크기(§9.2): 건당 페이로드의 JSON 직렬화 바이트 × 건수 (규약 고정 — ensure_ascii=False).
- phase(§9.3): 직렬 통신 단계 — 같은 단계의 병렬 메시지는 1 phase.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .domain import Candidate


def payload_bytes(payload: Any) -> int:
    return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


@dataclass
class MessageCounter:
    total: int = 0
    total_bytes: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)

    def add(self, kind: str, count: int, payload: Any = None) -> None:
        if count <= 0:
            return
        self.total += count
        self.by_kind[kind] = self.by_kind.get(kind, 0) + count
        if payload is not None:
            self.total_bytes += payload_bytes(payload) * count


@dataclass
class Blackboard:
    """공유 상태 — 담당자 단말에 있다고 가정한다."""

    n: int  # 참여자 수
    phases: int = 0
    counter: MessageCounter = field(default_factory=MessageCounter)
    proposed_by: dict[str, set[Candidate]] = field(default_factory=dict)  # 방안 2 누적
    load: dict[str, int] = field(default_factory=dict)  # 노드별 처리 건수 (부하 편중 관측)

    def submit(self, pid: str, is_coordinator: bool, payload: Any) -> None:
        self.counter.add("submit", 0 if is_coordinator else 1, payload)
        self.load[pid] = self.load.get(pid, 0) + 1

    def announce_candidates(self, payload: Any) -> None:  # 방안 1만 — 투표용 배포
        self.counter.add("announce", self.n - 1, payload)

    def vote(self, pid: str, is_coordinator: bool, payload: Any) -> None:  # 방안 1만, 번들 1건
        self.counter.add("vote", 0 if is_coordinator else 1, payload)
        self.load[pid] = self.load.get(pid, 0) + 1

    def round_result(self, payload: Any) -> None:  # 방안 1만
        self.counter.add("round_result", self.n - 1, payload)

    def final_notice(self, payload: Any) -> None:  # 성립/결렬 통지 — 공통 1회
        self.counter.add("final", self.n - 1, payload)

    def resync(self, payload: Any) -> None:  # 복구(REC) 시 상태 재동기화 — 담당자→전원
        self.counter.add("resync", self.n - 1, payload)
        self.phases += 1

    def tie_break_messages(self, count: int, payload: Any = None) -> None:
        self.counter.add("tiebreak", count, payload)
        if count > 0:
            self.phases += 2  # 결선 공지 + 표 회신

    def phase(self) -> None:
        self.phases += 1
