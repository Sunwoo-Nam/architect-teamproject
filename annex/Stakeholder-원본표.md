# Stakeholder 분석

> 출처: `[SW Architect 팀과제] On-Device Agentic Platform.docx` — "Stakeholder 분석" 섹션
>
> 원본 표를 GFM 마크다운 표로 변환했습니다. **원본의 빈 행과 중복된 ID(예: 16번이 두 번 등장)는 그대로 보존**합니다.

| #   | Stakeholder                                                                            | 관심사                                                                                            | 비고 |
| --- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ---- |
| 1   | End User<br>(자신의 일상/업무 조율을 agent에 위임하는 사용자)                          | - 편의성<br>- 결과 만족도<br>- 개인정보 보호<br>- 최종 통제권                                      |      |
| 2   | Counterparty User<br>(다른 사용자의 agent와 협상하는 대상 사용자)                      | - 자신의 일정 및 선호 노출 최소화<br>- 협상 과정의 신뢰성<br>- 수정/거절 권한 보장                 |      |
| 3   | Service Proxy Agent Owner<br>(예약 또는 구매 대상 서비스 제공자. 예: 미용실, 식당, 숙소, 커머스 사업자) | - 인증된 요청만 수신<br>- 운영 조건 반영<br>- 예약 전환율<br>- 기존 시스템과의 연동                |      |
| 4   | Project Leader                                                                         | - 신규 사용자 가치<br>- 시나리오 실현성<br>- UX 차별화<br>- 시장성<br>- 비용                       |      |
| 5   | Architect<br>(구조 설계를 담당하는 이해관계자)                                          | - 모듈화<br>- 확장성<br>- 유지보수성<br>- 테스트 용이성                                            |      |
| 6   | Multi agent framework Developer<br>(구현을 담당하는 이해관계자)                        |                                                                                                   |      |
| 7   | Third-party Sub-Agent developer                                                        |                                                                                                   |      |
| 8   | 가전사 담당자                                                                          |                                                                                                   |      |
| 9   | Security / Privacy 담당                                                                | - 최소 권한 원칙<br>- 데이터 보호<br>- 인증/인가<br>- 감사 로그                                    |      |
| 10  | AI/ML Engineer                                                                         | - intent 인식 품질<br>- on-device 추론 가능성<br>- memory personalization<br>- self-improving 구조 |      |
| 11  | UX 디자인 팀                                                                           |                                                                                                   |      |
| 12  | 운영 / SRE                                                                             | - 장애 복구<br>- 세션 복원<br>- 모니터링<br>- 로그 추적성                                          |      |
| 13  | 품질 검증팀                                                                            |                                                                                                   |      |
| 14  | Legal / Compliance                                                                     | - OSS 라이선스 적합성<br>- 개인정보 처리 적법성<br>- 예약/대행 행위 책임 범위                      |      |
| 15  | MX H/W 담당자                                                                          |                                                                                                   |      |
| 16  | MX 상품화 의사 결정 담당자                                                             |                                                                                                   |      |
| 16  | Cloud 담당자                                                                           |                                                                                                   |      |
| 17  | 개인정보 보안 담당자                                                                   |                                                                                                   |      |
