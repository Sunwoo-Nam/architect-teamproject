"""파이썬 버전 가드 — 선언(README)이 아니라 코드가 지키는지.

가드 자체는 어느 버전에서든 테스트할 수 있어야 하므로, 실제 인터프리터 버전이
아니라 monkeypatch한 버전으로 검사한다.
"""
from __future__ import annotations

import sys

import pytest

from total import pyversion


class TestRequire:
    def test_passes_on_required_version(self, monkeypatch):
        monkeypatch.setattr(sys, "version_info", pyversion.REQUIRED + (0, "final", 0))
        pyversion.require()     # 예외 없음

    def test_patch_version_is_not_checked(self, monkeypatch):
        monkeypatch.setattr(sys, "version_info",
                            pyversion.REQUIRED + (99, "final", 0))
        pyversion.require()     # (3, 14, 99)도 통과 — 패치는 묻지 않는다

    def test_blocks_on_mismatch(self, monkeypatch):
        monkeypatch.setattr(sys, "version_info", (3, 11, 15, "final", 0))
        with pytest.raises(SystemExit):
            pyversion.require()

    def test_mismatch_message_names_both_versions(self, monkeypatch):
        monkeypatch.setattr(sys, "version_info", (3, 11, 15, "final", 0))
        with pytest.raises(SystemExit) as e:
            pyversion.require()
        assert "3.14" in str(e.value) and "3.11" in str(e.value)

    def test_allow_mismatch_warns_but_continues(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "version_info", (3, 11, 15, "final", 0))
        pyversion.require(allow_mismatch=True)      # 중단하지 않는다
        assert "경고" in capsys.readouterr().err    # 대신 흔적은 남긴다
