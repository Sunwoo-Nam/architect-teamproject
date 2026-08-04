# 2. Stakeholder별 Quality Attributes 도출 (10명 × 10개)

> 분류 체계: **ISO/IEC 25010:2023** Product Quality Model — 표기는 `특성 — 하위특성(영문)`.
>
> **독립 도출 원칙**: 본 문서의 QA는 기존 QA/요구사항 문서(`docs/04-FR.md`, `docs/05-NFR.md`, `docs/07-QAS.md`)를
> 참고하지 않고, **stakeholder VOC([`docs/03-Stakeholder.md`](../03-Stakeholder.md) ·
> [`annex/Stakeholder-원본표.md`](../../annex/Stakeholder-원본표.md))와 과제 설명
> ([`docs/01`](../01-과제-배경-및-목적.md) · [`docs/02`](../02-과제-개요.md) ·
> [`annex/상호작용-시나리오-9종.md`](../../annex/상호작용-시나리오-9종.md))만을 근거**로 도출했다.
>
> **QA 기술 형식**: QA는 기능("~을 제공해야 한다")이 아니라 **정도·수치로 표현 가능한 요구**이므로,
> 모든 항목을 *"~을 최대화해야 한다 / ~을 최소화해야 한다 (측정 지표)"* 형태로 기술한다.
> 구체 임계값은 본 단계에서 정하지 않는다 (측정 지표와 방향만 정의 — 임계값은 실측 기반으로 QAS 단계에서 설정).
>
> 순위(1~10)는 해당 역할 관점의 상대적 중요도이며 분석자 판단이다. 하위특성의 중복 선택은 의도된
> 결과로, 빈도 집계는 [`03-QA-카테고리-정리.md`](03-QA-카테고리-정리.md)에서 수행한다.

---

## S1. End User

핵심 프레임: *"위임해도 안전한가(1~3위) → 위임한 일이 제대로 되는가(4~6위) → 계속 쓸 만한가(7~10위)"*.
프라이버시가 1위인 근거: 01 §1.2.1 — "개인 기기 안에서 처리되는 자율 비서가 아니면 사용자가 마음 놓고 권한을 위임할 수 없음".

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 (VOC·과제) |
|---|---|---|---|
| 1 | Security — Confidentiality | 외부(상대 Agent·서버)로 나가는 개인 정보를 협상에 필요한 최소 범위로 **최소화**해야 한다. 공유 불가로 지정한 정보의 외부 노출은 **0건** | VOC "내 일정·메시지가 외부 서버로 새는 건 절대 싫음", 01 §1.4.1 "최소 단위로 제한" |
| 2 | Interaction Capability — Operability | 사용자 개입(중단·조건 수정·거부)이 반영되기까지의 지연을 **최소화**해야 한다. 사용자 승인 없이 확정되는 실세계 행동은 **0건** | VOC "마지막엔 내가 승인하고 끝낼 수 있어야", 01 §1.4.1 "언제든 협상 중단 가능" |
| 3 | Safety — Operational Constraint | 위임 범위를 초과한 Agent 행동 발생을 **0건**으로 유지해야 한다 | VOC "Agent가 마음대로 결정해 버리는 게 제일 무서움" |
| 4 | Functional Suitability — Functional Correctness | 합의·실행 결과가 사용자 의도·제약과 일치하는 비율을 **최대화**해야 한다. 제약을 위반한 합의는 **0건** | 원본표 "결과 만족도", 01 §1.4.1 "결정 품질 향상" |
| 5 | Reliability — Fault Tolerance | 협상 중 일시 오류가 사용자 인지 없이 자동 처리되어 중단 없이 완료되는 비율을 **최대화**해야 한다 | 시나리오 1 "네트워크·LLM 추론 시간 등 가변 요인에 의해 중단·지연될 수 있는 문제" |
| 6 | Reliability — Recoverability | 중단된 협상 세션의 복구 성공률을 **최대화**하고 세션 유실 건수를 **최소화**해야 한다 | SRE VOC "'갑자기 사라진' 경험은 치명적" (사용자 체감의 원문) |
| 7 | Interaction Capability — Self-descriptiveness | 합의안에 선택 근거 설명이 제공되는 비율을 **최대화**(전 합의안 100%)해야 한다 | VOC "왜 그 안을 골랐는지 한 줄이라도 이해되어야 신뢰가 감" |
| 8 | Performance Efficiency — Time Behaviour | 의도 인지 알림·개입 반영·협상 완료까지의 시간을 각각 **최소화**해야 한다 | 01 §1.4.1 "메시지 왕복 시간이 거의 0에 수렴" (시간 회수가 핵심 가치) |
| 9 | Performance Efficiency — Resource Utilization | 백그라운드 동작의 배터리 소모·발열·메모리 점유를 **최소화**해야 한다 | MX VOC "발열·배터리 소비가 OS 정책 안에 들어와야 사용자가 비활성화하지 않음" |
| 10 | Interaction Capability — User Engagement | 선제 제안의 수락률을 **최대화**하고, 무시·차단되는 제안의 빈도를 **최소화**해야 한다 | VOC *"자율 모드는 꺼 두고 싶음"*, UX VOC "너무 자주 뜨면 침습적" |

