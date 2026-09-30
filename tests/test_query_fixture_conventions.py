from __future__ import annotations

from tests.conftest import LINKML_FIXTURES, OMNIGRAPH_FIXTURES


def test_every_query_fixture_has_a_matching_linkml_source_fixture() -> None:
    schema_stems = {path.stem for path in LINKML_FIXTURES.glob("*.yaml")}
    query_stems = {path.stem for path in OMNIGRAPH_FIXTURES.glob("*.gq")}

    assert query_stems <= schema_stems


def test_current_query_fixture_surface_matches_documented_stems() -> None:
    query_stems = sorted(path.stem for path in OMNIGRAPH_FIXTURES.glob("*.gq"))

    assert query_stems == [
        "basic",
        "constraint_surface",
        "current_names",
        "edge_uniqueness",
        "query_surface",
        "reified_nary_relationship",
        "reified_relationship",
        "search_surface",
        "ta1044",
    ]
