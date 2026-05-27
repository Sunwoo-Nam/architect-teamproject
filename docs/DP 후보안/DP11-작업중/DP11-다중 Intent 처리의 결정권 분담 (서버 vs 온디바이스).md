# DD-11-α / 다중 Intent 처리의 결정권 분담 (서버 vs 온디바이스)

> **문서 성격**: DP11에 대한 대안 후보 쌍 (Design Decision 후보)
>
> **다른 후보 쌍과의 관계**: 기존 `DP11-다중 Intent의 동시 발생 및 실행 중 변경·실패 처리 방식.md`(전역 원장 vs Intent Capsule)와는 *별개의 갈림 축*임. 본 문서는 **결정권의 위치(서버 vs 온디바이스)**에 본질적 차이를 두는 후보 쌍을 다룸. 기존 후보 쌍은 *상태 표현의 경계*(전역 vs Intent별)에 차이를 두었으나 양쪽 모두 append-only 이벤트 로그 패턴을 공유해 본질적 차이가 얕다는 비판이 있었음 — 본 문서는 그 비판에 답해 *실행 제어권* 축으로 다시 갈라 보는 시도임.
>
> **상위·인접 결정과의 분리**:
>   - DP08(A2A 다자간 협상)은 *디바이스 간* 협상의 효율화. 본 결정은 *한 디바이스 안*에서의 결정권 위치.
>   - DP09(협상 진행 중 인텐트 변경 시 동시성 제어)는 *한 A2A 세션의 상태 전이*. 본 결정은 *그 위에서의 다중 Intent 라이프사이클 관리*.
>   - DP07(P2P 협상 상태 복구)은 *영속화 정책*. 본 결정은 *결정 자체의 위치*로 영속화 정책과 직교.
>
> **관련 NFR·QAS**:
>   - **NFR-001 (권한 차단)**, **NFR-005 (PII 차단)**, **NFR-006 (불필요 정보 차단)** — mandatory
>   - **QA-001 (협상 완료 시간)**, **QA-002 (동적 실행 성공률)**, **QA-003 (배터리)**, **QA-004 (도메인 추가 비용)**, **QA-005 (Intent 감지 지연)**, **QA-007 (추적성)**
>   - **NFR-007 (시뮬레이션 가능 여부)**
>   - QS-002, QS-007, QS-021, QS-011, QS-001, QS-015
>
> **작성일**: 2026-05-27 (v1) / 2026-05-27 개정 (v2: 흐름 정정·trade-off 통합·NFR 라벨 명시·Policy Table 발급 주체 명시) / 2026-05-27 개정 (v3: 제목 정정 — "결정권 위치 축 (서버 사전계획 vs 온디바이스 반응형)" → "다중 Intent 처리의 결정권 분담 (서버 vs 온디바이스)". 파일명 일치 갱신) / 2026-05-27 개정 (v4: drawio 도식 2개 삭제·본문 링크 제거 — 추후 재작성 예정) / 2026-05-27 개정 (v5: 평가 표 axis를 ISO/IEC 25010 상위 카테고리 5종으로 통일) / 2026-05-27 개정 (v6: v5 되돌림 — 평가 표 axis를 본 프로젝트 정량 QA·NFR(8개) 기반으로 다시 통일) / 2026-05-27 개정 (v7: 평가 표를 *독립·차별적인* 5개 항목으로 축소 — NFR-005·QA-001·QA-002·QA-004·QA-007. NFR-006·QA-003·NFR-007은 위 5개와 메커니즘이 겹치는 중복 anchor라 표에서 제외하고 §4 권고·본문 narrative에서 보조 근거로 활용)

---

## 0. 풀고자 하는 문제

`DP11 문제 정의.md`의 시나리오를 다시 옮기면 — Orchestrator는 Intent를 받아 실행하는 동안 새 Intent가 계속 들어옴.

```
"토요일 저녁 식사 예약해줘"          ← Intent A 시작, 식당 검색 중
       ... 10초 후 ...
"아이도 갈 수 있는 곳으로"           ← Intent B 도착 (A에 조건 추가, 병합)
       ... 5초 후 ...
"내일 날씨도 알려줘"                 ← Intent C 도착 (A와 무관)
       ... 30초 후 ...
"아 그냥 일요일 점심으로 바꿔"       ← Intent D 도착 (A의 시간 조건 대체)
```

IDS가 각 Intent에 **도메인**(Intent의 application 분야 — 예: `restaurant`·`weather`·`calendar`·`travel` 등. 각 도메인은 자기 전용 Sub-Agent 셋과 Tool 셋에 대응됨)과 **관계 라벨**(`병합·대체·차단·취소·무관`)을 함께 분류·부여해 Orchestrator로 전달한다는 전제 위에서, MAF는 세 가지를 결정해야 함.

1. **동시 실행** — 활성 Intent와 Task 중 무엇을 어떻게 병렬로 실행할 것인가
2. **관계 라벨 처리** — 병합·대체·차단·취소를 진행 중 실행에 어떻게 반영할 것인가
3. **실패 회복** — 외부 사정으로 실패한 Task/Intent를 어디서부터 어떻게 재개할 것인가

본 DP는 이 세 결정을 **누가, 언제, 어디서** 내릴 것인가의 갈림을 다룸. 결정의 *내용*보다 결정의 *위치*에 본질적 차이를 둠.

---

## 1. 핵심 설계 목표

