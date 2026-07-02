# DP03 A2A 협상 메시지 구조 PoC: 03 결정론 NegMAS 구현계획

> 본 문서는 [02-측정-프로토콜](./02-측정-프로토콜.md)의 Track A를 구현하기 위한 계획이다.
> 범위는 `A1_DET_OFFER_ONLY`, `A2_DET_HINT_AWARE`, `A3_DET_FALLBACK`의 최소 구현이며, LLM 포함 Track B는 다루지 않는다.

---

## 1. 목적

결정론 Track A의 목적은 LLM 변동성을 제거한 상태에서 `preference_hint` 유무가 협상 수렴과 합의 품질에 주는 영향을 분리해 측정하는 것이다.

구현해야 할 비교는 다음 세 가지다.

| 실험군 | 목적 |
|---|---|
| `A1_DET_OFFER_ONLY` | 순수 NegMAS 메시지만으로 협상했을 때의 기준선 |
| `A2_DET_HINT_AWARE` | 동일 전략에 hint 활용만 추가했을 때의 변화 측정 |
| `A3_DET_FALLBACK` | hint 미지원 상대와 협상할 때 후보 A처럼 정상 퇴화하는지 검증 |

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
| hint 위치 | NegMAS OutcomeSpace가 아니라 PoC runner의 envelope metadata |
| LLM | 본 단계 제외 |
| 기존 PoC | `poc/dp03-privacy` 데이터, 코드, 리포트 재사용 금지 |

NegMAS 공식 문서 기준으로 `SAOMechanism`은 `outcome_space`, `issues`, `outcomes`, `n_steps`, `time_limit` 등을 입력으로 받을 수 있고, `trace`, `full_trace`, `extended_trace`, `offers`, `state` 같은 실행 이력 접근점을 제공한다. 또한 최신 문서에서는 SAO 계열 controller/negotiator가 `propose`와 `respond` 확장 지점을 가진다는 점을 확인할 수 있다.

단, NegMAS는 버전별 API 변화가 있으므로 구현 시작 시점에 설치 버전을 고정하고, `SAONegotiator`의 실제 method signature를 smoke test로 확인한다.

---

## 3. 구현 범위

### 포함

| 모듈 | 역할 |
|---|---|
| scenario loader | YAML scenario를 읽고 내부 모델로 변환 |
| outcome builder | `domain.issues`를 Cartesian product outcome 목록으로 변환 |
| utility evaluator | private profile 기반 utility 계산 |
| offer-only negotiator | hint 없이 offer/accept 판단 |
| hint-aware negotiator | 동일 정책에 hint 기반 후보 정렬만 추가 |
| fallback gate | capability 미지원 시 hint를 보내지 않고 offer-only 경로로 전환 |
| runner | scenario와 실험군을 조합해 NegMAS 협상 실행 |
| logger | run result, event log, metric input 생성 |
| validator | outcome, utility, hint, fallback 규칙 검증 |

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

실제 구현 단계에서 다음 구조를 제안한다. 본 문서 작성 시점에는 아직 생성하지 않는다.

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
      logging.py
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
  requirements.txt 또는 pyproject.toml
```

파일을 한 번에 모두 만들 필요는 없다. 최소 구현은 `models.py`, `outcome_space.py`, `utility.py`, `negotiators.py`, `runner.py`, `validators.py`부터 시작한다.

---

## 5. 데이터 모델

### 내부 모델

YAML을 그대로 dict로 흘려보내지 않고, 내부 모델로 변환한다.

| 모델 | 주요 필드 |
|---|---|
| `Scenario` | `scenario_id`, `task_family`, `domain`, `agents`, `privacy_labels`, `expected_checks` |
| `IssueSpec` | `name`, `type`, `values`, `order`, `hintable` |
| `AgentSpec` | `id`, `role`, `capability`, `private_profile`, `allowed_hint_projection` |
| `PrivateProfile` | `utility_weights`, `value_scores`, `hard_constraints`, `reservation_value`, `concession_policy` |
| `HintProjection` | `issue_preferences`, `issue_flexibility`, `hard_constraints`, `concession_phase_allowed` |
| `RunConfig` | `experiment_group`, `n_steps`, `seed`, `hint_enabled` |
| `RunResult` | `agreement`, `rounds`, `utilities`, `failure_reasons`, `hint_metrics` |

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

이 방식은 NegMAS issue class 세부 API에 덜 의존한다. `SAOMechanism`이 `outcomes` list를 받을 수 있다는 공식 API를 우선 사용한다.

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

`A2_DET_HINT_AWARE`는 offer-only와 동일한 기본 정책을 사용하되, 상대의 구조화 hint를 offer 후보 정렬에만 반영한다.

후보 B의 개선이 나오더라도 "더 강한 negotiator" 때문이 아니라 "상대가 공개한 제한된 hint" 때문이어야 한다.

### hint 입력

1차 구현에서 hint는 NegMAS 내부 outcome이 아니라 runner가 negotiator에 제공하는 metadata로 둔다.

```yaml
opponent_hint:
  issue_preferences:
    slot: high
    area: medium
  issue_flexibility:
    budget_band: low
  hard_constraints:
    - slot
  concession_phase: normal
