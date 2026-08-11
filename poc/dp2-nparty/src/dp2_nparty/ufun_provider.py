"""Ufun 자리 — 인터페이스 확정, 실제 구현은 별도 담당자 작업 예정.

계약:
- 협상 참여자 전원이 같은 Ufun 엔진을 쓴다 (입력만 다름) — 눈금 조정 불필요 전제(24 §24.2).
- provider는 시나리오·참여자 입력을 받아 Profile(후보별 utility 테이블 + initial threshold)을 만든다.
- 하니스·프로토콜·측정기는 Profile만 보고 동작하므로, 구현이 오면 이 모듈만 갈아끼우면 된다.

담당자 구현이 오기 전까지는 TableUfun(개발용 임시)으로 하니스를 돌린다.
"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod

from .domain import Candidate, Profile


class UfunProvider(ABC):
    """★ 별도 담당자가 구현할 인터페이스."""

    @abstractmethod
    def build_profiles(
        self, candidates: list[Candidate], n_participants: int, rng: random.Random
    ) -> list[Profile]:
        """시나리오의 후보 목록과 참여자 수로 봉인 프로파일들을 생성한다."""


class TableUfun(UfunProvider):
    """개발용 임시 구현 — 무작위 utility 테이블. 벤치마크 셋이 오면 대체된다.

    NegMAS로는 negmas.preferences.MappingUtilityFunction 과 동형이다.
    """

    def __init__(self, initial_threshold: float = 0.4):
        self.initial_threshold = initial_threshold

    def build_profiles(
        self, candidates: list[Candidate], n_participants: int, rng: random.Random
    ) -> list[Profile]:
        return [
            Profile(
                pid=f"P{i}",
                utilities={c: round(rng.random(), 4) for c in candidates},
                initial_threshold=self.initial_threshold,
            )
            for i in range(n_participants)
        ]
