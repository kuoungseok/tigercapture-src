"""Quality summaries for VTuber face-motion frames."""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


MOTION_QUALITY_SCHEMA = "tigerstudio.vtuber.motion_quality.v1"
MOTION_CHANNELS = ("yaw_deg", "pitch_deg", "roll_deg", "shoulder_roll_deg", "mouth_open", "blink_l", "blink_r", "confidence")


def summarize_motion_frames(frames: Iterable[Any]) -> dict[str, Any]:
    data = list(frames)
    if not data:
        return {
            "schema": MOTION_QUALITY_SCHEMA,
            "ok": False,
            "frame_count": 0,
            "duration_ms": 0,
            "source_counts": {},
            "channels": {},
            "checks": {
                "head_motion": False,
                "mouth_motion": False,
                "blink_motion": False,
                "confidence_ok": False,
            },
        }

    times = [int(_frame_value(frame, "time_ms", 0)) for frame in data]
    source_counts = Counter(str(_frame_value(frame, "source", "")) for frame in data)
    channels = {name: _channel_stats(_frame_value(frame, name, 0.0) for frame in data) for name in MOTION_CHANNELS}
    head_range = max(
        channels["yaw_deg"]["range"],
        channels["pitch_deg"]["range"],
        channels["roll_deg"]["range"],
    )
    blink_range = max(channels["blink_l"]["range"], channels["blink_r"]["range"])
    return {
        "schema": MOTION_QUALITY_SCHEMA,
        "ok": True,
        "frame_count": len(data),
        "duration_ms": max(times) - min(times) if times else 0,
        "time_min_ms": min(times) if times else 0,
        "time_max_ms": max(times) if times else 0,
        "source_counts": dict(sorted(source_counts.items())),
        "channels": channels,
        "checks": {
            "head_motion": head_range >= 1.0,
            "mouth_motion": channels["mouth_open"]["max"] >= 0.08,
            "blink_motion": blink_range >= 0.08 or max(channels["blink_l"]["max"], channels["blink_r"]["max"]) >= 0.25,
            "confidence_ok": channels["confidence"]["mean"] >= 0.5,
        },
    }


def representative_frame_indices(frame_count: int, slots: int = 3) -> list[int]:
    count = max(0, int(frame_count))
    slot_count = max(1, int(slots))
    if count <= 0:
        return []
    if slot_count == 1 or count == 1:
        return [0]
    return sorted({round((count - 1) * i / (slot_count - 1)) for i in range(slot_count)})


def _channel_stats(values: Iterable[Any]) -> dict[str, float]:
    data = [float(value) for value in values]
    if not data:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "range": 0.0}
    low = min(data)
    high = max(data)
    return {
        "min": low,
        "max": high,
        "mean": sum(data) / len(data),
        "range": high - low,
    }


def _frame_value(frame: Any, name: str, default: Any) -> Any:
    if isinstance(frame, dict):
        return frame.get(name, default)
    return getattr(frame, name, default)
