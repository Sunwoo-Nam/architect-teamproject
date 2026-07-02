"""권한 범위 검사 (실험 C). 게이트 전단/생성 단계에서 범위 초과 차단."""


class AuthorizationChecker:
    def check(self, field, value, auth):
        disclosable = auth.get("disclosable_fields")
        if disclosable is not None and field not in disclosable:
            return ("blocked", None)
        return ("ok", value)
