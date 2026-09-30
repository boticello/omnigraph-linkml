from __future__ import annotations

from pathlib import Path

import pytest

from linkml_omnigraph.generator import OmnigraphGenerator, OmnigraphGeneratorError
from tests.conftest import LINKML_FIXTURES, write_schema


def test_current_names_cover_all_emitted_declaration_kinds() -> None:
    generated = OmnigraphGenerator(LINKML_FIXTURES / "current_names.yaml").serialize()
    assert "interface Identified {\n  id: String" in generated
    assert "node Record implements Identified" in generated
    assert "edge Link: Record -> Record" in generated
    assert "node Association {\n  id: String" in generated
    assert "@key(id)" in generated
    assert "  from: String?" in generated and "  to: String?" in generated
    # Record inherits id through implements rather than duplicating its body.
    assert generated.count("  id: String") == 3
    assert generated.count("  src: String?") == 3
    assert generated.count("  dst: String?") == 3


@pytest.mark.parametrize("kind", ["entity", "interface", "relationship", "reified"])
@pytest.mark.parametrize("name", ["id", "src", "dst", "from", "to", "_private", "_rowid", "_score", "_distance"])
def test_property_names_follow_emitted_kind(tmp_path: Path, schema_prelude: str, kind: str, name: str) -> None:
    relationship = kind in {"relationship", "reified"}
    annotations = "kind: relationship, og_relationship_mode: reified" if kind == "reified" else f"kind: {kind}"
    endpoints = """      source:
        range: Record
        required: true
        annotations: {role: source}
      target:
        range: Record
        required: true
        annotations: {role: target}
""" if relationship else ""
    # Reification still requires identity, independently of the sampled property.
    identity = "      slug: {range: string, required: true, identifier: true}\n" if kind == "reified" else ""
    schema = write_schema(tmp_path / "schema.yaml", schema_prelude, f"""classes:
  Record:
    annotations: {{kind: entity}}
    attributes:
      slug: {{range: string, required: true, identifier: true}}
  Sample:
    annotations: {{{annotations}}}
    attributes:
{endpoints}{identity}      {name}: {{range: string}}
""")
    if name.startswith("_") or (kind == "relationship" and name in {"from", "to"}):
        with pytest.raises(OmnigraphGeneratorError, match="property identifier|reserved Omnigraph edge property"):
            OmnigraphGenerator(schema).serialize()
    else:
        assert f"  {name}: String?" in OmnigraphGenerator(schema).serialize()


def test_accepts_valid_type_property_and_enum_tokens(tmp_path: Path, schema_prelude: str) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        """
enums:
  AuthStatus:
    permissible_values:
      active-state:
      2fa_ready:
classes:
  Person_Record2:
    annotations:
      kind: entity
    attributes:
      person_id2:
        range: string
        identifier: true
        required: true
      givenName:
        range: string
      auth_status:
        range: AuthStatus
  WorksFor2:
    annotations:
      kind: relationship
      og_from_role: employee
      og_to_role: employer
    attributes:
      employee:
        range: Person_Record2
        required: true
        annotations:
          role: employee
      employer:
        range: Person_Record2
        required: true
        annotations:
          role: employer
      relationship_code:
        range: string
""",
    )

    generated = OmnigraphGenerator(schema).serialize()

    assert "node Person_Record2 {" in generated
    assert "  givenName: String?" in generated
    assert "  auth_status: enum(active-state, 2fa_ready)?" in generated
    assert "edge WorksFor2: Person_Record2 -> Person_Record2 {" in generated


@pytest.mark.parametrize(
    ("class_name", "message"),
    [
        ("person", "valid Omnigraph type identifier"),
        ("Person-Record", "valid Omnigraph type identifier"),
        ("9Person", "valid Omnigraph type identifier"),
        ("Café", "valid Omnigraph type identifier"),
    ],
)
def test_rejects_invalid_class_identifiers(
    tmp_path: Path, schema_prelude: str, class_name: str, message: str
) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        f"""
classes:
  {class_name}:
    annotations:
      kind: entity
    attributes:
      person_id:
        range: string
        identifier: true
        required: true
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match=message):
        OmnigraphGenerator(schema).serialize()


@pytest.mark.parametrize(
    ("slot_name", "message"),
    [
        ("GivenName", "valid Omnigraph property identifier"),
        ("given-name", "valid Omnigraph property identifier"),
        ("9name", "valid Omnigraph property identifier"),
        ("café", "valid Omnigraph property identifier"),
        ("_private", "valid Omnigraph property identifier"),
        ("_rowid", "valid Omnigraph property identifier"),
        ("_score", "valid Omnigraph property identifier"),
        ("_distance", "valid Omnigraph property identifier"),
    ],
)
def test_rejects_invalid_or_reserved_node_property_identifiers(
    tmp_path: Path, schema_prelude: str, slot_name: str, message: str
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
      {slot_name}:
        range: string
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match=message):
        OmnigraphGenerator(schema).serialize()


@pytest.mark.parametrize("slot_name", ["from", "to"])
def test_rejects_reserved_edge_storage_property_identifiers(
    tmp_path: Path, schema_prelude: str, slot_name: str
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
  Link:
    annotations:
      kind: relationship
      og_from_role: source
      og_to_role: target
    attributes:
      source:
        range: Person
        required: true
        annotations:
          role: source
      target:
        range: Person
        required: true
        annotations:
          role: target
      {slot_name}:
        range: string
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match="reserved Omnigraph edge property name"):
        OmnigraphGenerator(schema).serialize()


@pytest.mark.parametrize("enum_value", ["in progress", "Café"])
def test_rejects_invalid_enum_values(tmp_path: Path, schema_prelude: str, enum_value: str) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        f"""
enums:
  Status:
    permissible_values:
      {enum_value}:
classes:
  Person:
    annotations:
      kind: entity
    attributes:
      person_id:
        range: string
        identifier: true
        required: true
      status:
        range: Status
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match="unsupported Omnigraph enum values"):
        OmnigraphGenerator(schema).serialize()
