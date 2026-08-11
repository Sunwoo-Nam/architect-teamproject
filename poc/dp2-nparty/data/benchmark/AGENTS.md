# AGENTS.md

## 목적과 범위

- 이 폴더는 다자 합의 프로토콜 PoC가 공통으로 사용하는 정적 Benchmark Set을 보관한다.
- 작업 범위는 테스트 케이스 스키마, 정적 케이스 파일, 데이터 설명과 정합성 검증 기준이다.
- 협상 프로토콜, 라운드 실행, threshold tactic, NegMAS 연동, 측정기 구현은 이 폴더의 책임이 아니다.

## 근거 문서

- 프로토콜 의미는 `docs/changbae/51-설계후보1-다자-합의-프로토콜.md`를 따른다.
- Functional Correctness 사례 구성은 `docs/changbae/24-Functional-Correctness-정의-측정.md`를 따른다.
- 참여자 수 Scalability 사례 구성은 `docs/changbae/25-Scalability-참여자수-정의-측정.md`를 따른다.
- 근거 문서 사이에 모순이나 미정 사항이 있으면 임의로 확정하지 않고 사용자에게 확인한다.
- 이름이 `_legacy`로 끝나는 폴더는 별도 지시 없이 읽거나 참조하지 않는다.

## 작성 원칙

- 문서와 설명은 한글로 작성한다.
- 케이스 1건은 독립된 JSON 파일 하나로 정의한다.
- 후보 ID와 참여자 ID는 문자열을 사용한다.
- utility와 initial threshold는 0 이상 1 이하로 정의한다.
- revised threshold, 최대 바퀴, 동률 해소 규칙은 케이스 파일에 넣지 않는다.
- 특정 프로토콜 방안의 실행 결과를 정답으로 미리 기록하지 않는다.
- 직접 작성한 정적 케이스에는 불필요한 seed나 생성 메타데이터를 넣지 않는다.
- 생성하지 않은 값이나 출처를 추측해 기록하지 않는다.

## 정합성 기준

- case ID는 Benchmark Set 전체에서 유일해야 한다.
- 후보 ID와 참여자 ID는 케이스 안에서 유일해야 한다.
- 참여자는 3명 이상이어야 한다.
- 모든 참여자는 모든 후보에 대한 utility를 가져야 한다.
- 후보 목록과 utility map에 예약어 `NO_DEAL`을 포함하지 않는다.
- `expected_no_deal`을 기록했다면 initial threshold 기준 계산 결과와 일치해야 한다.
- Scalability family는 참여자 수 외의 난이도 조건이 의도대로 유지되는지 확인한다.

## 책임 분리

- Benchmark Set은 `candidates`, 참여자별 `utilities`, `initial_threshold`, 사례 분류 메타데이터만 제공한다.
- 유효 후보, 최적 후보, 결렬 utility, Total Utility 달성률은 PoC 측정기가 입력값으로부터 계산한다.
- JSON 파일을 `BenchmarkCase`와 `Profile`로 변환하는 로더는 기존 `BenchmarkLoader` 인터페이스를 따른다.
- 라운드별 후보 제출, 투표, 누적 제안, 합의와 결렬 판정은 동료 PoC가 담당한다.

## 변경 관리

- 스키마를 변경하기 전에 변경 이유와 기존 케이스에 미치는 영향을 제안하고 승인을 받는다.
- 대량 케이스를 작성하기 전에 대표 케이스를 먼저 검토받는다.
- 이 폴더 밖의 동료 PoC 코드는 별도 요청 없이 수정하지 않는다.
- 작업 완료 후 변경 파일, 검증 결과, 근거 문서를 보고한다.
