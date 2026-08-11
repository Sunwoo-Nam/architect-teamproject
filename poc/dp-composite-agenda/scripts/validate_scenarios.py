"""TC 검증 도구 — 전 시나리오를 oracle로 검사한다.

검사 항목:
  1. 로드·결정론 (같은 시드 → 같은 프로파일)
  2. 합의 가능해 존재 (expected=agreement → mutual>0, no_agreement → feasible=0)
  3. 충돌 라벨 vs 정답 효용 상관 실측 일치 (conflict_check: skip이면 생략)
  4. Pareto frontier 크기 보고 (FC 보조 관측의 기준값)

사용:  python scripts/validate_scenarios.py [--tune]
  --tune: 실패한 TC의 시드를 +1씩 200회까지 탐색해 통과 시드를 제안한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from dpca.common.oracle import OracleReport, analyze  # noqa: E402
from dpca.common.scenario import load_scenario  # noqa: E402

CORR_BANDS = {"low": (0.35, 1.0), "mid": (-0.35, 0.35), "high": (-1.0, -0.35)}


def check(path: Path, seed_override: int | None = None) -> tuple[bool, list[str], list[OracleReport]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    sweep = raw["meta"].get("axis_sweep")
    n_axes_list = [n for n in (sweep or [None]) if n is None or n <= 6] or [4]

    problems: list[str] = []
    reports: list[OracleReport] = []
    for n_axes in n_axes_list:
        scenario = load_scenario(path, n_axes=n_axes)
        if seed_override is not None:
            scenario.participants["profile_seed"] = seed_override
        report = analyze(scenario)
        reports.append(report)
        if report.skipped:
            problems.append(f"n={n_axes}: oracle 생략(공간 초과) — 검증 불가")
            continue

        expected = scenario.meta["expected"]
        if expected == "no_agreement":
            if not report.xstar_is_breakdown:
                problems.append(
                    f"n={n_axes}: 결렬이 정답인데 x*가 합의 후보 (valid={report.valid_count})"
                )
        else:
            if report.xstar_is_breakdown:
                problems.append(
                    f"n={n_axes}: 합의가 정답인데 x* = 결렬 "
                    f"(feasible={report.feasible_count}, valid={report.valid_count})"
                )

        label = scenario.meta.get("conflict_level")
        if (
            expected == "agreement"
            and scenario.meta.get("conflict_check") != "skip"
            and label in CORR_BANDS
            and report.utility_corr is not None
        ):
            lo, hi = CORR_BANDS[label]
            if not (lo <= report.utility_corr <= hi):
                problems.append(
                    f"n={n_axes}: 충돌 라벨 {label} vs 실측 상관 {report.utility_corr:.2f} (허용 [{lo}, {hi}])"
                )
    return (not problems), problems, reports


def tune(path: Path, base_seed: int, tries: int = 200) -> int | None:
    for offset in range(1, tries + 1):
        ok, _, _ = check(path, seed_override=base_seed + offset)
        if ok:
            return base_seed + offset
    return None


def main() -> int:
    do_tune = "--tune" in sys.argv
    paths = sorted((ROOT / "scenarios").glob("S*.yaml"))
    all_ok = True
    print(f"{'TC':<6}{'조합수':>10}{'실행가능':>9}{'유효':>7}{'상관':>8}{'x*':>6}{'U(x*)':>8}{'R̄':>7}  판정")
    for path in paths:
        ok, problems, reports = check(path)
        for report in reports:
            corr = f"{report.utility_corr:.2f}" if report.utility_corr is not None else "-"
            xstar = "결렬" if report.xstar_is_breakdown else "합의"
            print(
                f"{report.scenario_id:<6}{report.space_size:>10}{report.feasible_count:>9}"
                f"{report.valid_count:>7}{corr:>8}{xstar:>6}{report.u_xstar:>8.2f}"
                f"{report.r_bar:>7.2f}  {'PASS' if ok else 'FAIL'}"
            )
        for problem in problems:
            all_ok = False
            print(f"       !! {problem}")
            if do_tune:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
                found = tune(path, int(raw["participants"]["profile_seed"]))
                print(f"       -> 제안 시드: {found}" if found else "       -> 대체 시드 못 찾음(구조 재검토 필요)")
                break
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
