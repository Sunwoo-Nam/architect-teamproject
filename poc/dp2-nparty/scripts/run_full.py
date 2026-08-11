"""통합 실행 — 확정 벤치마크 기준 전 QA 측정, 한 timestamp·한 폴더.

사용: .venv/bin/python scripts/run_full.py
출력: results/full-<KST>KST/ 에 raw.json + report.md + report.html (대시보드)
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
    args = ap.parse_args()

    raw = run_full(seed=args.seed)
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
