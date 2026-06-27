"""OllamaClient — LLM-on(qwen3.5:4b)·LLM-cp(qwen3.5:9b) 래퍼.

temperature=0·seed 고정으로 재현성 확보, format=JSON 스키마로 구조화 출력 강제.
qwen3.5는 reasoning 모델이라 think=False로 사고 토큰을 끈다(미지원 시 무시).
벤치마크용으로 호출 수·토큰 수·추론 시간(ollama total_duration)을 누적한다.
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


def _g(resp, key, default=0):
    try:
        return resp[key]
    except Exception:
        return getattr(resp, key, default) or default


class OllamaClient:
    def __init__(self, model, seed=0, temperature=0.0, host=None):
        self.model = model
        self.seed = seed
        self.temperature = temperature
        self.client = Client(host=host) if host else Client()
        self.reset()

    def reset(self):
        self.calls = 0
        self.prompt_tokens = 0
        self.eval_tokens = 0
        self.duration_ns = 0      # ollama total_duration 누적

    def stats(self):
        return {"calls": self.calls, "tokens_in": self.prompt_tokens,
                "tokens_out": self.eval_tokens, "t_llm_s": self.duration_ns / 1e9}

    def complete_json(self, system, user, schema=None):
        kwargs = dict(
            model=self.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            options={"temperature": self.temperature, "seed": self.seed,
                     "num_predict": 512, "num_ctx": 4096},
            format=(schema or "json"),
        )
        try:
            resp = self.client.chat(think=False, **kwargs)
        except TypeError:
            resp = self.client.chat(**kwargs)
        self.calls += 1
        self.prompt_tokens += _g(resp, "prompt_eval_count")
        self.eval_tokens += _g(resp, "eval_count")
        self.duration_ns += _g(resp, "total_duration")
        return _parse_json(_g(resp, "message")["content"])


def available_models():
    try:
        data = Client().list()
        return [m.get("model") or m.get("name") for m in data.get("models", [])]
    except Exception:
        return []


def ollama_rss_bytes():
    """ollama 서버 프로세스들의 RSS 합(모델 가중치+KV 포함). 보조 지표."""
    try:
        import psutil
    except ImportError:
        return 0
    total = 0
    for p in psutil.process_iter(["name"]):
        try:
            if "ollama" in (p.info["name"] or "").lower():
                total += p.memory_info().rss
        except Exception:
            pass
    return total
