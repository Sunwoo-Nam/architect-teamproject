# 다자 합의 프로토콜 Benchmark Set

이 폴더는 `poc/dp2-nparty`의 두 프로토콜 방안이 공통으로 사용하는 정적 협상 사례를 보관한다.
두 방안은 동일한 후보 목록과 동일한 참여자 프로파일로 실행되어야 한다.

현재 단계에서는 정적 파일 계약만 정의한다. 실제 케이스와 `BenchmarkLoader` 구현은 대표 사례를 검토한 뒤 추가한다.

## 책임 경계

Benchmark Set이 제공하는 값:

- 협상 후보 ID 목록
- 참여자별 후보 utility
- 참여자별 initial threshold
- 사례 분류와 설명을 위한 메타데이터

Benchmark Set이 제공하지 않는 값:

- revised threshold 갱신 방식
- 최대 바퀴와 라운드 실행 순서
- 동률 해소 규칙
- 특정 프로토콜 방안의 예상 합의 결과
- 유효 후보, 최적 후보, 결렬 utility, Total Utility 달성률

마지막 항목들은 `src/dp2_nparty/measures/fc.py`가 케이스 입력으로부터 계산한다.

## 파일 형식

- 케이스 1건은 JSON 파일 하나로 작성한다.
- JSON은 [`schema/benchmark-case-v1.schema.json`](schema/benchmark-case-v1.schema.json)을 따른다.
- 후보 ID와 참여자 ID는 문자열로 제한한다.
- `NO_DEAL`은 측정기가 별도로 추가하는 예약 결과이므로 후보나 utility map에 넣지 않는다.
- 직접 작성한 정적 케이스에는 seed가 필요하지 않다.

권장 저장 구조:

```text
cases/
  conformance/   프로토콜 불변조건과 경계값 확인
  functional/    Total Utility 달성률 비교 표본
  scalability/   참여자 수 증가 비교 family
```

## 케이스와 코드의 대응

JSON 최상위 필드는 `src/dp2_nparty/benchmark.py`의 `BenchmarkCase`에 직접 대응한다.

| JSON 필드 | 코드 | 의미 |
|---|---|---|
| `case_id` | `BenchmarkCase.case_id` | Benchmark Set 전체에서 유일한 ID |
| `candidates` | `BenchmarkCase.candidates` | 협상에 제출할 수 있는 후보 ID 목록 |
| `profiles` | `BenchmarkCase.profiles` | JSON profile을 `domain.Profile`로 변환한 목록 |
| `meta` | `BenchmarkCase.meta` | track, scenario type, 설명과 분류표 |

각 profile은 `domain.Profile`에 대응한다.

| JSON 필드 | 코드 | 의미 |
|---|---|---|
| `pid` | `Profile.pid` | 케이스 안에서 유일한 참여자 ID |
| `utilities` | `Profile.utilities` | 모든 후보에 대한 0-1 utility map |
| `initial_threshold` | `Profile.initial_threshold` | 고정 수락 바닥선이자 결렬 시 utility |

## 예시

```json
{
  "case_id": "C-001-common-top",
  "candidates": ["A", "B", "C"],
  "profiles": [
    {
      "pid": "P0",
      "utilities": {"A": 0.9, "B": 0.6, "C": 0.2},
      "initial_threshold": 0.4
    },
    {
      "pid": "P1",
      "utilities": {"A": 0.9, "B": 0.5, "C": 0.3},
      "initial_threshold": 0.4
    },
    {
      "pid": "P2",
      "utilities": {"A": 0.9, "B": 0.7, "C": 0.1},
      "initial_threshold": 0.4
    }
  ],
  "meta": {
    "schema_version": "benchmark-case.v1",
    "track": "conformance",
    "scenario_type": "common_top",
    "expected_no_deal": false,
    "description": "모든 참여자가 후보 A를 가장 높게 평가한다."
  }
}
```

## 메타데이터

필수 필드:

- `schema_version`: 현재 값은 `benchmark-case.v1`
- `track`: `conformance`, `functional`, `scalability` 중 하나
- `scenario_type`: 사례의 의도를 나타내는 영문 식별자
- `expected_no_deal`: 모든 참여자의 initial threshold 이상인 실후보가 하나도 없는지 나타내는 분류표
- `description`: 사람이 사례의 의도를 검토할 수 있는 한글 설명

Scalability 사례의 선택 필드:

- `family_id`: 참여자 수만 다르게 구성한 연관 사례 묶음
- `common_feasible_count`: 모든 참여자의 initial threshold 이상인 실후보 수

`expected_no_deal`과 `common_feasible_count`는 채점기에 주는 정답이 아니다. 표본 구성을 확인하고 정적 파일의 오류를 발견하기 위한 검증용 메타데이터다.

## 정합성 검증

JSON Schema가 검사하는 항목:

- 필수 필드와 자료형
- ID 문자열 형식
- 후보 중복과 `NO_DEAL` 사용 여부
- 최소 참여자 수 3명
- utility와 initial threshold의 0-1 범위
- 허용된 track과 schema version

JSON Schema만으로 검사할 수 없어 로더 또는 별도 검증기가 확인해야 하는 항목:

- Benchmark Set 전체의 `case_id` 중복
- 케이스 안의 `pid` 중복
- 모든 profile의 utility key가 `candidates`와 정확히 일치하는지
- `expected_no_deal`과 실제 initial threshold 계산 결과가 일치하는지
- `common_feasible_count`가 실제 계산 결과와 일치하는지
- 같은 Scalability family가 의도한 통제 조건을 유지하는지

검증은 정적 데이터의 정합성만 확인한다. 라운드 수, 합의 결과, 메시지 수는 동료 PoC 실행기의 검증 대상이다.

## 표본 구성 요구

- Functional Correctness 표본에는 initial threshold 이상인 실후보가 없는 결렬 사례를 일정 비율 포함한다.
- 참여자 수 Scalability 표본은 `N ∈ {3, 4, 5, 6, 8, 10}`을 사용한다.
- 같은 Scalability family는 N과 무관하게 공통 feasible 후보 수를 고정하여 난이도 교락을 통제한다.
- 두 프로토콜 방안은 같은 `case_id`의 후보와 프로파일을 변경 없이 사용한다.
