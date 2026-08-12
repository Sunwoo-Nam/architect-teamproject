"""Blackboard 외 아키텍처 스타일의 방안들 (51 §4-2/4-3/4-4).

공통 유지: 순위 순서 제출·바퀴별 threshold 인하·만장일치(교집합)·순위합 최소 선별·
최대 5바퀴 NO_DEAL. 다른 것은 **통신·상태의 구조**다:

- Plan1aSao  (SAO 사설 메시지): 게시판 없음 — 담당자 1인이 양자 채널 N-1개로 offer/회신
- Plan3Mesh  (P2P 브로드캐스트): 중앙 없음 — 전원이 전원에게 방송, 각자 로컬 판정
- Plan4Ring  (Pipeline/token):  협상 문서가 고리를 순회 — 문서가 곧 상태, 홉마다 직렬
- Plan21Tree  (Hierarchical):   쌍별 수락 집합을 트리로 병합 — 상위엔 개인 귀속 없는 집계만

Blackboard 객체는 여기서 공유 저장소가 아니라 **계측기**(메시지·바이트·phase·부하)로만 쓴다.
"""
from __future__ import annotations

from .blackboard import Blackboard
from .domain import NO_DEAL, SessionResult
from .protocol import MAX_SWEEPS, _Agent, _Kill, KillAt
from .tiebreak import RankSumThenStdThenRunoff, RunoffMajority, TieBreaker


class _StyleBase:
    plan_name = "style"

    def __init__(
        self,
        profiles,
        tie_breaker: TieBreaker | None = None,
        max_sweeps: int = MAX_SWEEPS,
        aspiration_type="boulware",
        collect_log: bool = True,
    ):
        self.profiles = profiles
        self.agents = [_Agent(p, max_sweeps, aspiration_type) for p in profiles]
        self.tie = tie_breaker or RankSumThenStdThenRunoff()
        self.max_sweeps = max_sweeps
        self.n = len(profiles)
        self.collect_log = collect_log

    # 공통 상태: 참여자별 전달 완료 집합 (각 스타일의 '어디에 있느냐'만 다름)
    def _snapshot(self, delivered):
        return {"ptrs": [a.ptr for a in self.agents],
                "delivered": {k: set(v) for k, v in delivered.items()}}

    def _restore(self, delivered, snap):
        for a, ptr in zip(self.agents, snap["ptrs"]):
            a.ptr = ptr
        delivered.clear()
        delivered.update({k: set(v) for k, v in snap["delivered"].items()})

    def _pick(self, bb, delivered):
        if len(delivered) < self.n or any(not v for v in delivered.values()):
            return None
        common = set.intersection(*delivered.values())
        if not common:
            return None
        tied = sorted(common, key=repr)
        pick, extra = self.tie.pick(tied, self.profiles)
        bb.tie_break_messages(extra, {"tied": [str(c) for c in tied]})
        return pick, len(tied) > 1

    def _result(self, bb, rounds, sweep, outcome, tie_used, events):
        return SessionResult(
            self.plan_name, outcome, rounds, sweep, bb.counter.total,
            phases=bb.phases, tie_break_used=tie_used, log=events,
            bytes=bb.counter.total_bytes, eval_calls=self._eval_calls,
        )


