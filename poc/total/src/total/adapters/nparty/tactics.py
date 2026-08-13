"""방안 2 보완 택틱 — CF·TB 열세를 메우는 프로토콜 변형 (PL 지시 2026-08-13 밤샘 과제).

방안 2(누적 공통제안형)를 최종 설계로 선택하되, 열세 축을 택틱으로 보완한다:

**TB 택틱** (라운드 수 = phase 비용의 지배 항):
- `plan2b2` — 고정 배치: 라운드당 후보 2개 제출 (PL 제안). 라운드 절반.
- `plan2s`  — 전달 기억(delivered skip): 새 바퀴에서 이미 제출한 후보를 건너뛴다.
  vendor 원본은 바퀴마다 포인터를 0으로 되돌려 같은 후보를 재전송한다 — BB는 누적
  저장하므로 재전송은 순수 낭비다. FC·CF에 영향이 없는 무손실 최적화.
- `plan2ab` — 전달 기억 + **적응 배치**: 첫 라운드들은 1개(상위 순위 비밀 보호),
  라운드가 깊어질수록 2·4·8개로 가속. P95 꼬리(깊은 합의·다바퀴 판)를 정조준한다.

**CF 택틱**:
- `plan2c`  — **커밋 매칭(블라인드 BB)**: 제출을 후보 원문 대신 봉인(세션 솔트 해시)으로
  보내고, BB는 "같은 봉인이 전원에게서 왔는가"만 매칭한다. 성립 후보 1개만 공개(reveal).
  성립 규칙이 요구하는 정보는 교집합 여부뿐이므로 프로토콜 결과(FC)와 라운드 진행(TB)은
  그대로이고, 노출은 "성립 후보 1개"로 준다. 비용: 공개 1 phase + N건 + 소량 바이트.
  전제(문서 62에 명시): 참여자 간 공유 세션 솔트(BB 비공유) — 후보 공간이 작아도
  BB의 사전 대입을 막는 장치. BB-참여자 공모 시 무력화되는 신뢰 모델임을 함께 기록.

**결합 최종안**:
- `plan2plus` — plan2ab + 커밋 매칭. FC 동일, CF·TB 동시 보완.

vendor(`_vendor/protocol.py`)는 불변 — 전부 이 모듈의 서브클래스/래퍼다.
"""
from __future__ import annotations

from ._vendor.domain import NO_DEAL
from ._vendor.protocol import Plan2Cumulative


class _Plan2Tactic(Plan2Cumulative):
    """방안 2 라운드 루프의 택틱 훅 — 배치 폭·전달 기억.

    `_one_round`를 재정의한다 (base와 같은 계약: 반환 (성립|None, 전원 소진)).
    배치 제출은 라운드당 여전히 1 phase — 같은 방향 전송은 병렬이기 때문(51 §4와 동일 가정).
    이벤트는 "batch" 형식(순위 포함)으로 남겨 어댑터가 귀속 노출을 정확히 계상하게 한다.
    """

    #: 라운드(바퀴 내 순번) → 이번 라운드 제출 폭
    @staticmethod
    def batch_at(round_in_sweep: int) -> int:
        return 1

    #: 새 바퀴에서 이미 전달된 후보를 건너뛰는가 (무손실 — BB는 누적 저장)
    skip_delivered = False

    def __init__(self, profiles, **kw):
        super().__init__(profiles, **kw)
        self._cur_sweep = 0
        self._ris = 0  # round-in-sweep

    def _one_round(self, bb, sweep, round_no, injector, kill_at, events):
        if sweep != self._cur_sweep:
            self._cur_sweep, self._ris = sweep, 0
        self._ris += 1
        width = max(1, self.batch_at(self._ris))

        self._round_tick(bb, sweep)
        submitted: dict[str, list] = {}
        any_pending = False
        for i, a in enumerate(self.agents):
            delivered = bb.proposed_by.get(a.p.pid, set())
            taken = 0
            lost_now = False
            while taken < width and not lost_now:
                if self.skip_delivered:
                    while True:
                        c = a.peek(sweep)
                        if c is None or c not in delivered:
                            break
                        a.ptr += 1  # 이미 BB에 있음 — 전송 없이 전진 (무손실)
                c = a.peek(sweep)
                if c is None:
                    break
                any_pending = True
                bb.submit(a.p.pid, i == 0, {"candidate": str(c)})  # 전송 비용 지불
                if injector and injector.lost():
                    lost_now = True  # 유실 — 포인터 유지, 다음 라운드 재시도
                    continue
                submitted.setdefault(a.p.pid, []).append((a.ptr + 1, c))
                a.ptr += 1
                taken += 1
        if not any_pending:
            return None, True  # 전원 소진 — 다음 바퀴
        bb.phase()  # 배치 제출 = 1 phase (병렬 전송)
        if self.collect_log:
            events.append({"t": "batch", "sweep": sweep, "k": round_no,
                           "submitted": {pid: [(r, str(c)) for r, c in items]
                                         for pid, items in submitted.items()}})
        if kill_at and kill_at.round_no == round_no and kill_at.point == "mid_round":
            raise Exception("kill_at은 택틱 변형에서 지원하지 않는다")
        if not submitted:
            return None, False
        # 판정 — 방안 2와 동일: 누적 교집합 = 만장일치
        for pid, items in submitted.items():
            bb.proposed_by.setdefault(pid, set()).update(c for _r, c in items)
        if len(bb.proposed_by) < self.n:
            return None, False
        common = set.intersection(*bb.proposed_by.values())
        if not common:
            return None, False
        return self._resolve(bb, sorted(common, key=repr)), False


