"""[핸드북 §5-2] Recoverability — 복구 시간 비율 (ENV-A 대체: phase 비용).

ENV-A에는 벽시계가 없으므로 시간을 phase(직렬 통신 단계)로 대체한다:
- 복구 비용 = (중단 세션의 총 phase) − (동일 조건 무중단 세션의 총 phase)
  — 중단으로 버려진 단계 + 상태 재동기화(resync) 단계가 자연히 포함된다.
- 정상 라운드 1회 시간 = 무중단 세션의 (총 phase ÷ 라운드 수).
- 비율 = 복구 비용 ÷ 라운드 1회 phase. 별점 앵커: 1(한 라운드)-R(재시작 비용 = 무중단
  세션의 총 라운드 수), 로그 등분.

FR 판정: 복구 세션의 최종 결과가 무중단 기준 실행과 동일해야 한다 — 다르면 재개 실패
(결함)로 보고하고 지표 집계에서 제외한다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RecTrial:
    point: str
    round_no: int
    fr_ok: bool  # 결과 동일성 (재개 + 상태 일치)
    ratio: float | None  # 복구 phase 비용 ÷ 라운드 1회 phase (fr_ok일 때만)


def stars_rec(ratio: float, restart_cost: float) -> int:
    """별점 — 1 이하 5점, 1-R 로그 4등분, R 초과 0점."""
    if ratio <= 1.0:
        return 5
    if restart_cost <= 1.0 or ratio > restart_cost:
        return 0
    frac = math.log(ratio) / math.log(restart_cost)  # (0, 1]
    return max(1, 5 - math.ceil(frac * 4))


def trial(plan_cls, profiles, point: str, round_no: int, **plan_kw) -> RecTrial:
    ref = plan_cls(profiles, **plan_kw).run()
    from ..protocol import KillAt

    killed = plan_cls(profiles, **plan_kw).run(kill_at=KillAt(round_no, point))
    fr_ok = killed.outcome == ref.outcome
    if not fr_ok or ref.rounds == 0:
        return RecTrial(point, round_no, fr_ok, None)
    round_phase = ref.phases / ref.rounds
    recovery_cost = killed.phases - ref.phases
    if recovery_cost <= 0:  # 중단 지점이 실행 경로에 없었음 (라운드 수 부족) — 무효 시도
        return RecTrial(point, round_no, True, None)
    return RecTrial(point, round_no, True, recovery_cost / round_phase)
