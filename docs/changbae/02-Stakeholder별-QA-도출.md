# 2. Stakeholder별 Quality Attributes 도출 (10명 × 10개) — 다자간 협상 범위

> 분류 체계: **ISO/IEC 25010:2023** Product Quality Model — 표기는 `특성 — 하위특성(영문)`.
>
> **범위**: 다자간 협상(N-party Negotiation) — NegMAS 기반 효용·threshold 교대 제안 프로토콜의 다자 확장 ([`01`](01-Stakeholder-도출.md) 참조).
>
> **독립 도출 원칙**: 기존 QA/요구사항 문서(`docs/04-FR.md`, `docs/05-NFR.md`, `docs/07-QAS.md`)를 참고하지 않고,
> stakeholder VOC([`docs/03-Stakeholder.md`](../03-Stakeholder.md) · [`annex/Stakeholder-원본표.md`](../../annex/Stakeholder-원본표.md))와
> 과제 설명([`docs/01`](../01-과제-배경-및-목적.md) · [`docs/02`](../02-과제-개요.md) ·
> [`annex/상호작용-시나리오-9종.md`](../../annex/상호작용-시나리오-9종.md))만을 근거로 한다.
> 원본 VOC는 1:1 협상 어휘로 쓰였으므로, 다자 상황으로의 확장 해석은 "분석자 확장"으로 표시한다.
>
> **QA 기술 형식**: 모든 항목을 *"~을 최대화/최소화해야 한다 (측정 지표)"* 형태로 기술한다.
> 구체 임계값은 정하지 않는다 (지표·방향만 정의, 임계값은 실측 기반으로 QAS 단계에서 설정).

---

## S1. 협상 개시 사용자 (Initiator User)

핵심 프레임: *"그룹 협상을 맡겨도 안전한가 → 맡긴 합의가 제대로 되는가 → 계속 쓸 만한가."*

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 |
|---|---|---|---|
| 1 | Security — Confidentiality | 그룹 참여자들에게 공개되는 내 일정·선호 정보를 합의에 필요한 최소로 **최소화**해야 한다. 공유 불가 지정 정보의 노출 **0건** | VOC "내 일정·메시지가 외부로 새는 건 절대 싫음" |
| 2 | Interaction Capability — Operability | 진행 중 그룹 협상에 대한 내 개입(중단·조건 수정·거부)의 반영 지연을 **최소화**해야 한다. 내 승인 없는 확정 **0건** | VOC "마지막엔 내가 승인하고 끝낼 수 있어야" |
| 3 | Safety — Operational Constraint | 위임 범위(시간대·예산·공유 정보)를 초과한 Agent 행동을 **0건**으로 유지해야 한다. threshold를 넘어도 위임 범위 밖이면 수락 불가 | VOC "Agent가 마음대로 결정해 버리는 게 제일 무서움" |
| 4 | Functional Suitability — Functional Correctness | 그룹 합의안이 내 의도·제약·선호와 일치하는 비율을 **최대화**해야 한다 (내 제약 위반 합의 0건) | 원본표 "결과 만족도", 01 §1.4.1 "결정 품질" |
| 5 | Reliability — Fault Tolerance | 일부 참여자의 일시 오류·지연에도 그룹 협상이 중단 없이 완료되는 비율을 **최대화**해야 한다 | 시나리오 1·2 "네트워크·LLM 추론 시간 등 가변 요인" (다자 확장은 분석자 확장) |
| 6 | Reliability — Recoverability | 중단된 그룹 세션의 복구 성공률을 **최대화**하고 유실을 **최소화**해야 한다 | SRE VOC "'갑자기 사라진' 경험은 치명적" |
| 7 | Interaction Capability — Self-descriptiveness | 합의안에 "왜 이 안이 전원에게 선택됐는지" 설명이 제공되는 비율 **100%**를 유지해야 한다 | VOC "왜 그 안을 골랐는지 한 줄이라도" |
| 8 | Performance Efficiency — Time Behaviour | 그룹 합의 도달까지의 총 시간과 의도 인지·개입 반영 시간을 **최소화**해야 한다 | 01 §1.4.1 "시간 회수", 시나리오 2 "합의 지연 문제" |
| 9 | Performance Efficiency — Resource Utilization | 백그라운드 협상의 배터리·발열·메모리 사용을 **최소화**해야 한다 | MX VOC "OS 정책 안에 들어와야 사용자가 비활성화하지 않음" |
| 10 | Interaction Capability — User Engagement | 그룹 조율 의도에 대한 선제 제안의 수락률을 **최대화**하고 무시·차단 빈도를 **최소화**해야 한다 | UX VOC "너무 자주 뜨면 침습적" |

