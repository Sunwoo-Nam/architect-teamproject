"""정확한 x* 계산 — 전수열거 없이 성긴 의존 구조를 이용.

모든 하드·소프트 규칙은 소수의 축(vertex cover)에만 붙는다. 그 축들을 고정하면 나머지 축이
독립이 되어 각 축을 따로 최적화하면 된다. cover 조합(작음)만 훑어 total-utility 최대 outcome을
정확히 구한다 — 100억 조합이어도. 단 바닥선이 조이는 경우(무제약 최대가 무효)는 하한만 준다.
"""
from __future__ import annotations

import itertools
from collections import Counter

from .profiles import build_truth_profiles, truth_utility
from .rules import build_hard_rules, build_participant_hard, build_soft_rules


def _dep_edges(scenario) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for dep in scenario.active_dependencies():
        r = dep.get("rule")
        if r == "availability":
            edges.append((dep["subject"], dep["over"]))
        elif r == "membership":
            edges.append((dep["subject"], dep["region_axis"]))
        elif r == "availability_explicit":
            for a in dep.get("allowed", {}):
                edges.append((dep["subject"], a))
        elif r == "same_region":
            edges.append((dep["a"], dep["b"]))
        elif r in ("conditional_home", "conditional_pref"):
            edges.append((dep["if_axis"], dep["then_axis"]))
    for con in scenario.participants.get("constraints", []):
        if "pairs" in con:
            axes = con["pairs"]["axes"]
            for i in range(len(axes)):
                for j in range(i + 1, len(axes)):
                    edges.append((axes[i], axes[j]))
    return edges


def _vertex_cover(edges: list[tuple[str, str]]) -> set[str]:
    remaining = [e for e in edges if e[0] != e[1]]
    cover: set[str] = set()
    while remaining:
        deg: Counter = Counter()
        for a, b in remaining:
            deg[a] += 1
            deg[b] += 1
        pick = max(deg, key=lambda k: deg[k])
        cover.add(pick)
        remaining = [(a, b) for (a, b) in remaining if a != pick and b != pick]
    return cover


def _partial_ok(hard_rules, partial) -> bool:
    for rule in hard_rules:
        try:
            if not rule(partial):
                return False
        except KeyError:
            continue
    return True


def _soft_choice(soft_rules, partial, n_p: int) -> float:
    total = 0.0
    for p in range(n_p):
        for rule in soft_rules:
            try:
                total += rule(p, partial)
            except KeyError:
                continue
    return total


def exact_xstar(scenario) -> dict:
    """정확한 x*(유효·결렬 포함, 24 정본). unconstrained_valid=False면 하한임(바닥선 조임)."""
    truths = build_truth_profiles(scenario)
    hard = build_hard_rules(scenario) + build_participant_hard(scenario)
    soft = build_soft_rules(scenario, [t.home_region for t in truths])
    thresholds = [t.initial_threshold for t in truths]
    n_p = len(truths)

    cover = _vertex_cover(_dep_edges(scenario))
    hub_axes = [ax for ax in scenario.axes if ax.name in cover]
    other_axes = [ax for ax in scenario.axes if ax.name not in cover]
    hub_combos = itertools.product(*[ax.values for ax in hub_axes]) if hub_axes else [()]

    best_total = None
    best_outcome = None
    best_valid_total = None
    for combo in hub_combos:
        hub = {ax.name: v for ax, v in zip(hub_axes, combo)}
        if not _partial_ok(hard, hub):
            continue
        outcome = dict(hub)
        feasible = True
        for ax in other_axes:
            best_v, best_score = None, None
            for v in ax.values:
                trial = {**hub, ax.name: v}
                if not _partial_ok(hard, trial):
                    continue
                base = sum(truths[p].weights[ax.name] * truths[p].scores[ax.name][v.name]
                           for p in range(n_p))
                score = base - _soft_choice(soft, trial, n_p)
                if best_score is None or score > best_score:
                    best_v, best_score = v, score
            if best_v is None:
                feasible = False
                break
            outcome[ax.name] = best_v
        if not feasible:
            continue
        us = [truth_utility(truths[p], p, outcome, soft) for p in range(n_p)]
        total = sum(us)
        if best_total is None or total > best_total:
            best_total, best_outcome = total, dict(outcome)
        if all(us[p] >= thresholds[p] - 1e-9 for p in range(n_p)):
            if best_valid_total is None or total > best_valid_total:
                best_valid_total = total

    breakdown_total = sum(thresholds)
    valid_candidates = [breakdown_total] + ([best_valid_total] if best_valid_total is not None else [])
    u_xstar = max(valid_candidates)
    return {
        "u_xstar": u_xstar,
        "unconstrained_total": best_total,
        "unconstrained_valid": best_valid_total is not None and abs(best_valid_total - best_total) < 1e-9,
        "breakdown_total": breakdown_total,
        "outcome": {k: v.name for k, v in best_outcome.items()} if best_outcome else None,
    }
