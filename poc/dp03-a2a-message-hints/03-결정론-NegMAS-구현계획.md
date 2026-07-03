# DP03 A2A 협상 메시지 구조 PoC: 03 결정론 NegMAS 구현계획

> 본 문서는 [02-측정-프로토콜](./02-측정-프로토콜.md)의 Track A를 구현하기 위한 계획이다.
> 범위는 `A1_DET_OFFER_ONLY`, `A2_DET_HINT_AWARE`, `A3_DET_FALLBACK`의 최소 구현이며, LLM 포함 Track B는 다루지 않는다.

---

## 1. 목적

결정론 Track A의 목적은 LLM 변동성을 제거한 상태에서 `constraint_hint` 유무가 협상 수렴과 합의 품질에 주는 영향을 분리해 측정하는 것이다.

구현해야 할 비교는 다음 세 가지다.

| 실험군 | 목적 |
|---|---|
| `A1_DET_OFFER_ONLY` | 순수 NegMAS outcome만으로 협상했을 때의 기준선 |
| `A2_DET_HINT_AWARE` | 동일 전략에 constraint hint 활용만 추가했을 때의 변화 측정 |
| `A3_DET_FALLBACK` | constraint hint 미지원 상대와 협상할 때 후보 A처럼 정상 퇴화하는지 검증 |

본 단계에서 중요한 것은 "가장 똑똑한 negotiator"를 만드는 것이 아니다. 후보 A/B의 차이가 메시지 구조에서만 나오도록, 두 negotiator의 차이를 의도적으로 작게 유지해야 한다.

---

## 2. 구현 전제

| 항목 | 결정 |
|---|---|
| 협상 프레임워크 | NegMAS SAO |
| 협상 형태 | 1:1 bilateral 협상 |
| 입력 데이터 | `01-시나리오-스키마.md`를 만족하는 synthetic scenario |
| utility model | `linear_additive` |
| OutcomeSpace | scenario의 `domain.issues`에서 생성 |
| constraint hint 위치 | NegMAS OutcomeSpace가 아니라 `ExtendedOutcome.data["constraint_hint"]` |
| LLM | 본 단계 제외 |
| 기존 PoC | `poc/dp03-privacy` 데이터, 코드, 리포트 재사용 금지 |

PoC는 `negmas==0.15.7`을 기준으로 한다. 이 버전의 `SAONegotiator.propose()`는 `Outcome`, `ExtendedOutcome`, `None`을 반환할 수 있고, `SAOState.current_data`와 `new_data`를 통해 직전 메시지의 metadata를 조회할 수 있다. 따라서 constraint hint 전달을 위해 NegMAS 내부 프로토콜을 수정하지 않는다.

단, NegMAS는 버전별 API 변화가 있으므로 설치 버전을 고정하고, `SAONegotiator`의 실제 method signature를 smoke test로 확인한다.

---

## 3. 구현 범위

### 포함

| 모듈 | 역할 |
|---|---|
| scenario loader | YAML scenario를 읽고 내부 모델로 변환 |
| outcome builder | `domain.issues`를 Cartesian product outcome 목록으로 변환 |
| utility evaluator | private profile 기반 utility 계산 |
| offer-only negotiator | hint 없이 offer/accept 판단 |
| hint-aware negotiator | 동일 정책에 constraint hint 기반 후보 정렬만 추가 |
| fallback gate | capability 미지원 시 constraint hint를 보내지 않고 offer-only 경로로 전환 |
| runner | scenario와 실험군을 조합해 NegMAS 협상 실행 |
| logger | run result, event log, metric input 생성 |
| validator | outcome, utility, constraint hint, fallback 규칙 검증 |

### 제외

| 제외 항목 | 이유 |
|---|---|
| LLM negotiator | Track B에서 별도 구현 |
| 120개 scenario 생성기 | 다음 구현 단계에서 작성 |
| 결과 리포트 자동 생성 | metric runner 이후 단계 |
| N-party 협상 | 1차 PoC는 1:1 비교 |
| NegMAS 내부 프로토콜 수정 | 본 DP의 비교 대상이 아님 |

