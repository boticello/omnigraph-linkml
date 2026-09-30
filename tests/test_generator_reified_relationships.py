from __future__ import annotations

from pathlib import Path

import pytest

from linkml_omnigraph.generator import OmnigraphGenerator, OmnigraphGeneratorError
from tests.conftest import write_schema


def test_reified_relationship_emits_node_and_incident_role_edges(
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
  Team:
    annotations:
      kind: entity
    attributes:
      team_id:
        range: string
        identifier: true
        required: true
  Membership:
    annotations:
      kind: relationship
      og_relationship_mode: reified
    attributes:
      membership_id:
        range: string
        identifier: true
        required: true
      member:
        range: Person
        required: true
        annotations:
          role: member
      team:
        range: Team
        required: true
        annotations:
          role: team
      joined_on:
        range: date
        required: true
      label:
        range: string
        pattern: "^[a-z]+$"
""",
    )

    generated = OmnigraphGenerator(schema).serialize()

    assert "node Membership {" in generated
    assert "  membership_id: String" in generated
    assert "  joined_on: Date" in generated
    assert "  label: String?" in generated
    assert "  @key(membership_id)" in generated
    assert '  @check(label, "^[a-z]+$")' in generated
    assert "edge MembershipMember: Membership -> Person {}" in generated
    assert "edge MembershipTeam: Membership -> Team {}" in generated
    assert "edge Membership:" not in generated
    assert "  member:" not in generated
    assert "  team:" not in generated


def test_relationships_stay_native_edge_without_explicit_reified_mode(
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
      link_id:
        range: string
        identifier: true
        required: true
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

    with pytest.raises(OmnigraphGeneratorError, match="edge identity is deferred"):
        OmnigraphGenerator(schema).serialize()


def test_reified_relationship_requires_scalar_identifier(
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
      og_relationship_mode: reified
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

    with pytest.raises(OmnigraphGeneratorError, match="must declare exactly one scalar identifier"):
        OmnigraphGenerator(schema).serialize()


def test_reified_relationship_identifier_is_emitted_non_nullable_when_required_is_omitted(
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
      og_relationship_mode: reified
    attributes:
      link_id:
        range: string
        identifier: true
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

    generated = OmnigraphGenerator(schema).serialize()

    assert "  link_id: String\n" in generated
    assert "  @key(link_id)" in generated


def test_reified_relationship_rejects_multiple_scalar_identifiers(
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
      og_relationship_mode: reified
    attributes:
      link_id:
        range: string
        identifier: true
        required: true
      alternate_id:
        range: string
        identifier: true
        required: true
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

    with pytest.raises(OmnigraphGeneratorError, match="declares multiple identifier slots"):
        OmnigraphGenerator(schema)


def test_reified_relationship_rejects_endpoint_identifier(
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
      og_relationship_mode: reified
    attributes:
      source:
        range: Thing
        identifier: true
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

    with pytest.raises(OmnigraphGeneratorError, match="endpoint slot source cannot be an identifier"):
        OmnigraphGenerator(schema).serialize()


def test_reified_relationship_rejects_generated_edge_name_collision(
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
  LinkSource:
    annotations:
      kind: entity
    attributes:
      link_source_id:
        range: string
        identifier: true
        required: true
  Link:
    annotations:
      kind: relationship
      og_relationship_mode: reified
    attributes:
      link_id:
        range: string
        identifier: true
        required: true
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

    with pytest.raises(OmnigraphGeneratorError, match="collides with an existing LinkML class"):
        OmnigraphGenerator(schema).serialize()


def test_reified_relationship_emits_incident_edges_for_nary_roles(
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
      og_relationship_mode: reified
    attributes:
      link_id:
        range: string
        identifier: true
        required: true
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
        required: true
        annotations:
          role: context
""",
    )

    generated = OmnigraphGenerator(schema).serialize()

    assert "node Link {" in generated
    assert "  link_id: String" in generated
    assert "  @key(link_id)" in generated
    assert "edge LinkSource: Link -> Thing {}" in generated
    assert "edge LinkTarget: Link -> Thing {}" in generated
    assert "edge LinkContext: Link -> Thing {}" in generated


def test_reified_relationship_property_unique_keys_emit_node_unique(
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
      og_relationship_mode: reified
    unique_keys:
      external_identity:
        unique_key_slots:
          - external_id
          - sequence
    attributes:
      link_id:
        range: string
        identifier: true
        required: true
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
      external_id:
        range: string
        required: true
      sequence:
        range: integer
        required: true
""",
    )

    generated = OmnigraphGenerator(schema).serialize()

    assert "  @key(link_id)" in generated
    assert "  @unique(external_id, sequence)" in generated


def test_reified_relationship_rejects_endpoint_aware_unique_keys(
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
      og_relationship_mode: reified
    unique_keys:
      endpoint_identity:
        unique_key_slots:
          - source
          - target
          - external_id
    attributes:
      link_id:
        range: string
        identifier: true
        required: true
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
      external_id:
        range: string
        required: true
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match="Endpoint-aware uniqueness cannot be emitted"):
        OmnigraphGenerator(schema).serialize()
