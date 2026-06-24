"""NegotiationEngine — 구조화 제안 생성.

StubEngine: LLM 없이 결정적으로 제안을 만들어 파이프라인·게이트·유출 측정을 검증한다.
- 방안 1(filter_at_egress): 원본 컨텍스트로 제안 → 정확값 + over-precise 추가 필드 포함
- 방안 2(transform_at_ingress): SafeScope(coarse)만으로 제안
LLM 엔진은 Ollama 설치 후 추가.
"""
from helpers import first_free, exact_budget, pref_area


class StubEngine:
    def propose(self, approach, scenario, safescope):
        case = scenario.case
        if case != "negotiation":
            return {"msg_type": "propose", "case": case, "payload": {}}

        if approach == "filter_at_egress":
            free = first_free(scenario) or {}
            day, frm, to = free.get("day", ""), free.get("from", ""), free.get("to", "")
            payload = {
                "slot": f"{day} {frm}-{to}".strip(" -"),
                "area": pref_area(scenario),
                "budget_cap": exact_budget(scenario),
                "earliest_available": frm,        # over-precise 추가 필드 (누설 벡터)
            }
        else:
            s = safescope.fields
            payload = {
                "slot": s.get("slot"),
                "area": s.get("area"),
                "budget_cap": s.get("budget_cap"),
                "earliest_available": s.get("slot_daypart"),
            }
        return {"msg_type": "propose", "case": case, "payload": payload}
