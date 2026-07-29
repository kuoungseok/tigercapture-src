"""Shared Canvas/PNG/SVG geometry for editable Painter UI Boolean groups."""
from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath, QTransform


def boolean_operand_ids(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    result: set[str] = set()
    for row in rows:
        boolean = (row.get("content") or {}).get("boolean")
        if not isinstance(boolean, Mapping) or not boolean.get("enabled"):
            continue
        result.update(
            str(item)
            for item in boolean.get("operand_ids", [])
            if str(item or "")
        )
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
    elif kind == "path":
        from app.painter_ui_vector_network import vector_network_to_qpath

        path = vector_network_to_qpath(
            content.get("vector_network"),
            rect,
        )
    elif kind in {"polygon", "star", "arc"}:
        from app.painter_ui_parametric_shapes import parametric_shape_path

        path = parametric_shape_path(rect, kind, content)
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
    operands = [
        by_id[str(object_id)]
        for object_id in boolean.get("operand_ids", [])
        if str(object_id) in by_id
    ]
    if len(operands) < 2:
        return None
    def shape(operand: Mapping[str, Any]) -> QPainterPath:
        scale = (
            float(geometry_scale_for_object(operand))
            if geometry_scale_for_object is not None
            else 1.0
        )
        return ui_object_shape_path(
            operand,
            rect_for_object(operand),
            geometry_scale=scale,
        )

    result = shape(operands[0])
    operation = str(boolean.get("operation") or "union").casefold()
    for operand in operands[1:]:
        path = shape(operand)
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


__all__ = [
    "boolean_operand_ids",
    "qpath_to_svg_path",
    "resolve_ui_boolean_path",
    "ui_object_shape_path",
]
