"""Executed domain results and refusals, not just schema/query admission."""
import pytest

from linkml_omnigraph import OmnigraphDataValidationError, OmnigraphGenerator
from tests.ta1044_pilot import SCHEMA, run_pilot
from tests.ta1044_pilot_data import edge, records


def test_ta1044_mortality_branch(tmp_path):
    report = run_pilot(tmp_path / "pilot")
    assert report["source_rows"] == 6
    assert report["judgement_rows"] == 4
    assert report["evidence_use_rows"] == 4
    assert len(report["probes"]) == 6


@pytest.mark.parametrize("violation", ["missing", "multiple", "wrong-type"])
def test_curation_guard_refuses_invalid_source_use(violation):
    corpus = records()
    role = next(row for row in corpus if row.get("edge") == "EvidenceUseSource")
    if violation == "missing":
        corpus.remove(role)
    elif violation == "multiple":
        corpus.append(edge("EvidenceUseSource", "second-source", role["from"], "jiao-2023"))
    else:
        role["to"] = "company-mortality"
    with pytest.raises(OmnigraphDataValidationError, match="EvidenceUse.*role source"):
        OmnigraphGenerator(SCHEMA).validate_reified_roles(corpus)
