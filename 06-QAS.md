# 6. QAS (Quality Attribute Scenarios)

> 출처
> - `arch-with-ai/docs/quality/scenarios.md` (Utility Tree 및 24개 QAS 도출)
> - `arch-with-ai/docs/quality/QS-001 ~ QS-024.md` (개별 QAS 명세서)
> - `arch-with-ai/docs/quality/evaluations.md` (QAS 평가)
> - `arch-with-ai/docs/qualities.md` (NFR/QA 선정 결과)
>
> 본 문서는 **인덱스 + 요약 + 선정 결과**를 제공함. 24개 QAS 각각의 상세 명세는 [`annex/qas/QS-XXX.md`](annex/qas/) 참조.

---

## 6.1 QAS 란?

QAS(Quality Attribute Scenario, 품질 시나리오)는 시스템이 만족해야 할 **품질 속성**을 정량적·시나리오 형태로 기술한 것임. 추상적 NFR과 달리 다음 6요소를 명시함.

| 요소 | 설명 |
|---|---|
| 자극원 (Source) | 품질 요구를 발생시키는 주체 (예: 사용자, 외부 시스템) |
| 자극 (Stimulus) | 어떤 사건이 일어났는가 (예: 메시지 수신, 협상 시작) |
| 환경 (Environment) | 어떤 상태에서 (예: IDS 백그라운드 활성, 네트워크 정상) |
| 산출물 (Artifact) | 어느 컴포넌트가 (예: IntentDetector, A2AProtocolAdapter) |
| 반응 (Response) | 어떻게 응답해야 하는가 |
| 측정 (Measure) | 정량 측정 기준 (예: T_intent < 500ms, p95) |

QAS는 아키텍처 결정의 근거가 됨. 예: "QS-002의 측정치를 만족하려면 Orchestrator의 LLM 호출을 비동기로 분리해야 한다" 등의 추론이 가능해짐.

---

## 6.2 24개 QAS 인덱스

`arch-with-ai`에서 도출된 24개 QAS는 6개 품질 속성으로 분류됨.

| QS ID | 제목 | 품질 속성 | 세부 |
|---|---|---|---|
| [QS-001](annex/qas/QS-001-Intent-감지-지연-시간.md) | Intent 감지 지연 시간 | 성능 — 응답 시간 | IDS Intent 분류까지의 시간 |
| [QS-002](annex/qas/QS-002-A2A-협상-완료-시간.md) | A2A 협상 완료 시간 | 성능 — 응답 시간 | 협상 시작~합의안 도출 |
| [QS-003](annex/qas/QS-003-백그라운드-모니터링-메모리-사용량.md) | 백그라운드 모니터링 메모리 사용량 | 성능 — 자원 효율 | 백그라운드 RSS |
| [QS-004](annex/qas/QS-004-동시-Agent-실행-최대-메모리-사용량.md) | 동시 Agent 실행 메모리 | 성능 — 자원 효율 | 동시 Agent 수 × 메모리 |
| [QS-005](annex/qas/QS-005-온디바이스-LLM-추론-실패-처리.md) | 온디바이스 LLM 추론 실패 처리 | 신뢰성 — LLM 오류 | 추론 실패 시 fallback |
| [QS-006](annex/qas/QS-006-협상-중-네트워크-단절-복구.md) | 협상 중 네트워크 단절 복구 | 신뢰성 — 연결 복구 | 단절 후 재개 |
| [QS-007](annex/qas/QS-007-동적-생성-Agent-Tool-실행-성공률.md) | 동적 생성 Agent/Tool 실행 성공률 | 신뢰성 — 동적 생성 | First-run 성공률 |
| [QS-008](annex/qas/QS-008-권한-범위-초과-행동-차단.md) | 권한 범위 초과 행동 차단 | 보안 — 권한 강제 | 초과 행동 차단 비율 |
| [QS-009](annex/qas/QS-009-민감-데이터-서버-LLM-전송-최소화.md) | 민감 데이터 서버 LLM 전송 최소화 | 보안 — 프라이버시 | PII 유출 차단 |
| [QS-010](annex/qas/QS-010-온디바이스-LLM-모델-교체-비용.md) | 온디바이스 LLM 모델 교체 비용 | 변경 용이성 — LLM 교체 | 교체 시 외부 컴포넌트 수 |
| [QS-011](annex/qas/QS-011-새로운-협상-도메인-추가-비용.md) | 새로운 협상 도메인 추가 비용 | 변경 용이성 — 도메인 추가 | 신규 도메인 도입 비용 |
| [QS-012](annex/qas/QS-012-A2A-프로토콜-버전-업데이트-비용.md) | A2A 프로토콜 버전 업데이트 비용 | 변경 용이성 — 프로토콜 | 프로토콜 갱신 비용 |
| [QS-013](annex/qas/QS-013-외부-서비스-API-교체-비용.md) | 외부 서비스 API 교체 비용 | 변경 용이성 — API 교체 | API 변경 시 비용 |
| [QS-014](annex/qas/QS-014-A2A-협상-시뮬레이션-가능-여부.md) | A2A 협상 시뮬레이션 가능 여부 | 테스트 용이성 — 시뮬레이션 | Mock 기반 검증 가능성 |
| [QS-015](annex/qas/QS-015-Agent-의사결정-추적-가능성.md) | Agent 의사결정 추적 가능성 | 테스트 용이성 — 추적 | 결정 재구성 가능 비율 |
| [QS-016](annex/qas/QS-016-Android-프로세스-종료-후-협상-상태-복구.md) | Android 프로세스 종료 후 복구 | 가용성 — 프로세스 복구 | OS Kill 후 재시작 |
| [QS-017](annex/qas/QS-017-Orchestrator-계획-수립-지연-시간.md) | Orchestrator 계획 수립 지연 | 성능 — 응답 시간 | Task → Sub-task 분해 시간 |
| [QS-018](annex/qas/QS-018-Sub-Agent-Tool-실행-지연-시간.md) | Sub-Agent Tool 실행 지연 | 성능 — 응답 시간 | Tool 호출 응답 |
| [QS-019](annex/qas/QS-019-협상-제안-내-개인-기기-정보-최소화.md) | 협상 제안 내 개인/기기 정보 최소화 | 보안 — 협상 보안 | 불필요 정보 노출 차단 |
| [QS-020](annex/qas/QS-020-A2A-협상-메시지-기밀성.md) | A2A 협상 메시지 기밀성 | 보안 — 협상 보안 | 메시지 암호화·변조 감지 |
| [QS-021](annex/qas/QS-021-백그라운드-배터리-소비.md) | 백그라운드 배터리 소비 | 성능 — 자원 효율 | 백그라운드 시간당 배터리 소비 |
| [QS-022](annex/qas/QS-022-영속-데이터-저장-공간-누적.md) | 영속 데이터 저장 공간 누적 | 성능 — 자원 효율 | 데이터 저장 누적률 |
| [QS-023](annex/qas/QS-023-상대방-PPA-장기-미응답-세션-만료-처리.md) | 세션 만료 처리 | 가용성 — 세션 만료 | 미응답 세션 처리 |
| [QS-024](annex/qas/QS-024-합의-후-외부-서비스-실행-실패-처리.md) | 합의 후 실행 실패 처리 | 가용성 — 실행 실패 | 합의 후 외부 호출 실패 |

