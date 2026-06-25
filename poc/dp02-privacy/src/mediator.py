"""PrivacyMediator (방안 2) — tool 결과 ingress마다 안전형(SafeScope)으로 변환.

PII는 Vault 토큰화, 사유는 차단·폐기, 협상 사실값은 권한 범위로 정밀도 저하.
- secrets(정답지)가 주어지면 perfect 모드: 비밀 리터럴을 포함한 값은 안전 요약에서 제외(분류 완벽 가정).
- secrets가 없으면 rule 모드: PRIVATE_KW·RuleClassifier 휴리스틱(분류 오류 포함).
안전 요약(summary)은 모든 케이스에서 LLM-on(방안2)의 유일한 입력이 된다.
"""
import re
from dataclasses import dataclass, field

from message_schema import coarsen_time, coarsen_location, coarsen_budget
from helpers import (first_free, exact_budget, pref_area,
                     collect_pii, collect_private_reason, PRIVATE_KW)
from classifier import RuleClassifier, PII


@dataclass
class SafeScope:
    fields: dict = field(default_factory=dict)
    summary: str = ""
    blocked: list = field(default_factory=list)
    tokens: dict = field(default_factory=dict)


def _flatten(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _flatten(v, f"{prefix}{k}.")
    elif isinstance(obj, list):
        for x in obj:
            yield from _flatten(x, prefix)
    elif obj is not None:
        yield prefix.rstrip("."), obj


class PrivacyMediator:
    def __init__(self, backend="rule"):
        self.backend = backend

    def transform(self, scenario, vault, secrets=None, client=None):
        free = first_free(scenario) or {}
        slot = coarsen_time(f"{free.get('day', '')} {free.get('from', '')}-{free.get('to', '')}")
        area = coarsen_location(pref_area(scenario))
        budget = coarsen_budget(exact_budget(scenario), scenario.authorization)

        tokens = {raw: vault.tokenize(raw) for raw in collect_pii(scenario)}
        blocked = collect_private_reason(scenario)
        if self.backend == "llm" and client is not None:
            summary = self._safe_summary_llm(scenario, client, slot, area, budget)  # 값마다 LLM 분류(비용↑)
        else:
            summary = self._safe_summary(scenario, secrets, slot, area, budget)

        return SafeScope(
            fields={"slot": slot, "area": area, "budget_cap": budget, "slot_daypart": slot},
            summary=summary, blocked=blocked, tokens=tokens)

    def _safe_summary(self, scenario, secrets, slot, area, budget):
        """모든 케이스 공통의 안전 요약. 비밀(perfect: secrets / rule: 휴리스틱)은 제외."""
        secset = set(str(s) for s in (secrets or []))
        rc = RuleClassifier()

        def is_blocked(s):
            if secset:                                  # perfect 모드
                return any(sec and sec in s for sec in secset)
            return rc.classify(s) == PII or any(kw in s for kw in PRIVATE_KW)  # rule 모드

        lines = [f"가능 시간(대략): {slot}", f"지역: {area}"]
        if budget:
            lines.append(f"예산 상한: {budget}")
        for tr in scenario.tool_results:
            tool = tr.get("tool")
            for k, v in _flatten(tr.get("data") or {}):
                s = str(v)
                if is_blocked(s):
                    continue                            # 비밀 포함 → 제외
                if re.search(r"\d{1,2}:\d{2}", s):
                    v = coarsen_time(s)                 # 시각 → 정밀도 저하
                lines.append(f"{tool}.{k}: {v}")
        return "\n".join(lines)

    def _safe_summary_llm(self, scenario, client, slot, area, budget):
        """llm 백엔드: 값마다 LLM-on으로 분류해 pii·private_reason은 제외(비용 측정 대상)."""
        from classifier import LLMClassifier
        clf = LLMClassifier(client)
        lines = [f"가능 시간(대략): {slot}", f"지역: {area}"]
        if budget:
            lines.append(f"예산 상한: {budget}")
        for tr in scenario.tool_results:
            tool = tr.get("tool")
            for k, v in _flatten(tr.get("data") or {}):
                cat = clf.classify(v)                   # ← on-device LLM 호출
                if cat in ("pii", "private_reason"):
                    continue
                s = str(v)
                if re.search(r"\d{1,2}:\d{2}", s):
                    v = coarsen_time(s)
                lines.append(f"{tool}.{k}: {v}")
        return "\n".join(lines)
