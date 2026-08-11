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
# early가 2부터인 이유: 1순위 자리는 미끼 후보(아래 참조)에게 비워 둔다.
DEPTH_BANDS = {"early": (2, 3), "middle": (4, 7), "late": (8, 10)}

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
    decoy: bool  # 미끼 후보를 심는가 (아래 설명)
    description: str


# 미끼(decoy) 후보 — 두 방안을 갈라놓는 장치.
#
# 마지막 바퀴에서 revised threshold가 initial까지 내려오면 전원이 순위대로 전부 제출한다.
# 이때 방안 1은 "누군가의 1순위"가 실후보이기만 하면 첫 라운드에 곧바로 닫는다. x*는 총효용
# 최대라 대체로 모두에게 상위권이므로, 아무 장치 없이 만들면 방안 1도 x*를 잡아버려
# 두 방안의 결과가 같아진다 — 파일럿 1차에서 판별율 10%·천장 효과 90%로 확인했다.
#
# 그래서 "총효용은 낮은데 한 참여자에게는 1순위인 실후보"를 심는다. 방안 1은 이 미끼에
# 먼저 닫히고(달성률 하락), 방안 2는 전원이 직접 제안할 때까지 기다려 x*에 도달한다.
# 24 §24.4가 묻는 "빠른 성립이 낮은 안에 일찍 닫히는가"가 바로 이 구조다.

TYPES = (
    TypeSpec("wide_common", 4, "smooth", False, True, "전원 수락 가능한 상위 후보가 여러 개인 사례."),
    TypeSpec("single_common", 1, "smooth", False, False, "전원의 바닥선을 넘는 실후보가 하나뿐인 사례."),
    TypeSpec(
        "utility_tradeoff", 3, "bimodal", False, True,
        "유효 후보가 여러 개지만 총효용 차이가 커서 어느 것으로 닫히는지가 갈리는 사례.",
    ),
    TypeSpec(
        "bottleneck_participant", 2, "smooth", True, True,
        "한 참여자의 높은 바닥선이 전체 유효 영역을 제한하는 사례.",
    ),
    TypeSpec("no_deal_optimal", 0, "smooth", False, False, "전원의 바닥선을 넘는 실후보가 없어 결렬이 최적인 사례."),
)


