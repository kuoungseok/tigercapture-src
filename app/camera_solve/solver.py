"""Manual-assisted road plane and camera solution helpers."""
from __future__ import annotations

import hashlib
from typing import Any, Iterable


def camera_solution_id(
    *,
    source_id: str = "",
    points: Iterable[Iterable[float]] = (),
    time_ms: int = 0,
    model: str = "manual_depth_plane_v1",
) -> str:
    material = f"{source_id}|{model}|{int(time_ms)}|{list(points)}"
    return "cam_" + hashlib.sha1(material.encode("utf-8", "replace")).hexdigest()[:16]


def _point_depth(depth_frame: Any, x: float, y: float, default: float = 0.5) -> float:
    if depth_frame is None:
        return default
    try:
        import numpy as np

        arr = np.asarray(depth_frame, dtype=np.float32)
        if arr.ndim == 3:
            arr = arr[..., 0]
        h, w = arr.shape[:2]
        xi = max(0, min(w - 1, int(round(x))))
        yi = max(0, min(h - 1, int(round(y))))
        value = float(arr[yi, xi])
        if not np.isfinite(value):
            return default
        return max(0.01, min(1.0, value))
    except Exception:
        return default


def _normalize(v):
    import numpy as np

    n = float(np.linalg.norm(v))
    if n <= 1e-8:
        return v, n
    return v / n, n


def solve_road_plane_from_points(
    image_points: list[list[float]] | list[tuple[float, float]],
    *,
    depth_frame: Any = None,
    frame_size: tuple[int, int] | list[int] | None = None,
    source_id: str = "",
    depth_source_id: str = "",
    time_ms: int = 0,
    focal_length_px: float | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Solve a simple road plane from three or more image points.

    This first pass is deliberately manual-assisted. It is sufficient for
    storing the camera/plane contract and for synthetic QA, not full matchmove.
    """
    import numpy as np

    points = [(float(p[0]), float(p[1])) for p in list(image_points or []) if len(p) >= 2]
    if len(points) < 3:
        return None, {
            "ok": False,
            "reason": "need_at_least_three_points",
            "point_count": len(points),
            "warnings": [],
        }

    if frame_size is None:
        try:
            arr = np.asarray(depth_frame)
            h, w = arr.shape[:2]
            frame_size = (int(w), int(h))
        except Exception:
            max_x = max(p[0] for p in points)
            max_y = max(p[1] for p in points)
            frame_size = (max(1, int(max_x * 2)), max(1, int(max_y * 2)))
    width = max(1, int(frame_size[0]))
    height = max(1, int(frame_size[1]))
    fx = fy = float(focal_length_px or max(width, height) * 0.9)
    cx = width * 0.5
    cy = height * 0.5

    world = []
    for x, y in points[:3]:
        z = _point_depth(depth_frame, x, y, default=0.5)
        world.append([
            (x - cx) / fx * z,
            -(y - cy) / fy * z,
            z,
        ])
    p0 = np.asarray(world[0], dtype=np.float64)
    p1 = np.asarray(world[1], dtype=np.float64)
    p2 = np.asarray(world[2], dtype=np.float64)
    normal, norm_len = _normalize(np.cross(p1 - p0, p2 - p0))
    warnings: list[str] = []
    if norm_len <= 1e-8:
        normal = np.asarray([0.0, 1.0, 0.0], dtype=np.float64)
        warnings.append("degenerate plane points; using default up normal")
    if normal[1] < 0:
        normal = -normal
    d = -float(np.dot(normal, p0))
    sid = camera_solution_id(source_id=source_id or depth_source_id, points=points, time_ms=time_ms)
    solution = {
        "id": sid,
        "model": "manual_depth_plane_v1",
        "frame_size": [width, height],
        "intrinsics": {
            "fx": fx,
            "fy": fy,
            "cx": cx,
            "cy": cy,
        },
        "plane": {
            "point": [float(v) for v in p0.tolist()],
            "normal": [float(v) for v in normal.tolist()],
            "d": d,
        },
        "image_points": [[float(x), float(y)] for x, y in points],
        "depth_source_id": str(depth_source_id or ""),
    }
    diagnostics = {
        "ok": True,
        "camera_solution_id": sid,
        "point_count": len(points),
        "depth_source_id": str(depth_source_id or ""),
        "warnings": warnings,
        "manual_assist_required": True,
    }
    return solution, diagnostics

