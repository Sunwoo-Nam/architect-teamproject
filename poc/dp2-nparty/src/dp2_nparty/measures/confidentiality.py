"""[21 §21.3-9] Confidentiality — 역추론 이득 측정.

공격자: frequency 계열 상대 모델(빈도 기반 opponent modeling) — 관찰된 제안·수락/거절
신호의 빈도·시점으로 상대의 선호 상위 후보를 추정하는, 자동 협상 분야의 표준 기법.

구현 주석 (정직하게): 21번은 negmas `FrequencyUFunModel`을 지정했으나, 그 클래스는
NegMAS의 SAO/GB 메커니즘 콜백에 결합되어 있어 자체 프로토콜(51)에는 직접 꽂을 수 없다.
여기서는 **동일 원리(빈도·시점 기반 추정)를 관찰 이벤트 위에 재구현**하고, 공격자
규칙을 아래에 고정·명문화한다 — "공격자 고정·봉인" 요구는 이 명문화로 충족한다.

관점(viewpoint) — 각자가 정당하게 볼 수 있는 것만 입력으로 준다:
- participant (일반 참여자 관찰자):
  방안 1 → 라운드 후보 공지(제안자 포함)와 공개된 O/X 결과를 본다.
  방안 2 → 참여자 간 배포가 없어 남의 제안·의견을 전혀 보지 못한다.
- coordinator (Blackboard 담당자):
  두 방안 모두 전체 제출을 본다. 방안 1은 O/X까지 본다.

지표 (21 확정): 1순위 후보 추정 정확도 − 무작위 기준선(1/후보 수) = 이득(%p).
공격자가 아무 정보도 없으면 무작위 추측의 기대 정확도(1/M)로 계산한다.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..domain import Profile, SessionResult


@dataclass(frozen=True)
class InferenceGain:
    accuracy: float  # 공격자 1순위 적중률 (기대값 포함)
    random_baseline: float  # 1 / 후보 수
    gain_pp: float  # (accuracy - baseline) × 100


def _visible_events(session: SessionResult, observer: str, coordinator: str) -> list[dict]:
    """관점별 가시 이벤트 필터."""
    if session.plan == "plan1" or observer == coordinator:
        return session.log  # 방안 1은 공지·결과 공개로 전원이 봄 / 담당자는 항상 전부 봄
    # 방안 2·3-A의 일반 참여자: 배포가 없어 자기 제출만 보인다
    out = []
    for ev in session.log:
        if ev["t"] in ("round", "batch"):
            mine = {p: c for p, c in ev["submitted"].items() if p == observer}
            out.append({**ev, "submitted": mine})
    return out


def estimate_top(victim: str, events: list[dict]) -> object | None:
    """고정 공격자 규칙 (frequency 계열):
    1) 피해자의 제안이 보이면 — 가장 이른 (sweep, k)의 제안 = 1순위 추정.
       (빈도 모델의 '이른/잦은 제안 = 높은 선호' 원리. 본 프로토콜은 라운드=순위라 특히 강력)
    2) 제안이 안 보이면 — 피해자가 가장 이른 sweep에 O를 준 후보 중 사전순 첫 번째.
    3) 아무 신호도 없으면 None (무작위 추측 처리).
    """
    proposals = []  # (sweep, 순번, candidate)
    for ev in events:
        if ev["t"] == "round" and victim in ev["submitted"]:
            proposals.append((ev["sweep"], ev["k"], ev["submitted"][victim]))
        elif ev["t"] == "batch" and victim in ev["submitted"]:
            for rank, cand in ev["submitted"][victim]:
                proposals.append((ev["sweep"], rank, cand))  # 배치의 rank가 곧 순위
    if proposals:
        return min(proposals)[2]
    approvals = []  # (sweep, candidate)
    for ev in events:
        if ev["t"] == "votes" and victim in ev["votes"]:
            for c, ok in ev["votes"][victim].items():
                if ok:
                    approvals.append((ev["sweep"], repr(c), c))
    if approvals:
        return min(approvals)[2]
    return None


def measure_gain(
    runs: list[tuple[SessionResult, list[Profile]]],
    n_candidates: int,
    viewpoint: str = "participant",
) -> InferenceGain:
    """세션들에 대해 관찰자가 다른 참여자 전원의 1순위를 추정한 평균 정확도와 이득.

    viewpoint: "participant"(비담당 관찰자 P1) 또는 "coordinator"(담당자 P0).
    """
    baseline = 1.0 / n_candidates
    total, score = 0, 0.0
    for session, profiles in runs:
        coordinator = profiles[0].pid
        observer = coordinator if viewpoint == "coordinator" else profiles[1].pid
        events = _visible_events(session, observer, coordinator)
        for p in profiles:
            if p.pid == observer:
                continue
            guess = estimate_top(p.pid, events)
            truth = p.ranked()[0]
            total += 1
            score += (1.0 if guess == truth else 0.0) if guess is not None else baseline
    acc = score / total if total else baseline
    return InferenceGain(acc, baseline, (acc - baseline) * 100.0)


def exposure_rate(gain: InferenceGain, n_candidates: int) -> float:
    """29 §29.2 — 정규화 노출률 = 이득 ÷ 최대 이득(1 − 1/M)."""
    max_gain = (1.0 - 1.0 / n_candidates) * 100.0
    return max(0.0, gain.gain_pp / max_gain) if max_gain > 0 else 0.0


def stars_exposure(rate: float) -> int:
    """29 §29.3 — 유계 [0,1]을 6등분: 5점 ≤ 1/6 … 0점 > 5/6."""
    import math as _m

    return max(0, 5 - _m.floor(min(rate, 0.9999) * 6))
