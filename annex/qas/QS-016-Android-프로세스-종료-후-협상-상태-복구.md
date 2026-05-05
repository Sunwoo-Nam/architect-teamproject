# QS-016-Android-프로세스-종료-후-협상-상태-복구

## 개요

### Quality Scenario ID
QS-016

### 제목
Android 프로세스 종료 후 협상 상태 복구

### 설명
Android OS가 메모리 부족 등으로 플랫폼 프로세스를 강제 종료한 후 재시작 시, 진행 중이던 협상 세션이 NegotiationSessionDB에 저장된 마지막 상태에서 재개되어야 한다. 협상이 도중에 소실되면 사용자가 인지하지 못한 채 협상이 실패한 것으로 처리될 수 있다.

### 품질 속성
가용성 — 프로세스 복구

## 환경

### 시스템 상태
A2A 협상이 진행 중인 상태에서 Android OS가 플랫폼 프로세스를 강제 종료(kill)하고, 이후 플랫폼이 재시작되는 상황

### 초기 조건
- NegotiationController가 상대방 PPA와 협상 세션을 활성화하여 진행 중
- NegotiationSessionDB에 최소 1라운드 이상의 협상 상태가 저장된 상태
- 플랫폼 프로세스가 Android foreground service 또는 background service로 실행 중

### 부하 조건
Fault injection: 협상 라운드 진행 중(제안 전송 후 반제안 수신 전 또는 수신 직후) Android OS의 프로세스 강제 종료 신호(SIGKILL) 발송

### 관련 컴포넌트
- NegotiationSessionDB: 협상 세션의 마지막 유효 상태를 영속 저장 (Android SQLite 또는 Room Database)
- NegotiationController: 재시작 시 NegotiationSessionDB에서 세션 상태를 로드하고 복구 로직 실행
- A2AProtocolAdapter: 재시작 후 상대방 PPA와의 통신 채널 재수립
- Android OS: 프로세스 강제 종료 및 재시작 주체

## 동작

1. **자극원**: Android OS (메모리 부족 또는 배터리 절약 정책으로 인한 프로세스 강제 종료)
2. **자극**: 플랫폼 프로세스에 SIGKILL 신호 발송으로 협상 진행 중 프로세스 강제 종료
3. **반응 주체**: Android OS, 플랫폼 재시작 루틴, NegotiationController, NegotiationSessionDB
4. **반응 흐름**:
   - Android OS가 플랫폼 프로세스를 강제 종료
   - Android OS가 플랫폼 서비스를 재시작 (foreground service 재시작 정책에 따라)
   - 플랫폼이 재시작되면서 NegotiationController가 초기화 루틴에서 NegotiationSessionDB를 확인
   - NegotiationSessionDB에서 미완료 상태의 협상 세션을 조회
   - NegotiationController가 마지막 저장 상태에서 협상 재개를 결정
   - A2AProtocolAdapter가 상대방 PPA와 통신 채널을 재수립하고 세션 재개 알림 전송
   - 사용자에게 협상 재개 알림 전달

## 측정

### 측정 항목
협상 진행 중 프로세스 강제 종료 후 재시작 시 세션 복구 성공률 및 재개까지 소요 시간

### 측정 공식
```
R_recovery = (세션_복구_성공_건수 / 프로세스_강제_종료_주입_건수) × 100 (%)

세션_복구_성공 정의: 재시작 후 NegotiationSessionDB에 저장된 마지막 상태에서 데이터 손실 없이 협상이 재개된 경우
  - 데이터 손실 없음: 재개된 세션의 라운드 히스토리가 강제 종료 이전과 일치

T_recovery = T_session_resumed - T_process_restarted (초)

T_process_restarted: Android OS가 플랫폼 프로세스를 재시작한 타임스탬프
T_session_resumed: NegotiationController가 NegotiationSessionDB에서 상태를 로드하고 협상을 재개한 타임스탬프

측정 방법:
  - 협상 라운드 N = 1, 3, 5에서 각각 프로세스 강제 종료 주입 (각 10회 반복)
  - AgentExecutionLogDB에서 재개 성공 여부 및 데이터 손실 여부 확인
```

## 관련 문서
- UC-013
- UC-020
- QS-003 (백그라운드 모니터링 메모리 사용량)
- QS-006 (협상 중 네트워크 단절 복구)
- QS-023 (상대방 PPA 장기 미응답 시 협상 세션 만료 처리)
