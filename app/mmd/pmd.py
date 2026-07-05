"""PMD 1.x reader that adapts classic MMD models to the shared MMD model shape."""
from __future__ import annotations

from pathlib import Path
import struct

import numpy as np

from .pmx import (
    MMDBone,
    MMDIK,
    MMDIKLink,
    MMDJoint,
    MMDMaterial,
    MMDModel,
    MMDMorph,
    MMDVertexMorph,
    MMDVertexWeights,
    MMDRigidBody,
    PMXHeader,
    PMXParseError,
)


class PMDParseError(PMXParseError):
    """Raised when a PMD file is malformed or unsupported by the PMD reader."""


class _Reader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0

    @property
    def remaining(self) -> int:
        return max(0, len(self._data) - self._offset)

    def _take(self, size: int) -> bytes:
        size = int(size)
        end = self._offset + size
        if size < 0 or end > len(self._data):
            raise PMDParseError("Unexpected end of PMD data")
        chunk = self._data[self._offset:end]
        self._offset = end
        return chunk

    def u8(self) -> int:
        return self._take(1)[0]

    def u16(self) -> int:
        return struct.unpack("<H", self._take(2))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self._take(4))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self._take(4))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self._take(4))[0]

    def vec2(self) -> tuple[float, float]:
        return self.f32(), self.f32()

    def vec3(self) -> tuple[float, float, float]:
        return self.f32(), self.f32(), self.f32()

    def vec4(self) -> tuple[float, float, float, float]:
        return self.f32(), self.f32(), self.f32(), self.f32()

    def fixed_string(self, size: int) -> str:
        raw = self._take(size)
        raw = raw.split(b"\x00", 1)[0]
        return raw.decode("cp932", errors="replace").strip()


def _pmd_index(value: int) -> int:
    value = int(value)
    return -1 if value == 0xFFFF else value


def _texture_index(textures: list[str], value: str) -> int:
    value = value.replace("\\", "/").strip().strip("\x00")
    if not value:
        return -1
    try:
        return textures.index(value)
    except ValueError:
        textures.append(value)
        return len(textures) - 1


def _split_material_texture(value: str) -> tuple[str, str, int]:
    texture = ""
    sphere = ""
    sphere_mode = 0
    for part in str(value or "").replace("\\", "/").split("*"):
        part = part.strip().strip("\x00")
        if not part:
            continue
        suffix = Path(part).suffix.casefold()
        if suffix in {".sph", ".spa"}:
            sphere = part
            sphere_mode = 2 if suffix == ".spa" else 1
        elif not texture:
            texture = part
    return texture, sphere, sphere_mode


def _read_header(reader: _Reader) -> tuple[str, str]:
    magic = reader._take(3)
    if magic != b"Pmd":
        raise PMDParseError("Only PMD files with the Pmd signature are supported")
    version = reader.f32()
    if version < 1.0 or version >= 2.0:
        raise PMDParseError(f"Unsupported PMD version: {version:.2f}")
    name = reader.fixed_string(20)
    comment = reader.fixed_string(256)
    return name, comment


def _read_vertices(reader: _Reader) -> tuple[np.ndarray, np.ndarray, np.ndarray, MMDVertexWeights]:
    count = reader.i32()
    if count <= 0:
        raise PMDParseError("PMD has no vertices")
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
    for i in range(count):
        positions[i] = reader.vec3()
        normals[i] = reader.vec3()
        uvs[i] = reader.vec2()
        b0 = _pmd_index(reader.u16())
        b1 = _pmd_index(reader.u16())
        w0 = max(0.0, min(1.0, float(reader.u8()) / 100.0))
        edge_flag = reader.u8()
        if b1 < 0 or w0 >= 0.999:
            bone_indices[i] = (b0, -1, -1, -1)
            bone_weights[i] = (1.0, 0.0, 0.0, 0.0)
            weight_types[i] = 0
        else:
            bone_indices[i] = (b0, b1, -1, -1)
            bone_weights[i] = (w0, 1.0 - w0, 0.0, 0.0)
            weight_types[i] = 1
        edge_scales[i] = 0.0 if edge_flag else 1.0
    return positions, normals, uvs, MMDVertexWeights(
        bone_indices=np.ascontiguousarray(bone_indices),
        bone_weights=np.ascontiguousarray(bone_weights),
        weight_types=np.ascontiguousarray(weight_types),
        sdef_c=np.ascontiguousarray(sdef_c),
        sdef_r0=np.ascontiguousarray(sdef_r0),
        sdef_r1=np.ascontiguousarray(sdef_r1),
        edge_scales=np.ascontiguousarray(edge_scales),
    )


