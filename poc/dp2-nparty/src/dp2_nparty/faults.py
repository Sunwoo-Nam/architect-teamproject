"""장애 주입기 (핸드북 §5-1 FT 측정용) — ENV-A의 일시 오류 모델.

모델 v1 (실험 설계서 고정값):
- 전송 1건마다 확률 p로 유실된다 (Bernoulli). 전송 자체는 발생한 것으로 계측한다
  (라디오 비용은 이미 지불) — 도착만 실패한다.
- 유실된 제출은 다음 라운드에 자동 재시도된다 (순위 포인터가 전진하지 않음).
- 유실된 투표 번들은 그 라운드에서 부재 처리된다 (부재 = O 아님 → 그 라운드 성립 불가 —
  후보는 다음 바퀴 재제출 시 다시 표결된다).
- 일시 이탈(연속 무응답)은 연속 유실로 자연 발생한다 — 별도 이벤트 없음.
"""
from __future__ import annotations

import random


class FaultInjector:
    def __init__(self, p_loss: float, seed: int):
        self.p = p_loss
        self.rng = random.Random(seed)

    def lost(self) -> bool:
        return self.p > 0 and self.rng.random() < self.p
