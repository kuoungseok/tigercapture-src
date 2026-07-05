"""Transient loading state helpers for Live2D/Spine actor clips."""
from __future__ import annotations

import time
from typing import Any


STATUS_LOADING = "loading"
STATUS_READY = "ready"
STATUS_ERROR = "error"
STATUS_CANCELLED = "cancelled"
STATUS_TIMEOUT = "timeout"


def set_actor_clip_status(
    clip: Any,
    status: str,
    message: str = "",
    *,
    path: str = "",
) -> None:
    if clip is None:
        return
    try:
        setattr(clip, "_editor_load_status", str(status or ""))
        setattr(clip, "_editor_load_message", str(message or ""))
        setattr(clip, "_editor_load_path", str(path or ""))
        setattr(clip, "_editor_load_updated_at", time.time())
    except Exception:
        pass


def actor_clip_status(clip: Any) -> dict[str, Any]:
    if clip is None:
        return {}
    status = str(getattr(clip, "_editor_load_status", "") or "")
    if not status:
        return {}
    return {
        "status": status,
        "message": str(getattr(clip, "_editor_load_message", "") or ""),
        "path": str(getattr(clip, "_editor_load_path", "") or ""),
        "updated_at": float(getattr(clip, "_editor_load_updated_at", 0.0) or 0.0),
    }


def actor_clip_badge(clip: Any) -> tuple[str, str] | None:
    status = actor_clip_status(clip).get("status", "")
    if status == STATUS_LOADING:
        return "LOAD", "#5B45FF"
    if status == STATUS_READY:
        return "OK", "#38C7A0"
    if status == STATUS_ERROR:
        return "ERR", "#FF5A7A"
    if status == STATUS_TIMEOUT:
        return "TIME", "#FFBD59"
    if status == STATUS_CANCELLED:
        return "STOP", "#8A8FA8"
    return None
