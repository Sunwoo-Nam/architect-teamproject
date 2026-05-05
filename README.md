# Ondevice Agentic Platform — SW Architect 팀과제

> 자율 협상 및 권한 위임 기반의 **온디바이스 개인화 에이전트 플랫폼** 설계 산출물 저장소

---

## 본문 (1~6)

| # | 문서 | 내용 |
|---|---|---|
| 1 | [01-과제-배경-및-목적.md](01-과제-배경-및-목적.md) | 이 과제가 왜 태어났고, 왜 반드시 필요한지 |
| 2 | [02-과제-개요.md](02-과제-개요.md) | 시스템 명칭·핵심 개념·구성·범위·대표 시나리오·Context Diagram |
| 3 | [03-Stakeholder.md](03-Stakeholder.md) | 18명의 stakeholder와 각자의 VOC |
| 4 | [04-FR.md](04-FR.md) | 기능 요구사항 (4개 버전 보존) |
| 5 | [05-NFR.md](05-NFR.md) | 비기능 요구사항 + 제약 사항 (docx 원본 기준) |
| 6 | [06-QAS.md](06-QAS.md) | 24개 품질 시나리오 인덱스, NFR 7개·QA 8개 선정 결과 |

> **어체**: 본문은 음슴체. 단, FR(`04-FR.md`)·NFR(`05-NFR.md`)은 원본 어체("~한다") 그대로 유지.

---

## 도식 (drawio)

| 파일 | 설명 |
|---|---|
| [02-context-diagram.drawio](02-context-diagram.drawio) | arch-with-ai 관점 — 시스템 내부(IDS/MAF) 일부 노출 |
| [ondevice_agentic_platform_context_diagram.drawio](ondevice_agentic_platform_context_diagram.drawio) | C4 표준 System Context |
| [ondevice_agentic_platform_deployment_diagram.drawio](ondevice_agentic_platform_deployment_diagram.drawio) | 배치 다이어그램 |
| [ondevice_agentic_platform_domain_model.drawio](ondevice_agentic_platform_domain_model.drawio) | 도메인 모델 |

> 모든 도식은 [draw.io](https://app.diagrams.net/) 에서 열어 직접 수정 가능.

---

## 별첨 (annex/)

본문에서 직접 다루지는 않지만 **원본 도출 가치**가 있어 별도 보관하는 자료.

| 파일 | 내용 |
|---|---|
| [annex/약어.md](annex/약어.md) | PA / DA / SA / N-party 등 약어 정의 |
| [annex/상호작용-시나리오-9종.md](annex/상호작용-시나리오-9종.md) | docx 원본의 9개 상호작용 모델(P2P / Hierarchical / B2C / Delegation) 전체 |
| [annex/아키텍처-주요-용어.md](annex/아키텍처-주요-용어.md) | 트랜잭션 원자성 / 비동기 협상 / RAG / DAG |
| [annex/Stakeholder-원본표.md](annex/Stakeholder-원본표.md) | docx 원본의 Stakeholder 표 (빈 행·중복 ID 등 원본 그대로) |
| [annex/Usecase-원본.md](annex/Usecase-원본.md) | docx 원본의 UC 01~04 (Discovery / Secure Connection / Lifecycle / Negotiation) |
| [annex/qas/QS-001 ~ QS-024](annex/qas/) | 24개 품질 시나리오의 개별 상세 명세 (arch-with-ai 출처) |
| [annex/qas/_scenarios-utility-tree.md](annex/qas/_scenarios-utility-tree.md) | Utility Tree 시각화 |
| [annex/qas/_evaluations.md](annex/qas/_evaluations.md) | 24개 QAS 평가 과정·근거 |

---

## 원본 자료 (변경 금지)

| 파일 | 비고 |
|---|---|
| `[SW Architect 팀과제] On-Device Agentic Platform.docx` | 과제 본문 |
| `20260417_[SW Architect 팀과제] On-Device Agentic Platform.docx` | 일자별 보관본 |
| `AI에게 던지기 용 과제 설명.docx` | 요약본 |

---

## 작업 원칙

본 저장소의 모든 작업은 [`CLAUDE.md`](CLAUDE.md)에 기록된 원칙을 따른다.

1. **변경 사전 동의 원칙** (Ask-Before-Change)
2. **사실 기반 작성 원칙** (Evidence-Based)
3. **비판적·이성적 사고 원칙** (Critical Thinking)
4. 모든 도식은 **drawio xml** 형식으로 작성

---

## 빠르게 시작하기

처음 들르는 사람은 다음 순서로 읽으면 됨.

1. [01-과제-배경-및-목적.md](01-과제-배경-및-목적.md) — 우리가 왜 이걸 하는지
2. [02-과제-개요.md](02-과제-개요.md) — 무엇을 만드는지 (Context Diagram 포함)
3. [03-Stakeholder.md](03-Stakeholder.md) — 누구의 목소리를 들어야 하는지
4. [06-QAS.md](06-QAS.md) — 어떤 품질로 만들어야 하는지 (선정된 NFR/QA)
5. [04-FR.md](04-FR.md) / [05-NFR.md](05-NFR.md) — 원본 docx의 요구사항 전체

---

## 참고 외부 저장소

본 저장소의 일부 자료는 사전 작업 산출물인 [`arch-with-ai`](../arch-with-ai/) 저장소에서 가져온 것임. 출처는 각 파일 상단에 명시되어 있음.
