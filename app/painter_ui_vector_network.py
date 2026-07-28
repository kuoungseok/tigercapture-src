"""Typed, stable-ID vector paths for Painter UI Design."""
from __future__ import annotations

import copy
from typing import Any, Mapping


VECTOR_NODE_KINDS = {"corner", "smooth", "symmetric"}
VECTOR_SEGMENT_KINDS = {"line", "cubic"}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _point(value: Any) -> dict[str, float] | None:
    if not isinstance(value, Mapping):
        return None
    return {
        "x": _number(value.get("x")),
        "y": _number(value.get("y")),
    }


def _unique_id(prefix: str, used: set[str], preferred: Any = "") -> str:
    candidate = str(preferred or "").strip()
    if candidate and candidate not in used:
        used.add(candidate)
        return candidate
    serial = 1
    while f"{prefix}-{serial}" in used:
        serial += 1
    candidate = f"{prefix}-{serial}"
    used.add(candidate)
    return candidate


def create_vector_network(
    *,
    closed: bool = False,
) -> dict[str, Any]:
    """Create a useful default path rather than an invisible empty object."""
    nodes = [
        {
            "id": "node-1",
            "x": 0.0,
            "y": 0.5,
            "in_handle": None,
            "out_handle": None,
            "kind": "corner",
        },
        {
            "id": "node-2",
            "x": 1.0,
            "y": 0.5,
            "in_handle": None,
            "out_handle": None,
            "kind": "corner",
        },
    ]
    segments = [
        {
            "id": "segment-1",
            "start_node_id": "node-1",
            "end_node_id": "node-2",
            "kind": "line",
        }
    ]
    if closed:
        segments.append(
            {
                "id": "segment-2",
                "start_node_id": "node-2",
                "end_node_id": "node-1",
                "kind": "line",
            }
        )
    return {
        "nodes": nodes,
        "segments": segments,
        "closed": bool(closed),
    }


def normalize_vector_network(value: Any) -> dict[str, Any]:
    row = value if isinstance(value, Mapping) else {}
    raw_nodes = [
        item for item in row.get("nodes", []) if isinstance(item, Mapping)
    ]
    used_nodes: set[str] = set()
    nodes: list[dict[str, Any]] = []
    for item in raw_nodes:
        kind = str(item.get("kind") or "corner").strip().casefold()
        nodes.append(
            {
                "id": _unique_id("node", used_nodes, item.get("id")),
                "x": _number(item.get("x")),
                "y": _number(item.get("y")),
                "in_handle": _point(item.get("in_handle")),
                "out_handle": _point(item.get("out_handle")),
                "kind": kind if kind in VECTOR_NODE_KINDS else "corner",
            }
        )
    node_ids = {item["id"] for item in nodes}
    used_segments: set[str] = set()
    segments: list[dict[str, str]] = []
    for item in row.get("segments", []):
        if not isinstance(item, Mapping):
            continue
        start = str(item.get("start_node_id") or "")
        end = str(item.get("end_node_id") or "")
        if start not in node_ids or end not in node_ids or start == end:
            continue
        kind = str(item.get("kind") or "line").strip().casefold()
        segments.append(
            {
                "id": _unique_id("segment", used_segments, item.get("id")),
                "start_node_id": start,
                "end_node_id": end,
                "kind": kind if kind in VECTOR_SEGMENT_KINDS else "line",
            }
        )
    return {
        "nodes": nodes,
        "segments": segments,
        "closed": bool(row.get("closed", False)),
    }


