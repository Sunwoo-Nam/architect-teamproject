"""TC(시나리오) 로더 — 구조는 yaml, 크기(count·축 수)는 파라미터로 덮어쓴다."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .generators import Value, build_axis_values


@dataclass
class Axis:
    name: str
    generator: str
    values: list[Value]


@dataclass
class Scenario:
    meta: dict
    axes: list[Axis]
    dependencies: list[dict]
    participants: dict
    agent_view: dict
    judge: dict

    @property
    def id(self) -> str:
        return self.meta["id"]

    @property
    def profile_seed(self) -> int:
        return int(self.participants["profile_seed"])

    @property
    def n_participants(self) -> int:
        return int(self.participants.get("count", 2))

    def axis(self, name: str) -> Axis:
        for ax in self.axes:
            if ax.name == name:
                return ax
        raise KeyError(name)

    def axis_names(self) -> list[str]:
        return [ax.name for ax in self.axes]

    def space_size(self) -> int:
        size = 1
        for ax in self.axes:
            size *= len(ax.values)
        return size

    def active_dependencies(self) -> list[dict]:
        """축을 잘라 쓸 때(S11) 범위 밖 축을 참조하는 규칙은 비활성 (프리픽스 안전)."""
        names = set(self.axis_names())
        out = []
        for dep in self.dependencies:
            refs = _referenced_axes(dep)
            if refs <= names:
                out.append(dep)
        return out


def _referenced_axes(dep: dict) -> set[str]:
    keys = ("subject", "over", "region_axis", "if_axis", "then_axis", "a", "b")
    refs = {dep[k] for k in keys if k in dep}
    if "allowed" in dep:
        refs |= set(dep["allowed"].keys())
    return refs


def load_scenario(
    path: str | Path,
    n_axes: int | None = None,
    count_overrides: dict[str, int] | None = None,
    count_scale: float | None = None,
) -> Scenario:
    """n_axes: 앞 n개 축만 사용(S11 축 수 스윕). count_overrides/scale: c 스윕용 크기 조절."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))

    axis_specs = raw["axes"][: n_axes if n_axes else len(raw["axes"])]
    region_names: list[str] | None = None
    axes: list[Axis] = []
    for spec in axis_specs:
        count = int(spec["base_count"])
        if count_overrides and spec["name"] in count_overrides:
            count = int(count_overrides[spec["name"]])
        elif count_scale:
            count = max(2, round(count * count_scale))
        values = build_axis_values(spec["generator"], count, region_names)
        if spec["generator"] == "regions":
            region_names = [v.name for v in values]
        axes.append(Axis(spec["name"], spec["generator"], values))

    return Scenario(
        meta=raw["meta"],
        axes=axes,
        dependencies=raw.get("dependencies", []),
        participants=raw["participants"],
        agent_view=raw.get("agent_view", {}),
        judge=raw.get("judge", {}),
    )
