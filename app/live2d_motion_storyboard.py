"""Live2D motion storyboard helpers.

The first video-mocap slice only generated actor transform keyframes.  This
module uses the model's own motion3 clips more directly: it reads every motion
from the model3 file and rebuilds one Live2D actor clip into multiple timeline
clips aligned to video cuts/clip ranges.
"""
from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class Live2DMotionChoice:
    group: str
    index: int
    label: str
    file: str = ""


def list_live2d_motions(model_path: str | Path) -> list[Live2DMotionChoice]:
    path = str(model_path or "")
    if not path:
        return []
    try:
        from app.live2d.compat import normalize_live2d_model_path

        path = normalize_live2d_model_path(path) or path
    except Exception:
        pass
    base = os.path.dirname(path)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return []
    motions = data.get("FileReferences", {}).get("Motions", {})
    if not isinstance(motions, dict):
        return []
    out: list[Live2DMotionChoice] = []
    for group, items in motions.items():
        if not isinstance(items, list):
            continue
        for idx, item in enumerate(items):
            file_ref = item.get("File", "") if isinstance(item, dict) else ""
            if not isinstance(file_ref, str) or not file_ref:
                continue
            if not file_ref.lower().replace("\\", "/").endswith(".motion3.json"):
                continue
            motion_path = os.path.normpath(os.path.join(base, file_ref))
            if not os.path.exists(motion_path):
                continue
            label = os.path.basename(file_ref).replace(".motion3.json", "")
            out.append(
                Live2DMotionChoice(
                    group=str(group or ""),
                    index=int(idx),
                    label=f"{group}/{label}" if group else label,
                    file=file_ref,
                )
            )
    # Put obvious idle/base motions first, then keep authored order.  The
    # storyboard still uses every motion by cycling through this list.
    out.sort(key=lambda m: (0 if "idle" in m.label.casefold() else 1, m.group, m.index))
    return out


