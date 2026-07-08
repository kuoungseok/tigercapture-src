"""Conservative multicam workflow contracts for NLE readiness.

This is not a full Premiere/Resolve multicam switcher UI.  It provides the
stable data model that the editor UI, Python actions, QA, and export handoff can
share without exposing private editor methods.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


MULTICAM_SCHEMA = "tigerstudio.nle.multicam.v1"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _clip_start(clip: Mapping[str, Any]) -> int:
    return _int(clip.get("timeline_in_ms", clip.get("offset_ms", 0)), 0)


def _clip_end(clip: Mapping[str, Any]) -> int:
    explicit = _int(clip.get("timeline_out_ms", clip.get("end_ms", 0)), 0)
    if explicit > 0:
        return explicit
    return _clip_start(clip) + max(0, _int(clip.get("duration_ms"), 0))


def _has_sync_value(row: Mapping[str, Any], key: str) -> bool:
    if key not in row:
        return False
    value = row.get(key)
    return value is not None and str(value).strip() != ""


def _angle_id(track: Mapping[str, Any], clip: Mapping[str, Any], index: int) -> str:
    raw = (
        clip.get("camera_id")
        or clip.get("angle")
        or track.get("camera_id")
        or track.get("angle")
        or clip.get("source_path")
        or clip.get("name")
        or track.get("name")
        or track.get("id")
        or index
    )
    text = _text(raw, f"angle_{index + 1}")
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in text)
    return safe[:64] or f"angle_{index + 1}"


def _snapshot_video_clips(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track_index, track in enumerate(list(snapshot.get("video_tracks") or [])):
        if not isinstance(track, Mapping):
            continue
        for clip_index, clip in enumerate(list(track.get("clips") or [])):
            if not isinstance(clip, Mapping):
                continue
            start = _clip_start(clip)
            end = _clip_end(clip)
            if end <= start:
                continue
            row = dict(clip)
            row["track_id"] = _int(track.get("id", track_index + 1), track_index + 1)
            row["track_index"] = _int(track.get("index", track_index), track_index)
            row["clip_index"] = clip_index
            row["timeline_in_ms"] = start
            row["timeline_out_ms"] = end
            row["angle_id"] = _angle_id(track, clip, len(rows))
            rows.append(row)
    return rows


def _merge_ranges(ranges: Sequence[Mapping[str, Any]]) -> list[dict[str, int]]:
    ordered = sorted(
        (
            {
                "start_ms": max(0, _int(row.get("start_ms"), 0)),
                "end_ms": max(0, _int(row.get("end_ms"), 0)),
            }
            for row in ranges
        ),
        key=lambda row: (row["start_ms"], row["end_ms"]),
    )
    merged: list[dict[str, int]] = []
    for row in ordered:
        if row["end_ms"] <= row["start_ms"]:
            continue
        if not merged or row["start_ms"] > merged[-1]["end_ms"]:
            merged.append(dict(row))
            continue
        merged[-1]["end_ms"] = max(merged[-1]["end_ms"], row["end_ms"])
    return merged


def _range_gaps(ranges: Sequence[Mapping[str, Any]], *, start_ms: int, end_ms: int) -> list[dict[str, int]]:
    gaps: list[dict[str, int]] = []
    cursor = max(0, _int(start_ms, 0))
    limit = max(cursor, _int(end_ms, cursor))
    for row in _merge_ranges(ranges):
        start = max(cursor, _int(row.get("start_ms"), 0))
        end = min(limit, _int(row.get("end_ms"), 0))
        if start > cursor:
            gaps.append({"start_ms": cursor, "end_ms": start, "duration_ms": start - cursor})
        cursor = max(cursor, end)
    if cursor < limit:
        gaps.append({"start_ms": cursor, "end_ms": limit, "duration_ms": limit - cursor})
    return gaps


def build_multicam_groups(
    snapshot: Mapping[str, Any] | None,
    *,
    stored_groups: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return candidate multicam groups from snapshot clips and stored groups."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    clips = _snapshot_video_clips(snapshot)
    by_angle: dict[str, list[dict[str, Any]]] = {}
    for clip in clips:
        by_angle.setdefault(str(clip.get("angle_id") or ""), []).append(clip)
    angles: list[dict[str, Any]] = []
    for angle_index, (angle_id, angle_clips) in enumerate(sorted(by_angle.items())):
        if not angle_id:
            continue
        starts = [_int(row.get("timeline_in_ms"), 0) for row in angle_clips]
        ends = [_int(row.get("timeline_out_ms"), 0) for row in angle_clips]
        sources = sorted({_text(row.get("source_path")) for row in angle_clips if _text(row.get("source_path"))})
        track_ids = sorted({_int(row.get("track_id"), 0) for row in angle_clips if _int(row.get("track_id"), 0) > 0})
        angles.append(
            {
                "id": angle_id,
                "index": angle_index,
                "name": angle_id,
                "track_ids": track_ids,
                "source_paths": sources[:12],
                "clip_count": len(angle_clips),
                "first_ms": min(starts, default=0),
                "last_ms": max(ends, default=0),
            }
        )

    group_start = min((_int(row.get("timeline_in_ms"), 0) for row in clips), default=0)
    group_end = max((_int(row.get("timeline_out_ms"), 0) for row in clips), default=0)
    generated: list[dict[str, Any]] = []
    if len(angles) >= 2:
        generated.append(
            {
                "id": "multicam_auto_1",
                "name": "Auto Multicam Group",
                "source": "snapshot",
                "angle_count": len(angles),
                "clip_count": len(clips),
                "start_ms": group_start,
                "end_ms": group_end,
                "duration_ms": max(0, group_end - group_start),
                "angles": angles,
            }
        )

    stored: list[dict[str, Any]] = []
    for group in list(stored_groups or []):
        if not isinstance(group, Mapping):
            continue
        row = dict(group)
        if not row.get("id"):
            row["id"] = f"multicam_group_{len(stored) + 1}"
        row.setdefault("source", "project")
        stored.append(row)

    groups = stored or generated
    return {
        "schema": MULTICAM_SCHEMA,
        "group_count": len(groups),
        "groups": groups,
        "angle_count": max((_int(group.get("angle_count"), len(group.get("angles") or [])) for group in groups), default=0),
        "clip_count": len(clips),
        "ready": bool(groups and max((_int(group.get("angle_count"), 0) for group in groups), default=0) >= 2),
    }


def build_multicam_angle_bins(
    snapshot: Mapping[str, Any] | None,
    *,
    group_id: str = "",
    stored_groups: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return UI-ready multicam angle bins with coverage and gap diagnostics."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    groups_payload = build_multicam_groups(snapshot, stored_groups=stored_groups)
    groups = list(groups_payload.get("groups") or [])
    wanted = _text(group_id)
    group = next((row for row in groups if str(row.get("id") or "") == wanted), groups[0] if groups else {})
    clips = _snapshot_video_clips(snapshot)
    by_angle: dict[str, list[dict[str, Any]]] = {}
    for clip in clips:
        by_angle.setdefault(str(clip.get("angle_id") or ""), []).append(clip)

    group_start = _int(group.get("start_ms"), min((_int(row.get("timeline_in_ms"), 0) for row in clips), default=0))
    group_end = _int(group.get("end_ms"), max((_int(row.get("timeline_out_ms"), 0) for row in clips), default=0))
    if group_end <= group_start:
        group_start = min((_int(row.get("timeline_in_ms"), 0) for row in clips), default=0)
        group_end = max((_int(row.get("timeline_out_ms"), 0) for row in clips), default=0)
    group_duration = max(0, group_end - group_start)
    sync = build_multicam_sync_plan(snapshot, group_id=str(group.get("id") or wanted or ""))
    sync_by_angle = {str(row.get("angle_id") or ""): row for row in list(sync.get("angle_sync") or []) if isinstance(row, Mapping)}

    angle_rows = [row for row in list(group.get("angles") or []) if isinstance(row, Mapping)]
    if not angle_rows:
        for index, angle_id in enumerate(sorted(by_angle)):
            angle_rows.append({"id": angle_id, "name": angle_id, "index": index})

    bins: list[dict[str, Any]] = []
    for index, angle in enumerate(angle_rows):
        angle_id = str(angle.get("id") or angle.get("angle_id") or "")
        angle_clips = sorted(by_angle.get(angle_id) or [], key=lambda row: (_int(row.get("timeline_in_ms"), 0), _int(row.get("timeline_out_ms"), 0)))
        coverage = _merge_ranges(
            [
                {
                    "start_ms": _int(row.get("timeline_in_ms"), 0),
                    "end_ms": _int(row.get("timeline_out_ms"), 0),
                }
                for row in angle_clips
            ]
        )
        coverage_ms = sum(max(0, _int(row.get("end_ms"), 0) - _int(row.get("start_ms"), 0)) for row in coverage)
        gaps = _range_gaps(coverage, start_ms=group_start, end_ms=group_end)
        gap_ms = sum(_int(row.get("duration_ms"), 0) for row in gaps)
        sync_row = sync_by_angle.get(angle_id, {})
        sources = sorted({_text(row.get("source_path")) for row in angle_clips if _text(row.get("source_path"))})
        track_ids = sorted({_int(row.get("track_id"), 0) for row in angle_clips if _int(row.get("track_id"), 0) > 0})
        bins.append(
            {
                "angle_id": angle_id,
                "index": _int(angle.get("index"), index),
                "name": str(angle.get("name") or angle_id),
                "track_ids": track_ids,
                "source_paths": sources[:12],
                "clip_count": len(angle_clips),
                "first_ms": _int(coverage[0].get("start_ms"), 0) if coverage else 0,
                "last_ms": _int(coverage[-1].get("end_ms"), 0) if coverage else 0,
                "coverage": coverage,
                "coverage_ms": coverage_ms,
                "coverage_ratio": round((coverage_ms / group_duration), 4) if group_duration else 0.0,
                "gaps": gaps,
                "gap_count": len(gaps),
                "gap_ms": gap_ms,
                "sync_offset_ms": _int(sync_row.get("offset_ms"), 0),
                "sync_method": str(sync_row.get("sync_method") or "timeline"),
                "timecode_ready": str(sync_row.get("sync_method") or "") == "timecode",
                "audio_marker_ready": str(sync_row.get("sync_method") or "") == "audio_marker",
                "ready": bool(angle_clips and coverage_ms > 0),
                "health": "ready" if angle_clips and not gaps else ("has_gaps" if angle_clips else "empty"),
            }
        )

    sync_methods = sorted({str(row.get("sync_method") or "") for row in bins if str(row.get("sync_method") or "")})
    max_gap_count = max((_int(row.get("gap_count"), 0) for row in bins), default=0)
    return {
        "schema": MULTICAM_SCHEMA,
        "kind": "multicam_angle_bins",
        "group_id": str(group.get("id") or wanted or ""),
        "ready": bool(len(bins) >= 2 and all(bool(row.get("ready")) for row in bins)),
        "angle_count": len(bins),
        "group_range": {
            "start_ms": group_start,
            "end_ms": group_end,
            "duration_ms": group_duration,
        },
        "angle_bins": bins,
        "summary": {
            "total_clip_count": sum(_int(row.get("clip_count"), 0) for row in bins),
            "max_gap_count": max_gap_count,
            "angles_with_gaps": sum(1 for row in bins if _int(row.get("gap_count"), 0) > 0),
            "sync_methods": sync_methods,
        },
        "commands": {
            "create_group_enabled": bool(groups_payload.get("ready")),
            "sync_enabled": bool(sync.get("ready")),
            "open_switcher_enabled": bool(len(bins) >= 2),
            "export_handoff_enabled": bool(len(bins) >= 2 and any(bool(row.get("ready")) for row in bins)),
        },
    }


def build_multicam_switch_plan(
    snapshot: Mapping[str, Any] | None,
    *,
    group_id: str = "",
    strategy: str = "round_robin",
    max_segments: int = 240,
) -> dict[str, Any]:
    """Build a deterministic switch plan for preview/export handoff."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    groups_payload = build_multicam_groups(snapshot)
    groups = list(groups_payload.get("groups") or [])
    wanted = _text(group_id)
    group = next((row for row in groups if str(row.get("id") or "") == wanted), groups[0] if groups else {})
    clips = _snapshot_video_clips(snapshot)
    angles = [str(row.get("id") or "") for row in list(group.get("angles") or []) if str(row.get("id") or "")]
    if not angles:
        angles = sorted({str(row.get("angle_id") or "") for row in clips if str(row.get("angle_id") or "")})
    boundaries = sorted(
        {
            _int(row.get("timeline_in_ms"), 0)
            for row in clips
        }
        | {
            _int(row.get("timeline_out_ms"), 0)
            for row in clips
        }
    )
    boundaries = [value for value in boundaries if value >= 0]
    segments: list[dict[str, Any]] = []
    normalized_strategy = _text(strategy, "round_robin").lower()
    if len(boundaries) >= 2 and angles:
        for index, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
            if end <= start:
                continue
            active = [
                row
                for row in clips
                if _int(row.get("timeline_in_ms"), 0) <= start < _int(row.get("timeline_out_ms"), 0)
            ]
            if not active:
                continue
            if normalized_strategy in {"first", "a_cam", "a-cam"}:
                chosen_angle = angles[0]
            elif normalized_strategy in {"coverage", "longest"}:
                chosen = max(active, key=lambda row: _int(row.get("timeline_out_ms"), 0) - start)
                chosen_angle = str(chosen.get("angle_id") or angles[0])
            else:
                chosen_angle = angles[index % len(angles)]
                if not any(str(row.get("angle_id") or "") == chosen_angle for row in active):
                    chosen_angle = str(active[0].get("angle_id") or angles[0])
            chosen_clip = next((row for row in active if str(row.get("angle_id") or "") == chosen_angle), active[0])
            segments.append(
                {
                    "index": len(segments),
                    "timeline_in_ms": start,
                    "timeline_out_ms": end,
                    "angle_id": str(chosen_clip.get("angle_id") or chosen_angle),
                    "track_id": _int(chosen_clip.get("track_id"), 0),
                    "clip_id": _int(chosen_clip.get("id"), _int(chosen_clip.get("clip_index"), 0)),
                    "source_path": _text(chosen_clip.get("source_path")),
                    "source_in_ms": _int(chosen_clip.get("source_in_ms"), 0) + max(0, start - _int(chosen_clip.get("timeline_in_ms"), 0)),
                    "source_out_ms": _int(chosen_clip.get("source_in_ms"), 0) + max(0, end - _int(chosen_clip.get("timeline_in_ms"), 0)),
                }
            )
            if len(segments) >= max(1, _int(max_segments, 240)):
                break
    return {
        "schema": MULTICAM_SCHEMA,
        "group_id": str(group.get("id") or wanted or ""),
        "strategy": normalized_strategy,
        "angle_count": len(angles),
        "switch_count": len(segments),
        "segments": segments,
        "ready_for_export_handoff": bool(len(angles) >= 2 and segments),
    }


