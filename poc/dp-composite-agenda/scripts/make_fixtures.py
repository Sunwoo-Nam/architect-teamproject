"""고정 테스트(fixture) 생성 — 축·후보·프로파일·정답 x*를 파일로 박제.

고차원 10개(4~22축) + 소형 손검증본 2개. 각 케이스는 정답 x*가 정확한(바닥선 비조임) 시드만
선별해 굳힌다. 완벽 정보(뷰=진실) 전제. 한 번 만들면 이후엔 시드 무관하게 항상 동일.

사용:  .venv/bin/python scripts/make_fixtures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpca.common.exact import exact_xstar  # noqa: E402
from dpca.common.fixture import dump_fixture  # noqa: E402
from dpca.common.generators import Value  # noqa: E402
from dpca.common.scenario import Axis, load_scenario  # noqa: E402

FIX = ROOT / "fixtures"
S11 = ROOT / "scenarios" / "S11-축수스윕.yaml"
HI_AXES = [4, 6, 8, 10, 12, 14, 16, 18, 20, 22]   # 고차원 10개


def build_hi(n_axes: int, seed: int):
    sc = load_scenario(S11, n_axes=min(n_axes, 10))
    for i in range(10, n_axes):
        sc.axes.append(Axis(f"x{i}", "numbered", [Value(f"x{i}_v{j}") for j in range(5)]))
    sc.participants["profile_seed"] = seed
    sc.agent_view = {"score_dropout": 0.0}   # 완벽 정보
    sc.meta = {**sc.meta, "id": f"FIX-HI-{n_axes:02d}"}
    return sc


def first_valid_seed(make, base: int, max_try: int = 40) -> int | None:
    """정답 x*가 정확한(무제약 최대가 유효) 시드를 찾는다."""
    for s in range(max_try):
        if exact_xstar(make(base + s))["unconstrained_valid"]:
            return base + s
    return None


def main() -> int:
    FIX.mkdir(exist_ok=True)
    base = load_scenario(S11, n_axes=4).profile_seed
    made = []

    # 고차원 10개
    for n in HI_AXES:
        seed = first_valid_seed(lambda s: build_hi(n, s), base)
        if seed is None:
            print(f"  [건너뜀] {n}축: 정확 x* 시드 못 찾음")
            continue
        path = FIX / f"fix-hi-{n:02d}axis.json"
        doc = dump_fixture(build_hi(n, seed), path, f"고차원 {n}축 (seed {seed})")
        made.append((path.name, doc))
        print(f"  {path.name:<22} 축{n:>2} 공간{doc['space_size']:.2e} "
              f"U(x*)={doc['known_answer']['u_xstar']:.3f} seed{seed}")

    # 소형 손검증본 2개 (정의된 TC를 굳힘 — 값·점수가 JSON에 다 보임)
    for tag, yaml, n_axes in [("s04-3axis", "S04-독립축", 3), ("s05-4axis", "S05-부드러운의존", 4)]:
        def mk(s, y=yaml, na=n_axes):
            sc = load_scenario(ROOT / "scenarios" / f"{y}.yaml", n_axes=na)
            sc.participants["profile_seed"] = s
            sc.agent_view = {"score_dropout": 0.0}
            sc.meta = {**sc.meta, "id": f"FIX-{tag.upper()}"}
            return sc
        base2 = load_scenario(ROOT / "scenarios" / f"{yaml}.yaml", n_axes=n_axes).profile_seed
        seed = first_valid_seed(mk, base2)
        path = FIX / f"fix-small-{tag}.json"
        doc = dump_fixture(mk(seed), path, f"소형 {tag} (seed {seed})")
        made.append((path.name, doc))
        print(f"  {path.name:<22} 축{n_axes:>2} 공간{doc['space_size']:.2e} "
              f"U(x*)={doc['known_answer']['u_xstar']:.3f} seed{seed}")

    print(f"\n총 {len(made)}개 fixture → {FIX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
