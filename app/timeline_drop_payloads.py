"""Payload parsers for timeline drag/drop MIME data."""
from __future__ import annotations

import json
from typing import Any

from app.effect_cards import FADE_MIME_TYPE, SPEED_MIME_TYPE, ZOOM_MIME_TYPE
from app.typography import TEXT_CLIP_MIME
from app.video_editor_preset_cards import (
    EDITOR_PRESET_MIME_TYPE,
    EFFECT_PRESET_MIME_TYPE,
    TITLE_PRESET_MIME_TYPE,
    TRANSITION_MIME_TYPE,
)


def mime_text(mime: Any, mime_type: str) -> str:
    try:
        return bytes(mime.data(mime_type)).decode("utf-8")
    except Exception:
        return ""


def mime_json(mime: Any, mime_type: str) -> dict[str, Any] | None:
    try:
        value = json.loads(mime_text(mime, mime_type))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def fade_duration_from_mime(mime: Any, *, default_ms: int) -> int:
    try:
        return int(mime_text(mime, FADE_MIME_TYPE))
    except Exception:
        return int(default_ms)


def text_clip_duration_from_mime(mime: Any, *, default_ms: int = 2000) -> int:
    try:
        return int(mime_text(mime, TEXT_CLIP_MIME))
    except Exception:
        return int(default_ms)


def zoom_duration_from_mime(mime: Any, *, default_ms: int) -> int:
    try:
        return int(mime_text(mime, ZOOM_MIME_TYPE))
    except Exception:
        return int(default_ms)


def speed_payload_from_mime(
    mime: Any,
    *,
    default_speed: float,
    default_duration_ms: int,
) -> dict[str, Any]:
    try:
        parts = mime_text(mime, SPEED_MIME_TYPE).split("|")
        return {
            "speed": float(parts[0]),
            "duration_ms": int(parts[1]),
            "frame_blend": bool(int(parts[2])) if len(parts) > 2 else False,
            "blend_mode": parts[3] if len(parts) > 3 else "linear",
        }
    except Exception:
        return {
            "speed": float(default_speed),
            "duration_ms": int(default_duration_ms),
            "frame_blend": False,
            "blend_mode": "linear",
        }


def transition_payload_from_mime(mime: Any) -> dict[str, Any]:
    raw = mime_json(mime, TRANSITION_MIME_TYPE) or {}
    ttype = str(raw.get("type", "dissolve") or "dissolve")
    try:
        duration_ms = int(raw.get("ms", 500) or 500)
    except Exception:
        duration_ms = 500
    return {
        "type": ttype,
        "duration_ms": duration_ms,
        "raw": raw,
    }


def title_preset_from_mime(mime: Any) -> dict[str, Any] | None:
    return mime_json(mime, TITLE_PRESET_MIME_TYPE)


def effect_preset_from_mime(mime: Any) -> dict[str, Any] | None:
    return mime_json(mime, EFFECT_PRESET_MIME_TYPE)


def editor_preset_from_mime(mime: Any) -> dict[str, Any] | None:
    return mime_json(mime, EDITOR_PRESET_MIME_TYPE)
