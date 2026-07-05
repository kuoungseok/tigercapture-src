"""OBS-like live scene model and CPU compositor.

This is the small broadcast core needed before a VSeeFace bridge: it gives the
app a stable scene/source contract, alpha/chroma compositing, and diagnostics
without depending on Qt, OBS, or a specific capture backend.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np


SOURCE_FRAME = "frame"
SOURCE_COLOR = "color"
SOURCE_VSEEFACE = "vseeface"
SOURCE_INTERNAL_VRM = "internal_vrm"
SOURCE_WINDOW_CAPTURE = "window_capture"
SOURCE_DISPLAY_CAPTURE = "display_capture"
SOURCE_CAMERA = "camera"
SOURCE_IMAGE = "image"

SETTING_SUPPRESS_BLACK_FRAME = "suppress_black_frame"

FIT_STRETCH = "stretch"
FIT_CONTAIN = "contain"
FIT_COVER = "cover"
FIT_ORIGINAL = "original"


@dataclass
class BroadcastCanvas:
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    background: tuple[int, int, int, int] = (0, 0, 0, 255)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "BroadcastCanvas":
        data = payload or {}
        return cls(
            width=max(1, int(data.get("width", 1920) or 1920)),
            height=max(1, int(data.get("height", 1080) or 1080)),
            fps=max(1.0, float(data.get("fps", 30.0) or 30.0)),
            background=_rgba(data.get("background"), (0, 0, 0, 255)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": int(self.width),
            "height": int(self.height),
            "fps": float(self.fps),
            "background": list(self.background),
        }


@dataclass
class BroadcastTransform:
    x: float = 0.0
    y: float = 0.0
    width: float | None = None
    height: float | None = None
    opacity: float = 1.0
    fit: str = FIT_STRETCH
    visible: bool = True
    rotation: float = 0.0

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "BroadcastTransform":
        data = payload or {}
        return cls(
            x=float(data.get("x", 0.0) or 0.0),
            y=float(data.get("y", 0.0) or 0.0),
            width=_optional_float(data.get("width")),
            height=_optional_float(data.get("height")),
            opacity=max(0.0, min(1.0, float(data.get("opacity", 1.0) if data.get("opacity") is not None else 1.0))),
            fit=str(data.get("fit") or FIT_STRETCH),
            visible=bool(data.get("visible", True)),
            rotation=float(data.get("rotation", 0.0) or 0.0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": float(self.x),
            "y": float(self.y),
            "width": None if self.width is None else float(self.width),
            "height": None if self.height is None else float(self.height),
            "opacity": float(self.opacity),
            "fit": str(self.fit),
            "visible": bool(self.visible),
            "rotation": float(self.rotation),
        }


@dataclass
class BroadcastSource:
    id: str
    type: str = SOURCE_FRAME
    name: str = ""
    z_index: int = 0
    transform: BroadcastTransform = field(default_factory=BroadcastTransform)
    chroma_key: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "BroadcastSource":
        source_id = str(payload.get("id") or payload.get("source_id") or "")
        if not source_id:
            raise ValueError("broadcast source requires id")
        return cls(
            id=source_id,
            type=str(payload.get("type") or SOURCE_FRAME),
            name=str(payload.get("name") or source_id),
            z_index=int(payload.get("z_index", payload.get("order", 0)) or 0),
            transform=BroadcastTransform.from_mapping(payload.get("transform") if isinstance(payload.get("transform"), Mapping) else {}),
            chroma_key=dict(payload.get("chroma_key") if isinstance(payload.get("chroma_key"), Mapping) else {}),
            settings=dict(payload.get("settings") if isinstance(payload.get("settings"), Mapping) else {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "z_index": int(self.z_index),
            "transform": self.transform.to_dict(),
            "chroma_key": dict(self.chroma_key),
            "settings": dict(self.settings),
        }


@dataclass
class BroadcastAudioChannel:
    id: str
    name: str = ""
    source_id: str = ""
    volume: float = 1.0
    muted: bool = False
    monitor: bool = False

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "BroadcastAudioChannel":
        channel_id = str(payload.get("id") or payload.get("channel_id") or "")
        if not channel_id:
            raise ValueError("broadcast audio channel requires id")
        return cls(
            id=channel_id,
            name=str(payload.get("name") or channel_id),
            source_id=str(payload.get("source_id") or ""),
            volume=max(0.0, min(2.0, float(payload.get("volume", 1.0) if payload.get("volume") is not None else 1.0))),
            muted=bool(payload.get("muted", False)),
            monitor=bool(payload.get("monitor", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source_id": self.source_id,
            "volume": float(self.volume),
            "muted": bool(self.muted),
            "monitor": bool(self.monitor),
        }


@dataclass
class BroadcastScene:
    id: str = "scene_001"
    name: str = "Scene"
    canvas: BroadcastCanvas = field(default_factory=BroadcastCanvas)
    sources: list[BroadcastSource] = field(default_factory=list)
    audio: list[BroadcastAudioChannel] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "BroadcastScene":
        data = payload or {}
        sources = [
            BroadcastSource.from_mapping(item)
            for item in data.get("sources", [])
            if isinstance(item, Mapping)
        ]
        audio = [
            BroadcastAudioChannel.from_mapping(item)
            for item in data.get("audio", [])
            if isinstance(item, Mapping)
        ]
        return cls(
            id=str(data.get("id") or "scene_001"),
            name=str(data.get("name") or "Scene"),
            canvas=BroadcastCanvas.from_mapping(data.get("canvas") if isinstance(data.get("canvas"), Mapping) else {}),
            sources=sources,
            audio=audio,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "canvas": self.canvas.to_dict(),
            "sources": [source.to_dict() for source in self.sources],
            "audio": [channel.to_dict() for channel in self.audio],
        }


def create_vseeface_bridge_scene(
    *,
    width: int = 1920,
    height: int = 1080,
    fps: float = 30.0,
) -> BroadcastScene:
    """Return the default scene layout we need for a VSeeFace sidecar."""
    return BroadcastScene(
        id="vseeface_bridge_scene",
        name="VSeeFace Bridge",
        canvas=BroadcastCanvas(width=width, height=height, fps=fps, background=(0, 0, 0, 255)),
        sources=[
            BroadcastSource(
                id="background",
                type=SOURCE_COLOR,
                name="Background",
                z_index=0,
                settings={"color": [0, 0, 0, 255]},
            ),
            BroadcastSource(
                id="vseeface",
                type=SOURCE_VSEEFACE,
                name="VSeeFace Avatar",
                z_index=10,
                transform=BroadcastTransform(x=0, y=0, width=width, height=height, fit=FIT_CONTAIN),
                chroma_key={"enabled": False},
                settings={SETTING_SUPPRESS_BLACK_FRAME: True},
            ),
        ],
        audio=[
            BroadcastAudioChannel(id="mic", name="Mic/Aux", volume=1.0),
            BroadcastAudioChannel(id="desktop", name="Desktop Audio", volume=1.0),
        ],
    )


def composite_broadcast_frame(
    scene: BroadcastScene | Mapping[str, Any],
    frames: Mapping[str, Any] | None = None,
    *,
    output_alpha: bool = False,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Composite one live scene frame.

    `frames` maps source ids to RGB/RGBA numpy arrays. Capture backends can fill
    that mapping from Spout, window capture, camera, or decoded media.
    """
    scene_obj = scene if isinstance(scene, BroadcastScene) else BroadcastScene.from_mapping(scene)
    frame_map = frames or {}
    canvas = scene_obj.canvas
    out = _solid_rgba(canvas.height, canvas.width, canvas.background)
    diagnostics: dict[str, Any] = {
        "ok": True,
        "canvas": canvas.to_dict(),
        "source_count": len(scene_obj.sources),
        "rendered_source_count": 0,
        "skipped_source_count": 0,
        "warnings": [],
        "sources": [],
    }

    for source in sorted(scene_obj.sources, key=lambda item: (item.z_index, item.id)):
        row = _composite_source(out, source, frame_map)
        diagnostics["sources"].append(row)
        if row.get("rendered"):
            diagnostics["rendered_source_count"] += 1
        else:
            diagnostics["skipped_source_count"] += 1
            if row.get("warning"):
                diagnostics["warnings"].append(row["warning"])

    if output_alpha:
        return out, diagnostics
    return out[:, :, :3].copy(), diagnostics


