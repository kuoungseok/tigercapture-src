"""AR/PBR source adapter backed by Tiger Studio's existing OpenGL service."""
from __future__ import annotations

from collections import OrderedDict
import json
from pathlib import Path
from typing import Any

from PySide6.QtGui import QImage

from app.ar_pbr.compositor import composite_export_frame, composite_preview_frame
from app.motion_designer.ar_pbr_source import evaluate_ar_pbr_frame
from app.motion_designer.schema import MotionComposition, MotionLayer
from app.motion_designer.source_frame import premultiplied, transparent_image


_CACHE_CAPACITY = 24
_FRAME_CACHE: OrderedDict[tuple[Any, ...], QImage] = OrderedDict()
_DIAGNOSTICS: dict[str, dict[str, Any]] = {}


def _source_signature(layer: MotionLayer) -> tuple[Any, ...]:
    path = Path(layer.source.uri)
    try:
        stat = path.stat()
        file_signature = (str(path.resolve()), int(stat.st_size), int(stat.st_mtime_ns))
    except OSError:
        file_signature = (str(path), 0, 0)
    params = json.dumps(layer.source.params, sort_keys=True, ensure_ascii=True, default=str)
    return (*file_signature, str(layer.source.revision or ""), params)


def _qimage(value: Any, width: int, height: int) -> QImage:
    if isinstance(value, QImage):
        return premultiplied(value.copy())
    try:
        import numpy as np

        array = np.asarray(value, dtype=np.uint8)
        if array.ndim == 3 and array.shape[2] in {3, 4}:
            if array.shape[2] == 3:
                alpha = np.full((array.shape[0], array.shape[1], 1), 255, dtype=np.uint8)
                array = np.concatenate((array, alpha), axis=2)
            rgba = np.ascontiguousarray(array)
            image = QImage(
                rgba.data, int(rgba.shape[1]), int(rgba.shape[0]), int(rgba.strides[0]), QImage.Format_RGBA8888,
            ).copy()
            return premultiplied(image)
    except Exception:
        pass
    return transparent_image(width, height)


def render_ar_pbr(
    layer: MotionLayer,
    time_ms: float,
    *,
    composition: MotionComposition | None = None,
    composition_time_ms: float | None = None,
    quality: str = "preview",
    viewport_size: tuple[int, int] | None = None,
) -> QImage:
    params = layer.source.params
    width = max(2, int((viewport_size or (params.get("width", 1920), params.get("height", 1080)))[0]))
    height = max(2, int((viewport_size or (params.get("width", 1920), params.get("height", 1080)))[1]))
    global_time = float(time_ms if composition_time_ms is None else composition_time_ms)
    frame = evaluate_ar_pbr_frame(
        layer, time_ms, composition=composition, composition_time_ms=global_time,
    )
    preview_fps = max(1.0, min(60.0, float(params.get("preview_cache_fps", 30.0) or 30.0)))
    key_time = (
        round(global_time / (1000.0 / preview_fps)) * (1000.0 / preview_fps)
        if str(quality).lower() == "preview" else global_time
    )
    key = (
        layer.id, _source_signature(layer), int(getattr(composition, "revision", 0) or 0),
        round(float(time_ms), 3), round(float(key_time), 3), width, height, str(quality),
        json.dumps(frame.track, sort_keys=True, default=str),
        json.dumps(frame.settings, sort_keys=True, default=str),
    )
    cached = _FRAME_CACHE.get(key)
    if cached is not None:
        _FRAME_CACHE.move_to_end(key)
        diagnostics = dict(_DIAGNOSTICS.get(layer.id) or {})
        diagnostics["cache_hit"] = True
        _DIAGNOSTICS[layer.id] = diagnostics
        return cached.copy()

    try:
        import numpy as np

        base = np.zeros((height, width, 4), dtype=np.uint8)
        render = composite_export_frame if str(quality).lower() == "export" else composite_preview_frame
        output, render_diagnostics = render(
            base,
            int(round(time_ms)),
            [frame.track],
            {},
            depth_frame=frame.depth_frame,
            settings=frame.settings,
        )
        image = _qimage(output, width, height)
        diagnostics = {**frame.diagnostics, **dict(render_diagnostics or {})}
        diagnostics.update({
            "source_adapter": "motion_ar_pbr_existing_opengl_service",
            "quality": str(quality),
            "cache_hit": False,
            "width": width,
            "height": height,
        })
    except Exception as exc:
        image = transparent_image(width, height)
        diagnostics = {
            **frame.diagnostics,
            "ok": False,
            "fallback": True,
            "source_adapter": "motion_ar_pbr_existing_opengl_service",
            "quality": str(quality),
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
    _DIAGNOSTICS[layer.id] = diagnostics
    _FRAME_CACHE[key] = image.copy()
    _FRAME_CACHE.move_to_end(key)
    while len(_FRAME_CACHE) > _CACHE_CAPACITY:
        _FRAME_CACHE.popitem(last=False)
    return image


def ar_pbr_diagnostics(layer_id: str = "") -> dict[str, Any]:
    if layer_id:
        return dict(_DIAGNOSTICS.get(str(layer_id)) or {})
    return {key: dict(value) for key, value in _DIAGNOSTICS.items()}


def clear_ar_pbr_cache() -> None:
    _FRAME_CACHE.clear()


__all__ = ["render_ar_pbr", "ar_pbr_diagnostics", "clear_ar_pbr_cache"]
