"""Topology-safe vector path morph authoring helpers."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import hypot
from typing import Any
from uuid import uuid4

from .schema import AnimatedProperty, Keyframe, MotionLayer
from .vector_shapes import VectorPath, VectorPoint, flatten_path

PATH_MORPH_CONTRACT = "tigerstudio.motion.path_morph.v1"


def path_topology_signature(path: Mapping[str, Any]) -> dict[str, Any]:
    value = VectorPath.from_dict(path)
    return {
        "point_count": len(value.points),
        "closed": value.closed,
        "fill_rule": value.fill_rule,
    }


def _sample_polyline(
    points: list[tuple[float, float]],
    count: int,
    *,
    closed: bool,
) -> list[tuple[float, float]]:
    rows = list(points)
    if closed and rows and rows[-1] != rows[0]:
        rows.append(rows[0])
    if len(rows) < 2:
        return [rows[0] if rows else (0.0, 0.0)] * count
    lengths = [0.0]
    for left, right in zip(rows, rows[1:]):
        lengths.append(
            lengths[-1] + hypot(right[0] - left[0], right[1] - left[1]),
        )
    total = lengths[-1]
    if total <= 1e-9:
        return [rows[0]] * count
    denominator = count if closed else max(1, count - 1)
    result: list[tuple[float, float]] = []
    segment = 0
    for index in range(count):
        target = total * index / denominator
        while segment + 1 < len(lengths) and lengths[segment + 1] < target:
            segment += 1
        segment = min(segment, len(rows) - 2)
        start, end = rows[segment], rows[segment + 1]
        span = max(1e-9, lengths[segment + 1] - lengths[segment])
        amount = max(0.0, min(1.0, (target - lengths[segment]) / span))
        result.append((
            start[0] + (end[0] - start[0]) * amount,
            start[1] + (end[1] - start[1]) * amount,
        ))
    return result


def normalize_path_correspondence(
    paths: Sequence[Mapping[str, Any]],
    *,
    target_count: int = 0,
) -> list[dict[str, Any]]:
    values = [VectorPath.from_dict(path) for path in paths]
    if not values:
        return []
    closed = values[0].closed
    if any(value.closed != closed for value in values):
        raise ValueError("all morph paths must share open/closed topology")
    count = max(
        2 if not closed else 3,
        int(target_count or 0),
        *(len(value.points) for value in values),
    )
    output = []
    for value in values:
        sampled = _sample_polyline(
            flatten_path(value, tolerance=0.35),
            count,
            closed=closed,
        )
        output.append(VectorPath(
            points=[VectorPoint(position=point) for point in sampled],
            closed=closed,
            fill_rule=value.fill_rule,
        ).to_dict())
    return output


def set_layer_path_morph(
    layer: MotionLayer,
    keyframes: Sequence[Mapping[str, Any]],
    *,
    auto_correspond: bool = True,
    target_count: int = 0,
) -> dict[str, Any]:
    if layer.layer_type != "shape":
        raise ValueError("Path Morph requires a shape layer")
    rows = [dict(row) for row in keyframes]
    if len(rows) < 2:
        raise ValueError("Path Morph requires at least two keyframes")
    paths = [
        row.get("path") if isinstance(row.get("path"), Mapping) else row.get("value")
        for row in rows
    ]
    if not all(isinstance(path, Mapping) for path in paths):
        raise ValueError("Every Path Morph keyframe requires a path object")
    if auto_correspond:
        normalized_paths = normalize_path_correspondence(
            paths,
            target_count=target_count,
        )
    else:
        signatures = [path_topology_signature(path) for path in paths]
        if any(signature != signatures[0] for signature in signatures[1:]):
            raise ValueError("Path Morph keyframes have incompatible topology")
        normalized_paths = [dict(path) for path in paths]
    frames = [
        Keyframe(
            id=str(row.get("id") or f"path_key_{uuid4().hex[:10]}"),
            time_ms=int(row.get("time_ms", 0) or 0),
            value=path,
            interpolation=str(row.get("interpolation") or "bezier"),
            in_tangent=tuple(row.get("in_tangent") or (0.33, 0.0)),
            out_tangent=tuple(row.get("out_tangent") or (0.67, 1.0)),
        )
        for row, path in zip(rows, normalized_paths)
    ]
    frames.sort(key=lambda frame: (frame.time_ms, frame.id))
    prop = AnimatedProperty(
        value_type="path",
        default=normalized_paths[0],
        keyframes=frames,
    )
    layer.source.kind = "shape"
    layer.source.params["shape"] = "path"
    layer.source.params["path"] = prop.to_dict()
    report = {
        "contract": PATH_MORPH_CONTRACT,
        "point_count": len(normalized_paths[0].get("points", [])),
        "keyframe_count": len(frames),
        "auto_corresponded": bool(auto_correspond),
    }
    layer.metadata["path_morph"] = report
    return report


__all__ = [
    "PATH_MORPH_CONTRACT",
    "normalize_path_correspondence",
    "path_topology_signature",
    "set_layer_path_morph",
]
