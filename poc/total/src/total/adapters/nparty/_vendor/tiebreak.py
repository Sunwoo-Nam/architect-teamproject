"""동률 해소 — 플러그형(TieBreaker). PL 결정: 나중에 갈아끼울 수 있는 형태.

확정 규칙 (2026-08-11):
- 방안 1: 결선투표 1회 다수결 (utility 점수가 전송되지 않아 순위 정보를 모으는 수단이 투표뿐)
- 방안 2: 순위 합 최소 → (동률이면) 순위 표준편차 최소 → (그래도 동률이면) 결선투표 다수결
"""
from __future__ import annotations

import statistics
from abc import ABC, abstractmethod

from .domain import Candidate, Profile


class TieBreaker(ABC):
    name: str = "base"

    @abstractmethod
    def pick(self, tied: list[Candidate], profiles: list[Profile]) -> tuple[Candidate, int]:
        """동률 후보들 중 하나를 고른다. 반환: (선택 후보, 추가 발생 메시지 수 견적).

        메시지 견적: 결선투표는 담당자 공지 (N-1) + 표 회신 (N-1) = 2(N-1),
        계산만으로 끝나는 규칙은 0 (담당자 로컬 계산).
        """


def _runoff_majority(tied: list[Candidate], profiles: list[Profile]) -> Candidate:
    """결선투표 다수결 — 각자 동률 후보 중 자기 utility 최고인 안에 1표.

    최다득표 동률이면 후보 repr 순으로 결정론적 선택 (v1 규칙 — 필요시 교체).
    """
    votes: dict[Candidate, int] = {c: 0 for c in tied}
    for p in profiles:
        best = max(tied, key=lambda c: (p.utility(c), repr(c)))
        votes[best] += 1
    top = max(votes.values())
    winners = sorted((c for c, v in votes.items() if v == top), key=repr)
    return winners[0]


class RunoffMajority(TieBreaker):
    """방안 1용 — 결선투표 1회 다수결."""

    name = "runoff_majority"

    def pick(self, tied, profiles):
        n = len(profiles)
        return _runoff_majority(tied, profiles), 2 * (n - 1)


class RankSumThenStdThenRunoff(TieBreaker):
    """방안 2용 — 순위 합 최소 → 표준편차 최소 → 결선투표 다수결.

    순위 정보는 '라운드 번호 = 순위 번호' 규칙 덕분에 담당자가 이미 안다 (추가 통신 0).
    """

    name = "ranksum_std_runoff"

    def pick(self, tied, profiles):
        n = len(profiles)
        ranks = {c: [p.rank_of(c) for p in profiles] for c in tied}
        # 1차: 순위 합 최소 (모두에게 상위권인 안)
        min_sum = min(sum(r) for r in ranks.values())
        s1 = [c for c in tied if sum(ranks[c]) == min_sum]
        if len(s1) == 1:
            return s1[0], 0
        # 2차: 순위 표준편차 최소 (고른 만족 우선)
        min_std = min(statistics.pstdev(ranks[c]) for c in s1)
        s2 = [c for c in s1 if statistics.pstdev(ranks[c]) == min_std]
        if len(s2) == 1:
            return s2[0], 0
        # 3차: 결선투표 다수결
        return _runoff_majority(s2, profiles), 2 * (n - 1)


REGISTRY: dict[str, type[TieBreaker]] = {
    cls.name: cls for cls in (RunoffMajority, RankSumThenStdThenRunoff)
}
