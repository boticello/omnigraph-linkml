#!/usr/bin/env python3
"""Regenerate per-fixture Omnigraph ``.pg`` artefacts into ``generated/``.

The source fixtures under ``tests/fixtures/linkml/*.yaml`` are the canonical
inputs. This script lowers each one to ``generated/<stem>.pg`` so the
documentation and manual validation commands operate on output that mirrors the
fixtures the test suite exercises. The ``generated/`` directory is gitignored;
artefacts are reproducible scratch output, not tracked golden files.

Usage::

    python scripts/generate_artifacts.py

Run it whenever you need fresh ``.pg`` output for the documented
``omnigraph init`` / ``omnigraph lint`` verification snippets.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a script without installing the package: add ``src`` to the
# path so ``linkml_omnigraph`` resolves in a plain checkout.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from linkml_omnigraph.generator import OmnigraphGenerator, OmnigraphGeneratorError  # noqa: E402

LINKML_FIXTURES = ROOT / "tests" / "fixtures" / "linkml"
OUTPUT_DIR = ROOT / "generated"


def main() -> int:
    sources = sorted(LINKML_FIXTURES.glob("*.yaml"))
    if not sources:
        print(f"no LinkML fixtures found under {LINKML_FIXTURES}", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[tuple[str, str]] = []
    written: list[Path] = []
    for source in sources:
        try:
            text = OmnigraphGenerator(source).serialize()
        except OmnigraphGeneratorError as exc:
            failures.append((source.name, str(exc)))
            continue
        output = OUTPUT_DIR / f"{source.stem}.pg"
        output.write_text(text, encoding="utf-8")
        written.append(output)

    for output in written:
        print(f"generated {output.relative_to(ROOT)}")

    if failures:
        print("\nthe following fixtures failed to generate (expected for rejection fixtures):", file=sys.stderr)
        for name, message in failures:
            print(f"  {name}: {message}", file=sys.stderr)

    print(f"\nwrote {len(written)} artefact(s) to {OUTPUT_DIR.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
