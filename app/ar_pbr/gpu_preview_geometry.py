"""Geometry helpers for AR/PBR GPU preview packet building."""
from __future__ import annotations

import math
from typing import Any

from app.ar_pbr.gpu_preview_math import _extend_ndc_vertex, _float, _projected_bounds

def _ellipse_vertices(
    *,
    center_x: float,
    center_y: float,
    radius_x: float,
    radius_y: float,
    width: int,
    height: int,
    rgba: tuple[float, float, float, float],
    segments: int = 20,
) -> list[float]:
    if radius_x <= 0.5 or radius_y <= 0.5:
        return []
    out: list[float] = []
    center = (center_x, center_y, 0.0)
    segments = max(8, min(40, int(segments)))
    for idx in range(segments):
        a0 = (idx / segments) * math.tau
        a1 = ((idx + 1) / segments) * math.tau
        p0 = center
        p1 = (center_x + math.cos(a0) * radius_x, center_y + math.sin(a0) * radius_y, 0.0)
        p2 = (center_x + math.cos(a1) * radius_x, center_y + math.sin(a1) * radius_y, 0.0)
        for point in (p0, p1, p2):
            _extend_ndc_vertex(out, point, width, height, rgba)
    return out

def _rect_vertices(
    *,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    width: int,
    height: int,
    rgba: tuple[float, float, float, float],
) -> list[float]:
    if x1 <= x0 + 0.5 or y1 <= y0 + 0.5:
        return []
    out: list[float] = []
    points = [
        (x0, y0, 0.0),
        (x1, y0, 0.0),
        (x1, y1, 0.0),
        (x0, y0, 0.0),
        (x1, y1, 0.0),
        (x0, y1, 0.0),
    ]
    for point in points:
        _extend_ndc_vertex(out, point, width, height, rgba)
    return out

def _convex_hull_2d(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    clean = sorted({(round(float(x), 3), round(float(y), 3)) for x, y in points})
    if len(clean) <= 2:
        return clean

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for point in clean:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(clean):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]

def _polygon_fan_vertices(
    points: list[tuple[float, float]],
    *,
    width: int,
    height: int,
    rgba: tuple[float, float, float, float],
) -> list[float]:
    if len(points) < 3 or rgba[3] <= 0.001:
        return []
    cx = sum(float(p[0]) for p in points) / len(points)
    cy = sum(float(p[1]) for p in points) / len(points)
    out: list[float] = []
    for idx, point in enumerate(points):
        next_point = points[(idx + 1) % len(points)]
        for px, py in ((cx, cy), point, next_point):
            _extend_ndc_vertex(out, (px, py, 0.0), width, height, rgba)
    return out

def _mesh_contact_shadow_vertices(
    projected: list[tuple[float, float, float]],
    *,
    x0: float,
    y0: float,
    y1: float,
    span_x: float,
    span_y: float,
    width: int,
    height: int,
    light_dir: tuple[float, float, float],
    alpha: float,
    softness: float = 0.55,
    matte_alpha: float = 0.0,
) -> list[float]:
    soft = max(0.0, min(1.0, float(softness)))
    matte = max(0.0, min(1.0, float(matte_alpha)))
    if len(projected) < 3 or (alpha <= 0.001 and matte <= 0.001):
        return []
    base_y = min(float(height) - 1.0, y1 + max(1.0, span_y * 0.035))
    light_x = max(-1.0, min(1.0, float(light_dir[0])))
    light_y = max(0.05, min(1.0, abs(float(light_dir[1]))))
    candidates: list[tuple[float, float]] = []
    lower_cutoff = y0 + span_y * 0.35
    for px, py, _pz in projected:
        if py < lower_cutoff:
            continue
        fall = max(0.0, y1 - float(py))
        sx = float(px) - light_x * (fall * 0.20 + span_x * 0.035)
        sy = base_y + fall * (0.035 + light_y * 0.030)
        candidates.append((
            max(-width * 0.25, min(width * 1.25, sx)),
            max(0.0, min(height - 1.0, sy)),
        ))
    if len(candidates) < 3:
        return []
    hull = _convex_hull_2d(candidates)
    if len(hull) < 3:
        return []
    out = _polygon_fan_vertices(
        hull,
        width=width,
        height=height,
        rgba=(0.0, 0.0, 0.0, min(0.26, max(alpha * (0.50 - soft * 0.12), matte * 0.10))),
    )
    center_x = sum(x for x, _y in hull) / len(hull)
    center_y = sum(y for _x, y in hull) / len(hull)
    for radius_scale, y_scale, alpha_scale, segments in (
        (0.26 + soft * 0.12, 0.045 + soft * 0.030, 0.42, 24),
        (0.42 + soft * 0.24, 0.075 + soft * 0.055, 0.22, 32),
    ):
        out.extend(_ellipse_vertices(
            center_x=center_x,
            center_y=center_y,
            radius_x=max(2.0, span_x * radius_scale),
            radius_y=max(1.5, span_y * y_scale),
            width=width,
            height=height,
            rgba=(0.0, 0.0, 0.0, min(0.18, max(alpha * alpha_scale, matte * 0.05))),
            segments=segments,
        ))
    return out

