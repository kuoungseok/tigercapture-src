"""Motion Designer Live2D adapter backed by the existing Cubism renderer."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from PySide6.QtGui import QImage

from app.motion_designer.actor_source import MotionActorFrame, evaluate_actor_frame
from app.motion_designer.schema import MotionComposition, MotionLayer

from .actor_common import actor_qimage, actor_source_signature


_CACHE_CAPACITY = 20
_FRAME_CACHE: OrderedDict[tuple[Any, ...], QImage] = OrderedDict()
_DIAGNOSTICS: dict[str, dict[str, Any]] = {}


@dataclass
class _Live2DState:
    clip: Any
    last_frame_index: int = -1


_STATE_CAPACITY = 8
_STATES: OrderedDict[tuple[Any, ...], _Live2DState] = OrderedDict()


def _new_clip(frame: MotionActorFrame, duration_ms: int):
    from app.live2d.actor_track import Live2DActorClip

    return Live2DActorClip(
        model_path=frame.resolved_path,
        motion_group=frame.motion_group,
        motion_idx=frame.motion_index,
        expression_id=frame.expression,
        start_ms=0,
        duration_ms=max(1, int(duration_ms)),
        loop=frame.loop,
        pos_x=frame.position[0],
        pos_y=frame.position[1],
        scale=frame.scale,
        opacity=frame.opacity,
        auto_blink=False,
        auto_breath=False,
        parameter_keyframes=frame.parameters,
    )


def _evict(clip: Any) -> None:
    try:
        from app.live2d.actor_track import _OffscreenRenderer

        _OffscreenRenderer.instance().evict_model(str(clip.model_path), id(clip))
    except Exception:
        pass


def render_live2d(
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
    frame_index = max(0, int(round(frame.playback_time_ms * fps / 1000.0)))
    sample_ms = frame_index * 1000.0 / fps
    signature = actor_source_signature(layer)
    revision = int(getattr(composition, "revision", 0) or 0)
    runtime_key = (
        layer.id,
        frame.resolved_path,
        frame.motion_group,
        frame.motion_index,
        frame.expression,
        round(fps, 3),
        width,
        height,
    )
    state_key = runtime_key
    cache_key = (layer.id, signature, revision, width, height, frame_index)
    cached = _FRAME_CACHE.get(cache_key)
    if cached is not None:
        _FRAME_CACHE.move_to_end(cache_key)
        _DIAGNOSTICS[layer.id] = {
            **dict(_DIAGNOSTICS.get(layer.id) or {}),
            "cache_hit": True,
            "requested_quality": str(quality),
            "canonical_frame_cache": True,
        }
        return cached.copy()

    state = _STATES.get(state_key)
    if state is None or frame_index < state.last_frame_index:
        if state is not None:
            _evict(state.clip)
        state = _Live2DState(_new_clip(frame, layer.out_ms - layer.in_ms))
        _STATES[state_key] = state
    _STATES.move_to_end(state_key)
    while len(_STATES) > _STATE_CAPACITY:
        _old_key, old_state = _STATES.popitem(last=False)
        _evict(old_state.clip)
    clip = state.clip
    clip.motion_group = frame.motion_group
    clip.motion_idx = frame.motion_index
    clip.expression_id = frame.expression
    clip.pos_x, clip.pos_y = frame.position
    clip.scale, clip.opacity = frame.scale, frame.opacity
    clip.parameter_keyframes = frame.parameters
    clip.mocap_parameter_keyframes = {
        "ParamMouthOpenY": [{"time_ms": int(round(sample_ms)), "value": frame.mouth_open, "curve": "linear"}],
    }
    image = None
    try:
        start_index = max(0, state.last_frame_index + 1)
        for index in range(start_index, frame_index + 1):
            image = clip.render_frame(width, height, int(round(index * 1000.0 / fps)))
        if image is None:
            image = clip.render_frame(width, height, int(round(sample_ms)))
        state.last_frame_index = frame_index
        qimage = actor_qimage(image, width, height)
        diagnostics = {
            **frame.diagnostics,
            "ok": image is not None and not qimage.isNull(),
            "source_adapter": "motion_live2d_existing_cubism_renderer",
            "renderer": "live2d_cubism_gpu",
            "quality": str(quality),
            "canonical_frame_cache": True,
            "cache_hit": False,
            "sequential_frame_index": frame_index,
            "sequential_evaluation_fps": fps,
            "arbitrary_seek_policy": "reset_then_fixed_fps_forward_evaluation",
            "width": width,
            "height": height,
        }
    except Exception as exc:
        qimage = actor_qimage(None, width, height)
        diagnostics = {
            **frame.diagnostics,
            "ok": False,
            "source_adapter": "motion_live2d_existing_cubism_renderer",
            "renderer": "live2d_cubism_gpu",
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
    _DIAGNOSTICS[layer.id] = diagnostics
    _FRAME_CACHE[cache_key] = qimage.copy()
    _FRAME_CACHE.move_to_end(cache_key)
    while len(_FRAME_CACHE) > _CACHE_CAPACITY:
        _FRAME_CACHE.popitem(last=False)
    return qimage


def live2d_diagnostics(layer_id: str = "") -> dict[str, Any]:
    if layer_id:
        return dict(_DIAGNOSTICS.get(str(layer_id)) or {})
    return {key: dict(value) for key, value in _DIAGNOSTICS.items()}


def clear_live2d_cache() -> None:
    for state in _STATES.values():
        _evict(state.clip)
    _STATES.clear()
    _FRAME_CACHE.clear()


__all__ = ["clear_live2d_cache", "live2d_diagnostics", "render_live2d"]
