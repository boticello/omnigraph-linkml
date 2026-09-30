"""Opt-in role-set preflight for complete projected record batches."""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


class OmnigraphDataValidationError(ValueError):
    """A batch cannot establish complete, correctly typed reified roles."""


@dataclass(frozen=True)
class RoleRule:
    relationship: str
    role: str
    edge: str
    participant: str


def _scalar_key(value: Any, context: str) -> tuple[type, Any]:
    if type(value) not in (str, int, float, bool) or (
        isinstance(value, float) and not math.isfinite(value)
    ):
        raise OmnigraphDataValidationError(f"{context}: requires a non-null JSON scalar reference/key")
    # Bool and integer values must not collapse through Python equality.
    return type(value), value


def validate_role_records(
    records: Iterable[Mapping[str, Any]],
    keys: Mapping[str, str],
    rules: list[RoleRule],
    node_types: set[str],
    edge_types: set[str],
) -> None:
    """No I/O, mutation or assumptions about an existing store."""
    nodes: dict[str, set[tuple[type, Any]]] = {name: set() for name in keys}
    role_edges = {rule.edge: rule for rule in rules}
    pending: list[tuple[RoleRule, tuple[type, Any], tuple[type, Any]]] = []
    for position, row in enumerate(records):
        context = f"Record {position}"
        if not isinstance(row, Mapping) or ("type" in row) == ("edge" in row):
            raise OmnigraphDataValidationError(f"{context}: requires exactly one type or edge discriminator")
        if "type" in row:
            name = row["type"]
            if not isinstance(name, str) or name not in node_types:
                raise OmnigraphDataValidationError(f"{context}: unknown node type {name!r}")
            if name not in keys:
                continue
            data = row.get("data")
            if not isinstance(data, Mapping):
                raise OmnigraphDataValidationError(f"{context} {name}: requires data containing key {keys[name]}")
            identity = _scalar_key(data.get(keys[name]), f"{context} {name}.{keys[name]}")
            if identity in nodes[name]:
                raise OmnigraphDataValidationError(f"{context} {name}: duplicate key {identity[1]!r}")
            nodes[name].add(identity)
        else:
            name = row["edge"]
            if not isinstance(name, str) or name not in edge_types:
                raise OmnigraphDataValidationError(f"{context}: unknown edge type {name!r}")
            rule = role_edges.get(name)
            if rule is not None:
                context += f" {rule.relationship}.{rule.role}"
                pending.append((rule, _scalar_key(row.get("from"), context),
                                _scalar_key(row.get("to"), context)))

    counts: Counter[tuple[str, tuple[type, Any]]] = Counter()
    for rule, source, target in pending:
        context = f"{rule.relationship} {source[1]!r} role {rule.role}"
        if source not in nodes[rule.relationship]:
            raise OmnigraphDataValidationError(f"{context}: orphan role edge; relationship absent from batch")
        if target not in nodes[rule.participant]:
            raise OmnigraphDataValidationError(
                f"{context}: participant {target[1]!r} is absent or is not of type {rule.participant}"
            )
        counts[rule.edge, source] += 1
    for rule in rules:
        for identity in nodes[rule.relationship]:
            count = counts[rule.edge, identity]
            if count != 1:
                raise OmnigraphDataValidationError(
                    f"{rule.relationship} {identity[1]!r} role {rule.role}: "
                    f"requires exactly one participant of type {rule.participant}; found {count}"
                )
