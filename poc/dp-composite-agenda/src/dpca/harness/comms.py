"""통신 계측 — 29-1 핸드북 B1(phase)·C1(메시지 횟수)의 원자료를 프로토콜 경계에서 센다.

2인(N=2) ENV-A 기준:
- message: 물리 A2A 전송 건수. 제안 1건 = 상대에게 1건, 수락 통지 1건 = 1건.
  (N명이면 브로드캐스트 1회 = N-1건이지만 본 PoC는 2인이라 항상 1건.)
- phase: 직렬 통신 단계 — "상대가 받아야 다음이 진행되는" 단계 1회. 교대 제안에서
  각 제안은 상대의 응답을 기다리므로 제안마다 1 phase. 수락은 기존 제안 phase의
  응답이라 새 phase를 만들지 않는다.

seq는 축 세션들이 같은 Comms를 공유해 직렬 깊이가 전 세션에 걸쳐 누적된다
(축 세션이 시간상 직렬이므로 — 핸드북이 '라운드 수 비교 금지'라 한 왜곡을 phase가 흡수).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Comms:
    n_participants: int = 2
    messages: int = 0     # 물리 전송 건수 (C1)
    phases: int = 0       # 직렬 통신 단계 수 (B1 ENV-A / C3)

    @property
    def _fanout(self) -> int:
        return max(1, self.n_participants - 1)

    def proposal_sent(self) -> None:
        """제안 1건 전송 — 상대에게 도착해야 응답 가능하므로 1 message + 1 phase."""
        self.messages += self._fanout
        self.phases += 1

    def accept_sent(self) -> None:
        """수락 통지 — 물리 전송 1건이지만 새 직렬 단계는 아니다."""
        self.messages += self._fanout
