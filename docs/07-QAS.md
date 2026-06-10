# 품질 속성 시나리오 (Quality Attribute Scenarios)

> **본 문서는 [05-NFR.md](./05-NFR.md)에서 정의된 비기능 요구사항을 SEI 6-Part QAS 형식으로 구체화한 것이다.**
>
> **동기화 규칙**: `05-NFR.md`가 변경되는 경우 본 문서도 반드시 함께 갱신해야 한다.
> - NFR이 추가/삭제되면 → Utility Tree와 QAS 목록을 갱신한다.
> - NFR의 임계값·측정 구간이 바뀌면 → 대응되는 QAS의 **Response Measure**를 동일하게 갱신한다.
> - 각 QAS의 **Mapped NFR** 필드는 추적성(Traceability) 확보용이며, 누락 시 동기화 누락으로 간주한다.
>
> 품질 속성 분류는 **ISO/IEC 25010:2023** 기준을 따른다.
> 우선순위 표기 `[Business Value, Technical Risk]`는 각각 H/M/L로 표시한다.

---

## 1. Utility Tree

Utility Tree는 시스템의 품질 목표를 ISO/IEC 25010 품질 속성별로 분해하고, 각 리프 노드에 우선순위와 대응 NFR/QAS를 표시한다.

```
시스템 품질 (Utility)
│
├─ Performance Efficiency
│  ├─ Time Behaviour (응답성)
│  │  ├─ Intent 인지 알림 ≤ 2초                         [H, H] → NFR-IDS-01 / QAS-001
│  │  ├─ Communication 총 소요 ≤ 180초                  [H, H] → NFR-MAF-04 / QAS-002
│  │  ├─ Remote Monitoring 긴급 알림 ≤ 5초              [H, H] → NFR-MAF-04 / QAS-003
│  │  ├─ N-party Negotiation 선형 증가 (60+(N-2)·30초)  [H, M] → NFR-MAF-04 / QAS-004
│  │  ├─ 사용자 개입 반영 ≤ 2초                          [H, M] → NFR-MAF-05 / QAS-005
│  │  └─ Routing 판별 ≤ 1초 / 자체 Task ≤ 5초            [M, M] → NFR-IDS-02,03
│  ├─ Resource Utilisation
│  │  └─ IDS/MAF CPU·NPU·Memory 사용량 준수             [H, M] → NFR-IDS-04, NFR-MAF-06 / QAS-014
│  └─ Capacity / Scalability
│     └─ N-party 참여자 증가 시 자원 선형 확장            [H, H] → NFR-MAF-09 / QAS-010
│
├─ Reliability
│  ├─ Fault Tolerance
│  │  └─ 일시적 오류 자동 복구율 ≥ 99%                   [H, H] → NFR-MAF-01 / QAS-006
│  ├─ Recoverability
│  │  └─ 세션 복구 성공률 ≥ 95%                          [H, H] → NFR-MAF-03 / QAS-008
│  ├─ Maturity (성공률)
│  │  ├─ Communication Task 성공률 ≥ 95%                [H, H] → NFR-MAF-02 / QAS-007
│  │  └─ IDS 자체 Task 처리 성공률 ≥ 90%                 [H, M] → NFR-IDS-05 / QAS-009
│  └─ Consistency (분산 상태)
│     ├─ 다자간 협상 상태 불일치율 0%                    [H, H] → NFR-MAF-10 / QAS-011
│     └─ 다자간 합의 결과 불일치율 0%                    [H, H] → NFR-MAF-11 / QAS-012
│
├─ Security
│  └─ Confidentiality
│     └─ TLS 1.3 + Private Knowledge 외부 전송 0건       [H, H] → NFR-MAF-07 / QAS-013
│
└─ Maintainability (Traceability)
   └─ Communication 이력 추적
      └─ 이벤트 로그 100% / 조회 ≤ 2초                   [M, H] → NFR-MAF-08 / QAS-015
```

본 문서에서는 위 트리 중 `[H, H]` 및 일부 `[H, M]` 시나리오에 대해 6-Part QAS를 상세히 정의한다.
나머지 `[M, M]` 이하 항목은 NFR 명세로 갈음하며, 필요 시 후속 단계에서 QAS로 확장한다.

---

## 2. 품질 속성 시나리오 (QAS)

### QAS-001 Intent 인지 알림 2초 이내 표시
- **Source**: 사용자 (End User)
- **Stimulus**: 사용자가 명시적 또는 비명시적 Intent를 IDS에 전달함 (음성·텍스트 입력 모듈의 처리가 완료된 시점)
- **Artifact**: IDS Intent 인지 모듈, UI 알림 표시 컴포넌트
- **Environment**: 정상 운영 상태, 온디바이스 LLM 정상 로딩, 포그라운드 앱 동작 중
- **Response**: IDS가 Intent를 인지하고 "처리 중" 중간 피드백을 포함한 UI 알림을 사용자에게 표시함
- **Response Measure**: 알림 표시까지 **2초 이내** (Nielsen UX 응답성 임계값)
- **Mapped NFR**: NFR-IDS-01
- **Mapped QA leaf**: Performance Efficiency — Time Behaviour (Intent 인지 알림) [H, H]

