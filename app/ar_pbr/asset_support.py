"""Support classification for AR/PBR scene assets.

This module keeps the importer honest: every accepted FBX/glTF descriptor gets
a compact support report that UI, QA, and export code can consume without
guessing from backend-specific diagnostics.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


READY = "ready"
LIMITED = "limited"
UNSUPPORTED = "unsupported"
PLACEHOLDER = "placeholder"


_COMPRESSED_EXTENSION_CODES = {
    "KHR_draco_mesh_compression": "unsupported_required_compression",
    "EXT_meshopt_compression": "unsupported_required_compression",
}


def classify_asset_support(
    descriptor: Mapping[str, Any] | None,
    diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a stable support report for an imported AR/PBR asset descriptor."""
    asset = descriptor or {}
    diag = diagnostics or {}
    ext = str(asset.get("source_ext") or diag.get("source_ext") or Path(str(asset.get("source_path") or "")).suffix).casefold()
    backend = str(asset.get("backend") or diag.get("backend") or "")
    imported = bool(diag.get("imported")) or str(asset.get("import_state") or "") == READY
    fallback = bool(diag.get("fallback")) or backend == PLACEHOLDER or str(asset.get("import_state") or "") == PLACEHOLDER
    geometries = [item for item in asset.get("geometries") or [] if isinstance(item, Mapping)]
    materials = [item for item in asset.get("materials") or [] if isinstance(item, Mapping)]
    triangle_count = _triangle_count(geometries)
    skeletal_count = int(asset.get("skeletal_mesh_count") or 0)
    skin_count = int(asset.get("skin_count") or 0)
    animation_count = int(asset.get("animation_count") or 0)
    texture_count = int(asset.get("texture_count") or 0)
    material_texture_count = _material_texture_count(materials)
    issue_codes: list[str] = []
    feature_flags: list[str] = []

    is_vrm = _is_vrm_asset(asset, ext)
    is_mtoon = _is_mtoon_asset(asset, materials)

    if ext in {".gltf", ".glb", ".vrm"}:
        feature_flags.append("gltf_source")
        if is_vrm:
            feature_flags.append("vrm_source")
            feature_flags.append("vrm_avatar")
            if is_mtoon:
                feature_flags.append("vrm_mtoon_materials")
    elif ext == ".fbx":
        feature_flags.append("fbx_source")
    elif ext:
        feature_flags.append("unknown_source_format")

    if bool(asset.get("requires_runtime_conversion")) or ext == ".fbx":
        feature_flags.append("runtime_conversion_required")
        issue_codes.append("fbx_runtime_conversion_required")
    if materials:
        feature_flags.append("pbr_materials")
    if texture_count > 0 or material_texture_count > 0:
        feature_flags.append("texture_maps")
    if skeletal_count > 0 or skin_count > 0:
        feature_flags.append("skeletal_mesh")
        if is_vrm:
            feature_flags.append("humanoid_avatar")
    if animation_count > 0:
        feature_flags.append("animation_clips")
        if skeletal_count <= 0:
            feature_flags.append("static_mesh_animation")
    if any(_geometry_has_skin_data(item) for item in geometries):
        feature_flags.append("skin_weights")

    warnings_and_errors = " ".join(
        str(item)
        for item in list(diag.get("warnings") or [])
        + list(diag.get("errors") or [])
        + list(asset.get("warnings") or [])
    )
    for extension_name, code in _COMPRESSED_EXTENSION_CODES.items():
        if extension_name in warnings_and_errors:
            issue_codes.append(code)
            feature_flags.append("compressed_mesh_unsupported")

    if fallback:
        issue_codes.append("placeholder_descriptor")
    if not imported:
        issue_codes.append("import_failed_or_placeholder")
    if not geometries:
        issue_codes.append("no_geometry")
    if triangle_count <= 0:
        issue_codes.append("no_renderable_triangles")
    if not materials:
        issue_codes.append("no_materials")
    elif texture_count <= 0 and material_texture_count <= 0:
        issue_codes.append("material_constants_only")
    if skeletal_count > 0 and not any(_geometry_has_skin_data(item) for item in geometries):
        issue_codes.append("skeletal_mesh_missing_skin_weights")
    if ext == ".fbx" and skeletal_count > 0:
        issue_codes.append("fbx_skeletal_limited")
    if triangle_count >= 500_000:
        issue_codes.append("large_mesh_may_be_slow")

    issue_codes = _dedupe(issue_codes)
    feature_flags = _dedupe(feature_flags)
    asset_kind = _asset_kind(
        fallback=fallback,
        geometries=geometries,
        skeletal_count=skeletal_count,
        animation_count=animation_count,
        is_vrm=is_vrm,
    )
    support_level, confidence = _support_level(
        ext=ext,
        fallback=fallback,
        imported=imported,
        triangle_count=triangle_count,
        issue_codes=issue_codes,
        skeletal_count=skeletal_count,
        skin_count=skin_count,
        animation_count=animation_count,
    )
    render_path = _render_path(
        support_level=support_level,
        skeletal_count=skeletal_count,
        animation_count=animation_count,
        fallback=fallback,
        is_mtoon=is_mtoon,
    )
    summary = _summary(
        support_level=support_level,
        asset_kind=asset_kind,
        ext=ext,
        issue_codes=issue_codes,
    )
    ok_for_preview = support_level in {READY, LIMITED} and triangle_count > 0
    ok_for_export = support_level == READY and triangle_count > 0
    if support_level == LIMITED and "fbx_runtime_conversion_required" in issue_codes and "fbx_skeletal_limited" not in issue_codes:
        ok_for_export = True

    return {
        "support_level": support_level,
        "confidence": confidence,
        "asset_kind": asset_kind,
        "format_family": _format_family(ext),
        "render_path": render_path,
        "ok_for_preview": bool(ok_for_preview),
        "ok_for_export": bool(ok_for_export),
        "needs_attention": bool(issue_codes and support_level != READY),
        "issue_codes": issue_codes,
        "feature_flags": feature_flags,
        "summary": summary,
        "metrics": {
            "geometry_count": len(geometries),
            "triangle_count": int(triangle_count),
            "material_count": len(materials),
            "texture_count": int(max(texture_count, material_texture_count)),
            "animation_count": int(animation_count),
            "skeletal_mesh_count": int(skeletal_count),
            "skin_count": int(skin_count),
        },
    }


