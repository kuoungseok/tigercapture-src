"""VRM-only renderer routing for VTuber Studio and Program Output.

This module is the product boundary between VTuber/VRM rendering and the
general 3D AR/PBR workspace.  VRM surfaces may reuse low-level mesh parsing
helpers, but their public renderer contract must stay VRM/MToon-specific.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


VRM_RENDERER_FAMILY = "vtuber_vrm"
VRM_RENDER_PROFILE = "vrm_mtoon"
VRM_RENDERER_SOFTWARE = "vrm_mtoon_software"
VRM_RENDERER_GPU = "vrm_mtoon_gpu"
VRM_TRACK_TYPE = "vrm_avatar"
VRM_SOURCE_TYPE = "internal_vrm"

_SOFTWARE_ALIASES = {
    "",
    "auto",
    "software",
    "software_zbuffer",
    "software-zbuffer",
    "zbuffer",
    "mtoon",
    "vrm",
    "vrm_mtoon",
    "vrm-mtoon",
    VRM_RENDERER_SOFTWARE,
}
_GPU_ALIASES = {
    "vrm_gpu",
    "vrm-gpu",
    "vrm_mtoon_gpu",
    "vrm-mtoon-gpu",
    VRM_RENDERER_GPU,
}
_PBR_ALIASES = {
    "ar_pbr",
    "ar-pbr",
    "pbr",
    "software_pbr",
    "packet_pbr",
    "marmoset_pbr",
    "model_view_gpu",
    "full_gpu",
    "full-gpu",
    "offscreen_gpu",
}


def normalize_vrm_renderer(renderer: Any) -> str:
    """Return the only renderer id allowed to drive VRM Studio output."""
    key = str(renderer or "").strip().casefold().replace(" ", "_")
    # Until a true VRM/MToon GPU renderer exists, GPU-looking aliases must not
    # route into the general AR/PBR full-GPU path.
    if key in _GPU_ALIASES:
        return VRM_RENDERER_SOFTWARE
    if key in _SOFTWARE_ALIASES or key in _PBR_ALIASES:
        return VRM_RENDERER_SOFTWARE
    return VRM_RENDERER_SOFTWARE


def vrm_renderer_warnings(renderer: Any) -> list[str]:
    key = str(renderer or "").strip().casefold().replace(" ", "_")
    if key in _GPU_ALIASES:
        return [f"vrm_gpu_renderer_not_available_yet:{key}"]
    if key in _PBR_ALIASES:
        return [f"pbr_renderer_alias_rewritten_for_vrm:{key}"]
    if key and key not in _SOFTWARE_ALIASES and key not in _GPU_ALIASES:
        return [f"unknown_vrm_renderer_rewritten:{key}"]
    return []


def vrm_renderer_contract(renderer: Any = None) -> dict[str, Any]:
    normalized = normalize_vrm_renderer(renderer)
    return {
        "family": VRM_RENDERER_FAMILY,
        "renderer": normalized,
        "render_profile": VRM_RENDER_PROFILE,
        "track_type": VRM_TRACK_TYPE,
        "source_type": VRM_SOURCE_TYPE,
        "pbr_renderer": False,
        "ar_pbr_preview": False,
        "warnings": vrm_renderer_warnings(renderer),
    }


def make_vrm_render_track(
    *,
    track_id: str,
    asset_path: str | Path,
    transform: Mapping[str, Any],
    animation: Mapping[str, Any] | None = None,
    render: Mapping[str, Any] | None = None,
    start_ms: int = 0,
    end_ms: int = 60_000,
) -> dict[str, Any]:
    render_map = dict(render or {})
    renderer = normalize_vrm_renderer(render_map.get("renderer"))
    render_map.update(
        {
            "renderer": renderer,
            "renderer_family": VRM_RENDERER_FAMILY,
            "render_profile": VRM_RENDER_PROFILE,
            "pbr_enabled": False,
            "ar_pbr_preview": False,
        }
    )
    return {
        "id": str(track_id or "internal_vrm_fallback"),
        "type": VRM_TRACK_TYPE,
        "asset_path": str(asset_path),
        "start_ms": int(start_ms),
        "end_ms": int(end_ms),
        "renderer_family": VRM_RENDERER_FAMILY,
        "render_profile": VRM_RENDER_PROFILE,
        "performance_role": "avatar_target",
        "transform": dict(transform),
        "animation": dict(animation or {}),
        "shadow_catcher": False,
        "reflection_catcher": False,
        "occlusion": False,
        "render": render_map,
    }


def load_vrm_avatar_descriptor(
    vrm_path: str | Path,
    *,
    settings: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load a VRM descriptor through the VTuber boundary.

    The low-level importer currently lives in the AR/PBR package because it owns
    shared glTF buffer parsing.  This wrapper disables the AR/PBR persistent
    descriptor cache and stamps the result as a VRM/MToon avatar descriptor.
    """
    path = Path(vrm_path)
    if path.suffix.casefold() != ".vrm":
        raise ValueError(f"VRM renderer requires a .vrm avatar: {path}")
    from app.ar_pbr.importer import import_asset

    import_settings = {
        **dict(settings or {}),
        "placeholder_on_error": False,
        "disable_descriptor_cache": True,
        "max_triangles_per_geometry": 12000,
    }
    descriptor, diagnostics = import_asset(path, settings=import_settings)
    descriptor = dict(descriptor or {})
    descriptor["type"] = "vrm_avatar_descriptor"
    descriptor["runtime_format"] = "vrm_mtoon_avatar_descriptor"
    descriptor["renderer_family"] = VRM_RENDERER_FAMILY
    descriptor["render_profile"] = VRM_RENDER_PROFILE
    descriptor["ar_pbr_preview"] = False
    descriptor["pbr_renderer"] = False
    profiles = dict(descriptor.get("render_profiles") if isinstance(descriptor.get("render_profiles"), Mapping) else {})
    profiles["default_profile"] = VRM_RENDER_PROFILE
    profiles["source_style"] = VRM_RENDER_PROFILE
    descriptor["render_profiles"] = profiles
    diagnostics = dict(diagnostics or {})
    diagnostics.update(
        {
            "renderer_family": VRM_RENDERER_FAMILY,
            "render_profile": VRM_RENDER_PROFILE,
            "vrm_renderer_boundary": True,
            "ar_pbr_renderer_used": False,
            "descriptor_cache_disabled": True,
        }
    )
    return descriptor, diagnostics