---

### QAS-002 Communication 총 소요 시간 3분 이내 완료
- **Source**: MAF에 Task를 위임한 사용자 / Intent Detection System
- **Stimulus**: MAF에 Communication Task(Negotiation·Collaboration·Knowledge Sharing 등)가 전달됨
- **Artifact**: Meta Agent, Sub-Agent, Orchestrator, 상대 에이전트 통신 채널, Action 수행 모듈
- **Environment**: 정상 네트워크, 1:1 또는 N-party Communication, 온디바이스 LLM 정상 동작
- **Response**: Task 전달 시점부터 Action(캘린더 등록·예약 API 호출 등) 완료까지 정상 종결됨
- **Response Measure**: 총 소요 시간 **180초(3분) 이내** (백그라운드 처리 사용자 인내 허용치)
- **Mapped NFR**: NFR-MAF-04
- **Mapped QA leaf**: Performance Efficiency — Time Behaviour (Communication Latency) [H, H]

---

### QAS-003 Remote Monitoring 긴급 알림 5초 이내 전달
- **Source**: 모니터링 대상자(피보호자) 디바이스
- **Stimulus**: 피보호자 디바이스에서 이상 징후(낙상, 활력 징후 이상 등)가 감지됨
- **Artifact**: 모니터링 에이전트, 통신 채널, Caregiver 에이전트
- **Environment**: 정상 네트워크, 피보호자·Caregiver 디바이스 모두 활성
- **Response**: Caregiver 에이전트에 알림이 전달 완료됨
- **Response Measure**: 감지 시점 ~ 알림 전달 완료 시점 **5초 이내** (긴급 상황 대응)
- **Mapped NFR**: NFR-MAF-04 (Remote Monitoring 행)
- **Mapped QA leaf**: Performance Efficiency — Time Behaviour (긴급 알림) [H, H]

---

### QAS-004 N-Party Negotiation 선형 시간 증가 준수
- **Source**: 다자간 Negotiation을 시작한 사용자/에이전트
- **Stimulus**: 3인 이상(N≥3) 참여자가 협상 세션에 진입함
- **Artifact**: Meta Agent, N-1개 피어 메시지 처리기, 합의 판정 모듈
- **Environment**: 정상 네트워크, 참여자 수 N (검증 기준점: 3, 5, 7명)
- **Response**: 협상이 합의 또는 결렬 판정으로 종결됨
- **Response Measure**: **60 + (N-2) × 30초 이내** (검증점: 3명→90초, 5명→150초, 7명→210초)
- **Mapped NFR**: NFR-MAF-04 (N-party 행)
- **Mapped QA leaf**: Performance Efficiency — Time Behaviour (N-party 선형 증가) [H, M]

---

### QAS-005 사용자 개입 시 2초 이내 반영
- **Source**: 사용자 (End User)
- **Stimulus**: 진행 중인 Communication에 대해 사용자가 UI를 통해 직접 개입(취소·수정·우선순위 변경 등)을 수행함
- **Artifact**: UI, IDS Intent 변경 인지 경로, MAF Intent 적용 모듈
- **Environment**: 정상 운영, Communication 세션 진행 중
- **Response**: MAF가 변경된 Intent를 인지하고 내부 상태에 적용 완료
- **Response Measure**: 사용자 UI 조작 시점 ~ MAF Intent 적용 완료 시점 **2초 이내** (상대 에이전트 통보 등 후속 처리는 제외)
- **Mapped NFR**: NFR-MAF-05
- **Mapped QA leaf**: Performance Efficiency — Time Behaviour (사용자 개입 반영) [H, M]

---

### QAS-006 일시적 오류 자동 복구율 99% 이상
- **Source**: 네트워크/메시지 계층의 일시적 장애
- **Stimulus**: Communication 세션 진행 중 패킷 손실·일시적 연결 불안정·메시지 처리 실패가 발생함
- **Artifact**: 메시지 큐, 재전송 로직, 세션 상태 관리자, 통신 채널
- **Environment**: 일시적 네트워크 불안정(완전 단절은 NFR-MAF-03 범위로 제외)
- **Response**: 사용자 인지 없이 자동 재전송·재시도가 수행되어 세션이 중단 없이 정상 완료됨
- **Response Measure**: 일시적 오류 발생 케이스 중 자동 복구 완료율 **99% 이상**
- **Mapped NFR**: NFR-MAF-01
- **Mapped QA leaf**: Reliability — Fault Tolerance [H, H]

