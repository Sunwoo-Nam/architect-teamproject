"""참여자 수 Scalability family 생성기 — 참여자 수 외의 조건을 고정한 정적 케이스.

왜 정적 파일인가. 동료 PoC의 `ControlledTableUfun`은 전원이 수락 가능한 후보 수 k를
고정하지만, `Experiment`가 N 수준마다 `random.Random((seed, n_participants, ...))`로
프로파일을 새로 뽑는다 — **N=3의 참여자 3명과 N=4의 참여자 3명이 다른 사람**이다.
그러면 N 사이의 차이에 '참여자가 늘어난 효과'와 '문제가 통째로 바뀐 효과'가 함께 섞인다.

본 생성기는 family 하나에서 참여자 50명분과 후보 200개분을 한 번에 만들고 앞에서부터
잘라 각 N 수준의 파일을 낸다. 따라서 N이 늘어도 **기존 참여자와 기존 후보는 그대로이고,
새 참여자와 새 후보만 추가된다.**

후보 수를 N과 함께 늘리는 근거: 기준 시나리오가 3인·후보 12개이므로 **1인당 후보 4개**다.
그 비율을 모든 N에서 유지한다(M = 4N). 새 임의 상수를 만들지 않으면서, 참여자가 늘 때
탐색해야 할 공간도 함께 커지는 실제 상황을 반영한다.

k 불변의 보장: 공통 후보가 아닌 후보마다 '수락하지 않을 참여자'를 **초기 3인 중에서**
지정한다. 그 사람은 어느 N에서도 참가자에 포함되므로 그 후보는 끝까지 유효 후보가 되지
못한다. 뒤에 추가되는 후보들도 같은 규칙을 따르므로, common_feasible_count는 family 안에서
정확히 k로 유지된다.

사용:
    .venv/bin/python scripts/generate_scalability.py            # 30 family × 10 수준 = 300건
    .venv/bin/python scripts/generate_scalability.py --per-k 2  # 축소 (k당 2 family)
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

# [이식 시 수정] 본 파일은 poc/total/scripts/ 에 있으므로 parents[1] 이 poc/total 이고,
# 소스 루트는 poc/total/src 다 (원본 poc/dp2-nparty/scripts 와 폴더 깊이는 같다).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# [이식 시 수정] 원본은 `dp2_nparty.benchmark` 였다. 이식된 로더는
# total/adapters/nparty/_vendor/benchmark.py 에 있고, 그 안의 CASES_DIR 이 이미
# poc/total/datasets/nparty/cases 를 가리키므로 출력 경로 상수를 여기서 다시 쓰지 않는다 —
# 로더가 읽는 폴더와 생성기가 쓰는 폴더를 한 곳에서 정의해야 둘이 어긋나지 않는다.
from total.adapters.nparty._vendor.benchmark import CASES_DIR, SCHEMA_VERSION, validate_case

OUT_DIR = CASES_DIR / "scalability" / "participants"

# N 수준 — 로그에 가까운 간격 10단계.
#   3~10  : 실사용 구간. 만장일치 완결 규칙에서 실제로 합의가 성립할 수 있는 범위
#   15~50 : 구조 검증 구간. 이 규모는 후보 공간이 아무리 커도 만장일치로는 도달할 수
#           없다(N=20에 필요한 후보 6.3만 개 > 의제 조합 상한 32,768). 전원 수락 가능
#           후보를 심어서 자원 추세만 관찰하는 구간이며, 그 사실을 결과 해석에 명시한다.
N_LEVELS = (3, 4, 5, 6, 8, 10, 15, 20, 30, 50)
MAX_N = max(N_LEVELS)
BASE_N = min(N_LEVELS)

CANDIDATES_PER_PARTICIPANT = 4  # 기준 시나리오 3인·후보 12개에서 도출
MAX_CANDIDATES = CANDIDATES_PER_PARTICIPANT * MAX_N

K_VALUES = (1, 2, 3)  # 계획서 §7.3 — k별 10 family
THRESHOLD_POOL = (0.30, 0.35, 0.40, 0.45, 0.50)


def candidates_for(n: int) -> int:
    return CANDIDATES_PER_PARTICIPANT * n


def build_family(k: int, rng: random.Random) -> tuple[list[str], list[dict], list[str]]:
    """참여자 50명분 × 후보 200개분을 한 번에 만든다. N 수준 파일은 이것을 잘라낸 것이다."""
    cands = [f"S{i + 1:04d}" for i in range(MAX_CANDIDATES)]
    base_pool = cands[: candidates_for(BASE_N)]  # 공통 후보는 최소 N에도 존재해야 한다
    common = sorted(rng.sample(base_pool, k))
    others = [c for c in cands if c not in common]
    # 수락하지 않을 참여자는 반드시 초기 3인 중에서 — 그래야 모든 N에서 그 후보가 막힌다
    blockers = {c: rng.randrange(BASE_N) for c in others}
    # 최소 N의 후보 범위 안에서 초기 3인이 각각 최소 1건은 막도록 보정
    base_others = [c for c in base_pool if c not in common]
    for j in range(BASE_N):
        if not any(blockers[c] == j for c in base_others):
            blockers[rng.choice(base_others)] = j

    profiles = []
    for j in range(MAX_N):
        th = rng.choice(THRESHOLD_POOL)
        util = {}
        for c in cands:
            if c in common:
                util[c] = round(rng.uniform(th + 0.01, 1.0), 4)
            elif blockers[c] == j:
                util[c] = round(rng.uniform(0.02, th - 0.01), 4)
            else:
                util[c] = round(rng.random(), 4)
        profiles.append({"pid": f"P{j}", "utilities": util, "initial_threshold": th})
    return cands, profiles, common


def family_cases(family_id: str, k: int, rng: random.Random) -> list[dict]:
    all_cands, all_profiles, common = build_family(k, rng)
    out = []
    for n in N_LEVELS:
        cands = all_cands[: candidates_for(n)]
        members = [
            {"pid": p["pid"],
             "utilities": {c: p["utilities"][c] for c in cands},
             "initial_threshold": p["initial_threshold"]}
            for p in all_profiles[:n]
        ]
        # 실제 유효 후보가 정확히 k개인지 확인 — 막기 규칙이 지켜졌는지의 검산
        feasible = [
            c for c in cands if all(p["utilities"][c] >= p["initial_threshold"] for p in members)
        ]
        if sorted(feasible) != common:
            return []  # 재시도 신호
        case_id = f"S-{family_id}-n{n:02d}"
        regime = "실사용" if n <= 10 else "구조검증"
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
                    f"참여자 수 스윕 family {family_id} (N={n}, 후보 {len(cands)}개). "
                    f"전원 수락 가능 후보 {k}개를 N과 무관하게 고정하고, N이 늘어도 기존 참여자와 "
                    "기존 후보는 그대로 두고 새 참여자·새 후보만 추가한다."
                    + ("" if n <= 10 else
                       " 이 규모는 만장일치 완결 규칙으로는 실제 도달할 수 없으므로 자원 추세 관찰용이다.")
                ),
                "family_id": family_id,
                "common_feasible_count": k,
                "tags": [f"k:{k}", f"participants:{n}", f"candidates:{len(cands)}", f"regime:{regime}"],
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
    total_mb = sum(p.stat().st_size for p in written) / 1024 / 1024
    print(f"{len(written)}건 생성 ({n_family} family × {len(N_LEVELS)} 수준, {total_mb:.1f} MB) → {args.out}")
    print(f"  N 수준: {list(N_LEVELS)}")
    print(f"  후보 수: {[candidates_for(n) for n in N_LEVELS]} (1인당 {CANDIDATES_PER_PARTICIPANT}개)")


if __name__ == "__main__":
    main()
