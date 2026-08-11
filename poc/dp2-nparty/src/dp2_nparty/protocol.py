"""설계 후보 1의 프로토콜 구현 — 51번 문서 §2-§4의 스펙 (핸드북 24 측정 지원).

공통 기반: Blackboard + "자기 utility 순위 순서 제출"(포인터 기반 — 유실 시 재시도) +
바퀴(sweep) + 만장일치 완결 + 최대 5바퀴 결렬 + 바퀴 단위 threshold 인하.

측정 지원 훅:
- injector: 장애 주입(핸드북 §5-1 FT) — 유실된 제출은 포인터가 안 움직여 자동 재시도
- kill_at: 강제 중단·복구(§5-2 REC) — 지정 지점 도달 시 라운드 경계 스냅샷으로 복원하고
  resync 비용을 지불한 뒤 그 라운드를 재수행 (복구 비용은 phase 총량 차로 측정)
- on_round_end: 라운드 경계 콜백 (§2 RSS 평균의 ENV-A 대체 표집)
"""
from __future__ import annotations

from dataclasses import dataclass

from .blackboard import Blackboard
from .domain import NO_DEAL, Candidate, Profile, SessionResult
from .faults import FaultInjector
from .threshold import SweepThreshold
from .tiebreak import RankSumThenStdThenRunoff, RunoffMajority, TieBreaker

MAX_SWEEPS = 5  # PL 결정 (2026-08-11)

# 비교 대상 방안 목록 — 측정·리포트 전체가 이 목록을 순회한다
def all_plans():
    return (("plan1", Plan1Vote), ("plan2", Plan2Cumulative), ("plan3a", Plan3Batch))


PLAN_NAMES = ("plan1", "plan2", "plan3a")
PLAN_LABELS = {"plan1": "방안 1 전원동의 투표형", "plan2": "방안 2 누적 공통제안형",
               "plan3a": "방안 3-A 일괄 순위 제출형"}


@dataclass
class KillAt:
    """REC 측정용 강제 중단 지점 — 세션당 1회."""

    round_no: int
    point: str  # "mid_round"(제출 직후) | "post_votes"(방안1 투표 직후) | "pre_final"(성립 후 통지 전)


class _Kill(Exception):
    pass


