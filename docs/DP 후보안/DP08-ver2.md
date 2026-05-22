# DD-08 / 협상 테이블 Deployment 아키텍처 (v2)

> **문서 성격**: Design Decision 후보 (DP)
>
> **관련 결정**: [`../99-Design-Decision-후보-정제본.md`](../99-Design-Decision-후보-정제본.md) DD-08
>
> **관련 NFR·QAS**:
> - QS-002 (A2A 협상 완료 시간), QS-004 (동시 Agent 메모리), QS-019 (협상 내 개인/기기 정보 최소화)
> - NFR06 (세션 복구), NFR12 (최소 데이터 보관), NFR17 (모듈 경계), NFR19 (Agent 수 증가 대응)
> - NFR-006 (협상 제안 내 불필요 정보 노출 0%)
>
> **관련 DP**: [`./QS-002-프라이버시-보존-협상-속도.md`](./QS-002-프라이버시-보존-협상-속도.md) (메시지 단위 privacy 통제)
>
> **본 문서의 위치**: Network protocol (MQTT / WebSocket / WebRTC 등) 결정 위에서 동작하는 **state ownership·deployment topology** 결정. 협상의 canonical state가 어디 살고 누가 그것을 관리하는지에 대한 결정.

---

## 0. 풀고자 하는 문제

**N명의 사용자 디바이스 간 협상에서, 협상 상태(테이블)와 데이터 ownership을 어디에 둘 것인가**.

수년간의 product 운영을 가정할 때 이 결정은 다음 여섯 축을 동시에 결정함:

| 축 | 의미 |
|---|---|
| 데이터 ownership·규제 부합 | GDPR·K-PII 등에서 "이 데이터는 누구 것이고 어디 보관되는가" 답이 명확해야 함 |
| 사용자 trust 모델 | 가족·친구·낯선이 등 다양한 신뢰 수준 그룹을 포괄해야 함 |
| 차별화 잠재력 | Samsung ecosystem의 구조적 우위(TV·가전·폰) 활용 가능 여부 |
| Long-running·recurring 협상 지원 | "매주 가족 식사" 같은 지속 협상의 자연 home 여부 |
| 버전 일관성 운영 | 수억 단위 사용자 base에서 algorithm version mismatch 처리 |
| Lock-in 잠재력 | 사업 모델 측면의 ecosystem 강결합 |

---

## 1. 결정의 본질 — 3축 분해

본 결정은 처음에 single dimension으로 보이지만, 사실 **세 개의 독립적 축의 조합**임. 후보 비교 전에 이 분해를 먼저 명확히 함.

| 축 | 옵션 | 본 결정에서의 위치 |
|---|---|---|
| **Routing** (메시지 분배 인프라) | Cloud broker / Cloud relay / WebRTC + signaling | 모바일 NAT 제약으로 어떤 후보든 외부 인프라 필요. **Implementation detail** — 후보를 가르는 본질이 아님 |
| **State storage** (협상 테이블 위치) | 분산 (모든 폰) / 중앙집중 (한 곳) | **본질적 결정 ★** |
| **Solver execution** (algorithm 실행 위치) | 분산 (각 폰이 deterministic) / 중앙집중 (한 곳) | State storage와 실무적으로 같이 결정됨 |

State와 Solver는 실무적으로 항상 같은 위치에 있음 (분산이면 둘 다 분산, 중앙이면 둘 다 중앙). 그래서 본 결정은 **두 단계 질문으로 좁혀짐**:

1. **State·Solver를 분산할 것인가, 중앙집중할 것인가?** (1단계 결정)
2. **중앙집중이라면 어디에?** (참여자 한 명의 폰 vs 가정 hub — 2단계 결정)

Routing 어떻게 하느냐 (MQTT broker · WebSocket relay · WebRTC) 는 이 결정 *위에서* 따라 나옴.

---

## 2. 해결 후보

