# Example: trace a mortality evidence branch

This example models a bounded source trail from NICE TA1044 recommendation 1.1
through published committee discussion to mortality analyses and their source
documents. It uses manually curated identifiers, short original paraphrases and
source locations from public documents. It contains no patient records or full
source PDFs. It is an engineering example, not clinical advice, an appraisal of
article findings or the complete justification for the recommendation.

## Run it

From the repository root after [installation](../README.md), with Omnigraph 0.11.0:

```bash
.venv/bin/python -m tests.ta1044_pilot --output generated/ta1044/example
```

Choose a new output directory each time. The runner refuses an existing directory,
creates fresh local graphs, generates the schema, checks complete reified role
sets, loads the records, lints and executes queries, and asserts expected rows and
constraint refusals. Execution is offline. `results.json` records commands,
versions, input/output hashes and query results; graph files remain in that output
directory for inspection. It never targets an existing store.

The [model](../tests/fixtures/linkml/ta1044.yaml),
[curated records](../tests/ta1044_pilot_data.py),
[main query](../tests/fixtures/omnigraph/ta1044.gq) and
[runner](../tests/ta1044_pilot.py) are available for inspection.

## Read the result

Recommendation, Passage, Analysis and SourceDocument are identified entities
sharing a Locatable interface. Native binary relationships connect the discussion
trail and distinguish stances about the same analysis. EvidenceUse has its own
identity and three roles: analysis, source document and documenting passage.
Explicit reification preserves different uses of the same paper.

The run loads 16 nodes and 19 edges. Expected results are six source-trail rows,
four attributed judgements and four distinct evidence uses. Company and EAG
positions remain distinct, including criticism of both mortality alternatives,
the committee's retained validation uncertainty and the unresolved ICER report
edition. A joined judgement about an analysis is not an independent appraisal
of every source used by it.

The recommendation-to-conclusion correspondence is labelled as curated. The
3.28 → 3.26 → 3.8 references and source uses are located in their respective
passages. The later EAG critique is available in the source-use lookup but has
no invented route from the recommendation. Missing roles are refused by preflight;
a separate probe shows that the backend admits an incomplete reified node whose
complete-role join returns no rows.

Other probes exercise pattern/range/uniqueness refusal and reified identity.
They assert the tested graph state, rather than treating query lint as runtime
evidence. No concurrent ingestion, migration or broad performance claim follows.

## Provenance and limits

Source identities and locations were inspected on 30 September 2026. Bibliographic
identity was checked; individual article tables and numerical calculations were
not reanalysed. These links identify source documents, whose content remains
subject to its original terms:

| Source | Selected location |
| --- | --- |
| [TA1044 recommendations](https://www.nice.org.uk/guidance/ta1044/chapter/1-Recommendations) | 1.1 |
| [Committee discussion](https://www.nice.org.uk/guidance/ta1044/chapter/3-Committee-discussion) | 3.28, 3.26, 3.8 |
| [Committee papers](https://www.nice.org.uk/guidance/ta1044/documents/committee-papers-2) | PDF p.393 / report p.69, Table 15; PDF p.408 / report p.84, Issue 3 |
| [Desai et al. (2020)](https://doi.org/10.1007/s00277-020-04233-w) | Named company mortality input source |
| [Jiao et al. (2023)](https://doi.org/10.1182/bloodadvances.2022009202) | Earlier EAG input and distinct later critique source use |
| [ICER assessment materials](https://icer.org/assessment/sickle-cell-disease-2023/) | Report family; exact edition unresolved |

Coverage is deliberately small and depends on manual curation. The recommendation
has other clinical, economic and normative branches. Meeting history, individual
numerical inputs and production use are outside this example. Website dates are
not interpreted as committee meeting dates. The project's MIT licence covers
the code and original curation/documentation, not the linked third-party documents.
