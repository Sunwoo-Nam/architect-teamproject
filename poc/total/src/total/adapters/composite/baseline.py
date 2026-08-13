"""[24 §4] TB baseline — naive 2인 SAO(전 조합 순위 교대 제안)의 T를 열거 없이 계산.

판정 지표 ρ = T(제안 설계) ÷ T(naive baseline)의 분모를 만든다 (PL 확정 2026-08-13).
- eval 항 = N×S (S = 축별 값 수의 곱 — 해석적, 열거 불필요)
- 합의 시점 k* = lazy k-best 힙 탐색 (soft 감점은 admissible 가산 상한 + 정확 순서 버퍼)
- 벽시계 상한 도달 시 T는 하한(capped=True) → ρ는 상한 — 별점은 보수 방향으로 항상 판정 가능
- threshold·바퀴 tactic은 설계와 동일 (PolyAspiration boulware · [initial, own_max] · 5바퀴)
"""
from __future__ import annotations

import heapq
import time
from pathlib import Path

from negmas.negotiators.helpers import PolyAspiration

from ...qa.constants import SYNTH_TIME
from ._vendor.common.profiles import build_truth_profiles, truth_utility
from ._vendor.common.rules import (
    Outcome, build_hard_rules, build_participant_hard_for, build_soft_rules,
)
from ._vendor.common.scenario import load_scenario

MAX_SWEEPS = 5
POP_CAP = 2_000_000
WALL_CAP_S = 30.0


class LazyRank:
    """참여자 1인의 효용 내림차순 순위표를 필요한 만큼만 생성 (열거 없음).

    상태 = 축별 값 인덱스 튜플. UB = 가중치×점수 합(soft 감점 전). 감점 ≥ 0이므로
    UB는 admissible — 버퍼의 확정 효용이 힙 상단 UB 이상이 될 때만 방출하면 정확 순서다.
    """

    def __init__(self, scenario, truth, p_idx, soft_rules, hard_ok):
        self.scenario = scenario
        self.truth = truth
        self.p_idx = p_idx
        self.soft = soft_rules
        self.hard_ok = hard_ok
        self.axes = [a.name for a in scenario.axes]
        # 축별 값을 이 참여자의 기여(가중치×점수) 내림차순으로
        self.vals = []
        for a in scenario.axes:
            w = truth.weights[a.name]
            ordered = sorted(a.values, key=lambda v: -w * truth.scores[a.name][v.name])
            self.vals.append(ordered)
        self.contrib = [
            [truth.weights[a.name] * truth.scores[a.name][v.name] for v in vs]
            for a, vs in zip(scenario.axes, self.vals)
        ]
        top_ub = sum(c[0] for c in self.contrib)
        self.heap = [(-top_ub, (0,) * len(self.axes))]
        self.seen = {(0,) * len(self.axes)}
        self.buffer: list[tuple[float, tuple]] = []  # 최대힙: (-확정 효용, 상태)
        self.pops = 0
        self.emitted: list[tuple[float, object]] = []  # 방출 접두 캐시 — 바퀴 간 공유

    def _outcome(self, state) -> Outcome:
        return Outcome({a: self.vals[i][j] for i, (a, j) in enumerate(zip(self.axes, state))})

    def _exact(self, state) -> float:
        return truth_utility(self.truth, self.p_idx, self._outcome(state), self.soft)

    def get(self, rank_idx: int):
        """rank_idx번째(0-기반) 순위 후보 — 방출 접두 캐시 재사용, 부족하면 확장."""
        while len(self.emitted) <= rank_idx:
            nxt = self._advance()
            if nxt is None:
                return None
            self.emitted.append(nxt)
        return self.emitted[rank_idx]

    def _advance(self):
        while True:
            top_ub = -self.heap[0][0] if self.heap else float("-inf")
            if self.buffer and -self.buffer[0][0] >= top_ub - 1e-12:
                negu, state = heapq.heappop(self.buffer)
                return -negu, self._outcome(state)
            if not self.heap:
                return None
            if self.pops >= POP_CAP:
                raise RuntimeError(f"POP_CAP {POP_CAP} 도달")
            _negub, state = heapq.heappop(self.heap)
            self.pops += 1
            for i in range(len(state)):
                if state[i] + 1 < len(self.vals[i]):
                    nxt = state[:i] + (state[i] + 1,) + state[i + 1:]
                    if nxt not in self.seen:
                        self.seen.add(nxt)
                        ub = sum(self.contrib[k][nxt[k]] for k in range(len(nxt)))
                        heapq.heappush(self.heap, (-ub, nxt))
            out = self._outcome(state)
            if self.hard_ok(out):
                heapq.heappush(self.buffer, (-self._exact(state), state))


