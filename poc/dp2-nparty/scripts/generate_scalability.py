"""참여자 수 Scalability family 생성기 — 25 §25.5의 난이도 교락 통제를 정적 파일로 고정한다.

왜 정적 파일이 필요한가. 동료 PoC의 `ControlledTableUfun`은 공통 feasible 후보 수 k를
고정하지만, `Experiment`가 N 수준마다 `random.Random((seed, n_participants, ...))`로
프로파일을 새로 뽑는다 — **N=3의 참여자 3명과 N=4의 참여자 3명이 다른 사람**이다.
그래서 N 수준 간 분산이 커지고, 실제로 b_msg의 95% 신뢰구간이 3개 등급에 걸쳐
(25 §25.3) 등급 판정이 유보된 상태다.

본 생성기는 계획서 §7.2의 요구를 지킨다 — **N이 늘어도 기존 참여자는 그대로 두고
새 참여자만 추가한다.** family 1개당 10명분 프로파일을 한 번 만들고 앞에서부터 잘라
N ∈ {3,4,5,6,8,10}의 6개 파일을 낸다. 같은 사람이 계속 남으므로 N 사이의 차이가
'참여자가 늘어난 것' 하나로 좁혀진다.

k 불변의 보장: F 밖 후보마다 blocker를 **초기 3인 중에서** 고른다. 그러면 그 사람은
어느 N에서도 참가자에 포함되므로 그 후보는 끝까지 유효 후보가 되지 못한다.
따라서 common_feasible_count는 family 안에서 정확히 k로 유지된다.

사용:
    .venv/bin/python scripts/generate_scalability.py            # 30 family × 6 = 180건
    .venv/bin/python scripts/generate_scalability.py --per-k 2  # 축소 (k당 2 family)
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dp2_nparty.benchmark import CASES_DIR, SCHEMA_VERSION, validate_case

OUT_DIR = CASES_DIR / "scalability" / "participants"
N_CANDIDATES = 12  # 계획서 §7.2 통제 조건 (잠정값) — Functional과 맞춘다
N_LEVELS = (3, 4, 5, 6, 8, 10)  # 25 §25.5 로그 등간격 6단계
MAX_N = max(N_LEVELS)
BASE_N = min(N_LEVELS)
K_VALUES = (1, 2, 3)  # 계획서 §7.3 — k별 10 family
THRESHOLD_POOL = (0.30, 0.35, 0.40, 0.45, 0.50)


def build_family(k: int, rng: random.Random) -> tuple[list[str], list[dict], list[str]]:
    """10명분 프로파일을 한 번에 만든다. N 수준 파일은 이것을 앞에서부터 자른 것이다."""
    cands = [f"S{i + 1:02d}" for i in range(N_CANDIDATES)]
    common = sorted(rng.sample(cands, k))
    others = [c for c in cands if c not in common]
    # blocker는 반드시 초기 3인 중에서 — 그래야 모든 N에서 그 후보가 막힌다
    blockers = {c: rng.randrange(BASE_N) for c in others}
    # 모든 초기 참여자가 최소 1건은 막도록 보정 (없으면 k보다 많은 실후보가 생길 수 있다)
    for j in range(BASE_N):
        if not any(b == j for b in blockers.values()):
            blockers[rng.choice(others)] = j

    profiles = []
    for j in range(MAX_N):
        th = rng.choice(THRESHOLD_POOL)
        util = {}
        for c in common:
            util[c] = round(rng.uniform(th + 0.01, 1.0), 4)
        for c in others:
            if blockers[c] == j:
                util[c] = round(rng.uniform(0.02, th - 0.01), 4)
            else:
                util[c] = round(rng.random(), 4)
        profiles.append({"pid": f"P{j}", "utilities": util, "initial_threshold": th})
    return cands, profiles, common


def family_cases(family_id: str, k: int, rng: random.Random) -> list[dict]:
    cands, profiles, common = build_family(k, rng)
    out = []
    for n in N_LEVELS:
        members = profiles[:n]
        # 실제 실후보가 정확히 k개인지 확인 — blocker 규칙이 지켜졌는지의 검산
        feasible = [
            c for c in cands if all(p["utilities"][c] >= p["initial_threshold"] for p in members)
        ]
        if sorted(feasible) != common:
            return []  # 재시도 신호
        case_id = f"S-{family_id}-n{n:02d}"
        raw = {
            "case_id": case_id,
            "candidates": cands,
            "profiles": members,
            "meta": {
                "schema_version": SCHEMA_VERSION,
                "track": "scalability",
                "scenario_type": "participants_sweep",
                "expected_no_deal": False,
                "description": (
                    f"참여자 수 스윕 family {family_id} (N={n}). 공통 실후보 {k}개를 N과 무관하게"
                    " 고정하고, N이 늘어도 기존 참여자 프로파일은 바뀌지 않는다."
                ),
                "family_id": family_id,
                "common_feasible_count": k,
                "tags": [f"k:{k}", f"participants:{n}"],
            },
        }
        errors = validate_case(raw, case_id)
        if errors:
            raise SystemExit("생성기가 계약을 어겼다:\n" + "\n".join(errors))
        out.append(raw)
    return out


def generate(per_k: int, seed: int, out_dir: Path) -> list[Path]:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for k in K_VALUES:
        made = 0
        attempts = 0
        while made < per_k:
            attempts += 1
            if attempts > 200 * per_k:
                raise SystemExit(f"k={k}: family 생성 실패 — 불변조건을 만족하지 못했다")
            family_id = f"k{k}-f{made + 1:02d}"
            cases = family_cases(family_id, k, rng)
            if not cases:
                continue
            for raw in cases:
                path = out_dir / f"{raw['case_id']}.json"
                path.write_text(
                    json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                written.append(path)
            made += 1
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-k", type=int, default=10, help="k값 1개당 family 수 (계획서 §7.3: 10)")
    ap.add_argument("--seed", type=int, default=20260814)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    written = generate(args.per_k, args.seed, args.out)
    n_family = len(written) // len(N_LEVELS)
    print(f"{len(written)}건 생성 ({n_family} family × {len(N_LEVELS)} 수준) → {args.out}")


if __name__ == "__main__":
    main()
