# DP02 — 최소 공개 및 Private Knowledge 차단 방식

> **문서 성격**: Design Decision 후보 (draft)
> **솔루션 결정축**: 공개 가능한 사실을 보낼 것인가(Sanitized Fact Disclosure) vs 로컬 평가 결과만 보낼 것인가(Predicate-based Private Evaluation)
> **제약 사항**: Android 스마트폰 기반, 상대방 기기 동일 MAF 탑재 전제
> **근거 자료**: [`04-FR.md`](../04-FR.md), [`05-NFR.md`](../05-NFR.md), [`06-Constraints_20260608_창배.md`](../06-Constraints_20260608_창배.md), [`07-QAS.md`](../07-QAS.md), [`DP01-N명 커뮤니케이션 시나리오.md`](DP01-N명%20커뮤니케이션%20시나리오.md)
> **범위**: MAF Communication에서 `Private Knowledge`를 외부로 전송하지 않으면서도 Negotiation, Collaboration, Knowledge Sharing, Remote Monitoring을 성립시키는 에이전트 간 공개 프로토콜을 결정한다. N-party 토폴로지와 Coordinator 선출은 DP01 범위로 제외한다.

---

## 1. 결정 질문

최신 FR은 MAF가 사용자 에이전트 간 상호작용을 `Communication`으로 묶고, 그 하위에 Negotiation, Collaboration, Knowledge Sharing, Remote Monitoring을 둔다. 이 중 Knowledge Sharing은 `Shared/Public Knowledge`와 `Private Knowledge`를 구분하고, 외부 에이전트 요청 시 자동 필터링 및 익명화가 가능해야 한다.

동시에 QAS-013은 **Private Knowledge 외부 전송 0건**을 요구한다. 따라서 이 DP의 핵심 질문은 다음이다.

> 상대 에이전트가 판단에 필요한 정보를 요구할 때, 우리 MAF는 **공개 가능한 추상 사실을 payload로 보낼 것인가**, 아니면 **Private Knowledge는 끝까지 로컬에 두고 평가 결과만 보낼 것인가?**

이 결정은 단순 필터 구현 위치가 아니라, 에이전트 간 Communication의 기본 메시지 형식을 정하는 문제다.

---

## 2. 공통 전제

두 방안 모두 다음 전제를 공유한다.

1. TLS 1.3 이상 암호화는 공통 필수 조건이며, 본 DP의 비교 대상이 아니다.
2. 데이터는 정책에 따라 `Public / Shared / Private`으로 분류될 수 있어야 한다.
3. 상대 기기도 동일 MAF를 탑재하므로 메시지 스키마와 상태 전이 규칙을 양측에 강제할 수 있다.
4. 공개, 차단, 평가, 전송 이벤트는 QAS-015를 위해 로그로 남긴다.

---

## 3. 해결 방안 A — Sanitized Fact Disclosure

### 개념

단말 내부의 원본 데이터에서 Communication에 필요한 일부 사실을 추출한 뒤, 사전 정의된 스키마에 맞는 **비식별·저정밀도 payload**를 상대 에이전트에게 전송한다.

| 케이스 | 외부 전송 payload 예 |
|---|---|
| Negotiation | `available_window=[Sat 18:00-20:00]`, `preferred_area=Gangnam` |
| Collaboration | `can_join_session=true`, `role=reviewer`, `available_until=22:00` |
| Knowledge Sharing | `summary_level=coarse`, `source_category=public` |
| Remote Monitoring | `alert_type=inactivity`, `severity=medium`, `need_check=true` |

핵심은 raw data를 보내지 않되, 상대가 직접 판단할 수 있는 최소 사실은 공개한다는 점이다.

### 장점

- 한 번에 판단 재료를 제공하므로 Communication round 수가 줄어든다.
- Negotiation과 Collaboration에서 후보안 품질과 Task 성공률이 높아질 가능성이 크다.
- 전송 payload가 명확해 사용자 이력 조회와 감사 로그 구성이 쉽다.

### 위험

- Sanitizer나 정책 스키마가 잘못되면 Private Knowledge가 payload에 섞일 수 있다.
- raw data가 아니어도 여러 저정밀도 사실을 조합하면 생활 패턴이 추론될 수 있다.
- 도메인별 공개 스키마와 정밀도 기준을 계속 관리해야 한다.

---

## 4. 해결 방안 B — Predicate-based Private Evaluation

### 개념

상대 에이전트는 후보안이나 제한된 질의만 보내고, 우리 단말은 Private Knowledge를 로컬에서 평가한 뒤 **판정 결과만** 반환한다. 원본 데이터뿐 아니라 의미 있는 중간 사실도 외부 payload로 만들지 않는다.

| 케이스 | 상대 질의/후보 | 반환 payload 예 |
|---|---|---|
| Negotiation | "토요일 18~20시 가능한가?" | `acceptable=true`, `score=0.82` |
| Collaboration | "30분 리뷰 세션 참여 가능한가?" | `can_participate=true` |
| Knowledge Sharing | "이 주제에 공유 가능한 지식이 있는가?" | `has_shareable_knowledge=true`, `summary_level=coarse` |
| Remote Monitoring | "이상 징후가 있는가?" | `alert=true`, `severity=high` |