def build_multicam_sync_plan(
    snapshot: Mapping[str, Any] | None,
    *,
    group_id: str = "",
    strategy: str = "hybrid",
) -> dict[str, Any]:
    """Return angle sync offsets for timeline/timecode/audio-marker workflows.

    This is intentionally a planning contract, not media analysis.  If clips
    carry timecode or audio sync metadata, the plan uses it; otherwise it falls
    back to the current timeline placement so generated QA and user projects can
    still produce deterministic evidence.
    """

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    groups_payload = build_multicam_groups(snapshot)
    groups = list(groups_payload.get("groups") or [])
    wanted = _text(group_id)
    group = next((row for row in groups if str(row.get("id") or "") == wanted), groups[0] if groups else {})
    clips = _snapshot_video_clips(snapshot)
    by_angle: dict[str, list[dict[str, Any]]] = {}
    for clip in clips:
        by_angle.setdefault(str(clip.get("angle_id") or ""), []).append(clip)
    angles = [str(row.get("id") or "") for row in list(group.get("angles") or []) if str(row.get("id") or "")]
    if not angles:
        angles = sorted(by_angle)
    normalized_strategy = _text(strategy, "hybrid").lower()
    rows: list[dict[str, Any]] = []
    for angle in angles:
        angle_clips = sorted(by_angle.get(angle) or [], key=lambda row: _int(row.get("timeline_in_ms"), 0))
        first = angle_clips[0] if angle_clips else {}
        timeline_anchor = _int(first.get("timeline_in_ms"), 0)
        timecode_keys = ("timecode_ms", "source_timecode_ms", "capture_start_ms", "recorded_start_ms")
        has_timecode = any(_has_sync_value(first, key) for key in timecode_keys)
        timecode_anchor = next((_int(first.get(key), 0) for key in timecode_keys if _has_sync_value(first, key)), timeline_anchor)
        waveform_keys = (
            "waveform_sync_peak_ms",
            "waveform_peak_ms",
            "audio_waveform_peak_ms",
            "transient_peak_ms",
            "audio_fingerprint_anchor_ms",
        )
        has_waveform = any(_has_sync_value(first, key) for key in waveform_keys)
        waveform_anchor = next(
            (_int(first.get(key), 0) for key in waveform_keys if _has_sync_value(first, key)),
            timeline_anchor,
        )
        audio_marker_keys = ("audio_sync_offset_ms", "sync_offset_ms", "slate_offset_ms", "clap_offset_ms")
        has_audio_marker = any(_has_sync_value(first, key) for key in audio_marker_keys)
        audio_anchor = timeline_anchor + next((_int(first.get(key), 0) for key in audio_marker_keys if _has_sync_value(first, key)), 0)
        if normalized_strategy in {"timecode", "tc"} and has_timecode:
            anchor = timecode_anchor
            method = "timecode"
        elif normalized_strategy in {"waveform", "audio_waveform", "fingerprint"} and has_waveform:
            anchor = waveform_anchor
            method = "waveform"
        elif normalized_strategy in {"audio", "audio_marker", "slate", "clap"} and has_audio_marker:
            anchor = audio_anchor
            method = "audio_marker"
        elif normalized_strategy == "hybrid" and has_timecode:
            anchor = timecode_anchor
            method = "timecode"
        elif normalized_strategy == "hybrid" and has_waveform:
            anchor = waveform_anchor
            method = "waveform"
        elif normalized_strategy == "hybrid" and has_audio_marker:
            anchor = audio_anchor
            method = "audio_marker"
        else:
            anchor = timeline_anchor
            method = "timeline"
        rows.append(
            {
                "angle_id": angle,
                "clip_count": len(angle_clips),
                "track_ids": sorted({_int(row.get("track_id"), 0) for row in angle_clips if _int(row.get("track_id"), 0) > 0}),
                "timeline_anchor_ms": timeline_anchor,
                "timecode_anchor_ms": timecode_anchor if has_timecode else None,
                "waveform_anchor_ms": waveform_anchor if has_waveform else None,
                "audio_anchor_ms": audio_anchor if has_audio_marker else None,
                "chosen_anchor_ms": anchor,
                "sync_method": method,
                "waveform_available": has_waveform,
            }
        )
    reference = min((_int(row.get("chosen_anchor_ms"), 0) for row in rows), default=0)
    for row in rows:
        row["reference_ms"] = reference
        row["offset_ms"] = reference - _int(row.get("chosen_anchor_ms"), 0)
        row["needs_move"] = bool(row["offset_ms"])
    methods = sorted({str(row.get("sync_method") or "") for row in rows if str(row.get("sync_method") or "")})
    warnings: list[str] = []
    if len(rows) < 2:
        warnings.append("at least two angles are required")
    if methods == ["timeline"]:
        warnings.append("no timecode/waveform/audio-marker metadata found; using current timeline placement")
    return {
        "schema": MULTICAM_SCHEMA,
        "kind": "multicam_sync_plan",
        "group_id": str(group.get("id") or wanted or ""),
        "strategy": normalized_strategy,
        "angle_count": len(rows),
        "sync_methods": methods,
        "reference_ms": reference,
        "max_abs_offset_ms": max((abs(_int(row.get("offset_ms"), 0)) for row in rows), default=0),
        "angle_sync": rows,
        "warnings": warnings,
        "ready": bool(len(rows) >= 2),
    }


