"""실행 설정과 게이트 결함(gate_config) 프리셋 (02-구조설계 D)."""
from dataclasses import dataclass, field


@dataclass
class GateConfig:
    label: str = "complete"
    missing_rules: list = field(default_factory=list)       # coarsening 규칙 없는 필드 → 통과
    allow_extra_fields: bool = False                         # 화이트리스트 밖 필드 통과
    freeform_subfields: list = field(default_factory=list)  # free-form 문자열 sub-field
    granularity_override: dict = field(default_factory=dict)  # 권한보다 느슨한 단위


# 결함을 하나씩 켜고 끄며 측정 (방안1만 영향, 방안2는 원본 부재로 무관)
GATE_PRESETS = {
    "complete":    GateConfig("complete"),
    "extra_field": GateConfig("extra_field", allow_extra_fields=True),
    "granularity": GateConfig("granularity", granularity_override={"slot": "30m"}),
    "freeform_note": GateConfig("freeform_note", freeform_subfields=["note"]),  # note 자유텍스트 통과
}
