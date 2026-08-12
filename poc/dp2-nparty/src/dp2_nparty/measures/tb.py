"""[핸드북 §6] Time Behaviour — ENV-A 합성 시간 모델.

T(ms) = phases × t_phase + (eval_calls ÷ N) × t_eval + bytes ÷ bw

**평가 항의 ÷N 병렬 보정 (2026-08-12 개정)**: eval_calls는 전 참여자의 평가 횟수 합인데,
실제로는 참여자가 각자 자기 단말에서 동시에 평가한다. 이전 모델은 이를 직렬 합산해
N대가 나눠 하는 일을 1대가 순차로 하는 것처럼 계상했다. §6.3이 통신에 대해 이미
"전원 동시 제출 = 1 phase"로 병렬을 인정하므로, 평가에도 같은 원칙을 적용한다.
(임계 경로는 엄밀히는 참여자별 최댓값이지만, 참여자들이 거의 동일한 작업을 하므로
합÷N으로 근사한다.) 전송 항은 담당자 링크를 공유하므로 나누지 않는다.

상수 3개는 **잠정값** — ENV-B 실측으로 대체하는 자리다:
- t_phase_ms: **phase 1회 지연 (편도)** — LTE 클라우드 릴레이 기준 **75ms** (아래 참조)
- t_eval_ms: 후보 1건 순위표 구축 (**PoC 실측 기반 0.003ms**, 아래 참조)
- bw_bytes_per_s: 전송 대역 (**LTE 기준 20 Mbps = 2,500,000 B/s** — PL 결정 2026-08-12)

**개명 (2026-08-12): t_rtt_ms → t_phase_ms.** 구 이름은 "왕복(round trip)"을 뜻했으나
이 상수가 곱해지는 phase는 **편도**다 — `blackboard.phase()`는 논리 단계 1회마다
호출되고, 각 단계는 한 방향이다(수집=참여자→담당자, 배포=담당자→전원, 회신=전원→담당자).
이름과 실체의 불일치가 실제로 값 해석을 오도했으므로 바로잡는다. 구 raw.json은
`t_rtt_ms` 키를 갖고 있어 `phase_latency_ms()`가 양쪽을 모두 읽는다.

**t_phase 개정 (2026-08-12, 50ms → 75ms) — 클라우드 릴레이 구간 분해.**
전송 구조가 **클라우드 릴레이로 확정**되었다(PL 확인 2026-08-12): 모바일 간 P2P
연결이 불가해 메시지 서버를 클라우드에 두고 그곳을 경유한다. 따라서 편도 1회가
무선 1구간이 아니라 **업링크 레그 + 다운링크 레그 2구간**이다.

  참여자 폰 --[LTE UL]--> eNB --[백홀·인터넷]--> 클라우드 메시지 서버
  담당자 폰 <--[LTE DL]-- eNB <--[백홀·인터넷]--+

중앙값은 **독립된 두 방식으로 유도하고 교차 검산**한다:

(a) 상향식 — 구간 합:
  | 구간                          | 중앙값 | 근거                              |
  | LTE 업링크 RAN (UE→eNB)       |  30ms  | 실망 측정 중앙값 (하한 10ms)      |
  | 백홀+인터넷 (eNB→DC, 리전 내) |  10ms  | 분석자 추정                       |
  | 서버 처리·라우팅·팬아웃       |   5ms  | 분석자 추정                       |
  | 인터넷+백홀 (DC→eNB)          |  10ms  | 분석자 추정                       |
  | LTE 다운링크 RAN (eNB→UE)     |  15ms  | 분석자 추정 (SR/grant 절차 없음)  |
  | 합계                          | **70ms** |                                 |

(b) 하향식 — 앵커: 릴레이 편도(A→서버→B)는 업링크 레그와 다운링크 레그의 합인데,
  **폰↔서버 ping RTT도 같은 두 레그의 합**이다. 따라서 t_phase ≈ ping RTT + 서버 처리.
  공개 측정 LTE RTT 통상 50-100ms의 중앙 75ms + 서버 처리 5ms = **80ms**.

(a) 70ms · (b) 80ms → **채택 75ms** (두 값의 중앙). 구값 50ms는 통상 범위의 하단이었고,
"근거리 무선 왕복"이라는 P2P 전제에서 나온 값이라 릴레이 구조와 맞지 않았다.

**t_phase·bw는 짝으로 바꾼다.** 따로 두면 실재하지 않는 망이 만들어진다 — 개정 전
조합(50ms · 1 Mbps)은 "셀룰러급 지연 + BLE급 대역"이라 어떤 실제 망에도 대응하지
않았고, 하필 그 조합에서만 방안 비교 결론이 뒤집혔다. 승패를 가르는 것은 두 상수의
곱(대역폭-지연 곱, BDP)이다. t_phase 상향은 BDP를 키우므로 phase가 적은 방안이
더 유리해지는 방향이다 — 결론을 뒤집지 않고 강화한다.

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

DEFAULT_CONSTANTS = {"t_phase_ms": 75.0, "t_eval_ms": 0.003, "bw_bytes_per_s": 2_500_000.0}


def phase_latency_ms(constants: dict) -> float:
    """phase 1회 편도 지연 — 신 키 t_phase_ms, 구 raw.json은 t_rtt_ms (양쪽 호환)."""
    v = constants.get("t_phase_ms")
    return float(v) if v is not None else float(constants.get("t_rtt_ms", 0.0))


@dataclass(frozen=True)
class SynthTime:
    total_ms: float
    rtt_ms: float  # 통신 항 (phase × t_phase) — 필드명은 구 raw.json 호환 유지
    eval_ms: float  # 효용 평가(추론) 항
    transfer_ms: float  # 페이로드 전송 항

    @property
    def dominant(self) -> str:
        parts = {"rtt": self.rtt_ms, "eval": self.eval_ms, "transfer": self.transfer_ms}
        return max(parts, key=parts.get)


def synth_time(session: SessionResult, constants: dict | None = None) -> SynthTime:
    c = {**DEFAULT_CONSTANTS, **(constants or {})}
    rtt = session.phases * phase_latency_ms(c)
    # ÷N 병렬 보정 (모듈 docstring 참조). n=0은 구 raw.json 호환 — 보정 없이 구 동작.
    ev = session.eval_calls / (session.n or 1) * c["t_eval_ms"]
    tr = session.bytes / c["bw_bytes_per_s"] * 1000.0
    return SynthTime(rtt + ev + tr, rtt, ev, tr)