- **세 문제(동시 실행·관계 라벨·실패 회복)를 한 결정 모델 안에서 통합 처리**
- **활성 Intent 집합의 라이프사이클이 일관되게 관리**되도록 함 — Intent 추가, 라벨 적용, 실패 회복이 같은 의사결정 흐름 안에 있어야 함
- **온디바이스 자원 제약 충족** (NFR-003 배터리 < 2%/h, NFR-004 유휴 메모리 < 500MB)
- **PII·민감 데이터의 서버 LLM 전송 최소화** (NFR-005·NFR-006 mandatory)
- **새 도메인 추가가 본 구조의 큰 변경 없이 가능**해야 함 (QA-004)
- **`02-과제-개요.md §2.3`의 표준 계층(IDS → Orchestrator → Meta Agent → Sub-Agent) 준수**

---

## 2. 솔루션 후보

본 결정의 본질은 *서버 LLM이 모든 결정에 관여*하는 방향(전역 최적화·추적성·새 도메인 확장에 강하지만 응답 지연·PII 노출·토큰 비용 부담)과 *온디바이스 Runtime이 대부분 결정*하는 방향(응답·PII·자원 효율에 강하지만 정책 생성·추적성에 별도 설계 필요)의 권한 위임 비율임. 아래 두 후보는 그 양 극단에 가까운 형태로 설계됨. 두 후보 모두 `02-과제-개요.md §2.3`의 표준 계층(IDS → Orchestrator → Meta Agent → Sub-Agent)을 준수하되, **Orchestrator의 역할이 서로 다름** — Sol.1에서 Orchestrator는 매 이벤트에 서버 LLM을 호출하는 *Replanner*이고, Sol.2에서 Orchestrator는 새 도메인 첫 등장과 폴백 시에만 서버 LLM을 호출하는 *Thin Proxy*임.

> **QA 평가 척도**: ★★★ 강함 · ★★☆ 보통 · ★☆☆ 취약
>
> **평가 항목**: 본 프로젝트의 정량 QA·NFR(`docs/06-QAS.md` §6.3·§6.4) 중 본 DP 결정이 *독립적·차별적인* 차이를 만드는 5개 — **NFR-005 (PII 차단)·QA-001 (협상 완료 시간)·QA-002 (동적 실행 성공률)·QA-004 (도메인 추가 비용)·QA-007 (추적성)**. NFR-006 (불필요 정보 차단)·QA-003 (배터리)·NFR-007 (시뮬레이션)은 위 5개 중 일부와 메커니즘이 겹쳐 *중복 anchor*(NFR-006↔NFR-005, QA-003↔QA-001, NFR-007↔QA-007 같은 결)가 되므로 표에서 제외하고 §4 권고와 본문 narrative에서 보조 근거로 활용함. "전역 최적화"·"네트워크 강건성" 같이 정량 QA/NFR에 anchor되지 않는 측면도 동일하게 본문 서술로 다룸.

---

### Sol.1 — Server-Central Replanning

새 Intent 도착, Task 완료, Task 실패 같은 모든 의미 있는 이벤트마다 Orchestrator(서버 LLM)가 **활성 Intent 집합 전체에 대한 Plan을 다시 생성**한다. 온디바이스 Meta Agent Runtime은 plan을 받아 실행만 하는 dumb executor 역할을 맡고, "무엇을 어떻게 할 것인가"의 의사결정은 매번 서버 LLM으로 위임된다. 활성 Intent 전체를 한 번에 보고 결정한다는 점에서 전역 최적화·추적성·새 도메인 확장에 강점이 있으나, **매 이벤트마다 서버 round-trip이 발생하므로 응답 지연·토큰 비용·PII 노출의 부담이 모두 서버 쪽으로 누적**된다.

**구조:**

```
[User]
   ↓
[IDS — 온디바이스]
   (Intent 감지·관계 라벨 부여 — 본 DP scope 외)
   ↓ IntentEvent { id, 관계 라벨, 분석 결과 }
=================== SERVER BOUNDARY ===================
[Orchestrator (Server LLM) — Replanner]
   · IDS의 IntentEvent와 Meta Agent Runtime의 TaskEvent를 함께 수신
   · 활성 Intent 집합 전체에 대한 Plan_vN+1 재생성
   · 관계 라벨 반영, 무효화 범위 산출, 회복 경로 생성
========================================================
   ↓ Plan_vN+1                        ↑ TaskEvent (완료·실패)
[Meta Agent Runtime — 온디바이스, dumb executor]
   · Plan Cache (Plan_vN 영속 보관)
   · Plan Executor (Plan대로 Sub-Agent dispatch·cancel·retry)
   · PII Filter (TaskEvent 추상화 후 서버 전송)
   · TaskEvent Reporter
   ↓ dispatch
[Sub-Agent 1] [Sub-Agent 2] [Sub-Agent 3] ...
   ↓
[Local Tools / 외부 서비스 API / DPA / A2A]
```

**입력 정의 — IDS로부터 받는 데이터** *(IDS 내부 분류 로직은 본 DP scope 외)*:

| 필드 | 의미 |
|---|---|
| `intent_id` | IDS가 부여한 고유 ID |
| `relation_label` | 기존 Intent와의 관계 (`병합`·`대체`·`차단`·`취소`·`무관` 중 1) |
| `target_intent_id` | 라벨이 `무관`이 아닐 때 대상이 되는 기존 Intent ID |
| `analysis_payload` | IDS가 사전 분석한 도메인 키, 핵심 조건, 사용자 발화 추상화 등 |

**워크플로우 상세:**

