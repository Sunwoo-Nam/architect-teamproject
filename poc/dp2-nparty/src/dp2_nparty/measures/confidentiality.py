"""[21 §21.3-9] Confidentiality — 역추론 이득. ★ 공격자 구현 자리.

계약 (21번 확정 사항):
- 공격자 = NegMAS frequency 계열 상대 모델 (`FrequencyUFunModel`) 고정·봉인
- 관점 = 참여자 관찰자 — 자기에게 보이는 것만 입력:
  방안 1: 라운드 후보 공지 + O/X 결과 / 방안 2: (담당자만) 누적 제안, 일반 참여자는 자기 것만
- 지표 = 1순위 후보 추정 정확도 − 무작위 기준선(1/후보수) = 이득(%p)

구현 TODO: SessionResult.log 의 관찰 이벤트를 공격자 입력으로 넘기는 어댑터.
벤치마크 셋(프로파일 정답)이 와야 정확도 채점이 가능하므로, 데이터 도착 후 채운다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InferenceGain:
    accuracy: float  # 공격자 1순위 적중률
    random_baseline: float  # 1 / 후보 수
    gain_pp: float  # (accuracy - baseline) × 100


def measure_gain(*_args, **_kwargs) -> InferenceGain:
    raise NotImplementedError(
        "frequency 공격자 미구현 — 벤치마크 셋 도착 후 negmas FrequencyUFunModel 연동 예정"
    )
