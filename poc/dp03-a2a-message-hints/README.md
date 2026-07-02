# DP03 A2A Message Hints PoC

본 폴더는 `DP03-A2A 협상 메시지 구조`의 결정론 Track A PoC를 담는다.

비교 대상:

- `A1_DET_OFFER_ONLY`: 순수 NegMAS 메시지
- `A2_DET_HINT_AWARE`: A2A Envelope metadata로 `preference_hint` 사용
- `A3_DET_FALLBACK`: hint 미지원/버전 불일치 시 순수 NegMAS로 fallback

기존 `poc/dp03-privacy`의 코드, 데이터, 리포트는 사용하지 않는다.

## 환경

Python 3.12 기준으로 검증했다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## 테스트

```bash
.venv/bin/python -m pytest -q
```

## 샘플 실행

```bash
PYTHONPATH=src .venv/bin/python scripts/run_track_a_samples.py
```

샘플 실행은 `scenarios/samples`의 두 시나리오를 사용해 A1/A2/A3를 한 번씩 실행하고 요약 지표를 출력한다.
