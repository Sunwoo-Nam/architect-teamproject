# nparty 정본 측정 RAW 데이터 계획 (functional-ext · PL 지시 2026-08-13)

> 목적: **한 번 측정하면 이후의 모든 분석·재집계가 재시뮬레이션 없이 raw에서 이루어지게** 한다.
> 원칙: ① 판정에 쓰인 값은 물론 그 **원재료(피해자·항 단위)까지** 남긴다 ② 파생 가능한 값은 파생 규칙을 명시하고 원값을 우선한다 ③ 집계는 [`scripts/aggregate_nparty_ext.py`](../../scripts/aggregate_nparty_ext.py)가 raw만 읽어 수행한다.

## 산출물 구성 (run 폴더 = `nparty-tracks-<ts>/`)

| 파일 | 내용 |
|---|---|
| `raw.json` | 트랙·방안별 판정 집계 + **meta 블록**(commit·python·negmas·합성 상수·e₂·QA 판정 규칙 스냅샷) — 결과만 보고도 "어느 정의·상수로 쟀는지" 복원 가능해야 한다 |
| `cases.jsonl` | 케이스×방안 1행 (아래 스키마) — 세분화 raw의 정본 |
| `breakdowns.json` / `breakdowns.md` | 집계기가 raw에서 파생한 분해표 (N별·유형별·변형별·깊이별·분포·쌍대·통신) — **파생물**, 정본은 cases.jsonl |

## cases.jsonl 행 스키마 (케이스×방안)

**식별·구성** (데이터셋 메타에서):

| 필드 | 뜻 |
|---|---|
| `case_id` / `track` / `plan` | 케이스 ID / 트랙명(functional-ext) / 방안(plan1a·plan2) |
| `scenario_type` | 유형 5종 (wide_common 등) |
| `variant` | `plan2-miss`(방안 2 함정 변형) 또는 `normal` — tags에서 추출 |
| `depth_band` | x\*의 순위 깊이 밴드 (early/middle/late) — tags에서 추출 |
| `n_participants` / `n_candidates` / `k_feasible` | 참여자 수 / 후보 수(12) / 공통 유효 후보 수(planted) |

**FC (판정 = 달성률, 24 §1)**:

| 필드 | 뜻 |
|---|---|
| `agreed` | 합의 여부 (결렬 정답 판별·CF 모수 필터의 근거) |
| `achieved` / `stars_achieved` | 달성률 U(r)÷U(x\*) / 케이스 별점 |
| `baseline_R` / `s` | 무작위 베이스라인 R̄ / 보조 개선 비율 s |
| `degenerate` | R̄=1 케이스 (s 판별력 없음 표시) |
| `fr_violations` | FR 위반 건수 (바닥선 밑 수락 등 — 점수와 분리 집계) |

**CF (판정 = 후보안 노출률, 24 §3 — 분모 전체 후보·모수 합의 세션·대표값 평균; 2026-08-14 재개정 — 구 잔여 비밀률 = 1 − 노출률, 판정 동치)**:

| 필드 | 뜻 |
|---|---|
| `victim_depths` | **피해자별 최악 관찰자 노출 깊이 원값 목록** (참여자 순서, 0-1) — 노출률 = 깊이 그대로, 잔여 비밀률 = 1 − 깊이. e₂와 무관한 원값이라 어떤 재정의에도 재집계 가능 |
| `exposed_counts` | 피해자별 귀속 노출 후보 **개수** (깊이×12 정수 환원 — 격자 분석용) |
| `secret_case_mean` | 케이스 내 피해자 잔여 비밀률 평균 = 1 − 케이스 노출률 (결렬 케이스도 기록 — 모수 제외는 집계기 몫. 필드명은 raw 호환을 위해 유지 — 기존 run의 cases.jsonl과 스키마 동일) |

**TB (판정 = ρ P95, 24 §4 — 항 분해 포함)**:

| 필드 | 뜻 |
|---|---|
| `rho` / `rho_defect` | ρ = T_설계÷T_naive / ρ>1 결함 플래그 |
| `T_ms` / `T_phase_ms` / `T_eval_ms` / `T_transfer_ms` | 설계안 합성 시간 총·항별 (지배 항 분석용) |
| `T_baseline_ms` / `baseline_k` / `baseline_capped` | naive 시간 / naive 성립까지 제안 수 / 벽시계 상한 여부(참이면 ρ는 상한) |

**통신·진행 관측**:

| 필드 | 뜻 |
|---|---|
| `rounds` / `sweeps` / `phases` | 라운드 / 바퀴 / phase 수 |
| `messages` / `bytes` | 메시지 수 / 전송량 |

## 파생 규칙 (집계기가 raw에서 계산 — 재시뮬레이션 금지)

- FC 집계 s = (달성률 평균 − R̄ 평균) ÷ (1 − R̄ 평균) — 케이스 s를 평균 내지 않는다 (24 §1.4).
- CF 판정 = `agreed=true` 케이스의 victim_depths를 모아 mean(1 − depth). 보조 m = depth 합 ÷ e₂(raw.json meta의 값).
- TB 판정 = 전 케이스 rho의 P95 (중앙값·최대 병기).
- 승패 = 같은 case_id의 achieved 비교 (±1e-9 무승부).

_이 계획은 측정 전에 확정·기록되었다 (PL 지시). 스키마 변경 시 본 문서를 먼저 개정한다._