def _contact_shadow_vertices(
    *,
    x0: float,
    y1: float,
    span_x: float,
    span_y: float,
    width: int,
    height: int,
    light_dir: tuple[float, float, float],
    alpha: float,
    softness: float = 0.55,
    matte_alpha: float = 0.0,
) -> list[float]:
    soft = max(0.0, min(1.0, float(softness)))
    matte = max(0.0, min(1.0, float(matte_alpha)))
    if alpha <= 0.001 and matte <= 0.001:
        return []
    # This is still a packet catcher, not a real shadow map. Layering several
    # ellipses gives the GL preview/export path a softer contact-shadow falloff
    # without adding a new renderer surface.
    offset_x = max(-span_x * 0.18, min(span_x * 0.18, -float(light_dir[0]) * span_x * 0.12))
    offset_y = max(0.0, min(span_y * 0.12, abs(float(light_dir[1])) * span_y * 0.045))
    center_x = x0 + span_x * 0.5 + offset_x
    center_y = min(float(height) - 1.0, y1 + span_y * 0.035 + offset_y)
    layers = (
        (0.24 + soft * 0.10, 0.038 + soft * 0.028, min(0.30, max(alpha * 0.86, matte * 0.08)), 18),
        (0.42 + soft * 0.18, 0.075 + soft * 0.060, min(0.18, max(alpha * 0.42, matte * 0.05)), 26),
        (0.62 + soft * 0.32, 0.120 + soft * 0.115, min(0.10, max(alpha * 0.18, matte * 0.03)), 34),
    )
    out: list[float] = []
    for rx, ry, layer_alpha, segments in layers:
        out.extend(_ellipse_vertices(
            center_x=center_x,
            center_y=center_y,
            radius_x=max(2.0, span_x * rx),
            radius_y=max(1.5, span_y * ry),
            width=width,
            height=height,
            rgba=(0.0, 0.0, 0.0, layer_alpha),
            segments=segments,
        ))
    return out

