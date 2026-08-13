"""nparty 어댑터 — dp2-nparty 도메인(방안 1-A vs 방안 2)을 공통 계약으로 옮긴다.

**도메인 지식은 여기서 끝난다.** 특히 "이 방안에서 누가 무엇을 보는가"는 프로토콜이
아는 사실이므로 여기서 `ObservationEvent.audience`로 선언하고, 측정기는 방안 이름조차
모른다. 기존 dp2 `confidentiality._visible_events()`의 12종 if-else 체인이 이 몇 줄로
대체된 자리다.

프로토콜 구현은 `_vendor/`에 원본 그대로 두었다 — 재작성하면 수치 차이가 이식 버그인지
재작성 차이인지 가릴 수 없기 때문이다 (`_vendor/__init__.py` 참조).

## 가시성 규칙 (51 §3-1·§4)

| 이벤트 | 방안 1-A | 방안 2 |
|---|---|---|
| 제출 (참여자→담당자) | 담당자만 | 담당자만 |
| 배포 (담당자→전원) | **익명 목록** — actor가 담당자라 원제안자 귀속 없음 | 없음 |
| 투표 O/X | 담당자만 (결과 공지 없음) | 없음 |
| 라운드 진행 신호 | 배포가 겸함 | 담당자→전원 (tick) |
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Sequence

from ...qa.contract import NO_AGREEMENT, ObservationEvent, Outcome, SessionResult
from ...qa.ru import deep_size, measure_peak
from ._vendor.domain import NO_DEAL, Profile
from ._vendor.protocol import Plan2Cumulative
from ._vendor.protocol_styles import Plan1aSao
from ._vendor.measures.ru_person import holder_sizes


@dataclass(frozen=True)
class PlanSpec:
    name: str
    label: str
    cls: type


#: 비교 대상 — 51 §3-1(방안 1-A)과 §4(방안 2). 다른 방안은 이번 비교 범위 밖이다.
PLANS: dict[str, PlanSpec] = {
    "plan1a": PlanSpec("plan1a", "방안 1-A 순차 SAO 투표형", Plan1aSao),
    "plan2": PlanSpec("plan2", "방안 2 누적 공통제안형", Plan2Cumulative),
}

# 방안 2 보완 택틱 (62번 문서 — PL 지시 2026-08-13). 순환 회피를 위해 지연 등록.
from .tactics import TACTIC_SPECS  # noqa: E402

for _name, _label, _cls in TACTIC_SPECS:
    PLANS[_name] = PlanSpec(_name, _label, _cls)


class NpartyPreference:
    """원본 `Profile`을 계약 `Preference`로 감싼다.

    원본 `utility()`는 미등록 후보에 KeyError를 낸다. 계약은 0.0을 요구하므로
    (측정기가 결렬·미지 후보를 만나도 죽지 않아야 한다) 여기서 흡수한다.
    """

    __slots__ = ("_p", "pid", "initial_threshold")

    def __init__(self, profile: Profile) -> None:
        self._p = profile
        self.pid = profile.pid
        self.initial_threshold = profile.initial_threshold

    def utility(self, outcome: Outcome) -> float:
        return float(self._p.utilities.get(outcome, 0.0))

    def ranked(self) -> list[Outcome]:
        return list(self._p.ranked())

    def rank_of(self, outcome: Outcome) -> int | None:
        try:
            return self._p.rank_of(outcome)
        except KeyError:
            return None


@dataclass
class NpartyCase:
    """계약 `Case` — 후보 공간은 프로파일 효용 표의 키다."""

    case_id: str
    profiles: Sequence[Profile]
    n_issues: int = 1
    meta: dict | None = None

    @property
    def preferences(self) -> list[NpartyPreference]:
        return [NpartyPreference(p) for p in self.profiles]

    def candidates(self) -> Iterator[Outcome]:
        seen: dict[Outcome, None] = {}
        for p in self.profiles:
            for c in p.utilities:
                seen.setdefault(c, None)
        return iter(sorted(seen, key=repr))

    @property
    def pids(self) -> list[str]:
        return [p.pid for p in self.profiles]


def base_bytes(profiles: Sequence[Profile]) -> int:
    """공통 기저 — **1인분** (자기 효용 표 + 순위표). 단말 단위 판정이므로 전원 합이 아니라
    최대 부하 단말이 자기 단말에 드는 몫만 센다 (24 §2.8, PL 확정 2026-08-13).
    프로파일은 균등 생성이라 첫 참여자로 대표한다.

    프로토콜 상태만 재면 "조합이 늘어도 메모리가 안 는다"는 틀린 그림이 나온다.
    """
    p = profiles[0]
    return deep_size(p.utilities) + deep_size(p.ranked())


def _events(vendor_session, pids: Sequence[str]) -> list[ObservationEvent]:
    """원본 로그 → 계약 이벤트. **가시성을 여기서 선언한다.**"""
    coordinator = pids[0]
    others = tuple(p for p in pids if p != coordinator)
    out: list[ObservationEvent] = []

    for ev in vendor_session.log:
        kind = ev.get("t")
        sweep = ev.get("sweep", 1)

        if kind == "round":
            k = ev.get("k", 1)
            for pid, cand in ev.get("submitted", {}).items():
                # 제출은 담당자에게만 간다 (양 방안 공통)
                out.append(ObservationEvent(sweep, k, pid, "submit", cand, (coordinator,)))
            if vendor_session.plan == "plan1a" and others:
                # 배포 — 익명 목록. actor가 담당자라 원제안자에게 귀속되지 않는다
                for cand in dict.fromkeys(ev.get("submitted", {}).values()):
                    out.append(
                        ObservationEvent(sweep, k, coordinator, "announce", cand, others))
            if vendor_session.plan == "plan2" and others:
                # 라운드 진행 신호 — 참여자는 남의 제출을 못 보므로 담당자 신호 없이
                # 라운드를 넘길 수 없다 (dp2 `_round_tick`과 같은 자리)
                out.append(ObservationEvent(sweep, k, coordinator, "tick", None, others))

        elif kind == "batch":
            for pid, items in ev.get("submitted", {}).items():
                for rank, cand in items:
                    out.append(
                        ObservationEvent(sweep, rank, pid, "submit", cand, (coordinator,)))

        elif kind == "votes":
            # 1-A: O/X는 담당자에게만 가고 결과 공지가 없다
            for pid, votes in ev.get("votes", {}).items():
                for cand, approved in votes.items():
                    if approved:
                        out.append(
                            ObservationEvent(sweep, ev.get("k", 1), pid, "vote", cand,
                                             (coordinator,)))
    return out


def run_session(
    profiles: Sequence[Profile],
    plan: str,
    **plan_kwargs,
) -> tuple[SessionResult, NpartyCase]:
    """방안 1회 실행 → 계약 세션 + 케이스.

    피크 메모리는 협상 구간만 잰다 — 순위표 구축(공통 기저)은 협상 전에 끝나 있고
    방안과 무관하므로 별도로 계상한다.
    """
    spec = PLANS[plan]
    profs = [Profile(p.pid, dict(p.utilities), p.initial_threshold) for p in profiles]
    for p in profs:
        p.ranked()          # 공통 기저를 협상 구간 밖에서 구축
    base = base_bytes(profs)

    plan_obj = spec.cls(profs, **plan_kwargs)
    vendor, process_peak = measure_peak(plan_obj.run)
    # 최대 부하 단말의 프로토콜 상태 (24 §2.8 — 단말 단위 판정, PL 확정 2026-08-13).
    # 프로세스 피크는 전 참여자 합이라 참고로만 남긴다. 세션 종료 상태 근사 —
    # 누적 구조(교집합·계수)는 단조 증가라 정확, 라운드 국소 구조는 근사.
    peak = max(holder_sizes(plan_obj))

    pids = [p.pid for p in profs]
    agreement = NO_AGREEMENT if vendor.outcome == NO_DEAL else vendor.outcome
    session = SessionResult(
        plan=plan,
        participants=pids,
        agreement=agreement,
        rounds=vendor.rounds,
        sweeps=vendor.sweeps,
        phases=vendor.phases,
        messages=vendor.messages,
        bytes=vendor.bytes,
        eval_calls=vendor.eval_calls,
        events=_events(vendor, pids),
        peak_bytes=peak,
        base_bytes=base,
        extra={"profiles": profs, "tie_break_used": vendor.tie_break_used,
               "process_peak_bytes": process_peak},
    )
    case = NpartyCase(case_id="adhoc", profiles=profs)
    return session, case
