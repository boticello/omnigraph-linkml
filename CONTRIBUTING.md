# Contributing

Use British English in documentation. Report bugs and propose changes through
[GitHub issues](https://github.com/boticello/omnigraph-linkml/issues) and pull
requests. Describe the model, expected output and observed diagnostic or graph
behaviour; avoid attaching private data.

Keep models role-based. New backend projections must preserve the shared meaning
of entities, relationships and interfaces. Do not silently infer reification,
direction or discarded constraints. Document admitted/refused cases and add tests
that reach the relevant behaviour. A generator change and a backend upgrade need
evidence suited to their different contracts.

## Development and checks

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install --no-build-isolation -c requirements-dev.txt -e '.[test,dev]'
.venv/bin/python scripts/generate_artifacts.py
.venv/bin/python scripts/check_documentation.py
.venv/bin/ruff check src tests scripts
.venv/bin/mypy src
OMNIGRAPH_REQUIRE_INTEGRATION=1 .venv/bin/python -m pytest
.venv/bin/python -m build
.venv/bin/python scripts/check_distribution_contents.py dist/*
.venv/bin/twine check dist/*
```

Install exactly Omnigraph 0.11.0 and check `omnigraph --version` before the required
integration run. Fixture artefacts and graph files are ignored local output.
Tests use fresh disposable graphs. CI repeats the checks on Python 3.11 and 3.14
and installs the built wheel into a separate environment, running its CLI outside
the checkout.

The sdist deliberately includes source, tests, fixtures, build helpers, selected
public docs and licence files. Wheels contain generator modules, standard metadata
and the licence. Extend build and verification allowlists deliberately; do not
include local records, caches or downloaded sources. Before a release, inspect
archive contents and rendered metadata as well as test results.

Version 0.1.0 currently identifies source, not a claimed PyPI release. An authorised
release should update the changelog, pass review and CI, then use a matching version
tag. Package publication is a separate action; CI does not upload to a package index.
