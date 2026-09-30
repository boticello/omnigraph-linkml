from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from linkml.utils.generator import Generator
from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition
from linkml_runtime.utils.schemaview import SchemaView

from linkml_omnigraph.validation import (
    OmnigraphDataValidationError,
    RoleRule,
    validate_role_records,
)


class OmnigraphGeneratorError(ValueError):
    """Raised when a LinkML construct cannot be projected to Omnigraph."""


@dataclass(frozen=True)
class Property:
    name: str
    type_ref: str
    required: bool
    index: str | None = None
    embed_source: str | None = None
    identifier: bool = False
    unique: bool = False
    minimum_value: Any = None
    maximum_value: Any = None
    pattern: str | None = None

    def declaration(self) -> str:
        suffix = "" if self.required else "?"
        embed = f' @embed("{self.embed_source}")' if self.embed_source else ""
        return f"  {self.name}: {self.type_ref}{suffix}{embed}"


@dataclass(frozen=True)
class Endpoint:
    slot_name: str
    role: str
    range_name: str


class OmnigraphGenerator(Generator):
    """Generate Omnigraph .pg schema from the shared LinkML semantic layer."""

    generatorname = "omnigraphgen"
    generatorversion = "0.1.0"
    valid_formats = ["pg"]
    file_extension = "pg"
    schemaview: Any = None

    scalar_type_map = {
        "string": "String",
        "uri": "String",
        "boolean": "Bool",
        "integer": "I64",
        "float": "F64",
        "double": "F64",
        "decimal": "F64",
        "date": "Date",
        "datetime": "DateTime",
    }

    compatibility_alias_suggestions = {
        "normalized_string": "string",
        "token": "string",
        "ncname": "string",
        "uriorcurie": "string or uri, depending on the intended lexical contract",
        "curie": "string",
        "bool": "boolean",
        "long": "integer",
        "int": "integer",
        "non_negative_integer": "integer with minimum_value if the bound matters",
        "positive_integer": "integer with minimum_value if the bound matters",
        "bytes": "a deliberate project-local type or string encoding policy",
    }

    conventional_roles = (("from", "to"), ("source", "target"), ("subject", "object"))
    type_identifier_pattern = re.compile(r"^[A-Z][A-Za-z0-9_]*$")
    property_identifier_pattern = re.compile(r"^[a-z][A-Za-z0-9_]*$")
    enum_value_pattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    edge_reserved_property_names = {"from", "to"}

    # Canonical values for the shared class-level annotations defined in
    # docs/mapping.md. These have no Omnigraph
    # schema effect, but the generator validates their values so a typo such as
    # ``lifecycle: shred`` fails closed rather than being silently ignored.
    canonical_lifecycle_values = {"independent", "shared"}
    canonical_read_shape_values = {"reference", "inline"}

    def __post_init__(self) -> None:
        try:
            super().__post_init__()
        except ValueError as exc:
            if str(exc) == "unique_key_slots must be supplied":
                raise OmnigraphGeneratorError(
                    "Every unique_keys declaration must supply non-empty unique_key_slots."
                ) from exc
            alias = self._compatibility_alias_from_error(exc)
            if alias is not None:
                raise OmnigraphGeneratorError(self._compatibility_alias_message(alias)) from exc
            multiple_identifier = self._multiple_identifier_from_error(exc)
            if multiple_identifier is not None:
                raise OmnigraphGeneratorError(self._multiple_identifier_message(multiple_identifier)) from exc
            raise
        except TypeError as exc:
            detail = self._unknown_attribute_from_error(exc)
            if detail is not None:
                raise OmnigraphGeneratorError(self._unknown_attribute_message(detail)) from exc
            raise

    def serialize(self, **kwargs: Any) -> str:
        return self.generate()

    def validate_reified_roles(self, records: Iterable[Mapping[str, Any]]) -> None:
        """Validate exact-one role sets in a complete projected JSONL record batch.

        All reified nodes and their participants must be present in the batch,
        using scalar primary-key values as from/to references. No graph is read
        or written. This checks role sets, not general properties or incremental
        writes; unsupported key/reference forms fail explicitly.
        """
        self.generate()  # Share the full schema-admission and projection contract.
        classes = self.schemaview.all_classes(imports=False)
        keys: dict[str, str] = {}
        rules: list[RoleRule] = []
        node_types: set[str] = set()
        edge_types: set[str] = set()
        for cls in classes.values():
            kind = self._annotation(cls, "kind")
            if kind == "entity":
                node_types.add(cls.name)
            elif kind == "relationship":
                if self._relationship_mode(cls) != "reified":
                    edge_types.add(cls.name)
                    continue
                node_types.add(cls.name)
                for endpoint in self._reified_relationship_endpoints(cls):
                    edge_name = self._reified_role_edge_name(cls, endpoint)
                    if edge_name in edge_types:
                        raise OmnigraphDataValidationError(
                            f"{cls.name} role {endpoint.role}: ambiguous generated role edge {edge_name}; "
                            "role preflight requires distinct role-edge names"
                        )
                    rules.append(RoleRule(cls.name, endpoint.role, edge_name, endpoint.range_name))
                    edge_types.add(edge_name)
        needed = {rule.relationship for rule in rules} | {rule.participant for rule in rules}
        for name in sorted(needed):
            if name not in classes:
                raise OmnigraphDataValidationError(f"{name}: role preflight requires a locally emitted node class")
            cls = classes[name]
            key: list[str] | None
            if self._annotation(cls, "kind") == "relationship":
                props = [self._property_for_slot(slot, owner=cls, emitted_owner_kind="entity")
                         for slot in self._own_slots(cls) if slot.identifier]
                key = [prop.name for prop in props]
            else:
                props = self._properties_for_class(cls, include_inherited=False)
                key, _ = self._keys_for_node(cls, props)
            if key is None or len(key) != 1 or next(
                prop.type_ref for prop in props if prop.name == key[0]
            ).startswith(("[", "Vector(")):
                raise OmnigraphDataValidationError(
                    f"{name}: role preflight requires a single scalar key; "
                    "composite, unkeyed, list and vector key references are unsupported"
                )
            keys[name] = key[0]
        validate_role_records(records, keys, rules, node_types, edge_types)

    def generate(self) -> str:
        declarations: list[str] = []
        if self.schemaview is None:
            self.schemaview = SchemaView(self.schema)
        classes = self.schemaview.all_classes(imports=False)

        for class_name in sorted(classes):
            cls = classes[class_name]
            kind = self._annotation(cls, "kind")
            if kind is None:
                raise OmnigraphGeneratorError(
                    f"Class {class_name} is missing required annotation kind "
                    "(expected entity, relationship, interface, or embedded)."
                )
            self._validate_type_identifier(cls.name, context=f"{kind} class")
            self._validate_shared_class_annotations(cls)
            if kind == "interface":
                declarations.append(self._emit_interface(cls))
            elif kind == "entity":
                declarations.append(self._emit_node(cls))
            elif kind == "relationship":
                declarations.extend(self._emit_relationship(cls))
            elif kind == "embedded":
                raise OmnigraphGeneratorError(
                    f"Class {class_name} has kind: embedded, which Omnigraph does not support in this generator slice."
                )
            else:
                raise OmnigraphGeneratorError(
                    f"Class {class_name} has unsupported kind {kind!r}; expected entity, relationship, interface, or embedded."
                )

        return "\n\n".join(declarations).rstrip() + "\n"

    def _emit_interface(self, cls: ClassDefinition) -> str:
        lines = [f"interface {cls.name} {{"]
        for prop in self._properties_for_class(cls, include_inherited=False):
            lines.append(prop.declaration())
        lines.append("}")
        return "\n".join(lines)

    def _emit_node(self, cls: ClassDefinition) -> str:
        implements = self._implemented_interfaces(cls)
        header = f"node {cls.name}"
        if implements:
            header += " implements " + ", ".join(implements)
        header += " {"

        props = self._properties_for_class(cls, include_inherited=False)
        primary_key, unique_keys = self._keys_for_node(cls, props)

        lines = [header]
        lines.extend(prop.declaration() for prop in props)
        if primary_key:
            lines.append(f"  @key({', '.join(primary_key)})")
        lines.extend(f"  @unique({prop.name})" for prop in props if prop.unique and not prop.identifier)
        lines.extend(f"  @unique({', '.join(slots)})" for slots in unique_keys)
        lines.extend(f"  @index({prop.name})" for prop in props if prop.index in {"scalar", "vector"})
        lines.extend(self._range_declaration(prop) for prop in props if self._has_range_constraint(prop))
        lines.extend(self._check_declaration(prop) for prop in props if prop.pattern is not None)
        lines.append("}")
        return "\n".join(lines)

    def _emit_relationship(self, cls: ClassDefinition) -> list[str]:
        mode = self._relationship_mode(cls)
        if mode == "native_edge":
            return [self._emit_edge(cls)]
        if mode == "reified":
            return self._emit_reified_relationship(cls)
        raise OmnigraphGeneratorError(
            f"Relationship {cls.name} has unsupported og_relationship_mode {mode!r}; expected native_edge or reified."
        )

    def _emit_edge(self, cls: ClassDefinition) -> str:
        endpoints = self._relationship_endpoints(cls)
        from_ep, to_ep = self._resolve_direction(cls, endpoints)
        props = []
        endpoint_slots = {from_ep.slot_name, to_ep.slot_name}
        for slot in self._native_edge_slots(cls):
            if slot.name in endpoint_slots:
                self._validate_relationship_endpoint_cardinality(cls, slot)
                if slot.identifier:
                    raise OmnigraphGeneratorError(
                        f"Relationship {cls.name} endpoint slot {slot.name} cannot be an identifier in native edge mode."
                    )
                continue
            if self._slot_declares_explicit_cardinality(slot):
                raise OmnigraphGeneratorError(
                    f"Relationship {cls.name} slot {slot.name} declares LinkML cardinality, "
                    "which native edge mode does not map to Omnigraph edge constraints."
                )
            if self._is_class_range(slot.range):
                raise OmnigraphGeneratorError(
                    f"Relationship {cls.name} slot {slot.name} is class-valued but is not one of the two projected endpoints."
                )
            if slot.identifier:
                raise OmnigraphGeneratorError(
                    f"Relationship {cls.name} declares identifier slot {slot.name}; edge identity is deferred."
                )
            if self._slot_has_node_only_constraint(slot):
                raise OmnigraphGeneratorError(
                    f"Relationship {cls.name} slot {slot.name} uses node-only constraints; @range and @check are not supported on edges."
                )
            props.append(self._property_for_slot(slot, owner=cls))

        unique_tuple = self._native_edge_unique_tuple(cls, from_ep, to_ep, props)
        lines = [f"edge {cls.name}: {from_ep.range_name} -> {to_ep.range_name} {{"]
        lines.extend(prop.declaration() for prop in props)
        lines.extend(f"  @unique({prop.name})" for prop in props if prop.unique)
        if unique_tuple:
            lines.append(f"  @unique({', '.join(unique_tuple)})")
        lines.extend(f"  @index({prop.name})" for prop in props if prop.index in {"scalar", "vector"})
        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def _native_edge_unique_tuple(
        cls: ClassDefinition, from_ep: Endpoint, to_ep: Endpoint, props: list[Property]
    ) -> list[str] | None:
        """Project the qualified tuple constraint without selecting edge identity.

        The supported policy admits both endpoint slots plus at most one required scalar
        String property. Canonical endpoint order follows the resolved header,
        irrespective of source member ordering or the spelling of role labels.
        """
        keys = cls.unique_keys or {}
        if not keys:
            return None
        context = f"Relationship {cls.name} native-edge unique key"
        if len(keys) != 1:
            raise OmnigraphGeneratorError(f"{context} requires exactly one unique_keys declaration.")
        name, key = next(iter(keys.items()))
        context += f" {name}"
        members = list(key.unique_key_slots or [])
        if not members:
            raise OmnigraphGeneratorError(f"{context} must declare non-empty unique_key_slots.")
        if len(set(members)) != len(members):
            raise OmnigraphGeneratorError(f"{context} has repeated unique_key_slots; list each slot once.")
        if key.consider_nulls_inequal:
            raise OmnigraphGeneratorError(f"{context} does not support consider_nulls_inequal: true.")
        endpoints = {from_ep.slot_name, to_ep.slot_name}
        properties = {prop.name: prop for prop in props}
        unknown = set(members) - endpoints - properties.keys()
        if unknown:
            raise OmnigraphGeneratorError(f"{context} references unknown or unemitted slots: {', '.join(sorted(unknown))}.")
        if not endpoints.issubset(members):
            raise OmnigraphGeneratorError(
                f"{context} must contain both endpoint slots: {from_ep.slot_name}, {to_ep.slot_name}."
            )
        body = [member for member in members if member not in endpoints]
        if len(body) > 1:
            raise OmnigraphGeneratorError(f"{context} supports at most one body property.")
        if body:
            prop = properties[body[0]]
            if not prop.required or prop.type_ref != "String":
                raise OmnigraphGeneratorError(
                    f"{context} body member {prop.name} must be a required scalar String property."
                )
        return ["@src", "@dst", *body]

    def _emit_reified_relationship(self, cls: ClassDefinition) -> list[str]:
        if self._annotation(cls, "og_from_role") or self._annotation(cls, "og_to_role"):
            raise OmnigraphGeneratorError(
                f"Relationship {cls.name} uses native-edge direction annotations with og_relationship_mode: reified; "
                "reified incident edges always point from the relationship node to role players."
            )
        endpoints = self._reified_relationship_endpoints(cls)
        endpoint_slots = {endpoint.slot_name for endpoint in endpoints}
        props = []
        identifier_slots = []
        for slot in self._own_slots(cls):
            if slot.name in endpoint_slots:
                self._validate_relationship_endpoint_cardinality(cls, slot)
                if slot.identifier:
                    raise OmnigraphGeneratorError(
                        f"Relationship {cls.name} endpoint slot {slot.name} cannot be an identifier in reified mode; "
                        "use a scalar relationship identifier slot."
                    )
                continue
            if self._is_class_range(slot.range):
                raise OmnigraphGeneratorError(
                    f"Relationship {cls.name} slot {slot.name} is class-valued but has no role annotation; "
                    "reified mode only maps role-player class ranges to incident edges."
                )
            prop = self._property_for_slot(slot, owner=cls, emitted_owner_kind="entity")
            if prop.identifier:
                if not prop.required:
                    raise OmnigraphGeneratorError(
                        f"Relationship {cls.name} identifier slot {slot.name} must be required in reified mode; "
                        "relationship node identity cannot be nullable."
                    )
                identifier_slots.append(prop.name)
            props.append(prop)

        if len(identifier_slots) != 1:
            raise OmnigraphGeneratorError(
                f"Relationship {cls.name} in reified mode must declare exactly one scalar identifier slot; "
                "the generator never invents relationship identifiers."
            )
        self._validate_reified_relationship_unique_keys(cls, endpoint_slots)

        declarations = [self._emit_reified_relationship_node(cls, props)]
        declarations.extend(self._emit_reified_role_edge(cls, endpoint) for endpoint in endpoints)
        return declarations

    def _emit_reified_relationship_node(self, cls: ClassDefinition, props: list[Property]) -> str:
        lines = [f"node {cls.name} {{"]
        lines.extend(prop.declaration() for prop in props)
        primary_key, unique_keys = self._keys_for_node(cls, props)
        if primary_key:
            lines.append(f"  @key({', '.join(primary_key)})")
        lines.extend(f"  @unique({prop.name})" for prop in props if prop.unique and not prop.identifier)
        lines.extend(f"  @unique({', '.join(slots)})" for slots in unique_keys)
        lines.extend(f"  @index({prop.name})" for prop in props if prop.index in {"scalar", "vector"})
        lines.extend(self._range_declaration(prop) for prop in props if self._has_range_constraint(prop))
        lines.extend(self._check_declaration(prop) for prop in props if prop.pattern is not None)
        lines.append("}")
        return "\n".join(lines)

    def _emit_reified_role_edge(self, cls: ClassDefinition, endpoint: Endpoint) -> str:
        edge_name = self._reified_role_edge_name(cls, endpoint)
        return f"edge {edge_name}: {cls.name} -> {endpoint.range_name} {{}}"

    @staticmethod
    def _validate_reified_relationship_unique_keys(cls: ClassDefinition, endpoint_slots: set[str]) -> None:
        unique_keys = getattr(cls, "unique_keys", None) or {}
        for unique_key_name, unique_key in unique_keys.items():
            slots = list(getattr(unique_key, "unique_key_slots", None) or [])
            endpoint_members = [slot for slot in slots if slot in endpoint_slots]
            if endpoint_members:
                raise OmnigraphGeneratorError(
                    f"Relationship {cls.name} unique key {unique_key_name} references endpoint role slots "
                    f"that are incident edges in reified mode: {', '.join(endpoint_members)}. "
                    "Endpoint-aware uniqueness cannot be emitted as an enforceable Omnigraph @unique directive."
                )

    def _properties_for_class(self, cls: ClassDefinition, *, include_inherited: bool) -> list[Property]:
        slots = self.schemaview.class_induced_slots(cls.name) if include_inherited else self._own_slots(cls)
        props = []
        for slot in slots:
            if self._is_class_range(slot.range):
                raise OmnigraphGeneratorError(
                    f"Class {cls.name} slot {slot.name} has class range {slot.range}; explicit kind: relationship classes are required."
                )
            props.append(self._property_for_slot(slot, owner=cls))
        return props

    def _property_for_slot(
        self, slot: SlotDefinition, *, owner: ClassDefinition, emitted_owner_kind: str | None = None
    ) -> Property:
        type_ref = self._type_ref(slot, owner=owner)
        index = self._annotation(slot, "index")
        embed_source = self._annotation(slot, "og_embed_source")
        unique_annotation = self._annotation(slot, "unique")
        minimum_value = getattr(slot, "minimum_value", None)
        maximum_value = getattr(slot, "maximum_value", None)
        pattern = getattr(slot, "pattern", None)
        owner_kind = emitted_owner_kind or self._annotation(owner, "kind") or "class"

        self._validate_property_identifier(slot.name, owner=owner.name, owner_kind=owner_kind)

        if index not in {None, "scalar", "vector", "fulltext"}:
            raise OmnigraphGeneratorError(f"Slot {owner.name}.{slot.name} has unsupported index annotation {index!r}.")
        if index == "vector" and not type_ref.startswith("Vector("):
            raise OmnigraphGeneratorError(f"Slot {owner.name}.{slot.name} uses index: vector but is not a Vector(N) property.")
        if index == "fulltext" and type_ref != "String":
            raise OmnigraphGeneratorError(f"Slot {owner.name}.{slot.name} uses index: fulltext but is not a String property.")
        if embed_source and not type_ref.startswith("Vector("):
            raise OmnigraphGeneratorError(f"Slot {owner.name}.{slot.name} uses og_embed_source but is not a Vector(N) property.")
        if embed_source:
            source_slot = self._slot_named(owner, embed_source)
            if source_slot is None:
                raise OmnigraphGeneratorError(f"Slot {owner.name}.{slot.name} embeds from missing source slot {embed_source!r}.")
            if self._type_ref(source_slot, owner=owner) != "String":
                raise OmnigraphGeneratorError(f"Slot {owner.name}.{slot.name} embeds from {embed_source!r}, which is not a String property.")
        if (minimum_value is not None or maximum_value is not None) and type_ref not in {"I64", "F64"}:
            raise OmnigraphGeneratorError(
                f"Slot {owner.name}.{slot.name} uses minimum_value or maximum_value but maps to non-numeric Omnigraph type {type_ref}."
            )
        if pattern is not None and type_ref != "String":
            raise OmnigraphGeneratorError(f"Slot {owner.name}.{slot.name} uses pattern but maps to non-String Omnigraph type {type_ref}.")

        return Property(
            name=slot.name,
            type_ref=type_ref,
            required=bool(slot.required),
            index=index,
            embed_source=embed_source,
            identifier=bool(getattr(slot, "identifier", False)),
            unique=bool(getattr(slot, "unique", False)) or (unique_annotation or "").lower() == "true",
            minimum_value=minimum_value,
            maximum_value=maximum_value,
            pattern=pattern,
        )

    def _type_ref(self, slot: SlotDefinition, *, owner: ClassDefinition) -> str:
        vector_dimensions = self._annotation(slot, "vector_dimensions")
        if vector_dimensions is not None:
            if not str(vector_dimensions).isdigit() or int(vector_dimensions) <= 0:
                raise OmnigraphGeneratorError(f"Slot {owner.name}.{slot.name} has invalid vector_dimensions {vector_dimensions!r}.")
            if slot.range not in {"float", "double", None}:
                raise OmnigraphGeneratorError(
                    f"Slot {owner.name}.{slot.name} uses vector_dimensions but range {slot.range!r} is not float-compatible."
                )
            return f"Vector({int(vector_dimensions)})"

        if slot.range == "time":
            raise OmnigraphGeneratorError(f"Slot {owner.name}.{slot.name} has range time, which has no native Omnigraph scalar.")
        if slot.range in self.compatibility_alias_suggestions:
            raise OmnigraphGeneratorError(
                f"Slot {owner.name}.{slot.name} uses compatibility-only datatype alias {slot.range!r}. "
                f"Use {self.compatibility_alias_suggestions[slot.range]} instead."
            )
        if slot.range in self.schemaview.all_enums(imports=False):
            if bool(getattr(slot, "multivalued", False)):
                raise OmnigraphGeneratorError(f"Slot {owner.name}.{slot.name} is a multivalued enum, which is unsupported.")
            enum = self.schemaview.get_enum(slot.range)
            self._validate_enum_values(enum_name=slot.range, values=enum.permissible_values.keys(), owner=owner.name, slot_name=slot.name)
            values = ", ".join(enum.permissible_values.keys())
            return f"enum({values})"

        base = self.scalar_type_map.get(slot.range or "string")
        if base is None:
            raise OmnigraphGeneratorError(f"Slot {owner.name}.{slot.name} has unsupported range {slot.range!r}.")
        if bool(getattr(slot, "multivalued", False)):
            return f"[{base}]"
        return base

    def _relationship_endpoints(self, cls: ClassDefinition) -> list[Endpoint]:
        endpoints = []
        for slot in self._native_edge_slots(cls):
            role = self._annotation(slot, "role")
            if role is None:
                continue
            if bool(getattr(slot, "multivalued", False)):
                raise OmnigraphGeneratorError(f"Relationship {cls.name} role slot {slot.name} is multivalued; edge endpoints must be singular.")
            if not self._is_node_range(slot.range):
                raise OmnigraphGeneratorError(
                    f"Relationship {cls.name} role slot {slot.name} range {slot.range!r} does not resolve to an entity node."
                )
            if self._class_is_abstract(slot.range):
                raise OmnigraphGeneratorError(
                    f"Relationship {cls.name} role slot {slot.name} range {slot.range!r} does not resolve to an entity node "
                    "with concrete native-edge storage; abstract endpoint ranges are unsupported."
                )
            endpoints.append(Endpoint(slot.name, role, slot.range))

        if len(endpoints) != 2:
            raise OmnigraphGeneratorError(
                f"Relationship {cls.name} has {len(endpoints)} endpoint role slots; native-edge mode requires exactly two. "
                "N-ary relationships require a future explicit reified relationship mode."
            )
        return endpoints

    def _native_edge_slots(self, cls: ClassDefinition) -> list[SlotDefinition]:
        # LinkML's loader also synthesises class__attribute slots; as in
        # _own_slots, use their public induced counterparts exactly once. Keep
        # declared property names containing '__' when they have no such alias.
        slots = self.schemaview.class_induced_slots(cls.name)
        names = {slot.name for slot in slots}
        return [
            slot for slot in slots
            if not slot.is_usage_slot and not ("__" in slot.name and slot.alias in names)
        ]

    def _reified_relationship_endpoints(self, cls: ClassDefinition) -> list[Endpoint]:
        endpoints = []
        roles = set()
        for slot in self._own_slots(cls):
            role = self._annotation(slot, "role")
            if role is None:
                continue
            self._validate_property_identifier(role, owner=cls.name, owner_kind="relationship role")
            if role in roles:
                raise OmnigraphGeneratorError(f"Relationship {cls.name} declares duplicate role annotation {role!r}.")
            roles.add(role)
            if bool(getattr(slot, "multivalued", False)):
                raise OmnigraphGeneratorError(
                    f"Relationship {cls.name} role slot {slot.name} is multivalued; "
                    "reified mode currently supports only singular role players."
                )
            if not self._is_node_range(slot.range):
                raise OmnigraphGeneratorError(
                    f"Relationship {cls.name} role slot {slot.name} range {slot.range!r} does not resolve to an entity node."
                )
            if self._class_is_abstract(slot.range):
                raise OmnigraphGeneratorError(
                    f"Relationship {cls.name} role slot {slot.name} range {slot.range!r} does not resolve to an entity node "
                    "with concrete reified incident-edge storage; abstract endpoint ranges are unsupported."
                )
            endpoints.append(Endpoint(slot.name, role, slot.range))

        if len(endpoints) < 2:
            raise OmnigraphGeneratorError(
                f"Relationship {cls.name} has {len(endpoints)} endpoint role slots; "
                "reified mode requires at least two role-player slots."
            )
        return endpoints

    def _resolve_direction(self, cls: ClassDefinition, endpoints: list[Endpoint]) -> tuple[Endpoint, Endpoint]:
        by_role = {endpoint.role: endpoint for endpoint in endpoints}
        from_role = self._annotation(cls, "og_from_role")
        to_role = self._annotation(cls, "og_to_role")
        if from_role or to_role:
            if not from_role or not to_role:
                raise OmnigraphGeneratorError(f"Relationship {cls.name} must set both og_from_role and og_to_role.")
            if from_role == to_role:
                raise OmnigraphGeneratorError(f"Relationship {cls.name} uses the same role for og_from_role and og_to_role.")
            try:
                return by_role[from_role], by_role[to_role]
            except KeyError as exc:
                raise OmnigraphGeneratorError(
                    f"Relationship {cls.name} direction role {exc.args[0]!r} does not match endpoint roles {sorted(by_role)}."
                ) from exc

        roles = set(by_role)
        for conventional_from, conventional_to in self.conventional_roles:
            if roles == {conventional_from, conventional_to}:
                return by_role[conventional_from], by_role[conventional_to]

        raise OmnigraphGeneratorError(
            f"Relationship {cls.name} has ambiguous direction; add og_from_role and og_to_role."
        )

    def _implemented_interfaces(self, cls: ClassDefinition) -> list[str]:
        candidates = []
        if cls.is_a:
            candidates.append(cls.is_a)
        candidates.extend(cls.mixins or [])
        return [name for name in candidates if self._class_kind(name) == "interface"]

    def _relationship_mode(self, cls: ClassDefinition) -> str:
        mode = self._annotation(cls, "og_relationship_mode")
        if mode is None:
            return "native_edge"
        if mode in {"native_edge", "reified"}:
            return mode
        return mode

    def _reified_role_edge_name(self, cls: ClassDefinition, endpoint: Endpoint) -> str:
        edge_name = f"{cls.name}{self._role_suffix(endpoint.role)}"
        self._validate_type_identifier(edge_name, context=f"reified role edge for {cls.name}.{endpoint.role}")
        existing = self.schemaview.all_classes(imports=False)
        if edge_name in existing:
            raise OmnigraphGeneratorError(
                f"Generated reified role edge name {edge_name!r} for relationship {cls.name} role {endpoint.role!r} "
                "collides with an existing LinkML class; the generator does not invent alternate names."
            )
        return edge_name

    @staticmethod
    def _role_suffix(role: str) -> str:
        return role[0].upper() + role[1:]

    @classmethod
    def _validate_type_identifier(cls, name: str, *, context: str) -> None:
        if cls.type_identifier_pattern.fullmatch(name):
            return
        raise OmnigraphGeneratorError(
            f"{context.capitalize()} name {name!r} is not a valid Omnigraph type identifier. "
            "Expected ASCII PascalCase or Pascal_Snake matching ^[A-Z][A-Za-z0-9_]*$; "
            "the generator does not escape or normalise identifiers."
        )

    def _validate_shared_class_annotations(self, cls: ClassDefinition) -> None:
        """Validate canonical values of the no-schema-effect shared annotations.

        ``lifecycle`` and ``read_shape`` are accepted source annotations that
        emit nothing in the generated ``.pg`` schema. Their values are still
        validated against the canonical set so that a typo (e.g.
        ``lifecycle: shred``) fails closed rather than being silently ignored,
        matching how other annotations such as ``index`` are treated.
        """
        lifecycle = self._annotation(cls, "lifecycle")
        if lifecycle is not None and lifecycle not in self.canonical_lifecycle_values:
            raise OmnigraphGeneratorError(
                f"Class {cls.name} has lifecycle {lifecycle!r}; expected one of "
                f"{sorted(self.canonical_lifecycle_values)}."
            )
        read_shape = self._annotation(cls, "read_shape")
        if read_shape is not None and read_shape not in self.canonical_read_shape_values:
            raise OmnigraphGeneratorError(
                f"Class {cls.name} has read_shape {read_shape!r}; expected one of "
                f"{sorted(self.canonical_read_shape_values)}."
            )

    @classmethod
    def _validate_property_identifier(cls, name: str, *, owner: str, owner_kind: str) -> None:
        if not cls.property_identifier_pattern.fullmatch(name):
            raise OmnigraphGeneratorError(
                f"Slot {owner}.{name} is not a valid Omnigraph property identifier. "
                "Expected ASCII lowerCamelCase or lower_snake_case matching ^[a-z][A-Za-z0-9_]*$; "
                "the generator does not escape or normalise identifiers."
            )

        if owner_kind == "relationship" and name in cls.edge_reserved_property_names:
            raise OmnigraphGeneratorError(
                f"Slot {owner}.{name} uses reserved Omnigraph edge property name {name!r}. "
                "Omnigraph 0.11.0 reserves from/to on native edges; rename the emitted body property."
            )

    @classmethod
    def _validate_enum_values(cls, *, enum_name: str, values: Any, owner: str, slot_name: str) -> None:
        invalid = [value for value in values if not cls.enum_value_pattern.fullmatch(value)]
        if not invalid:
            return
        joined = ", ".join(repr(value) for value in invalid)
        raise OmnigraphGeneratorError(
            f"Slot {owner}.{slot_name} uses enum {enum_name} with unsupported Omnigraph enum values: {joined}. "
            "Expected ASCII tokens matching ^[A-Za-z0-9][A-Za-z0-9_-]*$; spaces, quotes, and Unicode are rejected."
        )

    def _own_slots(self, cls: ClassDefinition) -> list[SlotDefinition]:
        names = list(cls.attributes.keys()) if cls.attributes else []
        explicit_slots = [name for name in (cls.slots or []) if "__" not in name]
        names.extend(explicit_slots)
        seen = set()
        slots = []
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            try:
                slots.append(self.schemaview.induced_slot(name, cls.name))
            except ValueError as exc:
                alias = self._compatibility_alias_from_error(exc)
                if alias is not None:
                    raise OmnigraphGeneratorError(self._compatibility_alias_message(alias)) from exc
                raise
        return slots

    def _slot_named(self, cls: ClassDefinition, name: str) -> SlotDefinition | None:
        for slot in self._own_slots(cls):
            if slot.name == name:
                return slot
        return None

    def _validate_relationship_endpoint_cardinality(self, cls: ClassDefinition, slot: SlotDefinition) -> None:
        lower_bound, upper_bound = self._slot_cardinality_bounds(slot)
        if lower_bound == 1 and upper_bound == 1:
            return

        raise OmnigraphGeneratorError(
            f"Relationship {cls.name} endpoint slot {slot.name} must describe exactly one participant "
            f"per relationship instance, but its LinkML cardinality is {lower_bound}..{upper_bound}. "
            "Shared relationship-slot cardinality does not map to Omnigraph @card(...), so native edge mode "
            "accepts only exact-one endpoint participation."
        )

    def _keys_for_node(self, cls: ClassDefinition, props: list[Property]) -> tuple[list[str] | None, list[list[str]]]:
        identifier_slots = [prop.name for prop in props if prop.identifier]
        if len(identifier_slots) > 1:
            raise OmnigraphGeneratorError(
                f"Class {cls.name} declares multiple identifier slots; composite identifier-slot keys are unsupported. "
                "Use one identifier slot or one unambiguous required unique_keys declaration instead."
            )

        unique_keys = getattr(cls, "unique_keys", None) or {}
        if not unique_keys:
            return (identifier_slots or None), []

        prop_names = {prop.name for prop in props}
        prop_by_name = {prop.name: prop for prop in props}
        directives = []
        for unique_key_name, unique_key in unique_keys.items():
            slots = list(getattr(unique_key, "unique_key_slots", None) or [])
            if not slots:
                raise OmnigraphGeneratorError(f"Class {cls.name} unique key {unique_key_name} does not declare unique_key_slots.")
            missing = [slot for slot in slots if slot not in prop_names]
            if missing:
                raise OmnigraphGeneratorError(
                    f"Class {cls.name} unique key {unique_key_name} references slots that are not emitted node properties: {', '.join(missing)}."
                )
            directives.append(slots)

        if identifier_slots:
            return identifier_slots, directives

        if len(directives) != 1:
            return None, directives

        composite_key = directives[0]
        optional = [slot for slot in composite_key if not prop_by_name[slot].required]
        if optional:
            return None, directives

        return composite_key, []

    @staticmethod
    def _has_range_constraint(prop: Property) -> bool:
        return prop.minimum_value is not None or prop.maximum_value is not None

    @classmethod
    def _range_declaration(cls, prop: Property) -> str:
        lower = "" if prop.minimum_value is None else cls._format_constraint_value(prop.minimum_value)
        upper = "" if prop.maximum_value is None else cls._format_constraint_value(prop.maximum_value)
        return f"  @range({prop.name}, {lower}..{upper})"

    @staticmethod
    def _check_declaration(prop: Property) -> str:
        return f"  @check({prop.name}, {json.dumps(prop.pattern)})"

    @staticmethod
    def _format_constraint_value(value: Any) -> str:
        return str(value)

    @staticmethod
    def _slot_has_node_only_constraint(slot: SlotDefinition) -> bool:
        return (
            getattr(slot, "minimum_value", None) is not None
            or getattr(slot, "maximum_value", None) is not None
            or getattr(slot, "pattern", None) is not None
        )

    @staticmethod
    def _slot_declares_explicit_cardinality(slot: SlotDefinition) -> bool:
        return (
            getattr(slot, "minimum_cardinality", None) is not None
            or getattr(slot, "maximum_cardinality", None) is not None
            or getattr(slot, "exact_cardinality", None) is not None
        )

    @classmethod
    def _slot_cardinality_bounds(cls, slot: SlotDefinition) -> tuple[int, int]:
        exact = getattr(slot, "exact_cardinality", None)
        minimum = getattr(slot, "minimum_cardinality", None)
        maximum = getattr(slot, "maximum_cardinality", None)

        if exact is not None:
            return int(exact), int(exact)

        lower_bound = int(minimum) if minimum is not None else (1 if bool(slot.required) else 0)
        if maximum is not None:
            upper_bound = int(maximum)
        elif bool(getattr(slot, "multivalued", False)):
            upper_bound = lower_bound if lower_bound > 1 else 2
        else:
            upper_bound = 1

        return lower_bound, upper_bound

    @classmethod
    def _compatibility_alias_from_error(cls, error: ValueError) -> str | None:
        message = str(error)
        for alias in cls.compatibility_alias_suggestions:
            if f"unrecognized range ({alias})" in message:
                return alias
        return None

    @classmethod
    def _compatibility_alias_message(cls, alias: str) -> str:
        return (
            f"Range {alias!r} is a compatibility-only datatype alias and is not part of the canonical "
            f"Omnigraph LinkML contract. Use {cls.compatibility_alias_suggestions[alias]} instead."
        )

    unknown_attribute_pattern = re.compile(
        r"(SlotDefinition|ClassDefinition)\.__init__\(\) got an unexpected keyword argument '([^']+)'"
    )
    multiple_identifier_pattern = re.compile(r'Class "([^"]+)" - multiple keys/identifiers not allowed \(([^)]+)\)')

    @classmethod
    def _multiple_identifier_from_error(cls, error: ValueError) -> tuple[str, str] | None:
        match = cls.multiple_identifier_pattern.search(str(error))
        if match is None:
            return None
        return match.group(1), match.group(2)

    @staticmethod
    def _multiple_identifier_message(detail: tuple[str, str]) -> str:
        class_name, slots = detail
        return (
            f"Class {class_name} declares multiple identifier slots ({slots}); "
            "the Omnigraph generator supports exactly one identifier slot for node identity."
        )

    @classmethod
    def _unknown_attribute_from_error(cls, error: TypeError) -> tuple[str, str] | None:
        match = cls.unknown_attribute_pattern.search(str(error))
        if match is None:
            return None
        return match.group(1), match.group(2)

    @classmethod
    def _unknown_attribute_message(cls, detail: tuple[str, str]) -> str:
        owner_type, attribute = detail
        owner = "slot" if owner_type == "SlotDefinition" else "class"
        suffix = ""
        if attribute == "unique":
            suffix = (
                "; LinkML has no slot-level 'unique' predicate in this version. "
                "Use the annotations form 'annotations: { unique: true }' instead."
            )
        return (
            f"LinkML rejected an unsupported {owner} attribute {attribute!r}. "
            "The generator does not recognise it as part of the Omnigraph LinkML contract"
            f"{suffix}"
        )

    def _is_node_range(self, range_name: str | None) -> bool:
        return self._class_kind(range_name) == "entity"

    def _is_class_range(self, range_name: str | None) -> bool:
        return range_name in self.schemaview.all_classes(imports=False)

    def _class_kind(self, class_name: str | None) -> str | None:
        if not class_name:
            return None
        cls = self.schemaview.get_class(class_name)
        return self._annotation(cls, "kind") if cls else None

    def _class_is_abstract(self, class_name: str | None) -> bool:
        if not class_name:
            return False
        cls = self.schemaview.get_class(class_name)
        if cls is None:
            return False
        return bool(getattr(cls, "abstract", False))

    @staticmethod
    def _annotation(obj: Any, name: str) -> str | None:
        annotations = getattr(obj, "annotations", None)
        if not annotations:
            return None
        value = None
        if isinstance(annotations, dict):
            value = annotations.get(name)
        else:
            value = getattr(annotations, name, None)
        if value is None:
            return None
        return str(getattr(value, "value", value))


def generate_omnigraph(schema: str | Path) -> str:
    return OmnigraphGenerator(schema).serialize()
