"""Pure AR/PBR viewport gizmo geometry and track mutation helpers."""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def track_center_norm(track: dict, runtime_point: tuple[float, float] | None = None) -> tuple[float, float]:
    if runtime_point is not None:
        return (clamp01(runtime_point[0]), clamp01(runtime_point[1]))
    placement = track.get("placement") if isinstance(track, dict) else None
    if isinstance(placement, dict):
        point = placement.get("image_point")
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            try:
                return (clamp01(float(point[0])), clamp01(float(point[1])))
            except Exception:
                pass
    transform = track.get("transform") if isinstance(track, dict) else None
    position = transform.get("position") if isinstance(transform, dict) else None
    if isinstance(position, (list, tuple)) and len(position) >= 2:
        try:
            return (clamp01(0.5 + float(position[0]) / 4.0), clamp01(0.5 - float(position[1]) / 4.0))
        except Exception:
            pass
    return (0.5, 0.62)


def set_track_center_norm(track: dict, x_norm: float, y_norm: float) -> None:
    x = clamp01(x_norm)
    y = clamp01(y_norm)
    placement = track.setdefault("placement", {})
    mode = str(placement.get("mode") or "manual").casefold() if isinstance(placement, dict) else "manual"
    if isinstance(placement, dict):
        if mode not in {"road_plane_anchor", "plane_anchor", "screen_plane", "scene_anchor"}:
            placement["mode"] = "manual"
        placement["coordinate_space"] = "normalized"
        placement["image_point"] = [x, y]
        if mode in {"road_plane_anchor", "plane_anchor", "screen_plane", "scene_anchor"}:
            placement.pop("anchor_world", None)
    transform = track.setdefault("transform", {})
    if mode in {"road_plane_anchor", "plane_anchor", "screen_plane", "scene_anchor"}:
        return
    position = transform.get("position") if isinstance(transform, dict) else None
    z = 0.0
    if isinstance(position, (list, tuple)) and len(position) >= 3:
        try:
            z = float(position[2])
        except Exception:
            z = 0.0
    try:
        from app.ar_pbr.project_tracks import transform_position_from_frame_point

        transform["position"] = transform_position_from_frame_point(x, y, z=z)
    except Exception:
        transform["position"] = [(x - 0.5) * 4.0, (0.5 - y) * 4.0, z]


def track_uniform_scale(track: dict) -> float:
    transform = track.get("transform") if isinstance(track, dict) else None
    scale = transform.get("scale") if isinstance(transform, dict) else None
    if isinstance(scale, (list, tuple)) and scale:
        values: list[float] = []
        for value in scale[:3]:
            try:
                values.append(max(0.0001, float(value)))
            except Exception:
                pass
        if values:
            return sum(values) / len(values)
    return 1.0


def set_track_uniform_scale(track: dict, value: float) -> None:
    scale = max(0.05, min(8.0, float(value)))
    transform = track.setdefault("transform", {})
    transform["scale"] = [scale, scale, scale]


def track_scale_values(track: dict) -> list[float]:
    transform = track.get("transform") if isinstance(track, dict) else None
    scale = transform.get("scale") if isinstance(transform, dict) else None
    values: list[float] = []
    if isinstance(scale, (list, tuple)):
        for value in scale[:3]:
            try:
                values.append(max(0.0001, float(value)))
            except Exception:
                values.append(1.0)
    while len(values) < 3:
        values.append(values[-1] if values else 1.0)
    return values[:3]


def set_track_axis_scale(track: dict, axis: int, value: float) -> None:
    axis = max(0, min(2, int(axis)))
    values = track_scale_values(track)
    values[axis] = max(0.05, min(8.0, float(value)))
    transform = track.setdefault("transform", {})
    transform["scale"] = values


def track_position_z(track: dict) -> float:
    transform = track.get("transform") if isinstance(track, dict) else None
    position = transform.get("position") if isinstance(transform, dict) else None
    if isinstance(position, (list, tuple)) and len(position) >= 3:
        try:
            return float(position[2])
        except Exception:
            return 0.0
    return 0.0


