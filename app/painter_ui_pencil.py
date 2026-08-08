"""Freehand pencil strokes converted to editable Painter vector networks."""
from __future__ import annotations

import math
from typing import Iterable


def _distance(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    if dx * dx + dy * dy <= 1e-9:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    amount = max(
        0.0,
        min(
            1.0,
            ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy)
            / (dx * dx + dy * dy),
        ),
    )
    nearest = (start[0] + dx * amount, start[1] + dy * amount)
    return math.hypot(point[0] - nearest[0], point[1] - nearest[1])


def _simplify(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points
    start, end = points[0], points[-1]
    index, maximum = 0, 0.0
    for candidate_index, point in enumerate(points[1:-1], 1):
        distance = _distance(point, start, end)
        if distance > maximum:
            index, maximum = candidate_index, distance
    if maximum <= tolerance:
        return [start, end]
    left = _simplify(points[: index + 1], tolerance)
    right = _simplify(points[index:], tolerance)
    return left[:-1] + right


def pencil_vector_object(
    points: Iterable[tuple[float, float]],
    *,
    smoothing: float = 0.55,
) -> dict:
    """Create an open, smooth cubic vector object from document-space points."""
    sampled: list[tuple[float, float]] = []
    for raw_x, raw_y in points:
        point = (float(raw_x), float(raw_y))
        if not sampled or math.dist(point, sampled[-1]) >= 0.75:
            sampled.append(point)
    if len(sampled) < 2:
        raise ValueError("A pencil stroke requires at least two points")
    simplified = _simplify(sampled, max(0.35, 1.65 - float(smoothing)))
    if len(simplified) < 2:
        simplified = [sampled[0], sampled[-1]]
    left = min(point[0] for point in simplified)
    top = min(point[1] for point in simplified)
    width = max(1.0, max(point[0] for point in simplified) - left)
    height = max(1.0, max(point[1] for point in simplified) - top)
    normalized = [((x - left) / width, (y - top) / height) for x, y in simplified]
    tension = max(0.0, min(1.0, float(smoothing))) / 6.0
    nodes: list[dict] = []
    for index, (x, y) in enumerate(normalized):
        previous = normalized[max(0, index - 1)]
        following = normalized[min(len(normalized) - 1, index + 1)]
        tangent_x = (following[0] - previous[0]) * tension
        tangent_y = (following[1] - previous[1]) * tension
        nodes.append(
            {
                "id": f"node-{index + 1}",
                "x": x,
                "y": y,
                "in_handle": None if index == 0 else {"x": x - tangent_x, "y": y - tangent_y},
                "out_handle": None if index == len(normalized) - 1 else {"x": x + tangent_x, "y": y + tangent_y},
                "kind": "smooth" if 0 < index < len(normalized) - 1 else "corner",
            }
        )
    segments = [
        {
            "id": f"segment-{index + 1}",
            "start_node_id": f"node-{index + 1}",
            "end_node_id": f"node-{index + 2}",
            "kind": "cubic",
        }
        for index in range(len(nodes) - 1)
    ]
    from app.painter_ui_vector_network import normalize_vector_content

    content = normalize_vector_content(
        {
            "pencil_smoothing": max(0.0, min(1.0, float(smoothing))),
            "vector_network": {"nodes": nodes, "segments": segments, "closed": False},
        }
    )
    return {"x": left, "y": top, "width": width, "height": height, "content": content}


__all__ = ["pencil_vector_object"]
