"""통합 실행 — 확정 벤치마크 기준 전 QA 측정, 한 timestamp·한 폴더.

사용: .venv/bin/python scripts/run_full.py                 # 기본 — 방안 1-A·2만 (PL 지시 2026-08-12)
      .venv/bin/python scripts/run_full.py --plans all     # 전 방안 측정
      .venv/bin/python scripts/run_full.py --plans 2,6,20  # 방안 번호로 부분 실행
      .venv/bin/python scripts/run_full.py --plans plan2,plan6itree  # 내부 이름도 허용
출력: results/full-<KST>KST/ 에 raw.json + report.md + report.html (대시보드)
부분 실행 결과에는 meta.plans / caveat_plans 로 선택 방안이 기록된다.
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
    args = ap.parse_args()

    from dp2_nparty.full_campaign import resolve_plans

    plans = resolve_plans(args.plans)
    raw = run_full(seed=args.seed, plans=plans)
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
