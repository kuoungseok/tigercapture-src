"""AR/PBR proxy descriptor generation for Action Sequencer owner previews."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


OWNER_AR_PBR_PROXY_SCHEMA = "tigerstudio.ar_pbr.action_sequencer_owner_proxy.v1"


def default_owner_ar_pbr_proxy_path(owner_descriptor: Any, *, root: Path | None = None) -> Path:
    base = root or Path(__file__).resolve().parents[1] / "debugCapture"
    project_path = Path(getattr(owner_descriptor, "project_path", "ActionSequencer"))
    project_stem = project_path.stem or "ActionSequencer"
    owner = str(getattr(owner_descriptor, "owner_name", "Owner") or "Owner")
    return base / f"action_sequencer_{project_stem}_{owner}_owner_ar_pbr.arpbr"


def write_owner_ar_pbr_proxy_asset(owner_descriptor: Any, output_path: str | Path | None = None) -> Path:
    target = Path(output_path) if output_path is not None else default_owner_ar_pbr_proxy_path(owner_descriptor)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": OWNER_AR_PBR_PROXY_SCHEMA,
        "runtime_format": "ar_scene_descriptor",
        "descriptor": build_owner_ar_pbr_proxy_descriptor(owner_descriptor),
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def build_owner_ar_pbr_proxy_descriptor(owner_descriptor: Any) -> dict[str, Any]:
    owner_name = str(getattr(owner_descriptor, "owner_name", "BP_CombatCharacter") or "BP_CombatCharacter")
    geometries: list[dict[str, Any]] = []
    models: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []

    materials = _owner_proxy_materials()
    material_ids = {str(item["id"]) for item in materials}

    def add_geometry(geometry: dict[str, Any], *, model_name: str) -> None:
        if geometry["material_id"] not in material_ids:
            geometry["material_id"] = "mat_manny_shell"
        model_id = f"model_{geometry['id']}"
        geometry["model_id"] = model_id
        geometry["vertex_count"] = len(geometry.get("vertices") or [])
        geometry["triangle_count"] = len(geometry.get("triangles") or [])
        geometry["bounds"] = _bounds_from_vertices(geometry.get("vertices") or [])
        geometries.append(geometry)
        models.append({
            "id": model_id,
            "name": model_name,
            "type": "Mesh",
            "translation": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
        })
        connections.append({"child": geometry["id"], "parent": model_id, "type": "Geometry"})
        connections.append({"child": geometry["material_id"], "parent": model_id, "type": "Material"})

    add_geometry(_ellipsoid("geom_torso_core", "Manny tapered torso core", "mat_manny_shell", (0.02, 1.08, 0.0), (0.27, 0.46, 0.24), 26, 13), model_name="Torso core")
    add_geometry(_ellipsoid("geom_chest_plate", "Manny segmented chest plate", "mat_manny_panel", (0.13, 1.24, 0.0), (0.20, 0.25, 0.32), 22, 11), model_name="Chest plate")
    add_geometry(_box("geom_chest_center_trim", "Manny chest center trim", "mat_manny_trim", (0.33, 1.24, 0.0), (0.030, 0.28, 0.035)), model_name="Chest trim")
    add_geometry(_ellipsoid("geom_abdomen", "Manny abdomen joint", "mat_joint_black", (0.02, 0.84, 0.0), (0.20, 0.18, 0.20), 18, 9), model_name="Abdomen joint")
    add_geometry(_ellipsoid("geom_pelvis", "Manny pelvis shell", "mat_manny_shell", (0.01, 0.57, 0.0), (0.27, 0.18, 0.28), 20, 10), model_name="Pelvis")
    add_geometry(_ellipsoid("geom_neck", "Manny neck joint", "mat_joint_black", (0.03, 1.54, 0.0), (0.09, 0.09, 0.09), 16, 8), model_name="Neck")
    add_geometry(_ellipsoid("geom_head", "Manny helmet head", "mat_manny_shell", (0.04, 1.78, 0.0), (0.19, 0.24, 0.17), 26, 13), model_name="Head")
    add_geometry(_box("geom_face_plate", "Manny forward face plate", "mat_manny_panel", (0.225, 1.79, 0.0), (0.035, 0.13, 0.22)), model_name="Face plate")
    add_geometry(_box("geom_face_trim", "Manny visor trim", "mat_manny_trim", (0.252, 1.82, 0.0), (0.018, 0.035, 0.16)), model_name="Face trim")

    for side, z in (("left", -0.39), ("right", 0.39)):
        sign = -1.0 if side == "left" else 1.0
        add_geometry(_ellipsoid(f"geom_{side}_shoulder_socket", f"{side.title()} shoulder socket", "mat_joint_black", (0.03, 1.34, z), (0.13, 0.13, 0.13), 16, 8), model_name=f"{side.title()} shoulder socket")
        add_geometry(_ellipsoid(f"geom_{side}_shoulder_cap", f"{side.title()} shoulder shell", "mat_manny_shell", (0.07, 1.33, z + sign * 0.05), (0.16, 0.13, 0.14), 18, 9), model_name=f"{side.title()} shoulder shell")
        add_geometry(_capsule_between(f"geom_{side}_upper_arm", f"{side.title()} upper arm shell", "mat_manny_shell", (0.06, 1.20, z + sign * 0.07), (0.08, 0.86, z + sign * 0.18), 0.095, 18), model_name=f"{side.title()} upper arm")
        add_geometry(_ellipsoid(f"geom_{side}_elbow", f"{side.title()} elbow joint", "mat_joint_black", (0.08, 0.82, z + sign * 0.19), (0.10, 0.08, 0.09), 16, 8), model_name=f"{side.title()} elbow")
        add_geometry(_capsule_between(f"geom_{side}_forearm", f"{side.title()} forearm shell", "mat_manny_panel", (0.09, 0.78, z + sign * 0.19), (0.13, 0.48, z + sign * 0.23), 0.092, 18), model_name=f"{side.title()} forearm")
        add_geometry(_ellipsoid(f"geom_{side}_hand", f"{side.title()} hand", "mat_joint_black", (0.15, 0.40, z + sign * 0.24), (0.10, 0.075, 0.085), 14, 8), model_name=f"{side.title()} hand")
        add_geometry(_capsule_between(f"geom_{side}_thigh", f"{side.title()} thigh shell", "mat_manny_shell", (0.00, 0.45, sign * 0.14), (0.02, 0.07, sign * 0.17), 0.105, 18), model_name=f"{side.title()} thigh")
        add_geometry(_ellipsoid(f"geom_{side}_knee", f"{side.title()} knee joint", "mat_joint_black", (0.04, 0.02, sign * 0.17), (0.10, 0.08, 0.09), 16, 8), model_name=f"{side.title()} knee")
        add_geometry(_capsule_between(f"geom_{side}_shin", f"{side.title()} shin shell", "mat_manny_panel", (0.05, -0.04, sign * 0.17), (0.08, -0.43, sign * 0.16), 0.095, 18), model_name=f"{side.title()} shin")
        add_geometry(_ellipsoid(f"geom_{side}_ankle", f"{side.title()} ankle joint", "mat_joint_black", (0.09, -0.47, sign * 0.16), (0.075, 0.06, 0.075), 14, 7), model_name=f"{side.title()} ankle")
        add_geometry(_box(f"geom_{side}_foot", f"{side.title()} forward foot", "mat_joint_black", (0.22, -0.55, sign * 0.16), (0.33, 0.105, 0.145)), model_name=f"{side.title()} foot")

    bounds = _bounds_from_geometries(geometries)
    triangle_count = sum(int(item.get("triangle_count", 0) or 0) for item in geometries)
    vertex_count = sum(int(item.get("vertex_count", 0) or 0) for item in geometries)
    return {
        "schema": OWNER_AR_PBR_PROXY_SCHEMA,
        "id": f"action_sequencer_{owner_name}_owner_proxy",
        "type": "ar_pbr_asset",
        "source_format": "ar_pbr_proxy",
        "runtime_format": "ar_scene_descriptor",
        "import_state": "ready",
        "backend": "action_sequencer_proxy",
        "mesh_count": len(geometries),
        "material_count": len(materials),
        "texture_count": 0,
        "animation_count": 0,
        "animation_clips": [],
        "skeletal_mesh_count": 0,
        "skin_count": 0,
        "skeletons": [],
        "bones": [],
        "units": {"scale_to_meters": 1.0, "source": "ue_centimeters_proxy_scaled"},
        "axes": {"up": "Y", "forward": "+X", "source": "action_sequencer_owner_stage"},
        "bounds": bounds,
        "materials": materials,
        "geometries": geometries,
        "models": models,
        "connections": connections,
        "warnings": [
            "Action Sequencer V1 uses an AR/PBR proxy mesh until the internal CUE4Parse bridge exports real skeletal vertices.",
        ],
        "metadata": {
            "owner_name": owner_name,
            "owner_class_name": str(getattr(owner_descriptor, "owner_class_name", "") or ""),
            "owner_asset_path": _path_text(getattr(owner_descriptor, "owner_asset_path", None)),
            "render_asset_path": _path_text(getattr(owner_descriptor, "render_asset_path", None)),
            "animation_blueprint_path": _path_text(getattr(owner_descriptor, "animation_blueprint_path", None)),
            "idle_animation_path": _path_text(getattr(owner_descriptor, "idle_animation_path", None)),
            "action_candidate_path": _path_text(getattr(owner_descriptor, "action_candidate_path", None)),
            "stage_position": list(getattr(owner_descriptor, "stage_position", (-120.0, 0.0, 0.0)) or (-120.0, 0.0, 0.0)),
            "stage_forward": str(getattr(owner_descriptor, "stage_forward", "+X / screen right") or "+X / screen right"),
            "proxy_visual_style": "ue_manny_mannequin_pbr_proxy",
        },
    }


def _owner_proxy_materials() -> list[dict[str, Any]]:
    return [
        {
            "id": "mat_manny_shell",
            "name": "Manny warm grey shell",
            "base_color": [0.62, 0.64, 0.61, 1.0],
            "roughness": 0.38,
            "metallic": 0.05,
            "reflectance": 0.55,
            "pbr_available": True,
        },
        {
            "id": "mat_manny_panel",
            "name": "Manny dark panel",
            "base_color": [0.18, 0.19, 0.185, 1.0],
            "roughness": 0.34,
            "metallic": 0.08,
            "reflectance": 0.50,
            "pbr_available": True,
        },
        {
            "id": "mat_joint_black",
            "name": "Black joint rubber",
            "base_color": [0.006, 0.007, 0.008, 1.0],
            "roughness": 0.58,
            "metallic": 0.0,
            "reflectance": 0.42,
            "pbr_available": True,
        },
        {
            "id": "mat_manny_trim",
            "name": "Manny orange trim",
            "base_color": [1.0, 0.47, 0.13, 1.0],
            "roughness": 0.30,
            "metallic": 0.0,
            "reflectance": 0.72,
            "pbr_available": True,
        },
    ]


def _ellipsoid(
    geometry_id: str,
    name: str,
    material_id: str,
    center: tuple[float, float, float],
    radius: tuple[float, float, float],
    segments: int,
    rings: int,
) -> dict[str, Any]:
    cx, cy, cz = center
    rx, ry, rz = radius
    seg = max(8, int(segments))
    ring_count = max(5, int(rings))
    vertices: list[list[float]] = []
    uvs: list[list[float]] = []
    for iy in range(ring_count + 1):
        theta = math.pi * float(iy) / float(ring_count)
        y = math.cos(theta)
        radial = math.sin(theta)
        for ix in range(seg):
            phi = math.tau * float(ix) / float(seg)
            vertices.append([
                round(cx + math.cos(phi) * radial * rx, 6),
                round(cy + y * ry, 6),
                round(cz + math.sin(phi) * radial * rz, 6),
            ])
            uvs.append([round(float(ix) / float(seg), 6), round(float(iy) / float(ring_count), 6)])
    triangles: list[list[int]] = []
    for iy in range(ring_count):
        for ix in range(seg):
            a = iy * seg + ix
            b = iy * seg + ((ix + 1) % seg)
            c = (iy + 1) * seg + ix
            d = (iy + 1) * seg + ((ix + 1) % seg)
            if iy > 0:
                triangles.append([a, c, b])
            if iy < ring_count - 1:
                triangles.append([b, c, d])
    return {
        "id": geometry_id,
        "name": name,
        "material_id": material_id,
        "vertices": vertices,
        "triangles": triangles,
        "uvs": uvs,
    }


def _box(
    geometry_id: str,
    name: str,
    material_id: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
) -> dict[str, Any]:
    cx, cy, cz = center
    sx, sy, sz = (max(1.0e-4, value) * 0.5 for value in size)
    vertices = [
        [cx - sx, cy - sy, cz - sz],
        [cx + sx, cy - sy, cz - sz],
        [cx + sx, cy + sy, cz - sz],
        [cx - sx, cy + sy, cz - sz],
        [cx - sx, cy - sy, cz + sz],
        [cx + sx, cy - sy, cz + sz],
        [cx + sx, cy + sy, cz + sz],
        [cx - sx, cy + sy, cz + sz],
    ]
    triangles = [
        [0, 2, 1], [0, 3, 2],
        [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4],
        [3, 6, 2], [3, 7, 6],
        [1, 2, 6], [1, 6, 5],
        [0, 4, 7], [0, 7, 3],
    ]
    return {
        "id": geometry_id,
        "name": name,
        "material_id": material_id,
        "vertices": [[round(float(v), 6) for v in row] for row in vertices],
        "triangles": triangles,
        "uvs": [[0.0, 0.0] for _ in vertices],
    }


def _capsule_between(
    geometry_id: str,
    name: str,
    material_id: str,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
    segments: int,
) -> dict[str, Any]:
    sx, sy, sz = start
    ex, ey, ez = end
    axis = _normalize((ex - sx, ey - sy, ez - sz))
    if _length(axis) <= 1.0e-6:
        return _ellipsoid(geometry_id, name, material_id, start, (radius, radius, radius), segments, 8)
    ref = (0.0, 1.0, 0.0)
    if abs(_dot(axis, ref)) > 0.92:
        ref = (1.0, 0.0, 0.0)
    side = _normalize(_cross(axis, ref))
    up = _normalize(_cross(side, axis))
    seg = max(8, int(segments))
    vertices: list[list[float]] = []
    uvs: list[list[float]] = []
    for ring_index, center in enumerate((start, end)):
        cx, cy, cz = center
        for ix in range(seg):
            angle = math.tau * float(ix) / float(seg)
            c = math.cos(angle)
            s = math.sin(angle)
            px = cx + (side[0] * c + up[0] * s) * radius
            py = cy + (side[1] * c + up[1] * s) * radius
            pz = cz + (side[2] * c + up[2] * s) * radius
            vertices.append([round(px, 6), round(py, 6), round(pz, 6)])
            uvs.append([round(float(ix) / float(seg), 6), float(ring_index)])
    start_center = len(vertices)
    vertices.append([round(sx, 6), round(sy, 6), round(sz, 6)])
    uvs.append([0.5, 0.0])
    end_center = len(vertices)
    vertices.append([round(ex, 6), round(ey, 6), round(ez, 6)])
    uvs.append([0.5, 1.0])
    triangles: list[list[int]] = []
    for ix in range(seg):
        a = ix
        b = (ix + 1) % seg
        c = seg + ix
        d = seg + ((ix + 1) % seg)
        triangles.append([a, c, b])
        triangles.append([b, c, d])
        triangles.append([start_center, b, a])
        triangles.append([end_center, c, d])
    return {
        "id": geometry_id,
        "name": name,
        "material_id": material_id,
        "vertices": vertices,
        "triangles": triangles,
        "uvs": uvs,
    }


def _length(vector: tuple[float, float, float]) -> float:
    return math.sqrt(_dot(vector, vector))


def _normalize(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    length = _length(vector)
    if length <= 1.0e-9:
        return (0.0, 0.0, 0.0)
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _bounds_from_geometries(geometries: list[dict[str, Any]]) -> dict[str, list[float]]:
    vertices: list[list[float]] = []
    for geometry in geometries:
        vertices.extend(row for row in geometry.get("vertices") or [] if isinstance(row, list))
    return _bounds_from_vertices(vertices)


def _bounds_from_vertices(vertices: list[Any]) -> dict[str, list[float]]:
    rows = []
    for raw in vertices:
        if not isinstance(raw, (list, tuple)) or len(raw) < 3:
            continue
        try:
            rows.append([float(raw[0]), float(raw[1]), float(raw[2])])
        except Exception:
            continue
    if not rows:
        return {"center": [0.0, 0.0, 0.0], "size": [1.0, 1.0, 1.0]}
    mins = [min(row[i] for row in rows) for i in range(3)]
    maxs = [max(row[i] for row in rows) for i in range(3)]
    center = [(mins[i] + maxs[i]) * 0.5 for i in range(3)]
    size = [max(maxs[i] - mins[i], 1.0e-6) for i in range(3)]
    return {
        "center": [round(float(value), 6) for value in center],
        "size": [round(float(value), 6) for value in size],
    }


def _path_text(path: Any) -> str | None:
    if path is None:
        return None
    try:
        return Path(path).as_posix()
    except Exception:
        return str(path)


__all__ = [
    "OWNER_AR_PBR_PROXY_SCHEMA",
    "build_owner_ar_pbr_proxy_descriptor",
    "default_owner_ar_pbr_proxy_path",
    "write_owner_ar_pbr_proxy_asset",
]
