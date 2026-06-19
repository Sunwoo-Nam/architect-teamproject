## SLIDE 1 | 과제 배경 | 해결되지 않은 문제

### 일상의 미세 의사결정, 왜 여전히 사람이 직접 하는가

**■ 타인과의 일상적 조율이 생각보다 많은 비용을 유발한다**
- 일정 조율, 장소 선택, 조건 협의 등이 하루 수 건씩 발생
- 2인 조율 시에도 평균 **7.3회**의 메시지 왕복 소요
  > Calendly, "How to find a meeting time that works for everyone"
  > https://calendly.com/blog/find-a-meeting-time
- N명 참여 시 가능한 시간 교집합 쌍 수 = N(N−1)/2 로 증가
  **2인=1쌍, 3인=3쌍, 5인=10쌍** — 참여자가 늘수록 비선형으로 급증
- 누적된 결정 피로 → 질 낮은 선택의 반복

**■ 두 가지 상황에서 부담이 특히 심하다**
- **민감 정보 포함 시:** 일정·건강·선호 데이터를 클라우드에 전송하거나 타인에게 직접 제공하기 어려움. 결국 사람이 직접 처리
- **다수 의견 조율 시:** 참여자가 늘수록 가능한 시간 교집합이 줄어들고 왕복 비용이 급증

---

### 기존 AI 비서가 이를 해결하지 못하는 이유

**■ 현재 AI 비서는 "단일 사용자 + 명령 대기" 구조**
- 사용자가 직접 지시할 때만 동작하는 Reactive 모델
- 상대방 Agent와 자율 협상·합의하는 기능 없음
- 한 사람의 컨텍스트 안에서만 동작, 타인과의 조율 불가

**■ 클라우드 처리 방식은 민감 협상에 부적합**
- 개인 일정·대화·선호 데이터를 클라우드로 전송해야 협상 가능
- 민감 정보가 포함된 사안일수록 사용자의 위임 의지 저하
- 온디바이스에서 처리하면서 최소 정보만 교환하는 구조 필요

**■ → 이 문제를 해결하려면 두 가지가 필요하다**
- **IDS:** 명령 없이도 디바이스 컨텍스트에서 사용자 Intent를 능동적으로 감지
- **MAF:** 감지된 Intent를 기반으로 상대방 Agent와 자율 협상을 수행

> "필요한 것은 내가 직접 협상하는 것도, 데이터를 클라우드에 맡기는 것도 아니다.
> 내 기기 안의 Agent가 내 의도를 먼저 읽고,
> 상대방 Agent와 자율적으로 합의하여, 결과만 가져다 주는 것이다."

---
---

## SLIDE 2 | 과제 배경 | 기술 환경

### Agentic AI와 온디바이스 LLM의 성숙

**■ Agentic AI의 시장 주류 진입 (2026)**
- AI가 '답변'에서 '자율 행동'으로 전환
- 2026년 말까지 엔터프라이즈 앱 **40%**가 AI Agent 탑재 전망
  > Gartner Press Release, 2025.8
  > https://www.gartner.com/en/newsroom/press-releases/2025-08-26-gartner-predicts-40-percent-of-enterprise-apps-will-feature-task-specific-ai-agents-by-2026-up-from-less-than-5-percent-in-2025
- Google은 Android·Gemini를, Apple은 iOS·Siri를 Agent 기반으로 전환 중
- Samsung은 Android 위에서 Galaxy AI를 통해 독자 Agent 경험을 구현 중
  > Samsung Global Newsroom, 2026.3.1
  > https://news.samsung.com/global/samsung-advances-galaxy-ai-and-its-connected-ecosystem-at-mwc-2026

**■ 온디바이스 LLM의 실용화**
- Galaxy S26: 온디바이스 LLM 탑재 (Compact / Balanced / Supreme 3종)
  > Samsung Global Newsroom, 2026.3.9
  > https://news.samsung.com/global/samsung-unveils-galaxy-s26-series-the-most-intuitive-galaxy-ai-phone-yet