> 사후 감사(Accountability)는 End User 체감상 7위 Self-descriptiveness와 겹쳐 제외하고 S2·S7이 대변한다 (분석자 판단).

---

## S2. Counterparty User

핵심 프레임: *"내 정보가 최소로 노출되고, 상대 Agent가 일방적으로 밀어붙이지 못하며, 사후 검증이 가능한가."*

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 (VOC·과제) |
|---|---|---|---|
| 1 | Security — Confidentiality | 상대측에 공유되는 내 일정·선호 정보의 양을 협상 필요 최소로 **최소화**해야 한다 | VOC "일정을 통째로 보여주고 싶지 않음. 필요한 만큼만" |
| 2 | Interaction Capability — Operability | 내 거절·조건 변경이 협상에 반영되기까지의 지연을 **최소화**해야 한다 | VOC *"거절하거나 조건을 바꾸겠다고 할 때 즉시 반영"* |
| 3 | Safety — Operational Constraint | 내 동의 없이 일방적으로 확정되는 합의를 **0건**으로 유지해야 한다 | VOC "일방적으로 밀어붙이는 일은 없어야 함" |
| 4 | Security — Authenticity | 위장(스푸핑) Agent와의 협상 성립을 **0건**으로 유지해야 한다 (상대 신원 검증률 100%) | VOC "협상 과정 신뢰성" (원본표) |
| 5 | Security — Integrity | 협상 메시지의 변조가 탐지되지 않고 통과하는 건수를 **0건**으로 유지해야 한다 | Security 담당 VOC "변조도 감지·차단되어야 함" |
| 6 | Security — Accountability | 협상 과정 기록의 누락을 **0건**으로 하여 사후 조회 가능률 **100%**를 유지해야 한다 | VOC "어떻게 흘러갔는지 사후에 확인할 수 있어야 마음이 놓임" |
| 7 | Functional Suitability — Functional Correctness | 내 쪽 조건·제약이 합의안에 정확히 반영되는 비율을 **최대화**해야 한다 (양방향 정확성) | VOC "협상 과정 신뢰성" |
| 8 | Interaction Capability — Self-descriptiveness | 상대 제안의 근거·협상 경과를 이해할 수 있게 제공되는 비율을 **최대화**해야 한다 | VOC "어떻게 흘러갔는지" |
| 9 | Security — Non-repudiation | 합의 내용에 대한 증빙 보존율 **100%**를 유지해 사후 부인 가능성을 **최소화**해야 한다 | Legal VOC "책임 소재가 기록되어야" (분쟁 관점 적용) |
| 10 | Interaction Capability — User Error Protection | 조작 실수로 의도치 않게 확정되는 건수를 **최소화**해야 한다 | UX VOC "승인·거절 최소 단계"의 이면 (분석자 추론) |

---

## S3. Service Proxy Agent Owner