## S2. 협상 참여 사용자 (Participant Users)

핵심 프레임: *"N-1명 속에서 내 정보는 최소로 노출되고, 나 없이 결정되지 않으며, 내 조건도 동등하게 반영되는가."*

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 |
|---|---|---|---|
| 1 | Security — Confidentiality | 다른 참여자들에게 노출되는 내 일정·선호를 **최소화**해야 한다 — 제안·수락 패턴에서 내 선호가 역추론되는 정보량 포함 (역추론은 분석자 확장) | VOC "일정을 통째로 보여주고 싶지 않음" |
| 2 | Functional Suitability — Functional Correctness | 그룹 합의안에 내 조건·제약이 다른 참여자와 **동등하게** 반영되는 비율을 **최대화**해야 한다 (특정 참여자 일방 유리 편향 최소화) | VOC "협상 과정 신뢰성" — 다자 공정성은 분석자 확장 |
| 3 | Interaction Capability — Operability | 내 거절·조건 변경이 그룹 협상에 반영되는 지연을 **최소화**해야 한다 | VOC *"거절·조건 변경 시 즉시 반영"* |
| 4 | Safety — Operational Constraint | 내 동의 없이 그룹 다수결 등으로 일방 확정되는 합의를 **0건**으로 유지해야 한다 | VOC "일방적으로 밀어붙이는 일은 없어야" |
| 5 | Security — Authenticity | 그룹 내 위장(스푸핑) 참여자와의 협상 성립을 **0건**으로 유지해야 한다 (전 참여자 신원 검증률 100%) | VOC "협상 과정 신뢰성" |
| 6 | Security — Integrity | 협상 메시지(제안·수락·거절)의 변조 미탐지 통과를 **0건**으로 유지해야 한다 | Security 담당 VOC "변조도 감지·차단" |
| 7 | Security — Accountability | 그룹 협상 과정 기록의 누락 **0건**, 사후 조회 가능률 **100%**를 유지해야 한다 | VOC "어떻게 흘러갔는지 사후 확인" |
| 8 | Interaction Capability — Self-descriptiveness | 라운드별 제안·수락 경과를 이해 가능하게 제공하는 비율을 **최대화**해야 한다 | VOC "어떻게 흘러갔는지" |
| 9 | Security — Non-repudiation | 각 참여자의 수락·거절 행위에 대한 증빙 보존율 **100%**를 유지해야 한다 ("나는 동의한 적 없다" 분쟁 방지) | Legal VOC "책임 소재 기록" (다자 적용은 분석자 확장) |
| 10 | Interaction Capability — User Error Protection | 조작 실수로 의도치 않게 그룹 합의가 확정되는 건수를 **최소화**해야 한다 | UX VOC "승인·거절 최소 단계"의 이면 (분석자 추론) |

## S3. Project Leader

