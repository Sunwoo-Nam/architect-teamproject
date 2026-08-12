#!/usr/bin/env python3
"""메모리 예산 제약 하의 FC 측정 하니스 — 후보 공간을 예산이 자르는 실험.

문제 의식
---------
현재 13개 방안 비교에서 일괄 계열(방안 20·21·22)이 모든 축에서 우세해 trade-off가
드러나지 않는다. 원인은 후보 공간이 작다는 것(12-40개)이다. 일괄형은 참여자 전원의
순위표를 한 번에 모으므로 상태가 O(참여자 수 x 후보 수)로 자란다. 점진형은 라운드마다
한 칸씩 받으므로 훨씬 적다. 후보 공간이 커지고 **메모리 예산**이 걸리면, 일괄형은
같은 예산으로 훨씬 적은 후보밖에 다루지 못한다 — 그 대가가 FC로 나타난다.

측정 논리 (4단계)
-----------------
1. **후보 1개당 메모리 계수 실측** — 방안마다 보정 크기(기본 500개) 세션을 한 번 돌려
   피크 추가 메모리(tracemalloc, `measures/ru_memory.py`)를 재고 후보 수로 나눈다.
2. **예산 B → 최대 후보 수** `S_max = floor(B / 계수)` (전체 공간으로 상한 절단).
3. **부분집합 실행** — 전체 공간에서 `S_max`개를 뽑아 그것만 후보로 준 프로파일로 협상.
   추출은 케이스마다 고정된 셔플 순열의 앞에서 자른다 → 시드 고정(재현 가능)이고
   예산이 커질수록 후보 집합이 **중첩(nested)** 되어 예산-달성률 곡선이 해석 가능해진다.
4. **채점은 전체 공간 기준** — 분모 U(x*)는 전체 공간의 유효 후보 중 total utility 최대,
   분자는 실제 도달한 결과의 total utility. 자기가 본 부분집합 안에서 채점하면
   좁게 보는 방안이 유리해지는 왜곡이 생기므로 절대 그렇게 하지 않는다.

대조군으로 "예산 무제한"(전체 공간을 다 봄) 행을 항상 포함한다.

사용
----
    .venv/bin/python scripts/budget_report.py
    .venv/bin/python scripts/budget_report.py --space 3000 --participants 10 --runs 8
    .venv/bin/python scripts/budget_report.py --budgets 128,256,1024,4096
    .venv/bin/python scripts/budget_report.py --plans plan2,plan20batch
    .venv/bin/python scripts/budget_report.py --cases data/benchmark/cases/issue-space

출력: results/budget-<KST타임스탬프>/ 에 raw.json + report.md, 그리고 터미널.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dp2_nparty.campaign import _meta  # 메타(run_id·commit·환경) 생성 재사용
from dp2_nparty.domain import NO_DEAL, Candidate, Profile
from dp2_nparty.measures import fc as fcmod
from dp2_nparty.measures.ru_memory import peak_memory_bytes
from dp2_nparty.protocol import PLAN_LABELS, PLAN_NAMES, all_plans
from dp2_nparty.ufun_provider import ControlledTableUfun

KIB = 1024

# 계열 구분 — protocol.py의 번호 체계: 점진 공개(라운드당 자기 순위 1개) = 1-10번대,
# 후보군 전체를 한 번에 올리는 일괄 공개 = 20번대.
BATCH_PLANS = ("plan20batch", "plan21tree", "plan22rotate")


def family(plan: str) -> str:
    return "일괄" if plan in BATCH_PLANS else "점진"


# ------------------------------------------------------------------ 자료형


@dataclass
class Case:
    """한 케이스 = 하나의 전체 후보 공간 + 그 위의 봉인 프로파일들.

    x*·결렬값·무작위 베이스라인은 **케이스마다 한 번만** 계산한다 (방안마다 반복 금지).
    """

    case_id: str
    candidates: list[Candidate]
    profiles: list[Profile]
    perm: list[Candidate]  # 고정 셔플 순열 — 부분집합은 이 앞에서 자른다 (중첩 보장)
    u_star_c: Candidate | str = NO_DEAL
    u_star: float = 0.0
    u_nodeal: float = 0.0
    baseline: float = 0.0
    n_feasible: int = 0

    @property
    def space(self) -> int:
        return len(self.candidates)

    @property
    def n(self) -> int:
        return len(self.profiles)


@dataclass
class Cell:
    """(예산 수준 x 방안 x 케이스) 1건의 측정값."""

    plan: str
    case_id: str
    s_max: int
    s_max_linear: int  # 계수 나눗셈만으로 얻은 값 (--refine 전)
    peak_bytes: int
    seconds: float  # 채택된 세션 1회
    seconds_all: float  # 재보정 시도 포함
    attempts: int
    ratio: float
    agreed: bool
    hit_optimal: bool
    rounds: int
    messages: int
    bytes_sent: int


@dataclass
class Level:
    """예산 수준 하나 — 무제한 대조군은 budget_kib=None."""

    label: str
    budget_kib: float | None
    cells: dict[str, list[Cell]] = field(default_factory=dict)


# ------------------------------------------------------------------ 유틸


def _kib(b: float) -> str:
    return f"{b / KIB:,.1f} KiB"


def _stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n)


def _mean(xs: Sequence[float]) -> float:
    return statistics.mean(xs) if xs else 0.0


def _median(xs: Sequence[float]) -> float:
    return statistics.median(xs) if xs else 0.0


def _rng(*parts: Any) -> random.Random:
    """문자열 시드 — 프로세스마다 달라지는 str 해시에 의존하지 않아 재현 가능하다."""
    return random.Random("|".join(str(p) for p in parts))


def _progress(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ------------------------------------------------------------------ 케이스 준비


def _finalize(case: Case) -> Case:
    """전체 공간 기준 채점 상수 — x*, U(x*), 결렬값, 무작위 베이스라인 R̄."""
    valid = fcmod.valid_candidates(case.candidates, case.profiles)  # 결렬 포함
    case.n_feasible = len(valid) - 1  # 결렬을 뺀 실후보 수
    case.u_star_c = max(valid, key=lambda c: (fcmod.total_utility(c, case.profiles), repr(c)))
    case.u_star = fcmod.total_utility(case.u_star_c, case.profiles)
    case.u_nodeal = fcmod.total_utility(NO_DEAL, case.profiles)
    if case.u_star > 0:
        case.baseline = (
            sum(fcmod.total_utility(c, case.profiles) for c in valid) / len(valid) / case.u_star
        )
    return case


def build_generated_cases(
    space: int, participants: int, runs: int, seed: int, k_feasible: int
) -> list[Case]:
    """--generated — ControlledTableUfun으로 평면 후보 공간을 만든다.

    ControlledTableUfun은 '전원 수락 가능 후보 k개'를 참여자 수와 무관하게 고정한다
    (25 §25.5 교락 통제). 후보 공간을 키워도 문제 난이도가 아니라 구조를 재게 된다.
    """
    cases: list[Case] = []
    cands = [f"c{j:05d}" for j in range(space)]
    for i in range(runs):
        rng = _rng(seed, "gen", space, participants, k_feasible, i)
        profiles = ControlledTableUfun(k_feasible=k_feasible).build_profiles(
            cands, participants, rng
        )
        case_id = f"G-s{space}-n{participants}-{i:03d}"
        perm = list(cands)
        _rng(seed, "perm", case_id).shuffle(perm)
        cases.append(_finalize(Case(case_id, list(cands), profiles, perm)))
    return cases


def build_file_cases(
    root: Path, seed: int, limit: int, want_space: int, want_n: int
) -> list[Case] | None:
    """--cases — 정적 의제 조합 케이스에서 읽는다.

    `src/dp2_nparty/issue_space.py`(IssueSpaceLoader·expand)는 다른 작업자가 만드는 중이라
    아직 없거나 바뀔 수 있다. import 실패·디렉터리 부재·로더 오류는 모두 안내 후 None을
    돌려주고, 호출 측이 정상 종료(exit 0)한다.

    한 리포트 안의 케이스는 **(참여자 수, 후보 공간 크기)가 같아야** 한다. 계수 보정을
    한 번만 하고 그 계수로 전 케이스의 S_max를 정하기 때문이다. 섞여 있으면 조합 목록을
    보여 주고 --case-space / --case-participants 로 고르게 한다.
    """
    if not root.exists():
        _progress(f"[안내] 케이스 디렉터리가 아직 없다: {root}")
        _progress("       의제 조합 케이스가 준비된 뒤 다시 실행하거나, --generated로 돌린다.")
        return None
    try:
        from dp2_nparty.issue_space import IssueSpaceLoader, expand  # type: ignore
    except Exception as e:  # ImportError 외에 모듈 내부 오류도 같은 안내로 흡수
        _progress(f"[안내] dp2_nparty.issue_space 로더를 아직 쓸 수 없다: {type(e).__name__}: {e}")
        _progress("       IssueSpaceLoader/expand 구현이 들어온 뒤 다시 실행하거나, --generated로 돌린다.")
        return None

    try:
        loader = IssueSpaceLoader(root)
        # 전개 전 원본을 먼저 본다 — 조합 수·참여자 수를 알아야 전개 비용을 치를지 정할 수 있다.
        if hasattr(loader, "issue_cases"):
            raw_cases = list(loader.issue_cases())
            sizes = [(c.case_id, c.combination_count, len(c.participants)) for c in raw_cases]
            expander = expand
        else:  # 구현이 바뀌어 issue_cases가 없으면 전개본을 그대로 받는다
            raw_cases = list(loader.cases())
            sizes = [(c.case_id, len(c.candidates), len(c.profiles)) for c in raw_cases]
            expander = lambda c: c  # noqa: E731
    except Exception as e:
        _progress(f"[안내] 케이스를 읽지 못했다: {type(e).__name__}: {e}")
        _progress(f"       {root} 가 의제 조합 케이스(issue-space) 디렉터리가 맞는지 확인한다.")
        return None

    if not raw_cases:
        _progress(f"[안내] {root} 에서 읽을 케이스가 없다.")
        return None

    picked = [
        (c, s)
        for c, s in zip(raw_cases, sizes)
        if (want_space <= 0 or s[1] == want_space) and (want_n <= 0 or s[2] == want_n)
    ]
    if not picked:
        _progress(f"[안내] 조건(--case-space {want_space} / --case-participants {want_n})에 맞는 케이스가 없다.")
        _print_groups(sizes)
        return None

    groups = {(s[2], s[1]) for _c, s in picked}
    if len(groups) > 1:
        _progress("[안내] 한 리포트에는 (참여자 수, 후보 공간 크기)가 같은 케이스만 넣는다.")
        _progress("       계수 보정을 한 번만 하고 그 계수로 전 케이스의 S_max를 정하기 때문이다.")
        _print_groups([s for _c, s in picked])
        _progress("       --case-space / --case-participants 로 하나를 고른 뒤 다시 실행한다.")
        return None

    picked = picked[: limit] if limit > 0 else picked
    n_part, space = next(iter(groups))
    _progress(f"  전개: {len(picked)}건 x 조합 {space:,}개 x {n_part}인")

    cases: list[Case] = []
    for raw, (case_id, _s, _n) in picked:
        bc = expander(raw)  # 의제 조합 -> BenchmarkCase(candidates·profiles)
        cands = list(bc.candidates)
        if len(cands) < 2 or not bc.profiles:
            _progress(f"  [건너뜀] {case_id} — 후보 {len(cands)}개")
            continue
        perm = list(cands)
        _rng(seed, "perm", case_id).shuffle(perm)
        cases.append(_finalize(Case(str(case_id), cands, list(bc.profiles), perm)))
    if not cases:
        _progress("[안내] 유효한 케이스가 하나도 없다.")
        return None
    return cases


def _print_groups(sizes: list[tuple[Any, int, int]]) -> None:
    counts: dict[tuple[int, int], int] = {}
    for _cid, space, n in sizes:
        counts[(n, space)] = counts.get((n, space), 0) + 1
    _progress("       사용 가능한 조합 (참여자 x 후보 공간 = 케이스 수):")
    for (n, space), k in sorted(counts.items()):
        _progress(f"         --case-participants {n} --case-space {space}  → {k}건")


# ------------------------------------------------------------------ 실행 원자


def _restrict(profiles: list[Profile], subset: list[Candidate]) -> list[Profile]:
    """부분집합만 후보로 갖는 프로파일 사본 — 방안에게 '보이는 공간'을 잘라 준다.

    측정 구간 밖에서 만든다: 피크 메모리는 '협상 1회의 추가 메모리'만 재야 하고,
    후보 테이블 자체는 방안의 비용이 아니라 입력이다 (campaign.py의 RU 측정과 같은 경계).
    """
    return [
        Profile(
            pid=p.pid,
            utilities={c: p.utilities[c] for c in subset},
            initial_threshold=p.initial_threshold,
        )
        for p in profiles
    ]


def _run_once(cls: Callable, profiles: list[Profile]) -> tuple[Any, int, float]:
    """세션 1회 — (SessionResult, 피크 추가 바이트, 소요 초).

    clear_caches()로 순위표 구축 비용을 방안마다 동일하게 지불시킨다 (측정 공정성).
    """
    for p in profiles:
        p.clear_caches()
    t0 = time.perf_counter()
    session, peak = peak_memory_bytes(lambda: cls(profiles, collect_log=False).run())
    return session, peak, time.perf_counter() - t0


def _score(case: Case, outcome: Candidate | str) -> float:
    """**전체 공간 기준** 달성률 — 분모가 전체 공간의 U(x*)다."""
    if case.u_star <= 0:
        return 0.0
    return fcmod.total_utility(outcome, case.profiles) / case.u_star


# ------------------------------------------------------------------ 1단계: 계수 보정


def calibrate(
    plans: list[tuple[str, Any]], case: Case, calib_size: int
) -> dict[str, dict[str, Any]]:
    """방안별 '후보 1개당 메모리 계수'를 실측한다. 이 표가 모든 결과의 근거다."""
    size = max(1, min(calib_size, case.space))
    profiles_src = _restrict(case.profiles, case.perm[:size])
    out: dict[str, dict[str, Any]] = {}
    for name, cls in plans:
        profs = [
            Profile(pid=p.pid, utilities=dict(p.utilities), initial_threshold=p.initial_threshold)
            for p in profiles_src
        ]
        session, peak, dt = _run_once(cls, profs)
        coeff = peak / size if size else 0.0
        out[name] = {
            "calib_candidates": size,
            "calib_participants": case.n,
            "peak_bytes": peak,
            "bytes_per_candidate": coeff,
            "kib_per_candidate": coeff / KIB,
            "seconds": dt,
            "agreed": bool(session.agreed),
            "degenerate": coeff <= 0.0,  # 피크 0 — 예산 제약이 의미를 갖지 못한다
        }
        _progress(
            f"  보정 {name:12s} {_kib(peak):>12s} / {size}후보"
            f" = {coeff / KIB:7.4f} KiB/후보  ({dt:.2f}s)"
        )
    return out


def s_max_for(coeff_bytes: float, budget_kib: float | None, space: int) -> tuple[int, str]:
    """예산으로 다룰 수 있는 최대 후보 수. 0 나눗셈·상한 초과·예산 부족을 모두 방어한다."""
    if budget_kib is None:
        return space, "무제한"
    if coeff_bytes <= 0:
        return space, "계수0"  # 피크가 0으로 측정된 방안 — 제약 불가, 전체를 준다
    raw = int((budget_kib * KIB) // coeff_bytes)
    if raw < 1:
        return 1, "예산부족"  # 후보 1개도 못 담는 예산 — 최소 1개로 바닥을 친다
    if raw >= space:
        return space, "전체"
    return raw, ""


# ------------------------------------------------------------------ 2-4단계: 예산별 실행


def solve_cell(
    cls: Callable, case: Case, budget_bytes: float | None, s0: int, refine: int
) -> tuple[int, Any, int, float, float, int]:
    """예산 안에서 실제로 돌 수 있는 후보 수를 정하고 세션을 돌린다.

    refine=0 이면 계수 나눗셈 결과 s0을 그대로 쓴다 (측정 논리 2단계의 정의 그대로).
    refine>0 이면 실측 피크가 예산을 넘을 때 실측 기울기로 S를 줄여 다시 잰다 —
    계수가 보정 크기에서 잰 국소 기울기라 큰 S에서 과소평가되는 것을 보정한다.
    반환: (채택 S, 세션, 피크, 채택 세션 소요, 총 소요, 시도 횟수)
    """
    s = max(1, s0)
    total_dt = 0.0
    for attempt in range(1, refine + 2):
        profs = _restrict(case.profiles, case.perm[:s])
        session, peak, dt = _run_once(cls, profs)
        total_dt += dt
        if budget_bytes is None or peak <= budget_bytes or attempt == refine + 1 or s <= 1:
            return s, session, peak, dt, total_dt, attempt
        nxt = min(int(s * budget_bytes / peak), s - 1)  # 실측 기울기로 축소, 반드시 감소
        s = max(1, nxt)
    raise AssertionError("도달 불가")  # 방어적


def run_levels(
    plans: list[tuple[str, Any]],
    cases: list[Case],
    calib: dict[str, dict[str, Any]],
    budgets: list[float],
    refine: int = 0,
) -> list[Level]:
    levels = [Level(f"{b:g} KiB", b) for b in budgets]
    levels.append(Level("무제한(대조군)", None))
    for lv in levels:
        lv.cells = {name: [] for name, _ in plans}

    total = len(levels) * len(plans) * len(cases)
    done = 0
    for lv in levels:
        for name, cls in plans:
            coeff = calib[name]["bytes_per_candidate"]
            for case in cases:
                s_lin, _flag = s_max_for(coeff, lv.budget_kib, case.space)
                budget_bytes = lv.budget_kib * KIB if lv.budget_kib is not None else None
                s_max, session, peak, dt, dt_all, tries = solve_cell(
                    cls, case, budget_bytes, s_lin, refine
                )
                lv.cells[name].append(
                    Cell(
                        plan=name,
                        case_id=case.case_id,
                        s_max=s_max,
                        s_max_linear=s_lin,
                        peak_bytes=peak,
                        seconds=dt,
                        seconds_all=dt_all,
                        attempts=tries,
                        ratio=_score(case, session.outcome),
                        agreed=bool(session.agreed),
                        hit_optimal=session.outcome == case.u_star_c,
                        rounds=session.rounds,
                        messages=session.messages,
                        bytes_sent=session.bytes,
                    )
                )
                done += 1
            _progress(
                f"  [{done:>5}/{total}] {lv.label:>14s} {name:12s}"
                f" S_max={lv.cells[name][-1].s_max}"
                f" 달성률={_mean([c.ratio for c in lv.cells[name]]):.3f}"
            )
    return levels


# ------------------------------------------------------------------ 집계


def summarize(lv: Level, plan: str, cases: list[Case]) -> dict[str, Any]:
    cells = lv.cells.get(plan, [])
    if not cells:
        return {}
    ratios = [c.ratio for c in cells]
    mean_ratio = _mean(ratios)
    base = _mean([c.baseline for c in cases])
    s = (mean_ratio - base) / (1.0 - base) if base < 1.0 else 1.0
    peak_med = _median([c.peak_bytes for c in cells])
    budget_bytes = lv.budget_kib * KIB if lv.budget_kib is not None else None
    return {
        "s_max_median": _median([c.s_max for c in cells]),
        "s_max_min": min(c.s_max for c in cells),
        "s_max_max": max(c.s_max for c in cells),
        "s_max_linear_median": _median([c.s_max_linear for c in cells]),
        "refined": any(c.s_max != c.s_max_linear for c in cells),
        "space_median": _median([c.space for c in cases]),
        "coverage": _mean([c.s_max / cs.space for c, cs in zip(cells, cases)]),
        "peak_bytes_median": peak_med,
        "peak_bytes_max": max(c.peak_bytes for c in cells),
        "within_budget": None if budget_bytes is None else bool(peak_med <= budget_bytes),
        "budget_overshoot": None if budget_bytes is None else peak_med / budget_bytes,
        "mean_ratio": mean_ratio,
        "stdev_ratio": statistics.pstdev(ratios) if len(ratios) > 1 else 0.0,
        "baseline": base,
        "s": s,
        "stars": fcmod.stars_from_s(s),
        "agreed": sum(c.agreed for c in cells),
        "nodeal": sum(not c.agreed for c in cells),
        "optimal_hit": sum(c.hit_optimal for c in cells),
        "runs": len(cells),
        "seconds_total": sum(c.seconds_all for c in cells),
        "seconds_mean": _mean([c.seconds for c in cells]),
        "median_rounds": _median([c.rounds for c in cells]),
        "median_messages": _median([c.messages for c in cells]),
    }


def find_reversals(
    levels: list[Level], plan_names: list[str], table: dict[str, dict[str, float]], eps: float
) -> list[dict[str, Any]]:
    """인접 예산 구간에서 순위가 뒤집히는 방안 쌍을 찾는다."""
    out: list[dict[str, Any]] = []
    labels = [lv.label for lv in levels]
    for i in range(len(labels) - 1):
        lo, hi = labels[i], labels[i + 1]
        for a_i, a in enumerate(plan_names):
            for b in plan_names[a_i + 1 :]:
                da = table[lo].get(a), table[hi].get(a)
                db = table[lo].get(b), table[hi].get(b)
                if None in da or None in db:
                    continue
                d_lo, d_hi = da[0] - db[0], da[1] - db[1]
                if d_lo > eps and d_hi < -eps:
                    lead_lo, lead_hi = a, b
                elif d_lo < -eps and d_hi > eps:
                    lead_lo, lead_hi = b, a
                else:
                    continue
                out.append(
                    {
                        "from_level": lo,
                        "to_level": hi,
                        "leader_low": lead_lo,
                        "leader_high": lead_hi,
                        "gap_low": abs(d_lo),
                        "gap_high": abs(d_hi),
                        "swing": abs(d_lo) + abs(d_hi),
                        "cross_family": family(a) != family(b),
                    }
                )
    out.sort(key=lambda r: (-r["swing"], r["from_level"]))
    return out


# ------------------------------------------------------------------ 리포트


def render_markdown(raw: dict) -> str:
    m, cfg = raw["meta"], raw["config"]
    plan_names: list[str] = cfg["plans"]
    L: list[str] = []
    A = L.append

    A("# 메모리 예산 제약 하의 FC 리포트 — 후보 공간을 예산이 자를 때")
    A("")
    A(
        f"- 실행: {m['timestamp']} · run_id `{m['run_id']}` · seed {m['seed']}"
        f" · commit `{m['git_commit']}`"
    )
    A(f"- 환경: python {m['python']} · negmas {m['negmas_version']}")
    A(f"- 입력: {cfg['source_desc']}")
    A(f"- 프로파일 출처: {m['provider']}")
    why = []
    if cfg["plan_selected"]:
        why.append("--plans로 선택")
    if cfg["skipped"]:
        why.append("--skip-slow로 제외")
    A(
        f"- 대상 방안: {len(plan_names)}개"
        + (f" (전체 {len(PLAN_NAMES)}개 중 {' · '.join(why)})" if why else " (전체)")
    )
    if cfg["skipped"]:
        A(
            "- **제외된 방안**: "
            + ", ".join(f"{p}({r})" for p, r in cfg["skipped"].items())
        )
    A(
        f"- 예산 수준: {', '.join(f'{b:g} KiB' for b in cfg['budgets'])} + 무제한 대조군"
        f" · 보정 크기 {cfg['calib_size']}개 후보"
    )
    A(
        "- **S_max 산정**: "
        + (
            f"계수 나눗셈 후 실측 피크가 예산을 넘으면 최대 {cfg['refine']}회 축소 재측정"
            " (`--refine`) — 예산을 실측으로 강제한다."
            if cfg["refine"]
            else "`S_max = 예산 ÷ 계수` 그대로 (`--refine 0`)."
            " 계수는 보정 크기에서 잰 국소 기울기라 큰 S에서 실측 피크가 예산을 넘을 수 있다 —"
            " 아래 '예산 준수' 열이 그 초과분을 그대로 보여준다. 예산을 실측으로 강제하려면"
            " `--refine 3`."
        )
    )
    A(
        "- **채점 기준**: 전체 후보 공간의 x\\*(전원 수락 가능 후보 중 total utility 최대,"
        " 없으면 결렬값)를 분모로 쓴다. 부분집합 내부 채점이 아니다 —"
        " 그렇게 하면 좁게 보는 방안이 유리해지는 왜곡이 생긴다."
    )
    A(
        "- **부분집합 추출**: 케이스마다 고정 셔플 순열의 앞에서 자른다."
        " 시드 고정이라 재현 가능하고, 예산이 커질수록 후보 집합이 중첩된다."
    )
    A(f"- **주의**: {m['caveat']}")
    A(
        "- 메모리는 tracemalloc 기반 ENV-A 대체 측정(`measures/ru_memory.py`)이다."
        " 실기기 RSS 정본이 아니므로 방안 간 상대 비교로만 읽는다."
    )
    A("")

    # ---------------- 0. 전체 공간
    sp = raw["space"]
    A("## 0. 전체 후보 공간 (채점 분모)")
    A("")
    A(
        f"케이스 {len(sp['cases'])}건 · 후보 공간 중앙값 {sp['space_median']:,.0f}개"
        f" · 참여자 중앙값 {sp['n_median']:,.0f}인"
    )
    A("")
    A("| 케이스 | 후보 공간 | 참여자 | 실후보(전원 수락 가능) | U(x\\*) | U(결렬) | 결렬 달성률 | R̄ |")
    A("|---|---|---|---|---|---|---|---|")
    for c in sp["cases"][:12]:
        A(
            f"| {c['case_id']} | {c['space']:,} | {c['n']} | {c['n_feasible']:,}"
            f" | {c['u_star']:.3f} | {c['u_nodeal']:.3f}"
            f" | {c['nodeal_ratio']:.3f} | {c['baseline']:.3f} |"
        )
    if len(sp["cases"]) > 12:
        A(f"| … | 이하 {len(sp['cases']) - 12}건 생략 | | | | | | |")
    A("")
    A(
        "결렬 달성률 = U(결렬)/U(x\\*) — 어떤 방안이든 이 값 아래로는 잘 내려가지 않는 바닥선이다."
        " 달성률을 읽을 때 0이 아니라 이 값을 기준선으로 본다."
    )
    A("")

    # ---------------- 1. 계수 (근거)
    A("## 1. 방안별 후보 1개당 메모리 계수 — 이하 모든 결과의 근거")
    A("")
    A(
        f"보정: 후보 {cfg['calib_size']}개 · 참여자 {cfg['calib_participants']}인 세션 1회의"
        " 피크 추가 메모리를 후보 수로 나눈 값이다."
    )
    A("")
    A("| 방안 | 계열 | 보정 후보 | 보정 피크 | **후보당 계수 (KiB)** | 최저 대비 배수 | 보정 소요 |")
    A("|---|---|---|---|---|---|---|")
    cal = raw["calibration"]
    coeffs = [cal[p]["kib_per_candidate"] for p in plan_names if cal[p]["kib_per_candidate"] > 0]
    lo = min(coeffs) if coeffs else 0.0
    for p in sorted(plan_names, key=lambda x: cal[x]["kib_per_candidate"]):
        d = cal[p]
        mult = f"{d['kib_per_candidate'] / lo:.2f}x" if lo > 0 else "-"
        note = " ⚠계수0" if d["degenerate"] else ""
        A(
            f"| {PLAN_LABELS.get(p, p)} `{p}` | {family(p)} | {d['calib_candidates']:,}"
            f" | {_kib(d['peak_bytes'])} | **{d['kib_per_candidate']:.4f}**{note}"
            f" | {mult} | {d['seconds']:.2f}s |"
        )
    A("")
    A(
        "계수가 크다 = 같은 예산으로 더 적은 후보밖에 못 본다."
        " 일괄 계열은 전원의 순위표를 한 번에 들고 있으므로 O(참여자 x 후보) 상태가 그대로 계수에 들어간다."
    )
    A("")
    A(
        "> 한계: 계수는 보정 크기에서 잰 **국소 기울기**다. 상태가 후보 수에 완전 선형이 아닌"
        " 방안은 큰 공간에서 계수가 과소평가되고, 그 방안은 예산보다 많은 메모리를 실제로 쓴다."
        " 아래 표의 '실측 피크'와 '예산 준수' 열이 그 오차를 그대로 드러내도록 해 두었고,"
        " `--refine N` 을 주면 실측으로 예산을 강제한다."
    )
    A("")

    # ---------------- 2-1. 한눈 표
    lv_labels = [lv["label"] for lv in raw["levels"]]
    A("## 2. 예산 수준 x 방안")
    A("")
    A("### 2-1. 달성률 한눈 표 (행=방안, 열=예산 · 괄호는 그 예산에서의 순위)")
    A("")
    A("| 방안 | 계열 | " + " | ".join(lv_labels) + " |")
    A("|---" * (len(lv_labels) + 2) + "|")
    ranks = raw["ranks"]
    ratio_tbl = raw["ratio_table"]
    order = sorted(plan_names, key=lambda p: -ratio_tbl[lv_labels[-1]].get(p, 0.0))
    for p in order:
        row = [f"| {PLAN_LABELS.get(p, p)} `{p}` | {family(p)}"]
        for lab in lv_labels:
            v = ratio_tbl[lab].get(p)
            r = ranks[lab].get(p)
            mark = "**" if r == 1 else ""
            row.append(f" | {mark}{v:.3f}{mark} ({r}위)" if v is not None else " | - ")
        A("".join(row) + " |")
    A("")

    # ---------------- 2-2..: 예산별 상세
    for i, lv in enumerate(raw["levels"], start=2):
        A(f"### 2-{i}. 예산 {lv['label']}" + ("  — 대조군" if lv["budget_kib"] is None else ""))
        A("")
        A(
            "| 방안 | S_max | 전체 대비 | 실측 피크(중앙값) | 예산 준수 | **달성률** | s | 별점"
            " | 합의/결렬 | x\\* 도달 | 라운드(중앙) | 소요(평균) |"
        )
        A("|---" * 12 + "|")
        rows = sorted(plan_names, key=lambda p: -lv["plans"][p]["mean_ratio"])
        for p in rows:
            d = lv["plans"][p]
            smax = (
                f"{d['s_max_median']:,.0f}"
                if d["s_max_min"] == d["s_max_max"]
                else f"{d['s_max_min']:,}-{d['s_max_max']:,}"
            )
            if d["refined"]:  # 재보정으로 줄어든 경우 계수 나눗셈 원값을 함께 보인다
                smax += f" (계수값 {d['s_max_linear_median']:,.0f})"
            if d["within_budget"] is None:
                fit = "-"
            elif d["within_budget"]:
                fit = f"OK ({d['budget_overshoot'] * 100:.0f}%)"
            else:
                fit = f"**초과 x{d['budget_overshoot']:.2f}**"
            A(
                f"| `{p}` | {smax} | {d['coverage'] * 100:.1f}% | {_kib(d['peak_bytes_median'])}"
                f" | {fit} | **{d['mean_ratio']:.3f}** | {d['s']:.3f} | {_stars(d['stars'])}"
                f" | {d['agreed']}/{d['nodeal']} | {d['optimal_hit']}/{d['runs']}"
                f" | {d['median_rounds']:.0f} | {d['seconds_mean']:.2f}s |"
            )
        A("")

    # ---------------- 3. 역전
    A("## 3. 순위 역전 — 예산이 순위를 바꾸는 지점")
    A("")
    A("### 3-1. 예산별 1위")
    A("")
    A("| 예산 | 1위 방안 | 달성률 | 2위 | 달성률 | 격차 |")
    A("|---|---|---|---|---|---|")
    for lab in lv_labels:
        ordered = sorted(ratio_tbl[lab].items(), key=lambda kv: -kv[1])
        if not ordered:
            continue
        top = ordered[0]
        snd = ordered[1] if len(ordered) > 1 else (None, 0.0)
        A(
            f"| {lab} | **{top[0]}** ({family(top[0])}) | {top[1]:.3f}"
            f" | {snd[0] or '-'} | {snd[1]:.3f} | {top[1] - snd[1]:+.3f} |"
        )
    A("")

    fam = raw["family_table"]
    A("### 3-2. 계열 평균 — 점진 vs 일괄")
    A("")
    A("| 예산 | 점진 계열 평균 | 일괄 계열 평균 | 차이(점진-일괄) | 우세 |")
    A("|---|---|---|---|---|")
    for lab in lv_labels:
        f = fam[lab]
        if f["점진"] is None or f["일괄"] is None:
            A(f"| {lab} | {f['점진'] if f['점진'] is not None else '-'}"
              f" | {f['일괄'] if f['일괄'] is not None else '-'} | - | - |")
            continue
        diff = f["점진"] - f["일괄"]
        A(
            f"| {lab} | {f['점진']:.3f} | {f['일괄']:.3f} | {diff:+.3f}"
            f" | {'점진' if diff > 0 else ('일괄' if diff < 0 else '동률')} |"
        )
    A("")
    cross = raw["family_crossover"]
    if cross:
        A(
            f"**계열 교차점**: `{cross['from_level']}` → `{cross['to_level']}` 구간에서"
            f" {cross['leader_low']} 우세 → {cross['leader_high']} 우세로 뒤집힌다."
            " 이 구간이 예산 제약이 trade-off를 만들어 내는 지점이다."
        )
    else:
        A("계열 평균으로는 교차가 관측되지 않았다 (모든 예산에서 같은 계열이 앞선다).")
    A("")

    rev = raw["reversals"]
    A(f"### 3-3. 역전된 방안 쌍 — 총 {len(rev)}쌍 (계열 교차 {sum(r['cross_family'] for r in rev)}쌍)")
    A("")
    if not rev:
        A("인접 예산 구간에서 순위가 뒤집히는 쌍이 없다.")
    else:
        A("| 구간 | 낮은 예산 우세 | 높은 예산 우세 | 격차(낮음) | 격차(높음) | 계열 교차 |")
        A("|---|---|---|---|---|---|")
        for r in rev[:25]:
            A(
                f"| {r['from_level']} → {r['to_level']} | `{r['leader_low']}` ({family(r['leader_low'])})"
                f" | `{r['leader_high']}` ({family(r['leader_high'])})"
                f" | {r['gap_low']:.3f} | {r['gap_high']:.3f}"
                f" | {'O' if r['cross_family'] else '-'} |"
            )
        if len(rev) > 25:
            A(f"| … | 이하 {len(rev) - 25}쌍 생략 (raw.json 참조) | | | | |")
    A("")

    # ---------------- 4. 소요 시간
    A("## 4. 방안별 소요 시간 (전 예산 합계)")
    A("")
    A("| 방안 | 총 소요 | 무제한 1회 평균 | 세션 수 |")
    A("|---|---|---|---|")
    tt = raw["timing"]
    for p in sorted(plan_names, key=lambda x: -tt[x]["seconds_total"]):
        A(
            f"| `{p}` | {tt[p]['seconds_total']:.2f}s"
            f" | {tt[p]['unlimited_mean']:.2f}s | {tt[p]['sessions']} |"
        )
    A("")
    A(f"전체 측정 소요: {raw['elapsed_seconds']:.1f}s")
    A("")
    return "\n".join(L)


# ------------------------------------------------------------------ main


def parse_budgets(text: str) -> list[float]:
    out: list[float] = []
    for tok in text.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            v = float(tok)
        except ValueError:
            raise SystemExit(f"[오류] --budgets 값이 숫자가 아니다: {tok!r}")
        if v <= 0:
            raise SystemExit(f"[오류] --budgets 값은 양수여야 한다: {tok!r}")
        out.append(v)
    return sorted(set(out))


def main() -> None:
    ap = argparse.ArgumentParser(
        description="메모리 예산 제약 하의 FC 측정 — 예산이 후보 공간을 자를 때 방안 순위가 어떻게 바뀌는가",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--generated", action="store_true", help="평면 후보 공간을 생성해 쓴다 (기본)")
    src.add_argument("--cases", type=str, default=None, help="정적 의제 조합 케이스 디렉터리")
    ap.add_argument("--space", type=int, default=3000, help="전체 후보 공간 크기 (기본 3000)")
    ap.add_argument("--participants", type=int, default=10, help="참여자 수 (기본 10)")
    ap.add_argument("--runs", type=int, default=5, help="반복(케이스) 수 (기본 5)")
    ap.add_argument(
        "--budgets", type=str, default="256,1024,4096", help="메모리 예산 목록 (KiB, 쉼표 구분)"
    )
    ap.add_argument("--plans", type=str, default=None, help="측정할 방안 (쉼표 구분, 기본 전체)")
    ap.add_argument("--calib", type=int, default=500, help="계수 보정에 쓸 후보 수 (기본 500)")
    ap.add_argument("--k-feasible", type=int, default=3, help="전원 수락 가능 후보 수 (생성 모드)")
    ap.add_argument("--seed", type=int, default=20260812, help="난수 시드")
    ap.add_argument(
        "--skip-slow",
        type=float,
        default=0.0,
        help="보정 세션이 이 초를 넘는 방안을 제외한다 (0 = 비활성)",
    )
    ap.add_argument(
        "--refine",
        type=int,
        default=0,
        help="실측 피크가 예산을 넘으면 S_max를 줄여 다시 재는 재보정 횟수 (0 = 계수 나눗셈 그대로)",
    )
    ap.add_argument("--max-cases", type=int, default=0, help="--cases 모드에서 쓸 케이스 상한 (0=전부)")
    ap.add_argument(
        "--case-space", type=int, default=0, help="--cases 모드 — 이 조합 수를 가진 케이스만 (0=제한 없음)"
    )
    ap.add_argument(
        "--case-participants", type=int, default=0, help="--cases 모드 — 이 참여자 수인 케이스만 (0=제한 없음)"
    )
    ap.add_argument("--eps", type=float, default=0.002, help="순위 역전 판정 최소 격차")
    args = ap.parse_args()

    if args.space < 2:
        raise SystemExit("[오류] --space 는 2 이상이어야 한다.")
    if args.participants < 2:
        raise SystemExit("[오류] --participants 는 2 이상이어야 한다.")
    if args.runs < 1:
        raise SystemExit("[오류] --runs 는 1 이상이어야 한다.")
    if args.calib < 1:
        raise SystemExit("[오류] --calib 는 1 이상이어야 한다.")
    if args.refine < 0:
        raise SystemExit("[오류] --refine 는 0 이상이어야 한다.")
    budgets = parse_budgets(args.budgets)
    if not budgets:
        raise SystemExit("[오류] --budgets 가 비었다.")

    all_pairs = list(all_plans())
    known = {n for n, _ in all_pairs}
    if args.plans:
        want = [t.strip() for t in args.plans.split(",") if t.strip()]
        bad = [w for w in want if w not in known]
        if bad:
            raise SystemExit(
                f"[오류] 알 수 없는 방안: {bad}\n     사용 가능: {', '.join(sorted(known))}"
            )
        plans = [(n, c) for n, c in all_pairs if n in set(want)]
    else:
        plans = all_pairs
    if not plans:
        raise SystemExit("[오류] 측정할 방안이 없다.")

    t_start = time.perf_counter()

    # ---- 케이스 준비
    if args.cases:
        _progress(f"케이스 로딩: {args.cases}")
        cases = build_file_cases(
            Path(args.cases), args.seed, args.max_cases, args.case_space, args.case_participants
        )
        if cases is None:
            _progress("[종료] 케이스 입력을 쓸 수 없어 아무 것도 측정하지 않고 정상 종료한다.")
            sys.exit(0)
        source_desc = (
            f"정적 의제 조합 케이스 `{args.cases}` {len(cases)}건"
            f" · 전체 공간 {cases[0].space:,}개 · 참여자 {cases[0].n}인"
        )
    else:
        _progress(
            f"후보 공간 생성: {args.space}개 x {args.participants}인 x {args.runs}회"
            f" (k_feasible={args.k_feasible})"
        )
        cases = build_generated_cases(
            args.space, args.participants, args.runs, args.seed, args.k_feasible
        )
        source_desc = (
            f"생성(ControlledTableUfun) · 전체 공간 {args.space:,}개 · 참여자 {args.participants}인"
            f" · 반복 {args.runs}회 · k_feasible {args.k_feasible}"
        )

    # ---- 1단계: 계수 보정
    _progress(f"[1/2] 후보당 메모리 계수 보정 (후보 {min(args.calib, cases[0].space)}개)")
    calib = calibrate(plans, cases[0], args.calib)

    skipped: dict[str, str] = {}
    if args.skip_slow > 0:
        keep = []
        for name, cls in plans:
            if calib[name]["seconds"] > args.skip_slow:
                skipped[name] = f"보정 {calib[name]['seconds']:.2f}s > --skip-slow {args.skip_slow:g}s"
                _progress(f"  [제외] {name} — {skipped[name]}")
            else:
                keep.append((name, cls))
        plans = keep
        if not plans:
            raise SystemExit("[오류] --skip-slow 로 모든 방안이 제외됐다.")
    plan_names = [n for n, _ in plans]

    # ---- 2-4단계: 예산별 실행
    _progress(
        f"[2/2] 예산 {len(budgets)}수준 + 무제한 x 방안 {len(plans)} x 케이스 {len(cases)}"
        + (f" · 재보정 {args.refine}회" if args.refine else "")
    )
    levels = run_levels(plans, cases, calib, budgets, refine=args.refine)

    # ---- 집계
    lv_raw: list[dict[str, Any]] = []
    ratio_tbl: dict[str, dict[str, float]] = {}
    ranks: dict[str, dict[str, int]] = {}
    fam_tbl: dict[str, dict[str, float | None]] = {}
    for lv in levels:
        per_plan = {p: summarize(lv, p, cases) for p in plan_names}
        lv_raw.append({"label": lv.label, "budget_kib": lv.budget_kib, "plans": per_plan})
        ratio_tbl[lv.label] = {p: per_plan[p]["mean_ratio"] for p in plan_names}
        ordered = sorted(plan_names, key=lambda p: -ratio_tbl[lv.label][p])
        ranks[lv.label] = {p: i + 1 for i, p in enumerate(ordered)}
        fam_tbl[lv.label] = {
            f: (
                _mean([ratio_tbl[lv.label][p] for p in plan_names if family(p) == f])
                if any(family(p) == f for p in plan_names)
                else None
            )
            for f in ("점진", "일괄")
        }

    lv_labels = [lv.label for lv in levels]
    reversals = find_reversals(levels, plan_names, ratio_tbl, args.eps)

    crossover = None
    for i in range(len(lv_labels) - 1):
        a, b = fam_tbl[lv_labels[i]], fam_tbl[lv_labels[i + 1]]
        if None in (a["점진"], a["일괄"], b["점진"], b["일괄"]):
            continue
        d0, d1 = a["점진"] - a["일괄"], b["점진"] - b["일괄"]
        if d0 * d1 < 0:
            crossover = {
                "from_level": lv_labels[i],
                "to_level": lv_labels[i + 1],
                "leader_low": "점진" if d0 > 0 else "일괄",
                "leader_high": "점진" if d1 > 0 else "일괄",
            }
            break

    timing = {
        p: {
            "seconds_total": sum(c.seconds_all for lv in levels for c in lv.cells[p])
            + calib[p]["seconds"],
            "unlimited_mean": _mean([c.seconds for c in levels[-1].cells[p]]),
            "sessions": sum(c.attempts for lv in levels for c in lv.cells[p]) + 1,
        }
        for p in plan_names
    }

    meta = _meta(args.seed)
    meta["run_id"] = f"budget-{meta['run_id']}"
    if args.cases:  # _meta 기본값은 생성 프로파일 전제 — 정적 케이스에서는 출처를 바로잡는다
        meta["provider"] = f"정적 의제 조합 케이스 ({args.cases}) · issue_space.expand()"
        meta["caveat"] = (
            "케이스는 확정 벤치마크지만, 메모리는 tracemalloc 기반 ENV-A 대체 측정이다."
            " 예산 수치의 절대값이 아니라 방안 간 상대 순위로 읽는다."
        )
    raw = {
        "meta": meta,
        "config": {
            "source": "cases" if args.cases else "generated",
            "source_desc": source_desc,
            "cases_dir": args.cases,
            "space": args.space,
            "participants": args.participants,
            "runs": args.runs,
            "k_feasible": args.k_feasible,
            "budgets": budgets,
            "calib_size": min(args.calib, cases[0].space),
            "calib_participants": cases[0].n,
            "plans": plan_names,
            "plan_selected": bool(args.plans),
            "skipped": skipped,
            "eps": args.eps,
            "refine": args.refine,
            "scoring": "전체 공간 x* 기준 (부분집합 내부 채점 아님)",
            "subset_rule": "케이스별 고정 셔플 순열의 앞에서 S_max개 절단 (중첩·재현 가능)",
        },
        "space": {
            "space_median": _median([c.space for c in cases]),
            "n_median": _median([c.n for c in cases]),
            "cases": [
                {
                    "case_id": c.case_id,
                    "space": c.space,
                    "n": c.n,
                    "n_feasible": c.n_feasible,
                    "u_star": c.u_star,
                    "u_star_candidate": str(c.u_star_c),
                    "u_nodeal": c.u_nodeal,
                    "nodeal_ratio": (c.u_nodeal / c.u_star) if c.u_star else 0.0,
                    "baseline": c.baseline,
                }
                for c in cases
            ],
        },
        "calibration": calib,
        "levels": lv_raw,
        "ratio_table": ratio_tbl,
        "ranks": ranks,
        "family_table": fam_tbl,
        "family_crossover": crossover,
        "reversals": reversals,
        "timing": timing,
        "elapsed_seconds": time.perf_counter() - t_start,
        "cells": [
            {
                "level": lv.label,
                "budget_kib": lv.budget_kib,
                "plan": p,
                "case_id": c.case_id,
                "s_max": c.s_max,
                "s_max_linear": c.s_max_linear,
                "attempts": c.attempts,
                "peak_bytes": c.peak_bytes,
                "ratio": c.ratio,
                "agreed": c.agreed,
                "hit_optimal": c.hit_optimal,
                "rounds": c.rounds,
                "messages": c.messages,
                "bytes": c.bytes_sent,
                "seconds": c.seconds,
                "seconds_all": c.seconds_all,
            }
            for lv in levels
            for p in plan_names
            for c in lv.cells[p]
        ],
    }

    md = render_markdown(raw)

    base = ROOT / "results" / meta["run_id"]
    run_dir, k = base, 2
    while run_dir.exists():  # 같은 초 재실행 — 접미사로 유일성 확보 (run_full.py 방식)
        run_dir = base.with_name(f"{base.name}-{k}")
        k += 1
    meta["run_id"] = run_dir.name
    run_dir.mkdir(parents=True)
    (run_dir / "raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1))
    (run_dir / "report.md").write_text(md)

    print(md)
    print(f"\n저장: {run_dir}/\n  raw.json (셀 단위 원자료 포함) · report.md")


if __name__ == "__main__":
    main()
