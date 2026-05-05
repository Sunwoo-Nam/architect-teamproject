# QS-010-온디바이스-LLM-모델-교체-비용

## 개요

### Quality Scenario ID
QS-010

### 제목
온디바이스 LLM 모델 교체 비용

### 설명
온디바이스 LLM을 다른 모델(예: Gemma → Phi → Llama)로 교체할 때 수정이 LLMGateway 컴포넌트 내부로 한정되어야 한다. 시스템이 특정 LLM 벤더에 종속되면 온디바이스 LLM 성숙도 변화에 대응하기 어렵다.

### 품질 속성
변경 용이성 — LLM 교체

## 환경

### 시스템 상태
온디바이스 LLM 모델을 현재 사용 중인 모델에서 다른 벤더의 모델로 교체하는 변경 작업이 수행되는 상태

### 초기 조건
- 현재 플랫폼이 특정 온디바이스 LLM 모델을 사용 중 (예: Gemma)
- LLMGateway가 해당 모델의 API/인터페이스를 통해 추론 요청을 처리 중
- 교체 대상 모델은 추론 인터페이스(API 형식, 입출력 형식)가 다른 모델 (예: Phi, Llama)

### 부하 조건
없음 (개발/유지보수 변경 작업 시나리오)

### 관련 컴포넌트
- LLMGateway: 온디바이스 LLM 모델과의 인터페이스를 내부적으로 캡슐화하는 단일 진입점
- IntentDetector: LLMGateway를 통해 LLM을 사용하는 호출자 (변경 불필요 여부 확인 대상)
- ProposalGenerator: LLMGateway를 통해 LLM을 사용하는 호출자 (변경 불필요 여부 확인 대상)
- AgentFactory: LLMGateway를 통해 LLM을 사용하는 호출자 (변경 불필요 여부 확인 대상)
- ToolFactory: LLMGateway를 통해 LLM을 사용하는 호출자 (변경 불필요 여부 확인 대상)

## 동작

1. **자극원**: 개발팀 (온디바이스 LLM 모델 업그레이드 또는 벤더 변경 결정)
2. **자극**: 온디바이스 LLM 모델을 다른 모델로 교체하는 변경 작업 착수
3. **반응 주체**: LLMGateway (수정 대상), 나머지 컴포넌트 (변경 영향 없어야 함)
4. **반응 흐름**:
   - 교체할 온디바이스 LLM 모델의 API 형식 및 추론 인터페이스 분석
   - LLMGateway 내부에서 모델 로딩, 추론 요청 형식, 응답 파싱 로직만 수정
   - IntentDetector, ProposalGenerator, AgentFactory, ToolFactory 등 LLMGateway를 호출하는 컴포넌트는 수정 없이 동작
   - 교체 후 통합 테스트를 통해 전체 시스템의 정상 동작 확인

## 측정

### 측정 항목
온디바이스 LLM 모델 교체 시 LLMGateway 외부에서 수정이 필요한 컴포넌트 수

### 측정 공식
```
C_external = count(LLMGateway 외부에서 코드/설정 수정이 필요한 컴포넌트)

측정 방법:
  - 교체 시나리오: Gemma → Phi, Gemma → Llama 각각에 대해 수행
  - 변경 파일 범위를 git diff로 추적하여 LLMGateway 패키지/모듈 경계 외부에서 수정된 파일 수 집계
  - 컴포넌트 단위: 패키지 또는 클래스 수준에서 변경 발생 여부로 판단

C_external = 0이 목표 (LLMGateway 내부 변경만으로 교체 완료)

추가 측정:
  T_replacement = 모델 교체 작업 완료까지 소요 시간 (개발자-시간, hour)
```

## 관련 문서
- QS-005 (온디바이스 LLM 추론 실패 처리)
- QS-011 (새로운 협상 도메인 추가 비용)
- QS-012 (A2A 프로토콜 버전 업데이트 비용)
- QS-013 (외부 서비스 API 교체 비용)
