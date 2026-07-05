"""Binary FBX metadata/preview-mesh parser.

This parser targets the subset needed by the AR/PBR preview path: geometry
vertices, polygon indices, materials, transforms, global units/axes, and
connections. It is intentionally not a full FBX SDK replacement.
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass
from pathlib import Path
import math
import struct
import sys
from typing import Any, Iterator
import zlib

from app.ar_pbr.animation import ticks_to_ms
from app.ar_pbr.fbx_ascii import BINARY_FBX_MAGIC


DEFAULT_MAX_TRIANGLES_PER_GEOMETRY = 12000


@dataclass
class BinaryFbxNode:
    name: str
    props: list[Any]
    children: list["BinaryFbxNode"]


def _decode_string(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def _clean_node_name(value: Any, prefix: str) -> str:
    text = str(value or "").strip().strip('"')
    if "\x00\x01" in text:
        text = text.split("\x00\x01", 1)[0]
    if "::" in text:
        head, tail = text.split("::", 1)
        if head.casefold() == prefix.casefold():
            return tail
    return text


def _array_from_bytes(code: str, raw: bytes) -> array:
    mapping = {
        "f": "f",
        "d": "d",
        "i": "i",
        "l": "q",
        "b": "b",
    }
    arr = array(mapping[code])
    arr.frombytes(raw)
    if sys.byteorder != "little":
        arr.byteswap()
    return arr


class BinaryFbxReader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        if not data.startswith(BINARY_FBX_MAGIC):
            raise ValueError("not a binary FBX file")
        self.version = struct.unpack_from("<I", data, 23)[0]
        self.large_offsets = self.version >= 7500
        self.header_size = 27
        self.null_record_size = 25 if self.large_offsets else 13

    def _read_record_header(self, pos: int) -> tuple[int, int, int, int, int]:
        if self.large_offsets:
            end, prop_count, prop_len = struct.unpack_from("<QQQ", self.data, pos)
            pos += 24
        else:
            end, prop_count, prop_len = struct.unpack_from("<III", self.data, pos)
            pos += 12
        name_len = self.data[pos]
        pos += 1
        return int(end), int(prop_count), int(prop_len), int(name_len), pos

    def _read_property(self, pos: int) -> tuple[Any, int]:
        prop_type = chr(self.data[pos])
        pos += 1
        if prop_type == "Y":
            return struct.unpack_from("<h", self.data, pos)[0], pos + 2
        if prop_type == "C":
            return bool(self.data[pos]), pos + 1
        if prop_type == "I":
            return struct.unpack_from("<i", self.data, pos)[0], pos + 4
        if prop_type == "F":
            return struct.unpack_from("<f", self.data, pos)[0], pos + 4
        if prop_type == "D":
            return struct.unpack_from("<d", self.data, pos)[0], pos + 8
        if prop_type == "L":
            return struct.unpack_from("<q", self.data, pos)[0], pos + 8
        if prop_type in {"f", "d", "i", "l", "b"}:
            count, encoding, byte_count = struct.unpack_from("<III", self.data, pos)
            pos += 12
            raw = self.data[pos:pos + byte_count]
            pos += byte_count
            if encoding == 1:
                raw = zlib.decompress(raw)
            return _array_from_bytes(prop_type, raw), pos
        if prop_type in {"S", "R"}:
            size = struct.unpack_from("<I", self.data, pos)[0]
            pos += 4
            raw = self.data[pos:pos + size]
            pos += size
            if prop_type == "S":
                return _decode_string(raw), pos
            return raw, pos
        raise ValueError(f"unsupported FBX property type {prop_type!r} at {pos}")

    def _is_null_record(self, pos: int) -> bool:
        return self.data[pos:pos + self.null_record_size] == b"\x00" * self.null_record_size

    def read_node(self, pos: int) -> tuple[BinaryFbxNode | None, int]:
        if pos + self.null_record_size > len(self.data):
            return None, pos
        if self._is_null_record(pos):
            return None, pos + self.null_record_size
        end, prop_count, _prop_len, name_len, pos = self._read_record_header(pos)
        if end == 0 and prop_count == 0 and name_len == 0:
            return None, pos
        name = _decode_string(self.data[pos:pos + name_len])
        pos += name_len
        props: list[Any] = []
        for _ in range(prop_count):
            prop, pos = self._read_property(pos)
            props.append(prop)
        children: list[BinaryFbxNode] = []
        while pos < end:
            child, next_pos = self.read_node(pos)
            pos = next_pos
            if child is None:
                break
            children.append(child)
        return BinaryFbxNode(name=name, props=props, children=children), end

    def read_roots(self) -> list[BinaryFbxNode]:
        roots: list[BinaryFbxNode] = []
        pos = self.header_size
        while pos + self.null_record_size <= len(self.data):
            child, next_pos = self.read_node(pos)
            pos = next_pos
            if child is None:
                break
            roots.append(child)
        return roots


def _children(node: BinaryFbxNode, name: str) -> list[BinaryFbxNode]:
    return [child for child in node.children if child.name == name]


def _child(node: BinaryFbxNode, name: str) -> BinaryFbxNode | None:
    for child in node.children:
        if child.name == name:
            return child
    return None


def _properties70(node: BinaryFbxNode | None) -> dict[str, list[Any]]:
    props: dict[str, list[Any]] = {}
    if node is None:
        return props
    properties_node = _child(node, "Properties70")
    if properties_node is None:
        return props
    for pnode in _children(properties_node, "P"):
        if len(pnode.props) >= 5:
            props[str(pnode.props[0])] = list(pnode.props[4:])
    return props


def _first_number(properties: dict[str, list[Any]], key: str, default: float) -> float:
    values = properties.get(key) or []
    if not values:
        return float(default)
    try:
        return float(values[0])
    except Exception:
        return float(default)


def _color_property(properties: dict[str, list[Any]], key: str) -> list[float] | None:
    values = properties.get(key) or []
    if len(values) < 3:
        return None
    try:
        return [max(0.0, min(1.0, float(values[idx]))) for idx in range(3)]
    except Exception:
        return None


def _axis_name(axis: int, sign: int) -> str:
    name = {0: "X", 1: "Y", 2: "Z"}.get(int(axis), "unknown")
    if name == "unknown":
        return name
    return name if int(sign) >= 0 else f"-{name}"


def _parse_global_settings(roots: list[BinaryFbxNode]) -> tuple[dict[str, Any], dict[str, Any]]:
    global_node = next((node for node in roots if node.name == "GlobalSettings"), None)
    properties = _properties70(global_node)
    unit_scale_factor = _first_number(properties, "UnitScaleFactor", 1.0)
    up_axis = int(_first_number(properties, "UpAxis", 1.0))
    up_axis_sign = int(_first_number(properties, "UpAxisSign", 1.0))
    front_axis = int(_first_number(properties, "FrontAxis", 2.0))
    front_axis_sign = int(_first_number(properties, "FrontAxisSign", -1.0))
    coord_axis = int(_first_number(properties, "CoordAxis", 0.0))
    coord_axis_sign = int(_first_number(properties, "CoordAxisSign", 1.0))
    return (
        {
            "scale_to_meters": float(unit_scale_factor) * 0.01,
            "unit_scale_factor": float(unit_scale_factor),
            "source": "fbx_global_settings" if global_node else "default",
        },
        {
            "up": _axis_name(up_axis, up_axis_sign),
            "forward": _axis_name(front_axis, front_axis_sign),
            "coord": _axis_name(coord_axis, coord_axis_sign),
            "source": "fbx_global_settings" if global_node else "default",
        },
    )


def _bounds_from_vertices(vertices: array) -> dict[str, list[float]]:
    if len(vertices) < 3:
        return {"center": [0.0, 0.0, 0.0], "size": [1.0, 1.0, 1.0]}
    min_x = min_y = min_z = math.inf
    max_x = max_y = max_z = -math.inf
    for idx in range(0, len(vertices) - 2, 3):
        x = float(vertices[idx])
        y = float(vertices[idx + 1])
        z = float(vertices[idx + 2])
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        min_z = min(min_z, z)
        max_x = max(max_x, x)
        max_y = max(max_y, y)
        max_z = max(max_z, z)
    return {
        "center": [(min_x + max_x) * 0.5, (min_y + max_y) * 0.5, (min_z + max_z) * 0.5],
        "size": [max(max_x - min_x, 1e-6), max(max_y - min_y, 1e-6), max(max_z - min_z, 1e-6)],
    }


def _merge_bounds(bounds_list: list[dict[str, list[float]]]) -> dict[str, list[float]]:
    if not bounds_list:
        return {"center": [0.0, 0.0, 0.0], "size": [1.0, 1.0, 1.0]}
    lows = []
    highs = []
    for bounds in bounds_list:
        center = bounds.get("center", [0.0, 0.0, 0.0])
        size = bounds.get("size", [1.0, 1.0, 1.0])
        lows.append([float(center[idx]) - float(size[idx]) * 0.5 for idx in range(3)])
        highs.append([float(center[idx]) + float(size[idx]) * 0.5 for idx in range(3)])
    lo = [min(row[idx] for row in lows) for idx in range(3)]
    hi = [max(row[idx] for row in highs) for idx in range(3)]
    return {
        "center": [(lo[idx] + hi[idx]) * 0.5 for idx in range(3)],
        "size": [max(hi[idx] - lo[idx], 1e-6) for idx in range(3)],
    }


def _rotation_matrix(rx_deg: float, ry_deg: float, rz_deg: float) -> tuple[tuple[float, float, float], ...]:
    def mm(a, b):
        return tuple(
            tuple(sum(a[row][k] * b[k][col] for k in range(3)) for col in range(3))
            for row in range(3)
        )

    rx = math.radians(rx_deg)
    ry = math.radians(ry_deg)
    rz = math.radians(rz_deg)
    sx, cx = math.sin(rx), math.cos(rx)
    sy, cy = math.sin(ry), math.cos(ry)
    sz, cz = math.sin(rz), math.cos(rz)
    mx = (
        (1.0, 0.0, 0.0),
        (0.0, cx, -sx),
        (0.0, sx, cx),
    )
    my = (
        (cy, 0.0, sy),
        (0.0, 1.0, 0.0),
        (-sy, 0.0, cy),
    )
    mz = (
        (cz, -sz, 0.0),
        (sz, cz, 0.0),
        (0.0, 0.0, 1.0),
    )
    # Blender FBX local transforms are exported in XYZ Euler order. Applying
    # them as the renderer's ZYX-style track rotation separates wheel/body
    # geometry for this asset.
    return mm(mz, mm(my, mx))


def _mat_mul_vec(m: tuple[tuple[float, float, float], ...], v: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    )


def _bounds_corners(bounds: dict[str, list[float]]) -> list[list[float]]:
    center = bounds.get("center", [0.0, 0.0, 0.0])
    size = bounds.get("size", [1.0, 1.0, 1.0])
    lows = [float(center[idx]) - float(size[idx]) * 0.5 for idx in range(3)]
    highs = [float(center[idx]) + float(size[idx]) * 0.5 for idx in range(3)]
    return [
        [x, y, z]
        for x in (lows[0], highs[0])
        for y in (lows[1], highs[1])
        for z in (lows[2], highs[2])
    ]


def _bounds_from_points(points: list[list[float]]) -> dict[str, list[float]]:
    if not points:
        return {"center": [0.0, 0.0, 0.0], "size": [1.0, 1.0, 1.0]}
    lo = [min(point[idx] for point in points) for idx in range(3)]
    hi = [max(point[idx] for point in points) for idx in range(3)]
    return {
        "center": [(lo[idx] + hi[idx]) * 0.5 for idx in range(3)],
        "size": [max(hi[idx] - lo[idx], 1e-6) for idx in range(3)],
    }


def _effective_model_scale(values: list[float]) -> tuple[float, float, float]:
    out = []
    for value in (values + [1.0, 1.0, 1.0])[:3]:
        scale = float(value)
        if abs(scale) > 10.0:
            scale *= 0.01
        out.append(scale)
    return (out[0], out[1], out[2])


def _transform_point(
    point: list[float],
    model: dict[str, Any] | None,
    *,
    unit_scale: float,
) -> list[float]:
    if not model:
        return [float(point[0]), float(point[1]), float(point[2])]
    scale = _effective_model_scale([float(v) for v in model.get("scale", [1.0, 1.0, 1.0])])
    rotation = [float(v) for v in (model.get("rotation", [0.0, 0.0, 0.0]) + [0.0, 0.0, 0.0])[:3]]
    translation = [float(v) * unit_scale for v in (model.get("translation", [0.0, 0.0, 0.0]) + [0.0, 0.0, 0.0])[:3]]
    local = (
        float(point[0]) * scale[0],
        float(point[1]) * scale[1],
        float(point[2]) * scale[2],
    )
    rotated = _mat_mul_vec(_rotation_matrix(rotation[0], rotation[1], rotation[2]), local)
    return [
        rotated[0] + translation[0],
        rotated[1] + translation[1],
        rotated[2] + translation[2],
    ]


def _transform_normal(normal: list[float], model: dict[str, Any] | None) -> list[float]:
    if not model:
        return [float(normal[0]), float(normal[1]), float(normal[2])]
    rotation = [float(v) for v in (model.get("rotation", [0.0, 0.0, 0.0]) + [0.0, 0.0, 0.0])[:3]]
    rotated = _mat_mul_vec(
        _rotation_matrix(rotation[0], rotation[1], rotation[2]),
        (float(normal[0]), float(normal[1]), float(normal[2])),
    )
    length = math.sqrt(rotated[0] * rotated[0] + rotated[1] * rotated[1] + rotated[2] * rotated[2])
    if length <= 1e-8:
        return [0.0, 0.0, 0.0]
    return [rotated[0] / length, rotated[1] / length, rotated[2] / length]


def _iter_triangle_corners(indices: array) -> Iterator[tuple[list[int], list[int]]]:
    polygon: list[int] = []
    polygon_vertices: list[int] = []
    polygon_vertex_idx = 0
    for raw in indices:
        value = int(raw)
        if value < 0:
            polygon.append(-value - 1)
            polygon_vertices.append(polygon_vertex_idx)
            if len(polygon) >= 3:
                first = polygon[0]
                first_pvi = polygon_vertices[0]
                for idx in range(1, len(polygon) - 1):
                    yield (
                        [first, polygon[idx], polygon[idx + 1]],
                        [first_pvi, polygon_vertices[idx], polygon_vertices[idx + 1]],
                    )
            polygon = []
            polygon_vertices = []
        else:
            polygon.append(value)
            polygon_vertices.append(polygon_vertex_idx)
        polygon_vertex_idx += 1
    if len(polygon) >= 3:
        first = polygon[0]
        first_pvi = polygon_vertices[0]
        for idx in range(1, len(polygon) - 1):
            yield (
                [first, polygon[idx], polygon[idx + 1]],
                [first_pvi, polygon_vertices[idx], polygon_vertices[idx + 1]],
            )


def _iter_triangles(indices: array) -> Iterator[list[int]]:
    for triangle, _polygon_vertices in _iter_triangle_corners(indices):
        yield triangle


def _polygon_count(indices: array) -> int:
    count = 0
    open_poly = False
    for raw in indices:
        open_poly = True
        if int(raw) < 0:
            count += 1
            open_poly = False
    return count + (1 if open_poly else 0)


def _sample_triangle_corners(indices: array, max_triangles: int) -> tuple[list[tuple[list[int], list[int]]], int]:
    source_count = sum(1 for _ in _iter_triangle_corners(indices))
    if source_count <= 0:
        return [], 0
    if source_count <= max_triangles:
        return list(_iter_triangle_corners(indices)), source_count
    stride = max(1, source_count // max_triangles)
    selected: list[tuple[list[int], list[int]]] = []
    for idx, triangle in enumerate(_iter_triangle_corners(indices)):
        if idx % stride == 0:
            selected.append(triangle)
            if len(selected) >= max_triangles:
                break
    return selected, source_count


def _sample_vertex_points(vertices: array, max_points: int) -> list[list[float]]:
    vertex_count = len(vertices) // 3
    if vertex_count <= 0 or max_points <= 0:
        return []
    sample_count = min(vertex_count, max_points)
    points: list[list[float]] = []
    if sample_count >= vertex_count:
        indices = range(vertex_count)
    else:
        step = float(vertex_count) / float(sample_count)
        indices = (min(vertex_count - 1, int(round(idx * step))) for idx in range(sample_count))
    for source_idx in indices:
        base = int(source_idx) * 3
        points.append([
            float(vertices[base]),
            float(vertices[base + 1]),
            float(vertices[base + 2]),
        ])
    return points


def _vertex_tuple(vertices: array, source_idx: int) -> tuple[float, float, float]:
    base = int(source_idx) * 3
    return (float(vertices[base]), float(vertices[base + 1]), float(vertices[base + 2]))


def _clustered_preview_mesh(
    vertices: array,
    indices: array,
    *,
    max_triangles: int,
) -> tuple[list[list[float]], list[list[int]], list[list[float]], list[list[float]], list[int]]:
    vertex_count = len(vertices) // 3
    if vertex_count <= 0 or max_triangles <= 0:
        return [], [], [], [], []
    bounds = _bounds_from_vertices(vertices)
    center = bounds.get("center") or [0.0, 0.0, 0.0]
    size = bounds.get("size") or [1.0, 1.0, 1.0]
    mins = [float(center[idx]) - float(size[idx]) * 0.5 for idx in range(3)]
    spans = [max(float(size[idx]), 1e-6) for idx in range(3)]

    def _cell_for_index(source_idx: int, divisions: int) -> tuple[int, int, int]:
        x, y, z = _vertex_tuple(vertices, source_idx)
        return (
            max(0, min(divisions - 1, int((x - mins[0]) / spans[0] * divisions))),
            max(0, min(divisions - 1, int((y - mins[1]) / spans[1] * divisions))),
            max(0, min(divisions - 1, int((z - mins[2]) / spans[2] * divisions))),
        )

    divisions = max(6, int(round(math.sqrt(max(32, max_triangles) / 12.0))))
    best: tuple[dict[tuple[int, int, int], list[float]], list[tuple[tuple[int, int, int], ...]]] | None = None
    for _attempt in range(2):
        accum: dict[tuple[int, int, int], list[float]] = {}
        out_cells: list[tuple[tuple[int, int, int], ...]] = []
        seen: set[tuple[tuple[int, int, int], ...]] = set()
        for triangle, _polygon_vertices in _iter_triangle_corners(indices):
            cells = tuple(_cell_for_index(source_idx, divisions) for source_idx in triangle)
            if len(set(cells)) < 3:
                continue
            key = tuple(sorted(cells))
            if key in seen:
                continue
            seen.add(key)
            out_cells.append(cells)
            for source_idx, cell in zip(triangle, cells):
                point = _vertex_tuple(vertices, source_idx)
                row = accum.setdefault(cell, [0.0, 0.0, 0.0, 0.0])
                row[0] += point[0]
                row[1] += point[1]
                row[2] += point[2]
                row[3] += 1.0
        if best is None or abs(len(out_cells) - max_triangles) < abs(len(best[1]) - max_triangles):
            best = (accum, out_cells)
        if len(out_cells) <= max_triangles:
            break
        divisions = max(4, int(round(divisions * 0.78)))

    if best is None:
        return [], [], [], [], []
    accum, out_cells = best
    if len(out_cells) > max_triangles:
        stride = max(1, len(out_cells) // max_triangles)
        out_cells = [tri for idx, tri in enumerate(out_cells) if idx % stride == 0][:max_triangles]

    index_by_cell: dict[tuple[int, int, int], int] = {}
    compact_vertices: list[list[float]] = []
    compact_triangles: list[list[int]] = []
    source_indices: list[int] = []
    for cells in out_cells:
        tri: list[int] = []
        for cell in cells:
            if cell not in index_by_cell:
                row = accum.get(cell) or [0.0, 0.0, 0.0, 1.0]
                count = max(float(row[3]), 1.0)
                index_by_cell[cell] = len(compact_vertices)
                compact_vertices.append([float(row[0]) / count, float(row[1]) / count, float(row[2]) / count])
                source_indices.append(-1)
            tri.append(index_by_cell[cell])
        if len(set(tri)) == 3:
            compact_triangles.append(tri)
    compact_uvs = [[0.0, 0.0] for _ in compact_vertices]
    compact_normals = [[0.0, 0.0, 0.0] for _ in compact_vertices]
    return compact_vertices, compact_triangles, compact_uvs, compact_normals, source_indices


def _layer_value(node: BinaryFbxNode | None, child_name: str) -> Any:
    child = _child(node, child_name) if node else None
    return child.props[0] if child and child.props else None


def _layer_text(node: BinaryFbxNode | None, child_name: str) -> str:
    value = _layer_value(node, child_name)
    return str(value or "")


def _uv_lookup(node: BinaryFbxNode | None, source_idx: int, polygon_vertex_idx: int) -> tuple[list[float], int]:
    if node is None:
        return [0.0, 0.0], -1
    uvs = _layer_value(node, "UV")
    uv_indices = _layer_value(node, "UVIndex")
    mapping = _layer_text(node, "MappingInformationType")
    reference = _layer_text(node, "ReferenceInformationType")
    if not isinstance(uvs, array) or len(uvs) < 2:
        return [0.0, 0.0], -1
    direct_idx = source_idx if mapping == "ByVertice" else polygon_vertex_idx
    if reference == "IndexToDirect" and isinstance(uv_indices, array):
        if 0 <= direct_idx < len(uv_indices):
            direct_idx = int(uv_indices[direct_idx])
        else:
            direct_idx = -1
    if direct_idx < 0 or direct_idx * 2 + 1 >= len(uvs):
        return [0.0, 0.0], -1
    return [float(uvs[direct_idx * 2]), float(uvs[direct_idx * 2 + 1])], int(direct_idx)


def _normal_lookup(node: BinaryFbxNode | None, source_idx: int, polygon_vertex_idx: int) -> list[float] | None:
    if node is None:
        return None
    normals = _layer_value(node, "Normals")
    normal_indices = _layer_value(node, "NormalsIndex")
    mapping = _layer_text(node, "MappingInformationType")
    reference = _layer_text(node, "ReferenceInformationType")
    if not isinstance(normals, array) or len(normals) < 3:
        return None
    direct_idx = source_idx if mapping == "ByVertice" else polygon_vertex_idx
    if reference == "IndexToDirect" and isinstance(normal_indices, array):
        if 0 <= direct_idx < len(normal_indices):
            direct_idx = int(normal_indices[direct_idx])
        else:
            direct_idx = -1
    if direct_idx < 0 or direct_idx * 3 + 2 >= len(normals):
        return None
    return [
        float(normals[direct_idx * 3]),
        float(normals[direct_idx * 3 + 1]),
        float(normals[direct_idx * 3 + 2]),
    ]


def _compact_vertices(
    vertices: array,
    triangle_corners: list[tuple[list[int], list[int]]],
    *,
    uv_node: BinaryFbxNode | None,
    normal_node: BinaryFbxNode | None,
) -> tuple[list[list[float]], list[list[int]], list[list[float]], list[list[float]], list[int], int, int]:
    mapping: dict[tuple[int, int], int] = {}
    compact_vertices: list[list[float]] = []
    compact_triangles: list[list[int]] = []
    compact_uvs: list[list[float]] = []
    compact_normals: list[list[float]] = []
    source_indices: list[int] = []
    vertex_count = len(vertices) // 3
    uv_hits = 0
    normal_hits = 0
    for triangle, polygon_vertices in triangle_corners:
        out_triangle: list[int] = []
        valid = True
        for source_idx, polygon_vertex_idx in zip(triangle, polygon_vertices):
            if source_idx < 0 or source_idx >= vertex_count:
                valid = False
                break
            uv, uv_key = _uv_lookup(uv_node, source_idx, polygon_vertex_idx)
            normal = _normal_lookup(normal_node, source_idx, polygon_vertex_idx)
            key = (source_idx, uv_key)
            if key not in mapping:
                dst = len(compact_vertices)
                mapping[key] = dst
                base = source_idx * 3
                compact_vertices.append([
                    float(vertices[base]),
                    float(vertices[base + 1]),
                    float(vertices[base + 2]),
                ])
                source_indices.append(source_idx)
                compact_uvs.append(uv)
                compact_normals.append(normal or [0.0, 0.0, 0.0])
                if uv_key >= 0:
                    uv_hits += 1
                if normal is not None:
                    normal_hits += 1
            out_triangle.append(mapping[key])
        if valid and len(out_triangle) == 3:
            compact_triangles.append(out_triangle)
    return compact_vertices, compact_triangles, compact_uvs, compact_normals, source_indices, uv_hits, normal_hits


def _parse_geometries(objects: BinaryFbxNode, *, max_triangles_per_geometry: int) -> list[dict[str, Any]]:
    geometries: list[dict[str, Any]] = []
    for node in _children(objects, "Geometry"):
        node_id = str(node.props[0]) if node.props else ""
        name = _clean_node_name(node.props[1] if len(node.props) > 1 else "", "Geometry")
        kind = str(node.props[2]).strip('"') if len(node.props) > 2 else "Mesh"
        vertices_node = _child(node, "Vertices")
        indices_node = _child(node, "PolygonVertexIndex")
        uv_node = _child(node, "LayerElementUV")
        normal_node = _child(node, "LayerElementNormal")
        vertices = vertices_node.props[0] if vertices_node and vertices_node.props else array("d")
        indices = indices_node.props[0] if indices_node and indices_node.props else array("i")
        if not isinstance(vertices, array) or not isinstance(indices, array):
            continue
        source_triangle_count = sum(1 for _ in _iter_triangle_corners(indices))
        if source_triangle_count > max_triangles_per_geometry:
            compact_vertices, compact_triangles, compact_uvs, compact_normals, source_indices = _clustered_preview_mesh(
                vertices,
                indices,
                max_triangles=max_triangles_per_geometry,
            )
            uv_hits = 0
            normal_hits = 0
            reduction_method = "grid_cluster_proxy"
        else:
            selected = list(_iter_triangle_corners(indices))
            compact_vertices, compact_triangles, compact_uvs, compact_normals, source_indices, uv_hits, normal_hits = _compact_vertices(
                vertices,
                selected,
                uv_node=uv_node,
                normal_node=normal_node,
            )
            reduction_method = "none"
        bounds = _bounds_from_vertices(vertices)
        preview_point_limit = max(4000, min(24000, max_triangles_per_geometry * 2))
        geometries.append({
            "id": node_id,
            "name": name or f"geometry_{len(geometries)}",
            "kind": kind or "Mesh",
            "vertex_count": len(vertices) // 3,
            "stored_vertex_count": len(compact_vertices),
            "polygon_index_count": len(indices),
            "polygon_count": _polygon_count(indices),
            "source_triangle_count": source_triangle_count,
            "triangle_count": len(compact_triangles),
            "decimated": source_triangle_count > len(compact_triangles),
            "reduction_method": reduction_method,
            "bounds": bounds,
            "vertices": compact_vertices,
            "triangles": compact_triangles,
            "uvs": compact_uvs,
            "normals": compact_normals,
            "preview_points": _sample_vertex_points(vertices, preview_point_limit),
            "uv_count": len(compact_uvs),
            "normal_count": len(compact_normals),
            "uv_hit_count": uv_hits,
            "normal_hit_count": normal_hits,
            "source_indices": source_indices,
        })
    return geometries


def _material_defaults(name: str) -> dict[str, Any]:
    lowered = name.casefold()
    if "wheel" in lowered or "tire" in lowered:
        return {
            "base_color": [0.02, 0.022, 0.024, 1.0],
            "roughness": 0.72,
            "metallic": 0.0,
            "reflectance": 0.28,
        }
    if "glass" in lowered:
        return {
            "base_color": [0.12, 0.20, 0.28, 0.55],
            "roughness": 0.08,
            "metallic": 0.0,
            "reflectance": 0.9,
        }
    return {
        "base_color": [0.95, 0.24, 0.05, 1.0],
        "roughness": 0.38,
        "metallic": 0.0,
        "reflectance": 0.48,
    }


def _parse_materials(objects: BinaryFbxNode) -> list[dict[str, Any]]:
    materials: list[dict[str, Any]] = []
    for node in _children(objects, "Material"):
        node_id = str(node.props[0]) if node.props else ""
        name = _clean_node_name(node.props[1] if len(node.props) > 1 else "", "Material") or f"material_{len(materials)}"
        properties = _properties70(node)
        defaults = _material_defaults(name)
        diffuse = _color_property(properties, "DiffuseColor")
        if diffuse:
            defaults["base_color"] = [*diffuse, 1.0]
        if "SpecularFactor" in properties:
            defaults["reflectance"] = max(0.0, min(1.0, _first_number(properties, "SpecularFactor", defaults["reflectance"])))
        if "Shininess" in properties:
            defaults["roughness"] = max(0.02, min(1.0, 1.0 - _first_number(properties, "Shininess", 50.0) / 100.0))
        materials.append({"id": node_id, "name": name, **defaults})
    return materials


def _parse_models(objects: BinaryFbxNode) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    for node in _children(objects, "Model"):
        props = _properties70(node)
        models.append({
            "id": str(node.props[0]) if node.props else "",
            "name": _clean_node_name(node.props[1] if len(node.props) > 1 else "", "Model") or f"model_{len(models)}",
            "kind": str(node.props[2]) if len(node.props) > 2 else "",
            "translation": [float(v) for v in (props.get("Lcl Translation") or [0.0, 0.0, 0.0])[:3]],
            "rotation": [float(v) for v in (props.get("Lcl Rotation") or [0.0, 0.0, 0.0])[:3]],
            "scale": [float(v) for v in (props.get("Lcl Scaling") or [1.0, 1.0, 1.0])[:3]],
        })
    return models


def _parse_connections(roots: list[BinaryFbxNode]) -> list[dict[str, str]]:
    conns_node = next((node for node in roots if node.name == "Connections"), None)
    if conns_node is None:
        return []
    connections: list[dict[str, str]] = []
    for node in _children(conns_node, "C"):
        if len(node.props) >= 3:
            row = {
                "type": str(node.props[0]),
                "child": str(node.props[1]),
                "parent": str(node.props[2]),
            }
            if len(node.props) >= 4:
                row["property"] = str(node.props[3])
            connections.append(row)
    return connections


def _apply_model_parent_ids(models: list[dict[str, Any]], connections: list[dict[str, str]]) -> list[dict[str, Any]]:
    model_ids = {str(model.get("id") or "") for model in models}
    parent_by_id: dict[str, str] = {}
    for connection in connections:
        child = str(connection.get("child") or "")
        parent = str(connection.get("parent") or "")
        if child in model_ids and parent in model_ids:
            parent_by_id[child] = parent
    out: list[dict[str, Any]] = []
    for model in models:
        row = dict(model)
        parent_id = parent_by_id.get(str(model.get("id") or ""))
        if parent_id:
            row["parent_id"] = parent_id
        out.append(row)
    return out


def _axis_from_property(value: str) -> str:
    text = str(value or "").strip().casefold()
    if text.endswith("x") or text in {"x", "d|x"}:
        return "x"
    if text.endswith("y") or text in {"y", "d|y"}:
        return "y"
    if text.endswith("z") or text in {"z", "d|z"}:
        return "z"
    return "x"


def _curve_property_name(value: str) -> str:
    text = str(value or "").casefold()
    if "scal" in text:
        return "scale"
    if "rot" in text:
        return "rotation"
    return "translation"


def _parse_animation_clips(objects: BinaryFbxNode, connections: list[dict[str, str]]) -> list[dict[str, Any]]:
    curves: dict[str, dict[str, Any]] = {}
    curve_nodes: dict[str, dict[str, Any]] = {}
    stacks: list[dict[str, Any]] = []
    for node in _children(objects, "AnimationCurve"):
        curve_id = str(node.props[0]) if node.props else ""
        times_node = _child(node, "KeyTime")
        values_node = _child(node, "KeyValueFloat")
        times = times_node.props[0] if times_node and times_node.props else []
        values = values_node.props[0] if values_node and values_node.props else []
        if not isinstance(times, array) or not isinstance(values, array):
            continue
        keyframes: list[list[float]] = []
        for idx, raw_time in enumerate(times):
            if idx >= len(values):
                break
            keyframes.append([ticks_to_ms(raw_time), float(values[idx])])
        if curve_id and keyframes:
            curves[curve_id] = {"id": curve_id, "keyframes": keyframes}
    for node in _children(objects, "AnimationCurveNode"):
        node_id = str(node.props[0]) if node.props else ""
        if node_id:
            curve_nodes[node_id] = {
                "id": node_id,
                "name": _clean_node_name(node.props[1] if len(node.props) > 1 else "", "AnimationCurveNode"),
            }
    for node in _children(objects, "AnimationStack"):
        stack_id = str(node.props[0]) if node.props else f"clip_{len(stacks) + 1}"
        stack_name = _clean_node_name(node.props[1] if len(node.props) > 1 else "", "AnimationStack")
        stack_name = _clean_node_name(stack_name, "AnimStack")
        stacks.append({
            "id": stack_id,
            "name": stack_name or f"clip_{len(stacks) + 1}",
        })

    curve_to_node: dict[str, tuple[str, str]] = {}
    node_to_model: dict[str, tuple[str, str]] = {}
    for connection in connections:
        child = str(connection.get("child") or "")
        parent = str(connection.get("parent") or "")
        prop = str(connection.get("property") or "")
        if child in curves and parent in curve_nodes:
            curve_to_node[child] = (parent, _axis_from_property(prop))
        elif child in curve_nodes:
            node_to_model[child] = (parent, _curve_property_name(prop or curve_nodes[child].get("name", "")))

    model_curves: dict[str, dict[str, dict[str, list[list[float]]]]] = {}
    max_ms = 0.0
    for curve_id, curve in curves.items():
        node_id, axis = curve_to_node.get(curve_id, ("", "x"))
        if not node_id:
            continue
        model_id, prop_name = node_to_model.get(node_id, ("", "translation"))
        if not model_id:
            continue
        rows = list(curve.get("keyframes") or [])
        if rows:
            max_ms = max(max_ms, max(float(row[0]) for row in rows))
        model_curves.setdefault(model_id, {}).setdefault(prop_name, {})[axis] = rows

    if not model_curves and not stacks:
        return []
    if not stacks:
        stacks = [{"id": "clip_001", "name": "Take 001"}]
    return [
        {
            "id": str(stack.get("id") or f"clip_{idx + 1:03d}"),
            "name": str(stack.get("name") or f"clip_{idx + 1:03d}"),
            "duration_ms": max_ms,
            "model_curves": model_curves,
        }
        for idx, stack in enumerate(stacks)
    ]


def _parse_skeleton_metadata(
    objects: BinaryFbxNode,
    models: list[dict[str, Any]],
    connections: list[dict[str, str]],
) -> dict[str, Any]:
    bone_kinds = {"limbnode", "root", "skeleton"}
    bones = [
        {
            "id": str(model.get("id") or ""),
            "name": str(model.get("name") or ""),
            "parent_id": "",
            "kind": str(model.get("kind") or ""),
        }
        for model in models
        if str(model.get("kind") or "").casefold() in bone_kinds
    ]
    by_id = {bone["id"]: bone for bone in bones}
    for connection in connections:
        child = str(connection.get("child") or "")
        parent = str(connection.get("parent") or "")
        if child in by_id and parent in by_id:
            by_id[child]["parent_id"] = parent
    skin_count = 0
    cluster_count = 0
    for node in _children(objects, "Deformer"):
        kind = str(node.props[2] if len(node.props) > 2 else "").casefold()
        if kind == "skin":
            skin_count += 1
        elif kind == "cluster":
            cluster_count += 1
    roots = [bone for bone in bones if not bone.get("parent_id")]
    return {
        "bones": bones,
        "skeletons": [{"root_bone_id": bone["id"], "root_bone_name": bone["name"]} for bone in roots],
        "skin_count": skin_count,
        "cluster_count": cluster_count,
        "skeletal_mesh_count": 1 if bones or skin_count or cluster_count else 0,
    }


def _attach_skin_weights(
    objects: BinaryFbxNode,
    geometries: list[dict[str, Any]],
    connections: list[dict[str, str]],
    models: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cluster_rows: dict[str, dict[str, Any]] = {}
    skin_ids: set[str] = set()
    for node in _children(objects, "Deformer"):
        node_id = str(node.props[0]) if node.props else ""
        kind = str(node.props[2] if len(node.props) > 2 else "").casefold()
        if kind == "skin":
            skin_ids.add(node_id)
            continue
        if kind != "cluster":
            continue
        indexes = _layer_value(node, "Indexes")
        weights = _layer_value(node, "Weights")
        if not isinstance(indexes, array) or not isinstance(weights, array):
            continue
        cluster_rows[node_id] = {
            "id": node_id,
            "indices": [int(v) for v in indexes],
            "weights": [float(v) for v in weights],
            "skin_id": "",
            "bone_id": "",
            "bone_name": "",
        }
    cluster_ids = set(cluster_rows)
    model_names = {str(model.get("id") or ""): str(model.get("name") or "") for model in models}
    skin_to_geometry: dict[str, str] = {}
    for connection in connections:
        child = str(connection.get("child") or "")
        parent = str(connection.get("parent") or "")
        if child in cluster_ids and parent in skin_ids:
            cluster_rows[child]["skin_id"] = parent
        elif parent in cluster_ids and child in model_names:
            cluster_rows[parent]["bone_id"] = child
            cluster_rows[parent]["bone_name"] = model_names.get(child, "")
        elif child in skin_ids:
            skin_to_geometry[child] = parent

    if not cluster_rows or not skin_to_geometry:
        return geometries
    influences_by_geometry_source: dict[str, dict[int, list[dict[str, Any]]]] = {}
    for cluster in cluster_rows.values():
        geometry_id = skin_to_geometry.get(str(cluster.get("skin_id") or ""))
        bone_id = str(cluster.get("bone_id") or "")
        if not geometry_id or not bone_id:
            continue
        source_map = influences_by_geometry_source.setdefault(geometry_id, {})
        indices = cluster.get("indices") or []
        weights = cluster.get("weights") or []
        for idx, source_idx in enumerate(indices):
            if idx >= len(weights):
                break
            weight = float(weights[idx])
            if weight <= 0.0:
                continue
            source_map.setdefault(int(source_idx), []).append({
                "bone_id": bone_id,
                "bone_name": str(cluster.get("bone_name") or ""),
                "weight": weight,
            })

    out: list[dict[str, Any]] = []
    for geometry in geometries:
        geometry_id = str(geometry.get("id") or "")
        source_map = influences_by_geometry_source.get(geometry_id)
        if not source_map:
            out.append(geometry)
            continue
        source_indices = geometry.get("source_indices") if isinstance(geometry.get("source_indices"), list) else []
        skin_weights: list[list[dict[str, Any]]] = []
        for compact_idx in range(len(geometry.get("vertices") or [])):
            source_idx = int(source_indices[compact_idx]) if compact_idx < len(source_indices) else -1
            rows = list(source_map.get(source_idx, [])) if source_idx >= 0 else []
            total = sum(float(row.get("weight", 0.0) or 0.0) for row in rows)
            if total > 1e-8:
                rows = [
                    {**row, "weight": float(row.get("weight", 0.0) or 0.0) / total}
                    for row in rows
                ]
            skin_weights.append(rows)
        updated = dict(geometry)
        updated["skin_weights"] = skin_weights
        updated["skin_influence_count"] = sum(1 for row in skin_weights if row)
        out.append(updated)
    return out


def _geometry_model_map(geometries: list[dict[str, Any]], connections: list[dict[str, str]]) -> dict[str, str]:
    geometry_ids = {str(geometry.get("id") or "") for geometry in geometries}
    out: dict[str, str] = {}
    for connection in connections:
        child = str(connection.get("child") or "")
        parent = str(connection.get("parent") or "")
        if child in geometry_ids:
            out[child] = parent
    return out


def _apply_model_transforms(
    geometries: list[dict[str, Any]],
    models: list[dict[str, Any]],
    connections: list[dict[str, str]],
    *,
    unit_scale: float,
) -> list[dict[str, Any]]:
    model_by_id = {str(model.get("id") or ""): model for model in models}
    geometry_to_model = _geometry_model_map(geometries, connections)
    transformed: list[dict[str, Any]] = []
    for geometry in geometries:
        out = dict(geometry)
        model_id = geometry_to_model.get(str(geometry.get("id") or ""), "")
        model = model_by_id.get(model_id)
        out["model_id"] = model_id
        out["local_bounds"] = geometry.get("bounds")
        out["model_transform_applied"] = model is not None
        out["vertices"] = [
            _transform_point(point, model, unit_scale=unit_scale)
            for point in geometry.get("vertices", [])
        ]
        out["preview_points"] = [
            _transform_point(point, model, unit_scale=unit_scale)
            for point in geometry.get("preview_points", [])
        ]
        out["normals"] = [
            _transform_normal(normal, model)
            for normal in geometry.get("normals", [])
        ]
        out["bounds"] = _bounds_from_points([
            _transform_point(point, model, unit_scale=unit_scale)
            for point in _bounds_corners(geometry.get("bounds") or {})
        ])
        transformed.append(out)
    return transformed


def parse_binary_fbx_metadata(
    path: str | Path,
    *,
    max_triangles_per_geometry: int = DEFAULT_MAX_TRIANGLES_PER_GEOMETRY,
) -> tuple[dict[str, Any], str]:
    fbx_path = Path(path)
    try:
        data = fbx_path.read_bytes()
    except Exception as exc:
        return {}, f"internal_binary_fbx failed to read file: {type(exc).__name__}: {exc}"
    if not data.startswith(BINARY_FBX_MAGIC):
        return {}, "internal_binary_fbx skipped non-binary FBX"
    try:
        reader = BinaryFbxReader(data)
        roots = reader.read_roots()
        objects = next((node for node in roots if node.name == "Objects"), None)
        if objects is None:
            return {}, "internal_binary_fbx found no Objects node"
        geometries = _parse_geometries(objects, max_triangles_per_geometry=max_triangles_per_geometry)
        models = _parse_models(objects)
        materials = _parse_materials(objects)
        connections = _parse_connections(roots)
        models = _apply_model_parent_ids(models, connections)
        animation_clips = _parse_animation_clips(objects, connections)
        skeleton = _parse_skeleton_metadata(objects, models, connections)
        units, axes = _parse_global_settings(roots)
        geometries = _attach_skin_weights(objects, geometries, connections, models)
        geometries = _apply_model_transforms(
            geometries,
            models,
            connections,
            unit_scale=float(units.get("scale_to_meters", 1.0) or 1.0),
        )
        if not geometries and not models and not materials:
            return {}, "internal_binary_fbx found no scene objects"
        return {
            "parser": "internal_binary_fbx",
            "fbx_version": reader.version,
            "mesh_count": sum(1 for item in geometries if str(item.get("kind") or "").casefold() in {"mesh", ""}),
            "geometry_count": len(geometries),
            "model_count": len(models),
            "material_count": len(materials),
            "animation_count": max(len(animation_clips), sum(1 for node in roots if node.name == "Takes")),
            "animation_clips": animation_clips,
            "skeletal_mesh_count": skeleton["skeletal_mesh_count"],
            "skin_count": skeleton["skin_count"],
            "skeletons": skeleton["skeletons"],
            "bones": skeleton["bones"],
            "texture_count": 0,
            "bounds": _merge_bounds([item["bounds"] for item in geometries]),
            "units": units,
            "axes": axes,
            "geometries": geometries,
            "models": models,
            "materials": materials,
            "connections": connections,
            "warnings": [
                "binary FBX geometry is decimated for CPU preview"
            ] if any(item.get("decimated") for item in geometries) else [],
        }, ""
    except Exception as exc:
        return {}, f"internal_binary_fbx failed: {type(exc).__name__}: {exc}"
