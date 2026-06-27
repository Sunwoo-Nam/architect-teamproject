"""시나리오 YAML 로더. 입력(ids_command·tool_results)과 정답지(oracle)를 분리 노출."""
from pathlib import Path
import yaml


class Scenario:
    def __init__(self, data):
        self.data = data
        self.id = data["id"]
        self.case = data["case"]
        self.ids_command = data.get("ids_command", {})
        self.tool_results = data.get("tool_results", [])
        self.authorization = data.get("authorization", {})
        self.counterpart = data.get("counterpart", {})
        self.goal = data.get("goal", {})
        self.oracle = data.get("oracle", {})

    @property
    def secrets(self):
        """유출 오라클 1층 대상: 절대 egress에 나오면 안 되는 값 전체."""
        s = self.oracle.get("secrets", {})
        out = []
        for key in ("pii", "raw_context", "over_precise", "private_reason"):
            out += [str(x) for x in s.get(key, [])]
        return out


def load_scenario(path):
    return Scenario(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
