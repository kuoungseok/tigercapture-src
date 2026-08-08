"""Motion Designer MMD adapter using the existing OpenGL MMD painter."""
from __future__ import annotations

from collections import OrderedDict
import json
from pathlib import Path
from typing import Any

from PySide6.QtGui import QImage

from app.motion_designer.mmd_source import evaluate_mmd_frame
from app.motion_designer.schema import MotionComposition, MotionLayer

from .actor_common import actor_qimage


_FRAME_CACHE_CAPACITY = 12
_FRAME_CACHE: OrderedDict[tuple[Any, ...], QImage] = OrderedDict()
_RUNTIME_CAPACITY = 4
_RUNTIMES: OrderedDict[str, "_MMDPacketRuntime"] = OrderedDict()
_DIAGNOSTICS: dict[str, dict[str, Any]] = {}


class _MMDPacketRuntime:
    """Small method-compatible host for project_player_mmd_workflow."""

    def __init__(self) -> None:
        from app.mmd.offscreen_export import MMDOffscreenGLRenderer

        self._mmd_tracks: list[dict[str, Any]] = []
        self._mmd_model_cache: dict[str, object] = {}
        self._mmd_motion_cache: dict[str, object | None] = {}
        self._mmd_physics_cache: dict[Any, object] = {}
        self._mmd_last_frame_by_track: dict[str, float] = {}
        self._mmd_last_diagnostics: dict[str, Any] = {}
        self.renderer = MMDOffscreenGLRenderer()
        self.track_signature = ""

    def set_track(self, track: dict[str, Any]) -> None:
        signature = json.dumps(track, sort_keys=True, ensure_ascii=True, default=str)
        if signature != self.track_signature:
            self._mmd_tracks = [track]
            self._mmd_physics_cache.clear()
            self._mmd_last_frame_by_track.clear()
            self.track_signature = signature

    def _active_mmd_tracks(self, pos_ms: int):
        from app import project_player_mmd_workflow as workflow

        return workflow._active_mmd_tracks(self, pos_ms)

    def _mmd_model_for_path(self, path_text: str):
        from app import project_player_mmd_workflow as workflow

        return workflow._mmd_model_for_path(self, path_text)

    def _mmd_motion_for_path(self, path_text: str):
        from app import project_player_mmd_workflow as workflow

        return workflow._mmd_motion_for_path(self, path_text)

    def _mmd_motion_duration_ms(self, motion) -> int:
        from app import project_player_mmd_workflow as workflow

        return workflow._mmd_motion_duration_ms(motion)

    def _mmd_frame_for_track(self, track: dict, motion, pos_ms: int) -> float:
        from app import project_player_mmd_workflow as workflow

        return workflow._mmd_frame_for_track(self, track, motion, pos_ms)

    def _mmd_physics_backend_for_track(self, *args, **kwargs):
        from app import project_player_mmd_workflow as workflow

        return workflow._mmd_physics_backend_for_track(self, *args, **kwargs)

    def render(self, track: dict[str, Any], time_ms: int, width: int, height: int):
        from app import project_player_mmd_workflow as workflow

        self.set_track(track)
        items = workflow._mmd_overlay_items(self, int(time_ms), animate=True)
        return self.renderer.render_array(items, width, height) if items else None, items


def _file_signature(path_text: str) -> tuple[Any, ...]:
    path = Path(path_text)
    try:
        stat = path.stat()
        return str(path.resolve()), int(stat.st_size), int(stat.st_mtime_ns)
    except OSError:
        return str(path), 0, 0


def _source_signature(layer: MotionLayer) -> tuple[Any, ...]:
    asset = layer.source.params.get("asset") if isinstance(layer.source.params.get("asset"), dict) else {}
    return (
        *_file_signature(str(asset.get("model_path") or layer.source.uri)),
        *_file_signature(str(asset.get("motion_path") or "")),
        str(layer.source.revision or ""),
        json.dumps(layer.source.params, sort_keys=True, ensure_ascii=True, default=str),
    )


