"""자료형 — 후보·프로파일·세션 결과.

51번 문서(설계 후보 1)의 용어를 그대로 쓴다:
utility / initial threshold / revised threshold / 결렬(NO_DEAL) / 유효 후보.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Hashable

Candidate = Hashable  # 후보안 — 해시 가능하면 무엇이든 (예: 슬롯 id, (날짜, 시간) 튜플)

NO_DEAL = "NO_DEAL"  # 결렬 — 24번 정의상 "전원이 initial threshold 값을 얻는 후보"로 채점된다


@dataclass(frozen=True)
class Profile:
    """참여자 1인의 봉인 프로파일 — 채점기와 본인 Agent만 안다."""

    pid: str
    utilities: dict[Candidate, float]  # 후보 -> utility (0-1). Ufun 출력의 테이블 표현
    initial_threshold: float  # 수락 바닥선 = 결렬 시 본인이 얻는 가치

    def utility(self, c: Candidate) -> float:
        return self.utilities[c]

    def ranked(self) -> list[Candidate]:
        """utility 내림차순 순위표 — '라운드 k = 순위 k번째 제출' 규칙의 기준.

        동점은 후보의 repr 순으로 고정해 결정론을 보장한다.
        """
        return sorted(self.utilities, key=lambda c: (-self.utilities[c], repr(c)))

    def rank_of(self, c: Candidate) -> int:
        """1-기반 순위 — 방안 2 동률 해소(순위 합)에 사용."""
        return self.ranked().index(c) + 1


@dataclass
class SessionResult:
    plan: str  # "plan1" | "plan2"
    outcome: Candidate | str  # 성립 후보 또는 NO_DEAL
    rounds: int  # 진행된 총 라운드 수
    sweeps: int  # 진행된 바퀴 수
    messages: int  # 물리 전송 총 건수 (README 매핑 v1)
    phases: int = 0  # 직렬 통신 단계 수 (TB의 ENV-A 대체 지표)
    tie_break_used: bool = False
    log: list[dict[str, Any]] = field(default_factory=list)  # 라운드별 이벤트 (분석용)

    @property
    def agreed(self) -> bool:
        return self.outcome != NO_DEAL
