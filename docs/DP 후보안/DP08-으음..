# DD-08 / 협상 테이블 Deployment 아키텍처

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
> **본 문서의 위치**: Network protocol (MQTT / WebSocket / WebRTC 등) 결정 *위에서* 동작하는 **state ownership·deployment topology** 결정. 협상 메시지가 wire 위에서 어떻게 흐르는지가 아니라, **협상의 canonical state가 어디 살고 누가 그것을 관리하는지**에 대한 결정.

---

## 0. 풀고자 하는 문제

**N명의 사용자 디바이스 간 협상에서, 협상 상태(테이블)와 데이터 ownership을 어디에 둘 것인가**.

수년간의 product 운영을 가정할 때 이 결정은 다음 여섯 축을 동시에 결정함:

| 축 | 의미 |
|---|---|
| 데이터 ownership·규제 부합 | GDPR·K-PII 등에서 "이 데이터는 누구 것이고 어디 보관되는가" 답이 명확해야 함 |
| 사용자 trust 모델 | 가족·친구·낯선이 등 다양한 신뢰 수준 그룹을 포괄해야 함 |
| 차별화 잠재력 | Samsung ecosystem의 구조적 우위 (TV·가전·폰) 활용 가능 여부 |
| Long-running·recurring 협상 지원 | "매주 가족 식사", "매월 자원 분배" 같은 지속 협상의 자연 home 여부 |
| 버전 일관성 운영 | 수억 단위 사용자 base에서 algorithm version mismatch 처리 |
| Lock-in 잠재력 | 사업 모델 측면의 ecosystem 강결합 |

협상은 결국 **상태 가진 entity**다. "지금 어떤 제약들이 모였고, 어디까지 합의됐고, 누가 응답 안 했고…" 같은 상태가 어딘가 살아 있어야 함. 그 *어디* 가 deployment 결정이고, 본 문서가 다루는 결정 영역임.

---

## 1. 해결 후보

세 가지 본질적으로 다른 후보가 있음. 각각의 trust 모델·운영 모델·차별화 잠재력이 다름.

### 후보 1. Federated — 각 폰이 sovereign

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

- **Privacy 최강** — 데이터가 폰 밖으로 안 나감. GDPR·K-PII 부합 측면에서 가장 안전. 마케팅 메시지("당신 데이터는 당신 폰에만") 강력
- **단일 실패점 없음** — N-1 폰이 살아 있으면 협상 가능
- **확장성 최강** — N 증가에 중앙 capacity 한계 없음
- **운영 비용 최소** — broker 인프라만
- 사용자가 자기 데이터의 실제 owner

#### 단점

- **버전 호환성이 운영의 핵심 risk** — 모든 폰이 같은 algorithm version이어야 deterministic 일관성. 강제 업데이트 메커니즘 필요. 안 그러면 silent divergence(서로 다른 결과 도출) → 협상 결과 신뢰성 망가짐. 수억 단위 사용자 base에서 버전 fragmentation은 일상적 문제
- **Long-running·recurring 협상에 어색함** — 협상 history가 분산이라 "매주 가족 식사" 같은 recurring sync 부담
- **Samsung 차별화 약함** — 어떤 회사도 만들 수 있는 generic model. 가전·TV ecosystem 자산 미활용
- 각 폰이 모든 참여자의 제약을 보유함 (자기 것은 자기가 만들지만, 받은 것은 모두 가짐) → 참여자 간 privacy gradient 존재

---

### 후보 2. Initiator-Hosted — 시작한 사람이 host

#### 배치

```
A 폰 (initiator)              B·C·D 폰
[협상 테이블 ★]               [thin client]
[history DB]                  
       ▲                        │
       ├──── 메시지 ─────────────┤
       └──── 메시지 ─────────────┤
                              ─┘
```

협상 테이블 **1개** — initiator 폰에만. 다른 참여자는 thin client. Initiator가 데이터 owner이자 결정 권한 보유.

#### 진행

1. Initiator가 session 생성 (자기 폰에 host 모듈 기동)
2. 참여자 초대 → 폰들이 thin client로 join
3. 참여자가 자기 제약을 initiator 폰에 전송
4. Initiator 폰에서 algorithm 실행 → 결과 결정
5. Initiator가 모두에게 broadcast
6. History는 initiator 폰에 누적

#### 장점

- **App 모델 단순** — 게임 lobby·Zoom 호스트 같은 검증된 host-client 패턴
- **합의 권한 명확** — initiator가 분쟁 해소 가능
- 운영 인프라 없음 (P2P 메시지 layer만)
- Initiator 폰이 협상 SoT(Source of Truth) 이므로 long-running 협상 가능 (단 initiator 의존)

#### 단점

