"""Run the curated TA1044 investigation against a new disposable local graph.

    python -m tests.ta1044_pilot --output generated/ta1044/run-1

The output directory must not exist. No network, remote graph or ambient store is
used. Result files contain executed query rows, receipts and bounded probe results.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

from linkml_omnigraph.generator import OmnigraphGenerator
from tests.ta1044_pilot_data import edge, node, records

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "tests/fixtures/linkml/ta1044.yaml"
QUERY = ROOT / "tests/fixtures/omnigraph/ta1044.gq"
EXPECTED_SOURCES = [
    ("company-mortality", "preferred", "desai-2020"),
    ("company-mortality", "preferred", "icer-2023"),
    ("company-mortality", "questioned", "desai-2020"),
    ("company-mortality", "questioned", "icer-2023"),
    ("eag-earlier-base-case", "alternative", "jiao-2023"),
    ("eag-earlier-base-case", "questioned", "jiao-2023"),
]

USES_QUERY = """query evidence_uses() {
  match {
    $u: EvidenceUse
    $u evidenceUseAnalysis $a
    $u evidenceUseSource $s
    $u evidenceUsePassage $p
  }
  return { $u.evidence_use_id as identity, $a.analysis_id as analysis,
           $s.document_id as source, $u.purpose as purpose,
           $p.locator as locator, $p.url as url, $u.summary as summary }
  order { $u.evidence_use_id }
}"""

PREFERENCE_QUERY = """query preference() {
  match {
    $p: Passage { passage_id: "discussion-3-8" }
    $p $j:discussionAnalysis $a
  }
  return { $a.analysis_id as analysis, $j.stance as stance,
           $j.attributed_to as attributed_to, $j.summary as judgement,
           $p.locator as locator, $p.url as url }
  order { $a.analysis_id, $j.stance }
}"""

IDENTITY_QUERY = """query identities() {
  match { $u: EvidenceUse }
  return { $u.evidence_use_id as identity, $u.summary as summary }
  order { $u.evidence_use_id }
}"""


def run_pilot(output: Path) -> dict:
    binary = shutil.which("omnigraph")
    if binary is None:
        raise RuntimeError("Omnigraph 0.11.0 is required; the pilot cannot be skipped")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("OMNIGRAPH_") and key != "PYTHONPATH"}
    env["OMNIGRAPH_EMBED_PROVIDER"] = "mock"
    commands = []

    def run(*args, ok=True):
        result = subprocess.run([binary, *map(str, args)], cwd=output, env=env,
                                capture_output=True, text=True, timeout=60)
        commands.append({"args": list(map(str, args)), "returncode": result.returncode,
                         "stdout": result.stdout, "stderr": result.stderr})
        if (result.returncode == 0) != ok:
            raise AssertionError(result.stdout + result.stderr)
        return result

    version = run("--version").stdout.strip()
    if version != "omnigraph 0.11.0":
        raise RuntimeError(f"Only omnigraph 0.11.0 is qualified, found {version}")
    schema = output / "schema.pg"
    schema.write_text(OmnigraphGenerator(SCHEMA).serialize(), encoding="utf-8")
    graph = output / "graph.omni"
    run("init", "--schema", schema, graph)
    corpus = records()
    OmnigraphGenerator(SCHEMA).validate_reified_roles(corpus)

    def load(data, name, ok=True, mode="append"):
        path = output / (name + ".jsonl")
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in data),
                        encoding="utf-8")
        return run("load", graph, "--data", path, "--mode", mode, "--json", ok=ok)

    def query(text, name):
        path = output / (name + ".gq")
        path.write_text(text, encoding="utf-8")
        run("lint", "--schema", schema, "--query", path, "--json")
        result = json.loads(run("query", "--store", graph, "--query", path, "--json").stdout)
        (output / (name + ".json")).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result

    receipt = json.loads(load(corpus, "curated-data").stdout)
    sources = query(QUERY.read_text(encoding="utf-8"), "mortality-sources")
    assert [(row["analysis"], row["stance"], row["source"]) for row in sources["rows"]] == EXPECTED_SOURCES
    assert all((row["recommendation"], row["conclusion"], row["assumptions"], row["discussion"]) ==
               ("TA1044-R1", "TA1044 section 3.28", "TA1044 section 3.26", "TA1044 section 3.8")
               for row in sources["rows"])
    assert sources["graph_commit_id"] == receipt["commit"]["graph_commit_id"]
    assert all(row["discussion_url"].endswith("#standard-care-mortality-modelling") and
               row["recommendation_link_basis"].startswith("Curated correspondence:")
               for row in sources["rows"])
    assert sources["rows"][0]["analysis_url"].endswith("committee-papers-2#page=393")
    assert sources["rows"][0]["source_url"] == "https://doi.org/10.1007/s00277-020-04233-w"
    preferences = query(PREFERENCE_QUERY, "committee-judgements")
    uses = query(USES_QUERY, "evidence-uses")
    assert [(row["identity"], row["analysis"], row["source"], row["purpose"]) for row in uses["rows"]] == [
        ("use-company-desai", "company-mortality", "desai-2020", "mortality-input"),
        ("use-company-icer", "company-mortality", "icer-2023", "mortality-input"),
        ("use-eag-jiao", "eag-earlier-base-case", "jiao-2023", "mortality-input"),
        ("use-eag-jiao-critique", "eag-mortality-critique", "jiao-2023", "challenge"),
    ]
    assert [(row["analysis"], row["stance"], row["attributed_to"]) for row in preferences["rows"]] == [
        ("company-mortality", "preferred", "Committee"),
        ("company-mortality", "questioned", "EAG"),
        ("eag-earlier-base-case", "alternative", "EAG"),
        ("eag-earlier-base-case", "questioned", "Company and clinical experts"),
    ]
    assert "further validation" in preferences["rows"][0]["judgement"]
    assert "Whole-SCD data were questioned for severe SCD" in preferences["rows"][3]["judgement"]
    assert "company considered Jiao unsuitable" in sources["rows"][5]["judgement"]
    assert "edition not established" in sources["rows"][1]["identification"]
    probes = []

    def snapshot():
        result = json.loads(run("query", "--store", graph, "-e", IDENTITY_QUERY, "--json").stdout)
        return {"rows": result["rows"], "commit": result["graph_commit_id"]}

    for name, kind, updates, token in [
        ("identifier-pattern", "Recommendation", {"recommendation_id": "invalid"}, "check"),
        ("page-range", "Passage", {"passage_id": "invalid-page", "pdf_page": 0}, "range"),
        ("citation-uniqueness", "SourceDocument", {"document_id": "duplicate-source"}, "unique"),
    ]:
        original = next(row for row in corpus if row.get("type") == kind)
        invalid = copy.deepcopy(original)
        invalid["data"].update(updates)
        before = snapshot()
        refusal = load([invalid], name, ok=False, mode="merge")
        assert token in (refusal.stdout + refusal.stderr).lower()
        assert snapshot() == before
        probes.append({"name": name, "result": "refused", "commit_unchanged": True})

    before = snapshot()
    duplicate = edge("DiscussionAnalysis", "duplicate-preference", "discussion-3-8", "company-mortality",
                     stance="preferred", attributed_to="Committee", summary="Duplicate judgement probe")
    refusal = load([duplicate], "judgement-uniqueness", ok=False, mode="merge")
    assert "unique" in (refusal.stdout + refusal.stderr).lower()
    assert snapshot() == before
    probes.append({"name": "judgement-uniqueness", "result": "refused", "commit_unchanged": True})

    # Same independent relationship identifier updates one record; roles survive.
    original = next(row for row in corpus if row.get("type") == "EvidenceUse")
    updated = copy.deepcopy(original)
    updated["data"]["summary"] = "Identity update probe; original source-use assertion retained"
    load([updated], "reified-identity-update", mode="merge")
    after = query(USES_QUERY, "identity-after-update")
    assert len(after["rows"]) == 4
    assert after["rows"][0]["identity"] == "use-company-desai"
    assert after["rows"][0]["analysis"] == "company-mortality"
    assert after["rows"][0]["source"] == "desai-2020"
    assert after["rows"][0]["summary"] == updated["data"]["summary"]
    probes.append({"name": "reified-identity", "result": "updated-one-record; roles-retained"})
    load([original], "restore-curated-summary", mode="merge")
    restored = query(USES_QUERY, "evidence-uses-restored")
    assert restored["rows"] == uses["rows"]

    # A violating specimen reaches the backend in a second fresh graph. This
    # demonstrates why the curation guard is needed; it never changes the pilot.
    incomplete = node("EvidenceUse", evidence_use_id="use-incomplete", purpose="probe",
                      basis="Deliberately missing all roles", summary="Not domain evidence")
    try:
        OmnigraphGenerator(SCHEMA).validate_reified_roles([incomplete])
    except ValueError:
        pass
    else:
        raise AssertionError("Curation guard admitted an incomplete relationship")
    incomplete_graph = output / "incomplete-probe.omni"
    run("init", "--schema", schema, incomplete_graph)
    incomplete_data = output / "incomplete-probe.jsonl"
    incomplete_data.write_text(json.dumps(incomplete) + "\n", encoding="utf-8")
    run("load", incomplete_graph, "--data", incomplete_data, "--mode", "append", "--json")
    incomplete_result = json.loads(run("query", "--store", incomplete_graph,
                                       "-e", IDENTITY_QUERY, "--json").stdout)
    assert incomplete_result["rows"] == [{"identity": "use-incomplete", "summary": "Not domain evidence"}]
    joined = json.loads(run("query", "--store", incomplete_graph, "-e", USES_QUERY, "--json").stdout)
    assert joined["rows"] == []
    probes.append({"name": "missing-reified-roles", "result": "backend-admitted; curation-guard-refused",
                   "consequence": "Incomplete source uses disappear from joined trails"})

    report = {
        "versions": {"omnigraph": version, "python": platform.python_version(),
                     **{name: importlib.metadata.version(name) for name in
                        ["omnigraph-linkml-generator", "linkml", "linkml-runtime"]}},
        "schema_sha256": hashlib.sha256(schema.read_bytes()).hexdigest(),
        "inputs_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in [SCHEMA, QUERY, ROOT / "tests/ta1044_pilot_data.py",
                                       Path(__file__)]},
        "data_sha256": hashlib.sha256((output / "curated-data.jsonl").read_bytes()).hexdigest(),
        "load_receipt": receipt, "source_rows": len(sources["rows"]),
        "judgement_rows": len(preferences["rows"]), "evidence_use_rows": len(uses["rows"]),
        "probes": probes, "commands": commands,
    }
    (output / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output
    report = run_pilot(output)
    print(json.dumps({key: value for key, value in report.items() if key != "commands"}, indent=2))


if __name__ == "__main__":
    main()