핵심 프레임: *"검증된 요청만, 우리 정책 그대로, 기존 시스템 위에서."* — B2C 시나리오 5·6·7·9의 카운터파트.

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 (VOC·과제) |
|---|---|---|---|
| 1 | Security — Authenticity | 신원 미검증 Agent 요청의 수신을 **0건**으로 유지해야 한다 | VOC "인증된 요청만 받고 싶음" |
| 2 | Security — Resistance | 무차별·악성 자동화 요청의 차단율을 **최대화**하여 정상 운영 중단 시간을 **최소화**해야 한다 | VOC "봇이 무차별로 들어오면 운영이 마비됨" |
| 3 | Compatibility — Interoperability | 기존 예약 시스템과의 연동에 필요한 변경·개발 비용을 **최소화**해야 한다 | VOC *"우리 시스템을 갈아엎으라는 요구는 받기 어려움"* |
| 4 | Functional Suitability — Functional Correctness | 가격·시간·노쇼 페널티 등 운영 정책의 오반영 건수를 **0건**으로 유지해야 한다 | VOC "우리 가게의 정책이 그대로 반영되어야" |
| 5 | Security — Non-repudiation | 예약 부인으로 인한 분쟁 건수를 **최소화**해야 한다 (예약 증빙 보존율 100%) | VOC "실제 결제와 방문으로 이어져야", 시나리오 6 "노쇼 방지" |
| 6 | Functional Suitability — Functional Appropriateness | Agent 경유 예약의 실제 방문·결제 전환율을 **최대화**해야 한다 | 원본표 "예약 전환율" |
| 7 | Security — Accountability | 예약 요청의 주체·시각·내용 추적 가능률 **100%**를 유지해야 한다 | 시나리오 5 "실시간 동기화 및 신뢰성 확보" |
| 8 | Reliability — Availability | Agent 예약 채널의 가동률을 **최대화**해야 한다 (영업시간 기준) | 원본표 "예약 전환율"에서 도출 (분석자 추론) |
| 9 | Performance Efficiency — Capacity | 동시 수용 가능한 예약·조회 요청 수를 **최대화**해야 한다 | 시나리오 6·9 다자·동시다발 조율 (분석자 추론) |
| 10 | Compatibility — Co-existence | 연동으로 인한 기존 POS·예약 시스템의 성능 저하를 **최소화**해야 한다 | 원본표 "기존 시스템과의 연동" |

---

## S4. Project Leader

핵심 프레임: *"검증 가치가 명확하고, 데모에서 차별화가 체감되며, 상품화로 이어질 수 있는가."*
**1위는 PL 본인의 명시 지시(2026-08-04)**: "Functional Correctness가 가장 중요한 QA" — 정의는 [`05-Functional-Correctness-정의.md`](05-Functional-Correctness-정의.md).

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 (VOC·과제) |
|---|---|---|---|
| 1 | Functional Suitability — Functional Correctness | 협상·실행 결과가 사용자 의도에 비추어 "맞는" 비율을 **최대화**해야 한다. 틀린 결과는 다른 모든 품질을 무의미하게 함 | **PL 명시 지시 (2026-08-04)** |
| 2 | Functional Suitability — Functional Appropriateness | 선정 시나리오가 실현하는 사용자 가치(절감된 조율 시간 등)를 **최대화**해야 한다 | VOC "외부에 자랑할 수 있는 새로운 사용자 가치" |
| 3 | Functional Suitability — Functional Completeness | 차별화 핵심 시나리오의 E2E(감지→협상→합의→실행) 완결 구현률을 **최대화**해야 한다 | VOC "어느 것이 차별화의 핵심인지부터 정해야" |
| 4 | Interaction Capability — User Engagement | 선제 제안의 수락률과 사용자 체감 만족도를 **최대화**해야 한다 | VOC "사용자가 정말 다르게 느끼는 UX" |
| 5 | Maintainability — Testability | 3대 가설 검증 실험의 재현 성공률을 **최대화**해야 한다 (동일 조건 재실험 가능률 100%) | VOC *"비용 대비 검증 가치가 명확해야"*, 품질검증팀 VOC |
| 6 | Performance Efficiency — Time Behaviour | 데모·실사용에서 사용자가 기다리는 체감 시간을 **최소화**해야 한다 | VOC "UX 차별화" |
| 7 | Reliability — Faultlessness | 시연·평가 중 크래시·미처리 예외 발생을 **0건**으로 유지해야 한다 | VOC "시나리오 실현성" |
| 8 | Performance Efficiency — Resource Utilization | 양산 단말 자원 예산 초과 발생을 **0건**으로 유지해야 한다 | 상품화 담당 VOC *"양산 단말의 자원·OS 정책이 가장 큰 의사결정 변수"* |
| 9 | Flexibility — Scalability | 참여자 수·도메인 확장에 필요한 추가 개발·자원 비용을 **최소화**해야 한다 | VOC "시장성", 시나리오 2·6 |
| 10 | Interaction Capability — Appropriateness Recognizability | 신규 사용자가 시스템 가치를 인지하기까지의 시간을 **최소화**해야 한다 | VOC "외부에 자랑할 수 있는" (분석자 추론) |