def vector_network_to_svg_path(value: Any, rect: Any = None) -> str:
    network = normalize_vector_network(value)
    nodes = {item["id"]: item for item in network["nodes"]}
    if not nodes or not network["segments"]:
        return ""
    unused = list(network["segments"])
    chunks: list[str] = []
    def coordinate(node: Mapping[str, float]) -> tuple[float, float]:
        if rect is None:
            return float(node["x"]), float(node["y"])
        return (
            float(rect.left()) + float(node["x"]) * float(rect.width()),
            float(rect.top()) + float(node["y"]) * float(rect.height()),
        )

    while unused:
        segment = unused.pop(0)
        start = nodes[segment["start_node_id"]]
        start_x, start_y = coordinate(start)
        chunks.append(f"M {start_x:.8g} {start_y:.8g}")
        current_id = segment["start_node_id"]
        pending = [segment]
        while pending:
            active = pending.pop(0)
            if active["start_node_id"] != current_id:
                break
            end = nodes[active["end_node_id"]]
            start_node = nodes[active["start_node_id"]]
            if active["kind"] == "cubic":
                out_handle = start_node.get("out_handle") or {
                    "x": start_node["x"],
                    "y": start_node["y"],
                }
                in_handle = end.get("in_handle") or {
                    "x": end["x"],
                    "y": end["y"],
                }
                out_x, out_y = coordinate(out_handle)
                in_x, in_y = coordinate(in_handle)
                end_x, end_y = coordinate(end)
                chunks.append(
                    " C "
                    f"{out_x:.8g} {out_y:.8g} "
                    f"{in_x:.8g} {in_y:.8g} "
                    f"{end_x:.8g} {end_y:.8g}"
                )
            else:
                end_x, end_y = coordinate(end)
                chunks.append(f" L {end_x:.8g} {end_y:.8g}")
            current_id = active["end_node_id"]
            next_index = next(
                (
                    index
                    for index, candidate in enumerate(unused)
                    if candidate["start_node_id"] == current_id
                ),
                -1,
            )
            if next_index >= 0:
                pending.append(unused.pop(next_index))
        if network["closed"] and current_id == segment["start_node_id"]:
            chunks.append(" Z")
    return "".join(chunks)


