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


class ControlledTableUfun(UfunProvider):
    """개발용 임시 + 교락 통제(25 §25.5) — 공통 feasible 후보 k개를 N과 무관하게 고정.

    k개 후보는 전원에게 utility ∈ [threshold, 1) 로 역방향 생성하고, 나머지는 균등 무작위.
    참여자 수를 늘려도 '전원 수락 가능 후보 수'가 유지되어, 확장성 측정이
    문제 난이도가 아니라 프로토콜 구조를 재게 만든다.
    """

    def __init__(self, initial_threshold: float = 0.4, k_feasible: int = 3):
        self.initial_threshold = initial_threshold
        self.k_feasible = k_feasible

    def build_profiles(
        self, candidates: list[Candidate], n_participants: int, rng: random.Random
    ) -> list[Profile]:
        common = set(rng.sample(candidates, min(self.k_feasible, len(candidates))))
        th = self.initial_threshold
        return [
            Profile(
                pid=f"P{i}",
                utilities={
                    c: round(rng.uniform(th, 1.0) if c in common else rng.random(), 4)
                    for c in candidates
                },
                initial_threshold=th,
            )
            for i in range(n_participants)
        ]


class MultiIssueTableUfun(UfunProvider):
    """개발용 임시 — 복합의제(multi-issue) Ufun. 벤치마크·utility 규격 도착 전 대체.

    후보 = 의제 값의 튜플 (예: (날짜3, 영화1, 영화관2, 시간0)).
    utility(튜플) = Σ_j 가중치_j × 의제별 점수_j(값) — 선형 가중합.
    NegMAS의 LinearAdditiveUtilityFunction과 동형이다 (규격이 오면 그 클래스로 대체).
    """

    def __init__(self, initial_threshold: float = 0.4):
        self.initial_threshold = initial_threshold

    def build_profiles(
        self, candidates: list[Candidate], n_participants: int, rng: random.Random
    ) -> list[Profile]:
        d = len(candidates[0])  # 의제 수 — 후보 튜플의 길이
        issue_values = [sorted({c[j] for c in candidates}, key=repr) for j in range(d)]
        profiles = []
        for i in range(n_participants):
            raw_w = [rng.random() + 0.1 for _ in range(d)]
            w = [x / sum(raw_w) for x in raw_w]  # 의제 가중치 (합 1)
            score = [{v: rng.random() for v in issue_values[j]} for j in range(d)]
            utilities = {
                c: round(sum(w[j] * score[j][c[j]] for j in range(d)), 6) for c in candidates
            }
            profiles.append(
                Profile(pid=f"P{i}", utilities=utilities, initial_threshold=self.initial_threshold)
            )
        return profiles
