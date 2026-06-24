"""CounterpartSimulator (단말 밖, LLM-cp). StubCounterpart: 첫 제안 수락(1라운드).

LLM 상대(페르소나·적대적 캐묻기)는 Ollama 설치 후 추가.
"""


class StubCounterpart:
    def respond(self, msg):
        return {"msg_type": "accept", "case": msg["case"], "payload": {}}