def summarize_asset_support(report: Mapping[str, Any]) -> str:
    """Format a short one-line support summary for logs and QA output."""
    level = str(report.get("support_level") or "unknown")
    kind = str(report.get("asset_kind") or "asset")
    confidence = str(report.get("confidence") or "unknown")
    issues = [str(item) for item in report.get("issue_codes") or []]
    suffix = f" issues={','.join(issues[:4])}" if issues else ""
    return f"{level} {kind} confidence={confidence}{suffix}"


def asset_support_status_text(report: Mapping[str, Any] | None) -> str:
    """Return a short product-facing support badge.

    Keep this intentionally free of internal issue code names. Detailed QA logs
    can use ``summarize_asset_support``; UI should use this function.
    """
    if not isinstance(report, Mapping) or not report:
        return "Support check pending"
    level = str(report.get("support_level") or "").casefold()
    kind = str(report.get("asset_kind") or "asset").replace("_", " ")
    issues = {str(item) for item in report.get("issue_codes") or []}
    if level == READY:
        flags = {str(item) for item in report.get("feature_flags") or []}
        if "vrm_avatar" in flags or "humanoid" in kind:
            return "Ready: VRM MToon" if "vrm_mtoon_materials" in flags else "Ready: VRM avatar"
        if "skeletal" in kind:
            return "Ready: skeletal PBR"
        if "animated" in kind:
            return "Ready: animated PBR"
        return "Ready: realtime PBR"
    if level == LIMITED:
        if "fbx_runtime_conversion_required" in issues:
            return "Limited: FBX conversion"
        if "material_constants_only" in issues:
            return "Limited: material maps missing"
        return f"Limited: {kind}"
    if level == UNSUPPORTED:
        if "unsupported_required_compression" in issues:
            return "Unsupported: compressed mesh"
        return "Unsupported 3D asset"
    if level == PLACEHOLDER:
        if "background_import_pending" in issues:
            return "Loading: checking 3D support"
        return "Placeholder preview"
    return "Support check pending"


