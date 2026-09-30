from __future__ import annotations

from pathlib import Path

import pytest

from linkml_omnigraph.generator import OmnigraphGenerator, OmnigraphGeneratorError
from tests.conftest import write_schema


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            """
classes:
  Person:
    attributes:
      entity_id:
        range: string
""",
            "missing required annotation kind",
        ),
        (
            """
classes:
  Person:
    annotations:
      kind: widget
""",
            "unsupported kind",
        ),
        (
            """
classes:
  Thing:
    annotations:
      kind: entity
    attributes:
      entity_id:
        range: string
        identifier: true
        required: true
  Link:
    annotations:
      kind: relationship
    attributes:
      from_thing:
        range: Thing
        required: true
        annotations:
          role: from
""",
            "native-edge mode requires exactly two",
        ),
        (
            """
classes:
  Thing:
    annotations:
      kind: entity
    attributes:
      entity_id:
        range: string
        identifier: true
        required: true
  Link:
    annotations:
      kind: relationship
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
      reviewer:
        range: Thing
        required: true
        annotations:
          role: reviewer
""",
            "native-edge mode requires exactly two",
        ),
        (
            """
classes:
  Thing:
    annotations:
      kind: entity
    attributes:
      entity_id:
        range: string
        identifier: true
        required: true
  Link:
    annotations:
      kind: relationship
    attributes:
      source:
        range: Thing
        multivalued: true
        annotations:
          role: source
      target:
        range: Thing
        required: true
        annotations:
          role: target
""",
            "multivalued",
        ),
        (
            """
classes:
  Shape:
    annotations:
      kind: interface
    attributes:
      label:
        range: string
  Link:
    annotations:
      kind: relationship
    attributes:
      source:
        range: Shape
        required: true
        annotations:
          role: source
      target:
        range: Shape
        required: true
        annotations:
          role: target
""",
            "does not resolve to an entity node",
        ),
        (
            """
classes:
  AbstractThing:
    abstract: true
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
    attributes:
      source:
        range: AbstractThing
        required: true
        annotations:
          role: source
      target:
        range: AbstractThing
        required: true
        annotations:
          role: target
""",
            "abstract endpoint ranges are unsupported",
        ),
        (
            """
classes:
  Thing:
    annotations:
      kind: entity
    attributes:
      entity_id:
        range: string
        identifier: true
        required: true
  Link:
    annotations:
      kind: relationship
      og_from_role: source
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
""",
            "must set both og_from_role and og_to_role",
        ),
        (
            """
classes:
  Thing:
    annotations:
      kind: entity
    attributes:
      entity_id:
        range: string
        identifier: true
        required: true
  Link:
    annotations:
      kind: relationship
      og_from_role: source
      og_to_role: source
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
""",
            "same role",
        ),
        (
            """
classes:
  Thing:
    annotations:
      kind: entity
    attributes:
      entity_id:
        range: string
        identifier: true
        required: true
  Link:
    annotations:
      kind: relationship
      og_from_role: missing
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
""",
            "does not match endpoint roles",
        ),
        (
            """
classes:
  Thing:
    annotations:
      kind: entity
    attributes:
      entity_id:
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
        identifier: true
        annotations:
          role: source
      target:
        range: Thing
        required: true
        annotations:
          role: target
""",
            "endpoint slot source cannot be an identifier",
        ),
        (
            """
classes:
  Thing:
    annotations:
      kind: entity
    attributes:
      entity_id:
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
      link_id:
        range: string
        identifier: true
""",
            "edge identity is deferred",
        ),
        (
            """
classes:
  Thing:
    annotations:
      kind: entity
    attributes:
      entity_id:
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
      extra:
        range: Thing
""",
            "is class-valued but is not one of the two projected endpoints",
        ),
        (
            """
classes:
  Vectorised:
    annotations:
      kind: entity
    attributes:
      entity_id:
        range: string
        identifier: true
        required: true
      embedding:
        range: float
        annotations:
          index: vector
""",
            "is not a Vector",
        ),
        (
            """
classes:
  Vectorised:
    annotations:
      kind: entity
    attributes:
      entity_id:
        range: string
        identifier: true
        required: true
      embedding:
        range: float
        multivalued: true
        annotations:
          vector_dimensions: 0
""",
            "invalid vector_dimensions",
        ),
        (
            """
classes:
  Vectorised:
    annotations:
      kind: entity
    attributes:
      entity_id:
        range: string
        identifier: true
        required: true
      text:
        range: string
      embedding:
        range: float
        annotations:
          og_embed_source: text
""",
            "is not a Vector",
        ),
        (
            """
classes:
  Vectorised:
    annotations:
      kind: entity
    attributes:
      entity_id:
        range: string
        identifier: true
        required: true
      embedding:
        range: float
        multivalued: true
        annotations:
          vector_dimensions: 3
          og_embed_source: missing
""",
            "missing source slot",
        ),
        (
            """
classes:
  Vectorised:
    annotations:
      kind: entity
    attributes:
      entity_id:
        range: string
        identifier: true
        required: true
      rank:
        range: integer
      embedding:
        range: float
        multivalued: true
        annotations:
          vector_dimensions: 3
          og_embed_source: rank
""",
            "is not a String property",
        ),
        (
            """
enums:
  Status:
    permissible_values:
      active:
      inactive:
classes:
  Thing:
    annotations:
      kind: entity
    attributes:
      entity_id:
        range: string
        identifier: true
        required: true
      statuses:
        range: Status
        multivalued: true
""",
            "multivalued enum",
        ),
    ],
)
def test_rejects_documented_unsupported_constructs(tmp_path: Path, schema_prelude: str, body: str, message: str) -> None:
    schema = write_schema(tmp_path / "schema.yaml", schema_prelude, body)

    with pytest.raises(OmnigraphGeneratorError, match=message):
        OmnigraphGenerator(schema).serialize()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
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
      code:
        range: string
        unique: true
""",
            "slot attribute 'unique'",
        ),
        (
            """
classes:
  Thing:
    annotations:
      kind: entity
    bogus: true
    attributes:
      thing_id:
        range: string
        identifier: true
        required: true
""",
            "class attribute 'bogus'",
        ),
    ],
)
def test_rejects_unknown_linkml_attributes_with_a_clean_diagnostic(
    tmp_path: Path, schema_prelude: str, body: str, message: str
) -> None:
    schema = write_schema(tmp_path / "schema.yaml", schema_prelude, body)

    # These are rejected at construction time, before serialisation runs.
    with pytest.raises(OmnigraphGeneratorError, match=message):
        OmnigraphGenerator(schema)