def set_track_position_z(track: dict, value: float) -> None:
    transform = track.setdefault("transform", {})
    position = list(transform.get("position") or [0.0, 0.0, 0.0])
    while len(position) < 3:
        position.append(0.0)
    position[2] = max(-8.0, min(8.0, float(value)))
    transform["position"] = position[:3]


def track_rotation_value(track: dict, axis: int) -> float:
    axis = max(0, min(2, int(axis)))
    transform = track.get("transform") if isinstance(track, dict) else None
    rotation = transform.get("rotation") if isinstance(transform, dict) else None
    if isinstance(rotation, (list, tuple)) and len(rotation) > axis:
        try:
            return float(rotation[axis])
        except Exception:
            return 0.0
    return 0.0


def set_track_rotation_value(track: dict, axis: int, value: float) -> None:
    axis = max(0, min(2, int(axis)))
    transform = track.setdefault("transform", {})
    rotation = list(transform.get("rotation") or [0.0, 0.0, 0.0])
    while len(rotation) < 3:
        rotation.append(0.0)
    rotation[axis] = float(value) % 360.0
    transform["rotation"] = rotation[:3]


def track_rotation_values(track: dict) -> list[float]:
    return [track_rotation_value(track, 0), track_rotation_value(track, 1), track_rotation_value(track, 2)]


def rotate_vec3(vec: tuple[float, float, float], rotation_deg: Sequence[float]) -> tuple[float, float, float]:
    x, y, z = float(vec[0]), float(vec[1]), float(vec[2])
    try:
        rx, ry, rz = [math.radians(float(v)) for v in rotation_deg[:3]]
    except Exception:
        rx = ry = rz = 0.0

    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)

    y, z = y * cx - z * sx, y * sx + z * cx
    x, z = x * cy + z * sy, -x * sy + z * cy
    x, y = x * cz - y * sz, x * sz + y * cz
    return (x, y, z)


def project_gizmo_point3(vec: tuple[float, float, float]) -> tuple[float, float]:
    x, y, z = float(vec[0]), float(vec[1]), float(vec[2])
    perspective = 1.0 / max(0.35, 1.45 - z * 0.34)
    sx = (x - z * 0.38) * perspective
    sy = (-y + z * 0.28) * perspective
    return (sx, sy)


def project_gizmo_vec3(vec: tuple[float, float, float]) -> tuple[float, float]:
    sx, sy = project_gizmo_point3(vec)
    length = math.hypot(sx, sy)
    if length < 1e-4:
        return (0.0, -1.0)
    return (sx / length, sy / length)


def project_gizmo_axis(
    axis: tuple[float, float, float],
    rotation_deg: Sequence[float],
) -> tuple[tuple[float, float], float]:
    rotated = rotate_vec3(axis, rotation_deg)
    return project_gizmo_vec3(rotated), float(rotated[2])


def gizmo_ring_points(
    axis_name: str,
    rotation_deg: Sequence[float],
    cx: float,
    cy: float,
    radius: float,
    *,
    segments: int = 72,
) -> list[tuple[float, float]]:
    axis_name = str(axis_name or "").casefold()
    points: list[tuple[float, float]] = []
    count = max(12, int(segments))
    for index in range(count):
        t = math.tau * float(index) / float(count)
        ct, st = math.cos(t), math.sin(t)
        if axis_name == "x":
            vec3 = (0.0, ct, st)
        elif axis_name == "y":
            vec3 = (ct, 0.0, st)
        else:
            vec3 = (ct, st, 0.0)
        rotated = rotate_vec3(vec3, rotation_deg)
        sx, sy = project_gizmo_point3(rotated)
        points.append((float(cx) + sx * float(radius), float(cy) + sy * float(radius)))
    return points