def asset_support_user_message(report: Mapping[str, Any] | None) -> str:
    """Return one concise user-facing guidance sentence."""
    if not isinstance(report, Mapping) or not report:
        return "Support will be checked when the asset is previewed or placed."
    level = str(report.get("support_level") or "").casefold()
    issues = {str(item) for item in report.get("issue_codes") or []}
    if level == READY:
        return "Ready for preview and export."
    if level == LIMITED:
        if "fbx_runtime_conversion_required" in issues:
            return "Usable now, but FBX conversion may limit animation or material detail."
        if "material_constants_only" in issues:
            return "Usable now, but texture maps are missing so materials may look simplified."
        return "Usable now with limited renderer coverage."
    if level == UNSUPPORTED:
        if "unsupported_required_compression" in issues:
            return "Use an uncompressed GLB/FBX; this compressed mesh is not supported yet."
        return "Preview/export will skip this asset until it is converted to a supported format."
    if level == PLACEHOLDER:
        if "background_import_pending" in issues:
            return "Support will update after the background preview import finishes."
        return "A safe placeholder is being used because the asset could not be imported."
    return "Support will be checked when the asset is previewed or placed."


def public_asset_support(
    report: Mapping[str, Any] | None,
    *,
    asset_path: str = "",
    track_id: str = "",
) -> dict[str, Any]:
    """Return a UI/export-safe support row without raw issue codes."""
    data = report if isinstance(report, Mapping) else {}
    level = str(data.get("support_level") or "unknown")
    return {
        "level": level,
        "label": asset_support_status_text(report),
        "message": asset_support_user_message(report),
        "asset_path": str(asset_path or ""),
        "track_id": str(track_id or ""),
        "ok_for_preview": bool(data.get("ok_for_preview")),
        "ok_for_export": bool(data.get("ok_for_export")),
        "needs_attention": bool(data.get("needs_attention")),
    }


def placeholder_asset_support(
    path: str | Path | None = None,
    *,
    state: str = "loading",
) -> dict[str, Any]:
    """Build a non-importing placeholder support report for UI handoff."""
    ext = Path(str(path or "")).suffix.casefold()
    status = str(state or "loading").casefold()
    issue = "background_import_pending" if status != "error" else "import_failed_or_placeholder"
    support_level = PLACEHOLDER if status != "error" else UNSUPPORTED
    return {
        "support_level": support_level,
        "confidence": "none",
        "asset_kind": PLACEHOLDER,
        "format_family": _format_family(ext),
        "render_path": "unsupported_placeholder",
        "ok_for_preview": False,
        "ok_for_export": False,
        "needs_attention": status == "error",
        "issue_codes": [issue],
        "feature_flags": ["background_import"],
        "summary": asset_support_user_message({"support_level": support_level, "issue_codes": [issue]}),
        "metrics": {
            "geometry_count": 0,
            "triangle_count": 0,
            "material_count": 0,
            "texture_count": 0,
            "animation_count": 0,
            "skeletal_mesh_count": 0,
            "skin_count": 0,
        },
    }


def _format_family(ext: str) -> str:
    if ext == ".vrm":
        return "vrm"
    if ext in {".gltf", ".glb"}:
        return "gltf"
    if ext == ".fbx":
        return "fbx"
    return "unknown"


def _triangle_count(geometries: list[Mapping[str, Any]]) -> int:
    total = 0
    for geometry in geometries:
        try:
            total += int(geometry.get("triangle_count") or len(geometry.get("triangles") or []))
        except Exception:
            continue
    return int(total)