핵심 프레임: *"다자 협상 가설이 정량으로 검증되고, 데모에서 차별화가 체감되는가."*
**1위는 PL 명시 지시(2026-08-04)** — 정의는 [`05-Functional-Correctness-정의.md`](05-Functional-Correctness-정의.md).

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 |
|---|---|---|---|
| 1 | Functional Suitability — Functional Correctness | 그룹 협상·실행 결과가 참여자들 의도에 비추어 "맞는" 비율을 **최대화**해야 한다 | **PL 명시 지시 (2026-08-04)** |
| 2 | Functional Suitability — Functional Appropriateness | 다자 시나리오가 실현하는 사용자 가치(그룹 조율에 쓰던 메시지 왕복·시간의 절감)를 **최대화**해야 한다 | VOC "새로운 사용자 가치", 01 §1.2.1 "5~10번 왕복" |
| 3 | Functional Suitability — Functional Completeness | 다자 시나리오의 E2E(의도 감지→협상→합의→실행) 완결 구현률을 **최대화**해야 한다 | VOC "차별화의 핵심부터" |
| 4 | Flexibility — Scalability | 검증된 참여자 수 범위(N)를 **최대화**하고, N 증가에 따른 성능 저하를 **최소화**해야 한다 | 시나리오 2 (포커스 주제의 검증 목표) |
| 5 | Maintainability — Testability | 다자 가설 검증 실험의 재현 성공률을 **최대화**해야 한다 | VOC *"비용 대비 검증 가치"* |
| 6 | Performance Efficiency — Time Behaviour | 데모·실사용에서 그룹 합의까지의 체감 대기 시간을 **최소화**해야 한다 | VOC "UX 차별화" |
| 7 | Reliability — Faultlessness | 시연·평가 중 크래시·미처리 예외를 **0건**으로 유지해야 한다 | VOC "시나리오 실현성" |
| 8 | Performance Efficiency — Resource Utilization | 양산 단말 자원 예산 초과를 **0건**으로 유지해야 한다 | 상품화 담당 VOC *"양산 단말 자원·OS 정책"* |
| 9 | Interaction Capability — User Engagement | 그룹 조율 선제 제안의 수락률·체감 만족도를 **최대화**해야 한다 | VOC "정말 다르게 느끼는 UX" |
| 10 | Interaction Capability — Appropriateness Recognizability | 처음 보는 사람이 다자 자율 협상의 가치를 인지하기까지의 시간을 **최소화**해야 한다 | VOC "외부에 자랑할 수 있는" (분석자 추론) |

## S4. Architect

핵심 프레임: *"다자 프로토콜 구조가 N에 견디고, 전략이 교체 가능하고, 전체가 재현 가능한가."*

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 |
|---|---|---|---|
| 1 | Maintainability — Modularity | 협상 코어(프로토콜)·전략(Ufun·양보)·통신·UI 모듈 간 결합도를 **최소화**하고 인터페이스 위반 **0건**을 유지해야 한다 | VOC "모듈 사이의 경계" |
| 2 | Flexibility — Scalability | 참여자 수 증가에 따른 합의 시간·자원·메시지 수 증가를 설계 목표 함수(선형 등) 이내로 **최소화**해야 한다 | 시나리오 2 "기하급수적 합의 지연 문제" |
| 3 | Maintainability — Testability | Mock 참여자만으로 재현 가능한 다자 협상 흐름의 비율 **100%**를 유지해야 한다 | VOC *"Mock으로 협상 흐름 전체 재현"* |
| 4 | Maintainability — Modifiability | 정족수 규칙·양보 전략·제안 토폴로지 변경 시 코드 수정 범위를 **최소화**해야 한다 (설정·플러그인 수준) | VOC "손을 거의 안 대고도 확장" |
| 5 | Maintainability — Analysability | 협상 결과에 대한 변경·설계 결정의 영향 파악 시간을 **최소화**해야 한다 | VOC "변경 영향 추적" |
| 6 | Flexibility — Adaptability | 새 도메인(일정→장소→예산 등 의제 유형) 적용 시 구조 변경을 **최소화**해야 한다 | 원본표 "확장성" |
| 7 | Compatibility — Interoperability | A2A 표준 규격 위반 **0건**을 유지해야 한다 (다자 브로드캐스트 확장 포함) | 02 §2.2 A2A, 01 §1.2.2(3) 표준 선점 |
| 8 | Flexibility — Replaceability | LLM·협상 전략 구현의 교체 시 수정 범위를 추상화 계층 내부로 **최소화**해야 한다 | S6 VOC "모델 교체" |
| 9 | Maintainability — Reusability | 2자 협상과 다자 협상이 공유하는 공통 코어 코드의 비율을 **최대화**해야 한다 | 포커스: 2자 프로토콜의 다자 확장 (분석자 추론) |
| 10 | Reliability — Fault Tolerance | 단일 참여자 장애의 전파 범위를 **최소화**해야 한다 (격리 경계의 구조화) | SRE VOC "한 Agent 장애가 전체로 번지면 안 됨" |

