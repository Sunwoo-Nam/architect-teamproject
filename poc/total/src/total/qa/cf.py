r"""[24 §3] Confidentiality — 역추론 방지.

> **정의 (2026-08-13 개정, PL 확정)**: 제안한 설계가 **일반적인 2인(1:1) 협상보다
> 얼마나 더 내 선호를 노출하는가.** 2인 협상에서 상대가 내 제안 이력을 아는 것은
> **협상의 정의이지 실패가 아니다** — 그래서 참조 2인 협상을 기준선으로 삼고 설계가
> 만드는 과잉 노출만 잰다. 다자 도메인에서는 관찰자가 N−1명이라 생기는 과잉을,
> 2인 고정 도메인에서는 "무엇을 통째로 주고받는가"라는 설계 선택의 과잉을 같은 자로 잰다.

지표는 3층이다:

1. **판정 — 노출 배수 m** = Σ(전 관찰자의 노출 깊이 e) ÷ e₂ (피해자 1인 기준)
2. **병기** — 최대 단일 관찰자 깊이(집중도) · 정규화 노출률(1순위, 하위 호환)
3. **원재료** — 역추론 정확도 (2의 계산 입력)

깊이 e = **순위표 노출 비율**: 귀속 노출된 고유 후보 수 ÷ 유효 후보 수. 공격자와
무관한 정보론적 상한이다 — 공개된 것 이상은 어떤 공격자도 알 수 없다.

> 구 B축(접두 복원 깊이 — 공격자가 순서까지 복원한 최대 접두)은 2026-08-13 개정으로
> 제거했다 (24 §3.3 개정 기록). "라운드 = 순위" 제출 규칙(51 §2) 아래에서는 B가 A와
> 항상 일치하고, 복합 의제 도메인에서는 분모가 퇴화해 어느 쪽에서도 별도 정보가 없다.

**기존 구현 대비 가장 큰 변화**: dp2 `confidentiality._visible_events()`는 방안 12종의
if-else 체인으로 "이 방안에서 누가 무엇을 보는가"를 측정기가 알고 있었다. 방안이 늘
때마다 측정기를 고쳐야 했고 다른 도메인에는 맞지도 않았다. 여기서는
`ObservationEvent.audience`만 본다 — 가시성은 프로토콜이 아는 사실이므로 프로토콜이 채운다.

**e₂ 앵커는 도메인별로 따로 잰다.** 후보 공간·유효 후보 수가 도메인마다 달라 남의 e₂를
쓰면 분모가 맞지 않는다. 분모가 측정 대상이 아니라 **참조 프로토콜**이므로, 2인 고정
도메인에서도 m이 상수가 되지 않고 "이 설계가 평범한 양자 협상보다 더 새는가"를 잰다.
참조를 바꾸면 m 전체가 바뀌므로 실험이 명시하고 봉인한다 (24 §3.5).

**별점 사다리는 잠정이다** (24 §3.3, PL 조율 예정). 그래서 별점만 내지 않고
m·깊이·노출률 원지표를 항상 함께 보고한다.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Callable, Sequence

from .constants import BAND_CF_M
from .contract import Case, Outcome, Preference, SessionResult

#: 관찰 1건 — (바퀴, 라운드, 후보)
Sub = tuple[int, int, Outcome]


# --------------------------------------------------------------------------------------
# 관점 (viewpoint)
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Viewpoint:
    """관찰자를 고르는 규칙. 도메인마다 담당자 개념이 다르므로 실험이 선언한다."""

    name: str
    pick: Callable[[SessionResult], str]


#: 담당자 관점 — 첫 참여자를 담당자로 보는 관례 (dp2 계열).
COORDINATOR_FIRST = Viewpoint("coordinator", lambda s: s.participants[0])


def worst_participant(coordinator_index: int = 0) -> Viewpoint:
    """일반 참여자 관점 — 담당자를 뺀 참여자 중 **가장 많이 보는** 사람.

    24 §3.5의 "비루트 최악 관찰자" 규칙. 평균이 아니라 최악을 잡는 보수적 측정이다.
    """

    def pick(s: SessionResult) -> str:
        others = [p for i, p in enumerate(s.participants) if i != coordinator_index]
        if not others:
            return s.participants[coordinator_index]
        return max(others, key=lambda pid: (len(s.visible_events(pid)), pid))

    return Viewpoint("participant", pick)


# --------------------------------------------------------------------------------------
# 노출 깊이
# --------------------------------------------------------------------------------------


def valid_ranked(case: Case, victim: Preference) -> list[Outcome]:
    """피해자의 **유효 후보만** 담은 순위표.

    깊이의 분모를 전체 공간으로 잡으면 안 된다 — 피해자가 애초에 제안하지 않을
    (바닥선 미달·실현 불가) 후보가 분모를 부풀려 깊이가 과소평가된다.
    분모(d_v)는 피해자가 실제로 드러낼 수 있는 집합의 크기여야 한다.
    """
    ranked = victim.ranked()
    valid = {o for o in case.candidates() if victim.utility(o) >= victim.initial_threshold}
    return [o for o in ranked if o in valid]


def valid_count(case: Case, victim: Preference) -> int:
    """피해자의 유효 후보 수 d_v — 깊이의 분모. 0이 되지 않게 최소 1."""
    return max(1, len(valid_ranked(case, victim)))


def observed_subs(session: SessionResult, observer: str, victim: str) -> list[Sub]:
    """관찰자가 **귀속으로** 본 피해자의 제출들. (바퀴, 라운드) 오름차순, 중복은 최초만.

    익명 재배포는 actor가 담당자라 피해자에게 귀속되지 않는다 — 그래서 잡히지 않는다.
    이것이 방안 1-A의 "참여자 관점 노출 0"이 나오는 이유이고, 측정기가 방안을 몰라도
    자동으로 그렇게 되는 지점이다.
    """
    rows = [
        (e.sweep, e.round, e.outcome)
        for e in session.events
        if e.kind == "submit" and e.actor == victim and e.outcome is not None
        and e.visible_to(observer)
    ]
    rows.sort(key=lambda r: (r[0], r[1], repr(r[2])))
    seen: set[Outcome] = set()
    out: list[Sub] = []
    for row in rows:
        if row[2] not in seen:
            seen.add(row[2])
            out.append(row)
    return out


def depth(subs: Sequence[Sub], d_v: int) -> float:
    """노출 깊이 e — 귀속 노출된 고유 후보 수 ÷ 유효 후보 수 (순위표 노출 비율)."""
    if d_v <= 0:
        return 0.0
    return min(1.0, len({o for _s, _r, o in subs}) / d_v)


# --------------------------------------------------------------------------------------
# 공격자 (24 §3.4 — 고정·봉인)
# --------------------------------------------------------------------------------------


def estimate_top1(session: SessionResult, observer: str, victim: str) -> Outcome | None:
    """고정 공격자 규칙 (frequency 계열, 24 §3.4).

    ① 피해자의 제안이 보이면 → 가장 이른 (바퀴, 라운드)의 제안을 1순위로 추정
    ② 제안이 안 보이면 → 가장 이른 바퀴에 승인(vote)한 후보 중 사전순 첫 번째
    ③ 아무 신호도 없으면 → None (호출 측이 무작위 추측 1/M으로 처리)

    **공격자를 바꾸면 대안 간·시점 간 비교가 무너진다** — 변경 시 전 측정 재실행.
    """
    subs = observed_subs(session, observer, victim)
    if subs:
        return subs[0][2]

    approvals = [
        (e.sweep, repr(e.outcome), e.outcome)
        for e in session.events
        if e.kind == "vote" and e.actor == victim and e.outcome is not None
        and e.visible_to(observer)
    ]
    if approvals:
        return min(approvals)[2]
    return None


@dataclass(frozen=True)
class InferenceGain:
    """1순위 역추론 — 구 판정 지표. 지금은 병기(하위 호환)다."""

    accuracy: float
    random_baseline: float
    gain_pp: float
    exposure_rate: float
    stars: int
    samples: int

    def as_dict(self) -> dict:
        return {
            "accuracy": round(self.accuracy, 4),
            "random_baseline": round(self.random_baseline, 4),
            "gain_pp": round(self.gain_pp, 2),
            "exposure_rate": round(self.exposure_rate, 4),
            "stars": self.stars,
            "samples": self.samples,
        }


def _exposure_stars(rate: float) -> int:
    """구 척도 — 정규화 노출률 0-1의 6등분 (24 §3.3 표)."""
    for stars, hi in ((5, 1 / 6), (4, 2 / 6), (3, 3 / 6), (2, 4 / 6), (1, 5 / 6)):
        if rate <= hi:
            return stars
    return 0


def inference_gain(
    runs: Sequence[tuple[SessionResult, Case]],
    viewpoint: Viewpoint,
) -> InferenceGain:
    """관점별 1순위 역추론 정확도 → 이득 → 정규화 노출률."""
    if not runs:
        raise ValueError("측정할 세션이 없다")

    hits = 0.0
    baselines: list[float] = []
    total = 0
    for session, case in runs:
        observer = viewpoint.pick(session)
        by_pid = {p.pid: p for p in case.preferences}
        m = max(1, sum(1 for _ in case.candidates()))
        for victim_pid, victim in by_pid.items():
            if victim_pid == observer:
                continue
            total += 1
            baselines.append(1.0 / m)
            guess = estimate_top1(session, observer, victim_pid)
            if guess is None:
                hits += 1.0 / m          # 무작위 추측의 기대 적중
            elif victim.ranked() and guess == victim.ranked()[0]:
                hits += 1.0

    if total == 0:
        raise ValueError("관찰자를 뺀 피해자가 없다")

    accuracy = hits / total
    baseline = statistics.fmean(baselines)
    max_gain = 1.0 - baseline
    gain = accuracy - baseline
    rate = 0.0 if max_gain <= 0 else max(0.0, gain / max_gain)
    return InferenceGain(accuracy, baseline, gain * 100.0, rate,
                         _exposure_stars(rate), total)


# --------------------------------------------------------------------------------------
# e₂ 앵커와 노출 배수 m
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class E2Anchor:
    depth: float
    samples: int

    @property
    def degenerate(self) -> bool:
        """앵커가 사실상 0 — m의 분모가 무의미하다는 신호. 조용히 넘기면 안 된다."""
        return self.depth <= 1e-6

    def as_dict(self) -> dict:
        return {
            "depth": round(self.depth, 6),
            "samples": self.samples,
            "degenerate": self.degenerate,
            "note": "1:1 기준 노출량 — 참조 2인 협상에서 상대 1인이 도달하는 깊이. "
                    "m의 분모이며 도메인별로 따로 측정한다",
        }


def e2_anchor(runs: Sequence[tuple[SessionResult, Case]]) -> E2Anchor:
    """참조 양자(2인) 세션에서 상대 1인의 노출 깊이 중앙값.

    m의 분모라 0이면 안 된다 — 하한을 둔다.
    """
    if not runs:
        raise ValueError("앵커를 잴 세션이 없다")
    vals = []
    for session, case in runs:
        if session.n < 2:
            raise ValueError(f"e₂ 앵커는 2인 이상 세션이 필요하다: n={session.n}")
        observer, victim_pid = session.participants[0], session.participants[1]
        by_pid = {p.pid: p for p in case.preferences}
        victim = by_pid[victim_pid]
        d = valid_count(case, victim)
        subs = observed_subs(session, observer, victim_pid)
        vals.append(depth(subs, d))
    return E2Anchor(
        depth=max(1e-9, statistics.median(vals)),
        samples=len(vals),
    )


@dataclass(frozen=True)
class ExposureMultiple:
    m: float | None            # 앵커가 퇴화하면 None — 가짜 수를 내지 않는다
    stars_m: int | None
    max_single_depth: float
    victims: int
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "m": None if self.m is None else round(self.m, 3),
            "stars_m": self.stars_m,
            "max_single_depth": round(self.max_single_depth, 3),
            "victims": self.victims,
            "note": self.note,
            "band": BAND_CF_M.as_dict(),
        }


def exposure_multiple(
    runs: Sequence[tuple[SessionResult, Case]],
    anchor: E2Anchor,
) -> ExposureMultiple:
    """피해자별 노출 배수 m과 최대 단일 관찰자 깊이."""
    if not runs:
        raise ValueError("측정할 세션이 없다")
    multiples, single = [], []
    for session, case in runs:
        by_pid = {p.pid: p for p in case.preferences}
        for victim_pid in session.participants:
            victim = by_pid.get(victim_pid)
            if victim is None:
                continue
            d = valid_count(case, victim)
            total = best = 0.0
            for observer in session.participants:
                if observer == victim_pid:
                    continue
                e = depth(observed_subs(session, observer, victim_pid), d)
                total += e
                best = max(best, e)
            multiples.append(total / anchor.depth)
            single.append(best)

    if anchor.degenerate:
        # 앵커가 0에 가까우면 비율이 의미를 잃는다. 큰 수를 내놓으면 오독을 부르므로
        # None으로 비우고 사유를 남긴다 — "안 쟀다"와 "0이다"는 다르다.
        return ExposureMultiple(
            m=None, stars_m=None,
            max_single_depth=statistics.median(single), victims=len(multiples),
            note="e₂ 앵커가 0에 가까워 배수가 성립하지 않는다 — 참조 2인 협상에서 "
                 "귀속 노출이 관측되지 않았다는 뜻이므로 원지표(깊이)로 직접 비교할 것",
        )
    med = statistics.median(multiples)
    return ExposureMultiple(
        m=med, stars_m=BAND_CF_M.stars(med),
        max_single_depth=statistics.median(single), victims=len(multiples),
    )


def evaluate(
    runs: Sequence[tuple[SessionResult, Case]],
    anchor: E2Anchor,
    viewpoints: Sequence[Viewpoint],
) -> dict:
    """판정(m) + 관점별 병기 + e₂ 출처를 한 번에.

    **별점만 남기지 않는다** — 사다리가 잠정이라 원지표를 항상 함께 낸다.
    """
    return {
        "multiple": exposure_multiple(runs, anchor).as_dict(),
        "viewpoints": {vp.name: inference_gain(runs, vp).as_dict() for vp in viewpoints},
        "e2": anchor.as_dict(),
        "attacker": "frequency 고정 규칙 3개 (24 §3.4) — 변경 시 전 측정 재실행",
    }