---

## 4. 예상 파일 구조

현재 Track A 최소 구현은 다음 구조를 사용한다.

```text
poc/dp03-a2a-message-hints/
  src/
    dp03_a2a_hints/
      __init__.py
      models.py
      scenario_loader.py
      outcome_space.py
      utility.py
      hints.py
      negotiators.py
      runner.py
      validators.py
      metrics.py
  tests/
    test_utility.py
    test_outcome_space.py
    test_hints.py
    test_negotiators.py
    test_runner_smoke.py
  scenarios/
    samples/
  results/
    .gitkeep
  requirements.txt
```

---

## 5. 데이터 모델

### 내부 모델

YAML을 그대로 dict로 흘려보내지 않고, 내부 모델로 변환한다.

| 모델 | 주요 필드 |
|---|---|
| `Scenario` | `scenario_id`, `task_family`, `domain`, `agents`, `privacy_labels`, `expected_checks` |
| `IssueSpec` | `name`, `type`, `values`, `order`, `constraint_hintable` |
| `AgentSpec` | `id`, `role`, `capability`, `private_profile`, `allowed_constraint_hint` |
| `PrivateProfile` | `utility_weights`, `value_scores`, `hard_constraints`, `reservation_value`, `concession_policy` |
| `ConstraintHintPolicy` | `schema_version`, `anchor`, `issue_constraints` |
| `ConstraintHintMessage` | `schema_version`, `anchor`, `issue_constraints` |
| `RunConfig` | `experiment_group`, `n_steps`, `repeat_id`, `constraint_hint_weight` |
| `RunResult` | `agreement`, `rounds`, `utilities`, `failure_reasons`, `constraint_hint_metrics` |

### Outcome 표현

NegMAS에는 tuple outcome을 넘기고, PoC 내부에서는 dict outcome을 유지한다.

```text
dict outcome:
  {"slot": "saturday_lunch", "area": "midpoint"}

tuple outcome:
  ("saturday_lunch", "midpoint")
```

issue 순서는 `domain.issues`의 배열 순서를 canonical order로 사용한다.

| 함수 | 역할 |
|---|---|
| `to_tuple(outcome_dict, issues)` | dict outcome을 NegMAS용 tuple로 변환 |
| `to_dict(outcome_tuple, issues)` | NegMAS tuple을 metric/log용 dict로 변환 |
| `enumerate_outcomes(issues)` | 모든 가능한 outcome tuple 생성 |

이 방식은 metric/log 계산에서 issue 이름을 보존하기 위한 것이다. NegMAS에는 `make_issue()`와 `make_os()`로 만든 OutcomeSpace를 넘기고, negotiator 내부에서는 동일 canonical order의 tuple outcome을 사용한다.

---

## 6. Utility Evaluator

### 계산 규칙

```text
utility(agent, outcome) =
  sum(weight[issue] * value_scores[issue][value])
```

단, hard constraint를 위반하면 수락 불가로 판단한다.

| 함수 | 반환 |
|---|---|
| `utility(profile, outcome)` | 0.0~1.0 utility |
| `violates_hard_constraint(profile, outcome)` | bool |
| `is_acceptable(profile, outcome, threshold)` | bool |
| `reservation_margin(profile, outcome)` | `utility - reservation_value` |

### Threshold 계산

협상 진행에 따라 수락 threshold를 낮춘다.

```text
progress = current_step / max_steps
threshold = start_threshold - progress * (start_threshold - end_threshold)
threshold = max(threshold, reservation_value)
```

`boulware`, `conceder`는 schema에 남겨두되, 1차 구현은 `linear`부터 시작한다. 다른 concession policy는 테스트가 안정화된 뒤 확장한다.

