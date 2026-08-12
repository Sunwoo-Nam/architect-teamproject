"""[핸드북 §6] Time Behaviour — ENV-A 합성 시간 모델.

T(ms) = phases × t_rtt + (eval_calls ÷ N) × t_eval + bytes ÷ bw

**평가 항의 ÷N 병렬 보정 (2026-08-12 개정)**: eval_calls는 전 참여자의 평가 횟수 합인데,
실제로는 참여자가 각자 자기 단말에서 동시에 평가한다. 이전 모델은 이를 직렬 합산해
N대가 나눠 하는 일을 1대가 순차로 하는 것처럼 계상했다. §6.3이 통신에 대해 이미
"전원 동시 제출 = 1 phase"로 병렬을 인정하므로, 평가에도 같은 원칙을 적용한다.
(임계 경로는 엄밀히는 참여자별 최댓값이지만, 참여자들이 거의 동일한 작업을 하므로
합÷N으로 근사한다.) 전송 항은 담당자 링크를 공유하므로 나누지 않는다.

상수 3개는 **잠정값** — ENV-B 실측으로 대체하는 자리다:
- t_rtt_ms: 네트워크 왕복 1회 (**LTE 기준 50ms** — PL 결정 2026-08-12, 아래 참조)
- t_eval_ms: 후보 1건 순위표 구축 (**PoC 실측 기반 0.003ms**, 아래 참조)
- bw_bytes_per_s: 전송 대역 (**LTE 기준 20 Mbps = 2,500,000 B/s** — PL 결정 2026-08-12)

**t_rtt·bw 개정 (2026-08-12, bw 125,000 → 2,500,000 B/s)**: 두 상수는 **짝으로** 정해야
한다 — 따로 두면 실재하지 않는 망이 만들어진다. 개정 전 조합(50ms · 1 Mbps)은
"셀룰러급 지연 + BLE급 대역"이라 어떤 실제 망에도 대응하지 않았고, 하필 그 조합에서만
방안 비교 결론이 뒤집혔다. 대상 망을 **LTE로 확정**(PL 결정 2026-08-12, BLE는 대상 외)하고
t_rtt=50ms · bw=20 Mbps로 맞춘다 — 공개 측정치의 LTE 범위(RTT 50-100ms, 실효 대역
10-50 Mbps) 안이다. 승패를 가르는 것은 두 상수의 곱(대역폭-지연 곱, BDP)이므로,
상수를 바꿀 때는 반드시 쌍으로 바꾼다.

**t_eval 개정 (2026-08-12, 20ms → 0.003ms)**: 20ms는 "조합 1건마다 온디바이스 추론"
가정이었으나, 조합 효용은 의제별 기여값의 **덧셈**으로 유도된다(issue_space
`_utilities_in_product_order`). 선호 정보는 의제값 개수(10의제 케이스에서 31개)로
완결되고 조합 62,208개는 산술의 산물이다 — 즉 산술에 추론 가격을 매기고 있었다.
검산: 62,208 × 20ms = 20.7분(1인 순위표 구축만) — 제품으로 성립하지 않는다.
PoC 실측은 1건 1.394µs(효용 산술 0.080 + 순위 정렬 1.314)이고, 실기기 여유를 두어
**3µs로 반올림**했다(PL 결정 2026-08-12). ENV-A 실측 기반이므로 다른 두 상수와
출처가 다르다. LLM 선호 도출 비용(의제값당 1회)은 이 항에 포함되지 않는다 —
방안과 무관해 비교에서 상쇄되지만, 절대 시간을 말할 때는 별도로 더해야 한다.

절대값은 상수가 잠정인 동안 의미가 없다 — 용도는 ① 방안 간 상대 비교,
② 지배 항(regime) 파악: RTT 지배면 phase 비교와 동일 결론, 평가 지배면
투표마다 전 후보를 재평가하는 구조가 불리해진다.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..domain import SessionResult

DEFAULT_CONSTANTS = {"t_rtt_ms": 50.0, "t_eval_ms": 0.003, "bw_bytes_per_s": 2_500_000.0}


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
    # ÷N 병렬 보정 (모듈 docstring 참조). n=0은 구 raw.json 호환 — 보정 없이 구 동작.
    ev = session.eval_calls / (session.n or 1) * c["t_eval_ms"]
    tr = session.bytes / c["bw_bytes_per_s"] * 1000.0
    return SynthTime(rtt + ev + tr, rtt, ev, tr)
