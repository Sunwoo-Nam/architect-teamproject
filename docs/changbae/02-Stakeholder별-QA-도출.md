# 2. Stakeholder별 Quality Attributes 도출 (10명 × 10개)

> 분류 체계: **ISO/IEC 25010:2023** Product Quality Model — 표기는 `특성 — 하위특성(영문)`.
> 각 stakeholder의 QA는 **그 역할의 VOC·관심사([`docs/03-Stakeholder.md`](../03-Stakeholder.md))를 근거**로 도출했으며,
> 순위(1~10)는 해당 역할 관점에서의 상대적 중요도이다 (순위 부여는 분석자 판단).
> 하위특성이 여러 역할에서 반복 선택되는 것은 의도된 결과이며, 빈도 집계는 03 문서에서 수행한다.

---

## S1. End User

핵심 프레임: *"위임해도 안전한가(1~3위) → 위임한 일이 제대로 되는가(4~6위) → 계속 쓸 만한가(7~10위)"*.
프라이버시를 1위에 둔 근거는 01 문서 §1.2.1 — "개인 기기 안에서 처리되는 자율 비서가 아니면 사용자가 마음 놓고 권한을 위임할 수 없음" (채택의 전제 조건).

| 순위 | QA (특성 — 하위특성) | End User 관점에서의 의미 | 근거 |
|---|---|---|---|
| 1 | Security — Confidentiality | 내 메시지·일정·선호는 온디바이스에서 처리되고, 외부로는 협상에 필요한 최소 정보만 나간다 | VOC "내 일정·메시지가 외부 서버로 새는 건 절대 싫음", 01 §1.4.1 |
| 2 | Interaction Capability — Operability | 협상을 언제든 중단·수정·거부할 수 있고 최종 결정은 항상 내 승인으로 끝난다 (HITL) | VOC "마지막엔 내가 승인", FR-MAF-08 |
| 3 | Safety — Operational Constraint | Agent는 위임 범위 안에서만 행동하고, 벗어나는 행위는 멈추고 승인을 요청한다 | VOC "Agent가 마음대로 결정해 버리는 게 제일 무서움", FR-MAF-10 |
| 4 | Functional Suitability — Functional Correctness | 합의 결과가 내 실제 의도·선호·일정 제약에 맞는다 | 원본표 "결과 만족도", 01 §1.4.1 "결정 품질" |
| 5 | Reliability — Fault Tolerance | 협상 중 일시 오류는 내가 모르게 처리되고 협상이 중단 없이 완료된다 | NFR-MAF-01 |
| 6 | Reliability — Recoverability | 끊긴 협상은 사라지지 않고 중단 지점부터 복구된다 | NFR-MAF-03, SRE VOC "갑자기 사라진 경험은 치명적" |
| 7 | Interaction Capability — Self-descriptiveness | 협상 진행 상황을 보고 싶을 때 볼 수 있고, 왜 그 합의안인지 이해할 수 있다 | VOC "왜 그 안을 골랐는지 한 줄이라도", FR-MAF-07 |
| 8 | Performance Efficiency — Time Behaviour | Intent 인지·개입 반영은 즉각적이고 협상 전체도 기다릴 만한 시간에 끝난다 | NFR-IDS-01, NFR-MAF-04/05 |
| 9 | Performance Efficiency — Resource Utilization | 백그라운드 동작이 배터리·발열·앱 성능을 해치지 않는다 | NFR-IDS-04, NFR-MAF-06 |
| 10 | Interaction Capability — User Engagement | 선제 제안이 유용한 빈도·품질로 오고, 침습적으로 느껴지지 않는다 (자율 모드 일시 중지 포함) | VOC *"자율 모드는 꺼 두고 싶음"*, UX VOC "너무 자주 뜨면 침습적" |

> 참고: 사후 감사(Accountability)는 End User 체감상 7위 Self-descriptiveness와 겹쳐 10개에서 제외하고 S2·S7이 대변한다 (분석자 판단).

---

## S2. Counterparty User

핵심 프레임: 본 시스템의 직접 사용자가 아니면서 협상의 영향을 받는 쪽. *"내 정보가 최소로 노출되고, 상대 Agent가 나를 일방적으로 밀어붙이지 못하며, 사후 검증이 가능한가."*

