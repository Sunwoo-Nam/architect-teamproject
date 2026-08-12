"""통신 계측 — [24 §9]의 원자료를 프로토콜 경계에서 센다.

2인(N=2) ENV-A 기준:
- **message** (§9.1): 물리 A2A 전송 건수. 제안 1건 = 상대에게 1건, 수락 통지 1건 = 1건.
- **phase** (§9.3): 직렬 통신 단계 — "상대가 받아야 다음이 진행되는" 단계 1회. 교대
  제안에서 각 제안은 상대의 응답을 기다리므로 제안마다 1 phase. 수락은 기존 제안 phase의
  응답이라 새 phase를 만들지 않는다.
- **bytes** (§9.2): **[이식 시 신설]** 페이로드의 JSON 직렬화 바이트 × 건수.
  원본 dpca에는 바이트 계측이 아예 없었다. 합성 시간(24 §6.4)의 전송 항을 계산하려면
  필요하므로, dp2와 **같은 규약**(`json.dumps(..., ensure_ascii=False)` UTF-8 길이)으로
  신설한다 — 규약이 다르면 두 실험의 바이트를 나란히 볼 수 없다.
- **observations**: **[이식 시 신설]** Confidentiality 측정용 관찰 기록. 누가 무엇을
  언제 보냈고 **누가 볼 수 있는가**를 남긴다. 2인 교대 제안이므로 청중은 항상 상대 1인이다.

seq는 축 세션들이 같은 Comms를 공유해 직렬 깊이가 전 세션에 걸쳐 누적된다
(축 세션이 시간상 직렬이므로 — 핸드북이 '라운드 수 비교 금지'라 한 왜곡을 phase가 흡수).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


def payload_bytes(payload: Any) -> int:
    """dp2 `blackboard.payload_bytes()`와 동일 규약 — 규약이 다르면 비교가 무의미하다."""
    if payload is None:
        return 0
    return len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))


@dataclass
class Comms:
    n_participants: int = 2
    messages: int = 0     # 물리 전송 건수 (§9.1)
    phases: int = 0       # 직렬 통신 단계 수 (§9.3)
    bytes: int = 0        # 페이로드 바이트 (§9.2) — 이식 시 신설
    sweep: int = 1        # 축 세션 번호 (seq는 축마다 증가) — 관찰 순서의 상위 키
    observations: list[dict] = field(default_factory=list)

    @property
    def _fanout(self) -> int:
        return max(1, self.n_participants - 1)

    def _record(self, kind: str, actor: str | None, payload: Any) -> None:
        if actor is None:
            return
        self.observations.append({
            "kind": kind,
            "actor": actor,
            "sweep": self.sweep,
            "round": len(self.observations) + 1,   # 관찰 순서 — 단조 증가
            "outcome": payload,
        })

    def proposal_sent(self, payload: Any = None, actor: str | None = None) -> None:
        """제안 1건 전송 — 상대에게 도착해야 응답 가능하므로 1 message + 1 phase."""
        self.messages += self._fanout
        self.phases += 1
        self.bytes += payload_bytes(payload) * self._fanout
        self._record("submit", actor, payload)

    def accept_sent(self, payload: Any = None, actor: str | None = None) -> None:
        """수락 통지 — 물리 전송 1건이지만 새 직렬 단계는 아니다."""
        self.messages += self._fanout
        self.bytes += payload_bytes(payload) * self._fanout
        self._record("vote", actor, payload)