class Plan1aSao(_StyleBase):
    """방안 1-A — 순차 SAO 투표형 (Blackboard 제거·점진 공개, 신규 2026-08-12).

    방안 1의 **판정 규칙은 그대로**(그 라운드 후보에 전원 O = 성립) 두고, 공유 게시판을
    없앤 뒤 통신을 NegMAS SAO의 메시지 의미론 — offer / (accept·reject + counter-offer) —
    만으로 돌린다. 담당자 P0가 양자 채널 N-1개를 들고 있고, 게시가 아니라 사설 메시지가
    오간다. (구현 주석: negmas `SAOMechanism` 클래스를 쓰지 않는다 — 그 메커니즘은 자체
    프로토콜·계측 하니스에 직접 꽂히지 않아, `confidentiality.py`가 `FrequencyUFunModel`을
    재구현한 것과 같은 방식으로 **메시지 의미론만** 가져왔다.)

    절차 (바퀴 s):
    1. 수집 — 바퀴 시작 1회. 각자 자기 순위 후보 1개를 담당자에게만 보낸다 (N-1건, 1 phase).
    2. 배포(= SAO offer) — 담당자가 모인 후보를 **익명 목록**(누가 냈는지 없음)으로 전원에게
       던진다 (N-1건, 1 phase).
    3. 회신(= SAO accept/reject + counter-offer) — 각자 **O/X 번들과 자기 다음 순위 후보를
       한 메시지에** 실어 답한다 (N-1건, 1 phase). 2-3을 반복한다.
    4. 라운드 결과 공지가 없다 — 다음 배포가 곧 "미성립" 신호이고, 성립 시에만 최종 통지.

    성질:
    - 라운드당 2 phase · 2(N-1)건 — 방안 1(제출·공지·투표·결과 = 4 phase · 4(N-1)건)의 절반.
      바퀴마다 수집 1 phase가 선행 비용으로 붙는다.
    - **FC 동일성**: 라운드 k의 판정 후보 집합이 방안 1과 같은 "전원의 k순위"라, 무유실
      조건에서 결과·라운드 수가 방안 1과 일치한다.
    - 노출: 재배포가 익명이라 일반 참여자는 남의 귀속을 보지 못하고 O/X도 못 본다
      (방안 1은 공유 게시판이라 전면 노출). 대신 담당자 1인이 전 제출 + 전 O/X를 본다 —
      노출 지점이 담당자에게 집중된다.
    - 유실: O/X와 다음 후보가 **한 메시지에 결합**돼 1건 유실이 둘을 함께 잃는다 (방안 1은
      별개 사건). 포인터가 안 움직여 같은 후보를 다음 라운드에 재시도한다.
    - 담당자가 받은 것이 없으면(전원 유실) 빈 후보 목록을 던져 재요청한다 — 회신이 곧
      재전송 수단이라 배포 없이는 재시도가 일어나지 않는다.
    """

    plan_name = "plan1a"

    def __init__(self, profiles, tie_breaker: TieBreaker | None = None, **kw):
        # 방안 1과 같은 이유로 결선투표 — O/X는 문턱 통과 여부만 말해 주고, 만장일치 후보를
        # 전원이 제안했다는 보장이 없어 순위 합을 쓸 수 없다.
        super().__init__(profiles, tie_breaker or RunoffMajority(), **kw)

    def run(self, injector=None, kill_at=None, on_round_end=None) -> SessionResult:
        bb = Blackboard(n=self.n)
        events: list[dict] = []
        coord = self.agents[0].p.pid
        rounds = 0
        self._eval_calls = sum(len(a.ranked) for a in self.agents)
        max_rank = max(len(a.ranked) for a in self.agents)
        cap = self.max_sweeps * (max_rank + 20) * 3
        for sweep in range(1, self.max_sweeps + 1):
            for a in self.agents:
                a.ptr = 0  # 새 바퀴 — 낮아진 threshold로 처음부터 재순회
            carried, any_offer = self._collect(bb, sweep, injector, coord)
            self._carried_ref = carried  # RU 귀속: 담당자의 라운드 국소 상태 (누적 없음)
            while rounds < cap and any_offer:
                # 라운드별 판정이라 과거 상태가 불필요 — 복구 스냅샷도 라운드 경계의
                # 포인터·carried뿐이다 (누적 보유 제거: PL 지시 2026-08-12, REC 비핵심)
                boundary = {"ptrs": [a.ptr for a in self.agents], "carried": dict(carried)}
                try:
                    picked, carried, any_offer = self._exchange(
                        bb, sweep, rounds + 1, injector, kill_at, events, coord, carried,
                    )
                    self._carried_ref = carried
                except _Kill:
                    # 복구: 라운드 경계 복원 + 담당자↔복귀 단말 재동기화 → 라운드 재수행
                    for a, ptr in zip(self.agents, boundary["ptrs"]):
                        a.ptr = ptr
                    carried = dict(boundary["carried"])
                    self._carried_ref = carried
                    bb.resync({"sweep": sweep})
                    kill_at = None  # 세션당 1회
                    continue
                rounds += 1
                if on_round_end:
                    on_round_end()
                if picked:
                    bb.final_notice({"outcome": str(picked[0])})  # 성립 시에만 통지
                    bb.phase()
                    return self._result(bb, rounds, sweep, picked[0], picked[1], events)
        bb.final_notice({"outcome": NO_DEAL})
        bb.phase()
        return self._result(bb, rounds, self.max_sweeps, NO_DEAL, False, events)

    def _collect(self, bb, sweep, injector, coord):
        """바퀴 시작 1회 — 각자 자기 순위 후보 1개를 담당자에게만 사설 전송 (게시 없음).
        이후 라운드의 제출은 회신 메시지에 실려 오므로 이 phase가 다시 나오지 않는다."""
        carried: dict[str, object] = {}
        any_offer = False
        for i, a in enumerate(self.agents):
            c = a.peek(sweep)
            if c is None:
                continue
            any_offer = True
            if i != 0:  # 담당자 자신의 제출은 로컬 — 전송 0건
                bb.counter.add("collect", 1, {"candidate": str(c)})
                bb.load[coord] = bb.load.get(coord, 0) + 1  # 수신·처리 부하는 담당자에게
                if injector and injector.lost():
                    continue  # 유실 — ptr 유지 → 다음 회신에 같은 후보 재시도
            carried[a.p.pid] = c
            a.ptr += 1
        if any_offer:
            bb.phase()
        return carried, any_offer

    def _exchange(self, bb, sweep, round_no, injector, kill_at, events, coord, carried):
        """라운드 1회 = 배포(offer) + 회신(O/X + 다음 후보). 반환 (성립|None, 다음 carried, 계속 여부)."""
        candidates = sorted(set(carried.values()), key=repr)
        # 익명 후보 목록 — 게시판이 없어 제안자 귀속이 실리지 않는다 (PL 확정 2026-08-12).
        # 페이로드 형태는 방안 1의 후보 공지와 동일(맨 리스트)로 맞춘다 — 같은 정보를 담은
        # 메시지가 포장 차이만으로 바이트에서 불리해지지 않도록 (§9.2 비교 공정성).
        bb.counter.add("offer", self.n - 1, [str(c) for c in candidates])
        for a in self.agents[1:]:
            bb.load[a.p.pid] = bb.load.get(a.p.pid, 0) + 1
        bb.phase()
        if kill_at and kill_at.round_no == round_no and kill_at.point == "mid_round":
            raise _Kill()  # 배포 직후·회신 전 중단
        votes: dict[str, dict] = {}
        nxt_carried: dict[str, object] = {}
        any_offer = False
        self._eval_calls += len(candidates) * self.n  # O/X = 전원이 라운드 후보 전부 재평가
        for i, a in enumerate(self.agents):
            bundle = {c: a.vote(c, sweep) for c in candidates}
            nxt = a.peek(sweep)  # 다음 순위 후보 — 유실됐던 라운드면 같은 후보가 다시 나온다
            if nxt is not None:
                any_offer = True
            if i != 0:  # 담당자 자신의 O/X·다음 후보는 로컬
                bb.counter.add("reply", 1, {  # 반응 + 역제안 = SAO 1건
                    "votes": {str(c): v for c, v in bundle.items()},
                    "next": str(nxt) if nxt is not None else None,
                })
                bb.load[coord] = bb.load.get(coord, 0) + 1
                if injector and injector.lost():
                    continue  # 결합 유실 — O/X와 다음 후보를 함께 잃는다 (ptr 유지 → 재시도)
            votes[a.p.pid] = bundle
            if nxt is not None:
                nxt_carried[a.p.pid] = nxt
                a.ptr += 1
        bb.phase()
        if self.collect_log:
            events.append({"t": "round", "sweep": sweep, "k": round_no, "submitted": dict(carried)})
            events.append({"t": "votes", "sweep": sweep,
                           "votes": {p: dict(b) for p, b in votes.items()}})
        if kill_at and kill_at.round_no == round_no and kill_at.point == "post_votes":
            raise _Kill()  # 회신 도착 직후·판정 전 중단
        unanimous = [c for c in candidates
                     if len(votes) == self.n and all(votes[p.pid][c] for p in self.profiles)]
        picked = None
        if unanimous:
            tied = sorted(unanimous, key=repr)
            if len(tied) == 1:
                picked = (tied[0], False)  # 동률 아님 — 결선투표 비용을 물리지 않는다 (방안 1과 동일)
            else:
                pick, extra = self.tie.pick(tied, self.profiles)
                bb.tie_break_messages(extra, {"tied": [str(c) for c in tied]})
                picked = (pick, True)
            if kill_at and kill_at.round_no == round_no and kill_at.point == "pre_final":
                raise _Kill()
        return picked, nxt_carried, any_offer


