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

from dataclasses import dataclass, field, replace
from math import cos, floor, pi, radians, sin, tan
from typing import Any, Iterable, Sequence


Vec3 = tuple[float, float, float]

SUPPORTED_PRIMITIVES = {
    "arch",
    "box",
    "cone",
    "cylinder",
    "plane",
    "sphere",
}


@dataclass(frozen=True)
class BlockoutCamera:
    yaw_degrees: float = 35.0
    pitch_degrees: float = -18.0
    distance: float = 8.5
    target: Vec3 = (0.0, 0.0, 0.8)
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
    color: str = "#F2F2F2"
    opacity: float = 1.0
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
    show_floor: bool = True
    material_lit: bool = True
    show_shadows: bool = True
    show_fog: bool = False
    show_depth: bool = False
    light_yaw_degrees: float = 45.0
    light_pitch_degrees: float = 45.0
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
            show_floor=bool(self.show_floor),
            material_lit=bool(self.material_lit),
            show_shadows=bool(self.show_shadows),
            show_fog=bool(self.show_fog),
            show_depth=bool(self.show_depth),
            light_yaw_degrees=float(self.light_yaw_degrees) % 360.0,
            light_pitch_degrees=_clamp(float(self.light_pitch_degrees), 5.0, 85.0),
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
            "show_floor": scene.show_floor,
            "material_lit": scene.material_lit,
            "show_shadows": scene.show_shadows,
            "show_fog": scene.show_fog,
            "show_depth": scene.show_depth,
            "light_yaw_degrees": round(scene.light_yaw_degrees, 4),
            "light_pitch_degrees": round(scene.light_pitch_degrees, 4),
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
        target=_vec3(camera_payload.get("target", (0.0, 0.0, 0.8))),
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
                color=str(row.get("color") or "#F2F2F2"),
                opacity=float(row.get("opacity", 1.0) or 1.0),
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
        show_floor=bool(payload.get("show_floor", True)),
        material_lit=bool(payload.get("material_lit", True)),
        show_shadows=bool(payload.get("show_shadows", True)),
        show_fog=bool(payload.get("show_fog", False)),
        show_depth=bool(payload.get("show_depth", False)),
        light_yaw_degrees=float(payload.get("light_yaw_degrees", 45.0) or 45.0),
        light_pitch_degrees=float(payload.get("light_pitch_degrees", 45.0) or 45.0),
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
    return replace(base, camera=camera).normalized()


