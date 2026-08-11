"""results/INDEX.md 생성 — 전 측정 실행을 한눈에 보는 인덱스.

results/*/raw.json 을 전부 스캔해 실행 1건 = 표 1행으로 요약한다 (최신이 위).
측정 실행 후 자동 갱신되며, 수동 재생성: `.venv/bin/python scripts/build_index.py`
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _kst_display(ts: str | None) -> str:
    """저장 형식(UTC/KST 불문)을 KST로 변환해 표시."""
    if not ts:
        return "?"
    from datetime import datetime, timedelta, timezone

    try:
        dt = datetime.fromisoformat(ts)
        return dt.astimezone(timezone(timedelta(hours=9))).strftime("%m-%d %H:%M")
    except ValueError:
        return ts[:16]


def _stars(v) -> str:
    return f"★{v}" if isinstance(v, int) else "-"


def _row(run_dir: Path, raw: dict) -> dict:
    m = raw.get("meta", {})
    fc = raw.get("fc", {})
    sp = raw.get("sc_participants") or raw.get("overall") or {}
    cf = raw.get("confidentiality", {})
    ft, rc = raw.get("ft", {}), raw.get("rec", {})

    if run_dir.name.startswith("full-"):
        kind = "**벤치마크 전 항목 (통합)**"
    elif "sc_participants" in raw:
        kind = "개발용 무작위 (전 항목 캠페인)"
    elif "benchmark" in raw:
        kind = "벤치마크 셋 — FC·CF·RU"
    elif "overall" in raw:
        kind = "벤치마크 family — SC-참여자"
    else:
        kind = "?"

    plans = [p for p in ("plan1", "plan2", "plan3a") if p in fc or p in sp]

    def plan_pair(section, key="stars"):
        vals = [section.get(p, {}).get(key) for p in plans]
        if any(v is not None for v in vals):
            return ":".join(_stars(v) for v in vals)
        return "-"

    def ftrec_pair():
        if not ft or not rc:
            return "-"
        try:
            return ":".join(f"★{min(ft[p]['stars'], rc[p]['stars'])}" for p in plans)
        except (KeyError, TypeError):
            return "-"

    def cf_pair():
        try:
            return ":".join(f"★{cf[p]['participant']['stars']}" for p in plans)
        except (KeyError, TypeError):
            return "-"

    return {
        "run": run_dir.name,
        "date": _kst_display(m.get("timestamp") or m.get("timestamp_utc")),
        "commit": m.get("git_commit", "?"),
        "kind": kind,
        "fc": plan_pair(fc),
        "sc_n": plan_pair(sp),
        "ftrec": ftrec_pair(),
        "cf": cf_pair(),
    }


def main() -> None:
    rows = []
    for raw_file in sorted(ROOT.glob("results/*/raw.json"), reverse=True):
        try:
            rows.append(_row(raw_file.parent, json.loads(raw_file.read_text())))
        except Exception as e:  # 형식이 다른 결과가 와도 인덱스는 죽지 않는다
            rows.append({"run": raw_file.parent.name, "date": "?", "commit": "?",
                         "kind": f"파싱 실패 ({type(e).__name__})", "fc": "-", "sc_n": "-",
                         "ftrec": "-", "cf": "-"})

    L = [
        "# 측정 결과 인덱스 (자동 생성 — 직접 수정 금지)",
        "",
        "실행 1건 = 1행, 최신이 위. 별점은 `방안1:방안2`. 상세는 각 행의 report 링크.",
        "재생성: `.venv/bin/python scripts/build_index.py`",
        "",
        "| 실행 | 일시(KST) | commit | 입력 종류 | FC | SC-참여자 | FT&REC | CF(참여자) | 상세 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        L.append(
            f"| `{r['run']}` | {r['date']} | `{r['commit']}` | {r['kind']}"
            f" | {r['fc']} | {r['sc_n']} | {r['ftrec']} | {r['cf']}"
            f" | [report]({r['run']}/report.md) |"
        )
    L += [
        "",
        "읽는 법:",
        "- **판정에 쓰는 것**: 입력 종류가 **벤치마크**인 행 (정적 셋 — 결정론 재현). 개발용 무작위 행은 하니스 검증·상대 비교용.",
        "- 별점 척도·게이트 정의: [`docs/changbae/24-QA-측정-핸드북.md`](../../../docs/changbae/24-QA-측정-핸드북.md)",
        "- 측정값의 정본 위치는 이 폴더다 — 문서에는 방법만 있다.",
        "",
    ]
    (ROOT / "results" / "INDEX.md").write_text("\n".join(L))
    print(f"INDEX.md 갱신 — {len(rows)}개 실행")


if __name__ == "__main__":
    main()
