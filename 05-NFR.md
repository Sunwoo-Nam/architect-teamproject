# 5. NFR (Non-Functional Requirements) 및 제약 사항

> 출처: `[SW Architect 팀과제] On-Device Agentic Platform.docx` — "품질 요구 사항" 및 "제약 사항" 섹션
>
> 원본에는 **3개 버전의 품질 요구사항 정리본**과 **2개 버전의 제약사항**이 함께 존재한다. 누락 없이 모두 보존한다.
>
> 본 문서의 어체는 사용자 지시에 따라 **음슴체 적용 제외** — 원본의 "~해야 한다" 어체를 그대로 유지한다.
>
> ⚠️ **명칭 주의**: 원본 docx에서는 "품질 요구 사항"이라는 명칭을 사용하지만, 본 저장소에서는 사용자 지시에 따라 **NFR**(비기능 요구사항)로 분류하고, 별도의 정량 시나리오 형태인 **QAS**(Quality Attribute Scenario)는 [`06-QAS.md`](06-QAS.md)에서 다룬다.

---

# 품질 요구 사항 (= NFR)

## 버전 A — 과제 제안서 Version (분류·설명 표)

| 분류                          | 설명                                                                                              |
| ----------------------------- | ------------------------------------------------------------------------------------------------- |
| 성능<br>(Performance)         | 사용자 요청 시 Proxy Agent는 하나의 상대 Proxy Agent 와 단순한 Task (1라운드 이내) 협상 시 가능한 빠르게 결과 응답을 받을 수 있어야 한다. |
| 상호운용성<br>(Interoperability) | 시스템은 약속된 규약에 따라 각 Agent 간 연결 및 합의 과정이 이루어져야 한다.                     |
| 신뢰성<br>(Reliability)       | 시스템은 장애 발생률이 낮아야 하고, 장애가 발생하더라도 빠른 시간 내에 복구되어야 한다.            |
| 보안성<br>(Security)          | 시스템은 Agent 간 합의 시 데이터는 인증 및 권한 관리가 되어야 한다.                                |
| 사용성<br>(Usability)         | 사용자는 agent가 합의하는 결과에 만족스러워야 하고, 합의 과정을 편리하게 확인할 수 있어야 한다.    |
| 유지보수성<br>(Maintainability) | 개발자는 신규 기능 추가 혹은 변경 시 시스템 유지 보수를 쉽게 할 수 있어야 한다.                    |
| 확장성<br>(Scalability)       | 시스템은 Use Case 및 Agent 수가 늘어나더라도 확장이 용이해야 한다.                                 |
| 시험용이성<br>(Testability)   | 시스템은 정량적인 Agent 간 합의 성능을 측정할 수 있어야 한다.                                      |

---

## 버전 B — ID·품질속성·요구사항명·설명·관련 Stakeholder (NFR01~NFR26)

> 📝 **2026-05-09 변경**: 표에 "관련 Stakeholder" 컬럼 추가, NFR12 설명 보완(보관 기간 정책 추가), VOC 갭 분석 결과에 따라 신규 항목 5개 추가(NFR22~NFR26). 근거는 [`03-Stakeholder.md`](03-Stakeholder.md) §3.2의 VOC.

