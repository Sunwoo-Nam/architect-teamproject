#!/usr/bin/env python3
"""탐색 실험 — nparty 3트랙(functional·scalability·issue-space) 전수에서 FC·CF·TB 측정.

목적 (PL 지시 2026-08-13): 트랙 전수 실행의 실제 소요 시간 확정 + 트랙별/총합 QA 표.
- 판정 정본은 **functional-ext 트랙** (PL 확정 2026-08-13 — 구 functional의 컨셉 그대로
  N 3-50 확장 480건). 나머지 트랙은 강건성 관측
- FC 판정 = **달성률** (PL 확정 2026-08-13 재개정 — s는 보조 관측)
- e₂ 앵커는 **트랙별로 따로** 잰다 (후보 공간 규모가 달라 남의 앵커는 분모 왜곡 — 24 §3)
- 총합: FC = 전 케이스 가중 평균 달성률·R̄ → s (정본 환산 규칙), CF·TB = 케이스(피해자)별
  원값을 이어붙인 중앙값 — CF의 각 값은 자기 트랙 e₂로 정규화된 배수라 병합 가능.

사용: .venv/bin/python experiments/nparty_tracks.py [--limit N(트랙당 케이스 상한)]
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
from total.adapters.nparty import NpartyCase, Profile, run_session  # noqa: E402
from total.adapters.nparty._vendor import issue_space  # noqa: E402
from total.adapters.nparty._vendor.benchmark import CASES_DIR, JsonBenchmarkLoader  # noqa: E402
from total.adapters.nparty.baseline import baseline_t  # noqa: E402
from total.qa import cf, fc, tb  # noqa: E402
from total.qa.constants import BAND_FC_ACHIEVED, BAND_FC_S, BAND_TB_RHO  # noqa: E402

PLANS = ("plan1a", "plan2")
E2_REFERENCE_PLAN = "plan2"
E2_SAMPLES = 30


def _mkcase(bc) -> NpartyCase:
    return NpartyCase(bc.case_id, [Profile(p.pid, dict(p.utilities), p.initial_threshold)
                                   for p in bc.profiles])


def _e2(cases):
    runs = []
    for bc in cases[:E2_SAMPLES]:
        pair = bc.profiles[:2]
        session, _ = run_session(pair, E2_REFERENCE_PLAN)
        runs.append((session, NpartyCase(bc.case_id, [
            Profile(p.pid, dict(p.utilities), p.initial_threshold) for p in pair])))
    return cf.e2_anchor(runs)


def load_tracks(limit):
    tracks = {}
    tracks["functional"] = sorted(JsonBenchmarkLoader(track="functional").cases(),
                                  key=lambda c: c.case_id)[:limit]
    tracks["scalability"] = sorted(JsonBenchmarkLoader(track="scalability").cases(),
                                   key=lambda c: c.case_id)[:limit]
    isc = []
    for track_dir in ("issue-space", "issue-space-b"):
        root = CASES_DIR / track_dir
        if root.exists():
            for path in sorted(root.glob("*.json")):
                try:
                    isc.append(issue_space.expand(issue_space.load_issue_case(path)))
                except Exception:
                    continue
    tracks["issue-space"] = isc[:limit]
    main_root = CASES_DIR.parent / "main"
    if main_root.exists():
        tracks["main"] = [issue_space.expand(issue_space.load_issue_case(f))
                          for f in sorted(main_root.glob("*.json"))][:limit]
    # functional 확장 트랙 (PL 확정 2026-08-13 후자 논의): 컨셉 동일·N 3-50 8레벨×60 균등.
    # cases/ 밖 배치 — 기존 functional 트랙 구성을 바꾸지 않기 위함 (main과 동일 이유).
    ext_root = CASES_DIR.parent / "functional-ext"
    if ext_root.exists():
        tracks["functional-ext"] = sorted(
            JsonBenchmarkLoader(roots=ext_root, track="functional").cases(),
            key=lambda c: c.case_id)[:limit]
    return tracks


def measure_track(name, cases):
    t0 = time.perf_counter()
    anchor = _e2(cases)
    t_e2 = time.perf_counter() - t0

    baselines = {}
    t0 = time.perf_counter()
    for bc in cases:
        baselines[bc.case_id] = baseline_t(bc.profiles, bc.candidates)
    t_base = time.perf_counter() - t0

    out = {"cases": len(cases), "e2_depth": round(anchor.depth, 4),
           "sec_e2": round(t_e2, 1), "sec_baseline": round(t_base, 1)}
    pooled = {}
    case_rows = []  # 세분화 raw — 케이스×방안 1행 (재집계·부분 취합용, PL 지시 2026-08-13)
    for plan in PLANS:
        t0 = time.perf_counter()
        runs, scores, rhos = [], [], []
        for bc in cases:
            session, _ = run_session(bc.profiles, plan)
            case = _mkcase(bc)
            runs.append((session, case))
            scores.append(fc.score(case, session.agreement))
            t = tb.synth_time(session)
            b = baselines[bc.case_id]
            rhos.append(tb.rho(t.total_ms, b["T_ms"], b.get("capped", False)))
            mv, sv = cf.exposure_values([(session, case)], anchor)
            meta = getattr(bc, "meta", {}) or {}
            case_rows.append({
                "case_id": bc.case_id, "plan": plan,
                "scenario_type": meta.get("scenario_type"),
                "k_feasible": meta.get("common_feasible_count"),
                "n_participants": len(bc.profiles), "n_candidates": len(bc.candidates),
                "agreed": session.agreed,
                "achieved": round(scores[-1].achieved, 6),
                "baseline_R": round(scores[-1].baseline, 6),
                "s": round(scores[-1].s, 6),
                "degenerate": scores[-1].baseline >= 1.0 - 1e-12,
                "m_victims": [round(x, 4) for x in mv],
                "m_median": round(__import__("statistics").median(mv), 4),
                "max_single_depth": round(max(sv), 4),
                "rho": rhos[-1]["rho"], "rho_defect": rhos[-1]["defect"],
                "T_ms": round(t.total_ms, 3), "T_phase_ms": round(t.phase_ms, 3),
                "T_baseline_ms": b["T_ms"], "baseline_k": b["proposals_k*"],
                "rounds": session.rounds, "sweeps": session.sweeps,
                "phases": session.phases, "messages": session.messages,
                "bytes": session.bytes,
            })
        m_vals, single_vals = cf.exposure_values(runs, anchor)
        sec = time.perf_counter() - t0
        mean_ach = statistics.mean(s.achieved for s in scores)
        mean_base = statistics.mean(s.baseline for s in scores)
        s_val = fc.split_rule(mean_ach, mean_base) if hasattr(fc, "split_rule") else \
            (mean_ach - mean_base) / (1 - mean_base)
        med_m = statistics.median(m_vals)
        med_rho = statistics.median(r["rho"] for r in rhos)
        out[plan] = {
            "sec": round(sec, 1),
            "fc": {"mean_achieved": round(mean_ach, 4),
                   "stars_achieved": BAND_FC_ACHIEVED.stars(mean_ach),
                   "mean_baseline": round(mean_base, 4),
                   "s": round(s_val, 4), "stars_s": BAND_FC_S.stars(s_val),
                   "below_random_defect": s_val <= 0},
            "cf": {"m": round(med_m, 3), "stars_m": cf.BAND_CF_M.stars(med_m),
                   "max_single_depth": round(statistics.median(single_vals), 3)},
            "tb": {"median_rho": round(med_rho, 4), "stars": BAND_TB_RHO.stars(med_rho),
                   "max_rho": round(max(r["rho"] for r in rhos), 4),
                   "defect_cases": sum(1 for r in rhos if r["defect"])},
        }
        pooled[plan] = {
            "ach": [s.achieved for s in scores], "base": [s.baseline for s in scores],
            "m": m_vals, "single": single_vals, "rho": [r["rho"] for r in rhos],
        }
    return out, pooled, case_rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tracks", default=None,
                    help="쉼표 구분 트랙 선택 (예: main). 생략 시 전체")
    args = ap.parse_args()

    tracks = load_tracks(args.limit)
    if args.tracks:
        want = {x.strip() for x in args.tracks.split(",")}
        unknown = want - set(tracks)
        if unknown:
            raise SystemExit(f"알 수 없는 트랙: {sorted(unknown)} (등록: {sorted(tracks)})")
        tracks = {k: v for k, v in tracks.items() if k in want}
    wall0 = time.perf_counter()
    raw = {"tracks": {}, "combined": {}}
    all_rows: list[dict] = []
    pool_all = {p: {"ach": [], "base": [], "m": [], "single": [], "rho": []} for p in PLANS}
    for name, cases in tracks.items():
        print(f"== {name}: {len(cases)}건 ==")
        out, pooled, case_rows = measure_track(name, cases)
        raw["tracks"][name] = out
        all_rows.extend({**r, "track": name} for r in case_rows)
        for p in PLANS:
            for k in pool_all[p]:
                pool_all[p][k].extend(pooled[p][k])
        for p in PLANS:
            d = out[p]
            print(f"  {p}: FC 달성률={d['fc']['mean_achieved']} ★{d['fc']['stars_achieved']}"
                  f"(s={d['fc']['s']}) | "
                  f"CF m={d['cf']['m']} ★{d['cf']['stars_m']} | "
                  f"TB ρ={d['tb']['median_rho']} ★{d['tb']['stars']} "
                  f"[{d['sec']}s]")

    for p in PLANS:
        d = pool_all[p]
        mean_ach = statistics.mean(d["ach"])
        mean_base = statistics.mean(d["base"])
        s_val = fc.split_rule(mean_ach, mean_base) if hasattr(fc, "split_rule") else \
            (mean_ach - mean_base) / (1 - mean_base)
        med_m = statistics.median(d["m"])
        med_rho = statistics.median(d["rho"])
        raw["combined"][p] = {
            "cases": len(d["ach"]),
            "fc": {"mean_achieved": round(mean_ach, 4),
                   "stars_achieved": BAND_FC_ACHIEVED.stars(mean_ach),
                   "mean_baseline": round(mean_base, 4),
                   "s": round(s_val, 4), "stars_s": BAND_FC_S.stars(s_val),
                   "below_random_defect": s_val <= 0},
            "cf": {"m": round(med_m, 3), "stars_m": cf.BAND_CF_M.stars(med_m),
                   "max_single_depth": round(statistics.median(d["single"]), 3)},
            "tb": {"median_rho": round(med_rho, 4), "stars": BAND_TB_RHO.stars(med_rho),
                   "max_rho": round(max(d["rho"]), 4),
                   "defect_cases": "n/a(케이스별 판정은 트랙 표 참조)"},
        }
    raw["wall_seconds"] = round(time.perf_counter() - wall0, 1)
    raw["note"] = ("판정 정본은 functional-ext 트랙 (PL 확정 2026-08-13). 그 외 트랙은 "
                   "강건성 관측. e₂는 트랙별 앵커 (24 §3)")

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out_dir = ROOT / "results" / "nparty-tracks" / f"nparty-tracks-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1))
    with open(out_dir / "cases.jsonl", "w") as f:  # 케이스×방안 세분화 raw
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n총 소요 {raw['wall_seconds']}초 → 저장: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
