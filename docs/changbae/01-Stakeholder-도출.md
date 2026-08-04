# 1. 주요 Stakeholder 10개 역할 도출

> 입력: [`docs/03-Stakeholder.md`](../03-Stakeholder.md)의 18개 역할(원본표 기준, ID 16 중복 포함),
> [`annex/Stakeholder-원본표.md`](../../annex/Stakeholder-원본표.md)
> 방법: Sommerville·Wiegers의 stakeholder 식별 원칙 + Bass(*Software Architecture in Practice*)의
> 이해관계자 범주 커버리지 점검 + 원본 영향도/관심도 매트릭스(03 문서 §3.3)

---

## 1.1 선정 기준 (분석자 판단)

1. **Key Player 우선**: 영향도↑/관심도↑ 분면의 역할은 기본 포함한다 (03 문서 §3.3).
2. **범주 커버리지**: Bass의 이해관계자 범주(사용자 / 획득자·비즈니스 / 설계자 / 구현자 / 운영자 / 플랫폼 / 평가자)가 모두 최소 1개 역할로 대표되어야 한다.
3. **과제 범위 정합**: FR/NFR에서 명시적으로 범위 제외(Out of Scope)된 영역만 대표하는 역할은 후순위로 한다.
4. **관심사 중복 병합**: VOC가 실질적으로 겹치는 역할은 하나로 병합하고 그 사실을 명시한다.

## 1.2 선정 결과 — 10개 역할

| # | Stakeholder | Bass 범주 | 원본 분면 | 선정 근거 |
|---|---|---|---|---|
| S1 | **End User** | 사용자 | Key Player | 가치의 1차 소비자. 위임·승인·프라이버시·통제권의 주체 (03 §3.2.1) |
| S2 | **Counterparty User** | 사용자 (간접) | 영향도↓/관심도↑ | NPN은 **양쪽 모두 안전하다고 느낄 때만 성립**한다 (03 §3.2.2). 협상 시스템의 특수성상 상대편 관점은 생략 불가 |
| S3 | **Service Proxy Agent Owner** | 획득자·비즈니스 (외부) | 영향도↓/관심도↑ | 9개 시나리오 중 B2C 계열(5·6·7·9번)의 실질 카운터파트. 인증·정책 반영·기존 시스템 연동 요구의 원천 |
| S4 | **Project Leader** | 획득자 | Key Player | 과제 방향·검증 가치 책임. **Functional Correctness 최우선 지정(2026-08-04 구두 지시)** 의 발화자 |
| S5 | **Architect** | 설계자 | Key Player | 모듈 경계·확장성·변경 추적성의 책임자 (03 §3.2.5) |
| S6 | **Multi-agent Framework Developer** | 구현자 | Key Player | Orchestrator·Meta Agent·Sub-Agent 구현. sandbox·재시도 정책·lifecycle 표준화 요구의 원천 |
| S7 | **Security / Privacy 담당** (개인정보 보안 담당자 병합) | 평가자 | Key Player | 원본 ID 9와 ID 17은 관심사(최소 권한·데이터 보호·감사 / PII 흐름 통제)가 실질적으로 겹쳐 **하나의 보안·프라이버시 관점으로 병합** (분석자 판단, §1.4 참조) |
| S8 | **AI/ML Engineer** | 구현자 (특수) | Key Player | Intent 품질·온디바이스 추론·모델 교체 — 3대 검증 가설 중 "온디바이스 LLM 실용성"의 직접 책임자 |
| S9 | **운영 / SRE** | 운영자 | 영향도↓/관심도↑ | 세션 복구·장애 격리·관측 가능성 — PoC가 운영 단계로 가기 위한 품질 관점 대표 |
| S10 | **MX H/W 담당자** | 플랫폼 | 영향도↑/관심도↓ | Doze/OOM·발열·배터리 등 **온디바이스 제약의 최종 관문**. "온디바이스 LLM 실용성" 가설의 판정 관점 |

## 1.3 제외한 8개 역할과 그 사유 (분석자 판단)

| 제외 역할 | 사유 | 관심사의 대변자 |
|---|---|---|
| UX 디자인 팀 | VOC(승인 최소 단계, 침습성 회피)가 End User의 Interaction Capability 요구와 동일 방향 | S1 |
| 품질 검증팀 | VOC(정량 측정, Mock 재현, 장애 주입)가 Testability로 수렴 | S5·S6의 Testability |
| Third-party Sub-Agent Developer | Sub-Agent FR/NFR 자체가 중간점검까지 스펙 아웃 (04-FR §3, 05-NFR §3) | S6 (Safe Integration) |
| 가전사 담당자 | Device Agent NFR이 중간점검까지 범위 제외 (05-NFR §3). 단 DPA 컨텍스트 수집은 범위 내이므로 보안 요구는 S7이 대변 | S7 |
| Legal / Compliance | 영향도↑/관심도↓. 책임 소재·감사 요구는 Accountability·Non-repudiation으로 수렴 | S7 |
| MX 상품화 의사결정 담당자 | PoC **이후** 단계의 의사결정자. 판단 재료(검증/미검증 구분)는 S4의 Testability 요구로 수렴 | S4 |
| Cloud 담당자 | 서버 LLM은 Orchestrator(Task Planning) 한 지점으로 한정됨 (05-NFR-MAF-06). 장애 비전파 요구는 S9의 Fault Tolerance로 수렴 | S9 |
| (원본 중복분) | 원본표 ID 16 중복은 별개 역할 2개로 계수했으며 위 두 행에서 각각 처리 | — |

## 1.4 병합 결정의 근거

원본표에서 ID 9(Security/Privacy 담당)는 관심사가 기재되어 있고, ID 17(개인정보 보안 담당자)은 공란이다.
03 문서가 ID 17의 VOC를 추정으로 보완했으나, 그 내용(PII 흐름·최소 보관·요약 공유)은 ID 9의
관심사(데이터 보호·최소 권한)의 세부 전개에 해당한다. 별도 역할로 유지하면 QA 목록이 사실상 중복되므로
**하나의 관점(S7)으로 병합**하되, PII 특화 요구(요약·추상화 공유, 민감 사용자 그룹 보호)를 S7의 QA에 반영한다.

## 1.5 커버리지 자기 점검

- Bass 7개 범주 모두 최소 1개 역할로 대표됨 (사용자 2, 획득자 2, 설계자 1, 구현자 2, 운영자 1, 플랫폼 1, 평가자 1).
- 03 문서 §3.3의 Key Player 7인 중 7인 전원 포함 (병합 1건 반영 시 6개 역할 + PL).
- 한계: B2B·엔터프라이즈 관점(SDS)은 과제 범위 외(02 §2.5.2)이므로 미포함.
