"""Explicit conversion between Painter UI objects and Paint/Vector workflows."""
from __future__ import annotations

import copy
import math
from typing import Any, Mapping, Sequence

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainterPath

from app.painter_ui_document import (
    normalize_ui_document,
    validate_ui_document,
)
from app.painter_ui_motion_bridge import resolved_ui_geometry
from app.painter_ui_parametric_shapes import parametric_shape_path
from app.painter_ui_themes import resolve_ui_theme_document
from app.painter_ui_vector_network import normalize_vector_content


CONVERSION_INSPECT_SCHEMA = "tigerstudio.painter.ui.conversion.inspect.v1"
PAINT_CONVERSION_SCHEMA = "tigerstudio.painter.ui.conversion.paint.v1"
VECTOR_CONVERSION_SCHEMA = "tigerstudio.painter.ui.conversion.vector.v1"
_VECTOR_SOURCE_KINDS = {
    "rectangle",
    "ellipse",
    "line",
    "polygon",
    "star",
    "arc",
    "path",
}


def _selected_ids(
    document: Mapping[str, Any],
    object_ids: Sequence[str] | None,
) -> list[str]:
    requested = (
        [str(value) for value in object_ids if str(value)]
        if object_ids is not None
        else [
            str(value)
            for value in (document.get("selection") or {}).get(
                "object_ids",
                [],
            )
            if str(value)
        ]
    )
    existing = {str(row["id"]) for row in document["objects"]}
    return list(dict.fromkeys(value for value in requested if value in existing))


def _selection_subtree_ids(
    document: Mapping[str, Any],
    selected_ids: Sequence[str],
) -> list[str]:
    included = set(str(value) for value in selected_ids)
    changed = True
    while changed:
        before = len(included)
        included.update(
            str(row["id"])
            for row in document["objects"]
            if str(row.get("parent_id") or "") in included
        )
        changed = len(included) != before
    return [
        str(row["id"])
        for row in document["objects"]
        if str(row["id"]) in included
    ]


