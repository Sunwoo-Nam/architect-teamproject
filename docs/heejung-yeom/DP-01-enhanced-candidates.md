# DP-01 강화 후보안 — NegMAS Constraint Hint 운영 설계

> 대상: on-device-agentic-platform / architecture / DP-01
> 작성 기준일: 2026-08-09
> 목적: 기존 C1/C2/C3를 운영 가능한 두 후보로 강화한다.
> 상위 연결: DP-02 NegMAS N-party Negotiation
> 주 QA: QA-01 Resource Utilization, QA-02 Functional Correctness

## 1. 설계 방향

기존 DP-01은 Full Preference Context, Constraint Hint Pruned Space, LLM Full Context Dump를 비교한다. 이 구분은 입력량은 보여주지만 다음 운영 질문을 충분히 다루지 못한다.

- 과도한 prune으로 NO_DEAL이 되었을 때 복구할 수 있는가?
- 압축된 Soft Preference가 원래 ranking을 얼마나 보존하는가?
- Hint가 stale해졌거나 Hard Constraint가 바뀌면 어떻게 중단하는가?
- NegMAS session과 DP-02 commit 사이의 안전 경계는 무엇인가?

운영 후보는 다음 두 가지로 재정의한다.

| 후보 | 주 설계축 | 1차 목적 |
|---|---|---|
| A. Progressive Widening Hint | Memory 우선 + bounded recovery | Android 1차 운영 후보 |
| B. Utility Envelope Hint | Accuracy 우선 + safe dominance | 정확성 강화 후보 |

기존 C1은 oracle/regression baseline으로 유지하고 C3는 운영 후보에서 제외한다.

## 2. 공통 운영 경계

raw calendar, raw Soft Preference, PII는 협상 transport에 넣지 않는다. NegMAS는 compact Hint로 생성한 Issue, Outcome, UtilityFunction만 사용한다.

~~~mermaid
flowchart TB
  subgraph DEVICE["각 PPA Device"]
    CAL["Calendar / HardConstraintStore"]
    PREF["SoftPreferenceStore"]
    ENC["HintEncoder"]
    SNAP["Snapshot + Hint Contract"]
    CAL --> ENC
    PREF --> ENC
    ENC --> SNAP
  end
  SNAP --> VALIDATE["HintValidator"]
  VALIDATE -->|invalid / stale| REJECT["Reject + regenerate"]
  VALIDATE -->|valid| BUILD["OutcomeSpaceBuilder"]
  BUILD --> NEG["NegMAS Adapter"]
  NEG --> SAO["SAOMechanism or GB"]
  SAO --> RESULT["NegotiationResult"]
  RESULT --> GUARD["ActionGuard"]
  GUARD -->|Hard re-check + All-ACK| DP02["DP-02 commit candidate"]
  GUARD -->|fail / stale / timeout| NODEAL["NO_DEAL"]
~~~

공통 state:

~~~text
HINT_CREATED
  -> HINT_VALIDATED
  -> SESSION_STARTED
  -> SESSION_RUNNING
  -> AGREED_CANDIDATE
  -> COMMIT_READY
  -> ACTIONABLE_COMMITTED

예외:
  HINT_INVALID
  HINT_STALE
  SESSION_TIMEOUT
  HARD_CONFLICT
  NO_DEAL
  COMMIT_BLOCKED
~~~

AGREED_CANDIDATE는 calendar write 상태가 아니다. 최신 Hard snapshot, participant consistency, All-ACK, fencing/epoch 검증을 통과한 COMMIT_READY 이후에만 DP-02로 전달한다.

공통 Hint contract:

~~~text
schema_version
session_id
participant_id
snapshot_hash
hint_expiry
hard_unavailable_slots
reservation_bound
privacy_class
deterministic_seed
~~~

공통 불변 조건:

- snapshot_hash가 참가자 간 일치해야 한다.
- hint_expiry 이후에는 기존 Hint로 새 session을 시작하지 않는다.
- hard_unavailable_slots와 outcome_space가 모순되면 validation 실패다.
- reservation 기준 이하의 outcome은 합의 후보로 승격하지 않는다.
- 모든 negotiation session에 n_steps, time_limit 또는 step_time_limit을 둔다.

