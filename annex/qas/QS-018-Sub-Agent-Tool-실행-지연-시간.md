# QS-018-Sub-Agent-Tool-실행-지연-시간

## 개요

### Quality Scenario ID
QS-018

### 제목
Sub-Agent Tool 실행 지연 시간

### 설명
Sub-Agent가 외부 서비스 API Tool(숙박/교통/식당 예약 등)을 호출한 시점부터 결과를 수신하는 시점까지의 지연. 여러 Sub-Agent가 병렬로 Tool을 호출하는 경우에도 전체 Task 완료 시간이 허용 범위 내에 있어야 한다.

### 품질 속성
성능 — 응답 시간

## 환경

### 시스템 상태
Sub-Agent가 합의된 Task를 실행하기 위해 ExternalServiceAPIAdapter를 통해 외부 서비스 API를 호출하는 상태. 복수의 Sub-Agent가 병렬로 각자의 Tool을 호출하는 경우 포함

### 초기 조건
- Orchestrator가 Task 분해를 완료하고 Sub-Agent들이 활성화된 상태
- ExternalServiceAPIAdapter가 초기화되어 각 외부 서비스 API와 연동 준비 완료
- 각 Sub-Agent가 실행해야 할 외부 API 호출 목록을 보유한 상태
- 네트워크 연결이 정상 상태

### 부하 조건
단일 Sub-Agent가 순차적으로 API를 호출하는 경우 및 복수(3개 이상) Sub-Agent가 병렬로 API를 호출하는 경우 각각 측정

### 관련 컴포넌트
- ExternalServiceAPIAdapter: 외부 서비스 API 호출의 실제 실행 주체
- Sub-Agent: Tool을 호출하여 외부 서비스와 상호작용
- ToolFactory: Sub-Agent에 제공되는 Tool 인스턴스 생성

## 동작

1. **자극원**: Sub-Agent (합의된 Task 실행 지시)
2. **자극**: Sub-Agent가 ExternalServiceAPIAdapter를 통해 특정 외부 서비스 API(예: 숙박 예약 API) 호출 요청
3. **반응 주체**: ExternalServiceAPIAdapter, 외부 서비스 API 서버
4. **반응 흐름**:
   - Sub-Agent가 Tool을 통해 ExternalServiceAPIAdapter에 외부 API 호출 요청
   - ExternalServiceAPIAdapter가 해당 외부 서비스의 API 엔드포인트에 요청 전송
   - 외부 서비스 서버가 요청을 처리하고 응답 반환
   - ExternalServiceAPIAdapter가 응답을 수신하고 파싱하여 Sub-Agent에 결과 전달
   - Sub-Agent가 결과를 TaskDB에 저장하고 Orchestrator에 완료 보고
   - 병렬 호출의 경우 가장 늦게 완료되는 Sub-Agent의 응답 수신 시점이 전체 완료 시점

## 측정

### 측정 항목
ExternalServiceAPIAdapter가 외부 API를 호출한 시점부터 응답을 수신하는 시점까지의 경과 시간 (병렬 호출 시 가장 긴 경로 기준)

### 측정 공식
```
T_tool = T_response_received - T_api_called (초)

T_api_called: ExternalServiceAPIAdapter가 외부 API 엔드포인트에 요청을 전송한 타임스탬프
T_response_received: ExternalServiceAPIAdapter가 응답을 수신 완료한 타임스탬프

단일 호출:
  T_tool_single = T_response_received - T_api_called

병렬 호출 (Sub-Agent N개 동시 실행):
  T_tool_parallel = max(T_tool_i) for i in [1..N]
  (가장 늦게 완료되는 호출의 소요 시간)

서비스 유형별 측정:
  T_tool_accommodation: 숙박 예약 API 호출 시간
  T_tool_transport: 교통 예약 API 호출 시간
  T_tool_restaurant: 식당 예약 API 호출 시간

집계: 각 서비스 유형 및 병렬 수(N=1, 3, 5)에 대해 N=20회 반복 후 평균(avg), p95 산출
```

## 관련 문서
- UC-004
- UC-013
- QS-004 (동시 Agent 실행 시 최대 메모리 사용량)
- QS-013 (외부 서비스 API 교체 비용)
- QS-017 (Orchestrator 계획 수립 지연 시간)
- QS-024 (합의 후 외부 서비스 실행 실패 처리)
