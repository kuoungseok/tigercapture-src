"""Bristle/impasto stroke dynamics shared by color and material rendering."""
from __future__ import annotations

import colorsys
import math
from typing import Any, Sequence

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtCore import Qt


BRISTLE_V2_STYLES = frozenset(
    {
        "loaded_oil",
        "impasto_oil",
        "real_wet_oil",
        "bristle_oil",
        "filbert_oil",
        "flat_hog_oil",
        "fan_bristle_oil",
        "dry_oil",
        "scumble_oil",
        "acrylic_bristle",
    }
)


def _value(row: Any, name: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(name, default)
    return getattr(row, name, default)


def normalize_curve(values: Sequence[Any] | None, count: int, default: float) -> list[float]:
    rows = list(values or [])
    if not rows:
        return [max(0.0, min(1.0, float(default)))] * max(0, count)
    clean = []
    for value in rows:
        try:
            clean.append(max(0.0, min(1.0, float(value))))
        except (TypeError, ValueError):
            clean.append(max(0.0, min(1.0, float(default))))
    if len(clean) == count:
        return clean
    if count <= 1:
        return [clean[0]]
    out = []
    for index in range(count):
        position = index * (len(clean) - 1) / max(1, count - 1)
        left = min(len(clean) - 1, int(math.floor(position)))
        right = min(len(clean) - 1, left + 1)
        blend = position - left
        out.append(clean[left] * (1.0 - blend) + clean[right] * blend)
    return out


def stroke_uses_bristle_v2(stroke: Any) -> bool:
    return (
        int(_value(stroke, "brush_engine_version", 1) or 1) >= 2
        and str(_value(stroke, "brush_style", "") or "").casefold() in BRISTLE_V2_STYLES
    )


def bristle_lane_paths(
    stroke: Any,
    *,
    width: int,
    height: int,
) -> list[list[tuple[float, float, float, float]]]:
    raw_points = list(_value(stroke, "points", []) or [])
    if not raw_points:
        return []
    points = [
        (float(point[0]) * width, float(point[1]) * height)
        for point in raw_points
    ]
    if len(points) > 256:
        stride = max(1, int(math.ceil(len(points) / 256.0)))
        points = points[::stride]
        if points[-1] != (
            float(raw_points[-1][0]) * width,
            float(raw_points[-1][1]) * height,
        ):
            points.append(
                (
                    float(raw_points[-1][0]) * width,
                    float(raw_points[-1][1]) * height,
                )
            )
    point_count = len(points)
    pressure = normalize_curve(_value(stroke, "point_pressure", []), point_count, 0.82)
    load = normalize_curve(_value(stroke, "point_load", []), point_count, 1.0)
    rotation = normalize_curve(_value(stroke, "point_rotation", []), point_count, 0.5)
    depletion = max(0.0, min(1.0, float(_value(stroke, "load_depletion", 0.28) or 0.0)))
    base_width = max(0.25, float(_value(stroke, "width_px", 4.0) or 4.0))
    requested = int(_value(stroke, "bristle_count", 0) or 0)
    lanes = max(5, min(36, requested or int(round(base_width * 0.46))))
    seed = int(_value(stroke, "brush_seed", 0) or 0)
    out: list[list[tuple[float, float, float, float]]] = []
    for lane in range(lanes):
        lane_norm = (lane + 0.5) / lanes * 2.0 - 1.0
        lane_noise = math.sin((lane + 1) * 17.31 + seed * 0.137) * 0.5 + 0.5
        strand: list[tuple[float, float, float, float]] = []
        for index, (x, y) in enumerate(points):
            prev_x, prev_y = points[max(0, index - 1)]
            next_x, next_y = points[min(point_count - 1, index + 1)]
            dx = next_x - prev_x
            dy = next_y - prev_y
            length = max(0.001, math.hypot(dx, dy))
            nx = -dy / length
            ny = dx / length
            progress = index / max(1, point_count - 1)
            local_pressure = pressure[index]
            local_load = max(0.04, load[index] * (1.0 - depletion * progress))
            fan = 1.0 + (rotation[index] - 0.5) * lane_norm * 0.42
            jitter = math.sin(index * 1.71 + lane * 2.13 + seed * 0.19) * base_width * 0.025
            offset = lane_norm * base_width * 0.47 * local_pressure * fan + jitter
            strand.append((x + nx * offset, y + ny * offset, local_pressure, local_load))
        if lane_noise > 0.10:
            out.append(strand)
    return out


def _lane_color(base: QColor, lane: int, seed: int, alpha: int) -> QColor:
    r, g, b = base.redF(), base.greenF(), base.blueF()
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    noise = math.sin((lane + 1) * 12.17 + seed * 0.71) * 0.5 + 0.5
    h = (h + (noise - 0.5) * 0.035) % 1.0
    s = max(0.0, min(1.0, s * (0.88 + noise * 0.22)))
    v = max(0.0, min(1.0, v * (0.68 + noise * 0.54)))
    rr, gg, bb = colorsys.hsv_to_rgb(h, s, v)
    return QColor.fromRgbF(rr, gg, bb, max(0.0, min(1.0, alpha / 255.0)))


def paint_bristle_v2(
    painter: QPainter,
    stroke: Any,
    width: int,
    height: int,
    color: QColor,
) -> bool:
    if not stroke_uses_bristle_v2(stroke):
        return False
    lanes = bristle_lane_paths(stroke, width=width, height=height)
    if not lanes:
        return False
    base_width = max(0.25, float(_value(stroke, "width_px", 4.0) or 4.0))
    seed = int(_value(stroke, "brush_seed", 0) or 0)
    lane_width = max(0.65, base_width / max(5, len(lanes)) * 0.92)
    style = str(_value(stroke, "brush_style", "") or "").casefold()
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    try:
        body_alpha_scale = {
            "dry_oil": 0.08,
            "scumble_oil": 0.10,
            "fan_bristle_oil": 0.16,
            "bristle_oil": 0.24,
        }.get(style, 0.42)
        body = QColor(color)
        body.setAlpha(max(1, min(255, int(color.alpha() * body_alpha_scale))))
        body_pen = QPen(body, max(1.0, base_width * 0.76))
        body_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        body_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(body_pen)
        body_points = [
            QPointF(float(point[0]) * width, float(point[1]) * height)
            for point in list(_value(stroke, "points", []) or [])
        ]
        if len(body_points) == 1:
            painter.drawPoint(body_points[0])
        elif body_points:
            painter.drawPolyline(body_points)

        for lane_index, strand in enumerate(lanes):
            lane_color = _lane_color(color, lane_index, seed, color.alpha())
            for index in range(len(strand) - 1):
                x1, y1, pressure, load = strand[index]
                x2, y2, next_pressure, next_load = strand[index + 1]
                alpha = int(
                    color.alpha()
                    * (0.34 + 0.66 * min(load, next_load))
                    * (0.48 + 0.52 * min(pressure, next_pressure))
                )
                segment_color = QColor(lane_color)
                segment_color.setAlpha(max(1, min(255, alpha)))
                pen = QPen(
                    segment_color,
                    max(0.55, lane_width * (0.55 + min(pressure, next_pressure))),
                )
                pen.setCapStyle(Qt.PenCapStyle.FlatCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
                if lane_index % 4 == 0:
                    highlight = QColor(255, 246, 220, max(4, int(alpha * 0.20)))
                    highlight_pen = QPen(highlight, max(0.35, pen.widthF() * 0.24))
                    highlight_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
                    painter.setPen(highlight_pen)
                    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    finally:
        painter.restore()
    return True