def gizmo_geometry(
    track: dict,
    canvas_w: int,
    canvas_h: int,
    *,
    center_norm: tuple[float, float] | None = None,
) -> dict:
    cx_norm, cy_norm = center_norm if center_norm is not None else track_center_norm(track)
    cx = clamp01(cx_norm) * max(1, canvas_w)
    cy = clamp01(cy_norm) * max(1, canvas_h)
    scale = track_uniform_scale(track)
    base = min(max(1, canvas_w), max(1, canvas_h))
    gizmo_len = max(72.0, min(base * 0.2, 150.0))
    gizmo_len *= max(0.82, min(1.18, math.sqrt(max(0.25, scale / 1.35))))
    ring_radius = max(46.0, gizmo_len * 0.62)
    rotation = track_rotation_values(track)
    axis_vectors = {
        "x": (1.0, 0.0, 0.0),
        "y": (0.0, 1.0, 0.0),
        "z": (0.0, 0.0, 1.0),
    }
    axis_rows: dict[str, dict[str, Any]] = {}
    for name, axis in axis_vectors.items():
        (vx, vy), depth = project_gizmo_axis(axis, rotation)
        axis_rows[name] = {
            "vec": (vx, vy),
            "end": (cx + vx * gizmo_len, cy + vy * gizmo_len),
            "scale": (cx + vx * gizmo_len * 0.58, cy + vy * gizmo_len * 0.58),
            "depth": depth,
        }
    return {
        "cx": cx,
        "cy": cy,
        "center_radius": 14.0,
        "length": gizmo_len,
        "ring_radius": ring_radius,
        "axes": axis_rows,
        "rings": {name: gizmo_ring_points(name, rotation, cx, cy, ring_radius) for name in ("x", "y", "z")},
        "rotation": rotation,
        "uniform_scale": (cx + gizmo_len * 0.34, cy + gizmo_len * 0.34),
    }


def distance_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    abx = bx - ax
    aby = by - ay
    denom = abx * abx + aby * aby
    if denom <= 1e-6:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / denom))
    qx = ax + abx * t
    qy = ay + aby * t
    return math.hypot(px - qx, py - qy)


def ellipse_ring_hit(px: float, py: float, cx: float, cy: float, rx: float, ry: float, tol_px: float) -> bool:
    rx = max(1.0, float(rx))
    ry = max(1.0, float(ry))
    value = ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2
    tolerance = max(tol_px / rx, tol_px / ry) * 2.2
    return abs(value - 1.0) <= tolerance


def distance_to_polyline(px: float, py: float, points: list[tuple[float, float]]) -> float:
    if not points:
        return 1_000_000.0
    best = 1_000_000.0
    closed = list(points) + [points[0]]
    for a, b in zip(closed, closed[1:]):
        try:
            best = min(best, distance_to_segment(float(px), float(py), float(a[0]), float(a[1]), float(b[0]), float(b[1])))
        except Exception:
            continue
    return best


