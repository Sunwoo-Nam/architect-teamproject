"""[핸드북 §6] Time Behaviour — ENV-A 합성 시간 모델.

T(ms) = phases × t_rtt + eval_calls × t_eval + bytes ÷ bw

상수 3개는 **잠정값(분석자 제안)** — ENV-B 실측으로 대체하는 자리다:
- t_rtt_ms: 네트워크 왕복 1회 (근거리 무선 왕복 잠정 50ms)
- t_eval_ms: 후보 1건 효용 평가 1회 (온디바이스 추론 잠정 20ms — 테이블 조회면 훨씬 작음)
- bw_bytes_per_s: 전송 대역 (1 Mbps 급 잠정 125,000 B/s)

절대값은 상수가 잠정인 동안 의미가 없다 — 용도는 ① 방안 간 상대 비교,
② 지배 항(regime) 파악: RTT 지배면 phase 비교와 동일 결론, 평가 지배면
투표마다 전 후보를 재평가하는 구조가 불리해진다.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..domain import SessionResult

DEFAULT_CONSTANTS = {"t_rtt_ms": 50.0, "t_eval_ms": 20.0, "bw_bytes_per_s": 125_000.0}


@dataclass(frozen=True)
class SynthTime:
    total_ms: float
    rtt_ms: float  # 통신 왕복 항
    eval_ms: float  # 효용 평가(추론) 항
    transfer_ms: float  # 페이로드 전송 항

    @property
    def dominant(self) -> str:
        parts = {"rtt": self.rtt_ms, "eval": self.eval_ms, "transfer": self.transfer_ms}
        return max(parts, key=parts.get)


def synth_time(session: SessionResult, constants: dict | None = None) -> SynthTime:
    c = {**DEFAULT_CONSTANTS, **(constants or {})}
    rtt = session.phases * c["t_rtt_ms"]
    ev = session.eval_calls * c["t_eval_ms"]
    tr = session.bytes / c["bw_bytes_per_s"] * 1000.0
    return SynthTime(rtt + ev + tr, rtt, ev, tr)