def baseline_t(scenario_or_path) -> dict:
    scenario = (scenario_or_path if hasattr(scenario_or_path, "axes")
                else load_scenario(scenario_or_path))
    truths = build_truth_profiles(scenario)[:2]
    soft = build_soft_rules(scenario, [t.home_region for t in truths])
    hard = build_hard_rules(scenario)
    p_hard = [build_participant_hard_for(scenario, i) for i in range(2)]

    def hard_ok_for(i):
        def ok(o: Outcome) -> bool:
            return all(r(o) for r in hard) and all(r(o) for r in p_hard[i])
        return ok

    S = 1
    for a in scenario.axes:
        S *= len(a.values)

    asp = PolyAspiration(max_aspiration=1.0, aspiration_type="boulware")

    def threshold(truth, own_max, sweep):
        if MAX_SWEEPS <= 1:
            return truth.initial_threshold
        t = min(1.0, max(0.0, (sweep - 1) / (MAX_SWEEPS - 1)))
        frac = asp.utility_at(t)
        return max(truth.initial_threshold,
                   truth.initial_threshold + (own_max - truth.initial_threshold) * frac)

    t_start = time.time()
    ranks = [LazyRank(scenario, truths[i], i, soft, hard_ok_for(i)) for i in range(2)]
    own_max = []
    for i in range(2):
        first = ranks[i].get(0)
        own_max.append(first[0] if first else truths[i].initial_threshold)
    proposals = 0
    agreed = None
    capped = False
    try:
        for sweep in range(1, MAX_SWEEPS + 1):
            ptr = [0, 0]
            exhausted = [False, False]
            turn = 0
            while not (exhausted[0] and exhausted[1]):
                if time.time() - t_start > WALL_CAP_S:
                    raise RuntimeError("WALL_CAP")
                i, j = turn % 2, 1 - (turn % 2)
                turn += 1
                if exhausted[i]:
                    continue
                item = ranks[i].get(ptr[i])
                if item is None:
                    exhausted[i] = True
                    continue
                u_own, outcome = item
                if u_own < threshold(truths[i], own_max[i], sweep):
                    exhausted[i] = True
                    continue
                ptr[i] += 1
                proposals += 1
                u_resp = truth_utility(truths[j], j, outcome, soft)
                if all(r(outcome) for r in p_hard[j]) and \
                        u_resp >= threshold(truths[j], own_max[j], sweep):
                    agreed = outcome
                    break
            if agreed is not None:
                break
    except RuntimeError:
        capped = True  # 상한 도달 — 이하 T는 하한(≥)이고, ρ 상한으로 보수 판정 가능
    pops_total = ranks[0].pops + ranks[1].pops

    c = SYNTH_TIME
    phases = 2 * proposals + (1 if agreed is not None else 0)
    bytes_total = proposals * 24 * max(1, len(scenario.axes))  # 제안 페이로드 근사 + 회신
    eval_naive = 2 * S  # naive 정의: 전 조합 순위화 (N×S) — 해석적 계수
    t_phase = phases * c.t_phase_ms
    t_eval = eval_naive / 2 * c.t_eval_ms
    t_transfer = bytes_total / c.bw_bytes_per_s * 1000
    return {
        "scenario": getattr(scenario, "id", "?"), "axes": len(scenario.axes), "S": S,
        "capped": capped,
        "agreed": agreed is not None, "proposals_k*": proposals,
        "lazy_pops": pops_total,
        "T_ms": round(t_phase + t_eval + t_transfer, 1),
        "phase_ms": round(t_phase, 1), "eval_ms": round(t_eval, 1),
        "transfer_ms": round(t_transfer, 3),
    }


