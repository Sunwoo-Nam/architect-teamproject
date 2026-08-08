# NegMAS 기반 Co-Planning 구현 구조 — 안 1

## 1. 목적과 근거

IDS가 감지한 공동 일정·계획 의도를 Galaxy 단말의 PPA들이 협상하는 시스템의 구현 구조안이다. 최신 요구사항은 [raw.md](./raw.md)를 기준으로 한다.

- [raw.md](./raw.md) — 다자 협상, 연속 계획, OutcomeSpace OOM, constraint hint, Utility Function 기반 정확도
- [과제 개요](../../02-과제-개요.md) — IDS, Orchestrator, PPA와 Android 시스템 경계
- [NegMAS 공식 문서](https://negmas.readthedocs.io/en/latest/) — SAO, GB, OutcomeSpace, Utility Function, ExtendedOutcome

PlanGraph, 잠정 합의, bounded candidate generation과 backtracking은 원문에는 없지만 단계 의존성과 메모리 상한을 함께 만족시키기 위해 추가한 제안이다.

## 2. 재검토 결론

- NegMAS는 전체 계획 엔진이 아니라 PlanGraph의 개별 협상 단계를 수행하는 **협상 커널**로 사용한다.
- 런타임 메커니즘은 다자 전원 합의를 표현하는 `SAOMechanism`으로 확정한다. GB 계열은 오프라인 검증에서 TAU를 정확도 기준선으로 쓰는 용도로만 사용한다.
- 영화·식사·여행의 모든 속성을 하나의 OutcomeSpace로 합치지 않고 의존 관계가 있는 단계로 분리한다.
- 단계 합의는 전체 계획 완성 전까지 잠정 상태로 두고, 후속 단계가 불가능하면 선행 단계를 제한적으로 재협상한다.
- `fixed` hint는 Offer 전체가 아니라 해당 issue 값만 변경 불가능하다는 의미다. `relaxable` issue는 counter-offer할 수 있다.
- 정확도는 협상 해와 전체 계획의 2계층으로 측정한다. 선호 표현의 품질은 전제로 두고 측정 대상에서 제외한다. 메모리·OOM은 별도 QA다.

## 3. 구현 구조

| 컴포넌트 | 책임 |
|---|---|
| IDS Intent Adapter | IDS 결과를 참여자·목표·승인 조건이 포함된 PlanningIntent로 변환 |
| Plan Template/Compiler | 시나리오별 단계·issue·의존성·실패 정책을 PlanGraph로 컴파일 |
| Co-Planning Orchestrator | 단계 실행, 잠정 합의, backtracking과 종료 제어 |
| CandidateSpace Provider | 현재 context와 constraint를 만족하는 후보를 최대 K개씩 lazy 생성 |
| Constraint/Preference Manager | fixed predicate 교집합과 사용자 Utility Function 관리 |
| Negotiation Kernel Adapter | SAO 실행과 플랫폼 메시지·NegMAS 객체 변환 |
| Plan State/Commit Manager | 단계 상태·revision·실패 조합을 저장하고 전체 계획 확정·복구 |
| A2A Gateway | 기기 간 메시지의 인증, 라우팅, 재전송과 중복 제거 |

NegMAS Python 객체를 A2A 메시지로 직접 사용하지 않는다. 플랫폼 중립 스키마와 NegMAS API를 Adapter에서 분리해 Android 배포 방식과 버전 변경의 영향을 격리한다.

## 4. 실행 흐름

1. IDS Intent와 시나리오 템플릿으로 PlanGraph를 만든다.
2. 실행 가능한 단계의 DPA·외부 서비스 context를 수집한다.
3. CandidateSpace Provider가 로컬 hard constraint와 active fixed hint를 적용해, 요청 시마다 최대 K개씩 후보를 공급한다.
4. Negotiation Kernel Adapter가 해당 단계의 SAO 협상을 수행한다.
5. 합의를 `TENTATIVE`로 저장하고 후속 단계의 입력 constraint로 전달한다.
6. 후속 후보가 없으면 실패 조합을 no-good constraint로 기록하고 가장 가까운 선행 단계로 돌아간다.
7. 모든 단계 성공과 사용자 승인 후에만 전체 계획을 `COMMITTED`로 전환한다.
8. backtracking 상한을 넘으면 제약을 임의 완화하지 않고 사용자 결정을 요청한다.

단계 분할은 메모리를 줄이지만 지역 최적해가 전체 계획 효용을 낮출 수 있다. 잠정 합의와 제한적 backtracking은 이를 보완하기 위한 구조다.

## 5. OutcomeSpace와 Constraint Hint

상대방이 `fixed`로 전달한 issue는 해당 Offer의 값과 일치해야 하는 predicate로 변환한다. 수신 단말은 이 predicate를 자신의 로컬 제약과 결합하여 EffectiveOutcomeSpace를 구성하고, CandidateSpace Provider는 그 공간에 포함되는 outcome만 생성한다. 따라서 fixed 값과 다른 outcome은 협상 후보에서 제외된다.

- issue 정의와 후보 집합을 분리하고 전체 outcome을 생성하지 않는다.
- `next_batch(limit, constraints, exclusions, context)`가 1회 호출당 최대 K개를 공급한다.
- K는 순간 메모리만 결정한다. 탐색 범위의 실질 상한은 협상 라운드 상한(`n_steps`·`time_limit`)이 정한다.
- hard constraint와 fixed hint는 생성 전에 적용한다. `UFunConstraint`는 생성 후 방어적 검증에 사용한다.
- 전체 cache·정렬과 Pareto 전수 계산은 작은 검증 시나리오에만 허용한다.
- `fixed`를 `issue == offered value` predicate로 변환한다.
- 후보 공간은 `LocalCandidateSpace ∩ active fixed predicates`로 계산한다.
- 교집합이 비면 해당 Offer 또는 계획 분기를 `INFEASIBLE`로 거절하고 충돌 issue를 기록한다.
- hint에는 session, stage, actor, base offer, revision을 포함하며 원본 OutcomeSpace는 수정하지 않는다.

## 6. 정확도와 품질

**전제:** 사용자 선호가 Utility Function으로 올바르게 유도되었는지는 IDS·선호 유도의 문제이며 본 구조의 측정 대상이 아니다. 이하 지표는 **주어진 Utility Function을 참으로 간주하고**, 그 위에서 협상 결과가 최적해에 얼마나 가까운지를 측정한다.

| 계층 | 기준 공간 | 측정 대상 |
|---|---|---|
| 단계 협상 해 | 그 단계의 EffectiveOutcomeSpace | 단계 합의가 그 공간의 최적해에 얼마나 가까운가 |
| 전체 계획 | 단계들의 결합 공간 | 단계별 최적의 합이 계획 전체로도 최적인가. 단계 최적성 평균과의 격차를 함께 본다 |

지표는 NegMAS `calc_outcome_optimality()`의 `pareto_optimality`, `nash_optimality`, `kalai_optimality`, `max_welfare_optimality`를 사용한다(0~1 정규화, 1.0이 최적점). 시나리오 난이도는 `opposition_level`로 통제 변수화하고, 유보값 미만 합의 여부는 `is_rational(ufuns, outcome)`으로 판정한다.

계산 순서: `calc_scenario_stats(ufuns, outcomes)` → `calc_outcome_distances(utils, stats)` → `estimate_max_dist(ufuns)` → `calc_outcome_optimality(dists, stats, max_dist)`

**측정 범위:** 두 지표 모두 전 참여자의 Utility Function과 기준 공간의 전량 열거를 요구한다. 온디바이스 런타임에서는 계산할 수 없고, 오프라인 벤치마크에서만 계산한다. 결합 공간은 단계 수에 대해 곱셈으로 커지므로, 전체 계획 최적성은 단계 최적성보다 더 작은 시나리오에서만 측정한다. 열거 가능 범위를 넘는 큰 시나리오는 정확도가 아니라 자원 지표(peak 메모리, 배치 호출 횟수, 라운드 수) 측정에만 사용한다.

**손실 원인 분리:** 최적해에 도달하지 못한 경우, 원인을 다음 3회 실행으로 분리한다.

| 실행 | 목적 |
|---|---|
| SAO, 운영 `n_steps` | 실제 성능 |
| SAO, 충분히 큰 `n_steps` | 라운드 상한 때문에 잃은 몫 |
| TAU | 프로토콜이 완전할 때의 상한. TAU는 선언된 acceptable outcome 안에 합의가 존재하면 반드시 찾으므로, SAO와의 차이가 협상 전략이 도달하지 못한 몫이다 |

세 실행 모두 오프라인 검증 시나리오에서만 수행한다. TAU는 라운드 수가 후보 집합 크기에 비례하고 메커니즘이 모든 제안을 누적 보관하므로 단말 탑재 대상이 아니다.

## 7. 구현 순서와 미결정 사항

- PlanningIntent, PlanTemplate, PlanGraph, StageAgreement 정의
- issue별 hint와 revision을 포함한 A2A 스키마 정의
- 기존 전수 열거를 CandidateSpace Provider 뒤로 격리
- 영화→식사 2단계, 잠정 합의와 1단계 backtracking 구현
- 소규모 exact·대규모 bounded 검증 분리
- NegMAS의 Galaxy 탑재 메모리·의존성·ABI spike 수행

- fixed hint의 유지·철회와 context 변경 시 revision 정책
- K와 backtracking 상한을 산정할 단말 메모리 예산
- NegMAS 직접 탑재와 Android 상태기계 구현 중 배포 대안

안 1의 핵심은 **PlanGraph가 복합 계획을 관리하고, NegMAS는 단계 협상을 수행하며, CandidateSpace Provider가 메모리 상한을 보장하는 책임 분리**다.