```

### hint fit 점수

상대의 value preference는 공개되지 않는다. 따라서 hint-aware negotiator는 "상대가 어느 issue를 중요하게 보는지"만 반영한다.

```text
candidate_score =
  own_utility(candidate)
  + hint_weight * opponent_hint_fit(candidate)
```

`opponent_hint_fit`은 다음처럼 계산한다.

| hint | 반영 방식 |
|---|---|
| `issue_preferences[issue] = high` | 해당 issue 값을 자주 바꾸지 않도록 현재 상대 offer의 같은 issue value와 일치하면 가점 |
| `issue_preferences[issue] = medium` | 낮은 가점 |
| `issue_preferences[issue] = low` | 가점 없음 |
| `issue_flexibility[issue] = low` | 현재 상대 offer의 해당 issue value를 유지하면 가점 |
| `issue_flexibility[issue] = high` | 해당 issue를 양보 가능한 축으로 보고 own utility 중심 선택 |
| `hard_constraints`에 issue 포함 | 해당 issue의 상대 최근 offer value를 유지하면 큰 가점 |

중요한 제한은 다음이다.

- hint만 보고 상대의 허용 value를 만들어내지 않는다.
- `hard_constraints`가 issue 이름만 공개하므로, 상대의 최근 offer value를 임시 anchor로만 사용한다.
- hint fit이 own threshold를 무너뜨리면 안 된다.
- hint fit은 후보 정렬에만 쓰고 accept/reject의 최소 조건은 own utility와 hard constraint로 유지한다.

### 기본 파라미터

| 파라미터 | 초안 |
|---|---:|
| `hint_weight` | 0.15 |
| `high_preference_bonus` | 1.0 |
| `medium_preference_bonus` | 0.5 |
| `low_preference_bonus` | 0.0 |
| `hard_constraint_issue_bonus` | 2.0 |

수치는 임시값이며, 결과 해석에는 "hint를 어느 정도 반영했는가"라는 민감도 분석이 필요하다. 1차 구현에서는 `hint_weight = 0.0`, `0.15`, `0.30` 세 값을 옵션으로 둘 수 있다.

---

## 9. Fallback Gate

후보 B는 상대 capability가 확인된 경우에만 hint를 보낸다.

```text
hint_enabled =
  local.capability.preference_hint == true
  and remote.capability.preference_hint == true
  and local.hint_schema_version == remote.hint_schema_version
