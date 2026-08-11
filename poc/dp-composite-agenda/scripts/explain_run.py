"""추적 도구 — 이벤트 로그(JSONL)만 읽고 "결과가 어떻게 나왔는지"를 사람 말로 재구성한다.

사용:
  .venv/bin/python scripts/explain_run.py <run.jsonl>            # 로그 파일 해설
  .venv/bin/python scripts/explain_run.py --demo S01 pool        # TC·전략을 즉석 실행 후 해설
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dpca.harness.eventlog import load_events  # noqa: E402


def _fmt_offer(offer) -> str:
    if offer is None:
        return "(없음)"
    if isinstance(offer, (list, tuple)):
        return "·".join(str(x) for x in offer)
    return str(offer)


def explain(meta: dict, events: list[dict]) -> None:
    print(f"=== {meta.get('scenario')} / {meta.get('strategy')} "
          f"(시드 {meta.get('profile_seed')}, 공간 {meta.get('space_size'):,}, "
          f"바닥선 {meta.get('initial_thresholds')}) ===")
    for e in events:
        kind = e["kind"]
        who = f"P{e['agent']}" if "agent" in e else "  "
        if kind == "candidates_built":
            print(f"[{who}] 후보풀 구성: {e['pool_size']}개 "
                  f"(내 효용 {e.get('worst_utility')}~{e.get('best_utility')})")
        elif kind == "deepening":
            print(f"[{who}] ★ deepening → k={e['k']} — {e['reason']}")
        elif kind == "propose":
            extra = f", 내효용 {e['my_utility']}" if "my_utility" in e else \
                    (f", 값점수 {e['my_score']}" if "my_score" in e else "")
            print(f"[{who}] 제안(step {e.get('step')}): {_fmt_offer(e.get('offer'))} "
                  f"(양보선 {e.get('threshold')}{extra}) — {e['reason']}")
        elif kind == "respond":
            mark = "✓ 수락" if e.get("decision") == "ACCEPT" else "✗ 거절"
            extra = f", 내효용 {e['my_utility']}" if "my_utility" in e else \
                    (f", 값점수 {e['my_score']}" if "my_score" in e else "")
            print(f"[{who}] {mark}(step {e.get('step')}): {_fmt_offer(e.get('offer'))} "
                  f"(양보선 {e.get('threshold')}{extra}) — {e['reason']}")
        elif kind == "axis_session_start":
            print(f"--- 세션: {e['axis']} (후보 {len(e['space'])}개, "
                  f"확정 prefix {e['agreed_prefix']}) ---")
        elif kind == "axis_agreed":
            print(f"    ▶ {e['axis']} = {e['value']} 합의")
        elif kind == "backtrack":
            print(f"    ↩ 백트랙: {e['stuck_axis']} 진행 불가 → "
                  f"{e['forbid_axis']}={e['forbid_value']} 금지 — {e['reason']}")
        elif kind == "sequential_breakdown":
            print(f"    ✖ 결렬: {e['axis']}에서 백트랙 소진 — {e['reason']}")
        elif kind == "final_confirm_failed":
            print(f"    ✖ 최종 확인 실패: P{e['agent']} 효용 {e['utility']} < 바닥선 {e['floor']}")
        elif kind == "final_confirmed":
            print(f"    ✔ 최종 확인 통과: {e['agreement']}")
        elif kind == "session_end":
            outcome = e.get("agreement")
            print(f"=== 종료: {'합의 ' + str(outcome) if outcome else '결렬'} "
                  f"(라운드 {e.get('rounds')}, 제안 {e.get('proposals')}) ===")


def main() -> int:
    args = [a for a in sys.argv[1:]]
    if args and args[0] == "--demo":
        tc, strategy = (args[1] if len(args) > 1 else "S01"), (args[2] if len(args) > 2 else "pool")
        from dpca.common.scenario import load_scenario
        from dpca.harness.runner import run_one

        path = next((ROOT / "scenarios").glob(f"{tc}-*.yaml"))
        scenario = load_scenario(path, n_axes=4 if tc == "S11" else None)
        result = run_one(scenario, strategy, with_log=True)
        out = ROOT / "results" / f"demo-{tc}-{strategy}.jsonl"
        result.log.save(out)
        print(f"(로그 저장: {out})\n")
        meta, events = load_events(out)
        explain(meta, events)
        return 0
    if not args:
        print(__doc__)
        return 1
    meta, events = load_events(args[0])
    explain(meta, events)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