| 순위 | QA (특성 — 하위특성) | Counterparty 관점에서의 의미 | 근거 |
|---|---|---|---|
| 1 | Security — Confidentiality | 내 일정·선호는 협상에 필요한 만큼만 공유된다 | VOC "일정을 통째로 보여주고 싶지 않음", FR-MAF-05 |
| 2 | Interaction Capability — Operability | 내가 거절하거나 조건을 바꾸면 즉시 반영된다 | VOC *"즉시 반영되어야 함"*, FR-MAF-08 |
| 3 | Safety — Operational Constraint | 상대 Agent가 원치 않는 결정을 일방적으로 밀어붙이지 못한다 | VOC "일방적으로 밀어붙이는 일은 없어야", FR-MAF-10 |
| 4 | Security — Authenticity | 나와 협상하는 것이 진짜 그 사람의 PPA임이 보장된다 | FR-MAF-01 (Mutual Authentication) |
| 5 | Security — Integrity | 오간 협상 메시지가 위·변조되지 않는다 | Security 담당 VOC "변조 감지·차단", NFR-MAF-07 |
| 6 | Security — Accountability | 협상이 어떻게 흘러갔는지 사후에 확인할 수 있다 | VOC "사후에 확인할 수 있어야 마음이 놓임", NFR-MAF-08 |
| 7 | Functional Suitability — Functional Correctness | 합의안이 내 쪽 조건·제약도 정확히 반영한다 (양방향 정확성) | VOC "협상 과정 신뢰성" (원본표) |
| 8 | Interaction Capability — Self-descriptiveness | 상대 Agent의 제안 근거·협상 경과를 이해할 수 있다 | VOC "협상이 어떻게 흘러갔는지" |
| 9 | Security — Non-repudiation | 합의된 내용을 상대가 나중에 부인할 수 없다 | 분쟁 시 합의 증빙 (Legal VOC "책임 소재 기록"에서 도출) |
| 10 | Interaction Capability — User Error Protection | 승인·거절 조작 실수가 실세계 행동(예약 확정)으로 바로 이어지지 않는다 | UX VOC "승인·거절 최소 단계"의 이면 (분석자 추론) |

---

## S3. Service Proxy Agent Owner

핵심 프레임: *"검증된 요청만, 우리 정책 그대로, 기존 시스템 위에서."* — B2C 시나리오 5·6·7·9의 카운터파트.

| 순위 | QA (특성 — 하위특성) | 사업자 관점에서의 의미 | 근거 |
|---|---|---|---|
| 1 | Security — Authenticity | 신원이 검증된 사용자·Agent의 요청만 수신한다 | VOC "봇이 무차별로 들어오면 운영 마비" |
| 2 | Security — Resistance | 악의적·과도한 자동화 요청(무차별 예약 시도)을 견딘다 | 같은 VOC — 2023 신설 하위특성으로 매핑 (분석자 판단) |
| 3 | Compatibility — Interoperability | 기존 예약 시스템과 충돌 없이 연동된다 | VOC *"우리 시스템을 갈아엎으라는 요구는 받기 어려움"* |
| 4 | Functional Suitability — Functional Correctness | 가격·시간·노쇼 페널티 등 우리 정책이 그대로 정확히 반영된다 | VOC "가게 정책이 그대로 반영" |
| 5 | Security — Non-repudiation | Agent 경유 예약을 사용자가 부인할 수 없다 (노쇼 책임) | VOC "실제 결제와 방문으로 이어져야", 시나리오 6 "노쇼 방지 로직" |
| 6 | Functional Suitability — Functional Appropriateness | Agent 협상 방식이 예약·판매 업무 흐름에 실제로 맞는다 | VOC "예약 전환율" (원본표) |
| 7 | Security — Accountability | 어떤 Agent가 언제 무엇을 예약했는지 추적 가능하다 | 시나리오 5 "실시간 동기화 및 신뢰성" |
| 8 | Reliability — Availability | Agent 예약 채널이 영업시간 중 항상 동작한다 | VOC "예약 전환율"에서 도출 (분석자 추론) |
| 9 | Performance Efficiency — Capacity | 동시 다발 예약 요청(N-party·성수기)을 수용한다 | 시나리오 6·9 (분석자 추론) |
| 10 | Compatibility — Co-existence | 기존 POS·예약 시스템과 같은 환경에서 자원 간섭 없이 공존한다 | VOC "기존 시스템과의 연동" (원본표) |

