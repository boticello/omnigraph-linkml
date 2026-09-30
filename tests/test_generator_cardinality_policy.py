from __future__ import annotations

from pathlib import Path

import pytest

from linkml_omnigraph.generator import OmnigraphGenerator, OmnigraphGeneratorError
from tests.conftest import write_schema


@pytest.mark.parametrize(
    "endpoint_shape",
    [
        """
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
""",
        """
      source:
        range: Thing
        minimum_cardinality: 1
        annotations:
          role: source
      target:
        range: Thing
        exact_cardinality: 1
        annotations:
          role: target
""",
    ],
)
def test_accepts_exact_one_endpoint_participation(
    tmp_path: Path, schema_prelude: str, endpoint_shape: str
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
  Link:
    annotations:
      kind: relationship
      og_from_role: source
      og_to_role: target
    attributes:
{endpoint_shape}      code:
        range: string
""",
    )

    generated = OmnigraphGenerator(schema).serialize()

    assert "edge Link: Thing -> Thing {" in generated
    assert "@card(" not in generated


@pytest.mark.parametrize(
    ("endpoint_shape", "message"),
    [
        (
            """
      source:
        range: Thing
        annotations:
          role: source
      target:
        range: Thing
        required: true
        annotations:
          role: target
""",
            "must describe exactly one participant",
        ),
        (
            """
      source:
        range: Thing
        maximum_cardinality: 2
        annotations:
          role: source
      target:
        range: Thing
        required: true
        annotations:
          role: target
""",
            "must describe exactly one participant",
        ),
        (
            """
      source:
        range: Thing
        exact_cardinality: 0
        annotations:
          role: source
      target:
        range: Thing
        required: true
        annotations:
          role: target
""",
            "must describe exactly one participant",
        ),
    ],
)
def test_rejects_endpoint_cardinality_that_cannot_lower_honestly(
    tmp_path: Path, schema_prelude: str, endpoint_shape: str, message: str
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
  Link:
    annotations:
      kind: relationship
      og_from_role: source
      og_to_role: target
    attributes:
{endpoint_shape}      code:
        range: string
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match=message):
        OmnigraphGenerator(schema).serialize()


def test_rejects_explicit_body_slot_cardinality_on_relationship(
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
      code:
        range: string
        exact_cardinality: 1
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match="does not map to Omnigraph edge constraints"):
        OmnigraphGenerator(schema).serialize()
