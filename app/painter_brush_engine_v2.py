"""Bristle/impasto stroke dynamics shared by color and material rendering."""
from __future__ import annotations

import copy
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
        "stipple_oil",
        "palette_knife",
        "knife_scrape_oil",
        "acrylic_bristle",
    }
)
MAX_EXPLICIT_BRISTLE_COUNT = 64

BRISTLE_ENGINE_MODEL_CONTRACT = {
    "schema": "tigerstudio.painter.bristle_engine_model.v1",
    "model": "tiger_authored_deterministic_bristle_stylization_v1",
    "coefficient_source": "authored_style_preset_not_measured_physical_bristles",
    "deterministic_replay_claim": True,
    "physical_bristle_claim": False,
    "paint_rheology_claim": False,
    "external_brush_engine_parity_claim": False,
    "max_explicit_bristle_count": MAX_EXPLICIT_BRISTLE_COUNT,
    "capacity_source": "tiger_authored_bristle_stylization_policy",
}


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


def normalize_signed_curve(
    values: Sequence[Any] | None,
    count: int,
    default: float = 0.0,
) -> list[float]:
    rows = list(values or [])
    if not rows:
        return [max(-1.0, min(1.0, float(default)))] * max(0, count)
    clean = []
    for value in rows:
        try:
            clean.append(max(-1.0, min(1.0, float(value))))
        except (TypeError, ValueError):
            clean.append(max(-1.0, min(1.0, float(default))))
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