---

## S4. Project Leader

핵심 프레임: *"검증 가치가 명확하고, 데모에서 차별화가 체감되며, 상품화로 이어질 수 있는가."*
**1위는 PL 본인의 명시 지시(2026-08-04)** 에 따른다: "Functional Correctness가 가장 중요한 QA" — 정의 논의는 [`05-Functional-Correctness-정의.md`](05-Functional-Correctness-정의.md) 참조.

| 순위 | QA (특성 — 하위특성) | PL 관점에서의 의미 | 근거 |
|---|---|---|---|
| 1 | Functional Suitability — Functional Correctness | Agent가 수행한 협상·실행 결과가 사용자 의도에 비추어 "맞아야" 한다. 틀린 결과는 다른 모든 품질을 무의미하게 만든다 | **PL 명시 지시 (2026-08-04)** |
| 2 | Functional Suitability — Functional Appropriateness | 선정 시나리오가 신규 사용자 가치를 실제로 실현하는 데 적합하다 | VOC "외부에 자랑할 수 있는 새로운 사용자 가치" |
| 3 | Functional Suitability — Functional Completeness | 차별화 핵심 시나리오가 끝까지(합의→실행) 완결 구현된다 | VOC "어느 것이 차별화의 핵심인지부터" |
| 4 | Interaction Capability — User Engagement | 사용자가 "정말 다르게 느끼는" UX — 선제 제안의 체감 품질 | VOC "기술적으로 멋있는 것 말고 UX" |
| 5 | Maintainability — Testability | 3대 가설이 정량 지표로 검증/반증 가능해야 의사결정 재료가 된다 | VOC *"비용 대비 검증 가치"*, 품질검증팀 VOC |
| 6 | Performance Efficiency — Time Behaviour | 데모·실사용에서 체감 응답성이 경쟁 제품 대비 설득력 있다 | VOC "UX 차별화" |
| 7 | Reliability — Faultlessness | 시연·평가 중 크래시·미처리 예외가 없다 | VOC "시나리오 실현성" |
| 8 | Performance Efficiency — Resource Utilization | 양산 단말 자원 안에서 동작함이 입증된다 (상품화 전제) | 상품화 담당 VOC *"양산 단말의 자원·OS 정책"* |
| 9 | Flexibility — Scalability | 1:1 검증이 N-party·다도메인으로 확장 가능한 구조임을 보인다 | VOC "시장성", 시나리오 2·6 |
| 10 | Interaction Capability — Appropriateness Recognizability | 처음 보는 사용자·의사결정자가 시스템 가치를 즉시 인식한다 | VOC "외부에 자랑할 수 있는" (분석자 추론) |

---

## S5. Architect

핵심 프레임: *"모듈 경계가 명확하고, 확장이 국소적이며, 변경 영향이 추적되고, 전체 흐름이 재현 가능한가."*

| 순위 | QA (특성 — 하위특성) | Architect 관점에서의 의미 | 근거 |
|---|---|---|---|
| 1 | Maintainability — Modularity | Intent/Orchestration/Negotiation/Memory/Security 5모듈의 경계가 명확하다 | VOC "경계가 흐릿하면 운영 단계로 못 감" |
| 2 | Maintainability — Modifiability | Agent 종류·도메인 추가 시 기존 코드 수정이 최소화된다 | VOC "손을 거의 안 대고도 확장" |
| 3 | Maintainability — Testability | Mock PPA만으로 협상 흐름 전체를 재현·비교 실험할 수 있다 | VOC *"Mock으로 협상 흐름 전체 재현"* |
| 4 | Maintainability — Analysability | 한 곳의 변경이 어디에 영향을 주는지 추적 가능하다 | VOC "변경 영향이 추적 가능해야" |
| 5 | Flexibility — Adaptability | 새 도메인·새 시나리오에 구조 변경 없이 적응한다 | VOC "확장성" (원본표) |
| 6 | Flexibility — Scalability | 참여자 수(N-party)·Agent 수 증가에 구조가 견딘다 | NFR-MAF-09, 시나리오 2 |
| 7 | Compatibility — Interoperability | A2A 프로토콜 준수로 표준 진화에 열려 있다 | 02 §2.7 "A2A 프로토콜 준수", 01 §1.2.2(3) 표준 선점 |
| 8 | Flexibility — Replaceability | 온디바이스 LLM 모델을 다른 모델로 교체해도 구조가 유지된다 | AI/ML VOC "모델 교체", Galaxy S26 3종 변종 |
| 9 | Maintainability — Reusability | 협상·lifecycle 공통 로직이 시나리오 9종에 재사용된다 | VOC "모듈화"에서 도출 (분석자 추론) |
| 10 | Reliability — Fault Tolerance | 결함 격리 경계(bulkhead)가 구조 수준에서 정의된다 | SRE VOC "한 Agent의 장애가 전체로 번지면 안 됨" |