## 3. 후보 A — Progressive Widening Hint

### 3.1 핵심 아이디어

처음에는 Hard-safe한 작은 top-k frontier만 level 0으로 사용한다. 작은 outcome_space에서 SAOMechanism을 시작하고, NO_DEAL, timeout, offer stagnation, reservation 미달이 발생할 때만 다음 frontier를 추가한다.

widening은 level 0부터 level L까지 bounded recovery로 제한한다.

### 3.2 상세 구조

~~~mermaid
flowchart TB
  subgraph LOCAL["Device-local Hint Generation"]
    H["HardConstraintStore"]
    S["SoftPreferenceStore"]
    RANK["Local ranking / score bucket"]
    FRONT["Frontier partitioner"]
    H --> FRONT
    S --> RANK
    RANK --> FRONT
    FRONT --> L0["Level 0"]
    FRONT --> L1["Level 1"]
    FRONT --> LL["Level L"]
  end
  L0 --> VALIDATE["LevelValidator"]
  VALIDATE -->|Hard-safe| SPACE["Pruned OutcomeSpace"]
  VALIDATE -->|invalid| FAIL["HINT_INVALID"]
  SPACE --> UFUN["HintDerivedUtilityFunction"]
  UFUN --> NEG["SAONegotiator"]
  NEG --> SAO["Bounded SAOMechanism"]
  SAO --> OBS["SessionObserver"]
  OBS --> DECIDE{"Terminal / risk"}
  DECIDE -->|AGREED| VERIFY["Hard + reservation verify"]
  VERIFY --> CAND["AGREED_CANDIDATE"]
  DECIDE -->|NO_DEAL / timeout / stagnation| NEXT{"level < L?"}
  NEXT -->|yes| EXPAND["Add next frontier"]
  EXPAND --> SPACE
  NEXT -->|no| ND["NO_DEAL: budget exhausted"]
~~~

### 3.3 Contract와 불변 조건

~~~text
frontier_slots_by_level
score_bucket_by_slot
max_widening_levels
widening_reason_codes
level_budget:
  n_steps
  time_limit
~~~

- level N+1은 level N의 superset이다.
- Hard-infeasible slot은 어느 level에도 추가하지 않는다.
- 이전 level의 offer history를 보존한다.
- widening 사유와 결과를 함께 기록한다.
- Hint가 stale이면 widening하지 않고 재생성한다.

### 3.4 Component 책임

| Component | 책임 |
|---|---|
| HintEncoder | Hard-safe frontier와 compact score 생성 |
| LevelValidator | schema, snapshot, Hard subset, monotonicity 검증 |
| OutcomeSpaceBuilder | 현재 level만 NegMAS Issue/Outcome으로 구성 |
| HintDerivedUtilityFunction | bucket/reservation을 utility로 변환 |
| BoundedSAOExecutor | SAOMechanism 실행과 time/step budget 적용 |
| SessionObserver | round, stagnation, terminal reason 기록 |
| WideningController | 다음 level 진입 여부 결정 |
| ActionGuard | 최신 Hard와 commit 조건 재검증 |

### 3.5 실패 흐름

~~~mermaid
sequenceDiagram
  participant E as HintEncoder
  participant W as WideningController
  participant N as NegMAS SAO
  participant G as ActionGuard
  participant D as DP-02
  E->>W: level 0 Hint
  W->>N: OutcomeSpace(level 0)
  N-->>W: AGREED / NO_DEAL / TIMEOUT
  alt AGREED
    W->>G: Candidate + snapshot_hash
    G-->>D: COMMIT_READY if Hard/ACK valid
  else NO_DEAL or TIMEOUT
    W->>W: reason classify
    alt remaining level
      W->>N: widen to level 1..L
      N-->>W: new terminal result
    else budget exhausted
      W-->>D: NO_DEAL
    end
  end
~~~

장점은 평균 outcome cardinality와 peak state를 낮추면서 false NO_DEAL을 제한적으로 복구하는 것이다. 리스크는 widening 빈도가 높을 때 latency와 message 수가 증가하는 것이다.

