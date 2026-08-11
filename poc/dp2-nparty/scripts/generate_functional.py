"""Functional benchmark 케이스 생성기 — 계획서 §6의 유형별 구성 규칙을 코드로 고정한다.

왜 손으로 쓰지 않고 생성하는가: 3인 100건 + 5인 30건 + 7인 30건 = 160건 규모에서는
손으로 쓴 케이스의 일관성이 무너지고, "유형별 균등 배치"·"순위 깊이 균등" 같은 표본 구성
요구를 사람이 지킬 수 없다. 생성 규칙을 코드로 고정하면 표본 구성이 검증 가능해진다.
산출된 JSON은 정적 파일로 커밋하며, 그 파일에는 seed를 남기지 않는다 (AGENTS.md).

구성 방식은 **역방향**이다 — 무작위로 utility를 뿌리고 결과를 보는 것이 아니라,
"실후보 집합 F"와 "x*의 순위 깊이"를 먼저 정하고 그것이 성립하도록 utility를 만든다.
무작위 생성으로는 N이 커질수록 실후보 교집합이 저절로 사라져(25 §25.5의 난이도 교락)
표본이 결렬 쪽으로 쏠린다.

사용:
    .venv/bin/python scripts/generate_functional.py --pilot
    .venv/bin/python scripts/generate_functional.py --participants 3 --per-type 20
    .venv/bin/python scripts/generate_functional.py --participants 5 --per-type 6 --start 1
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dp2_nparty.benchmark import CASES_DIR, SCHEMA_VERSION, validate_case

OUT_DIR = CASES_DIR / "functional"
N_CANDIDATES = 12  # 계획서 §6.3 통제 조건 (잠정값)

# 순위 깊이 — x*가 각 참여자의 몇 순위에 놓이는가. 얕기만 하면 너무 쉬운 표본이 된다.
DEPTH_BANDS = {"early": (1, 3), "middle": (4, 7), "late": (8, 10)}

# 참여자별 바닥선 후보 — 전원 동일 케이스와 상이 케이스를 섞어 threshold 구성 편향을 막는다
THRESHOLD_POOL = (0.30, 0.35, 0.40, 0.45, 0.50, 0.55)
UNIFORM_THRESHOLD = 0.40


@dataclass(frozen=True)
class TypeSpec:
    """유형 1종의 구성 규칙 (계획서 §6.2)."""

    scenario_type: str
    n_feasible: int  # 실후보 수 — 전원의 바닥선을 넘는 후보 개수
    value_profile: str  # "smooth" | "bimodal"(총효용 격차를 만든다)
    bottleneck: bool  # 한 참여자만 바닥선을 크게 높여 유효 영역을 제한하는가
    description: str


TYPES = (
    TypeSpec("wide_common", 4, "smooth", False, "전원 수락 가능한 상위 후보가 여러 개인 사례."),
    TypeSpec("single_common", 1, "smooth", False, "전원의 바닥선을 넘는 실후보가 하나뿐인 사례."),
    TypeSpec(
        "utility_tradeoff", 3, "bimodal", False,
        "유효 후보가 여러 개지만 총효용 차이가 커서 어느 것으로 닫히는지가 갈리는 사례.",
    ),
    TypeSpec(
        "bottleneck_participant", 2, "smooth", True,
        "한 참여자의 높은 바닥선이 전체 유효 영역을 제한하는 사례.",
    ),
    TypeSpec("no_deal_optimal", 0, "smooth", False, "전원의 바닥선을 넘는 실후보가 없어 결렬이 최적인 사례."),
)


def _values_for(k: int, n: int, threshold: float, profile: str, rng: random.Random) -> list[float]:
    """순위 1..n 에 놓일 utility 값 — 앞의 k개는 바닥선 이상, 나머지는 미만.

    bimodal은 수락 구간을 상위군과 '겨우 넘긴 군'으로 갈라 총효용 격차를 만든다.
    """
    if profile == "bimodal" and k >= 2:
        high_n = max(1, k // 2)
        high = [rng.uniform(max(threshold + 0.2, 0.75), 1.0) for _ in range(high_n)]
        low = [rng.uniform(threshold + 0.005, threshold + 0.08) for _ in range(k - high_n)]
        above = sorted(high + low, reverse=True)
    else:
        above = sorted((rng.uniform(threshold + 0.005, 1.0) for _ in range(k)), reverse=True)
    below = sorted((rng.uniform(0.02, threshold - 0.01) for _ in range(n - k)), reverse=True)
    return [round(v, 4) for v in above + below]


def _rankings(spec: TypeSpec, n_part: int, cands: list[str], depth: str, rng: random.Random):
    """참여자별 (바닥선, 수락 후보 수 k, 순위 나열)를 만든다.

    불변조건:
    - F(실후보)는 전원의 상위 k 안에 든다 → 전원이 수락 가능
    - F 밖의 후보는 최소 한 명의 k 밖에 있다 → 유효 후보가 아니다 (blocker 배정)
    - 주 후보(F 중 총효용 최대가 될 것)는 목표 순위 깊이에 놓인다
    """
    n = len(cands)
    lo, hi = DEPTH_BANDS[depth]
    feasible = rng.sample(cands, spec.n_feasible)
    primary = feasible[0] if feasible else None
    others = feasible[1:]
    infeasible = [c for c in cands if c not in feasible]

    # F 밖 후보마다 blocker 1명 — 그 사람의 수락 범위 밖에 둔다
    blockers = {c: infeasible.index(c) % n_part for c in infeasible}

    uniform_th = rng.random() < 0.4  # threshold 구성 편향 방지 — 동일/상이를 섞는다
    out = []
    for j in range(n_part):
        mine_blocked = [c for c, b in blockers.items() if b == j]
        free = [c for c in infeasible if blockers[c] != j]

        if spec.bottleneck and j == 0:
            # 병목 참여자 — 수락 범위를 F 크기 바로 위로 좁힌다
            depth_rank = min(hi, max(lo, spec.n_feasible))
            k = max(spec.n_feasible, min(depth_rank, spec.n_feasible + 1))
            th = 0.70
        else:
            depth_rank = rng.randint(lo, hi) if primary else rng.randint(lo, hi)
            # 주 후보를 depth_rank 에 놓으려면 그 위에 depth_rank-1 개가 필요하다
            k = max(depth_rank + len(others), spec.n_feasible)
            k = min(k, n - len(mine_blocked))  # 내가 막는 후보는 반드시 k 밖
            k = max(k, spec.n_feasible)
            th = UNIFORM_THRESHOLD if uniform_th else rng.choice(THRESHOLD_POOL)
        if spec.n_feasible == 0:
            k = min(n - len(mine_blocked), max(1, n // 2))

        n_free_above = k - spec.n_feasible
        if n_free_above < 0 or n_free_above > len(free):
            return None  # 이 조합으로는 불변조건을 만족할 수 없다 — 재시도
        above_free = rng.sample(free, n_free_above)

        # 수락 구간(1..k) 배치 — 주 후보를 목표 깊이에, 나머지 F는 그 위/아래로 흩는다
        accepted = others + above_free
        rng.shuffle(accepted)
        if primary is not None:
            pos = min(len(accepted), max(0, min(depth_rank, k) - 1))
            accepted.insert(pos, primary)
        rejected = [c for c in cands if c not in accepted]
        rng.shuffle(rejected)
        out.append((th, len(accepted), accepted + rejected))
    return feasible, out


def build_case(case_id: str, spec: TypeSpec, n_part: int, depth: str, rng: random.Random) -> dict:
    cands = [f"S{i + 1:02d}" for i in range(N_CANDIDATES)]
    for _ in range(200):
        built = _rankings(spec, n_part, cands, depth, rng)
        if built is None:
            continue
        feasible, per_part = built
        profiles = []
        for j, (th, k, order) in enumerate(per_part):
            vals = _values_for(k, len(cands), th, spec.value_profile, rng)
            profiles.append(
                {
                    "pid": f"P{j}",
                    "utilities": {c: vals[p] for p, c in enumerate(order)},
                    "initial_threshold": th,
                }
            )
        # 실제 실후보가 의도한 F와 같은지 확인 — 값 반올림이 경계를 넘길 수 있다
        actual = [
            c
            for c in cands
            if all(p["utilities"][c] >= p["initial_threshold"] for p in profiles)
        ]
        if sorted(actual) != sorted(feasible):
            continue
        raw = {
            "case_id": case_id,
            "candidates": cands,
            "profiles": profiles,
            "meta": {
                "schema_version": SCHEMA_VERSION,
                "track": "functional",
                "scenario_type": spec.scenario_type,
                "expected_no_deal": spec.n_feasible == 0,
                "description": spec.description,
                "common_feasible_count": spec.n_feasible,
                "tags": [f"participants:{n_part}", f"depth:{depth}"],
            },
        }
        errors = validate_case(raw, case_id)
        if errors:
            raise SystemExit("생성기가 계약을 어겼다:\n" + "\n".join(errors))
        return raw
    raise SystemExit(f"{case_id}: 200회 시도에도 불변조건을 만족하는 구성을 찾지 못했다")


def generate(n_part: int, per_type: int, seed: int, start: int, out_dir: Path) -> list[Path]:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    depths = list(DEPTH_BANDS)
    written = []
    seq = start
    for i in range(per_type):
        for spec in TYPES:
            depth = depths[i % len(depths)]  # 유형 안에서 깊이를 순환 배치 → 깊이 편향 방지
            case_id = f"F-{n_part}p-{seq:03d}-{spec.scenario_type.replace('_', '-')}"
            raw = build_case(case_id, spec, n_part, depth, rng)
            path = out_dir / f"{case_id}.json"
            path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            written.append(path)
            seq += 1
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--participants", type=int, default=3)
    ap.add_argument("--per-type", type=int, default=2, help="유형 1종당 케이스 수 (전체 = ×5)")
    ap.add_argument("--pilot", action="store_true", help="유형별 2건 = 10건 (계획서 §6.4-1)")
    ap.add_argument("--seed", type=int, default=20260811)
    ap.add_argument("--start", type=int, default=1, help="case_id 일련번호 시작값")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    per_type = 2 if args.pilot else args.per_type
    written = generate(args.participants, per_type, args.seed, args.start, args.out)
    print(f"{len(written)}건 생성 → {args.out}")
    for p in written:
        print(f"  {p.name}")


if __name__ == "__main__":
    main()