---

## S6. Multi-agent Framework Developer

핵심 프레임: *"격리·표준화·재현 — 코드를 단순하게 짤 수 있는 구조적 전제."*

| 순위 | QA (특성 — 하위특성) | 구현자 관점에서의 의미 | 근거 |
|---|---|---|---|
| 1 | Maintainability — Testability | LLM 비결정성 하에서도 실패 케이스를 재현할 수 있다 | VOC *"재현이 안 되면 손을 못 댐"* |
| 2 | Maintainability — Analysability | Agent·Task·Tool 실행의 추적 로그로 디버깅이 가능하다 | VOC *"디버깅이 가능한 추적 로그"* |
| 3 | Safety — Safe Integration | 동적 생성된 Agent/Tool이 sandbox 안에서 격리 실행되어도 전체 시스템 안전이 유지된다 | VOC *"sandbox 안에서 안전하게 격리 실행"* |
| 4 | Reliability — Fault Tolerance | 실패한 LLM·Tool 호출의 재시도·대체·escalation 정책이 프레임워크 수준에서 제공된다 | VOC *"재시도·대체·escalation 정책"* |
| 5 | Reliability — Recoverability | 세션 상태 저장·복원이 프레임워크 공통 기능으로 제공된다 | NFR-MAF-03 |
| 6 | Maintainability — Modularity | 메시지 형식·lifecycle 상태 전이가 표준화되어 있다 | VOC *"메시지 형식과 lifecycle 표준화"* |
| 7 | Safety — Fail Safe | 이상 상황(무응답·타임아웃·합의 불가) 시 불확정 상태 없이 안전하게 완결된다 | FR-MAF-11 "불확정 상태에 빠지지 않아야" |
| 8 | Compatibility — Interoperability | A2A 스펙 준수가 구현 수준에서 검증 가능하다 | 02 §2.7, CON-02 |
| 9 | Maintainability — Modifiability | 협상 전략·정책 변경이 코드 전반 수정 없이 가능하다 | VOC "코드를 단순하게" (분석자 추론) |
| 10 | Maintainability — Reusability | 4대 케이스(Negotiation/Collaboration/Knowledge Sharing/Remote Monitoring)가 공통 Communication 기반을 공유한다 | 04-FR §2 구조 |

---

## S7. Security / Privacy 담당 (개인정보 보안 담당자 병합)

핵심 프레임: *"최소 권한·최소 노출·완전한 감사 — 단 한 건의 초과 행동도 없이."*