세 후보가 있지만, **본질적으로 후보 1 vs (후보 2·3) 의 양자택일이 1단계 결정**이고, 후보 2 vs 3는 중앙집중 안에서의 sub-선택임. 이 관계를 표로 미리 보이면:

```
        ┌─ 후보 1. Federated  (분산형)
        │
결정 ───┤
        │                    ┌─ 후보 2. Initiator-Hosted  (참여자 한 명의 폰)
        └─ 중앙집중형 ───────┤
                             └─ 후보 3. Home Hub-Hosted  (가정 hub)
```

### 후보 1. Federated — State·Solver 분산

#### 배치

```
A 폰          B 폰          C 폰          D 폰
[협상 사본]   [협상 사본]   [협상 사본]   [협상 사본]
   ↕              ↕              ↕              ↕
   └──── 메시지 분배 layer (broker) ──────────┘
```

협상 테이블이 **N개 사본** — 각 사용자 폰에. 모두 같은 algorithm으로 deterministic하게 같은 상태에 수렴. 데이터는 자기 폰 밖으로 안 나감. Broker는 메시지 분배만 담당하고 협상 state는 모름.

#### 진행

1. Initiator가 session 생성 → 참여자에게 invitation
2. 각 폰이 user 데이터로부터 자기 제약 추출 (LLM)
3. 모두 broker 통해 제약 broadcast
4. 각 폰이 자기 안에서 같은 solver 실행 → 같은 결과
5. 각자 Y/N publish → 합의 성립
6. 협상 종료 → 각자 history 유지 또는 삭제 (사용자 선택)

#### 장점

- **단일 실패점 없음** — N-1 폰이 살아 있으면 협상 가능
- **확장성 최강** — N 증가에 중앙 capacity 한계 없음
- **운영 비용 최소** — broker 인프라만
- 사용자가 자기 raw data의 실제 owner
- 외부 (cloud) 측 privacy 강함 — E2E 암호화 시 broker는 메타데이터만

#### 단점

- **버전 호환성이 운영의 핵심 risk** — 모든 폰이 같은 algorithm version이어야 deterministic 일관성. 강제 업데이트 안 되면 silent divergence (서로 다른 결과 도출) → 협상 결과 신뢰성 망가짐. 수억 사용자 base에서 fragmentation은 일상적 문제
- **Long-running·recurring 협상에 어색함** — 협상 history가 분산이라 "매주 가족 식사" 같은 recurring sync 부담
- **Samsung ecosystem 차별화 약함** — 어떤 회사도 만들 수 있는 generic model. 가전·TV ecosystem 자산 미활용
- **친구 사이 privacy는 오히려 약함** — 모든 참여자가 다른 모든 참여자의 constraint를 손에 갖게 됨 (대칭 노출)

### 후보 2. Initiator-Hosted — State·Solver를 참여자 한 명의 폰에 집중

#### 배치

```
A 폰 (initiator)              B·C·D 폰
[협상 테이블 ★]               [thin client]
[history DB]                  
       ▲                        │
       ├──── 메시지 (relay 경유) ─┤
       └──── 메시지 ─────────────┤
                              ─┘
```

협상 테이블 **1개** — initiator 폰에만. 다른 참여자는 thin client. Initiator가 데이터 owner이자 결정 권한 보유. 메시지 라우팅은 NAT 제약상 cloud relay 경유 필요.

#### 진행

1. Initiator가 session 생성 (자기 폰에 host 모듈 기동)
2. 참여자 초대 → 폰들이 thin client로 join
3. 참여자가 자기 제약을 initiator 폰에 전송 (cloud relay 통해)
4. Initiator 폰에서 algorithm 실행 → 결과 결정
5. Initiator가 모두에게 broadcast
6. History는 initiator 폰에 누적

#### 장점