핵심은 상대가 판단 재료를 받는 것이 아니라, 내 단말이 내 데이터를 보고 판단한 결과만 받는다는 점이다.

### 필수 메커니즘

- `Privacy Broker`: 질의가 목적, 권한, 케이스 범위 안에 있는지 검사한다.
- `Local Evaluator`: Private Knowledge를 로컬에서만 읽고 후보안을 평가한다.
- `Query Budget`: 반복 질의를 통한 역추론을 막기 위해 질의 횟수, TTL, rate limit을 둔다.
- `Evaluation Log`: 외부에 보낸 결과와 내부 평가 근거를 분리해 기록한다.

### 장점

- Private Knowledge가 외부 payload로 직렬화되지 않아 QAS-013을 구조적으로 만족시키기 쉽다.
- 정보 집중 위험이 작고, DP01의 중앙형/탈중앙형 어느 토폴로지에도 붙일 수 있다.
- Remote Monitoring처럼 `알림 여부`, `심각도`만 필요한 케이스에 잘 맞는다.

### 위험

- 상대가 충분한 판단 재료를 직접 보지 못해 협상 round가 늘 수 있다.
- `score`, `severity`도 반복되면 민감 사실을 역추론하는 단서가 될 수 있다.
- 사용자가 "왜 이런 결과가 나왔는가"를 조회하려면 로컬 평가 근거 로그가 필요하다.

---

## 5. 품질 속성 비교

> 척도: ★★★ 강함 · ★★☆ 보통 · ★☆☆ 취약

| QAS / NFR | A. Sanitized Fact Disclosure | B. Predicate-based Private Evaluation | 판단 |
|---|:---:|:---:|---|
| QAS-013 개인정보 보안 | ★★☆ | ★★★ | A는 공개 스키마와 sanitizer 정확성에 의존한다. B는 Private Knowledge를 외부 payload로 만들지 않는다. |
| QAS-002 Communication 180초 | ★★★ | ★★☆ | A는 round 수를 줄이기 쉽다. B는 후보 질의 반복으로 시간이 늘 수 있다. |
| QAS-003 Remote Monitoring 5초 | ★★★ | ★★★ | 둘 다 가능하다. 단, B는 로컬 이상 판단 후 즉시 severity만 보내는 구조가 적합하다. |
| QAS-007 Communication Task 성공률 | ★★★ | ★★☆ | A는 상대가 더 많은 판단 재료를 가진다. B는 정보 부족으로 후보 탐색이 느릴 수 있다. |
| QAS-014 온디바이스 자원 | ★★☆ | ★★☆ | A는 분류·익명화 비용, B는 로컬 평가·query budget 비용이 든다. |
| QAS-015 이력 추적 | ★★★ | ★★☆ | A는 공개 payload 추적이 쉽다. B는 공개 결과와 비공개 평가 근거를 분리해 기록해야 한다. |

---

## 6. 권고 방향

현재 QAS 우선순위를 기준으로는 **B. Predicate-based Private Evaluation을 기본 프로토콜로 두는 방향**이 더 방어 가능하다.

이유는 다음과 같다.

- QAS-013의 `Private Knowledge 외부 전송 0건`은 실패 허용 폭이 거의 없는 보안 요구다.
- 최신 제약상 양측이 동일 MAF를 탑재하므로, 제한된 질의·응답 프로토콜을 강제할 수 있다.
- Sanitized payload는 유용하지만, 공개 스키마가 틀리면 곧바로 과공개가 된다.

다만 B만으로 모든 Communication을 처리하면 QAS-002와 QAS-007이 약해질 수 있다. 따라서 최종 구조는 다음처럼 정리하는 것이 적절하다.

- 기본값: **Predicate-based Private Evaluation**
- 예외 경로: 사전 승인된 schema의 `Shared/Public Knowledge`에 한해 **Sanitized Fact Disclosure** 허용
- 예외 조건: 공개 필드, 정밀도, 목적, 상대, TTL, 로그 항목이 정책으로 고정되어야 함

이 결정은 단순한 "하이브리드"가 아니라, **B를 기본 아키텍처로 선택하고 A를 제한된 성능·성공률 보완 경로로 둔다**는 의미다.

---

## 7. 열린 질문

1. `Private Knowledge`의 기준을 필드 단위로 둘 것인가, 의미 단위로 둘 것인가?
2. `score`, `severity`, `acceptable` 같은 평가 결과가 반복될 때 역추론 위험을 어떻게 제한할 것인가?
3. Sanitized Fact Disclosure를 허용하는 공개 스키마는 누가 정의하고 검증할 것인가?
4. 사용자 이력 조회 화면에는 "외부로 보낸 값"과 "로컬 평가에 사용했지만 보내지 않은 근거"를 어디까지 보여줄 것인가?
