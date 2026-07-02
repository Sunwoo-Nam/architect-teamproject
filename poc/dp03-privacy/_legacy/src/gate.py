"""EgressGate — 방안1: 구조화 필드 새니타이저(불완전) / 방안2: 검증자."""
from message_schema import FIELD_RULES, apply_rule


def sanitize(payload, case, auth, gc):
    """방안 1: 필드별 coarsening + 결함(gate_config) 적용."""
    rules = FIELD_RULES.get(case, {})
    out = {}
    for f, v in payload.items():
        if f in gc.missing_rules:
            out[f] = v                       # 결함: 규칙 없는 필드 통과
        elif f not in rules:
            if gc.allow_extra_fields:
                out[f] = v                   # 결함: 화이트리스트 밖 필드 통과
            # else: 드롭
        elif f in gc.freeform_subfields:
            out[f] = v                       # 결함: free-form sub-field
        else:
            gran = gc.granularity_override.get(f, "daypart")
            val = apply_rule(rules[f], v, auth, gran)
            if val is not None:                 # freeform 등 드롭 결과는 제외
                out[f] = val
    return out


def verify(payload, vault):
    """방안 2: 토큰화된 원본이 평문으로 섞였는지 점검(정상이면 통과)."""
    for raw in vault.raw_values():
        for v in payload.values():
            assert str(raw) not in str(v), f"vault raw leaked into egress: {raw}"
    return dict(payload)
