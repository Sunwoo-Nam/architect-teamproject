#!/usr/bin/env python3
"""composite 정본(final) 데이터셋 생성기 — 500건 (PL 지시 2026-08-13).

## 설계 목표

1. **충분히 많은 의제 수 · 다양한 의제 수 조합**: CR 트랙 n=4~12 전 수준(오라클 가능),
   RS 트랙 n=12~20(조합 최대 10^13 — RU·TB 경량 측정).
2. **현실적 시나리오**: 하루 약속 도메인의 축 어휘(날짜·시간·지역·영화·식당·예산…),
   현실 의존성(상영표·지역 소속·심야 귀가·예산-메뉴), 참여자 하드 제약(캘린더).
3. **FC·RU·TB 변별**: nparty functional-ext의 「미끼(planted decoy)」 방법론을 composite에
   이식 — 방안별 구조 약점을 겨냥한 함정을 **효용 수준에서 정밀 배치**하고 oracle로 검산.

## 유형 6종 — 각 판이 검증하는 것

| 유형 | 함정 대상 | 장치 |
|---|---|---|
| hard_path | 경로 의존 검증 | 앞 축의 인기값이 뒤 축의 좋은 값을 하드 제약으로 봉쇄 — 축별 확정의 경로 의존 |
| soft_synergy | 조합 시너지 검증 | 한계효용 상위(=top-k) 값 조합에 soft 감점 — 압축이 좋은 조합을 놓침 |
| mixed | 복합 | 위 두 장치를 서로 다른 축에 동시 배치 (공정성 — 표본이 한쪽 편이 아님) |
| plain | 없음 | 현실 모사 무작위 판 — 함정 없는 기준선 |
| no_deal | 없음 | 결렬이 정답 (참여자 하드 제약 서로소 / 높은 바닥선) — 억지 합의 검증 |
| stress (RS) | RU | 축 수 12~20 — 실물화·총점유의 규모 성장 (FC는 오라클 불가 명시) |

**함정 = 의도 배치 + oracle 검산** (nparty B3와 동일 방법론): 생성 후 케이스마다
전수 열거로 (a) 기대 결과(합의/결렬), (b) x*가 함정 회피 값을 포함, (c) 미끼 조합이
"수락 가능하지만 나쁨" 대역(바닥선 위 0.02~0.3)에 실재함을 검사하고, 불변식을 만족할
때까지 시드를 교체한다(케이스당 상한 40). **방안을 실행해 결과로 선별하지는 않는다** —
그건 표본 조작이다. 함정의 실효는 측정 리포트가 사후 보고한다.

## 재현

    .venv/bin/python scripts/generate_composite_final.py            # 500건 전체
    .venv/bin/python scripts/generate_composite_final.py --pilot    # 수준당 축소판

출력: datasets/composite/final/FIN-*.json + MANIFEST.md (구성 표·검산 요약)
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from total.adapters.composite import load_fixture  # noqa: E402
from total.adapters.composite._vendor.common.oracle import analyze  # noqa: E402

OUT = ROOT / "datasets" / "composite" / "final"
BASE_SEED = 20260813
ORACLE_LIMIT = 150_000       # CR 트랙 조합 상한 (FC 전수 열거 여유)
MAX_RETRY = 40               # 케이스당 시드 재시도 상한

# ---------------------------------------------------------------------------------------
# 축 어휘 — 현실 시나리오 (region 축이 region-소속 축보다 앞에 오도록 순서 고정)
# ---------------------------------------------------------------------------------------

_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_REGIONS = ["gangnam", "hongdae", "yeongdeungpo", "jamsil", "seongsu"]
_MENUS = ["korean", "japanese", "chinese", "italian", "mexican", "vegan"]
_BUDGETS = ["low", "mid", "high", "premium"]
_TRANSPORTS = ["walk", "bus", "subway", "taxi", "car"]
_ACTIVITIES = ["board-game", "karaoke", "bowling", "escape-room", "arcade"]
_DESSERTS = ["bingsu", "cake", "gelato", "waffle"]


def _dates(count, rng):
    picks = rng.sample(range(7), min(count, 7))
    return [{"name": _DAYS[i], "attrs": {"weekend": _DAYS[i] in ("sat", "sun")}}
            for i in sorted(picks)]


def _times(count, rng):
    hours = rng.sample([11, 13, 15, 17, 19, 21], min(count, 6))
    return [{"name": f"{h:02d}:00", "attrs": {"late": h >= 20}} for h in sorted(hours)]


def _regions(count, rng):
    return [{"name": r, "attrs": {}} for r in rng.sample(_REGIONS, min(count, 5))]


def _fixed(pool):
    def gen(count, rng):
        return [{"name": v, "attrs": {}} for v in rng.sample(pool, min(count, len(pool)))]
    return gen


def _numbered(prefix):
    def gen(count, rng):
        return [{"name": f"{prefix}{i + 1}", "attrs": {}} for i in range(count)]
    return gen


def _region_linked(prefix):
    def gen(count, rng, region_names):
        return [{"name": f"{prefix}-{region_names[i % len(region_names)]}-{i // len(region_names) + 1}",
                 "attrs": {"region": region_names[i % len(region_names)]}}
                for i in range(count)]
    return gen


#: (축 이름, 생성기, region 필요 여부, CR count 범위) — 앞에서부터 n개를 쓴다
AXIS_CATALOG = [
    ("date", _dates, False, (4, 6)),
    ("time", _times, False, (3, 5)),
    ("region", _regions, False, (3, 4)),
    ("movie", _numbered("mv"), False, (4, 7)),
    ("restaurant", _region_linked("rest"), True, (3, 5)),
    ("menu", _fixed(_MENUS), False, (3, 5)),
    ("budget", _fixed(_BUDGETS), False, (3, 4)),
    ("theater", _region_linked("thtr"), True, (3, 4)),
    ("transport", _fixed(_TRANSPORTS), False, (3, 4)),
    ("cafe", _region_linked("cafe"), True, (3, 4)),
    ("activity", _fixed(_ACTIVITIES), False, (3, 4)),
    ("dessert", _fixed(_DESSERTS), False, (2, 4)),
    # RS 확장용 (13~20축) — 소형 어휘
    ("gift", _numbered("gift"), False, (3, 4)),
    ("music", _numbered("music"), False, (3, 4)),
    ("seat", _numbered("seat"), False, (3, 4)),
    ("snack", _numbered("snack"), False, (3, 4)),
    ("photo", _numbered("photo"), False, (3, 4)),
    ("walk", _numbered("course"), False, (3, 4)),
    ("game", _numbered("game"), False, (3, 4)),
    ("souvenir", _numbered("souv"), False, (3, 4)),
]


def build_axes(n, rng, cap=ORACLE_LIMIT):
    """앞 n개 축을 실체화하고 조합 수를 cap 이하로 맞춘다 (큰 축부터 축소)."""
    region_names = None
    axes = []
    for name, gen, needs_region, (lo, hi) in AXIS_CATALOG[:n]:
        count = rng.randint(lo, hi)
        if needs_region:
            values = gen(count, rng, region_names or _REGIONS[:3])
        else:
            values = gen(count, rng)
        if name == "region":
            region_names = [v["name"] for v in values]
        axes.append({"name": name, "generator": name, "values": values})
    while math.prod(len(a["values"]) for a in axes) > cap:
        big = max((a for a in axes if len(a["values"]) > 2), key=lambda a: len(a["values"]))
        big["values"] = big["values"][:-1]
    return axes


# ---------------------------------------------------------------------------------------
# 프로파일 — 명시 고정(frozen). 함정은 여기서 효용 수준으로 심는다
# ---------------------------------------------------------------------------------------

def _weights(axes, rng, boost=()):
    raw = {a["name"]: rng.gammavariate(1.0, 1.0) + 0.1 for a in axes}
    for ax in boost:                       # 함정 축은 무게를 실어 판정에 유효하게 만든다
        raw[ax] = max(raw.values()) * rng.uniform(1.3, 1.7)
    total = sum(raw.values())
    return {k: v / total for k, v in raw.items()}


def _scores(axes, rng, rho, p1_scores=None):
    out = {}
    for a in axes:
        n = len(a["values"])
        if p1_scores is None:
            vals = [rng.random() for _ in range(n)]
        else:
            base = p1_scores[a["name"]]
            noise = [rng.random() for _ in range(n)]
            mixed = [rho * b + math.sqrt(max(0.0, 1 - rho * rho)) * z
                     for b, z in zip(base, noise)]
            lo, hi = min(mixed), max(mixed)
            vals = [0.5] * n if hi - lo < 1e-9 else [(v - lo) / (hi - lo) for v in mixed]
        out[a["name"]] = vals
    return out


def make_profiles(axes, rng, rho, thresholds, boost=()):
    w1 = _weights(axes, rng, boost)
    w2 = _weights(axes, rng, boost)
    s1 = _scores(axes, rng, rho)
    s2 = _scores(axes, rng, rho, p1_scores=s1)
    region_names = next((tuple(v["name"] for v in a["values"])
                         for a in axes if a["name"] == "region"), tuple(_REGIONS[:3]))
    profiles = []
    for w, s in ((w1, s1), (w2, s2)):
        profiles.append({
            "weights": w,
            "scores": {a["name"]: {v["name"]: round(s[a["name"]][i], 4)
                                   for i, v in enumerate(a["values"])}
                       for a in axes},
            "home_region": rng.choice(region_names),
            "initial_threshold": thresholds[len(profiles)],
        })
    return profiles


def _set_scores(profiles, axis, mapping):
    """함정 수술 — 두 참여자 모두 같은 값 서열을 갖게 고정 (±0.03 지터)."""
    for p in profiles:
        for vname, s in mapping.items():
            p["scores"][axis][vname] = round(
                min(1.0, max(0.0, s + random.Random(f"{id(p)}{vname}").uniform(-0.03, 0.03))), 4)


# ---------------------------------------------------------------------------------------
# 함정 장치
# ---------------------------------------------------------------------------------------

def plant_pool_trap(axes, profiles, deps, rng):
    """2안(pool) 함정 — 한계효용 상위 조합에 soft 감점 (top-k 압축의 사각).

    t1·t2 축에서 미끼 d1(0.95)·d2(0.86)는 개별로는 최고지만 어느 쪽이든 포함하면
    감점 0.34 — 정답 c(0.62)는 한계효용 3위라 k=2 압축 풀 밖이다.
    """
    cands = [a for a in axes if a["name"] not in ("region",) and len(a["values"]) >= 3]
    t1, t2 = rng.sample(cands, 2)
    planted = {}
    for t in (t1, t2):
        names = [v["name"] for v in t["values"]]
        d1, d2, c = names[0], names[1], names[2]
        mapping = {n: 0.30 for n in names}
        mapping[d1], mapping[d2], mapping[c] = 0.95, 0.86, 0.68
        _set_scores(profiles, t["name"], mapping)
        planted[t["name"]] = {"decoys": [d1, d2], "target": c}
        deps.append({"type": "soft", "rule": "conditional_pref",
                     "if_axis": t["name"], "if_values": [d1, d2],
                     "then_axis": (t2 if t is t1 else t1)["name"],
                     "preferred": [], "penalty": 0.16})
    return {"trap": "pool", "axes": planted, "boost": [t1["name"], t2["name"]]}


def plant_path_trap(axes, profiles, deps, rng):
    """1안(seq) 함정 — 앞 축 인기값이 뒤 축의 좋은 값을 하드 봉쇄 (경로 의존).

    앞 축 e: 미끼 a(0.95) vs 대안 m(0.68). 뒤 축 L의 좋은 값 g1·g2(0.90)는
    availability_explicit로 e=m일 때만 허용 — e=a로 확정하면 L에는 나쁜 값(0.38)뿐.
    """
    early = axes[0] if axes[0]["name"] != "region" else axes[1]
    late_cands = [a for a in axes[2:] if a["name"] != "region" and len(a["values"]) >= 3]
    late = rng.choice(late_cands)
    e_names = [v["name"] for v in early["values"]]
    a_val, m_val = e_names[0], e_names[1]
    e_map = {n: 0.30 for n in e_names}
    e_map[a_val], e_map[m_val] = 0.95, 0.74
    _set_scores(profiles, early["name"], e_map)

    l_names = [v["name"] for v in late["values"]]
    goods = l_names[:2]
    l_map = {n: 0.56 for n in l_names}
    for g in goods:
        l_map[g] = 0.90
    _set_scores(profiles, late["name"], l_map)
    for g in goods:
        deps.append({"type": "hard", "rule": "availability_explicit",
                     "subject": late["name"], "subject_value": g,
                     "allowed": {early["name"]: [m_val]}})
    return {"trap": "path", "early": {early["name"]: {"lure": a_val, "alt": m_val}},
            "late": {late["name"]: {"goods": goods}},
            "boost": [early["name"], late["name"]]}


def realistic_deps(axes, rng, planted_axes=()):
    """현실 의존성 — 함정 축을 건드리지 않는 범위에서."""
    names = {a["name"] for a in axes}
    deps = []
    if {"movie", "region"} <= names and "movie" not in planted_axes:
        deps.append({"type": "hard", "rule": "availability", "subject": "movie",
                     "over": "region", "coverage": round(rng.uniform(0.6, 0.85), 2)})
    for linked in ("restaurant", "theater", "cafe"):
        if {linked, "region"} <= names and rng.random() < 0.6:
            deps.append({"type": "hard", "rule": "membership",
                         "subject": linked, "region_axis": "region"})
    if {"time", "region"} <= names and "time" not in planted_axes and rng.random() < 0.5:
        deps.append({"type": "soft", "rule": "conditional_home", "if_axis": "time",
                     "if_values": [v for v in ("21:00",) ],
                     "then_axis": "region", "penalty": 0.2})
    if {"budget", "menu"} <= names and "budget" not in planted_axes \
            and "menu" not in planted_axes and rng.random() < 0.5:
        deps.append({"type": "soft", "rule": "conditional_pref", "if_axis": "budget",
                     "if_values": ["low"], "then_axis": "menu",
                     "preferred": ["korean", "chinese"], "penalty": 0.15})
    return deps


# ---------------------------------------------------------------------------------------
# 케이스 조립 + oracle 검산
# ---------------------------------------------------------------------------------------

CONFLICTS = [("low", 0.6), ("mid", 0.0), ("high", -0.5)]


def _fixture(case_id, name, axes, deps, profiles, expected, conflict, extra_meta):
    return {
        "meta": {"id": case_id, "name": name, "conflict_level": conflict,
                 "expected": expected, **extra_meta},
        "axes": axes,
        "dependencies": deps,
        "participants": {
            "count": 2, "profile_seed": extra_meta.get("seed", 0),
            "initial_threshold": [p["initial_threshold"] for p in profiles],
            "styles": ["default", "default"],
            "constraints": extra_meta.pop("_constraints", []),
        },
        "agent_view": {"score_dropout": 0.0},   # 전 정보 — 함정은 구조·효용이 만든다
        "profiles": profiles,
    }


def _oracle_check(fix, expected, trap_info=None):
    """불변식 검산. 통과 시 (True, 요약) — 실패 시 (False, 사유)."""
    tmp = OUT / "__tmp__.json"
    tmp.write_text(json.dumps(fix, ensure_ascii=False))
    try:
        sc = load_fixture(tmp)
        rep = analyze(sc, enumeration_limit=ORACLE_LIMIT)
    finally:
        tmp.unlink(missing_ok=True)
    if rep.skipped:
        return False, "oracle 생략(공간 초과)"
    if expected == "no_agreement":
        if rep.valid_count != 0:
            return False, f"유효 후보 {rep.valid_count}개 — 결렬 정답 아님"
        return True, {"valid": 0, "u_xstar": round(rep.breakdown_total, 4)}
    if rep.valid_count < 1:
        return False, "유효 후보 없음 — 합의 판이 아님"
    thr_sum = rep.breakdown_total
    if trap_info is not None:
        margin = rep.u_xstar - thr_sum
        if margin < 0.12:
            return False, f"x* 여유 {margin:.3f} < 0.12 — 함정 변별 여지 부족"
    return True, {"valid": rep.valid_count, "u_xstar": round(rep.u_xstar, 4),
                  "r_bar": round(rep.r_bar, 4), "corr": rep.utility_corr}



def _trap_margins(fix, min_gap=0.12):
    """함정 불변식 검산 (전수 열거 — 함정 케이스는 S ≤ 30k로 통제).

    통과 조건:
    (1) x*가 함정을 회피한다 (soft_synergy: 함정 축이 미끼가 아님 / hard_path: 앞 축 ≠ 유인값)
    (2) 미끼 최상 조합이 **정착 가능** — 참여자별 효용 ≥ 자기 바닥선 + 0.03
        (아니면 함정이 "품질 손실"이 아니라 "교착 폭주"를 만든다 — 파일럿 v1의 교훈)
    (3) 미끼 최상 총효용 ≤ U(x*) − 0.12 (함정이 실제로 나쁨 — 변별 여지)
    """
    import itertools
    tmp = OUT / "__tmp__.json"
    tmp.write_text(json.dumps(fix, ensure_ascii=False))
    try:
        sc = load_fixture(tmp)
    finally:
        tmp.unlink(missing_ok=True)
    from total.adapters.composite._vendor.common.profiles import build_truth_profiles, truth_utility
    from total.adapters.composite._vendor.common.rules import (
        build_hard_rules, build_participant_hard, build_soft_rules)
    truths = build_truth_profiles(sc)
    hard = build_hard_rules(sc) + build_participant_hard(sc)
    soft = build_soft_rules(sc, [t.home_region for t in truths])
    thr = [t.initial_threshold for t in truths]
    planted = fix["meta"]["planted"]

    def decoy_hit(outcome):
        hits = []
        infos = [planted] if planted["trap"] != "both" else [planted["path"], planted["pool"]]
        for info in infos:
            if info["trap"] == "pool":
                for ax, d in info["axes"].items():
                    if outcome[ax].name in d["decoys"]:
                        hits.append(True)
            else:
                (e_ax, e_d), = info["early"].items()
                if outcome[e_ax].name == e_d["lure"]:
                    hits.append(True)
        return bool(hits)

    axis_names = sc.axis_names()
    best_clean, best_decoy = None, None
    for combo in itertools.product(*[ax.values for ax in sc.axes]):
        o = dict(zip(axis_names, combo))
        if not all(r(o) for r in hard):
            continue
        us = [truth_utility(truths[i], i, o, soft) for i in range(2)]
        if any(u < thr[i] for i, u in enumerate(us)):
            continue
        total = sum(us)
        entry = (total, min(us[i] - thr[i] for i in range(2)))
        if decoy_hit(o):
            if best_decoy is None or total > best_decoy[0]:
                best_decoy = entry
        else:
            if best_clean is None or total > best_clean[0]:
                best_clean = entry
    if best_clean is None:
        return False, "함정 회피 유효 조합 없음"
    if best_decoy is None:
        return False, "미끼 유효 조합 없음 — 함정이 정착 불가(교착 유발)"
    if best_decoy[1] < 0.10:
        return False, f"미끼 바닥선 여유 {best_decoy[1]:.3f} < 0.10 (막판 수락 → 라운드 폭주)"
    gap = best_clean[0] - best_decoy[0]
    if gap < min_gap:
        return False, f"함정 격차 {gap:.3f} < {min_gap}"
    return True, {"decoy_gap": round(gap, 4), "decoy_slack": round(best_decoy[1], 4)}


def gen_case(track, n, kind, idx, seed):
    rng = random.Random(f"{BASE_SEED}-{track}-{n}-{kind}-{idx}-{seed}")
    conflict, rho = CONFLICTS[idx % 3] if kind in ("plain", "stress") else ("mid", 0.0)
    cap = ORACLE_LIMIT if track == "cr" else 10**30
    if kind in ("hard_path", "soft_synergy", "mixed"):
        cap = min(cap, 30_000)     # 함정 마진 검산(전수)의 케이스당 비용 통제
    axes = build_axes(n, rng, cap=cap)
    thr = [round(rng.uniform(0.36, 0.48), 2) for _ in range(2)]
    expected = "agreement"
    extra = {"track": track, "type": kind, "seed": seed}
    deps, trap_info = [], None

    if kind == "no_deal":
        expected = "no_agreement"
        if idx % 2 == 0:      # (a) 서로소 캘린더 — 하드 제약으로 교집합 공백
            date_ax = next(a for a in axes if a["name"] == "date")
            names = [v["name"] for v in date_ax["values"]]
            half = max(1, len(names) // 2)
            extra["_constraints"] = [
                {"participant": 0, "axis": "date", "values": names[:half]},
                {"participant": 1, "axis": "date", "values": names[half:]},
            ]
            profiles = make_profiles(axes, rng, rho, thr)
        else:                 # (b) 높은 바닥선 + 상극 선호
            thr = [round(rng.uniform(0.66, 0.74), 2) for _ in range(2)]
            profiles = make_profiles(axes, rng, -0.6, thr)
        deps = realistic_deps(axes, rng)
    elif kind == "soft_synergy":
        profiles = make_profiles(axes, rng, rho, thr)
        trap_info = plant_pool_trap(axes, profiles, deps, rng)
        profiles = _reboost(axes, profiles, rng, trap_info["boost"])
        deps += realistic_deps(axes, rng, planted_axes=set(trap_info["boost"]))
    elif kind == "hard_path":
        profiles = make_profiles(axes, rng, rho, thr)
        trap_info = plant_path_trap(axes, profiles, deps, rng)
        profiles = _reboost(axes, profiles, rng, trap_info["boost"])
        deps += realistic_deps(axes, rng, planted_axes=set(trap_info["boost"]))
    elif kind == "mixed":
        profiles = make_profiles(axes, rng, rho, thr)
        trap_info = plant_path_trap(axes, profiles, deps, rng)
        used = set(trap_info["boost"])
        free = [a for a in axes if a["name"] not in used | {"region"}
                and len(a["values"]) >= 3]
        if len(free) >= 2:
            pool_info = plant_pool_trap(
                [a for a in axes if a["name"] in {f["name"] for f in free}],
                profiles, deps, rng)
            trap_info = {"trap": "both", "path": trap_info, "pool": pool_info,
                         "boost": trap_info["boost"] + pool_info["boost"]}
        profiles = _reboost(axes, profiles, rng, trap_info["boost"])
        deps += realistic_deps(axes, rng, planted_axes=set(trap_info["boost"]))
    else:                     # plain / stress
        profiles = make_profiles(axes, rng, rho, thr)
        deps = realistic_deps(axes, rng)

    case_id = f"FIN-{n:02d}ax-{kind}-{idx:02d}"
    label = {"hard_path": "경로 함정", "soft_synergy": "압축 함정", "mixed": "이중 함정",
             "plain": "현실 모사", "no_deal": "결렬 정답", "stress": "규모 스트레스"}[kind]
    if trap_info:
        extra["planted"] = trap_info
    fix = _fixture(case_id, f"{label} — {n}축", axes, deps, profiles, expected,
                   conflict, extra)
    return fix


def _reboost(axes, profiles, rng, boost_axes):
    """함정 축에 가중치를 싣는다 — 함정이 총효용에서 유의미하도록 (합계 재정규화)."""
    for p in profiles:
        w = p["weights"]
        for ax in boost_axes:
            w[ax] = max(w.values()) * rng.uniform(1.15, 1.45)
        total = sum(w.values())
        p["weights"] = {k: round(v / total, 6) for k, v in w.items()}
    return profiles


# ---------------------------------------------------------------------------------------
# 메인 — 트랙 구성과 생성 루프
# ---------------------------------------------------------------------------------------

def cr_plan(per_level):
    """CR 트랙 — n 수준마다 유형 배분. per_level = (path, pool, both, plain, no_deal)."""
    path_n, pool_n, both_n, plain_n, nd_n = per_level
    plan = []
    for n in range(4, 13):
        both_here = both_n if n >= 6 else 0
        plain_here = plain_n + (both_n - both_here)
        plan += [(n, "hard_path")] * path_n + [(n, "soft_synergy")] * pool_n
        plan += [(n, "mixed")] * both_here + [(n, "plain")] * plain_here
        plan += [(n, "no_deal")] * nd_n
    # 총합 보정 — 500건 정각을 위해 n=6·8·10·12에 plain 1건씩 추가
    if path_n == 8:
        plan += [(n, "plain") for n in (6, 8, 10, 12)]
    return plan


def rs_plan(per_level):
    return [(n, "stress") for n in (12, 14, 16, 18, 20) for _ in range(per_level)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pilot", action="store_true",
                    help="수준당 축소판 (유형별 1~2건) — 반복 설계용")
    ap.add_argument("--only", default=None, help="유형 필터 (예: pool_trap)")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    per_level = (1, 1, 1, 2, 1) if args.pilot else (8, 8, 3, 20, 5)
    rs_per = 2 if args.pilot else 20
    plan = [("cr", n, kind) for n, kind in cr_plan(per_level)]
    plan += [("rs", n, kind) for n, kind in rs_plan(rs_per)]
    if args.only:
        plan = [p for p in plan if p[2] == args.only]

    made, failed = [], []
    counters = {}
    for track, n, kind in plan:
        idx = counters.setdefault((n, kind), 0)
        counters[(n, kind)] += 1
        ok = False
        for attempt in range(MAX_RETRY):
            fix = gen_case(track, n, kind, idx, seed=attempt)
            if track == "rs":         # 오라클 불가 — 스키마 로드만 검증
                tmp = OUT / "__tmp__.json"
                tmp.write_text(json.dumps(fix, ensure_ascii=False))
                try:
                    load_fixture(tmp)
                    ok, summary = True, {"light": True}
                finally:
                    tmp.unlink(missing_ok=True)
            else:
                ok, summary = _oracle_check(
                    fix, fix["meta"]["expected"],
                    trap_info=fix["meta"].get("planted"))
                if ok and fix["meta"].get("planted"):
                    # mixed는 회피 대상이 3개(유인값+미끼 2)라 격차가 구조적으로 좁다
                    ok, trap_summary = _trap_margins(
                        fix, min_gap=0.08 if kind == "mixed" else 0.12)
                    if ok:
                        summary = {**summary, **trap_summary}
                    else:
                        summary = trap_summary
            if ok:
                fix["meta"]["oracle"] = summary
                fix["meta"]["attempts"] = attempt + 1
                path = OUT / f"{fix['meta']['id']}.json"
                path.write_text(json.dumps(fix, ensure_ascii=False, indent=1))
                made.append((fix["meta"]["id"], track, n, kind,
                             math.prod(len(a["values"]) for a in fix["axes"])))
                break
        if not ok and kind in ("hard_path", "soft_synergy", "mixed"):
            for attempt in range(MAX_RETRY):
                fix = gen_case(track, n, "plain", idx + 90, seed=attempt)
                fix["meta"]["id"] = f"FIN-{n:02d}ax-{kind}-{idx:02d}"
                fix["meta"]["type"] = "plain"
                fix["meta"]["fallback_from"] = kind
                ok, summary = _oracle_check(fix, "agreement")
                if ok:
                    fix["meta"]["oracle"] = summary
                    path = OUT / f"{fix['meta']['id']}.json"
                    path.write_text(json.dumps(fix, ensure_ascii=False, indent=1))
                    made.append((fix["meta"]["id"], track, n, "plain(대체)",
                                 math.prod(len(a["values"]) for a in fix["axes"])))
                    print(f"  대체: {n}축 {kind} #{idx} → plain (불변식 미충족)")
                    break
        if not ok:
            failed.append((f"FIN-{n:02d}ax-{kind}-{idx:02d}", summary))
            print(f"  실패: {n}축 {kind} #{idx} — {summary}")

    lines = ["# composite final 데이터셋 — MANIFEST", "",
             f"생성: `scripts/generate_composite_final.py` (BASE_SEED {BASE_SEED}) · "
             f"총 {len(made)}건 (실패 {len(failed)})", "",
             "| 케이스 | 트랙 | 축 수 | 유형 | 조합 수 |", "|---|---|---|---|---|"]
    for cid, track, n, kind, S in made:
        lines.append(f"| {cid} | {track} | {n} | {kind} | {S:,} |")
    (OUT / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n생성 {len(made)}건 · 실패 {len(failed)}건 → {OUT}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