수용 기준:

- hard_constraint_violation_count == 0
- NO_DEAL 원인 분류율 100%
- N=2/3/5 p95 deadline 준수
- C1 oracle 대비 agreement_oracle_regret gate 통과
- level 0 기준 memory/cardinality 감소

## 4. 후보 B — Utility Envelope Hint

### 4.1 핵심 아이디어

정확한 Soft Preference table 대신 slot별 효용 범위를 전달한다.

~~~text
utility_envelope_by_slot:
  slot_a:
    lower: 0.70
    upper: 0.90
    rank_band: 1
  slot_b:
    lower: 0.20
    upper: 0.40
    rank_band: 3
reservation_bound: 0.35
~~~

lower(A) > upper(B)이면 B를 안전하게 제거한다. Bound가 겹치는 후보는 제거하지 않고 협상 대상으로 유지한다. 즉, 모호한 후보를 성급하게 prune하지 않는 정확성 우선 전략이다.

### 4.2 상세 구조

~~~mermaid
flowchart TB
  subgraph LOCAL["Device-local Preference Compilation"]
    PREF["SoftPreferenceStore"]
    HARD["HardConstraintStore"]
    BOUND["BoundCompiler"]
    NORMAL["Normalizer"]
    PREF --> BOUND
    HARD --> BOUND
    BOUND --> NORMAL
    NORMAL --> ENV["UtilityEnvelopeHint"]
  end
  ENV --> CHECK["EnvelopeValidator"]
  CHECK -->|lower > upper violation| ERR["HINT_INVALID"]
  CHECK -->|valid| DOM["SafeDominanceFilter"]
  DOM --> PRUNE["Remove only dominated outcomes"]
  PRUNE --> UFUN["EnvelopeUtilityFunction"]
  UFUN --> POLICY["Acceptance + Offering Policies"]
  POLICY --> MECH{"Mechanism"}
  MECH -->|bilateral baseline| SAO["SAOMechanism"]
  MECH -->|multilateral experiment| GB["GB / ST / MT benchmark"]
  SAO --> VERIFY["Hard + bound consistency"]
  GB --> VERIFY
  VERIFY -->|safe| CAND["AGREED_CANDIDATE"]
  VERIFY -->|ambiguous| REFINE["RefineRequest(slot IDs only)"]
  REFINE --> BOUND
~~~

### 4.3 Contract와 검증 규칙

~~~text
schema_version
hard_unavailable_slots
utility_envelope_by_slot:
  lower
  upper
  rank_band
reservation_bound
dominance_rule_version
normalization_version
hint_expiry
~~~

- lower <= upper
- reservation_bound와 envelope가 모순되지 않음
- 같은 schema, dominance, normalization version만 비교
- bound가 겹치는 slot은 제거하지 않음
- refine 요청에는 slot ID만 포함
- 동일 envelope에서는 deterministic seed/tie-break 사용

### 4.4 Component 책임

| Component | 책임 |
|---|---|
| BoundCompiler | local Soft를 lower/upper/rank band로 변환 |
| Normalizer | participant별 utility scale 정규화 |
| EnvelopeValidator | bound, reservation, version 검증 |
| SafeDominanceFilter | 확실히 열등한 outcome만 제거 |
| EnvelopeUtilityFunction | envelope를 NegMAS utility로 노출 |
| AcceptancePolicy | reservation과 deadline 평가 |
| OfferingPolicy | top candidate, concession, tie-break 적용 |
| RefineController | ambiguous slot ID만 local 재평가 |
| ActionGuard | Hard와 snapshot 일관성 재검증 |

### 4.5 Acceptance/Offering 흐름

~~~mermaid
flowchart LR
  OFFER["Incoming offer"] --> U["Envelope utility"]
  U --> A1{"Above reservation?"}
  A1 -->|no| REJECT["Reject / End"]
  A1 -->|yes| A2{"Deadline policy?"}
  A2 -->|no| REJECT
  A2 -->|yes| A3{"All acceptance strategies?"}
  A3 -->|yes| ACCEPT["Accept candidate"]
  A3 -->|no| COUNTER["Counter offer"]
  COUNTER --> OFFER
