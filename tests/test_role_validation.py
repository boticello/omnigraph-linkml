"""Complete-batch preflight protects joins without claiming backend enforcement."""
from copy import deepcopy

import pytest

from linkml_omnigraph import OmnigraphDataValidationError, OmnigraphGenerator
from tests.conftest import write_schema
from tests.ta1044_pilot import SCHEMA
from tests.ta1044_pilot_data import edge, records


def test_complete_batch_is_order_independent_and_unchanged():
    corpus = list(reversed(records()))
    before = deepcopy(corpus)
    OmnigraphGenerator(SCHEMA).validate_reified_roles(iter(corpus))
    assert corpus == before


@pytest.mark.parametrize("violation", [
    "missing", "duplicate", "dangling", "wrong-type", "orphan", "reverse",
    "null-reference", "structured-reference", "missing-key", "duplicate-key",
    "unknown-node", "unknown-edge", "ambiguous-record", "missing-data", "nonfinite-key",
])
def test_reachable_invalid_role_sets_are_refused(violation):
    corpus = records()
    role = next(row for row in corpus if row.get("edge") == "EvidenceUseSource")
    if violation == "missing":
        corpus.remove(role)
    elif violation == "duplicate":
        corpus.append(edge("EvidenceUseSource", "duplicate", role["from"], "jiao-2023"))
    elif violation == "dangling":
        role["to"] = "absent-document"
    elif violation == "wrong-type":
        role["to"] = "company-mortality"
    elif violation == "orphan":
        role["from"] = "absent-use"
    elif violation == "reverse":
        role["from"], role["to"] = role["to"], role["from"]
    elif violation == "null-reference":
        role["to"] = None
    elif violation == "structured-reference":
        role["to"] = {"document_id": "desai-2020"}
    elif violation == "missing-key":
        next(row for row in corpus if row.get("type") == "SourceDocument")["data"].pop("document_id")
    elif violation == "duplicate-key":
        corpus.append(deepcopy(next(row for row in corpus if row.get("type") == "SourceDocument")))
    elif violation == "unknown-node":
        next(row for row in corpus if row.get("type") == "EvidenceUse")["type"] = "EvidenceTypo"
    elif violation == "unknown-edge":
        role["edge"] = "EvidenceUseTypo"
    elif violation == "ambiguous-record":
        role["type"] = "EvidenceUse"
    elif violation == "missing-data":
        next(row for row in corpus if row.get("type") == "SourceDocument")["data"] = None
    else:
        next(row for row in corpus if row.get("type") == "SourceDocument")["data"]["document_id"] = float("nan")
    with pytest.raises(OmnigraphDataValidationError):
        OmnigraphGenerator(SCHEMA).validate_reified_roles(corpus)


def test_relationship_and_role_rules_follow_schema_names(tmp_path):
    schema = tmp_path / "renamed.yaml"
    schema.write_text(SCHEMA.read_text().replace("EvidenceUse", "CitationUse").replace("role: passage", "role: location"))
    corpus = records()
    for row in corpus:
        if row.get("type") == "EvidenceUse":
            row["type"] = "CitationUse"
        if "edge" in row:
            row["edge"] = row["edge"].replace("EvidenceUse", "CitationUse").replace("UsePassage", "UseLocation")
    generator = OmnigraphGenerator(schema)
    generator.validate_reified_roles(corpus)
    corpus.remove(next(row for row in corpus if row.get("edge") == "CitationUseLocation"))
    with pytest.raises(OmnigraphDataValidationError, match="CitationUse.*location"):
        generator.validate_reified_roles(corpus)


def test_unsupported_participant_key_refuses_even_an_empty_batch(tmp_path):
    schema = tmp_path / "unkeyed.yaml"
    schema.write_text(SCHEMA.read_text().replace("document_id:\n        range: string\n        identifier: true", "document_id:\n        range: string"))
    generator = OmnigraphGenerator(schema)
    generator.serialize()  # Admitted schema does not imply supported preflight references.
    with pytest.raises(OmnigraphDataValidationError, match="SourceDocument.*single scalar key"):
        generator.validate_reified_roles([])


def test_composite_participant_key_is_explicitly_unsupported(tmp_path):
    schema = tmp_path / "composite.yaml"
    text = SCHEMA.read_text().replace("document_id:\n        range: string\n        identifier: true", "document_id:\n        range: string")
    text = text.replace("  SourceDocument:\n", "  SourceDocument:\n    unique_keys:\n      composite:\n        unique_key_slots: [document_id, citation_key]\n")
    schema.write_text(text)
    generator = OmnigraphGenerator(schema)
    generator.serialize()
    with pytest.raises(OmnigraphDataValidationError, match="SourceDocument.*single scalar key"):
        generator.validate_reified_roles(records())


def test_reified_body_uniqueness_does_not_change_role_keys(tmp_path):
    schema = tmp_path / "unique-body.yaml"
    schema.write_text(SCHEMA.read_text().replace("  EvidenceUse:\n", "  EvidenceUse:\n    unique_keys:\n      body:\n        unique_key_slots: [summary]\n"))
    OmnigraphGenerator(schema).validate_reified_roles(records())


