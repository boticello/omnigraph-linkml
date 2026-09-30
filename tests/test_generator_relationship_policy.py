from __future__ import annotations

from pathlib import Path

import pytest

from linkml_omnigraph.generator import OmnigraphGenerator, OmnigraphGeneratorError
from tests.conftest import write_schema


def test_native_edge_relationship_uses_header_endpoints_not_body_properties(
    tmp_path: Path, schema_prelude: str
) -> None:
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
  Organisation:
    annotations:
      kind: entity
    attributes:
      org_id:
        range: string
        identifier: true
        required: true
  Employment:
    annotations:
      kind: relationship
      og_from_role: employee
      og_to_role: employer
    attributes:
      employee:
        range: Person
        required: true
        annotations:
          role: employee
      employer:
        range: Organisation
        required: true
        annotations:
          role: employer
      since:
        range: date
""",
    )

    generated = OmnigraphGenerator(schema).serialize()

    assert "edge Employment: Person -> Organisation {" in generated
    assert "  since: Date?" in generated
    assert "  employee:" not in generated
    assert "  employer:" not in generated


@pytest.mark.parametrize(
    "unique_key_slots",
    [
        ["source", "target", "since"],
        ["relationship_code"],
    ],
)
def test_rejects_relationship_unique_keys_in_native_edge_mode(
    tmp_path: Path, schema_prelude: str, unique_key_slots: list[str]
) -> None:
    unique_key_slot_lines = "\n".join(f"          - {slot}" for slot in unique_key_slots)
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
    unique_keys:
      link_identity:
        unique_key_slots:
{unique_key_slot_lines}
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
      since:
        range: date
      relationship_code:
        range: string
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match="required scalar String|both endpoint slots"):
        OmnigraphGenerator(schema).serialize()


def test_edge_property_unique_remains_supported_for_single_emitted_property(
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
      relationship_code:
        range: string
        annotations:
          unique: true
""",
    )

    generated = OmnigraphGenerator(schema).serialize()

    assert "edge Link: Thing -> Thing {" in generated
    assert "  relationship_code: String?" in generated
    assert "  @unique(relationship_code)" in generated


def test_rejects_nary_relationship_even_when_two_roles_define_direction(
    tmp_path: Path, schema_prelude: str
) -> None:
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
  Organisation:
    annotations:
      kind: entity
    attributes:
      org_id:
        range: string
        identifier: true
        required: true
  Policy:
    annotations:
      kind: entity
    attributes:
      policy_id:
        range: string
        identifier: true
        required: true
  InsuranceObligation:
    annotations:
      kind: relationship
      og_from_role: employer
      og_to_role: employee
    attributes:
      employer:
        range: Organisation
        required: true
        annotations:
          role: employer
      employee:
        range: Person
        required: true
        annotations:
          role: employee
      policy:
        range: Policy
        required: true
        annotations:
          role: policy
      since:
        range: date
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match="N-ary relationships require"):
        OmnigraphGenerator(schema).serialize()


def test_rejects_class_valued_non_role_participant_in_relationship(
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
      context:
        range: Thing
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match="is class-valued but is not one of the two projected endpoints"):
        OmnigraphGenerator(schema).serialize()


@pytest.mark.parametrize("multivalued", ["", "        multivalued: true\n"])
def test_rejects_entity_class_valued_slots_instead_of_deriving_edges(
    tmp_path: Path, schema_prelude: str, multivalued: str
) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        f"""
classes:
  Person:
    annotations:
      kind: entity
    attributes:
      person_id:
        range: string
        identifier: true
        required: true
      manager:
        range: Person
{multivalued}
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match="explicit kind: relationship"):
        OmnigraphGenerator(schema).serialize()