- **App 모델 단순** — 게임 lobby·Zoom 호스트 같은 검증된 host-client 패턴
- **합의 권한 명확** — initiator가 분쟁 해소 가능
- Initiator 폰이 협상 SoT 이므로 long-running 협상 가능 (단 initiator 의존)
- **참여자 간 privacy** — initiator 외에는 다른 사람의 constraint를 못 봄 (Federated 대비 우월)

#### 단점

- **Initiator가 협상 데이터 다 봄** — 다른 참여자가 initiator를 trust해야 함. 친구·가족 OK, 회사·낯선이 위험
- **Initiator 폰 가용성 = 협상 가용성** — 폰 분실·교체·방전 시 협상 history 잃을 위험. Cloud backup 별도 설계 시 사실상 cloud-hosted 모델로 변질
- **Initiator 부담 비대칭** — 자주 host되는 사람의 폰 자원·history 누적
- Samsung ecosystem 차별화 측면 generic
- **본질적으로 후보 3의 약화 버전** — 24/7 가용성 X, 가전 데이터 활용 X, hub의 강점 모두 결여

### 후보 3. Home Hub-Hosted — State·Solver를 가정 hub에 집중

#### 배치

```
                [Samsung TV / SmartThings Hub / 가전]
                [협상 테이블 ★]
                [가족 history DB]
                [가전 사용 패턴 데이터]
               ╱    ╱    ╲    ╲
             폰A   폰B   폰C   폰D
            (가족 구성원, hub에 인증된 상태)
```

협상 테이블 **1개** — 가정의 hub 디바이스 (Samsung TV·SmartThings hub·냉장고) 에. 24/7 동작. Hub가 가전 ecosystem 데이터까지 보유 → 협상 input으로 활용.

#### 진행

1. 가족 구성원 폰이 가정 hub에 인증 (입주·동거 시작 시 1회)
2. 협상 발생 시 hub가 session 생성
3. 폰들이 자기 제약을 hub로 전송 (가정 wifi or cloud relay)
4. Hub는 가전 데이터까지 같이 고려해서 algorithm 실행
5. 결과를 모두에게 broadcast
6. History를 hub에 누적 → 다음 협상이 이전 history 참조 가능

#### 장점

- **Samsung 차별화의 핵심** — Samsung은 TV·가전·폰을 모두 보유한 유일한 회사. **Apple·Google·OpenAI가 못 만드는 그림**. 본 product의 가장 강한 strategic moat
- **Long-running·recurring 협상 자연 지원** — 24/7 hub가 history·schedule 보관
- **가전 ecosystem 데이터를 협상 input으로 활용** — 결과 품질이 다른 솔루션 추격 불가
- 가족 단위의 trust anchor — 일상에서 사용자가 자연 이해
- **Lock-in 잠재력 강함** — Samsung 생태계 진입 깊이 ↔ 가치 증가
- 가족 단위 데이터 ownership이 hub로 명확 → GDPR documentation 단순
- 펌웨어 업데이트 cycle이 한 곳 (hub) 에 집중 → 버전 fragmentation risk 낮음

#### 단점

- **가족 외 협상 안 됨** — hub의 trust boundary가 가정 단위. 친구·회사 협상은 별도 모델 필요. 단독 솔루션이 못 됨
- **하드웨어 의존** — Samsung TV·hub 없는 가정엔 적용 불가. 첫 사용자 진입 장벽
- 펌웨어 업데이트 cycle이 폰보다 느림 — TV·가전 OTA는 보수적 운영
- Hub 하드웨어 failure가 협상 가용성 단절 → cloud backup·redundancy 별도 설계 필요
- 가족 구성 변경 처리 까다로움 (입주·퇴거·이혼) — policy·UX 양 측면

---

## 3. 후보 간 본질 관계

### 1단계 결정: 분산 vs 중앙집중 (후보 1 vs 2·3)

