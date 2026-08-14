#!/usr/bin/env python3
"""functional-ext 정본 raw 재집계기 — cases.jsonl만 읽어 모든 분해표를 파생한다.

원칙 (RAW-SCHEMA.md): 측정은 한 번, 이후 분석은 전부 여기서. 재시뮬레이션 금지.
판정 규칙은 24 §0 (FC 달성률 평균 · CF 노출률 평균(합의 모수) · TB ρ P95).

사용: python scripts/aggregate_nparty_ext.py <run_dir>
출력: <run_dir>/breakdowns.json + breakdowns.md
"""
from __future__ import annotations

import collections
import json
import statistics
import sys
from pathlib import Path

PLANS = ("plan1a", "plan2")
DEAL_TYPES = ("wide_common", "single_common", "utility_tradeoff", "bottleneck_participant")
DECOY_TYPES = ("wide_common", "utility_tradeoff")


def stars_achieved(a):
    for st, th in ((5, 0.95), (4, 0.90), (3, 0.85), (2, 0.80), (1, 0.70)):
        if a >= th:
            return st
    return 0


def stars_exposure(e):
    if e >= 1.0 - 1e-9:
        return 0  # 전량 공개 별도 규칙 (24 §3.3)
    for st, th in ((5, 0.2), (4, 0.4), (3, 0.6), (2, 0.8), (1, 1.0)):
        if e <= th:
            return st
    return 0


def stars_rho(r):
    for st, th in ((5, 0.2), (4, 0.4), (3, 0.6), (2, 0.8), (1, 1.0)):
        if r <= th:
            return st
    return 0


def p95(vals):
    v = sorted(vals)
    return v[min(len(v) - 1, int(0.95 * len(v)))]


def agg(sel):
    """부분 표본 1개의 3-QA 판정 집계 (파생 규칙 = RAW-SCHEMA.md)."""
    ach = statistics.fmean(r["achieved"] for r in sel)
    base = statistics.fmean(r["baseline_R"] for r in sel)
    s = (ach - base) / (1 - base) if base < 1 - 1e-12 else 1.0
    deal = [r for r in sel if r["agreed"]]
    if deal:
        depths = [d for r in deal for d in r["victim_depths"]]
        cf_ = {"exposure_mean": round(statistics.fmean(depths), 4),
               "stars_exposure": stars_exposure(statistics.fmean(depths)),
               "exposure_sd": round(statistics.pstdev(depths), 4),
               "full_exposed_rate": round(sum(1 for d in depths if d >= 1 - 1e-9) / len(depths), 4)}
    else:
        cf_ = {"exposure_mean": None, "stars_exposure": None, "exposure_sd": None,
               "full_exposed_rate": None}
    rhos = [r["rho"] for r in sel]
    return {
        "cases": len(sel), "agree_rate": round(len(deal) / len(sel), 4),
        "achieved": round(ach, 4), "stars_achieved": stars_achieved(ach),
        "baseline_R": round(base, 4), "s": round(s, 4),
        "fr_violations": sum(r["fr_violations"] for r in sel),
        **cf_,
        "rho_p95": round(p95(rhos), 4), "stars_rho_p95": stars_rho(p95(rhos)),
        "rho_median": round(statistics.median(rhos), 4),
        "rho_max": round(max(rhos), 4),
        "rho_defects": sum(1 for r in sel if r["rho_defect"]),
    }


def wins(rows, keyfn, key):
    a = {r["case_id"]: r["achieved"] for r in rows if keyfn(r) == key and r["plan"] == "plan1a"}
    b = {r["case_id"]: r["achieved"] for r in rows if keyfn(r) == key and r["plan"] == "plan2"}
    w1 = sum(1 for c in a if a[c] > b[c] + 1e-9)
    w2 = sum(1 for c in a if b[c] > a[c] + 1e-9)
    return {"win_1a": w1, "tie": len(a) - w1 - w2, "win_2": w2}


def group(rows, name, keyfn, keys=None):
    out = {}
    found = sorted({keyfn(r) for r in rows}, key=lambda x: (isinstance(x, str), x))
    for key in (keys if keys is not None else found):
        sel_keys = [r for r in rows if keyfn(r) == key]
        if not sel_keys:
            continue
        out[str(key)] = {p: agg([r for r in sel_keys if r["plan"] == p]) for p in PLANS}
        out[str(key)].update(wins(rows, keyfn, key))
    return out


