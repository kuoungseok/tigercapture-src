"""Authored graph document for the UI material and PBR texture editors.

Unlike ``umg_material_graph``, which projects a fixed picture out of a material
record, this is the thing the user edits: nodes they placed, links they drew,
parameter values they typed.  Every mutation returns a new document so the
caller can push the previous one onto an undo stack, matching how the Painter UI
document is handled elsewhere in the app.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping

from app.material_graph.registry import (
    OUTPUT_TYPES,
    default_param_values,
    node_definition,
    normalize_pin_list,
    pins_are_compatible,
    resolve_pin,
)


SCHEMA_ID = "tigerstudio.material_graph.document.v1"

_SURFACES = ("ui", "pbr")


class MaterialGraphError(ValueError):
    """A rejected edit, with a message meant for the status bar."""


def _clean_number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    if number != number or number in (float("inf"), float("-inf")):
        return float(default)
    return number


def _clean_position(value: Any) -> list[float]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return [_clean_number(value[0]), _clean_number(value[1])]
    return [0.0, 0.0]


def create_graph(surface: str = "ui") -> dict[str, Any]:
    """A new graph holding only the output node its surface requires."""
    key = str(surface) if str(surface) in _SURFACES else "ui"
    output_type = OUTPUT_TYPES[key]
    return normalize_graph(
        {
            "schema": SCHEMA_ID,
            "surface": key,
            "nodes": [
                {
                    "id": "output",
                    "type": output_type,
                    "position": [420.0, 120.0],
                }
            ],
            "links": [],
            "selection": {"node_ids": []},
        }
    )


def normalize_graph(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Canonical form: known node types, unique ids, only legal links."""
    source = value if isinstance(value, Mapping) else {}
    surface = str(source.get("surface") or "ui")
    if surface not in _SURFACES:
        surface = "ui"
    nodes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in source.get("nodes") or []:
        if not isinstance(row, Mapping):
            continue
        node_type = str(row.get("type") or "")
        definition = node_definition(node_type)
        if definition is None:
            continue
        node_id = str(row.get("id") or "")
        if not node_id or node_id in seen_ids:
            node_id = _unique_id(node_type, seen_ids)
        seen_ids.add(node_id)
        params = dict(default_param_values(node_type))
        supplied = row.get("params")
        if isinstance(supplied, Mapping):
            for key, item in supplied.items():
                if str(key) in params:
                    params[str(key)] = copy.deepcopy(item)
        if "Inputs" in params:
            # A Custom node declares its own pins, so they have to be cleaned
            # before any link is checked against them.
            params["Inputs"] = normalize_pin_list(params["Inputs"])
        nodes.append(
            {
                "id": node_id,
                "type": node_type,
                "title": str(row.get("title") or definition["title"]),
                "position": _clean_position(row.get("position")),
                "params": params,
                "comment": str(row.get("comment") or ""),
            }
        )
    by_id = {row["id"]: row for row in nodes}
    links: list[dict[str, Any]] = []
    taken_inputs: set[tuple[str, str]] = set()
    for row in source.get("links") or []:
        if not isinstance(row, Mapping):
            continue
        link = _normalized_link(row, by_id)
        if link is None:
            continue
        target = (link["to_node"], link["to_pin"])
        if target in taken_inputs:
            # An input pin takes one wire; the later one loses, the same way a
            # material editor replaces the existing connection.
            continue
        taken_inputs.add(target)
        links.append(link)
    links = _without_cycles(links, by_id)
    selection = source.get("selection")
    selected = []
    if isinstance(selection, Mapping):
        selected = [
            str(item)
            for item in selection.get("node_ids") or []
            if str(item) in by_id
        ]
    return {
        "schema": SCHEMA_ID,
        "surface": surface,
        "nodes": nodes,
        "links": links,
        "selection": {"node_ids": selected},
    }


def _normalized_link(
    row: Mapping[str, Any],
    by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any] | None:
    from_node = str(row.get("from_node") or "")
    to_node = str(row.get("to_node") or "")
    if from_node not in by_id or to_node not in by_id or from_node == to_node:
        return None
    from_pin = str(row.get("from_pin") or "")
    to_pin = str(row.get("to_pin") or "")
    source = resolve_pin(
        by_id[from_node]["type"],
        from_pin,
        is_input=False,
        node=by_id[from_node],
    )
    target = resolve_pin(
        by_id[to_node]["type"],
        to_pin,
        is_input=True,
        node=by_id[to_node],
    )
    if source is None or target is None:
        return None
    if not pins_are_compatible(source["type"], target["type"]):
        return None
    return {
        "from_node": from_node,
        "from_pin": from_pin,
        "to_node": to_node,
        "to_pin": to_pin,
    }


