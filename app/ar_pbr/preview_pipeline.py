"""Pure AR/PBR preview policy helpers used by ProjectPlayer."""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Mapping


def gpu_preview_enabled(value: str | None = None) -> bool:
    mode = str(value if value is not None else os.environ.get("TIGERCAPTURE_AR_PBR_GPU_PREVIEW", "1"))
    return mode.strip().casefold() not in {"0", "false", "no", "off", "disabled", "cpu", "software"}


def normalize_preview_renderer_mode(value: str | None) -> str:
    text = str(value or "auto").strip().casefold()
    if text in {"gpu", "opengl", "offscreen", "offscreen_gpu", "full_gpu", "native_gpu", "model_view_gpu"}:
        return "full_gpu"
    if text in {"packet", "gpu_packet", "preview_packet", "packet_pbr"}:
        return "packet"
    if text in {"software", "software_pbr", "cpu"}:
        return "software_pbr"
    if text in {"off", "disabled", "none", "0", "false", "no"}:
        return "off"
    return "auto"


def preview_renderer_mode_from_env() -> str:
    return normalize_preview_renderer_mode(os.environ.get("TIGERCAPTURE_AR_PBR_PREVIEW_RENDERER", "auto"))


def should_use_full_gpu_preview(mode: str, *, playing: bool) -> bool:
    normalized = normalize_preview_renderer_mode(mode)
    if normalized == "full_gpu":
        return True
    if normalized != "auto":
        return False
    return not bool(playing)


def realtime_scene_anchor_enabled(*, playing: bool, value: str | None = None) -> bool:
    if not playing:
        return True
    text = str(value if value is not None else os.environ.get("TIGERCAPTURE_AR_PBR_PLAYBACK_SCENE_ANCHOR", ""))
    return text.strip().casefold() in {"1", "true", "yes", "on", "enabled"}


def realtime_depth_enabled(*, playing: bool, value: str | None = None) -> bool:
    if not playing:
        return True
    text = str(value if value is not None else os.environ.get("TIGERCAPTURE_AR_PBR_PLAYBACK_DEPTH", ""))
    return text.strip().casefold() in {"1", "true", "yes", "on", "enabled"}


def gpu_preview_triangle_limit(
    *,
    playing: bool,
    preview_limit: int,
    playback_limit: int,
    preview_env: str | None = None,
    playback_env: str | None = None,
) -> int:
    default = int(playback_limit if playing else preview_limit)
    raw = playback_env if playing else preview_env
    if raw is None:
        env_key = "TIGERCAPTURE_AR_PBR_PLAYBACK_TRIANGLE_LIMIT" if playing else "TIGERCAPTURE_AR_PBR_PREVIEW_TRIANGLE_LIMIT"
        raw = os.environ.get(env_key, "")
    try:
        value = int(raw) if str(raw or "").strip() else int(default)
    except Exception:
        value = int(default)
    return max(64, min(int(preview_limit), int(value)))


def cache_digest(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        )
    except Exception:
        payload = repr(value)
    return hashlib.sha1(payload.encode("utf-8", errors="ignore")).hexdigest()


def descriptor_fingerprint(descriptor: Mapping | None) -> tuple:
    if not isinstance(descriptor, Mapping):
        return ("missing",)
    cache = descriptor.get("cache") if isinstance(descriptor.get("cache"), Mapping) else {}
    bounds = descriptor.get("bounds") if isinstance(descriptor.get("bounds"), Mapping) else {}
    return (
        str(descriptor.get("id") or ""),
        str(descriptor.get("source_path") or ""),
        int(descriptor.get("mesh_count", 0) or 0),
        int(descriptor.get("material_count", 0) or 0),
        int(descriptor.get("animation_count", 0) or 0),
        int(cache.get("source_size", 0) or 0),
        int(cache.get("source_mtime_ns", 0) or 0),
        int(cache.get("schema_version", 0) or 0),
        cache_digest(bounds),
    )


def descriptor_has_playing_animation(track: Mapping, descriptor: Mapping | None) -> bool:
    if not isinstance(descriptor, Mapping):
        return False
    animation_clips = descriptor.get("animation_clips")
    if not isinstance(animation_clips, list) or not animation_clips:
        return False
    animation = track.get("animation") if isinstance(track.get("animation"), Mapping) else {}
    auto_play = bool(animation.get("auto_play", True))
    try:
        speed = float(animation.get("speed", 1.0) or 0.0)
    except Exception:
        speed = 1.0
    return auto_play and abs(speed) > 1e-6


def gpu_packet_cache_key(
    *,
    playing: bool,
    context: Mapping,
    active_tracks: list[dict],
    settings: Mapping,
    triangle_limit: int,
) -> tuple | None:
    if not playing:
        return None
    if context.get("depth_frame") is not None:
        return None
    descriptors = settings.get("asset_descriptors")
    if not isinstance(descriptors, Mapping):
        return None
    descriptor_rows: list[tuple[str, tuple]] = []
    for track in active_tracks:
        if not isinstance(track, Mapping):
            return None
        track_id = str(track.get("id") or "")
        asset_path = str(track.get("asset_path") or "")
        descriptor = None
        for key in (track_id, asset_path):
            candidate = descriptors.get(key)
            if isinstance(candidate, Mapping):
                descriptor = candidate
                break
        if descriptor_has_playing_animation(track, descriptor):
            return None
        descriptor_rows.append((track_id or asset_path, descriptor_fingerprint(descriptor)))
    payload = {
        "frame_size": [int(context.get("width") or 0), int(context.get("height") or 0)],
        "triangle_limit": int(triangle_limit),
        "camera_solution": context.get("camera_solution"),
        "tracks": active_tracks,
        "descriptors": descriptor_rows,
        "camera_z": settings.get("camera_z"),
        "shadow_blur": settings.get("shadow_blur"),
    }
    return ("ar_pbr_gpu_packet", cache_digest(payload))