```

| 조건 | 동작 |
|---|---|
| 양쪽 모두 `preference_hint: true` | `A2_DET_HINT_AWARE` 실행 가능 |
| 한쪽이라도 `false` | `A3_DET_FALLBACK`으로 실행 |
| schema version 불일치 | `A3_DET_FALLBACK`으로 실행 |
| fallback 중 hint 생성 | `fallback_violation` |

fallback은 성능 최적화가 아니라 개인정보와 상호운용성 검증 경로다. fallback에서 hint가 한 번이라도 전송되면 후보 B의 hard failure로 기록한다.

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

NegMAS trace는 offer 이력 확인에 유용하지만, 본 PoC의 모든 로그를 대신하지 않는다. hint는 NegMAS OutcomeSpace 밖 metadata이므로 runner가 별도 event log를 남겨야 한다.

| 로그 | 출처 |
|---|---|
| offer/accept/reject | NegMAS trace 및 negotiator callback |
| hint 생성/전송 여부 | PoC runner |
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
| hint field가 schema 밖 | `hint_schema_violation` |
| hint value가 `high/medium/low` 밖 | `hint_schema_violation` |
| fallback 중 hint 전송 | `fallback_violation` |
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
| `hint_message_count` | event log |
| `hint_sensitivity_score` | hint metric calculator |
| `fallback_violation_count` | validator |

Metric 계산은 runner 내부에 섞지 않는다. runner는 raw event와 run_result를 만들고, metrics module이 집계한다.

---

## 13. 테스트 계획

### 단위 테스트

| 테스트 | 내용 |
|---|---|
| `test_outcome_space.py` | issue value의 Cartesian product가 예상 개수와 순서를 갖는지 |
| `test_utility.py` | linear utility, reservation margin, hard constraint 검증 |
| `test_hints.py` | hint projection, hint sensitivity score, fallback leak 검증 |
| `test_negotiators.py` | offer-only와 hint-aware의 후보 정렬 차이 검증 |
| `test_validators.py` | invalid outcome, forbidden hint, PII label 실패 검증 |

### 통합 테스트

| 테스트 | 내용 |
|---|---|
| `test_runner_smoke.py` | sample scenario 1개로 A1/A2/A3 실행 |
| `test_fallback_smoke.py` | hint 미지원 scenario에서 hint가 0건인지 확인 |
| `test_metric_summary.py` | run_result에서 summary table 생성 확인 |

### NegMAS smoke test

구현 첫 단계에서 별도 smoke test를 둔다.

| 확인 | 이유 |
|---|---|
| 설치된 NegMAS 버전 출력 | API 변화 추적 |
| `SAOMechanism(outcomes=..., n_steps=...)` 생성 가능 여부 | OutcomeSpace 연결 확인 |
| custom negotiator method signature 확인 | `propose/respond` 구현 안정성 |
| trace/full_trace 접근 가능 여부 | metric 산출 가능성 확인 |
| invalid offer check 동작 확인 | validator와 중복 방지 |

NegMAS v0.15 계열에서 API 변경이 있었으므로, 구현계획의 method 이름은 실제 설치 버전에서 확인한 뒤 코드에 반영한다.

---

## 14. 구현 순서

### Step 1: 최소 환경 고정

- Python 버전 확인
- `negmas` 설치 버전 선택
- `requirements.txt` 또는 `pyproject.toml` 초안 작성
- NegMAS smoke test 작성

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
- deterministic tie-breaker

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
- hint metrics
- summary table

### Step 6: 120개 scenario 생성기로 연결

- 이 단계는 `04` 또는 별도 구현 문서에서 다룬다.

---

## 15. 주요 리스크와 대응

| 리스크 | 대응 |
|---|---|
| NegMAS 버전별 API 차이 | 버전 pin, smoke test, wrapper layer 사용 |
| hint-aware가 너무 강한 전략이 됨 | offer-only와 동일 threshold 유지, hint는 후보 정렬에만 사용 |
| hard constraint hint를 과대 해석 | issue 이름만 anchor로 사용하고 value는 추정하지 않음 |
| outcome tuple/dict 변환 오류 | canonical issue order와 round-trip test |
| fallback에서 hint 유출 | fallback gate와 validator를 모두 둠 |
| Pareto 계산 비용 증가 | 1차 scenario는 issue 3~5개, value 3개 수준으로 제한 |
| metric과 runner 결합 | raw log와 metric 계산을 분리 |

---

## 16. 구현 완료 기준

Track A 구현은 아래 조건을 만족하면 완료로 본다.

- sample scenario에서 `A1_DET_OFFER_ONLY`, `A2_DET_HINT_AWARE`, `A3_DET_FALLBACK`이 모두 실행된다.
- `run_result`, `event_log`, `metric_summary`가 생성된다.
- fallback scenario에서 hint 전송이 0건이다.
- invalid outcome과 hard constraint 위반이 validator에서 잡힌다.
- 같은 seed와 scenario로 실행했을 때 결과가 재현된다.
- 기존 `poc/dp03-privacy` 코드 또는 데이터에 의존하지 않는다.

---

## 17. 근거

- [00-실험-계약](./00-실험-계약.md): 결정론 Track A와 LLM Track B의 역할 분리.
- [01-시나리오-스키마](./01-시나리오-스키마.md): scenario, private profile, allowed hint projection 스키마.
- [02-측정-프로토콜](./02-측정-프로토콜.md): Track A 실험군과 측정 지표.
- [NegMAS SAOMechanism API](https://negmas.readthedocs.io/en/v0.11.4/api/negmas.sao.SAOMechanism.html): `outcomes`, `n_steps`, `trace`, `full_trace`, `is_valid` 등 구현 연결점 확인.
- [NegMAS negotiators documentation](https://negmas.readthedocs.io/en/latest/modules/negotiators.html): SAO 계열 확장 지점으로 `propose`, `respond`를 사용하는 구조 확인.
- [NegMAS releases](https://github.com/yasserfarouk/negmas/releases): v0.15 계열 변경 사항과 버전 pin 필요성 확인.

---

## 18. 다음 단계

다음 작업은 구현을 시작하기 전에 둘 중 하나를 선택하는 것이다.

| 선택지 | 설명 |
|---|---|
| `04-결정론-구현-스캐폴딩.md` 작성 | 실제 코드 생성 전 파일 구조, CLI, 테스트 명령까지 한 번 더 고정 |
| 코드 스캐폴딩 시작 | `src/`, `tests/`, sample scenario, requirements를 만들고 NegMAS smoke test부터 작성 |

제안은 코드 스캐폴딩 시작이다. `00`~`03`에서 계약과 구현 방향은 충분히 고정되었으므로, 다음에는 작은 sample scenario 2개와 NegMAS smoke test로 실제 API를 확인하는 편이 낫다.
