# poc/total — 통합 QA 측정 라이브러리

두 PoC가 **같은 자로** 재도록 QA 측정 코드를 한 곳에 모은 것이다.
설계 배경과 결정 근거는 [`00-설계안.md`](00-설계안.md).

**두 실험은 독립이다.** `nparty`(방안 1-A vs 방안 2)와 `composite`(1안 vs 2안)은 서로
다른 설계 문제이므로 각각 실행하고, **두 실험의 별점을 서로 비교하지 않는다.** 공유하는
것은 측정기와 결과 형식뿐이다.

## 빠른 시작

```bash
python3.14 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest                           # 테스트 (측정 라이브러리 커버리지 98%)

.venv/bin/python experiments/nparty_1a_vs_2.py       # 방안 1-A vs 2 — QA 별점
.venv/bin/python experiments/nparty_1a_vs_2_raw.py   # 방안 1-A vs 2 — 원지표 §1~§11
.venv/bin/python experiments/composite_1_vs_2.py     # 1안 vs 2안 — QA 별점
```

**파이썬은 3.14로 고정하며, 실험 스크립트가 이를 강제한다** (`src/total/pyversion.py` —
3.14가 아니면 실행 거부, 의도적 예외만 `--allow-python-mismatch`). 근거 두 가지:
① RU-메모리는 tracemalloc이 재는 파이썬 객체 크기라 **인터프리터 버전에 따라 5~10%
다르다** (3.11 vs 3.14 실측 — 00-설계안 §13-8). SC-의제 c도 여기서 회귀하므로 함께
흔들린다. ② 총효용 합산 순서가 1 ULP만 달라져도 x* 선택이 뒤집히는 사례가 실제로
있었다 — `python3`가 환경에 따라 다른 버전으로 잡히면 수치가 재현되지 않는다.

**nparty 실험은 2종이고 각각 따로 실행한다.** 같은 두 방안을 재지만 자료의 수준이 다르다.

| 실험 | 내용 | 측정기 | 소요 |
|---|---|---|---|
| `nparty-1a-vs-2` | QA 별점 — 항목별 등급 판정 | `total/qa/` | 수 분 |
| `nparty-1a-vs-2-raw` | 원지표 — 달성률·라운드·phase·메모리·시간 실측값 | `_vendor/measures/` | 약 40분 |

한 번 실행으로 둘 다 나오지 않는다. 실험 이름이 다르므로 `results/<실험명>/` 아래
별도 폴더에 쌓이고 리포트 파일도 섞이지 않는다.

빠른 확인은 `--cases 20` / `--scenarios 4 --sweep-axes 4,6,8` 로 규모를 줄인다.
`nparty_1a_vs_2_raw.py`는 `--skip-n-sweep`(§11 생략, 30분 절약) ·
`--issue-space-cases N`(§10 축소) 으로 줄인다.
결과는 [`results/INDEX.md`](results/INDEX.md)에 실행별로 쌓인다.

## 다루는 QA

| 모듈 | QA | 판정 지표 | 24 |
|---|---|---|---|
| `qa/fc.py` | Functional Correctness | 달성률 · 개선 비율 s (**2지표 병행**) | §1 |
| `qa/cf.py` | Confidentiality | 노출 배수 m (노출률·집중도 병기) | §7 |
| `qa/tb.py` | Time Behaviour | 합성 시간 + 지배 항 | §6 |
| `qa/ru.py` | Resource Utilization-메모리 | 프로세스 피크 · 공통 기저 (**각각**) | §2 |
| `qa/sc_issue.py` | Scalability-의제 | 탄력성 c · 최대 의제 수 (**2지표 병행**) | §4 |

**실험(DP)별 측정 범위** (PL 지시 2026-08-13 — `campaign.QA_NPARTY`·`QA_COMPOSITE`):

| 실험 | 측정 QA | 근거 |
|---|---|---|
| nparty | **FC · CF · TB** | 다자 프로토콜 DP의 변별축은 품질·노출·시간. RU는 kB 수준이라 포화, 의제 조합은 composite 소관 |
| composite | **FC · RU · TB** | 복합 의제 DP의 본질은 조합 폭발 → RU가 핵심. CF는 잔여 비밀률 분모(전체 후보)가 조합적으로 거대해 퇴화 — CF는 nparty 담당 |

