# QS-015-Agent-의사결정-추적-가능성

## 개요

### Quality Scenario ID
QS-015

### 제목
Agent 의사결정 추적 가능성

### 설명
Agent(IntentDetector, NegotiationController, ProposalGenerator 등)가 특정 결정을 내린 이유를 AgentExecutionLogDB를 통해 사후 재구성할 수 있어야 한다. LLM 기반 결정은 비결정적이므로, 입력 컨텍스트와 LLM 응답을 로그로 보존하지 않으면 오동작의 원인을 파악할 수 없다.

### 품질 속성
테스트 용이성 — Agent 결정 추적

## 환경

### 시스템 상태
Agent가 정상 동작 또는 오동작을 수행한 이후, 개발자 또는 QA 엔지니어가 해당 결정의 원인을 사후 분석하는 상태

### 초기 조건
- Agent(IntentDetector, NegotiationController, ProposalGenerator 등)가 특정 결정을 수행 완료
- AgentExecutionLogDB가 활성화되어 결정 이벤트를 기록하는 상태
- 분석 대상 결정 사건의 시간 범위가 특정된 상태

### 부하 조건
없음 (사후 로그 분석 시나리오)

### 관련 컴포넌트
- AgentExecutionLogDB: Agent의 입력 컨텍스트, LLM 프롬프트, LLM 응답, 최종 결정을 기록하는 로그 저장소
- IntentDetector: 로그 기록 대상 Agent
- NegotiationController: 로그 기록 대상 Agent
- ProposalGenerator: 로그 기록 대상 Agent
- LLMGateway: LLM 요청/응답 페이로드를 로그에 전달

## 동작

1. **자극원**: 개발자/QA 엔지니어 (오동작 원인 분석 요구)
2. **자극**: 특정 Agent 결정 사건(예: 잘못된 Intent 분류, 비합리적인 협상 제안)에 대한 원인 분석 요청
3. **반응 주체**: AgentExecutionLogDB, 분석 도구
4. **반응 흐름**:
   - 개발자가 분석 대상 결정의 시간 범위 또는 이벤트 ID를 특정
   - AgentExecutionLogDB에서 해당 결정 사건의 로그 레코드 조회
   - 로그에서 입력 컨텍스트(수신 메시지, 이전 협상 상태 등) 확인
   - 로그에서 LLM에 전달된 프롬프트 내용 확인
   - 로그에서 LLM이 반환한 응답 내용 확인
   - 로그에서 최종 결정(Intent 분류 결과, 협상 제안 내용 등) 확인
   - 네 가지 요소(입력 컨텍스트, LLM 프롬프트, LLM 응답, 최종 결정)를 조합하여 결정 과정 재구성

## 측정

### 측정 항목
임의의 Agent 결정 사건에 대해 입력 컨텍스트, LLM 프롬프트, LLM 응답, 최종 결정을 로그에서 재구성 가능한 비율

### 측정 공식
```
R_traceable = (추적_가능_결정_건수 / 전체_샘플_결정_건수) × 100 (%)

추적_가능 정의: 하나의 결정 사건에 대해 다음 4가지 요소가 모두 AgentExecutionLogDB에서 조회 가능한 경우
  1. 입력 컨텍스트 (해당 결정 시점의 시스템 상태 및 입력 데이터)
  2. LLM 프롬프트 (LLMGateway를 통해 전달된 프롬프트 전문)
  3. LLM 응답 (LLM이 반환한 원문 응답)
  4. 최종 결정 (Agent가 내린 분류/제안/행동 결과)

측정 방법:
  - 정상 운용 기간 동안 발생한 Agent 결정 사건에서 무작위 N=50건 샘플링
  - 각 결정 사건에 대해 AgentExecutionLogDB에서 4가지 요소의 존재 여부 확인
  - 4가지 요소가 모두 존재하는 경우 추적 가능으로 판정

Agent 유형별 세분화:
  R_intent = (IntentDetector 추적 가능 / IntentDetector 샘플) × 100 (%)
  R_proposal = (ProposalGenerator 추적 가능 / ProposalGenerator 샘플) × 100 (%)
```

## 관련 문서
- UC-027
- QS-005 (온디바이스 LLM 추론 실패 처리)
- QS-007 (동적 생성 Agent/Tool 실행 성공률)
- QS-014 (A2A 협상 시뮬레이션 가능 여부)