1. **IntentEvent 수신**: IDS가 위 구조의 IntentEvent를 Orchestrator로 전달함.
2. **Plan 재생성**: Orchestrator가 활성 Intent 집합 전체를 입력으로 받아 Plan_vN+1을 서버 LLM으로 생성. *어느 Task를 살리고·무효화하고·재실행하고·새로 추가할지*가 한 plan 안에서 결정됨.
3. **Plan 전달**: Plan_vN+1이 온디바이스 Meta Agent Runtime의 Plan Cache로 전달, 갱신.
4. **실행 재개**: Plan Executor가 Plan_vN+1에 따라 Sub-Agent dispatch. 새 Plan에서 무효화된 진행 중 Task는 cancel, 새로 추가된 Task는 시작.
5. **TaskEvent 보고**: Task 완료·실패 시 Meta Agent Runtime의 TaskEvent Reporter가 PII Filter를 거쳐 Orchestrator에 보고 → 2번부터 반복.
6. **서버 단절 시**: Plan_vN대로만 진행. 새 IntentEvent는 IDS가 큐잉, 연결 복구 시 일괄 전송.

**예시 (DP11 문제 정의의 4-Intent 시나리오 + T1 실패):**

```
[t=0초] Intent A 도착
  IDS → Orchestrator: IntentEvent(id=A, relation=신규,
                                  payload={domain=restaurant, time=Sat 18-20})
  Orchestrator (서버 LLM) → Plan_v1:
    [T1_search(time=Sat 18-20), T2_filter ← T1, T3_user_approval ← T2, T4_reserve ← T3]
  Orchestrator → Meta Agent Runtime: Plan_v1
  Runtime: T1 dispatch → restaurant Sub-Agent

[t=10초] Intent B 도착 (병합)
  IDS → Orchestrator: IntentEvent(id=B, relation=병합, target=A,
                                  payload={kid_friendly=true})
  Orchestrator (서버 LLM) → Plan_v2:
    [T1 (running), T2(kid_friendly=true) ← T1, T3, T4]
  Orchestrator → Meta Agent Runtime: Plan_v2
  Runtime: T2 아직 시작 전 → 입력 조건만 갱신, cancel 불필요

[t=15초] Intent C 도착 (무관)
  IDS → Orchestrator: IntentEvent(id=C, relation=무관,
                                  payload={domain=weather, date=tomorrow})
  Orchestrator (서버 LLM) → Plan_v3 = Plan_v2 ∥ [T5_weather]
  Orchestrator → Meta Agent Runtime: Plan_v3
  Runtime: T5 dispatch (T1과 병렬)

[t=45초] Intent D 도착 (대체)
  IDS → Orchestrator: IntentEvent(id=D, relation=대체, target=A,
                                  payload={time=Sun 12-14})
  Orchestrator (서버 LLM) → Plan_v4:
    [T1_new(time=Sun 12-14), T2 ← T1_new, T3, T4] ∥ [T5_weather]
  Runtime: 기존 T1 cancel → T1_new dispatch

[t=46초] T1_new restaurant API timeout 실패
  Runtime: TaskEvent(T1_new, failed, reason=timeout) → PII Filter → Orchestrator
  Orchestrator (서버 LLM) → Plan_v5:
    [T1_new_retry(attempt=2), fallback=T1_alt_finder, ...] ∥ [T5_weather]
  Runtime: T1_new_retry dispatch

→ 총 5번 서버 LLM 호출 (4 IntentEvent + 1 TaskEvent)
```

**모듈 설명:**

| 모듈 | 위치 | 역할 |
|---|---|---|
| IDS | 온디바이스 | IntentEvent를 Orchestrator로 전달 *(내부 동작은 본 DP scope 외)* |
| Orchestrator (Server LLM) | **서버** | 활성 Intent 전체를 보고 Plan_vN+1 생성 |
| Plan Cache | 온디바이스 | 현재 유효 Plan_vN 영속 보관 |
| Plan Executor | 온디바이스 | Plan에 따라 Sub-Agent dispatch·cancel·retry |
| PII Filter | 온디바이스 | 서버 전송 직전 PII·민감 정보 제거·추상화 (NFR-005 PII / NFR-006 불필요 정보) |
| TaskEvent Reporter | 온디바이스 | Task 완료·실패를 Orchestrator로 보고 |
| Sub-Agent (도메인별) | 온디바이스 | Tool 호출, 외부 서비스 연동 |

**QA 평가:**

| 평가 항목 | 평가 | 근거 |
|---|:---:|---|
| NFR-005 (PII 차단) | ★☆☆ | Intent 맥락이 매 plan 요청마다 서버 LLM에 도달. PII Filter에 전적으로 의존 — Filter가 잘못 설계되면 mandatory NFR 즉시 위반. (같은 메커니즘으로 NFR-006 불필요 정보 차단도 ★☆☆) |
| QA-001 (협상 완료 시간) | ★☆☆ | 매 IntentEvent·TaskEvent마다 네트워크 왕복 누적 (모바일 100ms~수 초). 짧은 간격 burst 시 비용 nonlinear 증가. (같은 호출 빈도가 QA-003 배터리·NFR-003에도 직접 불리) |
| QA-002 (동적 실행 성공률) | ★★★ | 활성 Intent 전체를 보고 서버 LLM이 plan 산출 — 추론력·일관성·재계획 능력 모두 강함. 무효화·재실행 판단이 plan 안에서 통합 |
| QA-004 (도메인 추가 비용) | ★★★ | 새 도메인 = 서버 LLM 프롬프트/지식 갱신만. 온디바이스 변경 불필요 |
| QA-007 (추적성) | ★★★ | Plan_v1, v2, v3…가 명시적 산출물로 영속화. 결정 시점·근거 재구성 100% 가능. (같은 산출물로 NFR-007 시뮬레이션도 mock plan 주입만으로 가능 — ★★★) |

**장점:**

