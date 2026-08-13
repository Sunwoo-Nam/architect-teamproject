"""실험 실행 환경의 파이썬 버전 고정 — README 「파이썬은 3.14로 고정한다」의 강제 장치.

버전이 실제로 수치를 바꾼다 (2026-08-13 실측, 00-설계안 §13-8):

- **RU-메모리**: tracemalloc이 재는 것은 파이썬 객체의 실제 바이트 수라, 인터프리터가
  다르면 객체 크기부터 다르다 — 3.11 vs 3.14에서 5~10% 차이 실측. 코드로 제거할 수
  없는 버전 의존이다.
- **SC-의제 c**: 위 메모리에서 회귀하므로 함께 흔들린다.
- **FC**: 총효용 합산이 1 ULP 달라지면 x* 선택이 뒤집힐 수 있다 (실제 전례 —
  README). 현행 벤치마크에서는 3.11/3.14가 동일했으나 원리상 위험이 남는다.

선언만으로는 지켜지지 않았다 — 고정 명시 후에도 실행 8건 중 5건이 3.11이었다.
그래서 **실험 진입점이 검사**한다. 테스트(pytest)는 막지 않는다 — 테스트는 발표
수치가 아니고, 어느 버전에서든 로직이 통과해야 오히려 정상이다.
"""
from __future__ import annotations

import sys

#: 실험 실행이 요구하는 (major, minor). 패치 버전은 묻지 않는다.
REQUIRED = (3, 14)


def require(allow_mismatch: bool = False) -> None:
    """버전이 REQUIRED와 다르면 실행을 중단한다.

    `allow_mismatch=True`(실험의 `--allow-python-mismatch`)로만 우회할 수 있고,
    우회해도 경고는 남는다 — 그 실행의 meta.json에 기록된 버전으로 구분한다.
    """
    actual = sys.version_info[:2]
    if actual == REQUIRED:
        return
    msg = (
        f"파이썬 {REQUIRED[0]}.{REQUIRED[1]} 고정 (README) — 현재 "
        f"{actual[0]}.{actual[1]} ({sys.executable})\n"
        "RU-메모리·SC-의제 c가 인터프리터 버전에 의존해, 버전이 섞이면 실행 간 "
        "비교가 무너진다. python3.14로 만든 .venv에서 실행할 것.\n"
        "의도적 예외라면 --allow-python-mismatch (수치는 판정에 쓰지 말 것)."
    )
    if allow_mismatch:
        print(f"[경고] {msg}", file=sys.stderr)
        return
    raise SystemExit(msg)