def _video_clip_ranges(video_clips: Iterable[Any]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for clip in video_clips or []:
        start = int(getattr(clip, "timeline_in_ms", 0) or 0)
        end = int(getattr(clip, "timeline_out_ms", 0) or 0)
        if end <= start:
            duration = int(getattr(clip, "effective_length_ms", 0) or getattr(clip, "duration_ms", 0) or 0)
            end = start + duration
        if end > start:
            ranges.append((start, end))
    ranges.sort()
    return ranges


def _split_longest_until_motion_coverage(
    ranges: list[tuple[int, int]],
    target_count: int,
    *,
    min_segment_ms: int = 1100,
) -> list[tuple[int, int]]:
    if target_count <= 0:
        return ranges
    out = list(ranges)
    while len(out) < target_count:
        idx = max(range(len(out)), key=lambda i: out[i][1] - out[i][0], default=-1)
        if idx < 0:
            break
        start, end = out[idx]
        if end - start < min_segment_ms * 2:
            break
        mid = start + (end - start) // 2
        out[idx:idx + 1] = [(start, mid), (mid, end)]
    out.sort()
    return out


def build_storyboard_ranges(
    *,
    video_clips: Iterable[Any] = (),
    fallback_start_ms: int = 0,
    fallback_duration_ms: int = 3000,
    motion_count: int = 0,
) -> list[tuple[int, int]]:
    ranges = _video_clip_ranges(video_clips)
    if not ranges:
        start = max(0, int(fallback_start_ms or 0))
        duration = max(1, int(fallback_duration_ms or 0))
        ranges = [(start, start + duration)]
    return _split_longest_until_motion_coverage(ranges, int(motion_count or 0))


def _keyframe_time_ms(key: Any) -> int:
    if isinstance(key, Mapping):
        return int(key.get("time_ms", 0) or 0)
    return int(getattr(key, "time_ms", 0) or 0)


def _copy_keyframe_with_time(key: Any, time_ms: int) -> Any:
    nk = copy.deepcopy(key)
    if isinstance(nk, dict):
        nk["time_ms"] = max(0, int(time_ms))
    else:
        try:
            nk.time_ms = max(0, int(time_ms))
        except Exception:
            pass
    return nk


def _slice_keyframes(kfs: Iterable[Any], src_clip: Any, new_start_ms: int, new_duration_ms: int) -> list[Any]:
    out = []
    src_start = int(getattr(src_clip, "start_ms", 0) or 0)
    rel_start = int(new_start_ms) - src_start
    rel_end = rel_start + int(new_duration_ms)
    for key in kfs or []:
        t = _keyframe_time_ms(key)
        if rel_start <= t <= rel_end:
            out.append(_copy_keyframe_with_time(key, t - rel_start))
    return out


def _slice_parameter_keyframes(
    tracks: Mapping[str, Any] | None,
    src_clip: Any,
    new_start_ms: int,
    new_duration_ms: int,
) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {}
    if not isinstance(tracks, Mapping):
        return out
    for raw_param_id, raw_keys in tracks.items():
        param_id = str(raw_param_id or "").strip()
        if not param_id:
            continue
        if isinstance(raw_keys, Mapping):
            keys = raw_keys.get("keyframes") or raw_keys.get("keys") or []
        else:
            keys = raw_keys or []
        sliced = _slice_keyframes(keys, src_clip, new_start_ms, new_duration_ms)
        if sliced:
            out[param_id] = sliced
    return out


def _clone_clip_for_range(
    source_clip: Any,
    *,
    start_ms: int,
    end_ms: int,
    motion: Live2DMotionChoice,
    ordinal: int,
    total: int,
) -> Any:
    clip = copy.deepcopy(source_clip)
    clip.start_ms = int(start_ms)
    clip.duration_ms = max(1, int(end_ms) - int(start_ms))
    clip.motion_group = motion.group
    clip.motion_idx = int(motion.index)
    clip.loop = False
    clip.kf_pos_x = _slice_keyframes(getattr(source_clip, "kf_pos_x", []), source_clip, start_ms, clip.duration_ms)
    clip.kf_pos_y = _slice_keyframes(getattr(source_clip, "kf_pos_y", []), source_clip, start_ms, clip.duration_ms)
    clip.kf_scale = _slice_keyframes(getattr(source_clip, "kf_scale", []), source_clip, start_ms, clip.duration_ms)
    clip.kf_opacity = _slice_keyframes(getattr(source_clip, "kf_opacity", []), source_clip, start_ms, clip.duration_ms)
    if hasattr(clip, "parameter_keyframes"):
        clip.parameter_keyframes = _slice_parameter_keyframes(
            getattr(source_clip, "parameter_keyframes", {}),
            source_clip,
            start_ms,
            clip.duration_ms,
        )
    if hasattr(clip, "mocap_parameter_keyframes"):
        clip.mocap_parameter_keyframes = _slice_parameter_keyframes(
            getattr(source_clip, "mocap_parameter_keyframes", {}),
            source_clip,
            start_ms,
            clip.duration_ms,
        )
    clip.motion_storyboard_payload = {
        "kind": "live2d_motion_storyboard",
        "motion_label": motion.label,
        "motion_group": motion.group,
        "motion_idx": int(motion.index),
        "ordinal": int(ordinal),
        "total": int(total),
        "source": "video_cuts",
    }
    try:
        clip.reset()
    except Exception:
        pass
    return clip


def apply_motion_storyboard_to_track(
    actor_track: Any,
    source_clip: Any,
    *,
    video_clips: Iterable[Any] = (),
) -> dict[str, Any]:
    if actor_track is None or source_clip is None:
        return {"ok": False, "reason": "missing_track_or_clip"}
    model_path = str(getattr(source_clip, "model_path", "") or "")
    motions = list_live2d_motions(model_path)
    if not motions:
        return {"ok": False, "reason": "no_live2d_motions", "model_path": model_path}
    ranges = build_storyboard_ranges(
        video_clips=video_clips,
        fallback_start_ms=int(getattr(source_clip, "start_ms", 0) or 0),
        fallback_duration_ms=int(getattr(source_clip, "duration_ms", 0) or 0),
        motion_count=len(motions),
    )
    if not ranges:
        return {"ok": False, "reason": "no_ranges", "motion_count": len(motions)}

    new_clips = [
        _clone_clip_for_range(
            source_clip,
            start_ms=start,
            end_ms=end,
            motion=motions[idx % len(motions)],
            ordinal=idx + 1,
            total=len(ranges),
        )
        for idx, (start, end) in enumerate(ranges)
        if end > start
    ]
    if not new_clips:
        return {"ok": False, "reason": "no_storyboard_clips"}

    existing = list(getattr(actor_track, "clips", []) or [])
    replaced = 0
    kept = []
    for clip in existing:
        if clip is source_clip:
            replaced += 1
            continue
        kept.append(clip)
    actor_track.clips = sorted(kept + new_clips, key=lambda c: int(getattr(c, "start_ms", 0) or 0))
    used_labels = [motions[idx % len(motions)].label for idx in range(len(new_clips))]
    return {
        "ok": True,
        "replaced": replaced,
        "created": len(new_clips),
        "motion_count": len(motions),
        "unique_motions_used": len(set(used_labels)),
        "motions_used": used_labels,
        "range_count": len(ranges),
    }