---

## S5. Architect

핵심 프레임: *"모듈 경계가 명확하고, 확장이 국소적이며, 변경 영향이 추적되고, 전체 흐름이 재현 가능한가."*

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 (VOC·과제) |
|---|---|---|---|
| 1 | Maintainability — Modularity | 모듈 간 결합도를 **최소화**하고 인터페이스 규약 위반을 **0건**으로 유지해야 한다 | VOC "다섯 모듈 사이의 경계가 흐릿하면 운영 단계로 못 감" |
| 2 | Maintainability — Modifiability | Agent 종류·도메인 추가 시 기존 코드 수정량을 **최소화**해야 한다 | VOC "기존 코드에 손을 거의 안 대고도 확장" |
| 3 | Maintainability — Testability | Mock 상대 Agent만으로 재현 가능한 협상 흐름의 비율을 **최대화**(100%)해야 한다 | VOC *"Mock으로 협상 흐름 전체를 재현할 수 있어야"* |
| 4 | Maintainability — Analysability | 변경 영향 범위를 파악하는 데 걸리는 시간을 **최소화**해야 한다 | VOC "변경 영향이 추적 가능해야" |
| 5 | Flexibility — Adaptability | 신규 시나리오·도메인 적용 시 구조 변경량을 **최소화**해야 한다 | 원본표 "확장성" |
| 6 | Flexibility — Scalability | 협상 참여자 수 증가에 따른 자원·지연 증가를 선형 이내로 **최소화**해야 한다 | 시나리오 2 "참여자가 늘수록 합의 시간이 기하급수적으로 늘어나는 문제" |
| 7 | Compatibility — Interoperability | A2A 표준 규격 위반을 **0건**으로 유지해야 한다 | 02 §2.2 "A2A 프로토콜", 01 §1.2.2(3) 표준 선점 전략 |
| 8 | Flexibility — Replaceability | LLM 모델 교체 시 수정 범위를 추상화 계층 내부로 **최소화**해야 한다 | AI/ML VOC "모델을 빠르게 교체할 수 있어야" |
| 9 | Maintainability — Reusability | 시나리오 9종 간 공통 로직의 재사용률을 **최대화**해야 한다 | VOC "모듈화"에서 도출 (분석자 추론) |
| 10 | Reliability — Fault Tolerance | 단일 Agent 장애의 전파 범위를 **최소화**해야 한다 (격리 경계 설계) | SRE VOC "한 Agent의 장애가 전체로 번지면 안 됨" |

---

## S6. Multi-agent Framework Developer