class Plan3Mesh(_StyleBase):
    """방안 3 — 전원 브로드캐스트 분산형 (P2P). 라운드마다 각자 순위 순서 후보 1개를
    전원에게 방송(전송 N-1건, 병렬 1 phase). 전원이 같은 데이터를 보므로 로컬 판정이
    결정적으로 일치한다 — 별도 성립 통지가 없다. 유실된 방송은 다음 라운드 재시도."""

    plan_name = "plan3mesh"

    def run(self, injector=None, kill_at=None, on_round_end=None) -> SessionResult:
        bb = Blackboard(n=self.n)
        events: list[dict] = []
        delivered: dict[str, set] = {}
        self._delivered_ref = delivered  # RU 1인당 귀속 측정용 참조
        rounds = 0
        self._eval_calls = sum(len(a.ranked) for a in self.agents)
        max_rank = max(len(a.ranked) for a in self.agents)
        cap = self.max_sweeps * (max_rank + 20) * 3
        for sweep in range(1, self.max_sweeps + 1):
            for a in self.agents:
                a.ptr = 0
            while rounds < cap:
                boundary = self._snapshot(delivered)
                submitted, any_pending = {}, False
                for a in self.agents:
                    c = a.peek(sweep)
                    if c is None:
                        continue
                    any_pending = True
                    bb.counter.add("bcast", self.n - 1, {"candidate": str(c)})  # 방송 = N-1 전송
                    bb.load[a.p.pid] = bb.load.get(a.p.pid, 0) + 1
                    if injector and injector.lost():
                        continue  # 방송 유실(보수 모델: 전체 재시도) — ptr 유지
                    delivered.setdefault(a.p.pid, set()).add(c)
                    submitted[a.p.pid] = c
                    a.ptr += 1
                if not any_pending:
                    break
                bb.phase()
                rounds += 1
                if self.collect_log:
                    events.append({"t": "round", "sweep": sweep, "k": rounds, "submitted": submitted})
                if on_round_end:
                    on_round_end()
                try:
                    if kill_at and kill_at.round_no == rounds and kill_at.point == "mid_round":
                        raise _Kill()
                    picked = self._pick(bb, delivered)
                    if picked and kill_at and kill_at.round_no == rounds and kill_at.point == "pre_final":
                        raise _Kill()
                except _Kill:
                    self._restore(delivered, boundary)
                    bb.resync({"sweep": sweep})  # 복귀 노드가 이웃에게서 상태 회수
                    kill_at = None
                    rounds -= 1
                    continue
                if picked:
                    winner, tie_used = picked
                    return self._result(bb, rounds, sweep, winner, tie_used, events)
        return self._result(bb, rounds, self.max_sweeps, NO_DEAL, False, events)


class Plan4Ring(_StyleBase):
    """방안 4 — 순차 릴레이형 (Pipeline/token). 협상 문서가 P0→P1→…→P0 고리를 돌며,
    받은 사람이 자기 다음 순위 후보를 문서에 덧붙이고 넘긴다 — 홉 1회 = 전송 1건 = 1 phase
    (직렬). 문서 보유자가 교집합을 발견하면 확정 순회(N-1 홉)로 전원에게 알린다.
    홉 유실은 즉시 재전송(+1 홉 비용)."""

    plan_name = "plan4ring"

    def _hop(self, bb, injector, payload):
        while True:
            bb.counter.add("relay", 1, payload)
            bb.phases += 1
            if not (injector and injector.lost()):
                return

    def run(self, injector=None, kill_at=None, on_round_end=None) -> SessionResult:
        bb = Blackboard(n=self.n)
        events: list[dict] = []
        delivered: dict[str, set] = {}
        self._delivered_ref = delivered  # RU 1인당 귀속 측정용 참조
        rounds = 0  # 라운드 = 고리 한 바퀴(전원 1회 처리)
        self._eval_calls = sum(len(a.ranked) for a in self.agents)
        max_rank = max(len(a.ranked) for a in self.agents)
        cap = self.max_sweeps * (max_rank + 20) * 3
        for sweep in range(1, self.max_sweeps + 1):
            for a in self.agents:
                a.ptr = 0
            while rounds < cap:
                boundary = self._snapshot(delivered)
                cycle_submitted, any_pending = {}, False
                killed = False
                for a in self.agents:  # 문서가 고리를 한 바퀴
                    c = a.peek(sweep)
                    if c is not None:
                        any_pending = True
                        delivered.setdefault(a.p.pid, set()).add(c)
                        cycle_submitted[a.p.pid] = c
                        a.ptr += 1
                        bb.load[a.p.pid] = bb.load.get(a.p.pid, 0) + 1
                    doc_size = sum(len(v) for v in delivered.values())
                    self._hop(bb, injector, {"doc_entries": doc_size})  # 다음 순번으로 전달
                    picked = self._pick(bb, delivered)
                    if picked:
                        rounds += 1
                        if self.collect_log:
                            events.append({"t": "round", "sweep": sweep, "k": rounds,
                                           "submitted": cycle_submitted})
                        if kill_at and kill_at.round_no == rounds and kill_at.point in ("mid_round", "pre_final"):
                            self._restore(delivered, boundary)
                            bb.resync({"sweep": sweep})  # 직전 보유자 사본에서 문서 복원
                            kill_at = None
                            rounds -= 1
                            killed = True
                            break
                        for _ in range(self.n - 1):  # 확정 순회
                            self._hop(bb, injector, {"final": str(picked[0])})
                        if on_round_end:
                            on_round_end()
                        return self._result(bb, rounds, sweep, picked[0], picked[1], events)
                if killed:
                    continue
                if not any_pending:
                    break
                rounds += 1
                if self.collect_log:
                    events.append({"t": "round", "sweep": sweep, "k": rounds, "submitted": cycle_submitted})
                if on_round_end:
                    on_round_end()
                if kill_at and kill_at.round_no == rounds and kill_at.point == "mid_round":
                    self._restore(delivered, boundary)
                    bb.resync({"sweep": sweep})
                    kill_at = None
                    rounds -= 1
        return self._result(bb, rounds, self.max_sweeps, NO_DEAL, False, events)


