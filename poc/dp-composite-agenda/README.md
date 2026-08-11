# PoC — 복합 의제 협상 방식 (dp-composite-agenda)

`docs/07-DP후보안/sunwoo/DP-복합의제-협상방식.md`의 두 설계안
(1안 의제별 순차 협상 / 2안 개인별 후보군 압축 후 복합 협상)을 동일 TC·동일 하니스로 비교하는 PoC.
QA 기준: `docs/changbae/23-핵심-QA-최종-확정.md` (핵심 5 · 비핵심 4, 측정 정의는 21 위임).
참여자는 2인 고정 — Scalability-참여자 수(b)는 `poc/dp2-nparty` 소관.

## 현재 상태

TC 계층까지 구현됨 (협상 하니스·전략 구현은 다음 단계):
- `scenarios/S01~S11.yaml` — TC 11종 (스키마: `01-TC-스키마.md`)
- `src/dpca/common/` — 로더·값 생성기·의존성 규칙·정답 프로파일(봉인)·oracle
- `scripts/validate_scenarios.py` — TC 검증 (합의 가능해 존재·충돌 라벨 실측·Pareto)

## 사용

```bash
python3 scripts/validate_scenarios.py          # TC 전수 검증
python3 scripts/validate_scenarios.py --tune   # 실패 TC의 대체 시드 탐색
python3 -m pytest tests/                       # 스모크
```