> 분류 체계의 Utility Tree 시각화는 [`annex/qas/_scenarios-utility-tree.md`](annex/qas/_scenarios-utility-tree.md) 참고.

---

## 6.3 NFR 선정 결과 (총 7개)

`qualities.md` 분석에서 **반드시 만족해야 하는 NFR 7개**가 선정됨. 만족하지 못하면 연구 과제 실패 또는 사용자 신뢰 붕괴를 초래함.

| ID | 제목 | 허용치 | 관련 QAS |
|---|---|---|---|
| **NFR-001** | 권한 범위 초과 행동 차단 | R_block = 100% | [QS-008](annex/qas/QS-008-권한-범위-초과-행동-차단.md) |
| **NFR-002** | A2A 협상 메시지 기밀성 | 암호화 = O, R_tamper_detect = 100% | [QS-020](annex/qas/QS-020-A2A-협상-메시지-기밀성.md) |
| **NFR-003** | 백그라운드 배터리 소비 허용치 | B_delta < 2%/h | [QS-021](annex/qas/QS-021-백그라운드-배터리-소비.md) |
| **NFR-004** | 백그라운드 유휴 메모리 허용치 | M_idle < 500MB | [QS-003](annex/qas/QS-003-백그라운드-모니터링-메모리-사용량.md) |
| **NFR-005** | 서버 LLM PII 전송 차단 | R_pii_leak = 0% | [QS-009](annex/qas/QS-009-민감-데이터-서버-LLM-전송-최소화.md) |
| **NFR-006** | 협상 제안 불필요 정보 노출 차단 | R_unnecessary_info = 0% | [QS-019](annex/qas/QS-019-협상-제안-내-개인-기기-정보-최소화.md) |
| **NFR-007** | A2A 협상 시뮬레이션 가능 여부 | 시뮬레이션 가능 = O, 커버리지 = 100% | [QS-014](annex/qas/QS-014-A2A-협상-시뮬레이션-가능-여부.md) |

> 본 NFR은 본 저장소 [`05-NFR.md`](05-NFR.md)의 NFR과는 **출처가 다름**에 유의함.
> - `05-NFR.md` → docx 원본의 NFR(NFR01~NFR21, NFR-1~NFR-24) — 추상적·서술적 형태
> - 위 표의 NFR-001~007 → arch-with-ai에서 24개 QAS를 평가한 후 **선정된** 형태 — 정량 허용치 포함
>
> 향후 단일화가 필요할 수 있으나, 두 문서는 서로 다른 단계의 산출물이므로 일단 병존시킴.