## S5. Multi-agent Framework Developer

핵심 프레임: *"N명 비동기 라운드를 표준화된 상태 기계로 — 재현·격리·복구 가능하게."*

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 |
|---|---|---|---|
| 1 | Maintainability — Testability | 다자 실패 케이스(이탈·교착·부분 응답)의 재현 성공률을 **최대화**해야 한다 | VOC *"재현이 안 되면 손을 못 댐"* |
| 2 | Maintainability — Analysability | 결함 원인 특정 시간을 **최소화**해야 한다 (라운드·참여자·제안 단위 추적 로그 커버리지 100%) | VOC *"디버깅 가능한 추적 로그"* |
| 3 | Safety — Fail Safe | 이상 상황(무응답·이탈·타임아웃·합의 불가)에서 불확정 상태로 남는 그룹 세션을 **0건**으로 유지해야 한다 | 시나리오 2 "무한 루프·교착 방지", 시나리오 1 "논리적 롤백" |
| 4 | Reliability — Fault Tolerance | 실패한 LLM·메시지 처리의 자동 복구(재시도·대체) 성공률을 **최대화**해야 한다 | VOC *"재시도·대체·escalation 정책"* |
| 5 | Reliability — Recoverability | 중단된 다자 세션의 저장·복원·**재동기화** 성공률을 **최대화**해야 한다 | 시나리오 1 중단 문제 + 시나리오 2 "데이터 일관성" |
| 6 | Maintainability — Modularity | 협상 메시지 형식·상태 전이의 표준 위반 **0건**을 유지해야 한다 | VOC *"메시지 형식·lifecycle 표준화"* |
| 7 | Compatibility — Interoperability | 프로토콜 적합성 검사 통과율 **100%**를 유지해야 한다 | 02 §2.2 A2A 준수 |
| 8 | Safety — Safe Integration | 동적 생성된 협상 Agent의 sandbox 이탈 행위를 **0건**으로 유지해야 한다 | VOC *"sandbox 격리 실행"* — 범위 축소로 우선순위 하향 (분석자 판단) |
| 9 | Maintainability — Modifiability | 라운드 규칙·타임아웃 정책 변경 시 수정 범위를 **최소화**해야 한다 | VOC "코드를 단순하게" (분석자 추론) |
| 10 | Maintainability — Reusability | 2자·다자 케이스 간 공통 기반 코드 비율을 **최대화**해야 한다 | 포커스: 2자 → 다자 확장 (분석자 추론) |

## S6. 협상 알고리즘 담당 (Negotiation/ML Engineer)