---

### QAS-007 Communication Task 성공률 95% 이상
- **Source**: MAF에 위임된 Communication 태스크 전체 모집단
- **Stimulus**: 다양한 케이스(Negotiation·Collaboration·Knowledge Sharing·Remote Monitoring)의 Task가 시작됨
- **Artifact**: MAF 전체(Meta/Sub/Orchestrator 및 통신 채널, Action 수행 모듈)
- **Environment**: 정상 운영 ~ 일시적 장애 혼재 환경
- **Response**: Task가 케이스별 정상 흐름(합의 타결 또는 합의 불가 판정 포함)으로 종결됨. 크래시·타임아웃 미처리·예외 미처리만 실패로 집계함
- **Response Measure**: 전체 시도 케이스 대비 기술적 Task 성공률 **95% 이상**
- **Mapped NFR**: NFR-MAF-02
- **Mapped QA leaf**: Reliability — Maturity (전체 Task 성공률) [H, H]

---

### QAS-008 세션 복구 성공률 95% 이상
- **Source**: 앱 강제 종료, 네트워크 완전 단절, OS 프로세스 재시작 등
- **Stimulus**: 진행 중이던 Communication 세션이 중단됨
- **Artifact**: 세션 상태 영속화 저장소, 세션 복구 매니저, 통신 채널 재수립 모듈
- **Environment**: 단절 후 연결이 복구된 상태, 세션 상태 저장 정보가 유효함
- **Response**: 중단 시점의 세션 상태를 복원하여 협상이 해당 시점부터 재개됨
- **Response Measure**: 복구 시도 케이스 중 정상 재개율 **95% 이상** (우선 적용: Negotiation)
- **Mapped NFR**: NFR-MAF-03
- **Mapped QA leaf**: Reliability — Recoverability [H, H]

---

### QAS-009 IDS 자체 Task 처리 성공률 90% 이상
- **Source**: IDS Routing 모듈이 "IDS 자체 처리"로 분류한 Task
- **Stimulus**: IDS가 단순 로컬 명령·정보 검색 수준의 Task를 자체 처리하기로 결정함
- **Artifact**: IDS Task 처리 모듈, 로컬 명령 실행기, 정보 검색 어댑터
- **Environment**: 정상 운영, 온디바이스 자원 정상
- **Response**: 기술적 오류(크래시·타임아웃·예외 미처리) 없이 결과가 반환됨 (의도 해석 정확도는 별도 평가)
- **Response Measure**: 자체 처리 Task 성공률 **90% 이상** (Production 95%+ 위한 초기 기준)
- **Mapped NFR**: NFR-IDS-05
- **Mapped QA leaf**: Reliability — Maturity (IDS 자체 처리) [H, M]

---

### QAS-010 N-Party 참여자 증가 시 자원 선형 확장
- **Source**: N-party Negotiation 시작 요청
- **Stimulus**: 참여자 수가 1명 증가함 (기준값: 1:1, CPU 피크 40% / Memory 300MB)
- **Artifact**: Meta Agent, 메시지 파서·라우터, 협상 상태 저장소, NPU 추론 엔진
- **Environment**: Galaxy S26(RAM 12~16GB) 기준 정상 운영, 다자간(N≥3) 협상 진행
- **Response**: 추가 참여자에 따른 자원 사용 증가가 선형(O(N)) 범위 내에서 제한됨
- **Response Measure**:
  - CPU 피크 증가분: **참여자 1명당 2% 이내** (3명→42%, 5명→46%, 7명→50% 이하)
  - Memory 증가분: **참여자 1명당 20MB 이내** (3명→320MB, 5명→360MB, 7명→400MB 이하)
- **Mapped NFR**: NFR-MAF-09
- **Mapped QA leaf**: Performance Efficiency — Capacity / Scalability [H, H]

---

### QAS-011 다자간 협상 상태 일관성 100%
- **Source**: 다자간 협상에 참여한 모든 에이전트
- **Stimulus**: 협상 라운드 진행 중 한 참여자가 제안·역제안·수락·거절·철회 등의 상태 변경을 발생시킴
- **Artifact**: 상태 동기화 프로토콜, 메시지 브로드캐스트 모듈, 참여 에이전트별 상태 저장소
- **Environment**: 다자간(N≥3) 협상 진행 중, 정상 네트워크
- **Response**: 모든 참여 에이전트가 동일한 "현재 협상 상태"(라운드, 제안 내용, 수락·거절 현황)를 공유함
- **Response Measure**:
  - 참여 에이전트 간 상태 불일치 발생률 **0%**
  - 상태 동기화 지연 **2초 이내**
  - 불일치 발생 시 해당 에이전트의 협상 진행은 일시 중단되어야 함