class Plan21Tree(_StyleBase):
    """방안 21 — 계층 병합형 (Hierarchical). 바퀴마다: 각자 threshold 이상 미전달 후보를
    배치로 준비 → 쌍(pair)의 오른쪽이 왼쪽 리더에게 전송(레벨당 병렬 1 phase) → 리더가
    교집합·순위합을 병합해 위로 — 트리 꼭대기(root = P0)에서 전역 교집합 판정, 결과를
    전원에 통지(1 phase, N-1건). 상위 계층에는 개인 귀속 없는 집계만 올라간다."""

    plan_name = "plan21tree"

    def run(self, injector=None, kill_at=None, on_round_end=None) -> SessionResult:
        import math

        bb = Blackboard(n=self.n)
        events: list[dict] = []
        delivered: dict[str, set] = {}
        self._delivered_ref = delivered  # RU 1인당 귀속 측정용 참조
        rounds = 0  # 라운드 = 바퀴당 트리 병합 1회
        self._eval_calls = sum(len(a.ranked) for a in self.agents)
        for sweep in range(1, self.max_sweeps + 1):
            boundary = self._snapshot(delivered)
            batch_log = {}
            for a in self.agents:  # 리프: 이번 바퀴 배치 준비 (로컬)
                th = a.th.at_sweep(sweep)
                got = delivered.setdefault(a.p.pid, set())
                items = [(r + 1, c) for r, c in enumerate(a.ranked)
                         if a.p.utility(c) >= th and c not in got]
                if items:
                    got.update(c for _r, c in items)
                    batch_log[a.p.pid] = [(r, str(c)) for r, c in items]
            # 병합: 레벨마다 쌍의 오른쪽 → 왼쪽 리더 전송 (병렬 = 레벨당 1 phase)
            nodes = list(range(self.n))
            while len(nodes) > 1:
                nxt = []
                for i in range(0, len(nodes), 2):
                    if i + 1 < len(nodes):
                        right = self.agents[nodes[i + 1]]
                        size = len(delivered[right.p.pid])
                        payload = {"agg_entries": size}  # 집계 전송 — 개인 귀속 없는 요약
                        while True:
                            bb.counter.add("merge", 1, payload)
                            bb.load[right.p.pid] = bb.load.get(right.p.pid, 0) + 1
                            if not (injector and injector.lost()):
                                break
                            bb.phases += 1  # 유실 재전송
                    nxt.append(nodes[i])
                bb.phase()
                nodes = nxt
            rounds += 1
            if self.collect_log:
                events.append({"t": "batch", "sweep": sweep, "k": rounds, "submitted": batch_log})
            if on_round_end:
                on_round_end()
            try:
                if kill_at and kill_at.round_no == rounds and kill_at.point == "mid_round":
                    raise _Kill()
                picked = self._pick(bb, delivered)  # root(P0)의 전역 판정
                if picked and kill_at and kill_at.round_no == rounds and kill_at.point == "pre_final":
                    raise _Kill()
            except _Kill:
                self._restore(delivered, boundary)
                bb.resync({"sweep": sweep})
                kill_at = None
                rounds -= 1
                sweep_again = sweep  # 같은 바퀴 재수행
                # 간단 재수행: 다음 루프 반복이 다음 sweep이므로 여기서 직접 한 번 더
                # (배치·병합을 동일하게) — 결정론이라 결과 동일
                for a in self.agents:
                    th = a.th.at_sweep(sweep_again)
                    got = delivered.setdefault(a.p.pid, set())
                    items = [(r + 1, c) for r, c in enumerate(a.ranked)
                             if a.p.utility(c) >= th and c not in got]
                    if items:
                        got.update(c for _r, c in items)
                nodes = list(range(self.n))
                while len(nodes) > 1:
                    nxt = []
                    for i in range(0, len(nodes), 2):
                        if i + 1 < len(nodes):
                            right = self.agents[nodes[i + 1]]
                            bb.counter.add("merge", 1, {"agg_entries": len(delivered[right.p.pid])})
                        nxt.append(nodes[i])
                    bb.phase()
                    nodes = nxt
                rounds += 1
                picked = self._pick(bb, delivered)
            if picked:
                bb.final_notice({"outcome": str(picked[0])})  # root → 전원 통지
                bb.phase()
                return self._result(bb, rounds, sweep, picked[0], picked[1], events)
        bb.final_notice({"outcome": NO_DEAL})
        bb.phase()
        return self._result(bb, rounds, self.max_sweeps, NO_DEAL, False, events)


def pair_partner(pids: list[str], pid: str) -> str | None:
    """방안 21의 레벨-0 짝 — CF 관점 필터에 사용."""
    idx = pids.index(pid)
    mate = idx + 1 if idx % 2 == 0 else idx - 1
    return pids[mate] if 0 <= mate < len(pids) else None


class Plan5Gossip(_StyleBase):
    """방안 5 — 가십 전파형 (Epidemic/P2P). 라운드마다 각자 자기 다음 순위 후보를 자기
    상태에 넣고(로컬), **딱 1명(라운드마다 순환하는 짝)에게 자기가 아는 전체 상태를 전송**
    (전송 N건/라운드 = 선형, 병렬 1 phase). 어느 노드든 자기 지식에서 전원 교집합을
    발견하면 확정을 방송한다. 유실된 가십은 다음 라운드의 다른 짝으로 자연 복구."""

    plan_name = "plan5gossip"

    def run(self, injector=None, kill_at=None, on_round_end=None) -> SessionResult:
        bb = Blackboard(n=self.n)
        events: list[dict] = []
        pids = [a.p.pid for a in self.agents]
        # knowledge[i] = 노드 i가 아는 {참여자: 제안 집합}
        knowledge = [{pid: set() for pid in pids} for _ in range(self.n)]
        self._knowledge_ref = knowledge  # RU 1인당 귀속 측정용 참조
        rounds = 0
        self._eval_calls = sum(len(a.ranked) for a in self.agents)
        max_rank = max(len(a.ranked) for a in self.agents)
        cap = self.max_sweeps * (max_rank + 20) * 3
        for sweep in range(1, self.max_sweeps + 1):
            for a in self.agents:
                a.ptr = 0
            flush = 0
            while rounds < cap:
                boundary = {"ptrs": [a.ptr for a in self.agents],
                            "know": [{k: set(v) for k, v in kn.items()} for kn in knowledge]}
                submitted, any_pending = {}, False
                for i, a in enumerate(self.agents):
                    c = a.peek(sweep)
                    if c is None:
                        continue
                    any_pending = True
                    knowledge[i][a.p.pid].add(c)  # 로컬 추가 — 전송 없음
                    submitted[a.p.pid] = c
                    a.ptr += 1
                if not any_pending:
                    flush += 1
                    if flush > self.n:  # 소진 후 전파 마무리 라운드까지 끝
                        break
                else:
                    flush = 0
                # 가십 교환: i → (i + 1 + r mod (N-1)) mod N, 전송 1건씩 (병렬)
                for i in range(self.n):
                    j = (i + 1 + (rounds % max(1, self.n - 1))) % self.n
                    size = sum(len(v) for v in knowledge[i].values())
                    bb.counter.add("gossip", 1, {"entries": size})
                    bb.load[pids[i]] = bb.load.get(pids[i], 0) + 1
                    if injector and injector.lost():
                        continue
                    for pid, s in knowledge[i].items():
                        knowledge[j][pid].update(s)
                bb.phase()
                rounds += 1
                if self.collect_log:
                    events.append({"t": "round", "sweep": sweep, "k": rounds, "submitted": submitted})
                if on_round_end:
                    on_round_end()
                try:
                    if kill_at and kill_at.round_no == rounds and kill_at.point == "mid_round":
                        raise _Kill()
                    picked = None
                    for kn in knowledge:  # 어느 노드든 전원 교집합을 알면 확정
                        if all(kn[pid] for pid in pids):
                            common = set.intersection(*kn.values())
                            if common:
                                tied = sorted(common, key=repr)
                                pick, extra = self.tie.pick(tied, self.profiles)
                                bb.tie_break_messages(extra, {"tied": [str(c) for c in tied]})
                                picked = (pick, len(tied) > 1)
                                break
                    if picked and kill_at and kill_at.round_no == rounds and kill_at.point == "pre_final":
                        raise _Kill()
                except _Kill:
                    for a, ptr in zip(self.agents, boundary["ptrs"]):
                        a.ptr = ptr
                    for kn, snap in zip(knowledge, boundary["know"]):
                        kn.clear(); kn.update({k: set(v) for k, v in snap.items()})
                    bb.resync({"sweep": sweep})  # 이웃에게서 상태 회수
                    kill_at = None
                    rounds -= 1
                    continue
                if picked:
                    bb.counter.add("final", self.n - 1, {"outcome": str(picked[0])})
                    bb.phase()
                    return self._result(bb, rounds, sweep, picked[0], picked[1], events)
        return self._result(bb, rounds, self.max_sweeps, NO_DEAL, False, events)