| 순위 | QA (특성 — 하위특성) | 보안 관점에서의 의미 | 근거 |
|---|---|---|---|
| 1 | Security — Confidentiality | 민감 데이터는 온디바이스 처리, 외부 전송 시 PII 제거·요약·추상화 | VOC "민감 데이터는 온디바이스", *"요약·추상화된 형태"* |
| 2 | Safety — Operational Constraint | Agent는 위임 권한 범위 안에서만 — 단 한 건의 초과 행동도 불가 | VOC "단 한 건의 초과 행동도 용납 불가" |
| 3 | Security — Integrity | Agent 간 메시지 암호화 + 변조 감지·차단 | VOC "암호화·변조 감지", NFR-MAF-07 (TLS 1.3) |
| 4 | Security — Accountability | 누가 어떤 권한으로 무엇을 했는지 사후 감사 가능 (기록률 100%) | VOC "사후 감사", NFR-MAF-08 |
| 5 | Security — Authenticity | Agent 상호 인증 — 동적 생성 Agent 포함 동일 검사 경로 통과 | VOC *"동적 생성 Agent도 동일한 보안 정책 경로"*, FR-MAF-01 |
| 6 | Security — Non-repudiation | 권한 위임·합의·실행 행위의 부인 방지 | Legal VOC "책임 소재가 약관과 시스템에 기록" |
| 7 | Security — Resistance | 외부 공격(스푸핑·재전송·주입)에 대한 저항 | VOC "인증/인가" (원본표) — 2023 신설 하위특성 매핑 |
| 8 | Safety — Risk Identification | 고령자·미성년자 등 민감 사용자 그룹의 위험이 사전 식별·완화된다 | VOC *"민감 사용자 그룹 별도 보호 장치"*, 시나리오 8 |
| 9 | Maintainability — Analysability | 감사 로그가 privacy-safe하면서 분석 가능한 형태로 남는다 | SRE VOC "privacy-safe 로그" |
| 10 | Functional Suitability — Functional Correctness | 정책 기반 필터링(Private Knowledge 0건)이 정확히 동작한다 | FR-MAF-05, NFR-MAF-07 "0건" |

---

## S8. AI/ML Engineer

핵심 프레임: *"Intent 품질이 전체의 상한 — 온디바이스에서 돌아가고, 빠르게 교체·개선 가능해야."*

| 순위 | QA (특성 — 하위특성) | AI/ML 관점에서의 의미 | 근거 |
|---|---|---|---|
| 1 | Functional Suitability — Functional Correctness | Intent 분류 정확도·confidence가 안정적이다 — "틀리면 뒤의 모든 Agent가 헛수고" | VOC "Intent 분류 품질" |
| 2 | Performance Efficiency — Time Behaviour | 온디바이스 추론 지연이 UX 임계값(라운드당 10~15초) 안에 든다 | NFR-MAF-04 근거 열 |
| 3 | Performance Efficiency — Resource Utilization | 메모리·CPU·NPU 사용량이 OS 정책 안에 든다 | VOC "OS 정책 안에 들어가야 모델을 올릴 수 있음" |
| 4 | Flexibility — Replaceability | 온디바이스 LLM을 다른 모델로 빠르게 교체할 수 있다 | VOC "시장 변화 속도가 너무 빠름" |
| 5 | Flexibility — Adaptability | 사용자 메모리·협상 이력이 모델 개선에 재유입되는 closed-loop | VOC "self-improving" |
| 6 | Maintainability — Testability | 모델 품질(정확도·성공률)을 재현 가능한 실험으로 평가할 수 있다 | 품질검증팀 VOC, NFR-IDS-05 |
| 7 | Maintainability — Analysability | 오분류·드리프트의 원인을 로그로 분석할 수 있다 | VOC "confidence score 안정" (분석자 추론) |
| 8 | Functional Suitability — Functional Appropriateness | 모델 크기·능력이 태스크 복잡도에 적합하다 (Compact/Balanced/Supreme 선택) | 01 §1.1.4 Galaxy S26 3종 변종 |
| 9 | Reliability — Faultlessness | 추론 실패·타임아웃률이 낮게 유지된다 | NFR-IDS-05 |
| 10 | Performance Efficiency — Capacity | IDS·Meta Agent·Sub-Agent의 동시 추론 요청을 수용한다 | NFR-MAF-06 "동시 동작하는 IDS·포그라운드 앱" |

---

## S9. 운영 / SRE

핵심 프레임: *"복구 가능하고, 격리되어 있고, 관찰 가능하고, 로그가 안전한가."*

