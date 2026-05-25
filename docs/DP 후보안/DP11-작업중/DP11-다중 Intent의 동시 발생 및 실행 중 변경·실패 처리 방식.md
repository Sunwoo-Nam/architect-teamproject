# DP 11. 다중 Intent의 동시 발생 및 실행 중 변경·실패 처리 방식

## 1. 풀고자 하는 문제

IDS가 Intent를 감지하고 기존 Intent와의 관계를 `병합·대체·차단·취소·무관`으로 분류해 Orchestrator에 전달하면, MAF는 활성 Intent 집합을 기준으로 실행 흐름을 재구성해야 한다.

이때 Orchestrator와 Meta Agent Runtime은 다음을 결정해야 한다.

- 여러 Intent와 Task 중 무엇을 병렬 실행할 것인가
- 병합·대체·차단·취소를 기존 실행 상태에 어떻게 반영할 것인가
- 이미 수행된 Task 결과와 외부 side-effect를 어디까지 재사용·무효화·보상할 것인가
- 실패한 Task 또는 Intent를 어디서부터 재개할 것인가

핵심 결정은 **다중 Intent 실행 상태를 전역적으로 통합 관리할 것인가, Intent별로 격리 관리하고 충돌만 전역 조정할 것인가**이다.

## 2. 아키텍처적 난제

다중 Intent 처리는 단순 큐잉 문제가 아니다. 새 Intent가 들어오는 시점에는 기존 Task가 이미 실행 중이거나, 일부 결과가 생성되었거나, 예약 hold·캘린더 임시 블록 같은 외부 효과가 발생했을 수 있다.

또한 Android 온디바이스 중심 구조에서는 민감한 실행 상태와 외부 효과 기록을 단말 내부에 보관해야 한다. 반면 Orchestrator는 서버 LLM 기반 계획 수립을 담당하므로, 계획 수립과 실제 실행 상태 소유권을 분리해야 한다.

## 3. 해결 방안 1: 전역 실행 원장 기반 통합 제어 구조

모든 Intent, Task, ResourceLease, SideEffectRecord를 하나의 전역 Local Execution Store에서 관리한다. Meta Agent Runtime은 이 전역 실행 원장을 기준으로 활성 Intent 집합과 실행 가능한 Task를 계산한다.

### 구조

- `IntentLedger`: Intent 생성, 병합, 대체, 차단, 취소, 재개 이벤트 기록
- `IntentState`: 현재 활성 Intent와 constraint version
- `TaskState`: Task 상태, dependency, 실행 조건, 결과 참조
- `ResourceLease`: 캘린더, 예약 슬롯, Tool, 화면 등 공유 자원 점유 상태
- `SideEffectRecord`: 외부 효과, 보상 action, idempotency key 기록
- `ExecutionProjection`: 현재 실행 가능한 Task 집합 계산용 상태

### 처리 방식

병합이 발생하면 전역 원장에서 기존 Intent의 constraint를 갱신하고, 영향을 받는 Task를 무효화하거나 재실행 후보로 올린다. 병렬 실행은 모든 활성 Intent의 Task를 한 번에 놓고 dependency와 ResourceLease 충돌 여부를 판단한다. 취소·실패 발생 시에도 전역 원장에서 영향을 받는 Task와 side-effect를 찾아 보상 또는 재개한다.

### 장점

복잡한 Intent 관계를 한 기준 상태에서 판단할 수 있다. 병합, 대체, 취소, 실패 회복이 같은 상태 모델 위에서 처리되므로 정합성이 높다. replay, postmortem, 감사 로그 구성에도 유리하다.

### 약점

전역 Runtime과 저장소가 커진다. 모든 Intent 관계가 한 제어 지점으로 모이므로 구현 복잡도가 높고, 병렬 실행이 많아질수록 원장 갱신과 충돌 판단 비용이 증가할 수 있다.

## 4. 해결 방안 2: Intent Capsule 기반 실행 격리 구조

각 Intent마다 독립적인 실행 캡슐을 두고, 캡슐 내부에서 자기 TaskState, side-effect, checkpoint를 관리한다. 전역 계층은 Intent 간 관계 라우팅과 공유 자원 충돌 조정만 담당한다.

