"""의존성 규칙 — 하드(실행 가능성 판정)와 소프트(효용 감점)를 스키마 어휘대로 구현한다."""
from __future__ import annotations

import random
from typing import Callable

from .generators import Value
from .scenario import Scenario

Outcome = dict[str, Value]  # 축 이름 -> 선택된 값
HardRule = Callable[[Outcome], bool]
SoftRule = Callable[[int, Outcome], float]  # (참여자 idx, outcome) -> 감점


def build_hard_rules(scenario: Scenario) -> list[HardRule]:
    rules: list[HardRule] = []
    for i, dep in enumerate(scenario.active_dependencies()):
        if dep["type"] != "hard":
            continue
        rule = dep["rule"]
        if rule == "availability":
            rules.append(_availability(scenario, dep, i))
        elif rule == "availability_explicit":
            rules.append(_availability_explicit(dep))
        elif rule == "membership":
            rules.append(_membership(dep))
        else:
            raise ValueError(f"알 수 없는 hard 규칙: {rule}")
    return rules


def _availability(scenario: Scenario, dep: dict, idx: int) -> HardRule:
    """상영표형: subject 값별로 over 값의 coverage 비율만 허용 (시드 결정론)."""
    subject, over = dep["subject"], dep["over"]
    coverage = float(dep["coverage"])
    over_names = [v.name for v in scenario.axis(over).values]
    k = max(1, round(len(over_names) * coverage))
    rng = random.Random(f"{scenario.id}-av{idx}-{scenario.profile_seed}")
    allowed = {
        v.name: set(rng.sample(over_names, k)) for v in scenario.axis(subject).values
    }

    def check(outcome: Outcome) -> bool:
        return outcome[over].name in allowed[outcome[subject].name]

    return check


def _availability_explicit(dep: dict) -> HardRule:
    subject, subject_value = dep["subject"], dep["subject_value"]
    allowed: dict[str, list] = dep["allowed"]

    def check(outcome: Outcome) -> bool:
        if outcome[subject].name != subject_value:
            return True
        return all(outcome[axis].name in values for axis, values in allowed.items())

    return check


def _membership(dep: dict) -> HardRule:
    subject, region_axis = dep["subject"], dep["region_axis"]

    def check(outcome: Outcome) -> bool:
        return outcome[subject].attrs.get("region") == outcome[region_axis].name

    return check


def build_participant_hard(scenario: Scenario) -> list[HardRule]:
    """전 참여자 하드 제약 (oracle용) — 전원 만족해야 실행 가능."""
    return _build_participant_hard(scenario, participant=None)


def build_participant_hard_for(scenario: Scenario, participant: int) -> list[HardRule]:
    """특정 참여자의 하드 제약만 (에이전트용 — 자기 캘린더·제약은 사유 정보)."""
    return _build_participant_hard(scenario, participant=participant)


def _build_participant_hard(scenario: Scenario, participant: int | None) -> list[HardRule]:
    rules: list[HardRule] = []
    for con in scenario.participants.get("constraints", []):
        if participant is not None and int(con.get("participant", -1)) != participant:
            continue
        if "axis" in con and "attr_equals" in con:
            # 속성 기반: 값 이름이 아니라 메타데이터로 판정 — count가 커져도(sat2, sun2 …) 의도 유지
            axis, attrs = con["axis"], dict(con["attr_equals"])
            rules.append(
                lambda o, a=axis, at=attrs: all(o[a].attrs.get(k) == v for k, v in at.items())
            )
        elif "axis" in con:
            axis, values = con["axis"], set(con["values"])
            rules.append(lambda o, a=axis, v=values: o[a].name in v)
        elif "pairs" in con:
            axes = con["pairs"]["axes"]
            pairs = {tuple(p) for p in con["pairs"]["values"]}
            rules.append(lambda o, ax=axes, p=pairs: tuple(o[a].name for a in ax) in p)
    return rules


def build_soft_rules(scenario: Scenario, home_regions: list[str]) -> list[SoftRule]:
    rules: list[SoftRule] = []
    for dep in scenario.active_dependencies():
        if dep["type"] != "soft":
            continue
        rule, penalty = dep["rule"], float(dep["penalty"])
        if rule == "conditional_home":
            if_axis, if_values, then_axis = dep["if_axis"], set(dep["if_values"]), dep["then_axis"]

            def fn(p: int, o: Outcome, ia=if_axis, iv=if_values, ta=then_axis, pen=penalty) -> float:
                if o[ia].name in iv and o[ta].name != home_regions[p]:
                    return pen
                return 0.0

            rules.append(fn)
        elif rule == "conditional_pref":
            if_axis, if_values = dep["if_axis"], set(dep["if_values"])
            then_axis, preferred = dep["then_axis"], set(dep["preferred"])

            def fn(p: int, o: Outcome, ia=if_axis, iv=if_values, ta=then_axis, pr=preferred, pen=penalty) -> float:
                if o[ia].name in iv and o[ta].name not in pr:
                    return pen
                return 0.0

            rules.append(fn)
        elif rule == "same_region":
            a, b = dep["a"], dep["b"]

            def fn(p: int, o: Outcome, a=a, b=b, pen=penalty) -> float:
                region_b = o[b].attrs.get("region", o[b].name)
                return 0.0 if region_b == o[a].name else pen

            rules.append(fn)
        else:
            raise ValueError(f"알 수 없는 soft 규칙: {rule}")
    return rules
