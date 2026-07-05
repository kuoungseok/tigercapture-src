"""Load Aplaybox public preview PMX JSON packets as shared MMD models."""
from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Iterable

import numpy as np

from .pmx import (
    MMDBone,
    MMDIK,
    MMDIKLink,
    MMDJoint,
    MMDMaterial,
    MMDModel,
    MMDMorph,
    MMDRigidBody,
    MMDVertexMorph,
    MMDVertexWeights,
    PMXHeader,
    PMXParseError,
)


def _values(value: Any, size: int, default: float = 0.0) -> tuple[float, ...]:
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
        items = [float(v) for v in value]
    else:
        items = []
    if len(items) < size:
        items.extend([float(default)] * (size - len(items)))
    return tuple(items[:size])


def _vec3(value: Any) -> tuple[float, float, float]:
    x, y, z = _values(value, 3)
    return float(x), float(y), float(z)


def _vec4(value: Any, alpha_default: float = 0.0) -> tuple[float, float, float, float]:
    x, y, z, w = _values(value, 4, alpha_default)
    return float(x), float(y), float(z), float(w)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _read_vertices(data: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray, MMDVertexWeights]:
    raw_vertices = data.get("vertices")
    if not isinstance(raw_vertices, list) or not raw_vertices:
        raise PMXParseError("Aplaybox preview JSON has no vertices")

    count = len(raw_vertices)
    positions = np.zeros((count, 3), dtype=np.float32)
    normals = np.zeros((count, 3), dtype=np.float32)
    uvs = np.zeros((count, 2), dtype=np.float32)
    bone_indices = np.full((count, 4), -1, dtype=np.int32)
    bone_weights = np.zeros((count, 4), dtype=np.float32)
    weight_types = np.zeros((count,), dtype=np.uint8)
    sdef_c = np.zeros((count, 3), dtype=np.float32)
    sdef_r0 = np.zeros((count, 3), dtype=np.float32)
    sdef_r1 = np.zeros((count, 3), dtype=np.float32)
    edge_scales = np.ones((count,), dtype=np.float32)

    for idx, vertex in enumerate(raw_vertices):
        if not isinstance(vertex, dict):
            continue
        positions[idx] = _vec3(vertex.get("position"))
        normals[idx] = _vec3(vertex.get("normal"))
        u, v = _values(vertex.get("uv"), 2)
        uvs[idx] = (float(u), float(v))

        raw_indices = vertex.get("skinIndices") if isinstance(vertex.get("skinIndices"), list) else []
        raw_weights = vertex.get("skinWeights") if isinstance(vertex.get("skinWeights"), list) else []
        indices = [_int(v, -1) for v in raw_indices[:4]]
        weights = [max(0.0, _float(v, 0.0)) for v in raw_weights[:4]]
        if not indices:
            indices = [-1]
        if not weights:
            weights = [1.0]
        while len(indices) < 4:
            indices.append(-1)
        while len(weights) < 4:
            weights.append(0.0)
        total = float(sum(weights))
        if total <= 0.00001:
            weights = [1.0, 0.0, 0.0, 0.0]
        else:
            weights = [v / total for v in weights]
        bone_indices[idx] = np.asarray(indices[:4], dtype=np.int32)
        bone_weights[idx] = np.asarray(weights[:4], dtype=np.float32)
        weight_types[idx] = max(0, min(4, _int(vertex.get("type"), 0)))
        if isinstance(vertex.get("sdef"), dict):
            sdef = vertex["sdef"]
            sdef_c[idx] = _vec3(sdef.get("c"))
            sdef_r0[idx] = _vec3(sdef.get("r0"))
            sdef_r1[idx] = _vec3(sdef.get("r1"))
        edge_scales[idx] = _float(vertex.get("edgeRatio"), 1.0)

    return positions, normals, uvs, MMDVertexWeights(
        bone_indices=np.ascontiguousarray(bone_indices),
        bone_weights=np.ascontiguousarray(bone_weights),
        weight_types=np.ascontiguousarray(weight_types),
        sdef_c=np.ascontiguousarray(sdef_c),
        sdef_r0=np.ascontiguousarray(sdef_r0),
        sdef_r1=np.ascontiguousarray(sdef_r1),
        edge_scales=np.ascontiguousarray(edge_scales),
    )


def _read_indices(data: dict[str, Any]) -> np.ndarray:
    raw_faces = data.get("faces")
    if not isinstance(raw_faces, list) or not raw_faces:
        raise PMXParseError("Aplaybox preview JSON has no faces")
    out: list[int] = []
    for face in raw_faces:
        values = face.get("indices") if isinstance(face, dict) else face
        if isinstance(values, list):
            out.extend(_int(v, 0) for v in values[:3])
    if not out:
        raise PMXParseError("Aplaybox preview JSON has no triangle indices")
    return np.asarray(out, dtype=np.int32)


