# QS-005-온디바이스-LLM-추론-실패-처리

## 개요

### Quality Scenario ID
QS-005

### 제목
온디바이스 LLM 추론 실패 처리

### 설명
온디바이스 LLM이 타임아웃, OOM, 비정상 출력(파싱 불가 응답) 등으로 실패했을 때 시스템이 오류 상태에 빠지지 않고 사용자에게 상황을 알리거나 대체 처리를 수행하는 능력. LLMGateway가 모든 LLM 호출의 단일 진입점이므로, 이 컴포넌트의 실패 처리 설계가 전체 신뢰성을 결정한다.

### 품질 속성
신뢰성 — LLM 오류 처리

## 환경

### 시스템 상태
LLMGateway를 통해 온디바이스 LLM 추론이 진행 중이거나 요청 대기 중인 상태. 정상 운용 중 LLM 오류가 발생하는 상황

### 초기 조건
- LLMGateway가 활성화되어 있으며 온디바이스 LLM 모델이 로드된 상태
- IntentDetector, ProposalGenerator, 또는 Sub-Agent 중 하나 이상이 LLMGateway에 추론 요청을 전송한 상태
- 오류 처리 정책(재시도 횟수, 타임아웃 임계값)이 LLMGateway에 설정된 상태

### 부하 조건
Fault injection: 타임아웃(응답 없음), OOM(메모리 부족으로 모델 로드 실패), 비정상 출력(JSON 파싱 불가 응답) 세 가지 오류 유형을 각각 주입

### 관련 컴포넌트
- LLMGateway: 온디바이스 LLM 오류를 감지하고 오류 처리 경로를 실행하는 단일 진입점
- IntentDetector: LLM 오류 발생 시 사용자 알림을 받는 호출자
- ProposalGenerator: LLM 오류 발생 시 협상 중단 처리를 받는 호출자
- NegotiationController: LLM 오류로 인한 협상 세션 상태 변경 관리

## 동작

1. **자극원**: 온디바이스 LLM 런타임 (오류 발생)
2. **자극**: LLM 추론 중 타임아웃, OOM, 또는 파싱 불가 응답 발생
3. **반응 주체**: LLMGateway, 호출 컴포넌트(IntentDetector/ProposalGenerator/Sub-Agent)
4. **반응 흐름**:
   - LLMGateway가 LLM 추론 오류를 감지 (타임아웃 만료, 예외 발생, 또는 응답 파싱 실패)
   - LLMGateway가 설정된 재시도 정책에 따라 재시도 수행 (해당하는 경우)
   - 재시도 소진 또는 복구 불가 오류 시 LLMGateway가 표준화된 오류 응답을 호출자에게 반환
   - 호출자(IntentDetector, ProposalGenerator 등)가 오류 응답을 수신하고 사용자 알림 또는 대체 처리 경로 실행
   - 오류 발생 이벤트와 오류 유형이 AgentExecutionLogDB에 기록됨

## 측정

### 측정 항목
LLM 추론 실패를 주입했을 때 시스템이 정상 오류 처리 경로를 완료하는 비율

### 측정 공식
```
R_error_handling = (정상_오류_처리_완료_건수 / 전체_오류_주입_건수) × 100 (%)

정의:
  - 전체_오류_주입_건수: fault injection으로 주입한 LLM 오류 이벤트 총 수
  - 정상_오류_처리_완료_건수: 오류 주입 후 시스템이 사용자 알림 전달 또는 대체 처리 완료 중 하나를 수행한 건수

오류 유형별 세분화:
  R_timeout = (타임아웃_정상처리_건수 / 타임아웃_주입_건수) × 100 (%)
  R_oom = (OOM_정상처리_건수 / OOM_주입_건수) × 100 (%)
  R_parse = (파싱오류_정상처리_건수 / 파싱오류_주입_건수) × 100 (%)

측정 방법:
  - LLMGateway에 fault injection 프레임워크를 통해 각 오류 유형을 N=100건씩 주입
  - AgentExecutionLogDB에서 오류 처리 완료 여부 확인
```

## 관련 문서
- UC-001
- UC-002
- UC-003
- UC-004
- UC-005
- UC-006
- UC-007
- UC-013
- UC-014
- UC-015
- QS-007 (동적 생성 Agent/Tool 실행 성공률)
- QS-015 (Agent 의사결정 추적 가능성)