---

## 7. Offer-only Negotiator

### 목적

`A1_DET_OFFER_ONLY`의 기준 negotiator다. 상대 hint, 상대 utility 추정, 자연어 설명을 사용하지 않는다.

### propose 규칙

1. 전체 outcome을 자신의 utility 기준으로 정렬한다.
2. 현재 threshold 이상이고 hard constraint를 만족하는 후보만 남긴다.
3. 이미 자신이 제안한 outcome은 후순위로 둔다.
4. 남은 후보 중 utility가 가장 높은 outcome을 제안한다.
5. 후보가 없으면 reservation value 이상 후보 중 최선 outcome을 제안한다.
6. 그래도 없으면 `None` 또는 no-response 정책을 따른다.

### respond 규칙

1. 상대 offer가 OutcomeSpace 밖이면 reject한다.
2. hard constraint를 위반하면 reject한다.
3. 현재 threshold 이상이면 accept한다.
4. threshold 미만이지만 reservation value 이상이고 마지막 구간이면 accept 가능하다.
5. 그 외에는 reject한다.

### 결정론 보장

동일 utility 후보가 여러 개면 다음 순서로 tie-break한다.

1. canonical tuple order
2. scenario seed 기반 stable hash
3. issue value order

랜덤 선택은 하지 않는다.

---

## 8. Hint-aware Negotiator

### 목적

`A2_DET_HINT_AWARE`는 offer-only와 동일한 기본 정책을 사용하되, 상대의 구조화 constraint hint를 offer 후보 정렬에만 반영한다.

후보 B의 개선이 나오더라도 "더 강한 negotiator" 때문이 아니라 "상대가 공개한 제한된 constraint hint" 때문이어야 한다.

### constraint hint 전달

1차 구현에서 constraint hint는 NegMAS OutcomeSpace의 issue가 아니다. offer와 함께 전송되는 metadata로 둔다.

```yaml
ExtendedOutcome:
  outcome:
    slot: saturday_lunch
    area: midpoint
    budget_band: medium
    notice_period: one_day
  data:
    constraint_hint:
      schema_version: constraint_hint.v1
      anchor: offered_outcome
      issue_constraints:
        slot: fixed
        notice_period: relaxable
```

수신 negotiator는 `SAOState.current_data["constraint_hint"]`를 읽어 상대의 직전 offer에 붙은 constraint hint를 복원한다.

### constraint hint fit 점수

상대의 value preference나 utility score는 공개되지 않는다. 따라서 hint-aware negotiator는 `fixed`와 `relaxable`이 가리키는 제한된 제약 단서만 후보 정렬에 반영한다.

```text
candidate_score =
  own_utility(candidate)
  + constraint_hint_weight * opponent_constraint_hint_fit(candidate)
```

`opponent_constraint_hint_fit`은 다음처럼 계산한다.

| constraint hint | 반영 방식 |
|---|---|
| `issue_constraints[issue] = fixed` | candidate의 해당 issue 값이 상대 직전 offer 값과 같으면 큰 가점, 다르면 감점 |
| `issue_constraints[issue] = relaxable` | candidate의 해당 issue 값이 상대 직전 offer 값과 다르면 낮은 가점 |
| issue 누락 | 공개하지 않은 것으로 보고 점수에 반영하지 않음 |

중요한 제한은 다음이다.

- constraint hint만 보고 상대의 전체 허용 value 목록을 만들어내지 않는다.
- `fixed`는 `anchor=offered_outcome` 기준으로만 해석한다.
- constraint hint fit이 own threshold를 무너뜨리면 안 된다.
- constraint hint fit은 후보 정렬에만 쓰고 accept/reject의 최소 조건은 own utility와 hard constraint로 유지한다.
- `relaxable`은 "바꿔도 됨"이지 "반드시 바꿔야 함"이 아니다.

### 기본 파라미터

