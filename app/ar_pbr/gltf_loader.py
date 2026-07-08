"""Minimal internal glTF 2.0 loader for AR/PBR preview descriptors."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any, Mapping

from app.ar_pbr.render_profile import inspect_asset_render_profiles_from_gltf


GLTF_EXTS = {".gltf", ".glb", ".vrm"}

_COMPONENT_DTYPES = {
    5120: "i1",
    5121: "u1",
    5122: "<i2",
    5123: "<u2",
    5125: "<u4",
    5126: "<f4",
}
_COMPONENT_MAX = {
    5120: 127.0,
    5121: 255.0,
    5122: 32767.0,
    5123: 65535.0,
    5125: 4294967295.0,
}
_TYPE_DIMS = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT4": 16,
}
_UNSUPPORTED_COMPRESSED_MESH_EXTS = {
    "KHR_draco_mesh_compression",
    "EXT_meshopt_compression",
}
_GLTF_WRAP_MODE_NAMES = {
    10497: "repeat",
    33071: "clamp_to_edge",
    33648: "mirrored_repeat",
}


def parse_gltf_metadata(
    path: str | Path,
    *,
    max_triangles_per_geometry: int = 12000,
) -> tuple[dict[str, Any], str]:
    """Parse a glTF/GLB file into the project descriptor metadata shape."""
    src = Path(path)
    warnings: list[str] = []
    try:
        gltf, embedded_bin = _load_gltf(src)
        unsupported_required = _unsupported_required_extensions(gltf)
        if unsupported_required:
            raise ValueError(
                "unsupported required glTF mesh compression extension(s): "
                + ", ".join(sorted(unsupported_required))
            )
        buffers = _load_buffers(src, gltf, embedded_bin)
        embedded_textures = _extract_embedded_images(src, gltf, buffers, warnings)
        node_world = _node_world_matrices(gltf)
        joint_nodes = _joint_node_set(gltf)
        vrm = _vrm_metadata(gltf)
        render_profiles = inspect_asset_render_profiles_from_gltf(gltf)
        materials = _materials(
            gltf,
            src.parent,
            embedded_textures=embedded_textures,
            vrm_materials=_vrm_material_properties(gltf),
        )
        models = _models(gltf, joint_nodes)
        geometries, connections = _geometries(
            gltf,
            buffers,
            node_world,
            max_triangles_per_geometry=max(100, int(max_triangles_per_geometry or 12000)),
            warnings=warnings,
        )
        animations = _animations(gltf, buffers)
        bounds = _bounds(geometries)
        bones = _bones(gltf, joint_nodes)
        metadata = {
            "parser": "internal_gltf",
            "gltf_version": str((gltf.get("asset") or {}).get("version") or ""),
            "extensions_used": [str(item) for item in (gltf.get("extensionsUsed") or [])],
            "extensions_required": [str(item) for item in (gltf.get("extensionsRequired") or [])],
            "vrm": vrm,
            "render_profiles": render_profiles,
            "mesh_count": len(gltf.get("meshes") or []),
            "material_count": len(materials),
            "texture_count": len(gltf.get("textures") or []),
            "animation_count": len(animations),
            "animation_clips": animations,
            "skeletal_mesh_count": sum(1 for item in geometries if item.get("skin_weights")),
            "skin_count": len(gltf.get("skins") or []),
            "skeletons": _skeletons(gltf),
            "bones": bones,
            "bounds": bounds,
            "units": {"scale_to_meters": 1.0},
            "axes": {"up": "Y", "front": "Z"},
            "geometries": geometries,
            "models": models,
            "materials": materials,
            "connections": connections,
            "warnings": warnings,
        }
        return metadata, ""
    except Exception as exc:
        return {}, f"internal glTF failed: {type(exc).__name__}: {exc}"


def _unsupported_required_extensions(gltf: Mapping[str, Any]) -> set[str]:
    required = {
        str(item)
        for item in (gltf.get("extensionsRequired") or [])
        if str(item) in _UNSUPPORTED_COMPRESSED_MESH_EXTS
    }
    return required


def _vrm_metadata(gltf: Mapping[str, Any]) -> dict[str, Any]:
    extensions = gltf.get("extensions") if isinstance(gltf.get("extensions"), Mapping) else {}
    vrm0 = extensions.get("VRM") if isinstance(extensions.get("VRM"), Mapping) else {}
    if vrm0:
        meta = vrm0.get("meta") if isinstance(vrm0.get("meta"), Mapping) else {}
        humanoid = vrm0.get("humanoid") if isinstance(vrm0.get("humanoid"), Mapping) else {}
        blend_shape = vrm0.get("blendShapeMaster") if isinstance(vrm0.get("blendShapeMaster"), Mapping) else {}
        secondary = vrm0.get("secondaryAnimation") if isinstance(vrm0.get("secondaryAnimation"), Mapping) else {}
        return {
            "profile": "VRM0",
            "version": str(vrm0.get("exporterVersion") or vrm0.get("specVersion") or "0.x"),
            "title": str(meta.get("title") or ""),
            "author": str(meta.get("author") or ""),
            "contact_information": str(meta.get("contactInformation") or ""),
            "reference": str(meta.get("reference") or ""),
            "humanoid_bone_count": len(humanoid.get("humanBones") or []),
            "blend_shape_group_count": len(blend_shape.get("blendShapeGroups") or []),
            "spring_bone_group_count": len(secondary.get("boneGroups") or []),
            "collider_group_count": len(secondary.get("colliderGroups") or []),
            "material_property_count": len(vrm0.get("materialProperties") or []),
        }
    vrm1 = extensions.get("VRMC_vrm") if isinstance(extensions.get("VRMC_vrm"), Mapping) else {}
    if vrm1:
        meta = vrm1.get("meta") if isinstance(vrm1.get("meta"), Mapping) else {}
        humanoid = vrm1.get("humanoid") if isinstance(vrm1.get("humanoid"), Mapping) else {}
        expressions = vrm1.get("expressions") if isinstance(vrm1.get("expressions"), Mapping) else {}
        preset = expressions.get("preset") if isinstance(expressions.get("preset"), Mapping) else {}
        custom = expressions.get("custom") if isinstance(expressions.get("custom"), Mapping) else {}
        authors = meta.get("authors") if isinstance(meta.get("authors"), list) else []
        return {
            "profile": "VRM1",
            "version": str(vrm1.get("specVersion") or "1.x"),
            "title": str(meta.get("name") or ""),
            "author": ", ".join(str(item) for item in authors),
            "humanoid_bone_count": len(humanoid.get("humanBones") or []),
            "expression_count": len(preset) + len(custom),
            "material_property_count": 0,
        }
    return {}


def _vrm_material_properties(gltf: Mapping[str, Any]) -> dict[Any, Mapping[str, Any]]:
    extensions = gltf.get("extensions") if isinstance(gltf.get("extensions"), Mapping) else {}
    vrm0 = extensions.get("VRM") if isinstance(extensions.get("VRM"), Mapping) else {}
    out: dict[Any, Mapping[str, Any]] = {}
    for idx, material in enumerate(vrm0.get("materialProperties") or []):
        if not isinstance(material, Mapping):
            continue
        out[idx] = material
        name = str(material.get("name") or "").strip()
        if name:
            out[name] = material
    return out


def _primitive_unsupported_compression(primitive: Mapping[str, Any]) -> str:
    extensions = primitive.get("extensions") if isinstance(primitive.get("extensions"), Mapping) else {}
    for name in sorted(_UNSUPPORTED_COMPRESSED_MESH_EXTS):
        if name in extensions:
            return name
    return ""


def _load_gltf(path: Path) -> tuple[dict[str, Any], bytes | None]:
    if path.suffix.casefold() in {".glb", ".vrm"}:
        data = path.read_bytes()
        if len(data) < 20 or data[:4] != b"glTF":
            raise ValueError("invalid GLB header")
        version, total_len = struct.unpack_from("<II", data, 4)
        if version != 2:
            raise ValueError(f"unsupported GLB version {version}")
        if total_len > len(data):
            raise ValueError("truncated GLB")
        offset = 12
        json_chunk: bytes | None = None
        bin_chunk: bytes | None = None
        while offset + 8 <= min(total_len, len(data)):
            chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
            offset += 8
            chunk = data[offset:offset + chunk_len]
            offset += chunk_len
            if chunk_type == 0x4E4F534A:
                json_chunk = chunk
            elif chunk_type == 0x004E4942:
                bin_chunk = chunk
        if json_chunk is None:
            raise ValueError("GLB has no JSON chunk")
        return json.loads(json_chunk.decode("utf-8")), bin_chunk
    return json.loads(path.read_text(encoding="utf-8")), None


def _load_buffers(path: Path, gltf: Mapping[str, Any], embedded_bin: bytes | None) -> list[bytes]:
    buffers: list[bytes] = []
    for idx, buffer in enumerate(gltf.get("buffers") or []):
        uri = str(buffer.get("uri") or "")
        if not uri and idx == 0 and embedded_bin is not None:
            buffers.append(embedded_bin)
        elif uri.startswith("data:"):
            payload = uri.split(",", 1)[1] if "," in uri else ""
            buffers.append(base64.b64decode(payload))
        elif uri:
            buffers.append((path.parent / uri).read_bytes())
        else:
            buffers.append(b"")
    return buffers


def _texture_cache_dir(path: Path) -> Path:
    try:
        stat = path.stat()
        seed = f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    except Exception:
        seed = str(path)
    key = hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:12]
    root = Path(__file__).resolve().parents[2] / "debugCapture" / "ar_pbr_asset_cache" / "textures"
    return root / f"{_safe_file_stem(path.stem)}_{key}"


def _safe_file_stem(value: Any) -> str:
    text = str(value or "image").strip()
    out = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in text)
    return out.strip("._") or "image"


def _extension_from_mime(mime: str) -> str:
    low = str(mime or "").casefold()
    if "jpeg" in low or "jpg" in low:
        return ".jpg"
    if "webp" in low:
        return ".webp"
    if "ktx2" in low:
        return ".ktx2"
    return ".png"


def _buffer_view_bytes(gltf: Mapping[str, Any], buffers: list[bytes], buffer_view_idx: Any) -> bytes:
    views = gltf.get("bufferViews") or []
    view = views[int(buffer_view_idx)]
    raw = buffers[int(view.get("buffer") or 0)]
    offset = int(view.get("byteOffset") or 0)
    length = int(view.get("byteLength") or 0)
    return bytes(raw[offset:offset + length])


def _data_uri_bytes(uri: str) -> bytes:
    if not uri.startswith("data:") or "," not in uri:
        return b""
    meta, payload = uri.split(",", 1)
    if ";base64" in meta.casefold():
        return base64.b64decode(payload)
    return payload.encode("utf-8")


def _extract_embedded_images(
    path: Path,
    gltf: Mapping[str, Any],
    buffers: list[bytes],
    warnings: list[str],
) -> dict[int, str]:
    images = gltf.get("images") or []
    if not images:
        return {}
    out: dict[int, str] = {}
    root = _texture_cache_dir(path)
    for idx, image in enumerate(images):
        if not isinstance(image, Mapping):
            continue
        uri = str(image.get("uri") or "")
        payload = b""
        if image.get("bufferView") is not None:
            try:
                payload = _buffer_view_bytes(gltf, buffers, image.get("bufferView"))
            except Exception as exc:
                warnings.append(f"embedded glTF image skipped: image={idx} {type(exc).__name__}: {exc}")
                continue
        elif uri.startswith("data:"):
            try:
                payload = _data_uri_bytes(uri)
            except Exception as exc:
                warnings.append(f"data-uri glTF image skipped: image={idx} {type(exc).__name__}: {exc}")
                continue
        if not payload:
            continue
        ext = _extension_from_mime(str(image.get("mimeType") or uri.split(";", 1)[0]))
        name = _safe_file_stem(image.get("name") or f"image_{idx}") + ext
        try:
            root.mkdir(parents=True, exist_ok=True)
            dst = root / name
            if not dst.exists() or dst.read_bytes() != payload:
                dst.write_bytes(payload)
            out[idx] = str(dst)
        except Exception as exc:
            warnings.append(f"embedded glTF image cache failed: image={idx} {type(exc).__name__}: {exc}")
    return out


def _accessor_array(gltf: Mapping[str, Any], buffers: list[bytes], accessor_idx: Any):
    import numpy as np

    idx = int(accessor_idx)
    accessors = gltf.get("accessors") or []
    if idx < 0 or idx >= len(accessors):
        raise IndexError(f"accessor index out of range: {idx}")
    accessor = accessors[idx]
    count = int(accessor.get("count") or 0)
    dims = _TYPE_DIMS.get(str(accessor.get("type") or "SCALAR"), 1)
    component_type = int(accessor.get("componentType") or 5126)
    dtype_name = _COMPONENT_DTYPES.get(component_type)
    if dtype_name is None:
        raise ValueError(f"unsupported glTF component type {component_type}")
    dtype = np.dtype(dtype_name)
    arr = np.zeros((count, dims), dtype=dtype)
    buffer_view_idx = accessor.get("bufferView")
    if buffer_view_idx is not None:
        views = gltf.get("bufferViews") or []
        view = views[int(buffer_view_idx)]
        raw = buffers[int(view.get("buffer") or 0)]
        view_offset = int(view.get("byteOffset") or 0)
        accessor_offset = int(accessor.get("byteOffset") or 0)
        offset = view_offset + accessor_offset
        stride = int(view.get("byteStride") or 0)
        packed = dims * dtype.itemsize
        if stride and stride != packed:
            rows = []
            for row in range(count):
                start = offset + row * stride
                rows.append(np.frombuffer(raw, dtype=dtype, count=dims, offset=start))
            arr = np.asarray(rows, dtype=dtype)
        else:
            arr = np.frombuffer(raw, dtype=dtype, count=count * dims, offset=offset).reshape((count, dims)).copy()
    if accessor.get("normalized") and component_type in _COMPONENT_MAX:
        arr = arr.astype(np.float32) / float(_COMPONENT_MAX[component_type])
        if component_type in {5120, 5122}:
            arr = np.maximum(arr, -1.0)
    sparse = accessor.get("sparse")
    if isinstance(sparse, Mapping) and int(sparse.get("count") or 0) > 0:
        # Sparse accessors are rare in the promo assets, but handling them keeps
        # the loader correct for Khronos conformance-style samples.
        sparse_count = int(sparse.get("count") or 0)
        indices = sparse.get("indices") if isinstance(sparse.get("indices"), Mapping) else {}
        values = sparse.get("values") if isinstance(sparse.get("values"), Mapping) else {}
        index_arr = _read_sparse_indices(gltf, buffers, indices, sparse_count)
        value_arr = _read_sparse_values(gltf, buffers, values, sparse_count, dims, dtype)
        arr = arr.copy()
        arr[index_arr] = value_arr
    return arr


def _read_sparse_indices(gltf: Mapping[str, Any], buffers: list[bytes], desc: Mapping[str, Any], count: int):
    import numpy as np

    component_type = int(desc.get("componentType") or 5123)
    dtype = np.dtype(_COMPONENT_DTYPES.get(component_type, "<u2"))
    view = (gltf.get("bufferViews") or [])[int(desc.get("bufferView") or 0)]
    raw = buffers[int(view.get("buffer") or 0)]
    offset = int(view.get("byteOffset") or 0) + int(desc.get("byteOffset") or 0)
    return np.frombuffer(raw, dtype=dtype, count=count, offset=offset).astype(np.int64)


def _read_sparse_values(
    gltf: Mapping[str, Any],
    buffers: list[bytes],
    desc: Mapping[str, Any],
    count: int,
    dims: int,
    dtype: Any,
):
    import numpy as np

    view = (gltf.get("bufferViews") or [])[int(desc.get("bufferView") or 0)]
    raw = buffers[int(view.get("buffer") or 0)]
    offset = int(view.get("byteOffset") or 0) + int(desc.get("byteOffset") or 0)
    return np.frombuffer(raw, dtype=dtype, count=count * dims, offset=offset).reshape((count, dims))


def _materials(
    gltf: Mapping[str, Any],
    asset_dir: Path,
    *,
    embedded_textures: Mapping[int, str] | None = None,
    vrm_materials: Mapping[Any, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    used_names: set[str] = set()
    for idx, material in enumerate(gltf.get("materials") or []):
        raw_name = str(material.get("name") or f"material_{idx}").strip() or f"material_{idx}"
        name = raw_name
        if name in used_names:
            name = f"{raw_name}_{idx}"
        used_names.add(name)
        pbr = material.get("pbrMetallicRoughness") if isinstance(material.get("pbrMetallicRoughness"), Mapping) else {}
        base_color = list(pbr.get("baseColorFactor") or [1.0, 1.0, 1.0, 1.0])
        base_color += [1.0, 1.0, 1.0, 1.0]
        emissive_factor = list(material.get("emissiveFactor") or [0.0, 0.0, 0.0])
        emissive_factor += [0.0, 0.0, 0.0]
        alpha_mode = str(material.get("alphaMode") or "OPAQUE").strip().upper() or "OPAQUE"
        row: dict[str, Any] = {
            "id": f"mat_{idx}",
            "name": name,
            "base_color": [float(v) for v in base_color[:4]],
            "roughness": float(pbr.get("roughnessFactor", 0.45) if pbr else 0.45),
            "metallic": float(pbr.get("metallicFactor", 0.0) if pbr else 0.0),
            "reflectance": 0.5,
            "alpha_mode": alpha_mode,
            "emissive_factor": [float(v) for v in emissive_factor[:3]],
        }
        if alpha_mode == "MASK":
            try:
                row["alpha_cutoff"] = float(material.get("alphaCutoff", 0.5))
            except Exception:
                row["alpha_cutoff"] = 0.5
        extensions = material.get("extensions") if isinstance(material.get("extensions"), Mapping) else {}
        if "KHR_materials_unlit" in extensions:
            row["shader_model"] = "unlit"
            row["unlit"] = True
        vrm_material = (vrm_materials or {}).get(idx) or (vrm_materials or {}).get(raw_name)
        if isinstance(vrm_material, Mapping):
            shader = str(vrm_material.get("shader") or "")
            if shader:
                row["source_shader"] = shader
            if "MToon" in shader:
                row["shader_model"] = "vrm_mtoon"
                row["mtoon"] = True
                row["unlit"] = True
                _copy_vrm_mtoon_metadata(row, vrm_material)
            texture_properties = (
                vrm_material.get("textureProperties")
                if isinstance(vrm_material.get("textureProperties"), Mapping)
                else {}
            )
        else:
            texture_properties = {}
        base_texture_info = pbr.get("baseColorTexture") if isinstance(pbr, Mapping) else None
        base = _texture_uri(
            gltf,
            base_texture_info,
            embedded_textures=embedded_textures,
        )
        if base:
            row["base_texture_source"] = "gltf_pbr_base_color_texture"
            _copy_texture_uv_metadata(row, "base", base_texture_info, gltf)
        if not base and texture_properties:
            base = _texture_uri(gltf, texture_properties.get("_MainTex"), embedded_textures=embedded_textures)
            if base:
                row["base_texture_source"] = "vrm0_mtoon_main_tex"
        if base:
            row["base_texture"] = base
        metal_rough_info = pbr.get("metallicRoughnessTexture") if isinstance(pbr, Mapping) else None
        metal_rough = _texture_uri(
            gltf,
            metal_rough_info,
            embedded_textures=embedded_textures,
        )
        if metal_rough:
            row["roughness_texture"] = metal_rough
            row["metallic_texture"] = metal_rough
            row["metallic_roughness_texture"] = metal_rough
            row["roughness_channel"] = "g"
            row["metallic_channel"] = "b"
            row["roughness_texture_source"] = "gltf_pbr_metallic_roughness_texture"
            row["metallic_texture_source"] = "gltf_pbr_metallic_roughness_texture"
            _copy_texture_uv_metadata(row, "roughness", metal_rough_info, gltf)
            _copy_texture_uv_metadata(row, "metallic", metal_rough_info, gltf)
            if "uv_set" not in row:
                _copy_texture_uv_metadata(row, "", metal_rough_info, gltf)
        normal_info = material.get("normalTexture")
        normal = _texture_uri(gltf, normal_info, embedded_textures=embedded_textures)
        if normal:
            row["normal_texture_source"] = "gltf_pbr_normal_texture"
            _copy_texture_uv_metadata(row, "normal", normal_info, gltf)
            if "uv_set" not in row:
                _copy_texture_uv_metadata(row, "", normal_info, gltf)
        if not normal and texture_properties:
            normal = _texture_uri(gltf, texture_properties.get("_BumpMap"), embedded_textures=embedded_textures)
            if normal:
                row["normal_texture_source"] = "vrm0_mtoon_bump_map"
        if normal:
            row["normal_texture"] = normal
        occlusion_info = material.get("occlusionTexture")
        occlusion = _texture_uri(gltf, occlusion_info, embedded_textures=embedded_textures)
        if occlusion:
            row["occlusion_texture"] = occlusion
            row["occlusion_channel"] = "r"
            row["occlusion_texture_source"] = "gltf_pbr_occlusion_texture"
            _copy_texture_uv_metadata(row, "occlusion", occlusion_info, gltf)
            if "uv_set" not in row:
                _copy_texture_uv_metadata(row, "", occlusion_info, gltf)
        emissive_info = material.get("emissiveTexture")
        emissive = _texture_uri(gltf, emissive_info, embedded_textures=embedded_textures)
        if emissive:
            row["emissive_texture_source"] = "gltf_pbr_emissive_texture"
            _copy_texture_uv_metadata(row, "emissive", emissive_info, gltf)
            if "uv_set" not in row:
                _copy_texture_uv_metadata(row, "", emissive_info, gltf)
        if not emissive and texture_properties:
            emissive = _texture_uri(gltf, texture_properties.get("_EmissionMap"), embedded_textures=embedded_textures)
            if emissive:
                row["emissive_texture_source"] = "vrm0_mtoon_emission_map"
        if emissive:
            row["emissive_texture"] = emissive
        row["pbr_available"] = any(
            str(row.get(key) or "").startswith("gltf_pbr")
            for key in (
                "base_texture_source",
                "roughness_texture_source",
                "metallic_texture_source",
                "normal_texture_source",
                "occlusion_texture_source",
                "emissive_texture_source",
            )
        ) or ("roughnessFactor" in pbr or "metallicFactor" in pbr) and "mtoon" not in str(row.get("shader_model") or row.get("source_shader") or "").casefold()
        out.append(row)
    return out


def _copy_vrm_mtoon_metadata(row: dict[str, Any], vrm_material: Mapping[str, Any]) -> None:
    """Expose VRM0 MToon state needed by preview/export render ordering.

    VRM0 stores critical material state outside ordinary glTF PBR fields. If we
    collapse it to a generic unlit material, alpha-cutout avatars can render as
    missing body parts because the renderer loses renderQueue, ZWrite, culling,
    and cutoff decisions.
    """
    float_props = (
        vrm_material.get("floatProperties")
        if isinstance(vrm_material.get("floatProperties"), Mapping)
        else {}
    )

    def _float_prop(name: str, default: float | None = None) -> float | None:
        try:
            return float(float_props.get(name))
        except Exception:
            return default

    try:
        row["mtoon_render_queue"] = int(vrm_material.get("renderQueue"))
        row["render_queue"] = int(vrm_material.get("renderQueue"))
    except Exception:
        pass
    cutoff = _float_prop("_Cutoff")
    if cutoff is not None:
        row["alpha_cutoff"] = max(0.0, min(1.0, float(cutoff)))
    cull = _float_prop("_CullMode")
    if cull is not None:
        row["mtoon_cull_mode"] = int(round(float(cull)))
        # Unity/VRM: 0=Off, 1=Front, 2=Back.
        row["double_sided"] = int(round(float(cull))) == 0
    zwrite = _float_prop("_ZWrite")
    if zwrite is not None:
        row["mtoon_zwrite"] = int(round(float(zwrite)))
        row["depth_write"] = bool(int(round(float(zwrite))))
    src_blend = _float_prop("_SrcBlend")
    dst_blend = _float_prop("_DstBlend")
    if src_blend is not None:
        row["mtoon_src_blend"] = int(round(float(src_blend)))
    if dst_blend is not None:
        row["mtoon_dst_blend"] = int(round(float(dst_blend)))
    if int(row.get("mtoon_zwrite", 1) or 1) == 0:
        row["alpha_mode"] = "BLEND"


def _texture_uv_info(texture_ref: Any) -> tuple[int, dict[str, Any] | None]:
    if not isinstance(texture_ref, Mapping):
        return 0, None
    try:
        uv_set = int(texture_ref.get("texCoord", 0) or 0)
    except Exception:
        uv_set = 0
    extensions = texture_ref.get("extensions") if isinstance(texture_ref.get("extensions"), Mapping) else {}
    transform = extensions.get("KHR_texture_transform") if isinstance(extensions.get("KHR_texture_transform"), Mapping) else {}
    if not transform:
        return uv_set, None
    try:
        uv_set = int(transform.get("texCoord", uv_set) or uv_set)
    except Exception:
        pass
    offset = _two_float_list(transform.get("offset"), (0.0, 0.0))
    scale = _two_float_list(transform.get("scale"), (1.0, 1.0))
    try:
        rotation = float(transform.get("rotation", 0.0) or 0.0)
    except Exception:
        rotation = 0.0
    payload = {
        "offset": offset,
        "scale": scale,
        "rotation": rotation,
    }
    if payload["offset"] == [0.0, 0.0] and payload["scale"] == [1.0, 1.0] and abs(rotation) <= 1.0e-8:
        return uv_set, None
    return uv_set, payload


def _two_float_list(value: Any, fallback: tuple[float, float]) -> list[float]:
    if isinstance(value, (list, tuple)):
        raw = list(value)
    else:
        raw = []
    out: list[float] = []
    for idx in range(2):
        try:
            out.append(float(raw[idx]))
        except Exception:
            out.append(float(fallback[idx]))
    return out


def _texture_sampler_wrap(gltf: Mapping[str, Any], texture_ref: Any) -> dict[str, str]:
    if not isinstance(texture_ref, Mapping):
        return {}
    try:
        texture_index = int(texture_ref.get("index"))
    except Exception:
        return {}
    wrap_s = 10497
    wrap_t = 10497
    try:
        texture = (gltf.get("textures") or [])[texture_index]
        sampler_index = texture.get("sampler") if isinstance(texture, Mapping) else None
        if sampler_index is not None:
            sampler = (gltf.get("samplers") or [])[int(sampler_index)]
            if isinstance(sampler, Mapping):
                wrap_s = int(sampler.get("wrapS", wrap_s) or wrap_s)
                wrap_t = int(sampler.get("wrapT", wrap_t) or wrap_t)
    except Exception:
        pass
    return {
        "wrap_s": _GLTF_WRAP_MODE_NAMES.get(int(wrap_s), "repeat"),
        "wrap_t": _GLTF_WRAP_MODE_NAMES.get(int(wrap_t), "repeat"),
    }


def _copy_texture_uv_metadata(
    row: dict[str, Any],
    prefix: str,
    texture_ref: Any,
    gltf: Mapping[str, Any] | None = None,
) -> None:
    uv_set, transform = _texture_uv_info(texture_ref)
    key_prefix = f"{prefix}_" if prefix else ""
    row[f"{key_prefix}uv_set"] = int(uv_set)
    if transform is not None:
        row[f"{key_prefix}uv_transform"] = transform
    if gltf is not None:
        sampler_wrap = _texture_sampler_wrap(gltf, texture_ref)
        for suffix in ("wrap_s", "wrap_t"):
            value = sampler_wrap.get(suffix)
            if value:
                row[f"{key_prefix}{suffix}"] = value
    if prefix == "base" or not prefix:
        row["uv_set"] = int(uv_set)
        if transform is not None:
            row["uv_transform"] = transform
        if gltf is not None:
            sampler_wrap = _texture_sampler_wrap(gltf, texture_ref)
            for suffix in ("wrap_s", "wrap_t"):
                value = sampler_wrap.get(suffix)
                if value:
                    row[suffix] = value


def _texture_uri(
    gltf: Mapping[str, Any],
    texture_ref: Any,
    *,
    embedded_textures: Mapping[int, str] | None = None,
) -> str:
    texture_index: int | None = None
    if isinstance(texture_ref, Mapping):
        try:
            texture_index = int(texture_ref.get("index"))
        except Exception:
            texture_index = None
    elif isinstance(texture_ref, (int, float)) and not isinstance(texture_ref, bool):
        try:
            texture_index = int(texture_ref)
        except Exception:
            texture_index = None
    if texture_index is None or texture_index < 0:
        return ""
    textures = gltf.get("textures") or []
    images = gltf.get("images") or []
    try:
        texture = textures[texture_index]
        image_idx = int(texture.get("source"))
        if embedded_textures and image_idx in embedded_textures:
            return str(embedded_textures[image_idx])
        uri = str(images[image_idx].get("uri") or "")
        return uri if uri and not uri.startswith("data:") else ""
    except Exception:
        return ""


def _models(gltf: Mapping[str, Any], joint_nodes: set[int]) -> list[dict[str, Any]]:
    parent = _parent_by_node(gltf)
    out: list[dict[str, Any]] = []
    for idx, node in enumerate(gltf.get("nodes") or []):
        t, r, s = _node_trs(node)
        row = {
            "id": f"node_{idx}",
            "name": str(node.get("name") or f"node_{idx}"),
            "translation": t,
            "rotation": r,
            "rotation_quat": _node_rotation_quat(node),
            "scale": s,
            "parent_id": f"node_{parent[idx]}" if idx in parent else "",
        }
        if idx in joint_nodes:
            row["kind"] = "LimbNode"
        out.append(row)
    return out


def _geometries(
    gltf: Mapping[str, Any],
    buffers: list[bytes],
    node_world: Mapping[int, Any],
    *,
    max_triangles_per_geometry: int,
    warnings: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    import numpy as np

    geometries: list[dict[str, Any]] = []
    connections: list[dict[str, str]] = []
    meshes = gltf.get("meshes") or []
    nodes = gltf.get("nodes") or []
    for node_idx, node in enumerate(nodes):
        mesh_idx_raw = node.get("mesh")
        if mesh_idx_raw is None:
            continue
        mesh_idx = int(mesh_idx_raw)
        if mesh_idx < 0 or mesh_idx >= len(meshes):
            continue
        mesh = meshes[mesh_idx]
        matrix = node_world.get(node_idx)
        skin_idx = node.get("skin")
        for prim_idx, prim in enumerate(mesh.get("primitives") or []):
            unsupported_compression = _primitive_unsupported_compression(prim)
            if unsupported_compression:
                warnings.append(
                    "skipped compressed glTF primitive requiring unsupported decoder: "
                    f"{unsupported_compression} mesh={mesh_idx} primitive={prim_idx}"
                )
                continue
            if int(prim.get("mode", 4) or 4) != 4:
                warnings.append(f"skipped non-triangle primitive mesh={mesh_idx} primitive={prim_idx}")
                continue
            attrs = prim.get("attributes") if isinstance(prim.get("attributes"), Mapping) else {}
            if "POSITION" not in attrs:
                continue
            positions = _accessor_array(gltf, buffers, attrs["POSITION"]).astype(np.float32)
            if positions.shape[1] < 3:
                continue
            skinned_mesh = skin_idx is not None
            vertices = positions[:, :3].astype(np.float32) if skinned_mesh else _transform_positions(positions[:, :3], matrix)
            indices = _indices(gltf, buffers, prim, len(vertices))
            if indices.size < 3:
                continue
            usable = (int(indices.size) // 3) * 3
            triangles_arr = indices[:usable].reshape((-1, 3)).astype(np.int64)
            if len(triangles_arr) > max_triangles_per_geometry:
                warnings.append(
                    "primitive exceeds preview triangle budget without import decimation: "
                    f"mesh={mesh_idx} primitive={prim_idx} triangles={len(triangles_arr)} "
                    f"budget={max_triangles_per_geometry}"
                )
            geometry_id = f"geom_{len(geometries)}"
            material_idx = prim.get("material")
            material_id = f"mat_{int(material_idx)}" if material_idx is not None else ""
            uvs: list[list[float]] = []
            uv_sets: dict[str, list[list[float]]] = {}
            for attr_name, accessor_idx in attrs.items():
                attr_text = str(attr_name)
                if not attr_text.startswith("TEXCOORD_"):
                    continue
                uv_set = attr_text.split("_", 1)[1]
                try:
                    uv_arr = _accessor_array(gltf, buffers, accessor_idx).astype(np.float32)
                except Exception as exc:
                    warnings.append(
                        f"skipped glTF UV accessor mesh={mesh_idx} primitive={prim_idx} "
                        f"attribute={attr_text}: {type(exc).__name__}: {exc}"
                    )
                    continue
                if len(uv_arr) >= len(vertices) and uv_arr.shape[1] >= 2:
                    uv_sets[str(uv_set)] = uv_arr[:, :2].tolist()
            if "0" in uv_sets:
                uvs = uv_sets["0"]
            geometry: dict[str, Any] = {
                "id": geometry_id,
                "name": str(mesh.get("name") or f"mesh_{mesh_idx}") + f"_prim_{prim_idx}",
                "model_id": f"node_{node_idx}",
                "material_id": material_id,
                "vertices": vertices.tolist(),
                "triangles": triangles_arr.tolist(),
                "triangle_count": int(len(triangles_arr)),
                "bounds": _array_bounds(vertices),
            }
            if uvs:
                geometry["uvs"] = uvs
            if uv_sets:
                geometry["uv_sets"] = uv_sets
            skin = _skin_payload(gltf, buffers, attrs, skin_idx, len(vertices))
            if skin.get("weights"):
                geometry["skin_weights"] = skin["weights"]
                geometry["skin_joint_ids"] = skin.get("joint_ids", [])
                geometry["skin_inverse_bind_matrices"] = skin.get("inverse_bind_matrices", [])
            geometries.append(geometry)
            connections.append({"child": geometry_id, "parent": f"node_{node_idx}", "type": "Geometry"})
            if material_id:
                connections.append({"child": material_id, "parent": f"node_{node_idx}", "type": "Material"})
    return geometries, connections


def _indices(gltf: Mapping[str, Any], buffers: list[bytes], primitive: Mapping[str, Any], vertex_count: int):
    import numpy as np

    if primitive.get("indices") is None:
        return np.arange(vertex_count, dtype=np.int64)
    arr = _accessor_array(gltf, buffers, primitive.get("indices"))
    return arr.reshape((-1,)).astype(np.int64)


def _skin_payload(
    gltf: Mapping[str, Any],
    buffers: list[bytes],
    attrs: Mapping[str, Any],
    skin_idx_raw: Any,
    vertex_count: int,
) -> dict[str, Any]:
    if skin_idx_raw is None or "JOINTS_0" not in attrs or "WEIGHTS_0" not in attrs:
        return {}
    skins = gltf.get("skins") or []
    skin_idx = int(skin_idx_raw)
    if skin_idx < 0 or skin_idx >= len(skins):
        return {}
    joints = list(skins[skin_idx].get("joints") or [])
    if not joints:
        return {}
    joint_values = _accessor_array(gltf, buffers, attrs["JOINTS_0"]).astype("int64")
    weight_values = _accessor_array(gltf, buffers, attrs["WEIGHTS_0"]).astype("float32")
    inverse_bind_matrices = _inverse_bind_matrices(gltf, buffers, skins[skin_idx], len(joints))
    out: list[list[dict[str, float | str]]] = []
    for idx in range(vertex_count):
        rows: list[dict[str, float | str]] = []
        if idx >= len(joint_values) or idx >= len(weight_values):
            out.append(rows)
            continue
        for joint_slot, weight in zip(joint_values[idx].tolist(), weight_values[idx].tolist()):
            w = float(weight)
            if w <= 1.0e-6:
                continue
            slot = int(joint_slot)
            if 0 <= slot < len(joints):
                rows.append({"bone_id": f"node_{int(joints[slot])}", "weight": w})
        out.append(rows)
    return {
        "weights": out,
        "joint_ids": [f"node_{int(joint)}" for joint in joints],
        "inverse_bind_matrices": inverse_bind_matrices,
    }


def _inverse_bind_matrices(
    gltf: Mapping[str, Any],
    buffers: list[bytes],
    skin: Mapping[str, Any],
    joint_count: int,
) -> list[list[list[float]]]:
    import numpy as np

    accessor_idx = skin.get("inverseBindMatrices")
    if accessor_idx is None:
        return [np.eye(4, dtype=np.float32).astype(float).tolist() for _ in range(joint_count)]
    try:
        arr = _accessor_array(gltf, buffers, accessor_idx).astype(np.float32)
        out: list[list[list[float]]] = []
        for row in arr[:joint_count]:
            out.append(row.reshape((4, 4)).T.astype(float).tolist())
        while len(out) < joint_count:
            out.append(np.eye(4, dtype=np.float32).astype(float).tolist())
        return out
    except Exception:
        return [np.eye(4, dtype=np.float32).astype(float).tolist() for _ in range(joint_count)]


def _animations(gltf: Mapping[str, Any], buffers: list[bytes]) -> list[dict[str, Any]]:
    clips: list[dict[str, Any]] = []
    for anim_idx, anim in enumerate(gltf.get("animations") or []):
        samplers = anim.get("samplers") or []
        channels = anim.get("channels") or []
        model_curves: dict[str, dict[str, Any]] = {}
        duration_ms = 0.0
        for channel in channels:
            target = channel.get("target") if isinstance(channel.get("target"), Mapping) else {}
            node_idx = target.get("node")
            path = str(target.get("path") or "")
            sampler_idx = channel.get("sampler")
            if node_idx is None or sampler_idx is None or path not in {"translation", "rotation", "scale"}:
                continue
            sampler = samplers[int(sampler_idx)]
            times = _accessor_array(gltf, buffers, sampler.get("input")).reshape((-1,)).astype("float64") * 1000.0
            values = _accessor_array(gltf, buffers, sampler.get("output")).astype("float64")
            if len(times) <= 0 or len(values) <= 0:
                continue
            duration_ms = max(duration_ms, float(times[-1]))
            curves = model_curves.setdefault(f"node_{int(node_idx)}", {})
            if path == "rotation":
                eulers = [_quat_to_euler_deg(row) for row in values]
                curves[path] = _curve_axes(times, eulers)
                curves["rotation_quat"] = _curve_components(times, values[:, :4], ("x", "y", "z", "w"))
            else:
                curves[path] = _curve_axes(times, values[:, :3])
        if model_curves:
            clips.append({
                "id": f"anim_{anim_idx}",
                "name": str(anim.get("name") or f"animation_{anim_idx}"),
                "duration_ms": float(duration_ms),
                "model_curves": model_curves,
            })
    return clips


def _curve_axes(times: Any, values: Any) -> dict[str, list[list[float]]]:
    axes = {"x": [], "y": [], "z": []}
    for time_ms, row in zip(times, values):
        for axis, value in zip(("x", "y", "z"), row[:3]):
            axes[axis].append([float(time_ms), float(value)])
    return axes


def _curve_components(times: Any, values: Any, names: tuple[str, ...]) -> dict[str, list[list[float]]]:
    axes = {name: [] for name in names}
    for time_ms, row in zip(times, values):
        for axis, value in zip(names, row[:len(names)]):
            axes[axis].append([float(time_ms), float(value)])
    return axes


def _node_world_matrices(gltf: Mapping[str, Any]) -> dict[int, Any]:
    import numpy as np

    nodes = gltf.get("nodes") or []
    parent = _parent_by_node(gltf)
    local = [_node_matrix(node) for node in nodes]
    cache: dict[int, Any] = {}

    def world(idx: int):
        if idx in cache:
            return cache[idx]
        if idx in parent:
            cache[idx] = world(parent[idx]) @ local[idx]
        else:
            cache[idx] = local[idx]
        return cache[idx]

    for idx in range(len(nodes)):
        world(idx)
    return cache


def _node_matrix(node: Mapping[str, Any]):
    import numpy as np

    if isinstance(node.get("matrix"), list) and len(node.get("matrix") or []) >= 16:
        return np.asarray(node.get("matrix"), dtype=np.float32).reshape((4, 4)).T
    t, r_deg, s = _node_trs(node)
    q = node.get("rotation") if isinstance(node.get("rotation"), list) else [0.0, 0.0, 0.0, 1.0]
    rot = _quat_matrix(q)
    mat = np.eye(4, dtype=np.float32)
    mat[:3, :3] = rot[:3, :3] @ np.diag(np.asarray(s, dtype=np.float32))
    mat[:3, 3] = np.asarray(t, dtype=np.float32)
    return mat


def _node_trs(node: Mapping[str, Any]) -> tuple[list[float], list[float], list[float]]:
    t = _vec(node.get("translation"), [0.0, 0.0, 0.0], 3)
    s = _vec(node.get("scale"), [1.0, 1.0, 1.0], 3)
    r = _quat_to_euler_deg(_vec(node.get("rotation"), [0.0, 0.0, 0.0, 1.0], 4))
    return t, r, s


def _node_rotation_quat(node: Mapping[str, Any]) -> list[float]:
    return _vec(node.get("rotation"), [0.0, 0.0, 0.0, 1.0], 4)


def _parent_by_node(gltf: Mapping[str, Any]) -> dict[int, int]:
    out: dict[int, int] = {}
    for idx, node in enumerate(gltf.get("nodes") or []):
        for child in node.get("children") or []:
            out[int(child)] = idx
    return out


def _joint_node_set(gltf: Mapping[str, Any]) -> set[int]:
    out: set[int] = set()
    for skin in gltf.get("skins") or []:
        for joint in skin.get("joints") or []:
            out.add(int(joint))
    return out


def _bones(gltf: Mapping[str, Any], joint_nodes: set[int]) -> list[dict[str, str]]:
    parent = _parent_by_node(gltf)
    nodes = gltf.get("nodes") or []
    out = []
    for idx in sorted(joint_nodes):
        node = nodes[idx] if 0 <= idx < len(nodes) else {}
        parent_id = f"node_{parent[idx]}" if idx in parent and parent[idx] in joint_nodes else ""
        out.append({
            "id": f"node_{idx}",
            "name": str(node.get("name") or f"node_{idx}"),
            "parent_id": parent_id,
            "kind": "LimbNode",
        })
    return out


def _skeletons(gltf: Mapping[str, Any]) -> list[dict[str, str]]:
    nodes = gltf.get("nodes") or []
    out = []
    for skin_idx, skin in enumerate(gltf.get("skins") or []):
        root = skin.get("skeleton")
        if root is None:
            joints = skin.get("joints") or []
            root = joints[0] if joints else None
        if root is None:
            continue
        root_idx = int(root)
        node = nodes[root_idx] if 0 <= root_idx < len(nodes) else {}
        out.append({"root_bone_id": f"node_{root_idx}", "root_bone_name": str(node.get("name") or f"skin_{skin_idx}")})
    return out


def _transform_positions(positions: Any, matrix: Any):
    import numpy as np

    if matrix is None:
        return positions.astype(np.float32)
    ones = np.ones((positions.shape[0], 1), dtype=np.float32)
    hom = np.concatenate([positions.astype(np.float32), ones], axis=1)
    out = hom @ matrix.T
    return out[:, :3].astype(np.float32)


def _array_bounds(vertices: Any) -> dict[str, list[float]]:
    import numpy as np

    if len(vertices) <= 0:
        return {"center": [0.0, 0.0, 0.0], "size": [1.0, 1.0, 1.0]}
    lo = np.min(vertices, axis=0)
    hi = np.max(vertices, axis=0)
    center = (lo + hi) * 0.5
    size = np.maximum(hi - lo, 1.0e-6)
    return {"center": center.astype(float).tolist(), "size": size.astype(float).tolist()}


def _bounds(geometries: list[Mapping[str, Any]]) -> dict[str, list[float]]:
    import numpy as np

    arrays = []
    for geometry in geometries:
        vertices = geometry.get("vertices")
        if isinstance(vertices, list) and vertices:
            arrays.append(np.asarray(vertices, dtype=np.float32))
    if not arrays:
        return {"center": [0.0, 0.0, 0.0], "size": [1.0, 1.0, 1.0]}
    merged = np.concatenate(arrays, axis=0)
    return _array_bounds(merged)


def _vec(value: Any, default: list[float], length: int) -> list[float]:
    source = value if isinstance(value, list) else default
    out = []
    for idx in range(length):
        try:
            out.append(float(source[idx]))
        except Exception:
            out.append(float(default[idx]))
    return out


def _quat_matrix(q: Any):
    import numpy as np

    x, y, z, w = _vec(q, [0.0, 0.0, 0.0, 1.0], 4)
    length = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / length, y / length, z / length, w / length
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return np.asarray([
        [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy), 0.0],
        [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx), 0.0],
        [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy), 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ], dtype=np.float32)


def _quat_to_euler_deg(q: Any) -> list[float]:
    x, y, z, w = _vec(q, [0.0, 0.0, 0.0, 1.0], 4)
    length = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / length, y / length, z / length, w / length
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    rx = math.atan2(sinr_cosp, cosr_cosp)
    sinp = 2.0 * (w * y - z * x)
    if abs(sinp) >= 1.0:
        ry = math.copysign(math.pi / 2.0, sinp)
    else:
        ry = math.asin(sinp)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    rz = math.atan2(siny_cosp, cosy_cosp)
    return [math.degrees(rx), math.degrees(ry), math.degrees(rz)]
