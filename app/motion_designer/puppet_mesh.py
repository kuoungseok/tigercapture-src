"""Serializable 2D puppet mesh contract and deterministic pin deformation."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from math import cos, exp, isfinite, radians, sin
from typing import Any, Mapping, Sequence

from .keyframes import evaluate_property
from .schema import AnimatedProperty, MotionLayer, new_motion_id


PUPPET_METADATA_KEY = "puppet_mesh"
PUPPET_SCHEMA = "tigerstudio.motion.puppet_mesh.v1"
PUPPET_PIN_KINDS = {"position", "bend", "starch", "overlap"}


def _point(value: Any, fallback=(0.0, 0.0)) -> tuple[float, float]:
    if (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes))
        and len(value) >= 2
    ):
        try:
            point = float(value[0]), float(value[1])
            if all(isfinite(item) for item in point):
                return point
        except (TypeError, ValueError):
            pass
    return float(fallback[0]), float(fallback[1])


@dataclass(slots=True)
class PuppetVertex:
    id: str = field(default_factory=lambda: new_motion_id("vertex"))
    uv: tuple[float, float] = (0.0, 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "uv": list(self.uv)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PuppetVertex":
        return cls(
            id=str(value.get("id") or new_motion_id("vertex")),
            uv=_point(value.get("uv")),
        )


@dataclass(slots=True)
class PuppetPin:
    id: str = field(default_factory=lambda: new_motion_id("pin"))
    name: str = "Pin"
    kind: str = "position"
    rest_position: tuple[float, float] = (0.5, 0.5)
    position: AnimatedProperty = field(
        default_factory=lambda: AnimatedProperty(
            value_type="vector2",
            default=[0.5, 0.5],
        ),
    )
    rotation: AnimatedProperty = field(
        default_factory=lambda: AnimatedProperty(value_type="scalar", default=0.0),
    )
    radius: float = 0.35
    strength: float = 1.0
    depth: float = 0.0
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "rest_position": list(self.rest_position),
            "position": self.position.to_dict(),
            "rotation": self.rotation.to_dict(),
            "radius": float(self.radius),
            "strength": float(self.strength),
            "depth": float(self.depth),
            "enabled": bool(self.enabled),
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PuppetPin":
        rest = _point(value.get("rest_position"), (0.5, 0.5))
        return cls(
            id=str(value.get("id") or new_motion_id("pin")),
            name=str(value.get("name") or "Pin"),
            kind=str(value.get("kind") or "position").lower(),
            rest_position=rest,
            position=AnimatedProperty.from_dict(
                value.get("position", list(rest)),
                value_type="vector2",
            ),
            rotation=AnimatedProperty.from_dict(
                value.get("rotation", 0.0),
                value_type="scalar",
            ),
            radius=float(value.get("radius", 0.35) or 0.35),
            strength=float(value.get("strength", 1.0) or 1.0),
            depth=float(value.get("depth", 0.0) or 0.0),
            enabled=bool(value.get("enabled", True)),
            metadata=(
                dict(value.get("metadata"))
                if isinstance(value.get("metadata"), Mapping)
                else {}
            ),
        )


@dataclass(slots=True)
class PuppetMesh:
    id: str = field(default_factory=lambda: new_motion_id("puppet"))
    vertices: list[PuppetVertex] = field(default_factory=list)
    triangles: list[tuple[int, int, int]] = field(default_factory=list)
    pins: list[PuppetPin] = field(default_factory=list)
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PUPPET_SCHEMA,
            "id": self.id,
            "vertices": [vertex.to_dict() for vertex in self.vertices],
            "triangles": [list(row) for row in self.triangles],
            "pins": [pin.to_dict() for pin in self.pins],
            "enabled": bool(self.enabled),
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PuppetMesh":
        triangles = []
        for row in value.get("triangles", []):
            if isinstance(row, Sequence) and len(row) >= 3:
                triangles.append((int(row[0]), int(row[1]), int(row[2])))
        return cls(
            id=str(value.get("id") or new_motion_id("puppet")),
            vertices=[
                PuppetVertex.from_dict(row)
                for row in value.get("vertices", [])
                if isinstance(row, Mapping)
            ],
            triangles=triangles,
            pins=[
                PuppetPin.from_dict(row)
                for row in value.get("pins", [])
                if isinstance(row, Mapping)
            ],
            enabled=bool(value.get("enabled", True)),
            metadata=(
                dict(value.get("metadata"))
                if isinstance(value.get("metadata"), Mapping)
                else {}
            ),
        )


def layer_puppet_mesh(layer: MotionLayer) -> PuppetMesh | None:
    value = layer.metadata.get(PUPPET_METADATA_KEY)
    return PuppetMesh.from_dict(value) if isinstance(value, Mapping) else None


def set_layer_puppet_mesh(layer: MotionLayer, mesh: PuppetMesh) -> None:
    layer.metadata[PUPPET_METADATA_KEY] = mesh.to_dict()


def create_grid_puppet_mesh(
    layer: MotionLayer,
    *,
    columns: int = 8,
    rows: int = 8,
) -> PuppetMesh:
    columns = max(2, min(128, int(columns)))
    rows = max(2, min(128, int(rows)))
    vertices = [
        PuppetVertex(uv=(column / columns, row / rows))
        for row in range(rows + 1)
        for column in range(columns + 1)
    ]
    triangles: list[tuple[int, int, int]] = []
    stride = columns + 1
    for row in range(rows):
        for column in range(columns):
            top_left = row * stride + column
            top_right = top_left + 1
            bottom_left = top_left + stride
            bottom_right = bottom_left + 1
            triangles.extend(
                (
                    (top_left, top_right, bottom_right),
                    (top_left, bottom_right, bottom_left),
                ),
            )
    mesh = PuppetMesh(
        vertices=vertices,
        triangles=triangles,
        metadata={"generator": "regular_grid_v1", "columns": columns, "rows": rows},
    )
    set_layer_puppet_mesh(layer, mesh)
    return mesh


def create_alpha_adaptive_puppet_mesh(
    layer: MotionLayer,
    *,
    columns: int = 16,
    rows: int = 16,
    alpha_threshold: int = 4,
) -> PuppetMesh:
    from pathlib import Path
    import cv2
    from PySide6.QtGui import QImage

    path = Path(layer.source.uri)
    image = QImage(str(path)) if path.is_file() else QImage()
    if image.isNull() or not image.hasAlphaChannel():
        mesh = create_grid_puppet_mesh(layer, columns=columns, rows=rows)
        mesh.metadata["generator"] = "regular_grid_v1"
        mesh.metadata["adaptive_reason"] = "source_alpha_unavailable"
        set_layer_puppet_mesh(layer, mesh)
        return mesh
    image = image.convertToFormat(QImage.Format_RGBA8888)
    threshold = max(0, min(255, int(alpha_threshold)))
    columns = max(2, min(128, int(columns)))
    rows = max(2, min(128, int(rows)))

    def alpha(point: tuple[float, float]) -> int:
        x = max(0, min(image.width() - 1, round(point[0] * (image.width() - 1))))
        y = max(0, min(image.height() - 1, round(point[1] * (image.height() - 1))))
        return int(image.pixelColor(x, y).alpha())

    points = {
        (column / columns, row / rows)
        for row in range(rows + 1)
        for column in range(columns + 1)
    }
    refined_cells = 0
    for row in range(rows):
        for column in range(columns):
            x0, x1 = column / columns, (column + 1) / columns
            y0, y1 = row / rows, (row + 1) / rows
            samples = (
                (x0, y0), (x1, y0), (x0, y1), (x1, y1),
                ((x0 + x1) * 0.5, y0),
                ((x0 + x1) * 0.5, y1),
                (x0, (y0 + y1) * 0.5),
                (x1, (y0 + y1) * 0.5),
                ((x0 + x1) * 0.5, (y0 + y1) * 0.5),
            )
            opaque = [alpha(point) > threshold for point in samples]
            if not any(opaque) or all(opaque):
                continue
            refined_cells += 1
            points.update(samples)

    ordered_points = sorted(points, key=lambda point: (point[1], point[0]))
    scale = float(max(1024, columns * 16, rows * 16))
    subdiv = cv2.Subdiv2D((0, 0, int(scale) + 1, int(scale) + 1))
    scaled_points = [(point[0] * scale, point[1] * scale) for point in ordered_points]
    for point in scaled_points:
        subdiv.insert(point)
    lookup = {
        (round(point[0], 3), round(point[1], 3)): index
        for index, point in enumerate(scaled_points)
    }

    def vertex_index(point: tuple[float, float]) -> int | None:
        direct = lookup.get((round(float(point[0]), 3), round(float(point[1]), 3)))
        if direct is not None:
            return direct
        nearest = min(
            range(len(scaled_points)),
            key=lambda index: (
                (scaled_points[index][0] - point[0]) ** 2
                + (scaled_points[index][1] - point[1]) ** 2
            ),
        )
        distance_sq = (
            (scaled_points[nearest][0] - point[0]) ** 2
            + (scaled_points[nearest][1] - point[1]) ** 2
        )
        return nearest if distance_sq <= 0.01 else None

    triangles: list[tuple[int, int, int]] = []
    seen_triangles: set[tuple[int, int, int]] = set()
    for raw in subdiv.getTriangleList():
        indexes = tuple(
            vertex_index((float(raw[offset]), float(raw[offset + 1])))
            for offset in (0, 2, 4)
        )
        if any(index is None for index in indexes):
            continue
        triangle = tuple(int(index) for index in indexes)
        if len(set(triangle)) != 3:
            continue
        a, b, c = (ordered_points[index] for index in triangle)
        area = (
            (b[0] - a[0]) * (c[1] - a[1])
            - (b[1] - a[1]) * (c[0] - a[0])
        )
        if abs(area) <= 1e-12:
            continue
        if area < 0.0:
            triangle = (triangle[0], triangle[2], triangle[1])
        canonical = tuple(sorted(triangle))
        if canonical in seen_triangles:
            continue
        seen_triangles.add(canonical)
        triangles.append(triangle)

    vertices = [
        PuppetVertex(
            id=f"vertex_{round(point[0] * 1_000_000):07d}_{round(point[1] * 1_000_000):07d}",
            uv=point,
        )
        for point in ordered_points
    ]
    retained: list[tuple[int, int, int]] = []
    for triangle in triangles:
        triangle_points = [vertices[index].uv for index in triangle]
        center = (
            sum(point[0] for point in triangle_points) / 3.0,
            sum(point[1] for point in triangle_points) / 3.0,
        )
        if max(
            *(alpha(point) for point in triangle_points),
            alpha(center),
        ) > threshold:
            retained.append(triangle)
    mesh = PuppetMesh(
        vertices=vertices,
        triangles=retained,
        metadata={
        "generator": "alpha_boundary_delaunay_v2",
        "alpha_threshold": threshold,
        "columns": columns,
        "rows": rows,
        "base_vertex_count": (columns + 1) * (rows + 1),
        "refined_vertex_count": len(vertices),
        "boundary_refined_cell_count": refined_cells,
        "retained_triangle_count": len(retained),
        },
    )
    set_layer_puppet_mesh(layer, mesh)
    return mesh


def add_puppet_pin(
    layer: MotionLayer,
    *,
    kind: str,
    position: Sequence[float],
    name: str = "",
    radius: float = 0.35,
    strength: float = 1.0,
) -> PuppetPin:
    mesh = layer_puppet_mesh(layer)
    if mesh is None:
        mesh = create_grid_puppet_mesh(layer)
    normalized_kind = str(kind or "position").lower()
    if normalized_kind not in PUPPET_PIN_KINDS:
        raise ValueError(f"Unsupported puppet pin kind: {kind}")
    rest = _point(position, (0.5, 0.5))
    pin = PuppetPin(
        name=str(name or normalized_kind.title()),
        kind=normalized_kind,
        rest_position=rest,
        position=AnimatedProperty(value_type="vector2", default=list(rest)),
        radius=max(0.001, min(2.0, float(radius))),
        strength=max(0.0, min(2.0, float(strength))),
    )
    mesh.pins.append(pin)
    set_layer_puppet_mesh(layer, mesh)
    return pin


def update_puppet_pin(
    layer: MotionLayer,
    pin_id: str,
    changes: Mapping[str, Any],
) -> PuppetPin:
    mesh = layer_puppet_mesh(layer)
    if mesh is None:
        raise ValueError("Layer has no puppet mesh")
    index = next(
        (index for index, pin in enumerate(mesh.pins) if pin.id == str(pin_id)),
        None,
    )
    if index is None:
        raise ValueError(f"Unknown puppet pin: {pin_id}")
    data = mesh.pins[index].to_dict()
    data.update(deepcopy(dict(changes)))
    data["id"] = mesh.pins[index].id
    mesh.pins[index] = PuppetPin.from_dict(data)
    set_layer_puppet_mesh(layer, mesh)
    return mesh.pins[index]


def delete_puppet_pin(layer: MotionLayer, pin_id: str) -> bool:
    mesh = layer_puppet_mesh(layer)
    if mesh is None:
        return False
    remaining = [pin for pin in mesh.pins if pin.id != str(pin_id)]
    if len(remaining) == len(mesh.pins):
        return False
    mesh.pins = remaining
    set_layer_puppet_mesh(layer, mesh)
    return True


def bind_puppet_pin_to_rig(
    layer: MotionLayer,
    pin_id: str,
    *,
    rig_id: str,
    bone_id: str,
) -> PuppetPin:
    mesh = layer_puppet_mesh(layer)
    if mesh is None:
        raise ValueError("Layer has no puppet mesh")
    pin = next((row for row in mesh.pins if row.id == str(pin_id)), None)
    if pin is None:
        raise ValueError(f"Unknown puppet pin: {pin_id}")
    pin.metadata["rig_driver"] = {
        "rig_id": str(rig_id),
        "bone_id": str(bone_id),
    }
    set_layer_puppet_mesh(layer, mesh)
    return pin


def remove_puppet_mesh(layer: MotionLayer) -> bool:
    return layer.metadata.pop(PUPPET_METADATA_KEY, None) is not None


def evaluate_puppet_vertices(
    mesh: PuppetMesh,
    time_ms: float,
    *,
    drivers: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[tuple[float, float]]:
    driver_rows = dict(drivers or {})
    output: list[tuple[float, float]] = []
    for vertex in mesh.vertices:
        x, y = vertex.uv
        dx_total = 0.0
        dy_total = 0.0
        weight_total = 0.0
        for pin in mesh.pins:
            if not pin.enabled:
                continue
            px, py = pin.rest_position
            distance_sq = (x - px) ** 2 + (y - py) ** 2
            radius = max(0.001, float(pin.radius))
            weight = exp(-distance_sq / (radius * radius * 0.5))
            weight *= max(0.0, min(2.0, float(pin.strength)))
            target = _point(evaluate_property(pin.position, time_ms), pin.rest_position)
            driver = driver_rows.get(pin.id)
            if isinstance(driver, Mapping):
                target = _point(driver.get("position"), target)
            if pin.kind == "position":
                dx_total += (target[0] - px) * weight
                dy_total += (target[1] - py) * weight
            elif pin.kind == "bend":
                rotation = float(evaluate_property(pin.rotation, time_ms) or 0.0)
                if isinstance(driver, Mapping):
                    rotation += float(driver.get("rotation", 0.0) or 0.0)
                angle = radians(rotation)
                local_x, local_y = x - px, y - py
                rotated_x = local_x * cos(angle) - local_y * sin(angle)
                rotated_y = local_x * sin(angle) + local_y * cos(angle)
                dx_total += (rotated_x - local_x) * weight
                dy_total += (rotated_y - local_y) * weight
            elif pin.kind == "starch":
                # Starch pins retain the rest pose against surrounding motion.
                weight_total += weight
            weight_total += weight if pin.kind != "starch" else 0.0
        damping = 1.0 / (1.0 + weight_total * 0.15)
        output.append((x + dx_total * damping, y + dy_total * damping))
    return output


def evaluate_puppet_render_vertices(
    mesh: PuppetMesh,
    time_ms: float,
    *,
    width: int,
    height: int,
    composition=None,
) -> tuple[list[tuple[float, float]], dict[str, Any]]:
    """Evaluate rig-driven vertices and apply the shared tear-repair policy."""
    drivers: dict[str, dict[str, Any]] = {}
    if composition is not None:
        from .rigging import composition_rigs

        rigs = {rig.id: rig for rig in composition_rigs(composition)}
        for pin in mesh.pins:
            driver = pin.metadata.get("rig_driver")
            if not isinstance(driver, Mapping):
                continue
            rig = rigs.get(str(driver.get("rig_id") or ""))
            bone = next(
                (
                    row
                    for row in rig.bones
                    if row.id == str(driver.get("bone_id") or "")
                ),
                None,
            ) if rig is not None else None
            if bone is None:
                continue
            translation = _point(evaluate_property(bone.translation, time_ms))
            drivers[pin.id] = {
                "position": [
                    pin.rest_position[0] + translation[0] / max(1, int(width)),
                    pin.rest_position[1] + translation[1] / max(1, int(height)),
                ],
                "rotation": float(evaluate_property(bone.rotation, time_ms) or 0.0),
            }
    evaluated = evaluate_puppet_vertices(mesh, time_ms, drivers=drivers)
    repair_settings = mesh.metadata.get("tear_repair")
    repair_settings = repair_settings if isinstance(repair_settings, Mapping) else {}
    if not bool(repair_settings.get("enabled", True)):
        return evaluated, {
            "mode": "disabled",
            "iterations": 0,
            "repaired_vertex_count": 0,
            "render_safe": True,
        }
    return repair_puppet_vertices(
        mesh,
        evaluated,
        max_edge_stretch=float(
            repair_settings.get("max_edge_stretch", 6.0) or 6.0
        ),
    )


def evaluate_puppet_depths(
    mesh: PuppetMesh,
) -> list[float]:
    depths: list[float] = []
    for vertex in mesh.vertices:
        weighted_depth = 0.0
        for pin in mesh.pins:
            if not pin.enabled or pin.kind != "overlap":
                continue
            distance_sq = (
                (vertex.uv[0] - pin.rest_position[0]) ** 2
                + (vertex.uv[1] - pin.rest_position[1]) ** 2
            )
            radius = max(0.001, float(pin.radius))
            weight = exp(-distance_sq / (radius * radius * 0.5))
            weight *= max(0.0, min(2.0, float(pin.strength)))
            weighted_depth += float(pin.depth) * weight
        # Do not normalize by total weight. A single overlap pin still needs a
        # spatial falloff; normalization would give every influenced vertex
        # the same depth and make the pin incapable of changing draw order.
        depths.append(weighted_depth)
    return depths


def stabilize_puppet_vertices(
    mesh: PuppetMesh,
    points: Sequence[tuple[float, float]],
) -> tuple[list[tuple[float, float]], float]:
    rest = [vertex.uv for vertex in mesh.vertices]

    def valid(candidate: Sequence[tuple[float, float]]) -> bool:
        for a, b, c in mesh.triangles:
            if min(a, b, c) < 0 or max(a, b, c) >= len(candidate):
                return False
            pa, pb, pc = candidate[a], candidate[b], candidate[c]
            area = (
                (pb[0] - pa[0]) * (pc[1] - pa[1])
                - (pb[1] - pa[1]) * (pc[0] - pa[0])
            )
            if area <= 1e-8:
                return False
        return True

    output = list(points)
    if valid(output):
        return output, 1.0
    low, high = 0.0, 1.0
    best = list(rest)
    for _ in range(12):
        amount = (low + high) * 0.5
        candidate = [
            (
                source[0] + (target[0] - source[0]) * amount,
                source[1] + (target[1] - source[1]) * amount,
            )
            for source, target in zip(rest, points)
        ]
        if valid(candidate):
            best = candidate
            low = amount
        else:
            high = amount
    return best, low


def _puppet_triangle_problems(
    mesh: PuppetMesh,
    points: Sequence[tuple[float, float]],
    *,
    max_edge_stretch: float,
) -> tuple[set[int], int, int, int]:
    problem_triangles: set[int] = set()
    flipped = 0
    degenerate = 0
    torn = 0
    rest = [vertex.uv for vertex in mesh.vertices]
    stretch_limit = max(1.01, float(max_edge_stretch))
    for triangle_index, (a, b, c) in enumerate(mesh.triangles):
        if min(a, b, c) < 0 or max(a, b, c) >= len(points):
            problem_triangles.add(triangle_index)
            degenerate += 1
            continue
        pa, pb, pc = points[a], points[b], points[c]
        ra, rb, rc = rest[a], rest[b], rest[c]
        area = (
            (pb[0] - pa[0]) * (pc[1] - pa[1])
            - (pb[1] - pa[1]) * (pc[0] - pa[0])
        )
        rest_area = (
            (rb[0] - ra[0]) * (rc[1] - ra[1])
            - (rb[1] - ra[1]) * (rc[0] - ra[0])
        )
        if abs(area) <= 1e-8 or abs(rest_area) <= 1e-12:
            problem_triangles.add(triangle_index)
            degenerate += 1
            continue
        if area * rest_area < 0.0:
            problem_triangles.add(triangle_index)
            flipped += 1
            continue
        for source_a, source_b, target_a, target_b in (
            (ra, rb, pa, pb),
            (rb, rc, pb, pc),
            (rc, ra, pc, pa),
        ):
            rest_length = (
                (source_b[0] - source_a[0]) ** 2
                + (source_b[1] - source_a[1]) ** 2
            ) ** 0.5
            deformed_length = (
                (target_b[0] - target_a[0]) ** 2
                + (target_b[1] - target_a[1]) ** 2
            ) ** 0.5
            if rest_length > 1e-9 and deformed_length / rest_length > stretch_limit:
                problem_triangles.add(triangle_index)
                torn += 1
                break
    return problem_triangles, flipped, degenerate, torn


def repair_puppet_vertices(
    mesh: PuppetMesh,
    points: Sequence[tuple[float, float]],
    *,
    max_edge_stretch: float = 6.0,
    max_iterations: int = 12,
) -> tuple[list[tuple[float, float]], dict[str, Any]]:
    """Repair only vertices around folded or excessively stretched triangles."""
    original = list(points)
    problems, flipped, degenerate, torn = _puppet_triangle_problems(
        mesh,
        original,
        max_edge_stretch=max_edge_stretch,
    )
    if not problems:
        return original, {
            "mode": "none",
            "iterations": 0,
            "repaired_vertex_count": 0,
            "flipped_triangle_count": 0,
            "degenerate_triangle_count": 0,
            "torn_triangle_count": 0,
            "render_safe": True,
        }

    rest = [vertex.uv for vertex in mesh.vertices]
    low, high = 0.0, 1.0
    safe = list(rest)
    safe_amount = 0.0
    for _ in range(14):
        amount = (low + high) * 0.5
        candidate = [
            (
                source[0] + (target[0] - source[0]) * amount,
                source[1] + (target[1] - source[1]) * amount,
            )
            for source, target in zip(rest, original)
        ]
        candidate_problems, *_ = _puppet_triangle_problems(
            mesh,
            candidate,
            max_edge_stretch=max_edge_stretch,
        )
        if candidate_problems:
            high = amount
        else:
            safe = candidate
            safe_amount = amount
            low = amount

    output = list(original)
    repaired_vertices: set[int] = set()
    iteration_count = 0
    for iteration in range(max(1, int(max_iterations))):
        current_problems, *_ = _puppet_triangle_problems(
            mesh,
            output,
            max_edge_stretch=max_edge_stretch,
        )
        if not current_problems:
            iteration_count = iteration
            break
        affected = {
            vertex_index
            for triangle_index in current_problems
            for vertex_index in mesh.triangles[triangle_index]
            if 0 <= vertex_index < len(output)
        }
        repaired_vertices.update(affected)
        for vertex_index in affected:
            output[vertex_index] = (
                output[vertex_index][0] * 0.5 + safe[vertex_index][0] * 0.5,
                output[vertex_index][1] * 0.5 + safe[vertex_index][1] * 0.5,
            )
        iteration_count = iteration + 1

    remaining, *_ = _puppet_triangle_problems(
        mesh,
        output,
        max_edge_stretch=max_edge_stretch,
    )
    mode = "local"
    if remaining:
        output = safe
        mode = "global_fallback"
    return output, {
        "mode": mode,
        "iterations": iteration_count,
        "repaired_vertex_count": len(repaired_vertices),
        "flipped_triangle_count": flipped,
        "degenerate_triangle_count": degenerate,
        "torn_triangle_count": torn,
        "fallback_deformation_amount": safe_amount,
        "render_safe": not _puppet_triangle_problems(
            mesh,
            output,
            max_edge_stretch=max_edge_stretch,
        )[0],
    }


def configure_puppet_tear_repair(
    layer: MotionLayer,
    *,
    enabled: bool,
    max_edge_stretch: float = 6.0,
) -> dict[str, Any]:
    mesh = layer_puppet_mesh(layer)
    if mesh is None:
        raise ValueError("Layer has no puppet mesh")
    value = {
        "enabled": bool(enabled),
        "mode": "local",
        "max_edge_stretch": max(1.01, min(100.0, float(max_edge_stretch))),
    }
    mesh.metadata["tear_repair"] = value
    set_layer_puppet_mesh(layer, mesh)
    return value


def puppet_mesh_diagnostics(
    mesh: PuppetMesh,
    time_ms: float = 0.0,
) -> dict[str, Any]:
    points = evaluate_puppet_vertices(mesh, time_ms)
    _stabilized, stable_amount = stabilize_puppet_vertices(mesh, points)
    repair_settings = mesh.metadata.get("tear_repair")
    repair_settings = repair_settings if isinstance(repair_settings, Mapping) else {}
    max_stretch = float(repair_settings.get("max_edge_stretch", 6.0) or 6.0)
    _repaired, repair = repair_puppet_vertices(
        mesh,
        points,
        max_edge_stretch=max_stretch,
    )
    flipped = int(repair["flipped_triangle_count"])
    degenerate = int(repair["degenerate_triangle_count"])
    out_of_bounds_pins = [
        pin.id for pin in mesh.pins
        if not (0.0 <= pin.rest_position[0] <= 1.0 and 0.0 <= pin.rest_position[1] <= 1.0)
    ]
    coincident_pairs: list[list[str]] = []
    for index, pin in enumerate(mesh.pins):
        for other in mesh.pins[index + 1:]:
            distance_sq = (
                (pin.rest_position[0] - other.rest_position[0]) ** 2
                + (pin.rest_position[1] - other.rest_position[1]) ** 2
            )
            if distance_sq <= 1e-8:
                coincident_pairs.append([pin.id, other.id])
    return {
        "schema": PUPPET_SCHEMA,
        "vertex_count": len(mesh.vertices),
        "triangle_count": len(mesh.triangles),
        "pin_count": len(mesh.pins),
        "flipped_triangle_count": flipped,
        "degenerate_triangle_count": degenerate,
        "valid": not flipped and not degenerate and not out_of_bounds_pins,
        "stabilization_amount": stable_amount,
        "torn_triangle_count": int(repair["torn_triangle_count"]),
        "repair_required": repair["mode"] != "none",
        "repair": repair,
        "render_safe": bool(repair["render_safe"]),
        "out_of_bounds_pin_ids": out_of_bounds_pins,
        "coincident_pin_pairs": coincident_pairs,
        "contract": "tiger_puppet_mesh_stability_v1",
    }


def deform_puppet_image(
    image,
    mesh: PuppetMesh,
    time_ms: float,
    *,
    composition=None,
):
    """Piecewise-affine warp that preserves the source image alpha channel."""
    if not mesh.enabled or not mesh.pins or image is None or image.isNull():
        return image
    import cv2
    import numpy as np
    from PySide6.QtGui import QImage

    straight = image.convertToFormat(QImage.Format_RGBA8888)
    source = np.frombuffer(straight.constBits(), dtype=np.uint8).reshape(
        straight.height(),
        straight.bytesPerLine(),
    )[:, : straight.width() * 4].reshape(
        straight.height(),
        straight.width(),
        4,
    )
    source = np.ascontiguousarray(source)
    width = max(1, straight.width())
    height = max(1, straight.height())
    source_points = np.asarray(
        [
            (vertex.uv[0] * (width - 1), vertex.uv[1] * (height - 1))
            for vertex in mesh.vertices
        ],
        dtype=np.float32,
    )
    evaluated, _repair = evaluate_puppet_render_vertices(
        mesh,
        time_ms,
        width=width,
        height=height,
        composition=composition,
    )
    depths = evaluate_puppet_depths(mesh)
    destination_points = np.asarray(
        [
            (point[0] * (width - 1), point[1] * (height - 1))
            for point in evaluated
        ],
        dtype=np.float32,
    )
    output = np.zeros_like(source)
    triangles = sorted(
        mesh.triangles,
        key=lambda indices: sum(depths[index] for index in indices) / 3.0,
    )
    for indices in triangles:
        if min(indices) < 0 or max(indices) >= len(source_points):
            continue
        source_triangle = source_points[list(indices)]
        destination_triangle = destination_points[list(indices)]
        sx, sy, sw, sh = cv2.boundingRect(source_triangle)
        dx, dy, dw, dh = cv2.boundingRect(destination_triangle)
        if sw <= 0 or sh <= 0 or dw <= 0 or dh <= 0:
            continue
        sx0, sy0 = max(0, sx), max(0, sy)
        sx1, sy1 = min(width, sx + sw), min(height, sy + sh)
        dx0, dy0 = max(0, dx), max(0, dy)
        dx1, dy1 = min(width, dx + dw), min(height, dy + dh)
        if sx1 <= sx0 or sy1 <= sy0 or dx1 <= dx0 or dy1 <= dy0:
            continue
        source_local = source_triangle - np.asarray([sx0, sy0], dtype=np.float32)
        destination_local = destination_triangle - np.asarray(
            [dx0, dy0],
            dtype=np.float32,
        )
        matrix = cv2.getAffineTransform(source_local, destination_local)
        warped = cv2.warpAffine(
            source[sy0:sy1, sx0:sx1],
            matrix,
            (dx1 - dx0, dy1 - dy0),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )
        mask = np.zeros((dy1 - dy0, dx1 - dx0), dtype=np.uint8)
        cv2.fillConvexPoly(
            mask,
            np.rint(destination_local).astype(np.int32),
            255,
            lineType=cv2.LINE_AA,
        )
        region = output[dy0:dy1, dx0:dx1]
        visible = mask > 0
        region[visible] = warped[visible]
    output = np.ascontiguousarray(output)
    return QImage(
        output.data,
        width,
        height,
        output.strides[0],
        QImage.Format_RGBA8888,
    ).copy().convertToFormat(QImage.Format_RGBA8888_Premultiplied)


__all__ = [
    "PUPPET_METADATA_KEY",
    "PUPPET_PIN_KINDS",
    "PUPPET_SCHEMA",
    "PuppetMesh",
    "PuppetPin",
    "PuppetVertex",
    "add_puppet_pin",
    "bind_puppet_pin_to_rig",
    "configure_puppet_tear_repair",
    "create_grid_puppet_mesh",
    "create_alpha_adaptive_puppet_mesh",
    "delete_puppet_pin",
    "deform_puppet_image",
    "evaluate_puppet_depths",
    "evaluate_puppet_render_vertices",
    "evaluate_puppet_vertices",
    "layer_puppet_mesh",
    "puppet_mesh_diagnostics",
    "repair_puppet_vertices",
    "remove_puppet_mesh",
    "set_layer_puppet_mesh",
    "stabilize_puppet_vertices",
    "update_puppet_pin",
]
