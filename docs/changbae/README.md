# Stakeholder 기반 QA·FR 재도출 분석

> 작성일: 2026-08-04 · 작성 브랜치: `changbae`
> 본 폴더는 On-Device Agentic Platform 과제의 **Quality Attributes와 Functional Requirements를
> Stakeholder 관점에서 처음부터 다시 도출**한 산출물이다. 기존 `docs/` 파일은 수정하지 않는다.

---

## 1. 분석 조건 (사용자 지시)

1. **독립 도출 원칙** — 기존 요구사항·QA 문서(`docs/04-FR.md`, `docs/05-NFR.md`, `docs/07-QAS.md`)를 **도출 근거로 사용하지 않는다.** 근거는 과제 설명(01·02)·Stakeholder VOC(03·annex 원본표)·상호작용 시나리오 9종(annex)으로 한정한다.
2. **기술 형식 구분** — FR은 기능이므로 *"~하는 기능을 제공해야 한다"*, QA는 정도이므로 *"~을 최대화/최소화해야 한다 (측정 지표)"* 형태로 기술한다.
3. **포커스: 다자간 협상(N-party Negotiation)** — 협상 알고리즘은 NegMAS 기반: 각 참여자가 자기 옵션을 효용 함수로 점수화 → 최고점 후보를 상대에게 제안 → 수신자는 자기 효용이 threshold 이상이면 수락, 미만이면 거절 후 역제안. 본 과제는 이 **2자 프로토콜의 다자 확장을 설계**한다. (지시 시점상 06~09 문서와 04 문서 매트릭스 해석에 반영됨)
4. **PL 지정** — Functional Correctness가 최우선 QA이며 그 정의 자체를 함께 수립한다 (05 문서).

## 2. 산출 문서

| 단계 | 내용 | 산출 문서 |
|---|---|---|
| 1 | 과제 이해 및 주요 stakeholder 10개 역할 도출 | [`01-Stakeholder-도출.md`](01-Stakeholder-도출.md) |
| 2 | Stakeholder별 QA 10개씩 도출 (ISO/IEC 25010:2023, 정량 방향 형식) | [`02-Stakeholder별-QA-도출.md`](02-Stakeholder별-QA-도출.md) |
| 3 | QA를 9개 품질 특성 카테고리로 취합·빈도 분석 | [`03-QA-카테고리-정리.md`](03-QA-카테고리-정리.md) |
| 4 | QA 전수(37종) 중요도·난이도 H/M/L 평가 | [`04-QA-중요도-난이도-평가.md`](04-QA-중요도-난이도-평가.md) |
| 5 | (PL 지시) Functional Correctness 정의 수립 | [`05-Functional-Correctness-정의.md`](05-Functional-Correctness-정의.md) |
| 6 | Stakeholder별 FR 10개씩 도출 ("기능 제공" 형식) | [`06-Stakeholder별-FR-도출.md`](06-Stakeholder별-FR-도출.md) |
| 7 | FR을 기능 카테고리(A~J)로 취합·통합 (100건 → CFR 66건) | [`07-FR-카테고리-정리.md`](07-FR-카테고리-정리.md) |
| 8 | FR(CFR 66건) 중요도·난이도 H/M/L 평가 | [`08-FR-중요도-난이도-평가.md`](08-FR-중요도-난이도-평가.md) |
| 9 | 빈도 상위(4 이상) 핵심 QA 11종 집중 평가 + 다자 확장 함의 | [`09-핵심-QA-중요도-난이도-평가.md`](09-핵심-QA-중요도-난이도-평가.md) |

## 3. 방법론 근거

텍스트북 인용은 **개념 수준의 참조**이며 원문 문장의 직접 인용이 아니다.

| 기법 | 적용 위치 | 출처 |
|---|---|---|
| Stakeholder 식별 — 관점(viewpoint)별 이해관계자 열거와 관심사 수집 | 01 | Sommerville, *Software Engineering* (10th ed.) — Requirements Engineering; Wiegers & Beatty, *Software Requirements* (3rd ed.) — Stakeholder 분석 |
| Stakeholder 범주 커버리지 — 사용자·획득자·개발자·운영자·평가자 등 범주의 완전성 점검 | 01 | Bass, Clements, Kazman, *Software Architecture in Practice* (4th ed.) |
| 요구사항의 FR/QA 분리 — 기능(무엇을 하는가)과 품질(얼마나 잘 하는가)의 구분 기술 | 02·06 | Sommerville (10th ed.) — Functional / Non-functional requirements; ISO/IEC 25010:2023 |
| 품질 속성 분류 체계 (9특성 40하위특성) | 02·03 | ISO/IEC 25010:2023 (SQuaRE Product Quality Model) |
| (Importance, Difficulty) 쌍 평가 — Utility Tree / ATAM의 우선순위화 기법 | 04·08·09 | Bass, Clements, Kazman (4th ed.) — Quality Attributes·평가(ATAM) |
| ASR(Architecturally Significant Requirement) 식별 — (H,H) 사분면 선별 | 04·08·09 | 같은 책 |
| 협상 메커니즘 참조 — 교대 제안·효용 함수·수락 threshold | 07·08·09 | NegMAS (자동 협상 프레임워크) — 사용자 지시로 채택된 알고리즘 기반 |

## 4. 입력 자료 (근거)

- [`docs/01-과제-배경-및-목적.md`](../01-과제-배경-및-목적.md) — 시스템 목적·비전·사용자 가치
- [`docs/02-과제-개요.md`](../02-과제-개요.md) — 시스템 구성·범위·대표 시나리오·3대 검증 가설·제약
- [`docs/03-Stakeholder.md`](../03-Stakeholder.md) · [`annex/Stakeholder-원본표.md`](../../annex/Stakeholder-원본표.md) — 18개 역할과 VOC
- [`annex/상호작용-시나리오-9종.md`](../../annex/상호작용-시나리오-9종.md) — 시나리오별 문제·설계 포인트
- 사용자·PL 구두 지시 (2026-08-04): FC 최우선 및 정의 수립 / 독립 도출 / 다자간 협상 포커스 (NegMAS 기반)

> **의도적 제외**: `docs/04-FR.md` · `docs/05-NFR.md` · `docs/07-QAS.md` — 독립 도출 원칙에 따라 본 분석의 근거로 사용하지 않았다.

## 5. 표기 원칙

- 근거가 원본 자료에 있는 항목은 출처를 표기하고, 원본에 없는 판단(순위·등급·정의 제안·카테고리 체계)은 **"분석자 판단/추론"** 으로 명시한다.
- ISO/IEC 25010:2023 개정 반영: Usability → **Interaction Capability**, Portability → **Flexibility**, **Safety** 특성 신설, Reliability의 Maturity → **Faultlessness**, Security에 **Resistance** 추가.
