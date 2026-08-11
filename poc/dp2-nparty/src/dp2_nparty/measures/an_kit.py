"""[핸드북 §8] Analysability — 사람 진단 실험 킷 생성 + 채점.

인과 재구성은 사람 진단이 필요한 실험이므로, PoC 코드의 책임은:
① 표본 생성 — 정상 세션 + 결함(유실) 주입 세션, ② 로그 패키지(진단자 제공용)와
봉인 정답(주입자 보관용)의 분리 저장, ③ 진단 답안 채점.

파일 구성 (out_dir 아래):
  cases/<case_id>.json   — 진단자에게 주는 것: 관찰 로그 + 최종 결과만
  sealed/answers.json    — 봉인 정답 (정상: 성립 라운드·후보 / 결함: 주입 위치)
  README.md              — 진단 절차 안내
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from ..domain import NO_DEAL
from ..faults import FaultInjector
from ..protocol import Plan1Vote, Plan2Cumulative, Plan3Batch
from ..ufun_provider import TableUfun

PLANS = {"plan1": Plan1Vote, "plan2": Plan2Cumulative, "plan3a": Plan3Batch}


def generate_kit(out_dir: Path, seed: int, n_normal: int = 20, n_fault: int = 20) -> dict:
    out_dir = Path(out_dir)
    (out_dir / "cases").mkdir(parents=True, exist_ok=True)
    (out_dir / "sealed").mkdir(parents=True, exist_ok=True)
    provider = TableUfun()
    answers: dict[str, dict] = {}
    idx = 0
    for kind, count in (("normal", n_normal), ("fault", n_fault)):
        for i in range(count):
            rng = random.Random((seed, "an", kind, i).__hash__())
            cands = [f"slot{j:02d}" for j in range(12)]
            profiles = provider.build_profiles(cands, 3, rng)
            plan_name = ("plan1", "plan2", "plan3a")[idx % 3]
            injector = FaultInjector(0.15, seed + idx) if kind == "fault" else None
            session = PLANS[plan_name](profiles).run(injector=injector)
            case_id = f"AN-{idx:03d}"
            (out_dir / "cases" / f"{case_id}.json").write_text(json.dumps({
                "case_id": case_id, "plan": plan_name,
                "outcome": str(session.outcome), "rounds": session.rounds,
                "log": session.log,
            }, ensure_ascii=False, indent=1))
            answers[case_id] = {
                "kind": kind, "plan": plan_name,
                # 정상: 성립 라운드·후보(또는 결렬)가 정답. 결함: 유실 주입 세션임을 특정해야.
                "outcome": str(session.outcome),
                "final_round": session.rounds,
                "fault_injected": kind == "fault",
            }
            idx += 1
    (out_dir / "sealed" / "answers.json").write_text(
        json.dumps(answers, ensure_ascii=False, indent=1)
    )
    (out_dir / "README.md").write_text(
        "# Analysability 진단 킷 (핸드북 §8)\n\n"
        "- 진단자는 `cases/`의 로그만 본다 (sealed/ 접근 금지 — 블라인드).\n"
        "- 과제: 정상 세션은 성립 라운드·결정 요인, 결렬·결함 세션은 원인(유실 주입 여부 포함) 특정.\n"
        "- 건당 30분 한도. 답안은 answers 제출 파일로 작성 후 `grade()`로 채점.\n"
    )
    return {"cases": idx, "dir": str(out_dir)}


def grade(sealed_file: Path, submission_file: Path) -> dict:
    """답안 채점 — 케이스별 (fault_injected 판정, outcome, final_round) 일치 검사."""
    sealed = json.loads(Path(sealed_file).read_text())
    sub = json.loads(Path(submission_file).read_text())
    total, correct = 0, 0
    for cid, ans in sealed.items():
        total += 1
        s = sub.get(cid, {})
        ok = (
            s.get("fault_injected") == ans["fault_injected"]
            and str(s.get("outcome")) == ans["outcome"]
            and s.get("final_round") == ans["final_round"]
        )
        correct += ok
    return {"total": total, "correct": correct, "rate": correct / total if total else 0.0}