def _read_indices(reader: _Reader) -> np.ndarray:
    count = reader.i32()
    if count <= 0:
        raise PMDParseError("PMD has no triangle indices")
    return np.asarray([reader.u16() for _ in range(count)], dtype=np.int32)


def _read_materials(reader: _Reader) -> tuple[tuple[MMDMaterial, ...], tuple[str, ...]]:
    count = reader.i32()
    if count < 0:
        raise PMDParseError("PMD material count is negative")
    textures: list[str] = []
    materials: list[MMDMaterial] = []
    for i in range(count):
        diffuse = reader.vec4()
        specular_strength = reader.f32()
        specular = reader.vec3()
        ambient = reader.vec3()
        toon_index = reader.u8()
        edge_flag = reader.u8()
        surface_count = reader.u32()
        raw_texture = reader.fixed_string(20)
        texture, sphere, sphere_mode = _split_material_texture(raw_texture)
        texture_index = _texture_index(textures, texture)
        sphere_texture_index = _texture_index(textures, sphere)
        edge_enabled = bool(edge_flag)
        materials.append(
            MMDMaterial(
                name=f"material_{i:03d}",
                english_name=f"material_{i:03d}",
                diffuse=tuple(float(v) for v in diffuse),
                specular=tuple(float(v) for v in specular),
                specular_strength=float(specular_strength),
                ambient=tuple(float(v) for v in ambient),
                flags=0x10 if edge_enabled else 0,
                edge_color=(0.02, 0.02, 0.02, 1.0 if edge_enabled else 0.0),
                edge_size=1.0 if edge_enabled else 0.0,
                texture_index=int(texture_index),
                sphere_texture_index=int(sphere_texture_index),
                sphere_mode=int(sphere_mode),
                toon_texture_index=-1 if toon_index == 0xFF else int(toon_index),
                toon_shared=toon_index != 0xFF,
                memo="",
                surface_count=max(0, int(surface_count)),
            )
        )
    return tuple(materials), tuple(textures)


def _read_bones(reader: _Reader) -> list[MMDBone]:
    count = reader.u16()
    bones: list[MMDBone] = []
    for _ in range(count):
        name = reader.fixed_string(20)
        parent_index = _pmd_index(reader.u16())
        tail_index = _pmd_index(reader.u16())
        bone_type = reader.u8()
        ik_parent = _pmd_index(reader.u16())
        position = reader.vec3()
        flags = 0x0001 if tail_index >= 0 else 0
        bones.append(
            MMDBone(
                name=name,
                english_name="",
                position=tuple(float(v) for v in position),
                parent_index=int(parent_index),
                transform_layer=0,
                flags=int(flags),
                tail_index=int(tail_index),
                tail_position=(0.0, 0.0, 0.0),
                inherit_parent_index=int(ik_parent if bone_type in {9} else -1),
                inherit_weight=0.0,
                ik=None,
            )
        )
    return bones


