r"""[24 §1] Functional Correctness — Total Utility 달성률.

24의 정의 그대로:
- **결렬 후보** = 전원이 자기 initial threshold를 얻는 후보. **항상** 후보 집합에 포함된다
- **유효 후보** = 전원 utility ≥ initial threshold (결렬은 항상 유효)
- **x\*** = 유효 후보 중 total utility 최대
- **달성률** = U(r) ÷ U(x\*)
- **R̄** = 유효 후보를 무작위로 고르는 전략의 평균 달성률.
  표본 추출이 아니라 **기대값을 정확 계산**한다 (유효 후보 달성률의 산술 평균)
- **개선 비율 s** = (달성률 − R̄) ÷ (1 − R̄)
- **집계 수준** — 표본 전체의 **달성률 평균과 R̄ 평균을 먼저** 구한 뒤 s로 **한 번** 환산한다.
  세션별 s를 평균 내지 **않는다** (24 §1.4 「집계 수준」)

**판정 지표는 달성률이다** (PL 확정 2026-08-13 — 종전 판정 s에서 교체). 별점은
달성률 원값에 BAND_FC_ACHIEVED를 직접 적용한다. `s`는 보조 관측으로 유지한다 —
후보 공간이 전부 좋으면 달성률은 높아도 무작위 대비 개선이 작을 수 있어, 그 확인과
**s ≤ 0(무작위 이하) 즉시 결함** 감시가 s의 남은 역할이다.

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


def improvement_ratio(achieved: float, baseline: float) -> float:
    """s = (달성률 − R̄) ÷ (1 − R̄) — 24 §1.4.

    **R̄ = 1은 두 경우로 갈린다** (24 §1.4, 2026-08-13 개정):

    - **달성률 = 1** (유효 후보에 도달) → 0/0 **부정형**이라 관례가 필요하다. 무작위와
      구분할 개선 여지 자체가 없는 시나리오이므로 **s = 1**.
    - **달성률 < 1** (유효 후보 밖) → 부정형이 **아니다.** R̄ ≤ 1이 항상 성립하므로
      (각 유효 후보 달성률 ≤ 1의 평균) 분모는 **양수 쪽에서** 0으로 가고 분자는 음수로
      고정이라 **극한이 −∞로 확정**된다. 24 밴드의 `s ≤ 0 → 0점` 구간이므로 **0.0**.

    R̄ = 1의 뜻은 "잴 수 없다"가 아니라 **"무작위조차 만점"** 이다 — 결렬 후보가 §1.3에
    따라 항상 후보 집합에 있어 무작위 선택 전략은 여기서도 정의되고, 선택지가 1개면
    결정론이 될 뿐 반드시 만점을 얻는다. 그 판에서 못 맞췄으면 무작위보다 나쁜 것이다.

    개정 전 규칙은 달성률과 무관하게 s = 1이었고 `_vendor/measures/fc.py`에 그대로 남아
    있다 (발표 수치 재현이 목적이라 값을 바꾸지 않는다 — `test_fc_crosscheck.py` 참조).

    세션 1건에도, 표본 전체 평균에도 **같은 함수**를 쓴다 — 두 곳에서 규칙이
    갈리는 것이 이 파일에서 실제로 났던 결함이다 (`00-설계안.md` §13-4).
    """
    if baseline >= 1.0 - 1e-12:
        return 1.0 if achieved >= 1.0 - 1e-12 else 0.0
    return (achieved - baseline) / (1.0 - baseline)


@dataclass(frozen=True)
class FcScore:
    achieved: float          # U(r) ÷ U(x*) — 판정 지표
    stars_achieved: int
    baseline: float          # R̄
    s: float                 # (달성률 − R̄) ÷ (1 − R̄) — 보조 관측
    stars_s: int
    optimal: Outcome
    u_optimal: float
    optimal_is_no_agreement: bool
    agreed: bool
    n_valid: int
    fr_violations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "achieved": round(self.achieved, 6),
            "stars_achieved": self.stars_achieved,
            "baseline": round(self.baseline, 6),
            "s": round(self.s, 6),
            "stars_s": self.stars_s,
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

    s = improvement_ratio(achieved, baseline)

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
        stars_achieved=BAND_FC_ACHIEVED.stars(achieved),
        baseline=baseline,
        s=s,
        stars_s=BAND_FC_S.stars(s),
        optimal=optimal,
        u_optimal=u_star,
        optimal_is_no_agreement=(optimal == NO_AGREEMENT),
        agreed=(agreement != NO_AGREEMENT),
        n_valid=len(valid),
        fr_violations=violations,
    )


def aggregate(scores: Sequence[FcScore]) -> dict:
    """케이스 여러 건의 집계. 별점은 평균값에 밴드를 다시 적용해 낸다.

    **s는 세션별로 구해 평균 내지 않는다** (24 §1.4 「집계 수준」, §1.5 절차 6):
    표본 전체의 달성률 평균과 R̄ 평균을 먼저 구한 뒤 **한 번** 환산한다. 세션별 s는
    개선 여지(분모 1−R̄)가 0에 가까운 쉬운 세션에서 크게 요동치므로, 그것을 평균 내면
    쉬운 세션의 잡음이 표본 대표값을 지배한다.

    `mean_baseline`을 함께 낸다 — 없으면 리포트에서 s를 재검산할 수 없다.
    """
    if not scores:
        raise ValueError("집계할 점수가 없다")
    mean_achieved = statistics.fmean(x.achieved for x in scores)
    mean_baseline = statistics.fmean(x.baseline for x in scores)
    mean_s = improvement_ratio(mean_achieved, mean_baseline)
    return {
        "cases": len(scores),
        "agreed": sum(1 for x in scores if x.agreed),
        "mean_achieved": round(mean_achieved, 6),
        "stars_achieved": BAND_FC_ACHIEVED.stars(mean_achieved),  # 판정 (PL 확정 2026-08-13)
        "mean_baseline": round(mean_baseline, 6),
        "mean_s": round(mean_s, 6),
        "stars_s": BAND_FC_S.stars(mean_s),
        # s ≤ 0 = 무작위 이하 — 달성률 별점과 무관하게 즉시 결함 (24 §1.4, 0점 정의 계승)
        "below_random_defect": mean_s <= 0,
        "optimal_hit": sum(1 for x in scores if x.achieved >= 1.0 - 1e-9),
        "fr_violation_cases": sum(1 for x in scores if x.fr_violations),
        # R̄=1 케이스에서는 s가 1 아니면 0뿐이라 판별력이 없다. 24 §1.4가 "달성률 원값으로
        # 확인하라"고 한 구간이므로, 몇 건인지 보이지 않으면 그 확인 자체를 할 수 없다
        "degenerate_cases": sum(1 for x in scores if x.baseline >= 1.0 - 1e-12),
        "degenerate_missed": sum(
            1 for x in scores
            if x.baseline >= 1.0 - 1e-12 and x.achieved < 1.0 - 1e-12
        ),
        # 판정 = 달성률, s는 보조 (PL 확정 2026-08-13 재개정)
        "bands": {"achieved": BAND_FC_ACHIEVED.as_dict(), "s": BAND_FC_S.as_dict()},
    }