def incremental_stroke_segments(
    stroke: Any,
    *,
    width: int | None = None,
    height: int | None = None,
) -> list[Any]:
    """Split Engine v2 strokes into prefix-stable two-point render units."""
    raw_points = list(_value(stroke, "points", []) or [])
    if not stroke_uses_bristle_v2(stroke) or len(raw_points) <= 2:
        return [stroke]
    curve_names = (
        "point_pressure",
        "point_tilt",
        "point_tilt_x",
        "point_tilt_y",
        "point_rotation",
        "point_tangential_pressure",
        "point_load",
    )
    segments: list[Any] = []
    cumulative_travel_px = max(
        0.0,
        float(_value(stroke, "brush_travel_offset_px", 0.0) or 0.0),
    )
    for index in range(len(raw_points) - 1):
        if isinstance(stroke, dict):
            segment = dict(stroke)
        else:
            segment = copy.copy(stroke)
        segment_points = raw_points[index : index + 2]
        if isinstance(segment, dict):
            segment["points"] = segment_points
            segment["brush_sample_offset"] = index
            segment["brush_travel_offset_px"] = cumulative_travel_px
            segment["brush_authored_stroke_start"] = index == 0
        else:
            segment.points = segment_points
            setattr(segment, "brush_sample_offset", index)
            setattr(segment, "brush_travel_offset_px", cumulative_travel_px)
            setattr(segment, "brush_authored_stroke_start", index == 0)
        for name in curve_names:
            values = list(_value(stroke, name, []) or [])
            sliced = values[index : index + 2] if values else []
            if isinstance(segment, dict):
                segment[name] = sliced
            else:
                setattr(segment, name, sliced)
        segments.append(segment)
        if width is not None and height is not None:
            first, second = segment_points
            cumulative_travel_px += math.hypot(
                (float(second[0]) - float(first[0])) * int(width),
                (float(second[1]) - float(first[1])) * int(height),
            )
    return segments


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
    point_count = len(points)
    pressure = normalize_curve(_value(stroke, "point_pressure", []), point_count, 1.0)
    tilt = normalize_curve(_value(stroke, "point_tilt", []), point_count, 0.5)
    raw_tilt_x = list(_value(stroke, "point_tilt_x", []) or [])
    raw_tilt_y = list(_value(stroke, "point_tilt_y", []) or [])
    tilt_x = normalize_signed_curve(raw_tilt_x, point_count)
    tilt_y = normalize_signed_curve(raw_tilt_y, point_count)
    has_directional_tilt = bool(raw_tilt_x or raw_tilt_y)
    load = normalize_curve(_value(stroke, "point_load", []), point_count, 1.0)
    rotation = normalize_curve(_value(stroke, "point_rotation", []), point_count, 0.5)
    depletion = max(0.0, min(1.0, float(_value(stroke, "load_depletion", 0.28) or 0.0)))
    dryout_px = max(1.0, float(_value(stroke, "load_dryout_px", 724.0) or 724.0))
    resaturation = max(
        0.0,
        min(1.0, float(_value(stroke, "material_resaturation", 0.0) or 0.0)),
    )
    base_width = max(0.25, float(_value(stroke, "width_px", 4.0) or 4.0))
    requested = int(_value(stroke, "bristle_count", 0) or 0)
    lanes = (
        max(1, min(MAX_EXPLICIT_BRISTLE_COUNT, requested))
        if requested > 0
        else max(5, min(36, int(round(base_width * 0.46))))
    )
    seed = int(_value(stroke, "brush_seed", 0) or 0)
    travel_offset_px = max(0.0, float(_value(stroke, "brush_travel_offset_px", 0.0) or 0.0))
    travel_px = [travel_offset_px]
    for first, second in zip(points, points[1:]):
        travel_px.append(
            travel_px[-1]
            + math.hypot(
                (second[0] - first[0]) * float(width),
                (second[1] - first[1]) * float(height),
            )
        )
    out: list[list[tuple[float, float, float, float]]] = []
    for lane in range(lanes):
        lane_norm = (lane + 0.5) / lanes * 2.0 - 1.0
        lane_noise = math.sin((lane + 1) * 17.31 + seed * 0.137) * 0.5 + 0.5
        strand: list[tuple[float, float, float, float]] = []
        sample_offset = int(_value(stroke, "brush_sample_offset", 0) or 0)
        for index, (x, y) in enumerate(points):
            global_index = sample_offset + index
            prev_x, prev_y = points[max(0, index - 1)]
            next_x, next_y = points[min(point_count - 1, index + 1)]
            dx = next_x - prev_x
            dy = next_y - prev_y
            length = max(0.001, math.hypot(dx, dy))
            nx = -dy / length
            ny = dx / length
            progress = min(1.0, travel_px[index] / dryout_px)
            local_pressure = pressure[index]
            depleted_load = max(
                0.04, load[index] * (1.0 - depletion * progress)
            )
            local_load = depleted_load + (1.0 - depleted_load) * resaturation
            tilt_magnitude = (
                min(1.0, math.hypot(tilt_x[index], tilt_y[index]))
                if has_directional_tilt
                else min(1.0, abs(tilt[index] - 0.5) * 2.0)
            )
            fan = 1.0 + (rotation[index] - 0.5) * lane_norm * 0.42
            jitter = math.sin(global_index * 1.71 + lane * 2.13 + seed * 0.19) * base_width * 0.025
            offset = (
                lane_norm
                * base_width
                * 0.47
                * local_pressure
                * fan
                * (1.0 + tilt_magnitude * 0.38)
                + jitter
            )
            tilt_shift = base_width * 0.16
            strand.append(
                (
                    x + nx * offset + tilt_x[index] * tilt_shift,
                    y + ny * offset + tilt_y[index] * tilt_shift,
                    local_pressure,
                    local_load,
                )
            )
        # Authored strand-density stylization, not a measured bristle cutoff.
        if requested > 0 or lane_noise > 0.10:
            out.append(strand)
    return out


