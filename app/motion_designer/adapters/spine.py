"""Motion Designer Spine adapter backed by Tiger Studio's existing renderer."""
from __future__ import annotations

from collections import OrderedDict
from typing import Any

from PySide6.QtGui import QImage

from app.motion_designer.actor_source import evaluate_actor_frame
from app.motion_designer.schema import MotionComposition, MotionLayer

from .actor_common import actor_qimage, actor_source_signature


_CACHE_CAPACITY = 24
_FRAME_CACHE: OrderedDict[tuple[Any, ...], QImage] = OrderedDict()
_CLIP_CAPACITY = 8
_CLIPS: OrderedDict[tuple[Any, ...], Any] = OrderedDict()
_DIAGNOSTICS: dict[str, dict[str, Any]] = {}


def render_spine(
    layer: MotionLayer,
    time_ms: float,
    *,
    composition: MotionComposition | None = None,
    composition_time_ms: float | None = None,
    quality: str = "preview",
    viewport_size: tuple[int, int] | None = None,
) -> QImage:
    params = layer.source.params
    render = params.get("render") if isinstance(params.get("render"), dict) else {}
    width, height = viewport_size or (render.get("width", 1920), render.get("height", 1080))
    width, height = max(2, int(width)), max(2, int(height))
    frame = evaluate_actor_frame(
        layer, time_ms, composition=composition, composition_time_ms=composition_time_ms,
    )
    playback = params.get("playback") if isinstance(params.get("playback"), dict) else {}
    fps = max(6.0, min(60.0, float(playback.get("preview_cache_fps", 30.0) or 30.0)))
    key_time = (
        round(frame.playback_time_ms / (1000.0 / fps)) * (1000.0 / fps)
        if str(quality).lower() == "preview" else frame.playback_time_ms
    )
    signature = actor_source_signature(layer)
    revision = int(getattr(composition, "revision", 0) or 0)
    clip_key = (layer.id, frame.resolved_path, frame.atlas_path, width, height)
    key = (layer.id, signature, revision, width, height, round(float(key_time), 3), str(quality))
    cached = _FRAME_CACHE.get(key)
    if cached is not None:
        _FRAME_CACHE.move_to_end(key)
        _DIAGNOSTICS[layer.id] = {**dict(_DIAGNOSTICS.get(layer.id) or {}), "cache_hit": True}
        return cached.copy()

    clip = _CLIPS.get(clip_key)
    if clip is None:
        from app.spine_editor.actor_track import SpineActorClip

        clip = SpineActorClip(
            skel_path=frame.resolved_path,
            atlas_path=frame.atlas_path,
            anim_name=frame.animation,
            skin_name=frame.skin,
            start_ms=0,
            duration_ms=max(1, layer.out_ms - layer.in_ms),
            loop=frame.loop,
            pos_x=frame.position[0],
            pos_y=frame.position[1],
            scale=frame.scale,
        )
        _CLIPS[clip_key] = clip
    _CLIPS.move_to_end(clip_key)
    while len(_CLIPS) > _CLIP_CAPACITY:
        _CLIPS.popitem(last=False)
    clip.anim_name = frame.animation
    clip.skin_name = frame.skin
    clip.loop = frame.loop
    clip.pos_x, clip.pos_y = frame.position
    clip.scale = frame.scale
    try:
        # Shared CPU output keeps preview and worker-thread export visually identical.
        image = clip.render_frame(
            width, height, int(round(key_time)), animated=True,
            fast_preview=False, use_gl=False,
        )
        if image is not None and frame.opacity < 0.999:
            image = image.copy()
            alpha = image.getchannel("A").point(lambda value: int(value * frame.opacity))
            image.putalpha(alpha)
        qimage = actor_qimage(image, width, height)
        diagnostics = {
            **frame.diagnostics,
            "ok": image is not None and not qimage.isNull(),
            "source_adapter": "motion_spine_existing_renderer",
            "renderer": "spine_shared_cpu_parity",
            "fast_mesh_preview": False,
            "quality": str(quality),
            "cache_hit": False,
            "animation": frame.animation,
            "skin": frame.skin,
            "resolved_skin": str(getattr(clip, "_resolved_skin_cache", "") or frame.skin),
            "width": width,
            "height": height,
            "lip_sync": "cue_timing_attached_no_generic_spine_slot_mapping" if frame.mouth_open else "inactive",
        }
    except Exception as exc:
        qimage = actor_qimage(None, width, height)
        diagnostics = {
            **frame.diagnostics,
            "ok": False,
            "source_adapter": "motion_spine_existing_renderer",
            "renderer": "spine_shared_cpu_parity",
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
    _DIAGNOSTICS[layer.id] = diagnostics
    _FRAME_CACHE[key] = qimage.copy()
    _FRAME_CACHE.move_to_end(key)
    while len(_FRAME_CACHE) > _CACHE_CAPACITY:
        _FRAME_CACHE.popitem(last=False)
    return qimage


def spine_diagnostics(layer_id: str = "") -> dict[str, Any]:
    if layer_id:
        return dict(_DIAGNOSTICS.get(str(layer_id)) or {})
    return {key: dict(value) for key, value in _DIAGNOSTICS.items()}


def clear_spine_cache() -> None:
    _CLIPS.clear()
    _FRAME_CACHE.clear()


__all__ = ["clear_spine_cache", "render_spine", "spine_diagnostics"]
