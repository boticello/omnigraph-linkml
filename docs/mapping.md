# Mapping reference

These rules describe the implemented generator for the qualified backend in
[compatibility](compatibility.md). They define an admitted subset of LinkML;
unsupported constructs are rejected rather than silently lowered.

## Classes and roles

| Input | Output and admission rules |
| --- | --- |
| `kind: entity` | A node, with scalar properties. |
| `kind: interface` | An interface, applied through `is_a` and `mixins`. |
| `kind: relationship`, absent mode or `native_edge` | A directed binary edge with exactly two concrete non-abstract entity roles. Each is singular and exact-one. |
| `kind: relationship`, `og_relationship_mode: reified` | A node with one required scalar identifier and an outgoing incident edge for each of two or more roles. Participants have the same concrete/singular/exact-one restriction. |
| Missing `kind`, `kind: embedded` | Refused. |

Slot `role` annotations identify participants. Native direction comes from both
`og_from_role`/`og_to_role` controls or a recognised conventional pair; see
[authoring](authoring.md). Role slots become endpoints or incident edges, never
scalar body properties. Optional or multivalued roles, abstract/interface ranges,
ambiguous direction and implicit edges from entity properties are refused.

Source participation cardinality describes one relationship instance. It is not
graph-wide edge multiplicity, so the generator emits no `@card` from it.
Schema admission alone does not enforce loaded reified role completeness.
Incident names are `<RelationshipName><RoleValueWithUppercaseFirstLetter>`;
collisions with class declarations are refused. [Batch validation](validation.md)
also refuses ambiguous generated role-edge projections.

`lifecycle` accepts `independent` or `shared`; `read_shape` accepts `reference`
or `inline`. These are validated shared annotations with no output
effect. They do not emit directives or metadata. Backend controls are explicitly
`og_`-prefixed; storage shape is not the shared domain model.

## Properties and scalar types

| LinkML range or shape | Omnigraph output |
| --- | --- |
| `string`, `uri` | `String`; URI lexical semantics are not enforced by this lowering. |
| `boolean` | `Bool` |
| `integer` | `I64` |
| `float`, `double`, `decimal` | `F64`; decimal precision may be lost. |
| `date`, `datetime` | `Date`, `DateTime` |
| Inline enum | `enum(...)` with valid tokens; no escaping added. |
| `multivalued: true` scalar | `[Type]` |
| Numeric vector with `vector_dimensions: N` | `Vector(N)` |

`required: true` emits a non-nullable property; absent/false emits `?`.
Unsupported ranges include `time`, custom datatypes, `int`, `long`, `bool`,
`positive_integer`, `non_negative_integer`, `token`, `bytes`, `normalized_string`,
`ncname`, `uriorcurie` and `curie`. Enum lists, class lists, nested objects, maps
and arbitrary JSON are not admitted. See the [supported types fixture](../tests/fixtures/linkml/supported_types.yaml).

Ordinary properties named `id`, `src` and `dst` are allowed. Native-edge body
properties named `from` and `to` are refused; node properties and endpoint role
slots with those names are allowed. The [identifier policy tests](../tests/test_generator_identifier_policy.py)
exercise these distinctions.

## Identity and uniqueness

An entity's single identifier emits `@key(property)`. With no identifier and
exactly one unambiguous required `unique_keys` declaration, its members can be
promoted to a composite node key. Other supported property uniqueness declarations
emit `@unique`. Node keys supply backend identity; uniqueness is a constraint.

Native relationships reject identifiers and emit no inferred edge `@key`.
Exactly one class `unique_keys` tuple may contain both endpoint **slot names**
and optionally one required scalar String body property. It emits
`@unique(@src, @dst[, property])`. Member order does not change the constraint.
Missing/repeated/unknown endpoints, multiple or empty declarations, property-only
tuples, more than one body member, enum/non-String/list/optional body members and
`consider_nulls_inequal: true` are refused. Without a constraint, parallel edge
occurrences remain possible. A repeated unique tuple is refused; it does not
select upsert identity. See [the edge uniqueness fixture](../tests/fixtures/linkml/edge_uniqueness.yaml).

Reified relationships require one required scalar identifier as node key.
Property-only `unique_keys` may emit node `@unique`. Composite relationship
identity, generated identifiers and endpoint-aware uniqueness are refused.
Slot `annotations: {unique: true}` on an emitted property supplies property
uniqueness; it is not a LinkML slot predicate.

## Constraints and search

| Input | Output and limits |
| --- | --- |
| Numeric `minimum_value` / `maximum_value` | Node `@range` when expressible. |
| String `pattern` | Node `@check`. |
| `index: scalar` | Property `@index`. |
| String `index: fulltext` | Accepted search intent, with no generated schema directive or companion artefact. |
| `index: vector` with dimensions | `Vector(N)` and `@index`; no tuning parameters. |
| `og_embed_source: slot` on a vector | `@embed("slot")`; source must be a String property on the same owner. |

Native-edge bodies reject range and pattern declarations because the admitted
backend edge schema does not support those node constraints. Reified body
properties use node rules. Embedding declarations do not populate missing
vectors during the qualified backend's load operation; supply prepared vectors.
Index declarations and query linting do not establish physical index coverage,
embedding execution or performance.

Automatic reification, query generation, configurable scalar lowering,
slot-derived edges, metadata emission and store migration are unsupported.
