"""고정 테스트(fixture) 측정 — 박제된 정답 x* 대비 전략별 절대 달성률.

fixtures/*.json을 로드해(프로파일 고정) pool·seq(있으면 seq2)를 돌리고, 저장된 U(x*) 대비
달성률과 합의 여부를 낸다. 시드 생성이 없어 **돌릴 때마다 완전히 동일**.

사용:  .venv/bin/python scripts/run_fixtures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpca.common.exact import exact_xstar  # noqa: E402
from dpca.common.fixture import load_fixture  # noqa: E402
from dpca.common.profiles import build_truth_profiles, truth_utility  # noqa: E402
from dpca.common.rules import build_soft_rules  # noqa: E402
from dpca.harness.runner import STRATEGIES, run_one  # noqa: E402

FIX = ROOT / "fixtures"


def true_total(sc, agreement) -> float:
    truths = build_truth_profiles(sc)
    soft = build_soft_rules(sc, [t.home_region for t in truths])
    out = {ax.name: next(v for v in ax.values if v.name == agreement[ax.name]) for ax in sc.axes}
    return sum(truth_utility(truths[p], p, out, soft) for p in range(len(truths)))


def main() -> int:
    strategies = ["pool", "seq", "seq2"]   # full은 고차원 실행 불가; seq2 = T1+T3 개선판
    paths = sorted(FIX.glob("*.json"))
    if not paths:
        print("fixtures 없음 — 먼저 make_fixtures.py 실행")
        return 1

    from statistics import mean, median
    rows = []
    print("=== ① 정확도(달성률=U(r)/U(x*)) + 피크 메모리(MB) ===")
    print(f"{'fixture':<22}{'축':>3}  " +
          "".join(f"{st:>18}" for st in strategies))
    for path in paths:
        sc, known = load_fixture(path)
        uxs = known["u_xstar"]
        rt_ok = abs(exact_xstar(sc)["u_xstar"] - uxs) < 1e-6   # 라운드트립 검증
        cells = []
        for st in strategies:
            r = run_one(sc, st)
            rate = true_total(sc, r.agreement) / uxs if r.agreement else None
            cells.append(f"{(f'{rate:.0%}' if rate is not None else '결렬'):>6}/{r.peak_kib/1024:>6.1f}MB")
            rows.append({"fixture": path.stem, "n_axes": len(sc.axes), "strategy": st,
                         "u_xstar": round(uxs, 4),
                         "achieved": round(rate, 4) if rate is not None else None,
                         "agreed": r.agreement is not None,
                         "peak_mb": round(r.peak_kib / 1024, 3), "wall_ms": round(r.wall_ms, 1),
                         "phases": r.phases, "roundtrip_ok": rt_ok})
        flag = "" if rt_ok else " ⚠x*불일치"
        print(f"{path.stem:<22}{len(sc.axes):>3}  " + "".join(f"{c:>18}" for c in cells) + flag)

    # 집계 QA 비교
    print("\n=== ② 전략별 QA 집계 (12 fixture) ===")
    print(f"{'전략':<6}{'FC 달성률µ':>12}{'합의율':>8}{'메모리 중앙MB':>14}{'시간 중앙ms':>12}")
    for st in strategies:
        rs = [r for r in rows if r["strategy"] == st]
        ach = [r["achieved"] for r in rs if r["achieved"] is not None]
        print(f"{st:<6}{mean(ach) if ach else 0:>12.1%}"
              f"{sum(r['agreed'] for r in rs)/len(rs):>8.0%}"
              f"{median(r['peak_mb'] for r in rs):>14.2f}"
              f"{median(r['wall_ms'] for r in rs):>12.1f}")

    out = ROOT / "results" / "fixtures_result.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\n{len(rows)} rows → {out}")
    print("라운드트립 OK — 로드한 x*가 저장값과 전부 일치" if all(r["roundtrip_ok"] for r in rows)
          else "⚠ 라운드트립 불일치 존재")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