def _without_cycles(
    links: list[dict[str, Any]],
    by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for link in links:
        if _creates_cycle(kept, link["from_node"], link["to_node"]):
            continue
        kept.append(link)
    return kept


def _creates_cycle(
    links: list[dict[str, Any]],
    from_node: str,
    to_node: str,
) -> bool:
    """True when adding from->to would let ``to_node`` reach ``from_node``."""
    if from_node == to_node:
        return True
    outgoing: dict[str, list[str]] = {}
    for link in links:
        outgoing.setdefault(link["from_node"], []).append(link["to_node"])
    stack = [to_node]
    seen = {to_node}
    while stack:
        current = stack.pop()
        if current == from_node:
            return True
        for following in outgoing.get(current, []):
            if following in seen:
                continue
            seen.add(following)
            stack.append(following)
    return False


def _unique_id(node_type: str, taken: set[str]) -> str:
    stem = "".join(
        character if character.isalnum() else "_"
        for character in str(node_type)
    ).strip("_").lower() or "node"
    index = 1
    while f"{stem}_{index}" in taken:
        index += 1
    return f"{stem}_{index}"


# ------------------------------------------------------------- mutations


def add_node(
    graph: Mapping[str, Any],
    node_type: str,
    *,
    position: tuple[float, float] | list[float] = (0.0, 0.0),
    node_id: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    definition = node_definition(node_type)
    if definition is None:
        raise MaterialGraphError(f"Unknown node type: {node_type}")
    current = normalize_graph(graph)
    if current["surface"] not in definition["surfaces"]:
        raise MaterialGraphError(
            f"{definition['title']} is not available on the "
            f"{current['surface']} graph."
        )
    taken = {row["id"] for row in current["nodes"]}
    identifier = str(node_id or "")
    if not identifier or identifier in taken:
        identifier = _unique_id(node_type, taken)
    row = {
        "id": identifier,
        "type": str(node_type),
        "title": definition["title"],
        "position": _clean_position(position),
        "params": default_param_values(node_type),
        "comment": "",
    }
    revised = copy.deepcopy(current)
    revised["nodes"].append(row)
    return normalize_graph(revised), dict(row)


def remove_nodes(
    graph: Mapping[str, Any],
    node_ids: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    current = normalize_graph(graph)
    doomed = {str(item) for item in node_ids}
    # The output node is the graph's reason to exist; deleting it would leave
    # nothing to evaluate, so it is refused rather than silently re-added.
    output_type = OUTPUT_TYPES[current["surface"]]
    protected = {
        row["id"] for row in current["nodes"] if row["type"] == output_type
    }
    doomed -= protected
    revised = copy.deepcopy(current)
    revised["nodes"] = [
        row for row in revised["nodes"] if row["id"] not in doomed
    ]
    revised["links"] = [
        row
        for row in revised["links"]
        if row["from_node"] not in doomed and row["to_node"] not in doomed
    ]
    revised["selection"] = {
        "node_ids": [
            item
            for item in revised["selection"]["node_ids"]
            if item not in doomed
        ]
    }
    return normalize_graph(revised)


def move_node(
    graph: Mapping[str, Any],
    node_id: str,
    position: tuple[float, float] | list[float],
) -> dict[str, Any]:
    current = normalize_graph(graph)
    revised = copy.deepcopy(current)
    for row in revised["nodes"]:
        if row["id"] == str(node_id):
            row["position"] = _clean_position(position)
            break
    else:
        raise MaterialGraphError(f"No such node: {node_id}")
    return normalize_graph(revised)


def set_node_param(
    graph: Mapping[str, Any],
    node_id: str,
    name: str,
    value: Any,
) -> dict[str, Any]:
    current = normalize_graph(graph)
    revised = copy.deepcopy(current)
    for row in revised["nodes"]:
        if row["id"] != str(node_id):
            continue
        if str(name) not in row["params"]:
            raise MaterialGraphError(
                f"{row['type']} has no parameter named {name}."
            )
        row["params"][str(name)] = copy.deepcopy(value)
        break
    else:
        raise MaterialGraphError(f"No such node: {node_id}")
    return normalize_graph(revised)


def connect(
    graph: Mapping[str, Any],
    from_node: str,
    from_pin: str,
    to_node: str,
    to_pin: str,
) -> dict[str, Any]:
    """Draw a wire, replacing whatever already drove the target pin."""
    current = normalize_graph(graph)
    by_id = {row["id"]: row for row in current["nodes"]}
    link = _normalized_link(
        {
            "from_node": from_node,
            "from_pin": from_pin,
            "to_node": to_node,
            "to_pin": to_pin,
        },
        by_id,
    )
    if link is None:
        raise MaterialGraphError(
            "Those pins cannot be connected: unknown pin or incompatible type."
        )
    kept = [
        row
        for row in current["links"]
        if not (
            row["to_node"] == link["to_node"]
            and row["to_pin"] == link["to_pin"]
        )
    ]
    if _creates_cycle(kept, link["from_node"], link["to_node"]):
        raise MaterialGraphError("That wire would make the graph loop.")
    revised = copy.deepcopy(current)
    revised["links"] = kept + [link]
    return normalize_graph(revised)


def disconnect(
    graph: Mapping[str, Any],
    to_node: str,
    to_pin: str,
) -> dict[str, Any]:
    current = normalize_graph(graph)
    revised = copy.deepcopy(current)
    revised["links"] = [
        row
        for row in revised["links"]
        if not (row["to_node"] == str(to_node) and row["to_pin"] == str(to_pin))
    ]
    return normalize_graph(revised)


def set_selection(
    graph: Mapping[str, Any],
    node_ids: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    current = normalize_graph(graph)
    revised = copy.deepcopy(current)
    revised["selection"] = {"node_ids": [str(item) for item in node_ids]}
    return normalize_graph(revised)


# ------------------------------------------------------------- inspection


def node_by_id(graph: Mapping[str, Any], node_id: str) -> dict[str, Any] | None:
    for row in normalize_graph(graph)["nodes"]:
        if row["id"] == str(node_id):
            return dict(row)
    return None


def input_link(
    graph: Mapping[str, Any],
    node_id: str,
    pin_name: str,
) -> dict[str, Any] | None:
    for row in normalize_graph(graph)["links"]:
        if row["to_node"] == str(node_id) and row["to_pin"] == str(pin_name):
            return dict(row)
    return None


def evaluation_order(graph: Mapping[str, Any]) -> list[str]:
    """Node ids in dependency order, sources first.

    Nodes the output cannot reach are still included, after the connected ones,
    so a half-built graph still lists everything the editor is holding.
    """
    current = normalize_graph(graph)
    incoming: dict[str, set[str]] = {row["id"]: set() for row in current["nodes"]}
    outgoing: dict[str, set[str]] = {row["id"]: set() for row in current["nodes"]}
    for link in current["links"]:
        incoming[link["to_node"]].add(link["from_node"])
        outgoing[link["from_node"]].add(link["to_node"])
    ready = [row["id"] for row in current["nodes"] if not incoming[row["id"]]]
    ordered: list[str] = []
    pending = {key: set(value) for key, value in incoming.items()}
    while ready:
        ready.sort()
        current_id = ready.pop(0)
        ordered.append(current_id)
        for following in sorted(outgoing[current_id]):
            pending[following].discard(current_id)
            if not pending[following]:
                ready.append(following)
    # normalize_graph already dropped cycles, so anything left is unreachable
    # rather than circular; keep it deterministic anyway.
    ordered.extend(sorted(set(pending) - set(ordered)))
    return ordered


def graph_report(graph: Mapping[str, Any]) -> dict[str, Any]:
    """What the editor's status bar and the tests read."""
    current = normalize_graph(graph)
    output_type = OUTPUT_TYPES[current["surface"]]
    outputs = [row for row in current["nodes"] if row["type"] == output_type]
    driven: list[str] = []
    missing: list[str] = []
    if outputs:
        from app.material_graph.registry import node_pins

        for pin in node_pins(outputs[0])[0]:
            name = str(pin["name"])
            if input_link(current, outputs[0]["id"], name) is None:
                missing.append(name)
            else:
                driven.append(name)
    reachable = set()
    if outputs:
        stack = [outputs[0]["id"]]
        while stack:
            node_id = stack.pop()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            for link in current["links"]:
                if link["to_node"] == node_id:
                    stack.append(link["from_node"])
    return {
        "schema": f"{SCHEMA_ID}.report",
        "surface": current["surface"],
        "node_count": len(current["nodes"]),
        "link_count": len(current["links"]),
        "output_id": outputs[0]["id"] if outputs else "",
        "driven_outputs": driven,
        "missing_outputs": missing,
        "unreachable_node_ids": sorted(
            row["id"] for row in current["nodes"] if row["id"] not in reachable
        ),
        "evaluation_order": evaluation_order(current),
    }
