"""실험 하니스 — 시드 관리·세션 실행·실험 매트릭스.

원칙 (25 §25.5): 두 방안에 동일 프로파일·동일 시드를 주고 방안만 교체한다.
프로파일 출처: 벤치마크 셋(도착 전) → 개발용 TableUfun 무작위 생성으로 대체.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .domain import Profile, SessionResult
from .measures import fc
from .measures.ru_memory import peak_memory_bytes
from .protocol import Plan1Vote, Plan2Cumulative
from .ufun_provider import TableUfun, UfunProvider

PLANS = {"plan1": Plan1Vote, "plan2": Plan2Cumulative}


@dataclass
class RunRecord:
    plan: str
    session: SessionResult
    fc: fc.FcScore
    peak_mem_bytes: int


@dataclass
class Experiment:
    """한 조건(참여자 수 × 후보 수)의 반복 실행."""

    n_participants: int = 3
    n_candidates: int = 12
    runs: int = 30
    seed: int = 20260811
    provider: UfunProvider = field(default_factory=TableUfun)

    def run(self) -> dict[str, list[RunRecord]]:
        out: dict[str, list[RunRecord]] = {name: [] for name in PLANS}
        for i in range(self.runs):
            rng = random.Random((self.seed, self.n_participants, self.n_candidates, i).__hash__())
            candidates = [f"slot{j:02d}" for j in range(self.n_candidates)]
            profiles: list[Profile] = self.provider.build_profiles(
                candidates, self.n_participants, rng
            )
            for name, cls in PLANS.items():  # 동일 프로파일로 두 방안 실행
                session, peak = peak_memory_bytes(lambda c=cls: c(profiles).run())
                out[name].append(
                    RunRecord(
                        plan=name,
                        session=session,
                        fc=fc.score(session.outcome, candidates, profiles),
                        peak_mem_bytes=peak,
                    )
                )
        return out


def participants_sweep(seed: int = 20260811, runs: int = 30) -> dict[int, dict[str, list[RunRecord]]]:
    """[25] N ∈ {3,4,5,6,8,10} 스윕 — b_msg 회귀의 입력."""
    return {
        n: Experiment(n_participants=n, runs=runs, seed=seed).run() for n in (3, 4, 5, 6, 8, 10)
    }


def issues_sweep(seed: int = 20260811, runs: int = 10) -> dict[int, dict[str, list[RunRecord]]]:
    """[21 §21.3-5] 의제 수 스윕(후보 조합 수 확장) — 탄력성 c 회귀의 입력.

    주의: 현재는 후보 수를 직접 늘리는 골격만 제공한다. 의제 구조(K×L×M×P)의
    조합 생성은 벤치마크 셋 규격이 확정되면 그 케이스로 대체한다.
    """
    return {
        m: Experiment(n_participants=3, n_candidates=m, runs=runs, seed=seed).run()
        for m in (8, 16, 32, 64, 128)
    }
