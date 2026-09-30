from __future__ import annotations

from pathlib import Path

import pytest

from linkml_omnigraph.generator import OmnigraphGenerator, OmnigraphGeneratorError
from tests.conftest import write_schema


def test_fulltext_index_intent_has_no_node_schema_directive(
    tmp_path: Path, schema_prelude: str
) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        """
classes:
  Document:
    annotations:
      kind: entity
    attributes:
      document_id:
        range: string
        identifier: true
        required: true
      body:
        range: string
        annotations:
          index: fulltext
""",
    )

    generated = OmnigraphGenerator(schema).serialize()

    assert "  body: String?" in generated
    assert "  @index(body)" not in generated


def test_fulltext_index_intent_has_no_edge_schema_directive(
    tmp_path: Path, schema_prelude: str
) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        """
classes:
  Thing:
    annotations:
      kind: entity
    attributes:
      thing_id:
        range: string
        identifier: true
        required: true
  Link:
    annotations:
      kind: relationship
      og_from_role: source
      og_to_role: target
    attributes:
      source:
        range: Thing
        required: true
        annotations:
          role: source
      target:
        range: Thing
        required: true
        annotations:
          role: target
      note:
        range: string
        annotations:
          index: fulltext
""",
    )

    generated = OmnigraphGenerator(schema).serialize()

    assert "  note: String?" in generated
    assert "  @index(note)" not in generated


def test_rejects_fulltext_index_intent_on_non_string_property(
    tmp_path: Path, schema_prelude: str
) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        """
classes:
  Document:
    annotations:
      kind: entity
    attributes:
      document_id:
        range: string
        identifier: true
        required: true
      score:
        range: integer
        annotations:
          index: fulltext
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match="index: fulltext but is not a String property"):
        OmnigraphGenerator(schema).serialize()
