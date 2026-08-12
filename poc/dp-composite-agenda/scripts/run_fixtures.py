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

    rows = []
    print(f"{'fixture':<24}{'축':>3}{'U(x*)':>8}  " +
          "".join(f"{st+' 달성/합의':>16}" for st in strategies))
    for path in paths:
        sc, known = load_fixture(path)
        uxs = known["u_xstar"]
        # 라운드트립 검증: 로드한(고정) 시나리오의 x*가 저장값과 일치해야
        rt = exact_xstar(sc)["u_xstar"]
        rt_ok = abs(rt - uxs) < 1e-6
        cells = []
        for st in strategies:
            r = run_one(sc, st)
            if r.agreement:
                rate = true_total(sc, r.agreement) / uxs
                cells.append(f"{rate:>10.1%}/합의")
            else:
                rate = None
                cells.append(f"{'—':>10}/결렬")
            rows.append({"fixture": path.stem, "n_axes": len(sc.axes), "strategy": st,
                         "u_xstar": round(uxs, 4),
                         "achieved": round(rate, 4) if rate is not None else None,
                         "agreed": r.agreement is not None, "roundtrip_ok": rt_ok})
        flag = "" if rt_ok else "  ⚠x*불일치"
        print(f"{path.stem:<24}{len(sc.axes):>3}{uxs:>8.3f}  " +
              "".join(f"{c:>16}" for c in cells) + flag)

    out = ROOT / "results" / "fixtures_result.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\n{len(rows)} rows → {out}")
    if all(r["roundtrip_ok"] for r in rows):
        print("라운드트립 OK — 로드한 고정본의 x*가 저장값과 전부 일치")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
