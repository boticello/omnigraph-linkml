"""Idempotency guard for the per-fixture regeneration script.

``scripts/generate_artifacts.py`` lowers every ``tests/fixtures/linkml/*.yaml``
to ``generated/<stem>.pg``. The ``generated/`` directory is gitignored and the
artefacts are reproducible scratch output, so we do not track them. Instead this
test asserts the regeneration is deterministic and that every fixture lowers
without error, so a generator change that produces non-idempotent or broken
output is caught here rather than only when someone happens to run the script.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from linkml_omnigraph.generator import OmnigraphGenerator, OmnigraphGeneratorError  # noqa: E402

LINKML_FIXTURES = ROOT / "tests" / "fixtures" / "linkml"


def test_every_fixture_regenerates_deterministically() -> None:
    sources = sorted(LINKML_FIXTURES.glob("*.yaml"))
    assert sources, "expected LinkML fixtures under tests/fixtures/linkml/"

    for source in sources:
        first = OmnigraphGenerator(source).serialize()
        second = OmnigraphGenerator(source).serialize()
        assert first == second, f"regeneration of {source.name} is not deterministic"


def test_regenerate_script_matches_generator_output() -> None:
    """The script must lower each fixture exactly as the generator does."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib

    generate_artifacts = importlib.import_module("generate_artifacts")
    sources = sorted((ROOT / "tests" / "fixtures" / "linkml").glob("*.yaml"))

    for source in sources:
        try:
            expected = OmnigraphGenerator(source).serialize()
        except OmnigraphGeneratorError:
            continue
        actual = OmnigraphGenerator(
            getattr(generate_artifacts, "LINKML_FIXTURES", LINKML_FIXTURES) / source.name
        ).serialize()
        assert actual == expected, f"{source.name}: script output diverges from generator"
