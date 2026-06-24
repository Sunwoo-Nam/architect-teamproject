"""PrivacyMediator (방안 2) — tool 결과 ingress마다 안전형(SafeScope)으로 변환.

PII는 Vault 토큰화, 사유는 차단·폐기, 협상 사실값은 권한 범위로 정밀도 저하.
(rule 백엔드. oracle/llm 백엔드는 분류 정확도만 다르며 변환 골격은 동일.)
"""
from dataclasses import dataclass, field
from message_schema import coarsen_time, coarsen_location, coarsen_budget
from helpers import first_free, exact_budget, pref_area, collect_pii, collect_private_reason


@dataclass
class SafeScope:
    fields: dict = field(default_factory=dict)
    blocked: list = field(default_factory=list)   # 차단한 사유
    tokens: dict = field(default_factory=dict)     # raw -> token


class PrivacyMediator:
    def __init__(self, backend="rule"):
        self.backend = backend

    def transform(self, scenario, vault):
        free = first_free(scenario) or {}
        slot = coarsen_time(f"{free.get('day', '')} {free.get('from', '')}-{free.get('to', '')}")
        area = coarsen_location(pref_area(scenario))
        budget = coarsen_budget(exact_budget(scenario), scenario.authorization)

        tokens = {raw: vault.tokenize(raw) for raw in collect_pii(scenario)}
        blocked = collect_private_reason(scenario)   # 사유는 SafeScope에 넣지 않고 폐기

        return SafeScope(
            fields={"slot": slot, "area": area, "budget_cap": budget, "slot_daypart": slot},
            blocked=blocked, tokens=tokens)
