"""FC 채점기 — 24 정본: 달성률 U(r) ÷ U(x*), 무작위 베이스라인 정규화 별점 0~5.

정답 프로파일은 여기(와 oracle)에서만 읽는다. FR 위반(바닥선 밑 수락, 하드 위반)은
점수와 별개 플래그로 보고한다 (24.7).
"""
from __future__ import annotations

from dataclasses import dataclass

from total.adapters.composite._vendor.common.oracle import OracleReport, analyze
from total.adapters.composite._vendor.common.profiles import build_truth_profiles, truth_utility
from total.adapters.composite._vendor.common.rules import build_hard_rules, build_participant_hard, build_soft_rules
from total.adapters.composite._vendor.common.scenario import Scenario


@dataclass
class Score:
    achieved_rate: float       # U(r) / U(x*)
    improvement_s: float       # (달성률 - R̄) / (1 - R̄)
    stars: int                 # 24.4 별점 0~5
    agreement_was_breakdown: bool
    xstar_is_breakdown: bool
    fr_violations: list[str]


def _stars(s: float) -> int:
    for bound, star in ((0.8, 5), (0.6, 4), (0.4, 3), (0.2, 2), (0.0, 1)):
        if s > bound:
            return star
    return 0


class Judge:
    def __init__(self, scenario: Scenario, oracle_report: OracleReport | None = None):
        self.scenario = scenario
        self.truths = build_truth_profiles(scenario)
        self.homes = [t.home_region for t in self.truths]
        self.soft = build_soft_rules(scenario, self.homes)
        self.hard = build_hard_rules(scenario) + build_participant_hard(scenario)
        self.report = oracle_report or analyze(scenario)

    def score(self, agreement_names: dict[str, str] | None) -> Score:
        fr: list[str] = []
        if agreement_names is None:
            total = self.report.breakdown_total
            breakdown = True
        else:
            outcome = {
                ax.name: next(v for v in ax.values if v.name == agreement_names[ax.name])
                for ax in self.scenario.axes
            }
            breakdown = False
            if not all(rule(outcome) for rule in self.hard):
                fr.append("하드 제약 위반 합의")
            utilities = [
                truth_utility(t, p, outcome, self.soft) for p, t in enumerate(self.truths)
            ]
            for p, (u, t) in enumerate(zip(utilities, self.truths)):
                if u < t.initial_threshold - 1e-9:
                    fr.append(f"참여자 {p} 바닥선({t.initial_threshold}) 밑 수락 (u={u:.3f})")
            total = sum(utilities)

        achieved = total / self.report.u_xstar if self.report.u_xstar > 0 else 0.0
        r_bar = self.report.r_bar
        s = (achieved - r_bar) / (1 - r_bar) if r_bar < 1.0 else (1.0 if achieved >= 1.0 else 0.0)
        return Score(
            achieved_rate=achieved,
            improvement_s=s,
            stars=_stars(s),
            agreement_was_breakdown=breakdown,
            xstar_is_breakdown=self.report.xstar_is_breakdown,
            fr_violations=fr,
        )
