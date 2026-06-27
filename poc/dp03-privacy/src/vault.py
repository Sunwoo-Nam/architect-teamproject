"""PrivacyVault — 토큰↔원본 매핑 (방안 2). 합의 후 실행 단계에서만 복원."""


class PrivacyVault:
    def __init__(self):
        self.map = {}      # token -> raw
        self._n = 0

    def tokenize(self, raw):
        self._n += 1
        tok = f"<tok{self._n}>"
        self.map[tok] = raw
        return tok

    def restore(self, token):
        return self.map.get(token)

    def raw_values(self):
        return list(self.map.values())
