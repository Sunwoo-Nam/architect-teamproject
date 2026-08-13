# composite 정본(FIN) 측정 RAW 데이터 계획 (PL 지시 2026-08-13)

> 목적: **한 번 측정하면 이후의 모든 분석·재집계가 재시뮬레이션 없이 raw에서 이루어지게** 한다.
> 원칙: ① 판정에 쓰인 값은 물론 그 **원재료(항 단위)까지** 남긴다 ② 파생 가능한 값은 파생 규칙을 명시하고 원값을 우선한다 ③ 집계는 [`scripts/aggregate_composite_final.py`](../../scripts/aggregate_composite_final.py)가 raw만 읽어 수행한다.
> 측정 범위: **FC·RU·TB** (campaign.QA_COMPOSITE — CF·SC는 본 DP 담당 밖).

## 산출물 구성 (run 폴더 = `composite-final-<ts>/`)

| 파일 | 내용 |
|---|---|
| `raw.json` | 방안별 판정 집계 + **meta 블록**(commit·python·합성 상수·세션 상한 `session_cap`·RU 밴드·판정 규칙 스냅샷) + baseline 실패 목록 — 결과만 보고도 "어느 정의·상수로 쟀는지" 복원 가능해야 한다 |
| `cases.jsonl` | 케이스×방안 1행, 1,000행 (아래 스키마) — 세분화 raw의 정본 |
| `breakdowns.json` / `breakdowns.md` | 집계기가 raw에서 파생한 분해표 (유형별·축 수별·트랙별·충돌 수준별·함정 실효·쌍대) — **파생물**, 정본은 cases.jsonl |

## 트랙 2종 — 측정 가능 범위가 다르다

| 트랙 | 조합 수 S | 측정 | 이유 |
|---|---|---|---|
| **CR** (n=4~12) | ≤ 150,000 | FC + RU + TB 전부 | 오라클(전수 열거)로 x\*·R̄ 산출 가능 |
| **RS** (n=12~20) | 최대 10^13 | RU + TB만 — FC 필드는 `null` 명시 | 전수 열거 불가 — "안 쟀다"를 null로 구분 (0·생략과 다름) |

## cases.jsonl 행 스키마 (케이스×방안)

**식별·구성** (데이터셋 메타에서):

| 필드 | 뜻 |
|---|---|
| `case_id` / `plan` | 케이스 ID (`FIN-<nn>ax-<유형>-<idx>`) / 방안(seq2·pool) |
| `track` / `type` / `conflict` | cr·rs / 유형(hard_path·plain·no_deal·stress) / 충돌 수준(low·mid·high) |
| `expected` / `planted` | 기대 결과(agreement·no_agreement) / 심은 함정 종류(path 또는 null) |
| `n_issues` / `S` / `oracle` | 의제(축) 수 / 조합 수 / 오라클 채점 여부 |

**FC (판정 = 달성률, 24 §1 — CR 트랙만, RS는 null)**:

| 필드 | 뜻 |
|---|---|
| `agreed` | 합의 여부 (결렬 정답 판별의 근거) |
| `achieved` | 달성률 U(r)÷U(x\*) — 유효 후보 = 하드 제약(의존성·참여자) 통과 ∧ 전원 바닥선 이상 |
| `baseline_R` / `s` | 무작위 베이스라인 R̄ / 보조 개선 비율 s |
| `fr_violations` | FR 위반 목록 (바닥선 밑 수락·하드 제약 위반 — 점수와 분리 집계) |

**RU (판정 = r P95 로그 사다리, 24 §2.8 — B안 기저)**:

| 필드 | 뜻 |
|---|---|
| `peak_bytes` | 협상 구간 프로토콜 상태 피크 (tracemalloc — **실물화 후보 구조 포함**) |
| `base_bytes` | 공통 기저 1인분 = 축 정의 + 자기 선호 표현 (방안 무관) |
| `materialized_bytes` | 방안이 실물화한 후보 구조의 보유 최대치 (최대 부하 단말) — 피크 내역 병기 |
| `total_mb` / `r_total` | 단말 총 점유(기저+피크) MB / 사용률 r = 총 점유 ÷ 128MB |
| `ru_stars` / `over_ceiling` | 케이스 별점 (로그 사다리) / 한도 초과 여부 (초과 = 즉시 결함) |

**TB (판정 = ρ P95, 24 §4)**:

| 필드 | 뜻 |
|---|---|
| `rho` / `rho_defect` | ρ = T_설계÷T_naive / ρ>1 결함 플래그 |
| `T_ms` | 설계안 합성 시간 (CR = 오라클 실행 합성 / RS = 러너 계수 합성 — 같은 상수) |
| `T_baseline_ms` / `baseline_capped` | naive 시간 / 상한 도달 여부(참이면 T는 하한, ρ는 상한 — 보수 판정) — baseline 실패 케이스는 null (ρ 모수에서 제외, raw.json에 사유 기록) |

**통신·진행 관측**:

| 필드 | 뜻 |
|---|---|
| `rounds` / `phases` | 라운드 / phase 수 (세션 상한 60스텝 아래 — raw.json meta `session_cap`) |
| `messages` / `bytes` | 메시지 수 / 전송량 |

## 파생 규칙 (집계기가 raw에서 계산 — 재시뮬레이션 금지)

- FC 집계 s = (달성률 평균 − R̄ 평균) ÷ (1 − R̄ 평균) — 케이스 s를 평균 내지 않는다 (24 §1.4).
- RU 판정 = 전 케이스 r_total의 **P95** (중앙값·최대 병기 — 24 §2.8 개정 2026-08-13).
- TB 판정 = ρ가 있는 전 케이스 rho의 **P95** (중앙값·최대·결함율 병기).
- 승패 = 같은 case_id의 achieved 비교 (±1e-9 무승부).

_이 계획은 본 측정 전에 확정·기록되었다 (PL 지시). 스키마 변경 시 본 문서를 먼저 개정한다._