def tree_children(pids: list[str], pid: str) -> list[str]:
    """방안 6(계층 교집합)의 이진 트리 자식 — CF 관점 필터에 사용. 인덱스 i의 자식 = 2i+1, 2i+2."""
    i = pids.index(pid)
    return [pids[j] for j in (2 * i + 1, 2 * i + 2) if j < len(pids)]


class Plan6ITree(_StyleBase):
    """방안 6 — 계층 교집합형 (Hierarchical·점진 공개). 방안 2와 같은 합의 규칙
    (라운드 = 순위 순서 후보 1개 제출, 누적 집합의 전원 교집합 = 만장일치)을 유지하되,
    제출이 **직속 부모에게만** 전달되는 이진 트리(root = P0) 위에서 돈다.

    - 라운드마다 각자 다음 순위 후보 1개를 부모에게 전송, 부모는 자기 서브트리의
      **교집합 집계만** 위로 올린다 — 개별 후보를 보는 것은 직속 부모 1명뿐이고,
      조상·형제에게는 개인 귀속 없는 집계만 보인다 (CF 국소화).
    - 전송은 제출 발생 경로의 간선만 사용하고, 깊은 레벨부터 레벨당 병렬 1 phase
      (라운드당 phase ≈ 트리 깊이 — N=3이면 방안 2와 같은 1 phase).
    - 유실: 경로 위 어느 간선이든 유실되면 그 서브트리의 이번 제출은 미전달 —
      포인터가 안 움직여 다음 라운드 자동 재시도 (보수 모델).
    - 판정은 root의 전역 교집합 — 방안 2와 라운드 단위로 동일해 FC가 같다."""

    plan_name = "plan6itree"

    @staticmethod
    def _level(i: int) -> int:
        return (i + 1).bit_length() - 1

    def run(self, injector=None, kill_at=None, on_round_end=None) -> SessionResult:
        bb = Blackboard(n=self.n)
        events: list[dict] = []
        delivered: dict[str, set] = {}
        self._delivered_ref = delivered  # RU 1인당 귀속 측정용 참조
        rounds = 0
        self._eval_calls = sum(len(a.ranked) for a in self.agents)
        max_rank = max(len(a.ranked) for a in self.agents)
        cap = self.max_sweeps * (max_rank + 20) * 3
        for sweep in range(1, self.max_sweeps + 1):
            for a in self.agents:
                a.ptr = 0
            while rounds < cap:
                boundary = self._snapshot(delivered)
                pending: dict[int, object] = {}
                for i, a in enumerate(self.agents):
                    c = a.peek(sweep)
                    if c is not None:
                        pending[i] = c
                if not pending:
                    break
                # 상향 경로(제출 노드 → root)의 간선 합집합만 전송
                route: set[int] = set()
                for i in pending:
                    j = i
                    while j != 0:
                        route.add(j)
                        j = (j - 1) // 2
                lost: set[int] = set()
                for lvl in range(max((self._level(j) for j in route), default=0), 0, -1):
                    senders = [j for j in route if self._level(j) == lvl]
                    if not senders:
                        continue
                    for j in senders:
                        own = pending.get(j)
                        agg = len(delivered.get(self.agents[j].p.pid, ()))
                        payload = ({"candidate": str(own), "agg_entries": agg}
                                   if own is not None else {"agg_entries": agg})
                        bb.counter.add("up", 1, payload)
                        parent = self.agents[(j - 1) // 2]
                        bb.load[parent.p.pid] = bb.load.get(parent.p.pid, 0) + 1
                        if injector and injector.lost():
                            lost.add(j)
                    bb.phase()
                # 전달 확정: 경로에 유실이 없는 제출만 반영 (root 자신은 전송 없음)
                submitted = {}
                for i, c in pending.items():
                    j, blocked = i, False
                    while j != 0:
                        if j in lost:
                            blocked = True
                            break
                        j = (j - 1) // 2
                    if blocked:
                        continue
                    a = self.agents[i]
                    delivered.setdefault(a.p.pid, set()).add(c)
                    submitted[a.p.pid] = c
                    a.ptr += 1
                if self.n == 1 or not route:
                    bb.phase()  # 방어적 — 발생하지 않음 (root 단독)
                rounds += 1
                if self.collect_log:
                    events.append({"t": "round", "sweep": sweep, "k": rounds, "submitted": submitted})
                if on_round_end:
                    on_round_end()
                try:
                    if kill_at and kill_at.round_no == rounds and kill_at.point == "mid_round":
                        raise _Kill()
                    picked = self._pick(bb, delivered)  # root(P0)의 전역 교집합 판정
                    if picked and kill_at and kill_at.round_no == rounds and kill_at.point == "pre_final":
                        raise _Kill()
                except _Kill:
                    self._restore(delivered, boundary)
                    bb.resync({"sweep": sweep})  # 부모·자식에게서 상태 회수
                    kill_at = None
                    rounds -= 1
                    continue
                if picked:
                    bb.final_notice({"outcome": str(picked[0])})  # root → 전원 하향 통지
                    bb.phase()
                    return self._result(bb, rounds, sweep, picked[0], picked[1], events)
        bb.final_notice({"outcome": NO_DEAL})
        bb.phase()
        return self._result(bb, rounds, self.max_sweeps, NO_DEAL, False, events)


class Plan22Rotate(_StyleBase):
    """방안 22 — 순환 담당자형 (Blackboard 변형). 방안 20의 일괄 제출·중앙 선별을
    유지하되 **바퀴마다 담당자를 교대**한다 (바퀴 s의 담당 = P[(s-1) mod N]).
    부하·노출이 한 단말에 누적되지 않는다 — 어느 단말도 전 바퀴의 전체 목록을 모으지 못함."""

    plan_name = "plan22rotate"

    def run(self, injector=None, kill_at=None, on_round_end=None) -> SessionResult:
        bb = Blackboard(n=self.n)
        events: list[dict] = []
        delivered: dict[str, set] = {}
        self._delivered_ref = delivered  # RU 1인당 귀속 측정용 참조
        rounds = 0
        self._eval_calls = sum(len(a.ranked) for a in self.agents)
        for sweep in range(1, self.max_sweeps + 1):
            coord = (sweep - 1) % self.n
            self._coord_idx = coord  # RU 귀속: 현 바퀴 담당자
            boundary = self._snapshot(delivered)
            batch_log = {}
            for i, a in enumerate(self.agents):
                th = a.th.at_sweep(sweep)
                got = delivered.setdefault(a.p.pid, set())
                items = [(r + 1, c) for r, c in enumerate(a.ranked)
                         if a.p.utility(c) >= th and c not in got]
                if not items:
                    continue
                payload = [{"rank": r, "candidate": str(c)} for r, c in items]
                bb.submit(a.p.pid, i == coord, payload)  # 이번 바퀴 담당자에게 배치 제출
                if injector and injector.lost():
                    continue
                got.update(c for _r, c in items)
                batch_log[a.p.pid] = [(r, str(c)) for r, c in items]
            bb.phase()
            rounds += 1
            if self.collect_log:
                events.append({"t": "batch", "sweep": sweep, "k": rounds,
                               "coord": self.agents[coord].p.pid, "submitted": batch_log})
            if on_round_end:
                on_round_end()
            try:
                if kill_at and kill_at.round_no == rounds and kill_at.point == "mid_round":
                    raise _Kill()
                picked = self._pick(bb, delivered)
                if picked and kill_at and kill_at.round_no == rounds and kill_at.point == "pre_final":
                    raise _Kill()
            except _Kill:
                self._restore(delivered, boundary)
                bb.resync({"sweep": sweep})
                kill_at = None
                rounds -= 1
                continue
            if picked:
                bb.final_notice({"outcome": str(picked[0])})
                bb.phase()
                return self._result(bb, rounds, sweep, picked[0], picked[1], events)
        bb.final_notice({"outcome": NO_DEAL})
        bb.phase()
        return self._result(bb, rounds, self.max_sweeps, NO_DEAL, False, events)


def shard_owner(candidate, n: int) -> int:
    """방안 10(샤딩)의 후보→담당 노드 매핑 — 결정론 해시. CF 관점 필터와 공유."""
    import hashlib

    return int(hashlib.md5(repr(candidate).encode()).hexdigest(), 16) % n


def hcube_direct_peers(pids: list[str], pid: str) -> list[str]:
    """방안 8(하이퍼큐브)에서 개별 제출이 귀속으로 보이는 직접 짝 — CF 관점 필터용.

    차원 0 짝(i XOR 1)과 접기(fold) 짝(i±m)만 상대의 개별 상태를 식별 가능하게 받는다.
    이후 차원의 교환은 이미 혼합된 집계라 귀속이 없다.
    """
    n = len(pids)
    i = pids.index(pid)
    m = 1
    while m * 2 <= n:
        m *= 2
    r = n - m
    peers = []
    if i < m:
        j = i ^ 1
        if j < m:
            peers.append(pids[j])
        if i < r:
            peers.append(pids[m + i])  # fold 짝
    else:
        peers.append(pids[i - m])
    return peers


class Plan7RotCollect(_StyleBase):
    """방안 7 — 순환 수집형 (Rotating Collector·점진 공개). 방안 2의 규칙을 유지하되
    **라운드마다 수집자가 교대**한다 (라운드 k의 수집자 = P[(k-1) mod N]).

    - 각자 이번 순위 후보 1개를 그 라운드의 수집자에게 전송 (N-1건, 병렬 1 phase).
    - 수집자는 **후보별 계수(counter) 집계**를 유지·판정하고, 다음 수집자에게 계수만
      인계한다 (1건, 1 phase). 순위 순서 제출이라 각자 같은 후보를 두 번 내지 않으므로
      계수 = 제안한 사람 수 — 계수가 N이면 만장일치다 (개인 귀속 없는 집계).
    - 노출: 수집자는 **자기가 담당한 라운드의 개별 제출만** 본다 — 전량 노출 지점이
      시간 축으로 N등분된다. 방안 6과 달리 트리 깊이 비용이 없다 (라운드당 2 phase).
    - 유실: 제출 유실은 포인터 유지로 다음 라운드 재시도, 인계 유실은 즉시 재전송."""

    plan_name = "plan7rotc"

    def run(self, injector=None, kill_at=None, on_round_end=None) -> SessionResult:
        bb = Blackboard(n=self.n)
        events: list[dict] = []
        delivered: dict[str, set] = {}
        self._delivered_ref = delivered
        self._counts_ref = {}
        rounds = 0
        self._eval_calls = sum(len(a.ranked) for a in self.agents)
        max_rank = max(len(a.ranked) for a in self.agents)
        cap = self.max_sweeps * (max_rank + 20) * 3
        for sweep in range(1, self.max_sweeps + 1):
            for a in self.agents:
                a.ptr = 0
            while rounds < cap:
                boundary = self._snapshot(delivered)
                coord = rounds % self.n
                self._coord_idx = coord
                submitted, any_pending = {}, False
                for i, a in enumerate(self.agents):
                    c = a.peek(sweep)
                    if c is None:
                        continue
                    any_pending = True
                    if i != coord:
                        bb.counter.add("collect", 1, {"candidate": str(c)})
                        bb.load[self.agents[coord].p.pid] = bb.load.get(self.agents[coord].p.pid, 0) + 1
                        if injector and injector.lost():
                            continue  # 제출 유실 — 포인터 유지, 다음 라운드 재시도
                    delivered.setdefault(a.p.pid, set()).add(c)
                    submitted[a.p.pid] = c
                    a.ptr += 1
                if not any_pending:
                    break
                bb.phase()  # 제출
                # 인계: 계수 집계를 다음 수집자에게 (유실 시 즉시 재전송)
                counts: dict = {}
                for s_ in delivered.values():
                    for c_ in s_:
                        counts[c_] = counts.get(c_, 0) + 1
                self._counts_ref = counts
                while True:
                    bb.counter.add("handoff", 1, {"agg_entries": len(self._counts_ref)})
                    if not (injector and injector.lost()):
                        break
                bb.phase()  # 인계
                rounds += 1
                if self.collect_log:
                    events.append({"t": "round", "sweep": sweep, "k": rounds,
                                   "coord": self.agents[coord].p.pid, "submitted": submitted})
                if on_round_end:
                    on_round_end()
                try:
                    if kill_at and kill_at.round_no == rounds and kill_at.point == "mid_round":
                        raise _Kill()
                    picked = self._pick(bb, delivered)
                    if picked and kill_at and kill_at.round_no == rounds and kill_at.point == "pre_final":
                        raise _Kill()
                except _Kill:
                    self._restore(delivered, boundary)
                    bb.resync({"sweep": sweep})  # 직전 수집자의 계수 사본에서 복원
                    kill_at = None
                    rounds -= 1
                    continue
                if picked:
                    bb.final_notice({"outcome": str(picked[0])})
                    bb.phase()
                    return self._result(bb, rounds, sweep, picked[0], picked[1], events)
        bb.final_notice({"outcome": NO_DEAL})
        bb.phase()
        return self._result(bb, rounds, self.max_sweeps, NO_DEAL, False, events)


class Plan8Hypercube(_StyleBase):
    """방안 8 — 하이퍼큐브 전대칭 병합형 (All-reduce·점진 공개). 루트가 없다 — 라운드마다
    각자 이번 순위 후보를 자기 상태에 넣고(로컬), **하이퍼큐브 차원 순서의 짝 교환**으로
    전원이 동일한 집계(후보별 계수)에 도달한다. 전원이 같은 데이터를 보므로 로컬 판정이
    일치한다 (방안 3의 성질 + 트리의 병합 비용).

    - 비2의 거듭제곱 N: 초과 노드 r = N - 2^⌊log₂N⌋ 은 접기(fold)로 짝에게 합류 후
      마지막에 펼치기(unfold)로 결과를 받는다.
    - 라운드당: 전송 = r + m·log₂m + r 건, phase = log₂m + (r>0이면 2).
    - 노출: 차원 0 짝·fold 짝의 개별 상태만 귀속으로 보인다 — 이후 차원 교환은 혼합
      집계라 귀속이 없다 (방안 21의 짝 노출과 유사하되 전원 대칭·점진).
    - 대가: **전원이 집계 사본을 보유** — RU 합계가 mesh처럼 N배.
    - 유실: 교환 유실은 즉시 재전송(+1 phase) — 라운드 판정 시점은 유지."""

    plan_name = "plan8hcube"

    def run(self, injector=None, kill_at=None, on_round_end=None) -> SessionResult:
        bb = Blackboard(n=self.n)
        events: list[dict] = []
        delivered: dict[str, set] = {}
        self._delivered_ref = delivered
        rounds = 0
        self._eval_calls = sum(len(a.ranked) for a in self.agents)
        max_rank = max(len(a.ranked) for a in self.agents)
        cap = self.max_sweeps * (max_rank + 20) * 3
        m = 1
        while m * 2 <= self.n:
            m *= 2
        r = self.n - m
        dims = m.bit_length() - 1
        for sweep in range(1, self.max_sweeps + 1):
            for a in self.agents:
                a.ptr = 0
            while rounds < cap:
                boundary = self._snapshot(delivered)
                submitted, any_pending = {}, False
                for a in self.agents:
                    c = a.peek(sweep)
                    if c is None:
                        continue
                    any_pending = True
                    delivered.setdefault(a.p.pid, set()).add(c)  # 로컬 추가 — 전송 없음
                    submitted[a.p.pid] = c
                    a.ptr += 1
                if not any_pending:
                    break
                agg = sum(len(v) for v in delivered.values())

                def _xfer(count, tag):
                    for _ in range(count):
                        while True:
                            bb.counter.add(tag, 1, {"agg_entries": agg})
                            if not (injector and injector.lost()):
                                break
                            bb.phases += 1  # 유실 재전송
                    bb.phase()

                if r:
                    _xfer(r, "fold")
                for _d in range(dims):
                    _xfer(m, "hcube")
                if r:
                    _xfer(r, "unfold")
                rounds += 1
                if self.collect_log:
                    events.append({"t": "round", "sweep": sweep, "k": rounds, "submitted": submitted})
                if on_round_end:
                    on_round_end()
                try:
                    if kill_at and kill_at.round_no == rounds and kill_at.point == "mid_round":
                        raise _Kill()
                    picked = self._pick(bb, delivered)
                    if picked and kill_at and kill_at.round_no == rounds and kill_at.point == "pre_final":
                        raise _Kill()
                except _Kill:
                    self._restore(delivered, boundary)
                    bb.resync({"sweep": sweep})  # 아무 짝에게서든 집계 회수 (전원 사본)
                    kill_at = None
                    rounds -= 1
                    continue
                if picked:
                    return self._result(bb, rounds, sweep, picked[0], picked[1], events)
        return self._result(bb, rounds, self.max_sweeps, NO_DEAL, False, events)


class Plan9Psi(_StyleBase):
    """방안 9 — 비공개 교집합형 (P2P + PSI, 암호 스텁·점진 공개). 노출의 이론적 최소를
    노린 극한 steelman — **합의 성립 순간까지 그 누구도 남의 후보를 하나도 보지 못한다.**

    - 라운드마다 각자 이번 순위 후보를 자기 비공개 집합에 넣고, 쌍별 DH-블라인딩
      원소 교환으로 전원 교집합의 존재만 공동 판정한다 (교집합 원소는 성립 시에만 공개).
    - 정보 모델만 시뮬레이션한다: 암호 연산은 스텁, 비용은 상수로 계상 —
      블라인딩 원소 1건 = 64 bytes (잠정), 라운드당 전송 N(N-1)건 · 2 phase(교환+확인).
    - 후보 공간이 유한·열거 가능하므로 단순 해시는 브루트포스에 뚫린다 — 실제 구현은
      상호 블라인딩 PSI가 필수라는 전제를 51 문서에 명시한다.
    - 동률 해소: 성립 시 공개된 동률 후보에 한해 순위를 조회한다 (누설 범위 = 동률 집합).
    - 유실: 쌍별 재전송(ack 전제 — 추가 전송으로 계상, phase 유지)."""

    plan_name = "plan9psi"
    BLIND_BYTES = 64  # 잠정 상수 — DH 블라인딩 원소 크기

    def run(self, injector=None, kill_at=None, on_round_end=None) -> SessionResult:
        bb = Blackboard(n=self.n)
        events: list[dict] = []
        delivered: dict[str, set] = {}
        self._delivered_ref = delivered
        rounds = 0
        self._eval_calls = sum(len(a.ranked) for a in self.agents)
        max_rank = max(len(a.ranked) for a in self.agents)
        cap = self.max_sweeps * (max_rank + 20) * 3
        blob = "x" * self.BLIND_BYTES
        for sweep in range(1, self.max_sweeps + 1):
            for a in self.agents:
                a.ptr = 0
            while rounds < cap:
                boundary = self._snapshot(delivered)
                submitted, any_pending = {}, False
                for a in self.agents:
                    c = a.peek(sweep)
                    if c is None:
                        continue
                    any_pending = True
                    delivered.setdefault(a.p.pid, set()).add(c)  # 비공개 로컬 집합
                    submitted[a.p.pid] = c
                    a.ptr += 1
                if not any_pending:
                    break
                # 쌍별 블라인딩 델타 교환 (신규 원소 1건씩) — 유실은 즉시 재전송
                for a in self.agents:
                    for _peer in range(self.n - 1):
                        while True:
                            bb.counter.add("psi", 1, {"blind": blob})
                            if not (injector and injector.lost()):
                                break
                    bb.load[a.p.pid] = bb.load.get(a.p.pid, 0) + self.n - 1
                bb.phase()  # 교환
                bb.phase()  # 교집합 존재 확인 (응답)
                rounds += 1
                if self.collect_log:
                    events.append({"t": "round", "sweep": sweep, "k": rounds, "submitted": submitted})
                if on_round_end:
                    on_round_end()
                try:
                    if kill_at and kill_at.round_no == rounds and kill_at.point == "mid_round":
                        raise _Kill()
                    picked = self._pick(bb, delivered)
                    if picked and kill_at and kill_at.round_no == rounds and kill_at.point == "pre_final":
                        raise _Kill()
                except _Kill:
                    self._restore(delivered, boundary)
                    bb.resync({"sweep": sweep})  # 자기 비공개 집합은 로컬 저장 — 재교환만
                    kill_at = None
                    rounds -= 1
                    continue
                if picked:
                    bb.final_notice({"outcome": str(picked[0])})
                    bb.phase()
                    return self._result(bb, rounds, sweep, picked[0], picked[1], events)
        bb.final_notice({"outcome": NO_DEAL})
        bb.phase()
        return self._result(bb, rounds, self.max_sweeps, NO_DEAL, False, events)


class Plan10Shard(_StyleBase):
    """방안 10 — 내용 주소 샤딩형 (DHT/Content-addressed·점진 공개). 후보 자체를 주소로
    쓴다 — 라운드마다 각자 이번 순위 후보를 **그 후보의 샤드 담당 노드**(결정론 해시)에게
    보낸다 (1건, 병렬 1 phase). 담당 노드는 후보별 계수를 유지하고, 순위 순서 제출의
    무중복 성질 덕에 계수 = 제안자 수 — 계수가 N이 되는 순간 만장일치를 방송한다.

    - 노출: 각 노드가 보는 것은 전체 제출 중 **자기 샤드로 해시되는 약 1/N 조각**뿐 —
      전량 노출 지점이 내용 축으로 N등분된다 (방안 7은 시간 축, 방안 6은 트리 축).
    - phase가 방안 2와 같은 라운드당 1 — 트리 깊이·인계 비용이 없다.
    - 대가: 노출 조각에 개인 귀속이 있고, 샤드 담당의 이탈이 그 샤드 후보의 판정을
      지연시킨다 (FT — 재배치 프로토콜은 범위 밖 명시).
    - 유실: 제출 유실은 포인터 유지로 다음 라운드 재시도."""

    plan_name = "plan10shard"

    def run(self, injector=None, kill_at=None, on_round_end=None) -> SessionResult:
        bb = Blackboard(n=self.n)
        events: list[dict] = []
        delivered: dict[str, set] = {}
        self._delivered_ref = delivered
        rounds = 0
        self._eval_calls = sum(len(a.ranked) for a in self.agents)
        max_rank = max(len(a.ranked) for a in self.agents)
        cap = self.max_sweeps * (max_rank + 20) * 3
        for sweep in range(1, self.max_sweeps + 1):
            for a in self.agents:
                a.ptr = 0
            while rounds < cap:
                boundary = self._snapshot(delivered)
                submitted, any_pending = {}, False
                for i, a in enumerate(self.agents):
                    c = a.peek(sweep)
                    if c is None:
                        continue
                    any_pending = True
                    owner = shard_owner(c, self.n)
                    if owner != i:
                        bb.counter.add("shard", 1, {"candidate": str(c)})
                        bb.load[self.agents[owner].p.pid] = bb.load.get(self.agents[owner].p.pid, 0) + 1
                        if injector and injector.lost():
                            continue  # 유실 — 포인터 유지, 다음 라운드 재시도
                    delivered.setdefault(a.p.pid, set()).add(c)
                    submitted[a.p.pid] = c
                    a.ptr += 1
                if not any_pending:
                    break
                bb.phase()
                rounds += 1
                if self.collect_log:
                    events.append({"t": "round", "sweep": sweep, "k": rounds, "submitted": submitted})
                if on_round_end:
                    on_round_end()
                try:
                    if kill_at and kill_at.round_no == rounds and kill_at.point == "mid_round":
                        raise _Kill()
                    picked = self._pick(bb, delivered)
                    if picked and kill_at and kill_at.round_no == rounds and kill_at.point == "pre_final":
                        raise _Kill()
                except _Kill:
                    self._restore(delivered, boundary)
                    bb.resync({"sweep": sweep})  # 샤드 계수는 제출자들의 재전송으로 재구성
                    kill_at = None
                    rounds -= 1
                    continue
                if picked:
                    bb.final_notice({"outcome": str(picked[0])})
                    bb.phase()
                    return self._result(bb, rounds, sweep, picked[0], picked[1], events)
        bb.final_notice({"outcome": NO_DEAL})
        bb.phase()
        return self._result(bb, rounds, self.max_sweeps, NO_DEAL, False, events)
