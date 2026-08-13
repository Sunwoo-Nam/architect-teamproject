#!/usr/bin/env python3
"""composite 세분화 raw 실험 — FC·RU·SC-의제·TB를 케이스 단위로 저장 (PL 지시 2026-08-13).

nparty_tracks.py와 동형: 한 번 돌리면 케이스×방안 원값이 파일로 남아, 이후의 임의
재집계(시나리오 유형별·규모별 취합 등)는 재시뮬레이션 없이 raw에서 수행한다.

측정 QA (PL 확정): FC · RU-메모리 · SC-의제 · TB(ρ). CF는 composite 비대상.

케이스 구성:
- **오라클 케이스** (조합 S ≤ 한도): FC(달성률·R̄·s) + RU + TB(ρ) 전부.
- **대규모 케이스** (S > 한도, 예: S11 977만): FC는 오라클 불가라 null로 명시하고
  RU·TB(ρ)는 계산한다 — baseline은 해석적(열거 없음)이라 규모 무관 (24 §4.2).
- **SC-의제 스윕**: 축 수준별 경량 실행 — 판정(최대 의제 수)의 입력. sweep.jsonl로 저장.

출력: results/composite-tracks/<ts>/ 에 raw.json(집계) + cases.jsonl + sweep.jsonl
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from total import pyversion  # noqa: E402,F401
from total.adapters.composite import (  # noqa: E402
    PLANS, CompositeCase, load, run_session, run_sweep_point, scenario_paths,
)
from total.adapters.composite._vendor.harness.runner import run_one  # noqa: E402
from total.adapters.composite.baseline import baseline_t  # noqa: E402
from total.qa import fc, ru, sc_issue, tb  # noqa: E402
from total.qa.constants import (  # noqa: E402
    RU_CEILING_BYTES, SYNTH_TIME, band_ru_usage,
)
from total.qa.ru import deep_size  # noqa: E402

PLAN_NAMES = ("seq2", "pool")
ORACLE_LIMIT = 200_000          # FC 전수 열거 한도 — 초과 시 fc=null 명시
SWEEP_AXES = (4, 6, 8, 10)      # 축 수준 — 시나리오가 보유한 축까지 자동 절단


def _base_one_device(scenario) -> int:
    """1인 기저 근사 — 축 수준 표현 (24 §2.8, 조합 열거 없음)."""
    return deep_size(scenario.axes) + deep_size(scenario.participants) // max(
        1, scenario.n_participants)


def _tb_from_counters(scenario, run) -> dict:
    """대규모 케이스의 T — 계수에서 직접 합성 (eval = N×S 해석)."""
    c = SYNTH_TIME
    S = max(1, scenario.space_size())
    n = max(1, scenario.n_participants)
    eval_calls = run.eval_calls or n * min(S, 10**12)
    phase_ms = run.phases * c.t_phase_ms
    eval_ms = eval_calls / n * c.t_eval_ms
    transfer_ms = run.bytes / c.bw_bytes_per_s * 1000
    return {"total_ms": phase_ms + eval_ms + transfer_ms,
            "phase_ms": phase_ms, "eval_ms": eval_ms, "transfer_ms": transfer_ms}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="시나리오 수 상한 (스모크용)")
    args = ap.parse_args()

    paths = scenario_paths()[: args.limit] if args.limit else scenario_paths()
    scenarios = [load(p) for p in paths]
    wall0 = time.perf_counter()

    # TB baseline — 시나리오당 1회, 방안 무관 공용 (해석적 — 대규모 포함)
    baselines = {}
    t0 = time.perf_counter()
    for sc in scenarios:
        baselines[sc.id] = baseline_t(sc)
    sec_baseline = round(time.perf_counter() - t0, 1)

    raw = {"tracks": {"scenarios": {}, "sweep": {}},
           "sec_baseline": sec_baseline, "qa": ["fc", "ru", "sc_issue", "tb"],
           "note": "CF는 composite 비대상 (PL 확정 2026-08-13). 대규모 케이스는 fc=null "
                   "(오라클 불가 명시) — RU·TB는 유효"}
    case_rows, sweep_rows = [], []

    for plan in PLAN_NAMES:
        t0 = time.perf_counter()
        scores, mems, times, rhos = [], [], [], []
        for sc in scenarios:
            b = baselines[sc.id]
            if sc.space_size() <= ORACLE_LIMIT:
                session, case = run_session(sc, plan)
                score = fc.score(case, session.agreement,
                                 extra_violations=case.hard_violations(session.agreement))
                mem = ru.measure(session)
                t = tb.synth_time(session)
                rho = tb.rho(t.total_ms, b["T_ms"], b.get("capped", False))
                scores.append(score); mems.append(mem); times.append(t); rhos.append(rho)
                case_rows.append({
                    "case_id": sc.id, "plan": plan, "oracle": True,
                    "n_issues": len(sc.axes), "S": sc.space_size(),
                    "agreed": session.agreed,
                    "achieved": round(score.achieved, 6),
                    "baseline_R": round(score.baseline, 6), "s": round(score.s, 6),
                    "fr_violations": score.fr_violations,
                    "peak_bytes": session.peak_bytes, "base_bytes": session.base_bytes,
                    "total_mb": round(mem.total_mb, 4),
                    "r_total": round(mem.r_total, 6), "ru_stars": mem.stars,
                    "over_ceiling": mem.over_ceiling,
                    "T_ms": round(t.total_ms, 3), "T_phase_ms": round(t.phase_ms, 3),
                    "T_baseline_ms": b["T_ms"], "baseline_k": b["proposals_k*"],
                    "baseline_capped": b["capped"],
                    "rho": rho["rho"], "rho_defect": rho["defect"],
                    "rounds": session.rounds, "phases": session.phases,
                    "messages": session.messages, "bytes": session.bytes,
                })
            else:
                run = run_one(sc, plan)
                base1 = _base_one_device(sc)
                peak = int(run.peak_kib * 1024)
                total = base1 + peak
                r_total = total / RU_CEILING_BYTES
                tt = _tb_from_counters(sc, run)
                rho = tb.rho(tt["total_ms"], b["T_ms"], b.get("capped", False))
                rhos.append(rho)
                case_rows.append({
                    "case_id": sc.id, "plan": plan, "oracle": False,
                    "n_issues": len(sc.axes), "S": sc.space_size(),
                    "agreed": run.agreement is not None,
                    "achieved": None, "baseline_R": None, "s": None,  # 오라클 불가 명시
                    "fr_violations": None,
                    "peak_bytes": peak, "base_bytes": base1,
                    "total_mb": round(total / (1024 * 1024), 4),
                    "r_total": round(r_total, 6),
                    "ru_stars": band_ru_usage().stars(r_total),
                    "over_ceiling": total > RU_CEILING_BYTES,
                    "T_ms": round(tt["total_ms"], 3), "T_phase_ms": round(tt["phase_ms"], 3),
                    "T_baseline_ms": b["T_ms"], "baseline_k": b["proposals_k*"],
                    "baseline_capped": b["capped"],
                    "rho": rho["rho"], "rho_defect": rho["defect"],
                    "rounds": run.rounds, "phases": run.phases,
                    "messages": run.messages, "bytes": run.bytes,
                })
        sec_cases = round(time.perf_counter() - t0, 1)

        # SC-의제 스윕 (경량 실행 — sweep.jsonl 세분화 저장)
        t0 = time.perf_counter()
        points = []
        sweep_source = next((sc for sc in scenarios if len(sc.axes) >= max(SWEEP_AXES)),
                            scenarios[-1])
        for n_axes in SWEEP_AXES:
            if n_axes > len(sweep_source.axes):
                continue
            # 축 절단 로드 — 스윕 소스 시나리오의 앞 n개 축만 사용
            from total.adapters.composite._vendor.common.scenario import load_scenario
            sub = load_scenario(paths[scenarios.index(sweep_source)], n_axes=n_axes)
            pt = run_sweep_point(sub, plan, n_issues=n_axes)
            points.append(pt)
            sweep_rows.append({
                "plan": plan, "n_issues": n_axes, "scale": pt.scale,
                "peak_bytes": pt.peak_bytes, "base_bytes": pt.base_bytes,
                "total_bytes": pt.total_bytes, "agreed": pt.agreed,
            })
        sec_sweep = round(time.perf_counter() - t0, 1)

        d_med = statistics.median_low([p.n_issues for p in points]) if points else 4
        raw["tracks"]["scenarios"][plan] = {
            "sec": sec_cases,
            "fc": fc.aggregate(scores) if scores else None,
            "ru": ru.aggregate(mems) if mems else None,
            "tb": {**(tb.aggregate(times) if times else {}), **tb.aggregate_rho(rhos)},
            "oracle_cases": len(scores), "big_cases": len(scenarios) - len(scores),
        }
        raw["tracks"]["sweep"][plan] = {
            "sec": sec_sweep,
            "sc_issue": sc_issue.evaluate(points, d=d_med) if len(points) >= 3 else None,
        }
        f = raw["tracks"]["scenarios"][plan]
        print(f"  {plan}: FC s={f['fc']['mean_s'] if f['fc'] else None} | "
              f"RU r중앙={f['ru']['median_r_total'] if f['ru'] else None} | "
              f"TB ρ중앙={f['tb'].get('median_rho')} ★{f['tb'].get('stars')} | "
              f"SC-의제 최대축={raw['tracks']['sweep'][plan]['sc_issue']['max_issues']['max_issues'] if raw['tracks']['sweep'][plan]['sc_issue'] else None} "
              f"[케이스 {sec_cases}s + 스윕 {sec_sweep}s]")

    raw["wall_seconds"] = round(time.perf_counter() - wall0, 1)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out_dir = ROOT / "results" / "composite-tracks" / f"composite-tracks-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1, default=str))
    with open(out_dir / "cases.jsonl", "w") as f_:
        for r in case_rows:
            f_.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(out_dir / "sweep.jsonl", "w") as f_:
        for r in sweep_rows:
            f_.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n총 소요 {raw['wall_seconds']}초 → 저장: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