- **Initiator가 협상 데이터 다 봄** — 다른 참여자가 initiator를 trust해야 함. 친구·가족 OK, 회사·낯선이 위험
- **Initiator 폰 가용성 = 협상 가용성** — 폰 분실·교체·방전 시 협상 history 잃을 위험. Cloud backup 별도 설계 필요 (그러면 cloud-hosted 모델로 사실상 변질)
- **Initiator 부담 비대칭** — 자주 host되는 사람의 폰 자원·history 누적
- **데이터 ownership이 모호** — "이 협상 데이터는 누구 것?" 답이 불분명 → GDPR documentation 까다로움
- Samsung ecosystem 차별화 측면 generic — 다른 회사도 똑같이 할 수 있음
- 협상 결과의 "공정성" 인식 — initiator가 다 본다는 점이 사용자 신뢰에 부담

---

### 후보 3. Home Hub-Hosted — 거실 hub 디바이스가 host

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

협상 테이블 **1개** — 가정의 hub 디바이스(Samsung TV·SmartThings hub·냉장고)에. 24/7 동작. Hub가 가전 ecosystem 데이터까지 보유 → 협상 input으로 활용.

#### 진행

1. 가족 구성원 폰이 가정 hub에 인증 (입주·동거 시작 시 1회)
2. 협상 발생 시 hub가 session 생성
3. 폰들이 자기 제약을 hub로 전송
4. Hub는 가전 데이터까지 같이 고려해서 algorithm 실행
5. 결과를 모두에게 broadcast
6. History를 hub에 누적 → 다음 협상이 이전 history 참조 가능 ("저번 토요일은 한식이었으니 이번엔 일식")

#### 장점

- **Samsung 차별화의 핵심** — Samsung은 TV·가전·폰을 모두 보유한 유일한 회사. **Apple·Google·OpenAI가 못 만드는 그림**. 본 product의 가장 강한 strategic moat
- **Long-running·recurring 협상 자연 지원** — 24/7 hub가 history·schedule 보관
- **가전 ecosystem 데이터를 협상 input으로 활용** — 결과 품질이 다른 솔루션 추격 불가 (가전 사용 패턴·집 상태가 협상 결정에 반영)
- 가족 단위의 trust anchor — 일상에서 사용자가 자연 이해
- **Lock-in 잠재력 강함** — Samsung 생태계 진입 깊이 ↔ 가치 증가
- 가족 단위 데이터 ownership이 hub로 명확 → GDPR documentation 단순
- 펌웨어 업데이트 cycle이 한 곳(hub)에 집중 → 버전 fragmentation risk 낮음

#### 단점

- **가족 외 협상 안 됨** — hub의 trust boundary가 가정 단위. **친구·회사 협상은 별도 모델 필요**. 단독 솔루션이 못 됨
- **하드웨어 의존** — Samsung TV·hub 없는 가정엔 적용 불가. 첫 사용자 진입 장벽
- **펌웨어 업데이트 cycle이 폰보다 느림** — TV·가전 OTA는 보수적 운영. Algorithm 업데이트 빈도에 제약
- Hub 하드웨어 failure가 협상 가용성 단절 → cloud backup·redundancy 별도 설계 필요
- **가족 구성 변경 처리 까다로움** (입주·퇴거·이혼) — policy·UX 양 측면

---

## 2. QA Tradeoff 평가

| 품질 속성 | 1. Federated | 2. Initiator-Hosted | 3. Home Hub |
|---|---|---|---|
| Privacy (사용자 측면) | ◎ 외부 노출 0 | △ initiator에 모임 | ○ hub에 모임 (가족 내) |
| 확장성 (N 증가) | ◎ 한계 없음 | △ initiator 폰 한계 | ○ hub 용량 한계 |
| 신뢰성 (단일 실패점) | ◎ 분산 | ✗ initiator 단일 실패 | △ hub 단일 실패 |
| 운영 비용 | ◎ broker만 | ◎ infra 없음 | △ hub 펌웨어·cloud sync |
| Samsung 차별화 | △ generic | △ generic | ◎ 유일 가능 |
| Lock-in 잠재력 | △ 약함 | △ 약함 | ◎ ecosystem 강결합 |
| Long-running 협상 | △ 어색 | ○ initiator 의존 | ◎ 자연 |
| 데이터 풍부도 | △ user 데이터만 | △ user 데이터만 | ◎ + 가전 데이터 |
| Trust 모델 명확성 | ◎ 자기만 | △ initiator 신뢰 | ○ 가족 신뢰 |
| 버전 호환성 관리 | ✗ silent divergence 위험 | ◎ host 버전이 truth | ◎ hub 버전이 truth |
| GDPR 부합 | ◎ 최소 데이터 | △ ownership 모호 | ○ 가족 단위 명확 |
| 적합 협상 유형 | 일회성·수평 | 호스트 있는 모임 | 가족·smart home |

