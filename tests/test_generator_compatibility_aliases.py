from __future__ import annotations

from pathlib import Path

import pytest

from linkml_omnigraph.generator import OmnigraphGenerator, OmnigraphGeneratorError
from tests.conftest import write_schema


@pytest.mark.parametrize(
    "range_name",
    [
        "normalized_string",
        "token",
        "ncname",
        "uriorcurie",
        "curie",
        "bool",
        "int",
        "long",
        "positive_integer",
        "non_negative_integer",
        "bytes",
    ],
)
def test_rejects_compatibility_only_alias_types(
    tmp_path: Path, schema_prelude: str, range_name: str
) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        f"""
classes:
  Thing:
    annotations:
      kind: entity
    attributes:
      thing_id:
        range: string
        identifier: true
        required: true
      value:
        range: {range_name}
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match="compatibility-only datatype alias"):
        OmnigraphGenerator(schema).serialize()
