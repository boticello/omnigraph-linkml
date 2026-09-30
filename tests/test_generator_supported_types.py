from __future__ import annotations

from pathlib import Path

from linkml_omnigraph.generator import OmnigraphGenerator
from tests.conftest import write_schema


def test_generates_canonical_supported_scalar_types_fixture() -> None:
    root = Path(__file__).parent
    schema = root / "fixtures" / "linkml" / "supported_types.yaml"
    expected = (root / "fixtures" / "omnigraph" / "supported_types.pg").read_text(encoding="utf-8")

    assert OmnigraphGenerator(schema).serialize() == expected


def test_interface_mixins_and_slots_are_emitted(tmp_path: Path, schema_prelude: str) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        """
slots:
  slug:
    range: string
    identifier: true
    required: true
classes:
  Audited:
    mixin: true
    annotations:
      kind: interface
    attributes:
      created_at:
        range: datetime
  Labelled:
    mixin: true
    annotations:
      kind: interface
    attributes:
      label:
        range: string
        required: true
  Thing:
    slots:
      - slug
    attributes:
      title:
        range: string
        required: true
    mixins:
      - Audited
      - Labelled
    annotations:
      kind: entity
""",
    )

    generated = OmnigraphGenerator(schema).serialize()

    assert "node Thing implements Audited, Labelled {" in generated
    assert "  slug: String" in generated
    assert "  title: String" in generated
    assert "  @key(slug)" in generated


def test_edge_properties_map_required_optional_and_unique(tmp_path: Path, schema_prelude: str) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        """
classes:
  Person:
    annotations:
      kind: entity
    attributes:
      person_id:
        range: string
        identifier: true
        required: true
  Review:
    annotations:
      kind: relationship
      og_from_role: author
      og_to_role: subject
    attributes:
      author:
        range: Person
        required: true
        annotations:
          role: author
      subject:
        range: Person
        required: true
        annotations:
          role: subject
      score:
        range: integer
        required: true
      reference_code:
        range: string
        annotations:
          unique: true
""",
    )

    generated = OmnigraphGenerator(schema).serialize()

    assert "edge Review: Person -> Person {" in generated
    assert "  score: I64" in generated
    assert "  reference_code: String?" in generated
    assert "  @unique(reference_code)" in generated


def test_declarations_are_sorted_deterministically(tmp_path: Path, schema_prelude: str) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        """
classes:
  Zebra:
    annotations:
      kind: entity
    attributes:
      zebra_id:
        range: string
        identifier: true
        required: true
  Ant:
    annotations:
      kind: entity
    attributes:
      ant_id:
        range: string
        identifier: true
        required: true
""",
    )

    generated = OmnigraphGenerator(schema).serialize()

    assert generated.index("node Ant") < generated.index("node Zebra")