- 활성 Intent 전체를 보고 결정하므로 전역 최적화·일관성이 가장 강함. 병합·대체·차단·취소가 같은 plan 산출 과정에서 통합 처리됨.
- 의사결정이 명시적 plan으로 남아 audit·debug·시뮬레이션이 가장 쉬움 — QA-007과 NFR-007 모두에 강함.
- 새 도메인·새 Tool 추가가 서버 LLM 측 갱신만으로 끝남 — 온디바이스 정책 등록 부담이 없음.
- Meta Agent Runtime이 dumb executor라 구현·테스트가 단순.

**단점:**

- **mandatory NFR-005 (PII 차단) · NFR-006 (불필요 정보 차단) 충족이 정면 부담**임. PII Filter가 빈틈없이 동작해야 하며, Filter의 정확성·완전성이 통째로 시스템의 보안 적합성을 결정.
- 응답 지연이 사용자 체감 가능한 수준으로 누적됨 — QA-001 최우선 QA에 직접 불리.
- 짧은 간격으로 여러 Intent가 도착하면 서버 호출이 급증해 토큰·배터리 비용이 nonlinear하게 증가.
- 네트워크 단절 동안 새 Intent 처리 불가 — 모바일 환경(음영 지역·기내·지하)에서 약함.
- 서버 LLM이 잘못된 plan을 내놓으면 온디바이스에서는 그것을 검증할 메커니즘이 부족 — *서버 신뢰성 = 시스템 신뢰성*.

**적합한 시나리오**: 활성 Intent가 적고(2~3개) 이벤트 빈도가 낮은 (분 단위) 상황, 네트워크 안정적, 추적성·전역 최적화가 사용자 경험보다 중요한 운영 환경.

---

### Sol.2 — On-Device Reactive Runtime

Orchestrator(서버 LLM)는 새 도메인 Intent가 **처음 등장할 때 1회**, *Skeleton — 필요한 Sub-Agent 타입 + 도메인별 초기 Policy Table 룰셋*을 자동 생성하여 Meta Agent Runtime에 발급한다. **Policy Table은 사람이 수작업으로 작성하는 것이 아니라 서버 LLM이 도메인 첫 등장 시 자동 생성하는 것이며**, 이후 모든 이벤트(관계 라벨 적용, 다른 Intent 도착, Task 실패) 처리는 온디바이스 Meta Agent Runtime이 그 정책표를 따라 즉시 결정한다. 정책표에 없는 새로운 상황(예: 처음 본 라벨 조합)에서는 Orchestrator의 Policy Fallback Resolver가 호출되어 일회성 해결안을 만들고, 그 응답은 새 룰로 정책표에 자동 추가되어 *점진적으로 보강*된다. 사용자 체감 응답성과 PII 보호에 강점이 있으나, **초기 정책 품질이 Orchestrator의 Skeleton 생성 능력에 좌우되고, 결정이 정책표·이벤트 시퀀스에 분산되어 추적성 보강에 별도 설계가 필요**하다.

**구조:**

```
[User]
   ↓
[IDS — 온디바이스]
   (Intent 감지·관계 라벨 부여 — 본 DP scope 외)
   ↓ IntentEvent { id, 관계 라벨, 분석 결과 }
=================== SERVER BOUNDARY ===================
[Orchestrator — Thin Proxy + Skeleton Generator (Server LLM)]
   · 대부분의 IntentEvent: 단순 routing only (서버 LLM 호출 없음)
   · 새 도메인 첫 등장: Skeleton 생성 (서버 LLM 호출 1회)
   · 폴백 요청: Policy Fallback Resolver (서버 LLM 호출, 드묾)
========================================================
   ↓ routing 결과 또는 Skeleton 또는 폴백 응답
[Meta Agent Runtime — 온디바이스, 본체 decision-maker]
   ┌──────────────────────────────────────────────────┐
   │  Skeleton Cache (Intent 도메인별, 영속)            │
   │  Policy Table (도메인별 룰셋 — 서버 LLM이 발급)    │
   │  Reactive Decision Engine                        │
   │   (이벤트 → 정책표 lookup → 즉시 액션)            │
   │  Resource Coordinator (lease 기반 자원 충돌 직렬화) │
   │  Policy Updater (폴백 응답을 새 룰로 자동 추가)     │
   │  Event Log + Decision Log (영속, 회복·추적용)      │
   └──────────────────────────────────────────────────┘
   ↓ dispatch (대부분 온디바이스에서 즉시)
[Sub-Agent 1] [Sub-Agent 2] [Sub-Agent 3] ...
   ↓
[Local Tools / 외부 서비스 API / DPA / A2A]
```

**입력 정의 — IDS로부터 받는 데이터**: Sol.1과 동일 (`intent_id`, `relation_label`, `target_intent_id`, `analysis_payload`).

**워크플로우 상세:**

1. **IntentEvent 수신**: IDS가 IntentEvent를 Orchestrator로 전달.
2. **Skeleton 조회·발급**: Orchestrator는 Meta Agent Runtime의 Skeleton Cache에 해당 도메인 Skeleton이 있는지 확인 (캐시 상태를 routing 단계에서 함께 확인). 캐시 hit이면 단순 routing — 서버 LLM 호출 없음. **캐시 miss이면 Orchestrator가 서버 LLM을 호출하여 Skeleton(Sub-Agent 타입 목록 + 초기 Policy Table 룰셋)을 1회 생성하고 Meta Agent Runtime에 전달.** Cache 저장.
3. **정책표 매칭**: 온디바이스 Meta Agent Runtime의 Reactive Decision Engine이 (이벤트 종류, Intent 라벨, 현재 진행 상태)를 키로 Policy Table에서 액션 룰을 lookup.
   - 예: `on_merge(restaurant, kid_friendly=true)` → "T2 filter에 조건 inject"
   - 예: `on_replace(restaurant, time=*)` → "현재 search task cancel + 새 time으로 재시작"
   - 예: `on_task_fail(restaurant_search, timeout)` → "3회 retry, 그 후 fallback finder 사용"