def paint_dynamic_basic_stroke(
    painter: QPainter,
    stroke: Any,
    width: int,
    height: int,
    color: QColor,
) -> bool:
    """Render basic strokes with per-point pressure and tablet tilt."""

    raw_points = list(_value(stroke, "points", []) or [])
    pressure_values = list(_value(stroke, "point_pressure", []) or [])
    tilt_x_values = list(_value(stroke, "point_tilt_x", []) or [])
    tilt_y_values = list(_value(stroke, "point_tilt_y", []) or [])
    if not raw_points or not (pressure_values or tilt_x_values or tilt_y_values):
        return False
    has_pressure_effect = any(abs(float(value) - 1.0) > 1e-4 for value in pressure_values)
    has_tilt_effect = any(abs(float(value)) > 1e-4 for value in (*tilt_x_values, *tilt_y_values))
    if not (has_pressure_effect or has_tilt_effect):
        return False
    points = [
        QPointF(float(point[0]) * width, float(point[1]) * height)
        for point in raw_points
    ]
    count = len(points)
    pressure = normalize_curve(pressure_values, count, 1.0)
    tilt_x = normalize_signed_curve(tilt_x_values, count)
    tilt_y = normalize_signed_curve(tilt_y_values, count)
    base_width = max(0.25, float(_value(stroke, "width_px", 4.0) or 4.0))
    closed = bool(_value(stroke, "closed_path", False))
    style = str(_value(stroke, "brush_style", "round") or "round").casefold()
    pairs = list(zip(range(count - 1), range(1, count)))
    if closed and count >= 3:
        pairs.append((count - 1, 0))
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    try:
        if count == 1:
            point_color = QColor(color)
            if style == "highlighter":
                point_color.setAlpha(min(point_color.alpha(), 110))
            pen = QPen(point_color, base_width * (0.18 + pressure[0] * 0.82))
            pen.setCapStyle(
                Qt.PenCapStyle.SquareCap
                if style in {"marker", "highlighter"}
                else Qt.PenCapStyle.RoundCap
            )
            painter.setPen(pen)
            painter.drawPoint(points[0])
            return True
        for first_index, second_index in pairs:
            local_pressure = (pressure[first_index] + pressure[second_index]) * 0.5
            tx = (tilt_x[first_index] + tilt_x[second_index]) * 0.5
            ty = (tilt_y[first_index] + tilt_y[second_index]) * 0.5
            tilt_magnitude = min(1.0, math.hypot(tx, ty))
            pen_width = (
                base_width
                * (0.18 + local_pressure * 0.82)
                * (1.0 + tilt_magnitude * 0.24)
            )
            segment_color = QColor(color)
            if style == "highlighter":
                segment_color.setAlpha(min(segment_color.alpha(), 110))
            pen = QPen(segment_color, max(0.25, pen_width))
            if style in {"marker", "highlighter"}:
                pen.setCapStyle(Qt.PenCapStyle.SquareCap)
                pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
            else:
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            if style == "dashed":
                pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            shift = base_width * 0.10
            painter.drawLine(
                points[first_index] + QPointF(tilt_x[first_index] * shift, tilt_y[first_index] * shift),
                points[second_index] + QPointF(tilt_x[second_index] * shift, tilt_y[second_index] * shift),
            )
    finally:
        painter.restore()
    return True


def _lane_color(base: QColor, lane: int, seed: int, alpha: int) -> QColor:
    r, g, b = base.redF(), base.greenF(), base.blueF()
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    noise = math.sin((lane + 1) * 12.17 + seed * 0.71) * 0.5 + 0.5
    h = (h + (noise - 0.5) * 0.035) % 1.0
    s = max(0.0, min(1.0, s * (0.88 + noise * 0.22)))
    v = max(0.0, min(1.0, v * (0.68 + noise * 0.54)))
    rr, gg, bb = colorsys.hsv_to_rgb(h, s, v)
    return QColor.fromRgbF(rr, gg, bb, max(0.0, min(1.0, alpha / 255.0)))


