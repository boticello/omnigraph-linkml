# Compatibility and limits

The qualified backend is exactly **Omnigraph 0.11.0 on newly initialised
format-v9 local graphs**. Earlier/later versions, existing stores, Edge and
served/cluster operation need separate qualification. Generating a schema does
not open a store or upgrade its format. Do not treat fresh-schema admission as
evidence that an existing-store migration is safe.

Python 3.11 and 3.14 are tested in CI. Runtime dependencies retain supported
minimum ranges; `requirements-dev.txt` pins the reproducible development stack.
Passing those pins does not establish compatibility with every permitted
dependency version. Source version 0.1.0 is not evidence of a package-index release.

CI requires the qualified backend and runs generation, quality checks, tests,
package-content and metadata checks and an installed-wheel smoke test. A missing
backend cannot silently skip integration tests in CI. Local integration tests may
skip if the CLI is absent unless `OMNIGRAPH_REQUIRE_INTEGRATION=1`; an available
unsupported version fails qualification.

Evidence has different scopes:

| Check | What it demonstrates |
| --- | --- |
| Generation tests | Admitted/refused source cases and deterministic schema output. |
| Fresh `omnigraph init` | Backend admission of that schema. |
| Query lint | Query typing against that schema. |
| Executed fixture and pilot tests | The asserted load, query, identity and constraint behaviours under their stated conditions. |
| Package checks | Deliberate archive membership, metadata and an installed CLI outside the checkout. |

The [TA1044 example](example-ta1044.md) covers one manually curated recommendation
branch. It does not establish extraction accuracy, complete source coverage,
clinical correctness, numerical lineage or suitability for production ingestion.
The optional [role preflight](validation.md) checks complete projected batches;
the backend itself still admits missing reified roles.

Decimal lowers to F64 without exact precision. URI ranges lower to String without
URI validation. Full-text intent has no generated schema directive. Embedding
declarations do not fill missing vectors during load. Schema admission and query
results do not prove broad index coverage or performance. Consult the
[mapping rules](mapping.md) before choosing an unsupported shape or constraint.
