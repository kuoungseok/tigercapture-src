"""Capture-source resolution for BroadcastScene.

This module is intentionally UI-neutral. It turns scene sources such as image,
camera, display capture, and externally supplied frame sources into the
``frames`` mapping consumed by ``composite_broadcast_frame``.
"""
from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

from app.broadcast_scene import (
    BroadcastScene,
    BroadcastSource,
    SOURCE_CAMERA,
    SOURCE_COLOR,
    SOURCE_DISPLAY_CAPTURE,
    SOURCE_FRAME,
    SOURCE_IMAGE,
    SOURCE_INTERNAL_VRM,
    SOURCE_VSEEFACE,
    SOURCE_WINDOW_CAPTURE,
    composite_broadcast_frame,
)


CAPTURE_BACKEND_PLAN_SCHEMA = "tigerstudio.broadcast.capture_backend_plan.v1"
CAPTURE_FRAME_MAP_SCHEMA = "tigerstudio.broadcast.capture_frame_map.v1"
CAPTURE_COMPOSITE_SCHEMA = "tigerstudio.broadcast.capture_composite.v1"


ImageReader = Callable[[str], Any]
ScreenGrabber = Callable[[Mapping[str, int]], Any]
CameraReader = Callable[[int | str], Any]


def broadcast_capture_backend_plan(
    scene: BroadcastScene | Mapping[str, Any] | None = None,
    *,
    dependency_availability: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    """Return capture backend readiness for a scene without opening devices."""
    deps = _dependency_availability(dependency_availability)
    scene_obj = scene if isinstance(scene, BroadcastScene) else BroadcastScene.from_mapping(scene or {})
    rows = [_source_plan(source, deps) for source in scene_obj.sources]
    blocking = [row for row in rows if row.get("required") and not row.get("available")]
    return {
        "schema": CAPTURE_BACKEND_PLAN_SCHEMA,
        "ok": not blocking,
        "scene_id": scene_obj.id,
        "dependencies": deps,
        "sources": rows,
        "missing_required_source_count": len(blocking),
        "supported_source_types": [
            SOURCE_FRAME,
            SOURCE_VSEEFACE,
            SOURCE_INTERNAL_VRM,
            SOURCE_IMAGE,
            SOURCE_CAMERA,
            SOURCE_DISPLAY_CAPTURE,
            SOURCE_WINDOW_CAPTURE,
        ],
        "notes": [
            "Performance Source video remains tracking input and must not be captured directly into Program Output.",
            "Window/display capture can use an explicit region without OBS; title-based window lookup is a UI/platform layer.",
        ],
    }


def resolve_broadcast_frame_map(
    scene: BroadcastScene | Mapping[str, Any],
    *,
    frame_overrides: Mapping[str, Any] | None = None,
    time_ms: int = 0,
    image_reader: ImageReader | None = None,
    screen_grabber: ScreenGrabber | None = None,
    camera_reader: CameraReader | None = None,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Resolve scene capture sources into a frame map for the compositor."""
    scene_obj = scene if isinstance(scene, BroadcastScene) else BroadcastScene.from_mapping(scene)
    frames: dict[str, np.ndarray] = {}
    diagnostics: dict[str, Any] = {
        "schema": CAPTURE_FRAME_MAP_SCHEMA,
        "ok": True,
        "scene_id": scene_obj.id,
        "time_ms": int(time_ms),
        "resolved_source_count": 0,
        "missing_source_count": 0,
        "degraded_source_count": 0,
        "sources": [],
        "warnings": [],
    }
    for key, value in dict(frame_overrides or {}).items():
        arr = _to_rgb_or_rgba(value)
        if arr.size:
            frames[str(key)] = arr

    for source in scene_obj.sources:
        row = _resolve_source(
            source,
            frames,
            image_reader=image_reader,
            screen_grabber=screen_grabber,
            camera_reader=camera_reader,
        )
        diagnostics["sources"].append(row)
        if row.get("resolved"):
            diagnostics["resolved_source_count"] += 1
        elif row.get("degraded"):
            diagnostics["degraded_source_count"] += 1
            diagnostics["warnings"].append(row.get("warning", "source degraded"))
        elif row.get("required"):
            diagnostics["missing_source_count"] += 1
            diagnostics["warnings"].append(row.get("warning", "source missing"))

    diagnostics["ok"] = diagnostics["missing_source_count"] == 0
    return frames, diagnostics


def composite_broadcast_frame_with_captures(
    scene: BroadcastScene | Mapping[str, Any],
    *,
    frame_overrides: Mapping[str, Any] | None = None,
    time_ms: int = 0,
    output_alpha: bool = False,
    image_reader: ImageReader | None = None,
    screen_grabber: ScreenGrabber | None = None,
    camera_reader: CameraReader | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Resolve capture sources, then composite the Program Output frame."""
    frames, capture_diag = resolve_broadcast_frame_map(
        scene,
        frame_overrides=frame_overrides,
        time_ms=time_ms,
        image_reader=image_reader,
        screen_grabber=screen_grabber,
        camera_reader=camera_reader,
    )
    frame, composite_diag = composite_broadcast_frame(scene, frames, output_alpha=output_alpha)
    diagnostics = {
        "schema": CAPTURE_COMPOSITE_SCHEMA,
        "ok": bool(capture_diag.get("ok")) and bool(composite_diag.get("ok", True)),
        "capture": capture_diag,
        "composite": composite_diag,
    }
    return frame, diagnostics


def _source_plan(source: BroadcastSource, deps: Mapping[str, bool]) -> dict[str, Any]:
    settings = source.settings
    if source.type == SOURCE_COLOR:
        return _plan_row(source, "generated", True, required=False)
    if source.type in {SOURCE_FRAME, SOURCE_VSEEFACE, SOURCE_INTERNAL_VRM}:
        return _plan_row(source, "frame_map", True, required=not _source_is_degraded(source))
    if source.type == SOURCE_IMAGE:
        path = _source_path(source)
        return _plan_row(source, "image_file", bool(path), required=True, detail={"path": path})
    if source.type == SOURCE_CAMERA:
        return _plan_row(source, "opencv_camera", bool(deps.get("opencv")), required=True)
    if source.type in {SOURCE_DISPLAY_CAPTURE, SOURCE_WINDOW_CAPTURE}:
        has_region = _capture_region(settings) is not None
        return _plan_row(
            source,
            "screen_region",
            bool(deps.get("mss") and has_region),
            required=True,
            detail={"requires_region": True, "has_region": has_region},
        )
    return _plan_row(source, "unsupported", False, required=True)


def _plan_row(
    source: BroadcastSource,
    backend: str,
    available: bool,
    *,
    required: bool,
    detail: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "source_id": source.id,
        "source_type": source.type,
        "backend": backend,
        "available": bool(available),
        "required": bool(required),
    }
    if detail:
        row["detail"] = dict(detail)
    return row


def _resolve_source(
    source: BroadcastSource,
    frames: dict[str, np.ndarray],
    *,
    image_reader: ImageReader | None,
    screen_grabber: ScreenGrabber | None,
    camera_reader: CameraReader | None,
) -> dict[str, Any]:
    if source.type == SOURCE_COLOR:
        return _resolved_row(source, "generated", resolved=True, required=False)
    if source.id in frames:
        return _resolved_row(source, "frame_map", resolved=True, required=False)
    if source.type in {SOURCE_FRAME, SOURCE_VSEEFACE, SOURCE_INTERNAL_VRM}:
        degraded = _source_is_degraded(source)
        return _resolved_row(
            source,
            "frame_map",
            resolved=False,
            required=not degraded,
            degraded=degraded,
            warning=f"missing frame for source {source.id}",
        )
    if source.type == SOURCE_IMAGE:
        path = _source_path(source)
        if not path:
            return _resolved_row(source, "image_file", resolved=False, required=True, warning="image source missing path")
        frame = _read_image(path, image_reader=image_reader)
        if frame.size:
            frames[source.id] = frame
            return _resolved_row(source, "image_file", resolved=True, required=False)
        return _resolved_row(source, "image_file", resolved=False, required=True, warning=f"image source failed: {path}")
    if source.type == SOURCE_CAMERA:
        frame = _read_camera(source, camera_reader=camera_reader)
        if frame.size:
            frames[source.id] = frame
            return _resolved_row(source, "opencv_camera", resolved=True, required=False)
        return _resolved_row(source, "opencv_camera", resolved=False, required=True, warning="camera source failed")
    if source.type in {SOURCE_DISPLAY_CAPTURE, SOURCE_WINDOW_CAPTURE}:
        region = _capture_region(source.settings)
        if region is None:
            return _resolved_row(source, "screen_region", resolved=False, required=True, warning="capture source missing region")
        frame = _grab_screen(region, screen_grabber=screen_grabber)
        if frame.size:
            frames[source.id] = frame
            return _resolved_row(source, "screen_region", resolved=True, required=False)
        return _resolved_row(source, "screen_region", resolved=False, required=True, warning="screen region capture failed")
    return _resolved_row(source, "unsupported", resolved=False, required=True, warning=f"unsupported source type {source.type}")


def _resolved_row(
    source: BroadcastSource,
    backend: str,
    *,
    resolved: bool,
    required: bool,
    degraded: bool = False,
    warning: str = "",
) -> dict[str, Any]:
    row = {
        "source_id": source.id,
        "source_type": source.type,
        "backend": backend,
        "resolved": bool(resolved),
        "required": bool(required),
        "degraded": bool(degraded),
    }
    if warning:
        row["warning"] = warning
    return row


def _read_image(path: str, *, image_reader: ImageReader | None) -> np.ndarray:
    if image_reader is not None:
        return _to_rgb_or_rgba(image_reader(path))
    try:
        from PIL import Image

        with Image.open(path) as img:
            return np.asarray(img.convert("RGBA"), dtype=np.uint8)
    except Exception:
        pass
    try:
        import cv2  # type: ignore

        bgr = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if bgr is None:
            return np.zeros((0, 0, 3), dtype=np.uint8)
        if bgr.ndim == 3 and bgr.shape[2] == 4:
            return cv2.cvtColor(bgr, cv2.COLOR_BGRA2RGBA)
        if bgr.ndim == 3:
            return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    except Exception:
        pass
    return np.zeros((0, 0, 3), dtype=np.uint8)


def _read_camera(source: BroadcastSource, *, camera_reader: CameraReader | None) -> np.ndarray:
    settings = source.settings
    camera_id: int | str = int(settings.get("device_index", settings.get("camera_index", 0)) or 0)
    if "device_name" in settings:
        camera_id = str(settings.get("device_name") or "")
    if camera_reader is not None:
        return _to_rgb_or_rgba(camera_reader(camera_id))
    try:
        import cv2  # type: ignore

        cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW) if isinstance(camera_id, int) else cv2.VideoCapture(camera_id)
        if not cap or not cap.isOpened():
            return np.zeros((0, 0, 3), dtype=np.uint8)
        try:
            ok, frame = cap.read()
            if not ok or frame is None:
                return np.zeros((0, 0, 3), dtype=np.uint8)
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        finally:
            cap.release()
    except Exception:
        return np.zeros((0, 0, 3), dtype=np.uint8)


def _grab_screen(region: Mapping[str, int], *, screen_grabber: ScreenGrabber | None) -> np.ndarray:
    if screen_grabber is not None:
        return _to_rgb_or_rgba(screen_grabber(region))
    try:
        import mss

        with mss.mss() as sct:
            shot = sct.grab(dict(region))
        arr = np.asarray(shot, dtype=np.uint8)
        if arr.ndim == 3 and arr.shape[2] == 4:
            return arr[:, :, [2, 1, 0, 3]]
    except Exception:
        return np.zeros((0, 0, 3), dtype=np.uint8)
    return np.zeros((0, 0, 3), dtype=np.uint8)


def _source_path(source: BroadcastSource) -> str:
    settings = source.settings
    return str(settings.get("path") or settings.get("file") or settings.get("source_path") or "")


def _capture_region(settings: Mapping[str, Any]) -> dict[str, int] | None:
    region = settings.get("region")
    if not isinstance(region, Mapping):
        return None
    left = int(region.get("left", region.get("x", 0)) or 0)
    top = int(region.get("top", region.get("y", 0)) or 0)
    width = int(region.get("width", 0) or 0)
    height = int(region.get("height", 0) or 0)
    if width <= 0 or height <= 0:
        return None
    return {"left": left, "top": top, "width": width, "height": height}


def _dependency_availability(overrides: Mapping[str, bool] | None = None) -> dict[str, bool]:
    if overrides is not None:
        return {
            "opencv": bool(overrides.get("opencv", False)),
            "mss": bool(overrides.get("mss", False)),
            "pillow": bool(overrides.get("pillow", False)),
        }
    return {
        "opencv": find_spec("cv2") is not None,
        "mss": find_spec("mss") is not None,
        "pillow": find_spec("PIL") is not None,
    }


def _source_is_degraded(source: BroadcastSource) -> bool:
    settings = source.settings
    if settings.get("capture_ready") is False:
        return True
    health = settings.get("capture_health")
    if isinstance(health, Mapping) and health.get("ready") is False:
        return True
    return False


def _to_rgb_or_rgba(value: Any) -> np.ndarray:
    arr = np.asarray(value)
    if arr.ndim != 3 or arr.shape[2] not in {3, 4}:
        return np.zeros((0, 0, 3), dtype=np.uint8)
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return np.ascontiguousarray(arr)
