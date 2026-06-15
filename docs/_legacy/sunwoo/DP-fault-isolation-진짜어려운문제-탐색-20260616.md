# 본 프로젝트에서 *진짜* 어려운 장애 격리 문제 — 탐색 메모

> **작성일**: 2026-06-16
> **맥락**: [DP-fault-isolation.md](../../07-DP후보안/DP-fault-isolation.md)의 B vs C 비교가 *큰 차이 없음*이라는 결론에 도달한 뒤, **본 프로젝트에서 진짜 소프트웨어 설계적으로 어려운 장애 격리 문제는 무엇인가**를 다시 탐색한 결과 정리.
> **성격**: 후속 DP의 *씨앗 문서* (draft). 정식 DP 후보로 승격 여부는 미정.

---

## 0. 출발점 — 본 DP가 풀지 *않은* 문제

기존 [DP-fault-isolation.md](../../07-DP후보안/DP-fault-isolation.md)는 다음을 다뤘다:
- supervision tree 채택 (감독자 트리)
- 자격 A 분리 (LLM·Accessibility)
- B(K=2) vs C(K=3) — MAF 분리 여부

분석 결과:
- **자격 A 분리**는 결정이 아니라 *제약*(런타임 또는 원칙으로 강제됨)
- **MAF 분리(B vs C)** 는 측정 의존적이며 *결정의 무게가 작음*
- 본 DP에 *진짜 architectural 결정*은 거의 없음 — 4/5가 제약, 1/5가 작은 최적화

→ 그렇다면 본 프로젝트의 *진짜* 장애 격리 어려움은 다른 곳에 있다. 본 메모는 그 후보 4개를 정리한 것.

---

## 1. 후보 4개

### 후보 1 — 외부 sub-agent의 *격리 + 신뢰 경계*

**문제**: 본 프로젝트의 MAF는 builtin sub-agent뿐 아니라 *외부에서 동적으로 로드되는* sub-agent를 호출할 가능성이 있다. *우리가 짜지 않은 코드를 사용자 디바이스에서 실행*하는 것.

**왜 어려운가**:
- 신뢰 모델: untrusted code with elevated permissions (Accessibility·네트워크 등)
- OS 표준 샌드박싱(SEAndroid·UID)으로 *일부* 격리되지만, **capability granting**(어디까지 권한을 줄 것인가)은 우리가 직접 설계해야 함
- 자원 폭주(메모리·CPU·네트워크) 방어 — quota·rate limit 정책
- **종결 권한**: 누가 외부 agent를 죽일 수 있는가? 어떤 조건에서?
- **결과 신뢰**: 외부 agent가 반환한 데이터를 *검증 없이* 시스템에 흘려보내면 안 됨

**유사 사례**: Chrome extension sandbox, browser plugin model, Erlang OTP의 hot code loading + supervision
**해결의 어려움**: 표준 *서랍* 없음. capability-based security + resource quota + termination authority를 *직접 설계*해야 함

---

### 후보 2 — 외부 앱 *부분 부작용*의 회수

**문제**: Accessibility Service로 외부 앱(예: 항공권 예약 앱)을 조작 중에 *우리 프로세스가 크래시* 또는 *세션 중단*. 외부 앱 상태는 *우리 통제 밖*.

**왜 어려운가**:
- 시나리오: "항공권 예약 시작 → 출발지 입력 → 도착지 입력 → 날짜 선택 → 결제 직전 크래시"
- *예약됐는지 안 됐는지 모름* — DP-A2(영속화)로도 해결 불가, **외부 상태가 진실**
- 우리가 보낸 마지막 탭이 *결제 버튼이었는가, 다음 페이지였는가*가 영속화 시점과 어긋남
- 재시도하면 *중복 예약* 위험. 안 하면 *누락* 위험
- 진짜 해결: idempotency key (외부 앱은 그걸 모름) + side-effect 사전 logging + *post-hoc 외부 상태 재조회*

**유사 사례**: 분산 트랜잭션의 Saga 패턴, payment processing의 exactly-once, 두 단계 커밋의 *준비* 단계
**해결의 어려움**: 외부 앱이 *우리 프로토콜을 모름*. 모든 reconciliation을 *우리 쪽에서* 추론해야 함

---

### 후보 3 — 분산 *취소 전파*

**문제**: 사용자가 협상 중간에 "취소"를 누름. 또는 IDS가 *새로운 우선 의도*를 감지. 진행 중인 *모든 것*을 멈춰야 하는데, 여러 프로세스·여러 외부 시스템에 걸쳐 있음.

