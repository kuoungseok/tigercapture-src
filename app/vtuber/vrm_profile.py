"""Lightweight VRM profile inspection for VTuber bridge preflight."""
from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any, Mapping


def inspect_vrm_profile(path: str | Path | None) -> dict[str, Any]:
    """Return VSeeFace-oriented VRM compatibility metadata.

    VSeeFace supports VRM0 avatars. VRM1 files can still be useful for internal
    preview, but they are reported as not compatible with this bridge target.
    """
    p = Path(str(path or ""))
    out: dict[str, Any] = {
        "ok": False,
        "path": str(p),
        "path_exists": p.is_file(),
        "source_ext": p.suffix.casefold(),
        "profile": "",
        "title": "",
        "author": "",
        "vseeface_compatible": False,
        "warnings": [],
        "errors": [],
    }
    if not str(path or "").strip():
        out["errors"].append("vrm_path_empty")
        return out
    if not p.is_file():
        out["errors"].append("vrm_file_missing")
        return out
    if p.suffix.casefold() != ".vrm":
        out["errors"].append("not_a_vrm_file")
        return out
    try:
        gltf = _load_glb_json(p)
    except Exception as exc:
        out["errors"].append(f"vrm_parse_failed: {type(exc).__name__}: {exc}")
        return out

    extensions = gltf.get("extensions") if isinstance(gltf.get("extensions"), Mapping) else {}
    vrm0 = extensions.get("VRM") if isinstance(extensions.get("VRM"), Mapping) else {}
    vrm1 = extensions.get("VRMC_vrm") if isinstance(extensions.get("VRMC_vrm"), Mapping) else {}
    if vrm0:
        meta = vrm0.get("meta") if isinstance(vrm0.get("meta"), Mapping) else {}
        out.update({
            "ok": True,
            "profile": "VRM0",
            "title": str(meta.get("title") or ""),
            "author": str(meta.get("author") or ""),
            "vseeface_compatible": True,
            "humanoid_bone_count": len(((vrm0.get("humanoid") or {}) if isinstance(vrm0.get("humanoid"), Mapping) else {}).get("humanBones") or []),
            "blend_shape_group_count": len(((vrm0.get("blendShapeMaster") or {}) if isinstance(vrm0.get("blendShapeMaster"), Mapping) else {}).get("blendShapeGroups") or []),
        })
        return out
    if vrm1:
        meta = vrm1.get("meta") if isinstance(vrm1.get("meta"), Mapping) else {}
        authors = meta.get("authors") if isinstance(meta.get("authors"), list) else []
        out.update({
            "ok": True,
            "profile": "VRM1",
            "title": str(meta.get("name") or ""),
            "author": ", ".join(str(item) for item in authors),
            "vseeface_compatible": False,
        })
        out["warnings"].append("vseeface_requires_vrm0")
        return out
    out["errors"].append("vrm_extension_missing")
    return out


def _load_glb_json(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        raise ValueError("invalid GLB header")
    version, total_len = struct.unpack_from("<II", data, 4)
    if int(version) != 2:
        raise ValueError(f"unsupported GLB version {version}")
    if total_len > len(data):
        raise ValueError("truncated GLB")
    offset = 12
    while offset + 8 <= min(total_len, len(data)):
        chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset:offset + chunk_len]
        offset += chunk_len
        if chunk_type == 0x4E4F534A:
            return json.loads(chunk.decode("utf-8"))
    raise ValueError("GLB JSON chunk missing")