핵심 프레임: *"Ufun이 선호를 맞게 반영하고, threshold·양보·집계가 수렴하며, 온디바이스에서 돌아가는가."*

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 |
|---|---|---|---|
| 1 | Functional Suitability — Functional Correctness | Intent 분류 정확도와 **Ufun의 선호 반영 정확도**(효용 순위와 사용자 실제 선호 순위의 일치율)를 **최대화**해야 한다 | VOC "Intent 품질이 떨어지면 전부 헛수고" + 포커스 알고리즘의 "자기 기준 점수" (분석자 확장) |
| 2 | Flexibility — Scalability | 참여자 수 증가에 따른 합의 수렴 라운드 수의 증가를 **최소화**해야 한다 (수렴 실패율 최소화) | 시나리오 2 "합의 지연·무한 루프" |
| 3 | Performance Efficiency — Time Behaviour | 라운드당 옵션 생성·효용 평가·판정의 추론 지연을 **최소화**해야 한다 | VOC "on-device 추론 가능성" |
| 4 | Flexibility — Replaceability | 협상 전략(양보 곡선·집계 규칙)과 LLM 모델의 교체 소요를 **최소화**해야 한다 | VOC "빠르게 교체. 시장 변화 속도" |
| 5 | Maintainability — Testability | 협상 시뮬레이션 실험의 재현율을 **최대화**해야 한다 (동일 조건 → 동일 결과 재생) | 품질검증팀 VOC *"같은 실험 반복"* |
| 6 | Maintainability — Analysability | 결렬·수렴 실패·편향 결과의 원인 분석 가능률을 **최대화**해야 한다 | VOC "confidence 안정" (분석자 추론) |
| 7 | Performance Efficiency — Resource Utilization | 모델·협상 상태의 메모리·NPU 점유를 **최소화**해야 한다 | VOC "OS 정책 안에 들어가야" |
| 8 | Flexibility — Adaptability | 협상 결과·사용자 피드백이 Ufun·전략 개선에 반영되는 주기를 **최소화**해야 한다 (closed-loop) | VOC "self-improving" |
| 9 | Reliability — Faultlessness | 추론 실패·타임아웃 발생률을 **최소화**해야 한다 | VOC "정확도·confidence 안정" |
| 10 | Functional Suitability — Functional Appropriateness | 의제 유형(일정·장소·예산)별 옵션 표현·전략의 적합률을 **최대화**해야 한다 | 시나리오 2 (모임·여행 의제) (분석자 추론) |

## S7. Security / Privacy 담당

핵심 프레임: *"그룹이 커질수록 노출 표면이 커진다 — 최소 공개·완전 감사·초과 0건."*

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 |
|---|---|---|---|
| 1 | Security — Confidentiality | 민감 데이터의 그룹 내·외부 유출 **0건**, 서버 전송 데이터 내 PII **0건**을 유지해야 한다. 제안 패턴을 통한 선호 역추론 가능 정보량을 **최소화** (역추론은 분석자 확장) | VOC "민감 데이터는 온디바이스. PII가 빠져야" |
| 2 | Safety — Operational Constraint | 위임 권한 범위를 초과한 Agent 행동을 **0건**으로 유지해야 한다 (집계·대표 제안 경로 포함) | VOC "단 한 건의 초과 행동도 용납 불가" |
| 3 | Security — Integrity | 협상 메시지 변조의 미탐지 통과를 **0건**으로 유지해야 한다 | VOC "암호화 + 변조 감지·차단" |
| 4 | Security — Accountability | 감사 대상 이벤트(참여자별 제안·수락·거절)의 기록 누락을 **0건**으로 유지해야 한다 | VOC "누가 어떤 권한으로 무엇을 했는지" |
| 5 | Security — Authenticity | 미인증 Agent의 그룹 세션 진입을 **0건**으로 유지해야 한다 | VOC "인증/인가" |
| 6 | Security — Non-repudiation | 참여자별 위임·수락·합의 행위의 증빙 보존율 **100%**를 유지해야 한다 | Legal VOC "책임 소재 기록" |
| 7 | Security — Resistance | 알려진 공격(스푸핑·재전송·메시지 주입)의 차단율을 **최대화**해야 한다 | 원본표 "인증/인가" — 2023 신설 매핑 (분석자 판단) |
| 8 | Safety — Risk Identification | 다자 고유 위험(담합 유도·소수 의견 배제·역추론)의 사전 식별 커버리지를 **최대화**해야 한다 | 다자 확장 고유 위험 (분석자 도출 — 원문에 없음) |
| 9 | Maintainability — Analysability | 감사 로그의 privacy-safe 분석 가능률을 **최대화**해야 한다 (원문 노출 0건) | SRE VOC "privacy-safe 로그" |
| 10 | Functional Suitability — Functional Correctness | 참여자별 공개 수준 차등 필터링의 오류(잘못 공유·잘못 차단)를 **최소화**해야 한다 | VOC "요약·추상화 형태 공유" (차등은 분석자 확장) |