**왜 어려운가**:
- 취소가 *cascading*: IDS → MAF → 여러 active sub-agent → LLM server → in-flight Accessibility actions → 다른 PPA와의 협상
- 각 경계마다 *취소 의미가 다름*:
  - LLM 추론 취소: 추론 중단 + 자원 회수
  - Accessibility action 취소: *이미 일으킨 외부 부작용은 어떡함?*
  - 협상 취소: 다른 PPA에게 *프로토콜 메시지*로 알려야 함 (그쪽도 진행 중일 테니)
- 취소가 *부분 성공*하면? (어떤 sub-agent는 멈추고 어떤 건 못 멈춤)
- 표준 답이 없음 — *application-specific protocol*

**유사 사례**: Go의 context cancellation, Kotlin Coroutines structured concurrency — 그러나 둘 다 *같은 프로세스* 가정. 분산 + 외부 부작용으로 확장은 직접 설계.

---

### 후보 4 — 동시 세션 *자원 경합 + 격리*

**문제**: 여러 PPA 세션이 동시에 진행(친구 약속 + 가족 일정 + 회의 조율). LLM·Accessibility는 *공유 자원*. 한 세션의 부하가 다른 세션 지연·실패를 일으킴.

**왜 어려운가**:
- LLM server는 단일 — 동시 요청 시 *큐잉*. 한 세션이 큰 모델 호출을 던지면 다른 세션 대기.
- Accessibility는 *물리적 단일 자원*(폰 화면) — 두 세션이 동시에 화면 조작 불가
- per-session quota? scheduling 알고리즘? priority?
- 한 세션 *failure가 격리*되려면 자원도 *격리*되어야 함 — 그런데 자원이 단일이라 격리가 *시간 분할*뿐
- QAS-014(300MB) 예산을 *N 세션이 어떻게 나눠 가질지*

**유사 사례**: kubernetes의 resource quota, browser tab의 메모리·CPU 격리, mobile OS의 multi-app scheduling
**해결의 어려움**: 모바일에서는 *OS가 도와주지 않음*. 직접 quota·scheduling 엔진 설계.

---

## 2. 어느 게 *가장* 어려운가 — 솔직한 평가

| | 어려움의 본질 |
|---|---|
| **후보 1 — 외부 sub-agent 격리·신뢰** | *우리가 통제 못 하는 코드*를 *우리 디바이스에서* 실행시키는 *결합 문제*. 보안·격리·기능이 한 결정 안에서 충돌. **표준 솔루션이 없음** |
| **후보 2 — 외부 앱 부분 부작용** | *외부 시스템 상태가 진실*인 세계에서의 회수. 우리 쪽 영속화만으로는 *원리적으로* 안 됨. reconciliation을 **우리가 직접 설계**해야 함 |
| 후보 3 — 분산 취소 전파 | 어렵지만 *조합* 문제 — 표준 패턴들(structured concurrency, saga)을 합성하면 가능 |
| 후보 4 — 자원 경합·격리 | 어렵지만 *측정·튜닝* 문제 — quota/scheduling 알고리즘 선택의 문제 |

후보 1·2는 **표준 답이 없어서** 어렵고, 후보 3·4는 **표준 답을 조합·튜닝**하면 어느 정도 풀린다.

---

## 3. 후속 DP 후보로의 승격 방향

본 프로젝트의 실제 범위에 따라 어느 후보가 *별도 DP*로 승격할지 결정:

- 외부 sub-agent를 *실제로 도입할 계획*이면 → **후보 1 중심으로 별도 DP** (가칭: "DP-external-agent-isolation")
- 캘린더·예약 같은 *side-effect 액션*이 핵심 기능이면 → **후보 2 중심으로 별도 DP** (가칭: "DP-side-effect-recovery")
- 위 둘 다 해당이면 → **두 DP 모두 만들고** 현 DP-fault-isolation은 *baseline*으로 남김

기존 [DP-fault-isolation.md](../../07-DP후보안/DP-fault-isolation.md)는 *프로세스 분리 baseline*만 정한 것이고, 위 두 DP가 추가되면 본 프로젝트의 장애 격리 설계가 *완성*된다.

---

## 4. 다음 단계

1. 본 프로젝트 범위에 외부 sub-agent가 있는지 확인 → 후보 1 DP 승격 여부 결정
2. 본 프로젝트 시나리오에 side-effect 액션이 있는지 확인 → 후보 2 DP 승격 여부 결정
3. 승격할 후보가 정해지면, 그 DP 후보안을 [07-DP후보안/](../../07-DP후보안/) 에 새로 작성
4. 본 메모는 *탐색 이력*으로 _legacy에 보존
