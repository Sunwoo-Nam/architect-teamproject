# QS-023-상대방-PPA-장기-미응답-세션-만료-처리

## 개요

### Quality Scenario ID
QS-023

### 제목
상대방 PPA 장기 미응답 시 협상 세션 만료 처리

### 설명
QS-006이 단기 네트워크 단절 후 재연결을 다루는 것과 달리, 이 시나리오는 상대방 PPA가 수 시간~수일간 응답하지 않는 경우를 다룬다. 무한정 대기하면 세션과 자원이 묶이고, 너무 일찍 만료하면 협상 기회를 잃는다. 세션 만료 임계값 설정, 사용자 알림, 세션 상태 정리가 NegotiationSessionDB 설계와 세션 생명주기 관리 컴포넌트 필요 여부에 영향을 미친다.

### 품질 속성
가용성 — 세션 만료 처리

## 환경

### 시스템 상태
NegotiationController가 상대방 PPA에게 제안 메시지를 전송한 후 응답을 대기하는 상태. 상대방 PPA가 수 시간 이상 응답을 전송하지 않는 상황

### 초기 조건
- NegotiationController가 협상 세션을 활성화하고 상대방 PPA에 제안 전송 완료
- NegotiationSessionDB에 세션 상태와 마지막 제안 전송 타임스탬프가 기록된 상태
- 세션 만료 임계값이 NegotiationController에 설정된 상태
- 상대방 PPA가 네트워크는 연결되어 있으나 응답을 보내지 않는 상태 (장기 미응답)

### 부하 조건
없음 (단일 협상 세션, 장기 대기 시나리오)

### 관련 컴포넌트
- NegotiationController: 세션 만료 임계값 초과를 감지하고 만료 처리 실행
- NegotiationSessionDB: 세션 상태(활성, 만료)와 마지막 활동 타임스탬프 저장
- A2AProtocolAdapter: 상대방 PPA로부터의 응답 수신 대기 및 연결 상태 모니터링

## 동작

1. **자극원**: 시간 경과 (상대방 PPA의 장기 미응답)
2. **자극**: NegotiationController가 마지막 제안 전송 후 설정된 만료 임계값 시간 동안 상대방 PPA로부터 응답을 수신하지 못함
3. **반응 주체**: NegotiationController, NegotiationSessionDB, 사용자 알림 컴포넌트
4. **반응 흐름**:
   - NegotiationController가 주기적으로 세션의 마지막 활동 타임스탬프를 현재 시간과 비교
   - 설정된 만료 임계값 초과 감지
   - NegotiationController가 세션 상태를 NegotiationSessionDB에서 '만료(EXPIRED)'로 업데이트
   - 만료된 세션에 할당된 메모리, 연결 자원 등을 해제
   - 사용자에게 협상 세션 만료 알림 전달 (협상 상대방이 응답하지 않아 세션이 종료되었음을 안내)
   - 만료 이벤트와 관련 자원 정리 완료 여부를 AgentExecutionLogDB에 기록

## 측정

### 측정 항목
설정된 만료 임계값 초과 후 세션이 올바른 만료 상태로 전환되고 사용자에게 알림이 전달될 때까지의 시간 및 만료 후 관련 자원 정리 완료 여부

### 측정 공식
```
T_expiry_processing = T_user_notified - T_threshold_exceeded (초)

T_threshold_exceeded: 세션의 마지막 활동 타임스탬프 + 만료 임계값으로 계산된 만료 시각
T_user_notified: 사용자에게 세션 만료 알림이 전달된 타임스탬프

자원_정리_완료 = 세션 만료 후 관련 메모리 및 연결 자원이 해제된 여부 (O/X)

세션_상태_정확성 = 만료 임계값 초과 후 NegotiationSessionDB에서 세션 상태가 'EXPIRED'로 올바르게 변경된 여부 (O/X)

측정 방법:
  - 협상 세션 시작 후 상대방 PPA 응답을 의도적으로 차단 (Mock PPA 사용)
  - 만료 임계값 도달 후 세션 상태 변경 타임스탬프와 사용자 알림 타임스탬프를 AgentExecutionLogDB에서 확인
  - adb shell dumpsys meminfo로 세션 종료 전후 메모리 해제 여부 확인
  - N=10회 반복하여 T_expiry_processing의 평균 및 편차 측정
```

## 관련 문서
- UC-016
- UC-023
- QS-006 (협상 중 네트워크 단절 복구)
- QS-016 (Android 프로세스 종료 후 협상 상태 복구)
- QS-022 (영속 데이터 저장 공간 누적)