def _read_ik(reader: _Reader, bones: list[MMDBone]) -> None:
    ik_count = reader.u16()
    for _ in range(ik_count):
        ik_bone_index = _pmd_index(reader.u16())
        target_index = _pmd_index(reader.u16())
        link_count = reader.u8()
        iteration_count = reader.u16()
        angle_limit = reader.f32()
        links: list[MMDIKLink] = []
        for _i in range(link_count):
            link_index = _pmd_index(reader.u16())
            link_name = bones[link_index].name if 0 <= link_index < len(bones) else ""
            is_knee = "ひざ" in link_name or "膝" in link_name or "knee" in link_name.casefold()
            links.append(
                MMDIKLink(
                    bone_index=int(link_index),
                    has_limit=bool(is_knee),
                    limit_min=(-3.1415927, 0.0, 0.0) if is_knee else (0.0, 0.0, 0.0),
                    limit_max=(-0.002, 0.0, 0.0) if is_knee else (0.0, 0.0, 0.0),
                )
            )
        if 0 <= ik_bone_index < len(bones):
            bone = bones[ik_bone_index]
            bones[ik_bone_index] = MMDBone(
                name=bone.name,
                english_name=bone.english_name,
                position=bone.position,
                parent_index=bone.parent_index,
                transform_layer=bone.transform_layer,
                flags=bone.flags | 0x0020,
                tail_index=bone.tail_index,
                tail_position=bone.tail_position,
                inherit_parent_index=bone.inherit_parent_index,
                inherit_weight=bone.inherit_weight,
                fixed_axis=bone.fixed_axis,
                local_axis_x=bone.local_axis_x,
                local_axis_z=bone.local_axis_z,
                external_parent_key=bone.external_parent_key,
                ik=MMDIK(
                    target_index=int(target_index),
                    iteration_count=int(iteration_count),
                    angle_limit=float(angle_limit),
                    links=tuple(links),
                ),
            )


def _read_morphs(reader: _Reader) -> tuple[MMDMorph, ...]:
    count = reader.u16()
    if count < 0:
        raise PMDParseError("PMD morph count is negative")
    morphs: list[MMDMorph] = []
    base_indices: np.ndarray | None = None
    for _ in range(count):
        name = reader.fixed_string(20)
        vertex_count = reader.u32()
        skin_type = reader.u8()
        raw_indices = np.zeros((vertex_count,), dtype=np.int32)
        offsets = np.zeros((vertex_count, 3), dtype=np.float32)
        for i in range(vertex_count):
            raw_indices[i] = int(reader.u32())
            offsets[i] = reader.vec3()
        if skin_type == 0:
            base_indices = np.ascontiguousarray(raw_indices, dtype=np.int32)
            continue
        indices = raw_indices
        if base_indices is not None and base_indices.size:
            valid = (raw_indices >= 0) & (raw_indices < base_indices.size)
            mapped = np.array(raw_indices, dtype=np.int32, copy=True)
            mapped[valid] = base_indices[raw_indices[valid]]
            indices = mapped
        morphs.append(
            MMDMorph(
                name=name,
                english_name="",
                panel=int(skin_type),
                morph_type=1,
                vertex_morph=MMDVertexMorph(
                    indices=np.ascontiguousarray(indices, dtype=np.int32),
                    offsets=np.ascontiguousarray(offsets, dtype=np.float32),
                ),
            )
        )
    return tuple(morphs)


def _skip_display_and_english(reader: _Reader, *, bone_count: int, morph_count: int) -> None:
    if reader.remaining < 1:
        return
    skin_display_count = reader.u8()
    reader._take(2 * skin_display_count)
    if reader.remaining < 1:
        return
    bone_frame_name_count = reader.u8()
    reader._take(50 * bone_frame_name_count)
    if reader.remaining < 4:
        return
    bone_display_count = reader.u32()
    reader._take(3 * bone_display_count)
    if reader.remaining < 1:
        return
    english_flag = reader.u8()
    if not english_flag:
        return
    reader._take(20 + 256)
    reader._take(20 * bone_count)
    reader._take(20 * max(0, morph_count - 1))
    reader._take(50 * bone_frame_name_count)


def _skip_toon_textures(reader: _Reader) -> None:
    if reader.remaining >= 1000:
        reader._take(1000)