---

## 6.4 QA(품질 속성) 선정 결과 — 우선순위 (총 8개)

NFR이 "최소 만족 기준"이라면, QA는 "더 만족할수록 좋은 품질". 8개 QA가 우선순위와 함께 선정됨. 트레이드오프 발생 시 **우선순위가 높은 QA를 우선 만족**시킴.

| 우선순위 | ID | 제목 | 관련 QAS |
|---|---|---|---|
| **1 (최우선)** | QA-001 | A2A 협상 완료 시간 최소화 | [QS-002](annex/qas/QS-002-A2A-협상-완료-시간.md) |
| 2 | QA-002 | 동적 생성 Agent/Tool 실행 성공률 최대화 | [QS-007](annex/qas/QS-007-동적-생성-Agent-Tool-실행-성공률.md) |
| 3 | QA-003 | 백그라운드 배터리 소비 최소화 | [QS-021](annex/qas/QS-021-백그라운드-배터리-소비.md) |
| 4 | QA-004 | 새로운 협상 도메인 추가 비용 최소화 | [QS-011](annex/qas/QS-011-새로운-협상-도메인-추가-비용.md) |
| 5 | QA-005 | Intent 감지 지연 시간 최소화 | [QS-001](annex/qas/QS-001-Intent-감지-지연-시간.md) |
| 6 | QA-006 | 온디바이스 LLM 모델 교체 비용 최소화 | [QS-010](annex/qas/QS-010-온디바이스-LLM-모델-교체-비용.md) |
| 7 | QA-007 | Agent 의사결정 추적 가능성 최대화 | [QS-015](annex/qas/QS-015-Agent-의사결정-추적-가능성.md) |
| 8 | QA-008 | A2A 프로토콜 업데이트 비용 최소화 | [QS-012](annex/qas/QS-012-A2A-프로토콜-버전-업데이트-비용.md) |

---

## 6.5 미선정 QAS 및 사유

24개 QAS 중 **9개는 NFR/QA로 선정되지 않음**. 사유는 다음과 같음.

| QS | 제목 | 미선정 사유 |
|---|---|---|
| QS-004 | 동시 Agent 실행 최대 메모리 | NFR-004(유휴 메모리)와 연동되며, 동시 실행 메모리는 기기 RAM에 따라 가변적. 아키텍처 결정보다 구현 튜닝 영역임 |
| QS-005 | LLM 추론 실패 처리 | 중요하지만 LLMGateway 설계 수준의 구현 패턴 문제. NFR 허용치 설정이 어려워 QA로도 미선정 |
| QS-006 | 협상 중 네트워크 단절 복구 | 신뢰성 중요하나, NegotiationSessionDB 영속화 설계에서 파생됨. QA-001(협상 완료 시간)과 상충 가능 |
| QS-013 | 외부 서비스 API 교체 비용 | 일상적 유지보수 수준. 아키텍처 차별화 요소 미해당 |
| QS-016 | Android 프로세스 종료 후 복구 | NFR-003/004의 해결 방향(foreground service + DB 영속화)에서 자연히 해결되는 파생 요건 |
| QS-017 | Orchestrator 계획 수립 지연 시간 | QA-001(협상 완료 시간)의 서브 지표. QA-001 최적화 과정에서 함께 다루어짐 |
| QS-018 | Sub-Agent Tool 실행 지연 시간 | 외부 API 지연이 주요 변수로 플랫폼 제어 범위 외 |
| QS-022 | 영속 데이터 저장 공간 누적 | PoC 연구 기간(수개월) 내 임계 영향 없음. TTL 정책은 구현 단계에서 다룸 |
| QS-023 | 세션 만료 처리 | NegotiationSessionDB 세션 생명주기 관리 구현 수준. 아키텍처 결정보다 정책 설정 영역 |
| QS-024 | 합의 후 실행 실패 처리 | AgreementDB/TaskDB 분리 설계 원칙으로 해결. 구현 패턴 수준으로 별도 QA/NFR 불필요 |

---

## 6.6 중복 선정 사항

- **QS-021 (배터리 소비)**: NFR-003(B_delta < 2%/h)과 QA-003(B_delta 최소화)으로 중복 선정됨. NFR 허용치는 반드시 만족하되, 허용치 이내에서도 최소화 방향으로 설계함.

---

## 6.7 보조 자료

- 24개 QAS 개별 명세: [`annex/qas/`](annex/qas/) 폴더
- Utility Tree(품질 속성 분류 시각화): [`annex/qas/_scenarios-utility-tree.md`](annex/qas/_scenarios-utility-tree.md)
- 24개 QAS 평가 과정·근거: [`annex/qas/_evaluations.md`](annex/qas/_evaluations.md)