| ID    | 품질 속성     | 요구사항명               | 설명                                                                                       | 관련 Stakeholder |
| ----- | ------------- | ------------------------ | ------------------------------------------------------------------------------------------ | ---------------- |
| NFR01 | 성능          | 단순 처리 응답성         | ZeroClaw로 처리 가능한 단순 intent는 빠른 시간 내 첫 응답을 제공해야 한다.                 | End User · AI/ML Engineer |
| NFR02 | 성능          | 단순 협상 응답성         | 단일 상대 proxy agent와의 단순 negotiation은 사용자가 체감상 지연이 크지 않은 수준으로 수행되어야 한다. | End User · AI/ML Engineer |
| NFR03 | 성능          | UI 상태 반영성           | 협상 상태 변화는 사용자 UI에 신속하게 반영되어야 한다.                                     | End User · UX 디자인 팀 |
| NFR04 | 상호운용성    | A2A 메시지 규약 준수     | Agent discovery, capability exchange, negotiation message는 표준화된 메시지 구조를 따라야 한다. | Multi-agent Framework Developer · Architect · Third-party Sub-Agent Developer |
| NFR05 | 상호운용성    | 하이브리드 연동성        | 시스템은 ZeroClaw 기반 local runtime, Android capability, 외부 service proxy와 연동 가능한 구조여야 한다. | Architect · Service Proxy Agent Owner · Multi-agent Framework Developer |
| NFR06 | 신뢰성        | 세션 복구 가능성         | 앱 재시작 또는 일시적 네트워크 장애 후에도 negotiation session을 복구할 수 있어야 한다.    | 운영/SRE · End User |
| NFR07 | 신뢰성        | 장애 격리성              | 특정 topic agent 또는 negotiation failure가 전체 시스템 장애로 확산되지 않아야 한다.       | 운영/SRE · Cloud 담당자 |
| NFR08 | 신뢰성        | 결과 일관성              | 합의 후 캘린더, 예약, 알림 반영은 중복 또는 누락 없이 처리되어야 한다.                     | End User · Service Proxy Agent Owner · 운영/SRE |
| NFR09 | 보안성        | 상호 인증                | agent 간 연결 시 상호 인증이 수행되어야 한다.                                              | Security/Privacy 담당 · Service Proxy Agent Owner |
| NFR10 | 보안성        | 암호화 통신              | agent 간 메시지와 민감 정보는 암호화되어야 한다.                                           | Security/Privacy 담당 · 개인정보 보안 담당자 |
| NFR11 | 보안성        | 최소권한 접근제어        | agent는 위임받은 권한 범위 내에서만 데이터 접근 및 action 수행이 가능해야 한다.            | Security/Privacy 담당 · End User |
| NFR12 | 보안성        | 최소 데이터 보관 + 보관 기간 정책 | 개인정보와 민감한 협상 정보는 최소한으로 저장·보관되어야 하며, 데이터 종류별 **보관 기간(retention period)** 과 **자동 삭제 정책**이 명시·집행되어야 한다. *(2026-05-09 보관 기간 문구 보완)* | 개인정보 보안 담당자 · Legal/Compliance |
| NFR13 | 사용성        | 협상 설명 가능성         | 사용자는 협상 결과와 제안 근거를 이해할 수 있어야 한다.                                    | End User · UX 디자인 팀 · AI/ML Engineer |
| NFR14 | 사용성        | 간단한 승인 UX           | 승인, 거절, 조건 수정 입력은 최소 단계로 처리 가능해야 한다.                               | End User · UX 디자인 팀 |
| NFR15 | 사용성        | 선제 제안의 비침습성     | 비명시적 intent 기반 proactive 제안은 사용자에게 과도한 방해를 주지 않아야 한다.           | End User · UX 디자인 팀 |
| NFR16 | 유지보수성    | Agent 확장 용이성        | 새로운 domain agent를 기존 구조 변경 최소화로 추가할 수 있어야 한다.                       | Architect · Multi-agent Framework Developer · Third-party Sub-Agent Developer |
| NFR17 | 유지보수성    | 모듈 경계 명확성         | Intent, Orchestration, Negotiation, Memory, Security는 명확히 분리된 모듈이어야 한다.      | Architect · Multi-agent Framework Developer |
| NFR18 | 확장성        | 시나리오 확장성          | 일정 협상 중심 구조가 예약, 쇼핑, 가격 협상 등으로 확장 가능해야 한다.                     | Architect · Project Leader |
| NFR19 | 확장성        | Agent 수 증가 대응       | 등록 agent 수와 동시 task 수가 증가해도 구조적으로 확장 가능해야 한다.                     | Architect · MX H/W 담당자 · 운영/SRE |
| NFR20 | 시험용이성    | 정량 평가 가능성         | 협상 성공률, 평균 협상 턴 수, 평균 응답시간, approval 전환율 등을 측정할 수 있어야 한다.   | 품질 검증팀 · Project Leader |
| NFR21 | 시험용이성    | Mock 기반 테스트 가능성  | mock agent를 사용해 discovery, negotiation, failure case를 재현할 수 있어야 한다.          | 품질 검증팀 · Architect |
| NFR22 | 보안성        | 메시지 무결성·변조 감지 *(신규)* | agent 간 통신 메시지는 서명 또는 MAC 등으로 무결성이 보장되어야 하며, 변조가 발생한 경우 감지·차단되어야 한다. | Security/Privacy 담당 · Multi-agent Framework Developer |
| NFR23 | 시험용이성    | 실패 주입(Fault Injection) *(신규)* | 시스템은 네트워크 단절·타임아웃·malformed message·합의 실패 등 실패 케이스를 의도적으로 주입할 수 있는 테스트 인터페이스를 제공해야 한다. | 품질 검증팀 · 운영/SRE |
| NFR24 | 유지보수성    | LLM 모델 어댑터 교체 용이성 *(신규)* | 온디바이스 및 서버 LLM은 어댑터 추상화 계층 뒤에서 동작해야 하며, 모델 교체 시 상위 모듈(Intent·Orchestration·Negotiation)의 변경이 최소화되어야 한다. | AI/ML Engineer · Architect · MX 상품화 의사결정 담당자 |
| NFR25 | 상호운용성    | 외부 SDK 안정성·버전 호환 *(신규)* | Third-party Sub-Agent 등록용 SDK는 의미적 버전 관리(semantic versioning)와 backward compatibility 정책을 보장해야 하며, breaking change는 사전 deprecation 절차를 거쳐야 한다. | Third-party Sub-Agent Developer · Architect |
| NFR26 | 성능 / 효율   | 서버 LLM 호출 비용 통제 *(신규)* | 서버 LLM 호출 빈도와 토큰 사용량은 사전 정의된 예측 모델·상한선 안에서 동작해야 하며, 임계치 초과 시 throttle 또는 escalation이 가능해야 한다. | Cloud 담당자 · MX 상품화 의사결정 담당자 |

