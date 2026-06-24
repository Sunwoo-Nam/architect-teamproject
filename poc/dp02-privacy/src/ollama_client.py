"""OllamaClient — LLM-on(Qwen 4B)·LLM-cp(Qwen 8B) 래퍼 (다음 단계).

Ollama 미설치 환경에서는 사용 시 명시적으로 실패한다.
"""


class OllamaClient:
    def __init__(self, model, seed=0, temperature=0.0):
        self.model = model
        self.seed = seed
        self.temperature = temperature

    def complete(self, prompt, schema=None):
        raise NotImplementedError(
            "Ollama 미설치. `ollama` 설치 + qwen 모델 pull 후 LLM 백엔드를 활성화한다.")
