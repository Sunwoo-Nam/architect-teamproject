# DP02 A2A Constraint Hints PoC

본 폴더는 `DP02-A2A 협상 메시지 구조`의 결정론 Track A PoC를 담는다.

비교 대상:

- `A1_DET_OFFER_ONLY`: 순수 NegMAS 메시지
- `A2_DET_HINT_AWARE`: NegMAS `ExtendedOutcome.data` metadata로 `constraint_hint` 사용
- `A3_DET_FALLBACK`: constraint hint 미지원/버전 불일치 시 순수 NegMAS로 fallback

내부 hard constraint는 NegMAS `UFunConstraint` adapter로 negotiator의 후보 선택과 수락 판단에 반영한다. 공개되는 `constraint_hint`는 이 내부 constraint 객체가 아니라, offer에 붙는 제한된 metadata다.

기존 `poc/dp02-privacy`의 코드, 데이터, 리포트는 사용하지 않는다.

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

## 시나리오 생성

기본 세트는 `01-시나리오-스키마.md`의 매트릭스에 따라 120개를 생성한다. 확장 세트는 variant를 하나 더 늘려 180개를 생성한다. 증강 세트는 bias audit 결과를 반영해 360개를 생성한다. fixed-only 전용 세트는 hard constraint 공개 패턴, 난이도, utility shape를 분리해 480개를 생성한다. 축 분리 증강 세트는 hint policy, difficulty, utility shape의 pairwise 균형을 맞춰 600개를 생성한다. 고복잡도 fixed-only 스트레스 세트는 issue_4/issue_5에서 양측이 서로 다른 issue에 fixed constraint를 갖는 경우를 640개 생성한다. 3자 협상 스트레스 세트는 issue_4/issue_5에서 세 참여자의 fixed constraint 참여 패턴을 나눠 120개를 생성한다. 4자 협상 스트레스 세트는 issue_4/issue_5에서 네 참여자의 constraint topology와 난이도를 분리해 160개를 생성한다.

```bash
PYTHONPATH=src .venv/bin/python scripts/generate_scenarios.py --count 120
PYTHONPATH=src .venv/bin/python scripts/generate_scenarios.py --count 180
PYTHONPATH=src .venv/bin/python scripts/generate_scenarios.py --count 360
PYTHONPATH=src .venv/bin/python scripts/generate_scenarios.py --count 480
PYTHONPATH=src .venv/bin/python scripts/generate_scenarios.py --count 600
PYTHONPATH=src .venv/bin/python scripts/generate_scenarios.py --count 640
PYTHONPATH=src .venv/bin/python scripts/generate_scenarios.py --preset fixed_three_party
PYTHONPATH=src .venv/bin/python scripts/generate_scenarios.py --preset fixed_four_party
```

120/180개 세트는 기본적으로 `scenarios/generated`, 360개 증강 세트는 `scenarios/generated_v3`, 480개 fixed-only 전용 세트는 `scenarios/generated_fixed_only_v1`, 600개 축 분리 증강 세트는 `scenarios/generated_v4`, 640개 고복잡도 fixed-only 스트레스 세트는 `scenarios/generated_fixed_high_complexity_v1`, 120개 3자 협상 스트레스 세트는 `scenarios/generated_fixed_three_party_v1`, 160개 4자 협상 스트레스 세트는 `scenarios/generated_fixed_four_party_v1` 하위에 저장된다.

## Generated Matrix 실행

생성된 120개 시나리오 전체에 대해 Track A의 A1/A2를 실행하고, 결과를 `results/track_a_generated` 하위에 저장한다.

```bash
PYTHONPATH=src .venv/bin/python scripts/run_track_a_generated.py
PYTHONPATH=src .venv/bin/python scripts/run_track_a_generated.py --scenario-dir scenarios/generated_fixed_only_v1 --output-dir results/track_a_fixed_only_v1
PYTHONPATH=src .venv/bin/python scripts/run_track_a_generated.py --scenario-dir scenarios/generated_fixed_three_party_v1 --output-dir results/track_a_fixed_three_party_v1_max100_concession30 --n-steps 100 --concession-steps 30
PYTHONPATH=src .venv/bin/python scripts/run_track_a_generated.py --scenario-dir scenarios/generated_fixed_four_party_v1 --output-dir results/track_a_fixed_four_party_v1_max100_concession30 --n-steps 100 --concession-steps 30
PYTHONPATH=src .venv/bin/python scripts/run_track_a_generated.py --scenario-dir scenarios/generated_fixed_four_party_v1 --output-dir results/track_a_fixed_four_party_v1_latency_repeat10 --n-steps 100 --concession-steps 30 --repeat-count 10
```

산출물은 `run_results.jsonl`, `scenario_comparison.jsonl`, `metric_summary.json`이다. `results` 하위 실행 산출물은 git에 커밋하지 않는다.
협상 지연시간 분석은 `wall_clock_ms_to_agreement`를 실측 지표로 보고, `offer_count_to_agreement`, `atomic_actions_to_agreement`, `candidate_evaluation_count`, `hint_fit_evaluation_count`를 처리량/계산량 proxy로 함께 확인한다. 기존 `rounds_to_agreement`는 호환을 위해 유지하지만 실제 의미는 offer count에 가깝다.

## Bias Audit

생성 시나리오와 Track A batch 결과를 기준으로 feature 분포, 난이도 분포, A2 faster/slower 상관을 점검한다.

```bash
PYTHONPATH=src .venv/bin/python scripts/audit_generated_bias.py
```

산출물은 `results/track_a_generated/bias_audit.json`이다.
