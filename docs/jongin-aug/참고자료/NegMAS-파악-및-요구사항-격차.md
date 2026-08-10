# NegMAS 파악 및 요구사항 격차 정리

> **작성 목적:** [raw.md](raw.md)의 시나리오 구체화안(다자간 일정/계획 협상 + co-planning 확장)을
> 어떤 구조로 구현할지 판단하기 위해, NegMAS가 무엇을 제공하고 무엇을 제공하지 않는지를 확정한다.
> **표기 원칙:** NegMAS 설치본 소스에서 직접 확인한 **사실**과, 그로부터 도출한 **해석·산정**을 구분해 적는다.
> **확인 대상:** `negmas==0.15.7` (`poc/dp02-a2a-message-hints/requirements.txt` 기준 설치본 소스).
> 인용한 파일 경로는 모두 설치된 negmas 패키지 내부 경로다.

---

## 1. NegMAS가 제공하는 것 (사실)

| 구분 | API·기능 | 확인 위치 |
|---|---|---|
| 협상 의제 | `Issue`, `Outcome`, `CartesianOutcomeSpace`, `DiscreteCartesianOutcomeSpace`, `make_issue`, `make_os` | `outcomes/outcome_space.py` |
| 프로토콜 | `SAOMechanism` (Stacked Alternating Offers) | `sao/mechanism.py` |
| 다자 협상 | `max_n_agents` 파라미터. 협상 도중 참여(`dynamic_entry=True`)와 이탈(`ResponseType.LEAVE`, `allow_negotiators_to_leave`) 지원 | `sao/mechanism.py:48` docstring |
| 라운드별 응답 | `SAOResponse(response, outcome, data)` — `data`는 `dict[str, Any] \| None` | `sao/common.py:24` |
| Offer 부가 데이터 | `ExtendedOutcome(outcome, data)`. offer 없이 data만 보내는 것도 허용(`allow_none_with_data=True`) | `outcomes/common.py:44`, `sao/mechanism.py` |
| 유효성 강제 | `check_offers`, `enforce_issue_types`, `cast_offers`. OutcomeSpace 밖의 값은 무효 offer 처리 | `sao/mechanism.py` |
| 종료 조건 | `n_steps`(라운드 상한), `time_limit`(벽시계 상한), `step_time_limit`, 협상자별 개별 상한 | `sao/mechanism.py` |
| 선호 표현 | `LinearAdditiveUtilityFunction` 등. ufun은 로컬 객체이며 프로토콜이 전송하지 않음 | `preferences/` |
| **최적성 계산** | `pareto_frontier`, `nash_points`, `kalai_points`, `ks_points`, `max_welfare_points`, `calc_scenario_stats`→`ScenarioStats`, `calc_outcome_distances`→`OutcomeDistances`, `calc_outcome_optimality`→`OutcomeOptimality` | `preferences/ops.py` |
| 시나리오 난이도 | `opposition_level`, `conflict_level`, `winwin_level`, `rational_fraction` | `preferences/ops.py` |
| 동시 협상 조율 | `SAOController`, `SAOSyncController(global_ufun=…)` — 여러 협상의 offer를 모아 일괄 대응. `SAOSingleAgreementController` — 여러 협상 중 최대 1건만 합의 | `sao/controllers.py:40, 186, 502` |
| 공간 크기 제어 | `cardinality`, `is_finite`, `cardinality_if_discretized`, `to_discrete(levels, max_cardinality)`, `limit_cardinality`, `enumerate_or_sample`, `sample(n, with_replacement=False)` | `outcomes/outcome_space.py` |
| 로컬 제약 | `OutcomeSpace.add_constraint(Constraint)`, `satisfies_constraints(outcome)` — **로컬 전용이며 전송되지 않음** | `outcomes/outcome_space.py:154, 391` |
| 제안 제약 | `OfferingConstraint`, `LocalOfferingConstraint`, `AllOfferingConstraints`, `UniqueOffers`, `RepeatLastOfferOnly` — 무엇을 제안할 수 있는지에 대한 제약 | `gb/constraints/` |
| 후보 탐색 | `SamplingInverseUtilityFunction`(샘플링 기반), `PresortingInverseUtilityFunction`(전량 정렬 기반) | `preferences/inv_ufun.py:68, 253` |
| 시뮬레이션 환경 | `negmas.situated`의 `World`, `Agent`. `request_negotiation_about`, `run_negotiation`, `run_negotiations(..., all_or_none=)` | `situated/world.py:2891, 2996, 3110` |

### 1.1 최적성 지표의 구체 항목

`calc_outcome_optimality()`가 반환하는 `OutcomeOptimality`의 필드는 다음과 같다 (`preferences/ops.py:609`).

