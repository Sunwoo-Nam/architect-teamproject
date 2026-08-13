r"""[24 §1] Functional Correctness — Total Utility 달성률.

24의 정의 그대로:
- **결렬 후보** = 전원이 자기 initial threshold를 얻는 후보. **항상** 후보 집합에 포함된다
- **유효 후보** = 전원 utility ≥ initial threshold (결렬은 항상 유효)
- **x\*** = 유효 후보 중 total utility 최대
- **달성률** = U(r) ÷ U(x\*)
- **R̄** = 유효 후보를 무작위로 고르는 전략의 평균 달성률.
  표본 추출이 아니라 **기대값을 정확 계산**한다 (유효 후보 달성률의 산술 평균)
- **개선 비율 s** = (달성률 − R̄) ÷ (1 − R̄)

**지표를 2개 병행한다** (사용자 지시 2026-08-12): `s`(베이스라인 정규화, 24 정본)와
`달성률`(절대 수준). 둘은 어긋날 수 있다 — 후보 공간이 전부 좋으면 절대 달성률은
높지만 무작위 대비 개선은 작다. 어느 쪽으로 좋은지가 다른 정보이므로 둘 다 낸다.

**FR 위반은 점수와 분리한다** (24 §1.7). 바닥선 밑 수락·하드 제약 위반은 달성률을
깎는 것이 아니라 별도 플래그다 — "달성률이 높아도 지켜야 할 것을 어겼다"가 드러나야 한다.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Sequence

from .constants import BAND_FC_ACHIEVED, BAND_FC_S
from .contract import NO_AGREEMENT, Case, Outcome, Preference


def no_agreement_utility(preferences: Sequence[Preference]) -> float:
    """결렬 후보의 total utility = 전원의 initial threshold 합 (24 §1.3)."""
    return sum(p.initial_threshold for p in preferences)


def total_utility(outcome: Outcome, preferences: Sequence[Preference]) -> float:
    if outcome == NO_AGREEMENT:
        return no_agreement_utility(preferences)
    return sum(p.utility(outcome) for p in preferences)


def valid_candidates(case: Case) -> list[Outcome]:
    """유효 후보 (결렬 포함). 순서는 결정론적이어야 한다 — R̄가 순서에 무관하도록."""
    prefs = case.preferences
    valid = [
        o for o in case.candidates()
        if all(p.utility(o) >= p.initial_threshold - 1e-12 for p in prefs)
    ]
    valid.append(NO_AGREEMENT)
    return valid


@dataclass(frozen=True)
class FcScore:
    achieved: float          # U(r) ÷ U(x*)
    baseline: float          # R̄
    s: float                 # (달성률 − R̄) ÷ (1 − R̄)
    stars_s: int
    stars_achieved: int
    optimal: Outcome
    u_optimal: float
    optimal_is_no_agreement: bool
    agreed: bool
    n_valid: int
    fr_violations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "achieved": round(self.achieved, 6),
            "baseline": round(self.baseline, 6),
            "s": round(self.s, 6),
            "stars_s": self.stars_s,
            "stars_achieved": self.stars_achieved,
            "u_optimal": round(self.u_optimal, 6),
            "optimal_is_no_agreement": self.optimal_is_no_agreement,
            "agreed": self.agreed,
            "n_valid": self.n_valid,
            "fr_violations": list(self.fr_violations),
        }


def score(
    case: Case,
    agreement: Outcome | str,
    extra_violations: Sequence[str] = (),
) -> FcScore:
    """합의 결과 1건을 채점한다.

    `extra_violations`는 어댑터가 도메인 규칙(하드 제약 등)을 검사해 넘긴다 —
    계약에 하드 규칙이 없으므로 측정기가 직접 볼 수 없는 부분이다.
    """
    prefs = case.preferences
    valid = valid_candidates(case)
    totals = [total_utility(o, prefs) for o in valid]

    u_star = max(totals)
    idx = totals.index(u_star)
    optimal = valid[idx]

    u_result = total_utility(agreement, prefs)
    achieved = (u_result / u_star) if u_star > 0 else 0.0

    if u_star > 0:
        baseline = statistics.fmean(t / u_star for t in totals)
    else:
        baseline = 0.0

    if baseline >= 1.0 - 1e-12:
        # 유효 후보가 전부 x*와 동률 — 고를 것이 없으니 도달했으면 만점
        s = 1.0 if achieved >= 1.0 - 1e-12 else 0.0
    else:
        s = (achieved - baseline) / (1.0 - baseline)

    violations: list[str] = []
    if agreement != NO_AGREEMENT:
        for p in prefs:
            u = p.utility(agreement)
            if u < p.initial_threshold - 1e-9:
                violations.append(
                    f"{p.pid} 바닥선({p.initial_threshold:.3f}) 밑 수락 (u={u:.3f})"
                )
    violations.extend(extra_violations)

    return FcScore(
        achieved=achieved,
        baseline=baseline,
        s=s,
        stars_s=BAND_FC_S.stars(s),
        stars_achieved=BAND_FC_ACHIEVED.stars(achieved),
        optimal=optimal,
        u_optimal=u_star,
        optimal_is_no_agreement=(optimal == NO_AGREEMENT),
        agreed=(agreement != NO_AGREEMENT),
        n_valid=len(valid),
        fr_violations=violations,
    )


def aggregate(scores: Sequence[FcScore]) -> dict:
    """케이스 여러 건의 집계. 별점은 평균값에 밴드를 다시 적용해 낸다."""
    if not scores:
        raise ValueError("집계할 점수가 없다")
    mean_achieved = statistics.fmean(x.achieved for x in scores)
    mean_s = statistics.fmean(x.s for x in scores)
    return {
        "cases": len(scores),
        "agreed": sum(1 for x in scores if x.agreed),
        "mean_achieved": round(mean_achieved, 6),
        "mean_s": round(mean_s, 6),
        "stars_achieved": BAND_FC_ACHIEVED.stars(mean_achieved),
        "stars_s": BAND_FC_S.stars(mean_s),
        "optimal_hit": sum(1 for x in scores if x.achieved >= 1.0 - 1e-9),
        "fr_violation_cases": sum(1 for x in scores if x.fr_violations),
        "bands": {"s": BAND_FC_S.as_dict(), "achieved": BAND_FC_ACHIEVED.as_dict()},
    }