class _Agent:
    """참여자 1인 — 자기 Profile만 안다. 순위 포인터는 제출이 도착했을 때만 전진한다."""

    def __init__(self, profile: Profile, max_sweeps: int, aspiration_type: str | float):
        self.p = profile
        self.ranked = profile.ranked()
        self.ptr = 0
        self.th = SweepThreshold(
            profile.initial_threshold, max_sweeps, aspiration_type,
            max_utility=profile.utility(self.ranked[0]),
        )

    def peek(self, sweep: int) -> Candidate | None:
        """이번에 낼 후보 — 포인터 위치 후보가 revised threshold 이상일 때만.
        순위표가 내림차순이라 한 번 미만이면 그 바퀴는 소진이다 (prefix 성질)."""
        if self.ptr >= len(self.ranked):
            return None
        c = self.ranked[self.ptr]
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
        collect_log: bool = True,
    ):
        self.profiles = profiles
        self.agents = [_Agent(p, max_sweeps, aspiration_type) for p in profiles]
        self.tie = tie_breaker
        self.max_sweeps = max_sweeps
        self.n = len(profiles)
        self.collect_log = collect_log

    # ---- 라운드 경계 스냅샷 = 복구 지점 ----
    def _snapshot(self, bb: Blackboard) -> dict:
        return {
            "ptrs": [a.ptr for a in self.agents],
            "proposed_by": {k: set(v) for k, v in bb.proposed_by.items()},
        }

    def _restore(self, bb: Blackboard, snap: dict) -> None:
        for a, ptr in zip(self.agents, snap["ptrs"]):
            a.ptr = ptr
        bb.proposed_by = {k: set(v) for k, v in snap["proposed_by"].items()}

    def run(
        self,
        injector: FaultInjector | None = None,
        kill_at: KillAt | None = None,
        on_round_end=None,
    ) -> SessionResult:
        bb = Blackboard(n=self.n)
        events: list[dict] = []
        rounds = 0
        # 효용 평가 호출: 순위표 구축 = 참여자마다 전 후보 1회 평가 (두 방안 공통)
        self._eval_calls = sum(len(a.ranked) for a in self.agents)
        max_rank = max(len(a.ranked) for a in self.agents)
        round_cap = self.max_sweeps * (max_rank + 20) * 3  # 유실 재시도 무한 루프 방지
        for sweep in range(1, self.max_sweeps + 1):
            for a in self.agents:
                a.ptr = 0  # 새 바퀴 — 낮아진 threshold로 처음부터 재순회
            while rounds < round_cap:
                # 스냅샷은 kill 실험에서만 — 일반 세션의 RU 측정을 오염시키지 않도록
                boundary = self._snapshot(bb) if kill_at else None
                try:
                    outcome, exhausted = self._one_round(
                        bb, sweep, rounds + 1, injector, kill_at, events
                    )
                except _Kill:
                    # 복구: 경계 스냅샷 복원 + 전원 상태 재동기화 → 라운드 재수행
                    self._restore(bb, boundary)
                    bb.resync({"sweep": sweep, "ptrs": [a.ptr for a in self.agents]})
                    kill_at = None  # 세션당 1회
                    continue
                if exhausted:
                    break  # 전원 소진 — 다음 바퀴
                rounds += 1
                if on_round_end:
                    on_round_end()
                if outcome is not None:
                    winner, tie_used = outcome
                    bb.final_notice({"outcome": str(winner)})
                    bb.phase()
                    return SessionResult(
                        self.plan_name, winner, rounds, sweep, bb.counter.total,
                        phases=bb.phases, tie_break_used=tie_used, log=events,
                        bytes=bb.counter.total_bytes, eval_calls=self._eval_calls,
                    )
        bb.final_notice({"outcome": NO_DEAL})
        bb.phase()
        return SessionResult(
            self.plan_name, NO_DEAL, rounds, self.max_sweeps, bb.counter.total,
            phases=bb.phases, tie_break_used=False, log=events,
            bytes=bb.counter.total_bytes, eval_calls=self._eval_calls,
        )

    def _one_round(self, bb, sweep, round_no, injector, kill_at, events):
        """한 라운드. 반환 (성립 결과 | None, 전원 소진 여부)."""
        submitted: dict[str, Candidate] = {}
        any_pending = False
        for i, a in enumerate(self.agents):
            c = a.peek(sweep)
            if c is None:
                continue
            any_pending = True
            bb.submit(a.p.pid, i == 0, {"candidate": str(c)})  # 전송 발생 (비용 지불)
            if injector and injector.lost():
                continue  # 도착 실패 — 포인터 유지 → 다음 라운드 재시도
            submitted[a.p.pid] = c
            a.ptr += 1
        if not any_pending:
            return None, True  # 전원 소진
        bb.phase()
        if self.collect_log:
            events.append(
                {"t": "round", "sweep": sweep, "k": round_no, "submitted": dict(submitted)}
            )
        if kill_at and kill_at.round_no == round_no and kill_at.point == "mid_round":
            raise _Kill()
        if not submitted:
            return None, False  # 이번 라운드 전원 유실 — 다음 라운드 재시도
        result = self._judge(bb, submitted, sweep, round_no, injector, kill_at, events)
        if result is not None and kill_at and kill_at.round_no == round_no and kill_at.point == "pre_final":
            raise _Kill()
        return result, False

    def _judge(self, bb, submitted, sweep, round_no, injector, kill_at, events):
        raise NotImplementedError

    def _resolve(self, bb, winners: list[Candidate]):
        if len(winners) == 1:
            return winners[0], False
        tied = sorted(winners, key=repr)
        pick, extra_msgs = self.tie.pick(tied, self.profiles)
        bb.tie_break_messages(extra_msgs, {"tied": [str(c) for c in tied]})
        return pick, True


class Plan1Vote(_BasePlan):
    """방안 1 — 전원동의 투표형. 라운드 = 제출·공지·투표·결과의 4 phase."""

    plan_name = "plan1"

    def __init__(self, profiles, tie_breaker: TieBreaker | None = None, **kw):
        super().__init__(profiles, tie_breaker or RunoffMajority(), **kw)

    def _judge(self, bb, submitted, sweep, round_no, injector, kill_at, events):
        candidates = sorted(set(submitted.values()), key=repr)
        bb.announce_candidates([str(c) for c in candidates])
        bb.phase()
        votes: dict[str, dict[Candidate, bool]] = {}
        self._eval_calls += len(candidates) * self.n  # 투표 = 전원이 라운드 후보 전부 재평가
        for i, a in enumerate(self.agents):
            bundle = {c: a.vote(c, sweep) for c in candidates}
            bb.vote(a.p.pid, i == 0, {str(c): v for c, v in bundle.items()})  # 전송 발생
            if injector and injector.lost():
                continue  # 번들 유실 — 이번 라운드 부재 처리 (O 아님)
            votes[a.p.pid] = bundle
        bb.phase()
        unanimous = [
            c for c in candidates
            if len(votes) == self.n and all(votes[p.pid][c] for p in self.profiles)
        ]
        bb.round_result({"unanimous": [str(c) for c in unanimous]})
        bb.phase()
        if self.collect_log:
            events.append({
                "t": "votes", "sweep": sweep,
                "votes": {p: dict(bundle) for p, bundle in votes.items()},
            })
        if kill_at and kill_at.round_no == round_no and kill_at.point == "post_votes":
            raise _Kill()
        if not unanimous:
            return None
        return self._resolve(bb, unanimous)


