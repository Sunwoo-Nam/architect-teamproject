"""분류기 백엔드 (교체식): rule / oracle / llm.

- rule: 정규식·사전 휴리스틱 (결정적, LLM 불필요)
- oracle: 정답지(labels) 사용 = perfect 모드
- llm: Qwen(LLM-on) 프롬프트 — Ollama 설치 후 활성화(다음 단계)
"""
import re

PII = "pii"
NEG = "negotiable_fact"
RAW = "raw_context"
PRIV = "private_reason"


class RuleClassifier:
    PHONE = re.compile(r"\d{2,4}-\d{3,4}-\d{4}")
    TIME = re.compile(r"\d{1,2}:\d{2}")

    def classify(self, value):
        s = str(value)
        if self.PHONE.search(s):
            return PII
        if ("시 " in s and ("로 " in s or "호" in s)) or "구 " in s:
            return PII
        if self.TIME.search(s):
            return RAW
        return NEG


class OracleClassifier:
    """정답지 labels(path -> category)를 그대로 사용하는 perfect 모드."""
    def __init__(self, labels):
        self.path2cat = {}
        for cat, paths in (labels or {}).items():
            for p in paths:
                self.path2cat[p] = cat

    def classify_path(self, path):
        return self.path2cat.get(path)


class LLMClassifier:
    def __init__(self, client=None):
        self.client = client

    def classify(self, value):
        raise NotImplementedError("LLM 분류기는 Ollama 설치 후 활성화 (다음 단계)")


def make_classifier(backend, scenario=None):
    if backend == "oracle":
        return OracleClassifier((scenario.oracle if scenario else {}).get("labels", {}))
    if backend == "llm":
        return LLMClassifier()
    return RuleClassifier()
