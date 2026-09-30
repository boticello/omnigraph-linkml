from __future__ import annotations

from pathlib import Path

import pytest

from linkml_omnigraph.generator import OmnigraphGenerator, OmnigraphGeneratorError
from tests.conftest import write_schema


def test_numeric_range_constraint_mapping(tmp_path: Path, schema_prelude: str) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        """
classes:
  Measure:
    annotations:
      kind: entity
    attributes:
      measure_id:
        range: string
        identifier: true
        required: true
      score:
        range: integer
        minimum_value: 0
        maximum_value: 10
""",
    )

    generated = OmnigraphGenerator(schema).serialize()
    assert "@range(score, 0..10)" in generated


@pytest.mark.parametrize(
    ("constraint", "expected"),
    [
        ("minimum_value: 0", "@range(score, 0..)"),
        ("maximum_value: 10", "@range(score, ..10)"),
    ],
)
def test_partial_numeric_range_constraint_mapping(
    tmp_path: Path, schema_prelude: str, constraint: str, expected: str
) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        f"""
classes:
  Measure:
    annotations:
      kind: entity
    attributes:
      measure_id:
        range: string
        identifier: true
        required: true
      score:
        range: integer
        {constraint}
""",
    )

    generated = OmnigraphGenerator(schema).serialize()
    assert expected in generated


def test_pattern_constraint_mapping(tmp_path: Path, schema_prelude: str) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        r"""
classes:
  Person:
    annotations:
      kind: entity
    attributes:
      person_id:
        range: string
        identifier: true
        required: true
      email:
        range: string
        pattern: "^[^@]+@[^@]+$"
""",
    )

    generated = OmnigraphGenerator(schema).serialize()
    assert '@check(email, "^[^@]+@[^@]+$")' in generated


def test_promotes_single_required_entity_unique_key_to_composite_key(tmp_path: Path, schema_prelude: str) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        """
classes:
  Account:
    annotations:
      kind: entity
    unique_keys:
      account_identity:
        unique_key_slots:
          - tenant_id
          - external_id
    attributes:
      tenant_id:
        range: string
        required: true
      external_id:
        range: string
        required: true
""",
    )

    generated = OmnigraphGenerator(schema).serialize()
    assert "@key(tenant_id, external_id)" in generated
    assert "@unique(tenant_id, external_id)" not in generated


def test_keeps_unique_keys_as_unique_when_identifier_slot_exists(tmp_path: Path, schema_prelude: str) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        """
classes:
  Account:
    annotations:
      kind: entity
    unique_keys:
      account_identity:
        unique_key_slots:
          - tenant_id
          - external_id
    attributes:
      account_id:
        range: string
        identifier: true
        required: true
      tenant_id:
        range: string
        required: true
      external_id:
        range: string
        required: true
""",
    )

    generated = OmnigraphGenerator(schema).serialize()
    assert "@key(account_id)" in generated
    assert "@unique(tenant_id, external_id)" in generated


def test_keeps_optional_composite_unique_key_as_unique(tmp_path: Path, schema_prelude: str) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        """
classes:
  Account:
    annotations:
      kind: entity
    unique_keys:
      account_identity:
        unique_key_slots:
          - tenant_id
          - external_id
    attributes:
      tenant_id:
        range: string
        required: true
      external_id:
        range: string
""",
    )

    generated = OmnigraphGenerator(schema).serialize()
    assert "@key(" not in generated
    assert "@unique(tenant_id, external_id)" in generated


def test_keeps_multiple_unique_keys_as_unique_when_primary_identity_is_ambiguous(
    tmp_path: Path, schema_prelude: str
) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        """
classes:
  Account:
    annotations:
      kind: entity
    unique_keys:
      tenant_external:
        unique_key_slots:
          - tenant_id
          - external_id
      tenant_slug:
        unique_key_slots:
          - tenant_id
          - slug
    attributes:
      tenant_id:
        range: string
        required: true
      external_id:
        range: string
        required: true
      slug:
        range: string
        required: true
""",
    )

    generated = OmnigraphGenerator(schema).serialize()
    assert "@key(" not in generated
    assert "@unique(tenant_id, external_id)" in generated
    assert "@unique(tenant_id, slug)" in generated


def test_rejects_non_numeric_range_constraint(tmp_path: Path, schema_prelude: str) -> None:
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
      code:
        range: string
        minimum_value: 1
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match="non-numeric"):
        OmnigraphGenerator(schema).serialize()


def test_rejects_non_string_pattern_constraint(tmp_path: Path, schema_prelude: str) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        """
classes:
  Measure:
    annotations:
      kind: entity
    attributes:
      measure_id:
        range: string
        identifier: true
        required: true
      score:
        range: integer
        pattern: "^[0-9]+$"
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match="non-String"):
        OmnigraphGenerator(schema).serialize()


def test_rejects_node_only_constraints_on_edge_properties(tmp_path: Path, schema_prelude: str) -> None:
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
      score:
        range: integer
        minimum_value: 0
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match="not supported on edges"):
        OmnigraphGenerator(schema).serialize()


def test_endpoint_relationship_unique_key_emits_unique_not_key(tmp_path: Path, schema_prelude: str) -> None:
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
    unique_keys:
      link_identity:
        unique_key_slots:
          - source
          - target
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

    generated = OmnigraphGenerator(schema).serialize()
    edge = generated.split("edge Link:")[1].split("}")[0]
    assert "@unique(@src, @dst)" in edge
    assert "@key" not in edge
