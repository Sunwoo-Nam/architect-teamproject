# QS-007-동적-생성-Agent-Tool-실행-성공률

## 개요

### Quality Scenario ID
QS-007

### 제목
동적 생성 Agent/Tool 실행 성공률

### 설명
AgentFactory/ToolFactory가 LLM 프롬프팅으로 동적 생성한 Agent 및 Tool이 첫 실행에서 의도한 기능을 정상 수행하는 비율. 이 값이 낮으면 동적 생성의 실용성을 입증할 수 없으므로 BG-4의 핵심 검증 지표이다.

### 품질 속성
신뢰성 — 동적 생성 품질

## 환경

### 시스템 상태
Orchestrator가 Task 분해를 완료하고 AgentFactory/ToolFactory가 LLM 기반 프롬프팅으로 새로운 Agent 또는 Tool을 동적으로 생성하는 상태

### 초기 조건
- Orchestrator가 서버 LLM으로부터 Agent/Tool 생성 명세를 수신 완료
- AgentFactory 및 ToolFactory가 활성화된 상태
- LLMGateway가 온디바이스 LLM과 연결된 상태
- 테스트 대상 Agent/Tool은 이전에 생성된 적 없는 신규 유형

### 부하 조건
다양한 도메인(숙박 예약, 교통 예약, 식당 예약, 가전 제어 등)에서 각각 Agent/Tool 동적 생성 시도

### 관련 컴포넌트
- AgentFactory: LLM 프롬프팅으로 Agent 코드/설정을 동적 생성
- ToolFactory: LLM 프롬프팅으로 Tool 코드/설정을 동적 생성
- LLMGateway: AgentFactory/ToolFactory의 생성 추론 요청 중개
- ExternalServiceAPIAdapter: 동적 생성된 Tool의 외부 API 호출 실행

## 동작

1. **자극원**: Orchestrator (Task 분해 후 Agent/Tool 생성 요청)
2. **자극**: AgentFactory 또는 ToolFactory에 특정 기능을 수행하는 신규 Agent/Tool 생성 요청
3. **반응 주체**: AgentFactory/ToolFactory, LLMGateway, 생성된 Agent/Tool 인스턴스
4. **반응 흐름**:
   - AgentFactory 또는 ToolFactory가 요청 명세를 수신하고 LLMGateway를 통해 생성 프롬프트 전송
   - 온디바이스 LLM이 Agent/Tool의 실행 로직 또는 설정을 생성
   - AgentFactory/ToolFactory가 생성된 결과를 파싱하여 실행 가능한 Agent/Tool 인스턴스로 변환
   - 생성된 Agent/Tool이 최초로 실행 요청을 받음
   - Agent/Tool이 의도된 외부 API 호출 완료 또는 의도된 협상 단계를 수행
   - 실행 결과(성공/실패)와 실행 로그를 AgentExecutionLogDB에 기록

## 측정

### 측정 항목
동적 생성된 Agent/Tool의 최초 실행(first-run) 성공률

### 측정 공식
```
R_first_run = (최초_실행_성공_건수 / 전체_동적_생성_건수) × 100 (%)

성공 기준:
  - Agent의 경우: 의도된 협상 단계(제안 생성, 반제안 평가 등)를 오류 없이 수행 완료
  - Tool의 경우: 의도된 외부 API 호출이 완료되고 유효한 응답을 수신

Agent/Tool 유형별 세분화:
  R_agent = (Agent_최초_실행_성공 / Agent_동적_생성_건수) × 100 (%)
  R_tool = (Tool_최초_실행_성공 / Tool_동적_생성_건수) × 100 (%)

측정 방법:
  - 각 도메인(숙박, 교통, 식당, 가전 등)에서 신규 Agent/Tool을 N=20건씩 동적 생성
  - 각 인스턴스의 최초 실행 결과를 AgentExecutionLogDB에서 집계
```

## 관련 문서
- UC-006
- UC-007
- QS-005 (온디바이스 LLM 추론 실패 처리)
- QS-004 (동시 Agent 실행 시 최대 메모리 사용량)
- QS-015 (Agent 의사결정 추적 가능성)