- `pareto_optimality` — 파레토 프론티어까지의 정규화 거리 기반 점수
- `nash_optimality` — Nash bargaining solution 근접도
- `kalai_optimality`, `modified_kalai_optimality`
- `ks_optimality`, `modified_ks_optimality` — Kalai-Smorodinsky 계열
- `max_welfare_optimality` — 사회후생 최대점 대비 비율

값은 0~1로 정규화되며 1.0이 해당 최적점에 위치함을 뜻한다.

`nash_points(ufuns: Sequence[UtilityFunction], frontier, …)` 및
`calc_scenario_stats(ufuns: tuple[UtilityFunction, ...] | list[UtilityFunction], …)`의 시그니처가
ufun **목록**을 받으므로, 2자 협상에 한정되지 않고 N자 협상에 그대로 적용된다.

---

## 2. NegMAS가 제공하지 않는 것 (사실 + 해석)

### G1. 세션 간 의존 관계를 표현하는 1급 구조가 없다

- **사실:** 하나의 `Mechanism`은 생성 시점에 OutcomeSpace가 고정되고, 합의 1건 또는 결렬로 종료한다.
- **사실:** `concurrent/chain.py`의 `ChainNegotiator`·`MultiChainNegotiator`는 파일 첫 줄에
  "a chain of bilateral negotiations"로 기술되어 있으며, **당사자**가 사슬을 이루는 공급망형 구조다.
  의제(agenda)가 사슬을 이루는 구조가 아니다.
- **사실:** `SAOSyncController`는 "manage multiple negotiators synchronously"로, 여러 협상을 **동시에** 조율한다.
  선행 협상의 합의 결과로 후행 협상의 의제를 만드는 경로는 없다.
- **사실:** `World.run_negotiations(...)`는 "Requests to run a set of negotiations simultaneously"로 동시 실행 배치다.
- **해석:** raw.md 8~12행의 co-planning(영화 합의 → 식사 협상, 오전 일정 합의 → 다음 일정 협상)에 해당하는
  **의제 의존 구조는 NegMAS 밖에서 우리가 만들어야 한다.**

### G2. constraint hint의 의미론이 없다

- **사실:** `SAOResponse.data`와 `ExtendedOutcome.data`는 타입 없는 `dict[str, Any]` 운반체다.
  docstring의 예시도 `{"text": "Price too high"}` 수준의 자유 데이터다.
- **사실:** `OutcomeSpace.add_constraint()`가 받는 `Constraint`는 로컬 OutcomeSpace의 유효성 판정에만 쓰이며,
  협상 메시지로 전송되지 않는다.
- **해석:** raw.md 14~15행의 `fixed`/`relaxable` 어휘, 검증 규칙, 수신 시 공간 축소 동작은
  **전부 우리 코드의 책임**이다. NegMAS는 이 데이터를 실어 나르는 통로만 제공한다.

### G3. 지연 생성(lazy) outcome space가 없다 — OOM이 기본 동작에 내재한다

- **사실:** `DiscreteCartesianOutcomeSpace.enumerate()`는 곱집합 전체를 실체화한다.
- **사실:** `Mechanism.discrete_outcomes()`는 열거 결과를 인스턴스에 캐시한다 (`mechanisms.py:1548-1557`).
- **사실:** `pareto_frontier` 계열과 `calc_scenario_stats`는 outcome 전량을 순회한다.
- **사실:** `PresortingInverseUtilityFunction`은 후보 선택을 위해 전체 outcome을 정렬해 보관한다.
  대안인 `SamplingInverseUtilityFunction`은 샘플링 기반이라 메모리 부담이 작다.
- **해석:** outcome space가 커지면 **NegMAS의 기본 경로를 그냥 쓰는 것만으로 OOM에 도달한다.**
  공간 상한을 강제하는 책임은 우리에게 있다.

### G4. 세션을 넘는 전역 효용 개념이 없다

- **사실:** ufun은 하나의 OutcomeSpace 위에 정의된다. `SAOSyncController(global_ufun=True)`는
  **동시 진행 중인** 협상 집합에 대한 공통 ufun을 가정하는 것이며, 이미 종료된 협상의 확정 결과를
  포함하는 개념이 아니다.
- **해석:** "하루 계획 전체에 대한 사용자 효용"을 유지하고 세션별 지역 최적과 구분하는 계층이 필요하다.

### G5. 최적성 지표는 런타임에서 계산할 수 없다

- **사실:** `calc_scenario_stats`·`calc_outcome_optimality`는 (a) **모든 참여자의 ufun**과
  (b) **outcome 전량 열거**를 입력으로 요구한다.
