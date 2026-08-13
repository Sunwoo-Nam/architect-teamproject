"""[24 §4] Time Behaviour — ENV-A 합성 시간 모델.

> **T = phase 수 × t_phase + (효용 평가 호출 수 ÷ N) × t_eval + 총 전송 바이트 ÷ bw**

세 항의 성격이 다르다:

- **phase 항** — `t_phase`는 **편도** 지연이다. phase는 수집·배포·회신 각각 1회이고
  모두 한 방향이다 (24 §4.3). 클라우드 릴레이에서 편도 1회는 업링크 레그 +
  다운링크 레그 2구간이라 75ms다 (24 §4.4-d).
- **eval 항** — `eval_calls`는 전 참여자의 **합**인데 실제로는 각자 자기 단말에서
  동시에 평가하므로 **÷N** 한다 (24 §4.4-a). 이 보정만으로 방안 비교 결론이
  뒤집힌 사례가 있다.
- **transfer 항** — **나누지 않는다.** 담당자 링크를 전원이 공유하므로 병렬이 아니다.

절대값보다 **지배 항(regime)** 이 중요하다 — phase 지배면 결론이 phase 비교와 같고,
transfer 지배면 페이로드가 큰 구조가 불리해진다.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Sequence

from .constants import SYNTH_TIME, SynthTimeConstants
from .contract import SessionResult


@dataclass(frozen=True)
class SynthTime:
    total_ms: float
    phase_ms: float      # 통신 항
    eval_ms: float       # 효용 평가 항 (÷N 보정 후)
    transfer_ms: float   # 페이로드 전송 항

    @property
    def dominant(self) -> str:
        parts = {"phase": self.phase_ms, "eval": self.eval_ms, "transfer": self.transfer_ms}
        return max(parts, key=lambda k: parts[k])

    def as_dict(self) -> dict:
        return {
            "total_ms": round(self.total_ms, 3),
            "phase_ms": round(self.phase_ms, 3),
            "eval_ms": round(self.eval_ms, 6),
            "transfer_ms": round(self.transfer_ms, 3),
            "dominant": self.dominant,
        }


def synth_time(
    session: SessionResult,
    constants: SynthTimeConstants = SYNTH_TIME,
) -> SynthTime:
    phase_ms = session.phases * constants.t_phase_ms
    eval_ms = session.eval_calls / max(1, session.n) * constants.t_eval_ms
    transfer_ms = session.bytes / constants.bw_bytes_per_s * 1000.0
    return SynthTime(phase_ms + eval_ms + transfer_ms, phase_ms, eval_ms, transfer_ms)


def aggregate(
    times: Sequence[SynthTime],
    constants: SynthTimeConstants = SYNTH_TIME,
) -> dict:
    """세션 여러 건의 집계. 중앙값을 쓴다 — 결렬 케이스가 평균을 왜곡하기 때문."""
    if not times:
        raise ValueError("집계할 시간이 없다")
    med_phase = statistics.median(t.phase_ms for t in times)
    med_eval = statistics.median(t.eval_ms for t in times)
    med_transfer = statistics.median(t.transfer_ms for t in times)
    parts = {"phase": med_phase, "eval": med_eval, "transfer": med_transfer}
    return {
        "sessions": len(times),
        "median_total_ms": round(statistics.median(t.total_ms for t in times), 3),
        "median_phase_ms": round(med_phase, 3),
        "median_eval_ms": round(med_eval, 6),
        "median_transfer_ms": round(med_transfer, 3),
        "dominant": max(parts, key=lambda k: parts[k]),
        "constants": constants.as_dict(),
    }
