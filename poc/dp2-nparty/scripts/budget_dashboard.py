#!/usr/bin/env python3
"""메모리 예산 제약 실험 (1인 기준) — 대시보드 리포트.

`scripts/budget_report.py` 와의 차이 — 무엇이 예산을 쓰는가
------------------------------------------------------------
budget_report.py 는 **프로세스 전체 메모리**(tracemalloc 피크)로 예산을 건다. 그런데
협상은 단말에서 돈다. 실제 제약은 "이 프로세스가 얼마를 썼는가"가 아니라
**"가장 많이 들고 있는 단말 1대가 얼마를 들고 있는가"** 다. 이 스크립트는 그래서
`measures/ru_person.holder_sizes(plan)` 의 **최댓값(1인 최대)** 을 예산 기준으로 쓴다.
프로세스 피크는 참고치로만 싣는다.

측정 논리 (budget_report.py 의 4단계를 1인 기준으로 옮긴 것)
------------------------------------------------------------
1. **조합 1개당 1인 메모리 계수 실측** — 방안마다 보정 크기 세션을 한 번 돌리고,
   세션이 끝난 뒤 `holder_sizes(plan)` 을 **딱 한 번** 호출해 1인 최대를 얻는다.
   계수 = 1인 최대 ÷ 보정 조합 수.
2. **예산 B → 최대 조합 수** `S_max = floor(B / 계수)` (전체 공간으로 상한 절단).
3. **부분집합 실행** — 전체 공간에서 `S_max`개를 뽑아 그것만 후보로 준 프로파일로 협상.
   추출은 케이스마다 고정된 셔플 순열의 앞에서 자른다 → 재현 가능하고, 예산이 커질수록
   후보 집합이 중첩(nested)되어 예산-달성률 곡선이 해석 가능해진다.
4. **채점은 전체 조합 공간 기준** — 분모 U(x*)는 전체 공간의 유효 후보 중 total utility
   최대(없으면 전원 initial_threshold 합), 분자는 실제 도달 결과의 total utility.
   자기가 본 부분집합 안에서 채점하면 좁게 보는 방안이 유리해지는 왜곡이 생긴다.

`holder_sizes` 호출 규칙 (실측으로 확인된 함정)
------------------------------------------------------------
`deep_size` 가 상태 전체를 재귀 순회하므로 **라운드마다 호출하면 안 된다** — 조합 6만 개
케이스에서 10분을 넘겨도 끝나지 않는다. 상태는 누적되므로 **종료 시점이 곧 최대치**다.
그래서 세션이 끝난 뒤 `plan` 객체에 대해 1회만 호출한다 (0.1~0.5초).

두 조건
------------------------------------------------------------
- **조건 1 (저난이도 · 정확도 판별용)**: `data/benchmark/cases/issue-space/` 의 정적 케이스.
  전원 수락 가능한 조합 비율이 약 0.5% 다.
- **조건 2 (고난이도 · 메모리 판별용)**: `MultiIssueTableUfun` 으로 같은 규모의 공간을
  만들되 수락 기준값을 낮춰 전원 수락 가능 조합 비율을 3~10%로 올린다. 비율은 실측해
  보고한다. 비율이 높으면 점진형이 일찍 멈춰 적게 보유할 것으로 **예상**되는데, 그
  예상이 맞는지 확인하는 것이 이 조건의 목적이다.

사용
------------------------------------------------------------
    .venv/bin/python scripts/budget_dashboard.py
    .venv/bin/python scripts/budget_dashboard.py --static-cases 3 --gen-cases 3
    .venv/bin/python scripts/budget_dashboard.py --budgets 128,512,2048,8192
    .venv/bin/python scripts/budget_dashboard.py --plans plan2,plan20batch --conditions static

출력: results/budget-dash-<KST타임스탬프>/ 에 report.html + raw.json + report.md.
"""
from __future__ import annotations

import argparse
import itertools
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
from dp2_nparty.html_report import _CSS  # 기존 대시보드와 같은 CSS를 그대로 쓴다
from dp2_nparty.issue_space import ISSUE_SPACE_DIR, IssueSpaceLoader, expand
from dp2_nparty.measures import fc as fcmod
from dp2_nparty.measures.ru_memory import peak_memory_bytes
from dp2_nparty.measures.ru_person import holder_sizes
from dp2_nparty.protocol import PLAN_LABELS, PLAN_NAMES, all_plans
from dp2_nparty.ufun_provider import MultiIssueTableUfun

KIB = 1024
MIB = 1024 * 1024

# 계열 구분 — protocol.py의 번호 체계: 점진 공개(라운드당 자기 순위 1개) = 1-10번대,
# 후보군 전체를 한 번에 올리는 일괄 공개 = 20번대.
BATCH_PLANS = ("plan20batch", "plan21tree", "plan22rotate")

STATIC = "static"
GENERATED = "generated"
COND_LABEL = {STATIC: "조건 1 — 저난이도(정적 케이스)", GENERATED: "조건 2 — 고난이도(생성)"}
COND_SHORT = {STATIC: "조건 1", GENERATED: "조건 2"}


def family(plan: str) -> str:
    return "일괄" if plan in BATCH_PLANS else "점진"


# ------------------------------------------------------------------ 자료형


