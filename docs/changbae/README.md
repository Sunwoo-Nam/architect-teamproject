# Stakeholder 기반 QA·FR 도출 분석 — 다자간 협상 범위

> 작성일: 2026-08-04 · 작성 브랜치: `changbae`
> 본 폴더는 On-Device Agentic Platform 과제의 범위를 **다자간 협상(N-party Negotiation)** 으로 한정하고,
> 그 범위에서 Quality Attributes와 Functional Requirements를 **Stakeholder 관점에서 도출**한 산출물이다.
> 기존 `docs/` 파일은 수정하지 않는다.

---

## 1. 분석 조건 (사용자 지시, 2026-08-04)

1. **범위: 다자간 협상** — 3인 이상의 사용자가 각자의 PPA를 투입해 공동 합의에 도달하는 시나리오(상호작용 시나리오 2)가 중심. 협상 알고리즘은 **NegMAS 기반**: 각 참여자가 자기 옵션 공간(OutcomeSpace)을 효용 함수(Ufun)로 점수화 → 최고점 후보 제안 → 수신자는 자기 효용이 threshold 이상이면 수락, 미만이면 거절 후 역제안. **이 2자 교대 제안 프로토콜의 N-party 확장을 설계**한다. 그룹 합의 후 예약(시나리오 6)은 확장 단계, 그 외(B2C 1:1·가전 중재·원격 케어)는 범위 외.
2. **독립 도출 원칙** — 기존 요구사항·QA 문서(`docs/04-FR.md`, `docs/05-NFR.md`, `docs/07-QAS.md`)를 도출 근거로 사용하지 않는다. 근거는 과제 설명(01·02)·Stakeholder VOC(03·annex 원본표)·상호작용 시나리오(annex)로 한정한다.
3. **기술 형식 구분** — FR은 *"~하는 기능을 제공해야 한다"*, QA는 *"~을 최대화/최소화해야 한다 (측정 지표)"* 형태로 기술한다.
4. **PL 지정 ①** — Functional Correctness가 최우선 QA이며 그 정의 자체를 함께 수립한다 (09 문서).
5. **PL 지정 ②** — 다중 의제 약속(예: 영화 — 날짜×영화×영화관×시간)에서 후보 조합의 전체 열거는 메모리 폭발을 일으키며, 현실적으로는 한 의제를 정하면 다른 의제의 후보 폭이 좁아진다. **이 탐색 공간 통제를 다루는 것이 중요 관심사** (구두 시나리오, 2026-08-04 — CFR-B5·B12와 설계 질문 8번으로 반영). *표기: PL 원 표현은 조합 크기 "K×L×M×N"이나, 참여자 수 N과의 혼동을 피하기 위해 본 문서군에서는 **K×L×M×P**로 표기한다 (원문 인용 제외).*

## 2. 산출 문서

문서 순서: **01 Stakeholder → 02~04 FR → 05~08 QA → 09 FC 정의(부록)**.

| # | 내용 | 산출 문서 |
|---|---|---|
| 01 | 다자 협상 범위의 주요 stakeholder 10개 역할 도출 | [`01-Stakeholder-도출.md`](01-Stakeholder-도출.md) |
| 02 | Stakeholder별 FR 10개씩 도출 ("기능 제공" 형식) | [`02-Stakeholder별-FR-도출.md`](02-Stakeholder별-FR-도출.md) |
| 03 | FR을 기능 카테고리(A~J)로 취합·통합 (100건 → CFR 64건) | [`03-FR-카테고리-정리.md`](03-FR-카테고리-정리.md) |
| 04 | FR(CFR 64건) 중요도·난이도 평가 → (H,H) 19건, 다자 신규 설계 영역 식별 | [`04-FR-중요도-난이도-평가.md`](04-FR-중요도-난이도-평가.md) |
| 05 | Stakeholder별 QA 10개씩 도출 (ISO/IEC 25010:2023, 정량 방향 형식) | [`05-Stakeholder별-QA-도출.md`](05-Stakeholder별-QA-도출.md) |
| 06 | QA를 9개 품질 특성 카테고리로 취합·빈도 분석 | [`06-QA-카테고리-정리.md`](06-QA-카테고리-정리.md) |
| 07 | QA 전수(37종) 중요도·난이도 H/M/L 평가 → (H,H) 11종 ASR 후보 | [`07-QA-중요도-난이도-평가.md`](07-QA-중요도-난이도-평가.md) |
| 08 | 빈도 상위(4 이상) 핵심 QA 12종 집중 평가 + 설계 질문 8가지 도출 | [`08-핵심-QA-중요도-난이도-평가.md`](08-핵심-QA-중요도-난이도-평가.md) |
| 09 | (PL 지시) 다자 협상에서의 Functional Correctness 4계층 정의 | [`09-Functional-Correctness-정의.md`](09-Functional-Correctness-정의.md) |