def _runtime(layer_id: str) -> _MMDPacketRuntime:
    runtime = _RUNTIMES.get(layer_id)
    if runtime is None:
        runtime = _MMDPacketRuntime()
        _RUNTIMES[layer_id] = runtime
    _RUNTIMES.move_to_end(layer_id)
    while len(_RUNTIMES) > _RUNTIME_CAPACITY:
        _RUNTIMES.popitem(last=False)
    return runtime


def render_mmd(
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
    frame = evaluate_mmd_frame(
        layer, time_ms, composition=composition, composition_time_ms=composition_time_ms,
    )
    playback = params.get("playback") if isinstance(params.get("playback"), dict) else {}
    fps = max(6.0, min(60.0, float(playback.get("preview_cache_fps", 30.0) or 30.0)))
    frame_index = max(0, int(round(frame.sample_time_ms * fps / 1000.0)))
    sample_ms = int(round(frame_index * 1000.0 / fps))
    key = (
        layer.id, _source_signature(layer), int(getattr(composition, "revision", 0) or 0),
        width, height, frame_index,
    )
    cached = _FRAME_CACHE.get(key)
    if cached is not None:
        _FRAME_CACHE.move_to_end(key)
        _DIAGNOSTICS[layer.id] = {
            **dict(_DIAGNOSTICS.get(layer.id) or {}),
            "cache_hit": True,
            "requested_quality": str(quality),
            "canonical_frame_cache": True,
            "frame_cache_size": len(_FRAME_CACHE),
        }
        return cached.copy()

    try:
        runtime = _runtime(layer.id)
        array, items = runtime.render(frame.track, sample_ms, width, height)
        image = actor_qimage(array, width, height)
        visible = bool(
            array is not None
            and getattr(array, "ndim", 0) == 3
            and int(array.shape[2]) >= 4
            and int(array[:, :, 3].max(initial=0)) > 0
        )
        item_diagnostics = dict((items[0] if items else {}).get("diagnostics") or {})
        diagnostics = {
            **frame.diagnostics,
            **item_diagnostics,
            "ok": visible and not image.isNull(),
            "source_adapter": "motion_mmd_existing_opengl_runtime",
            "renderer": "mmd_toon_opengl",
            "quality": str(quality),
            "canonical_frame_cache": True,
            "cache_hit": False,
            "frame_index": frame_index,
            "sample_time_ms": sample_ms,
            "frame_cache_size": len(_FRAME_CACHE) + 1,
            "frame_cache_capacity": _FRAME_CACHE_CAPACITY,
            "runtime_cache_size": len(_RUNTIMES),
            "width": width,
            "height": height,
        }
        if not visible:
            diagnostics["errors"] = ["MMD OpenGL renderer returned no visible frame"]
    except Exception as exc:
        image = actor_qimage(None, width, height)
        diagnostics = {
            **frame.diagnostics,
            "ok": False,
            "source_adapter": "motion_mmd_existing_opengl_runtime",
            "renderer": "mmd_toon_opengl",
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
    _DIAGNOSTICS[layer.id] = diagnostics
    if diagnostics.get("ok"):
        _FRAME_CACHE[key] = image.copy()
        _FRAME_CACHE.move_to_end(key)
        while len(_FRAME_CACHE) > _FRAME_CACHE_CAPACITY:
            _FRAME_CACHE.popitem(last=False)
    return image


def mmd_diagnostics(layer_id: str = "") -> dict[str, Any]:
    if layer_id:
        return dict(_DIAGNOSTICS.get(str(layer_id)) or {})
    return {key: dict(value) for key, value in _DIAGNOSTICS.items()}


def clear_mmd_cache() -> None:
    _FRAME_CACHE.clear()
    _RUNTIMES.clear()


__all__ = ["clear_mmd_cache", "mmd_diagnostics", "render_mmd"]
