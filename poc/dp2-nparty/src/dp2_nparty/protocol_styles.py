"""Blackboard 외 아키텍처 스타일의 방안들 (51 §4-2/4-3/4-4).

공통 유지: 순위 순서 제출·바퀴별 threshold 인하·만장일치(교집합)·순위합 최소 선별·
최대 5바퀴 NO_DEAL. 다른 것은 **통신·상태의 구조**다:

- Plan3Mesh  (P2P 브로드캐스트): 중앙 없음 — 전원이 전원에게 방송, 각자 로컬 판정
- Plan4Ring  (Pipeline/token):  협상 문서가 고리를 순회 — 문서가 곧 상태, 홉마다 직렬
- Plan11Tree  (Hierarchical):   쌍별 수락 집합을 트리로 병합 — 상위엔 개인 귀속 없는 집계만

Blackboard 객체는 여기서 공유 저장소가 아니라 **계측기**(메시지·바이트·phase·부하)로만 쓴다.
"""
from __future__ import annotations

from .blackboard import Blackboard
from .domain import NO_DEAL, SessionResult
from .protocol import MAX_SWEEPS, _Agent, _Kill, KillAt
from .tiebreak import RankSumThenStdThenRunoff, TieBreaker


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


class Plan3Mesh(_StyleBase):
    """방안 3 — 전원 브로드캐스트 분산형 (P2P). 라운드마다 각자 순위 순서 후보 1개를
    전원에게 방송(전송 N-1건, 병렬 1 phase). 전원이 같은 데이터를 보므로 로컬 판정이
    결정적으로 일치한다 — 별도 성립 통지가 없다. 유실된 방송은 다음 라운드 재시도."""

    plan_name = "plan3mesh"

    def run(self, injector=None, kill_at=None, on_round_end=None) -> SessionResult:
        bb = Blackboard(n=self.n)
        events: list[dict] = []
        delivered: dict[str, set] = {}
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


class Plan11Tree(_StyleBase):
    """방안 11 — 계층 병합형 (Hierarchical). 바퀴마다: 각자 threshold 이상 미전달 후보를
    배치로 준비 → 쌍(pair)의 오른쪽이 왼쪽 리더에게 전송(레벨당 병렬 1 phase) → 리더가
    교집합·순위합을 병합해 위로 — 트리 꼭대기(root = P0)에서 전역 교집합 판정, 결과를
    전원에 통지(1 phase, N-1건). 상위 계층에는 개인 귀속 없는 집계만 올라간다."""

    plan_name = "plan11tree"

    def run(self, injector=None, kill_at=None, on_round_end=None) -> SessionResult:
        import math

        bb = Blackboard(n=self.n)
        events: list[dict] = []
        delivered: dict[str, set] = {}
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
    """방안 11의 레벨-0 짝 — CF 관점 필터에 사용."""
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


class Plan12Rotate(_StyleBase):
    """방안 12 — 순환 담당자형 (Blackboard 변형). 방안 10의 일괄 제출·중앙 선별을
    유지하되 **바퀴마다 담당자를 교대**한다 (바퀴 s의 담당 = P[(s-1) mod N]).
    부하·노출이 한 단말에 누적되지 않는다 — 어느 단말도 전 바퀴의 전체 목록을 모으지 못함."""

    plan_name = "plan12rotate"

    def run(self, injector=None, kill_at=None, on_round_end=None) -> SessionResult:
        bb = Blackboard(n=self.n)
        events: list[dict] = []
        delivered: dict[str, set] = {}
        rounds = 0
        self._eval_calls = sum(len(a.ranked) for a in self.agents)
        for sweep in range(1, self.max_sweeps + 1):
            coord = (sweep - 1) % self.n
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