~~~

NegMAS의 modular component 모델에 맞춰 AcceptAbove, time-based acceptance, concession offering을 조합한다.

수용 기준:

- hard_constraint_violation_count == 0
- M02-2 agreement_oracle_regret 통과
- M02-3 soft_rank_spearman 또는 top_k_hit_rate 통과
- envelope/stale/normalization 오류 별도 측정
- M01-1/2 최소 감소율 만족

## 5. 후보 비교와 채택 방향

| 항목 | A. Progressive Widening | B. Utility Envelope |
|---|---|---|
| 주 driver | Memory / latency | Accuracy / explainability |
| 시작 공간 | 작은 top-k | safe dominance filter 결과 |
| 복구 | level widening | ambiguous slot local refine |
| 구현 난이도 | 낮음~중간 | 중간~높음 |
| 평균 memory | 낮음 | 중간 |
| oracle accuracy | 조정 필요 | 상대적으로 유리 |
| Android 1차 | 권고 | 정확성 강화 옵션 |

권고:

- Android 1차 운영: A
- C1 Full Preference Context: regression oracle
- 정확성·감사 가능성 강화: B
- 최종 선택: 동일 seed/scenario benchmark 후 ADR 확정

비교 지표:

- M01-1 peak_negotiator_state_bytes
- M01-2 outcome_space_cardinality
- M02-1 hard_constraint_violation_count
- M02-2 agreement_oracle_regret
- M02-3 soft_rank_spearman 또는 top_k_hit_rate
- M04-1 p95_completion_latency
- widening_count, refine_request_count
- 원인별 NO_DEAL rate
- stale_session_count, premature_action_count

## 6. NegMAS 및 SCML 사례 반영

NegMAS SAO는 bilateral negotiation, n_steps, time_limit, history, round/session callback을 제공한다. 후보 A는 SAO protocol 자체를 수정하기보다 Hint adapter와 bounded WideningController를 상위에 두는 구성이 적합하다.

NegMAS의 acceptance, offering, opponent modeling, concession component 조합은 후보 B의 reservation/deadline/utility gate에 활용한다.

SAOSyncController는 여러 negotiator를 동기화할 수 있지만 controller 간 loop 가능성이 있으므로 기본 경로가 아니라 병렬 확장 benchmark에서 검증한다. checkpoint/from-checkpoint는 장시간 session과 controller failover 검증에 활용한다.

SCML은 NegMAS 기반으로 여러 bilateral negotiation을 동시에 수행하는 autonomous agent 사례다. 각 negotiation과 계약은 private하지만 agent utility는 여러 negotiation 사이에서 interdependent할 수 있다.

차용할 운영 규칙:

1. bilateral negotiation은 작게 유지하고 상위 controller가 전역 상태를 관리한다.
2. local utility와 global cumulative state를 분리한다.
3. 한 slot 합의가 다른 slot availability를 변경하면 관련 session을 stale 처리한다.
4. 성공률뿐 아니라 cancellation, inter-session conflict, premature action을 측정한다.
5. 병렬 negotiation에서 독립 utility 가정을 금지한다.
6. 모든 Hint에 hint_expiry, snapshot_hash, schema_version을 포함한다.
7. AGREED와 calendar write를 분리하고 ActionGuard와 All-ACK 이후에만 commit한다.
8. controller failover 시 checkpoint와 epoch/fencing token으로 stale action을 차단한다.

## 7. 참조

- [NegMAS Negotiation Mechanisms](https://negmas.readthedocs.io/en/latest/negotiation_mechanisms.html)
- [NegMAS Negotiation Components](https://negmas.readthedocs.io/en/latest/components.html)
- [NegMAS SAOSyncController](https://negmas.readthedocs.io/en/v0.10.2/api/negmas.sao.SAOSyncController.html)
- [NegMAS Running a Negotiation](https://negmas.readthedocs.io/en/v0.10.13/tutorials/01.running_simple_negotiation.html)
- [ANAC Supply Chain Management League](https://anac.cs.brown.edu/scml)
- [SCML 2023 overview/report](https://www.yasserm.com/files/scml/scml2023.pdf)
