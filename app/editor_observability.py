from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


VIDEO_TRACK_HDR_PROBE_ENV = "TIGERCAPTURE_VIDEO_TRACK_HDR_PROBE"
LIVE2D_STARTUP_WARMUP_ENV = "TIGERCAPTURE_LIVE2D_STARTUP_WARMUP"
UX_EVENT_LOG_NAME = "ux_events.jsonl"


def append_ux_event(event: str, **payload) -> None:
    """Best-effort interaction log for hard-to-reproduce editing friction."""
    try:
        from app.paths import runtime_log_dir

        path = runtime_log_dir() / UX_EVENT_LOG_NAME
        row = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "event": str(event or "event"),
        }
        row.update(payload)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def video_track_hdr_probe_enabled() -> bool:
    value = str(os.environ.get(VIDEO_TRACK_HDR_PROBE_ENV, "")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def live2d_startup_warmup_enabled() -> bool:
    value = str(os.environ.get(LIVE2D_STARTUP_WARMUP_ENV, "")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def probe_track_hdr_info(path: Path):
    if not video_track_hdr_probe_enabled():
        return None
    try:
        from app.hdr_probe import probe_hdr

        return probe_hdr(path)
    except Exception:
        return None


__all__ = [
    "VIDEO_TRACK_HDR_PROBE_ENV",
    "LIVE2D_STARTUP_WARMUP_ENV",
    "UX_EVENT_LOG_NAME",
    "append_ux_event",
    "video_track_hdr_probe_enabled",
    "live2d_startup_warmup_enabled",
    "probe_track_hdr_info",
]
