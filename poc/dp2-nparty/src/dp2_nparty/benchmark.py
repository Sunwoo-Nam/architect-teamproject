"""벤치마크 셋 로더 자리 — 데이터는 별도 담당자 작업 예정.

계약 (data/benchmark/README.md 규격 참조):
- 벤치마크 케이스 1건 = 후보 목록 + 참여자별 Profile + (선택) 메타데이터(난이도, 정답이 결렬인지 등)
- 로더는 케이스들을 순회 가능하게 제공한다. 하니스는 케이스 단위로 두 방안을 동일 조건 실행한다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .domain import Candidate, Profile

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "benchmark"


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    candidates: list[Candidate]
    profiles: list[Profile]
    meta: dict[str, Any] = field(default_factory=dict)


class BenchmarkLoader(ABC):
    """★ 별도 담당자가 구현할 인터페이스 — 데이터 포맷이 정해지면 채운다."""

    @abstractmethod
    def cases(self) -> Iterator[BenchmarkCase]: ...


class NotReadyLoader(BenchmarkLoader):
    """자리 표시 — 벤치마크 셋 도착 전. 하니스는 이때 개발용 무작위 생성으로 대체한다."""

    def cases(self) -> Iterator[BenchmarkCase]:
        raise NotImplementedError(
            f"벤치마크 셋이 아직 없다 — {DATA_DIR} 에 데이터가 오면 로더를 구현한다."
        )
