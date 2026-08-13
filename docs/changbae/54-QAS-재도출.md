# 54. QAS 재도출 — ISO/IEC 25010 매핑, VoC 추적

> **배경**: [`52`](52-Stakeholder-재편-VoC.md)의 VoC로부터 품질 요구를 재도출한다 (사용자 지시, 2026-08-13).
> **작성 원칙**:
> ① 시나리오는 **"~해야 한다" 문체**로 기술한다 (사용자 지시).
> ② 모든 QAS는 **ISO/IEC 25010 특성—부특성에 매핑**한다. 매핑은 **2023년판 기준**(Flexibility—Scalability, Safety—Operational Constraint 포함)이며, 비표준 QA를 만들지 않는다 (PL 지시 ⑥ — [`09`](09-Functional-Correctness-정의.md) 헤더).
> ③ 각 QAS는 근거 VoC 인덱스를 표기한다 (1:1일 필요 없음). 협상 내용과 관련된 품질만 포함한다.
> ④ 응답 측정의 기술 표기(달성률 수식·확장 지수 등)는 측정 정의 층의 언어로서 허용한다. 상세 측정 방법은 [`24`](24-QA-측정-핸드북.md) 계열 소관.
> **기존 문서와의 관계**: [`../07-QAS.md`](../07-QAS.md)(QS-001~024)·[`20`](20-핵심-QA-확정.md)~[`24`](24-QA-측정-핸드북.md)와 별개의 신규 도출이다. 정제 완료 후 정본 관계를 정리한다.

---

## 54.1 QAS 목록 — 14건

| ID | ISO 25010 특성 — 부특성 | Quality Attribute Scenario | 응답 측정 | VoC 매핑 |
|---|---|---|---|---|
| QAS-01 | Functional Suitability — **Functional Correctness** | 벤치마크 협상을 실행했을 때, 시스템은 도달 가능한 가장 좋은 합의에 근접한 결과를 도출해야 한다 | 달성률 U(r)/U(x\*) | PL-V5, PD-V2 |
| QAS-02 | Functional Suitability — **Functional Correctness** | 정상·장애 어떤 상황에서 협상이 종결되더라도, 확정 당사자 전원은 동일한 합의 레코드를 보유해야 한다 | 레코드 불일치 0건 | EU-V6, SD-V3 |
| QAS-03 | Safety — **Operational Constraint** | 위임 범위 밖의 안이 제안되었을 때, 시스템은 자동 수락을 차단하고 사용자 승인을 요청해야 한다 | 범위 초과 자동 수락 0건 | SP-V1, EU-V2 |
| QAS-04 | Security — **Confidentiality** | 참여자·중계자가 협상 트래픽을 관찰하더라도, 타인의 선호를 역추론할 수 있는 정보 이득이 제한되어야 한다 | 역추론 이득 (공격자 모델 기준) | SP-V5, EU-V3 |
| QAS-05 | Performance Efficiency — **Time Behaviour** | N명·의제 M개의 협상이 개시되면, 정해진 시간 내에 종결까지 완료되어야 한다 | 개시→종결 완료 시간 (통신 지연 포함 — 방법은 측정 정의에 위임) | EU-V1, EU-V7 |
| QAS-06 | Performance Efficiency — **Resource Utilization** | 협상 1건을 수행하는 동안, 단말 자원 점유는 정해진 상한과 OS 정책 이내여야 한다 | 피크 메모리·CPU 상한 내, 발열·배터리 정책 통과 | HW-V2, HW-V3, OM-V2 |
| QAS-07 | Flexibility — **Scalability** | 참여자 수가 3→10→50으로 증가하더라도, 메시지·메모리 증가가 허용 추세 내에 있고 완결률이 유지되어야 한다 | 확장 지수, 완결률 유지 | HW-V4 |
| QAS-08 | Flexibility — **Scalability** | 의제·후보 수 증가로 조합이 급증하더라도, 자원 상한 내에서 협상을 완주해야 한다 | 최대 지원 의제 수 (상한 내) | SD-V6 |
| QAS-09 | Reliability — **Recoverability** | 프로세스 종료·네트워크 단절이 발생했을 때, 협상 세션은 정해진 시간 내에 유효한 상태로 복구·재개되어야 한다 | 복구 시간·복구율 | OP-V1, HW-V1 |
| QAS-10 | Reliability — **Fault Tolerance** | 참여자 1명의 무응답·이탈 또는 외부 서비스 장애가 발생하더라도, 잔여 협상은 장애 전파 없이 정의된 결말로 완결되어야 한다 | 전파 없는 완결률 | OP-V2, OP-V5, SA-V3, SD-V4 |
| QAS-11 | Interaction Capability — **Operability** | 사용자가 진행 중 협상에 개입(중단·조건 변경)하면, 정해진 시간 내에 협상에 반영되어야 한다 | 개입 반영 지연 시간 | EU-V4 |
| QAS-12 | Security — **Confidentiality** | 협상 중 외부 전송이 발생하더라도, PII와 선호 원문은 유출되지 않아야 한다 | 유출 0건 | SP-V4, PD-V4 |
| QAS-13 | Maintainability — **Testability** | 동일 조건·Mock 구성으로 재실행하면 동일 결과가 재현되어야 하며, 품질 문제의 원인(모델/프로토콜)을 분리 판정할 수 있어야 한다 | 재현 성공률, 원인 귀속 판정 가능 여부 | QA-V2, QA-V4, OM-V5, SD-V2 |
| QAS-14 | Reliability — **Fault Tolerance** | 모델이 형식 위반·비결정 출력을 생성하더라도, 합의 내용의 정확성과 협상 상태는 오염되지 않고 정의된 처리로 완결되어야 한다 | 오염 0건, 처리 완결률 | OM-V4, OM-V5 |

