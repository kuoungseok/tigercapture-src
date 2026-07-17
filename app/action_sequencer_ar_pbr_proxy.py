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
            geometry["material_id"] = "mat_body_teal"
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

    add_geometry(_ellipsoid("geom_torso", "Manny torso armor", "mat_body_teal", (0.04, 1.08, 0.0), (0.34, 0.54, 0.28), 22, 12), model_name="Torso")
    add_geometry(_ellipsoid("geom_chest", "Combat chest plate", "mat_armor_dark", (0.20, 1.24, 0.0), (0.18, 0.30, 0.31), 18, 10), model_name="Chest plate")
    add_geometry(_ellipsoid("geom_pelvis", "Manny pelvis", "mat_joint_black", (0.02, 0.56, 0.0), (0.28, 0.22, 0.25), 18, 9), model_name="Pelvis")
    add_geometry(_ellipsoid("geom_neck", "Neck joint", "mat_joint_black", (0.06, 1.55, 0.0), (0.11, 0.10, 0.10), 14, 8), model_name="Neck")
    add_geometry(_ellipsoid("geom_head", "Manny head", "mat_body_teal", (0.08, 1.78, 0.0), (0.23, 0.27, 0.20), 22, 12), model_name="Head")
    add_geometry(_box("geom_visor", "Forward visor", "mat_visor", (0.29, 1.80, 0.0), (0.035, 0.095, 0.24)), model_name="Forward visor")
    add_geometry(_box("geom_forward_mark", "Forward chest accent", "mat_accent_green", (0.38, 1.23, 0.0), (0.035, 0.22, 0.11)), model_name="Forward accent")

    for side, z in (("left", -0.42), ("right", 0.42)):
        add_geometry(_ellipsoid(f"geom_{side}_shoulder", f"{side.title()} shoulder", "mat_armor_dark", (0.06, 1.34, z), (0.16, 0.16, 0.16), 14, 8), model_name=f"{side.title()} shoulder")
        add_geometry(_ellipsoid(f"geom_{side}_upper_arm", f"{side.title()} upper arm", "mat_body_teal", (0.08, 1.02, z), (0.13, 0.31, 0.12), 16, 9), model_name=f"{side.title()} upper arm")
        add_geometry(_ellipsoid(f"geom_{side}_forearm", f"{side.title()} forearm guard", "mat_armor_dark", (0.16, 0.70, z), (0.13, 0.27, 0.11), 16, 9), model_name=f"{side.title()} forearm")
        add_geometry(_ellipsoid(f"geom_{side}_hand", f"{side.title()} hand", "mat_joint_black", (0.22, 0.46, z), (0.11, 0.09, 0.10), 14, 8), model_name=f"{side.title()} hand")
        add_geometry(_ellipsoid(f"geom_{side}_thigh", f"{side.title()} thigh armor", "mat_body_teal", (0.02, 0.22, z * 0.38), (0.13, 0.36, 0.11), 16, 9), model_name=f"{side.title()} thigh")
        add_geometry(_ellipsoid(f"geom_{side}_shin", f"{side.title()} shin guard", "mat_armor_dark", (0.09, -0.19, z * 0.38), (0.12, 0.34, 0.10), 16, 9), model_name=f"{side.title()} shin")
        add_geometry(_box(f"geom_{side}_foot", f"{side.title()} forward foot", "mat_joint_black", (0.21, -0.53, z * 0.38), (0.34, 0.11, 0.17)), model_name=f"{side.title()} foot")

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
            "proxy_visual_style": "combat_mannequin_pbr",
        },
    }


def _owner_proxy_materials() -> list[dict[str, Any]]:
    return [
        {
            "id": "mat_body_teal",
            "name": "Manny teal polymer",
            "base_color": [0.015, 0.34, 0.41, 1.0],
            "roughness": 0.33,
            "metallic": 0.05,
            "reflectance": 0.62,
            "pbr_available": True,
        },
        {
            "id": "mat_armor_dark",
            "name": "Dark combat armor",
            "base_color": [0.035, 0.048, 0.055, 1.0],
            "roughness": 0.28,
            "metallic": 0.16,
            "reflectance": 0.68,
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
            "id": "mat_visor",
            "name": "Gloss visor",
            "base_color": [0.01, 0.024, 0.028, 1.0],
            "roughness": 0.09,
            "metallic": 0.0,
            "reflectance": 0.88,
            "pbr_available": True,
            "clearcoat_strength": 0.55,
            "clearcoat_roughness": 0.06,
        },
        {
            "id": "mat_accent_green",
            "name": "Stage owner accent",
            "base_color": [0.29, 1.0, 0.57, 1.0],
            "emissive_color": [0.12, 0.55, 0.26],
            "roughness": 0.22,
            "metallic": 0.0,
            "reflectance": 0.76,
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