핵심 프레임: *"격리·표준화·재현 — 코드를 단순하게 짤 수 있는 구조적 전제."*

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 (VOC·과제) |
|---|---|---|---|
| 1 | Maintainability — Testability | 실패 케이스의 재현 성공률을 **최대화**해야 한다 (LLM 비결정성 하에서도) | VOC *"재현이 안 되면 손을 못 댐"* |
| 2 | Maintainability — Analysability | 결함 원인 특정까지의 시간을 **최소화**해야 한다 (실행 추적 로그 커버리지 100%) | VOC *"디버깅이 가능한 추적 로그가 필요함"* |
| 3 | Safety — Safe Integration | 동적 생성된 Agent/Tool의 sandbox 이탈 행위를 **0건**으로 유지해야 한다 | VOC *"sandbox 안에서 안전하게 격리 실행되어야"* |
| 4 | Reliability — Fault Tolerance | 실패한 LLM·Tool 호출의 자동 복구(재시도·대체) 성공률을 **최대화**해야 한다 | VOC *"재시도·대체·escalation 정책이 명확히"* |
| 5 | Reliability — Recoverability | 중단 세션의 저장·복원 성공률을 **최대화**해야 한다 | 시나리오 1 "협상 중단 문제" + 논리적 롤백 설계 포인트 |
| 6 | Maintainability — Modularity | 메시지 형식·lifecycle 상태 전이의 표준 위반을 **0건**으로 유지해야 한다 | VOC *"메시지 형식과 lifecycle 상태 전이가 표준화되어야"* |
| 7 | Safety — Fail Safe | 이상 상황(무응답·타임아웃·합의 불가)에서 불확정 상태로 남는 세션을 **0건**으로 유지해야 한다 | 시나리오 2 "무한 루프 방지", 시나리오 1 "논리적 롤백" |
| 8 | Compatibility — Interoperability | 프로토콜 적합성 검사 통과율 **100%**를 유지해야 한다 | 02 §2.2 A2A 프로토콜 준수 |
| 9 | Maintainability — Modifiability | 협상 전략·정책 변경 시 코드 수정 범위를 **최소화**해야 한다 | VOC "코드를 단순하게 짤 수 있어야" (분석자 추론) |
| 10 | Maintainability — Reusability | 4대 상호작용 케이스 간 공통 기반 코드의 비율을 **최대화**해야 한다 | 02 §2.5.1 상호작용 범위 (분석자 추론) |

---

## S7. Security / Privacy 담당 (개인정보 보안 담당자 병합)

핵심 프레임: *"최소 권한·최소 노출·완전한 감사 — 단 한 건의 초과 행동도 없이."*

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 (VOC·과제) |
|---|---|---|---|
| 1 | Security — Confidentiality | 민감 데이터의 외부 유출을 **0건**, 서버로 전송되는 데이터 내 PII를 **0건**으로 유지해야 한다 | VOC "민감 데이터는 온디바이스에서. 외부로 보낼 때는 PII가 빠져야" |
| 2 | Safety — Operational Constraint | 위임 권한 범위를 초과한 Agent 행동을 **0건**으로 유지해야 한다 | VOC "단 한 건의 초과 행동도 용납 불가" |
| 3 | Security — Integrity | 메시지 변조가 미탐지로 통과하는 건수를 **0건**으로 유지해야 한다 | VOC "암호화되어야 하고 변조도 감지·차단" |
| 4 | Security — Accountability | 감사 대상 이벤트의 기록 누락을 **0건**(기록률 100%)으로 유지해야 한다 | VOC "누가 어떤 권한으로 무엇을 했는지 사후 감사" |
| 5 | Security — Authenticity | 미인증 Agent의 시스템 진입을 **0건**으로 유지해야 한다 (동적 생성 Agent 포함) | VOC *"동적 생성된 Agent도 동일한 보안 정책 검사 경로"* |
| 6 | Security — Non-repudiation | 권한 위임·합의·실행 행위의 증빙 보존율 **100%**를 유지해야 한다 | Legal VOC "책임 소재가 약관과 시스템에 명확히 기록" |
| 7 | Security — Resistance | 알려진 공격 패턴(스푸핑·재전송·주입)의 차단율을 **최대화**해야 한다 | 원본표 "인증/인가" — 2023 신설 하위특성 매핑 (분석자 판단) |
| 8 | Safety — Risk Identification | 민감 사용자 그룹(고령자·미성년자) 시나리오의 위험 식별 커버리지를 **최대화**해야 한다 | VOC *"민감 사용자 그룹에 별도 보호 장치"*, 시나리오 8 |
| 9 | Maintainability — Analysability | 감사 로그의 privacy-safe 분석 가능률을 **최대화**해야 한다 (원문 노출 0건) | SRE VOC "privacy-safe 형태로 저장되어야 들여다볼 수 있음" |
| 10 | Functional Suitability — Functional Correctness | 정책 기반 필터링의 오류(잘못 공유·잘못 차단)를 **최소화**해야 한다 | VOC "공유 데이터는 요약·추상화된 형태여야" (필터링의 정확성) |

