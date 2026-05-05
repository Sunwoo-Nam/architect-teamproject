# QS-004-동시-Agent-실행-최대-메모리-사용량

## 개요

### Quality Scenario ID
QS-004

### 제목
동시 Agent 실행 시 최대 메모리 사용량

### 설명
복합 Task 처리 시 Orchestrator, Meta Agent, 다수의 Sub-Agent가 동시에 동작하는 동안의 최대 메모리 사용량. 동시에 몇 개의 Agent를 생성·실행할 수 있는지가 이 값에 의해 결정된다.

### 품질 속성
성능 — 자원 효율성

## 환경

### 시스템 상태
복합 Intent가 감지된 이후 Orchestrator가 Task를 분해하고, AgentFactory가 Sub-Agent 3개 이상을 동시에 생성하여 실행하는 최고 부하 상태

### 초기 조건
- IDS가 복합 Intent를 감지하고 Orchestrator에 Task 처리 요청 전달
- Orchestrator가 Task 분해 계획을 서버 LLM으로부터 수신 완료
- AgentFactory가 Sub-Agent 생성 준비 완료
- 온디바이스 LLM이 메모리에 로드된 상태
- 이전 협상 세션 없음 (초기 상태)

### 부하 조건
Sub-Agent 3개 이상이 동시에 활성화되어 각자 LLM 추론 또는 외부 API 호출을 병렬로 수행하는 상태

### 관련 컴포넌트
- AgentFactory: Sub-Agent 동적 생성 및 메모리 할당
- ToolFactory: 각 Sub-Agent에 필요한 Tool 생성
- LLMGateway: 다수 Sub-Agent의 동시 LLM 추론 요청 처리
- NegotiationController: Meta Agent의 협상 세션 메모리 점유
- TaskDB: 각 Sub-Agent의 Task 상태 저장
- AgentExecutionLogDB: 동시 실행 Agent의 로그 기록

## 동작

1. **자극원**: 사용자 (복합 Intent를 유발하는 메시지 또는 캘린더 이벤트)
2. **자극**: Orchestrator가 복합 Task를 3개 이상의 병렬 Sub-Task로 분해하고 AgentFactory에 Agent 생성 요청
3. **반응 주체**: AgentFactory, ToolFactory, LLMGateway, 각 Sub-Agent 인스턴스
4. **반응 흐름**:
   - Orchestrator가 Task 분해 결과를 AgentFactory에 전달
   - AgentFactory가 각 Sub-Task에 대응하는 Sub-Agent를 동시에 생성하고 메모리 할당
   - ToolFactory가 각 Sub-Agent에 필요한 Tool 인스턴스를 생성
   - 각 Sub-Agent가 독립적으로 LLMGateway를 통해 추론을 수행하거나 Tool을 호출
   - 모든 Sub-Agent가 동시에 활성 상태를 유지하는 구간에서 플랫폼 프로세스의 메모리가 최대치에 도달
   - 각 Sub-Agent가 Task를 완료하면 순차적으로 메모리 해제

## 측정

### 측정 항목
복합 Task 시나리오(Sub-Agent 3개 이상 동시 실행)에서 플랫폼 프로세스가 점유하는 최대 메모리 크기

### 측정 공식
```
M_peak = max(RSS_samples_during_execution) (MB)

RSS_samples_during_execution: AgentFactory가 첫 번째 Sub-Agent를 생성한 시점부터 마지막 Sub-Agent가 종료된 시점까지 수집한 RSS 샘플 집합

측정 방법:
  - Android Debug Bridge(adb shell dumpsys meminfo <package>) 또는
  - /proc/<pid>/status의 VmRSS 값을 고주기(예: 5초 간격)로 수집
  - 실행 시나리오: UC-005 기준, Sub-Agent 수 N = 3, 5, 7로 각각 측정

Agent 수별 메모리 증가율:
  delta_M = M_peak(N) - M_peak(N-1)

N: 동시 실행 Sub-Agent 수
```

## 관련 문서
- UC-005
- UC-006
- QS-003 (백그라운드 모니터링 메모리 사용량)
- QS-017 (Orchestrator 계획 수립 지연 시간)
- QS-018 (Sub-Agent Tool 실행 지연 시간)
