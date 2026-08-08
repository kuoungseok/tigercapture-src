"""Motion Designer VRM adapter using the internal MToon GPU renderer."""
from __future__ import annotations

from collections import OrderedDict
import time
from typing import Any

from PySide6.QtGui import QImage

from app.motion_designer.schema import MotionComposition, MotionLayer
from app.motion_designer.vrm_source import evaluate_vrm_frame
from app.vtuber.vrm_renderer import VRM_RENDERER_FAMILY, VRM_RENDERER_GPU

from .actor_common import actor_qimage, actor_source_signature


_FRAME_CACHE_CAPACITY = 12
_FRAME_CACHE: OrderedDict[tuple[Any, ...], QImage] = OrderedDict()
_DIAGNOSTICS: dict[str, dict[str, Any]] = {}


def render_vrm(
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
    width, height = max(16, int(width)), max(16, int(height))
    frame = evaluate_vrm_frame(
        layer, time_ms, composition=composition, composition_time_ms=composition_time_ms,
    )
    playback = params.get("playback") if isinstance(params.get("playback"), dict) else {}
    fps = max(1.0, min(60.0, float(playback.get("preview_cache_fps", 30.0) or 30.0)))
    frame_index = max(0, int(round(frame.sample_time_ms * fps / 1000.0)))
    sample_ms = int(round(frame_index * 1000.0 / fps))
    cache_key = (
        layer.id,
        actor_source_signature(layer),
        int(getattr(composition, "revision", 0) or 0),
        width,
        height,
        frame_index,
    )
    cached = _FRAME_CACHE.get(cache_key)
    if cached is not None:
        _FRAME_CACHE.move_to_end(cache_key)
        _DIAGNOSTICS[layer.id] = {
            **dict(_DIAGNOSTICS.get(layer.id) or {}),
            "cache_hit": True,
            "requested_quality": str(quality),
            "canonical_frame_cache": True,
            "frame_cache_size": len(_FRAME_CACHE),
        }
        return cached.copy()

    started = time.perf_counter()
    try:
        from app.vtuber.internal_vrm_fallback import render_internal_vrm_fallback_frame

        source = dict(frame.source)
        settings = dict(source.get("settings") or {})
        motion_frame = dict(settings.get("motion_frame") or {})
        motion_frame["time_ms"] = sample_ms
        settings["motion_frame"] = motion_frame
        source["settings"] = settings
        value, renderer_diagnostics = render_internal_vrm_fallback_frame(
            source,
            time_ms=sample_ms,
            width=width,
            height=height,
            renderer=VRM_RENDERER_GPU,
        )
        image = actor_qimage(value, width, height)
        alpha_visible = False
        try:
            alpha_visible = value.convert("RGBA").getchannel("A").getbbox() is not None
        except Exception:
            alpha_visible = not image.isNull()
        ok = bool(renderer_diagnostics.get("ok")) and alpha_visible and not image.isNull()
        diagnostics = {
            **frame.diagnostics,
            **dict(renderer_diagnostics),
            "ok": ok,
            "source_adapter": "motion_vrm_internal_mtoon_gpu",
            "renderer": VRM_RENDERER_GPU,
            "renderer_family": VRM_RENDERER_FAMILY,
            "quality": str(quality),
            "canonical_frame_cache": True,
            "cache_hit": False,
            "frame_index": frame_index,
            "sample_time_ms": sample_ms,
            "frame_render_seconds": round(time.perf_counter() - started, 4),
            "frame_cache_size": len(_FRAME_CACHE) + (1 if ok else 0),
            "frame_cache_capacity": _FRAME_CACHE_CAPACITY,
            "alpha_visible": alpha_visible,
            "width": width,
            "height": height,
            "realtime_claim": False,
        }
        if not ok:
            errors = list(diagnostics.get("errors") or [])
            if not alpha_visible:
                errors.append("VRM MToon GPU renderer returned no visible alpha")
            diagnostics["errors"] = errors
    except Exception as exc:
        image = actor_qimage(None, width, height)
        diagnostics = {
            **frame.diagnostics,
            "ok": False,
            "source_adapter": "motion_vrm_internal_mtoon_gpu",
            "renderer": VRM_RENDERER_GPU,
            "renderer_family": VRM_RENDERER_FAMILY,
            "canonical_frame_cache": True,
            "cache_hit": False,
            "frame_render_seconds": round(time.perf_counter() - started, 4),
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
    _DIAGNOSTICS[layer.id] = diagnostics
    if diagnostics.get("ok"):
        _FRAME_CACHE[cache_key] = image.copy()
        _FRAME_CACHE.move_to_end(cache_key)
        while len(_FRAME_CACHE) > _FRAME_CACHE_CAPACITY:
            _FRAME_CACHE.popitem(last=False)
    return image


def vrm_diagnostics(layer_id: str = "") -> dict[str, Any]:
    if layer_id:
        return dict(_DIAGNOSTICS.get(str(layer_id)) or {})
    return {key: dict(value) for key, value in _DIAGNOSTICS.items()}


def clear_vrm_cache() -> None:
    _FRAME_CACHE.clear()


__all__ = ["clear_vrm_cache", "render_vrm", "vrm_diagnostics"]