def _mesh_reflection_catcher_vertices(
    projected: list[tuple[float, float, float]],
    *,
    y1: float,
    span_y: float,
    width: int,
    height: int,
    rgba: tuple[float, float, float, float],
    roughness: float = 0.45,
    opacity: float = 0.35,
    softness: float = 0.45,
    matte_alpha: float = 0.0,
    contact_strength: float = 0.32,
) -> list[float]:
    if len(projected) < 3 or (rgba[3] <= 0.001 and matte_alpha <= 0.001):
        return []
    rough = max(0.04, min(1.0, float(roughness)))
    soft = max(0.0, min(1.0, float(softness)))
    opacity = max(0.0, min(1.0, float(opacity)))
    matte = max(0.0, min(1.0, float(matte_alpha)))
    contact = max(0.0, min(1.0, float(contact_strength)))
    out: list[float] = []
    layers = (
        (0.20 + rough * 0.08, 0.00, 0.68 + contact * 0.22),
        (0.34 + rough * 0.16 + soft * 0.06, span_y * (0.018 + soft * 0.020), 0.34),
        (0.50 + rough * 0.26 + soft * 0.12, span_y * (0.048 + soft * 0.050), 0.15),
    )
    for mirror_scale, y_offset, alpha_scale in layers:
        mirrored: list[tuple[float, float]] = []
        for px, py, _pz in projected:
            dy = max(0.0, y1 - float(py))
            if dy > span_y * 0.88:
                continue
            mx = max(0.0, min(width - 1.0, float(px)))
            my = max(0.0, min(height - 1.0, y1 + y_offset + dy * mirror_scale))
            mirrored.append((mx, my))
        hull = _convex_hull_2d(mirrored)
        if len(hull) < 3:
            continue
        out.extend(_polygon_fan_vertices(
            hull,
            width=width,
            height=height,
            rgba=(
                rgba[0] * (1.0 - rough * 0.20),
                rgba[1] * (1.0 - rough * 0.20),
                rgba[2] * (1.0 - rough * 0.20),
                min(0.20, max(rgba[3] * opacity * alpha_scale, matte * 0.035)),
            ),
        ))
    return out

def _reflection_catcher_vertices(
    *,
    x0: float,
    y1: float,
    span_x: float,
    span_y: float,
    width: int,
    height: int,
    rgba: tuple[float, float, float, float],
    roughness: float = 0.45,
    opacity: float = 0.35,
    softness: float = 0.45,
    matte_alpha: float = 0.0,
    contact_strength: float = 0.32,
    contact_falloff: float = 0.58,
) -> list[float]:
    if rgba[3] <= 0.001 and matte_alpha <= 0.001:
        return []
    rough = max(0.02, min(1.0, float(roughness)))
    soft = max(0.0, min(1.0, float(softness)))
    opacity = max(0.0, min(1.0, float(opacity)))
    matte = max(0.0, min(1.0, float(matte_alpha)))
    contact = max(0.0, min(1.0, float(contact_strength)))
    falloff = max(0.05, min(1.0, float(contact_falloff)))
    reach = 0.20 + rough * 0.24 + soft * 0.14
    out: list[float] = []
    out.extend(_rect_vertices(
        x0=max(0.0, x0 + span_x * 0.08),
        y0=max(0.0, y1),
        x1=min(float(width) - 1.0, x0 + span_x * 0.92),
        y1=min(float(height) - 1.0, y1 + span_y * (0.10 + falloff * 0.10)),
        width=width,
        height=height,
        rgba=(rgba[0], rgba[1], rgba[2], min(0.18, max(rgba[3] * opacity * (0.48 + contact * 0.42), matte * 0.035))),
    ))
    out.extend(_rect_vertices(
        x0=max(0.0, x0 + span_x * 0.18),
        y0=max(0.0, y1 + span_y * (0.10 + falloff * 0.06)),
        x1=min(float(width) - 1.0, x0 + span_x * 0.82),
        y1=min(float(height) - 1.0, y1 + span_y * (0.18 + reach * 0.36)),
        width=width,
        height=height,
        rgba=(rgba[0] * 0.75, rgba[1] * 0.75, rgba[2] * 0.75, min(0.10, max(rgba[3] * opacity * 0.26, matte * 0.025))),
    ))
    out.extend(_rect_vertices(
        x0=max(0.0, x0 + span_x * 0.28),
        y0=max(0.0, y1 + span_y * (0.20 + reach * 0.20)),
        x1=min(float(width) - 1.0, x0 + span_x * 0.72),
        y1=min(float(height) - 1.0, y1 + span_y * (0.28 + reach * 0.56)),
        width=width,
        height=height,
        rgba=(rgba[0] * 0.52, rgba[1] * 0.52, rgba[2] * 0.52, min(0.055, max(rgba[3] * opacity * 0.12, matte * 0.018))),
    ))
    return out