def _read_materials(data: dict[str, Any]) -> tuple[MMDMaterial, ...]:
    materials: list[MMDMaterial] = []
    for raw in data.get("materials") or []:
        if not isinstance(raw, dict):
            continue
        materials.append(
            MMDMaterial(
                name=str(raw.get("name") or ""),
                english_name=str(raw.get("englishName") or ""),
                diffuse=_vec4(raw.get("diffuse"), 1.0),
                specular=_values(raw.get("specular"), 3),
                specular_strength=_float(raw.get("shininess"), 0.0),
                ambient=_values(raw.get("ambient"), 3),
                flags=_int(raw.get("flag"), 0),
                edge_color=_vec4(raw.get("edgeColor"), 1.0),
                edge_size=_float(raw.get("edgeSize"), 0.0),
                texture_index=_int(raw.get("textureIndex"), -1),
                sphere_texture_index=_int(raw.get("envTextureIndex"), -1),
                sphere_mode=_int(raw.get("envFlag"), 0),
                toon_texture_index=_int(raw.get("toonIndex"), -1),
                toon_shared=bool(_int(raw.get("toonFlag"), 0)),
                memo=str(raw.get("comment") or ""),
                surface_count=max(0, _int(raw.get("faceCount"), 0) * 3),
            )
        )
    return tuple(materials)


def _read_bones(data: dict[str, Any]) -> tuple[MMDBone, ...]:
    bones: list[MMDBone] = []
    for raw in data.get("bones") or []:
        if not isinstance(raw, dict):
            continue
        flags = _int(raw.get("flag"), 0)
        tail_index = _int(raw.get("connectIndex"), -1) if "connectIndex" in raw else -1
        tail_position = _vec3(raw.get("offsetPosition")) if "offsetPosition" in raw else (0.0, 0.0, 0.0)
        grant = raw.get("grant") if isinstance(raw.get("grant"), dict) else {}
        inherit_parent_index = _int(grant.get("parentIndex"), -1)
        inherit_weight = _float(grant.get("ratio"), 0.0)
        ik = raw.get("ik") if isinstance(raw.get("ik"), dict) else None
        mmd_ik = None
        if ik is not None:
            links: list[MMDIKLink] = []
            for link in ik.get("links") or []:
                if not isinstance(link, dict):
                    continue
                has_limit = bool(_int(link.get("angleLimitation"), 0))
                links.append(
                    MMDIKLink(
                        bone_index=_int(link.get("index"), -1),
                        has_limit=has_limit,
                        limit_min=_vec3(link.get("lowerLimitationAngle")),
                        limit_max=_vec3(link.get("upperLimitationAngle")),
                    )
                )
            mmd_ik = MMDIK(
                target_index=_int(ik.get("effector"), -1),
                iteration_count=_int(ik.get("iteration"), 0),
                angle_limit=_float(ik.get("maxAngle"), 0.0),
                links=tuple(links),
            )
        bones.append(
            MMDBone(
                name=str(raw.get("name") or ""),
                english_name=str(raw.get("englishName") or ""),
                position=_vec3(raw.get("position")),
                parent_index=_int(raw.get("parentIndex"), -1),
                transform_layer=_int(raw.get("transformationClass"), 0),
                flags=flags,
                tail_index=tail_index,
                tail_position=tail_position,
                inherit_parent_index=inherit_parent_index,
                inherit_weight=inherit_weight,
                ik=mmd_ik,
            )
        )
    return tuple(bones)


def _read_morphs(data: dict[str, Any]) -> tuple[MMDMorph, ...]:
    morphs: list[MMDMorph] = []
    for raw in data.get("morphs") or []:
        if not isinstance(raw, dict):
            continue
        morph_type = _int(raw.get("type"), 0)
        vertex_morph = None
        if morph_type == 1:
            elements = raw.get("elements") if isinstance(raw.get("elements"), list) else []
            indices = np.zeros((len(elements),), dtype=np.int32)
            offsets = np.zeros((len(elements), 3), dtype=np.float32)
            for i, elem in enumerate(elements):
                if isinstance(elem, dict):
                    indices[i] = _int(elem.get("index"), 0)
                    offsets[i] = _vec3(elem.get("position"))
            vertex_morph = MMDVertexMorph(np.ascontiguousarray(indices), np.ascontiguousarray(offsets))
        morphs.append(
            MMDMorph(
                name=str(raw.get("name") or ""),
                english_name=str(raw.get("englishName") or ""),
                panel=_int(raw.get("panel"), 0),
                morph_type=morph_type,
                vertex_morph=vertex_morph,
            )
        )
    return tuple(morphs)


