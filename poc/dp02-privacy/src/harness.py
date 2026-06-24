"""Harness — 시나리오 × 방안 × 게이트결함 루프, 유출 측정, 결과 기록.

실행:  python3 poc/dp02-privacy/src/harness.py            # 전 시나리오
       python3 poc/dp02-privacy/src/harness.py S1 S3      # 일부

이 단계는 LLM 없는 결정적 코어다(StubEngine·rule/oracle 분류기).
방안1/방안2 대비를 게이트 결함별로 보인다. LLM 백엔드는 Ollama 설치 후 추가.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scenario import load_scenario          # noqa: E402
from config import GATE_PRESETS             # noqa: E402
from mediator import PrivacyMediator        # noqa: E402
from vault import PrivacyVault              # noqa: E402
from engine import StubEngine               # noqa: E402
from counterpart import StubCounterpart     # noqa: E402
from gate import sanitize, verify           # noqa: E402
from egress_monitor import EgressMonitor    # noqa: E402
from leak_oracle import LeakOracle          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCEN = os.path.join(ROOT, "scenarios")
RESULTS = os.path.join(ROOT, "results")
APPROACHES = ["filter_at_egress", "transform_at_ingress"]
GATES = ["complete", "extra_field", "granularity"]


def run_once(scenario, approach, gate, classifier_backend="rule"):
    vault = PrivacyVault()
    safescope = None
    if approach == "transform_at_ingress":
        safescope = PrivacyMediator(classifier_backend).transform(scenario, vault)

    proposal = StubEngine().propose(approach, scenario, safescope)
    payload = dict(proposal["payload"])
    if approach == "filter_at_egress":
        payload = sanitize(payload, scenario.case, scenario.authorization, gate)
    else:
        payload = verify(payload, vault)
    gated = {**proposal, "payload": payload}

    mon = EgressMonitor()
    mon.record(gated)
    StubCounterpart().respond(gated)         # 수락 → 1라운드

    findings = LeakOracle().score(mon.messages, scenario.secrets)
    return {
        "scenario": scenario.id, "case": scenario.case,
        "approach": approach, "gate": gate.label, "classifier": classifier_backend,
        "egress_payload": gated["payload"],
        "leak_count": len(findings),
        "leaks": sorted({f["secret"] for f in findings}),
        "rounds": 1, "agreement": True,
        "vault_tokens": (len(vault.map) if safescope else 0),
        "blocked_private": (safescope.blocked if safescope else None),
    }


def main():
    ids = sys.argv[1:] or [f"S{i}" for i in range(1, 11)]
    os.makedirs(RESULTS, exist_ok=True)
    rows = []
    for sid in ids:
        sc = load_scenario(os.path.join(SCEN, f"{sid}.yaml"))
        for approach in APPROACHES:
            for gp in GATES:
                rows.append(run_once(sc, approach, GATE_PRESETS[gp]))

    with open(os.path.join(RESULTS, "deterministic_run.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"{'scn':<4} {'approach':<22} {'gate':<12} {'leak':<4} leaks")
    print("-" * 70)
    for r in rows:
        print(f"{r['scenario']:<4} {r['approach']:<22} {r['gate']:<12} "
              f"{r['leak_count']:<4} {', '.join(r['leaks'])}")


if __name__ == "__main__":
    main()
