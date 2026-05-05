# Usecase 분석

> 출처: `[SW Architect 팀과제] On-Device Agentic Platform.docx` — "Usecase 분석" 및 "On-device Agentic Platform: Use Case Specification" 섹션

## 주요 관심 사항

- Discovery
- Secure Connection
- Dynamic Agent Generation & Life Cycle Management

---

# On-device Agentic Platform: Use Case Specification

## 1. UC 01: Agent Discovery & Capability Registry

**목표:** 협상 대상이 되는 타 에이전트(PA, SA, DA)를 식별하고 수행 가능한 기능(Skill)을 확인합니다.

- **UC 01-1: Cloud-based Service Discovery**
  - **대상 시나리오:** PA ↔ SA, PA ↔ Multi-SA, 자녀 PA ↔ 부모 PA ↔ Medical SA
  - **설명:** 단말 외부의 서비스 에이전트를 찾기 위해 Cloud Registry에 쿼리를 송신하고 주소록을 수신함.
  - **설계 포인트:** 검색 결과에 대한 신뢰 등급(Reputation) 필터링 및 지연 시간 최소화를 위한 지역 기반 캐싱 전략.

- **UC 01-2: P2P Local Mesh Discovery**
  - **대상 시나리오:** PA ↔ PA, N-party PA, Multi-PA(가족) ↔ DA
  - **설명:** Wi-Fi Direct 또는 BLE를 사용하여 근거리 내의 다른 에이전트 존재를 확인.
  - **설계 포인트:** 배터리 소모 최적화를 위한 주기적 비컨(Beacon) 설계 및 개인정보 보호를 위한 Intent 해시 기반 비식별 탐색.

- **UC 01-3: Legacy Service Information Probing**
  - **대상 시나리오:** N-party PA ↔ Legacy Service
  - **설명:** 에이전트가 없는 서비스에 대해 웹 인터페이스나 메시지 데이터를 탐색하여 협상에 필요한 파라미터를 추출.
  - **설계 포인트:** LLM 기반의 비정형 데이터 정형화(Schema Extraction) 및 가상 에이전트 프로필 생성.

## 2. UC 02: Multi-layer Secure Connection

**목표:** 서로 다른 도메인(개인, 가족, 외부 서비스) 간에 신뢰할 수 있는 보안 통신 채널을 수립합니다.

- **UC 02-1: Peer-to-Peer End-to-End Encryption**
  - **대상 시나리오:** PA ↔ PA, N-party PA
  - **설명:** 삼성 계정 인증을 기반으로 에이전트 간 세션 키를 교환하고 통신 내용을 암호화.
  - **설계 포인트:** Perfect Forward Secrecy(PFS)를 보장하는 키 교환 알고리즘 적용 및 중간자 공격(MITM) 방지.

- **UC 02-2: Authority Delegation & Proxy Authentication**
  - **대상 시나리오:** 자녀 PA ↔ 부모 PA ↔ Medical SA
  - **설명:** 부모 PA가 자녀 PA에게 특정 목적(의료 예약)과 기간에 한정된 대리 권한을 위임.
  - **설계 포인트:** OAuth 2.0 기반의 범위 제한 토큰(Scoped Token) 발행 및 위임 이력에 대한 감사 로그(Audit Log) 생성.

- **UC 02-3: Device-to-Agent Secure Tunneling**
  - **대상 시나리오:** Multi-PA(가족) ↔ DA, DA ↔ PA ↔ A/S SA
  - **설명:** 가전(DA)과 관리 에이전트(PA) 간의 폐쇄형 보안 채널 수립.
  - **설계 포인트:** DA의 원시 데이터(Raw Data)가 외부로 직접 유출되지 않도록 PA 내부 샌드박스에서 데이터 정제(Sanitization) 후 전달.

## 3. UC 03: Multi-Agent Dynamic LifeCycle Management

**목표:** 필요한 시점에 에이전트를 동적으로 생성하고, 자원 효율을 위해 생명주기를 관리합니다.

- **UC 03-1: On-demand Agent Module Generation**
  - **대상 시나리오:** 모든 시나리오 (특히 복합 시나리오)
  - **설명:** IDS가 감지한 복합 Intent 수행에 필요한 에이전트 모듈(APK/DEX/WASM)을 서버에 요청하여 수신.
  - **설계 포인트:** 서버 측 에이전트 생성 엔진과의 연동 규약 및 전송 데이터 압축 최적화.

- **UC 03-2: On-device Deployment & Verification**
  - **대상 시나리오:** PA ↔ Multi-SA, DA ↔ PA ↔ A/S SA
  - **설명:** 수신된 에이전트 모듈의 서명(Signature)을 검증하고 런타임 환경에 적재.
  - **설계 포인트:** 시스템 리소스(NPU/RAM) 할당 및 타 에이전트와의 격리(Isolation) 환경 보장.

- **UC 03-3: Intelligent Eviction & Memory Management**
  - **대상 시나리오:** 모든 시나리오
  - **설명:** 협상 종료 후 에이전트의 재사용 가능성을 판단하여 자원을 회수.
  - **설계 포인트:** LRU(Least Recently Used) 알고리즘 기반 폐기 전략 및 상태 정보(Context)만 저장 후 코드를 언로드하는 계층적 캐싱.

## 4. UC 04: Negotiation Transaction & Orchestration

**목표:** 9개 상호작용 모델의 핵심인 '합의'와 '결과 확정' 프로세스를 관리합니다.

- **UC 04-1: Multi-party Consensus Handling**
  - **대상 시나리오:** N-party PA, N-party PA ↔ SA
  - **설명:** 다수의 에이전트 제안을 수렴하고 충돌 시 중재안을 도출하여 최종 승인을 획득.
  - **설계 포인트:** 2단계 커밋(2-Phase Commit) 스타일의 합의 프로토콜 및 타임아웃 처리.

- **UC 04-2: Recursive Transaction Rollback**
  - **대상 시나리오:** PA ↔ PA ↔ SA (예약 실패 시)
  - **설명:** 서비스 예약 실패 시 전체 협상 상태를 이전 유효 상태로 되돌리고 재협상을 트리거.
  - **설계 포인트:** 논리적 일관성 유지를 위한 스냅샷(Snapshot) 관리 및 재협상 전략 자동 업데이트.
