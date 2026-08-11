"""이벤트 로그 — "결과가 어떻게 나왔는지"를 로그만으로 재구성할 수 있게 기록한다.

기록 완전성(FR CFR-H2) 취지: 모든 제안·응답·판정에 입력(offer), 효용값, 그 시점
양보선(threshold), 결정과 사유를 남긴다. 전략 이벤트(deepening·백트랙·최종 확인)와
실행 메타(TC·전략·시드)도 포함 — 같은 시드로 재실행하면 같은 로그가 나온다(결정론 재현).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EventLog:
    meta: dict
    events: list[dict] = field(default_factory=list)

    def log(self, kind: str, **fields) -> None:
        self.events.append({"seq": len(self.events), "kind": kind, **fields})

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"kind": "meta", **self.meta}, ensure_ascii=False) + "\n")
            for event in self.events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return path


def load_events(path: str | Path) -> tuple[dict, list[dict]]:
    lines = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]
    meta = lines[0] if lines and lines[0].get("kind") == "meta" else {}
    return meta, [e for e in lines if e.get("kind") != "meta"]
