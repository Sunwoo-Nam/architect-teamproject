"""고정 테스트(fixture) — 축·후보·프로파일·정답 x*를 파일에 박제해 재현 100% 보장.

시드 생성에 의존하지 않고 JSON에 모든 것을 명시한다. 로드 시 Scenario.frozen_profiles로
프로파일을 고정해, 돌릴 때마다 같은 테스트·같은 정답이 된다.
"""
from __future__ import annotations

import json
from pathlib import Path

from .exact import exact_xstar
from .generators import Value
from .profiles import TruthProfile, build_truth_profiles
from .scenario import Axis, Scenario


def dump_fixture(scenario: Scenario, path: str | Path, name: str) -> dict:
    """scenario(생성/고정 무관)를 완전 명시 JSON으로 박제. 정답 x*도 함께 계산·저장."""
    truths = build_truth_profiles(scenario)
    known = exact_xstar(scenario)
    doc = {
        "name": name,
        "meta": dict(scenario.meta),
        "space_size": scenario.space_size(),
        "n_axes": len(scenario.axes),
        "axes": [
            {"name": ax.name, "generator": ax.generator,
             "values": [{"name": v.name, "attrs": v.attrs} for v in ax.values]}
            for ax in scenario.axes
        ],
        "dependencies": scenario.dependencies,
        "participants": {k: v for k, v in scenario.participants.items()},
        "agent_view": scenario.agent_view,
        "judge": scenario.judge,
        "profiles": [
            {"weights": t.weights, "scores": t.scores,
             "home_region": t.home_region, "initial_threshold": t.initial_threshold}
            for t in truths
        ],
        "known_answer": {
            "u_xstar": known["u_xstar"],
            "outcome": known["outcome"],
            "unconstrained_valid": known["unconstrained_valid"],
            "breakdown_total": known["breakdown_total"],
        },
    }
    Path(path).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc


def load_fixture(path: str | Path) -> tuple[Scenario, dict]:
    """fixture JSON → (Scenario[frozen_profiles 세팅됨], known_answer)."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    axes = [
        Axis(a["name"], a["generator"],
             [Value(v["name"], dict(v.get("attrs", {}))) for v in a["values"]])
        for a in doc["axes"]
    ]
    sc = Scenario(
        meta=doc["meta"], axes=axes, dependencies=doc["dependencies"],
        participants=doc["participants"], agent_view=doc["agent_view"], judge=doc["judge"],
    )
    sc.frozen_profiles = [
        TruthProfile(weights=p["weights"], scores=p["scores"],
                     home_region=p["home_region"], initial_threshold=p["initial_threshold"])
        for p in doc["profiles"]
    ]
    return sc, doc["known_answer"]
