# Omnigraph LinkML Generator

A LinkML generator for Omnigraph `.pg` schemas. It projects a role-based domain
model into graph nodes, directed binary edges and interfaces.

Requires Python 3.11 or later. From an unpacked source distribution:

```bash
python -m pip install .
gen-omnigraph model.yaml -o model.pg
```

Annotate classes with `kind: entity`, `kind: relationship` or `kind: interface`.
Relationship endpoint slots use the shared `role` annotation; backend direction
can be specified with `og_from_role` and `og_to_role`. Native edges require exactly
two named roles, each required and single-valued, with non-abstract entity types
as participants. Set `og_relationship_mode: reified` to
project a binary or n-ary relationship into a node with outgoing role edges.
Reification is explicit and is never selected automatically.

Entity identifiers map to node keys. Native edges reject relationship identifiers;
their supported uniqueness tuple contains both endpoint slots and optionally one
required String property. Reified relationships require one scalar identifier and
reject endpoint-aware uniqueness. Embedded values and unsupported mappings fail
with diagnostics.

The qualified backend is Omnigraph 0.11.0 on fresh format-v9 graphs. Generation
does not open or upgrade graph stores. Decimal values lower to F64 and may lose
precision. Embedding declarations do not fill missing vectors during ingestion.
Schema generation and fixture checks do not establish domain-specific ingestion
completeness, physical index coverage or performance.

Before loading a complete batch of projected Omnigraph JSONL records, callers can
explicitly validate reified role sets:

```python
import json
from linkml_omnigraph import OmnigraphGenerator, OmnigraphDataValidationError

generator = OmnigraphGenerator("model.yaml")
with open("records.jsonl", encoding="utf-8") as source:
    generator.validate_reified_roles(json.loads(line) for line in source)
```

The method returns `None` on success and raises `OmnigraphDataValidationError`
for invalid role sets or unsupported batch/key forms. Schema admission errors
remain `OmnigraphGeneratorError`. Each reified node must have exactly one outgoing
edge for every declared role, pointing to the declared non-abstract entity type
present in the same batch. Generated role-edge names and keys come from the schema.
Record order does not matter; duplicate relevant node keys, orphan role edges,
unknown record types and unsupported references are refused.

Supply projected records with `type`/`data` for nodes and `edge`/`from`/`to` for
edges. Relevant nodes need a single scalar primary key; references must be its
non-null JSON scalar value and type, without coercion. Composite/list/vector keys,
unkeyed participants and ambiguous generated role-edge names are refused before
reading records. Structured references are unsupported. This is an opt-in
complete-batch role check: it does
not inspect an existing store, validate incremental writes or all scalar/property
constraints, load data or change backend enforcement. Native-edge properties and
endpoints remain outside this role-set check. Memory use grows with the batch.

Canonical scalar datatype names are:

- `string`
- `boolean`
- `integer`
- `float`
- `double`
- `decimal`
- `date`
- `datetime`
- `uri`

Inline enums and scalar lists are supported; compatibility aliases and enum lists
are rejected.

The source version is 0.1.0; this document does not establish a published release.
Source distributions contain the generator, tests, fixtures and build helpers.
The public source repository and user documentation are available at
[omnigraph-linkml](https://github.com/boticello/omnigraph-linkml).
Code and original documentation use the MIT licence, copyright 2026 Boticello.
Linked third-party documents retain their own terms.
