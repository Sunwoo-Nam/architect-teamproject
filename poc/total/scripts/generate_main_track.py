#!/usr/bin/env python3
"""main 트랙 생성기 — 현실 모사 단일 정본 후보 셋 (PL 확정 2026-08-13).

구성 (docs 없이 이 파일이 근거 기록):
- 후보 구조: 복합의제 4개 — 날짜 6 × 시간 4 × 장소 3 × 활동 4 = 288 조합.
  utility = 의제별 가중치×점수의 합 (선형 가중합 — 저장은 축 수준이라 케이스당 ~5KB).
- 인원: 3/5/7/10/15/20/30 — 7레벨 × 100케이스 = 700.
- 유형 4종 × 24 + 결렬 4 = 레벨당 100:
  balanced(고른 선호) / champion(편중 — 각자 강한 최애 존재) /
  bottleneck(병목 — 한 명의 선호가 뾰족해 수용 폭이 좁음) / polarized(양극화 — 두 그룹 상충)
- K(공통 유효 후보): 자연 유도 — 선호는 자유 생성하고 **threshold를 캘리브레이션**한다.
  목표 K*를 조합의 5-20%에서 뽑고, "전원 최소효용 상위 K*"가 통과하도록 각자
  threshold = min_{c∈C*} u_i(c) − ε 로 설정. 실측 K를 meta에 기록·검산한다.
  (N이 크면 독립 무작위로는 공통 유효가 소멸하므로 이 방식이 유일하게 현실적 —
  각자의 수락 기준이 자기 효용 분포 눈높이라는 점에서도 자연스럽다.)
- 결렬 케이스: 공통 유효가 0이 될 때까지 차단 참여자의 threshold를 올려 만든다.

사용: python scripts/generate_main_track.py  → datasets/nparty/main/*.json
"""
from __future__ import annotations

import itertools
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets" / "nparty" / "main"  # cases/ 밖 — 벤치마크 로더의 전체 스캔 검증과 충돌 방지

SEED = 20260813
ISSUES = [
    {"id": "date", "name": "날짜", "values": ["11-14", "11-15", "11-16", "11-17", "11-18", "11-19"]},
    {"id": "time", "name": "시간", "values": ["12:00", "15:00", "18:00", "20:30"]},
    {"id": "venue", "name": "장소", "values": ["강남", "홍대", "잠실"]},
    {"id": "activity", "name": "활동", "values": ["영화", "식사", "보드게임", "전시"]},
]
S = 6 * 4 * 3 * 4  # 288
N_LEVELS = (3, 5, 7, 10, 15, 20, 30)
TYPES = ("balanced", "champion", "bottleneck", "polarized")
PER_TYPE = 24
NO_DEAL = 4          # 레벨당 4건 = 4% (~5% 지시)
K_RATIO = (0.05, 0.20)
EPS = 1e-6


def _weights(rng):
    raw = [rng.random() + 0.1 for _ in ISSUES]
    tot = sum(raw)
    w = [round(r / tot, 4) for r in raw]
    w[-1] = round(1.0 - sum(w[:-1]), 4)  # 합 정확히 1 (검증기 요구)
    return {i["id"]: x for i, x in zip(ISSUES, w)}


def _scores(rng, flavor, idx, n):
    """유형별 의제값 점수 생성."""
    out = {}
    for issue in ISSUES:
        vals = issue["values"]
        if flavor == "balanced":
            sc = {v: rng.random() for v in vals}
        elif flavor == "champion":
            fav = rng.choice(vals)  # 각자 뚜렷한 최애 — 나머지는 낮게
            sc = {v: (rng.uniform(0.85, 1.0) if v == fav else rng.uniform(0.0, 0.6)) for v in vals}
        elif flavor == "bottleneck":
            if idx == 0:  # 병목 참여자 — 극도로 뾰족한 선호
                fav = rng.choice(vals)
                sc = {v: (rng.uniform(0.9, 1.0) if v == fav else rng.uniform(0.0, 0.25)) for v in vals}
            else:
                sc = {v: rng.random() for v in vals}
        else:  # polarized — 두 그룹이 값 절반씩을 상반되게 선호
            group = idx % 2
            half = len(vals) // 2
            sc = {}
            for j, v in enumerate(vals):
                mine = (j < half) == (group == 0)
                sc[v] = rng.uniform(0.6, 1.0) if mine else rng.uniform(0.0, 0.4)
        out[issue["id"]] = {v: round(s, 4) for v, s in sc.items()}
    return out


