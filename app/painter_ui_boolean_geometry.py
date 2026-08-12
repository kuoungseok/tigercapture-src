"""Shared Canvas/PNG/SVG geometry for editable Painter UI Boolean groups."""
from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainterPath,
    QPainterPathStroker,
    QTransform,
)


def boolean_operand_ids(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    """Every object a boolean operation consumes, including nested ones.

    ``operand_ids`` names the operation's direct children, but a boolean
    consumes its whole subtree - a group operand contributes its contents, not
    itself.  Stopping at the direct children left those descendants painting on
    their own, which is how imported Figma booleans showed their operands'
    placeholder colours on top of the resolved shape.
    """

    objects = list(rows)
    result: set[str] = set()
    for row in objects:
        boolean = (row.get("content") or {}).get("boolean")
        if not isinstance(boolean, Mapping) or not boolean.get("enabled"):
            continue
        result.update(
            str(item)
            for item in boolean.get("operand_ids", [])
            if str(item or "")
        )
    if not result:
        return result
    children: dict[str, list[str]] = {}
    for row in objects:
        parent = str(row.get("parent_id") or "")
        if parent:
            children.setdefault(parent, []).append(str(row.get("id") or ""))
    stack = list(result)
    while stack:
        current = stack.pop()
        for child in children.get(current, ()):
            if child and child not in result:
                result.add(child)
                stack.append(child)
    return result


def _rounded_rect_path(
    rect: QRectF,
    style: Mapping[str, Any],
    geometry_scale: float,
) -> QPainterPath:
    radii = style.get("corner_radii")
    radii = radii if isinstance(radii, Mapping) else {}
    scale = max(0.0, float(geometry_scale))
    fallback = max(0.0, float(style.get("radius") or 0.0) * scale)
    maximum = min(rect.width(), rect.height()) * 0.5
    tl, tr, br, bl = (
        min(
            maximum,
            max(
                0.0,
                float(
                    radii.get(
                        key,
                        float(style.get("radius") or 0.0),
                    )
                    or 0.0
                )
                * scale,
            ),
        )
        for key in ("top_left", "top_right", "bottom_right", "bottom_left")
    )
    path = QPainterPath()
    path.moveTo(rect.left() + tl, rect.top())
    path.lineTo(rect.right() - tr, rect.top())
    path.quadTo(rect.topRight(), QPointF(rect.right(), rect.top() + tr))
    path.lineTo(rect.right(), rect.bottom() - br)
    path.quadTo(
        rect.bottomRight(),
        QPointF(rect.right() - br, rect.bottom()),
    )
    path.lineTo(rect.left() + bl, rect.bottom())
    path.quadTo(
        rect.bottomLeft(),
        QPointF(rect.left(), rect.bottom() - bl),
    )
    path.lineTo(rect.left(), rect.top() + tl)
    path.quadTo(rect.topLeft(), QPointF(rect.left() + tl, rect.top()))
    path.closeSubpath()
    return path


def ui_object_shape_path(
    row: Mapping[str, Any],
    rect: QRectF,
    *,
    geometry_scale: float = 1.0,
) -> QPainterPath:
    """Resolve one supported UI object to a path in the supplied coordinate space."""
    kind = str(row.get("kind") or "rectangle")
    content = row.get("content") or {}
    path = QPainterPath()
    if kind == "ellipse":
        path.addEllipse(rect)
    elif kind == "text":
        style = row.get("style") or {}
        content = row.get("content") or {}
        font = QFont(str(style.get("font_family") or "Inter"))
        font.setPixelSize(
            max(
                1,
                round(
                    float(style.get("font_size") or 16.0)
                    * max(0.0, float(geometry_scale))
                ),
            )
        )
        font.setWeight(
            QFont.Weight(
                max(100, min(900, int(style.get("font_weight") or 400)))
            )
        )
        from app.painter_ui_typography import apply_ui_font_axes

        apply_ui_font_axes(font, style.get("font_axes"))
        metrics = QFontMetricsF(font)
        lines = str(content.get("text") or row.get("name") or "").splitlines()
        lines = lines or [""]
        line_height = max(
            metrics.height(),
            float(style.get("font_size") or 16.0)
            * max(0.5, float(style.get("line_height") or 1.2))
            * max(0.0, float(geometry_scale)),
        )
        total_height = line_height * len(lines)
        baseline = rect.center().y() - total_height * 0.5 + metrics.ascent()
        alignment = str(style.get("text_align") or "left").casefold()
        for line in lines:
            width = metrics.horizontalAdvance(line)
            if alignment == "center":
                x = rect.center().x() - width * 0.5
            elif alignment == "right":
                x = rect.right() - width
            else:
                x = rect.left()
            path.addText(QPointF(x, baseline), font, line)
            baseline += line_height
    elif kind == "path":
        vector_network = content.get("vector_network")
        if isinstance(vector_network, Mapping):
            from app.painter_ui_vector_network import vector_network_to_qpath

            path = vector_network_to_qpath(vector_network, rect)
        else:
            # Imported Figma vectors with no editable network (plain
            # REST-style fillGeometry, e.g. a polygon/star baked from a
            # commandsBlob) still need a real path here - this is what a
            # Boolean operation subtracts/unions, not just paints. Falling
            # through to an empty path silently dropped the whole operand,
            # which is why a Boolean group with such an operand (like the
            # Auto Layout playground's hatch-triangle cutouts) rendered
            # as nothing.
            from app.painter_ui_vector_network import local_svg_path_to_qpath

            fill_rows = [
                row
                for row in content.get("vector_fill_geometry") or []
                if isinstance(row, Mapping) and str(row.get("path") or "")
            ] or [
                {"path": row}
                for row in content.get("vector_paths") or []
                if str(row or "")
            ]
            path = QPainterPath()
            for row in fill_rows:
                piece = local_svg_path_to_qpath(
                    row.get("path"),
                    rect,
                    geometry_scale=geometry_scale,
                )
                path = path.united(piece) if not path.isEmpty() else piece
    elif kind in {"polygon", "star", "arc"}:
        from app.painter_ui_parametric_shapes import parametric_shape_path

        path = parametric_shape_path(
            rect,
            kind,
            content,
            geometry_scale=geometry_scale,
        )
    else:
        path = _rounded_rect_path(
            rect,
            row.get("style") or {},
            geometry_scale,
        )
    rotation = float(row.get("rotation") or 0.0)
    if abs(rotation) >= 0.001:
        pivot = QPointF(
            rect.left() + rect.width() * float(row.get("pivot_x", 0.5)),
            rect.top() + rect.height() * float(row.get("pivot_y", 0.5)),
        )
        transform = QTransform()
        transform.translate(pivot.x(), pivot.y())
        transform.rotate(rotation)
        transform.translate(-pivot.x(), -pivot.y())
        path = transform.map(path)
    return path


def _paint_is_visible(paint: Mapping[str, Any]) -> bool:
    if not bool(paint.get("visible", True)):
        return False
    if float(paint.get("opacity", 1.0) or 0.0) <= 0.0:
        return False
    if str(paint.get("type") or "solid").casefold() != "solid":
        return True
    return QColor(str(paint.get("color") or "#00000000")).alpha() > 0


def _fill_is_visible(row: Mapping[str, Any]) -> bool:
    style = row.get("style") or {}
    if row.get("kind") == "text":
        return QColor(str(style.get("text_color") or "#000000FF")).alpha() > 0
    paints = style.get("fills")
    if isinstance(paints, list):
        return any(
            _paint_is_visible(paint)
            for paint in paints
            if isinstance(paint, Mapping)
        )
    if "fill" not in style:
        return True
    return QColor(str(style.get("fill") or "#00000000")).alpha() > 0


def _stroke_paints(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    style = row.get("style") or {}
    paints = style.get("strokes")
    if isinstance(paints, list):
        return [
            dict(paint)
            for paint in paints
            if isinstance(paint, Mapping) and _paint_is_visible(paint)
        ]
    width = max(0.0, float(style.get("stroke_width") or 0.0))
    color = str(style.get("stroke") or "#00000000")
    if width <= 0.0 or QColor(color).alpha() <= 0:
        return []
    return [
        {
            "type": "solid",
            "visible": True,
            "opacity": 1.0,
            "color": color,
            "width": width,
            "align": style.get("stroke_align") or "center",
        }
    ]


def _stroke_geometry(
    path: QPainterPath,
    row: Mapping[str, Any],
    paint: Mapping[str, Any],
    *,
    geometry_scale: float,
) -> QPainterPath:
    width = max(0.0, float(paint.get("width") or 0.0)) * max(
        0.0,
        float(geometry_scale),
    )
    if width <= 0.0 or path.isEmpty():
        return QPainterPath()
    style = row.get("style") or {}
    alignment = str(
        paint.get("align") or style.get("stroke_align") or "center"
    ).casefold()
    stroker = QPainterPathStroker()
    stroker.setWidth(width * (2.0 if alignment in {"inside", "outside"} else 1.0))
    stroker.setCapStyle(
        {
            "round": Qt.PenCapStyle.RoundCap,
            "square": Qt.PenCapStyle.SquareCap,
        }.get(
            str(style.get("stroke_cap") or "").casefold(),
            Qt.PenCapStyle.FlatCap,
        )
    )
    stroker.setJoinStyle(
        {
            "round": Qt.PenJoinStyle.RoundJoin,
            "bevel": Qt.PenJoinStyle.BevelJoin,
        }.get(
            str(style.get("stroke_join") or "").casefold(),
            Qt.PenJoinStyle.MiterJoin,
        )
    )
    dash = style.get("stroke_dash")
    if isinstance(dash, list) and dash:
        stroker.setDashPattern([max(0.0, float(value)) for value in dash])
    outline = stroker.createStroke(path)
    if alignment == "inside":
        return outline.intersected(path)
    if alignment == "outside":
        return outline.subtracted(path)
    return outline


def ui_object_boolean_geometry_path(
    row: Mapping[str, Any],
    rect: QRectF,
    *,
    geometry_scale: float = 1.0,
) -> QPainterPath:
    """Resolve the visible fill and stroke footprint used by Boolean operations."""
    base = ui_object_shape_path(
        row,
        rect,
        geometry_scale=geometry_scale,
    )
    result = QPainterPath(base) if _fill_is_visible(row) else QPainterPath()
    stroke_paints = _stroke_paints(row)
    if not stroke_paints:
        # A fill-only path is already valid Boolean input.  Simplifying every
        # large operand here duplicates the canonicalization performed after
        # the group operation and causes a visible editing stall for large
        # vector networks.
        return result
    for paint in stroke_paints:
        result = result.united(
            _stroke_geometry(
                base,
                row,
                paint,
                geometry_scale=geometry_scale,
            )
        )
    return result.simplified()


def resolve_ui_boolean_path(
    rows: Iterable[Mapping[str, Any]],
    boolean_row: Mapping[str, Any],
    rect_for_object: Callable[[Mapping[str, Any]], QRectF],
    *,
    geometry_scale_for_object: (
        Callable[[Mapping[str, Any]], float] | None
    ) = None,
) -> QPainterPath | None:
    boolean = (boolean_row.get("content") or {}).get("boolean")
    if not isinstance(boolean, Mapping) or not boolean.get("enabled"):
        return None
    by_id = {str(row["id"]): row for row in rows}
    children_by_parent: dict[str, list[Mapping[str, Any]]] = {}
    for row in by_id.values():
        parent_id = str(row.get("parent_id") or "")
        if parent_id:
            children_by_parent.setdefault(parent_id, []).append(row)

    def shape(
        operand: Mapping[str, Any],
        visiting: set[str],
    ) -> QPainterPath:
        operand_id = str(operand.get("id") or "")
        operand_boolean = (operand.get("content") or {}).get("boolean")
        if (
            isinstance(operand_boolean, Mapping)
            and operand_boolean.get("enabled")
            and operand_boolean.get("group")
        ):
            nested = resolve(operand, visiting)
            return nested if nested is not None else QPainterPath()
        children = children_by_parent.get(operand_id)
        if children and str(operand.get("kind") or "") in {"frame", "group"}:
            # A plain (non-Boolean) group operand contributes its children's
            # combined shape, not its own bounding box - an operand like a
            # rotated rectangle wrapped in an organizational group otherwise
            # resolved to the group's axis-aligned box instead of the
            # rotated rectangle actually inside it.
            if operand_id in visiting:
                return QPainterPath()
            next_visiting = set(visiting)
            next_visiting.add(operand_id)
            combined = QPainterPath()
            for child in children:
                if not bool(child.get("visible", True)):
                    continue
                piece = shape(child, next_visiting)
                combined = (
                    combined.united(piece) if not combined.isEmpty() else piece
                )
            return combined
        scale = (
            float(geometry_scale_for_object(operand))
            if geometry_scale_for_object is not None
            else 1.0
        )
        return ui_object_boolean_geometry_path(
            operand,
            rect_for_object(operand),
            geometry_scale=scale,
        )

    def resolve(
        group_row: Mapping[str, Any],
        visiting: set[str],
    ) -> QPainterPath | None:
        group_id = str(group_row.get("id") or "")
        if not group_id or group_id in visiting:
            return None
        nested_boolean = (group_row.get("content") or {}).get("boolean")
        if not isinstance(nested_boolean, Mapping) or not nested_boolean.get("enabled"):
            return None
        operands = [
            by_id[str(object_id)]
            for object_id in nested_boolean.get("operand_ids", [])
            if str(object_id) in by_id
        ]
        if len(operands) < 2:
            return None
        next_visiting = set(visiting)
        next_visiting.add(group_id)
        result = shape(operands[0], next_visiting)
        operation = str(nested_boolean.get("operation") or "union").casefold()
        for operand in operands[1:]:
            path = shape(operand, next_visiting)
            if operation == "subtract":
                result = result.subtracted(path)
            elif operation == "intersect":
                result = result.intersected(path)
            elif operation == "exclude":
                result = result.united(path).subtracted(
                    result.intersected(path)
                )
            else:
                result = result.united(path)
        return result.simplified()

    return resolve(boolean_row, set())


def qpath_to_svg_path(path: QPainterPath) -> str:
    commands: list[str] = []
    index = 0
    while index < path.elementCount():
        element = path.elementAt(index)
        if element.isMoveTo():
            commands.append(f"M {element.x:.6f} {element.y:.6f}")
        elif element.isLineTo():
            commands.append(f"L {element.x:.6f} {element.y:.6f}")
        elif element.isCurveTo() and index + 2 < path.elementCount():
            control_2 = path.elementAt(index + 1)
            endpoint = path.elementAt(index + 2)
            commands.append(
                "C "
                f"{element.x:.6f} {element.y:.6f} "
                f"{control_2.x:.6f} {control_2.y:.6f} "
                f"{endpoint.x:.6f} {endpoint.y:.6f}"
            )
            index += 2
        index += 1
    return " ".join(commands)


def qpath_to_vector_network(
    path: QPainterPath,
    bounds: QRectF | None = None,
) -> dict[str, Any]:
    """Convert a resolved path into an editable, bounds-normalized network."""
    rect = QRectF(bounds or path.boundingRect())
    width = max(1e-9, float(rect.width()))
    height = max(1e-9, float(rect.height()))
    nodes: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    node_serial = 0
    segment_serial = 0
    current_id = ""
    subpath_start_id = ""

    def normalized(x: float, y: float) -> dict[str, float]:
        return {
            "x": (float(x) - rect.left()) / width,
            "y": (float(y) - rect.top()) / height,
        }

    def add_node(x: float, y: float) -> dict[str, Any]:
        nonlocal node_serial
        node_serial += 1
        point = normalized(x, y)
        node = {
            "id": f"node-{node_serial}",
            **point,
            "in_handle": None,
            "out_handle": None,
            "kind": "corner",
        }
        nodes.append(node)
        return node

    def add_segment(start_id: str, end_id: str, kind: str) -> None:
        nonlocal segment_serial
        if not start_id or not end_id or start_id == end_id:
            return
        segment_serial += 1
        segments.append(
            {
                "id": f"segment-{segment_serial}",
                "start_node_id": start_id,
                "end_node_id": end_id,
                "kind": kind,
            }
        )

    index = 0
    while index < path.elementCount():
        element = path.elementAt(index)
        if element.isMoveTo():
            node = add_node(element.x, element.y)
            current_id = node["id"]
            subpath_start_id = current_id
        elif element.isLineTo():
            point = normalized(element.x, element.y)
            start_node = next(
                (node for node in nodes if node["id"] == current_id),
                None,
            )
            if (
                start_node is not None
                and subpath_start_id
                and abs(point["x"] - nodes[int(subpath_start_id.split("-")[-1]) - 1]["x"]) < 1e-9
                and abs(point["y"] - nodes[int(subpath_start_id.split("-")[-1]) - 1]["y"]) < 1e-9
            ):
                add_segment(current_id, subpath_start_id, "line")
                current_id = subpath_start_id
            else:
                node = add_node(element.x, element.y)
                add_segment(current_id, node["id"], "line")
                current_id = node["id"]
        elif element.isCurveTo() and index + 2 < path.elementCount():
            control_2 = path.elementAt(index + 1)
            endpoint = path.elementAt(index + 2)
            start_node = next(
                (node for node in nodes if node["id"] == current_id),
                None,
            )
            if start_node is not None:
                start_node["out_handle"] = normalized(element.x, element.y)
                start_node["kind"] = "smooth"
            node = add_node(endpoint.x, endpoint.y)
            node["in_handle"] = normalized(control_2.x, control_2.y)
            node["kind"] = "smooth"
            add_segment(current_id, node["id"], "cubic")
            current_id = node["id"]
            index += 2
        index += 1
    return {
        "nodes": nodes,
        "segments": segments,
        "closed": bool(segments),
    }


__all__ = [
    "boolean_operand_ids",
    "qpath_to_svg_path",
    "qpath_to_vector_network",
    "resolve_ui_boolean_path",
    "ui_object_boolean_geometry_path",
    "ui_object_shape_path",
]
