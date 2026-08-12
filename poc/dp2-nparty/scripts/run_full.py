"""통합 실행 — 확정 벤치마크 기준 전 QA 측정, 한 timestamp·한 폴더.

사용: .venv/bin/python scripts/run_full.py                 # 기본 — 방안 1-A·2만 (PL 지시 2026-08-12)
      .venv/bin/python scripts/run_full.py --plans all     # 전 방안 측정
      .venv/bin/python scripts/run_full.py --plans 2,6,20  # 방안 번호로 부분 실행
      .venv/bin/python scripts/run_full.py --plans plan2,plan6itree  # 내부 이름도 허용
      .venv/bin/python scripts/run_full.py --issue-space-cases 5  # §10을 트랙당 5건으로 축소
출력: results/full-<KST>KST/ 에 raw.json + report.md + report.html (대시보드)
부분 실행 결과에는 meta.plans / caveat_plans 로 선택 방안이 기록된다.

주의(§10 의제 조합, A·B 트랙 각 30건): 순위를 한 칸씩 제출하는 방안은 조합 6만짜리
케이스에서 라운드가 수만 회다 (실측: 방안 2가 S=62,208에서 약 3만 라운드·케이스당 24~38초).
기본값(1a,2)은 약 7분이지만 --plans all 로 전 방안 14개를 돌리면 수 시간이 걸릴 수 있다
— 처음 재는 실행은 --issue-space-cases 로 규모를 줄여 시간을 재고 판단할 것을 권한다.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dp2_nparty.full_campaign import run_full
from dp2_nparty.html_report import render_html
from dp2_nparty.report import render_markdown


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260811)
    ap.add_argument("--plans", default="1a,2",
                    help="측정할 방안 선택 — 번호('2,6,10,20') 또는 내부 이름 혼용, 쉼표 구분. "
                         "기본 '1a,2' (PL 지시 2026-08-12), 전체는 '--plans all'")
    ap.add_argument("--issue-space-cases", type=int, default=None,
                    help="§10 의제 조합을 트랙(A·B)당 이 건수로 축소 (생략 시 전체)")
    args = ap.parse_args()

    from dp2_nparty.full_campaign import resolve_plans

    plans = resolve_plans(args.plans)
    raw = run_full(seed=args.seed, plans=plans, issue_space_limit=args.issue_space_cases)
    base = ROOT / "results" / raw["meta"]["run_id"]
    run_dir, n = base, 2
    while run_dir.exists():
        run_dir = base.with_name(f"{base.name}-{n}")
        n += 1
    raw["meta"]["run_id"] = run_dir.name
    run_dir.mkdir(parents=True)
    from dp2_nparty.measures.an_kit import generate_kit

    raw["an_kit"] = generate_kit(run_dir / "an-kit", args.seed)
    (run_dir / "raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1))
    (run_dir / "report.md").write_text(render_markdown(raw))
    (run_dir / "report.html").write_text(render_html(raw))

    print(f"저장: {run_dir}/")
    print("  report.html — 브라우저로 여는 대시보드 (전 QA 한 화면)")
    print("  report.md   — GitHub 렌더링용")
    print("  raw.json    — 원자료")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_index.py")], check=False)


if __name__ == "__main__":
    main()
