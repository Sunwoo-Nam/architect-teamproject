"""EgressMonitor — LLM-cp로 가는 모든 메시지의 단일 통과·기록 지점."""


class EgressMonitor:
    def __init__(self):
        self.messages = []

    def record(self, msg):
        self.messages.append(msg)
        return msg
