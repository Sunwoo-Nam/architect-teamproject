"""통합 실행 — 확정 벤치마크 기준 전 QA 측정, 한 timestamp.

사용: .venv/bin/python scripts/run_full.py
출력:
  results/report-<yymmdd_hhmmss>.html  대시보드 (브라우저로 여는 결과물)
  results/full-<KST>KST/               raw.json + report.md + an-kit (원자료)

대시보드를 폴더 밖에 두는 이유: 결과물을 이름만 보고 바로 열 수 있어야 해서다.
원자료는 폴더에 남기고, 대시보드 각주가 그 폴더를 가리킨다.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dp2_nparty.full_campaign import run_full
from dp2_nparty.html_report import render_html
from dp2_nparty.report import render_markdown


def _stamp(run_id: str) -> str:
    """run_id `full-20260811T202943KST[-2]` → `260811_202943[-2]`."""
    m = re.search(r"(\d{2})(\d{2})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})", run_id)
    if not m:
        return run_id
    _c, yy, mm, dd, hh, mi, ss = m.groups()
    suffix = re.search(r"(-\d+)$", run_id)
    return f"{yy}{mm}{dd}_{hh}{mi}{ss}" + (suffix.group(1) if suffix else "")


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
    dashboard = run_dir.parent / f"report-{_stamp(run_dir.name)}.html"
    raw["meta"]["dashboard"] = dashboard.name  # INDEX가 대시보드를 찾는 경로
    (run_dir / "raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1))
    (run_dir / "report.md").write_text(render_markdown(raw))
    dashboard.write_text(render_html(raw, raw_ref=f"{run_dir.name}/raw.json"))

    print(f"저장: {dashboard}")
    print(f"      {run_dir}/ (raw.json · report.md · an-kit)")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_index.py")], check=False)


if __name__ == "__main__":
    main()
