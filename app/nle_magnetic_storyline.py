"""Final Cut-style magnetic storyline helpers.

This is not a clone of Final Cut Pro's full Magnetic Timeline.  It provides a
small, deterministic primary-storyline contract: detect visible gaps on video
tracks, plan gap-closing moves that preserve clip order, and report why a track
cannot be safely magnetized.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any


MAGNETIC_STORYLINE_SCHEMA = "tigerstudio.nle.magnetic_storyline.v1"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _clip_id(clip: Any, index: int = 0) -> int:
    return _int(getattr(clip, "id", index), index)


def _track_id(track: Any, index: int = 0) -> int:
    return _int(getattr(track, "id", index), index)


def _clip_bounds(clip: Any) -> tuple[int, int]:
    start = _int(getattr(clip, "timeline_in_ms", 0), 0)
    explicit_end = _int(getattr(clip, "timeline_out_ms", -1), -1)
    if explicit_end > start:
        return start, explicit_end
    source_in = _int(getattr(clip, "source_in_ms", 0), 0)
    source_out = _int(
        getattr(clip, "effective_source_out_ms", getattr(clip, "source_out_ms", 0)),
        0,
    )
    if source_out > source_in:
        return start, start + max(0, source_out - source_in)
    duration = _int(getattr(clip, "duration_ms", getattr(clip, "source_duration_ms", 0)), 0)
    return start, start + max(0, duration)


def _sorted_clips(track: Any) -> list[Any]:
    return sorted(
        list(getattr(track, "clips", []) or []),
        key=lambda clip: (_clip_bounds(clip)[0], _clip_id(clip)),
    )


def _target_tracks(tracks: Sequence[Any], track_id: int | None = None) -> list[Any]:
    if track_id is None:
        return list(tracks or [])
    wanted = _int(track_id, -1)
    return [track for track in tracks or [] if _track_id(track, -1) == wanted]


def build_magnetic_storyline_status(
    tracks: Sequence[Any],
    *,
    track_id: int | None = None,
    min_gap_ms: int = 1,
) -> dict[str, Any]:
    threshold = max(1, _int(min_gap_ms, 1))
    rows: list[dict[str, Any]] = []
    total_gaps = 0
    total_overlaps = 0
    total_clips = 0
    for track_index, track in enumerate(_target_tracks(tracks, track_id)):
        tid = _track_id(track, track_index)
        clips = _sorted_clips(track)
        gaps: list[dict[str, int]] = []
        overlaps: list[dict[str, int]] = []
        cursor = 0
        for clip_index, clip in enumerate(clips):
            start, end = _clip_bounds(clip)
            cid = _clip_id(clip, clip_index)
            if clip_index == 0:
                cursor = end
                continue
            if start - cursor >= threshold:
                gaps.append(
                    {
                        "after_ms": cursor,
                        "before_ms": start,
                        "duration_ms": start - cursor,
                        "clip_id": cid,
                    }
                )
            elif start < cursor:
                overlaps.append(
                    {
                        "start_ms": start,
                        "previous_end_ms": cursor,
                        "duration_ms": cursor - start,
                        "clip_id": cid,
                    }
                )
            cursor = max(cursor, end)
        total_gaps += len(gaps)
        total_overlaps += len(overlaps)
        total_clips += len(clips)
        rows.append(
            {
                "track_id": tid,
                "locked": bool(getattr(track, "locked", False)),
                "clip_count": len(clips),
                "gap_count": len(gaps),
                "overlap_count": len(overlaps),
                "gaps": gaps,
                "overlaps": overlaps,
                "magnetic_ready": bool(clips and not gaps and not overlaps),
            }
        )
    return {
        "schema": MAGNETIC_STORYLINE_SCHEMA,
        "track_count": len(rows),
        "clip_count": total_clips,
        "gap_count": total_gaps,
        "overlap_count": total_overlaps,
        "tracks": rows,
        "min_gap_ms": threshold,
        "ready": bool(rows and total_gaps == 0 and total_overlaps == 0),
    }


def build_magnetic_storyline_plan(
    tracks: Sequence[Any],
    *,
    track_id: int | None = None,
    min_gap_ms: int = 1,
    pull_first_to_zero: bool = False,
) -> dict[str, Any]:
    threshold = max(1, _int(min_gap_ms, 1))
    track_rows: list[dict[str, Any]] = []
    moves: list[dict[str, int]] = []
    warnings: list[str] = []
    for track_index, track in enumerate(_target_tracks(tracks, track_id)):
        tid = _track_id(track, track_index)
        clips = _sorted_clips(track)
        locked = bool(getattr(track, "locked", False))
        if locked:
            warnings.append(f"track {tid} is locked")
            track_rows.append(
                {
                    "track_id": tid,
                    "locked": True,
                    "clip_count": len(clips),
                    "move_count": 0,
                    "moves": [],
                }
            )
            continue
        cursor = 0
        row_moves: list[dict[str, int]] = []
        for clip_index, clip in enumerate(clips):
            start, end = _clip_bounds(clip)
            length = max(0, end - start)
            if length <= 0:
                warnings.append(f"clip {_clip_id(clip, clip_index)} on track {tid} has no duration")
                continue
            target = start
            if clip_index == 0 and pull_first_to_zero:
                target = 0
            elif clip_index > 0 and start - cursor >= threshold:
                target = cursor
            if target != start:
                move = {
                    "track_id": tid,
                    "clip_id": _clip_id(clip, clip_index),
                    "from_ms": start,
                    "to_ms": max(0, target),
                    "delta_ms": max(0, target) - start,
                }
                row_moves.append(move)
                moves.append(move)
                start = max(0, target)
                end = start + length
            cursor = max(cursor, end)
        track_rows.append(
            {
                "track_id": tid,
                "locked": False,
                "clip_count": len(clips),
                "move_count": len(row_moves),
                "moves": row_moves,
            }
        )
    return {
        "schema": "tigerstudio.nle.magnetic_storyline.plan.v1",
        "track_count": len(track_rows),
        "move_count": len(moves),
        "tracks": track_rows,
        "moves": moves,
        "warnings": warnings,
        "min_gap_ms": threshold,
        "pull_first_to_zero": bool(pull_first_to_zero),
    }


def magnetic_storyline_contract_evidence(*, action_ids: Sequence[str] | None = None) -> dict[str, Any]:
    required = {
        "timeline.magnetic_storyline.status",
        "timeline.magnetic_storyline.apply",
        "timeline.close_all_gaps",
        "timeline.play_clip_range",
    }
    available = {str(action_id) for action_id in (action_ids or []) if str(action_id or "").strip()}
    return {
        "schema": "tigerstudio.nle.magnetic_storyline.evidence.v1",
        "required_actions": sorted(required),
        "available_actions": sorted(required & available),
        "ok": required <= available,
    }
