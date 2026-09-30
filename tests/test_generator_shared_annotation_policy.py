from __future__ import annotations

from pathlib import Path

import pytest

from linkml_omnigraph.generator import OmnigraphGenerator, OmnigraphGeneratorError
from tests.conftest import write_schema


def test_lifecycle_annotation_has_no_schema_effect_or_comment_output(
    tmp_path: Path, schema_prelude: str
) -> None:
    baseline = write_schema(
        tmp_path / "baseline.yaml",
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
      title:
        range: string
""",
    )
    with_lifecycle = write_schema(
        tmp_path / "with_lifecycle.yaml",
        schema_prelude,
        """
classes:
  Document:
    annotations:
      kind: entity
      lifecycle: shared
    attributes:
      document_id:
        range: string
        identifier: true
        required: true
      title:
        range: string
""",
    )

    baseline_generated = OmnigraphGenerator(baseline).serialize()
    lifecycle_generated = OmnigraphGenerator(with_lifecycle).serialize()

    assert lifecycle_generated == baseline_generated
    assert "lifecycle" not in lifecycle_generated
    assert "//" not in lifecycle_generated
    assert "/*" not in lifecycle_generated


def test_read_shape_annotation_has_no_schema_effect_or_comment_output(
    tmp_path: Path, schema_prelude: str
) -> None:
    baseline = write_schema(
        tmp_path / "baseline.yaml",
        schema_prelude,
        """
classes:
  Profile:
    annotations:
      kind: entity
    attributes:
      profile_id:
        range: string
        identifier: true
        required: true
      display_name:
        range: string
""",
    )
    with_read_shape = write_schema(
        tmp_path / "with_read_shape.yaml",
        schema_prelude,
        """
classes:
  Profile:
    annotations:
      kind: entity
      read_shape: inline
    attributes:
      profile_id:
        range: string
        identifier: true
        required: true
      display_name:
        range: string
""",
    )

    baseline_generated = OmnigraphGenerator(baseline).serialize()
    read_shape_generated = OmnigraphGenerator(with_read_shape).serialize()

    assert read_shape_generated == baseline_generated
    assert "read_shape" not in read_shape_generated
    assert "//" not in read_shape_generated
    assert "/*" not in read_shape_generated


@pytest.mark.parametrize("canonical", ["independent", "shared"])
def test_canonical_lifecycle_values_are_accepted(
    tmp_path: Path, schema_prelude: str, canonical: str
) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        f"""
classes:
  Document:
    annotations:
      kind: entity
      lifecycle: {canonical}
    attributes:
      document_id:
        range: string
        identifier: true
        required: true
""",
    )

    generated = OmnigraphGenerator(schema).serialize()

    assert "lifecycle" not in generated
    assert "@key(document_id)" in generated


def test_unknown_lifecycle_value_is_rejected(tmp_path: Path, schema_prelude: str) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        """
classes:
  Document:
    annotations:
      kind: entity
      lifecycle: shred
    attributes:
      document_id:
        range: string
        identifier: true
        required: true
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match="lifecycle 'shred'"):
        OmnigraphGenerator(schema).serialize()


@pytest.mark.parametrize("canonical", ["reference", "inline"])
def test_canonical_read_shape_values_are_accepted(
    tmp_path: Path, schema_prelude: str, canonical: str
) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        f"""
classes:
  Profile:
    annotations:
      kind: entity
      read_shape: {canonical}
    attributes:
      profile_id:
        range: string
        identifier: true
        required: true
""",
    )

    generated = OmnigraphGenerator(schema).serialize()

    assert "read_shape" not in generated
    assert "@key(profile_id)" in generated


def test_unknown_read_shape_value_is_rejected(tmp_path: Path, schema_prelude: str) -> None:
    schema = write_schema(
        tmp_path / "schema.yaml",
        schema_prelude,
        """
classes:
  Profile:
    annotations:
      kind: entity
      read_shape: inlined
    attributes:
      profile_id:
        range: string
        identifier: true
        required: true
""",
    )

    with pytest.raises(OmnigraphGeneratorError, match="read_shape 'inlined'"):
        OmnigraphGenerator(schema).serialize()
