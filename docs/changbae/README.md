# Quality Attributes 재도출 — Stakeholder 기반 분석

> 작성일: 2026-08-04 · 작성 브랜치: `changbae`
> 본 폴더는 On-Device Agentic Platform 과제의 Quality Attributes(품질 속성)를
> **Stakeholder 관점에서 처음부터 다시 도출**한 산출물이다.

---

## 1. 목적

기존 [`docs/05-NFR.md`](../05-NFR.md)는 컴포넌트(IDS/MAF) 축으로 NFR을 정의했다.
본 분석은 반대 방향 — **"누가(stakeholder) 무엇을(QA) 왜(VOC) 중요하게 여기는가"** — 에서 출발하여,
품질 속성의 전체 지형을 다시 그리고 아키텍처 설계의 우선순위(ASR 후보)를 식별한다.

## 2. 산출 절차

| 단계 | 내용 | 산출 문서 |
|---|---|---|
| 1 | 과제 이해 및 주요 stakeholder 10개 역할 도출 | [`01-Stakeholder-도출.md`](01-Stakeholder-도출.md) |
| 2 | Stakeholder별 중요 QA 10개씩 도출 (ISO/IEC 25010:2023) | [`02-Stakeholder별-QA-도출.md`](02-Stakeholder별-QA-도출.md) |
| 3 | 전체 QA를 품질 특성 카테고리별로 취합·정리 | [`03-QA-카테고리-정리.md`](03-QA-카테고리-정리.md) |
| 4 | 전체 QA에 대해 중요도·난이도 H/M/L 평가 | [`04-QA-중요도-난이도-평가.md`](04-QA-중요도-난이도-평가.md) |
| 5 | (PL 지시) Functional Correctness의 정의 수립 | [`05-Functional-Correctness-정의.md`](05-Functional-Correctness-정의.md) |

## 3. 방법론 근거

본 분석이 따르는 기법과 그 출처는 다음과 같다. 텍스트북 인용은 **개념 수준의 참조**이며 원문 문장의 직접 인용이 아니다.

| 기법 | 적용 위치 | 출처 |
|---|---|---|
| Stakeholder 식별 — 시스템에 관여하는 다양한 관점(viewpoint)의 사람·조직을 체계적으로 열거하고 관심사를 수집 | 01 문서 | Sommerville, *Software Engineering* (10th ed.) — Requirements Engineering 장; Wiegers & Beatty, *Software Requirements* (3rd ed.) — Stakeholder 분석 |
| Stakeholder 범주 커버리지 — 사용자·획득자·개발자·운영자·평가자 등 역할 범주가 빠짐없이 대표되는지 점검 | 01 문서 | Bass, Clements, Kazman, *Software Architecture in Practice* (4th ed.) — 아키텍처 이해관계자 논의 |
| 품질 속성 분류 체계 | 02·03 문서 | ISO/IEC 25010:2023 (SQuaRE — Product Quality Model, 9특성 40하위특성) |
| (Importance, Difficulty) 쌍 평가 — 각 품질 속성 시나리오에 "시스템 성공에의 중요도"와 "달성(아키텍처적) 난이도"를 H/M/L로 부여하여 우선순위화. Utility Tree / ATAM에서 사용하는 표준 기법 | 04 문서 | Bass, Clements, Kazman, *Software Architecture in Practice* (4th ed.) — Quality Attributes 및 평가(ATAM) 장 |
| ASR(Architecturally Significant Requirement) 식별 — (H,H) 사분면의 속성을 아키텍처 핵심 동인으로 선별 | 04 문서 | 같은 책 — ASR 개념 |

## 4. 입력 자료 (근거)

- [`docs/01-과제-배경-및-목적.md`](../01-과제-배경-및-목적.md) — 시스템 목적·비전·기대효과
- [`docs/02-과제-개요.md`](../02-과제-개요.md) — 시스템 구성·범위·대표 시나리오·3대 검증 가설
- [`docs/03-Stakeholder.md`](../03-Stakeholder.md) 및 [`annex/Stakeholder-원본표.md`](../../annex/Stakeholder-원본표.md) — 18개 역할과 VOC
- [`docs/04-FR.md`](../04-FR.md) — 기능 요구사항 (IDS 5건, MAF 11건)
- [`docs/05-NFR.md`](../05-NFR.md) — 기존 NFR 16건
- [`docs/06-Constraints.md`](../06-Constraints.md) — CON-01(Android 한정), CON-02(동일 MAF 전제)
- [`annex/상호작용-시나리오-9종.md`](../../annex/상호작용-시나리오-9종.md) — 시나리오별 설계 포인트
- PL 구두 지시 (2026-08-04): *"Functional Correctness가 가장 중요한 QA이며, 그 정의 자체를 함께 고민할 것"*

## 5. 표기 원칙

- 근거가 원본 자료에 있는 항목은 출처를 표기한다.
- 원본에 없는 판단(우선순위 논리, H/M/L 등급, 정의 제안)은 **"분석자 판단"** 으로 명시한다.
- ISO/IEC 25010:2023 개정 반영: Usability → **Interaction Capability**, Portability → **Flexibility**, **Safety** 특성 신설, Reliability의 Maturity → **Faultlessness**, Security에 **Resistance** 추가.
