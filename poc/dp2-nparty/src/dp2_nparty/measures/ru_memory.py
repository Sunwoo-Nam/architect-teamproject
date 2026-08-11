"""[21 §21.3-8] Resource Utilization-메모리 — 협상 1회 피크 추가 메모리.

정의 문서는 실기기(ENV-B) 프로파일러 측정이 정본이다. PoC(ENV-A)에서는
tracemalloc으로 파이썬 프로세스의 피크 할당 증가분을 재는 **대체 측정**을 쓰고,
결과 보고 시 대체 측정임을 명시한다. (앱 가용 예산 대비 50% 판정은 실기기 단계 소관)
"""
from __future__ import annotations

import tracemalloc
from typing import Any, Callable


def peak_memory_bytes(run: Callable[[], Any]) -> tuple[Any, int]:
    """run()을 실행하며 피크 추가 메모리(바이트)를 잰다. 반환: (run 결과, 피크 증가분)."""
    tracemalloc.start()
    tracemalloc.reset_peak()
    base, _ = tracemalloc.get_traced_memory()
    try:
        result = run()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, max(0, peak - base)
