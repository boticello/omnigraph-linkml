"""Reachable missing/wrong CLI cases for the CI qualification gate."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests import conftest


@pytest.mark.parametrize("version", [None, "omnigraph 0.7.2", "omnigraph 0.10.0", "omnigraph 0.11.1", "omnigraph 0.11.0"])
@pytest.mark.parametrize("trigger", ["CI", "OMNIGRAPH_REQUIRE_INTEGRATION"])
def test_qualification_requires_exact_available_backend(monkeypatch, version, trigger):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("OMNIGRAPH_REQUIRE_INTEGRATION", raising=False)
    monkeypatch.setenv(trigger, "true" if trigger == "CI" else "1")
    monkeypatch.setattr(conftest.shutil, "which", lambda _: "/fake/omnigraph" if version else None)
    monkeypatch.setattr(conftest.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, version + "\n", ""))
    if version == "omnigraph 0.11.0":
        conftest.pytest_sessionstart(None)
    else:
        with pytest.raises(pytest.UsageError, match="required|Required"):
            conftest.pytest_sessionstart(None)


@pytest.mark.parametrize("version", [None, "omnigraph 0.10.0"])
def test_required_gate_stops_real_pytest_before_integration_skips(tmp_path: Path, version: str | None) -> None:
    if version:
        binary = tmp_path / "omnigraph"
        binary.write_text(f"#!/bin/sh\nprintf '%s\\n' '{version}'\n", encoding="utf-8")
        binary.chmod(0o755)
    environment = dict(os.environ, PATH=str(tmp_path), OMNIGRAPH_REQUIRE_INTEGRATION="1")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_omnigraph_integration.py", "-q"],
        cwd=Path(__file__).resolve().parents[1], env=environment, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 4, result.stdout + result.stderr
    assert "required" in result.stderr.lower()
    assert "skipped" not in result.stdout
