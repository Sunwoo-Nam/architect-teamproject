#!/usr/bin/env python3
"""SC-의제(최대 의제 수) 스윕 — seq2/pool/poolka, 한도 128MB (24 §5.3).

01-축수-스윕(정본 135435Z, seq2·pool)에 없던 poolka를 같은 fix-hi fixture로 재고,
스윕 상한을 30축까지 확장한다 (확장 구간은 make_fixtures.build_hi와 동일 방식 —
S11 10축 + numbered 축, 축당 값 5, fix-hi-22의 profile_seed 유지).

게이트는 24 §5.3 그대로: 단말 총 점유 ≤ 128MB **이면서 정상 완결(합의)**.
결렬 실행은 수용의 증거로 세지 않는다. RU·완결만 재는 경량 실행(FC 오라클 없음).

측정 한계 (2026-08-14 실행에서 확인):
- pool 계열은 27축 초과에서 negmas 결과 공간 크기(5^28 ≈ 3.7e19)가 int64 한계를
  넘어 측정 자체가 불가 (OverflowError) — 메모리 문제가 아니라 하니스 제약.
- 완결 여부는 profile_seed 의존 — 그리드상 첫 결렬 지점은 확정 상한이 아니다.

    .venv/bin/python experiments/sweep_max_issues.py
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from total import pyversion  # noqa: E402
from total.adapters.composite import load, load_fixture, run_session  # noqa: E402
from total.adapters.composite._vendor.common.generators import Value  # noqa: E402
from total.adapters.composite._vendor.common.scenario import Axis  # noqa: E402
from total.qa import ru  # noqa: E402

FIX = ROOT / "datasets" / "composite" / "fixtures"
OUT_DIR = ROOT / "results" / "composite-per-case" / "max-issues-20260814"
CEIL_MB = 128.0
FIXTURE_AXES = [4, 6, 8, 10, 12, 14, 16, 18, 20, 22]
EXTENDED_AXES = [24, 26, 28, 30]


@contextmanager
def _deadline(seconds: int):
    def _h(signum, frame):
        raise TimeoutError(f"{seconds}s 초과")
    old = signal.signal(signal.SIGALRM, _h)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def extended_scenario(n_axes: int, seed: int):
    """make_fixtures.build_hi 재현 — 22축 초과 구간의 인메모리 시나리오."""
    sc = load("S11", n_axes=10)
    for i in range(10, n_axes):
        sc.axes.append(Axis(f"x{i}", "numbered", [Value(f"x{i}_v{j}") for j in range(5)]))
    sc.participants["profile_seed"] = seed
    sc.agent_view = {"score_dropout": 0.0}
    sc.meta = {**sc.meta, "id": f"EXT-HI-{n_axes:02d}"}
    return sc


def run_point(plan: str, sc, n: int, tag: str, timeout_s: int = 600) -> dict:
    try:
        with _deadline(timeout_s):
            session, _ = run_session(sc, plan, light=True)
        mem = ru.measure(session)
        row = {"plan": plan, "n_axes": n, "src": tag, "agreed": session.agreed,
               "total_mb": round(mem.total_mb, 4), "r_pct": round(mem.r_total * 100, 3),
               "over": mem.total_mb > CEIL_MB}
    except Exception as exc:
        row = {"plan": plan, "n_axes": n, "src": tag,
               "error": f"{type(exc).__name__}: {exc}"}
    print(row, flush=True)
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--allow-python-mismatch", action="store_true")
    args = ap.parse_args()
    pyversion.require(args.allow_python_mismatch)

    seed22 = json.loads((FIX / "fix-hi-22axis.json").read_text())["participants"]["profile_seed"]
    rows = []
    # fixture 구간 — poolka (seq2·pool은 정본 스윕 135435Z에 있음)
    for n in FIXTURE_AXES:
        rows.append(run_point("poolka", load_fixture(FIX / f"fix-hi-{n:02d}axis.json"), n, "fixture"))
    # 확장 구간 — seq2·poolka (pool은 20축 한도 초과가 정본 스윕에서 확정)
    for n in EXTENDED_AXES:
        for plan in ("seq2", "poolka"):
            rows.append(run_point(plan, extended_scenario(n, seed22), n, "extended"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "raw.jsonl", "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"저장: {OUT_DIR / 'raw.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