| 순위 | QA (특성 — 하위특성) | 운영 관점에서의 의미 | 근거 |
|---|---|---|---|
| 1 | Reliability — Recoverability | 장애 후 진행 중 협상 세션이 복구된다 | VOC "'갑자기 사라진' 경험은 치명적" |
| 2 | Reliability — Fault Tolerance | 한 Agent의 장애가 시스템 전체로 번지지 않는다 | VOC "장애가 전체로 번지면 안 됨" |
| 3 | Maintainability — Analysability | Agent·Task·Tool 실행 상태의 실시간 관측(observability)이 가능하다 | VOC "실시간으로 관찰" |
| 4 | Reliability — Availability | 플랫폼 서비스(특히 서버 Orchestrator 경로)의 가용성이 유지된다 | Cloud VOC *"서버 장애가 단말 협상을 멈추게 하지 않아야"* |
| 5 | Security — Accountability | 장애·분쟁 시 원인 분석 가능한 완전한 이벤트 이력 | NFR-MAF-08 "추적 공백이 발생하면 원인 분석 불가" |
| 6 | Security — Confidentiality | 로그가 privacy-safe 형태라 운영자가 열람할 수 있다 | VOC "privacy-safe 형태로 저장" |
| 7 | Reliability — Faultlessness | 반복 장애·미처리 예외의 발생률 자체가 낮다 | NFR-MAF-02 |
| 8 | Flexibility — Scalability | 사용자·세션 수 증가에 운영 부하가 선형 이내로 는다 | NFR-MAF-09 (분석자 확장 적용) |
| 9 | Safety — Hazard Warning | 위험 상황(폭주·비정상 패턴)이 운영자·사용자에게 조기 경보된다 | FR-MAF-11 이상 상황 감지 (분석자 매핑) |
| 10 | Flexibility — Installability | 대규모 단말군에 배포·업데이트·롤백이 안전하게 이뤄진다 | 01 §1.1.4 "3억 대 배포" 맥락 (분석자 추론) |

---

## S10. MX H/W 담당자

핵심 프레임: *"OS 정책과 물리 한계 안에서 — 아니면 OS와 사용자가 우리를 꺼 버린다."*

| 순위 | QA (특성 — 하위특성) | H/W 관점에서의 의미 | 근거 |
|---|---|---|---|
| 1 | Performance Efficiency — Resource Utilization | CPU·NPU·메모리·배터리 사용이 상한(IDS 200MB, MAF 300MB 등) 안에 든다 | VOC *"발열·배터리가 OS 정책 안에"*, NFR-IDS-04, NFR-MAF-06 |
| 2 | Compatibility — Co-existence | Android Doze·OOM Killer·포그라운드 앱과 정상 공존한다 | VOC *"Doze·OOM Killer를 정상 통과해야. 안 그러면 OS가 우리를 끝장냄"* |
| 3 | Performance Efficiency — Capacity | 동시 실행 Agent 수·세션 수에 명시적 상한이 있다 | VOC *"동시에 떠 있는 Agent 수 상한"* |
| 4 | Performance Efficiency — Time Behaviour | NPU 추론 시간이 발열 제약 하에서도 목표를 만족한다 | NFR-MAF-04 (온디바이스 추론 10~15초/라운드) |
| 5 | Safety — Operational Constraint | 발열·전력이 안전 한계 초과 시 시스템이 스스로 동작을 제한한다 | VOC "발열·배터리" — Safety 매핑 (분석자 판단) |
| 6 | Reliability — Recoverability | OS에 의해 프로세스가 종료돼도 상태 복원 후 재개된다 | VOC "Doze·OOM" + NFR-MAF-03 |
| 7 | Flexibility — Adaptability | 단말 등급별 모델 변종(Compact/Balanced/Supreme)에 맞춰 동작을 조정한다 | 01 §1.1.4 Galaxy S26 |
| 8 | Reliability — Fault Tolerance | 자원 부족 시 크래시가 아니라 단계적 성능 저하(degradation)로 대응한다 | VOC "메모리 점유 상한" (분석자 추론) |
| 9 | Flexibility — Scalability | N-party 협상 시 자원 증가가 선형 이내(참여자당 CPU +2%p, Mem +20MB)다 | NFR-MAF-09 |
| 10 | Flexibility — Installability | 다양한 단말 모델에 설치·업데이트가 자원 프로파일에 맞게 이뤄진다 | Galaxy 단말 스펙트럼 (분석자 추론) |

---

## 집계 예고

10명 × 10개 = **100개 항목**, 고유 하위특성 기준 **37종**이 선택되었다.
카테고리별 취합과 빈도 분석은 [`03-QA-카테고리-정리.md`](03-QA-카테고리-정리.md)에서 수행한다.