def stipple_dabs(
    stroke: Any,
    *,
    width: int,
    height: int,
) -> list[tuple[float, float, float, float, float]]:
    """Return compact, irregular paint deposits without translucent stamp rings."""

    raw_points = list(_value(stroke, "points", []) or [])
    if not raw_points:
        return []
    points = [
        (float(point[0]) * width, float(point[1]) * height)
        for point in raw_points
    ]
    center_x = sum(point[0] for point in points) / len(points)
    center_y = sum(point[1] for point in points) / len(points)
    if len(points) >= 2:
        angle = math.atan2(
            points[-1][1] - points[0][1],
            points[-1][0] - points[0][0],
        )
    else:
        angle = 0.0
    normal_x = -math.sin(angle)
    normal_y = math.cos(angle)
    tangent_x = math.cos(angle)
    tangent_y = math.sin(angle)
    base_width = max(1.0, float(_value(stroke, "width_px", 4.0) or 4.0))
    sample_offset = int(_value(stroke, "brush_sample_offset", 0) or 0)
    seed = int(_value(stroke, "brush_seed", 0) or 0) + sample_offset * 7919
    dabs: list[tuple[float, float, float, float, float]] = []
    count = max(3, min(7, int(round(base_width * 0.18))))
    for index in range(count):
        noise_a = math.sin((index + 1) * 19.73 + seed * 0.173)
        noise_b = math.sin((index + 1) * 31.17 + seed * 0.097)
        along = noise_a * base_width * 0.19
        across = noise_b * base_width * 0.31
        radius_x = base_width * (0.075 + (noise_b * 0.5 + 0.5) * 0.055)
        radius_y = base_width * (0.055 + (noise_a * 0.5 + 0.5) * 0.045)
        dabs.append(
            (
                center_x + tangent_x * along + normal_x * across,
                center_y + tangent_y * along + normal_y * across,
                max(1.0, radius_x),
                max(0.85, radius_y),
                angle + noise_b * 0.42,
            )
        )
    return dabs


def _paint_stipple_oil(
    painter: QPainter,
    stroke: Any,
    width: int,
    height: int,
    color: QColor,
) -> None:
    seed = int(_value(stroke, "brush_seed", 0) or 0)
    material_enabled = bool(_value(stroke, "material_enabled", False))
    for index, (x, y, radius_x, radius_y, angle) in enumerate(
        stipple_dabs(stroke, width=width, height=height)
    ):
        dab_color = _lane_color(color, index, seed, color.alpha())
        if material_enabled:
            dab_color.setRed(int(dab_color.red() * 0.32 + color.red() * 0.68))
            dab_color.setGreen(int(dab_color.green() * 0.32 + color.green() * 0.68))
            dab_color.setBlue(int(dab_color.blue() * 0.32 + color.blue() * 0.68))
            dab_color.setAlpha(color.alpha())
        else:
            dab_color.setAlpha(max(0, int(color.alpha() * 0.78)))
        half_length = max(0.5, radius_x * 0.46)
        dx = math.cos(angle) * half_length
        dy = math.sin(angle) * half_length
        pen = QPen(dab_color, max(1.0, radius_y * 2.0))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(x - dx, y - dy), QPointF(x + dx, y + dy))


def _paint_palette_knife_oil(
    painter: QPainter,
    stroke: Any,
    width: int,
    height: int,
    color: QColor,
) -> None:
    points = [
        QPointF(float(point[0]) * width, float(point[1]) * height)
        for point in list(_value(stroke, "points", []) or [])
    ]
    if not points:
        return
    base_width = max(1.0, float(_value(stroke, "width_px", 4.0) or 4.0))
    seed = int(_value(stroke, "brush_seed", 0) or 0)
    material_enabled = bool(_value(stroke, "material_enabled", False))
    base = QColor(color)
    base.setAlpha(color.alpha() if material_enabled else max(0, int(color.alpha() * 0.88)))
    base_pen = QPen(base, base_width * 0.96)
    base_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    base_pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    painter.setPen(base_pen)
    if len(points) == 1:
        painter.drawPoint(points[0])
    else:
        painter.drawPolyline(points)

    # Short broken deposits remove the synthetic parallel-line look while
    # preserving the broad, compressed plateau of a real palette knife.
    sample_offset = int(_value(stroke, "brush_sample_offset", 0) or 0)
    for segment_index, (first, second) in enumerate(zip(points, points[1:])):
        dx = second.x() - first.x()
        dy = second.y() - first.y()
        length = max(0.001, math.hypot(dx, dy))
        tx, ty = dx / length, dy / length
        nx, ny = -ty, tx
        deposits = max(2, int(math.ceil(length / max(6.0, base_width * 0.22))))
        for deposit_index in range(deposits):
            key = (sample_offset + segment_index) * 131 + deposit_index
            noise_a = math.sin((key + 1) * 17.13 + seed * 0.113)
            noise_b = math.sin((key + 1) * 29.71 + seed * 0.071)
            t = (deposit_index + 0.5 + noise_a * 0.24) / deposits
            cx = first.x() + dx * t + nx * noise_b * base_width * 0.31
            cy = first.y() + dy * t + ny * noise_b * base_width * 0.31
            half = base_width * (0.07 + (noise_a * 0.5 + 0.5) * 0.13)
            detail = _lane_color(color, key, seed, color.alpha())
            detail.setAlpha(
                max(0, int(color.alpha() * (0.82 if material_enabled else 0.48)))
            )
            pen = QPen(detail, max(0.8, base_width * (0.025 + abs(noise_b) * 0.045)))
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            painter.setPen(pen)
            painter.drawLine(
                QPointF(cx - tx * half, cy - ty * half),
                QPointF(cx + tx * half, cy + ty * half),
            )


