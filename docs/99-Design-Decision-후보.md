# Design Decision 후보

## 1. Orchestrator에서 Server에 위치한 LLM을 쓸 때 민감 정보를 어떻게 처리할 것인가?

- On-device에 Data sanitize 후 전송
- On-device LLM 사용 (서버 LLM과 역할 분리)
- Data를 Layer화해서...

## 2. Agent / tool 생성 방식

- 동적으로 생성하는게 정말 가능한가?
- 동적 생성이 반드시 필요한가?
- 코드까지 생성하는게 필요한가?

## 3. Single Agent VS Multi Agent

- Latency / Accuracy / Cost 를 고려해야할듯

## 4. 협상을 하나로 merge

- 각 Device에서 Intent를 각자 발생시킬 텐데, 어떻게 하나로 머지할 것인가
- 이 때, 누군가가 Master 역할을 할 것인지? 아니면 각자가 N:N으로 할 것인지

## 5. 가전기기의 Data를 누가 어떻게 처리? (DPA)

- 개인정보, 보안 문제 고려 필요

## 6. 협상시 각 device의 민감정보를 어떻게 처리할 것인가?

- Latency / Security 등의 고려 필요할듯 

## 7. 전체 Task의 수행이 신뢰성 있게 잘 완료될 수 있는 구조

- 신뢰성, 장애처리 등의 고려 필요

## 8. 협상시 Token 사용량 효율화

- Latency 도 함께 고려해야함 

## 9. 협상이 취소되거나 변경되었을 때 어떻게 처리할 것인가

- 어떻게 중단 시킬 수 있고, 중단후 정보의 삭제/보관은 어떻게 할 것인지
- 재시작한다면 복원을 어떻게 할 것인지  

## 10. IDS에서 효율적으로 monitoring 하는 방법

- 전력, 메모리 등을 고려

## 11. 다중 Intent의 동시발생시 처리 방법

- 동시에 여러 Intent가 들어올때, 하나의 Intent 처리중에 다른 것이 들어올때 등

## 12. Sub Agent의 life cycle

- Sub Agent를 언제까지 메모리에 올려둘지
- 어느 Data를 얼마나 오래 저장할지