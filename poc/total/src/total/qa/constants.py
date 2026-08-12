"""측정 상수와 별점 밴드 — [`24-QA-측정-핸드북`](../../../../../docs/changbae/24-QA-측정-핸드북.md) 동기화 지점.

상수를 코드 여기저기에 흩어 두면 "어느 값으로 잰 결과인지"를 잃는다. 전부 여기 모으고
각 값이 24의 어느 절에서 왔는지를 함께 적는다. 리포트는 이 객체를 그대로 직렬화해
결과 파일에 남긴다 — 나중에 결과만 보고도 어느 상수로 잰 것인지 알 수 있어야 한다.
"""
from __future__ import annotations

from dataclasses import dataclass

from .bands import Band, even_bands_between, fraction_bands

# --------------------------------------------------------------------------------------
# Time Behaviour — 24 §6.4
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SynthTimeConstants:
    """합성 시간 모델 T = phase×t_phase + (eval÷N)×t_eval + bytes÷bw.

    t_phase는 **편도**다. 구 이름 `t_rtt`("왕복")는 실체와 달라 값 해석을 오도했다
    — phase는 수집·배포·회신 각각 1회로 모두 한 방향이다 (24 §6.3).
    """

    t_phase_ms: float = 75.0            # 24 §6.4-d — LTE 클라우드 릴레이 구간 분해
    t_eval_ms: float = 0.003            # 24 §6.4-b — PoC 실측 1.394µs → 3µs
    bw_bytes_per_s: float = 2_500_000.0  # 24 §6.4-c — LTE 20 Mbps

    @property
    def bdp_bytes(self) -> float:
        """대역폭-지연 곱. 24 §6.4-c가 방안 우열을 가르는 양으로 지목했다."""
        return self.t_phase_ms / 1000.0 * self.bw_bytes_per_s

    def as_dict(self) -> dict:
        return {
            "t_phase_ms": self.t_phase_ms,
            "t_eval_ms": self.t_eval_ms,
            "bw_bytes_per_s": self.bw_bytes_per_s,
            "bdp_bytes": self.bdp_bytes,
            "note": "24 §6.4 — t_phase는 편도. LTE 클라우드 릴레이 기준",
        }


SYNTH_TIME = SynthTimeConstants()

# --------------------------------------------------------------------------------------
# Functional Correctness — 24 §1. 지표 2개를 병행한다.
# --------------------------------------------------------------------------------------

BAND_FC_S = Band(
    name="FC 개선 비율 s",
    thresholds=[0.8, 0.6, 0.4, 0.2, 0.0],
    direction="greater_than",
    note="24 §1.4 — s = (달성률 − R̄) ÷ (1 − R̄). 무작위 베이스라인 대비 개선. 경계 제외(strict >)",
)

BAND_FC_ACHIEVED = Band(
    name="FC 달성률",
    thresholds=[0.95, 0.90, 0.85, 0.80, 0.70],
    direction="at_least",
    note="절대 달성률 U(r)÷U(x*) 밴드. 24는 s를 정본으로 두나, 베이스라인에 무관한 "
         "절대 수준도 함께 보기 위해 병행한다 (사용자 지시 2026-08-12)",
)

# --------------------------------------------------------------------------------------
# Confidentiality — 24 §7.3
# --------------------------------------------------------------------------------------

BAND_CF_M = Band(
    name="CF 노출 배수 m",
    thresholds=[0.25, 0.5, 1.0, 2.0, 4.0],
    direction="at_most",
    note="24 §7.3 — 3점 경계(m=1)가 1:1 협상 등가. **잠정 사다리**(PL 조율 예정)이므로 "
         "별점만 보지 말고 m·깊이·노출률 원지표를 함께 읽어야 한다",
)

# --------------------------------------------------------------------------------------
# Scalability-의제 — 24 §4. 지표 2개를 병행한다.
# --------------------------------------------------------------------------------------


def band_sc_elasticity(d: int) -> Band:
    """탄력성 c의 별점 밴드 — 24 §4.3.

    전체 열거(c=1)와 순차 좁히기의 이론 이상값(c=1/d) 사이를 5등분한다.
    **d는 데이터셋의 의제 수다** — 24 §4.3이 "d가 바뀌면 하계 1/d와 구간 폭을 갱신한다"
    고 명시했으므로 상수로 굳히지 않고 매번 계산한다.
    """
    if d < 2:
        raise ValueError(f"d는 2 이상이어야 한다 (1/d가 1 미만이어야 등분 구간이 생긴다): {d}")
    return Band(
        name=f"SC-의제 탄력성 c (d={d})",
        thresholds=even_bands_between(1.0 / d, 1.0),
        direction="at_most",
        note=f"24 §4.3 — 이론 이상 1/d={1.0 / d:.3f} 와 전체 열거 1.0 사이 5등분",
    )


BAND_SC_MAX_ISSUES = Band(
    name="SC-의제 최대 의제 수",
    thresholds=[30, 20, 14, 10, 6],
    direction="at_least",
    note="메모리 한도 안에서 처리 가능한 최대 의제(축) 수. 탄력성 c가 구조 특성이라면 "
         "이쪽은 수용 한계 — 두 지표를 병행한다 (사용자 지시 2026-08-12)",
)

# --------------------------------------------------------------------------------------
# Resource Utilization-메모리 — 24 §2.8
# --------------------------------------------------------------------------------------

#: 협상 몫 한도. ART 힙 상한(`ActivityManager.getMemoryClass()`)의 전형값 256MB를 쓴다.
#: 24 §2.8이 요구하는 "런타임에 협상 기능이 쓸 수 있는 가용 메모리"의 자리이며,
#: 넘으면 `OutOfMemoryError`로 확실히 죽는 하드 리밋이라 결정론적이다.
#: ENV-B 실측이 오면 교체한다 — 실험에서 override 가능.
RU_CEILING_BYTES = 256 * 1024 * 1024

#: 한도 대비 사용률의 등분 폭. 24 §2.8은 15%p로 5구간을 잡고 초과분(>75%)을 0점으로 둔다
#: — 동시 부하·관측 오차를 감안한 여유다. step=0.2면 한도 전체를 5등분한 것이 된다.
RU_STEP = 0.15


def band_ru_usage(step: float = RU_STEP) -> Band:
    """사용률 r = 피크 ÷ 한도의 별점 밴드 — 24 §2.8."""
    return Band(
        name="RU 사용률 r",
        thresholds=fraction_bands(step),
        direction="at_most",
        note=f"24 §2.8 — r = 피크 ÷ 한도, {step:.0%}p 등분. 한도 초과는 0점",
    )