def paint_bristle_v2(
    painter: QPainter,
    stroke: Any,
    width: int,
    height: int,
    color: QColor,
) -> bool:
    if not stroke_uses_bristle_v2(stroke):
        return False
    style = str(_value(stroke, "brush_style", "") or "").casefold()
    if style == "stipple_oil":
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            _paint_stipple_oil(painter, stroke, width, height, color)
        finally:
            painter.restore()
        return True
    if style in {"palette_knife", "knife_scrape_oil"}:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            _paint_palette_knife_oil(painter, stroke, width, height, color)
        finally:
            painter.restore()
        return True
    lanes = bristle_lane_paths(stroke, width=width, height=height)
    if not lanes:
        return False
    base_width = max(0.25, float(_value(stroke, "width_px", 4.0) or 4.0))
    seed = int(_value(stroke, "brush_seed", 0) or 0)
    lane_width = max(
        0.65,
        base_width
        / max(5, len(lanes))
        * (1.16 if bool(_value(stroke, "material_enabled", False)) else 0.92),
    )
    material_enabled = bool(_value(stroke, "material_enabled", False))
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
        if material_enabled:
            body_alpha_scale = max(
                body_alpha_scale,
                1.0
                if style in {"impasto_oil", "loaded_oil"}
                else 0.92
                if style in {"palette_knife", "knife_scrape_oil", "bristle_oil"}
                else 0.82,
            )
        body.setAlpha(max(0, min(255, int(color.alpha() * body_alpha_scale))))
        body_pen = QPen(
            body,
            max(
                1.0,
                base_width
                * (
                    0.62
                    if material_enabled and style in {"impasto_oil", "loaded_oil"}
                    else 0.76
                ),
            ),
        )
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
            if material_enabled:
                lane_color.setRed(int(lane_color.red() * 0.38 + color.red() * 0.62))
                lane_color.setGreen(int(lane_color.green() * 0.38 + color.green() * 0.62))
                lane_color.setBlue(int(lane_color.blue() * 0.38 + color.blue() * 0.62))
            for index in range(len(strand) - 1):
                x1, y1, pressure, load = strand[index]
                x2, y2, next_pressure, next_load = strand[index + 1]
                alpha = int(
                    color.alpha()
                    * (0.34 + 0.66 * min(load, next_load))
                    * (0.48 + 0.52 * min(pressure, next_pressure))
                )
                if material_enabled:
                    alpha = max(alpha, int(color.alpha() * 0.90))
                segment_color = QColor(lane_color)
                segment_color.setAlpha(max(0, min(255, alpha)))
                pen = QPen(
                    segment_color,
                    max(0.55, lane_width * (0.55 + min(pressure, next_pressure))),
                )
                pen.setCapStyle(Qt.PenCapStyle.FlatCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
                if not material_enabled and lane_index % 4 == 0:
                    highlight = QColor(255, 246, 220, max(0, int(alpha * 0.20)))
                    highlight_pen = QPen(highlight, max(0.35, pen.widthF() * 0.24))
                    highlight_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
                    painter.setPen(highlight_pen)
                    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    finally:
        painter.restore()
    return True