@dataclass
class Case:
    """한 케이스 = 하나의 전체 조합 공간 + 그 위의 봉인 프로파일들.

    x*·결렬값·무작위 베이스라인은 케이스마다 한 번만 계산한다 (방안마다 반복 금지).
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
    threshold: float | None = None  # 조건 2에서 인위로 낮춘 균일 수락 기준값

    @property
    def space(self) -> int:
        return len(self.candidates)

    @property
    def n(self) -> int:
        return len(self.profiles)

    @property
    def feasible_ratio(self) -> float:
        return self.n_feasible / self.space if self.space else 0.0


@dataclass
class Cell:
    """(조건 x 예산 수준 x 방안 x 케이스) 1건의 측정값."""

    plan: str
    case_id: str
    s_max: int
    s_max_linear: int  # 계수 나눗셈만으로 얻은 값 (재보정 전)
    person_peak: int  # 1인 최대 (holder_sizes 최댓값) — 예산의 기준
    total_logical: int  # 전원 합계 (복제 반영)
    process_peak: int | None  # tracemalloc 프로세스 피크 (참고 · 미측정이면 None)
    seconds: float  # 채택된 세션 1회 (tracemalloc 없이 잰 값)
    seconds_all: float  # 재보정 시도 + 프로세스 피크 재측정 포함
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


def _mib(b: float) -> str:
    """MB 단위 — 1 MB 미만은 KiB로 보여 준다 (0.00 MB로 뭉개지지 않게)."""
    return f"{b / MIB:,.2f} MB" if b >= MIB else f"{b / KIB:,.1f} KiB"


def _budget_label(kib: float) -> str:
    return f"{kib / KIB:g} MB" if kib >= KIB else f"{kib:g} KiB"


def _stars_txt(n: int) -> str:
    return "★" * n + "☆" * (5 - n)


def _stars_html(n: int) -> str:
    return f'<span class="stars">{"★" * n}{"☆" * (5 - n)}</span> {n}점'


def _mean(xs: Sequence[float]) -> float:
    return statistics.mean(xs) if xs else 0.0


def _median(xs: Sequence[float]) -> float:
    return statistics.median(xs) if xs else 0.0


def _rng(*parts: Any) -> random.Random:
    """문자열 시드 — 프로세스마다 달라지는 str 해시에 의존하지 않아 재현 가능하다."""
    return random.Random("|".join(str(p) for p in parts))


def _progress(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _esc(s: Any) -> str:
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


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


def build_static_cases(root: Path, seed: int, limit: int, space: int, n_part: int) -> list[Case]:
    """조건 1 — 정적 의제 조합 케이스.

    한 조건 안의 케이스는 (조합 수, 참여자 수)가 같아야 한다: 계수 보정을 한 번만 하고
    그 계수로 전 케이스의 S_max를 정하기 때문이다.
    """
    loader = IssueSpaceLoader(root)
    raw = [
        c
        for c in loader.issue_cases()
        if (space <= 0 or c.combination_count == space)
        and (n_part <= 0 or len(c.participants) == n_part)
    ]
    if not raw:
        raise SystemExit(
            f"[오류] 조건에 맞는 정적 케이스가 없다 (--case-space {space} / --case-participants {n_part})"
        )
    raw = raw[:limit] if limit > 0 else raw
    _progress(f"  [조건1] 전개: {len(raw)}건 x 조합 {raw[0].combination_count:,}개"
              f" x {len(raw[0].participants)}인")
    cases: list[Case] = []
    for rc in raw:
        bc = expand(rc)
        cands = list(bc.candidates)
        perm = list(cands)
        _rng(seed, "perm", rc.case_id).shuffle(perm)
        cases.append(_finalize(Case(str(rc.case_id), cands, list(bc.profiles), perm)))
    return cases


def build_generated_cases(
    issue_sizes: list[int], n_part: int, runs: int, seed: int, target_ratio: float
) -> list[Case]:
    """조건 2 — MultiIssueTableUfun 으로 같은 규모의 공간을 만들고 수락 기준값을 낮춘다.

    낮추는 방법: 조합별 `min_i utility_i` 를 내림차순 정렬해 목표 비율에 해당하는 분위값을
    균일 수락 기준값으로 삼는다. 그러면 전원 수락 가능 조합 비율이 목표치에 정확히 맞는다
    (동점 때문에 목표보다 약간 커질 수 있어, 실제 비율을 세어 보고한다).
    기준값을 낮추면 결렬값 U(결렬) = Σ threshold 도 함께 낮아진다 — 채점 바닥선이 내려간다.
    """
    values = [[f"i{j}v{k}" for k in range(s)] for j, s in enumerate(issue_sizes)]
    cands = list(itertools.product(*values))
    cases: list[Case] = []
    for i in range(runs):
        case_id = f"G-{'x'.join(str(s) for s in issue_sizes)}-n{n_part}-{i:03d}"
        rng = _rng(seed, "gen", case_id)
        base = MultiIssueTableUfun(initial_threshold=0.4).build_profiles(cands, n_part, rng)
        mins = [min(p.utilities[c] for p in base) for c in cands]
        srt = sorted(mins, reverse=True)
        idx = min(len(srt) - 1, max(0, int(round(target_ratio * len(srt))) - 1))
        th = float(srt[idx])
        profs = [
            Profile(pid=p.pid, utilities=p.utilities, initial_threshold=th) for p in base
        ]
        perm = list(cands)
        _rng(seed, "perm", case_id).shuffle(perm)
        case = _finalize(Case(case_id, list(cands), profs, perm, threshold=th))
        cases.append(case)
        _progress(
            f"  [조건2] {case_id} 기준값 {th:.4f} → 전원 수락 가능 {case.n_feasible:,}개"
            f" / {case.space:,} = {case.feasible_ratio * 100:.2f}%"
        )
    return cases


# ------------------------------------------------------------------ 실행 원자


def _restrict(profiles: list[Profile], subset: list[Candidate]) -> list[Profile]:
    """부분집합만 후보로 갖는 프로파일 사본 — 방안에게 '보이는 공간'을 잘라 준다.

    측정 구간 밖에서 만든다: 후보 테이블 자체는 방안의 비용이 아니라 입력이다.
    """
    return [
        Profile(
            pid=p.pid,
            utilities={c: p.utilities[c] for c in subset},
            initial_threshold=p.initial_threshold,
        )
        for p in profiles
    ]


def _copy(profiles: list[Profile]) -> list[Profile]:
    return [
        Profile(pid=p.pid, utilities=dict(p.utilities), initial_threshold=p.initial_threshold)
        for p in profiles
    ]


def _run_once(cls: Callable, profiles: list[Profile]) -> tuple[Any, list[int], float]:
    """세션 1회 — (SessionResult, 참여자별 논리 상태 bytes, 소요 초).

    clear_caches()로 순위표 구축 비용을 방안마다 동일하게 지불시킨다 (측정 공정성).
    holder_sizes 는 **세션 종료 후 1회만** 호출한다 (모듈 docstring 참조).
    tracemalloc 은 켜지 않는다 — 시간 측정을 오염시키고 큰 공간에서 수 배 느려진다.
    """
    for p in profiles:
        p.clear_caches()
    t0 = time.perf_counter()
    plan = cls(profiles, collect_log=False)
    session = plan.run()
    dt = time.perf_counter() - t0
    sizes = holder_sizes(plan)  # 상태는 누적 — 종료 시점이 곧 최대치
    return session, sizes, dt


def _process_peak(cls: Callable, profiles: list[Profile]) -> tuple[int, float]:
    """참고치용 프로세스 피크 — tracemalloc 세션을 따로 한 번 더 돌린다.

    본 세션과 분리하는 이유: tracemalloc 은 할당마다 후킹해 실행 시간을 크게 늘린다.
    시간 표는 tracemalloc 없이 잰 값이어야 방안 간 비교가 성립한다.
    """
    for p in profiles:
        p.clear_caches()
    t0 = time.perf_counter()
    _session, peak = peak_memory_bytes(lambda: cls(profiles, collect_log=False).run())
    return peak, time.perf_counter() - t0


def _score(case: Case, outcome: Candidate | str) -> float:
    """**전체 조합 공간 기준** 달성률 — 분모가 전체 공간의 U(x*)다."""
    if case.u_star <= 0:
        return 0.0
    return fcmod.total_utility(outcome, case.profiles) / case.u_star


# ------------------------------------------------------------------ 1단계: 계수 보정


def calibrate(plans: list[tuple[str, Any]], case: Case, calib_size: int) -> dict[str, dict]:
    """방안별 '조합 1개당 1인 메모리 계수'를 실측한다. 이 표가 모든 결과의 근거다."""
    size = max(1, min(calib_size, case.space))
    src = _restrict(case.profiles, case.perm[:size])
    out: dict[str, dict] = {}
    for name, cls in plans:
        session, sizes, dt = _run_once(cls, _copy(src))
        person = max(sizes) if sizes else 0
        coeff = person / size if size else 0.0
        peak, dt2 = _process_peak(cls, _copy(src))
        out[name] = {
            "calib_candidates": size,
            "calib_participants": case.n,
            "person_peak_bytes": person,
            "total_logical_bytes": sum(sizes),
            "process_peak_bytes": peak,
            "bytes_per_candidate": coeff,
            "kib_per_candidate": coeff / KIB,
            "seconds": dt,
            "seconds_all": dt + dt2,
            "rounds": session.rounds,
            "agreed": bool(session.agreed),
            "degenerate": coeff <= 0.0,  # 1인 최대 0 — 예산 제약이 의미를 갖지 못한다
        }
        _progress(
            f"  보정 {name:12s} 1인최대 {_kib(person):>12s} / {size}조합"
            f" = {coeff / KIB:8.4f} KiB/조합  ({dt:.2f}s)"
        )
    return out


def s_max_for(coeff_bytes: float, budget_kib: float | None, space: int) -> tuple[int, str]:
    """예산으로 다룰 수 있는 최대 조합 수. 0 나눗셈·상한 초과·예산 부족을 모두 방어한다."""
    if budget_kib is None:
        return space, "무제한"
    if coeff_bytes <= 0:
        return space, "계수0"  # 1인 최대가 0으로 측정된 방안 — 제약 불가, 전체를 준다
    raw = int((budget_kib * KIB) // coeff_bytes)
    if raw < 1:
        return 1, "예산부족"
    if raw >= space:
        return space, "전체"
    return raw, ""


# ------------------------------------------------------------------ 2-4단계: 예산별 실행


def solve_cell(
    cls: Callable, case: Case, budget_bytes: float | None, s0: int, refine: int
) -> tuple[int, Any, list[int], float, float, int]:
    """예산 안에서 실제로 돌 수 있는 조합 수를 정하고 세션을 돌린다.

    계수는 보정 크기에서 잰 국소 기울기라 큰 S에서 어긋날 수 있다. refine>0 이면 실측
    1인 최대가 예산을 넘을 때 실측 기울기로 S를 줄여 다시 잰다 — 예산을 실측으로 강제한다.
    반환: (채택 S, 세션, holder_sizes, 채택 세션 소요, 총 소요, 시도 횟수)
    """
    s = max(1, s0)
    total_dt = 0.0
    for attempt in range(1, refine + 2):
        session, sizes, dt = _run_once(cls, _restrict(case.profiles, case.perm[:s]))
        total_dt += dt
        person = max(sizes) if sizes else 0
        if budget_bytes is None or person <= budget_bytes or attempt == refine + 1 or s <= 1:
            return s, session, sizes, dt, total_dt, attempt
        nxt = min(int(s * budget_bytes / person), s - 1)  # 실측 기울기로 축소, 반드시 감소
        s = max(1, nxt)
    raise AssertionError("도달 불가")  # 방어적


def run_levels(
    plans: list[tuple[str, Any]],
    cases: list[Case],
    calib: dict[str, dict],
    budgets: list[float],
    refine: int,
    proc_peak_max_s: float,
) -> list[Level]:
    levels = [Level(_budget_label(b), b) for b in budgets]
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
                s_max, session, sizes, dt, dt_all, tries = solve_cell(
                    cls, case, budget_bytes, s_lin, refine
                )
                # 프로세스 피크는 참고치 — 빠른 셀에서만 따로 잰다 (tracemalloc 비용 통제)
                proc, dt2 = (None, 0.0)
                if dt <= proc_peak_max_s:
                    proc, dt2 = _process_peak(cls, _restrict(case.profiles, case.perm[:s_max]))
                lv.cells[name].append(
                    Cell(
                        plan=name,
                        case_id=case.case_id,
                        s_max=s_max,
                        s_max_linear=s_lin,
                        person_peak=max(sizes) if sizes else 0,
                        total_logical=sum(sizes),
                        process_peak=proc,
                        seconds=dt,
                        seconds_all=dt_all + dt2,
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
            last = lv.cells[name][-1]
            _progress(
                f"  [{done:>5}/{total}] {lv.label:>14s} {name:12s}"
                f" S={last.s_max:,} 1인최대={_mib(last.person_peak)}"
                f" 달성률={_mean([c.ratio for c in lv.cells[name]]):.3f}"
                f" ({_mean([c.seconds for c in lv.cells[name]]):.1f}s)"
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
    person_med = _median([c.person_peak for c in cells])
    budget_bytes = lv.budget_kib * KIB if lv.budget_kib is not None else None
    procs = [c.process_peak for c in cells if c.process_peak is not None]
    return {
        "s_max_median": _median([c.s_max for c in cells]),
        "s_max_min": min(c.s_max for c in cells),
        "s_max_max": max(c.s_max for c in cells),
        "s_max_linear_median": _median([c.s_max_linear for c in cells]),
        "refined": any(c.s_max != c.s_max_linear for c in cells),
        "coverage": _mean([c.s_max / cs.space for c, cs in zip(cells, cases)]),
        "person_peak_median": person_med,
        "person_peak_max": max(c.person_peak for c in cells),
        "total_logical_median": _median([c.total_logical for c in cells]),
        "process_peak_median": _median(procs) if procs else None,
        "process_peak_measured": len(procs),
        "within_budget": None if budget_bytes is None else bool(person_med <= budget_bytes),
        "budget_overshoot": None if budget_bytes is None else person_med / budget_bytes,
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
    lv_labels: list[str], plan_names: list[str], table: dict[str, dict[str, float]], eps: float
) -> list[dict[str, Any]]:
    """인접 예산 구간에서 순위가 뒤집히는 방안 쌍을 찾는다."""
    out: list[dict[str, Any]] = []
    for i in range(len(lv_labels) - 1):
        lo, hi = lv_labels[i], lv_labels[i + 1]
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


def aggregate(cond: str, plan_names: list[str], cases: list[Case], levels: list[Level],
              calib: dict, eps: float, desc: str, extra: dict) -> dict[str, Any]:
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
    crossover = None
    for i in range(len(lv_labels) - 1):
        a, b = fam_tbl[lv_labels[i]], fam_tbl[lv_labels[i + 1]]
        if None in (a["점진"], a["일괄"], b["점진"], b["일괄"]):
            continue
        d0, d1 = a["점진"] - a["일괄"], b["점진"] - b["일괄"]
        if d0 * d1 < 0:
            crossover = {
                "from_level": lv_labels[i], "to_level": lv_labels[i + 1],
                "leader_low": "점진" if d0 > 0 else "일괄",
                "leader_high": "점진" if d1 > 0 else "일괄",
            }
            break
    timing = {
        p: {
            "seconds_total": sum(c.seconds_all for lv in levels for c in lv.cells[p])
            + calib[p]["seconds_all"],
            "unlimited_mean": _mean([c.seconds for c in levels[-1].cells[p]]),
            "sessions": sum(c.attempts for lv in levels for c in lv.cells[p]) + 1,
        }
        for p in plan_names
    }
    unl = levels[-1]
    return {
        "condition": cond,
        "label": COND_LABEL[cond],
        "short": COND_SHORT[cond],
        "desc": desc,
        "extra": extra,
        "space": {
            "space_median": _median([c.space for c in cases]),
            "n_median": _median([c.n for c in cases]),
            "feasible_ratio_mean": _mean([c.feasible_ratio for c in cases]),
            "cases": [
                {
                    "case_id": c.case_id, "space": c.space, "n": c.n,
                    "n_feasible": c.n_feasible, "feasible_ratio": c.feasible_ratio,
                    "threshold": c.threshold, "u_star": c.u_star,
                    "u_star_candidate": str(c.u_star_c), "u_nodeal": c.u_nodeal,
                    "nodeal_ratio": (c.u_nodeal / c.u_star) if c.u_star else 0.0,
                    "baseline": c.baseline,
                }
                for c in cases
            ],
        },
        "calibration": calib,
        "levels": lv_raw,
        "level_labels": lv_labels,
        "ratio_table": ratio_tbl,
        "ranks": ranks,
        "family_table": fam_tbl,
        "family_crossover": crossover,
        "reversals": find_reversals(lv_labels, plan_names, ratio_tbl, eps),
        "timing": timing,
        "unlimited": {
            p: {
                "person_peak_median": _median([c.person_peak for c in unl.cells[p]]),
                "total_logical_median": _median([c.total_logical for c in unl.cells[p]]),
                "process_peak_median": (
                    _median([c.process_peak for c in unl.cells[p] if c.process_peak is not None])
                    if any(c.process_peak is not None for c in unl.cells[p]) else None
                ),
                "median_rounds": _median([c.rounds for c in unl.cells[p]]),
                "median_messages": _median([c.messages for c in unl.cells[p]]),
                "agreed": sum(c.agreed for c in unl.cells[p]),
                "runs": len(unl.cells[p]),
                "mean_ratio": _mean([c.ratio for c in unl.cells[p]]),
                "seconds_mean": _mean([c.seconds for c in unl.cells[p]]),
            }
            for p in plan_names
        },
        "cells": [
            {
                "level": lv.label, "budget_kib": lv.budget_kib, "plan": p, "case_id": c.case_id,
                "s_max": c.s_max, "s_max_linear": c.s_max_linear, "attempts": c.attempts,
                "person_peak": c.person_peak, "total_logical": c.total_logical,
                "process_peak": c.process_peak, "ratio": c.ratio, "agreed": c.agreed,
                "hit_optimal": c.hit_optimal, "rounds": c.rounds, "messages": c.messages,
                "bytes": c.bytes_sent, "seconds": c.seconds, "seconds_all": c.seconds_all,
            }
            for lv in levels for p in plan_names for c in lv.cells[p]
        ],
    }


# ------------------------------------------------------------------ 사전 예상 검증


def build_hypothesis(conditions: list[dict], plan_names: list[str]) -> dict | None:
    """조건 2의 **사전 예상**을 측정값으로 판정한다.

    예상: "전원 수락 가능한 조합 비율이 높으면 점진형이 일찍 멈춰 적게 보유한다."
    판정: 예산 무제한(대조군)에서 조건 1 대비 조건 2의 1인 최대가 유의하게 줄었는가.
    결론을 맞추려 조건을 조정하지 않는다 — 틀리면 틀린 대로 싣는다.
    """
    by = {c["condition"]: c for c in conditions}
    if STATIC not in by or GENERATED not in by:
        return None
    a, b = by[STATIC], by[GENERATED]
    rows = []
    for p in plan_names:
        ua, ub = a["unlimited"][p], b["unlimited"][p]
        pa, pb = ua["person_peak_median"], ub["person_peak_median"]
        rows.append({
            "plan": p, "family": family(p),
            "cond1_person": pa, "cond2_person": pb,
            "delta_pct": ((pb - pa) / pa * 100.0) if pa > 0 else None,
            "cond1_rounds": ua["median_rounds"], "cond2_rounds": ub["median_rounds"],
            "rounds_delta_pct": ((ub["median_rounds"] - ua["median_rounds"])
                                 / ua["median_rounds"] * 100.0) if ua["median_rounds"] else None,
        })
    prog = [r for r in rows if r["family"] == "점진" and r["delta_pct"] is not None]
    batch = [r for r in rows if r["family"] == "일괄" and r["delta_pct"] is not None]
    mean_prog = _mean([r["delta_pct"] for r in prog])
    # 판정 기준(사전 고정): 점진 계열 평균이 10% 이상 감소하면 '예상대로'
    if mean_prog <= -10.0:
        verdict, holds = "예상대로 — 점진 계열의 1인 최대가 뚜렷하게 줄었다", True
    elif mean_prog >= 10.0:
        verdict, holds = "예상과 반대 — 점진 계열의 1인 최대가 오히려 늘었다", False
    else:
        verdict, holds = "예상이 빗나갔다 — 점진 계열의 1인 최대가 사실상 그대로다(±10% 이내)", False
    return {
        "statement": "조건 2 사전 예상: 전원 수락 가능한 조합 비율이 높으면 점진형이 일찍 멈춰"
                     " 담당자의 최종 보유량이 일괄형보다 적어진다.",
        "criterion": "예산 무제한 대조군에서 조건 1 대비 조건 2의 1인 최대 변화율."
                     " 점진 계열 평균이 -10% 이하면 '예상대로', +10% 이상이면 '예상과 반대',"
                     " 그 사이면 '예상이 빗나갔다'로 사전 고정한 기준으로 판정한다.",
        "rows": rows,
        "mean_progressive_delta_pct": mean_prog,
        "mean_batch_delta_pct": _mean([r["delta_pct"] for r in batch]),
        "cond1_feasible_ratio": a["space"]["feasible_ratio_mean"],
        "cond2_feasible_ratio": b["space"]["feasible_ratio_mean"],
        "verdict": verdict,
        "holds": holds,
    }


# ------------------------------------------------------------------ 리포트 — 공통 조각


def _pl(p: str) -> str:
    return PLAN_LABELS.get(p, p)


def _tbl(headers: Sequence[str], rows: Sequence[Sequence[str]], win_cols: dict[int, str] | None = None) -> str:
    """win_cols: {열 index: 'min'|'max'} — 그 열의 최고값 셀을 초록 강조 (값이 갈릴 때만)."""
    win_cols = win_cols or {}
    best: dict[int, float] = {}
    for ci, mode in win_cols.items():
        vals = []
        for r in rows:
            v = r[ci]
            if isinstance(v, tuple):
                vals.append(v[0])
        if vals and len(set(vals)) > 1:
            best[ci] = min(vals) if mode == "min" else max(vals)
    h = "".join(f"<th>{x}</th>" for x in headers)
    body = []
    for r in rows:
        tds = []
        for ci, v in enumerate(r):
            if isinstance(v, tuple):
                num, txt = v
                cls = ' class="win"' if ci in best and num == best[ci] else ""
                tds.append(f'<td{cls}><span class="num">{txt}</span></td>')
            else:
                tds.append(f"<td>{v}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    return f"<table><tr>{h}</tr>{''.join(body)}</table>"


def _card(title: str, badge: str, badge_cls: str, sub: str, inner: str) -> str:
    b = f'<span class="badge {badge_cls}">{badge}</span>' if badge else ""
    return (f'<div class="card"><h2>{title}{b}</h2><div class="sub">{sub}</div>'
            f'<div class="scroll">{inner}</div></div>')


# ------------------------------------------------------------------ 리포트 — HTML


def render_html(raw: dict) -> str:
    m, cfg = raw["meta"], raw["config"]
    plan_names: list[str] = cfg["plans"]
    conds: list[dict] = raw["conditions"]

    parts: list[str] = []

    # ---- 종합 카드
    mem_headers = ["방안", "계열"]
    for c in conds:
        mem_headers += [f"{c['short']} 1인 최대", f"{c['short']} 전원 합계",
                        f"{c['short']} 프로세스(참고)"]
    mem_rows = []
    for p in plan_names:
        row: list[Any] = [f"{_pl(p)} <code>{p}</code>", family(p)]
        for c in conds:
            u = c["unlimited"][p]
            row.append((u["person_peak_median"], _mib(u["person_peak_median"])))
            row.append((u["total_logical_median"], _mib(u["total_logical_median"])))
            pk = u["process_peak_median"]
            row.append("미측정" if pk is None else _mib(pk))
        mem_rows.append(row)
    win = {}
    for i in range(len(conds)):
        win[2 + i * 3] = "min"
        win[3 + i * 3] = "min"
    mem_rows.sort(key=lambda r: r[2][0])
    mem_tbl = _tbl(mem_headers, mem_rows, win)

    # 예산별 달성률 (조건별 하위 표)
    budget_blocks = []
    for c in conds:
        labels = c["level_labels"]
        headers = ["방안", "계열"] + labels
        rows = []
        for p in plan_names:
            r: list[Any] = [f"{_pl(p)} <code>{p}</code>", family(p)]
            for lab in labels:
                v = c["ratio_table"][lab][p]
                rk = c["ranks"][lab][p]
                r.append((v, f"{v:.3f} <span class='tie'>({rk}위)</span>"))
            rows.append(r)
        rows.sort(key=lambda r: -r[-1][0])
        budget_blocks.append(
            f"<h3>{c['label']} — 예산별 달성률 (전체 조합 공간 기준 채점)</h3>"
            + _tbl(headers, rows, {i: "max" for i in range(2, 2 + len(labels))})
        )

    parts.append(_card(
        "종합 — 1인 최대 메모리 · 전원 합계 · 예산별 달성률",
        "초록 = 그 열의 최고 등급", "core",
        "메모리는 예산 무제한(대조군) 세션의 중앙값 · 1인 최대 = holder_sizes 최댓값(세션 종료 후 1회 호출)"
        " · 달성률 분모는 전체 조합 공간의 U(x*)",
        "<h3>메모리 (예산 무제한 대조군)</h3>" + mem_tbl + "".join(budget_blocks)))

    # ---- 조건 2 사전 예상 검증
    hyp = raw.get("hypothesis")
    if hyp:
        hrows = []
        for r in hyp["rows"]:
            d = r["delta_pct"]
            rd = r["rounds_delta_pct"]
            hrows.append([f"{_pl(r['plan'])} <code>{r['plan']}</code>", r["family"],
                          _mib(r["cond1_person"]), _mib(r["cond2_person"]),
                          "-" if d is None else f"<b>{d:+.1f}%</b>",
                          f"{r['cond1_rounds']:,.0f}", f"{r['cond2_rounds']:,.0f}",
                          "-" if rd is None else f"{rd:+.1f}%"])
        cls = "caveat" if not hyp["holds"] else "sub"
        parts.append(_card(
            "조건 2 사전 예상 검증 — 맞았는가", "정직 보고", "sub",
            _esc(hyp["statement"]) + "<br>" + _esc(hyp["criterion"]),
            f'<div class="{cls}"><b>판정: {_esc(hyp["verdict"])}</b><br>'
            f'점진 계열 1인 최대 평균 변화 {hyp["mean_progressive_delta_pct"]:+.1f}%'
            f' · 일괄 계열 {hyp["mean_batch_delta_pct"]:+.1f}%'
            f' · 전원 수락 가능 조합 비율 {hyp["cond1_feasible_ratio"] * 100:.2f}%'
            f' → {hyp["cond2_feasible_ratio"] * 100:.2f}%</div>'
            + _tbl(["방안", "계열", "조건 1 1인 최대", "조건 2 1인 최대", "변화율",
                    "조건 1 라운드", "조건 2 라운드", "라운드 변화율"], hrows)))

    # ---- 조건별 상세
    for c in conds:
        sp = c["space"]
        rows = [
            [x["case_id"], f"{x['space']:,}", str(x["n"]),
             f"{x['n_feasible']:,} ({x['feasible_ratio'] * 100:.2f}%)",
             "-" if x["threshold"] is None else f"{x['threshold']:.4f}",
             f"{x['u_star']:.3f}", f"{x['u_nodeal']:.3f}", f"{x['nodeal_ratio']:.3f}",
             f"{x['baseline']:.3f}"]
            for x in sp["cases"]
        ]
        parts.append(_card(
            f"{c['label']} — 입력 공간과 채점 분모", "채점 근거", "aux",
            _esc(c["desc"]),
            _tbl(["케이스", "조합 수", "참여자", "전원 수락 가능 조합", "수락 기준값",
                  "U(x*)", "U(결렬)", "결렬 달성률", "R̄"], rows)))

        cal = c["calibration"]
        coeffs = [cal[p]["kib_per_candidate"] for p in plan_names if cal[p]["kib_per_candidate"] > 0]
        lo = min(coeffs) if coeffs else 0.0
        crows = []
        for p in sorted(plan_names, key=lambda x: cal[x]["kib_per_candidate"]):
            d = cal[p]
            mult = f"{d['kib_per_candidate'] / lo:.2f}x" if lo > 0 else "-"
            note = ' <span class="badge sub">계수0</span>' if d["degenerate"] else ""
            crows.append([f"{_pl(p)} <code>{p}</code>", family(p), f"{d['calib_candidates']:,}",
                          _kib(d["person_peak_bytes"]),
                          (d["kib_per_candidate"], f"<b>{d['kib_per_candidate']:.4f}</b>{note}"),
                          mult, f"{d['rounds']:,}", f"{d['seconds']:.2f}s"])
        parts.append(_card(
            f"{c['label']} — 조합 1개당 1인 메모리 계수", "예산 산정 근거", "aux",
            f"보정: 조합 {cfg['calib_size']}개 · 참여자 {sp['n_median']:.0f}인 세션 1회의"
            " 1인 최대(holder_sizes 최댓값)를 조합 수로 나눈 값. 계수가 크다 = 같은 예산으로 더 적은 조합만 본다.",
            _tbl(["방안", "계열", "보정 조합", "보정 1인 최대", "조합당 계수 (KiB)", "최저 대비 배수",
                  "라운드", "보정 소요"], crows, {4: "min"})))

        for lv in c["levels"]:
            hdr = ["방안", "S_max", "전체 대비", "실측 1인 최대", "예산 준수", "전원 합계",
                   "달성률", "s", "별점", "합의/결렬", "x* 도달", "라운드(중앙)", "메시지(중앙)", "소요(평균)"]
            lrows = []
            for p in sorted(plan_names, key=lambda x: -lv["plans"][x]["mean_ratio"]):
                d = lv["plans"][p]
                smax = (f"{d['s_max_median']:,.0f}" if d["s_max_min"] == d["s_max_max"]
                        else f"{d['s_max_min']:,}-{d['s_max_max']:,}")
                if d["refined"]:
                    smax += f" <span class='tie'>(계수값 {d['s_max_linear_median']:,.0f})</span>"
                if d["within_budget"] is None:
                    fit = "-"
                elif d["within_budget"]:
                    fit = f"OK ({d['budget_overshoot'] * 100:.0f}%)"
                else:
                    fit = f"<b>초과 x{d['budget_overshoot']:.2f}</b>"
                lrows.append([
                    f"{_pl(p)} <code>{p}</code>", smax, f"{d['coverage'] * 100:.1f}%",
                    (d["person_peak_median"], _mib(d["person_peak_median"])), fit,
                    _mib(d["total_logical_median"]),
                    (d["mean_ratio"], f"<b>{d['mean_ratio']:.3f}</b>"), f"{d['s']:.3f}",
                    _stars_html(d["stars"]), f"{d['agreed']}/{d['nodeal']}",
                    f"{d['optimal_hit']}/{d['runs']}", f"{d['median_rounds']:,.0f}",
                    f"{d['median_messages']:,.0f}", f"{d['seconds_mean']:.2f}s"])
            badge = "대조군" if lv["budget_kib"] is None else "예산 제약"
            parts.append(_card(
                f"{c['label']} — 예산 {lv['label']}", badge,
                "sub" if lv["budget_kib"] is None else "core",
                "달성률 분모는 전체 조합 공간의 U(x*) — 부분집합 내부 채점이 아니다.",
                _tbl(hdr, lrows, {3: "min", 6: "max"})))

    # ---- 순위 역전 카드
    rev_blocks = []
    for c in conds:
        labels = c["level_labels"]
        top_rows = []
        for lab in labels:
            ordered = sorted(c["ratio_table"][lab].items(), key=lambda kv: -kv[1])
            top, snd = ordered[0], (ordered[1] if len(ordered) > 1 else (None, 0.0))
            top_rows.append([lab, f"<b>{_pl(top[0])}</b> ({family(top[0])})", f"{top[1]:.3f}",
                             _pl(snd[0]) if snd[0] else "-", f"{snd[1]:.3f}",
                             f"{top[1] - snd[1]:+.3f}"])
        fam_rows = []
        for lab in labels:
            f = c["family_table"][lab]
            if f["점진"] is None or f["일괄"] is None:
                fam_rows.append([lab, "-", "-", "-", "-"])
                continue
            diff = f["점진"] - f["일괄"]
            fam_rows.append([lab, f"{f['점진']:.3f}", f"{f['일괄']:.3f}", f"{diff:+.3f}",
                             "점진" if diff > 0 else ("일괄" if diff < 0 else "동률")])
        cross = c["family_crossover"]
        cross_txt = (
            f"<p><b>계열 교차점</b>: <code>{cross['from_level']}</code> → "
            f"<code>{cross['to_level']}</code> 구간에서 {cross['leader_low']} 우세 → "
            f"{cross['leader_high']} 우세로 뒤집힌다. 이 구간이 예산 제약이 trade-off를 만드는 지점이다.</p>"
            if cross else "<p>계열 평균으로는 교차가 관측되지 않았다 (모든 예산에서 같은 계열이 앞선다).</p>")
        rev = c["reversals"]
        if rev:
            rrows = [[f"{r['from_level']} → {r['to_level']}",
                      f"{_pl(r['leader_low'])} ({family(r['leader_low'])})",
                      f"{_pl(r['leader_high'])} ({family(r['leader_high'])})",
                      f"{r['gap_low']:.3f}", f"{r['gap_high']:.3f}",
                      "O" if r["cross_family"] else "-"] for r in rev[:20]]
            rev_tbl = _tbl(["구간", "낮은 예산 우세", "높은 예산 우세", "격차(낮음)", "격차(높음)",
                            "계열 교차"], rrows)
            if len(rev) > 20:
                rev_tbl += f"<div class='sub'>이하 {len(rev) - 20}쌍 생략 (raw.json 참조)</div>"
        else:
            rev_tbl = "<p>인접 예산 구간에서 순위가 뒤집히는 쌍이 없다.</p>"
        rev_blocks.append(
            f"<h3>{c['label']} — 예산별 1위</h3>"
            + _tbl(["예산", "1위 방안", "달성률", "2위", "달성률", "격차"], top_rows)
            + f"<h3>{c['label']} — 계열 평균 (점진 vs 일괄)</h3>"
            + _tbl(["예산", "점진 계열 평균", "일괄 계열 평균", "차이(점진-일괄)", "우세"], fam_rows)
            + cross_txt
            + f"<h3>{c['label']} — 역전된 방안 쌍 (총 {len(rev)}쌍 · 계열 교차 "
              f"{sum(r['cross_family'] for r in rev)}쌍)</h3>" + rev_tbl)
    parts.append(_card("순위 역전 구간 — 예산이 순위를 바꾸는 지점", "핵심 결론", "core",
                       f"역전 판정 최소 격차 eps={cfg['eps']}", "".join(rev_blocks)))

    # ---- 소요 시간 카드
    t_rows = []
    for p in plan_names:
        cols = [f"{_pl(p)} <code>{p}</code>"]
        tot = 0.0
        for c in conds:
            t = c["timing"][p]
            cols += [f"{t['seconds_total']:.1f}s", f"{t['unlimited_mean']:.1f}s", f"{t['sessions']}"]
            tot += t["seconds_total"]
        cols.append((tot, f"<b>{tot:.1f}s</b>"))
        t_rows.append(cols)
    t_rows.sort(key=lambda r: -r[-1][0])
    t_hdr = ["방안"] + [x for c in conds for x in
                        (f"{c['short']} 합계", f"{c['short']} 무제한 1회", f"{c['short']} 세션")] + ["총합"]
    parts.append(_card("방안별 소요 시간", "재현·계획용", "aux",
                       f"전체 측정 소요 {raw['elapsed_seconds']:.1f}s"
                       " · 시간은 tracemalloc 없이 잰 값 (프로세스 피크 재측정은 합계에만 포함)",
                       _tbl(t_hdr, t_rows)))

    # ---- 한계·건너뛴 것
    notes = "".join(f"<li>{_esc(x)}</li>" for x in raw["notes"])
    parts.append(_card("한계 · 건너뛴 것 — 정직 보고", "필독", "sub",
                       "조용히 뺀 것은 없다. 아래가 이 실행에서 제외되거나 근사된 전부다.",
                       f"<ul style='font-size:.87rem;line-height:1.7'>{notes}</ul>"))

    caveat = _esc(m["caveat"])
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>메모리 예산 제약 대시보드 {m['run_id']}</title><style>{_CSS}
code{{background:#f1f3f4;border-radius:4px;padding:1px 5px;font-size:.85em}}
.card ul{{margin:6px 0 0 18px;padding:0}} .card p{{font-size:.87rem;line-height:1.6}}
</style></head><body><div class="wrap">
<h1>메모리 예산 제약 대시보드 — 단말 1인 기준 예산으로 자른 {len(cfg['plans'])}개 방안</h1>
<div class="meta">실행 {m['timestamp']} · run_id <b>{m['run_id']}</b> · seed {m['seed']}
 · commit {m['git_commit']} · python {m['python']} · negmas {m['negmas_version']}<br>
입력: {_esc(cfg['source_desc'])}<br>
예산 수준: {' · '.join(_budget_label(b) for b in cfg['budgets'])} + 무제한 대조군
 · 보정 크기 {cfg['calib_size']:,}조합 · 재보정 {cfg['refine']}회</div>
<div class="caveat">⚠ {caveat}</div>
<div class="caveat"><b>읽는 법 — 채점 기준</b>: 달성률의 분모는 <b>전체 조합 공간</b>의
 x*(전원 수락 가능한 조합 중 total utility 최대, 없으면 전원 initial_threshold 합)이다.
 각 방안이 자기가 본 부분집합 안에서 채점하면 좁게 보는 방안이 유리해지는 왜곡이 생기므로
 절대 그렇게 하지 않았다. 부분집합은 케이스마다 고정된 셔플 순열의 앞에서 잘라
 예산이 커질수록 중첩(nested)된다.</div>
{''.join(parts)}
<footer>1인 귀속 모델 정의: src/dp2_nparty/measures/ru_person.py · 원자료: raw.json (같은 폴더)
 · 자동 생성 문서 (scripts/budget_dashboard.py)</footer>
</div></body></html>"""


