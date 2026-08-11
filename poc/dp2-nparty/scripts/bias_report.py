"""벤치마크 표본 편향 진단 리포트 — 케이스 집합이 한쪽으로 쏠렸는지 수치로 보여준다.

사용:
    .venv/bin/python scripts/bias_report.py                       # data/benchmark/cases 전체
    .venv/bin/python scripts/bias_report.py --track functional
    .venv/bin/python scripts/bias_report.py <경로...> [--verbose]

케이스마다 두 방안(plan1/plan2)을 기본 설정으로 1회씩만 돌려 10개 지표를 집계한다.
이 도구는 **진단**용이지 판정용이 아니다 — 경고는 "표본이 이 축으로 쏠려 있으니
결론을 낼 때 감안하라"는 신호일 뿐, 데이터가 틀렸다는 뜻이 아니다.
conformance fixture처럼 경계 사례만 모은 집합은 경고가 많이 뜨는 것이 정상이다.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dp2_nparty.benchmark import (  # noqa: E402
    CASES_DIR,
    TRACKS,
    BenchmarkCase,
    BenchmarkValidationError,
    JsonBenchmarkLoader,
    load_case,
)
from dp2_nparty.domain import NO_DEAL  # noqa: E402
from dp2_nparty.measures import fc  # noqa: E402
from dp2_nparty.protocol import Plan1Vote, Plan2Cumulative  # noqa: E402

PLANS = (Plan1Vote, Plan2Cumulative)
PLAN_NAMES = [cls.plan_name for cls in PLANS]

EPS = 1e-9  # 부동소수 비교 허용오차 (JSON에서 읽은 값끼리의 동일성 판정)
W = 62  # 구분선 너비
WARN_MARK = "  ⚠ 경고"

# 경고 기준 — 표에 명시된 값 그대로
TH_DISCRIM = 0.20  # 1. 방안 판별율 이 값 미만이면 경고
TH_CEILING = 0.50  # 2. 천장 효과 이 값 초과면 경고
TH_IQR = 0.10  # 3. R̄ 사분위 범위 이 값 미만이면 경고
TH_DEPTH_BIN = 0.60  # 4. 한 깊이 구간 이 값 초과면 경고
TH_FEASIBLE_BIN = 0.70  # 5. 한 실후보 수 값 이 값 초과면 경고
TH_NO_DEAL_REF = 0.20  # 6. 결렬 정답 비율 참고 기준 (경고 아님)
TH_UNIFORM = 0.80  # 8. threshold 구성 한쪽 이 값 초과면 경고


# ---------------------------------------------------------------- 케이스 1건 실행 결과


@dataclass
class CaseRow:
    case_id: str
    scenario_type: str
    n_candidates: int
    n_parties: int
    n_feasible: int  # len(case.feasible()) — 결렬 제외 실후보 수
    optimal: Any  # x*
    baseline: float  # R̄ (결과와 무관하게 케이스 고유)
    uniform_threshold: bool  # 전원 바닥선 동일 여부
    depth: float | None  # x*에 대한 전 참여자 rank_of 평균 (x*=NO_DEAL이면 None)
    outcome: dict[str, Any] = field(default_factory=dict)
    ratio: dict[str, float] = field(default_factory=dict)
    tie: dict[str, bool] = field(default_factory=dict)


def run_case(case: BenchmarkCase) -> CaseRow:
    """케이스 1건을 두 방안으로 1회씩 실행하고 집계에 필요한 값만 뽑는다."""
    profs, cands = case.profiles, case.candidates
    # baseline(R̄)과 x*는 실행 결과와 무관하므로 한 번만 계산한다 (inspect_case.py와 같은 방식)
    ref = fc.score(NO_DEAL, cands, profs)

    depth: float | None = None
    if ref.optimal != NO_DEAL:
        depth = statistics.fmean(p.rank_of(ref.optimal) for p in profs)

    ths = [p.initial_threshold for p in profs]

    row = CaseRow(
        case_id=case.case_id,
        scenario_type=str(case.meta.get("scenario_type", "?")),
        n_candidates=len(cands),
        n_parties=len(profs),
        n_feasible=len(case.feasible()),
        optimal=ref.optimal,
        baseline=ref.baseline,
        uniform_threshold=(max(ths) - min(ths)) <= EPS if ths else True,
        depth=depth,
    )
    for cls in PLANS:
        r = cls(profs).run()
        s = fc.score(r.outcome, cands, profs)
        row.outcome[cls.plan_name] = r.outcome
        row.ratio[cls.plan_name] = s.ratio
        row.tie[cls.plan_name] = bool(r.tie_break_used)
    return row


# ---------------------------------------------------------------- 계산 도우미


def ratio_of(k: int, n: int) -> float:
    """k/n — n=0이면 0.0 (0으로 나누기 방어)."""
    return (k / n) if n else 0.0


def pct(k: int, n: int) -> str:
    return f"{k:>3d}/{n:<3d} = {100.0 * ratio_of(k, n):5.1f}%" if n else f"{k:>3d}/0   =     -"


def quartiles(xs: list[float]) -> tuple[float, float, float, float, float]:
    """min/Q1/median/Q3/max — 표본이 1건이어도 예외 없이 동작하도록 직접 처리한다."""
    if not xs:
        return (0.0, 0.0, 0.0, 0.0, 0.0)
    s = sorted(xs)
    if len(s) == 1:
        v = s[0]
        return (v, v, v, v, v)
    q1, med, q3 = statistics.quantiles(s, n=4, method="inclusive")
    return (s[0], q1, med, q3, s[-1])


def depth_bin(avg: float) -> str:
    """x* 순위 깊이 구간 — early(≤3) / middle(4-7) / late(≥8).

    평균이라 정수가 아니므로 경계는 avg≤3 / 3<avg<8 / avg≥8 로 해석한다.
    """
    if avg <= 3.0 + EPS:
        return "early"
    if avg >= 8.0 - EPS:
        return "late"
    return "middle"


def hist_line(counter: Counter, n: int, unit: str) -> str:
    if not counter:
        return "(없음)"
    return ", ".join(
        f"{k}{unit}×{c}건({100.0 * ratio_of(c, n):.1f}%)" for k, c in sorted(counter.items())
    )


# ---------------------------------------------------------------- 출력 도우미


class Report:
    """리포트 출력 + 경고 누적."""

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def rule(self, ch: str = "-") -> None:
        print(ch * W)

    def head(self, title: str) -> None:
        self.rule()
        print(f" {title}")
        self.rule()

    def line(self, text: str, warn: bool = False, note: str = "") -> None:
        print(text + (WARN_MARK if warn else ""))
        if warn:
            self.warnings.append(note or text.strip())

    def summary(self) -> None:
        self.rule("=")
        if not self.warnings:
            print(" 경고 없음 — 확인한 축에서는 뚜렷한 쏠림이 발견되지 않았다.")
        else:
            print(f" 경고 요약 (총 {len(self.warnings)}건)")
            for w in self.warnings:
                print(f"   - {w}")
        self.rule("=")


# ---------------------------------------------------------------- 케이스 수집


def resolve(arg: str) -> Path:
    """상대 경로는 현재 디렉터리 → PoC 루트 순으로 찾는다."""
    p = Path(arg)
    if p.exists():
        return p
    alt = ROOT / arg
    return alt if alt.exists() else p


def collect(raw_paths: list[str], track: str | None) -> tuple[list[BenchmarkCase], list[Path]]:
    """경로 인자를 디렉터리/파일로 나눠 읽는다. 반환: (케이스 목록, 없는 경로 목록)."""
    dirs: list[Path] = []
    files: list[Path] = []
    missing: list[Path] = []
    for a in raw_paths:
        p = resolve(a)
        if p.is_dir():
            dirs.append(p)
        elif p.is_file():
            files.append(p)
        else:
            missing.append(p)

    cases: list[BenchmarkCase] = []
    if dirs:
        cases.extend(JsonBenchmarkLoader(roots=dirs, track=track).cases())
    for f in files:
        c = load_case(f)
        if track is None or c.track == track:
            cases.append(c)

    uniq: dict[str, BenchmarkCase] = {}  # 디렉터리와 파일을 함께 준 경우의 중복 제거
    for c in cases:
        uniq.setdefault(c.case_id, c)
    return [uniq[k] for k in sorted(uniq)], missing


# ---------------------------------------------------------------- 리포트 본문


def verbose_table(rep: Report, rows: list[CaseRow]) -> None:
    rep.head("[V] 개별 케이스")
    wid = max([len(r.case_id) for r in rows] + [7])
    wsc = max([len(r.scenario_type) for r in rows] + [13])
    wo = max([len(str(r.optimal)) for r in rows] + [len(str(r.outcome[p])) for r in rows for p in PLAN_NAMES] + [7])
    print(
        f"   {'case_id':<{wid}}  {'scenario_type':<{wsc}}  실후보  {'x*':<{wo}}  "
        f"{'plan1':<{wo}}  {'plan2':<{wo}}  달성1  달성2"
    )
    for r in rows:
        print(
            f"   {r.case_id:<{wid}}  {r.scenario_type:<{wsc}}  {r.n_feasible:>6d}  "
            f"{str(r.optimal):<{wo}}  {str(r.outcome['plan1']):<{wo}}  {str(r.outcome['plan2']):<{wo}}  "
            f"{r.ratio['plan1']:.3f}  {r.ratio['plan2']:.3f}"
        )


def build(rep: Report, rows: list[CaseRow]) -> None:
    n = len(rows)

    # 1. 방안 판별율 -------------------------------------------------
    rep.head("[1] 방안 판별율 — 두 방안의 결과가 갈리는 케이스 비율")
    diff = sum(1 for r in rows if r.outcome["plan1"] != r.outcome["plan2"])
    v = ratio_of(diff, n)
    rep.line(
        f"   결과 상이 {pct(diff, n)}   (기준: {TH_DISCRIM:.0%} 미만 경고)",
        warn=v < TH_DISCRIM,
        note=f"[1] 방안 판별율 {v:.1%} — 두 방안을 구분하지 못하는 표본이다 (기준 {TH_DISCRIM:.0%})",
    )

    # 2. 천장 효과 ---------------------------------------------------
    rep.head("[2] 천장 효과 — 두 방안 모두 달성률 1.0인 케이스 비율")
    ceil = sum(1 for r in rows if all(r.ratio[p] >= 1.0 - EPS for p in PLAN_NAMES))
    v = ratio_of(ceil, n)
    rep.line(
        f"   양쪽 만점 {pct(ceil, n)}   (기준: {TH_CEILING:.0%} 초과 경고)",
        warn=v > TH_CEILING,
        note=f"[2] 천장 효과 {v:.1%} — 너무 쉬운 케이스가 많아 변별력이 낮다 (기준 {TH_CEILING:.0%})",
    )

    # 3. R̄ 분포 ------------------------------------------------------
    rep.head("[3] R̄(무작위 베이스라인) 분포")
    bl = [r.baseline for r in rows]
    lo, q1, med, q3, hi = quartiles(bl)
    iqr = q3 - q1
    print(f"   min {lo:.3f}   Q1 {q1:.3f}   median {med:.3f}   Q3 {q3:.3f}   max {hi:.3f}")
    rep.line(
        f"   IQR(Q3-Q1) {iqr:.3f}   (기준: {TH_IQR:.2f} 미만 경고)",
        warn=iqr < TH_IQR,
        note=f"[3] R̄ IQR {iqr:.3f} — 난이도가 좁은 구간에 몰려 있다 (기준 {TH_IQR:.2f})",
    )

    # 4. x* 순위 깊이 ------------------------------------------------
    rep.head("[4] x* 순위 깊이 — x*에 대한 전 참여자 rank_of 평균")
    depths = [r.depth for r in rows if r.depth is not None]
    excluded = n - len(depths)
    dn = len(depths)
    bins = Counter(depth_bin(d) for d in depths)
    for key, label in (("early", "early (≤3)  "), ("middle", "middle (4-7)"), ("late", "late (≥8)   ")):
        k = bins.get(key, 0)
        share = ratio_of(k, dn)
        rep.line(
            f"   {label} {pct(k, dn)}",
            warn=share > TH_DEPTH_BIN,
            note=f"[4] x* 깊이 {key} 구간 {share:.1%} 편중 (기준 {TH_DEPTH_BIN:.0%})",
        )
    if depths:
        print(
            f"   깊이 평균 {statistics.fmean(depths):.2f}  "
            f"(min {min(depths):.2f} / max {max(depths):.2f})"
        )
    print(f"   제외(x* = {NO_DEAL}): {excluded}건 / 집계 대상 {dn}건")

    # 5. 유효 후보 수 ------------------------------------------------
    rep.head("[5] 유효 후보 수 — len(case.feasible()) 값별 분포")
    feas = Counter(r.n_feasible for r in rows)
    for k in sorted(feas):
        c = feas[k]
        share = ratio_of(c, n)
        rep.line(
            f"   {k:>2d}개: {pct(c, n)}",
            warn=share > TH_FEASIBLE_BIN,
            note=f"[5] 실후보 {k}개 케이스가 {share:.1%} (기준 {TH_FEASIBLE_BIN:.0%})",
        )
    if not feas:
        print("   (없음)")

    # 6. 결렬 정답 비율 ----------------------------------------------
    rep.head("[6] 결렬 정답 비율 — x*가 NO_DEAL인 케이스 비율")
    nd = sum(1 for r in rows if r.optimal == NO_DEAL)
    print(f"   x* = {NO_DEAL}: {pct(nd, n)}   (참고 기준 {TH_NO_DEAL_REF:.0%}, 경고 없음)")

    # 7. 동률 발생률 -------------------------------------------------
    rep.head("[7] 동률 발생률 — 방안별 tie_break_used 비율")
    for p in PLAN_NAMES:
        t = sum(1 for r in rows if r.tie[p])
        print(f"   {p}: {pct(t, n)}")

    # 8. threshold 구성 ----------------------------------------------
    rep.head("[8] threshold 구성 — 참여자 바닥선이 전원 동일한가")
    uni = sum(1 for r in rows if r.uniform_threshold)
    var = n - uni
    # 한글은 표시 폭이 2칸이라 str.ljust로는 정렬되지 않는다 — 라벨에 직접 여백을 넣는다
    for label, k in (("전원 동일    ", uni), ("참여자별 상이", var)):
        share = ratio_of(k, n)
        rep.line(
            f"   {label}: {pct(k, n)}",
            warn=share > TH_UNIFORM,
            note=f"[8] threshold '{label.strip()}' 구성이 {share:.1%} (기준 {TH_UNIFORM:.0%})",
        )

    # 9. 구성 다양성 -------------------------------------------------
    rep.head("[9] 구성 다양성 — 후보 수·참여자 수 분포")
    print(f"   후보 수   : {hist_line(Counter(r.n_candidates for r in rows), n, '개')}")
    print(f"   참여자 수 : {hist_line(Counter(r.n_parties for r in rows), n, '명')}")

    # 10. 달성률 요약 -------------------------------------------------
    rep.head("[10] 달성률 요약 — 방안별 평균 달성률과 집계 별점")
    mean_bl = statistics.fmean(bl) if bl else 0.0
    for p in PLAN_NAMES:
        vals = [r.ratio[p] for r in rows]
        mean_ratio = statistics.fmean(vals) if vals else 0.0
        denom = 1.0 - mean_bl
        s = ((mean_ratio - mean_bl) / denom) if denom > EPS else 1.0  # R̄=1이면 fc.score와 같게 1.0
        stars = fc.stars_from_s(s)
        print(
            f"   {p}: 평균 달성률 {mean_ratio:.3f}   평균 R̄ {mean_bl:.3f}   "
            f"s {s:+.3f}   별점 {stars}  {'★' * stars}{'☆' * (5 - stars)}"
        )
    print("   (집계 s는 케이스별 s의 평균이 아니라 평균값끼리의 s다 — 표본 전체를 한 덩어리로 본 값)")


# ---------------------------------------------------------------- 진입점


def main() -> None:
    ap = argparse.ArgumentParser(
        description="벤치마크 표본의 편향을 진단한다 (판정 도구 아님).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("paths", nargs="*", help="케이스 디렉터리 또는 JSON 파일 (기본: data/benchmark/cases)")
    ap.add_argument("--track", choices=TRACKS, default=None, help="지정 트랙만 집계")
    ap.add_argument("--verbose", action="store_true", help="개별 케이스 표까지 출력")
    args = ap.parse_args()

    raw_paths = args.paths or [str(CASES_DIR)]
    try:
        cases, missing = collect(raw_paths, args.track)
    # 계약 위반, 또는 다른 작업자가 쓰는 중인 반쪽짜리 JSON — 트레이스백 대신 사유만 알린다
    except (BenchmarkValidationError, json.JSONDecodeError) as e:
        print("벤치마크 데이터를 읽지 못했다 — 집계를 중단한다:", file=sys.stderr)
        print(str(e), file=sys.stderr)
        raise SystemExit(1)

    rep = Report()
    shown = ", ".join(str(resolve(p)) for p in raw_paths)

    rep.rule("=")
    print(" 벤치마크 표본 편향 리포트")
    rep.rule("=")
    print(f" 대상 경로 : {shown}")
    print(f" 트랙 필터 : {args.track or '(없음)'}")
    for m in missing:
        print(f" ! 경로 없음(건너뜀) : {m}")

    if not cases:
        print(" 케이스 : 0건")
        rep.rule()
        print(" 집계할 케이스가 없다 — 경로 또는 --track 필터를 확인하라. (정상 종료)")
        return

    tracks = Counter(c.track or "(미지정)" for c in cases)
    print(f" 케이스    : {len(cases)}건   [{', '.join(f'{k} {v}건' for k, v in sorted(tracks.items()))}]")
    print(" 실행      : 케이스당 plan1/plan2 각 1회 (기본 설정 — 5바퀴, boulware, 기본 동률규칙)")
    print(" 성격      : 표본 진단용. 경고는 '쏠림 신호'이지 데이터 오류가 아니다.")

    rows = [run_case(c) for c in cases]
    build(rep, rows)
    if args.verbose:
        verbose_table(rep, rows)
    rep.summary()


if __name__ == "__main__":
    main()