- 민감 데이터를 기기 밖으로 내보내지 않고 추론·협상 가능
- **Intent 감지(IDS)와 Agent 간 협상(MAF), 두 가지 모두 온디바이스에서 처리 가능**

---

### Agent 간 협상: 기업도 개인도 아직 없다

**■ A2A 프로토콜: '협상'이 아닌 '작업 위임' 표준**
- Google 주도 A2A(Agent2Agent) 발표(2025.4) → 150+ 조직 채택, 주요 클라우드 통합
  > PR Newswire, 2026
  > https://www.prnewswire.com/news-releases/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year-302737641.html
- A2A는 "일을 시키고 결과를 받는" Task 위임·조율 프로토콜
- 조건을 두고 제안·역제안·합의하는 진정한 '협상'은 A2A의 설계 범위 밖
  > A2CN 개발 배경: "MCP, A2A, AP2 — 조직 경계를 넘는 상업적 협상을 커버하는 것은 없다"
  > https://a2cn.io

**■ 기업 간 진정한 Agent 협상: 이제 막 시작**
- Pactum이 Walmart 공급사 계약 재협상에 AI Agent를 적용한 소수 선례 있음
  > Hoek et al., 2022
  > https://arxiv.org/pdf/2503.06416
- 독자 플랫폼 기반. 표준화된 기업 간 Agent 협상 인프라는 아직 없음

**■ 개인 간 Agent 자율 협상: 완전한 미개척**
- 기업 간에도 이제 막 시작된 협상이, 개인 간에는 사례 자체가 없음
- 기술의 부재가 아니다. 아직 아무도 구현하지 않은 영역

> "기업들 사이에서도 Agent가 협상하는 것은 이제 막 시작됐다.
> 개인들 사이에서는 아직 아무것도 없다."

---
---

## SLIDE 3 | 과제 필요성 | 왜 지금, 왜 당사인가

### 당사의 고유 실현 조건

**■ 폰 + 가전 통합 생태계**
- 스마트폰 + 세탁기·TV·냉장고 — 당사만 보유한 디바이스 생태계
- Google·Apple은 스마트폰 중심. 이 생태계 구조는 당사만이 그릴 수 있는 그림

**■ 이미 구축된 Agent 역량 기반**
- Galaxy AI를 통해 단일 기기 내 Agent 기능이 이미 실현된 상태
- 본 과제는 이 기반 위에 기기 간 자율 협상 레이어를 추가하는 구조

**■ MX + DA + Cloud 통합 인프라**
- 모바일·가전·클라우드 Agent 경험이 당사 안에 모두 존재
- 공통 Agent 협상 레이어로 연결 가능한 유일한 사업자

---

### 과제 구성 · 목표 · 기대 효과

**■ 핵심 구성**

| 구성 요소 | 역할 |
|---|---|
| **IDS** (Intent Driven Secretary) | 디바이스 컨텍스트를 모니터링하여 사용자의 명시적·비명시적 Intent를 능동적으로 감지·분류 |
| **MAF** (Multi-Agent Framework) | 감지된 Intent를 기반으로 Agent를 동적으로 구성하고, 상대방 Agent와 자율 협상을 수행 |

흐름: `사용자 행동 → IDS 감지 → Task 생성 → MAF 협상·실행 → 결과 전달`

**■ 과제 목표**

> 사용자의 AI Agent가 상대방 Agent와 자율 협상하여,
> 일상의 미세 의사결정에서 발생하는 인지 부하를 제거한다.

**■ 기대 효과**

**① Galaxy 단말 차별화 축 확보**
- H/W 평준화 이후 새로운 경쟁 변수: "내 Agent가 상대 Agent와 협상하는 능력"
- 당사가 먼저 제품화하면 다음 단말 사업의 핵심 차별화 축이 됨

**② 폰+가전 통합 Agent Ecosystem 실현**
- MX + DA + Cloud 공통 Agent Layer — 당사 생태계 자산의 완전한 활용