## 54.2 매핑 판단 근거 (논쟁 여지가 있는 항목)

| 항목 | 판단 | 근거 |
|---|---|---|
| QAS-02 → Functional Correctness (Reliability 아님) | 종결 정합은 신뢰성 문제로 볼 수도 있으나, [`09`](09-Functional-Correctness-정의.md) §9.3이 L4(합의 종결 정합)를 FC의 4계층으로 확정했고 PL 협의(2026-08-10)로 정본화됨 | 기존 결정 준수 |
| QAS-03 → Safety — Operational Constraint (Security 아님) | 위임 범위는 접근 통제라기보다 "운용상 넘지 말아야 할 경계". [`09`](09-Functional-Correctness-정의.md)의 QA-OC-1(운용 제약 준수) 귀속과 일치. 25010:2023의 Safety 특성 신설로 표준 내 매핑 가능 | 기존 결정 준수 |
| QAS-11 → Operability (Time Behaviour 아님) | 측정값은 지연 시간이지만 시나리오의 본질은 사용자 통제력(HITL). 시간은 그 측정 수단 | 분석자 판단 — 팀 선호에 따라 Time Behaviour로 조정 가능 |
| QAS-13의 원인 귀속 | Analysability 성격도 있으나 중심이 재현 가능한 검증 환경이므로 Testability를 주특성으로, 원인 귀속은 응답 측정에 포함 | 분석자 판단 |
| QAS-14 → Fault Tolerance (Security — Integrity 아님) | 모델 오출력은 자체 구성 요소의 결함(fault)이며 위협 주체가 공격자가 아님. 결함에도 의도대로 동작해야 한다는 요구 | 분석자 판단 |

## 54.3 특성 분포 자기 점검

| ISO 25010 특성 | 건수 | 해당 QAS |
|---|---|---|
| Functional Suitability | 2 | QAS-01, 02 |
| Performance Efficiency | 2 | QAS-05, 06 |
| Flexibility | 2 | QAS-07, 08 |
| Reliability | 3 | QAS-09, 10, 14 |
| Security | 2 | QAS-04, 12 |
| Safety | 1 | QAS-03 |
| Interaction Capability | 1 | QAS-11 |
| Maintainability | 1 | QAS-13 |
| Compatibility | 0 | A2A 상호운용은 과제 부여 제약 — [`../06-Constraints.md`](../06-Constraints.md) 소관 |

9개 특성 중 8개 커버. QAS-05(Time Behaviour)와 QAS-08(의제 Scalability)의 VoC 근거는 EU-V7·SD-V6 채택(2026-08-13, [`52`](52-Stakeholder-재편-VoC.md) §52.4)으로 확보되었다.

---

_본 문서는 사용자 지시(2026-08-13)로 작성됨. 근거: [`52`](52-Stakeholder-재편-VoC.md)의 VoC, PL 지시 ⑥([`09`](09-Functional-Correctness-정의.md) 헤더), ISO/IEC 25010:2023 특성 체계._
