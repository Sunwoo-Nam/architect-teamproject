# QS-001-Intent-감지-지연-시간

## 개요

### Quality Scenario ID
QS-001

### 제목
Intent 감지 지연 시간

### 설명
사용자가 메신저 앱에서 메시지를 주고받는 동안 IDS가 Intent를 감지하기까지의 지연 시간. 온디바이스 LLM 추론이 포함되며, 지연이 길면 사용자가 이미 다른 행동을 취한 후 Intent가 감지되는 문제가 발생한다.

### 품질 속성
성능 — 응답 시간

## 환경

### 시스템 상태
IDS(Intent Detection System)가 백그라운드에서 활성화되어 있으며, MessageMonitorUI가 메신저 앱의 메시지를 실시간으로 감지하는 상태

### 초기 조건
- MessageMonitorUI가 대상 메신저 앱을 모니터링 중
- LLMGateway가 온디바이스 LLM과 연결된 상태
- IntentDetector가 초기화 완료 상태
- 온디바이스 LLM 모델이 메모리에 로드된 상태

### 부하 조건
메신저 앱에서 일반적인 대화 중 새로운 메시지 수신 이벤트 발생

### 관련 컴포넌트
- MessageMonitorUI: 메신저 앱의 메시지 이벤트를 캡처하고 IDS에 전달
- LLMGateway: 온디바이스 LLM 추론 요청을 중개
- IntentDetector: 메시지 컨텍스트를 분석하여 Intent를 분류

## 동작

1. **자극원**: 메신저 앱 사용자 (메시지 수신 이벤트)
2. **자극**: 메신저 앱에서 새로운 메시지가 수신됨
3. **반응 주체**: MessageMonitorUI → LLMGateway → IntentDetector
4. **반응 흐름**:
   - MessageMonitorUI가 메시지 수신 이벤트를 감지하고 메시지 텍스트를 추출
   - 추출된 메시지와 최근 대화 컨텍스트를 IntentDetector에 전달
   - IntentDetector가 LLMGateway를 통해 온디바이스 LLM에 Intent 분류 추론 요청
   - 온디바이스 LLM이 메시지 컨텍스트를 기반으로 Intent 유형을 추론
   - LLMGateway가 추론 결과를 IntentDetector에 반환
   - IntentDetector가 Intent 분류를 완료하고 결과를 IntentDB에 저장

## 측정

### 측정 항목
메시지 수신 이벤트 발생 시점부터 IntentDetector가 Intent 분류를 완료하는 시점까지의 경과 시간

### 측정 공식
```
T_intent = T_classification_complete - T_message_received (ms)

T_message_received: MessageMonitorUI가 메시지 수신 이벤트를 캡처한 타임스탬프
T_classification_complete: IntentDetector가 Intent 분류 결과를 IntentDB에 저장 완료한 타임스탬프

측정 단위: ms
측정 방식: AgentExecutionLogDB에 기록된 각 단계별 타임스탬프 기반 계산
집계: 다수 이벤트에 대한 평균(avg), 중앙값(p50), 95th 백분위(p95) 산출
```

## 관련 문서
- UC-001
- UC-002
- UC-003
- QS-003 (백그라운드 모니터링 메모리 사용량)
- QS-017 (Orchestrator 계획 수립 지연 시간)
