# QS-002 프라이버시 보존 협상 속도 — 설계 뷰 (UML)

> 본 문서의 다이어그램은 Mermaid로 작성되어 GitHub에서 그대로 렌더링된다.
> 후보 구조 본문은 [`QS-002-프라이버시-보존-협상-속도.md`](./QS-002-프라이버시-보존-협상-속도.md) 참조.

---

## 1. 컴포넌트 뷰 — 프라이버시 경계와 출구 게이트 (공통)

기기 밖으로 데이터가 나가는 출구는 **두 곳뿐**이며(서버 LLM행, 상대 PPA행), 모든 후보는 이 두 출구를 강제 게이트로 막는다.

```mermaid
flowchart TB
    subgraph Device["📱 Android Phone (온디바이스 경계 — 원문 PII 보존)"]
        IDS["IDS / IntentDetector"]
        NC["NegotiationController"]
        PG["ProposalGenerator"]
        CTX["ContextAggregator"]
        AUTH["AuthorizationChecker"]
        DPI["DeviceProxyInterface"]
    end

    subgraph Gates["🔒 강제 출구 게이트 (우회 불가)"]
        GW["LLMGateway<br/>+ PII 필터 (NFR-005)"]
        A2A["A2AProtocolAdapter<br/>+ 정보최소화 필터 (NFR-006)"]
    end

    SRV["☁️ 서버 LLM<br/>(Task 분해)"]
    PPA["🤝 상대방 PPA"]
    DPA["🔌 DPA (가전)"]

    IDS --> NC
    CTX --> PG
    DPI --> CTX
    NC --> PG
    PG -->|제안| AUTH
    AUTH -->|권한 통과분만| A2A
    IDS -->|Task 분해 요청| GW

    GW ==>|"PII 0% 보장"| SRV
    A2A ==>|"불필요정보 0% 보장"| PPA
    DPA -.->|컨텍스트| DPI

    classDef gate fill:#ffe6e6,stroke:#cc0000,stroke-width:2px;
    classDef ext fill:#eef,stroke:#558;
    class GW,A2A gate;
    class SRV,PPA,DPA ext;
```

---

## 2. 컴포넌트 뷰 — 후보별 차이

### CA-DP1: 인라인 동기 필터

```mermaid
flowchart LR
    PG["ProposalGenerator"] --> A2A["A2AProtocolAdapter<br/>【인라인 동기 필터】"]
    A2A -->|매 라운드 동기 필터| PPA["상대 PPA"]
    note["⏱ 매 라운드 T_privacy_filter 누적"]
    A2A -.- note
    classDef n fill:#fff7e6,stroke:#d48806;
    class note n;
```

### CA-DP2: 세션 토큰화 + 안전범위 사전 컴파일

```mermaid
flowchart TB
    subgraph Once["세션 시작 시 1회"]
        VAULT["PrivacyVault<br/>PII·기기ID → 토큰 매핑"]
        SCOPE["NegotiationScopeCompiler<br/>안전 협상범위 사전 컴파일"]
    end
    subgraph PerRound["라운드 N회 (원문 접근 불가)"]
        PG["ProposalGenerator<br/>(토큰·안전범위만 사용)"]
    end
    AUTHDB[("AuthorizationDB")]
    DPI["DeviceProxyInterface"]
    A2A["A2AProtocolAdapter"]
    EXEC["BookingExecutor / DeviceCommandGenerator<br/>(합의 후 de-tokenize 실행)"]

    AUTHDB --> SCOPE
    DPI --> SCOPE
    SCOPE --> PG
    VAULT --> PG
    PG --> A2A
    VAULT -->|토큰→원문 복원| EXEC

    classDef new fill:#e6ffed,stroke:#1a7f37,stroke-width:2px;
    class VAULT,SCOPE new;
```

### CA-DP3: 비동기 파이프라인 + 전송 직전 동기 게이트

```mermaid
flowchart LR
    PG["ProposalGenerator"] -->|라운드 N 제안| EG["EgressPrivacyGate<br/>【전송 직전 동기 검증】"]
    PG -.->|라운드 N+1 필터링<br/>비동기 선행| PRE["PreFilter Worker"]
    PRE -.->|준비된 후보| EG
    EG ==>|"미통과 시 차단 (NFR 사수)"| PPA["상대 PPA"]

    classDef gate fill:#ffe6e6,stroke:#cc0000,stroke-width:2px;
    classDef async fill:#e6f4ff,stroke:#0958d9,stroke-dasharray:4 3;
    class EG gate;
    class PRE async;
```

---

## 3. 시퀀스 뷰 — CA-DP2 협상 라운드 (권고안)

```mermaid
sequenceDiagram
    autonumber
    participant NC as NegotiationController
    participant SC as NegotiationScopeCompiler
    participant PV as PrivacyVault
    participant PG as ProposalGenerator
    participant GT as A2AProtocolAdapter(게이트)
    participant OP as 상대 PPA
    participant EX as BookingExecutor

    Note over NC,EX: 세션 시작 (1회) — 프라이버시 경계 설정
    NC->>SC: 안전 협상범위 컴파일 요청 (AuthScope + DPA 컨텍스트)
    SC-->>NC: 노출 가능 변수집합(가격·날짜 범위 등 사실값)
    NC->>PV: PII·기기ID 토큰화
    PV-->>NC: 토큰 매핑 생성 완료

    loop 라운드 N (원문 미도달 → 라운드당 필터 비용 0)
        NC->>PG: 제안 생성 요청(토큰·안전범위만)
        PG-->>NC: NegotiationProposal(토큰)
        NC->>GT: 전송
        GT->>OP: A2A 제안 (암호화·NFR-006 충족)
        OP-->>GT: 반제안
        GT-->>NC: 디코딩 전달
        NC->>NC: 합의/교착 판정
    end

    Note over NC,EX: 합의 후 — 온디바이스에서만 원문 복원
    NC->>PV: 토큰 → 원문 복원
    PV-->>EX: 원문 결합 실행 컨텍스트
    EX->>EX: 실제 예약 / 기기 반영
```

---

## 4. 상태 뷰 — 협상 세션과 프라이버시 경계

```mermaid
stateDiagram-v2
    [*] --> 세션초기화
    세션초기화 --> 경계설정: 토큰화 + 안전범위 컴파일
    경계설정 --> 라운드진행: 토큰·안전범위만 노출
    라운드진행 --> 라운드진행: 제안/반제안 (PII 미포함)
    라운드진행 --> 교착: N회 합의 실패
    교착 --> 라운드진행: 대안 제안
    라운드진행 --> 합의도출: 조건 충족
    교착 --> 사용자개입: 반복 교착
    사용자개입 --> 라운드진행: 조건 수정(재컴파일)
    합의도출 --> 원문복원: 온디바이스 de-tokenize
    원문복원 --> 실행완료: 예약/기기 반영
    실행완료 --> [*]

    note right of 경계설정
        이 시점 이후 ProposalGenerator는
        원문 PII에 접근 불가 (NFR-006 설계상 보장)
    end note
```

---

## 5. 측정 매핑

| 다이어그램 요소 | 측정 지표 | 요구사항 |
|------------------|-----------|----------|
| 출구 게이트(LLMGateway) | `R_pii_leak = 0%` | NFR-005 / QS-009 |
| 출구 게이트(A2AProtocolAdapter) | `R_unnecessary_info = 0%` | NFR-006 / QS-019 |
| 라운드 루프 총 시간 | `T_negotiation` (분), 라운드 수 N | QA-001 / QS-002 |
| 라운드당 필터 비용 | `T_privacy_filter` per round | DP-2 효과 검증 |