def main() -> int:
    run_dir = Path(sys.argv[1])
    track = sys.argv[2] if len(sys.argv) > 2 else "functional-ext2"  # 정본 (2026-08-14 승격)
    rows = [json.loads(l) for l in open(run_dir / "cases.jsonl")]
    rows = [r for r in rows if r.get("track") == track]
    by_plan = {p: [r for r in rows if r["plan"] == p] for p in PLANS}

    out = {
        "source": "cases.jsonl 재집계 파생물 (정본은 cases.jsonl — RAW-SCHEMA.md). "
                  "판정: FC 달성률 평균 · CF 노출률 평균(분모 전체 후보, 모수 합의 세션) · "
                  "TB ρ P95 (PL 확정 2026-08-13)",
        "overall": {p: agg(by_plan[p]) for p in PLANS},
        "by_n": group(rows, "n", lambda r: r["n_participants"]),
        "by_type": group(rows, "type", lambda r: r["scenario_type"]),
        "by_variant_decoy2": group(
            [r for r in rows if r["scenario_type"] in DECOY_TYPES],
            "variant", lambda r: r["variant"]),
        "by_depth_band": group(rows, "depth", lambda r: r["depth_band"]),
    }
    out["overall"].update(wins(rows, lambda r: True, True))

    # 분포 — FC 달성률 히스토그램 (미끼 3유형: 변별 유효 구간), 노출 개수, ρ 분위
    disc = [r for r in rows if r["scenario_type"] in
            ("wide_common", "utility_tradeoff", "bottleneck_participant")]
    out["dist"] = {}
    for p in PLANS:
        ach = [r["achieved"] for r in disc if r["plan"] == p]
        hist = collections.Counter(min(int(a * 10), 10) for a in ach)
        exposed = [c for r in by_plan[p] if r["agreed"] for c in r["exposed_counts"]]
        ehist = collections.Counter(exposed)
        rhos = sorted(r["rho"] for r in by_plan[p])
        q = lambda x: rhos[min(len(rhos) - 1, int(x * len(rhos)))]
        out["dist"][p] = {
            "achieved_hist_decoy3": {f"{b / 10:.1f}": hist.get(b, 0) for b in range(11)},
            "exposed_count_hist": {str(k): ehist[k] for k in sorted(ehist)},
            "rho_quantiles": {"p50": round(q(.5), 4), "p75": round(q(.75), 4),
                              "p90": round(q(.9), 4), "p95": round(q(.95), 4),
                              "max": round(rhos[-1], 4)},
        }

    # 쌍대 (같은 케이스 직접 비교)
    a_by = {r["case_id"]: r for r in by_plan["plan1a"]}
    b_by = {r["case_id"]: r for r in by_plan["plan2"]}
    t_ratio = [a_by[c]["T_ms"] / b_by[c]["T_ms"] for c in a_by if b_by[c]["T_ms"] > 0]
    # 노출률 = 1 − 잔여 비밀률이므로, (2 노출) − (1-A 노출) = (1-A 비밀) − (2 비밀)
    exp_diff = [a_by[c]["secret_case_mean"] - b_by[c]["secret_case_mean"]
                for c in a_by if a_by[c]["agreed"]]
    out["paired"] = {
        "t_ratio_1a_over_2_median": round(statistics.median(t_ratio), 4),
        "t_faster_1a_cases": sum(1 for x in t_ratio if x < 1),
        "exposure_diff_2_minus_1a_median": round(statistics.median(exp_diff), 4),
        "exposure_lower_1a_cases": sum(1 for x in exp_diff if x > 0),
        "note": "같은 케이스에서 두 방안을 직접 나눈/뺀 값 — 주변 분포가 못 보는 차이",
    }

    # 통신 (N별 중앙값)
    out["comm_by_n"] = {}
    for n in sorted({r["n_participants"] for r in rows}):
        out["comm_by_n"][str(n)] = {
            p: {k: statistics.median(r[k] for r in by_plan[p] if r["n_participants"] == n)
                for k in ("rounds", "messages", "bytes", "T_ms")}
            for p in PLANS}

    (run_dir / "breakdowns.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # 사람이 읽는 md — 60번 문서 appendix의 원천
    md = ["# functional-ext 분해표 (자동 생성 — aggregate_nparty_ext.py)", ""]

    def table(title, grp, key_label):
        md.append(f"## {title}")
        md.append("")
        md.append(f"| {key_label} | 1-A 달성률(★) | 2 달성률(★) | 승(1A/무/2) | "
                  "1-A 노출률(★) | 2 노출률(★) | 1-A ρP95(★) | 2 ρP95(★) |")
        md.append("|---|---|---|---|---|---|---|---|")
        for k, v in grp.items():
            a, b = v["plan1a"], v["plan2"]
            def sec_cell(x):
                if x["exposure_mean"] is None:
                    return "모수 제외(결렬)"
                return f"{x['exposure_mean'] * 100:.1f}% (★{x['stars_exposure']})"
            md.append(
                f"| {k} | {a['achieved']:.3f} (★{a['stars_achieved']}) | "
                f"{b['achieved']:.3f} (★{b['stars_achieved']}) | "
                f"{v['win_1a']}/{v['tie']}/{v['win_2']} | "
                f"{sec_cell(a)} | {sec_cell(b)} | "
                f"{a['rho_p95']:.3f} (★{a['stars_rho_p95']}) | "
                f"{b['rho_p95']:.3f} (★{b['stars_rho_p95']}) |")
        md.append("")

    table("N(참여자 수)별", out["by_n"], "N")
    table("유형별", out["by_type"], "유형")
    table("변형별 (미끼 2유형 한정)", out["by_variant_decoy2"], "변형")
    table("x* 순위 깊이별", out["by_depth_band"], "깊이")
    (run_dir / "breakdowns.md").write_text("\n".join(md), encoding="utf-8")
    print(f"breakdowns.json / breakdowns.md 저장 → {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