def _values_for(
    k: int,
    n: int,
    threshold: float,
    profile: str,
    rng: random.Random,
    high_n: int | None = None,
    tail_near: int = 0,
) -> list[float]:
    """순위 1..n 에 놓일 utility 값 — 앞의 k개는 바닥선 이상, 나머지는 미만.

    tail_near > 0 이면 수락 구간의 **맨 아래 tail_near 개를 바닥선 바로 위**에 붙인다.
    이것이 미끼 구조의 핵심이다 — 실후보 전체가 이 참여자에게 '겨우 수락 가능'이어야
    revised threshold가 initial까지 내려온 마지막 바퀴에야 열린다. 그래야 방안 1이
    x*를 미리 잡아버리지 않고, 같은 바퀴 안에서 라운드 순서로 승부가 난다.

    bimodal은 수락 구간을 상위군과 '겨우 넘긴 군'으로 갈라 총효용 격차를 만든다.
    """
    if tail_near:
        head_n = k - tail_near
        head = sorted((rng.uniform(threshold + 0.12, 1.0) for _ in range(head_n)), reverse=True)
        above = head + [threshold + 0.005 * (tail_near - i) for i in range(tail_near)]
    elif profile == "bimodal" and k >= 2:
        hi_n = max(1, min(k - 1, high_n if high_n else k // 2))
        high = [rng.uniform(max(threshold + 0.2, 0.75), 1.0) for _ in range(hi_n)]
        low = [rng.uniform(threshold + 0.005, threshold + 0.08) for _ in range(k - hi_n)]
        above = sorted(high, reverse=True) + sorted(low, reverse=True)
    else:
        above = sorted((rng.uniform(threshold + 0.005, 1.0) for _ in range(k)), reverse=True)
    below = sorted((rng.uniform(0.02, threshold - 0.01) for _ in range(n - k)), reverse=True)
    return [round(v, 4) for v in above + below]


def _rankings(
    spec: TypeSpec,
    n_part: int,
    cands: list[str],
    depth: str,
    rng: random.Random,
    plan2_miss: bool = False,
):
    """참여자별 (바닥선, 수락 후보 수 k, 순위 나열)를 만든다.

    불변조건:
    - F(실후보)는 전원의 상위 k 안에 든다 → 전원이 수락 가능
    - F 밖의 후보는 최소 한 명의 k 밖에 있다 → 유효 후보가 아니다 (blocker 배정)
    - 주 후보(x*가 될 것)는 전원에게 목표 순위 깊이에 놓인다 — 1순위는 아니다
    - 미끼가 있으면: 소유자에게만 1순위, 나머지에게는 수락 구간의 최하위
    """
    n = len(cands)
    lo, hi = DEPTH_BANDS[depth]
    feasible = rng.sample(cands, spec.n_feasible)
    primary = feasible[0] if feasible else None
    decoy = feasible[1] if (spec.decoy and len(feasible) >= 2) else None
    others = [c for c in feasible[1:] if c != decoy]
    infeasible = [c for c in cands if c not in feasible]

    # F 밖 후보마다 blocker 1명 — 그 사람의 수락 범위 밖에 둔다.
    # 균등 배분하면 전원의 수락 범위 상한이 같아져 x*의 순위 깊이가 얕은 쪽으로만 몰린다.
    # 그래서 한 명에게 몰아주는 쏠린 배분을 쓴다 — 나머지는 수락 범위가 넓어져 깊은 순위가 가능해진다.
    weights = [rng.random() ** 2 + 0.05 for _ in range(n_part)]
    blockers = {c: rng.choices(range(n_part), weights=weights)[0] for c in infeasible}

    # constrained = 실후보 전체를 '겨우 수락 가능'으로 붙잡아 두는 참여자.
    # 반드시 **수락 범위가 가장 넓은**(= 막는 후보가 가장 적은) 참여자여야 한다.
    # 방안 2의 성립 라운드는 max_i rank_i(후보)로 정해지므로, 순위가 가장 깊은 이 사람이
    # 어느 후보가 먼저 완성되는지를 결정한다. 다른 사람을 고르면 구성이 무력해진다.
    blocked_n = [sum(1 for b in blockers.values() if b == j) for j in range(n_part)]
    by_depth = sorted(range(n_part), key=lambda j: (blocked_n[j], j))
    if spec.bottleneck:
        owner, constrained = 1, 0  # P0가 병목 — 수락 범위가 좁아 미끼를 둘 자리가 없다
    else:
        constrained = by_depth[0]
        owner = by_depth[-1]  # 미끼 소유자는 수락 범위가 좁은 쪽 — 미끼가 얕게 열린다

    # 깊이를 참여자별로 먼저 확정한다. k = depth_rank + |F| - 1 이므로 깊이가 곧 수락 범위이고,
    # 방안 2의 성립 순서(max_i rank_i)는 가장 깊은 참여자가 지배한다 — 그래서 깊이를
    # 루프 안에서 각자 뽑으면 누가 지배자인지 통제할 수 없다.
    k_maxes = [n - blocked_n[j] for j in range(n_part)]
    base = rng.randint(lo, hi)
    cap = [km - spec.n_feasible + 1 for km in k_maxes]
    depth_ranks = [max(2, min(base, cap[j])) for j in range(n_part)]
    if spec.bottleneck:
        depth_ranks[0] = 2  # 병목 참여자는 수락 범위를 F 바로 위로 좁힌다
    if plan2_miss and others:
        # constrained를 확실한 최심으로 만든다 — 그래야 x*가 아닌 얕은 실후보가 먼저 완성된다
        target = max(depth_ranks) + spec.n_feasible - 1
        depth_ranks[constrained] = max(2, min(target, cap[constrained]))
        rest_max = max(d for j, d in enumerate(depth_ranks) if j != constrained)
        if depth_ranks[constrained] < rest_max + spec.n_feasible - 2:
            return None  # 깊이 차를 낼 여지가 없다 — 다른 blocker 배분으로 재시도

    uniform_th = rng.random() < 0.4  # threshold 구성 편향 방지 — 동일/상이를 섞는다
    out = []
    for j in range(n_part):
        mine_blocked = [c for c, b in blockers.items() if b == j]
        free = [c for c in infeasible if blockers[c] != j]

        k_max = k_maxes[j]
        depth_rank = depth_ranks[j]
        th = UNIFORM_THRESHOLD if uniform_th else rng.choice(THRESHOLD_POOL)
        if spec.n_feasible == 0:
            depth_rank, k = 1, min(k_max, max(1, n // 2))
        elif spec.bottleneck and j == 0:
            th = 0.70
            k = spec.n_feasible + 1
        else:
            k = depth_rank + spec.n_feasible - 1
        # k < 1 은 그 참여자가 모든 비실후보를 막아 수락 구간이 비는 경우 — 쏠린 blocker
        # 배분에서 드물게 나온다. 재시도로 처리한다.
        if k > k_max or k < max(1, spec.n_feasible):
            return None  # 이 조합으로는 불변조건을 만족할 수 없다 — 재시도

        n_free_above = k - spec.n_feasible
        if n_free_above < 0 or n_free_above > len(free):
            return None
        above_free = rng.sample(free, n_free_above)
        rng.shuffle(above_free)

        # 수락 구간(1..k) 배치
        if primary is None:
            accepted = above_free
        elif decoy is not None and j == owner:
            # 미끼가 1순위 — 방안 1은 마지막 바퀴 **첫 라운드**에 여기서 닫힌다
            accepted = [decoy, primary] + others + above_free
        elif decoy is not None and plan2_miss and others and j == constrained:
            # 방안 2도 x*를 놓치는 구성 — 이 참여자에게만 x*를 다른 실후보보다 깊게 둔다.
            # 방안 2는 '전원이 낸 순간'이 가장 이른 후보로 닫히므로 얕은 쪽(others)을 고르고,
            # 총효용 최대인 x*는 놓친다. 두 방안 모두 만점이 아닌 사례가 있어야
            # 표본이 어느 한쪽의 우세를 구조적으로 보장하지 않는다.
            accepted = above_free + others + [primary, decoy]
        elif decoy is not None:
            # 실후보 블록을 수락 구간 맨 아래에, 미끼를 그 맨 끝에 —
            # 방안 2는 전원이 직접 낼 때까지 기다리므로 미끼(최하위)보다 x*가 먼저 완성된다
            accepted = above_free + [primary] + others + [decoy]
        else:
            accepted = above_free[: depth_rank - 1] + [primary] + others + above_free[depth_rank - 1 :]
        if len(accepted) != k:
            return None
        if accepted[0] in feasible and not (decoy is not None and j == owner):
            return None  # 미끼 외의 실후보가 1순위면 방안 1이 그것으로 닫혀 판별 구조가 무너진다
        rejected = [c for c in cands if c not in accepted]
        rng.shuffle(rejected)
        # constrained 참여자에게만 실후보 전체를 바닥선 바로 위로 붙인다 → 개방 시점을 마지막 바퀴로
        tail_near = spec.n_feasible if (j == constrained and decoy is not None) else 0
        out.append((th, k, depth_rank, tail_near, accepted + rejected))
    return feasible, primary, decoy, out


def build_case(
    case_id: str,
    spec: TypeSpec,
    n_part: int,
    depth: str,
    rng: random.Random,
    plan2_miss: bool = False,
) -> dict:
    cands = [f"S{i + 1:02d}" for i in range(N_CANDIDATES)]
    # 깊은 순위 + plan2-miss 조합은 후보 수가 12개로 고정된 탓에 참여자가 많으면
    # 성립하지 않을 수 있다. 그때는 일반 구성으로 물러난다 (실제 구성은 tags에 남는다).
    for attempt in range(800):
        want_miss = plan2_miss and attempt < 400
        built = _rankings(spec, n_part, cands, depth, rng, want_miss)
        if built is None:
            continue
        feasible, primary, decoy, per_part = built
        profiles = []
        for j, (th, k, depth_rank, tail_near, order) in enumerate(per_part):
            # bimodal일 때 상위군을 depth_rank까지로 잡아야 주 후보가 상위군에 들어간다
            vals = _values_for(
                k, len(cands), th, spec.value_profile, rng, high_n=depth_rank, tail_near=tail_near
            )
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
        # x*가 의도한 주 후보인지 — 미끼가 총효용까지 이기면 판별 구조가 뒤집힌다
        if primary is not None:
            totals = {c: sum(p["utilities"][c] for p in profiles) for c in feasible}
            no_deal_total = sum(p["initial_threshold"] for p in profiles)
            if max(totals, key=lambda c: totals[c]) != primary:
                continue
            if totals[primary] <= no_deal_total:
                continue  # 결렬보다 못한 합의는 이 유형의 의도가 아니다
            if decoy is not None and totals[decoy] >= totals[primary] * 0.95:
                continue  # 미끼와 x*의 총효용 격차가 없으면 달성률 차이가 안 보인다
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
                "tags": [f"participants:{n_part}", f"depth:{depth}"]
                + (["variant:plan2-miss"] if want_miss and spec.decoy else []),
            },
        }
        errors = validate_case(raw, case_id)
        if errors:
            raise SystemExit("생성기가 계약을 어겼다:\n" + "\n".join(errors))
        return raw
    raise SystemExit(f"{case_id}: 800회 시도에도 불변조건을 만족하는 구성을 찾지 못했다")


def generate(n_part: int, per_type: int, seed: int, start: int, out_dir: Path) -> list[Path]:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    depths = list(DEPTH_BANDS)
    written = []
    seq = start
    for i in range(per_type):
        for spec in TYPES:
            depth = depths[i % len(depths)]  # 유형 안에서 깊이를 순환 배치 → 깊이 편향 방지
            # 절반은 방안 2도 x*를 놓치는 구성 — 표본이 한쪽 방안의 우세를 보장하지 않게 한다
            plan2_miss = spec.n_feasible >= 3 and i % 2 == 1
            case_id = f"F-{n_part}p-{seq:03d}-{spec.scenario_type.replace('_', '-')}"
            raw = build_case(case_id, spec, n_part, depth, rng, plan2_miss)
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