# ------------------------------------------------------------------ 리포트 — Markdown


def render_markdown(raw: dict) -> str:
    m, cfg = raw["meta"], raw["config"]
    plan_names: list[str] = cfg["plans"]
    conds: list[dict] = raw["conditions"]
    L: list[str] = []
    A = L.append

    A("# 메모리 예산 제약 리포트 (1인 기준) — 단말 예산이 조합 공간을 자를 때")
    A("")
    A(f"- 실행: {m['timestamp']} · run_id `{m['run_id']}` · seed {m['seed']} · commit `{m['git_commit']}`")
    A(f"- 환경: python {m['python']} · negmas {m['negmas_version']}")
    A(f"- 입력: {cfg['source_desc']}")
    A(f"- 대상 방안: {len(plan_names)}개 (전체 {len(PLAN_NAMES)}개 중)")
    A(f"- 예산 수준: {', '.join(_budget_label(b) for b in cfg['budgets'])} + 무제한 대조군"
      f" · 보정 크기 {cfg['calib_size']:,}조합 · 재보정 {cfg['refine']}회")
    A("- **예산 기준**: `holder_sizes(plan)`의 최댓값 = **1인 최대**. 프로세스 전체가 아니라"
      " 가장 많이 들고 있는 단말 1대가 기준이다. `holder_sizes`는 세션 종료 후 1회만 호출한다"
      " (라운드마다 호출하면 deep_size 재귀 순회로 조합 6만 케이스에서 10분을 넘긴다).")
    A("- **채점 기준**: 전체 조합 공간의 x\\*(전원 수락 가능한 조합 중 total utility 최대,"
      " 없으면 전원 initial_threshold 합)를 분모로 쓴다. 부분집합 내부 채점이 아니다.")
    A("- **부분집합 추출**: 케이스마다 고정 셔플 순열의 앞에서 자른다 (재현 가능 · 중첩).")
    A(f"- **주의**: {m['caveat']}")
    A("")

    A("## 0. 한계 · 건너뛴 것")
    A("")
    for x in raw["notes"]:
        A(f"- {x}")
    A("")

    A("## 1. 종합 — 예산 무제한(대조군)에서의 1인 최대 · 전원 합계")
    A("")
    hdr = ["방안", "계열"]
    for c in conds:
        hdr += [f"{c['short']} 1인최대", f"{c['short']} 전원합계", f"{c['short']} 프로세스(참고)"]
    A("| " + " | ".join(hdr) + " |")
    A("|" + "---|" * len(hdr))
    order = sorted(plan_names, key=lambda p: conds[0]["unlimited"][p]["person_peak_median"])
    for p in order:
        row = [f"{_pl(p)} `{p}`", family(p)]
        for c in conds:
            u = c["unlimited"][p]
            row += [_mib(u["person_peak_median"]), _mib(u["total_logical_median"]),
                    "미측정" if u["process_peak_median"] is None else _mib(u["process_peak_median"])]
        A("| " + " | ".join(row) + " |")
    A("")

    hyp = raw.get("hypothesis")
    if hyp:
        A("## 1-1. 조건 2 사전 예상 검증 — 맞았는가")
        A("")
        A(f"- 예상: {hyp['statement']}")
        A(f"- 판정 기준(사전 고정): {hyp['criterion']}")
        A(f"- **판정: {hyp['verdict']}**")
        A(f"- 점진 계열 1인 최대 평균 변화 {hyp['mean_progressive_delta_pct']:+.1f}%"
          f" · 일괄 계열 {hyp['mean_batch_delta_pct']:+.1f}%"
          f" · 전원 수락 가능 조합 비율 {hyp['cond1_feasible_ratio'] * 100:.2f}%"
          f" → {hyp['cond2_feasible_ratio'] * 100:.2f}%")
        A("")
        A("| 방안 | 계열 | 조건 1 1인 최대 | 조건 2 1인 최대 | 변화율 | 조건 1 라운드 | 조건 2 라운드 | 라운드 변화율 |")
        A("|---|---|---|---|---|---|---|---|")
        for r in hyp["rows"]:
            d = "-" if r["delta_pct"] is None else f"**{r['delta_pct']:+.1f}%**"
            rd = "-" if r["rounds_delta_pct"] is None else f"{r['rounds_delta_pct']:+.1f}%"
            A(f"| {_pl(r['plan'])} `{r['plan']}` | {r['family']} | {_mib(r['cond1_person'])}"
              f" | {_mib(r['cond2_person'])} | {d} | {r['cond1_rounds']:,.0f}"
              f" | {r['cond2_rounds']:,.0f} | {rd} |")
        A("")

    for ci, c in enumerate(conds, start=2):
        A(f"## {ci}. {c['label']}")
        A("")
        A(f"{c['desc']}")
        A("")
        sp = c["space"]
        A("### 입력 공간과 채점 분모")
        A("")
        A("| 케이스 | 조합 수 | 참여자 | 전원 수락 가능 조합 | 수락 기준값 | U(x\\*) | U(결렬) | 결렬 달성률 | R̄ |")
        A("|---|---|---|---|---|---|---|---|---|")
        for x in sp["cases"]:
            th = "-" if x["threshold"] is None else f"{x['threshold']:.4f}"
            A(f"| {x['case_id']} | {x['space']:,} | {x['n']}"
              f" | {x['n_feasible']:,} ({x['feasible_ratio'] * 100:.2f}%) | {th}"
              f" | {x['u_star']:.3f} | {x['u_nodeal']:.3f} | {x['nodeal_ratio']:.3f}"
              f" | {x['baseline']:.3f} |")
        A("")
        A("### 조합 1개당 1인 메모리 계수")
        A("")
        A("| 방안 | 계열 | 보정 조합 | 보정 1인 최대 | 조합당 계수 (KiB) | 최저 대비 | 라운드 | 소요 |")
        A("|---|---|---|---|---|---|---|---|")
        cal = c["calibration"]
        coeffs = [cal[p]["kib_per_candidate"] for p in plan_names if cal[p]["kib_per_candidate"] > 0]
        lo = min(coeffs) if coeffs else 0.0
        for p in sorted(plan_names, key=lambda x: cal[x]["kib_per_candidate"]):
            d = cal[p]
            mult = f"{d['kib_per_candidate'] / lo:.2f}x" if lo > 0 else "-"
            note = " ⚠계수0" if d["degenerate"] else ""
            A(f"| {_pl(p)} `{p}` | {family(p)} | {d['calib_candidates']:,}"
              f" | {_kib(d['person_peak_bytes'])} | **{d['kib_per_candidate']:.4f}**{note}"
              f" | {mult} | {d['rounds']:,} | {d['seconds']:.2f}s |")
        A("")
        A("### 예산별 달성률 한눈 표 (괄호는 그 예산에서의 순위)")
        A("")
        labels = c["level_labels"]
        A("| 방안 | 계열 | " + " | ".join(labels) + " |")
        A("|" + "---|" * (len(labels) + 2))
        order = sorted(plan_names, key=lambda p: -c["ratio_table"][labels[-1]][p])
        for p in order:
            row = [f"{_pl(p)} `{p}`", family(p)]
            for lab in labels:
                v, rk = c["ratio_table"][lab][p], c["ranks"][lab][p]
                mark = "**" if rk == 1 else ""
                row.append(f"{mark}{v:.3f}{mark} ({rk}위)")
            A("| " + " | ".join(row) + " |")
        A("")
        for lv in c["levels"]:
            A(f"### 예산 {lv['label']}" + ("  — 대조군" if lv["budget_kib"] is None else ""))
            A("")
            A("| 방안 | S_max | 전체 대비 | 실측 1인 최대 | 예산 준수 | 전원 합계 | **달성률** | s"
              " | 별점 | 합의/결렬 | x\\* 도달 | 라운드 | 메시지 | 소요 |")
            A("|" + "---|" * 14)
            for p in sorted(plan_names, key=lambda x: -lv["plans"][x]["mean_ratio"]):
                d = lv["plans"][p]
                smax = (f"{d['s_max_median']:,.0f}" if d["s_max_min"] == d["s_max_max"]
                        else f"{d['s_max_min']:,}-{d['s_max_max']:,}")
                if d["refined"]:
                    smax += f" (계수값 {d['s_max_linear_median']:,.0f})"
                if d["within_budget"] is None:
                    fit = "-"
                elif d["within_budget"]:
                    fit = f"OK ({d['budget_overshoot'] * 100:.0f}%)"
                else:
                    fit = f"**초과 x{d['budget_overshoot']:.2f}**"
                A(f"| `{p}` | {smax} | {d['coverage'] * 100:.1f}% | {_mib(d['person_peak_median'])}"
                  f" | {fit} | {_mib(d['total_logical_median'])} | **{d['mean_ratio']:.3f}**"
                  f" | {d['s']:.3f} | {_stars_txt(d['stars'])} | {d['agreed']}/{d['nodeal']}"
                  f" | {d['optimal_hit']}/{d['runs']} | {d['median_rounds']:,.0f}"
                  f" | {d['median_messages']:,.0f} | {d['seconds_mean']:.2f}s |")
            A("")
        A("### 순위 역전")
        A("")
        A("| 예산 | 1위 | 달성률 | 2위 | 달성률 | 격차 |")
        A("|---|---|---|---|---|---|")
        for lab in labels:
            ordered = sorted(c["ratio_table"][lab].items(), key=lambda kv: -kv[1])
            top, snd = ordered[0], (ordered[1] if len(ordered) > 1 else (None, 0.0))
            A(f"| {lab} | **{top[0]}** ({family(top[0])}) | {top[1]:.3f}"
              f" | {snd[0] or '-'} | {snd[1]:.3f} | {top[1] - snd[1]:+.3f} |")
        A("")
        A("| 예산 | 점진 계열 평균 | 일괄 계열 평균 | 차이(점진-일괄) | 우세 |")
        A("|---|---|---|---|---|")
        for lab in labels:
            f = c["family_table"][lab]
            if f["점진"] is None or f["일괄"] is None:
                A(f"| {lab} | - | - | - | - |")
                continue
            diff = f["점진"] - f["일괄"]
            A(f"| {lab} | {f['점진']:.3f} | {f['일괄']:.3f} | {diff:+.3f}"
              f" | {'점진' if diff > 0 else ('일괄' if diff < 0 else '동률')} |")
        A("")
        cross = c["family_crossover"]
        if cross:
            A(f"**계열 교차점**: `{cross['from_level']}` → `{cross['to_level']}` 구간에서"
              f" {cross['leader_low']} 우세 → {cross['leader_high']} 우세로 뒤집힌다.")
        else:
            A("계열 평균으로는 교차가 관측되지 않았다.")
        A("")
        rev = c["reversals"]
        A(f"역전된 방안 쌍 {len(rev)}쌍 (계열 교차 {sum(r['cross_family'] for r in rev)}쌍)")
        A("")
        if rev:
            A("| 구간 | 낮은 예산 우세 | 높은 예산 우세 | 격차(낮음) | 격차(높음) | 계열 교차 |")
            A("|---|---|---|---|---|---|")
            for r in rev[:20]:
                A(f"| {r['from_level']} → {r['to_level']} | `{r['leader_low']}`"
                  f" | `{r['leader_high']}` | {r['gap_low']:.3f} | {r['gap_high']:.3f}"
                  f" | {'O' if r['cross_family'] else '-'} |")
            if len(rev) > 20:
                A(f"| … | 이하 {len(rev) - 20}쌍 생략 | | | | |")
        A("")

    A("## 방안별 소요 시간")
    A("")
    hdr = ["방안"] + [x for c in conds for x in
                      (f"{c['short']} 합계", f"{c['short']} 무제한 1회", f"{c['short']} 세션")] + ["총합"]
    A("| " + " | ".join(hdr) + " |")
    A("|" + "---|" * len(hdr))
    tot_by_plan = {p: sum(c["timing"][p]["seconds_total"] for c in conds) for p in plan_names}
    for p in sorted(plan_names, key=lambda x: -tot_by_plan[x]):
        row = [f"`{p}`"]
        for c in conds:
            t = c["timing"][p]
            row += [f"{t['seconds_total']:.1f}s", f"{t['unlimited_mean']:.1f}s", str(t["sessions"])]
        row.append(f"**{tot_by_plan[p]:.1f}s**")
        A("| " + " | ".join(row) + " |")
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


