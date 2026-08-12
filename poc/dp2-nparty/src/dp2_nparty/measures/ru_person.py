"""[24 §2] RU 1인당 귀속 측정 — 프로토콜 상태의 논리 크기(deep size)를 보유 구조대로 귀속.

프로세스 tracemalloc 합계는 시뮬레이션이 상태를 1부만 들고 있어 복제 구조(mesh 등)의
비용을 과소계상한다. 여기서는 **누가 무엇을 들고 있는가**를 방안별 보유 모델대로 귀속해
(1) 최대 부하 단말과 (2) 전원 합계(복제 반영)를 계산한다. 공통 기저(각자 자기 순위표)는
전 방안 동일이므로 제외하고 **프로토콜 상태만** 잰다 — 방안 간 차이가 나는 부분이다.

귀속 모델 (PL 승인 2026-08-11):
- plan1 / plan2 / plan20batch: 담당자 P0가 누적 제안 집합 전체 보유, 일반 참여자 ≈ 0
- plan1a: 담당자 P0가 **이번 라운드의 carried 후보 목록만** 보유 — 라운드별 판정이라
  과거 상태 불필요 (누적 보유 제거: PL 지시 2026-08-12,
   방안 1과 나란히 비교하기 위해 같은 보수 모델을 쓴다)
- plan22rotate: 현 바퀴 담당자가 누적 전체 보유로 **보수 계상** (스펙상 요약 인계면 더 작음)
- plan3mesh: 전원이 누적 집합 전체를 복제 보유 → 합계 = 1부의 N배
- plan4ring: 문서 1부 = 현재 보유자 귀속 (백업 사본은 계상하지 않음 — 명시적 제외)
- plan5gossip: 노드별 knowledge를 실측 그대로
- plan6itree: 각 노드가 자기 서브트리의 누적 집합(개인 귀속 포함) 보유 — root가 전체
- plan21tree: 병합 리더가 흡수한 그룹의 합집합(개인 귀속 없는 집계) 보유 — root가 전체
"""
from __future__ import annotations

import sys


def deep_size(obj, _seen: set | None = None) -> int:
    if _seen is None:
        _seen = set()
    oid = id(obj)
    if oid in _seen:
        return 0
    _seen.add(oid)
    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        for k, v in obj.items():
            size += deep_size(k, _seen) + deep_size(v, _seen)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for it in obj:
            size += deep_size(it, _seen)
    return size


def _delivered_map(plan) -> dict:
    d = getattr(plan, "_delivered_ref", None)
    if d is not None:
        return d
    bb = getattr(plan, "_bb_ref", None)
    return bb.proposed_by if bb is not None else {}


def _subtree(i: int, n: int) -> list[int]:
    out, stack = [], [i]
    while stack:
        j = stack.pop()
        out.append(j)
        for c in (2 * j + 1, 2 * j + 2):
            if c < n:
                stack.append(c)
    return out


def _merge_groups(n: int) -> list[list[int]]:
    """plan21tree의 최종 병합 그룹 — index별로 자기가 리더로서 흡수한 구성원 목록."""
    members = {i: [i] for i in range(n)}
    nodes = list(range(n))
    while len(nodes) > 1:
        nxt = []
        for i in range(0, len(nodes), 2):
            if i + 1 < len(nodes):
                members[nodes[i]] = members[nodes[i]] + members[nodes[i + 1]]
            nxt.append(nodes[i])
        nodes = nxt
    return [members[i] for i in range(n)]


def holder_sizes(plan) -> list[int]:
    """참여자 인덱스별 프로토콜 상태 bytes (모듈 docstring의 귀속 모델)."""
    n = plan.n
    name = plan.plan_name
    if name == "plan5gossip":
        return [deep_size(k) for k in getattr(plan, "_knowledge_ref", [{}] * n)]
    d = _delivered_map(plan)
    pid_of = [a.p.pid for a in plan.agents]
    per = [0] * n
    if name in ("plan1", "plan2", "plan20batch"):
        per[0] = deep_size(d)
    elif name == "plan1a":
        per[0] = deep_size(getattr(plan, "_carried_ref", {}))  # 라운드 국소 O(N)
    elif name == "plan22rotate":
        per[getattr(plan, "_coord_idx", 0)] = deep_size(d)
    elif name == "plan3mesh":
        s = deep_size(d)
        per = [s] * n
    elif name == "plan4ring":
        per[0] = deep_size(d)
    elif name == "plan6itree":
        for i in range(n):
            sub = _subtree(i, n)
            per[i] = deep_size({pid_of[j]: d.get(pid_of[j], set()) for j in sub})
    elif name == "plan21tree":
        for i, grp in enumerate(_merge_groups(n)):
            agg = set()
            for j in grp:
                agg |= d.get(pid_of[j], set())
            per[i] = deep_size(agg)
    elif name == "plan7rotc":
        per[getattr(plan, "_coord_idx", 0)] = deep_size(getattr(plan, "_counts_ref", {}))
    elif name == "plan8hcube":
        counts: dict = {}
        for s_ in d.values():
            for c_ in s_:
                counts[c_] = counts.get(c_, 0) + 1
        sz = deep_size(counts)
        per = [sz] * n  # all-reduce — 전원이 집계 사본 보유
    elif name == "plan9psi":
        blind = getattr(plan, "BLIND_BYTES", 64)
        total = sum(len(s) for s in d.values())
        for i, pid in enumerate(pid_of):
            own = d.get(pid, set())
            per[i] = deep_size(own) + blind * (total - len(own))  # 남의 원소는 블라인딩 blob로 보유
    elif name == "plan10shard":
        from ..protocol_styles import shard_owner

        shards: list[dict] = [{} for _ in range(n)]
        for s_ in d.values():
            for c_ in s_:
                sh = shards[shard_owner(c_, n)]
                sh[c_] = sh.get(c_, 0) + 1
        per = [deep_size(sh) for sh in shards]
    else:  # 미등록 방안 — 보수적으로 담당자 전체 보유 취급
        per[0] = deep_size(d)
    return per
