# DP02 — 최소 공개 및 Private Knowledge 차단 방식

---

## 1. 풀고자 하는 문제

최신 FR은 MAF가 사용자 에이전트 간 상호작용을 `Communication`으로 묶고, 그 하위에 Negotiation, Collaboration, Knowledge Sharing, Remote Monitoring을 둔다. 이 중 Knowledge Sharing은 `Shared/Public Knowledge`와 `Private Knowledge`를 구분하고, 외부 에이전트 요청 시 자동 필터링 및 익명화가 가능해야 한다.

동시에 QAS-012은 **Private Knowledge 외부 전송 0건**을 요구한다. 따라서 이 DP의 핵심 질문은 다음이다.

> 상대 에이전트가 판단에 필요한 정보를 요구할 때, 우리 MAF는 **공개 가능한 추상 사실을 payload로 보낼 것인가**, 아니면 **Private Knowledge는 끝까지 로컬에 두고 평가 결과만 보낼 것인가?**

이 결정은 단순 필터 구현 위치가 아니라, 에이전트 간 Communication의 기본 메시지 형식을 정하는 문제다.

---

## 2. 아키텍처적 난제

| 난제 | 내용 | 관련 FR/NFR/QAS |
|---|---|---|
| **Private Knowledge 0건 전송** | Private Knowledge가 외부 payload에 한 번이라도 포함되면 보안 요구를 위반한다. | FR-MAF-05, NFR-MAF-07, QAS-012 |
| **유용성 vs 최소 공개** | 너무 적게 공개하면 협상·협업·지식 공유가 성립하지 않고, 너무 많이 공개하면 개인정보 노출 위험이 커진다. | FR-MAF-02~06, QAS-009, QAS-007 |
| **추론 공격** | raw data가 아니어도 `score`, `severity`, `available_window` 같은 결과가 반복되면 생활 패턴이 역추론될 수 있다. | FR-MAF-05, QAS-012 |
| **이력 추적** | 사용자는 무엇이 외부로 나갔고 무엇이 로컬 평가에만 쓰였는지 조회할 수 있어야 한다. | FR-MAF-07, NFR-MAF-08, QAS-013 |
| **케이스별 공개 수준 차이** | Negotiation, Collaboration, Knowledge Sharing, Remote Monitoring은 필요한 정보량과 시간 제약이 다르다. | FR-MAF 공통 및 4대 케이스, QAS-009 |

두 방안 모두 다음 전제를 공유한다.

1. TLS 1.3 이상 암호화는 공통 필수 조건이며, 본 DP의 비교 대상이 아니다.
2. 데이터는 정책에 따라 `Public / Shared / Private`으로 분류될 수 있어야 한다.
3. 상대 기기도 동일 MAF를 탑재하므로 메시지 스키마와 상태 전이 규칙을 양측에 강제할 수 있다.
4. 공개, 차단, 평가, 전송 이벤트는 QAS-013를 위해 로그로 남긴다.

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

- Private Knowledge가 외부 payload로 직렬화되지 않아 QAS-012을 구조적으로 만족시키기 쉽다.
- 정보 집중 위험이 작고, DP01의 중앙형/탈중앙형 어느 토폴로지에도 붙일 수 있다.
- Remote Monitoring처럼 `알림 여부`, `심각도`만 필요한 케이스에 잘 맞는다.

### 위험

- 상대가 충분한 판단 재료를 직접 보지 못해 협상 round가 늘 수 있다.
- `score`, `severity`도 반복되면 민감 사실을 역추론하는 단서가 될 수 있다.
- 사용자가 "왜 이런 결과가 나왔는가"를 조회하려면 로컬 평가 근거 로그가 필요하다.

---

## 5. 종합 비교 (Quality Attribute & 영향 정보)

> 척도: ★★★ 강함 · ★★☆ 보통 · ★☆☆ 취약

| QAS / NFR | A. Sanitized Fact Disclosure | B. Predicate-based Private Evaluation | 판단 |
|---|:---:|:---:|---|
| QAS-012 개인정보 보안 | ★★☆ | ★★★ | A는 공개 스키마와 sanitizer 정확성에 의존한다. B는 Private Knowledge를 외부 payload로 만들지 않는다. |
| QAS-009 Communication 180초 | ★★★ | ★★☆ | A는 round 수를 줄이기 쉽다. B는 후보 질의 반복으로 시간이 늘 수 있다. |
| QAS-011 온디바이스 자원 | ★★☆ | ★★☆ | A는 분류·익명화 비용, B는 로컬 평가·query budget 비용이 든다. |

**핵심 긴장:** A는 Communication 시간에 유리하지만 공개 스키마가 틀리면 과공개 위험이 커진다. B는 QAS-012에 가장 강하지만 후보 질의 반복으로 Communication 시간이 늘 수 있다. 따라서 이 DP의 실제 선택은 **QAS-012의 보안 보장을 더 우선할 것인가**, 아니면 **QAS-009의 Communication 시간을 더 우선할 것인가**의 문제로 좁혀진다.
