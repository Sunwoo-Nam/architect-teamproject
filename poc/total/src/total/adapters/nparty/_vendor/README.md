# `_vendor/` — dp2-nparty 원본 이식 목록

이 폴더는 `poc/dp2-nparty/src/dp2_nparty/`의 프로토콜·측정기·리포트 생성기를 **그대로 옮긴 것**이다.
`poc/total/src/total/qa/`의 계약으로 재작성하지 않았다.

**재작성하지 않은 이유.** 통합의 검증 기준이 "기존 실행과 같은 수치가 나오는가"인데,
측정기를 다시 쓰면 수치 차이가 이식 버그 때문인지 재작성 때문인지 가릴 수 없다.
현재 채점 로직은 기존 구현과 값이 일치하도록 확인된 상태이므로 그 상태를 보존한다.

**`total/qa/`와의 관계.** 이 폴더의 `report.py`는 nparty 원지표(§1~§11) 리포트이고,
`total/qa/report.py`는 QA 별점 리포트다. 이름만 같고 입력 dict 구조도 출력 문서도 다르며,
서로 임포트하지 않는다. `total/campaign.py`·`total/experiments/`·`total/results/`는
QA 별점 경로이고, 이 폴더의 `campaign.py`·`full_campaign.py`는 nparty 원지표 경로다.

---

## 1차 이식 (2026-08-13, 프로토콜)

원본 `poc/dp2-nparty/src/dp2_nparty/`에서 9개 모듈:

| 파일 | 역할 |
|---|---|
| `__init__.py` | 패키지 표지 (내용은 이식용으로 새로 씀) |
| `benchmark.py` | `benchmark-case.v1` 로더 (functional·scalability 트랙) |
| `blackboard.py` | 공유 게시판 |
| `domain.py` | `Profile`·`Candidate`·`SessionResult`·`NO_DEAL` |
| `faults.py` | 결함(유실) 주입기 |
| `issue_space.py` | `issue-space-case.v1` 로더 + `expand()` |
| `protocol.py` | 방안 구현·`all_plans()`·`PLAN_NAMES`·`PLAN_LABELS` |
| `protocol_styles.py` | 방안 변형 구현 (`Plan1aSao` 등) |
| `threshold.py` | 임계값 정책 |
| `tiebreak.py` | 동점 해소 |

## 2차 이식 (2026-08-13, 측정기·리포트)

같은 원본에서 17개 파일. 원본 기준 커밋 `ce3e643` (2026-08-13 09:11 KST),
이식 시점 원본 작업 트리에 미커밋 변경 없음.

| 파일 | 역할 | 원본 SHA-256 앞 16자리 |
|---|---|---|
| `measures/__init__.py` | 측정기 패키지 표지 (빈 파일) | `e3b0c44298fc1c14` |
| `measures/an_kit.py` | §8 Analysability — 진단 킷 생성·채점 | `28f4dc8b4d9b1046` |
| `measures/cf_depth.py` | §7 Confidentiality — 노출 깊이 | `c1c694d298e43264` |
| `measures/confidentiality.py` | §7 — 노출률·측정 이득·별점 | `18fb564e60ff96db` |
| `measures/fc.py` | §1 Functional Correctness — 달성률·기준선 | `2c7a2ee797e15ebe` |
| `measures/ft.py` | §5 Fault Tolerance | `2de023b60bc48465` |
| `measures/rec.py` | §5 Recoverability | `ee27ba9d22b1ecac` |
| `measures/ru_memory.py` | §2 Resource Utilization — 최대 메모리 | `d14c0e831563809d` |
| `measures/ru_person.py` | §2 — 1인당 점유(`deep_size`·`holder_sizes`·`base_size`) | `b78e906b93429a02` |
| `measures/scaling.py` | §3 Scalability — 로그-로그 회귀·완주 게이트 | `2b860c84b81048df` |
| `measures/tb.py` | §6 Time Behaviour — 합성 시간·구간 지연 | `5cee9ef8d341af32` |
| `harness.py` | 실험 하니스 (`Experiment`·스윕) | `d3306422efb0e04d` |
| `ufun_provider.py` | 개발용 효용 생성기(`TableUfun`)·`UfunProvider` | `25719f794ee19697` |
| `campaign.py` | 개발용 캠페인 + `KST`·`_meta`·`_sc_issues_section` | `1c1af1e0033031e3` |
| `full_campaign.py` | 확정 벤치마크 캠페인 (`run_full`·`resolve_plans`) | `dbefb7910d025f72` |
| `report.py` | 원지표 markdown 렌더러 (`render_markdown`) | `4bb363a0a6f5633d` |
| `html_report.py` | 원지표 HTML 대시보드 (`render_html`) | `181097d6f6ef6107` |

`__pycache__`·`.pyc`는 옮기지 않았다.

---

## 원본 대비 의도적으로 고친 곳

수정한 자리에는 소스에도 `[이식 시 수정]` 표시와 이유를 붙였다.
아래 4개 파일 외에는 원본과 바이트 단위로 같다 (`diff -q`로 확인).

### 1. `benchmark.py` — `DATA_DIR` (1차 이식)

```
원본   DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "benchmark"
벤더링 DATA_DIR = Path(__file__).resolve().parents[5] / "datasets" / "nparty"
```

데이터셋이 `poc/dp2-nparty/data/benchmark/`에서 `poc/total/datasets/nparty/`로 옮겨졌다.
`parents` 첨자가 2에서 5로 바뀐 것은 폴더 깊이 차이다 —
원본은 `src/dp2_nparty/benchmark.py`(2단계 위가 패키지 루트),
벤더링본은 `src/total/adapters/nparty/_vendor/benchmark.py`(5단계 위가 `poc/total`)다.
`FIXTURES_DIR`·`CASES_DIR`는 `DATA_DIR` 파생이라 따로 고칠 것이 없다.

