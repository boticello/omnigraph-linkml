from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
LINKML_FIXTURES = FIXTURES / "linkml"
OMNIGRAPH_FIXTURES = FIXTURES / "omnigraph"

SUPPORTED_OMNIGRAPH_VERSION = "omnigraph 0.11.0"


def pytest_sessionstart(session: pytest.Session) -> None:
    """Qualification must never turn a missing backend into skipped tests."""
    required = os.environ.get("OMNIGRAPH_REQUIRE_INTEGRATION") == "1" or os.environ.get("CI") == "true"
    if not required:
        return
    binary = shutil.which("omnigraph")
    if binary is None:
        raise pytest.UsageError("Omnigraph 0.11.0 is required for integration qualification; CLI is missing")
    try:
        result = subprocess.run([binary, "--version"], capture_output=True, text=True, check=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        raise pytest.UsageError(f"Cannot verify required Omnigraph CLI: {error}") from error
    if result.stdout.strip() != SUPPORTED_OMNIGRAPH_VERSION:
        raise pytest.UsageError(f"Required {SUPPORTED_OMNIGRAPH_VERSION}; found {result.stdout.strip()!r}")


@pytest.fixture
def schema_prelude() -> str:
    return """id: https://example.org/test
name: test
prefixes:
  linkml: https://w3id.org/linkml/
  test: https://example.org/test/
default_prefix: test
imports:
  - linkml:types
"""


def write_schema(path: Path, prelude: str, body: str) -> Path:
    path.write_text(f"{prelude}\n{body.lstrip()}", encoding="utf-8")
    return path