def broadcast_scene_diagnostics(
    scene: BroadcastScene | Mapping[str, Any],
    available_frames: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate scene/source readiness without compositing pixels."""
    scene_obj = scene if isinstance(scene, BroadcastScene) else BroadcastScene.from_mapping(scene)
    available = set((available_frames or {}).keys())
    missing = []
    degraded = []
    for source in scene_obj.sources:
        if source.type == SOURCE_INTERNAL_VRM and bool(source.settings.get("program_output", False)):
            continue
        if source.type in {SOURCE_FRAME, SOURCE_VSEEFACE, SOURCE_INTERNAL_VRM, SOURCE_WINDOW_CAPTURE, SOURCE_DISPLAY_CAPTURE, SOURCE_CAMERA, SOURCE_IMAGE}:
            if source.id not in available:
                if _missing_frame_is_degraded(source):
                    degraded.append(source.id)
                else:
                    missing.append(source.id)
    return {
        "ok": not missing,
        "scene_id": scene_obj.id,
        "canvas": scene_obj.canvas.to_dict(),
        "source_count": len(scene_obj.sources),
        "audio_channel_count": len(scene_obj.audio),
        "missing_frame_sources": missing,
        "degraded_frame_sources": degraded,
        "has_vseeface_source": any(source.type == SOURCE_VSEEFACE for source in scene_obj.sources),
    }


def _composite_source(out: np.ndarray, source: BroadcastSource, frames: Mapping[str, Any]) -> dict[str, Any]:
    transform = source.transform
    row: dict[str, Any] = {
        "id": source.id,
        "type": source.type,
        "visible": bool(transform.visible),
        "rendered": False,
    }
    if not transform.visible or transform.opacity <= 0.0:
        row["warning"] = "source hidden"
        return row
    if abs(float(transform.rotation)) > 1e-6:
        row["warning"] = "source rotation is not implemented in CPU broadcast compositor"
        return row

    if source.type == SOURCE_COLOR:
        color = _rgba(source.settings.get("color"), (0, 0, 0, 255))
        src = _solid_rgba(out.shape[0], out.shape[1], color)
        dest = (0, 0, out.shape[1], out.shape[0])
    else:
        raw = frames.get(source.id)
        if raw is None:
            row["warning"] = f"missing frame for source {source.id}"
            return row
        src = _frame_to_rgba(raw)
        if src.size == 0:
            row["warning"] = f"empty frame for source {source.id}"
            return row
        if bool(source.settings.get(SETTING_SUPPRESS_BLACK_FRAME, False)) and _is_black_frame(src):
            row["warning"] = f"suppressed black frame for source {source.id}"
            row["suppressed_black_frame"] = True
            return row
        src = _apply_chroma_key(src, source.chroma_key)
        src, dest = _fit_source_to_canvas(src, transform, out.shape[1], out.shape[0])

    if src.size == 0:
        row["warning"] = f"source {source.id} has no visible pixels"
        return row
    _alpha_blend(out, src, dest, opacity=transform.opacity)
    row.update({
        "rendered": True,
        "bounds": [int(dest[0]), int(dest[1]), int(dest[2]), int(dest[3])],
    })
    return row


def _fit_source_to_canvas(
    src: np.ndarray,
    transform: BroadcastTransform,
    canvas_w: int,
    canvas_h: int,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    src_h, src_w = src.shape[:2]
    target_w = int(round(transform.width if transform.width is not None else src_w))
    target_h = int(round(transform.height if transform.height is not None else src_h))
    target_w = max(1, target_w)
    target_h = max(1, target_h)

    fit = str(transform.fit or FIT_STRETCH)
    if fit == FIT_ORIGINAL:
        resize_w, resize_h = src_w, src_h
    elif fit in {FIT_CONTAIN, FIT_COVER}:
        scale = min(target_w / max(src_w, 1), target_h / max(src_h, 1))
        if fit == FIT_COVER:
            scale = max(target_w / max(src_w, 1), target_h / max(src_h, 1))
        resize_w = max(1, int(round(src_w * scale)))
        resize_h = max(1, int(round(src_h * scale)))
    else:
        resize_w, resize_h = target_w, target_h

    resized = _resize_rgba(src, resize_w, resize_h)
    if fit == FIT_COVER and (resize_w != target_w or resize_h != target_h):
        ox = max(0, (resize_w - target_w) // 2)
        oy = max(0, (resize_h - target_h) // 2)
        resized = resized[oy:oy + target_h, ox:ox + target_w]
        resize_h, resize_w = resized.shape[:2]

    x = int(round(transform.x))
    y = int(round(transform.y))
    if fit == FIT_CONTAIN:
        x += max(0, (target_w - resize_w) // 2)
        y += max(0, (target_h - resize_h) // 2)
    return resized, (x, y, x + resize_w, y + resize_h)


def _alpha_blend(
    dst: np.ndarray,
    src: np.ndarray,
    dest: tuple[int, int, int, int],
    *,
    opacity: float,
) -> None:
    x0, y0, x1, y1 = dest
    canvas_h, canvas_w = dst.shape[:2]
    clip_x0 = max(0, min(canvas_w, x0))
    clip_y0 = max(0, min(canvas_h, y0))
    clip_x1 = max(0, min(canvas_w, x1))
    clip_y1 = max(0, min(canvas_h, y1))
    if clip_x1 <= clip_x0 or clip_y1 <= clip_y0:
        return
    src_x0 = clip_x0 - x0
    src_y0 = clip_y0 - y0
    src_x1 = src_x0 + (clip_x1 - clip_x0)
    src_y1 = src_y0 + (clip_y1 - clip_y0)
    src_roi = src[src_y0:src_y1, src_x0:src_x1].astype(np.float32)
    dst_roi = dst[clip_y0:clip_y1, clip_x0:clip_x1].astype(np.float32)
    alpha = (src_roi[:, :, 3:4] / 255.0) * max(0.0, min(1.0, float(opacity)))
    out_rgb = src_roi[:, :, :3] * alpha + dst_roi[:, :, :3] * (1.0 - alpha)
    out_alpha = src_roi[:, :, 3:4] * max(0.0, min(1.0, float(opacity))) + dst_roi[:, :, 3:4] * (1.0 - alpha)
    dst[clip_y0:clip_y1, clip_x0:clip_x1, :3] = np.clip(out_rgb, 0, 255).astype(np.uint8)
    dst[clip_y0:clip_y1, clip_x0:clip_x1, 3:4] = np.clip(out_alpha, 0, 255).astype(np.uint8)


def _apply_chroma_key(src: np.ndarray, chroma: Mapping[str, Any] | None) -> np.ndarray:
    if not isinstance(chroma, Mapping) or not bool(chroma.get("enabled", False)):
        return src
    try:
        from app.chroma_key import ChromaKeyParams

        params = ChromaKeyParams.from_dict(dict(chroma))
        keyed, alpha = params.apply(src[:, :, :3])
        out = src.copy()
        out[:, :, :3] = keyed
        out[:, :, 3] = np.minimum(out[:, :, 3], alpha)
        return out
    except Exception:
        return src


def _frame_to_rgba(frame: Any) -> np.ndarray:
    arr = np.asarray(frame)
    if arr.ndim != 3 or arr.shape[2] not in {3, 4}:
        return np.zeros((0, 0, 4), dtype=np.uint8)
    arr = arr.astype(np.uint8, copy=False)
    if arr.shape[2] == 4:
        return np.ascontiguousarray(arr)
    alpha = np.full(arr.shape[:2] + (1,), 255, dtype=np.uint8)
    return np.ascontiguousarray(np.concatenate([arr, alpha], axis=2))


def _is_black_frame(src: np.ndarray) -> bool:
    if src.ndim != 3 or src.shape[2] < 3 or src.size == 0:
        return False
    rgb = src[:, :, :3]
    if src.shape[2] >= 4:
        visible = src[:, :, 3] > 0
        if not bool(np.any(visible)):
            return False
        rgb = rgb[visible]
    return int(np.max(rgb)) <= 3


def _missing_frame_is_degraded(source: BroadcastSource) -> bool:
    settings = source.settings
    if settings.get("capture_ready") is False:
        return True
    health = settings.get("capture_health")
    if isinstance(health, Mapping) and health.get("ready") is False:
        return True
    return False


def _resize_rgba(src: np.ndarray, width: int, height: int) -> np.ndarray:
    width = max(1, int(width))
    height = max(1, int(height))
    if src.shape[1] == width and src.shape[0] == height:
        return np.ascontiguousarray(src)
    try:
        import cv2

        return np.ascontiguousarray(cv2.resize(src, (width, height), interpolation=cv2.INTER_LINEAR))
    except Exception:
        y_idx = np.clip((np.arange(height) * (src.shape[0] / height)).astype(int), 0, src.shape[0] - 1)
        x_idx = np.clip((np.arange(width) * (src.shape[1] / width)).astype(int), 0, src.shape[1] - 1)
        return np.ascontiguousarray(src[y_idx][:, x_idx])


def _solid_rgba(height: int, width: int, color: tuple[int, int, int, int]) -> np.ndarray:
    out = np.zeros((max(1, int(height)), max(1, int(width)), 4), dtype=np.uint8)
    out[:, :] = np.array(color, dtype=np.uint8)
    return out


def _rgba(value: Any, fallback: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    if isinstance(value, str):
        text = value.strip().lstrip("#")
        if len(text) in {6, 8}:
            try:
                rgb = [int(text[idx:idx + 2], 16) for idx in range(0, 6, 2)]
                alpha = int(text[6:8], 16) if len(text) == 8 else 255
                return _clamp_rgba((*rgb, alpha))
            except Exception:
                return fallback
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        alpha = value[3] if len(value) >= 4 else 255
        return _clamp_rgba((value[0], value[1], value[2], alpha))
    return fallback


def _clamp_rgba(value: tuple[Any, Any, Any, Any]) -> tuple[int, int, int, int]:
    return tuple(max(0, min(255, int(round(float(item))))) for item in value)  # type: ignore[return-value]


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None
