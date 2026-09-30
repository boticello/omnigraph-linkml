"""Native-edge uniqueness admission boundaries from the mapping contract."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from linkml_omnigraph.generator import OmnigraphGenerator, OmnigraphGeneratorError


def source_model() -> dict:
    return {
        "id": "https://example.org/edge-uniqueness", "name": "edge_uniqueness",
        "prefixes": {"linkml": "https://w3id.org/linkml/"}, "imports": ["linkml:types"],
        "enums": {"Code": {"permissible_values": {"Research": {}, "Training": {}}}},
        "classes": {
            "Person": {"annotations": {"kind": "entity"}, "attributes": {
                "slug": {"range": "string", "required": True, "identifier": True}}},
            "Organisation": {"annotations": {"kind": "entity"}, "attributes": {
                "slug": {"range": "string", "required": True, "identifier": True}}},
            "Employment": {
                "annotations": {"kind": "relationship", "og_from_role": "employee", "og_to_role": "employer"},
                "unique_keys": {"assignment": {"unique_key_slots": ["person", "organisation", "code"]}},
                "attributes": {
                    "person": {"range": "Person", "required": True, "annotations": {"role": "employee"}},
                    "organisation": {"range": "Organisation", "required": True, "annotations": {"role": "employer"}},
                    "code": {"range": "string", "required": True},
                    "note": {"range": "string", "required": True},
                },
            },
        },
    }


def generate_model(tmp_path: Path, model: dict) -> str:
    path = tmp_path / "source.yaml"
    path.write_text(yaml.safe_dump(model, sort_keys=False), encoding="utf-8")
    return OmnigraphGenerator(path).serialize()


@pytest.mark.parametrize("members", [
    ["person", "organisation"], ["organisation", "person"],
    ["person", "organisation", "code"], ["code", "organisation", "person"],
])
@pytest.mark.parametrize("nulls", [None, False])
def test_endpoint_tuple_unique_without_edge_key(tmp_path, members, nulls):
    model = source_model()
    key = model["classes"]["Employment"]["unique_keys"]["assignment"]
    key["unique_key_slots"] = members
    if nulls is not None:
        key["consider_nulls_inequal"] = nulls
    edge = generate_model(tmp_path, model).split("edge Employment:")[1].split("}")[0]
    expected = "@unique(@src, @dst, code)" if "code" in members else "@unique(@src, @dst)"
    assert expected in edge
    assert "@key" not in edge
    assert "person:" not in edge and "organisation:" not in edge


@pytest.mark.parametrize("direction", ["reverse", "conventional"])
def test_direction_resolves_roles_not_slot_names(tmp_path, direction):
    model = source_model()
    cls = model["classes"]["Employment"]
    if direction == "reverse":
        cls["annotations"].update(og_from_role="employer", og_to_role="employee")
        header = "Organisation -> Person"
    else:
        cls["annotations"] = {"kind": "relationship"}
        cls["attributes"]["person"]["annotations"]["role"] = "source"
        cls["attributes"]["organisation"]["annotations"]["role"] = "target"
        header = "Person -> Organisation"
    result = generate_model(tmp_path, model)
    assert f"edge Employment: {header}" in result
    assert "@unique(@src, @dst, code)" in result


@pytest.mark.parametrize("inheritance", ["is_a", "mixins"])
@pytest.mark.parametrize("declarations", ["slots", "attributes"])
def test_inherited_slots_and_slot_usage_are_resolved(tmp_path, inheritance, declarations):
    model = source_model()
    cls = model["classes"]["Employment"]
    attributes = cls.pop("attributes")
    # Inherit role players and a body property, then strengthen requiredness in
    # the child relationship. Its inherited body is flattened on the edge.
    attributes["code"]["required"] = False
    base = {"annotations": deepcopy(cls["annotations"])}
    if declarations == "slots":
        model["slots"] = attributes
        base["slots"] = list(attributes)
    else:
        base["attributes"] = attributes
    model["classes"]["AssignmentShape"] = base
    cls[inheritance] = "AssignmentShape" if inheritance == "is_a" else ["AssignmentShape"]
    cls["slot_usage"] = {"code": {"required": True}}
    result = generate_model(tmp_path, model)
    edge = result.split("edge Employment:")[1].split("}")[0]
    assert "code: String\n" in edge
    assert "@unique(@src, @dst, code)" in edge
    assert "@key" not in edge


@pytest.mark.parametrize("key,diagnostic", [
    ({}, "unique_key_slots"),
    ({"unique_key_slots": []}, "unique_key_slots"),
    ({"unique_key_slots": ["person"]}, "both endpoint slots"),
    ({"unique_key_slots": ["code"]}, "both endpoint slots"),
    ({"unique_key_slots": ["person", "organisation", "missing"]}, "unknown"),
    ({"unique_key_slots": ["person", "organisation", "person"]}, "repeated"),
    ({"unique_key_slots": ["person", "organisation", "code", "note"]}, "at most one body"),
    ({"unique_key_slots": ["person", "organisation"], "consider_nulls_inequal": True}, "consider_nulls_inequal"),
])
def test_refuses_unqualified_tuple_shapes(tmp_path, key, diagnostic):
    model = source_model()
    model["classes"]["Employment"]["unique_keys"] = {"assignment": key}
    with pytest.raises(OmnigraphGeneratorError, match=diagnostic):
        generate_model(tmp_path, model)


def test_refuses_multiple_declarations(tmp_path):
    model = source_model()
    keys = model["classes"]["Employment"]["unique_keys"]
    keys["second"] = deepcopy(keys["assignment"])
    with pytest.raises(OmnigraphGeneratorError, match="exactly one"):
        generate_model(tmp_path, model)


@pytest.mark.parametrize("change", [
    {"required": False}, {"multivalued": True}, {"range": "Code"},
    {"range": "integer"}, {"range": "float"}, {"range": "boolean"},
    {"range": "date"}, {"range": "datetime"},
    {"range": "float", "annotations": {"vector_dimensions": 2}},
])
def test_refuses_unqualified_body_members(tmp_path, change):
    model = source_model()
    model["classes"]["Employment"]["attributes"]["code"].update(change)
    with pytest.raises(OmnigraphGeneratorError, match="required scalar String"):
        generate_model(tmp_path, model)


@pytest.mark.parametrize("slot", ["code", "person"])
def test_identifiers_still_refused_with_tuple_uniqueness(tmp_path, slot):
    model = source_model()
    model["classes"]["Employment"]["attributes"][slot]["identifier"] = True
    with pytest.raises(OmnigraphGeneratorError, match="identifier"):
        generate_model(tmp_path, model)


def test_no_declaration_retains_parallel_edge_projection(tmp_path):
    model = source_model()
    model["classes"]["Employment"].pop("unique_keys")
    edge = generate_model(tmp_path, model).split("edge Employment:")[1].split("}")[0]
    assert "@unique" not in edge and "@key" not in edge


def test_uri_body_maps_to_qualified_string(tmp_path):
    model = source_model()
    model["classes"]["Employment"]["attributes"]["code"]["range"] = "uri"
    assert "@unique(@src, @dst, code)" in generate_model(tmp_path, model)


def test_declared_double_underscore_property_is_preserved(tmp_path):
    model = source_model()
    cls = model["classes"]["Employment"]
    cls["attributes"]["code__value"] = cls["attributes"].pop("code")
    cls["unique_keys"]["assignment"]["unique_key_slots"] = ["person", "organisation", "code__value"]
    result = generate_model(tmp_path, model)
    assert "code__value: String" in result
    assert "@unique(@src, @dst, code__value)" in result


@pytest.mark.parametrize("change,diagnostic", [
    ({"required": False}, "exactly one participant"),
    ({"multivalued": True}, "singular"),
    ({"maximum_cardinality": 2}, "exactly one participant"),
])
def test_tuple_does_not_relax_endpoint_requirements(tmp_path, change, diagnostic):
    model = source_model()
    model["classes"]["Employment"]["attributes"]["person"].update(change)
    with pytest.raises(OmnigraphGeneratorError, match=diagnostic):
        generate_model(tmp_path, model)


def test_reified_endpoint_tuple_remains_refused(tmp_path):
    model = source_model()
    cls = model["classes"]["Employment"]
    cls["annotations"] = {"kind": "relationship", "og_relationship_mode": "reified"}
    cls["attributes"]["record_id"] = {"range": "string", "required": True, "identifier": True}
    with pytest.raises(OmnigraphGeneratorError, match="endpoint role slots"):
        generate_model(tmp_path, model)
