"""Road-plane placement helpers for AR/PBR tracks."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


def _as_vec2(value: Any, default: tuple[float, float]) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return default
    try:
        return (float(value[0]), float(value[1]))
    except Exception:
        return default


def _as_vec3(value: Any, default: tuple[float, float, float]) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return default
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return default


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _normalize(v: tuple[float, float, float]) -> tuple[float, float, float]:
    import math

    length = math.sqrt(_dot(v, v))
    if length <= 1e-8:
        return (0.0, 0.0, 1.0)
    return (v[0] / length, v[1] / length, v[2] / length)


def _intrinsics_for_frame(
    camera_solution: Mapping[str, Any],
    frame_size: tuple[int, int],
) -> tuple[float, float, float, float]:
    width, height = max(1, int(frame_size[0])), max(1, int(frame_size[1]))
    intrinsics = camera_solution.get("intrinsics") if isinstance(camera_solution, Mapping) else {}
    source_size = camera_solution.get("frame_size") if isinstance(camera_solution, Mapping) else None
    src_w = float(source_size[0]) if isinstance(source_size, (list, tuple)) and len(source_size) >= 1 else float(width)
    src_h = float(source_size[1]) if isinstance(source_size, (list, tuple)) and len(source_size) >= 2 else float(height)
    sx = float(width) / max(src_w, 1.0)
    sy = float(height) / max(src_h, 1.0)
    if isinstance(intrinsics, Mapping):
        fx = float(intrinsics.get("fx", width)) * sx
        fy = float(intrinsics.get("fy", height)) * sy
        cx = float(intrinsics.get("cx", width * 0.5)) * sx
        cy = float(intrinsics.get("cy", height * 0.5)) * sy
    else:
        fx = fy = float(max(width, height))
        cx = float(width) * 0.5
        cy = float(height) * 0.5
    return fx, fy, cx, cy


def _image_point_for_frame(
    image_point: Any,
    *,
    frame_size: tuple[int, int],
    camera_solution: Mapping[str, Any],
    coordinate_space: str,
) -> tuple[float, float]:
    width, height = max(1, int(frame_size[0])), max(1, int(frame_size[1]))
    x, y = _as_vec2(image_point, (width * 0.5, height * 0.5))
    space = str(coordinate_space or "frame").casefold()
    if space == "normalized" or (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        return x * width, y * height
    if space == "camera_solution":
        source_size = camera_solution.get("frame_size") if isinstance(camera_solution, Mapping) else None
        src_w = float(source_size[0]) if isinstance(source_size, (list, tuple)) and len(source_size) >= 1 else float(width)
        src_h = float(source_size[1]) if isinstance(source_size, (list, tuple)) and len(source_size) >= 2 else float(height)
        return x * width / max(src_w, 1.0), y * height / max(src_h, 1.0)
    return x, y


def camera_ray_from_image_point(
    image_point: tuple[float, float] | list[float],
    camera_solution: Mapping[str, Any],
    *,
    frame_size: tuple[int, int],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Return camera-space ray origin and direction for an image point."""
    fx, fy, cx, cy = _intrinsics_for_frame(camera_solution, frame_size)
    x, y = _as_vec2(image_point, (cx, cy))
    direction = _normalize(((x - cx) / max(fx, 1e-6), -(y - cy) / max(fy, 1e-6), 1.0))
    return (0.0, 0.0, 0.0), direction


def intersect_ray_plane(
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    plane: Mapping[str, Any],
) -> tuple[float, float, float] | None:
    """Intersect a camera-space ray with a plane."""
    normal = _normalize(_as_vec3(plane.get("normal"), (0.0, 1.0, 0.0)))
    if "d" in plane:
        try:
            d = float(plane.get("d"))
        except Exception:
            point = _as_vec3(plane.get("point"), (0.0, 0.0, 1.0))
            d = -_dot(normal, point)
    else:
        point = _as_vec3(plane.get("point"), (0.0, 0.0, 1.0))
        d = -_dot(normal, point)
    denom = _dot(normal, direction)
    if abs(denom) <= 1e-8:
        return None
    t = -(_dot(normal, origin) + d) / denom
    if t <= 0:
        return None
    return (
        origin[0] + direction[0] * t,
        origin[1] + direction[1] * t,
        origin[2] + direction[2] * t,
    )


def resolve_track_placement(
    track: Mapping[str, Any],
    camera_solution: Mapping[str, Any] | None,
    *,
    frame_size: tuple[int, int],
    settings: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve a track's road-plane anchor into renderer-space transform."""
    settings_map = settings or {}
    out = deepcopy(dict(track))
    placement = out.get("placement") if isinstance(out.get("placement"), Mapping) else {}
    mode = str(placement.get("mode") or "manual").casefold() if isinstance(placement, Mapping) else "manual"
    diagnostics = {
        "ok": True,
        "applied": False,
        "mode": mode,
        "track_id": str(out.get("id") or ""),
        "warnings": [],
    }
    if mode not in {"road_plane_anchor", "plane_anchor", "screen_plane", "scene_anchor"}:
        return out, diagnostics
    if not isinstance(camera_solution, Mapping):
        diagnostics["warnings"].append("missing camera_solution")
        return out, diagnostics
    plane = camera_solution.get("plane")
    if not isinstance(plane, Mapping):
        diagnostics["warnings"].append("missing camera_solution.plane")
        return out, diagnostics
    image_point = _image_point_for_frame(
        placement.get("image_point"),
        frame_size=frame_size,
        camera_solution=camera_solution,
        coordinate_space=str(placement.get("coordinate_space") or "frame"),
    )
    anchor_world = placement.get("anchor_world") if isinstance(placement, Mapping) else None
    if isinstance(anchor_world, (list, tuple)) and len(anchor_world) >= 3:
        hit = _as_vec3(anchor_world, (0.0, 0.0, 1.0))
    else:
        origin, direction = camera_ray_from_image_point(image_point, camera_solution, frame_size=frame_size)
        hit = intersect_ray_plane(origin, direction, plane)
        if hit is None:
            diagnostics["warnings"].append("ray does not intersect road plane in front of camera")
            return out, diagnostics

    normal = _normalize(_as_vec3(plane.get("normal"), (0.0, 1.0, 0.0)))
    surface_offset = float(placement.get("surface_offset", 0.0) or 0.0)
    hit = (
        hit[0] + normal[0] * surface_offset,
        hit[1] + normal[1] * surface_offset,
        hit[2] + normal[2] * surface_offset,
    )
    transform = deepcopy(out.get("transform") if isinstance(out.get("transform"), Mapping) else {})
    manual_offset = _as_vec3(placement.get("manual_offset"), _as_vec3(transform.get("position"), (0.0, 0.0, 0.0)))
    camera_z = float(settings_map.get("camera_z", 3.25) or 3.25)
    transform["position"] = [
        hit[0] + manual_offset[0],
        hit[1] + manual_offset[1],
        hit[2] - camera_z + manual_offset[2],
    ]
    out["transform"] = transform
    diagnostics.update({
        "applied": True,
        "image_point": [float(image_point[0]), float(image_point[1])],
        "camera_space_point": [float(hit[0]), float(hit[1]), float(hit[2])],
        "renderer_position": list(transform["position"]),
    })
    return out, diagnostics