## S8. 운영 / SRE

핵심 프레임: *"N명 분산 세션 — 복구는 그룹 단위, 장애는 참여자 단위로 격리."*

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 |
|---|---|---|---|
| 1 | Reliability — Recoverability | 그룹 세션의 복구 성공률을 **최대화**하고 복구 시 전 참여자 재동기화 시간을 **최소화**해야 한다 | VOC "진행 중 세션은 복구 가능해야" |
| 2 | Reliability — Fault Tolerance | 장애 참여자의 격리 성공률을 **최대화**하고 잔여 그룹의 협상 지속률을 **최대화**해야 한다 | VOC "한 Agent 장애가 전체로 번지면 안 됨" |
| 3 | Maintainability — Analysability | 장애 원인 특정 시간(MTTD)을 **최소화**해야 한다 (N명 교차 로그의 상관 분석 가능률 최대화) | VOC "실시간 관찰" |
| 4 | Reliability — Availability | 협상 서비스 가동률을 **최대화**하고 MTTR을 **최소화**해야 한다 | Cloud VOC *"서버 장애가 단말 협상을 멈추게 하지 않아야"* |
| 5 | Security — Accountability | 운영 분석용 이벤트 기록 누락을 **0건**으로 유지해야 한다 | 원본표 "로그 추적성" |
| 6 | Security — Confidentiality | 로그 내 개인정보 원문 노출을 **0건**으로 유지해야 한다 | VOC "privacy-safe 로그" |
| 7 | Reliability — Faultlessness | 동일 원인 반복 장애 발생률을 **최소화**해야 한다 | 원본표 "장애 복구" (분석자 추론) |
| 8 | Flexibility — Scalability | 동시 그룹 세션 수 증가 대비 운영 부하 증가를 **최소화**해야 한다 | 01 §1.1.4 대규모 단말군 (분석자 추론) |
| 9 | Safety — Hazard Warning | 메시지 폭주·무한 루프 등 위험 징후의 경보 지연·미탐지율을 **최소화**해야 한다 | 시나리오 2 "무한 루프·메시지 폭주" |
| 10 | Flexibility — Installability | 배포·업데이트·롤백 실패율을 **최소화**해야 한다 | 대규모 단말군 전제 (분석자 추론) |

## S9. MX H/W 담당자

핵심 프레임: *"참여자가 늘어도 폰은 하나 — N의 비용이 단말 자원 한계 안에."*

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 |
|---|---|---|---|
| 1 | Performance Efficiency — Resource Utilization | CPU·NPU·메모리·배터리 사용을 **최소화**하고 상한 초과 **0건**을 유지해야 한다 | VOC *"발열·배터리가 OS 정책 안에"* |
| 2 | Compatibility — Co-existence | 포그라운드 앱 성능 저하와 OS(Doze·OOM)에 의한 강제 종료 빈도를 **최소화**해야 한다 | VOC *"Doze·OOM Killer를 정상 통과. 안 그러면 OS가 우리를 끝장냄"* |
| 3 | Flexibility — Scalability | 참여자 1인 추가당 자원(메모리·CPU·네트워크) 증가분을 **최소화**해야 한다 (선형 이내) | VOC "메모리 점유 상한" + 시나리오 2 (분석자 확장) |
| 4 | Performance Efficiency — Time Behaviour | 발열 제약(스로틀링) 하 라운드당 추론 시간을 **최소화**해야 한다 | VOC "발열" + 온디바이스 LLM 전제 (02 §2.3) |
| 5 | Performance Efficiency — Capacity | 동시 유지 가능한 그룹 세션·피어 연결 수의 상한 준수 위반 **0건**을 유지해야 한다 | VOC *"동시에 떠 있는 Agent 수 상한"* |
| 6 | Safety — Operational Constraint | 발열·전력의 안전 한계 초과를 **0건**으로 유지해야 한다 (초과 전 자체 제한) | VOC "발열·배터리" — Safety 매핑 (분석자 판단) |
| 7 | Reliability — Recoverability | OS 프로세스 종료 후 그룹 세션 상태 복원 성공률을 **최대화**해야 한다 | VOC "Doze·OOM" |
| 8 | Reliability — Fault Tolerance | 자원 고갈 시 크래시 대신 단계적 성능 저하로 전환되는 비율을 **최대화**해야 한다 | VOC "메모리 상한" (분석자 추론) |
| 9 | Flexibility — Adaptability | 단말 등급별(Compact/Balanced/Supreme) 자원 프로파일 적합률을 **최대화**해야 한다 | 01 §1.1.4 Galaxy S26 3종 변종 |
| 10 | Flexibility — Installability | 단말 모델별 설치·업데이트 실패율을 **최소화**해야 한다 | Galaxy 단말 스펙트럼 (분석자 추론) |

