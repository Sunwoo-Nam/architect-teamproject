# PoC — 설계 후보 1: 다자 합의 프로토콜 (dp2-nparty)

[`docs/changbae/51-설계후보1-다자-합의-프로토콜.md`](../../docs/changbae/51-설계후보1-다자-합의-프로토콜.md)의 두 방안
(방안 1 전원동의 투표형 / 방안 2 누적 공통제안형)을 구현하고, 확정된 QA 측정 정의로 성능을 비교하는 PoC.

## 환경

```bash
python3 -m virtualenv .venv          # ensurepip 미제공 환경이라 virtualenv 사용
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/    # 스모크 테스트
```

- Python 3.14 / **negmas 0.15.7** (버전 고정 — 재현성)
- NegMAS 재사용 범위: OutcomeSpace·Ufun(선호 표현·점수화)과 **양보 곡선(`PolyAspiration`)**.
  협상 루프 자체는 51 스펙(동시 제출·전원 투표/누적 교집합)이 표준 SAO가 아니므로 자체 구현.

## 확정된 프로토콜 파라미터 (PL 결정, 2026-08-11)

| 항목 | 값 |
|---|---|
| 완결 규칙 | **만장일치만** (전원 동의) |
| 결렬 상한 | **최대 5바퀴(sweep)** — 소진 후에도 성립 없으면 NO_DEAL |
| revised threshold 갱신 | **한 바퀴를 다 돌고 결론이 없을 때** 인하 |
| 인하 곡선 | NegMAS `PolyAspiration` — 고정 인하폭 대신 곡선 사용. 기본 `boulware`(끝까지 버티다 후반에 양보), `linear`/`conceder`로 교체 가능. t = (바퀴-1)/최대바퀴 로 정규화, 하한 = initial threshold |
| 동률 해소 | **플러그형(TieBreaker 인터페이스)** — 방안 1: 결선투표 1회 다수결. 방안 2: 순위 합 최소 → 표준편차 최소 → 결선투표 다수결 |

## 메시지 전송 매핑 v1 (b_msg 측정 기준 — 물리 전송 건수)

Blackboard 담당자 = 참여자 중 1인(개시자). 담당자 자신의 제출·투표는 전송 0건(로컬).

| 이벤트 | 방안 1 | 방안 2 |
|---|---|---|
| 라운드 제출 (참여자→담당자) | N-1 | N-1 |
| 라운드 후보 공지 (담당자→전원) | N-1 | **0** (방안 2는 투표가 없어 배포 불필요) |
| O/X 투표 (참여자→담당자, 라운드당 번들 1건) | N-1 | 0 |
| 라운드 결과 통지 (담당자→전원) | N-1 | 0 |
| 최종 성립/결렬 통지 (담당자→전원) | N-1 (1회) | N-1 (1회) |

## 폴더 구조와 담당

```
src/dp2_nparty/
  domain.py          후보·프로파일·세션 결과 자료형
  ufun_provider.py   ★ Ufun 자리 — 인터페이스 확정, 구현은 별도 담당자 작업 예정
  benchmark.py       ★ 벤치마크 셋 로더 자리 — 규격은 data/benchmark/README.md
  threshold.py       바퀴 단위 revised threshold (negmas PolyAspiration 래퍼)
  tiebreak.py        동률 해소 플러그인 (registry 방식 — 교체 가능)
  blackboard.py      Blackboard 상태 + 메시지 카운터 (위 매핑 표 구현)
  protocol.py        공통 라운드/바퀴 루프 + Plan1Vote + Plan2Cumulative
  measures/
    fc.py            [24] Total Utility 달성률·별점 (x*, 무작위 베이스라인 R̄)
    scaling.py       [25] 확장 지수 회귀(b, 95% CI, R²)·완결률 게이트·별점 — 참여자 수/의제 수 공용
    ru_memory.py     [21 §21.3-8] 피크 메모리 측정 (tracemalloc)
    confidentiality.py [21 §21.3-9] frequency 공격자 — 관점별(참여자/담당자) 역추론 이득
  harness.py         시드 관리·세션 러너·실험 매트릭스
data/benchmark/      ★ 벤치마크 셋 데이터 자리 (별도 담당자)
tests/test_smoke.py  end-to-end 스모크 (개발용 임시 Ufun 사용)
```

★ = 다른 팀원이 작업 중인 자리 — 인터페이스만 고정해 두었고, 구현이 오면 갈아끼운다.
그 전까지 하니스는 `ufun_provider.TableUfun`(개발용 임시)으로 동작한다.

## 측정하는 QA (5종)

| QA | 지표 | 정의 문서 |
|---|---|---|
| Functional Correctness | Total Utility 달성률 → 별점 0-5 | [`24`](../../docs/changbae/24-Functional-Correctness-정의-측정.md) |
| Scalability-참여자 수 | 메시지 확장 지수 b_msg → 별점 0-5 (N ∈ {3,4,5,6,8,10}) | [`25`](../../docs/changbae/25-Scalability-참여자수-정의-측정.md) |
| Scalability-의제 수 | 조합-메모리 탄력성 c (의제 조합 스윕) | [`21`](../../docs/changbae/21-핵심-QA-측정-정의.md) §21.3-5 |
| Resource Utilization-메모리 | 협상 1회 피크 추가 메모리 | [`21`](../../docs/changbae/21-핵심-QA-측정-정의.md) §21.3-8 (PoC에서는 프로세스 메모리로 대체 측정) |
| Confidentiality | 역추론 이득 (frequency 공격자 — 자체 구현: negmas 클래스는 SAO/GB 결합형이라 동일 원리를 관찰 이벤트 위에 재구현, 규칙은 `measures/confidentiality.py`에 고정·명문화) | [`21`](../../docs/changbae/21-핵심-QA-측정-정의.md) §21.3-9 |
| Time Behaviour (보조) | ENV-A 대체 지표 = **직렬 통신 단계(phase) 수** — 방안별 라운드 구성이 달라(방안1 4단계/방안2 1단계) 라운드 수만으로는 비교가 왜곡됨. 정본 지표(오버헤드 비율)는 실기기 소관 | [`21`](../../docs/changbae/21-핵심-QA-측정-정의.md) §21.3-6 |

비교 원칙: 두 방안에 **동일 프로파일·동일 시드**를 주고 방안만 교체한다.