def _utilities(w, sc):
    combos = list(itertools.product(*[i["values"] for i in ISSUES]))
    ids = [i["id"] for i in ISSUES]
    return combos, [sum(w[a] * sc[a][v] for a, v in zip(ids, c)) for c in combos]


def build_case(rng, n, flavor, no_deal, case_id):
    parts = [{"pid": f"P{i}", "weights": _weights(rng), "scores": _scores(rng, flavor, i, n)}
             for i in range(n)]
    utils = []
    combos = None
    for p in parts:
        combos, u = _utilities(p["weights"], p["scores"])
        utils.append(u)

    # 전원 최소효용 기준 상위 K* 선정 → threshold 캘리브레이션
    min_u = [min(utils[i][j] for i in range(n)) for j in range(S)]
    order = sorted(range(S), key=lambda j: -min_u[j])
    if not no_deal:
        k_target = max(2, round(rng.uniform(*K_RATIO) * S))
        cstar = order[:k_target]
        for i, p in enumerate(parts):
            p["initial_threshold"] = round(min(utils[i][j] for j in cstar) - EPS, 4)
    else:
        # 결렬: 공통 유효 0이 될 때까지 차단 — 각자 자기 90분위에서 시작해 올린다
        for i, p in enumerate(parts):
            srt = sorted(utils[i])
            p["initial_threshold"] = round(srt[int(0.9 * S)], 4)
        while True:
            feas = [j for j in range(S)
                    if all(utils[i][j] >= parts[i]["initial_threshold"] for i in range(n))]
            if not feas:
                break
            j = feas[0]
            i = min(range(n), key=lambda i_: utils[i_][j] - parts[i_]["initial_threshold"])
            parts[i]["initial_threshold"] = round(utils[i][j] + EPS, 4)

    # 실측 K (검산·기록)
    k_actual = sum(1 for j in range(S)
                   if all(utils[i][j] >= parts[i]["initial_threshold"] for i in range(n)))
    assert (k_actual == 0) == no_deal, (case_id, k_actual, no_deal)
    if not no_deal:
        assert k_actual >= 2, (case_id, k_actual)

    return {
        "case_id": case_id,
        "issues": ISSUES,
        "participants": parts,
        "meta": {
            "schema_version": "issue-space-case.v1",
            "track": "issue_space",  # 검증기 고정값 — main 트랙 식별은 디렉터리·태그로
            "scenario_type": flavor if not no_deal else "no_deal",
            "combination_count": S,
            "issue_sizes": [len(i["values"]) for i in ISSUES],
            "common_feasible_count": k_actual,
            "expected_no_deal": no_deal,
            "tags": ["track:main", f"participants:{n}",
                     f"type:{flavor if not no_deal else 'no_deal'}",
                     f"k:{k_actual}", f"feasible_ratio:{k_actual / S:.4f}"],
            "description": f"main 트랙 — {n}인·{flavor if not no_deal else '결렬'} 유형. "
                           f"의제 4개(6×4×3×4=288 조합), utility는 의제 가중합. "
                           f"공통 유효 후보 {k_actual}개 (threshold 캘리브레이션, 생성기 참조).",
        },
    }


def main() -> int:
    rng = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    count = 0
    ks = []
    for n in N_LEVELS:
        idx = 0
        for flavor in TYPES:
            for _ in range(PER_TYPE):
                idx += 1
                c = build_case(rng, n, flavor, False, f"M-{n:02d}p-{flavor}-{idx:03d}")
                (OUT / f"{c['case_id']}.json").write_text(
                    json.dumps(c, ensure_ascii=False))
                ks.append(c["meta"]["common_feasible_count"])
                count += 1
        for _ in range(NO_DEAL):
            idx += 1
            c = build_case(rng, n, rng.choice(TYPES), True, f"M-{n:02d}p-nodeal-{idx:03d}")
            (OUT / f"{c['case_id']}.json").write_text(json.dumps(c, ensure_ascii=False))
            count += 1
    import statistics
    print(f"생성 {count}건 → {OUT}")
    print(f"K 실측: 최소 {min(ks)} · 중앙값 {statistics.median(ks)} · 최대 {max(ks)} "
          f"(비율 {min(ks)/S:.1%}-{max(ks)/S:.1%})")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
