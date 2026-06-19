## SLIDE 1 | 과제 배경 | 해결되지 않은 문제

### 일상의 미세 의사결정 — 여전히 사람이 직접 처리하는 현실

**■ 타인과의 일상적 조율의 높은 비용**
- 하루 수 건씩 발생하는 일정 조율·장소 선택·조건 협의
- 2인 조율 기준 평균 **7.3회** 메시지 왕복 소요
  > Calendly, "How to find a meeting time that works for everyone"
  > https://calendly.com/blog/find-a-meeting-time
- 참여자 증가에 따른 비선형 급증: N(N−1)/2 쌍
  **2인=1쌍, 3인=3쌍, 5인=10쌍**
- 누적 결정 피로 → 질 낮은 선택 반복

**■ 부담이 심화되는 두 가지 상황**
- **민감 정보 포함 시:** 일정·건강·선호 데이터의 클라우드 전송·타인 제공 어려움 → 사람이 직접 처리
- **다수 의견 조율 시:** 참여자 증가에 따른 시간 교집합 감소·왕복 비용 급증

---

### 기존 AI 비서의 한계

**■ "단일 사용자 + 명령 대기" 구조**
- 사용자 직접 지시 시에만 동작하는 Reactive 모델
- 상대방 Agent와의 자율 협상·합의 기능 부재
- 단일 사용자 컨텍스트 내 동작 — 타인 조율 불가

**■ 민감 협상에 부적합한 클라우드 처리 방식**
- 협상을 위한 개인 데이터(일정·대화·선호)의 클라우드 전송 필수
- 민감 정보 포함 사안일수록 사용자 위임 의지 저하
- 온디바이스 처리 + 최소 정보 교환 구조 필요

**■ → 해결을 위한 두 가지 필수 요소**
- **IDS:** 디바이스 컨텍스트 기반 사용자 Intent 능동 감지 (명령 없이도)
- **MAF:** 감지된 Intent 기반 상대방 Agent와의 자율 협상 수행

> "필요한 것은 내가 직접 협상하는 것도, 데이터를 클라우드에 맡기는 것도 아니다.
> 내 기기 안의 Agent가 내 의도를 먼저 읽고,
> 상대방 Agent와 자율적으로 합의하여, 결과만 가져다 주는 것이다."

---
---

## SLIDE 2 | 과제 배경 | 기술 환경

### Agentic AI와 온디바이스 LLM의 성숙

**■ Agentic AI의 시장 주류 진입 (2026)**
- AI의 '답변'에서 '자율 행동'으로의 전환
- 2026년 말 엔터프라이즈 앱 **40%** AI Agent 탑재 전망
  > Gartner Press Release, 2025.8
  > https://www.gartner.com/en/newsroom/press-releases/2025-08-26-gartner-predicts-40-percent-of-enterprise-apps-will-feature-task-specific-ai-agents-by-2026-up-from-less-than-5-percent-in-2025
- Google(Android·Gemini)·Apple(iOS·Siri) — Agent 기반 전환 중
- Samsung — Android 위 Galaxy AI 기반 독자 Agent 경험 구현 중
  > Samsung Global Newsroom, 2026.3.1
  > https://news.samsung.com/global/samsung-advances-galaxy-ai-and-its-connected-ecosystem-at-mwc-2026

**■ 온디바이스 LLM의 실용화**
- Galaxy S26: 온디바이스 LLM 탑재 (Compact / Balanced / Supreme 3종)
  > Samsung Global Newsroom, 2026.3.9
  > https://news.samsung.com/global/samsung-unveils-galaxy-s26-series-the-most-intuitive-galaxy-ai-phone-yet
- 기기 외부 데이터 유출 없이 추론·협상 가능
- **IDS(Intent 감지)·MAF(Agent 협상) 모두 온디바이스 처리 가능**

---

### Agent 간 협상 — 기업·개인 모두 부재

**■ A2A 프로토콜: '협상'이 아닌 '작업 위임' 표준**
- Google 주도 A2A(Agent2Agent) 발표(2025.4) → 150+ 조직 채택, 주요 클라우드 통합
  > PR Newswire, 2026
  > https://www.prnewswire.com/news-releases/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year-302737641.html
- A2A — "일을 시키고 결과를 받는" Task 위임·조율 프로토콜
- 진정한 '협상'(제안·역제안·합의)은 A2A 설계 범위 밖
  > A2CN 개발 배경: "MCP, A2A, AP2 — 조직 경계를 넘는 상업적 협상을 커버하는 것은 없다"
  > https://a2cn.io

**■ 기업 간 진정한 Agent 협상: 이제 막 시작**
- Pactum × Walmart 공급사 계약 재협상 — AI Agent 적용 소수 선례
  > Hoek et al., 2022
  > https://arxiv.org/pdf/2503.06416
- 독자 플랫폼 기반 — 표준화된 기업 간 Agent 협상 인프라 부재

**■ 개인 간 Agent 자율 협상: 완전한 미개척**
- 기업 간 협상조차 이제 막 시작 — 개인 간 사례 전무
- 기술 부재가 아님 — 아직 아무도 구현하지 않은 영역

> "기업들 사이에서도 Agent가 협상하는 것은 이제 막 시작됐다.
> 개인들 사이에서는 아직 아무것도 없다."

---
---

## SLIDE 3 | 과제 필요성 | 왜 지금, 왜 당사인가

### 당사의 고유 실현 조건

**■ 폰 + 가전 통합 생태계**
- 스마트폰 + 세탁기·TV·냉장고 — 당사만 보유한 디바이스 생태계
- Google·Apple은 스마트폰 중심 — 당사 생태계 구조는 당사만의 고유 자산

**■ 이미 구축된 Agent 역량 기반**
- Galaxy AI 기반 단일 기기 내 Agent 기능 이미 실현
- 본 과제 = 기존 기반 위 기기 간 자율 협상 레이어 추가

**■ MX + DA + Cloud 통합 인프라**
- 모바일·가전·클라우드 Agent 경험 — 당사 내 모두 보유
- 공통 Agent 협상 레이어 연결 가능한 유일한 사업자

---

### 과제 구성 · 목표 · 기대 효과

**■ 핵심 구성**

| 구성 요소 | 역할 |
|---|---|
| **IDS** (Intent Driven Secretary) | 디바이스 컨텍스트 모니터링 기반 사용자 명시적·비명시적 Intent 능동 감지·분류 |
| **MAF** (Multi-Agent Framework) | 감지된 Intent 기반 Agent 동적 구성 및 상대방 Agent와의 자율 협상 수행 |

흐름: `사용자 행동 → IDS 감지 → Task 생성 → MAF 협상·실행 → 결과 전달`

**■ 과제 목표**

> 사용자의 AI Agent가 상대방 Agent와 자율 협상하여,
> 일상의 미세 의사결정에서 발생하는 인지 부하를 제거한다.

**■ 기대 효과**

**① Galaxy 단말 차별화 축 확보**
- H/W 평준화 이후 새로운 경쟁 변수: "내 Agent가 상대 Agent와 협상하는 능력"
- 선제 제품화 시 다음 단말 사업의 핵심 차별화 축

**② 폰+가전 통합 Agent Ecosystem 실현**
- MX + DA + Cloud 공통 Agent Layer — 당사 생태계 자산의 완전한 활용