## 3. 핵심 결론 (요약)

- **FR**: 플랫폼 공통 기반(I, 31건)이 항목 수 최다이며, 과제 성격은 다자 협상 코어(B, 15건)·검증(J, 24건)의 비중에서 드러남. (H,H) 19건 중 **B2(라운드)·B4(동기화)·B8(양보)·B9(집계·정족수)·B11(이탈)** 이 "2자 → 다자 확장"의 신규 설계 목록이며, **B12(제약 전파 기반 탐색 공간 축소)** 가 다중 의제 조합 폭발(PL 지목)의 대응 설계다 (04 §4.4).
- **QA**: 빈도 공동 1위는 Functional Correctness · Fault Tolerance · Analysability · **Scalability**(6/10) — 포커스 주제의 품질 축이 도출에서도 1위로 나타남. (H,H) 11종이 ASR 후보 (07 §7.4).
- **다음 단계 입력**: 다자 프로토콜이 답해야 할 설계 질문 8가지 (08 §8.3) — 제안 토폴로지 / 집계 규칙 / 양보 전략 / 이탈 처리 / 정보 공개 / 개입 시점 / 합의 커밋 / 의제 분해·어젠다.

## 4. 방법론 근거

텍스트북 인용은 **개념 수준의 참조**이며 원문 문장의 직접 인용이 아니다.

| 기법 | 적용 위치 | 출처 |
|---|---|---|
| Stakeholder 식별 — 관점별 이해관계자 열거·관심사 수집 | 01 | Sommerville, *Software Engineering* (10th ed.); Wiegers & Beatty, *Software Requirements* (3rd ed.) |
| Stakeholder 범주 커버리지 점검 | 01 | Bass, Clements, Kazman, *Software Architecture in Practice* (4th ed.) |
| FR/QA 분리 기술 (기능 vs 정도) | 02·05 | Sommerville (10th ed.); ISO/IEC 25010:2023 |
| 품질 속성 분류 (9특성 40하위특성) | 05·06 | ISO/IEC 25010:2023 (SQuaRE Product Quality Model) |
| (Importance, Difficulty) 쌍 평가 — Utility Tree / ATAM | 04·07·08 | Bass, Clements, Kazman (4th ed.) |
| ASR 식별 — (H,H) 사분면 선별 | 04·07·08 | 같은 책 |
| 협상 메커니즘 — 교대 제안·효용 함수(Ufun)·OutcomeSpace·threshold·양보 전략 | 전반 | NegMAS (자동 협상 프레임워크) — 사용자 지시로 채택된 알고리즘 기반 |

## 5. 입력 자료 (근거)

- [`docs/01-과제-배경-및-목적.md`](../01-과제-배경-및-목적.md) · [`docs/02-과제-개요.md`](../02-과제-개요.md) — 목적·구성·범위·제약
- [`docs/03-Stakeholder.md`](../03-Stakeholder.md) · [`annex/Stakeholder-원본표.md`](../../annex/Stakeholder-원본표.md) — 18개 역할과 VOC
- [`annex/상호작용-시나리오-9종.md`](../../annex/상호작용-시나리오-9종.md) — 특히 시나리오 1·2·6의 문제·설계 포인트
- 사용자·PL 구두 지시 (2026-08-04): 다자간 협상 범위 한정 / NegMAS 기반 알고리즘 / FC 최우선·정의 수립 / 다중 의제 탐색 공간 통제(영화 약속 시나리오) / 독립 도출

> **의도적 제외**: `docs/04-FR.md` · `docs/05-NFR.md` · `docs/07-QAS.md` — 독립 도출 원칙에 따라 근거로 사용하지 않았다.

## 6. 표기 원칙

- 원본 자료에 있는 근거는 출처를 표기하고, 원본에 없는 판단(순위·등급·다자 확장 해석·카테고리 체계)은 **"분석자 판단/추론/확장"** 으로 명시한다. 원본 VOC는 1:1 협상 어휘이므로 다자 적용은 대부분 분석자 확장에 해당한다.
- ISO/IEC 25010:2023 개정 반영: Usability → **Interaction Capability**, Portability → **Flexibility**, **Safety** 신설, Maturity → **Faultlessness**, Security에 **Resistance** 추가.