class Plan2Batch2(_Plan2Tactic):
    """TB 택틱(PL 제안) — 라운드당 2개 고정 배치."""

    plan_name = "plan2b2"

    @staticmethod
    def batch_at(round_in_sweep: int) -> int:
        return 2


class Plan2Skip(_Plan2Tactic):
    """TB 택틱 — 전달 기억만 (배치 1 유지). FC·CF 무손실 대조군."""

    plan_name = "plan2s"
    skip_delivered = True


class Plan2Adaptive(_Plan2Tactic):
    """TB 택틱 — 전달 기억 + 적응 배치 (1,1,2,2,4,4,8…)."""

    plan_name = "plan2ab"
    skip_delivered = True

    @staticmethod
    def batch_at(round_in_sweep: int) -> int:
        return min(8, 2 ** ((round_in_sweep - 1) // 2))


def _commit_wrap(inner_cls, name: str):
    """CF 택틱 — 커밋 매칭(블라인드 BB) 래퍼.

    프로토콜 진행·결과는 inner와 동일 (커밋도 같은 라운드 규칙으로 흐른다).
    바뀌는 것은 ① 관찰: 제출이 무귀속 봉인이라 BB에게 후보 내용이 안 보인다 —
    성립 후보 1개의 공개(reveal)만 전원에게 귀속된다. ② 비용: 공개 1 phase +
    참여자당 공개 메시지 1건(+48B 근사 — 원문+솔트).
    """

    class _Commit:
        plan_name = name

        def __init__(self, profiles, **kw):
            self._inner = inner_cls(profiles, **kw)
            self.n = self._inner.n
            self.agents = self._inner.agents

        def run(self, injector=None, kill_at=None, on_round_end=None):
            v = self._inner.run(injector=injector, kill_at=kill_at,
                                on_round_end=on_round_end)
            self._bb_ref = getattr(self._inner, "_bb_ref", None)
            if v.outcome != NO_DEAL:
                v.phases += 1                 # reveal 1 phase
                v.messages += self.n          # 전원 공개 1건씩
                v.bytes += 48 * self.n        # 원문+솔트 근사
            # 관찰 로그 재작성 — 커밋 제출은 무귀속. 성립 시 당첨 후보 공개만 남긴다.
            new_log = []
            if v.outcome != NO_DEAL:
                new_log.append({
                    "t": "round", "sweep": v.sweeps, "k": v.rounds,
                    "submitted": {a.p.pid: v.outcome for a in self._inner.agents},
                })
            v.log = new_log
            v.plan = name
            return v

        def __getattr__(self, key):
            return getattr(self._inner, key)

    _Commit.__name__ = f"Commit[{inner_cls.__name__}]"
    return _Commit


class Plan2Batch3(_Plan2Tactic):
    """탐색 — 라운드당 3개 고정 배치 (배치 폭 스윕용)."""

    plan_name = "plan2b3"

    @staticmethod
    def batch_at(round_in_sweep: int) -> int:
        return 3


class Plan2AdaptiveX(_Plan2Tactic):
    """탐색 — 전달 기억 + 공격적 적응 배치 (1,2,4,8,8…). 커밋과 결합하면 CF 비용이
    없으므로(노출 = 성립 후보 1개 고정) 가속을 더 세게 걸 수 있다."""

    plan_name = "plan2abx"
    skip_delivered = True

    @staticmethod
    def batch_at(round_in_sweep: int) -> int:
        return min(8, 2 ** (round_in_sweep - 1))


Plan2Commit = _commit_wrap(Plan2Cumulative, "plan2c")
Plan2Plus = _commit_wrap(Plan2Adaptive, "plan2plus")
Plan2PlusX = _commit_wrap(Plan2AdaptiveX, "plan2plusx")

#: 어댑터 PLANS에 등록되는 택틱 목록 (label은 62번 문서와 동기)
TACTIC_SPECS = [
    ("plan2b2", "방안 2 + 고정 배치 2 (TB)", Plan2Batch2),
    ("plan2s", "방안 2 + 전달 기억 (TB, 무손실)", Plan2Skip),
    ("plan2ab", "방안 2 + 전달 기억·적응 배치 (TB)", Plan2Adaptive),
    ("plan2c", "방안 2 + 커밋 매칭 (CF)", Plan2Commit),
    ("plan2plus", "방안 2+ = 적응 배치 + 커밋 매칭 (최종안)", Plan2Plus),
    ("plan2b3", "방안 2 + 고정 배치 3 (탐색)", Plan2Batch3),
    ("plan2abx", "방안 2 + 공격 적응 배치 (탐색)", Plan2AdaptiveX),
    ("plan2plusx", "방안 2+ 공격형 = 공격 배치 + 커밋 (탐색)", Plan2PlusX),
]
