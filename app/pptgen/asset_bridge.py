"""Convert editor/media-pool assets into PPT slide elements."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.pptgen.schema import ElementStyle, SlideElement


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv"}
AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp2", ".wma"}
AR_PBR_SUFFIXES = {".fbx", ".glb", ".gltf", ".obj", ".usd", ".usdz"}
VRM_SUFFIXES = {".vrm"}
MMD_SUFFIXES = {".pmx", ".pmd"}
MMD_PACKAGE_SUFFIX = ".pbx.json"


def asset_kind_for_path(path: str | Path) -> str:
    p = Path(path)
    suffix = p.suffix.casefold()
    if p.name.casefold().endswith(MMD_PACKAGE_SUFFIX):
        return "mmd_actor"
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in VIDEO_SUFFIXES:
        return "video_actor"
    if suffix in AUDIO_SUFFIXES:
        return "audio_actor"
    if suffix in AR_PBR_SUFFIXES:
        return "ar_pbr_actor"
    if suffix in VRM_SUFFIXES:
        return "vrm_actor"
    if suffix in MMD_SUFFIXES:
        return "mmd_actor"
    return "media_actor"


def _default_box(kind: str) -> tuple[float, float]:
    if kind == "typography_actor":
        return 0.58, 0.13
    if kind in {"video_actor", "image"}:
        return 0.54, 0.34
    if kind in {"ar_pbr_actor", "vrm_actor", "mmd_actor"}:
        return 0.34, 0.46
    if kind == "audio_actor":
        return 0.50, 0.12
    return 0.42, 0.26


def _style_for_kind(kind: str) -> ElementStyle:
    if kind == "video_actor":
        return ElementStyle(fill="#101722", stroke="#2F6FED", stroke_width=1.4, color="#EAF2FF", font_size=18)
    if kind in {"ar_pbr_actor", "vrm_actor"}:
        return ElementStyle(fill="#F3F6FA", stroke="#3A8F5A", stroke_width=1.4, color="#182033", font_size=18)
    if kind == "mmd_actor":
        return ElementStyle(fill="#F7F1FF", stroke="#8B5CF6", stroke_width=1.4, color="#182033", font_size=18)
    if kind == "audio_actor":
        return ElementStyle(fill="#FFF7E8", stroke="#D88716", stroke_width=1.2, color="#182033", font_size=16)
    if kind == "typography_actor":
        return ElementStyle(fill=None, stroke=None, stroke_width=0.0, color="#182033", font_size=34, bold=True, align="center")
    return ElementStyle(fill="#F3F6FA", stroke="#2F6FED", stroke_width=1.0, color="#182033", font_size=18)


def slide_element_from_media_asset(
    path: str | Path,
    element_id: str,
    *,
    x: float = 0.18,
    y: float = 0.24,
    w: float | None = None,
    h: float | None = None,
    kind: str | None = None,
    name: str = "",
    source: str = "media_pool",
) -> SlideElement:
    p = Path(path)
    resolved_kind = str(kind or asset_kind_for_path(p))
    default_w, default_h = _default_box(resolved_kind)
    box_w = float(default_w if w is None else w)
    box_h = float(default_h if h is None else h)
    box_x = max(0.0, min(1.0 - box_w, float(x)))
    box_y = max(0.0, min(1.0 - box_h, float(y)))
    label = str(name or p.stem or p.name or resolved_kind.replace("_", " ").title())
    if resolved_kind == "image" and p.exists():
        element = SlideElement.image(element_id, p, x=box_x, y=box_y, w=box_w, h=box_h, kind="image", name=label)
    else:
        element = SlideElement(
            id=element_id,
            kind=resolved_kind,
            name=label,
            source_path=str(p),
            x=box_x,
            y=box_y,
            w=box_w,
            h=box_h,
            style=_style_for_kind(resolved_kind),
        )
    element.metadata.update(
        {
            "source": source,
            "asset_kind": resolved_kind,
            "source_path": str(p),
            "editable_actor": resolved_kind in {"video_actor", "ar_pbr_actor", "vrm_actor", "mmd_actor", "typography_actor"},
        }
    )
    return element


def slide_element_from_typography(
    payload: Any,
    element_id: str,
    *,
    x: float = 0.21,
    y: float = 0.42,
    w: float = 0.58,
    h: float = 0.13,
    source: str = "typography",
) -> SlideElement:
    text = "Typography"
    style_payload: Any = None
    animation_payload: Any = None
    duration_ms = 2000
    if isinstance(payload, dict):
        text = str(payload.get("text") or payload.get("label") or text)
        style_payload = payload.get("style")
        animation_payload = payload.get("animation")
        try:
            duration_ms = int(payload.get("duration_ms") or duration_ms)
        except Exception:
            duration_ms = 2000
    else:
        text = str(getattr(payload, "text", "") or text)
        style_payload = getattr(payload, "style", None)
        animation_payload = getattr(payload, "animation", None)
        try:
            duration_ms = int(getattr(payload, "duration_ms", duration_ms) or duration_ms)
        except Exception:
            duration_ms = 2000

    style = _style_for_kind("typography_actor")
    if style_payload is not None:
        for src_name, dst_name in (
            ("font_family", "font_family"),
            ("font_size", "font_size"),
            ("color", "color"),
            ("alignment", "align"),
            ("line_height", "line_height"),
            ("letter_spacing", "letter_spacing"),
        ):
            value = style_payload.get(src_name) if isinstance(style_payload, dict) else getattr(style_payload, src_name, None)
            if value is not None:
                setattr(style, dst_name, value)
        weight = style_payload.get("font_weight") if isinstance(style_payload, dict) else getattr(style_payload, "font_weight", None)
        if weight is not None:
            try:
                style.bold = int(weight) >= 600
            except Exception:
                pass
    element = SlideElement.text_box(
        element_id,
        text,
        x=max(0.0, min(1.0 - float(w), float(x))),
        y=max(0.0, min(1.0 - float(h), float(y))),
        w=w,
        h=h,
        font_size=int(style.font_size),
        font_family=style.font_family,
        bold=style.bold,
        color=style.color,
        align=style.align,
        line_height=float(style.line_height or 1.2),
        letter_spacing=float(style.letter_spacing or 0.0),
    )
    element.kind = "typography_actor"
    element.name = text[:32] or "Typography"
    element.metadata.update(
        {
            "source": source,
            "asset_kind": "typography_actor",
            "duration_ms": max(1, duration_ms),
            "animation": animation_payload if isinstance(animation_payload, dict) else {},
            "editable_actor": True,
        }
    )
    return element


__all__ = [
    "AR_PBR_SUFFIXES",
    "IMAGE_SUFFIXES",
    "MMD_SUFFIXES",
    "VIDEO_SUFFIXES",
    "VRM_SUFFIXES",
    "asset_kind_for_path",
    "slide_element_from_media_asset",
    "slide_element_from_typography",
]
