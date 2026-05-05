# QS-013-외부-서비스-API-교체-비용

## 개요

### Quality Scenario ID
QS-013

### 제목
외부 서비스 API 교체 비용

### 설명
숙박/교통/식당 예약 외부 서비스 API 제공업체가 변경되거나 신규 서비스가 추가될 때 수정이 ExternalServiceAPIAdapter 내부로 한정되어야 한다.

### 품질 속성
변경 용이성 — 외부 서비스 API 교체

## 환경

### 시스템 상태
플랫폼이 특정 외부 서비스 API 제공업체와 연동된 상태에서 다른 제공업체로 교체하거나 신규 서비스를 추가하는 변경 작업이 수행되는 상태

### 초기 조건
- 현재 플랫폼이 특정 숙박/교통/식당 예약 API 제공업체와 연동하여 동작 중
- Sub-Agent가 ExternalServiceAPIAdapter를 통해서만 외부 API를 호출
- 교체 대상 API 제공업체의 인터페이스(엔드포인트, 인증 방식, 요청/응답 형식)가 다름

### 부하 조건
없음 (개발/유지보수 변경 작업 시나리오)

### 관련 컴포넌트
- ExternalServiceAPIAdapter: 외부 서비스 API 연동을 내부에 캡슐화 (수정 대상)
- Sub-Agent: ExternalServiceAPIAdapter를 통해 외부 API를 호출하는 실행 주체 (수정 불필요 여부 확인 대상)
- NegotiationController: 합의 결과를 실행에 연결하는 컴포넌트 (수정 불필요 여부 확인 대상)
- ToolFactory: Tool 생성 시 API 인터페이스 의존 여부 (수정 불필요 여부 확인 대상)

## 동작

1. **자극원**: 개발팀 (외부 서비스 API 제공업체 변경 또는 신규 서비스 추가 요구)
2. **자극**: 외부 예약 서비스 API가 다른 제공업체로 교체되거나 신규 서비스 카테고리 추가 요구
3. **반응 주체**: ExternalServiceAPIAdapter (수정 대상), 나머지 컴포넌트 (변경 영향 없어야 함)
4. **반응 흐름**:
   - 교체 대상 외부 서비스 API의 인터페이스 명세 분석
   - ExternalServiceAPIAdapter 내부의 해당 서비스 어댑터 구현만 수정 또는 새 어댑터 추가
   - Sub-Agent는 ExternalServiceAPIAdapter의 공통 인터페이스를 통해 서비스를 호출하므로 수정 불필요
   - NegotiationController, ToolFactory 등 상위 컴포넌트는 수정 없이 동작
   - 교체 후 해당 서비스에 대한 통합 테스트 수행

## 측정

### 측정 항목
외부 서비스 API 교체 시 ExternalServiceAPIAdapter 외부에서 수정이 필요한 컴포넌트 수

### 측정 공식
```
C_external = count(ExternalServiceAPIAdapter 패키지/모듈 외부에서 코드/설정 수정이 필요한 컴포넌트)

측정 방법:
  - 변경 시나리오: 숙박 API 교체, 신규 서비스 카테고리(예: 차량 공유) 추가 각각에 대해 수행
  - git diff로 변경된 파일 추적
  - ExternalServiceAPIAdapter 패키지/모듈 경계 외부에서 변경된 파일 수 집계

C_external = 0이 목표 (ExternalServiceAPIAdapter 내부 변경만으로 교체 완료)

추가 측정:
  T_api_replace = API 교체 작업 완료까지 소요 시간 (개발자-시간, hour)
```

## 관련 문서
- UC-013
- QS-010 (온디바이스 LLM 모델 교체 비용)
- QS-011 (새로운 협상 도메인 추가 비용)
- QS-012 (A2A 프로토콜 버전 업데이트 비용)
- QS-018 (Sub-Agent Tool 실행 지연 시간)
- QS-024 (합의 후 외부 서비스 실행 실패 처리)
