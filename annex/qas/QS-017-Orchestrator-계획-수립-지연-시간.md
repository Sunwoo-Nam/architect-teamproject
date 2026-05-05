# QS-017-Orchestrator-계획-수립-지연-시간

## 개요

### Quality Scenario ID
QS-017

### 제목
Orchestrator 계획 수립 지연 시간

### 설명
IDS가 복합 Intent를 Orchestrator에 넘긴 시점부터 Orchestrator가 Task 분해와 Agent 생성 계획을 완료하는 시점까지의 시간. Orchestrator는 서버 LLM을 사용하므로 네트워크 왕복 지연과 고성능 추론 시간이 포함된다. 이 단계가 느리면 전체 Task 시작 자체가 지연된다.

### 품질 속성
성능 — 응답 시간

## 환경

### 시스템 상태
IDS가 복합 Intent(여러 서비스를 동시에 처리해야 하는 Intent)를 감지하고 Orchestrator에 Task 분해를 요청한 상태. 서버 LLM과의 네트워크 연결이 정상인 상태

### 초기 조건
- IDS가 복합 Intent를 감지 완료하고 Intent 정보를 Orchestrator에 전달
- Orchestrator가 서버 LLM에 Task 분해 요청을 전송 준비 완료
- 서버 LLM 서비스가 정상 가동 중
- 네트워크 연결이 정상 상태

### 부하 조건
복합 Intent의 복잡도에 따른 측정: Sub-Task 2개, 4개, 6개로 분해되는 Intent 각각에 대해 측정

### 관련 컴포넌트
- LLMGateway: 서버 LLM에 대한 Task 분해 요청 중개
- AgentFactory: Orchestrator로부터 Agent 생성 명세를 수신하고 Agent 그룹 생성
- TaskDB: 분해된 Sub-Task 목록 저장

## 동작

1. **자극원**: IDS (복합 Intent 감지 후 Orchestrator 활성화)
2. **자극**: Orchestrator가 서버 LLM에 복합 Intent에 대한 Task 분해 계획 수립 요청
3. **반응 주체**: LLMGateway(서버 LLM 연동), Orchestrator, AgentFactory
4. **반응 흐름**:
   - Orchestrator가 복합 Intent 정보를 받아 서버 LLM에 Task 분해 프롬프트 전송 (LLMGateway 경유)
   - 서버 LLM이 네트워크를 통해 요청을 수신하고 Task 분해 및 Agent 생성 계획 추론
   - 서버 LLM이 분해된 Sub-Task 목록과 각 Task에 필요한 Agent/Tool 명세를 응답으로 반환
   - LLMGateway가 응답을 Orchestrator에 전달
   - Orchestrator가 분해된 Task 목록을 TaskDB에 저장
   - Orchestrator가 AgentFactory에 Agent 그룹 생성 요청 전달
   - AgentFactory가 명세에 따라 Agent 인스턴스 생성 완료

## 측정

### 측정 항목
TaskDecomposer가 Orchestrator에 계획 수립을 요청한 시점부터 AgentFactory가 Agent 그룹 생성을 완료하는 시점까지의 경과 시간

### 측정 공식
```
T_plan = T_agent_group_ready - T_decompose_request (초)

T_decompose_request: TaskDecomposer가 Orchestrator(서버 LLM)에 Task 분해 요청을 전송한 타임스탬프
T_agent_group_ready: AgentFactory가 모든 Sub-Agent 인스턴스 생성을 완료한 타임스탬프

세부 분해:
  T_network_rtt = 서버 LLM 요청-응답 왕복 시간 (초)
  T_llm_inference = 서버 LLM 추론 시간 (T_network_rtt 내 포함)
  T_agent_creation = AgentFactory의 Agent 생성 시간 (초)
  T_plan = T_network_rtt + T_agent_creation

복잡도별 측정:
  T_plan(Sub-Task=2), T_plan(Sub-Task=4), T_plan(Sub-Task=6) 각각 측정

집계: 각 복잡도에서 N=10회 반복 후 평균(avg), p95 산출
```

## 관련 문서
- UC-005
- UC-006
- UC-007
- QS-001 (Intent 감지 지연 시간)
- QS-004 (동시 Agent 실행 시 최대 메모리 사용량)
- QS-018 (Sub-Agent Tool 실행 지연 시간)