4. **즉시 액션**: 정책표가 지정한 액션을 Resource Coordinator의 잠금 검사 후 즉시 Sub-Agent에 dispatch. 서버 LLM 호출 없음.
5. **이벤트·결정 로그 기록**: 모든 결정과 액션이 Decision Log에 append-only로 기록됨 (QA-007 추적성 보강용).
6. **폴백 호출**: 정책표에 매칭이 없는 상황 발생 시 Orchestrator의 Policy Fallback Resolver(서버 LLM)를 호출 → 일회성 해결안 수신. Policy Updater가 이 해결안을 새 룰로 정책표에 자동 추가.
7. **회복**: 프로세스 강제 종료 후 재시작 시 Event Log replay로 진행 상태 재구성. Skeleton Cache·Policy Table은 영속화되어 있으므로 즉시 재가동.

**예시 (같은 4-Intent 시나리오 + T1 실패):**

```
[t=0초] Intent A 도착
  IDS → Orchestrator: IntentEvent(A, 신규, domain=restaurant)
  Orchestrator: Skeleton Cache 확인 → restaurant 도메인 miss
    → 서버 LLM 호출 → Skeleton_restaurant = {
        sub_agents: [restaurant_finder, calendar_writer],
        policy_rules: {
          on_merge:     'inject_constraint_to_finder',
          on_replace:   'cancel_finder_and_restart',
          on_cancel:    'release_holds_and_drop',
          on_task_fail: 'retry_3x_then_fallback_finder'
        }
      }
  Orchestrator → Meta Agent Runtime: Skeleton 전달
  Runtime: Skeleton Cache·Policy Table 저장 → restaurant_finder dispatch
  ※ 서버 LLM 호출 1회 (새 도메인 첫 등장)

[t=10초] Intent B 도착 (병합)
  IDS → Orchestrator: IntentEvent(B, 병합→A, kid_friendly=true)
  Orchestrator: 캐시 hit (restaurant) → 단순 routing
  Runtime: Policy Table lookup → on_merge → 'inject_constraint_to_finder'
    → 진행 중 finder에 kid_friendly 조건 inject
  ※ 서버 LLM 호출 0회

[t=15초] Intent C 도착 (무관, 새 도메인)
  IDS → Orchestrator: IntentEvent(C, 무관, domain=weather)
  Orchestrator: Skeleton Cache miss (weather)
    → 서버 LLM 호출 → Skeleton_weather 발급
  Runtime: weather_query dispatch (restaurant_finder와 병렬)
  ※ 서버 LLM 호출 1회 (새 도메인 첫 등장)

[t=45초] Intent D 도착 (대체)
  IDS → Orchestrator: IntentEvent(D, 대체→A.time, Sun 12-14)
  Orchestrator: 캐시 hit → 단순 routing
  Runtime: Policy Table lookup → on_replace → 'cancel_finder_and_restart'
    → 현재 finder cancel + 새 time으로 재시작
  ※ 서버 LLM 호출 0회

[t=46초] restaurant_finder API timeout
  Sub-Agent → Runtime: TaskFailed(finder, timeout)
  Runtime: Policy Table lookup → on_task_fail(timeout) → 'retry_3x_then_fallback'
    → retry 1회 시도
  ※ 서버 LLM 호출 0회 (정책 안에서 처리)

→ 총 5번 이벤트 중 서버 LLM 호출 2회 (모두 새 도메인 첫 등장)
   Sol.1 동일 시나리오: 5회 (이벤트마다)
```

**모듈 설명:**

| 모듈 | 위치 | 역할 |
|---|---|---|
| IDS | 온디바이스 | IntentEvent를 Orchestrator로 전달 *(내부 동작은 본 DP scope 외)* |
| Orchestrator (Server LLM) | **서버** | Thin proxy + Skeleton Generator + Policy Fallback Resolver. 서버 LLM 호출은 새 도메인 첫 등장 + 폴백 시만 |
| Skeleton Cache | 온디바이스 | Orchestrator가 발급한 도메인별 Skeleton 영속 보관 |
| Policy Table | 온디바이스 | (이벤트, 라벨, 상태) → 액션 lookup 룰셋. **서버 LLM이 Skeleton 발급 시 초기 룰셋 생성** + 폴백 응답으로 점진 보강 |
| Reactive Decision Engine | 온디바이스 | 이벤트 수신 → 정책표 lookup → 즉시 액션 결정 |
| Resource Coordinator | 온디바이스 | lease 기반 자원 충돌 직렬화 |
| Policy Updater | 온디바이스 | 폴백 응답을 새 룰로 정책표에 자동 추가 |
| Event Log / Decision Log | 온디바이스 | 모든 결정·액션 영속화 (회복 + QA-007 추적성 보강) |
| Sub-Agent (도메인별) | 온디바이스 | Tool 호출, 외부 서비스 (Sol.1과 동일) |

**QA 평가:**