| 파라미터 | 초안 |
|---|---:|
| `constraint_hint_weight` | 0.15 |
| `fixed_match_bonus` | 3.0 |
| `fixed_mismatch_penalty` | -3.0 |
| `relaxable_change_bonus` | 0.5 |

수치는 임시값이며, 결과 해석에는 "constraint hint를 어느 정도 반영했는가"라는 민감도 분석이 필요하다. 1차 구현에서는 `constraint_hint_weight = 0.0`, `0.15`, `0.30` 세 값을 옵션으로 둘 수 있다.

---

## 9. Fallback Gate

후보 B는 상대 capability가 확인된 경우에만 constraint hint를 보낸다.

```text
constraint_hint_enabled =
  local.capability.constraint_hint == true
  and remote.capability.constraint_hint == true
  and local.constraint_hint_schema_version == "constraint_hint.v1"
  and remote.constraint_hint_schema_version == "constraint_hint.v1"
  and scenario.privacy_labels.external_constraint_hint_allowed == true
```

| 조건 | 동작 |
|---|---|
| 양쪽 모두 `constraint_hint: true`이고 schema version 일치 | `A2_DET_HINT_AWARE` 실행 가능 |
| 한쪽이라도 `false` | `A3_DET_FALLBACK`으로 실행 |
| schema version 불일치 | `A3_DET_FALLBACK`으로 실행 |
| scenario가 외부 constraint hint를 금지 | `A3_DET_FALLBACK`으로 실행 |
| fallback 중 constraint hint 생성 | `fallback_violation` |

fallback은 성능 최적화가 아니라 개인정보와 상호운용성 검증 경로다. fallback에서 constraint hint가 한 번이라도 전송되면 후보 B의 hard failure로 기록한다.

---

## 10. Runner 흐름

### 단일 run 흐름

```text
1. scenario 로드
2. schema validation
3. OutcomeSpace tuple 목록 생성
4. private profile별 utility evaluator 생성
5. experiment_group에 맞는 negotiator 생성
6. SAOMechanism 생성
7. negotiator 2개 추가
8. negotiation 실행
9. NegMAS trace와 runner event log 수집
10. agreement 검증
11. metrics input 생성
12. run_result 저장
```

### 실험군별 실행

| 실험군 | negotiator 조합 |
|---|---|
| `A1_DET_OFFER_ONLY` | `OfferOnlyNegotiator` vs `OfferOnlyNegotiator` |
| `A2_DET_HINT_AWARE` | `HintAwareNegotiator` vs `HintAwareNegotiator` |
| `A3_DET_FALLBACK` | capability 결과에 따라 `OfferOnlyNegotiator`로 강제 |

### NegMAS trace 보완

NegMAS trace는 offer 이력 확인에 유용하지만, 본 PoC의 모든 로그를 대신하지 않는다. constraint hint는 NegMAS OutcomeSpace 밖 metadata이므로 runner가 별도 event log를 남겨야 한다. 단, 실제 전송 경로는 `ExtendedOutcome.data`와 `SAOState.current_data`를 사용하므로 NegMAS `full_trace`의 data 필드에서도 확인할 수 있어야 한다.

| 로그 | 출처 |
|---|---|
| offer/accept/reject | NegMAS trace 및 negotiator callback |
| constraint hint 생성/전송 여부 | `ExtendedOutcome.data`, `SAOState.current_data`, PoC event log |
| validation 결과 | validator |
| utility와 threshold | PoC negotiator |
| fallback 판단 | fallback gate |

---

## 11. Validator

### 사전 검증

협상 실행 전 scenario를 검증한다.

| 검증 | 실패 시 |
|---|---|
| issue 개수와 complexity 일치 | scenario invalid |
| utility weight 합계 1.0 | scenario invalid |
| value_scores 범위 0.0~1.0 | scenario invalid |
| hard constraint value 유효성 | scenario invalid |
| agreement region 존재 여부 | expected check와 불일치 시 scenario invalid |
| PII label 모두 false | scenario invalid |

