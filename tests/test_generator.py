from __future__ import annotations

import pytest

from linkml_omnigraph.generator import OmnigraphGenerator, OmnigraphGeneratorError
from tests.conftest import write_schema

ROOT = __import__("pathlib").Path(__file__).parent


def test_generates_basic_schema_fixture() -> None:
    schema = ROOT / "fixtures" / "linkml" / "basic.yaml"
    expected = (ROOT / "fixtures" / "omnigraph" / "basic.pg").read_text(encoding="utf-8")

    assert OmnigraphGenerator(schema).serialize() == expected


def test_conventional_source_target_roles_define_direction(tmp_path, schema_prelude: str) -> None:
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
    )

    assert "edge Link: Thing -> Thing" in OmnigraphGenerator(schema).serialize()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            """
  Address:
    annotations:
      kind: embedded
""",
            "kind: embedded",
        ),
        (
            """
  Person:
    annotations:
      kind: entity
    attributes:
      friend:
        range: Person
""",
            "explicit kind: relationship",
        ),
        (
            """
  Person:
    annotations:
      kind: entity
    attributes:
      person_id:
        range: string
        identifier: true
        required: true
  Employment:
    annotations:
      kind: relationship
    attributes:
      employee:
        range: Person
        required: true
        annotations:
          role: employee
      employer:
        range: Person
        required: true
        annotations:
          role: employer
""",
            "ambiguous direction",
        ),
        (
            """
  Event:
    annotations:
      kind: entity
    attributes:
      starts:
        range: time
""",
            "range time",
        ),
    ],
)
def test_rejects_unsupported_constructs(tmp_path, schema_prelude: str, body: str, message: str) -> None:
    schema = write_schema(tmp_path / "schema.yaml", schema_prelude, f"classes:\n{body}")

    with pytest.raises(OmnigraphGeneratorError, match=message):
        OmnigraphGenerator(schema).serialize()