| 평가 항목 | 평가 | 근거 |
|---|:---:|---|
| NFR-005 (PII 차단) | ★★★ | Skeleton 요청 시 도메인 키 수준의 추상화 메시지만 서버 도달. Intent 본문·사용자 데이터는 온디바이스 유지 — 구조적 충족. (같은 메커니즘으로 NFR-006 불필요 정보 차단도 ★★★) |
| QA-001 (협상 완료 시간) | ★★★ | 대부분 이벤트가 온디바이스에서 즉시 처리. 서버 호출은 도메인 첫 등장·폴백 시만 — QA-001 최우선 요구에 정면 부합. (같은 낮은 호출 빈도가 QA-003 배터리·NFR-003에도 유리) |
| QA-002 (동적 실행 성공률) | ★★☆ | 정책표가 잘 발급되어 있으면 충분. 단 폴백 빈도가 높거나 초기 정책 품질이 낮으면 ★☆☆까지 떨어질 수 있음 — Skeleton 생성 품질에 좌우 |
| QA-004 (도메인 추가 비용) | ★★☆ | 서버 LLM이 Skeleton·초기 정책을 자동 생성하므로 사람 수작업 0. 단 폴백 빈도·정책 품질 검증 운영 비용은 발생 |
| QA-007 (추적성) | ★☆☆ | 결정 로직이 정책표·이벤트 시퀀스에 분산. Plan_v1, v2 같은 명시적 산출물 없음 (Decision Log를 통한 사후 재구성은 가능하나 셋업 무거움). (같은 분산 구조라 NFR-007 시뮬레이션도 셋업 무거워 ★★☆) |

**장점:**

- mandatory NFR-005 (PII 차단) · NFR-006 (불필요 정보 차단)을 구조적으로 충족하기 쉬움 — 서버에 가는 정보가 도메인 키 수준으로 추상화됨.
- 사용자 체감 응답 지연이 최소 (QA-001 최우선 요구에 직접 부합).
- 네트워크 단절·음영 지역에서도 정상 동작.
- 배터리·토큰 비용이 가장 낮음 (NFR-003, QA-003).
- "온디바이스 LLM이 IDS·Meta·Sub에 배치된다"는 본 프로젝트의 LLM 배치 결정(`02-과제-개요.md §2.3`)과 가장 잘 맞음 — Meta Agent Runtime이 본체 decision-maker로 동작.
- **Policy Table을 서버 LLM이 자동 생성하므로 사람의 도메인별 수작업이 불필요** — Sol.1의 QA-004 강점을 부분적으로 가져옴.

**단점:**

- 초기 정책 품질이 *Orchestrator의 Skeleton 생성 능력*에 좌우됨. 서버 LLM이 부실한 룰셋을 발급하면 폴백 빈도가 높아져 결국 Sol.1과 비슷한 비용으로 수렴할 수 있음.
- 정책표에 없는 새로운 라벨 조합·실패 양상에서는 폴백 호출이 필요. 폴백 빈도가 예상보다 높으면 사용자 체감 응답성 강점이 약화됨.
- Decision Engine이 한 이벤트만 보므로 cross-Intent 최적화가 약함. 예: "Intent A의 식당 검색과 Intent E의 식당 검색이 같은 시간대를 노릴 때 한 번에 묶어 효율화" 같은 전역 최적화는 어려움.
- 결정이 정책표·이벤트 시퀀스에 분산되어 QA-007(추적성)·NFR-007(시뮬레이션 커버리지) 충족에 별도 Decision Log 설계 필요.
- 정책표 자체의 정확성·완전성이 시스템 정합성을 결정 — 정책 룰의 충돌·누락이 곧 시스템 결함.

**적합한 시나리오**: 다수 Intent가 짧은 간격으로 들어오는 일상 사용 (메신저 대화 중 자연스러운 의도 표출), 네트워크 불안정한 모바일 환경, 사용자 체감 응답성이 가장 중요한 운영 환경.

---

## 3. 종합 비교

| 평가 항목 | Sol.1 (Server-Central) | Sol.2 (On-Device Reactive) |
|---|:---:|:---:|
| NFR-005 (PII 차단) | ★☆☆ | ★★★ |
| QA-001 (협상 완료 시간) | ★☆☆ | ★★★ |
| QA-002 (동적 실행 성공률) | ★★★ | ★★☆ |
| QA-004 (도메인 추가 비용) | ★★★ | ★★☆ |
| QA-007 (추적성) | ★★★ | ★☆☆ |
| **별점 합계** (★★★=3, ★★☆=2, ★☆☆=1) | **11** | **11** |

구조·운영 측면의 부수 비교:

| | Sol.1 (Server-Central) | Sol.2 (On-Device Reactive) |
|---|:---:|:---:|
| Orchestrator 역할 | Replanner (매 이벤트 서버 LLM 호출) | Thin Proxy (도메인당 1회 + 폴백만 서버 LLM 호출) |
| Meta Agent Runtime 역할 | Dumb Executor | 본체 Decision-maker |
| Policy 작성 주체 | 해당 없음 (서버 LLM이 매번 plan 직생성) | **서버 LLM이 Skeleton 발급 시 자동 생성** + 폴백 보강 (사람 수작업 0) |
| 서버 LLM 호출 빈도 | 매 이벤트 | 도메인당 1회 + 폴백 |

본 두 후보는 5개 평가 항목 중 Sol.1이 3개(QA-002 실행 성공률·QA-004 도메인 추가·QA-007 추적성), Sol.2가 2개(NFR-005 PII·QA-001 응답)에서 우위 — 횟수 기준으론 Sol.1 3-2 우세, 별점 합계 기준으로는 양쪽 모두 11점으로 *완전 동률*임. 한쪽이 모든 항목에서 압승하지 않고 각 후보가 최소 2개 항목에서 명확한 우위를 가지므로 AGENT.md §4.2 조건을 만족함. 최종 권고의 가중치(QA-001 최우선·NFR-005 mandatory 등 QA 우선순위)는 §4에서 명시적으로 적용함.

