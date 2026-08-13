"""composite 어댑터 — dp-composite-agenda 도메인(1안 seq vs 2안 pool)을 공통 계약으로.

nparty 어댑터와 같은 원칙: 도메인 지식은 여기서 끝나고, 프로토콜 구현은 `_vendor/`에
원본 그대로 둔다 (재작성하면 수치 차이의 원인을 가릴 수 없다).

## 이식하며 신설한 것

- **바이트 계측** — 원본 dpca에는 없었다. dp2와 **같은 규약**으로 신설
  (`_vendor/harness/comms.py` 참조). 규약이 다르면 두 실험의 바이트를 나란히 볼 수 없다.
- **관찰 기록** — CF 측정용. 2인 교대 제안이라 청중은 항상 상대 1인이다.

## 관점이 1개인 이유

dpca는 2인 교대 제안이라 **담당자가 곧 상대 참여자**다. dp2처럼 관점 2개
(참여자/담당자)로 나눌 대상이 없으므로 `participant` 하나만 보고한다.

## CF 측정 공간에 대한 정직한 한계

1안(seq)은 **축값**을 교환하고(`('sun',)`), 2안(pool)은 **전체 조합**을 교환한다
(`('sun','11:00','yeongdeungpo','mv3')`). 노출 깊이를 전체 조합 공간에서 재면 1안은
조합을 직접 드러내지 않으므로 낮게 나온다 — 이는 "전체 조합 선호가 직접 노출되지
않는다"는 사실의 반영이지만, **축 단위 선호 노출은 이 지표가 잡지 못한다.**
축 단위 노출을 재려면 별도 지표가 필요하며 이번 범위 밖이다. 그래서 조합 공간 기준
m과 함께 **교환 건수·축값 노출 수를 원자료로 병기**해 오독을 막는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Sequence

from ...qa.contract import (
    NO_AGREEMENT,
    ObservationEvent,
    Outcome,
    SessionResult,
    SweepPoint,
)
from ...qa.ru import deep_size
from ._vendor.common.generators import Value
from ._vendor.common.oracle import analyze
from ._vendor.common.profiles import TruthProfile, build_truth_profiles, truth_utility
from ._vendor.common.rules import build_hard_rules, build_participant_hard, build_soft_rules
from ._vendor.common.scenario import Axis, Scenario, load_scenario
from ._vendor.harness.runner import RunResult, run_one

DATASETS = Path(__file__).resolve().parents[4] / "datasets" / "composite"
SCENARIOS = DATASETS / "scenarios"


@dataclass(frozen=True)
class PlanSpec:
    name: str
    label: str


#: 비교 대상 — `docs/07-DP후보안/sunwoo/DP-복합의제-협상방식.md`의 두 안.
#: 정본(seq·pool)과 개선판(seq2·pool2)을 모두 등록하되, 기본 비교는 최종 문서와 같이
#: 1안=seq2 · 2안=pool 이다.
PLANS: dict[str, PlanSpec] = {
    "seq": PlanSpec("seq", "1안 정본 — 의제별 순차 협상"),
    "seq2": PlanSpec("seq2", "1안 개선 — 소프트 반영 + 최종확인 백트랙"),
    "pool": PlanSpec("pool", "2안 정본 — 개인별 후보군 압축 후 복합 협상"),
    "pool2": PlanSpec("pool2", "2안 개선 — 유효-only 조건부 확장"),
    "full": PlanSpec("full", "baseline 전수 나열 (c≈1 앵커 · CF 참조 프로토콜)"),
}

#: CF의 e₂ 앵커로 쓰는 참조 프로토콜. 전체 조합을 그대로 교환하는 평범한 양자 SAO라
#: "협상의 정의상 피할 수 없는 교환량"에 가장 가깝다.
E2_REFERENCE_PLAN = "full"


def scenario_paths() -> list[Path]:
    return sorted(SCENARIOS.glob("*.yaml"))


def load(name_or_path: str | Path, **kw) -> Scenario:
    p = Path(name_or_path)
    if not p.exists():
        matches = [q for q in scenario_paths() if q.stem.startswith(str(name_or_path))]
        if not matches:
            raise FileNotFoundError(f"시나리오를 찾을 수 없다: {name_or_path}")
        p = matches[0]
    return load_scenario(p, **kw)


def load_fixture(path: str | Path) -> Scenario:
    """fixture JSON → `Scenario`. yaml 시나리오와 달리 **값이 실체화**되어 있다.

    선택적으로 `"profiles"` 절을 지원한다 — 참여자별 weights·scores·home_region·
    initial_threshold를 명시 고정(frozen)해 시드 생성을 우회한다. 함정(변별 장치)을
    구조가 아니라 효용 수준에서 정밀하게 심어야 하는 정본 데이터셋(final 트랙)용이다.
    `build_truth_profiles()`가 `frozen_profiles`를 읽는다.
    """
    import json as _json

    raw = _json.loads(Path(path).read_text(encoding="utf-8"))
    axes = [
        Axis(a["name"], a.get("generator", ""),
             [Value(v["name"], dict(v.get("attrs", {}))) for v in a["values"]])
        for a in raw["axes"]
    ]
    sc = Scenario(
        meta=raw["meta"],
        axes=axes,
        dependencies=raw.get("dependencies", []),
        participants=raw["participants"],
        agent_view=raw.get("agent_view", {}),
        judge=raw.get("judge", {"expected": raw["meta"].get("expected", "agreement")}),
    )
    profs = raw.get("profiles")
    if profs:
        sc.frozen_profiles = [
            TruthProfile(
                weights=dict(p["weights"]),
                scores={ax: dict(vals) for ax, vals in p["scores"].items()},
                home_region=p.get("home_region", "gangnam"),
                initial_threshold=float(p["initial_threshold"]),
            )
            for p in profs
        ]
    return sc


class CompositePreference:
    """진실 프로파일을 계약 `Preference`로. 효용은 soft 규칙까지 반영한 실제 값이다.

    `truth_utility`는 축→**Value 객체** 매핑을 받는다. 계약의 `Outcome`은 해시 가능한
    정규형(축명·값명 문자열 튜플)이므로 여기서 되돌려 준다 — 이 변환을 빠뜨리면
    효용이 조용히 0이 되어 달성률이 전부 0으로 나온다.
    """

    __slots__ = ("pid", "index", "initial_threshold", "_truth", "_soft", "_space",
                 "_lookup", "_feasible", "_ranked_cache")

    def __init__(self, pid: str, index: int, truth, soft, space: Sequence[Outcome],
                 lookup: dict, feasible=None) -> None:
        self.pid = pid
        self.index = index
        self.initial_threshold = float(truth.initial_threshold)
        self._truth = truth
        self._soft = soft
        self._space = space
        self._lookup = lookup      # (축명, 값명) -> Value
        self._feasible = feasible  # 하드 제약 통과 여부 — ranked()가 제안 가능한 것만 담게
        self._ranked_cache: list[Outcome] | None = None

    def _as_map(self, outcome: Outcome) -> dict | None:
        try:
            return {k: self._lookup[(k, v)] for k, v in outcome}
        except (KeyError, TypeError, ValueError):
            return None

    def utility(self, outcome: Outcome) -> float:
        mapping = self._as_map(outcome)
        if mapping is None:
            return 0.0
        return float(truth_utility(self._truth, self.index, mapping, self._soft))

    def ranked(self) -> list[Outcome]:
        """**제안 가능한** 후보만의 선호 순위표.

        하드 제약을 어기는 조합은 애초에 제안하지 않으므로 순위표에 넣으면 안 된다.
        넣으면 CF의 유효 후보 집합(노출 깊이의 분모)이 부풀어 깊이가 과소평가된다 —
        실제로 그 버그가 있었다. FC의 후보 공간(`Case.candidates()`)은 24 §1.3
        정의대로 전수를 유지하므로 달성률은 영향받지 않는다.
        """
        if self._ranked_cache is None:
            space = ([o for o in self._space if self._feasible(o)]
                     if self._feasible else list(self._space))
            self._ranked_cache = sorted(space, key=lambda o: (-self.utility(o), repr(o)))
        return list(self._ranked_cache)

    def rank_of(self, outcome: Outcome) -> int | None:
        try:
            return self.ranked().index(outcome) + 1
        except ValueError:
            return None


def _outcome_key(mapping: dict) -> Outcome:
    """축→값 매핑을 해시 가능한 정규형으로. 계약의 `Outcome`은 Hashable이면 된다."""
    return tuple(sorted((str(k), str(v)) for k, v in mapping.items()))


@dataclass
class CompositeCase:
    """계약 `Case` — 후보 공간은 축값의 곱집합.

    조합이 크면 전수 열거가 메모리에 안 들어가므로 `candidates()`는 generator다.
    다만 FC의 x\\* 계산은 전수를 요구하므로 `enumeration_limit`을 넘으면 거부한다 —
    조용히 표본으로 바꾸면 달성률이 틀린 값이 되기 때문이다.
    """

    case_id: str
    scenario: Scenario
    enumeration_limit: int = 200_000
    _prefs: list[CompositePreference] | None = field(default=None, init=False, repr=False)
    _space: list[Outcome] | None = field(default=None, init=False, repr=False)
    _feasible_cached: object = field(default=None, init=False, repr=False)

    @property
    def n_issues(self) -> int:
        return len(self.scenario.axes)

    def _space_list(self) -> list[Outcome]:
        if self._space is None:
            size = self.scenario.space_size()
            if size > self.enumeration_limit:
                raise ValueError(
                    f"조합 {size:,}개가 열거 한도 {self.enumeration_limit:,}를 넘는다 — "
                    "표본으로 바꾸면 달성률이 틀린 값이 되므로 거부한다")
            axes = self.scenario.axes
            out: list[Outcome] = []

            def walk(i: int, acc: dict) -> None:
                if i == len(axes):
                    out.append(_outcome_key(acc))
                    return
                for v in axes[i].values:
                    acc[axes[i].name] = v.name
                    walk(i + 1, acc)
                acc.pop(axes[i].name, None)

            walk(0, {})
            self._space = out
        return self._space

    def candidates(self) -> Iterator[Outcome]:
        return iter(self._space_list())

    @property
    def preferences(self) -> list[CompositePreference]:
        if self._prefs is None:
            truths = build_truth_profiles(self.scenario)
            homes = [t.home_region for t in truths]
            soft = build_soft_rules(self.scenario, homes)
            space = self._space_list()
            lookup = {(a.name, v.name): v for a in self.scenario.axes for v in a.values}
            feasible = self._feasibility_predicate()
            self._prefs = [CompositePreference(f"P{i}", i, t, soft, space, lookup, feasible)
                           for i, t in enumerate(truths)]
        return self._prefs

    @property
    def pids(self) -> list[str]:
        return [p.pid for p in self.preferences]

    def _feasibility_predicate(self):
        """하드 제약 통과 판정 — 순위표에서 제안 불가 조합을 걸러내는 데 쓴다."""
        axes = {a.name: {v.name: v for v in a.values} for a in self.scenario.axes}
        rules = build_hard_rules(self.scenario) + build_participant_hard(self.scenario)

        def ok(outcome: Outcome) -> bool:
            try:
                mapping = {k: axes[k][v] for k, v in outcome}
            except (KeyError, TypeError, ValueError):
                return False
            return all(r(mapping) for r in rules)

        return ok

    def is_feasible(self, outcome: Outcome) -> bool:
        """FC 유효 후보의 하드 필터 (24 §1.2) — `fc.valid_candidates`가 읽는다.

        이 필터가 없으면 실행 불가능한 조합이 x*(분모)에 들어가, 결렬이 정답인
        케이스에서 정확히 결렬해도 달성률 < 1이 된다 (2026-08-13 발견·수정 —
        S08 계열의 기존 수치가 이 결함을 포함한다).
        """
        if self._feasible_cached is None:
            self._feasible_cached = self._feasibility_predicate()
        return self._feasible_cached(outcome)

    def hard_violations(self, outcome: Outcome | str) -> list[str]:
        """도메인 규칙 위반 — 계약에 없어 측정기가 볼 수 없으므로 어댑터가 검사한다."""
        if outcome == NO_AGREEMENT:
            return []
        axes = {a.name: a for a in self.scenario.axes}
        mapping = {}
        for k, v in outcome:
            axis = axes.get(k)
            if axis is None:
                return ["알 수 없는 축"]
            found = next((val for val in axis.values if val.name == v), None)
            if found is None:
                return ["알 수 없는 축값"]
            mapping[k] = found
        rules = build_hard_rules(self.scenario) + build_participant_hard(self.scenario)
        return [] if all(r(mapping) for r in rules) else ["하드 제약 위반 합의"]


def oracle_space_bytes(case: CompositeCase) -> int:
    """채점 오라클이 든 전체 후보 공간 + 순위표 1인분 — **단말 점유가 아니다** (참고 지표).

    구 `base_bytes` — RU B안 개정(PL 확정 2026-08-13) 전에는 이것을 공통 기저로
    총점유에 물렸다. 그러나 1안(축값)·2안(압축 풀)은 전체 공간을 만들지 않는 것이
    설계의 요점이고, 이 공간을 실제로 물화하는 것은 FC 채점 인프라(oracle)다 —
    단말 기저에 넣으면 방안 간 RU 변별이 구조적으로 0이 된다. extra에 참고로 남긴다."""
    space = case._space_list()
    total = deep_size(space)
    if case.preferences:
        total += deep_size(case.preferences[0].ranked())
    return total


def _to_outcome(payload, axis_names: Sequence[str]):
    """교환된 offer를 계약 `Outcome` 정규형으로.

    dpca의 offer는 축 순서대로 나열된 **원시 튜플**이다(`('sat','17:00',…)`). 후보 공간은
    `(('date','sat'), …)` 정규형이므로 변환하지 않으면 어떤 후보와도 매칭되지 않아
    노출 깊이가 조용히 0이 된다 — 실제로 그 버그가 있었다.

    1안(seq)의 offer는 **축값 1개**라 전체 조합으로 환원할 수 없다. 그대로 두면 조합
    공간에서 매칭되지 않는데, 이는 "전체 조합 선호를 직접 드러내지 않는다"는 사실의
    반영이다 (모듈 docstring의 한계 설명 참조).
    """
    if isinstance(payload, dict):
        return _outcome_key(payload)
    if isinstance(payload, (tuple, list)) and len(payload) == len(axis_names):
        return _outcome_key(dict(zip(axis_names, payload)))
    return tuple(payload) if isinstance(payload, list) else payload


def _events(run: RunResult, pids: Sequence[str],
            axis_names: Sequence[str]) -> list[ObservationEvent]:
    """관찰 기록 → 계약 이벤트. 2인 교대 제안이라 청중은 항상 상대 1인이다."""
    out: list[ObservationEvent] = []
    for obs in run.observations:
        actor = obs["actor"]
        audience = tuple(p for p in pids if p != actor)
        out.append(ObservationEvent(
            sweep=obs.get("sweep", 1), round=obs.get("round", 1), actor=actor,
            kind=obs["kind"], outcome=_to_outcome(obs.get("outcome"), axis_names),
            audience=audience))
    return out


def run_session(
    scenario: Scenario,
    plan: str,
    case: CompositeCase | None = None,
    light: bool = False,
    **kw,
) -> tuple[SessionResult, CompositeCase]:
    """전략 1회 실행 → 계약 세션 + 케이스.

    `light=True`는 **후보 공간을 열거하지 않는** 경량 실행이다 — FC 채점 오라클을
    만들지 않으므로 조합이 열거 한도를 넘는 대상(S11·대형 fixture)도 RU·TB를 잴 수
    있다. 반환된 세션은 FC 채점에 쓸 수 없다 (`measure(qa=("ru","tb"))`와 함께 쓸 것).
    """
    if plan not in PLANS:
        raise KeyError(f"알 수 없는 방안: {plan} (등록: {sorted(PLANS)})")
    case = case or CompositeCase(scenario.id, scenario)
    if not light:
        case.preferences      # 채점 오라클(x*·순위표)을 협상 구간 밖에서 구축

    # 기저 = 축 정의 + 자기 선호 표현 1인분 (24 §2.8 — RU B안, PL 확정 2026-08-13).
    # 전체 조합 공간 사본을 기저로 물리지 않는다: 1안(축값)·2안(압축 풀)은 전체 공간을
    # 만들지 않는 것이 설계의 요점이고, 공간을 실제로 만드는 것은 채점 오라클이다.
    # 방안이 실제로 만든 후보 구조는 전략 계측(materialized)이 잰다 — 스윕 경로
    # (`run_sweep_point`)와 같은 기저 공식이라 두 경로의 수치가 정합한다.
    base = deep_size(scenario.axes) + deep_size(scenario.participants) // max(
        1, scenario.n_participants)

    # 피크는 원본 러너가 협상 구간에서 이미 tracemalloc으로 잰다. 밖에서 한 번 더
    # 감싸면 내부 stop()이 추적을 꺼 버려 0이 나온다 — 원본 값을 그대로 쓴다.
    # 실물화 후보 구조는 협상 구간 안에서 만들어지므로 피크에 포함된다 (이중 계상 없음).
    run = run_one(scenario, plan, **kw)
    peak = int(run.peak_kib * 1024)

    # light 모드에서는 case.pids(→ preferences → 공간 열거)를 피한다 — 벤더 규약과 동일
    pids = ([f"P{i}" for i in range(scenario.n_participants)] if light else case.pids)
    agreement = NO_AGREEMENT if run.agreement is None else _outcome_key(run.agreement)
    session = SessionResult(
        plan=plan,
        participants=pids,
        agreement=agreement,
        rounds=run.rounds,
        sweeps=1,
        phases=run.phases,
        messages=run.messages,
        bytes=run.bytes,
        # 효용 평가 호출 수 — `AgentBeliefs.utility()` 실측 카운트 (24 §4.4-a).
        # 예전에는 `참여자 수 × 후보 수` 공식이었는데 방안에 의존하지 않아 eval 항이
        # 방안을 구분하지 못했다 (seq2·pool의 eval_ms가 똑같이 5.04ms로 나왔다).
        # nparty 쪽은 처음부터 실측이라, 같은 항을 두 시나리오가 다르게 재고 있었다.
        eval_calls=run.eval_calls,
        events=_events(run, pids, [a.name for a in scenario.axes]),
        peak_bytes=peak,
        base_bytes=base,
        materialized_bytes=run.materialized_bytes,
        extra={
            "wall_ms": run.wall_ms,          # 참고 관측 — 실행 머신 의존이라 판정 제외
            "proposals": run.proposals,
            "exchanged_items": len(run.observations),
            "scenario_id": scenario.id,
            # 채점 오라클이 든 전체 공간 사본 — 단말 점유가 아니라 측정 인프라 비용 (참고).
            # light 모드는 오라클을 만들지 않으므로 이 값도 없다 (열거 자체가 목적 밖)
            **({} if light else
               {"oracle_space_mb": round(oracle_space_bytes(case) / (1024 * 1024), 4)}),
            **run.extra,
        },
    )
    return session, case


def run_sweep_point(scenario: Scenario, plan: str, n_issues: int, **kw) -> SweepPoint:
    """SC-의제 스윕용 **경량 실행** — 후보 공간을 열거하지 않는다.

    스윕은 규모별 피크만 필요한데, `run_session`은 FC를 위해 후보를 전수 열거한다.
    축이 10개면 조합이 900만을 넘어 열거만으로 프로세스가 죽는다 — 실제로 그랬다.
    여기서는 프로토콜만 돌리고 피크를 읽는다.
    """
    if plan not in PLANS:
        raise KeyError(f"알 수 없는 방안: {plan} (등록: {sorted(PLANS)})")
    run = run_one(scenario, plan, **kw)
    # 기저 1인분 근사 (24 §5 — 판정은 단말 총 점유): 복합 의제의 단말 기저는 조합 표가
    # 아니라 **축 수준 표현**(축 정의 + 자기 선호 스펙)이다 — 조합 열거 없이 계산 가능.
    base = deep_size(scenario.axes) + deep_size(scenario.participants) // max(
        1, scenario.n_participants)
    return SweepPoint(
        scale=max(1, scenario.space_size()),
        peak_bytes=int(run.peak_kib * 1024),
        base_bytes=base,
        agreed=run.agreement is not None,
        n_issues=n_issues,
    )


def oracle_report(scenario: Scenario):
    """정답 x\\*·R̄ — dpca 자체 oracle. FC 교차 검산에 쓴다."""
    return analyze(scenario)
