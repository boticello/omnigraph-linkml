# Authoring a model

Give each materialised class an explicit `kind` annotation. An `entity` is an
independently modelled object; an `interface` is reusable shape; a `relationship`
is an association with named roles. A relationship's direction is a backend
projection choice. `embedded` values are unsupported by this generator.

Every admitted participant role must be required and single-valued: each
relationship instance has exactly one participant in that role. For the usual
form, write `required: true` and leave `multivalued` absent or false. Alternatively,
explicit cardinality must resolve to exactly one participant (effective bounds
1..1). Its range must be a specific,
non-abstract entity class, rather than an interface or abstract class.

Here is a complete binary example. Save it as `model.yaml`:

```yaml
id: https://example.org/employment
name: employment
prefixes:
  linkml: https://w3id.org/linkml/
  example: https://example.org/employment/
default_prefix: example
imports:
  - linkml:types
classes:
  Person:
    annotations:
      kind: entity
    attributes:
      person_id:
        range: string
        identifier: true
        required: true
  Organisation:
    annotations:
      kind: entity
    attributes:
      org_id:
        range: string
        identifier: true
        required: true
  Employment:
    annotations:
      kind: relationship
      og_from_role: employee
      og_to_role: employer
    attributes:
      person:
        range: Person
        required: true
        annotations:
          role: employee
      organisation:
        range: Organisation
        required: true
        annotations:
          role: employer
      title:
        range: string
```

Run `gen-omnigraph model.yaml -o model.pg`. The relationship becomes:

```pg
edge Employment: Person -> Organisation {
  title: String?
}
```

The role labels `employee` and `employer` supply meaning; `og_from_role` and
`og_to_role` select direction. They refer to role **values**, not slot names.
Without explicit controls, only the pairs `from`/`to`, `source`/`target` and
`subject`/`object` resolve direction. Declaration order is not a fallback.

For a relationship with independent identity or three or more participants, use
`og_relationship_mode: reified` and one required scalar `identifier: true` slot.
Do not include native direction annotations in that mode. The checked-in
[Membership](../tests/fixtures/linkml/reified_relationship.yaml) and
[three-role example](../tests/fixtures/linkml/reified_nary_relationship.yaml)
show complete inputs. A Membership instance becomes a Membership node with
`MembershipMember` and `MembershipTeam` edges pointing to its participants.
Check loaded role completeness separately using [batch validation](validation.md).

Interfaces use `kind: interface` and can be inherited through `is_a` or `mixins`;
the [basic fixture](../tests/fixtures/linkml/basic.yaml) includes `NamedThing`.
Class-valued entity properties do not create edges. Model associations as explicit
relationship classes instead.

Use uppercase-initial type names (`Person`) and lowercase-initial property/role
names (`person_id`, `employee`). Type names must match `[A-Z][A-Za-z0-9_]*`;
property names must match `[a-z][A-Za-z0-9_]*`. Names are preserved, without
renaming or escaping. Leading underscores are refused. Inline enum tokens must
match `[A-Za-z0-9][A-Za-z0-9_-]*`.

Declare identifiers and required properties explicitly. Use canonical scalar
types from the [mapping reference](mapping.md), rather than storage widths or
compatibility aliases. Unsupported models raise `OmnigraphGeneratorError` in
Python or produce a non-zero CLI exit with a diagnostic.
