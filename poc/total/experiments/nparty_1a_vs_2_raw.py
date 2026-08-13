#!/usr/bin/env python3
"""실험(원지표) — 방안 1-A vs 방안 2, §1~§11 전 항목 상세.

같은 두 방안을 재는 `nparty_1a_vs_2.py`와 **자료의 수준이 다르다.**

    nparty_1a_vs_2.py      QA 별점 — 항목별 등급 판정 (total/qa 측정기)
    nparty_1a_vs_2_raw.py  원지표 — 달성률·라운드·phase·메모리·시간의 실측값 (본 파일)

방안 수는 둘 다 1-A와 2로 같다. 실험 이름이 다르므로 `results/<실험명>/` 아래
별도 폴더에 저장되고, 리포트 파일도 서로 섞이지 않는다.

**`total/qa/report.py`의 `write_run()`을 쓰지 않는다.** 그쪽은 `QA_KEYS`
(fc·cf·tb·ru·sc_issue)만 허용하는데, 본 실험의 raw에는 §10 의제 조합·§11 참여자 수
스윕처럼 등록되지 않은 키가 들어간다. 대신 `meta.json`을 같은 규격(`RunMeta`)으로
써서 `render_index()`가 INDEX에 자동 등재하도록 맞춘다.

    .venv/bin/python experiments/nparty_1a_vs_2_raw.py                    # 기본 — 방안 1-A·2
    .venv/bin/python experiments/nparty_1a_vs_2_raw.py --plans all        # 전 방안 14개
    .venv/bin/python experiments/nparty_1a_vs_2_raw.py --skip-n-sweep     # §11 생략
    .venv/bin/python experiments/nparty_1a_vs_2_raw.py --issue-space-cases 5

소요 시간(방안 2개 기준): §1~§10 약 9분 + §11 약 32분(480건, 프로세스 병렬).
`--plans all`로 14개를 돌리면 수 시간이 걸릴 수 있다 — 처음 재는 실행은
`--issue-space-cases`·`--skip-n-sweep`으로 규모를 줄여 시간을 재고 판단할 것.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from total.adapters.nparty._vendor.full_campaign import resolve_plans, run_full  # noqa: E402
from total.adapters.nparty._vendor.html_report import render_html  # noqa: E402
from total.adapters.nparty._vendor.measures.an_kit import generate_kit  # noqa: E402
from total.adapters.nparty._vendor.report import render_markdown  # noqa: E402
from total.qa.report import RunMeta, make_run_id, now_stamp, render_index  # noqa: E402

EXPERIMENT = "nparty-1a-vs-2-raw"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=20260811)
    ap.add_argument("--plans", default="1a,2",
                    help="측정할 방안 — 번호('2,6,10,20') 또는 내부 이름 혼용, 쉼표 구분. "
                         "기본 '1a,2', 전체는 '--plans all'")
    ap.add_argument("--skip-n-sweep", action="store_true",
                    help="§11(참여자 수 3~50인 스윕)을 건너뛴다 — 방안 2개 기준 30분 안팎 절약")
    ap.add_argument("--issue-space-cases", type=int, default=None,
                    help="§10 의제 조합을 트랙(A·B)당 이 건수로 축소 (생략 시 전체)")
    ap.add_argument("--results", default=str(ROOT / "results"),
                    help="결과 루트 (기본: total/results)")
    args = ap.parse_args()

    plans = resolve_plans(args.plans)
    raw = run_full(seed=args.seed, plans=plans,
                   issue_space_limit=args.issue_space_cases,
                   skip_n_sweep=args.skip_n_sweep)

    # run_id는 total 규칙(<실험명>-<UTC 타임스탬프>Z)으로 덮어쓴다 — run_full이 채워 넣는
    # 'full-<KST>KST'는 dp2-nparty 시절 관례라 results/<실험명>/ 구조와 맞지 않는다.
    run_id = make_run_id(EXPERIMENT, now_stamp())
    raw["meta"]["run_id"] = run_id

    out = Path(args.results) / EXPERIMENT / run_id
    out.mkdir(parents=True, exist_ok=True)

    # 진단 킷은 raw에 경로가 기록되므로 raw.json을 쓰기 전에 만든다.
    raw["an_kit"] = generate_kit(out / "an-kit", args.seed)

    meta = RunMeta(
        run_id=run_id,
        experiment=EXPERIMENT,
        seed=args.seed,
        dataset={"name": "nparty benchmark", "cases": str(ROOT / "datasets" / "nparty" / "cases")},
        plans=list(plans),
        note="방안 1-A vs 방안 2 — §1~§11 원지표. 별점 판정은 nparty-1a-vs-2 쪽을 볼 것. "
             "입력은 확정 벤치마크 셋(결정론) — 같은 입력이면 같은 결과.",
    )
    (out / "meta.json").write_text(
        json.dumps(meta.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "raw.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "report.md").write_text(render_markdown(raw), encoding="utf-8")
    (out / "report.html").write_text(render_html(raw), encoding="utf-8")

    index = Path(args.results) / "INDEX.md"
    index.write_text(render_index(Path(args.results)), encoding="utf-8")

    print(f"저장: {out}/")
    print("  report.html — 브라우저로 여는 대시보드 (§1~§11 한 화면)")
    print("  report.md   — GitHub 렌더링용")
    print("  raw.json    — 원자료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
