dp-composite-agenda `src/dpca/` 원본 이식 (동작 무변경).

재작성하지 않은 이유는 nparty `_vendor`와 같다 — 통합의 검증 기준이 "기존 실행과 같은
수치가 나오는가"인데, 전략을 다시 쓰면 차이가 이식 버그인지 재작성 차이인지 가릴 수 없다.

이식 시 수정한 것:
- 시나리오·픽스처 경로를 `poc/total/datasets/composite/` 로 재지정
- 바이트 계측 신설 (`harness/comms.py`) — 원본에 없던 항목. dp2와 동일 규약
  (`json.dumps(payload, ensure_ascii=False)` UTF-8 길이 × 전송 건수)

**이식하며 뺀 것** (원본에는 있으나 통합본에서 쓰지 않는 것):
- `harness/recovery.py` — REC는 이번 범위 밖 (`qa/__init__.py`의 제외 사유 참조)
- `harness/judge.py` — FC 채점은 `qa/fc.py`가 정본이다. 채점기를 둘 두면 조용히
  갈라질 수 있어 뺐다 (원본 대비 유일하게 **삭제**한 항목)
- `common/fixture.py` — 픽스처 덤프/로드는 통합본이 쓰지 않는다
