from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from linkml_omnigraph.generator import OmnigraphGenerator
from tests.conftest import LINKML_FIXTURES, OMNIGRAPH_FIXTURES, SUPPORTED_OMNIGRAPH_VERSION

OMNIGRAPH = shutil.which("omnigraph")
pytestmark = pytest.mark.skipif(OMNIGRAPH is None, reason="omnigraph CLI is not available")

SCHEMA_FIXTURES = sorted(path.name for path in LINKML_FIXTURES.glob("*.yaml"))
QUERY_FIXTURE_PAIRS = sorted((path.stem + ".yaml", path.name) for path in OMNIGRAPH_FIXTURES.glob("*.gq"))


@pytest.fixture(scope="module", autouse=True)
def qualified_backend() -> None:
    result = subprocess.run([OMNIGRAPH, "--version"], check=True, capture_output=True, text=True, timeout=30)
    assert result.stdout.strip() == SUPPORTED_OMNIGRAPH_VERSION, "Only Omnigraph 0.11.0 fresh graphs are qualified"


def _generate(schema: Path, output: Path) -> None:
    output.write_text(OmnigraphGenerator(schema).serialize(), encoding="utf-8")


def test_current_names_load_and_execute(tmp_path: Path) -> None:
    """Generated properties remain distinct from wire and GQ system identity."""
    output = tmp_path / "schema.pg"
    graph = tmp_path / "graph.omni"
    _generate(LINKML_FIXTURES / "current_names.yaml", output)

    def run(*args: str | Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run([OMNIGRAPH, *map(str, args)], check=True, capture_output=True, text=True, timeout=60)

    run("init", "--schema", output, graph)
    records = [
        {"type": "Record", "data": {"slug": "a", "id": "domain-a", "from": "origin", "to": "destination"}},
        {"type": "Record", "data": {"slug": "b", "id": "domain-b"}},
        {"type": "Association", "data": {"id": "association", "src": "owned-source", "dst": "owned-target"}},
        {"edge": "Link", "id": "wire-edge", "from": "a", "to": "b",
         "data": {"id": "domain-edge", "src": "domain-source", "dst": "domain-target"}},
        {"edge": "AssociationFrom", "from": "association", "to": "a"},
        {"edge": "AssociationTo", "from": "association", "to": "b"},
    ]
    source = tmp_path / "data.jsonl"
    source.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    receipt = json.loads(run("load", graph, "--data", source, "--mode", "append", "--json").stdout)
    assert receipt["total_entities"] == 6
    result = json.loads(run("query", "--store", graph, "--query", OMNIGRAPH_FIXTURES / "current_names.gq", "--json").stdout)
    assert result["rows"] == [{
        "identity": "a", "domain_id": "domain-a", "origin": "origin", "destination": "destination",
        "edge_identity": "wire-edge", "source": "a", "target": "b", "edge_id": "domain-edge",
        "domain_source": "domain-source", "domain_target": "domain-target",
    }]
    assert result["graph_commit_id"] == receipt["commit"]["graph_commit_id"]
    reified = json.loads(run("query", "--store", graph, "-e", """query q() {
      match { $r: Association $r associationFrom $a $r associationTo $b }
      return { $r.@id as identity, $r.id as domain_id, $r.src, $r.dst, $a.id, $b.id }
    }""", "--json").stdout)
    assert reified["rows"] == [{"identity": "association", "domain_id": "association",
                                "r.src": "owned-source", "r.dst": "owned-target",
                                "a.id": "domain-a", "b.id": "domain-b"}]


@pytest.mark.parametrize("schema_name", SCHEMA_FIXTURES)
def test_generated_schema_initialises_throwaway_graph(tmp_path: Path, schema_name: str) -> None:
    schema = LINKML_FIXTURES / schema_name
    output = tmp_path / "schema.pg"
    graph = tmp_path / "graph.omni"

    _generate(schema, output)

    subprocess.run(
        [OMNIGRAPH, "init", "--schema", str(output), str(graph)],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(("schema_name", "query_name"), QUERY_FIXTURE_PAIRS)
def test_generated_query_lints_against_generated_schema(tmp_path: Path, schema_name: str, query_name: str) -> None:
    schema = LINKML_FIXTURES / schema_name
    query = OMNIGRAPH_FIXTURES / query_name
    output = tmp_path / "schema.pg"

    _generate(schema, output)

    result = subprocess.run(
        [OMNIGRAPH, "lint", "--schema", str(output), "--query", str(query), "--json"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert '"status": "ok"' in result.stdout
    assert '"errors": 0' in result.stdout


def test_omnigraph_lint_catches_wrong_type_binding(tmp_path: Path) -> None:
    """Locks the documented lint/init boundary.

    ``omnigraph lint`` enforces property-existence and scalar typing, but it
    does not enforce semantic constraints (``@range``/``@check``/``@unique``/
    ``@key`` composition). This test pins the half it does check: a wrong-type
    binding must be rejected. The boundary itself is documented in
    ``docs/compatibility.md`` describes the query-typing boundary.
    """
    schema = LINKML_FIXTURES / "constraint_surface.yaml"
    output = tmp_path / "schema.pg"
    _generate(schema, output)

    wrong_type_query = tmp_path / "wrong_type.gq"
    wrong_type_query.write_text(
        'query find_account($tenant: String) {\n'
        '  match {\n'
        '    $a: Account { score: "not-an-integer" }\n'
        '  }\n'
        '  return { $a.email }\n'
        '  limit 10\n'
        '}\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [OMNIGRAPH, "lint", "--schema", str(output), "--query", str(wrong_type_query), "--json"],
        capture_output=True,
        text=True,
    )

    # `omnigraph lint` exits non-zero when a query has errors; that is the
    # expected outcome here, so we read stdout regardless of return code.
    assert '"status": "error"' in result.stdout
    assert '"errors": 1' in result.stdout
    assert "has type I64 but got String" in result.stdout
