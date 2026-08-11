"""후보 목록 기반 SAO 협상자 공통 골격 — baseline(전수)과 2안(압축 풀)이 공유한다.

차이는 `_build_candidates()`(후보를 어떻게 만드나)와 `_replenish()`(소진 시 확장)뿐이다.
수락 규칙: 상대 offer가 자기 기준(공유 규칙 + 자기 하드)에 유효하고, 자기 효용이
양보선(1.0 → initial_threshold, boulware) 이상이면 수락 — 바닥선 밑 수락은 구조적으로 불가(24.7 FR).
"""
from __future__ import annotations

from negmas.sao import ResponseType, SAONegotiator, SAOState

from dpca.harness.beliefs import AgentBeliefs
from dpca.harness.negmas_bridge import TupleCodec, aspiration


class CandidateNegotiator(SAONegotiator):
    def __init__(self, beliefs: AgentBeliefs, codec: TupleCodec, n_steps: int, name: str):
        super().__init__(name=name)
        self.beliefs = beliefs
        self.codec = codec
        self.n_steps = n_steps
        self.proposal_count = 0
        self.response_count = 0
        self._offered: set[tuple] = set()
        self._candidates: list[tuple[float, tuple]] | None = None  # (내 효용, offer 튜플) 내림차순

    # --- 전략별로 구현 ---
    def _build_candidates(self) -> list[tuple[float, tuple]]:
        raise NotImplementedError

    def _replenish(self) -> bool:
        """제안할 후보가 소진됐을 때 확장 시도. 확장했으면 True (2안 deepening 지점)."""
        return False

    # --- SAO 훅 ---
    def _ensure(self) -> list[tuple[float, tuple]]:
        if self._candidates is None:
            self._candidates = self._build_candidates()
        return self._candidates

    def propose(self, state: SAOState, dest: str | None = None):
        self.proposal_count += 1
        thr = aspiration(state.step, self.n_steps, self.beliefs.initial_threshold)
        while True:
            candidates = self._ensure()
            for utility, offer in candidates:
                if utility < thr:
                    break  # 내림차순이라 이후는 전부 양보선 미만
                if offer not in self._offered:
                    self._offered.add(offer)
                    return offer
            # 확장 조건: 풀이 비었거나, 양보선이 풀 하한 아래로 내려감
            # (= 내 양보 수준이 풀 전체보다 낮아졌는데도 합의가 없다 → 풀이 좁다)
            pool_min = candidates[-1][0] if candidates else None
            if (pool_min is None or thr < pool_min) and self._replenish():
                continue
            break
        # 확장 없이 버티는 구간 — 양보선 이상 최선안을 반복 제안 (없으면 자기 최선안)
        candidates = self._ensure()
        if candidates:
            return candidates[0][1]
        return None

    def respond(self, state: SAOState, source: str | None = None) -> ResponseType:
        self.response_count += 1
        offer = state.current_offer
        if offer is None:
            return ResponseType.REJECT_OFFER
        outcome = self.codec.to_outcome(tuple(offer))
        if not self.beliefs.feasible(outcome):
            return ResponseType.REJECT_OFFER
        thr = aspiration(state.step, self.n_steps, self.beliefs.initial_threshold)
        if self.beliefs.utility(outcome) >= thr:
            return ResponseType.ACCEPT_OFFER
        return ResponseType.REJECT_OFFER