### 종속·상충 관계

- 후보 1 ↔ 후보 3: 상충 — 협상 테이블이 분산이냐 hub 집중이냐 양립 불가. 단 협상 도메인(가족 vs 친구) 기준으로 분기 라우팅하면 공존 가능
- 후보 2는 후보 3의 약화 버전이며, 후보 1의 trust 모델보다 약함 → 본 결정의 dominant 선택지가 못 됨
- 본 결정은 [`./QS-002-프라이버시-보존-협상-속도.md`](./QS-002-프라이버시-보존-협상-속도.md) (메시지 단위 privacy 통제)과 독립이지만 정합 필요 — 어느 후보든 DP-1(단일 강제 게이트) 원칙을 깨면 안 됨

---

## 3. 권고

**Tier 1 (Home Hub) 를 전략 anchor로, Tier 2 (Federated) 를 보완 layer로 가는 2-tier deployment** 채택.

### Tier 1 — Home Hub-Hosted (default)

가족·smart home 도메인에 default. 근거:

- Samsung의 구조적 차별화 영역 — **본 product의 가장 강한 strategic moat**. Apple·Google·OpenAI 누구도 못 만드는 그림
- 가전 데이터를 협상 input으로 활용 → 결과 품질이 다른 솔루션 추격 불가
- Long-running·recurring 협상의 자연 home (가족 일정·가전 자원 조율)
- Lock-in이 product 사업 모델 측면에서 매우 가치 있음
- 버전 일관성을 hub 펌웨어 한 곳에서 통제 가능 → Federated의 silent divergence risk 회피

### Tier 2 — Federated (보완)

친구·낯선이·cross-household 협상에 Federated. 근거:

- Hub의 trust boundary 밖 그룹에는 본질적으로 hub model 적용 불가
- "데이터가 폰을 안 떠난다"는 강력한 privacy 메시지 — 규제·마케팅 양 측면에서 무기
- 가족 외 그룹은 N이 큰 경우 많아 (예: 친구 8명 약속) 확장성 강한 모델 필요

### Initiator-Hosted는 권장하지 않음

근거:

- **Home Hub의 약화 버전에 불과** — Hub가 제공하는 가치(24/7 가용성·가전 데이터·long-running)를 절반도 못 함
- Friend-group에서는 Federated가 더 적합 (trust 비대칭 없음)
- Initiator 폰의 가용성·history loss risk가 product 운영 비용으로 돌아옴 — Cloud backup 추가 시 사실상 cloud-hosted 모델로 변질
- Samsung 차별화 측면에서 generic — 다른 회사도 똑같이 할 수 있음

### 라우팅 정책

협상 시작 시 IDS의 intent classification으로 자동 라우팅:

| Intent 분류 | Tier |
|---|---|
| 가족 협상 (가전 사용 조율·가족 일정·가정 자원 분배) | Tier 1 (Home Hub) |
| 친구 협상 (약속·식사·여행) | Tier 2 (Federated) |
| 회사·낯선이 협상 | Tier 2 (Federated) |
| 가족이지만 외부 hub 미존재 | Tier 2 (Federated) 로 fallback |

두 Tier는 **동일 제약 schema·동일 algorithm 공유** → 사용자 UX는 일관, 내부 deployment만 분기.

---

## 4. 열린 이슈 (Open Questions)

본 결정 이후 추가 결정이 필요한 영역:

- **Hub failure 시 fallback** — Tier 1 운영 중 hub 장애 시 Tier 2로 transparent fallback 가능 여부와 fallback 시 history 어떻게 처리할지
- **가족 구성 변경 정책** — 입주·퇴거·이혼 시 hub의 인증된 폰 목록·history 처리 정책. 본 product의 hidden UX cost가 가장 큰 영역
- **Cross-Tier 협상** — "가족 + 친구" 혼합 협상(예: 가족 + 친구 1명이 함께 저녁 식사) 발생 시 어느 Tier에 위치할지
- **Hub 펌웨어 호환성 management** — TV 펌웨어 cycle과 폰 app 업데이트 cycle 간 schema 호환성 관리 방식
- **Multi-Hub 가정** — 한 가정에 Samsung TV + 냉장고 + Hub 셋이 모두 있는 경우 어느 디바이스가 협상 테이블 host인지 결정 정책

---

## 5. 설계 뷰 (UML) — TBD

본 결정의 컴포넌트 뷰·시퀀스 뷰·deployment 뷰는 결정 채택 후 별도 문서 `./DD-08-design-views.md` 에 정리 예정.

---

## 변경 이력

| 일자 | 변경 | 작성 |
|---|---|---|
| 2026-05-21 | 초안 작성 | 협의 결과 정리 |