추가로 표에 포함되지 않은 항목들도 §4 권고에서 보조 근거로 다룸:
- *중복 anchor*로 제외된 항목 — NFR-006 (불필요 정보)은 NFR-005와, QA-003 (배터리)은 QA-001과, NFR-007 (시뮬레이션)은 QA-007과 같은 메커니즘에 묶임
- *정량 anchor 없는 측면* — Sol.1의 *전역 최적화*(활성 Intent 전체 시야), Sol.2의 *네트워크 강건성*(서버 단절 무관)

---

## 4. 권고 방향

**Sol.2 (On-Device Reactive Runtime) 권고. 단, 폴백 경로의 1차 시민화와 Decision Log 의무화로 단점을 정직하게 보강.**

근거를 QA 우선순위(`06-QAS.md §6.4`)에 연결하면:

- **QA-001 협상 완료 시간 (최우선)**: Sol.2가 명확히 우위 — 매 이벤트가 온디바이스에서 즉시 처리되므로 서버 round-trip 누적이 없음.
- **QA-002 동적 실행 성공률**: Sol.1이 우위 — 서버 LLM의 추론력이 더 큼. 그러나 Sol.2의 정책표가 서버 LLM에 의해 도메인별로 잘 발급되면 충분.
- **QA-003 배터리**: Sol.2가 명확히 우위.
- **QA-004 도메인 추가 비용**: Sol.1이 우위. 다만 Sol.2도 Skeleton·정책을 서버 LLM이 자동 발급하므로 *사람의 수작업 부담은 동일하게 0*. 차이는 발급된 정책의 *품질 검증·운영* 비용 정도임.
- **QA-005 Intent 감지 지연**: Sol.2가 우위.
- **QA-007 추적성**: Sol.1이 우위. Sol.2의 약점.

상위 3개(QA-001, 002, 003) 중 2개에서 Sol.2가 우위이고, mandatory NFR-005 (PII 차단)·NFR-006 (불필요 정보 차단) 충족도 Sol.2가 구조적으로 유리함. 또한 `02-과제-개요.md §2.3`이 명시한 "Meta Agent는 온디바이스 LLM" 배치 결정과 가장 잘 맞음 — Sol.1을 채택하면 Meta Agent Runtime이 dumb executor가 되어 *"왜 Meta Agent에도 온디바이스 LLM이 필요한가"*의 답이 약해짐.

다만 Sol.2의 약점(QA-007 추적성, 초기 정책 품질 의존)을 솔직히 인정하고 다음 두 메커니즘을 본 안의 일부로 명시 권고:

1. **폴백 경로의 1차 시민화** — 정책표 lookup miss는 *예외*가 아니라 *정상 동작 분기*로 설계. 폴백 결과는 정책표에 새 룰로 자동 추가되어 점진적 학습이 일어남. 운영 초기엔 폴백 비율이 높지만 시간이 지나며 줄어드는 곡선을 기대.
2. **Decision Log의 의무화** — Reactive Decision Engine의 모든 lookup 결과·액션 명령이 영속화되어, 사후에 "Plan_v1, v2, v3"에 준하는 시계열 재구성이 가능하도록 함. 이로써 QA-007 약점을 부분 보강.

본 권고의 핵심은 *"모든 이벤트가 서버 LLM을 거치는가, 거의 거치지 않는가"* 의 갈림이지 *"서버를 절대 거치지 않는가"* 의 갈림이 아님. Sol.2도 Orchestrator를 거쳐 라우팅이 일어나며, 도메인 첫 등장과 폴백 시에는 서버 LLM이 호출됨 — *서버 LLM 추론 호출 빈도*가 결정적 차이임.

---

## 5. 남은 Open Questions

본 안을 본격 구현으로 옮기기 전 다음 질문에 답이 필요함.

1. **PII Filter의 충분성 검증 방법** (Sol.1 채택 시 mandatory)
   Sol.1을 채택한다면 PII Filter가 NFR-005·006을 100% 충족시켜야 하는데, Filter의 *완전성*을 어떻게 검증할 것인가. Adversarial 테스트·정적 분석·런타임 모니터링 중 어느 조합을 채택할 것인가.

2. **Sol.2 채택 시 정책표의 표현력 한계**
   정책표는 (이벤트, 라벨, 상태) → 액션의 lookup table 구조인데, 라벨 조합이 폭발하면 (5종 × 5종 × N개 도메인 × 진행 상태) lookup 키 공간이 너무 커짐. 정책 룰의 일반화 수준(예: 와일드카드, 룰 우선순위)을 어떻게 설계할 것인가.

3. **폴백 빈도의 정량 기준**
   Sol.2의 폴백 경로가 *예외*가 아닌 *분기*라면, 폴백 비율의 운영 임계치(예: 첫 한 달 30% 이하)를 어떻게 정할 것인가. 임계치 초과 시 Sol.1로 회귀할 것인가, Skeleton 생성 프롬프트 품질을 개선할 것인가.

4. **Decision Log의 보관 기간과 PII 균형**
   QA-007 보강용 Decision Log는 사용자 발화·Intent 맥락을 포함할 가능성이 큰데, 어디까지 보관할 것인가. NFR-005의 *서버 전송* 0%와 *로컬 보관*은 다른 차원이지만, Log dump가 외부로 유출될 위험은 따로 다뤄야 함.

5. **활성 Intent 수의 상한**
   Sol.2는 활성 Intent가 늘어나도 cross-Intent 조정을 Resource Coordinator만 보는데, 활성 Intent 수가 안드로이드 자원 한계(NFR-004 유휴 메모리 < 500MB, QS-004 동시 Agent 메모리)를 넘으면 어떻게 throttle할 것인가.