---

## S8. AI/ML Engineer

핵심 프레임: *"Intent 품질이 전체의 상한 — 온디바이스에서 돌아가고, 빠르게 교체·개선 가능해야."*

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 (VOC·과제) |
|---|---|---|---|
| 1 | Functional Suitability — Functional Correctness | Intent 분류 정확도를 **최대화**하고 오탐율을 **최소화**해야 한다 (confidence 안정) | VOC "Intent 분류 품질이 떨어지면 뒤의 모든 Agent가 헛수고" |
| 2 | Performance Efficiency — Time Behaviour | 온디바이스 추론 1회의 지연을 **최소화**해야 한다 | VOC "on-device 추론 가능성" (원본표) |
| 3 | Performance Efficiency — Resource Utilization | 모델의 메모리·CPU·NPU 점유를 **최소화**해야 한다 | VOC "메모리·CPU·NPU 사용량이 OS 정책 안에 들어가야" |
| 4 | Flexibility — Replaceability | 온디바이스 LLM 교체에 걸리는 기간·수정 범위를 **최소화**해야 한다 | VOC "다른 모델로 빠르게 교체. 시장 변화 속도가 너무 빠름" |
| 5 | Flexibility — Adaptability | 사용자 피드백·협상 이력이 모델 개선에 반영되는 주기를 **최소화**해야 한다 (closed-loop) | VOC "closed-loop가 있어야 self-improving이 됨" |
| 6 | Maintainability — Testability | 모델 품질 평가 실험의 재현율을 **최대화**해야 한다 | 품질검증팀 VOC *"같은 실험을 반복할 수 있어야"* |
| 7 | Maintainability — Analysability | 오분류·품질 저하(드리프트)의 원인 분석 가능률을 **최대화**해야 한다 | VOC "confidence score가 안정되어야" (분석자 추론) |
| 8 | Functional Suitability — Functional Appropriateness | 태스크 복잡도별 최적 모델 변종(Compact/Balanced/Supreme) 매칭률을 **최대화**해야 한다 | 01 §1.1.4 Galaxy S26 3종 변종 |
| 9 | Reliability — Faultlessness | 추론 실패·타임아웃 발생률을 **최소화**해야 한다 | VOC "정확도와 confidence score가 안정되어야" |
| 10 | Performance Efficiency — Capacity | 동시 추론 요청(IDS·Meta Agent·Sub-Agent)의 수용량을 **최대화**해야 한다 | 02 §2.3 — 3개 계층이 온디바이스 LLM 공유 |

---

## S9. 운영 / SRE

핵심 프레임: *"복구 가능하고, 격리되어 있고, 관찰 가능하고, 로그가 안전한가."*

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 (VOC·과제) |
|---|---|---|---|
| 1 | Reliability — Recoverability | 장애 후 세션 복구 성공률을 **최대화**하고 복구 소요 시간을 **최소화**해야 한다 | VOC "진행 중이던 협상 세션은 복구 가능해야" |
| 2 | Reliability — Fault Tolerance | 단일 Agent 장애의 전파를 차단하는 격리 성공률을 **최대화**해야 한다 | VOC "한 Agent의 장애가 시스템 전체로 번지면 안 됨" |
| 3 | Maintainability — Analysability | 장애 원인 특정까지의 시간(MTTD)을 **최소화**해야 한다 (실시간 관측 커버리지 최대화) | VOC "실행 상태를 실시간으로 관찰할 수 있어야" |
| 4 | Reliability — Availability | 서비스 가동률을 **최대화**하고 복구 시간(MTTR)을 **최소화**해야 한다 | Cloud VOC *"서버 측 장애가 단말 측 협상 흐름을 멈추게 하지 않아야"* |
| 5 | Security — Accountability | 운영 분석에 필요한 이벤트 기록 누락을 **0건**으로 유지해야 한다 | 원본표 "로그 추적성" |
| 6 | Security — Confidentiality | 로그 내 개인정보 원문 노출을 **0건**으로 유지해야 한다 | VOC "로그가 privacy-safe 형태로 저장되어야" |
| 7 | Reliability — Faultlessness | 동일 원인의 반복 장애 발생률을 **최소화**해야 한다 | 원본표 "장애 복구" (분석자 추론) |
| 8 | Flexibility — Scalability | 사용자·세션 수 증가 대비 운영 부하 증가를 **최소화**해야 한다 | 01 §1.1.4 "3억 대 배포" 맥락 (분석자 추론) |
| 9 | Safety — Hazard Warning | 위험 상황(Agent 폭주·비정상 패턴)의 경보 지연과 미탐지율을 **최소화**해야 한다 | VOC "모니터링" + 시나리오 2 "무한 루프·메시지 폭주" |
| 10 | Flexibility — Installability | 배포·업데이트·롤백의 실패율을 **최소화**해야 한다 | 01 §1.1.4 대규모 단말군 전제 (분석자 추론) |