**제외**: FT·REC (측정 방식이 두 PoC에서 근본적으로 다름 — 정본 결정 선행 필요),
SC-참여자 수 (dpca는 2인 고정), AN·AD (범위 밖). 사유는 `qa/__init__.py`에 기록.

## 구조

```
src/total/
  qa/                  ★ 공통 측정 — 실험 도메인을 모른다
    contract.py        계약: Outcome · Preference · ObservationEvent · SessionResult · Dataset
    bands.py           별점 밴드 (24의 ≥ / ≤ / > 차이를 고정)
    constants.py       상수와 밴드 정의 — 24 동기화 지점
    fc.py cf.py tb.py ru.py sc_issue.py
    report.py          meta·raw.json·cases.jsonl·md/html·INDEX
  campaign.py          실험 공통 — 방안별 세션 묶음 → QA 5종 집계
  adapters/
    nparty/            dp2 도메인 → 계약  (+ _vendor/ 프로토콜·측정기·리포트 원본)
    composite/         dpca 도메인 → 계약 (+ _vendor/ 전략 원본)
datasets/              벤치마크 데이터 (nparty 1,112건 · composite 25건)
scripts/               nparty 케이스 생성기 3종 (재생성용)
experiments/           실험 3종 (독립 실행) — nparty 별점 · nparty 원지표 · composite 별점
results/<실험>/<run_id>/
```

### 왜 프로토콜을 `_vendor/`에 원본 그대로 두었나

통합의 검증 기준이 **"기존 실행과 같은 수치가 나오는가"** 다. 프로토콜을 다시 쓰면
차이가 이식 버그인지 재작성 차이인지 가릴 수 없다. 원본을 보존하고 계약 변환만
어댑터에서 한다. 원본에서 손댄 곳은 각 `_vendor` README·주석에 `[이식 시 수정]`으로 표시.

### 설계 원칙 두 가지

**1. 측정기는 도메인을 모른다.** 가장 큰 구조 변화는 **가시성을 이벤트가 선언**하게
한 것이다. 기존 dp2 `confidentiality._visible_events()`는 방안 12종의 if-else 체인으로
"이 방안에서 누가 무엇을 보는가"를 측정기가 알고 있었다. 지금은:

```python
visible = [e for e in session.events if observer in e.audience]
```

방안이 늘어도 측정기는 그대로다.

**2. 별점만 내지 않는다.** 여러 밴드가 잠정이므로(24 §7.3 등) 원지표를 항상 함께 낸다.

## 회귀 안전망

`tests/test_regression_nparty.py`·`tests/test_adapter_composite.py`가 **기존 두 PoC의
실측값을 그대로 재현하는지** 검사한다. 이게 없으면 "통합했더니 결과가 달라졌다"를
설명할 수 없다.

| 실험 | 기준 | 재현 확인 |
|---|---|---|
| nparty | `dp2-nparty/results/full-20260812T171034KST` | FC 8개 값 · CF 노출 배수 m · 노출률 · 최대 단일 깊이 |
| composite | `dp-composite-agenda/results/fc_benchmark.jsonl` | FC 달성률·s · phase · message |

**의도적으로 바꾼 것**은 각 테스트의 `TestIntentionalChanges`에 사유와 함께 명시한다
(CF B축 제거 — 24 §7.3 개정 2026-08-13, dpca 별점 밴드 → 24 정본 교체,
TB의 wall-clock → 합성 모델).

## 알려진 한계 (정직하게)

- **RU 별점은 작은 규모에서 포화한다.** 24 §2.8이 인정하는 바로, 논리 크기와 실기기
  RSS는 단위가 다르다. 절대 MB를 항상 병기한다.
- **composite에서는 관찰 순서로 진실 선호의 순서를 복원할 수 없다.** dpca는 `agent_view`로
  에이전트가 자기 선호를 부분적으로만 안다(예: S01 `score_dropout: 0.3`). 구 B축(접두 복원
  깊이)이 늘 0이었던 이유이고, 24 §7.3 개정(2026-08-13)에서 B축을 제거한 근거 중 하나다 —
  노출 깊이(순위표 노출 비율)는 정상 변별한다.
- **1안(seq)은 축값을, 2안(pool)은 전체 조합을 교환한다.** 조합 공간 기준 노출 깊이는
  granularity가 다르다 — 축 단위 노출은 이 지표가 잡지 못한다 (별도 지표 필요, 범위 밖).
- **CF 별점 사다리는 잠정**이다 (24 §7.3, PL 조율 예정).
