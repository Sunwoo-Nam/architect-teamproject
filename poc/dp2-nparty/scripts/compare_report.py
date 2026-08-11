"""방안 결과 비교 리포트 — 같은 정적 케이스에서 plan1과 plan2를 나란히 비교한다.

사용:
    .venv/bin/python scripts/compare_report.py
    .venv/bin/python scripts/compare_report.py data/benchmark/fixtures/conformance
    .venv/bin/python scripts/compare_report.py --track functional
    .venv/bin/python scripts/compare_report.py <경로...> [--verbose]

이 리포트는 두 방안의 품질(FC 달성률)과 실행 비용을 비교하는 도구다.
표본 구성 자체를 진단하는 bias_report.py와 목적이 다르다. 동일 케이스에 두 방안을
각 1회 실행하므로 모든 차이는 paired delta(plan2 - plan1)로 계산한다.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from scipy.stats import t as student_t

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

EPS = 1e-9
W = 78


@dataclass(frozen=True)
class PlanMetrics:
    outcome: Any
    ratio: float
    rounds: int
    sweeps: int
    messages: int
    phases: int
    tie_break_used: bool


@dataclass(frozen=True)
class CaseRow:
    case_id: str
    track: str
    scenario_type: str
    n_candidates: int
    n_parties: int
    optimal: Any
    baseline: float
    plan1: PlanMetrics
    plan2: PlanMetrics

    @property
    def delta_fc(self) -> float:
        return self.plan2.ratio - self.plan1.ratio

    @property
    def outcome_differs(self) -> bool:
        return self.plan1.outcome != self.plan2.outcome


def run_plan(case: BenchmarkCase, plan_cls: type[Plan1Vote] | type[Plan2Cumulative]) -> PlanMetrics:
    result = plan_cls(case.profiles, collect_log=False).run()
    score = fc.score(result.outcome, case.candidates, case.profiles)
    return PlanMetrics(
        outcome=result.outcome,
        ratio=score.ratio,
        rounds=result.rounds,
        sweeps=result.sweeps,
        messages=result.messages,
        phases=result.phases,
        tie_break_used=bool(result.tie_break_used),
    )


def run_case(case: BenchmarkCase) -> CaseRow:
    reference = fc.score(NO_DEAL, case.candidates, case.profiles)
    return CaseRow(
        case_id=case.case_id,
        track=case.track or "(미지정)",
        scenario_type=str(case.meta.get("scenario_type", "(미지정)")),
        n_candidates=len(case.candidates),
        n_parties=len(case.profiles),
        optimal=reference.optimal,
        baseline=reference.baseline,
        plan1=run_plan(case, Plan1Vote),
        plan2=run_plan(case, Plan2Cumulative),
    )


# ---------------------------------------------------------------- 케이스 수집


def resolve(arg: str) -> Path:
    """상대 경로는 현재 디렉터리, 그다음 PoC 루트 기준으로 찾는다."""
    path = Path(arg)
    if path.exists():
        return path
    alternative = ROOT / arg
    return alternative if alternative.exists() else path


def collect(raw_paths: list[str], track: str | None) -> tuple[list[BenchmarkCase], list[Path]]:
    dirs: list[Path] = []
    files: list[Path] = []
    missing: list[Path] = []
    for raw in raw_paths:
        path = resolve(raw)
        if path.is_dir():
            dirs.append(path)
        elif path.is_file():
            files.append(path)
        else:
            missing.append(path)

    cases: list[BenchmarkCase] = []
    if dirs:
        cases.extend(JsonBenchmarkLoader(roots=dirs, track=track).cases())
    for path in files:
        case = load_case(path)
        if track is None or case.track == track:
            cases.append(case)

    unique: dict[str, BenchmarkCase] = {}
    for case in cases:
        unique.setdefault(case.case_id, case)
    return [unique[case_id] for case_id in sorted(unique)], missing


# ---------------------------------------------------------------- 계산 도우미


def mean(values: Iterable[float | int]) -> float:
    xs = list(values)
    return statistics.fmean(xs) if xs else 0.0


def median(values: Iterable[float | int]) -> float:
    xs = list(values)
    return statistics.median(xs) if xs else 0.0


def paired_ci95(deltas: list[float]) -> tuple[float, float] | None:
    """paired delta 평균의 양측 95% t 신뢰구간. 2건 미만이면 계산하지 않는다."""
    if len(deltas) < 2:
        return None
    center = statistics.fmean(deltas)
    spread = statistics.stdev(deltas)
    if spread <= EPS:
        return center, center
    critical = float(student_t.ppf(0.975, df=len(deltas) - 1))
    margin = critical * spread / math.sqrt(len(deltas))
    return center - margin, center + margin


def quality_counts(rows: list[CaseRow]) -> tuple[int, int, int]:
    """FC 기준 plan1 우위 / plan2 우위 / 동률."""
    p1 = sum(row.delta_fc < -EPS for row in rows)
    p2 = sum(row.delta_fc > EPS for row in rows)
    return p1, p2, len(rows) - p1 - p2


def lower_cost_counts(rows: list[CaseRow], attr: str) -> tuple[int, int, int]:
    """비용 기준 plan1이 적음 / plan2가 적음 / 동률."""
    p1 = sum(getattr(row.plan1, attr) < getattr(row.plan2, attr) for row in rows)
    p2 = sum(getattr(row.plan2, attr) < getattr(row.plan1, attr) for row in rows)
    return p1, p2, len(rows) - p1 - p2


def aggregate_score(rows: list[CaseRow], plan: str) -> tuple[float, float, int]:
    """bias_report와 같은 방식의 표본 전체 평균 달성률, 개선 비율 s, 별점."""
    mean_ratio = mean(getattr(row, plan).ratio for row in rows)
    mean_baseline = mean(row.baseline for row in rows)
    denominator = 1.0 - mean_baseline
    s = (mean_ratio - mean_baseline) / denominator if denominator > EPS else 1.0
    return mean_ratio, s, fc.stars_from_s(s)


def pct(count: int, total: int) -> str:
    return f"{count}/{total} ({100.0 * count / total:.1f}%)" if total else "0/0 (-)"


def signed(value: float, digits: int = 3) -> str:
    return f"{value:+.{digits}f}"


# ---------------------------------------------------------------- 출력


class Report:
    def rule(self, ch: str = "-") -> None:
        print(ch * W)

    def head(self, title: str) -> None:
        self.rule()
        print(f" {title}")
        self.rule()


def print_interpretation(tracks: set[str]) -> None:
    print(" 해석 규칙  : 모든 Δ는 plan2 - plan1")
    print("              FC Δ > 0이면 plan2 품질 우위, 비용 Δ < 0이면 plan2 비용 우위")
    print(" 비교 단위  : 같은 정적 케이스에 plan1/plan2를 각각 1회 실행한 paired 비교")
    if "conformance" in tracks:
        print(" ! Conformance 포함: 명세·경계 동작 확인용 fixture이므로 전체 우열의 근거로 쓰지 않는다.")
    if "scalability" in tracks:
        print(" ! Scalability 포함: 참여자/후보(안건) 수 증가 추세는 family별 회귀 분석이 별도로 필요하다.")


def print_quality(rep: Report, rows: list[CaseRow]) -> None:
    rep.head("[1] 합의 품질 — FC 달성률 paired 비교")
    p1_mean, p1_s, p1_stars = aggregate_score(rows, "plan1")
    p2_mean, p2_s, p2_stars = aggregate_score(rows, "plan2")
    deltas = [row.delta_fc for row in rows]
    p1_wins, p2_wins, ties = quality_counts(rows)
    outcomes_differ = sum(row.outcome_differs for row in rows)
    ci = paired_ci95(deltas)

    print(f"   plan1 평균 FC {p1_mean:.3f}   s {p1_s:+.3f}   별점 {p1_stars}")
    print(f"   plan2 평균 FC {p2_mean:.3f}   s {p2_s:+.3f}   별점 {p2_stars}")
    print(f"   FC Δ 평균 {signed(mean(deltas))}   중앙값 {signed(median(deltas))}")
    if ci is None:
        print("   FC Δ 평균의 95% t 신뢰구간: 계산 불가 (2건 이상 필요)")
    else:
        print(f"   FC Δ 평균의 95% t 신뢰구간: [{signed(ci[0])}, {signed(ci[1])}]")
    print(f"   FC 승/패/동률: plan1 {p1_wins} / plan2 {p2_wins} / 동률 {ties}")
    print(f"   최종 결과 후보가 다른 케이스: {pct(outcomes_differ, len(rows))}")
    print("   주의: 신뢰구간은 케이스 간 독립을 가정하며, 정적으로 설계한 케이스 집합 자체가 모집단을 뜻하지 않는다.")


def print_cost_row(rows: list[CaseRow], label: str, attr: str) -> None:
    p1_values = [getattr(row.plan1, attr) for row in rows]
    p2_values = [getattr(row.plan2, attr) for row in rows]
    deltas = [p2 - p1 for p1, p2 in zip(p1_values, p2_values)]
    p1_lower, p2_lower, ties = lower_cost_counts(rows, attr)
    print(
        f"   {label:<6} 평균 P1 {mean(p1_values):8.2f}  P2 {mean(p2_values):8.2f}  "
        f"Δ {signed(mean(deltas), 2):>8}  적은 쪽 P1/P2/동률 {p1_lower}/{p2_lower}/{ties}"
    )


def print_efficiency(rep: Report, rows: list[CaseRow]) -> None:
    rep.head("[2] 실행 비용 — 낮을수록 유리")
    print_cost_row(rows, "라운드", "rounds")
    print_cost_row(rows, "바퀴", "sweeps")
    print_cost_row(rows, "메시지", "messages")
    print_cost_row(rows, "직렬단계", "phases")
    print("   Δ가 음수면 plan2가 더 적게 사용했고, 양수면 plan1이 더 적게 사용했다.")


def tradeoff_category(row: CaseRow) -> str:
    quality = 1 if row.delta_fc > EPS else -1 if row.delta_fc < -EPS else 0
    round_delta = row.plan2.rounds - row.plan1.rounds
    if quality > 0 and round_delta <= 0:
        return "plan2 품질↑·라운드 비증가"
    if quality < 0 and round_delta >= 0:
        return "plan1 품질↑·라운드 비증가"
    if quality != 0:
        return "품질-라운드 trade-off"
    if round_delta < 0:
        return "품질 동률·plan2 라운드↓"
    if round_delta > 0:
        return "품질 동률·plan1 라운드↓"
    return "품질·라운드 모두 동률"


def print_tradeoff(rep: Report, rows: list[CaseRow]) -> None:
    rep.head("[3] 품질-라운드 관계")
    counts = Counter(tradeoff_category(row) for row in rows)
    order = (
        "plan1 품질↑·라운드 비증가",
        "plan2 품질↑·라운드 비증가",
        "품질-라운드 trade-off",
        "품질 동률·plan1 라운드↓",
        "품질 동률·plan2 라운드↓",
        "품질·라운드 모두 동률",
    )
    for category in order:
        print(f"   {category:<30} {pct(counts[category], len(rows))}")
    print("   '라운드 비증가'는 품질이 높은 방안의 라운드 수도 상대 방안보다 많지 않다는 뜻이다.")


def print_groups(rep: Report, rows: list[CaseRow]) -> None:
    rep.head("[4] 트랙·시나리오 유형별 비교")
    groups: dict[tuple[str, str], list[CaseRow]] = defaultdict(list)
    for row in rows:
        groups[(row.track, row.scenario_type)].append(row)

    label_width = max([len(f"{track}/{scenario}") for track, scenario in groups] + [10])
    print(
        f"   {'track/scenario':<{label_width}}   n   FC P1   FC P2    FC Δ   "
        "승 P1/P2/동률   라운드 Δ   메시지 Δ"
    )
    for (track, scenario), members in sorted(groups.items()):
        p1_wins, p2_wins, ties = quality_counts(members)
        wins = f"{p1_wins}/{p2_wins}/{ties}"
        round_delta = mean(row.plan2.rounds - row.plan1.rounds for row in members)
        message_delta = mean(row.plan2.messages - row.plan1.messages for row in members)
        label = f"{track}/{scenario}"
        print(
            f"   {label:<{label_width}} {len(members):>3d}   "
            f"{mean(row.plan1.ratio for row in members):>5.3f}   "
            f"{mean(row.plan2.ratio for row in members):>5.3f}   "
            f"{signed(mean(row.delta_fc for row in members)):>7}   "
            f"{wins:<12} "
            f"{signed(round_delta, 2):>8}   {signed(message_delta, 2):>8}"
        )


def print_case_rows(rep: Report, rows: list[CaseRow], limit: int, verbose: bool) -> None:
    changed = [row for row in rows if row.outcome_differs or abs(row.delta_fc) > EPS]
    changed.sort(key=lambda row: (-abs(row.delta_fc), row.case_id))
    shown = rows if verbose else changed
    title = "[5] 전체 케이스" if verbose else "[5] 결과 후보 또는 FC가 다른 케이스"
    rep.head(title)

    if not shown:
        print("   해당 케이스 없음")
        return

    if not verbose and limit > 0:
        shown = shown[:limit]
    id_width = max([len(row.case_id) for row in shown] + [7])
    outcome_width = max(
        [len(str(metric.outcome)) for row in shown for metric in (row.plan1, row.plan2)] + [7]
    )
    print(
        f"   {'case_id':<{id_width}}  {'P1 결과':<{outcome_width}}  {'P2 결과':<{outcome_width}}  "
        "FC1   FC2     FC Δ   R1/R2   Msg1/Msg2"
    )
    for row in shown:
        print(
            f"   {row.case_id:<{id_width}}  {str(row.plan1.outcome):<{outcome_width}}  "
            f"{str(row.plan2.outcome):<{outcome_width}}  {row.plan1.ratio:.3f}  "
            f"{row.plan2.ratio:.3f}  {signed(row.delta_fc):>7}   "
            f"{row.plan1.rounds:>2}/{row.plan2.rounds:<2}   "
            f"{row.plan1.messages:>4}/{row.plan2.messages:<4}"
        )
    if not verbose and len(changed) > len(shown):
        print(
            f"   ... {len(changed) - len(shown)}건 생략 "
            "(--detail-limit 0으로 모두 표시, --verbose로 동률 케이스까지 표시)"
        )


def build(rep: Report, rows: list[CaseRow], detail_limit: int, verbose: bool) -> None:
    print_quality(rep, rows)
    print_efficiency(rep, rows)
    print_tradeoff(rep, rows)
    print_groups(rep, rows)
    print_case_rows(rep, rows, detail_limit, verbose)
    rep.rule("=")


# ---------------------------------------------------------------- 진입점


def main() -> None:
    parser = argparse.ArgumentParser(
        description="동일 벤치마크 케이스에서 plan1과 plan2 결과를 paired 비교한다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "paths", nargs="*", help="케이스 디렉터리 또는 JSON 파일 (기본: data/benchmark/cases)"
    )
    parser.add_argument("--track", choices=TRACKS, default=None, help="지정 트랙만 집계")
    parser.add_argument(
        "--detail-limit",
        type=int,
        default=20,
        help="차이 케이스 최대 표시 수 (기본 20, 0이면 전부)",
    )
    parser.add_argument("--verbose", action="store_true", help="차이 여부와 무관하게 모든 케이스 표시")
    args = parser.parse_args()
    if args.detail_limit < 0:
        parser.error("--detail-limit은 0 이상이어야 한다")

    raw_paths = args.paths or [str(CASES_DIR)]
    try:
        cases, missing = collect(raw_paths, args.track)
    except (BenchmarkValidationError, json.JSONDecodeError, OSError) as error:
        print("벤치마크 데이터를 읽지 못했다 — 비교를 중단한다:", file=sys.stderr)
        print(str(error), file=sys.stderr)
        raise SystemExit(1)

    rep = Report()
    rep.rule("=")
    print(" 방안 결과 비교 리포트")
    rep.rule("=")
    print(f" 대상 경로  : {', '.join(str(resolve(path)) for path in raw_paths)}")
    print(f" 트랙 필터  : {args.track or '(없음)'}")
    for path in missing:
        print(f" ! 경로 없음(건너뜀): {path}")

    if not cases:
        print(" 케이스     : 0건")
        rep.rule()
        print(" 비교할 케이스가 없다 — 경로 또는 --track 필터를 확인하라. (정상 종료)")
        return

    tracks = Counter(case.track or "(미지정)" for case in cases)
    track_text = ", ".join(f"{track} {count}건" for track, count in sorted(tracks.items()))
    print(f" 케이스     : {len(cases)}건   [{track_text}]")
    print(" 실행 설정  : 케이스당 plan1/plan2 각 1회 (5바퀴, boulware, 방안별 기본 동률규칙)")
    print_interpretation(set(tracks))

    rows = [run_case(case) for case in cases]
    build(rep, rows, args.detail_limit, args.verbose)


if __name__ == "__main__":
    main()