def inspect_painter_ui_conversion(
    value: Mapping[str, Any],
    *,
    object_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    selected_ids = _selected_ids(document, object_ids)
    selected_set = set(selected_ids)
    rows = [
        row for row in document["objects"] if str(row["id"]) in selected_set
    ]
    vector_features = []
    vector_counts = {"Convertible": 0, "Already Vector": 0, "Blocked": 0}
    for row in rows:
        kind = str(row["kind"])
        if row["locked"]:
            resolved = "Blocked"
            reason = "locked UI object"
        elif (
            str(row.get("component_id") or "")
            or str(row.get("component_role") or "none") != "none"
        ):
            resolved = "Blocked"
            reason = "detach the component before converting its geometry"
        elif kind == "path":
            resolved = "Already Vector"
            reason = "object already owns an editable Vector Network"
        elif kind in _VECTOR_SOURCE_KINDS:
            resolved = "Convertible"
            reason = "shape can become editable Vector Network geometry"
        else:
            resolved = "Blocked"
            reason = f"{kind} semantics cannot be preserved as one vector path"
        vector_counts[resolved] += 1
        vector_features.append(
            {
                "object_id": row["id"],
                "object_name": row["name"],
                "object_kind": kind,
                "resolved": resolved,
                "reason": reason,
            }
        )
    subtree_ids = _selection_subtree_ids(document, selected_ids)
    artboard_ids = {
        str(row["artboard_id"])
        for row in document["objects"]
        if str(row["id"]) in set(subtree_ids)
    }
    paint_blockers = []
    if not selected_ids:
        paint_blockers.append("selection_required")
    if len(artboard_ids) > 1:
        paint_blockers.append("paint_conversion_requires_one_artboard")
    return {
        "schema": CONVERSION_INSPECT_SCHEMA,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "selected_object_ids": selected_ids,
        "paint": {
            "available": not paint_blockers,
            "source_object_ids": subtree_ids,
            "blockers": paint_blockers,
            "result": "editable Paint image layer with preserved UI source",
        },
        "vector": {
            "available": bool(vector_counts["Convertible"]),
            "counts": vector_counts,
            "features": vector_features,
            "blockers": [
                f"{row['object_id']}:{row['reason']}"
                for row in vector_features
                if row["resolved"] == "Blocked"
            ],
        },
    }


def _path_to_vector_network(path: QPainterPath) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    node_serial = 0
    segment_serial = 0
    for polygon in path.toSubpathPolygons():
        points = list(polygon)
        if len(points) > 1 and points[0] == points[-1]:
            points.pop()
        if len(points) < 2:
            continue
        polygon_ids = []
        for point in points:
            node_serial += 1
            node_id = f"node-{node_serial}"
            polygon_ids.append(node_id)
            nodes.append(
                {
                    "id": node_id,
                    "x": float(point.x()),
                    "y": float(point.y()),
                    "in_handle": None,
                    "out_handle": None,
                    "kind": "corner",
                }
            )
        for start_id, end_id in zip(polygon_ids, polygon_ids[1:]):
            segment_serial += 1
            segments.append(
                {
                    "id": f"segment-{segment_serial}",
                    "start_node_id": start_id,
                    "end_node_id": end_id,
                    "kind": "line",
                }
            )
        if len(polygon_ids) >= 3:
            segment_serial += 1
            segments.append(
                {
                    "id": f"segment-{segment_serial}",
                    "start_node_id": polygon_ids[-1],
                    "end_node_id": polygon_ids[0],
                    "kind": "line",
                }
            )
    return {
        "nodes": nodes,
        "segments": segments,
        "closed": any(
            segment["end_node_id"] == nodes[0]["id"]
            for segment in segments
        )
        if nodes
        else False,
    }


def _shape_vector_network(row: Mapping[str, Any]) -> dict[str, Any]:
    kind = str(row["kind"])
    if kind == "path":
        return copy.deepcopy(
            normalize_vector_content(row.get("content"))["vector_network"]
        )
    rect = QRectF(0.0, 0.0, 1.0, 1.0)
    path = QPainterPath()
    if kind == "rectangle":
        radius_px = max(0.0, float((row.get("style") or {}).get("radius") or 0.0))
        radius_x = min(0.5, radius_px / max(1.0, float(row["width"])))
        radius_y = min(0.5, radius_px / max(1.0, float(row["height"])))
        if radius_x or radius_y:
            path.addRoundedRect(rect, radius_x, radius_y)
        else:
            path.addRect(rect)
    elif kind == "ellipse":
        path.addEllipse(rect)
    elif kind == "line":
        path.moveTo(0.0, 0.0)
        path.lineTo(1.0, 1.0)
    elif kind in {"polygon", "star", "arc"}:
        path = parametric_shape_path(rect, kind, row.get("content"))
    else:
        raise ValueError(f"Unsupported vector conversion kind: {kind}")
    return _path_to_vector_network(path)


def convert_painter_ui_to_vector(
    value: Mapping[str, Any],
    *,
    object_ids: Sequence[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    inspection = inspect_painter_ui_conversion(
        document,
        object_ids=object_ids,
    )
    convertible = {
        row["object_id"]
        for row in inspection["vector"]["features"]
        if row["resolved"] == "Convertible"
    }
    if not convertible:
        raise ValueError("No selected UI object can be converted to Vector")
    converted = []
    for index, row in enumerate(document["objects"]):
        if row["id"] not in convertible:
            continue
        source_kind = str(row["kind"])
        content = copy.deepcopy(dict(row.get("content") or {}))
        content["vector_network"] = _shape_vector_network(row)
        content["converted_from_kind"] = source_kind
        document["objects"][index] = {
            **row,
            "kind": "path",
            "name": (
                row["name"]
                if str(row["name"]).casefold().endswith("vector")
                else f"{row['name']} Vector"
            ),
            "content": normalize_vector_content(content),
        }
        converted.append(row["id"])
    document["revision"] = int(document["revision"]) + 1
    document = normalize_ui_document(document)
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise ValueError(
            "Vector conversion produced invalid Painter UI: "
            + ", ".join(validation["errors"])
        )
    report = {
        "schema": VECTOR_CONVERSION_SCHEMA,
        "ok": True,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "converted_object_ids": converted,
        "converted_count": len(converted),
        "blocked": inspection["vector"]["blockers"],
        "stable_ids_preserved": True,
        "undo_steps": 1,
    }
    return document, report


def render_painter_ui_selection_to_paint(
    value: Mapping[str, Any],
    *,
    object_ids: Sequence[str] | None = None,
) -> tuple[QImage, dict[str, Any]]:
    document = resolve_ui_theme_document(normalize_ui_document(value))
    inspection = inspect_painter_ui_conversion(
        document,
        object_ids=object_ids,
    )
    if not inspection["paint"]["available"]:
        raise ValueError(
            "Painter UI to Paint conversion blocked: "
            + ", ".join(inspection["paint"]["blockers"])
        )
    source_ids = list(inspection["paint"]["source_object_ids"])
    source_set = set(source_ids)
    source_rows = [
        row for row in document["objects"] if row["id"] in source_set
    ]
    artboard_id = str(source_rows[0]["artboard_id"])
    artboard = next(
        row for row in document["artboards"] if row["id"] == artboard_id
    )
    geometry = resolved_ui_geometry(document)

    def visual_bounds(row: Mapping[str, Any]) -> tuple[float, float, float, float]:
        resolved = geometry[row["id"]]
        x = float(resolved["x"])
        y = float(resolved["y"])
        width = float(resolved["width"])
        height = float(resolved["height"])
        angle = math.radians(float(row.get("rotation") or 0.0))
        if abs(angle) < 1e-9:
            return x, y, x + width, y + height
        center_x = x + width * 0.5
        center_y = y + height * 0.5
        cosine = math.cos(angle)
        sine = math.sin(angle)
        corners = []
        for point_x, point_y in (
            (x, y),
            (x + width, y),
            (x + width, y + height),
            (x, y + height),
        ):
            local_x = point_x - center_x
            local_y = point_y - center_y
            corners.append(
                (
                    center_x + local_x * cosine - local_y * sine,
                    center_y + local_x * sine + local_y * cosine,
                )
            )
        return (
            min(point[0] for point in corners),
            min(point[1] for point in corners),
            max(point[0] for point in corners),
            max(point[1] for point in corners),
        )

    bounds = [visual_bounds(row) for row in source_rows]
    left = min(row[0] for row in bounds)
    top = min(row[1] for row in bounds)
    right = max(row[2] for row in bounds)
    bottom = max(row[3] for row in bounds)
    width = max(1, int(math.ceil(right - left)))
    height = max(1, int(math.ceil(bottom - top)))
    isolated = copy.deepcopy(document)
    isolated["artboards"] = [
        {
            **artboard,
            "id": artboard_id,
            "width": width,
            "height": height,
            "x": 0.0,
            "y": 0.0,
            "background": "#00000000",
        }
    ]
    isolated["active_artboard_id"] = artboard_id
    isolated["objects"] = []
    for row in source_rows:
        resolved = geometry[row["id"]]
        isolated["objects"].append(
            {
                **copy.deepcopy(row),
                "parent_id": "",
                "x": float(resolved["x"]) - left,
                "y": float(resolved["y"]) - top,
                "width": float(resolved["width"]),
                "height": float(resolved["height"]),
            }
        )
    isolated["selection"] = {"object_id": "", "object_ids": []}
    isolated = normalize_ui_document(isolated)
    from app.painter_ui_asset_export import render_ui_artboard

    image = render_ui_artboard(isolated, artboard_id, density=1.0)
    report = {
        "schema": PAINT_CONVERSION_SCHEMA,
        "ok": not image.isNull(),
        "document_id": document["document_id"],
        "source_revision": document["revision"],
        "artboard_id": artboard_id,
        "source_object_ids": source_ids,
        "source_bounds": {
            "x": left,
            "y": top,
            "width": right - left,
            "height": bottom - top,
        },
        "artboard_size": {
            "width": int(artboard["width"]),
            "height": int(artboard["height"]),
        },
        "pixel_size": {"width": image.width(), "height": image.height()},
        "source_preserved": True,
        "result": "paint_image_layer",
        "undo_steps": 1,
    }
    return image, report


__all__ = [
    "CONVERSION_INSPECT_SCHEMA",
    "PAINT_CONVERSION_SCHEMA",
    "VECTOR_CONVERSION_SCHEMA",
    "convert_painter_ui_to_vector",
    "inspect_painter_ui_conversion",
    "render_painter_ui_selection_to_paint",
]