def add_blockout_primitive(scene: BlockoutScene | dict[str, Any] | None, **params: Any) -> BlockoutScene:
    base = blockout_scene_from_dict(scene)
    primitive_id = str(params.get("primitive_id") or "").strip() or f"blockout:{base.next_index}"
    if any(p.id == primitive_id for p in base.primitives):
        raise ValueError(f"3D blockout primitive already exists: {primitive_id}")
    primitive = _primitive_from_params(primitive_id, params)
    return replace(
        base,
        primitives=(*base.primitives, primitive),
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
    return replace(
        base,
        primitives=tuple(updated),
    ).normalized()


def delete_blockout_primitive(scene: BlockoutScene | dict[str, Any], primitive_id: str) -> BlockoutScene:
    base = blockout_scene_from_dict(scene)
    wanted = str(primitive_id or "").strip()
    remaining = tuple(p for p in base.primitives if p.id != wanted)
    if len(remaining) == len(base.primitives):
        raise ValueError(f"3D blockout primitive not found: {wanted}")
    return replace(
        base,
        primitives=remaining,
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
    return replace(
        base,
        primitives=(*base.primitives, duplicated),
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
        px, py, _pz = primitive.position
        ground_z = 0.0 if primitive.kind == "arch" else sz * 0.5
        updated.append(
            BlockoutPrimitive(
                id=primitive.id,
                kind=primitive.kind,
                name=primitive.name,
                position=(px, py, ground_z),
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
    return replace(
        base,
        primitives=tuple(updated),
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
    return replace(
        base,
        primitives=tuple(updated),
    ).normalized()


def set_blockout_snap(scene: BlockoutScene | dict[str, Any], enabled: bool) -> BlockoutScene:
    base = blockout_scene_from_dict(scene)
    return replace(base, snap_to_grid=bool(enabled)).normalized()


def apply_blockout_camera_preset(scene: BlockoutScene | dict[str, Any], preset: str) -> BlockoutScene:
    key = str(preset or "perspective").strip().lower().replace("-", "_")
    if key in {"front", "front_view"}:
        return update_blockout_camera(scene, yaw_degrees=0.0, pitch_degrees=0.0, distance=7.0, fov_degrees=35.0)
    if key in {"side", "right", "side_view"}:
        return update_blockout_camera(scene, yaw_degrees=90.0, pitch_degrees=0.0, distance=7.0, fov_degrees=35.0)
    if key in {"top", "top_view"}:
        return update_blockout_camera(scene, yaw_degrees=0.0, pitch_degrees=-82.0, distance=8.0, fov_degrees=45.0)
    return update_blockout_camera(scene, yaw_degrees=35.0, pitch_degrees=-18.0, distance=8.5, fov_degrees=42.0)


def screen_to_blockout_ground(
    scene: BlockoutScene | dict[str, Any],
    screen_x: float,
    screen_y: float,
    width: int,
    height: int,
) -> Vec3:
    """Unproject a canvas point to the Z-up blockout ground plane."""

    normalized = blockout_scene_from_dict(scene)
    camera = normalized.camera
    w = max(1, int(width or 1))
    h = max(1, int(height or 1))
    focal = 0.5 * min(w, h) / tan(radians(_clamp(camera.fov_degrees, 15.0, 90.0)) * 0.5)
    ray_camera = (
        (float(screen_x) - w * 0.5) / focal,
        1.0,
        (h * 0.5 - float(screen_y)) / focal,
    )
    origin_camera = (0.0, -max(0.25, float(camera.distance)), 0.0)
    origin_relative = _camera_to_world_vector(origin_camera, camera)
    ray_world = _normalized(_camera_to_world_vector(ray_camera, camera))
    origin_world = (
        origin_relative[0] + camera.target[0],
        origin_relative[1] + camera.target[1],
        origin_relative[2] + camera.target[2],
    )
    if abs(ray_world[2]) < 0.00001:
        return (camera.target[0], camera.target[1], 0.0)
    distance = -origin_world[2] / ray_world[2]
    if distance <= 0.0:
        return (camera.target[0], camera.target[1], 0.0)
    return (
        origin_world[0] + ray_world[0] * distance,
        origin_world[1] + ray_world[1] * distance,
        0.0,
    )


def project_blockout_scene(scene: BlockoutScene | dict[str, Any], width: int = 640, height: int = 360) -> dict[str, Any]:
    """Project a 3D blockout scene to serializable 2D faces/edges."""

    normalized = blockout_scene_from_dict(scene)
    w = max(1, int(width or 1))
    h = max(1, int(height or 1))
    faces: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    shadows: list[dict[str, Any]] = []
    floor_tiles = _project_world_checker_floor(normalized, w, h) if normalized.show_floor else []
    light_direction = _direction_from_angles(
        normalized.light_yaw_degrees,
        normalized.light_pitch_degrees,
    )
    for primitive in normalized.primitives:
        mesh = _mesh_for_primitive(primitive)
        transformed = [_transform_local_vertex(vertex, primitive) for vertex in mesh["vertices"]]
        projected = [_project_point(vertex, normalized.camera, w, h) for vertex in transformed]
        if normalized.show_shadows and primitive.kind != "plane":
            light_z = float(light_direction[2])
            ground_world: list[Vec3] = []
            for vertex in transformed:
                height_above_ground = max(0.0, float(vertex[2]))
                cast_scale = height_above_ground / max(0.12, abs(light_z))
                ground_world.append(
                    (
                        float(vertex[0]) - float(light_direction[0]) * cast_scale,
                        float(vertex[1]) - float(light_direction[1]) * cast_scale,
                        0.006,
                    )
                )
            ground_points = [
                _project_point(vertex, normalized.camera, w, h)
                for vertex in ground_world
            ]
            visible_ground = [point for point in ground_points if point is not None]
            if visible_ground:
                xs = [float(point["x"]) for point in visible_ground]
                ys = [float(point["y"]) for point in visible_ground]
                hull = _convex_hull_2d(
                    [(float(point["x"]), float(point["y"])) for point in visible_ground]
                )
                shadows.append(
                    {
                        "primitive_id": primitive.id,
                        "kind": primitive.kind,
                        "polygon": [(round(x, 3), round(y, 3)) for x, y in hull],
                        "point_depths": [
                            round(float(point["depth"]), 5) for point in visible_ground
                        ],
                        "depth": round(
                            sum(float(point["depth"]) for point in visible_ground)
                            / len(visible_ground),
                            5,
                        ),
                        "rect": [
                            round(min(xs), 3),
                            round(min(ys), 3),
                            round(max(6.0, max(xs) - min(xs)), 3),
                            round(max(4.0, max(ys) - min(ys)), 3),
                        ],
                        "opacity": round(min(0.34, 0.16 + primitive.opacity * 0.16), 4),
                    }
                )
        for face_index, face in enumerate(mesh["faces"]):
            points = [projected[index] for index in face]
            if any(point is None for point in points):
                continue
            depth = sum(projected[index]["depth"] for index in face if projected[index] is not None) / len(face)
            screen_points = [(round(p["x"], 3), round(p["y"], 3)) for p in points if p is not None]
            shade = 1.0
            if normalized.material_lit and len(face) >= 3:
                a, b, c = (transformed[index] for index in face[:3])
                normal = _normalized(_cross(_subtract(b, a), _subtract(c, a)))
                diffuse = abs(_dot(normal, light_direction))
                shade = 0.38 + 0.62 * diffuse
            faces.append(
                {
                    "primitive_id": primitive.id,
                    "kind": primitive.kind,
                    "face_index": face_index,
                    "points": screen_points,
                    "point_depths": [
                        round(float(projected[index]["depth"]), 5)
                        for index in face
                        if projected[index] is not None
                    ],
                    "depth": round(depth, 5),
                    "color": primitive.color,
                    "opacity": round(primitive.opacity, 4),
                    "shade": round(shade, 4),
                    "depth_preview": normalized.show_depth,
                    "fog": round(
                        _clamp(
                            (depth - normalized.camera.distance * 0.6)
                            / max(0.25, normalized.camera.distance * 1.8),
                            0.0,
                            0.58,
                        )
                        if normalized.show_fog
                        else 0.0,
                        4,
                    ),
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
    if faces:
        near_depth = min(float(row["depth"]) for row in faces)
        far_depth = max(float(row["depth"]) for row in faces)
        depth_span = max(0.0001, far_depth - near_depth)
        for row in faces:
            normalized_depth = (float(row["depth"]) - near_depth) / depth_span
            row["depth_value"] = round(1.0 - normalized_depth * 0.78, 4)
    faces.sort(key=lambda row: row["depth"], reverse=True)
    edges.sort(key=lambda row: row["depth"], reverse=True)
    all_depths = [
        float(depth)
        for row in [*floor_tiles, *shadows, *faces]
        for depth in (row.get("point_depths") or [row.get("depth", 0.0)])
    ]
    return {
        "schema": "tigerstudio.painter.3d_blockout.projection.v1",
        "viewport": {"width": w, "height": h},
        "scene": normalized.to_dict(),
        "floor_tiles": floor_tiles,
        "shadows": shadows,
        "faces": faces,
        "edges": edges,
        "depth_range": {
            "near": min(all_depths, default=0.05),
            "far": max(all_depths, default=max(1.0, normalized.camera.distance * 2.0)),
        },
        "face_count": len(faces),
        "edge_count": len(edges),
    }


def project_blockout_world_point(
    scene: BlockoutScene | dict[str, Any],
    point: Vec3,
    width: int,
    height: int,
) -> dict[str, float] | None:
    """Project one world point through the same camera used by the preview."""

    normalized = blockout_scene_from_dict(scene)
    projected = _project_point(
        _vec3(point),
        normalized.camera,
        max(1, int(width or 1)),
        max(1, int(height or 1)),
    )
    if projected is None:
        return None
    return {
        "x": float(projected["x"]),
        "y": float(projected["y"]),
        "depth": float(projected["depth"]),
    }


def render_blockout_scene_qimage(scene: BlockoutScene | dict[str, Any], width: int = 640, height: int = 360):
    """Render a lightweight preview QImage for tests and future UI panels."""

    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

    w = max(1, int(width or 1))
    h = max(1, int(height or 1))
    image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    projection = project_blockout_scene(scene, w, h)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)
        for tile in projection.get("floor_tiles", []):
            polygon = QPolygonF(
                [QPointF(float(x), float(y)) for x, y in tile.get("points", [])]
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(str(tile.get("color") or "#707276")))
            painter.drawPolygon(polygon)
        if projection["scene"].get("show_grid") and not projection["scene"].get("show_floor"):
            painter.setPen(QPen(QColor(210, 220, 255, 36), 1, Qt.DashLine))
            step = max(24, int(min(w, h) / 10))
            for x in range(w // 2 % step, w, step):
                painter.drawLine(x, 0, x, h)
            for y in range(h // 2 % step, h, step):
                painter.drawLine(0, y, w, y)
        for shadow in projection.get("shadows", []):
            x, y, width, height = shadow["rect"]
            opacity = _clamp(float(shadow.get("opacity", 0.25)), 0.0, 0.5)
            polygon_points = [
                QPointF(float(px), float(py))
                for px, py in shadow.get("polygon", []) or []
            ]
            if len(polygon_points) >= 3:
                polygon = QPolygonF(polygon_points)
                center = polygon.boundingRect().center()
                for scale, alpha_scale in ((1.12, 0.28), (1.05, 0.5), (1.0, 0.9)):
                    softened = QPolygonF(
                        [
                            QPointF(
                                center.x() + (point.x() - center.x()) * scale,
                                center.y() + (point.y() - center.y()) * scale,
                            )
                            for point in polygon
                        ]
                    )
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(0, 0, 0, int(255 * opacity * alpha_scale)))
                    painter.drawPolygon(softened)
                continue
            for inset, alpha_scale in ((0.0, 0.35), (2.0, 0.55), (5.0, 1.0)):
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(0, 0, 0, int(255 * opacity * alpha_scale)))
                painter.drawEllipse(
                    QRectF(
                        float(x) + inset,
                        float(y) + inset * 0.45,
                        max(1.0, float(width) - inset * 2.0),
                        max(1.0, float(height) - inset * 0.9),
                    )
                )
        for face in projection["faces"]:
            if bool(projection["scene"].get("show_depth", False)):
                value = int(255 * _clamp(float(face.get("depth_value", 1.0)), 0.0, 1.0))
                color = QColor(value, value, value)
            else:
                color = QColor(str(face["color"]))
            shade = _clamp(float(face.get("shade", 1.0)), 0.0, 1.0)
            if not bool(projection["scene"].get("show_depth", False)):
                color.setRed(int(color.red() * shade))
                color.setGreen(int(color.green() * shade))
                color.setBlue(int(color.blue() * shade))
            fog = (
                0.0
                if bool(projection["scene"].get("show_depth", False))
                else _clamp(float(face.get("fog", 0.0)), 0.0, 0.75)
            )
            color.setRed(int(color.red() * (1.0 - fog) + 58 * fog))
            color.setGreen(int(color.green() * (1.0 - fog) + 60 * fog))
            color.setBlue(int(color.blue() * (1.0 - fog) + 63 * fog))
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


def _project_world_checker_floor(
    scene: BlockoutScene,
    width: int,
    height: int,
    *,
    tile_size: float = 1.0,
    radius: int = 14,
) -> list[dict[str, Any]]:
    """Project a world-aligned checker whose tile size ignores actor scale."""

    size = max(0.05, float(tile_size))
    center_x = floor(scene.camera.target[0] / size) * size
    center_y = floor(scene.camera.target[1] / size) * size
    tiles: list[dict[str, Any]] = []
    for tile_y in range(-radius, radius):
        for tile_x in range(-radius, radius):
            x0 = center_x + tile_x * size
            y0 = center_y + tile_y * size
            corners = (
                (x0, y0, 0.0),
                (x0 + size, y0, 0.0),
                (x0 + size, y0 + size, 0.0),
                (x0, y0 + size, 0.0),
            )
            camera_points = [_world_to_camera_point(point, scene.camera) for point in corners]
            clipped = _clip_camera_polygon_near(camera_points, near=0.06)
            if len(clipped) < 3:
                continue
            projected = [_project_camera_point(point, scene.camera, width, height) for point in clipped]
            points = [
                (round(float(point["x"]), 3), round(float(point["y"]), 3))
                for point in projected
            ]
            if not points:
                continue
            depth = sum(float(point["depth"]) for point in projected) / len(projected)
            tiles.append(
                {
                    "points": points,
                    "point_depths": [
                        round(float(point["depth"]), 5) for point in projected
                    ],
                    "depth": round(depth, 5),
                    "color": "#74767A" if (tile_x + tile_y) % 2 == 0 else "#606266",
                    "world_tile_size": size,
                    "world_origin": [round(x0, 4), round(y0, 4), 0.0],
                }
            )
    tiles.sort(key=lambda row: float(row["depth"]), reverse=True)
    return tiles


def _convex_hull_2d(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Return a stable screen-space hull for projected ground shadows."""

    unique = sorted(set((float(x), float(y)) for x, y in points))
    if len(unique) <= 2:
        return unique

    def cross(
        origin: tuple[float, float],
        a: tuple[float, float],
        b: tuple[float, float],
    ) -> float:
        return (a[0] - origin[0]) * (b[1] - origin[1]) - (
            a[1] - origin[1]
        ) * (b[0] - origin[0])

    lower: list[tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0.0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0.0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _primitive_from_params(primitive_id: str, params: dict[str, Any]) -> BlockoutPrimitive:
    kind = _supported_kind(params.get("kind"))
    return BlockoutPrimitive(
        id=primitive_id,
        kind=kind,
        name=str(params.get("name") or kind.title()),
        position=_params_vec(params, "x", "y", "z", (0.0, 0.0, 0.0)),
        rotation=_params_vec(params, "rx", "ry", "rz", (0.0, 0.0, 0.0)),
        scale=_params_vec(params, "sx", "sy", "sz", _default_scale_for_kind(kind)),
        color=str(params.get("color") or "#F2F2F2"),
        opacity=float(params.get("opacity", 1.0) or 1.0),
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
    kind = primitive.normalized().kind
    if kind == "arch":
        return _compound_boxes([(-0.42, 0.0, 0.5, 0.16, 0.2, 1.0), (0.42, 0.0, 0.5, 0.16, 0.2, 1.0), (0.0, 0.0, 0.98, 1.0, 0.2, 0.18)])
    if kind == "sphere":
        return _sphere_mesh()
    if kind == "cylinder":
        return _cylinder_mesh(cone=False)
    if kind == "cone":
        return _cylinder_mesh(cone=True)
    if kind == "plane":
        return {
            "vertices": [(-0.5, -0.5, 0.0), (0.5, -0.5, 0.0), (0.5, 0.5, 0.0), (-0.5, 0.5, 0.0)],
            "faces": [(0, 1, 2, 3)],
        }
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


def _sphere_mesh(*, latitude_steps: int = 6, longitude_steps: int = 10) -> dict[str, Any]:
    vertices: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    for latitude in range(latitude_steps + 1):
        phi = -pi * 0.5 + pi * latitude / latitude_steps
        z = sin(phi) * 0.5
        radius = cos(phi) * 0.5
        for longitude in range(longitude_steps):
            theta = 2.0 * pi * longitude / longitude_steps
            vertices.append((cos(theta) * radius, sin(theta) * radius, z))
    for latitude in range(latitude_steps):
        row = latitude * longitude_steps
        next_row = (latitude + 1) * longitude_steps
        for longitude in range(longitude_steps):
            nxt = (longitude + 1) % longitude_steps
            faces.append((row + longitude, row + nxt, next_row + nxt, next_row + longitude))
    return {"vertices": vertices, "faces": faces}


def _cylinder_mesh(*, cone: bool, segments: int = 12) -> dict[str, Any]:
    vertices: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    for z, radius in ((-0.5, 0.5), (0.5, 0.0 if cone else 0.5)):
        for segment in range(segments):
            theta = 2.0 * pi * segment / segments
            vertices.append((cos(theta) * radius, sin(theta) * radius, z))
    bottom_center = len(vertices)
    vertices.append((0.0, 0.0, -0.5))
    top_center = len(vertices)
    vertices.append((0.0, 0.0, 0.5))
    for segment in range(segments):
        nxt = (segment + 1) % segments
        lower_a = segment
        lower_b = nxt
        upper_a = segments + segment
        upper_b = segments + nxt
        faces.append((lower_a, lower_b, upper_b, upper_a))
        faces.append((bottom_center, lower_b, lower_a))
        if not cone:
            faces.append((top_center, upper_a, upper_b))
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
    camera_point = _world_to_camera_point(point, camera)
    if camera_point[1] <= 0.04:
        return None
    return _project_camera_point(camera_point, camera, width, height)


def _world_to_camera_point(point: Vec3, camera: BlockoutCamera) -> Vec3:
    x, y, z = point[0] - camera.target[0], point[1] - camera.target[1], point[2] - camera.target[2]
    yaw = radians(-camera.yaw_degrees)
    x, y = x * cos(yaw) + y * sin(yaw), -x * sin(yaw) + y * cos(yaw)
    pitch = radians(camera.pitch_degrees)
    z, y = z * cos(pitch) - y * sin(pitch), z * sin(pitch) + y * cos(pitch)
    y += max(0.25, float(camera.distance))
    return (x, y, z)


def _project_camera_point(
    point: Vec3,
    camera: BlockoutCamera,
    width: int,
    height: int,
) -> dict[str, float]:
    x, y, z = point
    focal = 0.5 * min(width, height) / tan(radians(_clamp(camera.fov_degrees, 15.0, 90.0)) * 0.5)
    return {"x": width * 0.5 + x * focal / y, "y": height * 0.5 - z * focal / y, "depth": y}


def _clip_camera_polygon_near(points: Sequence[Vec3], *, near: float) -> list[Vec3]:
    if not points:
        return []
    clipped: list[Vec3] = []
    previous = points[-1]
    previous_inside = previous[1] >= near
    for current in points:
        current_inside = current[1] >= near
        if current_inside != previous_inside:
            denominator = current[1] - previous[1]
            amount = 0.0 if abs(denominator) < 0.000001 else (near - previous[1]) / denominator
            clipped.append(
                (
                    previous[0] + (current[0] - previous[0]) * amount,
                    near,
                    previous[2] + (current[2] - previous[2]) * amount,
                )
            )
        if current_inside:
            clipped.append(current)
        previous = current
        previous_inside = current_inside
    return clipped


def _camera_to_world_vector(point: Vec3, camera: BlockoutCamera) -> Vec3:
    x_camera, y_camera, z_camera = point
    pitch = radians(camera.pitch_degrees)
    z = z_camera * cos(pitch) + y_camera * sin(pitch)
    y_rotated = -z_camera * sin(pitch) + y_camera * cos(pitch)
    yaw = radians(-camera.yaw_degrees)
    x = x_camera * cos(yaw) - y_rotated * sin(yaw)
    y = x_camera * sin(yaw) + y_rotated * cos(yaw)
    return (x, y, z)


def _face_edges(face: Sequence[int]) -> list[tuple[int, int]]:
    return [(int(face[index]), int(face[(index + 1) % len(face)])) for index in range(len(face))]


def _subtract(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _normalized(value: Vec3) -> Vec3:
    length = max(0.000001, (_dot(value, value)) ** 0.5)
    return (value[0] / length, value[1] / length, value[2] / length)


def _direction_from_angles(yaw_degrees: float, pitch_degrees: float) -> Vec3:
    yaw = radians(float(yaw_degrees))
    pitch = radians(float(pitch_degrees))
    horizontal = cos(pitch)
    return _normalized(
        (
            cos(yaw) * horizontal,
            sin(yaw) * horizontal,
            sin(pitch),
        )
    )


def _params_vec(params: dict[str, Any], x_key: str, y_key: str, z_key: str, default: Vec3) -> Vec3:
    if all(params.get(key) is None for key in (x_key, y_key, z_key)):
        return default
    return (
        float(params.get(x_key, default[0]) if params.get(x_key) is not None else default[0]),
        float(params.get(y_key, default[1]) if params.get(y_key) is not None else default[1]),
        float(params.get(z_key, default[2]) if params.get(z_key) is not None else default[2]),
    )


def _default_scale_for_kind(kind: str) -> Vec3:
    normalized = _supported_kind(kind)
    if normalized == "arch":
        return (2.2, 2.4, 0.8)
    if normalized == "plane":
        return (3.0, 3.0, 1.0)
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
    text = str(value or "#F2F2F2").strip()
    if len(text) == 7 and text.startswith("#"):
        return text.upper()
    return "#F2F2F2"


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
    "project_blockout_world_point",
    "screen_to_blockout_ground",
    "render_blockout_scene_qimage",
    "set_blockout_snap",
    "snap_blockout_primitive_to_grid",
    "update_blockout_camera",
    "update_blockout_primitive",
]
