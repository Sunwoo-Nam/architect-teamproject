"""시나리오 입력에서 값을 끌어오는 보조 함수. 정답지(oracle)는 쓰지 않는다."""
from classifier import RuleClassifier, PII

# rule 백엔드의 사유(Private Knowledge) 탐지 키워드 — 정규식으로 못 잡는 의미 범주의 한계 예시
PRIVATE_KW = ["진료", "병원", "정신건강", "불안장애", "우울", "당뇨", "저당식",
              "할랄", "이슬람", "종교", "권고사직", "급전"]


def first_free(scenario):
    for tr in scenario.tool_results:
        if tr.get("tool") == "calendar":
            fr = (tr.get("data") or {}).get("free") or []
            if fr:
                return fr[0]
    return None


def pref_area(scenario):
    p = (scenario.ids_command.get("preferences") or {})
    if p.get("area"):
        return p["area"]
    for tr in scenario.tool_results:
        if tr.get("tool") == "location":
            return (tr.get("data") or {}).get("home_address", "")
    return ""


def exact_budget(scenario):
    for tr in scenario.tool_results:
        if tr.get("tool") == "payment":
            d = tr.get("data") or {}
            # account_balance_krw(잔액)는 공개할 예산이 아니라 사적 정보 → 제외
            if "budget_available_krw" in d:
                return d["budget_available_krw"]
    c = scenario.ids_command.get("constraints") or {}
    return c.get("budget_cap_krw", "")


def _walk(scenario):
    def rec(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                yield from rec(v)
        elif isinstance(obj, list):
            for x in obj:
                yield from rec(x)
        elif obj is not None:
            yield obj
    yield from rec(scenario.ids_command)
    for tr in scenario.tool_results:
        yield from rec(tr.get("data"))


def collect_pii(scenario):
    rc = RuleClassifier()
    return {str(v) for v in _walk(scenario) if rc.classify(v) == PII}


def collect_private_reason(scenario):
    out = []
    for v in _walk(scenario):
        s = str(v)
        if any(kw in s for kw in PRIVATE_KW):
            out.append(s)
    return out
