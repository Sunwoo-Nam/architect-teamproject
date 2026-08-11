"""설계 후보 1의 프로토콜 구현 — 51번 문서 §2-§4의 스펙.

공통 기반: Blackboard + "라운드 k = 자기 utility 순위 k번째 후보 제출" + 바퀴(sweep) +
만장일치 완결(PL 결정) + 최대 5바퀴 결렬(PL 결정) + 바퀴 단위 threshold 인하.

Plan1Vote      — 방안 1 전원동의 투표형: 라운드 후보 전부에 O/X, 전원 O면 성립
Plan2Cumulative — 방안 2 누적 공통제안형: 누적 제안의 전원 교집합 발생 시 성립
"""
from __future__ import annotations

from .blackboard import Blackboard
from .domain import NO_DEAL, Candidate, Profile, SessionResult
from .threshold import SweepThreshold
from .tiebreak import RankSumThenStdThenRunoff, RunoffMajority, TieBreaker

MAX_SWEEPS = 5  # PL 결정 (2026-08-11)


class _Agent:
    """참여자 1인 — 자기 Profile만 안다. 제출·투표 판단은 전부 로컬."""

    def __init__(self, profile: Profile, max_sweeps: int, aspiration_type: str | float):
        self.p = profile
        self.ranked = profile.ranked()
        self.th = SweepThreshold(
            profile.initial_threshold,
            max_sweeps,
            aspiration_type,
            max_utility=profile.utility(self.ranked[0]),
        )

    def proposal_at(self, sweep: int, k: int) -> Candidate | None:
        """바퀴 sweep의 라운드 k(1-기반)에 낼 후보 — 순위 k번째, revised threshold 이상일 때만."""
        if k > len(self.ranked):
            return None
        c = self.ranked[k - 1]
        return c if self.p.utility(c) >= self.th.at_sweep(sweep) else None

    def vote(self, c: Candidate, sweep: int) -> bool:
        """방안 1의 O/X — NegMAS 판정 그대로: utility ≥ revised threshold면 O."""
        return self.p.utility(c) >= self.th.at_sweep(sweep)


class _BasePlan:
    plan_name = "base"

    def __init__(
        self,
        profiles: list[Profile],
        tie_breaker: TieBreaker,
        max_sweeps: int = MAX_SWEEPS,
        aspiration_type: str | float = "boulware",
    ):
        self.profiles = profiles
        self.agents = [_Agent(p, max_sweeps, aspiration_type) for p in profiles]
        self.tie = tie_breaker
        self.max_sweeps = max_sweeps
        self.n = len(profiles)

    def run(self) -> SessionResult:
        bb = Blackboard(n=self.n)
        events: list[dict] = []  # 관찰 이벤트 — Confidentiality 공격자의 입력
        rounds = 0
        max_rank = max(len(a.ranked) for a in self.agents)
        for sweep in range(1, self.max_sweeps + 1):
            for k in range(1, max_rank + 1):
                # 이번 라운드 제출 (전원 동시, 담당자=0번) — 직렬 단계 1
                submitted: dict[str, Candidate] = {}
                for i, a in enumerate(self.agents):
                    c = a.proposal_at(sweep, k)
                    if c is not None:
                        bb.submit(a.p.pid, is_coordinator=(i == 0))
                        submitted[a.p.pid] = c
                if not submitted and k > 1:
                    break  # 전원 소진 — 이 바퀴 종료, threshold 내리고 다음 바퀴
                bb.phase()
                rounds += 1
                events.append({"t": "round", "sweep": sweep, "k": k, "submitted": dict(submitted)})
                winner, tie_used = self._round(bb, submitted, sweep, events)
                if winner is not None:
                    bb.final_notice()
                    bb.phase()
                    return SessionResult(
                        self.plan_name, winner, rounds, sweep, bb.counter.total,
                        bb.phases, tie_used, events,
                    )
        bb.final_notice()
        bb.phase()
        return SessionResult(
            self.plan_name, NO_DEAL, rounds, self.max_sweeps, bb.counter.total, bb.phases, False, events
        )

    def _round(
        self, bb: Blackboard, submitted: dict[str, Candidate], sweep: int, events: list[dict]
    ) -> tuple[Candidate | None, bool]:
        raise NotImplementedError

    def _resolve(self, bb: Blackboard, winners: list[Candidate]) -> tuple[Candidate, bool]:
        if len(winners) == 1:
            return winners[0], False
        pick, extra_msgs = self.tie.pick(sorted(winners, key=repr), self.profiles)
        bb.tie_break_messages(extra_msgs)
        return pick, True


class Plan1Vote(_BasePlan):
    """방안 1 — 전원동의 투표형. 동률 기본 규칙: 결선투표 1회 다수결."""

    plan_name = "plan1"

    def __init__(self, profiles, tie_breaker: TieBreaker | None = None, **kw):
        super().__init__(profiles, tie_breaker or RunoffMajority(), **kw)

    def _round(self, bb, submitted, sweep, events):
        candidates = sorted(set(submitted.values()), key=repr)
        bb.announce_candidates()  # 투표하려면 그 라운드 후보를 전원에게 배포해야 한다
        bb.phase()
        votes: dict[str, dict[Candidate, bool]] = {}
        for i, a in enumerate(self.agents):
            bb.vote(a.p.pid, is_coordinator=(i == 0))  # 라운드당 O/X 번들 1건
            votes[a.p.pid] = {c: a.vote(c, sweep) for c in candidates}
        bb.phase()
        bb.round_result()  # O/X 결과가 전원에게 공개된다
        bb.phase()
        events.append({"t": "votes", "sweep": sweep, "votes": {p: dict(v) for p, v in votes.items()}})
        unanimous = [c for c in candidates if all(votes[p.pid][c] for p in self.profiles)]
        if not unanimous:
            return None, False
        return self._resolve(bb, unanimous)


class Plan2Cumulative(_BasePlan):
    """방안 2 — 누적 공통제안형. 동률 기본 규칙: 순위 합 → 표준편차 → 결선투표."""

    plan_name = "plan2"

    def __init__(self, profiles, tie_breaker: TieBreaker | None = None, **kw):
        super().__init__(profiles, tie_breaker or RankSumThenStdThenRunoff(), **kw)

    def _round(self, bb, submitted, sweep, events):
        for pid, c in submitted.items():
            bb.proposed_by.setdefault(pid, set()).add(c)
        if len(bb.proposed_by) < self.n:
            return None, False  # 아직 제안 이력이 없는 참여자가 있음
        common = set.intersection(*bb.proposed_by.values())  # 전원이 제안한 적 있는 안 = 만장일치
        if not common:
            return None, False
        return self._resolve(bb, sorted(common, key=repr))
