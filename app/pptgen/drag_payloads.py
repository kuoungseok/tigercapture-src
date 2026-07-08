"""Drag/drop payload helpers for moving editor objects into PPT slides."""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from app.typography import TEXT_CLIP_MIME


PPT_TIMELINE_CLIP_MIME = "application/x-tigercapture-ppt-timeline-clip+json"
PPT_TYPOGRAPHY_MIME = "application/x-tigercapture-ppt-typography+json"


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _to_plain(value: Any) -> Any:
    if value is None:
        return None
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {str(key): _to_plain(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(row) for row in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def timeline_clip_drag_payload(track: Any, clip: Any) -> dict[str, Any]:
    source = getattr(clip, "source_path", None)
    source_path = str(source or "")
    duration = _as_int(
        getattr(clip, "effective_length_ms", None),
        _as_int(getattr(clip, "duration_ms", None), 0),
    )
    if duration <= 0:
        source_in = _as_int(getattr(clip, "source_in_ms", 0))
        source_out = _as_int(getattr(clip, "source_out_ms", 0))
        duration = max(0, source_out - source_in)
    return {
        "schema": "tigercapture.ppt.timeline_clip_drag.v1",
        "kind": "timeline_clip",
        "track_id": _as_int(getattr(track, "id", 0)),
        "clip_id": _as_int(getattr(clip, "id", 0)),
        "source_path": source_path,
        "label": str(getattr(clip, "display_name", "") or Path(source_path).name or "Timeline clip"),
        "timeline_in_ms": _as_int(getattr(clip, "timeline_in_ms", 0)),
        "duration_ms": max(1, duration),
        "source_in_ms": _as_int(getattr(clip, "source_in_ms", 0)),
        "source_out_ms": _as_int(getattr(clip, "effective_source_out_ms", getattr(clip, "source_out_ms", 0))),
    }


def typography_drag_payload(track: Any, actor: Any) -> dict[str, Any]:
    duration = _as_int(getattr(actor, "duration_ms", None), 0)
    if duration <= 0:
        duration = max(1, _as_int(getattr(actor, "end_ms", 0)) - _as_int(getattr(actor, "start_ms", 0)))
    text = str(getattr(actor, "text", "") or "")
    if not text:
        display_text = getattr(actor, "display_text", None)
        if callable(display_text):
            try:
                text = str(display_text() or "")
            except Exception:
                text = ""
        elif display_text is not None:
            text = str(display_text or "")
    if not text:
        text = "Typography"
    return {
        "schema": "tigercapture.ppt.typography_drag.v1",
        "kind": "typography_actor",
        "track_id": _as_int(getattr(track, "id", 0)),
        "clip_id": _as_int(getattr(actor, "id", 0)),
        "text": text,
        "duration_ms": max(1, duration),
        "start_ms": _as_int(getattr(actor, "start_ms", 0)),
        "end_ms": _as_int(getattr(actor, "end_ms", duration)),
        "style": _to_plain(getattr(actor, "style", None)) or {},
        "animation": _to_plain(getattr(actor, "animation", None)) or {},
    }


def set_json_payload(mime: Any, mime_type: str, payload: dict[str, Any]) -> None:
    mime.setData(mime_type, json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))


def payload_from_mime(mime: Any, mime_type: str) -> dict[str, Any] | None:
    try:
        if mime is None or not mime.hasFormat(mime_type):
            return None
        payload = json.loads(bytes(mime.data(mime_type)).decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def timeline_clip_payload_from_mime(mime: Any) -> dict[str, Any] | None:
    return payload_from_mime(mime, PPT_TIMELINE_CLIP_MIME)


def typography_payload_from_mime(mime: Any) -> dict[str, Any] | None:
    payload = payload_from_mime(mime, PPT_TYPOGRAPHY_MIME)
    if payload is not None:
        return payload
    try:
        if mime is not None and mime.hasFormat(TEXT_CLIP_MIME):
            duration_ms = _as_int(bytes(mime.data(TEXT_CLIP_MIME)).decode("utf-8"), 2000)
            return {
                "schema": "tigercapture.ppt.typography_drag.v1",
                "kind": "typography_actor",
                "text": "Typography",
                "duration_ms": max(1, duration_ms),
                "style": {},
                "animation": {},
            }
    except Exception:
        pass
    return None


def has_ppt_drag_payload(mime: Any) -> bool:
    if mime is None:
        return False
    for mime_type in (PPT_TIMELINE_CLIP_MIME, PPT_TYPOGRAPHY_MIME, TEXT_CLIP_MIME):
        try:
            if mime.hasFormat(mime_type):
                return True
        except Exception:
            pass
    return False


__all__ = [
    "PPT_TIMELINE_CLIP_MIME",
    "PPT_TYPOGRAPHY_MIME",
    "has_ppt_drag_payload",
    "payload_from_mime",
    "set_json_payload",
    "timeline_clip_drag_payload",
    "timeline_clip_payload_from_mime",
    "typography_drag_payload",
    "typography_payload_from_mime",
]