def build_multicam_waveform_sync_board(
    snapshot: Mapping[str, Any] | None,
    *,
    group_id: str = "",
    strategy: str = "waveform",
) -> dict[str, Any]:
    """Return a UI-ready waveform/fingerprint sync review board.

    This consumes already extracted waveform/transient metadata. It does not run
    heavy media analysis on the UI path, so real waveform extraction can remain
    a background media/proxy job.
    """

    sync = build_multicam_sync_plan(snapshot, group_id=group_id, strategy=strategy)
    rows: list[dict[str, Any]] = []
    missing = 0
    for index, row in enumerate(list(sync.get("angle_sync") or [])):
        if not isinstance(row, Mapping):
            continue
        method = str(row.get("sync_method") or "timeline")
        waveform_available = bool(row.get("waveform_available"))
        if not waveform_available:
            missing += 1
        confidence = 0.9 if method == "waveform" else (0.72 if waveform_available else 0.48)
        rows.append(
            {
                "angle_id": str(row.get("angle_id") or ""),
                "index": index,
                "waveform_available": waveform_available,
                "waveform_anchor_ms": row.get("waveform_anchor_ms"),
                "chosen_anchor_ms": _int(row.get("chosen_anchor_ms"), 0),
                "offset_ms": _int(row.get("offset_ms"), 0),
                "needs_move": bool(row.get("needs_move")),
                "sync_method": method,
                "confidence": round(confidence, 3),
                "tone": "ok" if method == "waveform" else "warning",
                "recommended_action": "accept" if method == "waveform" else "extract_waveform",
            }
        )
    ready = bool(rows and len(rows) >= 2 and missing == 0)
    return {
        "schema": MULTICAM_SCHEMA,
        "kind": "multicam_waveform_sync_board",
        "ready": ready,
        "group_id": str(sync.get("group_id") or group_id or ""),
        "strategy": str(sync.get("strategy") or strategy),
        "summary": {
            "angle_count": len(rows),
            "waveform_ready_count": sum(1 for row in rows if bool(row.get("waveform_available"))),
            "missing_waveform_count": missing,
            "average_confidence": round(sum(float(row.get("confidence") or 0.0) for row in rows) / len(rows), 3) if rows else 0.0,
        },
        "rows": rows,
        "warnings": ["waveform_metadata_missing"] if missing else [],
        "commands": {
            "accept_offsets_enabled": ready,
            "extract_waveforms_enabled": missing > 0,
            "open_sync_quality_enabled": True,
            "fallback_timeline_sync_enabled": True,
        },
        "readiness": {
            "waveform_sync_board_ready": ready,
            "has_waveform_rows": bool(rows),
            "requires_waveform_extraction": missing > 0,
        },
    }


