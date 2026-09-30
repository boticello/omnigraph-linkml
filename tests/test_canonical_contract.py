from __future__ import annotations

import re
from pathlib import Path

import yaml


def test_canonical_supported_types_fixture_uses_only_canonical_names() -> None:
    root = Path(__file__).parent
    canonical_doc = (root.parent / "README.package.md").read_text(encoding="utf-8")
    fixture = yaml.safe_load((root / "fixtures" / "linkml" / "supported_types.yaml").read_text(encoding="utf-8"))

    section = canonical_doc.split("Canonical scalar datatype names are:", 1)[1].split("Inline enums", 1)[0]
    canonical_names = set(re.findall(r"- `([^`]+)`", section))

    attributes = fixture["classes"]["Example"]["attributes"]
    used_ranges = {slot["range"] for slot in attributes.values() if "range" in slot}
    enum_names = set(fixture.get("enums", {}).keys())

    assert used_ranges - enum_names <= canonical_names


def test_canonical_fixture_excludes_compatibility_only_aliases() -> None:
    root = Path(__file__).parent
    fixture = yaml.safe_load((root / "fixtures" / "linkml" / "supported_types.yaml").read_text(encoding="utf-8"))
    attributes = fixture["classes"]["Example"]["attributes"]
    used_ranges = {slot["range"] for slot in attributes.values() if "range" in slot}

    for alias in [
        "int",
        "long",
        "bool",
        "positive_integer",
        "non_negative_integer",
        "token",
        "bytes",
        "normalized_string",
        "ncname",
        "uriorcurie",
        "curie",
    ]:
        assert alias not in used_ranges