### 구조

- `IntentCapsule`: 개별 Intent의 실행 상태와 Task 목록 보유
- `CapsuleCommandJournal`: 해당 Intent에 적용된 병합, 대체, 취소, 재개 명령 기록
- `CapsuleTaskState`: 캡슐 내부 Task 상태
- `CapsuleSideEffectRecord`: 캡슐 내부 외부 효과와 보상 정보
- `ResourceCoordinator`: 캡슐 간 공유 자원 충돌 조정
- `RelationCoordinator`: IDS 관계 라벨을 보고 어떤 Capsule에 명령을 보낼지 결정

### 처리 방식

병합이 들어오면 RelationCoordinator가 대상 Capsule을 찾아 `merge command`를 전달한다. Capsule은 자기 내부 Task 중 새 조건과 충돌하는 Task만 무효화한다. 무관한 Intent는 별도 Capsule로 실행되며, 병렬 실행 시 ResourceCoordinator가 공유 자원 충돌만 막는다.

### 장점

Intent별 실행 상태가 격리되어 모듈성이 높다. 하나의 Intent 실패가 다른 Intent Runtime에 직접 전파되지 않는다. 도메인별 Capsule 정책을 다르게 가져갈 수 있어 확장성과 구현 분할에 유리하다.

### 약점

여러 Intent가 반복적으로 병합·대체·취소되는 상황에서는 Capsule 간 관계 추적이 복잡해진다. 전역 replay와 postmortem을 만들려면 각 Capsule 기록과 ResourceCoordinator 기록을 다시 합쳐야 한다. cross-intent side-effect 보상도 더 어렵다.

## 5. Quality Attribute Trade-off 종합 평가

| 품질 속성 | 전역 실행 원장 기반 통합 제어 구조 | Intent Capsule 기반 실행 격리 구조 |
|---|---|---|
| 성능 효율성 | 전역 충돌 판단과 원장 갱신 비용이 있음 | 독립 Capsule 병렬 실행에 유리하고 실행 경로가 분산됨 |
| 신뢰성 | 전역 상태 기준 복구와 영향 범위 판단이 쉬움 | 장애 격리는 좋지만 Capsule 간 복구 정합성 확보가 어려움 |
| 유지보수성 | 중앙 모델이 커져 초기 구현 난도가 높음 | Capsule 단위 개발과 도메인 확장이 쉬움 |
| 이식성 | 전역 Runtime 의존성이 커 이식 부담이 있음 | Capsule 단위 재사용과 분리가 쉬움 |

## 6. 최종 판단

최종 권고는 **전역 실행 원장 기반 통합 제어 구조**이다.

DP11은 단순히 여러 Intent를 병렬 실행하는 문제가 아니라, 실행 중 병합·대체·차단·취소·실패 회복이 반복되는 상황에서 무엇을 살리고, 무엇을 무효화하고, 무엇을 보상할지 결정하는 문제다. 이 경우 Intent별 격리보다 전역 기준 상태가 있는 편이 실행 흐름의 일관성과 복구 판단 측면에서 유리하다.

다만 구현 시 모든 세부 상태를 무조건 전역 원장에 밀어 넣기보다, 전역 원장은 Intent 관계, Task 상태, ResourceLease, SideEffectRecord처럼 cross-intent 판단에 필요한 정보만 소유하고, 도메인별 세부 실행 로직은 Sub-Agent 또는 Capsule에 위임하는 절충이 적절하다.

## 7. 남은 Open Questions

- 전역 실행 원장에 반드시 기록해야 하는 최소 이벤트 범위는 어디까지인가?
- Intent Capsule 구조를 일부 도메인 Sub-Agent 내부 구현 패턴으로 허용할 것인가?
- 외부 side-effect의 보상 가능 여부를 Orchestrator 계획 단계에서 확정할 것인가, Runtime에서 Tool metadata로 판단할 것인가?
- 전역 replay를 위해 보관해야 하는 데이터와 개인정보 최소 보관 원칙 사이의 균형을 어떻게 둘 것인가?
