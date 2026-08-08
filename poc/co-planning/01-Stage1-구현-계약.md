# Co-Planning PoC: 01 Stage 1 구현 계약

> [00-구현-계획.md](00-구현-계획.md)의 Stage 1을 착수하기 위해 필요한 결정을 확정한다.
> 범위는 단일 단계 협상 커널과 후보 공급기이며, 참여자는 2자로 고정한다.

---

## 1. 후보 열거 알고리즘

### 전제

- 효용 모델은 `linear_additive`로 한정한다.
- 제약은 **issue별 허용 값 집합**으로만 표현한다. hard constraint와 Stage 2의 `fixed` 조건 모두 이 형태다.
- 교차 issue 제약(한 issue의 값이 다른 issue의 허용 값을 바꾸는 형태)은 다루지 않는다.

### 절차

1. **사전 준비.** issue별로 값을 효용 기여도(`weight × value_score`) 내림차순 정렬한다. 제약에 걸리는 값은 이 목록에서 제외한다. 비용은 전체 값 개수의 합에 비례하며, 조합을 만들지 않는다.
2. **시작.** 각 issue의 1순위 값을 모은 조합이 효용 최댓값이다.
3. **확장.** 조합을 내보낼 때, 한 issue의 값만 한 순위 내린 조합들을 우선순위 큐에 넣는다.
4. **반복.** 큐에서 효용이 가장 큰 것을 꺼내 내보내고 3을 다시 적용한다.

결과는 효용 내림차순이며, 곱집합을 만들지 않는다.

### 중복 방지

1차 구현은 이미 큐에 넣은 조합의 인덱스를 집합에 기록한다. 집합 크기가 문제가 되면, 값을 내릴 issue를 제한하는 생성 규칙으로 교체한다. 규칙 방식은 집합이 필요 없는 대신 큐 크기가 커진다.

### 인터페이스

```
next_batch(limit, constraints, exclusions, context) -> list[Outcome]
```

| 인자 | 의미 |
|---|---|
| `limit` | 이번 호출에서 내보낼 최대 개수 (= K) |
| `constraints` | issue별 허용 값 집합. **변경되면 열거 상태를 초기화한다** |
| `exclusions` | 이미 제안하여 제외할 조합 |
| `context` | 단계 식별자 등 호출 맥락 |

`constraints` 변경 시 초기화가 필요한 이유는 값 목록 자체가 바뀌어 기존 큐의 순위 인덱스가 무효가 되기 때문이다. Stage 2에서 `fixed` 조건을 수신할 때 발생한다. 초기화 대신 큐에서 조건 불만족 항목만 제거하는 방식도 가능하며, 어느 쪽을 쓸지는 Stage 2에서 정한다. Stage 1에서는 `constraints`가 변하지 않으므로 영향이 없다.

`UFunConstraint`는 생성 후 방어적 검증에만 사용한다. 제약은 값 목록 단계에서 이미 적용된다.

---

## 2. 배치 요청 상한과 열거 상태 크기

### 값

| 항목 | 초기값 |
|---|---|
| K (배치 크기) | 200 |
| 라운드당 배치 요청 횟수 상한 | 3 |
| `n_steps` | 100 |

한 세션에서 내보내는 최대 후보 수 = `100 × 3 × 200 = 60,000`.

### 열거 상태

후보 공급기가 호출 사이에 유지하는 것은 세 가지다.

| 구성 | 크기 |
|---|---|
| issue별 정렬 목록 | 고정. 전체 값 개수의 합에 비례 |
| 우선순위 큐 | 내보낸 개수에 비례해 증가 |
| 중복 방지 집합 | 내보낸 개수에 비례해 증가 |

항목 1건을 인덱스 튜플과 효용값으로 약 100바이트로 보면, 60,000개 기준 큐와 집합을 합쳐 12MB 수준이다. §3의 예산 안에 들어간다.

### 라운드 동작

threshold 이상인 후보가 나올 때까지 배치를 요청하되 3회를 넘지 않는다. 3회 안에 없으면 그때까지 확인한 후보 중 유보값 이상인 최선을 제안하고, 그것도 없으면 제안하지 않는다.

위 세 값은 Stage 5의 측정 결과로 재산정한다.

---

## 3. 메모리 예산과 측정

### 판정선

**협상 세션 1건이 추가로 점유하는 메모리 50MB.**

이 값은 단말 프로파일링 결과가 아니라 PoC 판정을 위한 가정이다. 근거는 백그라운드 프로세스가 메모리 압박 시 우선 종료 대상이고, 같은 프로세스에 온디바이스 LLM과 프레임워크가 함께 올라간다는 점이다. 실제 단말 측정값으로 대체해야 한다.

### 측정 방법

