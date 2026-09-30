"""Exercise native-edge uniqueness on generated schemas in fresh qualified graphs."""
from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

from linkml_omnigraph.generator import OmnigraphGenerator
from tests.conftest import LINKML_FIXTURES, SUPPORTED_OMNIGRAPH_VERSION

BINARY = shutil.which("omnigraph")
pytestmark = pytest.mark.skipif(BINARY is None, reason="omnigraph CLI is not available")


@pytest.fixture
def graph_cli(tmp_path):
    # Explicit stores and a clean environment keep every write in this test's
    # fresh graph. No ambient server/store settings or credentials are used.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("OMNIGRAPH_") and key != "PYTHONPATH"}
    env["OMNIGRAPH_EMBED_PROVIDER"] = "mock"

    def run(*args, ok=True):
        result = subprocess.run([BINARY, *map(str, args)], cwd=tmp_path, env=env,
                                text=True, capture_output=True, timeout=60)
        assert (result.returncode == 0) == ok, result.stdout + result.stderr
        return result

    assert run("--version").stdout.strip() == SUPPORTED_OMNIGRAPH_VERSION
    schema = tmp_path / "schema.pg"
    generated = OmnigraphGenerator(LINKML_FIXTURES / "edge_uniqueness.yaml").serialize()
    for name in ["Employment", "Membership"]:
        assert "@key" not in generated.split(f"edge {name}:")[1].split("}")[0]
    schema.write_text(generated, encoding="utf-8")
    graph = tmp_path / "graph.omni"
    run("init", "--schema", schema, graph)

    def load(records, branch="main", ok=True, mode="append"):
        data = tmp_path / "data.jsonl"
        data.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
        return run("load", graph, "--data", data, "--branch", branch,
                   "--mode", mode, "--json", ok=ok)

    load([{"type": kind, "data": {"slug": slug}} for kind, slugs in [
        ("Person", ["alice", "bob"]), ("Organisation", ["acme", "beta"])] for slug in slugs])
    return run, load, graph


def edge(kind, identity, code="research", alternative=False):
    source, target = ("alice", "acme") if kind == "Employment" else ("acme", "alice")
    if alternative:
        target = "beta" if kind == "Employment" else "bob"
    return {"edge": kind, "id": identity, "from": source, "to": target,
            "data": {"code": code, "note": identity}}


def read(run, graph, kind, branch="main"):
    node = "Person" if kind == "Employment" else "Organisation"
    traversal = kind[0].lower() + kind[1:]
    query = f"""query q() {{ match {{ $a: {node} $a $e:{traversal} $b }}
      return {{ $e.@id as identity, $e.@src as source, $e.@dst as target, $e.code, $e.note }}
      order {{ $e.@id }} }}"""
    return json.loads(run("query", "--store", graph, "--branch", branch, "-e", query, "--json").stdout)


@pytest.mark.parametrize("kind", ["Employment", "Membership"])
def test_generated_unique_load_and_mutation_admission_and_refusal(graph_cli, kind):
    run, load, graph = graph_cli
    first = edge(kind, "first")
    load([first])
    duplicate = edge(kind, "second", code="training" if kind == "Membership" else "research")
    before = read(run, graph, kind)
    assert before["rows"] == [{"identity": "first", "source": first["from"], "target": first["to"],
                               "e.code": "research", "e.note": "first"}]
    refusal = load([duplicate], ok=False, mode="merge")
    assert "unique" in (refusal.stdout + refusal.stderr).lower()
    assert read(run, graph, kind) == before
    # Different body values remain parallel for Employment; Membership requires
    # a different pair regardless of body values.
    load([edge(kind, "allowed", code="training", alternative=kind == "Membership")])
    assert len(read(run, graph, kind)["rows"]) == 2
    before = read(run, graph, kind)
    query = f'query q() {{ insert {kind} {{ from: "{duplicate["from"]}", to: "{duplicate["to"]}", code: "{duplicate["data"]["code"]}", note: "duplicate" }} }}'
    refusal = run("mutate", "--store", graph, "-e", query, "--json", ok=False)
    assert "unique" in (refusal.stdout + refusal.stderr).lower()
    assert read(run, graph, kind) == before  # Includes unchanged graph commit ID.
    allowed = edge(kind, "mutation", code="new", alternative=True)
    query = f'query q() {{ insert {kind} {{ from: "{allowed["from"]}", to: "{allowed["to"]}", code: "new", note: "mutation" }} }}'
    # Membership already uses acme->bob; choose a third allowed pair instead.
    if kind == "Membership":
        query = 'query q() { insert Membership { from: "beta", to: "alice", code: "new", note: "mutation" } }'
    run("mutate", "--store", graph, "-e", query, "--json")
    result = read(run, graph, kind)["rows"]
    assert len(result) == 3 and len({row["identity"] for row in result}) == 3
    assert any(row["e.note"] == "mutation" and row["e.code"] == "new" for row in result)


@pytest.mark.parametrize("kind", ["Employment", "Membership"])
def test_generated_unique_branch_merge_preserves_target_on_refusal(graph_cli, kind):
    run, load, graph = graph_cli
    for branch in ["left", "right", "allowed"]:
        run("branch", "create", branch, "--store", graph, "--from", "main", "--json")
    load([edge(kind, "left")], branch="left")
    load([edge(kind, "right", code="training" if kind == "Membership" else "research")], branch="right")
    load([edge(kind, "allowed", code="training", alternative=True)], branch="allowed")
    assert read(run, graph, kind)["rows"] == []
    for branch in ["left", "right", "allowed"]:
        assert read(run, graph, kind, branch)["rows"][0]["identity"] == branch
    run("branch", "merge", "left", "--into", "main", "--store", graph, "--json")
    before = read(run, graph, kind)
    source_before = read(run, graph, kind, "right")
    refusal = run("branch", "merge", "right", "--into", "main", "--store", graph, "--json", ok=False)
    assert "unique_violation" in refusal.stdout + refusal.stderr
    assert read(run, graph, kind) == before
    assert read(run, graph, kind, "right") == source_before
    run("branch", "merge", "allowed", "--into", "main", "--store", graph, "--json")
    assert {row["identity"] for row in read(run, graph, kind)["rows"]} == {"left", "allowed"}
