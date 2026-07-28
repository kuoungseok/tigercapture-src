"""Shared geometry contract for Painter UI parametric shapes."""
from __future__ import annotations

import math
from typing import Any, Mapping

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainterPath


PARAMETRIC_SHAPE_KINDS = frozenset({"polygon", "star", "arc"})


def _number(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def normalize_parametric_shape_content(
    kind: str,
    content: Mapping[str, Any] | None,
) -> dict[str, Any]:
    result = dict(content) if isinstance(content, Mapping) else {}
    shape_kind = str(kind or "").strip().casefold()
    if shape_kind not in PARAMETRIC_SHAPE_KINDS:
        return result
    result["point_count"] = max(
        3,
        min(64, int(round(_number(result.get("point_count"), 5.0)))),
    )
    result["rotation_offset"] = max(
        -360.0,
        min(360.0, _number(result.get("rotation_offset"), -90.0)),
    )
    if shape_kind == "star":
        result["inner_radius"] = max(
            0.05,
            min(0.95, _number(result.get("inner_radius"), 0.45)),
        )
    elif shape_kind == "arc":
        result["start_angle"] = max(
            -360.0,
            min(360.0, _number(result.get("start_angle"), -90.0)),
        )
        result["sweep_angle"] = max(
            1.0,
            min(360.0, abs(_number(result.get("sweep_angle"), 270.0))),
        )
        result["inner_radius"] = max(
            0.0,
            min(0.95, _number(result.get("inner_radius"), 0.55)),
        )
    return result


def _radial_point(
    rect: QRectF,
    angle_degrees: float,
    radius_ratio: float = 1.0,
) -> QPointF:
    radians = math.radians(float(angle_degrees))
    return QPointF(
        rect.center().x()
        + math.cos(radians) * rect.width() * 0.5 * radius_ratio,
        rect.center().y()
        + math.sin(radians) * rect.height() * 0.5 * radius_ratio,
    )


def _polygon_points(
    rect: QRectF,
    *,
    point_count: int,
    rotation_offset: float,
    inner_radius: float | None = None,
) -> list[QPointF]:
    steps = point_count if inner_radius is None else point_count * 2
    points: list[QPointF] = []
    for index in range(steps):
        ratio = (
            float(inner_radius)
            if inner_radius is not None and index % 2
            else 1.0
        )
        points.append(
            _radial_point(
                rect,
                rotation_offset + 360.0 * index / steps,
                ratio,
            )
        )
    return points


def _append_polygon(path: QPainterPath, points: list[QPointF]) -> None:
    if not points:
        return
    path.moveTo(points[0])
    for point in points[1:]:
        path.lineTo(point)
    path.closeSubpath()


def parametric_shape_path(
    rect: QRectF,
    kind: str,
    content: Mapping[str, Any] | None = None,
) -> QPainterPath:
    shape_kind = str(kind or "").strip().casefold()
    normalized = normalize_parametric_shape_content(shape_kind, content)
    path = QPainterPath()
    if shape_kind == "polygon":
        _append_polygon(
            path,
            _polygon_points(
                rect,
                point_count=int(normalized["point_count"]),
                rotation_offset=float(normalized["rotation_offset"]),
            ),
        )
        return path
    if shape_kind == "star":
        _append_polygon(
            path,
            _polygon_points(
                rect,
                point_count=int(normalized["point_count"]),
                rotation_offset=float(normalized["rotation_offset"]),
                inner_radius=float(normalized["inner_radius"]),
            ),
        )
        return path
    if shape_kind != "arc":
        path.addRect(rect)
        return path

    start = float(normalized["start_angle"])
    sweep = float(normalized["sweep_angle"])
    inner_radius = float(normalized["inner_radius"])
    if sweep >= 359.999:
        path.addEllipse(rect)
        if inner_radius > 0.0:
            inner = QRectF(
                rect.center().x() - rect.width() * inner_radius * 0.5,
                rect.center().y() - rect.height() * inner_radius * 0.5,
                rect.width() * inner_radius,
                rect.height() * inner_radius,
            )
            path.addEllipse(inner)
            path.setFillRule(Qt.FillRule.OddEvenFill)
        return path

    segment_count = max(4, int(math.ceil(sweep / 6.0)))
    path.moveTo(rect.center())
    path.lineTo(_radial_point(rect, start))
    for index in range(1, segment_count + 1):
        path.lineTo(
            _radial_point(rect, start + sweep * index / segment_count)
        )
    path.lineTo(rect.center())
    path.closeSubpath()
    if inner_radius <= 0.0:
        return path

    inner = QPainterPath()
    inner.moveTo(rect.center())
    inner.lineTo(_radial_point(rect, start, inner_radius))
    for index in range(1, segment_count + 1):
        inner.lineTo(
            _radial_point(
                rect,
                start + sweep * index / segment_count,
                inner_radius,
            )
        )
    inner.lineTo(rect.center())
    inner.closeSubpath()
    return path.subtracted(inner)


def parametric_shape_svg_path(
    rect: QRectF,
    kind: str,
    content: Mapping[str, Any] | None = None,
) -> str:
    path = parametric_shape_path(rect, kind, content)
    polygons = path.toSubpathPolygons()
    commands: list[str] = []
    for polygon in polygons:
        points = list(polygon)
        if not points:
            continue
        commands.append(f"M {points[0].x():.4f} {points[0].y():.4f}")
        commands.extend(
            f"L {point.x():.4f} {point.y():.4f}"
            for point in points[1:]
        )
        commands.append("Z")
    return " ".join(commands)


__all__ = [
    "PARAMETRIC_SHAPE_KINDS",
    "normalize_parametric_shape_content",
    "parametric_shape_path",
    "parametric_shape_svg_path",
]
