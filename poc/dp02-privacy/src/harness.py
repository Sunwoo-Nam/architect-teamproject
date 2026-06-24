"""Harness — 시나리오 × 방안 × 게이트결함 루프, 유출 측정, 결과 기록.

결정적 모드(LLM 없음):
    python3 src/harness.py                 # 전 시나리오, StubEngine
    python3 src/harness.py S1 S3

LLM 모드(Ollama + qwen3.5):
    python3 src/harness.py --llm           # 기본 S1·S3
    python3 src/harness.py --llm S3 S10
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scenario import load_scenario          # noqa: E402
from config import GATE_PRESETS             # noqa: E402
from mediator import PrivacyMediator        # noqa: E402
from vault import PrivacyVault              # noqa: E402
from engine import StubEngine, LLMEngine    # noqa: E402
from counterpart import StubCounterpart, LLMCounterpart  # noqa: E402
from gate import sanitize, verify           # noqa: E402
from egress_monitor import EgressMonitor    # noqa: E402
from leak_oracle import LeakOracle, LLMJudge  # noqa: E402
from ollama_client import OllamaClient, available_models  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCEN = os.path.join(ROOT, "scenarios")
RESULTS = os.path.join(ROOT, "results")
APPROACHES = ["filter_at_egress", "transform_at_ingress"]

ON_MODEL = "qwen3.5:4b"
CP_MODEL = "qwen3.5:9b"


# ───────────────────────── 결정적 모드 ─────────────────────────
def run_once(scenario, approach, gate, classifier_backend="rule"):
    vault = PrivacyVault()
    safescope = None
    if approach == "transform_at_ingress":
        safescope = PrivacyMediator(classifier_backend).transform(scenario, vault)
    proposal = StubEngine().propose(approach, scenario, safescope)
    payload = (sanitize(proposal["payload"], scenario.case, scenario.authorization, gate)
               if approach == "filter_at_egress" else verify(proposal["payload"], vault))
    gated = {**proposal, "payload": payload}
    mon = EgressMonitor()
    mon.record(gated)
    StubCounterpart().respond(gated)
    findings = LeakOracle().score(mon.messages, scenario.secrets)
    return {"scenario": scenario.id, "approach": approach, "gate": gate.label,
            "leak_count": len(findings), "leaks": sorted({f["secret"] for f in findings}),
            "rounds": 1, "agreement": True}


def run_deterministic(ids):
    rows = []
    for sid in ids:
        sc = load_scenario(os.path.join(SCEN, f"{sid}.yaml"))
        for approach in APPROACHES:
            for gp in ("complete", "extra_field", "granularity"):
                rows.append(run_once(sc, approach, GATE_PRESETS[gp]))
    _save("deterministic_run.json", rows)
    _print(rows)


# ───────────────────────── LLM 모드 ─────────────────────────
def run_llm_once(scenario, approach, gate, on_client, cp_client, judge_client,
                 classifier_backend="rule", max_rounds=3):
    vault = PrivacyVault()
    safescope = None
    if approach == "transform_at_ingress":
        safescope = PrivacyMediator(classifier_backend).transform(scenario, vault)

    engine, cp = LLMEngine(on_client), LLMCounterpart(cp_client)
    mon = EgressMonitor()
    incoming, agreement, rounds = None, False, 0
    for r in range(max_rounds):
        rounds = r + 1
        proposal = engine.propose(approach, scenario, safescope, incoming)
        payload = (sanitize(proposal["payload"], scenario.case, scenario.authorization, gate)
                   if approach == "filter_at_egress" else verify(proposal["payload"], vault))
        gated = {**proposal, "payload": payload}
        mon.record(gated)
        resp = cp.respond(gated, scenario, r)
        if resp.get("decision") == "accept":
            agreement = True
            break
        incoming = f"상대 질문: {resp.get('probe')}" if resp.get("probe") else "상대가 재협상을 요청함"

    det = LeakOracle().score(mon.messages, scenario.secrets)
    judge = LLMJudge(judge_client).score(mon.messages, scenario.secrets)
    leaks = sorted({f["secret"] for f in det + judge})
    return {"scenario": scenario.id, "approach": approach, "gate": gate.label,
            "leak_count": len(leaks), "leaks": leaks,
            "det": len(det), "judge": len(judge),
            "rounds": rounds, "agreement": agreement,
            "egress": [m.get("payload") for m in mon.messages]}


def run_llm(ids):
    models = available_models()
    cp_model = CP_MODEL if CP_MODEL in models else ON_MODEL
    if cp_model != CP_MODEL:
        print(f"[경고] {CP_MODEL} 없음 → LLM-cp도 {ON_MODEL} 사용")
    on_client = OllamaClient(ON_MODEL, seed=0)
    cp_client = OllamaClient(cp_model, seed=0)
    judge_client = OllamaClient(cp_model, seed=0)

    rows = []
    for sid in ids:
        sc = load_scenario(os.path.join(SCEN, f"{sid}.yaml"))
        for approach in APPROACHES:
            for gp in ("complete", "freeform_note"):
                print(f"... {sid} {approach} {gp}", flush=True)
                rows.append(run_llm_once(sc, approach, GATE_PRESETS[gp],
                                         on_client, cp_client, judge_client))
    _save("llm_run.json", rows)
    print(f"\n{'scn':<4} {'approach':<22} {'gate':<14} {'leak':<4} {'det':<3} {'jdg':<3} {'rnd':<3} leaks")
    print("-" * 80)
    for r in rows:
        print(f"{r['scenario']:<4} {r['approach']:<22} {r['gate']:<14} "
              f"{r['leak_count']:<4} {r['det']:<3} {r['judge']:<3} {r['rounds']:<3} "
              f"{', '.join(r['leaks'])}")


# ───────────────────────── 공통 ─────────────────────────
def _save(name, rows):
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, name), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def _print(rows):
    print(f"{'scn':<4} {'approach':<22} {'gate':<12} {'leak':<4} leaks")
    print("-" * 70)
    for r in rows:
        print(f"{r['scenario']:<4} {r['approach']:<22} {r['gate']:<12} "
              f"{r['leak_count']:<4} {', '.join(r['leaks'])}")


def main():
    args = sys.argv[1:]
    if "--llm" in args:
        ids = [a for a in args if not a.startswith("--")] or ["S1", "S3"]
        run_llm(ids)
    else:
        ids = args or [f"S{i}" for i in range(1, 11)]
        run_deterministic(ids)


if __name__ == "__main__":
    main()