def _read_rigid_bodies(data: dict[str, Any]) -> tuple[MMDRigidBody, ...]:
    bodies: list[MMDRigidBody] = []
    for raw in data.get("rigidBodies") or []:
        if not isinstance(raw, dict):
            continue
        bodies.append(
            MMDRigidBody(
                name=str(raw.get("name") or ""),
                english_name=str(raw.get("englishName") or ""),
                bone_index=_int(raw.get("boneIndex"), -1),
                collision_group=_int(raw.get("groupIndex"), 0),
                collision_mask=_int(raw.get("groupTarget"), 0),
                shape=_int(raw.get("shapeType"), 0),
                size=(
                    _float(raw.get("width"), 0.0),
                    _float(raw.get("height"), 0.0),
                    _float(raw.get("depth"), 0.0),
                ),
                position=_vec3(raw.get("position")),
                rotation=_vec3(raw.get("rotation")),
                mass=_float(raw.get("weight"), 0.0),
                linear_damping=_float(raw.get("positionDamping"), 0.0),
                angular_damping=_float(raw.get("rotationDamping"), 0.0),
                restitution=_float(raw.get("restitution"), 0.0),
                friction=_float(raw.get("friction"), 0.0),
                physics_mode=_int(raw.get("type"), 0),
            )
        )
    return tuple(bodies)


def _read_joints(data: dict[str, Any]) -> tuple[MMDJoint, ...]:
    joints: list[MMDJoint] = []
    for raw in data.get("constraints") or []:
        if not isinstance(raw, dict):
            continue
        joints.append(
            MMDJoint(
                name=str(raw.get("name") or ""),
                english_name=str(raw.get("englishName") or ""),
                joint_type=_int(raw.get("type"), 0),
                rigid_body_a=_int(raw.get("rigidBodyIndex1"), -1),
                rigid_body_b=_int(raw.get("rigidBodyIndex2"), -1),
                position=_vec3(raw.get("position")),
                rotation=_vec3(raw.get("rotation")),
                linear_lower=_vec3(raw.get("translationLimitation1")),
                linear_upper=_vec3(raw.get("translationLimitation2")),
                angular_lower=_vec3(raw.get("rotationLimitation1")),
                angular_upper=_vec3(raw.get("rotationLimitation2")),
                linear_spring=_vec3(raw.get("springPosition")),
                angular_spring=_vec3(raw.get("springRotation")),
            )
        )
    return tuple(joints)


def load_aplaybox_pbx_json(path: str | Path) -> MMDModel:
    """Load a decoded Aplaybox ``*.pbx.json`` preview model."""
    model_path = Path(path)
    try:
        data = json.loads(model_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PMXParseError(f"Failed to parse Aplaybox preview JSON: {model_path}") from exc
    if not isinstance(data, dict):
        raise PMXParseError("Aplaybox preview JSON root must be an object")

    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    positions, normals, uvs, weights = _read_vertices(data)
    indices = _read_indices(data)
    textures = tuple(str(v or "").replace("\\", "/") for v in (data.get("textures") or []))
    materials = _read_materials(data)
    bones = _read_bones(data)
    morphs = _read_morphs(data)
    rigid_bodies = _read_rigid_bodies(data)
    joints = _read_joints(data)
    mins = np.min(positions, axis=0)
    maxs = np.max(positions, axis=0)
    header = PMXHeader(
        version=_float(metadata.get("version"), 2.0),
        encoding="utf-16-le" if _int(metadata.get("encoding"), 0) == 0 else "utf-8",
        additional_uv_count=_int(metadata.get("additionalUvNum"), 0),
        vertex_index_size=_int(metadata.get("vertexIndexSize"), 4),
        texture_index_size=_int(metadata.get("textureIndexSize"), 4),
        material_index_size=_int(metadata.get("materialIndexSize"), 4),
        bone_index_size=_int(metadata.get("boneIndexSize"), 4),
        morph_index_size=_int(metadata.get("morphIndexSize"), 4),
        rigid_body_index_size=_int(metadata.get("rigidBodyIndexSize"), 4),
    )
    return MMDModel(
        path=model_path,
        header=header,
        name=str(metadata.get("modelName") or model_path.stem),
        english_name=str(metadata.get("englishModelName") or ""),
        comment=str(metadata.get("comment") or ""),
        english_comment=str(metadata.get("englishComment") or ""),
        positions=np.ascontiguousarray(positions),
        normals=np.ascontiguousarray(normals),
        uvs=np.ascontiguousarray(uvs),
        weights=weights,
        indices=np.ascontiguousarray(indices),
        textures=textures,
        materials=materials,
        bones=bones,
        morphs=morphs,
        rigid_bodies=rigid_bodies,
        joints=joints,
        bounds_min=tuple(float(v) for v in mins),
        bounds_max=tuple(float(v) for v in maxs),
    )
