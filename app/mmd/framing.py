"""Camera framing helpers for MMD preview bounds."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np


@dataclass(frozen=True)
class MMDFrameFit:
    zoom: float
    offset_x: float
    offset_y: float
    coverage_x: float
    coverage_y: float

    def to_camera_controls(self, *, yaw: float, pitch: float, roll: float) -> dict[str, float]:
        return {
            "yaw": float(yaw),
            "pitch": float(pitch),
            "roll": float(roll),
            "zoom": float(self.zoom),
            "offset_x": float(self.offset_x),
            "offset_y": float(self.offset_y),
        }


def bounds_from_positions(positions: np.ndarray, *, trim_percentile: float = 0.0) -> dict[str, Any]:
    arr = np.asarray(positions, dtype=np.float32)
    if arr.ndim != 2 or arr.shape[0] <= 0 or arr.shape[1] < 3:
        mins = np.zeros((3,), dtype=np.float32)
        maxs = np.ones((3,), dtype=np.float32)
    else:
        xyz = arr[:, :3]
        trim = max(0.0, min(10.0, float(trim_percentile)))
        if trim > 0.0 and xyz.shape[0] >= 64:
            mins = np.percentile(xyz, trim, axis=0).astype(np.float32)
            maxs = np.percentile(xyz, 100.0 - trim, axis=0).astype(np.float32)
        else:
            mins = np.min(xyz, axis=0)
            maxs = np.max(xyz, axis=0)
    return bounds_from_min_max(mins, maxs)


def bounds_from_min_max(mins: np.ndarray | tuple[float, float, float], maxs: np.ndarray | tuple[float, float, float]) -> dict[str, Any]:
    min_arr = np.asarray(mins, dtype=np.float32)[:3]
    max_arr = np.asarray(maxs, dtype=np.float32)[:3]
    size = np.maximum(max_arr - min_arr, 0.0001)
    center = (min_arr + max_arr) * 0.5
    fit_extent = float(max(size[1], size[0] * 1.35, size[2] * 1.15, 0.0001))
    return {
        "min": tuple(float(v) for v in min_arr),
        "max": tuple(float(v) for v in max_arr),
        "center": tuple(float(v) for v in center),
        "size": tuple(float(v) for v in size),
        "radius": max(0.0001, float(np.linalg.norm(size) * 0.5)),
        "fit_extent": max(0.0001, fit_extent),
    }


def _rotation_matrix(pitch: float, yaw: float, roll: float) -> np.ndarray:
    px = math.radians(float(pitch))
    yy = math.radians(float(yaw))
    rz = math.radians(float(roll))
    cx, sx = math.cos(px), math.sin(px)
    cy, sy = math.cos(yy), math.sin(yy)
    cz, sz = math.cos(rz), math.sin(rz)
    rx = np.asarray([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]], dtype=np.float32)
    ry = np.asarray([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float32)
    rz_mat = np.asarray([[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)
    return ry @ rx @ rz_mat


def _bounds_corners(bounds: dict[str, Any]) -> np.ndarray:
    mins = np.asarray(bounds.get("min") or (-1.0, 0.0, -1.0), dtype=np.float32)
    maxs = np.asarray(bounds.get("max") or (1.0, 1.0, 1.0), dtype=np.float32)
    return np.asarray(
        [
            (mins[0], mins[1], mins[2]),
            (mins[0], mins[1], maxs[2]),
            (mins[0], maxs[1], mins[2]),
            (mins[0], maxs[1], maxs[2]),
            (maxs[0], mins[1], mins[2]),
            (maxs[0], mins[1], maxs[2]),
            (maxs[0], maxs[1], mins[2]),
            (maxs[0], maxs[1], maxs[2]),
        ],
        dtype=np.float32,
    )


def _project_bounds(bounds: dict[str, Any], *, zoom: float, yaw: float, pitch: float, roll: float, aspect: float) -> tuple[np.ndarray, np.ndarray]:
    center = np.asarray(bounds.get("center") or (0.0, 0.0, 0.0), dtype=np.float32)
    fit_extent = max(0.0001, float(bounds.get("fit_extent") or 1.0))
    scale = max(0.05, float(zoom)) * 1.84 / fit_extent
    rotation = _rotation_matrix(pitch, yaw, roll)
    local = (_bounds_corners(bounds) - center) * float(scale)
    rotated = (rotation @ local.T).T
    camera = 3.2
    z = rotated[:, 2] + camera
    persp = camera / np.maximum(0.35, z)
    safe_aspect = max(0.1, float(aspect))
    xs = (rotated[:, 0] * persp) / safe_aspect
    ys = rotated[:, 1] * persp
    return xs.astype(np.float32, copy=False), ys.astype(np.float32, copy=False)


def auto_frame_bounds(
    bounds: dict[str, Any],
    *,
    yaw: float = 0.0,
    pitch: float = 0.0,
    roll: float = 0.0,
    aspect: float = 16.0 / 9.0,
    padding: float = 0.04,
    min_zoom: float = 0.35,
    max_zoom: float = 2.2,
) -> MMDFrameFit:
    """Fit model bounds into the editor MMD projection with stable margins."""
    limit = max(0.55, min(0.98, 1.0 - float(padding)))
    lo = max(0.05, float(min_zoom))
    hi = max(lo, float(max_zoom))

    def fits(value: float) -> bool:
        xs, ys = _project_bounds(bounds, zoom=value, yaw=yaw, pitch=pitch, roll=roll, aspect=aspect)
        span_x = float(np.max(xs) - np.min(xs))
        span_y = float(np.max(ys) - np.min(ys))
        return span_x <= limit * 2.0 and span_y <= limit * 2.0

    for _ in range(28):
        mid = (lo + hi) * 0.5
        if fits(mid):
            lo = mid
        else:
            hi = mid

    zoom = lo
    xs, ys = _project_bounds(bounds, zoom=zoom, yaw=yaw, pitch=pitch, roll=roll, aspect=aspect)
    center_x = (float(np.min(xs)) + float(np.max(xs))) * 0.5
    center_y = (float(np.min(ys)) + float(np.max(ys))) * 0.5
    offset_x = max(-0.75, min(0.75, -center_x))
    offset_y = max(-0.75, min(0.75, -center_y))
    coverage_x = min(1.0, float(np.max(xs) - np.min(xs)) / 2.0)
    coverage_y = min(1.0, float(np.max(ys) - np.min(ys)) / 2.0)
    return MMDFrameFit(
        zoom=max(lo, min(hi, zoom)),
        offset_x=offset_x,
        offset_y=offset_y,
        coverage_x=coverage_x,
        coverage_y=coverage_y,
    )