| 측면 | 후보 1 (Federated) | 후보 2·3 (Centralized) |
|---|---|---|
| State 보유 | 모든 폰에 분산 | 한 곳에 집중 |
| Solver 실행 | 각 폰이 deterministic | 집중된 곳에서만 |
| 친구 사이 privacy | 모두가 모두 봄 (대칭 노출) | 중앙 호스트만 봄 (비대칭) |
| 단일 실패점 | 없음 | 중앙 호스트 |
| Long-running 협상 | 어색 (sync 부담) | 자연 |
| 가전 데이터 활용 | 불가 | (3의 경우) 가능 |
| 버전 일관성 risk | 높음 (silent divergence) | 낮음 (호스트가 truth) |

### 2단계 결정: 중앙집중 위치 (후보 2 vs 3)

| 측면 | 후보 2 (Initiator) | 후보 3 (Home Hub) |
|---|---|---|
| 호스트 디바이스 | 참여자 한 명의 폰 | 가정의 hub 디바이스 |
| 가용성 | 폰 의존 (켜져 있어야) | 24/7 |
| 가전 데이터 활용 | 불가 | 가능 |
| Samsung 차별화 | Generic | 유일 가능 |
| Trust anchor | 한 명의 참여자 | 가족·세대 |
| Long-running 안정성 | 약함 | 강함 |

→ **후보 2는 후보 3가 적용 불가한 환경 (hub 없는 가정·가족 외 그룹) 에서의 약화 버전 역할만 함**. Product 단계에서 후보 2를 단독 선택할 합리적 이유는 없음.

---

## 4. QA Tradeoff 평가

| 품질 속성 | 1. Federated | 2. Initiator-Hosted | 3. Home Hub |
|---|---|---|---|
| 외부 (cloud) 측 privacy | ◎ 메타만 노출 | ◎ 메타만 노출 | ○ 메타만 (가정 LAN 시 더 강함) |
| 참여자 간 privacy | △ 모두가 모두 봄 | ○ host만 봄 | ○ hub만 봄 (가족 내) |
| 확장성 (N 증가) | ◎ 한계 없음 | △ initiator 폰 한계 | ○ hub 용량 한계 |
| 신뢰성 (단일 실패점) | ◎ 분산 | ✗ initiator 단일 | △ hub 단일 |
| 운영 비용 | ◎ broker만 | ◎ infra 없음 | △ hub 펌웨어·cloud sync |
| Samsung 차별화 | △ generic | △ generic | ◎ 유일 가능 |
| Lock-in 잠재력 | △ 약함 | △ 약함 | ◎ ecosystem 강결합 |
| Long-running 협상 | △ 어색 | ○ initiator 의존 | ◎ 자연 |
| 데이터 풍부도 | △ user 데이터만 | △ user 데이터만 | ◎ + 가전 데이터 |
| Trust 모델 명확성 | ◎ 자기만 | △ initiator 신뢰 | ○ 가족 신뢰 |
| 버전 호환성 관리 | ✗ silent divergence 위험 | ◎ host 버전이 truth | ◎ hub 버전이 truth |
| GDPR 부합 | ◎ 최소 데이터 | △ ownership 모호 | ○ 가족 단위 명확 |

### 종속·상충 관계

- 후보 1 ↔ 후보 3: 상충 (분산 vs 중앙). 단 협상 도메인 (가족·smart home vs 친구·회사) 기준 분기 라우팅으로 공존 가능
- 후보 2는 후보 3의 약화 버전 → product에서 후보 2를 단독 선택할 합리적 이유 없음
- Routing 인프라 (broker / relay) 는 어느 후보든 필요 → 후보 선택의 결정 변수 아님

---

## 5. 권고

**진짜 결정은 후보 1 (Federated) vs 후보 3 (Home Hub) 두 갈래**. 후보 2 (Initiator-Hosted) 는 hub 없는 사용자를 위한 fallback 으로만 가치.

### 2-Tier Deployment 채택