`tracemalloc`으로 세션 시작부터 종료까지의 peak를 기록한다.

### 기준 수치

Python 3.9에서 5-issue 문자열 튜플 1건은 리스트 포인터를 포함해 88바이트다.

| outcome 수 | 후보 목록만 |
|---:|---:|
| 100,000 | 8.4 MB |
| 500,000 | 42.0 MB |
| 1,048,576 | 88.0 MB |

dp02 방식은 `(score, outcome)` 쌍 목록을 별도로 만들므로 실제 사용량은 위 값의 2배 이상이다.

---

## 4. 단일 단계 시나리오 스키마

```yaml
schema_version: coplan_stage.v1
scenario_id: S1-basic-625
issues:
  - name: slot
    values: [v1, v2, v3, v4, v5]
agents:
  - id: ppa_a
    private_profile:
      utility_model: linear_additive
      utility_weights: {slot: 0.4, area: 0.3, cuisine: 0.2, price: 0.1}
      value_scores:
        slot: {v1: 1.0, v2: 0.7, v3: 0.4, v4: 0.2, v5: 0.0}
      hard_constraints:
        - issue: slot
          allowed_values: [v1, v2, v3]
      reservation_value: 0.55
      concession_policy: {type: linear, start_threshold: 0.90, end_threshold: 0.55}
run_defaults:
  n_steps: 100
  batch_size: 200
  batch_calls_per_round: 3
```

dp02 스키마에서 제외하는 필드와 이유는 다음과 같다.

| 제외 필드 | 이유 |
|---|---|
| `capability`, `allowed_constraint_hint` | Stage 2에서 추가 |
| `privacy_labels` | 본 Stage의 측정 대상이 아님 |
| `expected_checks` | 종료 판정을 §6에서 직접 정의함 |
| `task_family`, `complexity_level`, `tension_pattern`, `variant_id` | 생성기의 축이므로 Stage 6에서 도입 |
| `generation_meta` | 수기 작성 시나리오이므로 불필요 |

---

## 5. 로그 필드

### EventLog (라운드별)

`step`, `actor`, `event_type`, `outcome`, `response_type`

### RunResult (세션별)

dp02에서 이식하는 필드: `run_id`, `scenario_id`, `agreement_success`, `agreement_outcome`, `wall_clock_ms`, `steps_to_agreement`, `utilities`, `failure_reasons`

본 PoC에서 추가하는 필드:

| 필드 | 의미 |
|---|---|
| `batch_call_count` | `next_batch` 호출 횟수 |
| `emitted_candidate_count` | 후보 공급기가 내보낸 총 개수 |
| `peak_candidate_count` | 동시에 보관한 후보 수의 최댓값 |
| `peak_bytes` | `tracemalloc` peak |
| `enumeration_reset_count` | `constraints` 변경으로 열거 상태를 초기화한 횟수 |

`enumeration_reset_count`는 Stage 1에서는 항상 0이며, Stage 2에서 의미를 갖는다.

---

## 6. Stage 1 종료 판정과 계획서 수정분

### 종료 판정 (개정)

| # | 판정 | 시나리오 |
|---|---|---|
| 1 | dp02 전수 열거 negotiator와 합의 결과가 일치한다 | 4 issue × 5 값 = 625 |
| 2 | 모든 실행에서 `peak_candidate_count ≤ 600` (K × 라운드당 배치 요청 횟수 상한) | 전체 |
| 3 | dp02 방식은 `peak_bytes`가 50MB를 초과하고, 후보 공급기 방식은 초과하지 않는다 | 5 issue × 16 값 = 1,048,576 |

판정 1은 dp02 negotiator가 실제로 실행되어야 하므로 소형 시나리오를 쓴다. 판정 3은 dp02 방식이 판정선을 넘어야 비교가 성립하므로 대형 시나리오를 쓴다.

### `00-구현-계획.md` 수정분

| 위치 | 수정 |
|---|---|
| §4 Stage 1 종료 판정 3항 | "5 issue × 10 값(=100,000)" → "5 issue × 16 값(=1,048,576)". 100,000은 8.4MB로 판정선에 미달하여 양쪽 모두 성공하고 비교가 성립하지 않는다 |
| §5 미결정 사항 | "배치 크기 K의 값"을 확정으로 변경 (200). "라운드당 배치 요청 횟수 상한"(3)과 "메모리 예산"(50MB) 항목 추가 |
| §6 예상 파일 구조 | `utility.py`, `negmas_preferences.py`, `validators.py`, `scenario_loader.py` 추가. §2.1에서 이식 대상으로 지정했으나 누락되어 있음 |

열거 알고리즘은 별도 모듈로 분리하지 않고 `candidate_space.py`에 둔다.

---

_본 문서는 사용자 지시(2026-08-08)로 작성되었다._