def test_scalar_key_types_do_not_conflate_bool_and_integer():
    corpus = records()
    role = next(row for row in corpus if row.get("edge") == "EvidenceUseSource")
    target = next(row for row in corpus if row.get("type") == "SourceDocument" and row["data"]["document_id"] == role["to"])
    old = role["to"]
    target["data"]["document_id"] = 1
    for row in corpus:
        if row.get("edge") == "EvidenceUseSource" and row["to"] == old:
            row["to"] = 1
    generator = OmnigraphGenerator(SCHEMA)
    generator.validate_reified_roles(corpus)  # Role check; scalar property validation remains backend-owned.
    role["to"] = True
    with pytest.raises(OmnigraphDataValidationError, match="not of type SourceDocument"):
        generator.validate_reified_roles(corpus)


def test_promoted_single_key_and_type_scoped_equal_identities(tmp_path):
    schema = tmp_path / "promoted.yaml"
    text = SCHEMA.read_text().replace("document_id:\n        range: string\n        identifier: true", "document_id:\n        range: string")
    text = text.replace("  SourceDocument:\n", "  SourceDocument:\n    unique_keys:\n      identity:\n        unique_key_slots: [document_id]\n")
    schema.write_text(text)
    corpus = records()
    target = next(row for row in corpus if row.get("type") == "SourceDocument")
    old = target["data"]["document_id"]
    target["data"]["document_id"] = "company-mortality"  # Also an Analysis key.
    for row in corpus:
        if row.get("edge") == "EvidenceUseSource" and row["to"] == old:
            row["to"] = "company-mortality"
    OmnigraphGenerator(schema).validate_reified_roles(corpus)


@pytest.mark.parametrize("owner", ["entity", "promoted", "relationship"])
@pytest.mark.parametrize("shape", ["list", "vector"])
def test_non_scalar_key_schema_refuses_before_consuming_batch(tmp_path, owner, shape):
    schema = tmp_path / "non-scalar-key.yaml"
    text = SCHEMA.read_text()
    name = "evidence_use_id" if owner == "relationship" else "document_id"
    original = f"{name}:\n        range: string\n        identifier: true"
    shape_yaml = "multivalued: true" if shape == "list" else "annotations:\n          vector_dimensions: 2"
    replacement = f"{name}:\n        range: float\n        {shape_yaml}"
    if owner != "promoted":
        replacement += "\n        identifier: true"
    else:
        text = text.replace("  SourceDocument:\n", "  SourceDocument:\n    unique_keys:\n      identity:\n        unique_key_slots: [document_id]\n")
    schema.write_text(text.replace(original, replacement))
    generator = OmnigraphGenerator(schema)
    generator.serialize()  # Unsupported preflight key, rather than rejected schema.
    for corpus in ([], records()):
        with pytest.raises(OmnigraphDataValidationError, match="single scalar key"):
            generator.validate_reified_roles(corpus)
    def unreadable():
        raise AssertionError("Records consumed before key compatibility was checked")
        yield
    with pytest.raises(OmnigraphDataValidationError, match="single scalar key"):
        generator.validate_reified_roles(unreadable())


@pytest.mark.parametrize("target_type", ["Person", "Organisation"])
def test_colliding_role_edge_names_refuse_before_consuming_batch(tmp_path, schema_prelude, target_type):
    schema = write_schema(tmp_path / "collision.yaml", schema_prelude, f"""
classes:
  Person:
    annotations: {{kind: entity}}
    attributes:
      person_id: {{range: string, identifier: true, required: true}}
  Organisation:
    annotations: {{kind: entity}}
    attributes:
      org_id: {{range: string, identifier: true, required: true}}
  Rel:
    annotations: {{kind: relationship, og_relationship_mode: reified}}
    attributes:
      rel_id: {{range: string, identifier: true, required: true}}
      first: {{range: Person, required: true, annotations: {{role: useSource}}}}
      second: {{range: Person, required: true, annotations: {{role: other}}}}
  RelUse:
    annotations: {{kind: relationship, og_relationship_mode: reified}}
    attributes:
      rel_id: {{range: string, identifier: true, required: true}}
      first: {{range: {target_type}, required: true, annotations: {{role: source}}}}
      second: {{range: Person, required: true, annotations: {{role: other}}}}
""")
    generator = OmnigraphGenerator(schema)
    assert generator.serialize().count("edge RelUseSource:") == 2
    corpus = [
        {"type": "Person", "data": {"person_id": "p"}},
        {"type": "Organisation", "data": {"org_id": "p"}},
        {"type": "Rel", "data": {"rel_id": "r"}},
        {"type": "RelUse", "data": {"rel_id": "r"}},
        edge("RelUseSource", "one", "r", "p"),
        edge("RelOther", "two", "r", "p"),
        edge("RelUseOther", "three", "r", "p"),
    ]
    for batch in ([], corpus):
        with pytest.raises(OmnigraphDataValidationError, match="ambiguous generated role edge RelUseSource"):
            generator.validate_reified_roles(batch)
    def unreadable():
        raise AssertionError("Records consumed before projection ambiguity was checked")
        yield
    with pytest.raises(OmnigraphDataValidationError, match="ambiguous generated role edge"):
        generator.validate_reified_roles(unreadable())
