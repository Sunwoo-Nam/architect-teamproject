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


def participants_sweep(
    seed: int = 20260811, runs: int = 30, provider: UfunProvider | None = None
) -> dict[int, dict[str, list[RunRecord]]]:
    """[25] N ∈ {3,4,5,6,8,10} 스윕 — b_msg 회귀의 입력.

    provider 기본값은 교락 통제 생성기(공통 feasible k=3 고정) — 25 §25.5의 요구.
    """
    from .ufun_provider import ControlledTableUfun

    prov = provider or ControlledTableUfun()
    return {
        n: Experiment(n_participants=n, runs=runs, seed=seed, provider=prov).run()
        for n in (3, 4, 5, 6, 8, 10)
    }


# 복합의제 스윕 구성 — (의제별 후보 수 목록). 의제 수 d가 2→5로 늘며 조합 수 S가 로그 등간격 확장
ISSUE_CONFIGS = [
    (10, 10),            # d=2, S=100
    (7, 7, 7),           # d=3, S=343
    (10, 10, 10),        # d=3, S=1,000
    (8, 8, 8, 8),        # d=4, S=4,096
    (10, 10, 10, 10),    # d=4, S=10,000
    (8, 8, 8, 8, 8),     # d=5, S=32,768
]


def multi_issue_sweep(
    seed: int = 20260811, runs: int = 5
) -> dict[tuple, dict[str, list[tuple[SessionResult, int]]]]:
    """[21 §21.3-5] 복합의제(multi-issue) 스윕 — 조합-메모리 탄력성 c 회귀의 입력.

    후보 = 의제 값 튜플의 곱집합. 관찰 로그를 끄고(collect_log=False) 순수 협상
    상태의 피크 메모리만 잰다. 반환: {의제 구성: {plan: [(세션, 피크바이트)]}}.
    현 구현(전 후보 순위표 사전 생성)은 전체 열거 구조라 c ≈ 1이 **베이스라인 기대값**이다.
    """
    import itertools

    from .ufun_provider import MultiIssueTableUfun

    provider = MultiIssueTableUfun()
    out: dict[tuple, dict[str, list[tuple[SessionResult, int]]]] = {}
    for sizes in ISSUE_CONFIGS:
        per_plan: dict[str, list[tuple[SessionResult, int]]] = {n: [] for n in PLANS}
        for i in range(runs):
            rng = random.Random((seed, "mi", sizes, i).__hash__())
            candidates = list(itertools.product(*[range(s) for s in sizes]))
            profiles = provider.build_profiles(candidates, 3, rng)
            for name, cls in PLANS.items():
                session, peak = peak_memory_bytes(
                    lambda c=cls: c(profiles, collect_log=False).run()
                )
                per_plan[name].append((session, peak))
        out[sizes] = per_plan
    return out
