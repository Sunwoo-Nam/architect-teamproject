"""NegMAS 브리지 — 시나리오 축을 NegMAS OutcomeSpace로 만들고 튜플↔Outcome 딕셔너리 변환."""
from __future__ import annotations

from negmas import make_issue, make_os

from dpca.common.generators import Value
from dpca.common.rules import Outcome
from dpca.common.scenario import Axis, Scenario


def make_outcome_space(axes: list[Axis]):
    return make_os(issues=[make_issue([v.name for v in ax.values], name=ax.name) for ax in axes])


class TupleCodec:
    """SAO offer(이름 튜플) <-> Outcome(축 -> Value) 변환기."""

    def __init__(self, axes: list[Axis]):
        self.axes = axes
        self._lookup: dict[str, dict[str, Value]] = {
            ax.name: {v.name: v for v in ax.values} for ax in axes
        }

    def to_outcome(self, offer: tuple) -> Outcome:
        return {ax.name: self._lookup[ax.name][name] for ax, name in zip(self.axes, offer)}

    def to_tuple(self, outcome: Outcome) -> tuple:
        return tuple(outcome[ax.name].name for ax in self.axes)


def aspiration(step: int, n_steps: int, floor: float, exponent: float = 4.0) -> float:
    """양보선 — boulware형(끝까지 버티다 후반 양보): 1.0 → floor."""
    t = min(1.0, max(0.0, step / max(1, n_steps - 1)))
    return floor + (1.0 - floor) * (1.0 - t) ** exponent
