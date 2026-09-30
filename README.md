# Omnigraph LinkML

Generate Omnigraph `.pg` schemas from LinkML domain models. Model independently
identified entities, reusable interfaces and relationships with named participant
roles, then choose a graph projection explicitly.

The Python distribution is `omnigraph-linkml-generator`, the import package is
`linkml_omnigraph`, and the command is `gen-omnigraph`. This repository contains
the maintained implementation, tests and user documentation. Python 3.11 and 3.14
are tested; the qualified graph backend is **Omnigraph 0.11.0 on fresh format-v9
graphs**.

## Install and generate a schema

Install from this checkout; no package-index release is claimed:

```bash
git clone https://github.com/boticello/omnigraph-linkml.git
cd omnigraph-linkml
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/gen-omnigraph tests/fixtures/linkml/basic.yaml -o generated/basic.pg
```

With Omnigraph 0.11.0 installed, initialise a disposable graph and check its query:

```bash
omnigraph init --schema generated/basic.pg "$(mktemp -d)/example.omni"
omnigraph lint --schema generated/basic.pg --query tests/fixtures/omnigraph/basic.gq --json
```

The generator writes schema text only; it does not load data, operate an existing
store or migrate graph formats. See the [authoring guide](docs/authoring.md) for
a complete model and [mapping reference](docs/mapping.md) for supported rules.

## Choose a relationship projection

| Projection | Use and limits |
| --- | --- |
| Native edge (default) | Two named roles, each required and single-valued, with non-abstract entity types as participants. Explicit direction or a recognised role pair. No relationship identifier. A uniqueness constraint may use both endpoints and optionally one required String property. |
| Reified relationship | Set `og_relationship_mode: reified`. Two or more such roles and one required scalar identifier. Produces a relationship node and one outgoing edge per role. |

Reification is never automatic. Embedded values, implicit edges from entity slots,
polymorphic participants and unsupported constraints are refused with diagnostics.
The optional Python [complete-batch role validator](docs/validation.md) checks
reified participant edges before ingestion; it is not a general data validator.

## Run the evidence-tracing example

The [TA1044 example](docs/example-ta1044.md) generates a schema, loads manually
curated public-source records into fresh graphs and executes recommendation-to-source
queries. It preserves competing judgements and uncertainty. This is a bounded
modelling example, not a clinical assessment or a complete explanation of the
recommendation.

```bash
.venv/bin/python -m tests.ta1044_pilot --output generated/ta1044/example
```

The output directory must be new. Execution is offline and requires the qualified
Omnigraph CLI. The example writes local graph files and a results receipt.

Read [compatibility and limits](docs/compatibility.md) before relying on the output,
and [CONTRIBUTING](CONTRIBUTING.md) for development and verification. The source
version is 0.1.0; [CHANGELOG](CHANGELOG.md) distinguishes source history from releases.
Code and original documentation are available under the [MIT licence](LICENSE).
Third-party sources linked by the example retain their own terms.
