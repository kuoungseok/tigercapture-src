"""Small ASCII FBX metadata parser for AR/PBR asset import.

This is not a full FBX SDK replacement. It extracts the stable scene metadata
the renderer pipeline needs before a native importer is available: mesh bounds,
material slots, model names, units, axes, and basic animation presence.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Iterator

from app.ar_pbr.animation import ticks_to_ms


BINARY_FBX_MAGIC = b"Kaydara FBX Binary"
MAX_ASCII_FBX_BYTES = 64 * 1024 * 1024
_NUMBER_RE = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")


def _parse_csv_tokens(payload: str) -> list[str]:
    try:
        return [part.strip() for part in next(csv.reader([payload], skipinitialspace=True))]
    except Exception:
        return [part.strip().strip('"') for part in payload.split(",")]


def _clean_node_name(value: str, prefix: str) -> str:
    text = str(value or "").strip().strip('"')
    if "::" in text:
        head, tail = text.split("::", 1)
        if head.casefold() == prefix.casefold():
            return tail
    return text


def _matching_brace(text: str, open_idx: int) -> int:
    depth = 0
    in_string = False
    escape = False
    for idx in range(open_idx, len(text)):
        ch = text[idx]
        if in_string:
            if ch == "\\" and not escape:
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = False
            escape = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def _iter_blocks(text: str, name: str) -> Iterator[tuple[str, str]]:
    pattern = re.compile(rf"(?m)(?<![A-Za-z0-9_]){re.escape(name)}\s*:\s*([^\{{\r\n]*)\{{")
    cursor = 0
    while True:
        match = pattern.search(text, cursor)
        if not match:
            break
        open_idx = match.end() - 1
        close_idx = _matching_brace(text, open_idx)
        if close_idx < 0:
            break
        yield match.group(1).strip(), text[open_idx + 1:close_idx]
        cursor = close_idx + 1


def _numbers_from_array_block(body: str, name: str, *, as_int: bool = False) -> list[float] | list[int]:
    match = re.search(rf"(?s)(?<![A-Za-z0-9_]){re.escape(name)}\s*:\s*\*\d+\s*\{{(.*?)\}}", body)
    if not match:
        return []
    payload = match.group(1)
    marker = payload.find("a:")
    if marker >= 0:
        payload = payload[marker + 2:]
    values = _NUMBER_RE.findall(payload)
    if as_int:
        return [int(float(value)) for value in values]
    return [float(value) for value in values]


def _bounds_from_vertices(vertices: list[float]) -> dict[str, list[float]]:
    if len(vertices) < 3:
        return {
            "center": [0.0, 0.0, 0.0],
            "size": [1.0, 1.0, 1.0],
        }
    xs = vertices[0::3]
    ys = vertices[1::3]
    zs = vertices[2::3]
    lo = [min(xs), min(ys), min(zs)]
    hi = [max(xs), max(ys), max(zs)]
    center = [(lo[idx] + hi[idx]) * 0.5 for idx in range(3)]
    size = [max(hi[idx] - lo[idx], 1e-6) for idx in range(3)]
    return {
        "center": [float(value) for value in center],
        "size": [float(value) for value in size],
    }


def _triangulate_polygon_indices(indices: list[int]) -> tuple[list[list[int]], list[list[int]]]:
    polygons: list[list[int]] = []
    current: list[int] = []
    for raw in indices:
        value = int(raw)
        if value < 0:
            current.append(-value - 1)
            if len(current) >= 3:
                polygons.append(current)
            current = []
        else:
            current.append(value)
    if len(current) >= 3:
        polygons.append(current)

    triangles: list[list[int]] = []
    for polygon in polygons:
        first = polygon[0]
        for idx in range(1, len(polygon) - 1):
            triangles.append([first, polygon[idx], polygon[idx + 1]])
    return polygons, triangles


def _triangulate_polygon_corners(indices: list[int]) -> tuple[list[list[int]], list[tuple[list[int], list[int]]]]:
    polygons: list[list[int]] = []
    triangle_corners: list[tuple[list[int], list[int]]] = []
    polygon: list[int] = []
    polygon_vertices: list[int] = []
    polygon_vertex_idx = 0
    for raw in indices:
        value = int(raw)
        if value < 0:
            polygon.append(-value - 1)
            polygon_vertices.append(polygon_vertex_idx)
            if len(polygon) >= 3:
                polygons.append(list(polygon))
                first = polygon[0]
                first_pvi = polygon_vertices[0]
                for idx in range(1, len(polygon) - 1):
                    triangle_corners.append((
                        [first, polygon[idx], polygon[idx + 1]],
                        [first_pvi, polygon_vertices[idx], polygon_vertices[idx + 1]],
                    ))
            polygon = []
            polygon_vertices = []
        else:
            polygon.append(value)
            polygon_vertices.append(polygon_vertex_idx)
        polygon_vertex_idx += 1
    if len(polygon) >= 3:
        polygons.append(list(polygon))
        first = polygon[0]
        first_pvi = polygon_vertices[0]
        for idx in range(1, len(polygon) - 1):
            triangle_corners.append((
                [first, polygon[idx], polygon[idx + 1]],
                [first_pvi, polygon_vertices[idx], polygon_vertices[idx + 1]],
            ))
    return polygons, triangle_corners


def _vertices_as_triplets(vertices: list[float]) -> list[list[float]]:
    triplets: list[list[float]] = []
    for idx in range(0, len(vertices) - 2, 3):
        triplets.append([
            float(vertices[idx]),
            float(vertices[idx + 1]),
            float(vertices[idx + 2]),
        ])
    return triplets


def _merge_bounds(bounds_list: list[dict[str, list[float]]]) -> dict[str, list[float]]:
    if not bounds_list:
        return {
            "center": [0.0, 0.0, 0.0],
            "size": [1.0, 1.0, 1.0],
        }
    lows: list[list[float]] = []
    highs: list[list[float]] = []
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


def _parse_properties(body: str) -> dict[str, list[Any]]:
    properties: dict[str, list[Any]] = {}
    for match in re.finditer(r"(?m)^\s*P\s*:\s*(.+)$", body):
        parts = _parse_csv_tokens(match.group(1))
        if len(parts) < 5:
            continue
        key = parts[0].strip().strip('"')
        values: list[Any] = []
        for raw in parts[4:]:
            value = raw.strip().strip('"')
            number = _NUMBER_RE.fullmatch(value)
            if number:
                parsed = float(value)
                if parsed.is_integer():
                    values.append(int(parsed))
                else:
                    values.append(parsed)
            else:
                values.append(value)
        properties[key] = values
    return properties


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


def _first_existing_color(properties: dict[str, list[Any]], keys: tuple[str, ...]) -> list[float] | None:
    for key in keys:
        color = _color_property(properties, key)
        if color is not None:
            return color
    return None


def _first_existing_number(properties: dict[str, list[Any]], keys: tuple[str, ...], default: float) -> float:
    for key in keys:
        if key in properties:
            return _first_number(properties, key, default)
    return float(default)


def _field_text(body: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*:\s*(.+)$", body)
    if not match:
        return ""
    tokens = _parse_csv_tokens(match.group(1))
    if not tokens:
        return ""
    return tokens[0].strip().strip('"')


def _first_uv_layer(body: str) -> dict[str, Any] | None:
    for _header, layer_body in _iter_blocks(body, "LayerElementUV"):
        values = _numbers_from_array_block(layer_body, "UV")
        if len(values) < 2:
            continue
        indices = _numbers_from_array_block(layer_body, "UVIndex", as_int=True)
        return {
            "uv": values,
            "indices": indices,
            "mapping": _field_text(layer_body, "MappingInformationType"),
            "reference": _field_text(layer_body, "ReferenceInformationType"),
        }
    return None


def _uv_lookup(layer: dict[str, Any] | None, source_idx: int, polygon_vertex_idx: int) -> tuple[list[float], int]:
    if layer is None:
        return [0.0, 0.0], -1
    values = layer.get("uv") if isinstance(layer.get("uv"), list) else []
    if len(values) < 2:
        return [0.0, 0.0], -1
    mapping = str(layer.get("mapping") or "").casefold()
    reference = str(layer.get("reference") or "").casefold()
    direct_idx = int(source_idx) if mapping in {"byvertice", "byvertex"} else int(polygon_vertex_idx)
    uv_indices = layer.get("indices") if isinstance(layer.get("indices"), list) else []
    if reference == "indextodirect" and uv_indices:
        if 0 <= direct_idx < len(uv_indices):
            direct_idx = int(uv_indices[direct_idx])
        else:
            direct_idx = -1
    if direct_idx < 0 or direct_idx * 2 + 1 >= len(values):
        return [0.0, 0.0], -1
    return [float(values[direct_idx * 2]), float(values[direct_idx * 2 + 1])], int(direct_idx)


def _compact_vertices_for_uvs(
    vertices: list[float],
    triangle_corners: list[tuple[list[int], list[int]]],
    uv_layer: dict[str, Any] | None,
) -> tuple[list[list[float]], list[list[int]], list[list[float]], list[int], int]:
    vertex_count = len(vertices) // 3
    mapping: dict[tuple[int, int], int] = {}
    compact_vertices: list[list[float]] = []
    compact_triangles: list[list[int]] = []
    compact_uvs: list[list[float]] = []
    source_indices: list[int] = []
    uv_hits = 0
    for triangle, polygon_vertices in triangle_corners:
        out_triangle: list[int] = []
        valid = True
        for source_idx, polygon_vertex_idx in zip(triangle, polygon_vertices):
            source_idx = int(source_idx)
            if source_idx < 0 or source_idx >= vertex_count:
                valid = False
                break
            uv, uv_key = _uv_lookup(uv_layer, source_idx, int(polygon_vertex_idx))
            key = (source_idx, uv_key)
            if key not in mapping:
                base = source_idx * 3
                mapping[key] = len(compact_vertices)
                compact_vertices.append([
                    float(vertices[base]),
                    float(vertices[base + 1]),
                    float(vertices[base + 2]),
                ])
                compact_uvs.append(uv)
                source_indices.append(source_idx)
                if uv_key >= 0:
                    uv_hits += 1
            out_triangle.append(mapping[key])
        if valid and len(out_triangle) == 3:
            compact_triangles.append(out_triangle)
    return compact_vertices, compact_triangles, compact_uvs, source_indices, uv_hits


def _axis_name(axis: int, sign: int) -> str:
    name = {0: "X", 1: "Y", 2: "Z"}.get(int(axis), "unknown")
    if name == "unknown":
        return name
    return name if int(sign) >= 0 else f"-{name}"


def _parse_global_settings(text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    body = ""
    for _, block in _iter_blocks(text, "GlobalSettings"):
        body = block
        break
    properties = _parse_properties(body)
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
            "source": "fbx_global_settings" if body else "default",
        },
        {
            "up": _axis_name(up_axis, up_axis_sign),
            "forward": _axis_name(front_axis, front_axis_sign),
            "coord": _axis_name(coord_axis, coord_axis_sign),
            "source": "fbx_global_settings" if body else "default",
        },
    )


def _parse_geometries(text: str) -> list[dict[str, Any]]:
    geometries: list[dict[str, Any]] = []
    for header, body in _iter_blocks(text, "Geometry"):
        tokens = _parse_csv_tokens(header)
        node_id = str(tokens[0]) if tokens else ""
        name = _clean_node_name(tokens[1] if len(tokens) > 1 else "", "Geometry")
        kind = tokens[2].strip().strip('"') if len(tokens) > 2 else ""
        vertices = _numbers_from_array_block(body, "Vertices")
        poly_indices = _numbers_from_array_block(body, "PolygonVertexIndex", as_int=True)
        uv_layer = _first_uv_layer(body)
        if uv_layer is not None:
            polygons, triangle_corners = _triangulate_polygon_corners(poly_indices)  # type: ignore[arg-type]
            stored_vertices, triangles, uvs, source_indices, uv_hits = _compact_vertices_for_uvs(
                vertices,  # type: ignore[arg-type]
                triangle_corners,
                uv_layer,
            )
        else:
            polygons, triangles = _triangulate_polygon_indices(poly_indices)  # type: ignore[arg-type]
            stored_vertices = _vertices_as_triplets(vertices)  # type: ignore[arg-type]
            uvs = []
            source_indices = []
            uv_hits = 0
        bounds = _bounds_from_vertices(vertices)  # type: ignore[arg-type]
        geometry: dict[str, Any] = {
            "id": node_id,
            "name": name or f"geometry_{len(geometries)}",
            "kind": kind or "Mesh",
            "vertex_count": len(vertices) // 3,
            "stored_vertex_count": len(stored_vertices),
            "polygon_index_count": len(poly_indices),
            "polygon_count": len(polygons),
            "triangle_count": len(triangles),
            "bounds": bounds,
            "vertices": stored_vertices,
            "polygons": polygons,
            "triangles": triangles,
        }
        if uvs:
            geometry["uvs"] = uvs
            geometry["uv_count"] = len(uvs)
            geometry["uv_hit_count"] = uv_hits
            geometry["source_indices"] = source_indices
        geometries.append(geometry)
    return geometries


def _parse_models(text: str) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    for header, body in _iter_blocks(text, "Model"):
        tokens = _parse_csv_tokens(header)
        properties = _parse_properties(body)
        models.append({
            "id": str(tokens[0]) if tokens else "",
            "name": _clean_node_name(tokens[1] if len(tokens) > 1 else "", "Model") or f"model_{len(models)}",
            "kind": tokens[2].strip().strip('"') if len(tokens) > 2 else "",
            "translation": [float(v) for v in (properties.get("Lcl Translation") or [0.0, 0.0, 0.0])[:3]],
            "rotation": [float(v) for v in (properties.get("Lcl Rotation") or [0.0, 0.0, 0.0])[:3]],
            "scale": [float(v) for v in (properties.get("Lcl Scaling") or [1.0, 1.0, 1.0])[:3]],
        })
    return models


def _parse_materials(text: str) -> list[dict[str, Any]]:
    materials: list[dict[str, Any]] = []
    for header, body in _iter_blocks(text, "Material"):
        tokens = _parse_csv_tokens(header)
        properties = _parse_properties(body)
        diffuse = _first_existing_color(properties, (
            "Maya|base_color",
            "Maya|BaseColor",
            "base_color",
            "BaseColor",
            "DiffuseColor",
        ))
        specular_factor = _first_existing_number(properties, (
            "Maya|specular",
            "Maya|Specular",
            "SpecularFactor",
            "Reflectance",
        ), 0.5)
        roughness = _first_existing_number(properties, (
            "Maya|roughness",
            "Maya|Roughness",
            "roughness",
            "Roughness",
        ), -1.0)
        if roughness < 0.0:
            shininess = _first_number(properties, "Shininess", 50.0)
            roughness = 1.0 - shininess / 100.0
        metallic = _first_existing_number(properties, (
            "Maya|metallic",
            "Maya|Metallic",
            "metallic",
            "Metallic",
            "Metalness",
        ), 0.0)
        materials.append({
            "id": str(tokens[0]) if tokens else "",
            "name": _clean_node_name(tokens[1] if len(tokens) > 1 else "", "Material") or f"material_{len(materials)}",
            "base_color": [*(diffuse or [1.0, 1.0, 1.0]), 1.0],
            "roughness": max(0.02, min(1.0, roughness)),
            "metallic": max(0.0, min(1.0, metallic)),
            "reflectance": max(0.0, min(1.0, specular_factor)),
        })
    return materials


def _parse_connections(text: str) -> list[dict[str, str]]:
    connections: list[dict[str, str]] = []
    for _, body in _iter_blocks(text, "Connections"):
        for match in re.finditer(r"(?m)^\s*C\s*:\s*(.+)$", body):
            parts = _parse_csv_tokens(match.group(1))
            if len(parts) >= 3:
                row = {
                    "type": parts[0].strip().strip('"'),
                    "child": parts[1].strip().strip('"'),
                    "parent": parts[2].strip().strip('"'),
                }
                if len(parts) >= 4:
                    row["property"] = parts[3].strip().strip('"')
                connections.append(row)
        break
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


def _parse_animation_curves(text: str, connections: list[dict[str, str]]) -> list[dict[str, Any]]:
    curves: dict[str, dict[str, Any]] = {}
    curve_nodes: dict[str, dict[str, Any]] = {}
    stacks: list[dict[str, Any]] = []
    for header, body in _iter_blocks(text, "AnimationCurve"):
        tokens = _parse_csv_tokens(header)
        curve_id = str(tokens[0]) if tokens else ""
        times = _numbers_from_array_block(body, "KeyTime", as_int=True)
        values = _numbers_from_array_block(body, "KeyValueFloat")
        keyframes: list[list[float]] = []
        for idx, raw_time in enumerate(times):
            if idx >= len(values):
                break
            keyframes.append([ticks_to_ms(raw_time), float(values[idx])])
        if curve_id and keyframes:
            curves[curve_id] = {"id": curve_id, "keyframes": keyframes}
    for header, _body in _iter_blocks(text, "AnimationCurveNode"):
        tokens = _parse_csv_tokens(header)
        node_id = str(tokens[0]) if tokens else ""
        if node_id:
            curve_nodes[node_id] = {
                "id": node_id,
                "name": _clean_node_name(tokens[1] if len(tokens) > 1 else "", "AnimationCurveNode"),
            }
    for header, _body in _iter_blocks(text, "AnimationStack"):
        tokens = _parse_csv_tokens(header)
        stack_id = str(tokens[0]) if tokens else f"clip_{len(stacks) + 1}"
        stack_name = _clean_node_name(tokens[1] if len(tokens) > 1 else "", "AnimationStack")
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
        target = model_curves.setdefault(model_id, {}).setdefault(prop_name, {})
        target[axis] = rows

    if not model_curves and not stacks:
        return []
    if not stacks:
        stacks = [{"id": "clip_001", "name": "Take 001"}]
    clips: list[dict[str, Any]] = []
    for idx, stack in enumerate(stacks):
        clips.append({
            "id": str(stack.get("id") or f"clip_{idx + 1:03d}"),
            "name": str(stack.get("name") or f"clip_{idx + 1:03d}"),
            "duration_ms": max_ms,
            "model_curves": model_curves,
        })
    return clips


def _parse_skeleton_metadata(models: list[dict[str, Any]], connections: list[dict[str, str]], text: str) -> dict[str, Any]:
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
    for header, _body in _iter_blocks(text, "Deformer"):
        tokens = _parse_csv_tokens(header)
        if len(tokens) > 2 and str(tokens[2]).strip().strip('"').casefold() == "skin":
            skin_count += 1
    roots = [bone for bone in bones if not bone.get("parent_id")]
    return {
        "bones": bones,
        "skeletons": [{"root_bone_id": bone["id"], "root_bone_name": bone["name"]} for bone in roots],
        "skin_count": skin_count,
        "skeletal_mesh_count": 1 if bones or skin_count else 0,
    }


def _parse_version(text: str) -> int | None:
    match = re.search(r"(?m)^\s*FBXVersion\s*:\s*(\d+)", text)
    if match:
        return int(match.group(1))
    match = re.search(r"FBX\s+(\d+)\.(\d+)\.(\d+)", text)
    if match:
        return int(match.group(1)) * 1000 + int(match.group(2)) * 100 + int(match.group(3))
    return None


def parse_ascii_fbx_metadata(path: str | Path) -> tuple[dict[str, Any], str]:
    """Parse an ASCII FBX file and return metadata or an error string."""
    fbx_path = Path(path)
    try:
        data = fbx_path.read_bytes()
    except Exception as exc:
        return {}, f"internal_ascii_fbx failed to read file: {type(exc).__name__}: {exc}"

    if data.startswith(BINARY_FBX_MAGIC) or b"\x00" in data[:256]:
        return {}, "internal_ascii_fbx skipped binary FBX"
    if len(data) > MAX_ASCII_FBX_BYTES:
        return {}, f"internal_ascii_fbx skipped large ASCII FBX over {MAX_ASCII_FBX_BYTES} bytes"

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="replace")

    if "FBX" not in text[:4096] and "Objects:" not in text:
        return {}, "internal_ascii_fbx did not recognize FBX text"

    geometries = _parse_geometries(text)
    models = _parse_models(text)
    materials = _parse_materials(text)
    connections = _parse_connections(text)
    models = _apply_model_parent_ids(models, connections)
    animation_clips = _parse_animation_curves(text, connections)
    skeleton = _parse_skeleton_metadata(models, connections, text)
    units, axes = _parse_global_settings(text)
    animation_count = max(len(animation_clips), sum(1 for _ in _iter_blocks(text, "AnimationStack")))
    texture_count = sum(1 for _ in _iter_blocks(text, "Texture"))

    if not geometries and not models and not materials:
        return {}, "internal_ascii_fbx found no scene objects"

    mesh_count = sum(1 for item in geometries if str(item.get("kind") or "").casefold() in {"mesh", ""})
    return {
        "parser": "internal_ascii_fbx",
        "fbx_version": _parse_version(text),
        "mesh_count": mesh_count,
        "geometry_count": len(geometries),
        "model_count": len(models),
        "material_count": len(materials),
        "animation_count": animation_count,
        "animation_clips": animation_clips,
        "skeletal_mesh_count": skeleton["skeletal_mesh_count"],
        "skin_count": skeleton["skin_count"],
        "skeletons": skeleton["skeletons"],
        "bones": skeleton["bones"],
        "texture_count": texture_count,
        "bounds": _merge_bounds([item["bounds"] for item in geometries]),
        "units": units,
        "axes": axes,
        "geometries": geometries,
        "models": models,
        "materials": materials,
        "connections": connections,
    }, ""
