# PoC — 복합 의제 협상 방식 (dp-composite-agenda)

`docs/07-DP후보안/sunwoo/DP-복합의제-협상방식.md`의 두 설계안
(1안 의제별 순차 협상 / 2안 개인별 후보군 압축 후 복합 협상)을 동일 TC·동일 하니스로 비교하는 PoC.
QA 기준: `docs/changbae/23-핵심-QA-최종-확정.md` (핵심 5 · 비핵심 4) + **QA별 측정 정본 24~29**
(FC는 24의 Total Utility 달성률, 의제 수 c는 27, FT/REC는 28, Confidentiality 공격자는 29 — 21의 해당 항목 대체. 26 RU는 정의안 단계).
참여자는 2인 고정 — Scalability-참여자 수(b)는 `poc/dp2-nparty` 소관.

## 현재 상태

P1(하니스 + 전략 3구현)까지 구현됨:
- `src/dpca/harness/` — beliefs(에이전트가 아는 것만: 부분 정보 뷰·자기 제약·바닥선),
  NegMAS 브리지(SAOMechanism·양보선), Judge(24 정본 달성률·별점), 러너(tracemalloc 피크·라운드·제안 수)
- `src/dpca/strategies/` — `full`(baseline 전수 나열, c≈1 앵커) · `seq`(1안 축별 순차 SAO 세션 +
  낙관적 완성 하한·백트랙·최종 확인) · `pool`(2안 축별 top-k 압축 풀 + 양보선-풀하한 deepening)
- `scripts/run_smoke.py [--all]` — TC × 전략 3종 스모크 (달성률·별점·라운드·피크 메모리)
- **추적성**: 모든 실행은 이벤트 로그(JSONL)를 남길 수 있다 — 제안·응답마다 offer·자기 효용·
  그 시점 양보선·결정 사유, deepening/백트랙/최종 확인 이벤트까지 (기록 완전성 FR 취지).
  `scripts/explain_run.py <log.jsonl>` (또는 `--demo S01 pool`)이 로그만으로 협상 전개를
  사람 말로 재구성한다. 같은 시드 → 같은 로그(결정론 재현).

TC 계층:
- `scenarios/S01~S11.yaml` — TC 11종 (스키마: `01-TC-스키마.md`)
- `src/dpca/common/` — 로더·값 생성기·의존성 규칙·정답 프로파일(봉인)·oracle
- `scripts/validate_scenarios.py` — TC 검증 (합의 가능해 존재·충돌 라벨 실측·Pareto)

## 사용

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # negmas 0.15.7 포함
python3 scripts/validate_scenarios.py          # TC 전수 검증 (negmas 불필요)
.venv/bin/python scripts/run_smoke.py --all    # 전략 3종 × TC 11종 스모크
.venv/bin/python -m pytest tests/              # 테스트 (21건)
```