- **해석:** 상대 ufun은 원리적으로 비공개이고 전량 열거는 G3의 OOM 대상이므로,
  이 지표들은 **온디바이스 런타임에서 계산 불가능하며 오프라인 평가 도구로만 성립한다.**
  "정확도"를 QA로 세울 때 측정 위치를 반드시 명시해야 한다.

---

## 3. raw.md 요구사항 ↔ NegMAS 대응 격차

| # | raw.md 요구사항 (행) | NegMAS 대응 | 격차 |
|---|---|---|---|
| R-1 | 다자간 협상 (5행) | `SAOMechanism` + `max_n_agents` | **없음.** 그대로 사용 |
| R-2 | 모바일 온디바이스 동작 (6행) | 순수 Python 라이브러리 | **자원 상한 강제가 없음** → G3 |
| R-3 | 자사 기기 전용, 표준 준수 불필요 (7행) | `data` 필드가 자유 스키마 | **없음.** 자체 어휘 정의가 오히려 용이 |
| R-4 | co-planning: 선행 합의가 후행 협상의 입력 (8~10행) | 없음 | **전면 부재** → G1 |
| R-5 | 다양한 co-planning 시나리오 확장성 (12행) | 없음 | **전면 부재** → G1, G4 |
| R-6 | outcome space 비대 시 OOM (13행) | `to_discrete`, `limit_cardinality`, `sample` 등 도구는 있음 | **정책·강제 지점이 없음** → G3 |
| R-7 | offer에 constraint hint 동반, 수신자가 자기 공간 축소 (14~15행) | `ExtendedOutcome.data` 운반만 제공 | **의미론 전부 부재** → G2 |
| R-8 | 정확도 = 각자 ufun 상 최적해 도달 여부 (16~17행) | `calc_outcome_optimality` 등 계산 도구 완비 | **계산은 가능, 측정 위치가 문제** → G5 |
| R-9 | 협상 정상 종료는 핵심 QA 아님 (18행) | — | 해당 없음 |
| R-10 | 협상 소요 시간은 핵심 QA 아님 (19행) | `n_steps`, `time_limit` 제공 | 아래 §6 참조 |

---

## 4. OOM 규모 산정 (해석 — 가정 기반)

raw.md 9행의 "영화 → 식사" 예시에 issue 어휘 크기를 **가정**해 산정한다.
아래 어휘 크기는 원문에 없으며, 규모감을 잡기 위해 본 문서에서 임의로 설정한 값이다.

| 세션 | 가정한 의제 | outcome 수 |
|---|---|---|
| 영화 | slot(14) × theater(8) × movie(12) | 1,344 |
| 식사 | slot(14) × area(10) × cuisine(8) × price(6) | 6,720 |

- **순차 실행 시** 동시에 상주하는 최대 공간: **6,720**
- **결합 실행 시** (두 세션 의제를 하나의 공간으로 묶을 때): 1,344 × 6,720 = **9,031,680**

여행 계획처럼 오전·점심·오후·저녁 4개 세션이면 곱셈이 3회 더 붙는다.
CPython에서 outcome 1건은 최소 수십 바이트의 튜플 객체 + 리스트 포인터를 차지하므로,
900만 건 규모는 이미 수백 MB~GB 수준이며 모바일 백그라운드 프로세스에서 성립하지 않는다.

**결론:** 결합 공간 방식은 세션 수에 대해 곱셈으로 증가하므로, 공간 상한을 강제하는 지점이
설계에 명시적으로 존재해야 한다.

---

## 5. constraint hint 의미론 확정 (raw.md 15행 기준)

raw.md 15행이 규정하는 동작은 다음과 같다.

- Offer는 issue별 constraint hint를 동반할 수 있다.
- issue가 `fixed`로 표시되면, 수신자는 **해당 Offer에 실린 그 issue의 값**을 변경 불가 조건으로 해석한다.
- 이후 counter-offer는 그 값을 유지하고, `relaxable` issue의 값만 변경한다.
- fixed 값을 만족할 수 없으면 해당 Offer 또는 계획 분기를 거절한다.

**정리:** 힌트는 **수신자의 counter-offer 생성 범위**를 제한한다. 수락·거절 판단 자체는
여전히 수신자의 ufun과 내부 제약이 결정한다(만족 불가 시 거절). 두 층위가 분리되어 있다.

### 5.1 현재 PoC 코드와의 차이 (사실)

현행 `poc/dp02-a2a-message-hints`의 구현은 힌트를 **후보 정렬 가중치**로만 반영한다.
`src/dp03_a2a_hints/negotiators.py`의 `HintAwareNegotiator._proposal_score()`가
`opponent_constraint_hint_fit()` 결과에 `constraint_hint_weight`(기본 0.15)를 곱해 점수에 더한다.
후보 집합 자체는 줄지 않는다.