| Tier | 후보 | 적용 도메인 | 근거 |
|---|---|---|---|
| **Tier 1** | 후보 3. Home Hub | 가족·smart home 협상 (가전 사용 조율·가족 일정·가정 자원 분배) | Samsung 구조적 차별화. Apple·Google·OpenAI 누구도 못 만드는 그림 |
| **Tier 2** | 후보 1. Federated | 친구·회사·낯선이 협상 | Hub의 trust boundary 밖. 강력한 privacy 마케팅 메시지 |
| Fallback | 후보 2. Initiator-Hosted | Hub 없는 가정의 가족 협상 | Hub 없는 신규 사용자를 위한 진입 경로. 장기적으로 Hub 보급과 함께 deprecation |

### 라우팅 정책

협상 시작 시 IDS의 intent classification으로 자동 라우팅:

```
Intent 분류 → Tier 결정
├ "가족 협상" + Hub 인증됨        → Tier 1 (Home Hub)
├ "가족 협상" + Hub 없음          → Fallback (Initiator-Hosted, 향후 deprecation)
├ "친구·회사 협상"                → Tier 2 (Federated)
└ Hub failure 발생 시             → Tier 2로 graceful degradation
```

두 Tier는 **동일 제약 schema·동일 algorithm 공유** → 사용자 UX는 일관, 내부 deployment만 분기.

### 후보 2를 fallback으로만 두는 이유 (단독 선택 안 하는 이유)

- Hub 적용 불가 환경 (Hub 보급 전·가족 외) 의 유일한 중앙집중 선택지
- 그러나 24/7 가용성·가전 데이터·Samsung 차별화 모두 결여
- Cloud backup 추가 시 사실상 cloud-hosted 모델로 변질 → 별도 architecture 결정 필요
- Hub 보급률이 충분해지면 deprecation 가능한 경로

---

## 6. 열린 이슈 (Open Questions)

본 결정 이후 추가 결정이 필요한 영역:

- **Hub failure 시 fallback** — Tier 1 운영 중 hub 장애 시 Tier 2로 transparent fallback 가능 여부와 fallback 시 history 처리 방식
- **가족 구성 변경 정책** — 입주·퇴거·이혼 시 hub의 인증된 폰 목록·history 처리. 본 product의 hidden UX cost가 가장 큰 영역
- **Cross-Tier 협상** — "가족 + 친구" 혼합 협상 (예: 가족 + 친구 1명이 함께 저녁 식사) 발생 시 어느 Tier에 위치할지
- **Hub 펌웨어 호환성** — TV 펌웨어 cycle과 폰 app 업데이트 cycle 간 schema 호환성 관리 방식
- **Multi-Hub 가정** — 한 가정에 Samsung TV + 냉장고 + Hub 셋이 모두 있는 경우 어느 디바이스가 협상 테이블 host인지
- **Hub 부재 시 Fallback의 ownership 정책** — Cloud backup 없이는 폰 분실 = history 분실. 이걸 사용자에게 어떻게 설명할지

---

## 7. 설계 뷰 (UML) — TBD

본 결정의 컴포넌트 뷰·시퀀스 뷰·deployment 뷰는 결정 채택 후 별도 문서 `./DD-08-design-views.md` 에 정리 예정.

---

## 변경 이력

| 일자 | 버전 | 변경 | 작성 |
|---|---|---|---|
| 2026-05-21 | v1 | 초안 작성 — 3개 후보 평등 비교 | 협의 결과 정리 |
| 2026-05-22 | v2 | 결정 framing 재구성. 본질이 "분산 vs 중앙집중" 의 1단계 결정이고, 중앙집중 안에서의 위치 선택이 sub-결정임을 명확화. 후보 2 (Initiator-Hosted) 는 후보 3의 약화 버전으로 재분류, fallback으로 격하. 3축 분해 (Routing/State/Solver) 섹션 추가하여 routing 인프라가 implementation detail임을 명시 | 추가 협의 반영 |
