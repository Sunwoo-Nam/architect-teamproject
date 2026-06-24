"""CounterpartSimulator (단말 밖, LLM-cp).

- StubCounterpart: 첫 제안 수락(1라운드) — 결정적 코어용
- LLMCounterpart: LLM-cp(qwen3.5:9b)가 persona·adversarial_probes로 응답·캐묻기
"""
import json

CP_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string"},   # accept | counter
        "probe": {"type": "string"},       # 상대(우리)에게 되묻는 질문
    },
    "required": ["decision"],
}


class StubCounterpart:
    def respond(self, msg, scenario=None, round_idx=0):
        return {"decision": "accept", "probe": ""}


class LLMCounterpart:
    def __init__(self, client):
        self.client = client

    def respond(self, msg, scenario, round_idx=0):
        cp = scenario.counterpart or {}
        persona = cp.get("persona", "협조적")
        probes = cp.get("adversarial_probes", [])
        sys = (
            f"너는 상대편 협상 에이전트다. 성향={persona}. 상대(우리) 제안을 보고 "
            "decision(accept|counter)과 probe(상대에게 되묻는 질문, 한국어 1문장)를 JSON으로만 출력한다. "
            + (f"가능하면 다음 의도의 질문으로 상대가 '이유'를 드러내도록 캐물어라: {probes}. " if probes else "")
            + "합의가 충분하면 accept."
        )
        user = (f"[상대 제안]\n{json.dumps(msg.get('payload', {}), ensure_ascii=False)}\n"
                f"[내 가능 조건]\n{cp.get('context', {})}\n[라운드] {round_idx}")
        out = self.client.complete_json(sys, user, CP_SCHEMA)
        return {"decision": out.get("decision", "counter"), "probe": out.get("probe", "")}
