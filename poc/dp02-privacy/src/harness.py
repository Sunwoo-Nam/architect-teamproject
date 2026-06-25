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
import statistics
from time import perf_counter

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
from ollama_client import OllamaClient, available_models, ollama_rss_bytes  # noqa: E402

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
        # perfect 모드: 정답지로 비밀을 제외(변환 분류 완벽 가정 — 메커니즘 격리)
        safescope = PrivacyMediator(classifier_backend).transform(
            scenario, vault, scenario.secrets)

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
                                         on_client, cp_client, judge_client,
                                         max_rounds=2))
    _save("llm_run.json", rows)
    print(f"\n{'scn':<4} {'approach':<22} {'gate':<14} {'leak':<4} {'det':<3} {'jdg':<3} {'rnd':<3} leaks")
    print("-" * 80)
    for r in rows:
        print(f"{r['scenario']:<4} {r['approach']:<22} {r['gate']:<14} "
              f"{r['leak_count']:<4} {r['det']:<3} {r['judge']:<3} {r['rounds']:<3} "
              f"{', '.join(r['leaks'])}")


# ───────────────────────── 벤치(속도·리소스) 모드 ─────────────────────────
# 상대(9b)는 stub 처리 — LLM-on(4b)+프라이버시 처리만 깨끗하게 계측한다.
_PROBE = "상대가 더 구체적인 시간/이유를 물었습니다."


def run_bench_once(scenario, approach, classifier_backend, on_client, n_rounds):
    """단계별 분해 계측: LLM 시간(분류/제안)과 순수 처리 시간(변환/게이트)을 분리."""
    import psutil
    on_client.reset()
    vault = PrivacyVault()
    safescope = None
    rss_peak = ollama_rss_bytes()
    proc = psutil.Process()
    proc.cpu_percent(None)

    # ── ingress 변환(방안2): LLM 분류 시간과 순수 처리 시간을 분리 ──
    t_classify_llm, classify_calls, t_transform_cpu = 0.0, 0, 0.0
    if approach == "transform_at_ingress":
        t0 = perf_counter()
        safescope = PrivacyMediator(classifier_backend).transform(
            scenario, vault, scenario.secrets,
            client=on_client if classifier_backend == "llm" else None)
        t_transform_wall = perf_counter() - t0
        s1 = on_client.stats()                       # 변환이 쓴 LLM 시간/호출
        t_classify_llm, classify_calls = s1["t_llm_s"], s1["calls"]
        t_transform_cpu = max(0.0, t_transform_wall - t_classify_llm)

    # ── 라운드: 제안(LLM) + 게이트(CPU) ──
    engine = LLMEngine(on_client)
    incoming, t_gate = None, 0.0
    for r in range(n_rounds):
        proposal = engine.propose(approach, scenario, safescope, incoming)
        t0 = perf_counter()
        if approach == "filter_at_egress":
            sanitize(proposal["payload"], scenario.case, scenario.authorization,
                     GATE_PRESETS["complete"])
        else:
            verify(proposal["payload"], vault)
        t_gate += perf_counter() - t0
        rss_peak = max(rss_peak, ollama_rss_bytes())
        incoming = _PROBE

    st = on_client.stats()
    t_propose_llm = max(0.0, st["t_llm_s"] - t_classify_llm)
    t_priv_cpu = t_transform_cpu + t_gate
    vault_bytes = sum(len(str(k)) + len(str(v)) for k, v in vault.map.items())
    return {"scenario": scenario.id, "approach": approach, "classifier": classifier_backend,
            "n_rounds": n_rounds,
            "t_session_s": round(st["t_llm_s"] + t_priv_cpu, 4),
            "t_llm_total_s": round(st["t_llm_s"], 4),
            "t_classify_llm_s": round(t_classify_llm, 4),    # ingress 분류 LLM(방안2·llm)
            "t_propose_llm_s": round(t_propose_llm, 4),       # 협상 제안 LLM
            "t_transform_cpu_s": round(t_transform_cpu, 6),   # 변환 순수 처리
            "t_gate_cpu_s": round(t_gate, 6),                 # 게이트 순수 처리(라운드 합)
            "t_privacy_cpu_s": round(t_priv_cpu, 6),
            "llm_calls": st["calls"], "classify_calls": classify_calls,
            "propose_calls": st["calls"] - classify_calls,
            "tokens_in": st["tokens_in"], "tokens_out": st["tokens_out"],
            "vault_bytes": vault_bytes, "ollama_rss_mb": round(rss_peak / 1e6, 1),
            "cpu_pct": round(proc.cpu_percent(None), 1)}