### 2. `benchmark.py` — `FOREIGN_SCHEMA_DIRS` (2차 이식에서 정정)

```
1차 이식본 ("issue-space", "issue-space-b")
정정 후     ("issue-space", "issue-space-b", "issue-space-n")   ← 원본과 같음
```

1차 이식에서 `"issue-space-n"`이 빠져 있었다. 이 폴더는 §11(참여자 수별 상세)용 케이스이고
스키마가 `issue-space-case.v1`이라 `benchmark-case.v1` 로더가 읽으면 안 된다.
빠져 있으면 v1 로더가 480건을 스키마 오류로 처리한다. 원본 값으로 되돌렸으므로
이 상수는 이제 원본과 같다.

### 3. `harness.py` — `PLANS` 초기화 (2차 이식)

```
원본   PLANS = dict(__import__("dp2_nparty.protocol", fromlist=["all_plans"]).all_plans())
벤더링 from .protocol import all_plans
       PLANS = dict(all_plans())
```

원본은 패키지 이름을 문자열로 박은 절대 임포트를 썼다. 벤더링본에는 `dp2_nparty` 패키지가
없으므로 같은 모듈을 상대 임포트로 가져온다. `all_plans()`가 돌려주는 값은 원본과 같다.

### 4. `report.py`·`__init__.py` — docstring 보강 (2차 이식)

동작에 영향 없는 주석·docstring만 고쳤다.

- `report.py`: `total/qa/report.py`와 이름이 겹치므로 구분 설명을 docstring에 추가.
- `_vendor/__init__.py`: 1차 이식본에 "ufun_provider.py는 뺐다"는 주석이 있었으나
  2차 이식에서 가져왔으므로 갱신. `harness.py`·`campaign.py`·`measures/an_kit.py`가
  `TableUfun`을 직접 임포트하기 때문에 빼면 그 세 모듈이 임포트되지 않는다.

---

## 고치지 **않은** 것 (확인만 한 항목)

- **`measures/an_kit.py`의 출력 경로** — `generate_kit(out_dir, ...)`가 `out_dir`를 인자로
  받고 그 아래에만 쓴다. `__file__` 기준 상수가 없어 폴더 깊이 변화의 영향을 받지 않는다.
  `grade()`도 파일 경로 2개를 인자로 받는다.
- **`full_campaign.py`의 케이스 경로** — 전부 `benchmark.CASES_DIR` 파생
  (`ISSUE_SPACE_TRACKS`, `ISSUE_SPACE_N_DIR = "issue-space-n"`)이라 `DATA_DIR` 하나만 맞으면 된다.
- **`sys.path` 조작** — 이식 대상 모듈에는 없었다 (원본에서도 `scripts/` 쪽에만 있다).
- **결과 저장 경로** — 원본에서도 라이브러리가 아니라 `scripts/run_full.py`가 정한다.
  이식 범위 밖이다.
- **상대 임포트** — `measures/*`의 `from ..domain import ...`, 최상위의 `from .protocol import ...`
  형태를 그대로 두었다. 폴더 구조를 같게 옮겼으므로 그대로 동작한다.

---

## 이식 후 확인한 것 (2026-08-13)

`poc/dp2-nparty` 소스를 경로에서 배제한 상태로 확인했다. 배제 방법은
`sys.path`에 `poc/dp2-nparty/src`를 넣지 않고, `sys.meta_path`에 `dp2_nparty` 이름을
막는 finder를 심은 뒤, 마지막에 적재된 모듈 중 그 소스에서 온 것이 0건임을 확인하는 것이다.
(인터프리터만 `dp2-nparty/.venv`를 썼다 — `poc/total/.venv`가 아직 없기 때문이며,
그 venv에 `dp2_nparty` 패키지는 설치돼 있지 않다.)

- 벤더링 모듈 26개 전수 임포트 성공.
- `full_campaign.run_full` · `report.render_markdown` · `html_report.render_html` 임포트 성공.
- v1 로더가 `total/datasets/nparty/cases/`의 functional·scalability 트랙을 읽음.
  (건수는 데이터셋 갱신 중이라 단언하지 않는다.)
- `issue-space-n`이 v1 로더 결과에 섞이지 않음 — `FOREIGN_SCHEMA_DIRS` 정정이 적용됨.
- `IssueSpaceLoader`가 `issue-space`·`issue-space-b`를, `load_issue_case`가 `issue-space-n`을 읽음.
- §11 워커(`_issue_space_n_worker`)를 `ProcessPoolExecutor`(spawn)로 2건 실행 — 자식 프로세스에서
  벤더링 모듈 재임포트 성공.
- 기존 실행 `dp2-nparty/results/full-20260813T082239KST/raw.json`을 벤더링본 렌더러에 넣으니
  같은 폴더의 `report.md`(18,196자)·`report.html`(34,549자)와 문자 단위로 일치.
- 같은 케이스 3건 × 방안 2개를 원본과 벤더링본에서 각각 별도 프로세스로 측정 — 실행 시간을
  뺀 전 지표(달성률·기준선·최적해 적중·선택 순위·유효 후보 수·라운드·구간·메시지·점유)가 일치.
- `generate_kit`을 임시 폴더에 소규모 실행 — 파일 4개 생성, `grade()` 정상 동작.

`run_full()` 전체 실행은 하지 않았다 (§11이 480건이라 40분 규모).
