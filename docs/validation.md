# Validate reified roles before loading

Generated schemas cannot require a complete set of incident role edges around
a reified relationship node. An incomplete node can be stored but disappear from
a query that joins through every participant. Call the optional Python validator
on a **complete batch** before loading it:

```python
import json
from linkml_omnigraph import OmnigraphGenerator, OmnigraphDataValidationError

generator = OmnigraphGenerator("model.yaml")
with open("records.jsonl", encoding="utf-8") as source:
    generator.validate_reified_roles(json.loads(line) for line in source)
```

The method returns `None` on success. It raises `OmnigraphDataValidationError`
for invalid role sets, records or unsupported validation projections. Schema
admission failures raise `OmnigraphGeneratorError` separately. Neither outcome
loads records or changes a store.

Nodes use `{"type": "Person", "data": {"person_id": "p1"}}`. Edges use
`{"edge": "MembershipMember", "from": "m1", "to": "p1"}`. Each reified node
must have exactly one outgoing edge for every declared role, to a node of the
declared non-abstract entity type present in the same batch. Record order does
not matter. Duplicate relevant keys, missing/multiple/wrong-type participants,
orphan role edges, unknown types and unsupported references are refused.

The supported validation projection requires relevant relationship and participant
nodes to have one scalar primary key. References must match its non-null JSON
scalar value **and type**, without coercion. Structured references, composite/list/
vector keys and unkeyed participants are refused before records are consumed.
Generated role-edge projections must be unambiguous. A schema may be admitted for
generation yet refused for this narrower validation use.

Supply the whole projected batch, including participants. The validator does not
query an existing store, validate incremental writes, enforce every scalar/property
constraint or check native-edge properties/endpoints. It does not make concurrent
ingestion safe or replace backend checks. Memory use grows with the batch.

The [TA1044 runner](../tests/ta1044_pilot.py) demonstrates preflight followed by
an explicit load. [Role validation tests](../tests/test_role_validation.py) include
positive, ordering, malformed-record and unsupported-key cases.
