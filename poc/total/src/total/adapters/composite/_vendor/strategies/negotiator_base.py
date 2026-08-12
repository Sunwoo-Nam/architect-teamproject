"""후보 목록 기반 SAO 협상자 공통 골격 — baseline(전수)과 2안(압축 풀)이 공유한다.

차이는 `_build_candidates()`(후보를 어떻게 만드나)와 `_replenish()`(소진 시 확장)뿐이다.
수락 규칙: 상대 offer가 자기 기준(공유 규칙 + 자기 하드)에 유효하고, 자기 효용이
양보선(1.0 → initial_threshold, boulware) 이상이면 수락 — 바닥선 밑 수락은 구조적으로 불가(24.7 FR).
모든 제안·응답은 EventLog에 효용·양보선·사유와 함께 기록된다.
"""
from __future__ import annotations

from negmas.sao import ResponseType, SAONegotiator, SAOState

from total.adapters.composite._vendor.harness.beliefs import AgentBeliefs
from total.adapters.composite._vendor.harness.comms import Comms
from total.adapters.composite._vendor.harness.eventlog import EventLog
from total.adapters.composite._vendor.harness.negmas_bridge import TupleCodec, aspiration


class CandidateNegotiator(SAONegotiator):
    def __init__(
        self,
        beliefs: AgentBeliefs,
        codec: TupleCodec,
        n_steps: int,
        name: str,
        log: EventLog | None = None,
        comms: Comms | None = None,
    ):
        super().__init__(name=name)
        self.beliefs = beliefs
        self.codec = codec
        self.n_steps = n_steps
        self.eventlog = log
        self.comms = comms
        self.proposal_count = 0
        self.response_count = 0
        self._offered: set[tuple] = set()
        self._candidates: list[tuple[float, tuple]] | None = None  # (내 효용, offer 튜플) 내림차순
        # [이식 시 신설] 관찰 기록의 행위자 식별자 — CF 측정이 누가 무엇을 보냈는지 알아야 한다
        self._pid = f"P{beliefs.idx}"

    def _log(self, kind: str, **fields) -> None:
        if self.eventlog is not None:
            self.eventlog.log(kind, agent=self.beliefs.idx, **fields)

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
            self._log(
                "candidates_built",
                pool_size=len(self._candidates),
                best_utility=round(self._candidates[0][0], 4) if self._candidates else None,
                worst_utility=round(self._candidates[-1][0], 4) if self._candidates else None,
            )
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
                    if self.comms:
                        self.comms.proposal_sent(offer, self._pid)
                    self._log("propose", step=state.step, offer=offer, my_utility=round(utility, 4),
                              threshold=round(thr, 4), reason="양보선 이상 미제안 후보 중 최선")
                    return offer
            # 확장 조건: 풀이 비었거나, 양보선이 풀 하한 아래로 내려감
            # (= 내 양보 수준이 풀 전체보다 낮아졌는데도 합의가 없다 → 풀이 좁다)
            pool_min = candidates[-1][0] if candidates else None
            if (pool_min is None or thr < pool_min) and self._replenish():
                continue
            break
        # 확장 없이 버티는 구간 — 최선안을 반복 제안
        candidates = self._ensure()
        if candidates:
            utility, offer = candidates[0]
            if self.comms:
                self.comms.proposal_sent(offer, self._pid)
            self._log("propose", step=state.step, offer=offer, my_utility=round(utility, 4),
                      threshold=round(thr, 4), reason="새 후보 없음 — 최선안 반복 제안")
            return offer
        self._log("propose", step=state.step, offer=None, threshold=round(thr, 4),
                  reason="제안 가능 후보 없음")
        return None

    def respond(self, state: SAOState, source: str | None = None) -> ResponseType:
        self.response_count += 1
        offer = state.current_offer
        if offer is None:
            return ResponseType.REJECT_OFFER
        outcome = self.codec.to_outcome(tuple(offer))
        thr = aspiration(state.step, self.n_steps, self.beliefs.initial_threshold)
        if not self.beliefs.feasible(outcome):
            self._log("respond", step=state.step, offer=tuple(offer), decision="REJECT",
                      threshold=round(thr, 4), reason="내 하드 제약(또는 공유 규칙) 위반")
            return ResponseType.REJECT_OFFER
        utility = self.beliefs.utility(outcome)
        if utility >= thr:
            if self.comms:
                self.comms.accept_sent(tuple(offer), self._pid)
            self._log("respond", step=state.step, offer=tuple(offer), decision="ACCEPT",
                      my_utility=round(utility, 4), threshold=round(thr, 4),
                      reason="내 효용 ≥ 양보선")
            return ResponseType.ACCEPT_OFFER
        self._log("respond", step=state.step, offer=tuple(offer), decision="REJECT",
                  my_utility=round(utility, 4), threshold=round(thr, 4),
                  reason="내 효용 < 양보선")
        return ResponseType.REJECT_OFFER