6. **DP07·DP09와의 상호작용**
   본 결정은 DP07(영속화)·DP09(A2A 세션 상태 전이)와 직교한다고 가정했지만, Sol.2의 Event Log·Decision Log가 DP07이 다루는 영속화 매체와 어떻게 일관성을 가질 것인가. 한 SQLite·KV 저장소를 공유할 것인가 분리할 것인가.

7. **하나의 Intent가 여러 도메인에 걸치는 경우**
   "토요일 저녁 식사 예약 + 캘린더 등록"처럼 한 Intent가 여러 Sub-Agent를 필요로 할 때, Sol.2의 Skeleton은 어떻게 묶어 발급할 것인가. cross-Sub-Agent 정책 일관성은 어떻게 보장할 것인가.

8. **Orchestrator의 thin proxy 모드와 서버 LLM 호출 모드의 식별 기준** (Sol.2 채택 시)
   Orchestrator가 routing only로 동작할지 서버 LLM을 호출할지를 판단하는 기준이 어디에 있어야 하는가 — Orchestrator 내부 캐시 메타데이터인가, Meta Agent Runtime이 미리 알린 캐시 상태인가, IDS의 IntentEvent에 부착된 힌트인가.

---

_본 문서는 DP11에 대한 대안 후보 쌍이며, 기존 `DP11-다중 Intent의 동시 발생 및 실행 중 변경·실패 처리 방식.md`와 병존함._
_작성 근거: `DP11 문제 정의.md`, `DP11_AGENT.md`, `02-과제-개요.md`, `06-QAS.md`, `QualityAttributes.md`, DP07·DP08·DP09 문서, 사용자와의 2026-05-27 설계 논의._
_v2 개정: §2 핵심 긴장 관계를 §2 도입부 narrative와 §4 권고에 통합·삭제. IDS → Orchestrator → Meta Agent 표준 계층 준수로 흐름 정정. NFR/QA 아이디에 한~두 단어 설명 추가. Sol.2의 Policy Table 작성 주체를 *서버 LLM의 Skeleton 발급 시 자동 생성*으로 명시._
_v3 개정: 제목 변경 (파일명·H1 일치). "결정권 위치 축 (서버 사전계획 vs 온디바이스 반응형)" → "다중 Intent 처리의 결정권 분담 (서버 vs 온디바이스)". 다른 후보 쌍과의 짝 패턴(상태 소유권 vs 결정권 분담)이 보이도록 정정. 내용 변경 없음._
_v4 개정: drawio 도식 2개(`DP11-α-sol1.drawio`, `DP11-α-sol2.drawio`) 삭제 및 본문 §3 Sol.1·Sol.2 내 도식 링크 제거. 추후 재작성 예정._
_v5 개정: 평가 표 axis 통일 — 기존 8개 임의 항목(NFR-005·006, 토큰/배터리, 응답 지연, 추적성, 전역 최적화, 네트워크 강건성, 도메인 확장, NFR-007 시뮬레이션)을 ISO/IEC 25010(2011) 상위 카테고리 5종(보안성·성능 효율성·신뢰성·기능 적합성·유지보수성)으로 통일. AGENT.md §4.5(상위 카테고리만 axis로 허용) 준수. 구체 QA·NFR ID는 본문·근거 칸에서 자유 인용. 호환성·사용성·이식성은 본 DP 결정과 무관하여 평가 대상에서 제외._
_v6 개정: v5 되돌림 — 평가 표 axis를 본 프로젝트 정량 QA·NFR(`06-QAS.md`) 8개(NFR-005·NFR-006·QA-001·QA-002·QA-003·QA-004·QA-007·NFR-007) 기반으로 재정리. v5의 ISO 카테고리 axis는 *기능 적합성*처럼 본 프로젝트의 정량 QA에 anchored되지 않은 axis를 만들어 평가 근거가 약해지는 문제가 있었음. 정량 QA로 직접 anchor되지 않는 "전역 최적화"(Sol.1 강점)·"네트워크 강건성"(Sol.2 강점)은 표에서 제외하고 각 솔루션 narrative와 §4 권고에서 본문 서술로만 다룸. AGENT.md §4.5의 "상위 카테고리 axis" 원칙과는 형식상 거리가 있으나, 동 §4.5 끝 문장의 *"본 프로젝트 정량 QA는 위 상위 카테고리의 인스턴스로 봄"* 을 활용해 정량 anchor 우선으로 정직히 정리._
_v7 개정: 평가 표를 *독립·차별적인* 5개 항목(NFR-005·QA-001·QA-002·QA-004·QA-007)으로 축소. NFR-006(불필요 정보 차단)은 NFR-005와, QA-003(배터리)은 QA-001과, NFR-007(시뮬레이션)은 QA-007과 *같은 메커니즘*에 묶이는 중복 anchor라 표에 포함하면 한쪽으로 별점 합계가 기울어 보이게 함. 5개로 축소 결과 별점 합계는 양쪽 모두 11점 동률·횟수 기준 Sol.1 3-2 우세 — 후보 쌍의 trade-off가 더 첨예해짐. 중복 anchor 항목들은 각 5개 항목의 근거 칸에 *같은 메커니즘으로 영향 받는다는 사실*을 부기하고, §4 권고에서 보조 근거로 활용함. **유의 — 별점 합계가 동률이 됨에 따라 §4 권고의 Sol.2 선택 근거가 별점이 아니라 QA 우선순위(QA-001 최우선·NFR-005 mandatory) 가중치에 더 강하게 의존하게 됨. §4 권고는 이미 QA 우선순위 기반 서술이므로 그대로 유효하나, 가중치 적용을 더 명시적으로 보강할 여지가 있음 (별도 결정 사항).**_