raw.md 기준으로는 fixed 표시된 issue 값을 **만족하지 않는 후보를 후보 집합에서 제외**해야 하며,
이는 raw.md 13~14행이 힌트를 **OOM 대책**으로 지목한 이유와 일치한다. 정렬 가중치로는 메모리가 줄지 않는다.

### 5.2 미정의 항목

raw.md 15행이 규정하지 않아 별도 결정이 필요한 사항.

- **H-1. 유효 범위:** 힌트가 해당 세션에만 유효한가, 계획 그래프의 후속 세션까지 승계되는가.
- **H-2. 철회:** 발신자가 이전에 보낸 fixed를 무르는 절차가 있는가, 아니면 세션 내 단조(monotonic)인가.
- **H-3. 충돌:** 서로 다른 참여자가 같은 issue에 서로 다른 fixed 값을 표시했을 때의 처리.
  N자 협상에서는 반드시 발생한다.
- **H-4. 공집합:** fixed 적용 결과 자신의 후보 집합이 비었을 때, 세션 결렬인가 계획 분기 거절인가.

---

## 6. 정확도·시간 QA 관련 정리

### 6.1 정확도 지표 (R-8)

NegMAS `calc_outcome_optimality()`의 반환 필드를 그대로 지표로 채택할 수 있다(§1.1).
시나리오 난이도는 `opposition_level`로 통제 변수화한다.

co-planning으로 확장하면 두 지표가 분리된다.

- **세션 최적성** — 각 세션의 파레토/Nash 최적성 (해당 세션 공간 기준)
- **계획 최적성** — 계획 전체를 하나의 결합 결과로 보고, 결합 공간의 파레토 프론티어 기준으로 계산

선행 세션을 확정한 뒤 후행으로 넘어가는 방식은 **세션 최적성은 높고 계획 최적성은 낮게** 나올 것으로
예상된다(해석). 이 격차 자체가 구조 선택의 정량적 근거가 된다.

**측정 위치:** G5에 따라 두 지표 모두 오프라인 합성 벤치마크(모든 참여자 ufun을 아는 환경)에서만
계산 가능하다. 기존 `poc/dp02-a2a-message-hints/src/dp03_a2a_hints/scenario_generator.py`가
이 역할을 수행하고 있어 재사용 가능하다.

### 6.2 협상 소요 시간 (R-10) — 부분 이견 (해석)

백그라운드 동작이므로 **사용자 체감 지연은 핵심 QA가 아니라는 판단에 동의**한다. 다만 두 가지가 남는다.

- **기한 내 완료 가능성:** 계획 그래프를 순차 실행하면 총 소요가 노드 수만큼 누적된다.
  계획에는 실효 기한이 있다(19시 영화를 18시까지 정하지 못하면 결과가 무가치).
  이는 지연 QA가 아니라 **기한 내 합의 도달 가능성**이며, 순차 실행 구조의 실질적 약점이다.
- **연산 자원:** 라운드당 후보 평가 비용은 시간이 아니라 연산·배터리 자원으로 계상되어야 하며,
  메모리와 함께 자원 QA에 남는다.

---

## 7. 구현 시 확인된 기존 코드 이슈 (사실)

`poc/dp02-a2a-message-hints/src/dp03_a2a_hints/negotiators.py`의 `_candidate_outcomes()`가
매 호출마다 `outcome_space.py`의 `enumerate_outcomes()`를 부른다. 이 함수는
`tuple(tuple(v) for v in product(*value_lists))`로 **곱집합 전체를 새로 실체화**한다.
협상자 수 × 라운드 수만큼 전체 공간 할당이 반복된다.

현재 실험 규모(수백 outcome)에서는 문제가 드러나지 않지만, §4의 co-planning 규모에서는
첫 라운드에 한계에 도달한다. co-planning 구조를 구현할 때 이 경로는 재설계 대상이다.

---

## 8. 근거·출처

- 설치본 소스 직접 확인: `negmas==0.15.7` (경로는 §1 표에 명시)
- NegMAS 공식 문서: https://negmas.readthedocs.io/en/stable/
- Advanced Negotiation (동시 협상·컨트롤러): https://negmas.readthedocs.io/en/v0.15.6/advanced_negotiation.html
- NegMAS GitHub: https://github.com/yasserfarouk/negmas

---

_본 문서는 사용자 지시(2026-08-08)로 작성되었다. 근거는 [raw.md](raw.md)와 negmas 0.15.7 설치본 소스다._
_구조 제안은 [co-planning-구조-초안.md](co-planning-구조-초안.md)에 분리해 둔다._