---

## 버전 C — NFR-1 ~ NFR-24 (단일 리스트)

- NFR-1. IDS의 intent detection은 실시간 또는 준실시간으로 동작해야 한다.
- NFR-2. 온디바이스 agent의 응답 지연은 사용자 상호작용을 방해하지 않아야 한다.
- NFR-3. 협상 세션은 reasonable latency 내에 수렴해야 한다.
- NFR-4. 모바일 디바이스의 CPU/NPU/메모리 사용량은 OS 정책 범위 내에 있어야 한다.
- NFR-5. 배터리 소모가 지속적인 background agent 운영에 치명적이지 않아야 한다.
- NFR-6. 동적 생성 agent 수와 수명은 제어 가능해야 한다.
- NFR-7. 최소 권한 원칙을 따라야 한다.
- NFR-8. 공유 데이터는 가능한 한 요약/추상화된 형태여야 한다.
- NFR-9. 원본 메시지, 원본 일정, 민감 metadata는 정책상 허용 없이는 외부 agent에 직접 노출되지 않아야 한다.
- NFR-10. agent-to-agent 통신은 상호 인증과 암호화를 지원해야 한다.
- NFR-11. 동적 생성 tool/agent는 sandbox와 policy enforcement를 반드시 거쳐야 한다.
- NFR-12. 협상 실패, 네트워크 단절, tool 오류 시 graceful fallback이 가능해야 한다.
- NFR-13. partial result와 재개(resume)가 가능해야 한다.
- NFR-14. agent runaway, deadlock, infinite negotiation을 방지해야 한다.
- NFR-15. task cancellation과 rollback 전략이 있어야 한다.
- NFR-16. 새로운 agent type, tool type, device type을 쉽게 추가할 수 있어야 한다.
- NFR-17. 다양한 도메인으로 수평 확장이 가능해야 한다.
- NFR-18. 협상 프로토콜과 capability schema는 표준화/버전관리가 가능해야 한다.
- NFR-19. 사용자는 agent가 어떤 근거로 제안을 했는지 이해할 수 있어야 한다.
- NFR-20. 사용자는 자동화 수준을 세밀하게 조절할 수 있어야 한다.
- NFR-21. 사용자는 데이터 공유 범위를 지속적으로 재정의할 수 있어야 한다.
- NFR-22. agent/task/tool 실행 상태를 관찰할 수 있는 observability 체계가 필요하다.
- NFR-23. 실험/평가/정책 업데이트가 가능해야 한다.
- NFR-24. 로그는 privacy-safe 형태로 저장/분석되어야 한다.

---

# 제약 사항

## 버전 A — 과제 제안서 Version (서술형)

- On-device(Android)에서 동작 가능한 Agent Platform 을 확보할 수 있어야 한다.
- 설계에서 제안한 오픈소스나 솔루션은 사내에서 사용 시 문제가 발생되지 않는 라이선스여야 한다.

## 버전 B — ID·제약사항명·설명

| ID    | 제약사항명           | 설명                                                                                                  |
| ----- | -------------------- | ----------------------------------------------------------------------------------------------------- |
| CON01 | Android On-device 동작 | 핵심 personal proxy, IDS, orchestrator, ZeroClaw 연동 계층은 Android 환경에서 동작 가능해야 한다.     |
| CON02 | OSS 라이선스 적합성  | 적용하는 오픈소스 및 솔루션은 사내 사용 가능한 라이선스여야 한다.                                     |