def _material_texture_count(materials: list[Mapping[str, Any]]) -> int:
    texture_keys = {
        "base_texture",
        "roughness_texture",
        "metallic_texture",
        "normal_texture",
        "occlusion_texture",
        "emissive_texture",
        "opacity_texture",
        "alpha_texture",
        "orm_texture",
        "metallic_roughness_texture",
    }
    count = 0
    for material in materials:
        for key in texture_keys:
            if material.get(key):
                count += 1
    return count


def _geometry_has_skin_data(geometry: Mapping[str, Any]) -> bool:
    return bool(geometry.get("skin_weights")) or bool(geometry.get("skin_indices")) or bool(geometry.get("skin_joints"))


def _asset_kind(
    *,
    fallback: bool,
    geometries: list[Mapping[str, Any]],
    skeletal_count: int,
    animation_count: int,
    is_vrm: bool = False,
) -> str:
    if fallback:
        return PLACEHOLDER
    if is_vrm:
        if skeletal_count > 0:
            return "humanoid_avatar"
        return "vrm_avatar"
    if skeletal_count > 0:
        return "skeletal_mesh"
    if animation_count > 0:
        return "animated_static_mesh"
    if geometries:
        return "static_mesh"
    return "unknown"


def _support_level(
    *,
    ext: str,
    fallback: bool,
    imported: bool,
    triangle_count: int,
    issue_codes: list[str],
    skeletal_count: int,
    skin_count: int,
    animation_count: int,
) -> tuple[str, str]:
    if fallback:
        if "unsupported_required_compression" in issue_codes:
            return UNSUPPORTED, "none"
        return PLACEHOLDER, "none"
    if not imported or triangle_count <= 0:
        return UNSUPPORTED, "low"
    if "unsupported_required_compression" in issue_codes:
        return UNSUPPORTED, "none"
    if ext == ".fbx":
        if skeletal_count > 0:
            return LIMITED, "medium" if skin_count > 0 else "low"
        if animation_count > 0:
            return LIMITED, "medium"
        return LIMITED, "medium"
    if skeletal_count > 0:
        if skin_count > 0:
            return READY, "high"
        return LIMITED, "medium"
    if "no_materials" in issue_codes:
        return LIMITED, "medium"
    return READY, "high"


def _render_path(
    *,
    support_level: str,
    skeletal_count: int,
    animation_count: int,
    fallback: bool,
    is_mtoon: bool = False,
) -> str:
    if fallback or support_level in {PLACEHOLDER, UNSUPPORTED}:
        return "unsupported_placeholder"
    if is_mtoon and skeletal_count > 0:
        return "full_gpu_vrm_mtoon_cpu_baked_skeletal"
    if is_mtoon:
        return "full_gpu_vrm_mtoon"
    if skeletal_count > 0:
        return "full_gpu_pbr_cpu_baked_skeletal"
    if animation_count > 0:
        return "full_gpu_pbr_cpu_baked_animation"
    return "full_gpu_pbr"


def _summary(*, support_level: str, asset_kind: str, ext: str, issue_codes: list[str]) -> str:
    fmt = _format_family(ext).upper()
    if support_level == READY:
        return f"{fmt} {asset_kind} is ready for AR/PBR preview and export."
    if support_level == LIMITED:
        return f"{fmt} {asset_kind} is usable with limitations: {', '.join(issue_codes[:3]) or 'limited renderer coverage'}."
    if support_level == PLACEHOLDER:
        return f"{fmt} asset fell back to a placeholder descriptor."
    return f"{fmt} asset is not supported by the current AR/PBR importer."


def _is_vrm_asset(asset: Mapping[str, Any], ext: str) -> bool:
    if ext == ".vrm":
        return True
    vrm = asset.get("vrm")
    return isinstance(vrm, Mapping) and bool(vrm)


def _is_mtoon_asset(asset: Mapping[str, Any], materials: list[Mapping[str, Any]]) -> bool:
    profiles = asset.get("render_profiles") if isinstance(asset.get("render_profiles"), Mapping) else {}
    if str(profiles.get("source_style") or "").casefold() == "vrm_mtoon":
        return True
    for material in materials:
        shader = str(material.get("shader_model") or material.get("source_shader") or "").casefold()
        if "mtoon" in shader:
            return True
    return False


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out