---

## S10. MX H/W 담당자

핵심 프레임: *"OS 정책과 물리 한계 안에서 — 아니면 OS와 사용자가 우리를 꺼 버린다."*

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 (VOC·과제) |
|---|---|---|---|
| 1 | Performance Efficiency — Resource Utilization | CPU·NPU·메모리·배터리 사용을 **최소화**하고 정의된 상한 초과를 **0건**으로 유지해야 한다 | VOC *"발열·배터리 소비가 OS 정책 안에"*, *"메모리 점유에 상한"* |
| 2 | Compatibility — Co-existence | 포그라운드 앱 성능 저하와 OS(Doze·OOM Killer)에 의한 강제 종료 빈도를 **최소화**해야 한다 | VOC *"Doze·OOM Killer를 정상적으로 통과해야. 안 그러면 OS가 우리를 끝장냄"* |
| 3 | Performance Efficiency — Capacity | 동시 실행 Agent 수의 상한 준수 위반을 **0건**으로 유지해야 한다 | VOC *"동시에 떠 있는 Agent 수와 메모리 점유에 상한"* |
| 4 | Performance Efficiency — Time Behaviour | 발열 제약(스로틀링) 하에서의 추론 시간을 **최소화**해야 한다 | VOC "발열" + 온디바이스 LLM 전제 (02 §2.3) |
| 5 | Safety — Operational Constraint | 발열·전력의 안전 한계 초과를 **0건**으로 유지해야 한다 (초과 전 자체 동작 제한) | VOC "발열·배터리" — Safety 매핑 (분석자 판단) |
| 6 | Reliability — Recoverability | OS에 의한 프로세스 종료 후 상태 복원 성공률을 **최대화**해야 한다 | VOC "Doze·OOM" + 세션 복구 필요성 |
| 7 | Flexibility — Adaptability | 단말 등급별 자원 프로파일에 맞는 동작 조정 적합률을 **최대화**해야 한다 | 01 §1.1.4 Compact/Balanced/Supreme |
| 8 | Reliability — Fault Tolerance | 자원 고갈 시 크래시 대신 단계적 성능 저하로 전환되는 비율을 **최대화**해야 한다 | VOC "메모리 점유 상한" (분석자 추론) |
| 9 | Flexibility — Scalability | 협상 참여자 1인 추가당 자원 증가분을 **최소화**해야 한다 (선형 이내) | 시나리오 2 N-party + 자원 상한 요구의 결합 (분석자 추론) |
| 10 | Flexibility — Installability | 단말 모델별 설치·업데이트 실패율을 **최소화**해야 한다 | Galaxy 단말 스펙트럼 (분석자 추론) |

---

## 집계 예고

10명 × 10개 = **100개 항목**, 고유 하위특성 기준 **37종**.
카테고리별 취합·빈도 분석: [`03-QA-카테고리-정리.md`](03-QA-카테고리-정리.md)
전수 평가: [`04-QA-중요도-난이도-평가.md`](04-QA-중요도-난이도-평가.md) · 빈도 상위 집중 평가: [`09-핵심-QA-중요도-난이도-평가.md`](09-핵심-QA-중요도-난이도-평가.md)
