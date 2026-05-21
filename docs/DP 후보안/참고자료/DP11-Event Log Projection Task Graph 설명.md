# DP11 참고: Event Log, Projection, Task Graph 설명

DP11의 2안인 **Event Log 기반 Task Graph**는 현재 상태값 하나만 저장하는 방식이 아니라, 시스템에서 발생한 사건의 이력을 남기고 그 이력으로 현재 상태와 관계 구조를 재구성하는 방식입니다.
이 문서는 해당 대안에서 사용하는 Event Log, Projection, Task Graph의 의미를 설명합니다.

## Event Log

Event Log는 시스템에서 발생한 일을 시간순으로 계속 쌓는 원본 기록입니다.
기존 데이터를 덮어쓰는 방식이 아니라, 발생한 사건을 append-only 방식으로 추가합니다.

예를 들면 다음과 같은 기록이 쌓일 수 있습니다.

```text
1. IntentReceived: "토요일 저녁 식사 예약"
2. IntentUpdated: "아이 동반 가능 조건 추가"
3. CalendarConflictDetected: "토요일 저녁 일정 충돌"
4. IntentUpdated: "일요일 점심으로 변경"
5. TaskExecuted: "식당 후보 검색"
6. ExternalStateChanged: "캘린더 임시 블록 생성"
7. TaskFailed: "예약 API hold 실패"
```

핵심은 현재 상태만 저장하는 것이 아니라, 상태가 왜 그렇게 되었는지의 이력을 남기는 것입니다.
따라서 이후 실패, 취소, 변경이 발생했을 때 어떤 판단과 실행이 선행되었는지를 추적할 수 있습니다.

## Projection

Projection은 Event Log를 읽어서 특정 목적에 맞는 현재 상태 뷰를 만드는 과정입니다.
Event Log 자체는 시간순 사건 목록이기 때문에, 그 목록만으로는 현재 어떤 Intent가 유효한지나 어떤 실행을 되돌려야 하는지 바로 판단하기 어렵습니다.

Projection은 Event Log를 읽고 다음과 같은 질문에 답할 수 있는 형태로 데이터를 재구성합니다.

- 현재 유효한 Intent는 무엇인가?
- 어떤 Intent가 어떤 Intent를 대체했는가?
- 어떤 조건이 기존 Intent에 병합되었는가?
- 어떤 Task가 이미 실행되었는가?
- 어떤 외부 상태 변경이 이미 발생했는가?
- 실패나 취소가 발생하면 무엇을 유지하고 무엇을 취소해야 하는가?

즉 Projection은 로그를 읽어서 의미 있는 현재 그림을 만드는 계산 과정입니다.

## Task Graph

Task Graph는 Projection 결과 중 하나입니다.
Intent, Task, Agent, Resource 사이의 관계를 graph 형태로 표현합니다.

예를 들면 다음과 같은 구조를 만들 수 있습니다.

```text
Intent A: 토요일 저녁 식사 예약
  ├─ 조건 추가: 아이 동반 가능
  ├─ 대체됨: 일요일 점심으로 변경
  ├─ 실행 Task: 식당 후보 검색
  ├─ 실행 Task: 캘린더 임시 블록
  └─ 영향 Resource: Calendar, Restaurant API
```

관계 중심으로 표현하면 다음과 같습니다.

```text
"일요일 점심 변경 Intent"
  supersedes
"토요일 저녁 예약 Intent"

"아이 동반 가능 조건"
  merges into
"식사 예약 Intent"

"캘린더 충돌 감지"
  blocks
"토요일 저녁 예약 실행"

"캘린더 임시 블록"
  affects
"Calendar Resource"
```

Task Graph가 있으면 단순히 현재 상태가 `running`인지 `failed`인지보다 더 많은 것을 판단할 수 있습니다.
예를 들어 “일요일 점심으로 바뀌었으니 토요일 저녁 예약 hold는 취소해야 하지만, 아이 동반 가능 조건은 유지해야 한다” 같은 판단이 가능해집니다.

## 세 개념의 관계

| 개념 | 역할 |
|---|---|
| Event Log | 발생한 사건의 원본 기록 |
| Projection | Event Log를 읽어서 현재 판단 가능한 형태로 변환하는 과정 |
| Task Graph | Projection 결과로 만들어진 Intent/Task/Resource 관계 구조 |

비유하면 다음과 같습니다.

- Event Log: 회의 녹취록 전체
- Projection: 녹취록을 읽고 결정사항, 할일, 변경사항을 정리하는 작업
- Task Graph: 정리된 할일 간 관계도

따라서 Event Log 기반 Task Graph 방식은 현재 상태 하나만 저장하지 않고, 사건 이력을 남긴 뒤 그 이력으로 관계도를 재구성하는 접근입니다.
이 방식은 저장 비용과 계산 비용이 커질 수 있지만, 복잡한 변경, 취소, 복구 판단에는 더 강합니다.
