"""Small PMX 2.x reader used by the standalone MMD player."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct

import numpy as np


class PMXParseError(ValueError):
    """Raised when a PMX file is malformed or unsupported by the MVP reader."""


@dataclass(frozen=True)
class PMXHeader:
    version: float
    encoding: str
    additional_uv_count: int
    vertex_index_size: int
    texture_index_size: int
    material_index_size: int
    bone_index_size: int
    morph_index_size: int
    rigid_body_index_size: int


@dataclass(frozen=True)
class MMDMaterial:
    name: str
    english_name: str
    diffuse: tuple[float, float, float, float]
    specular: tuple[float, float, float]
    specular_strength: float
    ambient: tuple[float, float, float]
    flags: int
    edge_color: tuple[float, float, float, float]
    edge_size: float
    texture_index: int
    sphere_texture_index: int
    sphere_mode: int
    toon_texture_index: int
    toon_shared: bool
    memo: str
    surface_count: int


@dataclass(frozen=True)
class MMDVertexWeights:
    bone_indices: np.ndarray
    bone_weights: np.ndarray
    weight_types: np.ndarray
    sdef_c: np.ndarray
    sdef_r0: np.ndarray
    sdef_r1: np.ndarray
    edge_scales: np.ndarray


@dataclass(frozen=True)
class MMDIKLink:
    bone_index: int
    has_limit: bool
    limit_min: tuple[float, float, float]
    limit_max: tuple[float, float, float]


@dataclass(frozen=True)
class MMDIK:
    target_index: int
    iteration_count: int
    angle_limit: float
    links: tuple[MMDIKLink, ...]


@dataclass(frozen=True)
class MMDBone:
    name: str
    english_name: str
    position: tuple[float, float, float]
    parent_index: int
    transform_layer: int
    flags: int
    tail_index: int
    tail_position: tuple[float, float, float]
    inherit_parent_index: int
    inherit_weight: float
    fixed_axis: tuple[float, float, float] | None = None
    local_axis_x: tuple[float, float, float] | None = None
    local_axis_z: tuple[float, float, float] | None = None
    external_parent_key: int | None = None
    ik: MMDIK | None = None


@dataclass(frozen=True)
class MMDVertexMorph:
    indices: np.ndarray
    offsets: np.ndarray


@dataclass(frozen=True)
class MMDMorph:
    name: str
    english_name: str
    panel: int
    morph_type: int
    vertex_morph: MMDVertexMorph | None = None


@dataclass(frozen=True)
class MMDRigidBody:
    name: str
    english_name: str
    bone_index: int
    collision_group: int
    collision_mask: int
    shape: int
    size: tuple[float, float, float]
    position: tuple[float, float, float]
    rotation: tuple[float, float, float]
    mass: float
    linear_damping: float
    angular_damping: float
    restitution: float
    friction: float
    physics_mode: int


@dataclass(frozen=True)
class MMDJoint:
    name: str
    english_name: str
    joint_type: int
    rigid_body_a: int
    rigid_body_b: int
    position: tuple[float, float, float]
    rotation: tuple[float, float, float]
    linear_lower: tuple[float, float, float]
    linear_upper: tuple[float, float, float]
    angular_lower: tuple[float, float, float]
    angular_upper: tuple[float, float, float]
    linear_spring: tuple[float, float, float]
    angular_spring: tuple[float, float, float]


@dataclass(frozen=True)
class MMDModel:
    path: Path
    header: PMXHeader
    name: str
    english_name: str
    comment: str
    english_comment: str
    positions: np.ndarray
    normals: np.ndarray
    uvs: np.ndarray
    weights: MMDVertexWeights
    indices: np.ndarray
    textures: tuple[str, ...]
    materials: tuple[MMDMaterial, ...]
    bones: tuple[MMDBone, ...]
    morphs: tuple[MMDMorph, ...]
    rigid_bodies: tuple[MMDRigidBody, ...]
    joints: tuple[MMDJoint, ...]
    bounds_min: tuple[float, float, float]
    bounds_max: tuple[float, float, float]

    @property
    def vertex_count(self) -> int:
        return int(self.positions.shape[0])

    @property
    def triangle_count(self) -> int:
        return int(self.indices.size // 3)


class _Reader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0

    @property
    def offset(self) -> int:
        return self._offset

    def _take(self, size: int) -> bytes:
        size = int(size)
        end = self._offset + size
        if size < 0 or end > len(self._data):
            raise PMXParseError("Unexpected end of PMX data")
        chunk = self._data[self._offset:end]
        self._offset = end
        return chunk

    def u8(self) -> int:
        return self._take(1)[0]

    def i8(self) -> int:
        return struct.unpack("<b", self._take(1))[0]

    def i16(self) -> int:
        return struct.unpack("<h", self._take(2))[0]

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

    def string(self, encoding: str) -> str:
        size = self.i32()
        if size <= 0:
            return ""
        raw = self._take(size)
        return raw.decode(encoding, errors="replace").replace("\x00", "")

    def index(self, size: int, *, signed: bool) -> int:
        if size == 1:
            return self.i8() if signed else self.u8()
        if size == 2:
            return self.i16() if signed else self.u16()
        if size == 4:
            return self.i32() if signed else self.u32()
        raise PMXParseError(f"Unsupported PMX index size: {size}")


def _read_header(reader: _Reader) -> PMXHeader:
    magic = reader._take(4)
    if magic != b"PMX ":
        raise PMXParseError("Only PMX files are supported by the MMD player MVP")
    version = reader.f32()
    if version < 2.0 or version >= 3.0:
        raise PMXParseError(f"Unsupported PMX version: {version:.2f}")
    header_size = reader.u8()
    if header_size < 8:
        raise PMXParseError(f"Unsupported PMX header size: {header_size}")
    globals_ = [reader.u8() for _ in range(header_size)]
    encoding = "utf-16-le" if globals_[0] == 0 else "utf-8"
    return PMXHeader(
        version=float(version),
        encoding=encoding,
        additional_uv_count=int(globals_[1]),
        vertex_index_size=int(globals_[2]),
        texture_index_size=int(globals_[3]),
        material_index_size=int(globals_[4]),
        bone_index_size=int(globals_[5]),
        morph_index_size=int(globals_[6]),
        rigid_body_index_size=int(globals_[7]),
    )


def _read_vertex_weight(
    reader: _Reader,
    header: PMXHeader,
    weight_type: int,
) -> tuple[list[int], list[float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    bone_size = header.bone_index_size
    zero = (0.0, 0.0, 0.0)
    if weight_type == 0:  # BDEF1
        return [reader.index(bone_size, signed=True), -1, -1, -1], [1.0, 0.0, 0.0, 0.0], zero, zero, zero
    elif weight_type == 1:  # BDEF2
        b0 = reader.index(bone_size, signed=True)
        b1 = reader.index(bone_size, signed=True)
        w0 = reader.f32()
        return [b0, b1, -1, -1], [w0, 1.0 - w0, 0.0, 0.0], zero, zero, zero
    elif weight_type in {2, 4}:  # BDEF4 / QDEF
        bones = [reader.index(bone_size, signed=True) for _ in range(4)]
        weights = [reader.f32() for _ in range(4)]
        return bones, weights, zero, zero, zero
    elif weight_type == 3:  # SDEF
        b0 = reader.index(bone_size, signed=True)
        b1 = reader.index(bone_size, signed=True)
        w0 = reader.f32()
        c = reader.vec3()
        r0 = reader.vec3()
        r1 = reader.vec3()
        return [b0, b1, -1, -1], [w0, 1.0 - w0, 0.0, 0.0], c, r0, r1
    else:
        raise PMXParseError(f"Unsupported PMX vertex weight type: {weight_type}")


def _read_vertices(reader: _Reader, header: PMXHeader) -> tuple[np.ndarray, np.ndarray, np.ndarray, MMDVertexWeights]:
    count = reader.i32()
    if count <= 0:
        raise PMXParseError("PMX has no vertices")
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
        for _ in range(header.additional_uv_count):
            reader.vec4()
        weight_type = reader.u8()
        bones, weights, c, r0, r1 = _read_vertex_weight(reader, header, weight_type)
        total = sum(max(0.0, float(v)) for v in weights)
        if total <= 0.00001:
            total = 1.0
        bone_indices[i] = np.asarray([int(v) for v in bones[:4]], dtype=np.int32)
        bone_weights[i] = np.asarray([max(0.0, float(v)) / total for v in weights[:4]], dtype=np.float32)
        weight_types[i] = int(weight_type)
        sdef_c[i] = c
        sdef_r0[i] = r0
        sdef_r1[i] = r1
        edge_scales[i] = float(reader.f32())
    return positions, normals, uvs, MMDVertexWeights(
        bone_indices=np.ascontiguousarray(bone_indices),
        bone_weights=np.ascontiguousarray(bone_weights),
        weight_types=np.ascontiguousarray(weight_types),
        sdef_c=np.ascontiguousarray(sdef_c),
        sdef_r0=np.ascontiguousarray(sdef_r0),
        sdef_r1=np.ascontiguousarray(sdef_r1),
        edge_scales=np.ascontiguousarray(edge_scales),
    )


def _read_indices(reader: _Reader, header: PMXHeader) -> np.ndarray:
    count = reader.i32()
    if count <= 0:
        raise PMXParseError("PMX has no triangle indices")
    indices = np.zeros((count,), dtype=np.int32)
    for i in range(count):
        indices[i] = int(reader.index(header.vertex_index_size, signed=False))
    return indices


def _read_textures(reader: _Reader, header: PMXHeader) -> tuple[str, ...]:
    count = reader.i32()
    if count < 0:
        raise PMXParseError("PMX texture count is negative")
    return tuple(reader.string(header.encoding) for _ in range(count))


def _read_materials(reader: _Reader, header: PMXHeader) -> tuple[MMDMaterial, ...]:
    count = reader.i32()
    if count < 0:
        raise PMXParseError("PMX material count is negative")
    materials: list[MMDMaterial] = []
    tex_size = header.texture_index_size
    for _ in range(count):
        name = reader.string(header.encoding)
        english_name = reader.string(header.encoding)
        diffuse = reader.vec4()
        specular = reader.vec3()
        specular_strength = reader.f32()
        ambient = reader.vec3()
        flags = reader.u8()
        edge_color = reader.vec4()
        edge_size = reader.f32()
        texture_index = reader.index(tex_size, signed=True)
        sphere_texture_index = reader.index(tex_size, signed=True)
        sphere_mode = reader.u8()
        toon_shared = bool(reader.u8())
        if toon_shared:
            toon_texture_index = reader.i8()
        else:
            toon_texture_index = reader.index(tex_size, signed=True)
        memo = reader.string(header.encoding)
        surface_count = reader.i32()
        materials.append(
            MMDMaterial(
                name=name,
                english_name=english_name,
                diffuse=tuple(float(v) for v in diffuse),
                specular=tuple(float(v) for v in specular),
                specular_strength=float(specular_strength),
                ambient=tuple(float(v) for v in ambient),
                flags=int(flags),
                edge_color=tuple(float(v) for v in edge_color),
                edge_size=float(edge_size),
                texture_index=int(texture_index),
                sphere_texture_index=int(sphere_texture_index),
                sphere_mode=int(sphere_mode),
                toon_texture_index=int(toon_texture_index),
                toon_shared=toon_shared,
                memo=memo,
                surface_count=max(0, int(surface_count)),
            )
        )
    return tuple(materials)


def _read_bone_tail_and_options(reader: _Reader, header: PMXHeader, flags: int) -> dict:
    out = {
        "tail_index": -1,
        "tail_position": (0.0, 0.0, 0.0),
        "inherit_parent_index": -1,
        "inherit_weight": 0.0,
        "fixed_axis": None,
        "local_axis_x": None,
        "local_axis_z": None,
        "external_parent_key": None,
        "ik": None,
    }
    if flags & 0x0001:
        out["tail_index"] = int(reader.index(header.bone_index_size, signed=True))
    else:
        out["tail_position"] = tuple(float(v) for v in reader.vec3())
    if flags & (0x0100 | 0x0200):
        out["inherit_parent_index"] = int(reader.index(header.bone_index_size, signed=True))
        out["inherit_weight"] = float(reader.f32())
    if flags & 0x0400:
        out["fixed_axis"] = tuple(float(v) for v in reader.vec3())
    if flags & 0x0800:
        out["local_axis_x"] = tuple(float(v) for v in reader.vec3())
        out["local_axis_z"] = tuple(float(v) for v in reader.vec3())
    if flags & 0x2000:
        out["external_parent_key"] = int(reader.i32())
    if flags & 0x0020:
        target_index = int(reader.index(header.bone_index_size, signed=True))
        iteration_count = int(reader.i32())
        angle_limit = float(reader.f32())
        link_count = reader.i32()
        links: list[MMDIKLink] = []
        for _ in range(max(0, link_count)):
            bone_index = int(reader.index(header.bone_index_size, signed=True))
            has_limit = bool(reader.u8())
            if has_limit:
                limit_min = tuple(float(v) for v in reader.vec3())
                limit_max = tuple(float(v) for v in reader.vec3())
            else:
                limit_min = (0.0, 0.0, 0.0)
                limit_max = (0.0, 0.0, 0.0)
            links.append(
                MMDIKLink(
                    bone_index=bone_index,
                    has_limit=has_limit,
                    limit_min=limit_min,
                    limit_max=limit_max,
                )
            )
        out["ik"] = MMDIK(
            target_index=target_index,
            iteration_count=iteration_count,
            angle_limit=angle_limit,
            links=tuple(links),
        )
    return out


def _read_bones(reader: _Reader, header: PMXHeader) -> tuple[MMDBone, ...]:
    count = reader.i32()
    if count < 0:
        raise PMXParseError("PMX bone count is negative")
    bones: list[MMDBone] = []
    for _ in range(count):
        name = reader.string(header.encoding)
        english_name = reader.string(header.encoding)
        position = reader.vec3()
        parent_index = reader.index(header.bone_index_size, signed=True)
        transform_layer = reader.i32()
        flags = reader.u16()
        extra = _read_bone_tail_and_options(reader, header, flags)
        bones.append(
            MMDBone(
                name=name,
                english_name=english_name,
                position=tuple(float(v) for v in position),
                parent_index=int(parent_index),
                transform_layer=int(transform_layer),
                flags=int(flags),
                tail_index=int(extra["tail_index"]),
                tail_position=extra["tail_position"],
                inherit_parent_index=int(extra["inherit_parent_index"]),
                inherit_weight=float(extra["inherit_weight"]),
                fixed_axis=extra["fixed_axis"],
                local_axis_x=extra["local_axis_x"],
                local_axis_z=extra["local_axis_z"],
                external_parent_key=extra["external_parent_key"],
                ik=extra["ik"],
            )
        )
    return tuple(bones)


def _skip_morph_offset(reader: _Reader, header: PMXHeader, morph_type: int) -> None:
    if morph_type == 0:
        reader.index(header.morph_index_size, signed=True)
        reader.f32()
    elif morph_type == 1:
        reader.index(header.vertex_index_size, signed=False)
        reader.vec3()
    elif morph_type == 2:
        reader.index(header.bone_index_size, signed=True)
        reader.vec3()
        reader.vec4()
    elif 3 <= morph_type <= 7:
        reader.index(header.vertex_index_size, signed=False)
        reader.vec4()
    elif morph_type == 8:
        reader.index(header.material_index_size, signed=True)
        reader.u8()
        reader.vec4()
        reader.vec3()
        reader.f32()
        reader.vec3()
        reader.vec4()
        reader.f32()
        reader.vec4()
        reader.vec4()
        reader.vec4()
    elif morph_type == 9:
        reader.index(header.morph_index_size, signed=True)
        reader.f32()
    elif morph_type == 10:
        reader.index(header.rigid_body_index_size, signed=True)
        reader.u8()
        reader.vec3()
        reader.vec3()
    else:
        raise PMXParseError(f"Unsupported PMX morph type: {morph_type}")


def _read_morphs(reader: _Reader, header: PMXHeader) -> tuple[MMDMorph, ...]:
    count = reader.i32()
    if count < 0:
        raise PMXParseError("PMX morph count is negative")
    morphs: list[MMDMorph] = []
    for _ in range(count):
        name = reader.string(header.encoding)
        english_name = reader.string(header.encoding)
        panel = reader.u8()
        morph_type = reader.u8()
        offset_count = reader.i32()
        if morph_type == 1:
            indices = np.zeros((max(0, offset_count),), dtype=np.int32)
            offsets = np.zeros((max(0, offset_count), 3), dtype=np.float32)
            for i in range(max(0, offset_count)):
                indices[i] = int(reader.index(header.vertex_index_size, signed=False))
                offsets[i] = reader.vec3()
            vertex_morph = MMDVertexMorph(
                indices=np.ascontiguousarray(indices),
                offsets=np.ascontiguousarray(offsets),
            )
        else:
            for _i in range(max(0, offset_count)):
                _skip_morph_offset(reader, header, morph_type)
            vertex_morph = None
        morphs.append(
            MMDMorph(
                name=name,
                english_name=english_name,
                panel=int(panel),
                morph_type=int(morph_type),
                vertex_morph=vertex_morph,
            )
        )
    return tuple(morphs)


def _skip_display_frames(reader: _Reader, header: PMXHeader) -> None:
    count = reader.i32()
    if count < 0:
        raise PMXParseError("PMX display frame count is negative")
    for _ in range(count):
        reader.string(header.encoding)
        reader.string(header.encoding)
        reader.u8()
        element_count = reader.i32()
        for _i in range(max(0, element_count)):
            element_type = reader.u8()
            if element_type == 0:
                reader.index(header.bone_index_size, signed=True)
            else:
                reader.index(header.morph_index_size, signed=True)


def _read_rigid_bodies(reader: _Reader, header: PMXHeader) -> tuple[MMDRigidBody, ...]:
    count = reader.i32()
    if count < 0:
        raise PMXParseError("PMX rigid body count is negative")
    bodies: list[MMDRigidBody] = []
    for _ in range(count):
        name = reader.string(header.encoding)
        english_name = reader.string(header.encoding)
        bone_index = reader.index(header.bone_index_size, signed=True)
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
                english_name=english_name,
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


def _read_joints(reader: _Reader, header: PMXHeader) -> tuple[MMDJoint, ...]:
    count = reader.i32()
    if count < 0:
        raise PMXParseError("PMX joint count is negative")
    joints: list[MMDJoint] = []
    for _ in range(count):
        name = reader.string(header.encoding)
        english_name = reader.string(header.encoding)
        joint_type = reader.u8()
        rigid_body_a = reader.index(header.rigid_body_index_size, signed=True)
        rigid_body_b = reader.index(header.rigid_body_index_size, signed=True)
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
                english_name=english_name,
                joint_type=int(joint_type),
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


def load_pmx(path: str | Path) -> MMDModel:
    """Load PMX bind-pose geometry and material metadata."""
    pmx_path = Path(path)
    data = pmx_path.read_bytes()
    reader = _Reader(data)
    header = _read_header(reader)
    name = reader.string(header.encoding)
    english_name = reader.string(header.encoding)
    comment = reader.string(header.encoding)
    english_comment = reader.string(header.encoding)
    positions, normals, uvs, weights = _read_vertices(reader, header)
    indices = _read_indices(reader, header)
    textures = _read_textures(reader, header)
    materials = _read_materials(reader, header)
    bones = _read_bones(reader, header)
    morphs = _read_morphs(reader, header)
    rigid_bodies: tuple[MMDRigidBody, ...] = ()
    joints: tuple[MMDJoint, ...] = ()
    if reader.offset < len(data):
        _skip_display_frames(reader, header)
    if reader.offset < len(data):
        rigid_bodies = _read_rigid_bodies(reader, header)
    if reader.offset < len(data):
        joints = _read_joints(reader, header)
    if positions.size:
        bounds_min_arr = np.min(positions, axis=0)
        bounds_max_arr = np.max(positions, axis=0)
    else:
        bounds_min_arr = np.zeros((3,), dtype=np.float32)
        bounds_max_arr = np.zeros((3,), dtype=np.float32)
    return MMDModel(
        path=pmx_path,
        header=header,
        name=name,
        english_name=english_name,
        comment=comment,
        english_comment=english_comment,
        positions=np.ascontiguousarray(positions, dtype=np.float32),
        normals=np.ascontiguousarray(normals, dtype=np.float32),
        uvs=np.ascontiguousarray(uvs, dtype=np.float32),
        weights=weights,
        indices=np.ascontiguousarray(indices, dtype=np.int32),
        textures=textures,
        materials=materials,
        bones=bones,
        morphs=morphs,
        rigid_bodies=rigid_bodies,
        joints=joints,
        bounds_min=tuple(float(v) for v in bounds_min_arr),
        bounds_max=tuple(float(v) for v in bounds_max_arr),
    )