def gizmo_hit_test(
    active_tracks: list[dict],
    visible_track_id: str,
    nx: float,
    ny: float,
    canvas_w: int,
    canvas_h: int,
    *,
    center_lookup: Callable[[dict], tuple[float, float]] | None = None,
) -> tuple[dict | None, str]:
    px = float(nx) * max(1, canvas_w)
    py = float(ny) * max(1, canvas_h)
    visible_id = str(visible_track_id or "")
    selected = next((track for track in active_tracks if str(track.get("id") or "") == visible_id), None)

    def _geometry(track: dict) -> dict:
        center = center_lookup(track) if callable(center_lookup) else None
        return gizmo_geometry(track, canvas_w, canvas_h, center_norm=center)

    if selected is not None:
        geom = _geometry(selected)
        cx = float(geom["cx"])
        cy = float(geom["cy"])
        center_radius = float(geom["center_radius"])
        usx, usy = geom.get("uniform_scale", (cx, cy))
        if math.hypot(px - float(usx), py - float(usy)) <= 13.0:
            return selected, "scale_uniform"
        axes = geom.get("axes") if isinstance(geom, dict) else {}
        if isinstance(axes, dict):
            for axis_name in ("x", "y", "z"):
                row = axes.get(axis_name)
                if not isinstance(row, dict):
                    continue
                sx, sy = row.get("scale", (cx, cy))
                if math.hypot(px - float(sx), py - float(sy)) <= 12.0:
                    return selected, f"scale_{axis_name}"
            for axis_name in ("x", "y", "z"):
                row = axes.get(axis_name)
                if not isinstance(row, dict):
                    continue
                ex, ey = row.get("end", (cx, cy))
                if distance_to_segment(px, py, cx, cy, float(ex), float(ey)) <= 10.0:
                    return selected, f"move_{axis_name}"
        if math.hypot(px - cx, py - cy) <= center_radius:
            return selected, "move_xy"
        rings = geom.get("rings") if isinstance(geom, dict) else {}
        if isinstance(rings, dict):
            nearest_ring: tuple[float, str] | None = None
            for axis_name in ("x", "y", "z"):
                points = rings.get(axis_name)
                if not isinstance(points, list):
                    continue
                distance = distance_to_polyline(px, py, points)
                if nearest_ring is None or distance < nearest_ring[0]:
                    nearest_ring = (distance, axis_name)
            if nearest_ring is not None and nearest_ring[0] <= 10.5:
                return selected, f"rotate_{nearest_ring[1]}"
        ring_radius = float(geom["ring_radius"])
        if math.hypot(px - cx, py - cy) <= max(24.0, ring_radius * 0.36):
            return selected, "move_xy"
    for track in reversed(active_tracks):
        geom = _geometry(track)
        cx = float(geom["cx"])
        cy = float(geom["cy"])
        ring_radius = float(geom["ring_radius"])
        if math.hypot(px - cx, py - cy) <= max(28.0, ring_radius * 0.42):
            return track, "move_xy"
    return None, ""


def axis_index(axis_name: str) -> int:
    return {"x": 0, "y": 1, "z": 2}.get(str(axis_name or "").casefold(), 0)


def track_lighting_dict(track: dict) -> dict:
    render = track.setdefault("render", {})
    if not isinstance(render, dict):
        render = {}
        track["render"] = render
    lighting = render.setdefault("lighting", {})
    if not isinstance(lighting, dict):
        lighting = {}
        render["lighting"] = lighting
    return lighting


def begin_depth_interaction_cue(track: dict, restore: dict[str, dict]) -> None:
    if not isinstance(track, dict):
        return
    track_id = str(track.get("id") or "")
    if not track_id:
        return
    lighting = track_lighting_dict(track)
    keys = (
        "depth_edge_glow_enabled",
        "depth_edge_glow_strength",
        "depth_edge_glow_radius_px",
        "depth_edge_glow_color",
    )
    if track_id not in restore:
        restore[track_id] = {
            "occlusion_present": "occlusion" in track,
            "occlusion": bool(track.get("occlusion", False)),
            "lighting": {key: {"present": key in lighting, "value": lighting.get(key)} for key in keys},
        }
    track["occlusion"] = True
    lighting["depth_edge_glow_enabled"] = True
    try:
        current_strength = float(lighting.get("depth_edge_glow_strength", 0.0) or 0.0)
    except Exception:
        current_strength = 0.0
    try:
        current_radius = float(lighting.get("depth_edge_glow_radius_px", 0.0) or 0.0)
    except Exception:
        current_radius = 0.0
    lighting["depth_edge_glow_strength"] = max(current_strength, 0.65)
    lighting["depth_edge_glow_radius_px"] = max(current_radius, 7.0)
    lighting["depth_edge_glow_color"] = list(lighting.get("depth_edge_glow_color") or [0.35, 0.85, 1.0])


def restore_depth_interaction_cue(track: dict, saved: dict) -> None:
    if not isinstance(track, dict) or not isinstance(saved, dict):
        return
    if bool(saved.get("occlusion_present")):
        track["occlusion"] = bool(saved.get("occlusion"))
    else:
        track.pop("occlusion", None)
    lighting = track_lighting_dict(track)
    for key, row in dict(saved.get("lighting") or {}).items():
        if not isinstance(row, dict):
            continue
        if bool(row.get("present")):
            lighting[key] = row.get("value")
        else:
            lighting.pop(key, None)
