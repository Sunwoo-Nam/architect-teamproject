"""composite 보완 택틱 — vendor 불변의 어댑터 계층 변형 (65 문서, PL 채택분).

62의 nparty `tactics.py`와 같은 원칙: 프로토콜(vendor)은 건드리지 않고 전략
서브클래스로 변형하며, 측정 하니스는 `--plans` 확장만으로 동일 조건 비교한다.

현재 등록: **P6 k 비대칭 배분** (`poolka`) — PL 채택 2026-08-14 ("방안 2의 문제는
RU다 — 얼마나 개선되는지 측정하라").

## P6의 문제 의식 (63 실측)

정본 pool은 전 축 동일 k(시작 2)로 풀 kⁿ을 실물화하고, 막히면 **전역 k+1 →
전 축 재압축**한다. 축이 20개면 풀이 2^20 = 100만 조합이고, 심화 한 번에
(3/2)^20 ≈ 3,300배로 자란다 — 63 실측의 한도 초과 11건·극단 r 3,692%(4.7GB)의
직접 원인이다. 그런데 가중치가 낮은 축은 k=1이어도 총효용 손실이 작다.

## P6의 규칙

- **예산제**: 풀 조합 수 상한 B = min(2ⁿ, B_MAX). CR 구간(n ≤ 12)에서는 2ⁿ ≤ B_MAX
  라 정본과 같은 예산 — 비교의 공정성. RS 구간(n > 12)에서는 B_MAX가 지수 성장을
  자른다.
- **탐욕 배분**: 전 축 k=1에서 시작해, "다음 값의 한계 기여(w·score)"가 가장 큰
  축의 k를 1씩 올린다 — 예산이 허용하는 동안. 중요한 축이 k를 가져가고 중요하지
  않은 축은 k=1로 남는다.
- **심화 = 예산 배가**: 양보선이 풀 하한 아래로 내려가면 전역 k+1 대신 **B를 2배**
  로 올려 재배분한다 — 성장이 ×2로 유계 (정본은 ×(k+1/k)ⁿ).

배분 기준이 자기 가중치·점수뿐이라 **로컬 계산**이고, 제안·수락 프로토콜은 정본
pool과 동일하다 — RunResult 계측(피크·실물화·phase)도 vendor 경로 그대로다.
"""
from __future__ import annotations

import heapq
import math
from contextlib import contextmanager

from ._vendor.common.scenario import Scenario
from ._vendor.harness import runner as _runner
from ._vendor.harness.runner import RunResult
from ._vendor.strategies.pool import PoolNegotiator

#: 풀 예산 상한 — 2^12: CR 상한(12축)까지는 정본(균일 k=2)과 동일 예산이 되도록 잡은
#: 값이다. 심화 배가로도 B_HARD_MAX를 넘지 않는다 (65 §2.2 P6).
B_MAX = 4096
B_HARD_MAX = 65536


class KAsymPoolNegotiator(PoolNegotiator):
    """P6 — 가중치 탐욕 배분의 축별 kᵢ 풀 (예산 ∏kᵢ ≤ B)."""

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        n = len(self.scenario.axes)
        self.budget = min(2 ** n, B_MAX)
        self._full_space = math.prod(len(ax.values) for ax in self.scenario.axes)
        self.k_alloc: dict[str, int] = self._allocate()

    # -- 배분 ---------------------------------------------------------------------

    def _allocate(self) -> dict[str, int]:
        axes = self.scenario.axes
        ranked = {ax.name: sorted(ax.values, key=lambda v: -self._marginal(ax.name, v))
                  for ax in axes}
        # v2 (1차 측정 관찰 반영): 예산이 균일 k=2 풀(2ⁿ)을 허용하면 **k=2 바닥에서
        # 시작**한다 — CR 구간(예산 = 2ⁿ)에서는 정본 pool과 동일 풀이 되어 FC 손실이
        # 없고, 비대칭 배분은 예산이 모자라는 규모(RS)에서만 발동한다. 1차(전 구간
        # k=1 시작 탐욕)는 CR에서도 풀이 달라져 FC −0.020을 냈다 (65 §7).
        floor_k = 2 if math.prod(min(2, len(ax.values)) for ax in axes) <= self.budget else 1
        alloc = {ax.name: min(floor_k, len(ax.values)) for ax in axes}
        prod = math.prod(alloc.values())
        heap: list[tuple[float, str]] = []
        for ax in axes:
            k0 = alloc[ax.name]
            if len(ranked[ax.name]) > k0:
                heapq.heappush(heap, (-self._marginal(ax.name, ranked[ax.name][k0]), ax.name))
        while heap:
            _gain, name = heapq.heappop(heap)
            k = alloc[name]
            new_prod = (prod // k) * (k + 1)   # k는 prod의 인수 — 정수 나눗셈 정확
            if new_prod > self.budget:
                continue                        # 이 축은 못 키움 — 다른 축 후보는 계속
            alloc[name] = k + 1
            prod = new_prod
            if k + 1 < len(ranked[name]):
                heapq.heappush(heap, (-self._marginal(name, ranked[name][k + 1]), name))
        return alloc

    # -- vendor 훅 재정의 ----------------------------------------------------------

    def _compress(self):
        """부모의 양립-우선 선별을 축별 kᵢ로 수행 (부모는 전역 self.k)."""
        selected: dict[str, list] = {}
        for ax in self.scenario.axes:
            k_i = self.k_alloc[ax.name]
            ranked = sorted(ax.values, key=lambda v: -self._marginal(ax.name, v))
            compatible = [v for v in ranked if self._compatible(ax.name, v, selected)]
            pick = compatible[:k_i]
            if len(pick) < k_i:   # 양립 후보 부족 시 비양립까지 채움 — 부모와 동일 규칙
                pick += [v for v in ranked if v not in pick][: k_i - len(pick)]
            selected[ax.name] = pick
        return selected

    def _replenish(self) -> bool:
        """심화 = 예산 배가 (정본: 전역 k+1). 배분이 포화되면 소진."""
        new_budget = min(self.budget * 2, B_HARD_MAX, self._full_space)
        if new_budget <= self.budget:
            self._log("deepening_exhausted", k=self.budget,
                      reason="예산 상한/전체 공간 도달 (P6)")
            return False
        self.budget = new_budget
        old = dict(self.k_alloc)
        self.k_alloc = self._allocate()
        self.deepening_count += 1
        self.k = max(self.k_alloc.values())   # extra["final_k"] 호환 관측치
        self._candidates = None               # 재압축
        self._log("deepening", k=self.budget,
                  reason=f"양보선이 풀 하한 아래로 — 예산 배가 재배분 (P6, "
                         f"확장 축 {sum(1 for a in old if self.k_alloc[a] > old[a])}개)")
        return True


@contextmanager
def _swap(module, attr, replacement):
    original = getattr(module, attr)
    setattr(module, attr, replacement)
    try:
        yield
    finally:
        setattr(module, attr, original)


#: 택틱 방안명 → 치환할 전략 클래스. run_session이 이 표를 보고 분기한다.
TACTIC_PLANS = {
    "poolka": ("pool", KAsymPoolNegotiator, "2안 + P6 k 비대칭 배분 (예산제 탐욕)"),
}


def run_one_tactic(scenario: Scenario, plan: str, **kw) -> RunResult:
    """vendor `run_one`을 전략 클래스만 치환해 실행 — 계측·RunResult 경로 동일."""
    base, cls, _label = TACTIC_PLANS[plan]
    with _swap(_runner, "PoolNegotiator", cls):
        run = _runner.run_one(scenario, base, **kw)
    return run
