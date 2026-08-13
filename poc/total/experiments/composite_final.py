#!/usr/bin/env python3
"""composite 정본(final) 측정 — FIN 데이터셋 500건 × 방안 2종 (PL 지시 2026-08-13).

nparty_tracks.py와 동형: 케이스×방안 원값을 cases.jsonl로 남겨, 이후의 임의 재집계
(유형별·축 수별·함정 실효 등)는 재시뮬레이션 없이 raw에서 수행한다.

- **CR 트랙** (조합 ≤ 오라클 한도): FC(달성률·R̄·s·FR) + RU + TB(ρ) 전부.
- **RS 트랙** (조합 최대 10^13): FC는 오라클 불가라 null 명시 — RU(실물화 포함)·TB(ρ)만.
- 측정 범위 FC·RU·TB (campaign.QA_COMPOSITE — CF는 nparty 담당).
- RU 별점은 로그(데케이드) 사다리 (24 §2.8 개정 2026-08-13).

출력: results/composite-final/composite-final-<ts>/ — raw.json(집계) + cases.jsonl
     + meta.json. 재집계·보고 표는 scripts/aggregate_composite_final.py.
"""
from __future__ import annotations

import argparse
import json
import platform
import signal
import statistics
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from total import pyversion  # noqa: E402
from total.adapters.composite import (  # noqa: E402
    CompositeCase,
    load_fixture,
    run_session,
)
from total.adapters.composite.baseline import baseline_t  # noqa: E402
from total.qa import fc, ru, tb  # noqa: E402
from total.qa.constants import RU_CEILING_BYTES, SYNTH_TIME, band_ru_usage  # noqa: E402

FINAL_DIR = ROOT / "datasets" / "composite" / "final"
PLAN_NAMES = ("seq2", "pool")
ORACLE_LIMIT = 150_000


def _git_commit():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except Exception:
        return None