class Plan2Cumulative(_BasePlan):
    """방안 2 — 누적 공통제안형. 라운드 = 제출 1 phase (판정은 담당자 로컬)."""

    plan_name = "plan2"

    def __init__(self, profiles, tie_breaker: TieBreaker | None = None, **kw):
        super().__init__(profiles, tie_breaker or RankSumThenStdThenRunoff(), **kw)

    def _judge(self, bb, submitted, sweep, round_no, injector, kill_at, events):
        for pid, c in submitted.items():
            bb.proposed_by.setdefault(pid, set()).add(c)
        if len(bb.proposed_by) < self.n:
            return None
        common = set.intersection(*bb.proposed_by.values())  # 전원 제안 = 만장일치
        if not common:
            return None
        return self._resolve(bb, sorted(common, key=repr))


class Plan3Batch(_BasePlan):
    """방안 3-A — 일괄 순위 제출·중앙 선별형 (51 §3-A).

    라운드 반복이 없다: 바퀴(sweep)마다 각자 revised threshold 이상의 미전달 후보
    **전부를 순위와 함께 한 번에** 제출(배치 1건 = 1 phase)하고, 담당자가 누적 교집합에서
    순위 합 최소 후보를 선별한다. 배치 유실은 다음 바퀴에 자동 재시도(미전달 유지).
    담당자의 누적 저장소는 bb.proposed_by를 재사용한다 (스냅샷·복구 기계 공유).
    """

    plan_name = "plan3a"

    def __init__(self, profiles, tie_breaker: TieBreaker | None = None, **kw):
        super().__init__(profiles, tie_breaker or RankSumThenStdThenRunoff(), **kw)

    def run(self, injector=None, kill_at=None, on_round_end=None) -> SessionResult:
        bb = Blackboard(n=self.n)
        events: list[dict] = []
        rounds = 0  # 방안 3-A의 라운드 = 배치 제출 회수 (바퀴당 1회)
        self._eval_calls = sum(len(a.ranked) for a in self.agents)  # 순위표 구축 (공통)
        for sweep in range(1, self.max_sweeps + 1):
            boundary = self._snapshot(bb)
            try:
                outcome = self._one_sweep(bb, sweep, rounds + 1, injector, kill_at, events)
            except _Kill:
                self._restore(bb, boundary)
                bb.resync({"sweep": sweep, "delivered": {k: len(v) for k, v in bb.proposed_by.items()}})
                kill_at = None
                try:
                    outcome = self._one_sweep(bb, sweep, rounds + 1, injector, None, events)
                except _Kill:  # 방어적 — 발생하지 않음
                    outcome = None
            rounds += 1
            if on_round_end:
                on_round_end()
            if outcome is not None:
                winner, tie_used = outcome
                bb.final_notice({"outcome": str(winner)})
                bb.phase()
                return SessionResult(
                    self.plan_name, winner, rounds, sweep, bb.counter.total,
                    phases=bb.phases, tie_break_used=tie_used, log=events,
                    bytes=bb.counter.total_bytes, eval_calls=self._eval_calls,
                )
        bb.final_notice({"outcome": NO_DEAL})
        bb.phase()
        return SessionResult(
            self.plan_name, NO_DEAL, rounds, self.max_sweeps, bb.counter.total,
            phases=bb.phases, tie_break_used=False, log=events,
            bytes=bb.counter.total_bytes, eval_calls=self._eval_calls,
        )

    def _one_sweep(self, bb, sweep, round_no, injector, kill_at, events):
        batch_log: dict[str, list] = {}
        for i, a in enumerate(self.agents):
            th = a.th.at_sweep(sweep)
            delivered = bb.proposed_by.setdefault(a.p.pid, set())
            items = [
                (rank + 1, c)
                for rank, c in enumerate(a.ranked)
                if a.p.utility(c) >= th and c not in delivered
            ]
            if not items:
                continue
            payload = [{"rank": r, "candidate": str(c)} for r, c in items]
            bb.submit(a.p.pid, i == 0, payload)  # 배치 1건 — 페이로드가 후보 수에 비례
            if injector and injector.lost():
                continue  # 배치 유실 — 미전달 유지 → 다음 바퀴 재시도
            delivered.update(c for _r, c in items)
            batch_log[a.p.pid] = [(r, str(c)) for r, c in items]
        bb.phase()  # 배치 제출 = 1 phase
        if self.collect_log:
            events.append({"t": "batch", "sweep": sweep, "k": round_no, "submitted": batch_log})
        if kill_at and kill_at.round_no == round_no and kill_at.point == "mid_round":
            raise _Kill()
        if len(bb.proposed_by) < self.n or any(not v for v in bb.proposed_by.values()):
            return None
        common = set.intersection(*bb.proposed_by.values())
        if not common:
            return None
        result = self._resolve(bb, sorted(common, key=repr))  # 순위 합 최소 선별 (tie 체인)
        if kill_at and kill_at.round_no == round_no and kill_at.point == "pre_final":
            raise _Kill()
        return result