## S10. 품질 검증팀

핵심 프레임: *"실기기 N대 없이, 같은 다자 실험을 몇 번이고 — 재현·측정·판정 가능하게."*

| 순위 | QA (특성 — 하위특성) | 품질 요구 (정량 방향) | 근거 |
|---|---|---|---|
| 1 | Maintainability — Testability | Mock 참여자 N명만으로 재현 가능한 E2E 다자 협상 흐름의 비율 **100%**를 유지해야 한다 | VOC *"Mock PPA만으로 E2E 재현"* |
| 2 | Maintainability — Analysability | 실패 실험의 원인(어느 라운드·어느 참여자·어느 판정) 특정 가능률을 **최대화**해야 한다 | VOC *"실패 케이스 주입"의 후속 분석 (분석자 추론) |
| 3 | Functional Suitability — Functional Correctness | 정확성 판정(L1~L4, [`05`](05-Functional-Correctness-정의.md))의 자동 측정 가능률을 **최대화**해야 한다 | VOC *"정량으로 측정할 수 있어야"* |
| 4 | Maintainability — Modifiability | 실험 조건(N·전략·threshold·장애 시나리오) 변경에 필요한 작업량을 **최소화**해야 한다 | VOC *"같은 실험을 반복"* (조건 변경 실험은 분석자 추론) |
| 5 | Performance Efficiency — Time Behaviour | 합의 도달 시간·라운드 수의 측정 정밀도를 **최대화**해야 한다 (측정 오차 최소화) | VOC *"평균 협상 턴 수·응답시간 측정"* |
| 6 | Flexibility — Scalability | 검증 가능한 참여자 수 범위(N 스케일 벤치마크)를 **최대화**해야 한다 | 시나리오 2 검증 필요성 (분석자 추론) |
| 7 | Reliability — Fault Tolerance | 장애 주입(이탈·단절·타임아웃) 케이스의 검증 커버리지를 **최대화**해야 한다 | VOC *"실패 케이스도 자유롭게 주입"* |
| 8 | Reliability — Recoverability | 복구 시나리오의 검증 커버리지를 **최대화**해야 한다 | VOC "세션 복원" (SRE 원본표) 검증 관점 |
| 9 | Security — Accountability | 실험 이력·조건·결과의 기록 누락 **0건**을 유지해야 한다 (실험 추적성) | VOC "재현 가능한 실험 환경" |
| 10 | Reliability — Faultlessness | 검증 중 발견되는 기술 결함 밀도의 측정 정확도를 **최대화**해야 한다 | VOC "정량 평가" (분석자 추론) |

---

## 집계 예고

10명 × 10개 = **100개 항목**, 고유 하위특성 **37종**.
빈도 집계: [`03-QA-카테고리-정리.md`](03-QA-카테고리-정리.md) · 전수 평가: [`04`](04-QA-중요도-난이도-평가.md) · 빈도 상위 집중 평가: [`09`](09-핵심-QA-중요도-난이도-평가.md)