def _tb_from_counters(scenario, run) -> dict:
    """경량(RS) 케이스의 합성 T — 러너 계수에서 직접 (오라클·열거 없음)."""
    c = SYNTH_TIME
    n = max(1, scenario.n_participants)
    phase_ms = run.phases * c.t_phase_ms
    eval_ms = (run.eval_calls or 0) / n * c.t_eval_ms
    transfer_ms = run.bytes / c.bw_bytes_per_s * 1000
    return {"total_ms": phase_ms + eval_ms + transfer_ms, "phase_ms": phase_ms,
            "eval_ms": eval_ms, "transfer_ms": transfer_ms}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None, help="케이스 수 상한 (파일럿용)")
    ap.add_argument("--only", default=None, help="유형 필터 (예: pool_trap)")
    ap.add_argument("--allow-python-mismatch", action="store_true")
    args = ap.parse_args()
    pyversion.require(args.allow_python_mismatch)

    paths = sorted(FINAL_DIR.glob("FIN-*.json"))
    if args.only:
        paths = [p for p in paths if json.loads(p.read_text())["meta"]["type"] == args.only]
    if args.limit:
        paths = paths[: args.limit]
    scenarios = [load_fixture(p) for p in paths]
    print(f"FIN 케이스 {len(scenarios)}건 · 방안 {list(PLAN_NAMES)}")
    wall0 = time.perf_counter()

    @contextmanager
    def _deadline(seconds):
        def _h(signum, frame):
            raise TimeoutError(f"{seconds}s 초과")
        old = signal.signal(signal.SIGALRM, _h)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)

    # baseline은 케이스별로 실패할 수 있다 (RS 규모에서 lazy k-best 탐색 한도 —
    # POP_CAP / 벽시계). 실패는 기록하고 해당 케이스의 ρ만 비운다 — RU는 유효하다.
    baselines, baseline_failures = {}, []
    t0 = time.perf_counter()
    for sc in scenarios:
        try:
            with _deadline(90):
                baselines[sc.id] = baseline_t(sc)
        except Exception as exc:
            baselines[sc.id] = None
            baseline_failures.append((sc.id, f"{type(exc).__name__}: {exc}"))
    sec_baseline = round(time.perf_counter() - t0, 1)
    print(f"  TB baseline {len(baselines) - len(baseline_failures)}건 성공 · "
          f"{len(baseline_failures)}건 실패 ({sec_baseline}s)")

    raw = {"qa": ["fc", "ru", "tb"], "plans": {}, "sec_baseline": sec_baseline,
           "baseline_failures": baseline_failures,
           "meta": {
               "dataset": "composite final (FIN)", "cases": len(scenarios),
               "commit": _git_commit(), "python": platform.python_version(),
               "constants": SYNTH_TIME.as_dict(),
               "ru_band": band_ru_usage().as_dict(),
               "judgement": "FC=달성률 · RU=사용률 r P95 로그 사다리(2026-08-13 개정) · TB=ρ P95",
           }}
    case_rows = []

    for plan in PLAN_NAMES:
        t0 = time.perf_counter()
        scores, mems, times, rhos = [], [], [], []
        for sc, path in zip(scenarios, paths):
            meta = sc.meta
            b = baselines[sc.id]
            oracle = sc.space_size() <= ORACLE_LIMIT and meta.get("track") == "cr"
            row = {
                "case_id": sc.id, "plan": plan, "track": meta.get("track"),
                "type": meta.get("type"), "conflict": meta.get("conflict_level"),
                "expected": meta.get("expected"), "oracle": oracle,
                "n_issues": len(sc.axes), "S": sc.space_size(),
                "planted": meta.get("planted", {}).get("trap"),
            }
            if oracle:
                session, case = run_session(sc, plan)
                score = fc.score(case, session.agreement,
                                 extra_violations=case.hard_violations(session.agreement))
                mem = ru.measure(session)
                t = tb.synth_time(session)
                rho = (tb.rho(t.total_ms, b["T_ms"], b.get("capped", False))
                       if b else {"rho": None, "defect": None})
                scores.append(score); mems.append(mem); times.append(t)
                if rho["rho"] is not None:
                    rhos.append(rho)
                row.update({
                    "agreed": session.agreed,
                    "achieved": round(score.achieved, 6),
                    "baseline_R": round(score.baseline, 6), "s": round(score.s, 6),
                    "fr_violations": score.fr_violations,
                    "T_ms": round(t.total_ms, 3),
                    "peak_bytes": session.peak_bytes, "base_bytes": session.base_bytes,
                    "materialized_bytes": session.materialized_bytes,
                    "total_mb": round(mem.total_mb, 4),
                    "r_total": round(mem.r_total, 8), "ru_stars": mem.stars,
                    "over_ceiling": mem.over_ceiling,
                })
            else:
                session, _ = run_session(sc, plan, light=True)
                mem = ru.measure(session)
                tt = _tb_from_counters(sc, session)
                rho = (tb.rho(tt["total_ms"], b["T_ms"], b.get("capped", False))
                       if b else {"rho": None, "defect": None})
                mems.append(mem)
                if rho["rho"] is not None:
                    rhos.append(rho)
                row.update({
                    "agreed": session.agreed,
                    "achieved": None, "baseline_R": None, "s": None,
                    "fr_violations": None,
                    "T_ms": round(tt["total_ms"], 3),
                    "peak_bytes": session.peak_bytes, "base_bytes": session.base_bytes,
                    "materialized_bytes": session.materialized_bytes,
                    "total_mb": round(mem.total_mb, 4),
                    "r_total": round(mem.r_total, 8), "ru_stars": mem.stars,
                    "over_ceiling": mem.over_ceiling,
                })
            row.update({
                "T_baseline_ms": b["T_ms"] if b else None,
                "baseline_capped": b["capped"] if b else None,
                "rho": rho["rho"], "rho_defect": rho["defect"],
                "rounds": session.rounds, "phases": session.phases,
                "messages": session.messages, "bytes": session.bytes,
            })
            case_rows.append(row)
        sec = round(time.perf_counter() - t0, 1)
        raw["plans"][plan] = {
            "sec": sec,
            "fc": fc.aggregate(scores) if scores else None,
            "ru": ru.aggregate(mems) if mems else None,
            "tb": {**(tb.aggregate(times) if times else {}), **tb.aggregate_rho(rhos)},
            "oracle_cases": len(scores), "light_cases": len(scenarios) - len(scores),
        }
        f_ = raw["plans"][plan]
        print(f"  {plan}: FC={f_['fc']['mean_achieved'] if f_['fc'] else None} "
              f"★{f_['fc']['stars_achieved'] if f_['fc'] else '-'} · "
              f"RU rP95 {f_['ru']['p95_r_total']} ★{f_['ru']['stars_p95']} "
              f"(중앙 ★{f_['ru']['stars_median']} · max ★{f_['ru']['stars_max']}) · "
              f"TB ρP95 {f_['tb'].get('p95_rho')} ★{f_['tb'].get('stars')} [{sec}s]")

    raw["wall_seconds"] = round(time.perf_counter() - wall0, 1)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out_dir = ROOT / "results" / "composite-final" / f"composite-final-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "raw.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=1, default=str))
    with open(out_dir / "cases.jsonl", "w") as fh:
        for r in case_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n총 {raw['wall_seconds']}초 → 저장: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