def _read_rigid_bodies(reader: _Reader) -> tuple[MMDRigidBody, ...]:
    if reader.remaining < 4:
        return ()
    count = reader.u32()
    bodies: list[MMDRigidBody] = []
    for _ in range(count):
        name = reader.fixed_string(20)
        bone_index = _pmd_index(reader.u16())
        collision_group = reader.u8()
        collision_mask = reader.u16()
        shape = reader.u8()
        size = reader.vec3()
        position = reader.vec3()
        rotation = reader.vec3()
        mass = reader.f32()
        linear_damping = reader.f32()
        angular_damping = reader.f32()
        restitution = reader.f32()
        friction = reader.f32()
        physics_mode = reader.u8()
        bodies.append(
            MMDRigidBody(
                name=name,
                english_name="",
                bone_index=int(bone_index),
                collision_group=int(collision_group),
                collision_mask=int(collision_mask),
                shape=int(shape),
                size=tuple(float(v) for v in size),
                position=tuple(float(v) for v in position),
                rotation=tuple(float(v) for v in rotation),
                mass=float(mass),
                linear_damping=float(linear_damping),
                angular_damping=float(angular_damping),
                restitution=float(restitution),
                friction=float(friction),
                physics_mode=int(physics_mode),
            )
        )
    return tuple(bodies)


def _read_joints(reader: _Reader) -> tuple[MMDJoint, ...]:
    if reader.remaining < 4:
        return ()
    count = reader.u32()
    joints: list[MMDJoint] = []
    for _ in range(count):
        name = reader.fixed_string(20)
        rigid_body_a = reader.u32()
        rigid_body_b = reader.u32()
        position = reader.vec3()
        rotation = reader.vec3()
        linear_lower = reader.vec3()
        linear_upper = reader.vec3()
        angular_lower = reader.vec3()
        angular_upper = reader.vec3()
        linear_spring = reader.vec3()
        angular_spring = reader.vec3()
        joints.append(
            MMDJoint(
                name=name,
                english_name="",
                joint_type=0,
                rigid_body_a=int(rigid_body_a),
                rigid_body_b=int(rigid_body_b),
                position=tuple(float(v) for v in position),
                rotation=tuple(float(v) for v in rotation),
                linear_lower=tuple(float(v) for v in linear_lower),
                linear_upper=tuple(float(v) for v in linear_upper),
                angular_lower=tuple(float(v) for v in angular_lower),
                angular_upper=tuple(float(v) for v in angular_upper),
                linear_spring=tuple(float(v) for v in linear_spring),
                angular_spring=tuple(float(v) for v in angular_spring),
            )
        )
    return tuple(joints)


def load_pmd(path: str | Path) -> MMDModel:
    model_path = Path(path)
    reader = _Reader(model_path.read_bytes())
    name, comment = _read_header(reader)
    positions, normals, uvs, weights = _read_vertices(reader)
    indices = _read_indices(reader)
    materials, textures = _read_materials(reader)
    bones = _read_bones(reader)
    _read_ik(reader, bones)
    morphs = _read_morphs(reader)
    _skip_display_and_english(reader, bone_count=len(bones), morph_count=len(morphs) + 1)
    _skip_toon_textures(reader)
    rigid_bodies = _read_rigid_bodies(reader)
    joints = _read_joints(reader)
    mins = np.min(positions, axis=0)
    maxs = np.max(positions, axis=0)
    return MMDModel(
        path=model_path,
        header=PMXHeader(
            version=1.0,
            encoding="cp932",
            additional_uv_count=0,
            vertex_index_size=2,
            texture_index_size=4,
            material_index_size=4,
            bone_index_size=2,
            morph_index_size=2,
            rigid_body_index_size=4,
        ),
        name=name,
        english_name="",
        comment=comment,
        english_comment="",
        positions=np.ascontiguousarray(positions, dtype=np.float32),
        normals=np.ascontiguousarray(normals, dtype=np.float32),
        uvs=np.ascontiguousarray(uvs, dtype=np.float32),
        weights=weights,
        indices=np.ascontiguousarray(indices, dtype=np.int32),
        textures=tuple(textures),
        materials=materials,
        bones=tuple(bones),
        morphs=morphs,
        rigid_bodies=rigid_bodies,
        joints=joints,
        bounds_min=tuple(float(v) for v in mins),
        bounds_max=tuple(float(v) for v in maxs),
    )
