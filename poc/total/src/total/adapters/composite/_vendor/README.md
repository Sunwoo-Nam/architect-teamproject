dp-composite-agenda `src/dpca/` 원본 이식 (동작 무변경).

재작성하지 않은 이유는 nparty `_vendor`와 같다 — 통합의 검증 기준이 "기존 실행과 같은
수치가 나오는가"인데, 전략을 다시 쓰면 차이가 이식 버그인지 재작성 차이인지 가릴 수 없다.

이식 시 수정한 것:
- 시나리오·픽스처 경로를 `poc/total/datasets/composite/` 로 재지정
- 바이트 계측 신설 (`harness/comms.py`) — 원본에 없던 항목. dp2와 동일 규약
  (`json.dumps(payload, ensure_ascii=False)` UTF-8 길이 × 전송 건수)