- **Mapped NFR**: NFR-MAF-10
- **Mapped QA leaf**: Reliability — Consistency (State Consistency) [H, H]

---

### QAS-012 다자간 합의 결과 일관성 100%
- **Source**: 다자간 협상 완료 시점의 모든 참여 에이전트
- **Stimulus**: N-party Negotiation이 합의 타결로 종결됨
- **Artifact**: 합의 결과 브로드캐스트 모듈, ACK 수집기, 후속 Action 트리거(FR-MAF-09)
- **Environment**: 다자간(N≥3) 협상 타결 직후
- **Response**: 모든 참여 에이전트가 동일한 최종 합의 결과를 수신·확인하고, 모든 ACK 완료 후에만 후속 Action(캘린더 등록·예약 API 호출 등)이 트리거됨
- **Response Measure**:
  - 합의 결과 불일치 발생률 **0%**
  - 합의 완료 기준: **모든 참여 에이전트의 ACK 수신** (단 1명 미확인도 미완료로 간주)
- **Mapped NFR**: NFR-MAF-11
- **Mapped QA leaf**: Reliability — Consistency (Consensus Consistency) [H, H]

---

### QAS-013 에이전트 간 통신 개인정보 보안
- **Source**: 외부 에이전트(상대방 디바이스), 잠재적 네트워크 도청자
- **Stimulus**: 에이전트 간 Communication을 위해 데이터 전송이 발생함
- **Artifact**: 통신 채널(TLS 계층), FR-MAF-05 지식 보안 등급 분류기, 전송 필터
- **Environment**: 모든 Communication(Discovery·Negotiation·Collaboration·Knowledge Sharing·Remote Monitoring) 상황
- **Response**: 전송 계층은 암호화되고, Private Knowledge로 분류된 항목은 외부로 전송되지 않음
- **Response Measure**:
  - 전송 계층 암호화: **TLS 1.3 이상**
  - Private Knowledge 외부 전송 건수: **0건**
- **Mapped NFR**: NFR-MAF-07
- **Mapped QA leaf**: Security — Confidentiality [H, H]

---

### QAS-014 IDS·MAF 온디바이스 자원 사용량 준수
- **Source**: 동시 동작하는 포그라운드 앱, OS 자원 관리자
- **Stimulus**: IDS·MAF가 백그라운드에서 Intent 인지·Communication을 수행함
- **Artifact**: IDS 백그라운드 서비스, MAF Meta/Sub-Agent, 온디바이스 LLM 추론 엔진
- **Environment**: Galaxy S26 기준 (Android, RAM 12~16GB, NPU 탑재), 포그라운드 앱 활성
- **Response**: 자원 사용이 임계값 내에서 유지되어 포그라운드 앱 성능에 영향을 주지 않음
- **Response Measure**:
  - **IDS**: CPU 평균 10% / 피크 25% / NPU 70% / Memory 200MB 이하
  - **MAF (1:1 기준)**: CPU 평균 15% / 피크 40% / NPU 70% / Memory 300MB 이하
- **Mapped NFR**: NFR-IDS-04, NFR-MAF-06
- **Mapped QA leaf**: Performance Efficiency — Resource Utilisation [H, M]

---

### QAS-015 Communication 이력 추적 완전성 및 조회 응답성
- **Source**: 사용자, 분쟁 조정자, 디버깅 담당자
- **Stimulus**: Communication 진행 중 상태 전이(제안·수락·거절·세션 수립·이상 징후 알림 등)가 발생하거나, 사용자가 이력을 조회함
- **Artifact**: 이벤트 로깅 모듈, 이력 저장소, 사용자 이력 조회 UI(FR-MAF-07)
- **Environment**: 모든 Communication 케이스, 정상 운영 상태
- **Response**: 모든 상태 전이 이벤트가 누락 없이 기록되고, 사용자 조회 시 즉시 응답함
- **Response Measure**:
  - 이벤트 로그 기록률 **100%**
  - 사용자 이력 조회 응답 시간 **2초 이내**
- **Mapped NFR**: NFR-MAF-08
- **Mapped QA leaf**: Maintainability — Traceability [M, H]

---

## 3. 본 문서에서 제외된 항목

다음 NFR은 QAS화 우선순위가 낮거나 NFR 명세로 갈음한다. 향후 단계에서 필요 시 QAS를 추가한다.

- **NFR-IDS-02 (Routing 처리 속도)**, **NFR-IDS-03 (IDS 자체 Task 처리 속도)**:
  Utility Tree 우선순위 `[M, M]`. NFR-IDS-01(2초)과 NFR-IDS-05(성공률)에 의해 사용자 가시 영역은 이미 보장됨.

---

_본 문서는 2026-06-10 작성되었으며, [05-NFR.md](./05-NFR.md)의 변경에 종속된다._
