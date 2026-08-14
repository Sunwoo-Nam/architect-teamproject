#!/usr/bin/env python3
"""composite final 재집계 — cases.jsonl만 읽어 보고용 표를 재생성한다 (재시뮬레이션 없음).

    .venv/bin/python scripts/aggregate_composite_final.py results/composite-final/<run>/

출력: 같은 폴더에 breakdowns.json + breakdowns.md (유형별·축 수별·승패·분포·함정 실효).
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from total.qa.bands import stars_at_least, stars_at_most  # noqa: E402

FC_BAND = [0.95, 0.90, 0.85, 0.80, 0.70]      # 달성률 (24 §1)
RHO_BAND = [0.2, 0.4, 0.6, 0.8, 1.0]          # ρ (24 §4)
RU_BAND = [0.2, 0.4, 0.6, 0.8, 1.0]           # r 20%p 등분 (24 §2.8, 2026-08-14 확정)
PLANS = ("seq2", "pool")


def p95(xs):
    """P95 규약 = 정렬 후 0-기반 색인 int(0.95·n) — 측정 파이프라인(qa/tb.py·qa/ru.py)과
    동일. nearest-rank(ceil(0.95n)-1)보다 1랭크 위를 취하는 **상향 보수**로, n ≤ 20에서는
    최댓값과 일치한다 (제3자 리뷰 2026-08-14에서 이원화 발견 — 파이프라인 쪽으로 통일)."""
    if not xs:
        return None
    ys = sorted(xs)
    return ys[min(len(ys) - 1, int(0.95 * len(ys)))]


def fc_stars(v):
    return None if v is None else stars_at_least(v, FC_BAND)


def rho_stars(v):
    return None if v is None else stars_at_most(v, RHO_BAND)


def ru_stars(v):
    return None if v is None else stars_at_most(v, RU_BAND)


def summarize(rows):
    """방안 1개의 행 묶음 → 판정·보조 요약."""
    ach = [r["achieved"] for r in rows if r.get("achieved") is not None]
    rbar = [r["baseline_R"] for r in rows if r.get("baseline_R") is not None]
    rhos = [r["rho"] for r in rows if r.get("rho") is not None]
    rts = [r["r_total"] for r in rows]
    mats = [r.get("materialized_bytes") or 0 for r in rows]
    frs = sum(len(r["fr_violations"] or []) > 0 for r in rows if r.get("fr_violations") is not None)
    out = {
        "n": len(rows),
        "fc_mean": round(statistics.fmean(ach), 4) if ach else None,
        "fc_stars": fc_stars(statistics.fmean(ach)) if ach else None,
        "r_bar": round(statistics.fmean(rbar), 4) if rbar else None,
        "fr_cases": frs if ach else None,
        "rho_p95": round(p95(rhos), 4) if rhos else None,
        "rho_stars": rho_stars(p95(rhos)) if rhos else None,
        "rho_med": round(statistics.median(rhos), 4) if rhos else None,
        "rho_defects": sum(r.get("rho_defect") or 0 for r in rows),
        "r_med": round(statistics.median(rts), 8) if rts else None,
        "ru_stars_med": ru_stars(statistics.median(rts)) if rts else None,
        # RU 판정 = r 최대값 (2026-08-14 재개정, 24 §2.8 — OOM은 최악 1건이 크리티컬).
        # P95(꼬리)·중앙(전형)은 병기
        "r_max": round(max(rts), 6) if rts else None,
        "ru_stars_max": ru_stars(max(rts)) if rts else None,
        "r_p95": round(p95(rts), 8) if rts else None,
        "ru_stars_p95": ru_stars(p95(rts)) if rts else None,
        "over_ceiling": sum(1 for r in rows if r.get("over_ceiling")),
        "mat_med_mb": round(statistics.median(mats) / 2**20, 4) if mats else None,
        "mat_max_mb": round(max(mats) / 2**20, 3) if mats else None,
    }
    if ach and out["r_bar"] is not None and out["r_bar"] < 1:
        out["s_pooled"] = round((out["fc_mean"] - out["r_bar"]) / (1 - out["r_bar"]), 4)
    return out


def pairwise(rows_by_plan):
    """같은 케이스의 두 방안 직접 비교 — 승패·격차."""
    a = {r["case_id"]: r for r in rows_by_plan["seq2"]}
    b = {r["case_id"]: r for r in rows_by_plan["pool"]}
    fc_w = {"seq2": 0, "tie": 0, "pool": 0}
    t_ratio, ru_ratio = [], []
    for cid in a.keys() & b.keys():
        ra, rb = a[cid], b[cid]
        if ra.get("achieved") is not None and rb.get("achieved") is not None:
            d = ra["achieved"] - rb["achieved"]
            fc_w["seq2" if d > 1e-9 else ("pool" if d < -1e-9 else "tie")] += 1
        if ra.get("T_ms") and rb.get("T_ms"):
            t_ratio.append(ra["T_ms"] / rb["T_ms"])
        if rb.get("total_mb") and ra.get("total_mb"):
            ru_ratio.append(rb["total_mb"] / ra["total_mb"])
    return {
        "fc_wins": fc_w,
        "t_ratio_med_seq_over_pool": round(statistics.median(t_ratio), 4) if t_ratio else None,
        "ru_ratio_med_pool_over_seq": round(statistics.median(ru_ratio), 4) if ru_ratio else None,
    }


def group(rows, key):
    g = defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    return dict(sorted(g.items(), key=lambda kv: str(kv[0])))


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join("—" if v is None else str(v) for v in r) + " |")
    return out


def fmt(sm, k, star_k=None):
    if sm[k] is None:
        return "—"
    v = f"{sm[k]:.4f}" if isinstance(sm[k], float) else str(sm[k])
    if star_k and sm.get(star_k) is not None:
        v += f" ★{sm[star_k]}"
    return v


def main():
    run_dir = Path(sys.argv[1])
    rows = [json.loads(l) for l in (run_dir / "cases.jsonl").read_text().splitlines()]
    by_plan = {p: [r for r in rows if r["plan"] == p] for p in PLANS}

    bd = {"overall": {p: summarize(by_plan[p]) for p in PLANS},
          "pairwise": pairwise(by_plan)}
    for dim, key in (("by_type", lambda r: r["type"]),
                     ("by_n", lambda r: r["n_issues"]),
                     ("by_track", lambda r: r["track"]),
                     ("by_conflict", lambda r: r["conflict"])):
        bd[dim] = {str(k): {p: summarize([r for r in g if r["plan"] == p]) for p in PLANS}
                   for k, g in group(rows, key).items()}

    # 함정 실효 — planted 유형별 FC 승패
    trap_rows = [r for r in rows if r.get("planted")]
    bd["trap_effect"] = {}
    for trap, g in group(trap_rows, lambda r: r["planted"]).items():
        gp = {p: [r for r in g if r["plan"] == p] for p in PLANS}
        bd["trap_effect"][trap] = {**{p: summarize(gp[p]) for p in PLANS},
                                   "pairwise": pairwise(gp)}

    (run_dir / "breakdowns.json").write_text(
        json.dumps(bd, ensure_ascii=False, indent=1))

    L = [f"# composite final 재집계 — {run_dir.name}", "",
         "판정: FC=달성률 평균 · RU=사용률 r P95 (로그 사다리, 중앙·최악 병기) · TB=ρ P95. "
         "원본: cases.jsonl (케이스×방안 1행).", "", "## 종합"]
    L += md_table(
        ["지표"] + list(PLANS),
        [[lab] + [fmt(bd["overall"][p], k, sk) for p in PLANS]
         for lab, k, sk in (
             ("FC 달성률 (판정)", "fc_mean", "fc_stars"),
             ("FC 보조 s(전체 환산)", "s_pooled", None),
             ("무작위 R̄", "r_bar", None),
             ("FR 위반 케이스", "fr_cases", None),
             ("TB ρ P95 (판정)", "rho_p95", "rho_stars"),
             ("TB ρ 중앙", "rho_med", None),
             ("ρ>1 결함", "rho_defects", None),
             ("RU r 최대 (판정)", "r_max", "ru_stars_max"),
             ("RU r P95", "r_p95", "ru_stars_p95"),
             ("RU r 중앙", "r_med", "ru_stars_med"),
             ("한도 초과 케이스", "over_ceiling", None),
             ("실물화 중앙 MB", "mat_med_mb", None),
             ("실물화 최대 MB", "mat_max_mb", None))])
    L += ["", f"쌍대: FC 승패(seq2/무/pool) = "
          f"{bd['pairwise']['fc_wins']['seq2']}/{bd['pairwise']['fc_wins']['tie']}/"
          f"{bd['pairwise']['fc_wins']['pool']} · "
          f"T(seq2)÷T(pool) 중앙 {bd['pairwise']['t_ratio_med_seq_over_pool']} · "
          f"RU(pool)÷RU(seq2) 중앙 {bd['pairwise']['ru_ratio_med_pool_over_seq']}", ""]

    for dim, title, head in (("by_type", "유형별", "유형"),
                             ("by_n", "축 수별", "축 수"),
                             ("by_conflict", "충돌 수준별", "충돌"),
                             ("by_track", "트랙별", "트랙")):
        L += [f"## {title}", ""]
        body = []
        for k, per in bd[dim].items():
            body.append([k] + sum(([fmt(per[p], "fc_mean", "fc_stars"),
                                    fmt(per[p], "rho_p95", "rho_stars"),
                                    fmt(per[p], "r_max", "ru_stars_max"),
                                    fmt(per[p], "r_p95", "ru_stars_p95")]
                                   for p in PLANS), []))
        L += md_table([head, "seq2 FC", "seq2 ρP95", "seq2 r최대", "seq2 rP95",
                       "pool FC", "pool ρP95", "pool r최대", "pool rP95"], body)
        L.append("")

    L += ["## 함정 실효 (planted별 FC 승패)", ""]
    for trap, d in bd["trap_effect"].items():
        w = d["pairwise"]["fc_wins"]
        L.append(f"- **{trap}**: seq2 {w['seq2']}승 / 무 {w['tie']} / pool {w['pool']}승 · "
                 f"seq2 FC {fmt(d['seq2'], 'fc_mean', 'fc_stars')} vs "
                 f"pool {fmt(d['pool'], 'fc_mean', 'fc_stars')}")
    (run_dir / "breakdowns.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"저장: {run_dir}/breakdowns.json + breakdowns.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
