"""저장된 raw.json에서 리포트를 재생성한다 (측정 재실행 없음).

사용: .venv/bin/python scripts/make_report.py results/<run_id>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dp2_nparty.report import render_markdown


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("사용법: make_report.py results/<run_id>")
    run_dir = Path(sys.argv[1])
    raw = json.loads((run_dir / "raw.json").read_text())
    report = render_markdown(raw)
    (run_dir / "report.md").write_text(report)
    print(report)
    print(f"재생성: {run_dir}/report.md")


if __name__ == "__main__":
    main()