def vector_network_to_qpath(value: Any, rect) -> Any:
    """Build a QPainterPath in the supplied object-local screen rectangle."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPainterPath

    network = normalize_vector_network(value)
    nodes = {item["id"]: item for item in network["nodes"]}
    path = QPainterPath()
    if not nodes or not network["segments"]:
        return path

    def point(value_point: Mapping[str, float]) -> QPointF:
        return QPointF(
            float(rect.left()) + float(value_point["x"]) * float(rect.width()),
            float(rect.top()) + float(value_point["y"]) * float(rect.height()),
        )

    unused = list(network["segments"])
    while unused:
        segment = unused.pop(0)
        start_id = segment["start_node_id"]
        start = nodes[start_id]
        path.moveTo(point(start))
        current_id = start_id
        while True:
            active = segment
            if active["start_node_id"] != current_id:
                break
            start_node = nodes[active["start_node_id"]]
            end = nodes[active["end_node_id"]]
            if active["kind"] == "cubic":
                path.cubicTo(
                    point(start_node.get("out_handle") or start_node),
                    point(end.get("in_handle") or end),
                    point(end),
                )
            else:
                path.lineTo(point(end))
            current_id = active["end_node_id"]
            next_index = next(
                (
                    index
                    for index, candidate in enumerate(unused)
                    if candidate["start_node_id"] == current_id
                ),
                -1,
            )
            if next_index < 0:
                break
            segment = unused.pop(next_index)
        if network["closed"] and current_id == start_id:
            path.closeSubpath()
    return path


def normalize_vector_content(content: Any) -> dict[str, Any]:
    result = copy.deepcopy(dict(content)) if isinstance(content, Mapping) else {}
    if not isinstance(result.get("vector_network"), Mapping):
        return result
    network = normalize_vector_network(result["vector_network"])
    result["vector_network"] = network
    path = vector_network_to_svg_path(network)
    if path:
        geometry = [{"path": path, "winding_rule": "nonzero"}]
        result["vector_fill_geometry"] = geometry
        result["vector_paths"] = [path]
        result["vector_coordinate_space"] = "normalized"
    else:
        result["vector_fill_geometry"] = []
        result["vector_paths"] = []
    return result


def _network_copy(value: Any) -> dict[str, Any]:
    return copy.deepcopy(normalize_vector_network(value))


def update_vector_node(
    value: Any,
    node_id: str,
    changes: Mapping[str, Any],
) -> dict[str, Any]:
    network = _network_copy(value)
    node = next(
        (item for item in network["nodes"] if item["id"] == str(node_id)),
        None,
    )
    if node is None:
        raise ValueError(f"Unknown vector node: {node_id}")
    for key in ("x", "y"):
        if key in changes:
            node[key] = _number(changes[key], node[key])
    for key in ("in_handle", "out_handle"):
        if key in changes:
            node[key] = _point(changes[key])
    if "kind" in changes:
        kind = str(changes["kind"] or "").strip().casefold()
        if kind not in VECTOR_NODE_KINDS:
            raise ValueError(f"Unsupported vector node kind: {kind}")
        node["kind"] = kind
    return normalize_vector_network(network)


def add_vector_node(
    value: Any,
    *,
    x: float,
    y: float,
    after_node_id: str = "",
) -> tuple[dict[str, Any], str]:
    network = _network_copy(value)
    used = {item["id"] for item in network["nodes"]}
    node_id = _unique_id("node", used)
    network["nodes"].append(
        {
            "id": node_id,
            "x": float(x),
            "y": float(y),
            "in_handle": None,
            "out_handle": None,
            "kind": "corner",
        }
    )
    if after_node_id:
        used_segments = {item["id"] for item in network["segments"]}
        network["segments"].append(
            {
                "id": _unique_id("segment", used_segments),
                "start_node_id": str(after_node_id),
                "end_node_id": node_id,
                "kind": "line",
            }
        )
    return normalize_vector_network(network), node_id


def remove_vector_node(value: Any, node_id: str) -> dict[str, Any]:
    network = _network_copy(value)
    identifier = str(node_id)
    if identifier not in {item["id"] for item in network["nodes"]}:
        raise ValueError(f"Unknown vector node: {node_id}")
    network["nodes"] = [
        item for item in network["nodes"] if item["id"] != identifier
    ]
    network["segments"] = [
        item
        for item in network["segments"]
        if identifier
        not in {item["start_node_id"], item["end_node_id"]}
    ]
    if len(network["nodes"]) < 3:
        network["closed"] = False
    return normalize_vector_network(network)


def set_vector_segment_kind(
    value: Any,
    segment_id: str,
    kind: str,
) -> dict[str, Any]:
    network = _network_copy(value)
    value_kind = str(kind or "").strip().casefold()
    if value_kind not in VECTOR_SEGMENT_KINDS:
        raise ValueError(f"Unsupported vector segment kind: {kind}")
    segment = next(
        (
            item
            for item in network["segments"]
            if item["id"] == str(segment_id)
        ),
        None,
    )
    if segment is None:
        raise ValueError(f"Unknown vector segment: {segment_id}")
    segment["kind"] = value_kind
    if value_kind == "cubic":
        nodes = {item["id"]: item for item in network["nodes"]}
        start = nodes[segment["start_node_id"]]
        end = nodes[segment["end_node_id"]]
        dx = (end["x"] - start["x"]) / 3.0
        dy = (end["y"] - start["y"]) / 3.0
        if start["out_handle"] is None:
            start["out_handle"] = {"x": start["x"] + dx, "y": start["y"] + dy}
        if end["in_handle"] is None:
            end["in_handle"] = {"x": end["x"] - dx, "y": end["y"] - dy}
    return normalize_vector_network(network)


def split_vector_segment(
    value: Any,
    segment_id: str,
    *,
    position: float = 0.5,
) -> tuple[dict[str, Any], str]:
    network = _network_copy(value)
    segment_index = next(
        (
            index
            for index, item in enumerate(network["segments"])
            if item["id"] == str(segment_id)
        ),
        -1,
    )
    if segment_index < 0:
        raise ValueError(f"Unknown vector segment: {segment_id}")
    segment = network["segments"][segment_index]
    nodes = {item["id"]: item for item in network["nodes"]}
    start = nodes[segment["start_node_id"]]
    end = nodes[segment["end_node_id"]]
    t = max(0.01, min(0.99, float(position)))

    def lerp(first: Mapping[str, float], second: Mapping[str, float]) -> dict[str, float]:
        return {
            "x": first["x"] + (second["x"] - first["x"]) * t,
            "y": first["y"] + (second["y"] - first["y"]) * t,
        }

    start_point = {"x": start["x"], "y": start["y"]}
    end_point = {"x": end["x"], "y": end["y"]}
    in_handle = None
    out_handle = None
    if segment["kind"] == "cubic":
        control_a = start.get("out_handle") or start_point
        control_b = end.get("in_handle") or end_point
        ab = lerp(start_point, control_a)
        bc = lerp(control_a, control_b)
        cd = lerp(control_b, end_point)
        abc = lerp(ab, bc)
        bcd = lerp(bc, cd)
        point = lerp(abc, bcd)
        start["out_handle"] = ab
        end["in_handle"] = cd
        in_handle = abc
        out_handle = bcd
    else:
        point = lerp(start_point, end_point)
    used_nodes = {item["id"] for item in network["nodes"]}
    node_id = _unique_id("node", used_nodes)
    network["nodes"].append(
        {
            "id": node_id,
            "x": point["x"],
            "y": point["y"],
            "in_handle": in_handle,
            "out_handle": out_handle,
            "kind": "smooth" if segment["kind"] == "cubic" else "corner",
        }
    )
    used_segments = {item["id"] for item in network["segments"]}
    first_id = segment["id"]
    second_id = _unique_id("segment", used_segments)
    network["segments"][segment_index : segment_index + 1] = [
        {
            "id": first_id,
            "start_node_id": segment["start_node_id"],
            "end_node_id": node_id,
            "kind": segment["kind"],
        },
        {
            "id": second_id,
            "start_node_id": node_id,
            "end_node_id": segment["end_node_id"],
            "kind": segment["kind"],
        },
    ]
    return normalize_vector_network(network), node_id


def set_vector_path_closed(value: Any, closed: bool) -> dict[str, Any]:
    network = _network_copy(value)
    if len(network["nodes"]) < 3:
        if closed:
            raise ValueError("A closed vector path requires at least three nodes")
        network["closed"] = False
        return network
    network["closed"] = bool(closed)
    first_id = network["nodes"][0]["id"]
    last_id = network["nodes"][-1]["id"]
    closing = next(
        (
            item
            for item in network["segments"]
            if item["start_node_id"] == last_id
            and item["end_node_id"] == first_id
        ),
        None,
    )
    if closed and closing is None:
        used_segments = {item["id"] for item in network["segments"]}
        network["segments"].append(
            {
                "id": _unique_id("segment", used_segments),
                "start_node_id": last_id,
                "end_node_id": first_id,
                "kind": "line",
            }
        )
    if not closed:
        network["segments"] = [
            item
            for item in network["segments"]
            if not (
                item["start_node_id"] == last_id
                and item["end_node_id"] == first_id
            )
        ]
    return normalize_vector_network(network)


def join_vector_nodes(
    value: Any,
    start_node_id: str,
    end_node_id: str,
    *,
    kind: str = "line",
) -> dict[str, Any]:
    network = _network_copy(value)
    ids = {item["id"] for item in network["nodes"]}
    start = str(start_node_id)
    end = str(end_node_id)
    if start not in ids or end not in ids or start == end:
        raise ValueError("Vector join requires two different existing nodes")
    if any(
        item["start_node_id"] == start and item["end_node_id"] == end
        for item in network["segments"]
    ):
        return network
    value_kind = str(kind or "line").casefold()
    if value_kind not in VECTOR_SEGMENT_KINDS:
        raise ValueError(f"Unsupported vector segment kind: {kind}")
    used_segments = {item["id"] for item in network["segments"]}
    network["segments"].append(
        {
            "id": _unique_id("segment", used_segments),
            "start_node_id": start,
            "end_node_id": end,
            "kind": value_kind,
        }
    )
    return set_vector_segment_kind(
        network,
        network["segments"][-1]["id"],
        value_kind,
    )


__all__ = [
    "VECTOR_NODE_KINDS",
    "VECTOR_SEGMENT_KINDS",
    "add_vector_node",
    "create_vector_network",
    "join_vector_nodes",
    "normalize_vector_content",
    "normalize_vector_network",
    "remove_vector_node",
    "set_vector_path_closed",
    "set_vector_segment_kind",
    "split_vector_segment",
    "update_vector_node",
    "vector_network_to_svg_path",
    "vector_network_to_qpath",
]
