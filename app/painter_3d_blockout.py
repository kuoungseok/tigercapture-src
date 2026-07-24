"""Painter 3D blockout scene primitives and safe projection helpers.

This module is intentionally UI-light.  It gives Painter a deterministic
concept-art blockout data model that can later be shown in a dock/panel without
coupling the feature to ``app.drawing``.

Design guardrails:
- 3D blockout is additive; it must not hide Texture Lab/PBR doorways.
- Layers/Channels/Paths remain primary Painter docks, not optional 3D UI.
- The scene contract is serializable and GPU-friendly so future previews can
  replace the Qt painter preview with accelerated draw packets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, radians, sin, tan
from typing import Any, Iterable, Sequence


Vec3 = tuple[float, float, float]

SUPPORTED_PRIMITIVES = {
    "arch",
    "box",
}


@dataclass(frozen=True)
class BlockoutCamera:
    yaw_degrees: float = 35.0
    pitch_degrees: float = -18.0
    distance: float = 8.5
    target: Vec3 = (0.0, 0.8, 0.0)
    fov_degrees: float = 42.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "yaw_degrees": round(float(self.yaw_degrees), 4),
            "pitch_degrees": round(float(self.pitch_degrees), 4),
            "distance": round(max(0.25, float(self.distance)), 4),
            "target": _vec_to_list(self.target),
            "fov_degrees": round(_clamp(float(self.fov_degrees), 15.0, 90.0), 4),
        }


@dataclass(frozen=True)
class BlockoutPrimitive:
    id: str
    kind: str = "box"
    name: str = ""
    position: Vec3 = (0.0, 0.0, 0.0)
    rotation: Vec3 = (0.0, 0.0, 0.0)
    scale: Vec3 = (1.0, 1.0, 1.0)
    color: str = "#7C8CFF"
    opacity: float = 0.72
    wireframe: bool = True
    locked: bool = False

    def normalized(self) -> "BlockoutPrimitive":
        kind = str(self.kind or "box").strip().lower()
        if kind not in SUPPORTED_PRIMITIVES:
            kind = "box"
        return BlockoutPrimitive(
            id=str(self.id or "").strip() or "blockout:1",
            kind=kind,
            name=str(self.name or "").strip() or kind.title(),
            position=_vec3(self.position),
            rotation=_vec3(self.rotation),
            scale=tuple(max(0.001, abs(v)) for v in _vec3(self.scale)),
            color=_normalize_hex(self.color),
            opacity=_clamp(float(self.opacity), 0.05, 1.0),
            wireframe=bool(self.wireframe),
            locked=bool(self.locked),
        )

    def to_dict(self) -> dict[str, Any]:
        row = self.normalized()
        return {
            "id": row.id,
            "kind": row.kind,
            "name": row.name,
            "position": _vec_to_list(row.position),
            "rotation": _vec_to_list(row.rotation),
            "scale": _vec_to_list(row.scale),
            "color": row.color,
            "opacity": round(row.opacity, 4),
            "wireframe": row.wireframe,
            "locked": row.locked,
        }


@dataclass(frozen=True)
class BlockoutScene:
    schema: str = "tigerstudio.painter.3d_blockout.v1"
    camera: BlockoutCamera = field(default_factory=BlockoutCamera)
    primitives: tuple[BlockoutPrimitive, ...] = ()
    grid_size: float = 1.0
    show_grid: bool = True
    show_wireframe: bool = True
    snap_to_grid: bool = False
    next_index: int = 1

    def normalized(self) -> "BlockoutScene":
        primitives = tuple(p.normalized() for p in self.primitives)
        used = {_primitive_index(p.id) for p in primitives}
        next_index = max([int(self.next_index or 1), *[n + 1 for n in used if n > 0]], default=1)
        return BlockoutScene(
            camera=self.camera,
            primitives=primitives,
            grid_size=max(0.05, float(self.grid_size or 1.0)),
            show_grid=bool(self.show_grid),
            show_wireframe=bool(self.show_wireframe),
            snap_to_grid=bool(self.snap_to_grid),
            next_index=max(1, next_index),
        )

    def to_dict(self) -> dict[str, Any]:
        scene = self.normalized()
        return {
            "schema": scene.schema,
            "camera": scene.camera.to_dict(),
            "primitives": [p.to_dict() for p in scene.primitives],
            "grid_size": round(scene.grid_size, 4),
            "show_grid": scene.show_grid,
            "show_wireframe": scene.show_wireframe,
            "snap_to_grid": scene.snap_to_grid,
            "next_index": int(scene.next_index),
            "primitive_count": len(scene.primitives),
            "supported_primitives": sorted(SUPPORTED_PRIMITIVES),
        }


def default_blockout_scene() -> BlockoutScene:
    """Return the empty Painter 3D blockout scene."""

    return BlockoutScene()


def blockout_scene_from_dict(payload: Any) -> BlockoutScene:
    if isinstance(payload, BlockoutScene):
        return payload.normalized()
    if not isinstance(payload, dict):
        return default_blockout_scene()
    camera_payload = payload.get("camera") if isinstance(payload.get("camera"), dict) else {}
    camera = BlockoutCamera(
        yaw_degrees=float(camera_payload.get("yaw_degrees", 35.0) or 35.0),
        pitch_degrees=float(camera_payload.get("pitch_degrees", -18.0) or -18.0),
        distance=max(0.25, float(camera_payload.get("distance", 8.5) or 8.5)),
        target=_vec3(camera_payload.get("target", (0.0, 0.8, 0.0))),
        fov_degrees=_clamp(float(camera_payload.get("fov_degrees", 42.0) or 42.0), 15.0, 90.0),
    )
    primitives = []
    for row in payload.get("primitives", []) or []:
        if not isinstance(row, dict):
            continue
        primitives.append(
            BlockoutPrimitive(
                id=str(row.get("id") or ""),
                kind=str(row.get("kind") or "box"),
                name=str(row.get("name") or ""),
                position=_vec3(row.get("position", (0.0, 0.0, 0.0))),
                rotation=_vec3(row.get("rotation", (0.0, 0.0, 0.0))),
                scale=_vec3(row.get("scale", (1.0, 1.0, 1.0))),
                color=str(row.get("color") or "#7C8CFF"),
                opacity=float(row.get("opacity", 0.72) or 0.72),
                wireframe=bool(row.get("wireframe", True)),
                locked=bool(row.get("locked", False)),
            )
        )
    return BlockoutScene(
        camera=camera,
        primitives=tuple(primitives),
        grid_size=float(payload.get("grid_size", 1.0) or 1.0),
        show_grid=bool(payload.get("show_grid", True)),
        show_wireframe=bool(payload.get("show_wireframe", True)),
        snap_to_grid=bool(payload.get("snap_to_grid", False)),
        next_index=int(payload.get("next_index", 1) or 1),
    ).normalized()


def update_blockout_camera(scene: BlockoutScene | dict[str, Any], **params: Any) -> BlockoutScene:
    """Update orbit/pan/zoom/FOV camera values for the blockout guide scene."""

    base = blockout_scene_from_dict(scene)
    current = base.camera.to_dict()
    yaw = _param_float(params, "yaw_degrees", current["yaw_degrees"], aliases=("yaw",))
    pitch = _param_float(params, "pitch_degrees", current["pitch_degrees"], aliases=("pitch",))
    distance = _param_float(params, "distance", current["distance"], aliases=("zoom_distance", "camera_distance"))
    fov = _param_float(params, "fov_degrees", current["fov_degrees"], aliases=("fov",))
    target = list(_vec3(current["target"]))
    target[0] = _param_float(params, "target_x", target[0], aliases=("tx", "pan_x"))
    target[1] = _param_float(params, "target_y", target[1], aliases=("ty", "pan_y"))
    target[2] = _param_float(params, "target_z", target[2], aliases=("tz", "pan_z"))
    camera = BlockoutCamera(
        yaw_degrees=yaw,
        pitch_degrees=pitch,
        distance=max(0.25, distance),
        target=_vec3(target),
        fov_degrees=_clamp(fov, 15.0, 90.0),
    )
    return BlockoutScene(
        camera=camera,
        primitives=base.primitives,
        grid_size=base.grid_size,
        show_grid=base.show_grid,
        show_wireframe=base.show_wireframe,
        snap_to_grid=base.snap_to_grid,
        next_index=base.next_index,
    ).normalized()


def add_blockout_primitive(scene: BlockoutScene | dict[str, Any] | None, **params: Any) -> BlockoutScene:
    base = blockout_scene_from_dict(scene)
    primitive_id = str(params.get("primitive_id") or "").strip() or f"blockout:{base.next_index}"
    if any(p.id == primitive_id for p in base.primitives):
        raise ValueError(f"3D blockout primitive already exists: {primitive_id}")
    primitive = _primitive_from_params(primitive_id, params)
    return BlockoutScene(
        camera=base.camera,
        primitives=(*base.primitives, primitive),
        grid_size=base.grid_size,
        show_grid=base.show_grid,
        show_wireframe=base.show_wireframe,
        snap_to_grid=base.snap_to_grid,
        next_index=max(base.next_index + 1, _primitive_index(primitive_id) + 1),
    ).normalized()


def update_blockout_primitive(scene: BlockoutScene | dict[str, Any], primitive_id: str, **params: Any) -> BlockoutScene:
    base = blockout_scene_from_dict(scene)
    wanted = str(primitive_id or "").strip()
    updated: list[BlockoutPrimitive] = []
    found = False
    for primitive in base.primitives:
        if primitive.id != wanted:
            updated.append(primitive)
            continue
        found = True
        merged = primitive.to_dict()
        _apply_param_updates(merged, params)
        updated.append(
            BlockoutPrimitive(
                id=primitive.id,
                kind=str(merged["kind"]),
                name=str(merged["name"]),
                position=_vec3(merged["position"]),
                rotation=_vec3(merged["rotation"]),
                scale=_vec3(merged["scale"]),
                color=str(merged["color"]),
                opacity=float(merged["opacity"]),
                wireframe=bool(merged["wireframe"]),
                locked=bool(merged["locked"]),
            ).normalized()
        )
    if not found:
        raise ValueError(f"3D blockout primitive not found: {wanted}")
    return BlockoutScene(
        camera=base.camera,
        primitives=tuple(updated),
        grid_size=base.grid_size,
        show_grid=base.show_grid,
        show_wireframe=base.show_wireframe,
        snap_to_grid=base.snap_to_grid,
        next_index=base.next_index,
    ).normalized()


def delete_blockout_primitive(scene: BlockoutScene | dict[str, Any], primitive_id: str) -> BlockoutScene:
    base = blockout_scene_from_dict(scene)
    wanted = str(primitive_id or "").strip()
    remaining = tuple(p for p in base.primitives if p.id != wanted)
    if len(remaining) == len(base.primitives):
        raise ValueError(f"3D blockout primitive not found: {wanted}")
    return BlockoutScene(
        camera=base.camera,
        primitives=remaining,
        grid_size=base.grid_size,
        show_grid=base.show_grid,
        show_wireframe=base.show_wireframe,
        snap_to_grid=base.snap_to_grid,
        next_index=base.next_index,
    ).normalized()


def duplicate_blockout_primitive(
    scene: BlockoutScene | dict[str, Any],
    primitive_id: str,
    *,
    offset: Vec3 = (0.65, 0.0, 0.25),
) -> BlockoutScene:
    base = blockout_scene_from_dict(scene)
    wanted = str(primitive_id or "").strip()
    source = next((p for p in base.primitives if p.id == wanted), None)
    if source is None:
        raise ValueError(f"3D blockout primitive not found: {wanted}")
    new_id = f"blockout:{base.next_index}"
    px, py, pz = source.position
    ox, oy, oz = _vec3(offset)
    duplicated = BlockoutPrimitive(
        id=new_id,
        kind=source.kind,
        name=f"{source.name} Copy",
        position=(px + ox, py + oy, pz + oz),
        rotation=source.rotation,
        scale=source.scale,
        color=source.color,
        opacity=source.opacity,
        wireframe=source.wireframe,
        locked=source.locked,
    ).normalized()
    return BlockoutScene(
        camera=base.camera,
        primitives=(*base.primitives, duplicated),
        grid_size=base.grid_size,
        show_grid=base.show_grid,
        show_wireframe=base.show_wireframe,
        snap_to_grid=base.snap_to_grid,
        next_index=max(base.next_index + 1, _primitive_index(new_id) + 1),
    ).normalized()


def align_blockout_primitive_to_ground(scene: BlockoutScene | dict[str, Any], primitive_id: str) -> BlockoutScene:
    base = blockout_scene_from_dict(scene)
    wanted = str(primitive_id or "").strip()
    updated: list[BlockoutPrimitive] = []
    found = False
    for primitive in base.primitives:
        if primitive.id != wanted:
            updated.append(primitive)
            continue
        found = True
        sx, sy, sz = primitive.scale
        px, _py, pz = primitive.position
        ground_y = 0.0 if primitive.kind == "arch" else sy * 0.5
        updated.append(
            BlockoutPrimitive(
                id=primitive.id,
                kind=primitive.kind,
                name=primitive.name,
                position=(px, ground_y, pz),
                rotation=primitive.rotation,
                scale=(sx, sy, sz),
                color=primitive.color,
                opacity=primitive.opacity,
                wireframe=primitive.wireframe,
                locked=primitive.locked,
            ).normalized()
        )
    if not found:
        raise ValueError(f"3D blockout primitive not found: {wanted}")
    return BlockoutScene(
        camera=base.camera,
        primitives=tuple(updated),
        grid_size=base.grid_size,
        show_grid=base.show_grid,
        show_wireframe=base.show_wireframe,
        snap_to_grid=base.snap_to_grid,
        next_index=base.next_index,
    ).normalized()


def snap_blockout_primitive_to_grid(
    scene: BlockoutScene | dict[str, Any],
    primitive_id: str,
    *,
    grid_size: float | None = None,
) -> BlockoutScene:
    base = blockout_scene_from_dict(scene)
    wanted = str(primitive_id or "").strip()
    step = max(0.05, float(grid_size if grid_size is not None else base.grid_size))
    updated: list[BlockoutPrimitive] = []
    found = False
    for primitive in base.primitives:
        if primitive.id != wanted:
            updated.append(primitive)
            continue
        found = True
        updated.append(
            BlockoutPrimitive(
                id=primitive.id,
                kind=primitive.kind,
                name=primitive.name,
                position=tuple(_snap_value(v, step) for v in primitive.position),
                rotation=tuple(_snap_value(v, 5.0) for v in primitive.rotation),
                scale=tuple(max(0.001, _snap_value(v, step)) for v in primitive.scale),
                color=primitive.color,
                opacity=primitive.opacity,
                wireframe=primitive.wireframe,
                locked=primitive.locked,
            ).normalized()
        )
    if not found:
        raise ValueError(f"3D blockout primitive not found: {wanted}")
    return BlockoutScene(
        camera=base.camera,
        primitives=tuple(updated),
        grid_size=base.grid_size,
        show_grid=base.show_grid,
        show_wireframe=base.show_wireframe,
        snap_to_grid=base.snap_to_grid,
        next_index=base.next_index,
    ).normalized()


def set_blockout_snap(scene: BlockoutScene | dict[str, Any], enabled: bool) -> BlockoutScene:
    base = blockout_scene_from_dict(scene)
    return BlockoutScene(
        camera=base.camera,
        primitives=base.primitives,
        grid_size=base.grid_size,
        show_grid=base.show_grid,
        show_wireframe=base.show_wireframe,
        snap_to_grid=bool(enabled),
        next_index=base.next_index,
    ).normalized()


def apply_blockout_camera_preset(scene: BlockoutScene | dict[str, Any], preset: str) -> BlockoutScene:
    key = str(preset or "perspective").strip().lower().replace("-", "_")
    if key in {"front", "front_view"}:
        return update_blockout_camera(scene, yaw_degrees=0.0, pitch_degrees=0.0, distance=7.0, fov_degrees=35.0)
    if key in {"side", "right", "side_view"}:
        return update_blockout_camera(scene, yaw_degrees=90.0, pitch_degrees=0.0, distance=7.0, fov_degrees=35.0)
    if key in {"top", "top_view"}:
        return update_blockout_camera(scene, yaw_degrees=0.0, pitch_degrees=-82.0, distance=8.0, fov_degrees=45.0)
    return update_blockout_camera(scene, yaw_degrees=35.0, pitch_degrees=-18.0, distance=8.5, fov_degrees=42.0)


def project_blockout_scene(scene: BlockoutScene | dict[str, Any], width: int = 640, height: int = 360) -> dict[str, Any]:
    """Project a 3D blockout scene to serializable 2D faces/edges."""

    normalized = blockout_scene_from_dict(scene)
    w = max(1, int(width or 1))
    h = max(1, int(height or 1))
    faces: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for primitive in normalized.primitives:
        mesh = _mesh_for_primitive(primitive)
        transformed = [_transform_local_vertex(vertex, primitive) for vertex in mesh["vertices"]]
        projected = [_project_point(vertex, normalized.camera, w, h) for vertex in transformed]
        for face_index, face in enumerate(mesh["faces"]):
            points = [projected[index] for index in face]
            if any(point is None for point in points):
                continue
            depth = sum(projected[index]["depth"] for index in face if projected[index] is not None) / len(face)
            screen_points = [(round(p["x"], 3), round(p["y"], 3)) for p in points if p is not None]
            faces.append(
                {
                    "primitive_id": primitive.id,
                    "kind": primitive.kind,
                    "face_index": face_index,
                    "points": screen_points,
                    "depth": round(depth, 5),
                    "color": primitive.color,
                    "opacity": round(primitive.opacity, 4),
                }
            )
            if primitive.wireframe or normalized.show_wireframe:
                for a, b in _face_edges(face):
                    pa = projected[a]
                    pb = projected[b]
                    if pa is None or pb is None:
                        continue
                    edge = {
                        "primitive_id": primitive.id,
                        "a": (round(pa["x"], 3), round(pa["y"], 3)),
                        "b": (round(pb["x"], 3), round(pb["y"], 3)),
                        "depth": round((pa["depth"] + pb["depth"]) * 0.5, 5),
                    }
                    if edge not in edges:
                        edges.append(edge)
    faces.sort(key=lambda row: row["depth"], reverse=True)
    edges.sort(key=lambda row: row["depth"], reverse=True)
    return {
        "schema": "tigerstudio.painter.3d_blockout.projection.v1",
        "viewport": {"width": w, "height": h},
        "scene": normalized.to_dict(),
        "faces": faces,
        "edges": edges,
        "face_count": len(faces),
        "edge_count": len(edges),
    }


def render_blockout_scene_qimage(scene: BlockoutScene | dict[str, Any], width: int = 640, height: int = 360):
    """Render a lightweight preview QImage for tests and future UI panels."""

    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

    w = max(1, int(width or 1))
    h = max(1, int(height or 1))
    image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    projection = project_blockout_scene(scene, w, h)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)
        if projection["scene"].get("show_grid"):
            painter.setPen(QPen(QColor(210, 220, 255, 36), 1, Qt.DashLine))
            step = max(24, int(min(w, h) / 10))
            for x in range(w // 2 % step, w, step):
                painter.drawLine(x, 0, x, h)
            for y in range(h // 2 % step, h, step):
                painter.drawLine(0, y, w, y)
        for face in projection["faces"]:
            color = QColor(str(face["color"]))
            color.setAlphaF(_clamp(float(face["opacity"]), 0.05, 1.0))
            polygon = QPolygonF([QPointF(float(x), float(y)) for x, y in face["points"]])
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawPolygon(polygon)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(245, 248, 255, 180), 1.1))
        for edge in projection["edges"]:
            ax, ay = edge["a"]
            bx, by = edge["b"]
            painter.drawLine(QPointF(float(ax), float(ay)), QPointF(float(bx), float(by)))
    finally:
        painter.end()
    return image


def _primitive_from_params(primitive_id: str, params: dict[str, Any]) -> BlockoutPrimitive:
    kind = _supported_kind(params.get("kind"))
    return BlockoutPrimitive(
        id=primitive_id,
        kind=kind,
        name=str(params.get("name") or kind.title()),
        position=_params_vec(params, "x", "y", "z", (0.0, 0.0, 0.0)),
        rotation=_params_vec(params, "rx", "ry", "rz", (0.0, 0.0, 0.0)),
        scale=_params_vec(params, "sx", "sy", "sz", _default_scale_for_kind(kind)),
        color=str(params.get("color") or "#7C8CFF"),
        opacity=float(params.get("opacity", 0.72) or 0.72),
        wireframe=bool(params.get("wireframe", True)),
        locked=bool(params.get("locked", False)),
    ).normalized()


def _apply_param_updates(payload: dict[str, Any], params: dict[str, Any]) -> None:
    if params.get("kind") is not None:
        payload["kind"] = _supported_kind(params.get("kind"))
    for key in ("name", "color", "opacity", "wireframe", "locked"):
        if params.get(key) is not None:
            payload[key] = params[key]
    for group, keys in (("position", ("x", "y", "z")), ("rotation", ("rx", "ry", "rz")), ("scale", ("sx", "sy", "sz"))):
        current = list(_vec3(payload.get(group)))
        changed = False
        for index, key in enumerate(keys):
            if params.get(key) is None:
                continue
            current[index] = float(params[key])
            changed = True
        if changed:
            payload[group] = current


def _mesh_for_primitive(primitive: BlockoutPrimitive) -> dict[str, Any]:
    if primitive.normalized().kind == "arch":
        return _compound_boxes([(-0.42, 0.5, 0.0, 0.16, 1.0, 0.2), (0.42, 0.5, 0.0, 0.16, 1.0, 0.2), (0.0, 0.98, 0.0, 1.0, 0.18, 0.2)])
    return _box_mesh((1.0, 1.0, 1.0))


def _box_mesh(size: Vec3) -> dict[str, Any]:
    sx, sy, sz = (v * 0.5 for v in size)
    vertices = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz), (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    return {"vertices": vertices, "faces": faces}


def _compound_boxes(parts: Iterable[tuple[float, float, float, float, float, float]]) -> dict[str, Any]:
    vertices: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    for cx, cy, cz, sx, sy, sz in parts:
        mesh = _box_mesh((sx, sy, sz))
        offset = len(vertices)
        vertices.extend((x + cx, y + cy, z + cz) for x, y, z in mesh["vertices"])
        faces.extend(tuple(index + offset for index in face) for face in mesh["faces"])
    return {"vertices": vertices, "faces": faces}


def _transform_local_vertex(vertex: Vec3, primitive: BlockoutPrimitive) -> Vec3:
    sx, sy, sz = primitive.scale
    x, y, z = vertex[0] * sx, vertex[1] * sy, vertex[2] * sz
    x, y, z = _rotate_xyz((x, y, z), primitive.rotation)
    px, py, pz = primitive.position
    return (x + px, y + py, z + pz)


def _rotate_xyz(point: Vec3, rotation: Vec3) -> Vec3:
    x, y, z = point
    rx, ry, rz = (radians(v) for v in rotation)
    cy, sy = cos(rx), sin(rx)
    y, z = y * cy - z * sy, y * sy + z * cy
    cy, sy = cos(ry), sin(ry)
    x, z = x * cy + z * sy, -x * sy + z * cy
    cy, sy = cos(rz), sin(rz)
    x, y = x * cy - y * sy, x * sy + y * cy
    return (x, y, z)


def _project_point(point: Vec3, camera: BlockoutCamera, width: int, height: int) -> dict[str, float] | None:
    x, y, z = point[0] - camera.target[0], point[1] - camera.target[1], point[2] - camera.target[2]
    yaw = radians(-camera.yaw_degrees)
    x, z = x * cos(yaw) + z * sin(yaw), -x * sin(yaw) + z * cos(yaw)
    pitch = radians(-camera.pitch_degrees)
    y, z = y * cos(pitch) - z * sin(pitch), y * sin(pitch) + z * cos(pitch)
    z += max(0.25, float(camera.distance))
    if z <= 0.04:
        return None
    focal = 0.5 * min(width, height) / tan(radians(_clamp(camera.fov_degrees, 15.0, 90.0)) * 0.5)
    return {"x": width * 0.5 + x * focal / z, "y": height * 0.5 - y * focal / z, "depth": z}


def _face_edges(face: Sequence[int]) -> list[tuple[int, int]]:
    return [(int(face[index]), int(face[(index + 1) % len(face)])) for index in range(len(face))]


def _params_vec(params: dict[str, Any], x_key: str, y_key: str, z_key: str, default: Vec3) -> Vec3:
    if all(params.get(key) is None for key in (x_key, y_key, z_key)):
        return default
    return (
        float(params.get(x_key, default[0]) if params.get(x_key) is not None else default[0]),
        float(params.get(y_key, default[1]) if params.get(y_key) is not None else default[1]),
        float(params.get(z_key, default[2]) if params.get(z_key) is not None else default[2]),
    )


def _default_scale_for_kind(kind: str) -> Vec3:
    if _supported_kind(kind) == "arch":
        return (2.2, 2.4, 0.8)
    return (1.0, 1.0, 1.0)


def _supported_kind(value: Any) -> str:
    kind = str(value or "box").strip().lower()
    return kind if kind in SUPPORTED_PRIMITIVES else "box"


def _vec3(value: Any) -> Vec3:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        row = list(value)[:3]
        while len(row) < 3:
            row.append(0.0)
        return (float(row[0] or 0.0), float(row[1] or 0.0), float(row[2] or 0.0))
    return (0.0, 0.0, 0.0)


def _vec_to_list(value: Vec3) -> list[float]:
    return [round(float(value[0]), 4), round(float(value[1]), 4), round(float(value[2]), 4)]


def _primitive_index(primitive_id: str) -> int:
    text = str(primitive_id or "")
    if ":" not in text:
        return 0
    try:
        return int(text.rsplit(":", 1)[1])
    except Exception:
        return 0


def _normalize_hex(value: Any) -> str:
    text = str(value or "#7C8CFF").strip()
    if len(text) == 7 and text.startswith("#"):
        return text.upper()
    return "#7C8CFF"


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _snap_value(value: float, step: float) -> float:
    safe_step = max(0.0001, float(step or 1.0))
    return round(round(float(value) / safe_step) * safe_step, 4)


def _param_float(params: dict[str, Any], key: str, default: float, *, aliases: Sequence[str] = ()) -> float:
    for candidate in (key, *aliases):
        if params.get(candidate) is not None:
            return float(params[candidate])
    return float(default)


__all__ = [
    "BlockoutCamera",
    "BlockoutPrimitive",
    "BlockoutScene",
    "SUPPORTED_PRIMITIVES",
    "add_blockout_primitive",
    "align_blockout_primitive_to_ground",
    "apply_blockout_camera_preset",
    "blockout_scene_from_dict",
    "default_blockout_scene",
    "delete_blockout_primitive",
    "duplicate_blockout_primitive",
    "project_blockout_scene",
    "render_blockout_scene_qimage",
    "set_blockout_snap",
    "snap_blockout_primitive_to_grid",
    "update_blockout_camera",
    "update_blockout_primitive",
]