### 실행 중 검증

| 검증 | 실패 reason |
|---|---|
| offer가 OutcomeSpace에 없음 | `invalid_outcome` |
| offer가 actor 자신의 hard constraint 위반 | `hard_constraint_violation` |
| constraint hint field가 schema 밖 | `constraint_hint_schema_violation` |
| constraint hint value가 `fixed/relaxable` 밖 | `constraint_hint_schema_violation` |
| fallback 중 constraint hint 전송 | `fallback_violation` |
| 사유·원문·PII 포함 | `prohibited_content` |

### 사후 검증

| 검증 | 실패 reason |
|---|---|
| agreement 없음 | `no_agreement` |
| agreement가 한쪽 reservation 미만 | `reservation_violation` |
| agreement가 hard constraint 위반 | `hard_constraint_violation` |
| expected fallback 미동작 | `fallback_violation` |

---

## 12. Metric 산출

결정론 Track A에서 최소 산출할 metric은 다음이다.

| metric | 산출 위치 |
|---|---|
| `agreement_success` | runner 사후 검증 |
| `rounds_to_agreement` | NegMAS trace + runner round counter |
| `atomic_actions_to_agreement` | event log |
| `utility_a`, `utility_b` | utility evaluator |
| `joint_utility` | metrics |
| `utility_min` | metrics |
| `fairness_gap` | metrics |
| `pareto_dominated` | 전체 OutcomeSpace 열거 |
| `pareto_joint_gap` | 전체 OutcomeSpace 열거 |
| `constraint_hint_message_count` | event log |
| `constraint_hint_sensitivity_score` | constraint hint metric calculator |
| `fallback_violation_count` | validator |

Metric 계산은 runner 내부에 섞지 않는다. runner는 raw event와 run_result를 만들고, metrics module이 집계한다.

---

## 13. 테스트 계획

### 단위 테스트

| 테스트 | 내용 |
|---|---|
| `test_outcome_space.py` | issue value의 Cartesian product가 예상 개수와 순서를 갖는지 |
| `test_utility.py` | linear utility, reservation margin, hard constraint 검증 |
| `test_hints.py` | constraint hint 생성, sensitivity score, fallback leak 검증 |
| `test_negotiators.py` | offer-only와 hint-aware의 후보 정렬 차이 검증 |
| `test_validators.py` | invalid outcome, forbidden constraint hint, PII label 실패 검증 |

### 통합 테스트

| 테스트 | 내용 |
|---|---|
| `test_runner_smoke.py` | sample scenario 1개로 A1/A2/A3 실행 |
| `test_fallback_smoke.py` | constraint hint 미지원 scenario에서 constraint hint가 0건인지 확인 |
| `test_metric_summary.py` | run_result에서 summary table 생성 확인 |

### NegMAS smoke test

구현 첫 단계에서 별도 smoke test를 둔다.

| 확인 | 이유 |
|---|---|
| 설치된 NegMAS 버전 출력 | API 변화 추적 |
| `SAOMechanism(outcome_space=..., n_steps=...)` 생성 가능 여부 | OutcomeSpace 연결 확인 |
| custom negotiator method signature 확인 | `propose/respond` 구현 안정성 |
| trace/full_trace 접근 가능 여부 | metric 산출 가능성 확인 |
| invalid offer check 동작 확인 | validator와 중복 방지 |

NegMAS v0.15 계열에서 API 변경이 있었으므로, method 이름과 반환 타입은 실제 설치 버전에서 확인한 뒤 코드에 반영한다.

---

## 14. 현재 구현 상태

### Step 1: 최소 환경 고정

- Python 버전 확인
- `requirements.txt`에 `negmas==0.15.7` 고정
- NegMAS API smoke 확인

### Step 2: scenario와 utility 기반 구현

