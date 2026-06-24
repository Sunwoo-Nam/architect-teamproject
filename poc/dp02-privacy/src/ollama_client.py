"""OllamaClient — LLM-on(qwen3.5:4b)·LLM-cp(qwen3.5:9b) 래퍼.

temperature=0·seed 고정으로 재현성 확보, format=JSON 스키마로 구조화 출력 강제.
qwen3.5는 reasoning 모델이라 think=False로 사고 토큰을 끈다(미지원 시 무시).
"""
import json
import re
from ollama import Client


def _parse_json(text):
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise ValueError(f"JSON 파싱 실패: {text[:200]!r}")


class OllamaClient:
    def __init__(self, model, seed=0, temperature=0.0, host=None):
        self.model = model
        self.seed = seed
        self.temperature = temperature
        self.client = Client(host=host) if host else Client()
        self.calls = 0

    def complete_json(self, system, user, schema=None):
        self.calls += 1
        kwargs = dict(
            model=self.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            options={"temperature": self.temperature, "seed": self.seed},
            format=(schema or "json"),
        )
        try:
            resp = self.client.chat(think=False, **kwargs)
        except TypeError:
            resp = self.client.chat(**kwargs)
        return _parse_json(resp["message"]["content"])


def available_models():
    try:
        data = Client().list()
        return [m.get("model") or m.get("name") for m in data.get("models", [])]
    except Exception:
        return []
