"""Editable hierarchy and rigid-motion grouping for decomposed images."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


LAYER_GRAPH_SCHEMA = "tigerstudio.motion.layer_graph.v1"


def _value(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _bbox(item: Any) -> tuple[int, int, int, int]:
    value = list(_value(item, "bbox", (0, 0, 1, 1)))
    return int(value[0]), int(value[1]), max(1, int(value[2])), max(1, int(value[3]))


def _intersection_ratio(child: tuple[int, int, int, int], parent: tuple[int, int, int, int]) -> float:
    cx, cy, cw, ch = child
    px, py, pw, ph = parent
    x0 = max(cx, px)
    y0 = max(cy, py)
    x1 = min(cx + cw, px + pw)
    y1 = min(cy + ch, py + ph)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return float((x1 - x0) * (y1 - y0)) / float(max(1, cw * ch))


@dataclass(slots=True)
class LayerGraphNode:
    id: str
    role: str
    parent_id: str = ""
    motion_group_id: str = ""
    rigid: bool = False
    pivot: tuple[float, float] = (0.0, 0.0)
    depth: float = 0.5
    z_order: int = 0
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "parent_id": self.parent_id,
            "motion_group_id": self.motion_group_id,
            "rigid": bool(self.rigid),
            "pivot": [float(self.pivot[0]), float(self.pivot[1])],
            "depth": float(self.depth),
            "z_order": int(self.z_order),
            "confidence": float(self.confidence),
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class LayerGraph:
    nodes: list[LayerGraphNode]
    schema: str = LAYER_GRAPH_SCHEMA
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "nodes": [item.to_dict() for item in self.nodes],
            "warnings": list(self.warnings),
        }

    def by_id(self) -> dict[str, LayerGraphNode]:
        return {item.id: item for item in self.nodes}


def validate_layer_graph(graph: LayerGraph | Mapping[str, Any]) -> list[str]:
    rows = graph.nodes if isinstance(graph, LayerGraph) else list(graph.get("nodes") or [])
    parent_by_id: dict[str, str] = {}
    ids: set[str] = set()
    warnings: list[str] = []
    for row in rows:
        node_id = str(_value(row, "id", "") or "")
        parent_id = str(_value(row, "parent_id", "") or "")
        if not node_id:
            warnings.append("Layer graph contains an empty node id.")
            continue
        if node_id in ids:
            warnings.append(f"Layer graph contains duplicate node id: {node_id}")
        ids.add(node_id)
        parent_by_id[node_id] = parent_id
    for node_id, parent_id in parent_by_id.items():
        if parent_id and parent_id not in ids:
            warnings.append(f"Layer graph node {node_id} has missing parent {parent_id}.")
        seen = {node_id}
        cursor = parent_id
        while cursor:
            if cursor in seen:
                warnings.append(f"Layer graph contains a parent cycle at {node_id}.")
                break
            seen.add(cursor)
            cursor = parent_by_id.get(cursor, "")
    return list(dict.fromkeys(warnings))


def build_layer_graph(
    elements: Iterable[Any],
    *,
    width: int,
    height: int,
) -> LayerGraph:
    rows = list(elements)
    primary = next((item for item in rows if str(_value(item, "role", "")) == "primary_subject"), None)
    primary_id = str(_value(primary, "id", "") or "") if primary is not None else ""
    primary_bbox = _bbox(primary) if primary is not None else (0, 0, 1, 1)
    nodes: list[LayerGraphNode] = []

    visual_rows = [item for item in rows if str(_value(item, "role", "")) != "text"]
    visual_rows.sort(key=lambda item: (float(_value(item, "depth", 0.5)), -float(_value(item, "area_ratio", 0.0))))
    visual_z = {str(_value(item, "id", "")): index + 1 for index, item in enumerate(visual_rows)}
    text_z_start = len(visual_rows) + 1

    for index, item in enumerate(rows):
        node_id = str(_value(item, "id", "") or f"element_{index + 1:02d}")
        role = str(_value(item, "role", "secondary_element") or "secondary_element")
        metadata = dict(_value(item, "metadata", {}) or {})
        bbox = _bbox(item)
        parent_id = str(metadata.get("parent_id") or "")
        rigid = bool(metadata.get("motion_lock_to_background")) or role == "primary_subject"
        motion_group_id = str(metadata.get("motion_group_id") or f"group_{node_id}")
        warnings: list[str] = []

        if role == "text":
            motion_group_id = "group_typography"
        elif parent_id:
            motion_group_id = str(
                metadata.get("motion_group_id") or f"group_{parent_id}"
            )
            rigid = bool(metadata.get("rigid", True))
        elif role == "secondary_element" and primary_id:
            overlap = _intersection_ratio(bbox, primary_bbox)
            if overlap >= 0.2:
                parent_id = primary_id
                motion_group_id = f"group_{primary_id}"
                rigid = True
                warnings.append("Secondary element is attached to the primary rigid group.")

        raw_pivot = metadata.get("pivot")
        pivot = (
            (
                max(0.0, min(float(width), float(raw_pivot[0]))),
                max(0.0, min(float(height), float(raw_pivot[1]))),
            )
            if isinstance(raw_pivot, (list, tuple)) and len(raw_pivot) >= 2
            else (
                max(0.0, min(float(width), bbox[0] + bbox[2] * 0.5)),
                max(0.0, min(float(height), bbox[1] + bbox[3] * 0.5)),
            )
        )
        default_z = (
            text_z_start + index
            if role == "text"
            else visual_z.get(node_id, index + 1)
        )
        nodes.append(LayerGraphNode(
            id=node_id,
            role=role,
            parent_id=parent_id,
            motion_group_id=motion_group_id,
            rigid=rigid,
            pivot=pivot,
            depth=float(_value(item, "depth", 0.5)),
            z_order=int(metadata.get("z_order", default_z) or default_z),
            confidence=float(_value(item, "confidence", 0.0)),
            warnings=warnings,
        ))
    graph = LayerGraph(nodes=nodes)
    graph.warnings.extend(validate_layer_graph(graph))
    return graph


__all__ = [
    "LAYER_GRAPH_SCHEMA",
    "LayerGraph",
    "LayerGraphNode",
    "build_layer_graph",
    "validate_layer_graph",
]