def build_multicam_export_handoff(
    snapshot: Mapping[str, Any] | None,
    *,
    group_id: str = "",
    switches: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return flattened multicam edit decisions for export or timeline bake."""

    plan = build_multicam_switch_plan(snapshot, group_id=group_id)
    rows = [dict(row) for row in (switches or []) if isinstance(row, Mapping)]
    if not rows:
        rows = [dict(row) for row in list(plan.get("segments") or []) if isinstance(row, Mapping)]
    rows.sort(key=lambda row: (_int(row.get("timeline_in_ms"), 0), _int(row.get("timeline_out_ms"), 0)))
    return {
        "schema": MULTICAM_SCHEMA,
        "group_id": _text(group_id, str(plan.get("group_id") or "multicam_auto_1")),
        "kind": "multicam_export_handoff",
        "decision_count": len(rows),
        "decisions": rows,
        "ready": bool(rows),
        "notes": [
            "Handoff is a deterministic flatten contract; full live multicam switcher UI remains a separate product task."
        ],
    }


def build_multicam_switcher_workbench(
    snapshot: Mapping[str, Any] | None,
    *,
    group_id: str = "",
    switches: Sequence[Mapping[str, Any]] | None = None,
    playhead_ms: int = 0,
    strategy: str = "round_robin",
) -> dict[str, Any]:
    """Return UI-ready live-switcher state for multicam panels."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    groups_payload = build_multicam_groups(snapshot)
    sync = build_multicam_sync_plan(snapshot, group_id=group_id)
    plan = build_multicam_switch_plan(snapshot, group_id=group_id, strategy=strategy)
    handoff = build_multicam_export_handoff(snapshot, group_id=group_id, switches=switches)
    playhead = max(0, _int(playhead_ms, 0))
    switch_rows = [dict(row) for row in list(switches or []) if isinstance(row, Mapping)]
    planned_segments = [dict(row) for row in list(plan.get("segments") or []) if isinstance(row, Mapping)]
    active_angle = ""
    if switch_rows:
        ordered = sorted(switch_rows, key=lambda row: _int(row.get("timeline_in_ms"), 0))
        for row in ordered:
            if _int(row.get("timeline_in_ms"), 0) <= playhead:
                active_angle = str(row.get("angle_id") or active_angle)
    if not active_angle:
        for segment in planned_segments:
            if _int(segment.get("timeline_in_ms"), 0) <= playhead < _int(segment.get("timeline_out_ms"), 0):
                active_angle = str(segment.get("angle_id") or "")
                break
    sync_by_angle = {str(row.get("angle_id") or ""): row for row in list(sync.get("angle_sync") or []) if isinstance(row, Mapping)}
    group = next((row for row in list(groups_payload.get("groups") or []) if str(row.get("id") or "") == str(plan.get("group_id") or "")), {})
    tiles: list[dict[str, Any]] = []
    for angle in list(group.get("angles") or []):
        if not isinstance(angle, Mapping):
            continue
        angle_id = str(angle.get("id") or "")
        sync_row = sync_by_angle.get(angle_id, {})
        coverage_now = _int(angle.get("first_ms"), 0) <= playhead < _int(angle.get("last_ms"), 0)
        tiles.append(
            {
                "angle_id": angle_id,
                "name": str(angle.get("name") or angle_id),
                "active": angle_id == active_angle,
                "armed": coverage_now,
                "track_ids": list(angle.get("track_ids") or []),
                "clip_count": _int(angle.get("clip_count"), 0),
                "first_ms": _int(angle.get("first_ms"), 0),
                "last_ms": _int(angle.get("last_ms"), 0),
                "sync_offset_ms": _int(sync_row.get("offset_ms"), 0),
                "sync_method": str(sync_row.get("sync_method") or "timeline"),
                "preview_label": f"{angle_id} · {_int(angle.get('clip_count'), 0)} clips",
                "health": "ready" if coverage_now else "no_current_coverage",
            }
        )
    return {
        "schema": MULTICAM_SCHEMA,
        "kind": "multicam_switcher_workbench",
        "group_id": str(plan.get("group_id") or group_id or ""),
        "playhead_ms": playhead,
        "ready": bool(tiles and plan.get("ready_for_export_handoff")),
        "active_angle_id": active_angle,
        "angle_tiles": tiles,
        "sync_plan": sync,
        "switch_plan_summary": {
            "strategy": str(plan.get("strategy") or strategy),
            "switch_count": _int(plan.get("switch_count"), 0),
            "ready_for_export_handoff": bool(plan.get("ready_for_export_handoff")),
        },
        "export_handoff_summary": {
            "ready": bool(handoff.get("ready")),
            "decision_count": _int(handoff.get("decision_count"), 0),
        },
        "commands": {
            "create_group_enabled": bool(groups_payload.get("ready")),
            "sync_enabled": bool(sync.get("ready")),
            "live_switch_enabled": bool(tiles),
            "bake_enabled": bool(handoff.get("ready")),
            "export_handoff_enabled": bool(handoff.get("ready")),
        },
    }


def build_multicam_switcher_tile_board(
    snapshot: Mapping[str, Any] | None,
    *,
    group_id: str = "",
    switches: Sequence[Mapping[str, Any]] | None = None,
    playhead_ms: int = 0,
    strategy: str = "round_robin",
) -> dict[str, Any]:
    """Return a visual multicam switcher board contract.

    This stays UI-neutral but gives the editor enough information to render a
    Premiere/Final Cut-like angle grid: active tile, armed state, sync badges,
    keyboard numbers, and export/bake readiness.
    """

    workbench = build_multicam_switcher_workbench(
        snapshot,
        group_id=group_id,
        switches=switches,
        playhead_ms=playhead_ms,
        strategy=strategy,
    )
    tiles = [dict(row) for row in list(workbench.get("angle_tiles") or []) if isinstance(row, Mapping)]
    tile_count = len(tiles)
    columns = 1 if tile_count <= 1 else (2 if tile_count <= 4 else 3)
    board_tiles: list[dict[str, Any]] = []
    for index, tile in enumerate(tiles):
        board_tiles.append(
            {
                "angle_id": str(tile.get("angle_id") or ""),
                "name": str(tile.get("name") or tile.get("angle_id") or f"Angle {index + 1}"),
                "row": index // columns,
                "column": index % columns,
                "hotkey": str(index + 1),
                "active": bool(tile.get("active")),
                "armed": bool(tile.get("armed")),
                "health": str(tile.get("health") or "unknown"),
                "sync_badge": str(tile.get("sync_method") or "timeline"),
                "sync_offset_ms": _int(tile.get("sync_offset_ms"), 0),
                "track_ids": list(tile.get("track_ids") or []),
                "clip_count": _int(tile.get("clip_count"), 0),
                "style": {
                    "accent": "#ff6a3d" if bool(tile.get("active")) else ("#7c5cff" if bool(tile.get("armed")) else "#2b3144"),
                    "dimmed": not bool(tile.get("armed")),
                    "show_safe_border": bool(tile.get("active")),
                },
            }
        )
    return {
        "schema": MULTICAM_SCHEMA,
        "kind": "multicam_switcher_tile_board",
        "ready": bool(tile_count >= 2 and workbench.get("ready")),
        "group_id": str(workbench.get("group_id") or group_id or ""),
        "playhead_ms": _int(workbench.get("playhead_ms"), playhead_ms),
        "active_angle_id": str(workbench.get("active_angle_id") or ""),
        "grid": {
            "columns": columns,
            "rows": (tile_count + columns - 1) // columns if columns else 0,
            "tile_count": tile_count,
        },
        "tiles": board_tiles,
        "footer": {
            "switch_count": _int((workbench.get("switch_plan_summary") or {}).get("switch_count"), 0),
            "export_decision_count": _int((workbench.get("export_handoff_summary") or {}).get("decision_count"), 0),
            "ready_for_export_handoff": bool((workbench.get("export_handoff_summary") or {}).get("ready")),
        },
        "commands": {
            "set_active_angle_enabled": tile_count >= 2,
            "keyboard_switch_enabled": tile_count >= 2,
            "bake_enabled": bool((workbench.get("commands") or {}).get("bake_enabled")),
            "export_handoff_enabled": bool((workbench.get("commands") or {}).get("export_handoff_enabled")),
        },
    }


def build_multicam_switch_review_board(
    snapshot: Mapping[str, Any] | None,
    *,
    group_id: str = "",
    switches: Sequence[Mapping[str, Any]] | None = None,
    playhead_ms: int = 0,
    strategy: str = "round_robin",
) -> dict[str, Any]:
    """Return a UI-ready multicam switch review and bake board."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    tile_board = build_multicam_switcher_tile_board(
        snapshot,
        group_id=group_id,
        switches=switches,
        playhead_ms=playhead_ms,
        strategy=strategy,
    )
    bins = build_multicam_angle_bins(snapshot, group_id=group_id)
    plan = build_multicam_switch_plan(snapshot, group_id=group_id, strategy=strategy)
    handoff = build_multicam_export_handoff(snapshot, group_id=group_id, switches=switches)
    segments = [dict(row) for row in list(plan.get("segments") or []) if isinstance(row, Mapping)]
    decisions = [dict(row) for row in list(handoff.get("decisions") or []) if isinstance(row, Mapping)]
    review_rows: list[dict[str, Any]] = []
    for index, row in enumerate(decisions or segments):
        start = _int(row.get("timeline_in_ms"), 0)
        end = _int(row.get("timeline_out_ms"), start)
        review_rows.append(
            {
                "index": index,
                "angle_id": str(row.get("angle_id") or ""),
                "track_id": _int(row.get("track_id"), 0),
                "clip_id": _int(row.get("clip_id"), 0),
                "timeline_in_ms": start,
                "timeline_out_ms": end,
                "duration_ms": max(0, end - start),
                "source_path": str(row.get("source_path") or ""),
                "active_at_playhead": start <= _int(playhead_ms, 0) < end,
            }
        )
    warnings: list[str] = []
    if not bool(tile_board.get("ready")):
        warnings.append("tile_board_not_ready")
    if not bool(bins.get("ready")):
        warnings.append("angle_coverage_incomplete")
    if not bool(handoff.get("ready")):
        warnings.append("export_handoff_empty")
    if _int((bins.get("summary") or {}).get("angles_with_gaps"), 0) > 0:
        warnings.append("angle_gaps_present")
    return {
        "schema": MULTICAM_SCHEMA,
        "kind": "multicam_switch_review_board",
        "ready": bool(tile_board.get("ready") and handoff.get("ready")),
        "group_id": str(tile_board.get("group_id") or plan.get("group_id") or group_id or ""),
        "playhead_ms": max(0, _int(playhead_ms, 0)),
        "active_angle_id": str(tile_board.get("active_angle_id") or ""),
        "summary": {
            "angle_count": _int(tile_board.get("grid", {}).get("tile_count"), 0) if isinstance(tile_board.get("grid"), Mapping) else 0,
            "switch_count": len(review_rows),
            "export_decision_count": _int(handoff.get("decision_count"), len(decisions)),
            "angles_with_gaps": _int((bins.get("summary") or {}).get("angles_with_gaps"), 0),
            "strategy": str(plan.get("strategy") or strategy),
        },
        "sections": [
            {
                "id": "angles",
                "title": "Angle tiles",
                "rows": list(tile_board.get("tiles") or []),
            },
            {
                "id": "coverage",
                "title": "Coverage",
                "rows": list(bins.get("angle_bins") or []),
            },
            {
                "id": "switches",
                "title": "Switch decisions",
                "rows": review_rows,
            },
        ],
        "warnings": warnings,
        "commands": {
            "keyboard_switch_enabled": bool((tile_board.get("commands") or {}).get("keyboard_switch_enabled")),
            "set_active_angle_enabled": bool((tile_board.get("commands") or {}).get("set_active_angle_enabled")),
            "bake_enabled": bool((tile_board.get("commands") or {}).get("bake_enabled")) and bool(handoff.get("ready")),
            "export_handoff_enabled": bool((tile_board.get("commands") or {}).get("export_handoff_enabled")) and bool(handoff.get("ready")),
        },
    }


def build_multicam_live_switch_dashboard(
    snapshot: Mapping[str, Any] | None,
    *,
    group_id: str = "",
    switches: Sequence[Mapping[str, Any]] | None = None,
    playhead_ms: int = 0,
    strategy: str = "round_robin",
) -> dict[str, Any]:
    """Return one dashboard for multicam live switching and bake/export review."""

    tile_board = build_multicam_switcher_tile_board(
        snapshot,
        group_id=group_id,
        switches=switches,
        playhead_ms=playhead_ms,
        strategy=strategy,
    )
    review = build_multicam_switch_review_board(
        snapshot,
        group_id=group_id,
        switches=switches,
        playhead_ms=playhead_ms,
        strategy=strategy,
    )
    sync_quality = build_multicam_sync_quality_board(snapshot, group_id=group_id)
    waveform = build_multicam_waveform_sync_board(snapshot, group_id=group_id)
    tiles = [dict(row) for row in list(tile_board.get("tiles") or []) if isinstance(row, Mapping)]
    decisions: list[dict[str, Any]] = []
    for section in list(review.get("sections") or []):
        if isinstance(section, Mapping) and str(section.get("id") or "") == "switches":
            decisions = [dict(row) for row in list(section.get("rows") or []) if isinstance(row, Mapping)]
            break
    ready = bool(tile_board.get("ready") and review.get("ready") and sync_quality.get("ready"))
    return {
        "schema": MULTICAM_SCHEMA,
        "kind": "multicam_live_switch_dashboard",
        "ready": ready,
        "group_id": str(tile_board.get("group_id") or review.get("group_id") or group_id or ""),
        "playhead_ms": max(0, _int(playhead_ms, 0)),
        "active_angle_id": str(tile_board.get("active_angle_id") or review.get("active_angle_id") or ""),
        "summary": {
            "angle_count": len(tiles),
            "switch_count": len(decisions),
            "sync_row_count": _int((sync_quality.get("summary") or {}).get("angle_count"), 0),
            "waveform_ready_count": _int((waveform.get("summary") or {}).get("waveform_ready_count"), 0),
            "warning_count": len(list(review.get("warnings") or [])) + len(list(waveform.get("warnings") or [])),
        },
        "cards": [
            {"id": "angles", "label": "Angles", "value": len(tiles), "tone": "ok" if len(tiles) >= 2 else "warning"},
            {"id": "active", "label": "Active angle", "value": str(tile_board.get("active_angle_id") or ""), "tone": "ok"},
            {"id": "switches", "label": "Switches", "value": len(decisions), "tone": "ok" if decisions else "warning"},
            {
                "id": "sync",
                "label": "Sync",
                "value": float((sync_quality.get("summary") or {}).get("average_confidence") or 0.0),
                "tone": "ok" if bool(sync_quality.get("ready")) else "warning",
            },
        ],
        "sections": [
            {"id": "tiles", "title": "Live Angle Tiles", "rows": tiles},
            {"id": "switch_decisions", "title": "Switch Decisions", "rows": decisions},
            {"id": "sync_quality", "title": "Sync Quality", "rows": list(sync_quality.get("rows") or [])},
            {"id": "waveform", "title": "Waveform Sync", "rows": list(waveform.get("rows") or [])},
        ],
        "commands": {
            "keyboard_switch_enabled": bool((tile_board.get("commands") or {}).get("keyboard_switch_enabled")),
            "set_active_angle_enabled": bool((tile_board.get("commands") or {}).get("set_active_angle_enabled")),
            "open_sync_quality_enabled": True,
            "open_waveform_sync_enabled": True,
            "bake_enabled": bool((review.get("commands") or {}).get("bake_enabled")),
            "export_handoff_enabled": bool((review.get("commands") or {}).get("export_handoff_enabled")),
        },
        "readiness": {
            "live_switch_dashboard_ready": ready,
            "tile_board_ready": bool(tile_board.get("ready")),
            "review_board_ready": bool(review.get("ready")),
            "sync_quality_board_ready": bool(sync_quality.get("ready")),
            "waveform_sync_board_ready": bool((waveform.get("readiness") or {}).get("waveform_sync_board_ready")),
        },
    }


def build_multicam_sync_quality_board(
    snapshot: Mapping[str, Any] | None,
    *,
    group_id: str = "",
    strategy: str = "hybrid",
) -> dict[str, Any]:
    """Return a UI-ready sync confidence board for multicam angle setup."""

    sync = build_multicam_sync_plan(snapshot, group_id=group_id, strategy=strategy)
    bins = build_multicam_angle_bins(snapshot, group_id=group_id)
    bin_by_angle = {
        str(row.get("angle_id") or ""): row
        for row in list(bins.get("angle_bins") or [])
        if isinstance(row, Mapping)
    }
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(list(sync.get("angle_sync") or [])):
        if not isinstance(row, Mapping):
            continue
        angle_id = str(row.get("angle_id") or "")
        method = str(row.get("sync_method") or "timeline")
        coverage = bin_by_angle.get(angle_id, {})
        gap_count = _int(coverage.get("gap_count"), 0)
        if method == "timecode":
            confidence = 0.95
            tone = "ok"
        elif method == "waveform":
            confidence = 0.88
            tone = "ok"
        elif method == "audio_marker":
            confidence = 0.82
            tone = "ok"
        else:
            confidence = 0.62
            tone = "warning"
        if gap_count:
            confidence = max(0.2, confidence - min(0.25, gap_count * 0.05))
            tone = "warning"
        rows.append(
            {
                "angle_id": angle_id,
                "index": index,
                "sync_method": method,
                "offset_ms": _int(row.get("offset_ms"), 0),
                "needs_move": bool(row.get("needs_move")),
                "clip_count": _int(row.get("clip_count"), 0),
                "coverage_ratio": coverage.get("coverage_ratio", 0.0),
                "gap_count": gap_count,
                "confidence": round(confidence, 3),
                "tone": tone,
                "recommended_action": "accept" if confidence >= 0.8 else "review",
            }
        )
    warnings = list(sync.get("warnings") or [])
    if any(str(row.get("tone")) == "warning" for row in rows):
        warnings.append("sync_quality_needs_review")
    ready = bool(rows and len(rows) >= 2)
    return {
        "schema": MULTICAM_SCHEMA,
        "kind": "multicam_sync_quality_board",
        "ready": ready,
        "group_id": str(sync.get("group_id") or group_id or ""),
        "strategy": str(sync.get("strategy") or strategy),
        "summary": {
            "angle_count": len(rows),
            "sync_methods": list(sync.get("sync_methods") or []),
            "max_abs_offset_ms": _int(sync.get("max_abs_offset_ms"), 0),
            "average_confidence": round(sum(float(row.get("confidence") or 0.0) for row in rows) / len(rows), 3) if rows else 0.0,
            "review_count": sum(1 for row in rows if str(row.get("recommended_action")) == "review"),
        },
        "rows": rows,
        "warnings": sorted({str(row) for row in warnings if str(row or "").strip()}),
        "commands": {
            "accept_offsets_enabled": ready,
            "open_angle_bins_enabled": True,
            "review_low_confidence_enabled": any(str(row.get("recommended_action")) == "review" for row in rows),
            "prefer_timecode_enabled": "timecode" in set(sync.get("sync_methods") or []),
            "prefer_audio_marker_enabled": "audio_marker" in set(sync.get("sync_methods") or []),
        },
        "readiness": {
            "sync_quality_board_ready": ready,
            "has_confidence_rows": bool(rows),
            "requires_manual_review": any(str(row.get("recommended_action")) == "review" for row in rows),
        },
    }


def multicam_contract_evidence(
    snapshot: Mapping[str, Any] | None,
    *,
    action_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    actions = {str(row) for row in list(action_ids or [])}
    required_actions = {
        "timeline.multicam.summary",
        "timeline.multicam.create_group",
        "timeline.multicam.sync_plan",
        "timeline.multicam.switch_plan",
        "timeline.multicam.switcher_workbench",
        "timeline.multicam.set_active_angle",
        "timeline.multicam.angle_bins",
        "timeline.multicam.export_handoff",
        "timeline.multicam.tile_board",
        "timeline.multicam.review_board",
        "timeline.multicam.live_switch_dashboard",
        "timeline.multicam.sync_quality_board",
        "timeline.multicam.waveform_sync_board",
    }
    groups = build_multicam_groups(snapshot)
    angle_bins = build_multicam_angle_bins(snapshot)
    sync = build_multicam_sync_plan(snapshot)
    plan = build_multicam_switch_plan(snapshot)
    handoff = build_multicam_export_handoff(snapshot)
    workbench = build_multicam_switcher_workbench(snapshot)
    tile_board = build_multicam_switcher_tile_board(snapshot)
    review_board = build_multicam_switch_review_board(snapshot)
    live_dashboard = build_multicam_live_switch_dashboard(snapshot)
    sync_quality = build_multicam_sync_quality_board(snapshot)
    waveform_sync = build_multicam_waveform_sync_board(snapshot)
    angle_count = _int(groups.get("angle_count"), 0)
    switch_count = _int(plan.get("switch_count"), 0)
    ok = (
        angle_count >= 3
        and switch_count >= 4
        and bool(angle_bins.get("ready"))
        and bool(sync.get("ready"))
        and bool(workbench.get("ready"))
        and bool(handoff.get("ready"))
        and required_actions <= actions
    )
    return {
        "ok": ok,
        "required_actions": sorted(required_actions),
        "available_actions": sorted(required_actions & actions),
        "angle_count": angle_count,
        "switch_count": switch_count,
        "angle_bins_ready": bool(angle_bins.get("ready")),
        "angle_bin_count": _int(angle_bins.get("angle_count"), 0),
        "angle_gap_count": _int((angle_bins.get("summary") or {}).get("angles_with_gaps"), 0),
        "sync_plan_ready": bool(sync.get("ready")),
        "sync_methods": list(sync.get("sync_methods") or []),
        "switcher_workbench_ready": bool(workbench.get("ready")),
        "switcher_tile_board_ready": bool(tile_board.get("ready")) and "timeline.multicam.tile_board" in actions,
        "switch_review_board_ready": bool(review_board.get("ready")) and "timeline.multicam.review_board" in actions,
        "live_switch_dashboard_ready": bool((live_dashboard.get("readiness") or {}).get("live_switch_dashboard_ready"))
        and "timeline.multicam.live_switch_dashboard" in actions,
        "sync_quality_board_ready": bool((sync_quality.get("readiness") or {}).get("sync_quality_board_ready"))
        and "timeline.multicam.sync_quality_board" in actions,
        "waveform_sync_board_ready": bool((waveform_sync.get("readiness") or {}).get("waveform_sync_board_ready"))
        and "timeline.multicam.waveform_sync_board" in actions,
        "export_handoff_ready": bool(handoff.get("ready")),
        "group_count": _int(groups.get("group_count"), 0),
    }