def _bench_key(r):
    return (r["phase"], r["scenario"], r["approach"], r["classifier"], r["n_rounds"], r["rep"])


def run_bench(ids, R=10):
    on_client = OllamaClient(ON_MODEL, seed=0)
    os.makedirs(RESULTS, exist_ok=True)
    jsonl = os.path.join(RESULTS, "bench.jsonl")

    rows, done = [], set()
    if os.path.exists(jsonl):                      # 이어하기: 기존 진행분 로드
        with open(jsonl, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    rows.append(r)
                    done.add(_bench_key(r))
    fout = open(jsonl, "a", encoding="utf-8")

    def do(phase, sid, sc, approach, clf, n, rep):
        key = (phase, sid, approach, clf, n, rep)
        if key in done:
            return
        print(f"... {phase} {sid} {approach} {clf} N{n} rep{rep+1}", flush=True)
        r = {**run_bench_once(sc, approach, clf, on_client, n), "rep": rep, "phase": phase}
        rows.append(r)
        fout.write(json.dumps(r, ensure_ascii=False) + "\n")
        fout.flush()

    # 워밍업(모델 로드 시간 제외)
    LLMEngine(on_client).propose(
        "filter_at_egress", load_scenario(os.path.join(SCEN, f"{ids[0]}.yaml")), None, None)

    for sid in ids:                                # 메인: N=3, 분류기 {rule, llm}
        sc = load_scenario(os.path.join(SCEN, f"{sid}.yaml"))
        for approach in APPROACHES:
            for clf in ("rule", "llm"):
                for rep in range(R):
                    do("main", sid, sc, approach, clf, 3, rep)
    fout.close()  # 크로스오버는 제외(사용자 요청)
    _save("bench.json", rows)
    _bench_summary(rows)


def _mean(xs):
    return round(statistics.mean(xs), 4) if xs else 0


def _bench_summary(rows):
    main = [r for r in rows if r["phase"] == "main"]
    print("\n[메인 — 방안×분류기 평균 (단계별 분해, 전 시나리오·R회)]  단위 초")
    h = (f"{'approach':<22} {'clf':<5} {'t_sess':<7} {'propose':<8} {'classfy':<8} "
         f"{'gate':<7} {'transf':<7} {'calls':<6} {'tok_in':<7} {'rss_mb':<7} {'vault':<6}")
    print(h)
    print("-" * len(h))
    for approach in APPROACHES:
        for clf in ("rule", "llm"):
            g = [r for r in main if r["approach"] == approach and r["classifier"] == clf]
            if not g:
                continue
            print(f"{approach:<22} {clf:<5} "
                  f"{_mean([r['t_session_s'] for r in g]):<7} "
                  f"{_mean([r['t_propose_llm_s'] for r in g]):<8} "
                  f"{_mean([r['t_classify_llm_s'] for r in g]):<8} "
                  f"{_mean([r['t_gate_cpu_s'] for r in g]):<7} "
                  f"{_mean([r['t_transform_cpu_s'] for r in g]):<7} "
                  f"{_mean([r['llm_calls'] for r in g]):<6} "
                  f"{_mean([r['tokens_in'] for r in g]):<7} "
                  f"{_mean([r['ollama_rss_mb'] for r in g]):<7} "
                  f"{_mean([r['vault_bytes'] for r in g]):<6}")


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
    if "--bench" in args:
        ids = [a for a in args if not a.startswith("--")] or [f"S{i}" for i in range(1, 11)]
        run_bench(ids)
    elif "--llm" in args:
        ids = [a for a in args if not a.startswith("--")] or [f"S{i}" for i in range(1, 11)]
        run_llm(ids)
    else:
        ids = args or [f"S{i}" for i in range(1, 11)]
        run_deterministic(ids)


if __name__ == "__main__":
    main()