def parse_sizes(text: str) -> list[int]:
    try:
        out = [int(t) for t in text.split(",") if t.strip()]
    except ValueError:
        raise SystemExit(f"[오류] --gen-issue-sizes 가 정수 목록이 아니다: {text!r}")
    if not out or any(v < 2 for v in out):
        raise SystemExit("[오류] --gen-issue-sizes 는 2 이상 정수의 목록이어야 한다.")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="메모리 예산 제약 실험 (1인 기준) — 대시보드 리포트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--conditions", default="both", choices=["both", "static", "generated"])
    ap.add_argument("--cases-dir", default=str(ISSUE_SPACE_DIR))
    ap.add_argument("--static-cases", type=int, default=2, help="조건 1 케이스 수 (0=전부)")
    ap.add_argument("--case-space", type=int, default=62208, help="조건 1 — 이 조합 수인 케이스만")
    ap.add_argument("--case-participants", type=int, default=10, help="조건 1 — 이 참여자 수인 케이스만")
    ap.add_argument("--gen-cases", type=int, default=2, help="조건 2 케이스 수")
    ap.add_argument("--gen-issue-sizes", default="4,4,4,3,3,3,3,3,2,2",
                    help="조건 2 의제별 값 개수 (곱이 조합 수)")
    ap.add_argument("--gen-participants", type=int, default=10)
    ap.add_argument("--gen-feasible-target", type=float, default=0.05,
                    help="조건 2 목표 '전원 수락 가능 조합' 비율 (0.03~0.10)")
    ap.add_argument("--budgets", default="128,512,2048,8192", help="예산 목록 (KiB, 쉼표 구분)")
    ap.add_argument("--plans", default=None, help="측정할 방안 (쉼표 구분, 기본 전체)")
    ap.add_argument("--calib", type=int, default=2000, help="계수 보정에 쓸 조합 수")
    ap.add_argument("--refine", type=int, default=2, help="예산 초과 시 S_max 축소 재측정 횟수")
    ap.add_argument("--proc-peak-max-seconds", type=float, default=10.0,
                    help="이 초 이하인 셀에서만 프로세스 피크를 따로 잰다 (참고치 · tracemalloc 비용 통제)")
    ap.add_argument("--seed", type=int, default=20260812)
    ap.add_argument("--eps", type=float, default=0.002, help="순위 역전 판정 최소 격차")
    args = ap.parse_args()

    if not (0.0 < args.gen_feasible_target < 1.0):
        raise SystemExit("[오류] --gen-feasible-target 은 0과 1 사이여야 한다.")
    if args.refine < 0:
        raise SystemExit("[오류] --refine 는 0 이상이어야 한다.")
    if args.calib < 1:
        raise SystemExit("[오류] --calib 는 1 이상이어야 한다.")
    budgets = parse_budgets(args.budgets)
    issue_sizes = parse_sizes(args.gen_issue_sizes)

    all_pairs = list(all_plans())
    known = {n for n, _ in all_pairs}
    if args.plans:
        want = [t.strip() for t in args.plans.split(",") if t.strip()]
        bad = [w for w in want if w not in known]
        if bad:
            raise SystemExit(f"[오류] 알 수 없는 방안: {bad}\n     사용 가능: {', '.join(sorted(known))}")
        plans = [(n, c) for n, c in all_pairs if n in set(want)]
    else:
        plans = all_pairs
    plan_names = [n for n, _ in plans]

    t_start = time.perf_counter()
    wanted = ([STATIC, GENERATED] if args.conditions == "both"
              else [STATIC] if args.conditions == "static" else [GENERATED])

    notes: list[str] = []
    conditions: list[dict] = []
    source_bits: list[str] = []

    for cond in wanted:
        _progress(f"=== {COND_LABEL[cond]} ===")
        if cond == STATIC:
            cases = build_static_cases(Path(args.cases_dir), args.seed, args.static_cases,
                                       args.case_space, args.case_participants)
            desc = (f"정적 의제 조합 케이스 `{args.cases_dir}` {len(cases)}건"
                    f" · 조합 {cases[0].space:,}개 · 참여자 {cases[0].n}인"
                    f" · 전원 수락 가능 조합 비율 평균 "
                    f"{_mean([c.feasible_ratio for c in cases]) * 100:.2f}%")
            extra = {"cases_dir": args.cases_dir, "case_space": args.case_space,
                     "case_participants": args.case_participants}
        else:
            cases = build_generated_cases(issue_sizes, args.gen_participants, args.gen_cases,
                                          args.seed, args.gen_feasible_target)
            desc = (f"생성(MultiIssueTableUfun) · 의제 {len(issue_sizes)}개"
                    f" {'x'.join(str(s) for s in issue_sizes)} = 조합 {cases[0].space:,}개"
                    f" · 참여자 {cases[0].n}인 · {len(cases)}건"
                    f" · 목표 비율 {args.gen_feasible_target * 100:g}% → 실측 평균 "
                    f"{_mean([c.feasible_ratio for c in cases]) * 100:.2f}%")
            extra = {"issue_sizes": issue_sizes, "participants": args.gen_participants,
                     "target_ratio": args.gen_feasible_target,
                     "thresholds": [c.threshold for c in cases],
                     "feasible_ratios": [c.feasible_ratio for c in cases]}
        source_bits.append(f"{COND_LABEL[cond]}: {desc}")

        _progress(f"[1/2] 계수 보정 (조합 {min(args.calib, cases[0].space):,}개)")
        calib = calibrate(plans, cases[0], args.calib)
        _progress(f"[2/2] 예산 {len(budgets)}수준 + 무제한 x 방안 {len(plans)} x 케이스 {len(cases)}")
        levels = run_levels(plans, cases, calib, budgets, args.refine, args.proc_peak_max_seconds)
        conditions.append(aggregate(cond, plan_names, cases, levels, calib, args.eps, desc, extra))

        # 어떤 예산에서도 잘리지 않은 방안 — 계수가 사실상 0이라 예산 제약이 걸리지 않은 경우
        budget_levels = [lv for lv in levels if lv.budget_kib is not None]
        space_of = {c.case_id: c.space for c in cases}
        unconstrained = [
            p for p in plan_names
            if budget_levels
            and all(c.s_max >= space_of[c.case_id] for lv in budget_levels for c in lv.cells[p])
        ]
        if unconstrained:
            notes.append(
                f"{COND_LABEL[cond]}: {', '.join(unconstrained)} 는 **모든 예산 수준에서 전체 공간을"
                " 그대로 봤다** — 1인 계수가 사실상 0(조합 수에 비례하지 않는 상수)이라 예산이 자르지"
                " 못했다. ru_person 귀속 모델은 라운드 간 **누적** 상태만 계상하는데, 예컨대 plan1은"
                " bb.proposed_by 에 아무것도 쌓지 않고 라운드 내 일시 상태(그 라운드의 후보 목록·"
                "투표 번들)는 이 모델이 0으로 본다. 이 방안들의 달성률은 그만큼 유리하게 읽힌 값이며,"
                " 예산 제약 비교에서 제외하고 읽어야 한다.")
        no_proc = [p for p in plan_names
                   if any(c.process_peak is None for lv in levels for c in lv.cells[p])]
        if no_proc:
            notes.append(
                f"{COND_LABEL[cond]}: {', '.join(no_proc)} 의 일부 셀에서 프로세스 피크(참고치)를"
                f" 재지 않았다 — 세션이 {args.proc_peak_max_seconds:g}초를 넘어 tracemalloc 재실행"
                " 비용이 과했다. 1인 최대·전원 합계는 전 셀에서 측정했다.")

    if STATIC in wanted:
        notes.append(
            f"조건 1은 (의제 수 x 참여자 수) 8가지 조합 중 **조합 {args.case_space:,}개 ·"
            f" 참여자 {args.case_participants}인** 하나만 대표로 썼다 (8가지 중 조합 수가 가장 작아"
            " 가장 빠른 군이다). 조합이 큰 케이스는 세션 1회에 수십 초~수 분이 걸려 8조합 전체는"
            " 시간 안에 불가능했다. 나머지 7조합은 측정하지 않았다.")
    for c in conditions:
        notes.append(
            f"{c['label']}: 케이스 {len(c['space']['cases'])}건만 썼다"
            " — 정적 케이스는 80건, 생성은 임의 개수를 만들 수 있지만, 예산 무제한 세션 1회가"
            " 방안에 따라 수십 초~10분이라 전부를 돌리면 수십 시간이 걸린다.")
    notes.append(
        "1인 최대는 `ru_person.holder_sizes(plan)` 의 최댓값이며, **세션 종료 후 1회만** 호출했다."
        " 라운드마다 호출하면 deep_size 재귀 순회 비용으로 조합 6만 케이스에서 10분을 넘긴다."
        " 상태가 누적되므로 종료 시점이 곧 최대치다.")
    notes.append(
        "프로세스 피크는 tracemalloc 기반 ENV-A 대체 측정이며 **참고치**다. 시간 표를 오염시키지"
        " 않도록 본 세션과 분리해 별도 세션에서 쟀다 (그래서 시간 합계에만 포함된다).")
    notes.append(
        "계수는 보정 크기에서 잰 국소 기울기다. 실측 1인 최대가 예산을 넘으면"
        f" 최대 {args.refine}회 축소 재측정해 예산을 강제했고, 각 표의 '예산 준수' 열이 최종 결과다.")

    meta = _meta(args.seed)
    meta["run_id"] = f"budget-dash-{meta['run_id']}"
    meta["provider"] = ("조건1: 정적 의제 조합 케이스(issue_space.expand) · "
                        "조건2: MultiIssueTableUfun(개발용 임시) + 기준값 인하")
    meta["caveat"] = (
        "메모리는 ru_person 귀속 모델의 논리 크기(deep_size)이며 실기기 RSS 정본이 아니다."
        " 조건 2의 프로파일은 무작위 생성이다. 절대값이 아니라 방안 간 상대 순위로 읽는다.")

    raw = {
        "meta": meta,
        "config": {
            "conditions": wanted,
            "source_desc": " / ".join(source_bits),
            "budgets": budgets,
            "calib_size": min(args.calib, conditions[0]["space"]["cases"][0]["space"]),
            "plans": plan_names,
            "plan_selected": bool(args.plans),
            "refine": args.refine,
            "eps": args.eps,
            "proc_peak_max_seconds": args.proc_peak_max_seconds,
            "budget_basis": "holder_sizes(plan) 최댓값 = 1인 최대 (프로세스 전체 아님)",
            "scoring": "전체 조합 공간 x* 기준 (부분집합 내부 채점 아님)",
            "subset_rule": "케이스별 고정 셔플 순열의 앞에서 S_max개 절단 (중첩·재현 가능)",
        },
        "conditions": conditions,
        "hypothesis": build_hypothesis(conditions, plan_names),
        "notes": notes,
        "elapsed_seconds": time.perf_counter() - t_start,
    }

    base = ROOT / "results" / meta["run_id"]
    run_dir, k = base, 2
    while run_dir.exists():
        run_dir = base.with_name(f"{base.name}-{k}")
        k += 1
    meta["run_id"] = run_dir.name
    run_dir.mkdir(parents=True)
    (run_dir / "raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1))
    (run_dir / "report.md").write_text(render_markdown(raw), encoding="utf-8")
    (run_dir / "report.html").write_text(render_html(raw), encoding="utf-8")
    _progress(f"\n저장: {run_dir}/\n  report.html · raw.json · report.md")
    print(f"{run_dir}")


if __name__ == "__main__":
    main()
