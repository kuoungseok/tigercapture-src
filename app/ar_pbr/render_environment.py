"""Environment ray-visibility and hardware-RT capability contracts.

This module is intentionally renderer-neutral. OpenGL preview, packet export,
Actions, and a future native DXR/Vulkan helper consume the same normalized
policy without claiming hardware ray tracing when no native backend exists.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any, Mapping


ENVIRONMENT_SCHEMA = "tigerstudio.ar_pbr.environment_visibility.v1"
RT_CAPABILITY_SCHEMA = "tigerstudio.ar_pbr.hardware_rt_capability.v1"
RENDER_MODE_SCHEMA = "tigerstudio.ar_pbr.render_mode.v1"
RENDER_MODES: tuple[str, ...] = (
    "ibl_realtime",
    "hybrid_rt",
    "path_traced",
    "studio_lights_only",
)
BACKGROUND_OUTPUTS: tuple[str, ...] = ("environment", "transparent", "solid")
_CAPABILITY_CACHE: dict[tuple[str, int], dict[str, Any]] = {}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "visible"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", "hidden"}:
        return False
    return bool(default)


def _float(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        number = float(value)
    except Exception:
        number = float(default)
    return max(float(lo), min(float(hi), number))


def normalize_environment_visibility(value: Any) -> dict[str, Any]:
    data = _mapping(value)
    nested = _mapping(data.get("environment_visibility"))

    def get(key: str, *aliases: str, default: Any = None) -> Any:
        for name in (key, *aliases):
            if name in nested:
                return nested.get(name)
            if name in data:
                return data.get(name)
        return default

    camera = _bool(get("camera_visible", "show_environment_background", default=True), True)
    reflection = _bool(get("reflection_visible", "reflection_environment_visible", default=True), True)
    diffuse = _bool(get("diffuse_visible", "diffuse_environment_visible", default=True), True)
    refraction = _bool(get("refraction_visible", "refraction_environment_visible", default=True), True)
    background = str(get("background_output", default="environment" if camera else "transparent") or "environment")
    background = background.strip().casefold().replace("-", "_")
    if background not in BACKGROUND_OUTPUTS:
        background = "environment" if camera else "transparent"
    if background == "environment":
        camera = True
    else:
        camera = False
    return {
        "schema": ENVIRONMENT_SCHEMA,
        "camera_visible": camera,
        "reflection_visible": reflection,
        "diffuse_visible": diffuse,
        "refraction_visible": refraction,
        "background_output": background,
        "diffuse_strength": _float(get("diffuse_strength", default=1.0), 1.0, 0.0, 8.0),
        "reflection_strength": _float(get("reflection_strength", default=1.0), 1.0, 0.0, 8.0),
        "refraction_strength": _float(get("refraction_strength", default=1.0), 1.0, 0.0, 8.0),
        "reflection_rotation": _float(
            get("reflection_rotation", default=data.get("ibl_rotation", 0.0)),
            0.0,
            -180.0,
            180.0,
        ),
        "invisible_reflection_environment": bool(not camera and reflection),
    }


def hardware_rt_capability(
    helper_path: str | Path | None = None,
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    """Probe an explicit native helper; CUDA alone never counts as DXR/VKRT.

    Capability checks are cached by helper path and file timestamp. Render
    loops may normalize lighting for every object and must never spawn a helper
    process per object or per frame.
    """
    configured = str(helper_path or os.environ.get("TIGERSTUDIO_HARDWARE_RT_HELPER") or "").strip()
    if not configured:
        try:
            from app.ar_pbr.native_rt import default_native_rt_helper_path

            default_helper = default_native_rt_helper_path()
            if default_helper.is_file():
                configured = str(default_helper)
        except Exception:
            configured = ""
    path = Path(configured).expanduser() if configured else None
    try:
        stamp = int(path.stat().st_mtime_ns) if path is not None and path.is_file() else 0
    except OSError:
        stamp = 0
    cache_key = (str(path) if path is not None else "", stamp)
    if refresh:
        _CAPABILITY_CACHE.pop(cache_key, None)
    cached = _CAPABILITY_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)
    payload: dict[str, Any] = {}
    error = ""
    if path is not None and path.is_file():
        try:
            completed = subprocess.run(
                [str(path), "--capabilities-json"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if completed.returncode == 0:
                payload = json.loads(completed.stdout or "{}")
            else:
                error = f"helper_exit_{completed.returncode}"
        except Exception as exc:
            error = f"helper_probe_failed:{type(exc).__name__}"
    api = str(payload.get("api") or "").strip().lower()
    if api not in {"dxr", "vulkan_rt"}:
        api = ""
    available = bool(payload.get("hardware_ray_tracing") and api)
    result = {
        "schema": RT_CAPABILITY_SCHEMA,
        "available": available,
        "api": api or None,
        "device": str(payload.get("device") or ""),
        "raytracing_tier": str(payload.get("raytracing_tier") or ""),
        "renderer": str(payload.get("renderer") or ""),
        "shader_model_6_5": bool(payload.get("shader_model_6_5")),
        "helper_path": str(path) if path is not None else "",
        "helper_configured": path is not None,
        "helper_exists": bool(path is not None and path.is_file()),
        "separate_process_required": True,
        "cuda_is_not_rt_proof": True,
        "error": error or None,
    }
    _CAPABILITY_CACHE[cache_key] = dict(result)
    return result


def resolve_render_mode(value: Any, *, capability: Mapping[str, Any] | None = None) -> dict[str, Any]:
    data = _mapping(value)
    requested = str(data.get("render_mode") or data.get("rt_mode") or "ibl_realtime")
    requested = requested.strip().casefold().replace("-", "_")
    aliases = {"realtime": "ibl_realtime", "ibl": "ibl_realtime", "hybrid": "hybrid_rt", "rt": "hybrid_rt", "pt": "path_traced"}
    requested = aliases.get(requested, requested)
    if requested not in RENDER_MODES:
        requested = "ibl_realtime"
    rt = dict(capability or hardware_rt_capability())
    needs_rt = requested in {"hybrid_rt", "path_traced"}
    native = bool(rt.get("available"))
    active = requested if not needs_rt or native else "ibl_realtime"
    fallback = active != requested
    if requested == "studio_lights_only":
        environment_policy = "disabled"
    elif requested == "path_traced" and native:
        environment_policy = "ray_sampled_environment_no_prefilter_approximation"
    elif requested == "hybrid_rt" and native:
        environment_policy = "diffuse_ibl_rt_reflection_with_environment_miss"
    else:
        environment_policy = "prefiltered_diffuse_and_specular_ibl"
    return {
        "schema": RENDER_MODE_SCHEMA,
        "requested": requested,
        "active": active,
        "hardware_rt_active": bool(native and needs_rt),
        "fallback": fallback,
        "fallback_reason": "native_rt_backend_unavailable" if fallback else None,
        "environment_policy": environment_policy,
        "rt_capability": rt,
    }
