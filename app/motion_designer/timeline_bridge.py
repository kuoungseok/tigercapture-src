"""Time mapping and clip edits shared by editor, player, and exporter."""
from __future__ import annotations

from typing import Iterable, Mapping

from .clip import MotionClip
from .schema import MotionComposition, new_motion_id


def normalize_motion_clips(clips: Iterable[MotionClip | Mapping]) -> list[MotionClip]:
    return [item if isinstance(item, MotionClip) else MotionClip.from_dict(item) for item in clips]


def active_motion_clips(clips: Iterable[MotionClip | Mapping], position_ms: int) -> list[MotionClip]:
    position = int(position_ms)
    return sorted((clip for clip in normalize_motion_clips(clips)
                   if clip.enabled and clip.start_ms <= position < clip.end_ms), key=lambda clip: clip.z_index)


def composition_time_ms(clip: MotionClip, composition: MotionComposition, timeline_ms: int) -> float:
    elapsed = max(0.0, (float(timeline_ms) - clip.start_ms) * clip.time_scale) + clip.source_in_ms
    if clip.loop and composition.duration_ms > 0:
        elapsed %= composition.duration_ms
    return max(0.0, min(float(composition.duration_ms), elapsed))


def split_motion_clip(clip: MotionClip, timeline_ms: int) -> tuple[MotionClip, MotionClip]:
    split_at = int(timeline_ms)
    if not clip.start_ms < split_at < clip.end_ms:
        raise ValueError("split point must be inside the Motion Clip")
    left_duration = split_at - clip.start_ms
    right = MotionClip.from_dict(clip.to_dict())
    right.id = new_motion_id("motion_clip")
    right.start_ms = split_at
    right.duration_ms = clip.duration_ms - left_duration
    right.source_in_ms = clip.source_in_ms + int(left_duration * clip.time_scale)
    left = MotionClip.from_dict(clip.to_dict())
    left.duration_ms = left_duration
    return left, right


def duplicate_motion_clip(clip: MotionClip, *, start_ms: int | None = None) -> MotionClip:
    copied = MotionClip.from_dict(clip.to_dict())
    copied.id = new_motion_id("motion_clip")
    copied.name = f"{clip.name} Copy"
    copied.start_ms = clip.end_ms if start_ms is None else max(0, int(start_ms))
    return copied


def motion_timeline_extent(clips: Iterable[MotionClip | Mapping]) -> int:
    return max((clip.end_ms for clip in normalize_motion_clips(clips)), default=0)
