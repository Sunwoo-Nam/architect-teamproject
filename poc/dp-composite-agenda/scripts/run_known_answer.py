"""정답(x*)을 아는 고차원 테스트 — 전수열거 없이 정확한 x*로 절대 정확도 측정.

이 시나리오들의 의존 구조는 성기다: 모든 하드·소프트 규칙이 소수 축(vertex cover)에만 붙는다.
그 축들을 고정하면 나머지 축이 독립이 되어 정확한 x*를 구할 수 있다(dpca.common.exact).

절차:
  1) exact_xstar를 작은 시나리오(≤20만, 전수열거 가능)에서 기존 오라클 u_xstar와 대조 검증.
  2) 검증 통과 시 고차원(합성 축)에 적용 → 정확한 U(x*)로 pool·seq의 절대 달성률 U(r)/U(x*) 측정.

사용:  .venv/bin/python scripts/run_known_answer.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpca.common.exact import exact_xstar  # noqa: E402
from dpca.common.generators import Value  # noqa: E402
from dpca.common.oracle import analyze  # noqa: E402
from dpca.common.profiles import build_truth_profiles, truth_utility  # noqa: E402
from dpca.common.rules import build_soft_rules  # noqa: E402
from dpca.common.scenario import Axis, load_scenario  # noqa: E402
from dpca.harness.runner import run_one  # noqa: E402


def build_hi(n_axes: int, seed: int):
    sc = load_scenario(ROOT / "scenarios" / "S11-축수스윕.yaml", n_axes=min(n_axes, 10))
    for i in range(10, n_axes):
        sc.axes.append(Axis(f"x{i}", "numbered", [Value(f"x{i}_v{j}") for j in range(5)]))
    sc.participants["profile_seed"] = seed
    sc.agent_view = {"score_dropout": 0.0}   # 완벽 정보
    return sc


def validate() -> bool:
    """무제약 최대가 유효(양측 ≥ threshold)한 경우에만 정확 일치를 요구한다.
    바닥선이 조이는 경우(무제약 최대가 무효) 솔버는 하한만 주므로 별도 표기(버그 아님)."""
    print("=== 검증: exact_xstar vs 전수열거 오라클 (작은 시나리오) ===")
    ok = True
    for path in sorted((ROOT / "scenarios").glob("S*.yaml")):
        n_axes = 4 if "S11" in path.name else None
        bug = bind = 0
        for s in range(8):
            sc = load_scenario(path, n_axes=n_axes)
            sc.participants["profile_seed"] = sc.profile_seed + s
            rep = analyze(sc)
            if rep.skipped:
                continue
            ex = exact_xstar(sc)
            if abs(ex["u_xstar"] - rep.u_xstar) > 1e-6:
                if ex["unconstrained_valid"]:
                    bug += 1
                    if bug <= 1:
                        print(f"  [버그] {sc.id} seed{sc.profile_seed+s}: "
                              f"exact={ex['u_xstar']:.4f} vs oracle={rep.u_xstar:.4f}")
                else:
                    bind += 1
        tag = "OK" if bug == 0 and bind == 0 else (
            f"바닥선조임 {bind}/8 (한계)" if bug == 0 else f"버그 {bug}/8")
        print(f"  {path.stem:<16} {tag}")
        ok = ok and bug == 0
    print("  → 버그 없음(바닥선 비조임 케이스 전부 일치)" if ok else "  → 진짜 버그 존재")
    return ok


def measure_hi(n_seeds: int = 12):
    print(f"\n=== 고차원 절대 정확도 (정확한 x* 기준, 완벽 정보, seed {n_seeds}) ===")
    print("달성률 = U(합의)/U(x*). x*가 정확한(바닥선 비조임) 시드만 집계.")
    print(f"{'축':>3} {'U(x*)µ':>8} {'pool달성률':>10} {'seq달성률':>9} "
          f"{'pool합의':>8} {'seq합의':>7} {'정확x*':>7}")
    base = load_scenario(ROOT / "scenarios" / "S11-축수스윕.yaml", n_axes=4).profile_seed
    for n in (8, 12, 16, 20):
        pr, sr, uxs_list, pa, sa, exact = [], [], [], 0, 0, 0
        for s in range(n_seeds):
            sc = build_hi(n, base + s)
            xs = exact_xstar(sc)
            if not xs["unconstrained_valid"]:
                continue
            exact += 1
            uxs = xs["u_xstar"]
            uxs_list.append(uxs)
            truths = build_truth_profiles(sc)
            soft = build_soft_rules(sc, [t.home_region for t in truths])

            def uofr(agr):
                out = {ax.name: next(v for v in ax.values if v.name == agr[ax.name]) for ax in sc.axes}
                return sum(truth_utility(truths[p], p, out, soft) for p in range(len(truths)))

            rp = run_one(sc, "pool")
            rs = run_one(sc, "seq")
            if rp.agreement:
                pa += 1
                pr.append(uofr(rp.agreement) / uxs)
            if rs.agreement:
                sa += 1
                sr.append(uofr(rs.agreement) / uxs)
        print(f"{n:>3} {mean(uxs_list) if uxs_list else 0:>8.3f} "
              f"{mean(pr) if pr else 0:>10.1%} {mean(sr) if sr else 0:>9.1%} "
              f"{pa}/{exact:<6} {sa}/{exact:<4} {exact}/{n_seeds}")


def main() -> int:
    if validate():
        measure_hi()
    else:
        print("\n검증 실패로 고차원 측정 생략 — 솔버가 정답을 못 맞춤.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
