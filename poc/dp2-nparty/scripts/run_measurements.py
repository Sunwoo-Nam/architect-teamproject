"""전 QA 측정 실행 → results/<run_id>/raw.json + report.md 저장.

사용:
  .venv/bin/python scripts/run_measurements.py            # 전체 표본
  .venv/bin/python scripts/run_measurements.py --scale 0.1  # 스모크 (표본 1/10)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dp2_nparty.campaign import run_all
from dp2_nparty.report import render_markdown


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260811)
    ap.add_argument("--scale", type=float, default=1.0, help="표본 크기 배율 (스모크용 축소)")
    args = ap.parse_args()

    raw = run_all(seed=args.seed, scale=args.scale)
    # 실행 1회 = 폴더 1개. 같은 초에 재실행돼도 덮어쓰지 않도록 접미사로 유일성 보장
    base = ROOT / "results" / raw["meta"]["run_id"]
    run_dir, n = base, 2
    while run_dir.exists():
        run_dir = base.with_name(f"{base.name}-{n}")
        n += 1
    raw["meta"]["run_id"] = run_dir.name
    run_dir.mkdir(parents=True)
    from dp2_nparty.measures.an_kit import generate_kit

    kit_n = max(2, int(20 * args.scale))
    raw["an_kit"] = generate_kit(run_dir / "an-kit", args.seed, n_normal=kit_n, n_fault=kit_n)
    (run_dir / "raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1))
    report = render_markdown(raw)
    (run_dir / "report.md").write_text(report)

    print(report)
    print(f"저장: {run_dir}/raw.json · {run_dir}/report.md")
    import subprocess

    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_index.py")], check=False)


if __name__ == "__main__":
    main()