- `models.py`
- `scenario_loader.py`
- `outcome_space.py`
- `utility.py`
- sample scenario 2개

### Step 3: 결정론 negotiator 구현

- `OfferOnlyNegotiator`
- `HintAwareNegotiator`
- threshold calculator
- deterministic tie-breaker는 canonical tuple order와 재제안 penalty로 처리

### Step 4: runner와 validator 구현

- experiment group 실행
- fallback gate
- event log
- run result
- validator

### Step 5: metrics 구현

- agreement metrics
- utility metrics
- Pareto metrics
- constraint hint metrics
- summary table

### Step 6: 120개 scenario 생성기로 연결

- 미구현. 이 단계는 별도 구현 문서에서 다룬다.

---

## 15. 주요 리스크와 대응

| 리스크 | 대응 |
|---|---|
| NegMAS 버전별 API 차이 | 버전 pin, smoke test, wrapper layer 사용 |
| hint-aware가 너무 강한 전략이 됨 | offer-only와 동일 threshold 유지, constraint hint는 후보 정렬에만 사용 |
| constraint hint를 과대 해석 | `anchor=offered_outcome` 기준으로만 해석하고 전체 허용 값 목록은 추정하지 않음 |
| outcome tuple/dict 변환 오류 | canonical issue order와 round-trip test |
| fallback에서 constraint hint 유출 | fallback gate와 validator를 모두 둠 |
| Pareto 계산 비용 증가 | 1차 scenario는 issue 3~5개, value 3개 수준으로 제한 |
| metric과 runner 결합 | raw log와 metric 계산을 분리 |

---

## 16. 구현 완료 기준

Track A 구현은 아래 조건을 만족하면 완료로 본다.

- sample scenario에서 `A1_DET_OFFER_ONLY`, `A2_DET_HINT_AWARE`, `A3_DET_FALLBACK`이 모두 실행된다.
- `run_result`, `event_log`, `metric_summary`가 생성된다.
- fallback scenario에서 constraint hint 전송이 0건이다.
- invalid outcome과 hard constraint 위반이 validator에서 잡힌다.
- 같은 seed와 scenario로 실행했을 때 결과가 재현된다.
- 기존 `poc/dp03-privacy` 코드 또는 데이터에 의존하지 않는다.

---

## 17. 근거

- [00-실험-계약](./00-실험-계약.md): 결정론 Track A와 LLM Track B의 역할 분리.
- [01-시나리오-스키마](./01-시나리오-스키마.md): scenario, private profile, allowed constraint hint 스키마.
- [02-측정-프로토콜](./02-측정-프로토콜.md): Track A 실험군과 측정 지표.
- [requirements.txt](./requirements.txt): Track A PoC의 NegMAS 버전을 `negmas==0.15.7`로 고정.
- [src/dp03_a2a_hints/negotiators.py](./src/dp03_a2a_hints/negotiators.py): `ExtendedOutcome.data["constraint_hint"]` 송신과 `SAOState.current_data` 수신 구현.
- [tests/test_runner_smoke.py](./tests/test_runner_smoke.py): A1/A2/A3 실행과 constraint hint 전달 경로 검증.

---

## 18. 다음 단계

다음 작업은 내부 hard constraint 처리 방식을 NegMAS preference/constraint 객체로 옮길지 검토하는 것이다.

| 선택지 | 설명 |
|---|---|
| 현재 방식 유지 | private hard constraint를 PoC `utility.py`와 negotiator 로직에서 직접 검증 |
| NegMAS constraint adapter 도입 | 내부 hard constraint를 NegMAS `UtilityFunction`/constraint 계층으로 옮기고, 공개 metadata는 `constraint_hint`로 유지 |

제안은 별도 작은 리팩토링 단계로 NegMAS constraint adapter를 검토하는 것이다. 이 단계의 목표는 공개 `constraint_hint`와 내부 `UFunConstraint`의 경계를 코드에서도 분명히 하는 것이다.
