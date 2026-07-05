"""Clip and timeline edit action registrations."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.actions.result import ActionResult, error_result, ok_result
from app.actions.schema import ActionSpec, schema_object


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def register_clip_edit_actions(registry: Any) -> None:
    """Register clip edit, range edit, clipboard edit, and trim-tool actions."""
    registry.register(
        ActionSpec(
            "timeline.split",
            "Split the clip on a video track at project time.",
            "timeline",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "at_ms": {"type": "integer", "minimum": 0},
                },
                required=("track_id", "at_ms"),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Split clip",
        ),
        lambda params, dry: _timeline_split(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "clip.trim",
            "Set a video clip source in/out range.",
            "clip",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "source_in_ms": {"type": "integer", "minimum": 0},
                    "source_out_ms": {"type": "integer", "minimum": 1},
                },
                required=("track_id", "clip_id"),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Trim clip",
        ),
        lambda params, dry: _clip_trim(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "clip.ripple_trim",
            "Ripple-trim a video clip edge and move following clips with linked audio.",
            "clip",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "edge": {"type": "string", "enum": ["left", "right", "start", "end", "in", "out"]},
                    "delta_ms": {"type": "integer"},
                    "ripple_linked_audio": {"type": "boolean"},
                },
                required=("track_id", "clip_id", "delta_ms"),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Ripple trim clip",
        ),
        lambda params, dry: _clip_ripple_trim(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.precision_trim",
            "Apply exact numeric trim values or edge deltas to a selected clip.",
            "timeline",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "timeline_in_ms": {"type": "integer", "minimum": 0},
                    "source_in_ms": {"type": "integer", "minimum": 0},
                    "source_out_ms": {"type": "integer", "minimum": 1},
                    "left_delta_ms": {"type": "integer"},
                    "right_delta_ms": {"type": "integer"},
                    "slip_delta_ms": {"type": "integer"},
                    "ripple": {"type": "boolean"},
                    "ripple_linked_audio": {"type": "boolean"},
                },
                required=("track_id", "clip_id"),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Precision trim",
        ),
        lambda params, dry: _timeline_precision_trim(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.trim_to_playhead",
            "Trim the selected or current clip edge to the playhead.",
            "timeline",
            params_schema=schema_object(
                {
                    "edge": {"type": "string", "enum": ["auto", "left", "right", "start", "end", "in", "out"]},
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "at_ms": {"type": "integer", "minimum": 0},
                    "ripple": {"type": "boolean"},
                    "ripple_linked_audio": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Trim to playhead",
        ),
        lambda params, dry: _timeline_trim_to_playhead(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.ripple_delete",
            "Delete a clip and close the resulting gap.",
            "timeline",
            params_schema=schema_object(
                {"track_id": {"type": "integer"}, "clip_id": {"type": "integer"}},
                required=("track_id", "clip_id"),
            ),
            mutating=True,
            destructive=True,
            requires_owner=True,
            requires_review=True,
            undo_label="Ripple delete",
        ),
        lambda params, dry: _timeline_ripple_delete(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.cleanup_edges",
            "Close micro gaps and trim micro overlaps on timeline clip edges.",
            "timeline",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "frame_ms": {"type": "integer", "minimum": 1},
                    "close_gaps": {"type": "boolean"},
                    "trim_overlaps": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Cleanup timeline edges",
        ),
        lambda params, dry: _timeline_cleanup_edges(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.range_delete",
            "Lift or extract the timeline In/Out range on targeted video tracks.",
            "timeline",
            params_schema=schema_object(
                {
                    "start_ms": {"type": "integer", "minimum": 0},
                    "end_ms": {"type": "integer", "minimum": 1},
                    "track_id": {"type": "integer"},
                    "ripple": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            mutating=True,
            destructive=True,
            requires_owner=True,
            requires_review=True,
            undo_label="Range delete",
        ),
        lambda params, dry: _timeline_range_delete(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.lift",
            "Lift the timeline In/Out range without closing the gap.",
            "timeline",
            params_schema=schema_object(
                {
                    "start_ms": {"type": "integer", "minimum": 0},
                    "end_ms": {"type": "integer", "minimum": 1},
                    "track_id": {"type": "integer"},
                },
                additional_properties=True,
            ),
            mutating=True,
            destructive=True,
            requires_owner=True,
            requires_review=True,
            undo_label="Lift range",
        ),
        lambda params, dry: _timeline_lift(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.extract",
            "Extract the timeline In/Out range and close the gap.",
            "timeline",
            params_schema=schema_object(
                {
                    "start_ms": {"type": "integer", "minimum": 0},
                    "end_ms": {"type": "integer", "minimum": 1},
                    "track_id": {"type": "integer"},
                },
                additional_properties=True,
            ),
            mutating=True,
            destructive=True,
            requires_owner=True,
            requires_review=True,
            undo_label="Extract range",
        ),
        lambda params, dry: _timeline_extract(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "clip.delete",
            "Delete a clip without closing gaps.",
            "clip",
            params_schema=schema_object(
                {"track_id": {"type": "integer"}, "clip_id": {"type": "integer"}},
                required=("track_id", "clip_id"),
            ),
            mutating=True,
            destructive=True,
            requires_owner=True,
            requires_review=True,
            undo_label="Delete clip",
        ),
        lambda params, dry: _clip_delete(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "clip.duplicate",
            "Duplicate a clip on the same track.",
            "clip",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "at_ms": {"type": "integer", "minimum": 0},
                },
                required=("track_id", "clip_id"),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Duplicate clip",
        ),
        lambda params, dry: _clip_duplicate(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "clip.copy",
            "Copy selected or explicit video clips into the internal timeline clipboard.",
            "clip",
            params_schema=schema_object(
                {
                    "clips": {"type": "array"},
                    "use_selection": {"type": "boolean"},
                    "include_linked_audio": {"type": "boolean"},
                }
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Copy clips",
        ),
        lambda params, dry: _clip_copy(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "clip.cut_to_clipboard",
            "Copy selected or explicit video clips and remove them from the timeline.",
            "clip",
            params_schema=schema_object(
                {
                    "clips": {"type": "array"},
                    "use_selection": {"type": "boolean"},
                    "include_linked_audio": {"type": "boolean"},
                }
            ),
            mutating=True,
            destructive=True,
            requires_owner=True,
            requires_review=True,
            undo_label="Cut clips",
        ),
        lambda params, dry: _clip_cut_to_clipboard(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "clip.paste",
            "Paste internal timeline clipboard clips at the playhead or explicit time.",
            "clip",
            params_schema=schema_object(
                {
                    "at_ms": {"type": "integer", "minimum": 0},
                    "target_track_id": {"type": "integer"},
                    "include_linked_audio": {"type": "boolean"},
                }
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Paste clips",
        ),
        lambda params, dry: _clip_paste(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.insert_clipboard",
            "Insert internal timeline clipboard clips at the playhead or explicit time, pushing later clips on targeted tracks.",
            "timeline",
            params_schema=schema_object(
                {
                    "at_ms": {"type": "integer", "minimum": 0},
                    "target_track_id": {"type": "integer"},
                    "include_linked_audio": {"type": "boolean"},
                }
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Insert clipboard",
        ),
        lambda params, dry: _timeline_insert_clipboard(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.overwrite_clipboard",
            "Overwrite targeted timeline ranges with internal timeline clipboard clips.",
            "timeline",
            params_schema=schema_object(
                {
                    "at_ms": {"type": "integer", "minimum": 0},
                    "target_track_id": {"type": "integer"},
                    "include_linked_audio": {"type": "boolean"},
                }
            ),
            mutating=True,
            destructive=True,
            requires_owner=True,
            requires_review=True,
            undo_label="Overwrite clipboard",
        ),
        lambda params, dry: _timeline_overwrite_clipboard(registry, params, dry),
    )
    three_point_schema = schema_object(
        {
            "at_ms": {"type": "integer", "minimum": 0},
            "record_out_ms": {"type": "integer", "minimum": 1},
            "target_track_id": {"type": "integer"},
            "source_in_ms": {"type": "integer", "minimum": 0},
            "source_out_ms": {"type": "integer", "minimum": 1},
        },
        additional_properties=True,
    )
    registry.register(
        ActionSpec(
            "timeline.three_point_insert",
            "Insert the Source monitor range into the Record monitor/playhead, pushing later clips.",
            "timeline",
            params_schema=three_point_schema,
            mutating=True,
            requires_owner=True,
            undo_label="3-point insert",
        ),
        lambda params, dry: _timeline_three_point_insert(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.three_point_overwrite",
            "Overwrite the Record monitor/playhead range with the Source monitor range.",
            "timeline",
            params_schema=three_point_schema,
            mutating=True,
            destructive=True,
            requires_owner=True,
            requires_review=True,
            undo_label="3-point overwrite",
        ),
        lambda params, dry: _timeline_three_point_overwrite(registry, params, dry),
    )
    registry.register_adapter_action(
        "clip.move",
        "Move a video clip to an absolute project time.",
        "clip",
        "move_clip",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "at_ms": {"type": "integer", "minimum": 0},
                "allow_overlap": {"type": "boolean"},
            },
            required=("track_id", "clip_id", "at_ms"),
        ),
        required=("track_id", "clip_id", "at_ms"),
        undo_label="Move clip",
        dry_summary="clip would move",
    )
    registry.register(
        ActionSpec(
            "clip.move_snapped",
            "Move a video clip using timeline snap targets and collision clamp.",
            "clip",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "at_ms": {"type": "integer", "minimum": 0},
                    "snap_ms": {"type": "integer", "minimum": 0},
                    "include_playhead": {"type": "boolean"},
                    "include_markers": {"type": "boolean"},
                    "extra_snap_targets": {"type": "array", "items": {"type": "integer"}},
                },
                required=("track_id", "clip_id", "at_ms"),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Move clip with snapping",
        ),
        lambda params, dry: _clip_move_snapped(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "clip.move_linked",
            "Move a video clip and its linked audio by the same delta.",
            "clip",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "delta_ms": {"type": "integer"},
                    "strict_links": {"type": "boolean"},
                },
                required=("track_id", "clip_id", "delta_ms"),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Move linked clip",
        ),
        lambda params, dry: _clip_move_linked(registry, params, dry),
    )
    registry.register_adapter_action(
        "clip.link_audio",
        "Link a video clip to a specific or nearest audio clip.",
        "clip",
        "link_audio_clip",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "audio_track_id": {"type": "integer"},
                "audio_clip_id": {"type": "integer"},
                "nearest": {"type": "boolean"},
            },
            required=("track_id", "clip_id"),
        ),
        required=("track_id", "clip_id"),
        undo_label="Link audio",
        dry_summary="audio link would be set",
    )
    registry.register_adapter_action(
        "clip.unlink_audio",
        "Remove a video clip audio link.",
        "clip",
        "unlink_audio_clip",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
            },
            required=("track_id", "clip_id"),
        ),
        required=("track_id", "clip_id"),
        undo_label="Unlink audio",
        dry_summary="audio link would be cleared",
    )
    registry.register_adapter_action(
        "clip.set_sync_offset",
        "Set linked audio offset relative to the video clip.",
        "clip",
        "set_linked_clip_sync_offset",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "sync_offset_ms": {"type": "integer"},
            },
            required=("track_id", "clip_id", "sync_offset_ms"),
        ),
        required=("track_id", "clip_id", "sync_offset_ms"),
        undo_label="Set sync offset",
        dry_summary="linked audio sync offset would change",
    )
    registry.register_adapter_action(
        "clip.j_cut",
        "Extend linked audio earlier for a J-cut.",
        "clip",
        "j_cut_linked_clip",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "extend_ms": {"type": "integer", "minimum": 1},
            },
            required=("track_id", "clip_id"),
        ),
        required=("track_id", "clip_id"),
        undo_label="J-cut linked clip",
        dry_summary="linked audio would extend earlier",
    )
    registry.register_adapter_action(
        "clip.l_cut",
        "Extend linked audio later for an L-cut.",
        "clip",
        "l_cut_linked_clip",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "extend_ms": {"type": "integer", "minimum": 1},
            },
            required=("track_id", "clip_id"),
        ),
        required=("track_id", "clip_id"),
        undo_label="L-cut linked clip",
        dry_summary="linked audio would extend later",
    )
    registry.register(
        ActionSpec(
            "clip.slip",
            "Slip a clip source window while keeping its timeline edges fixed.",
            "clip",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "delta_ms": {"type": "integer"},
                },
                required=("track_id", "clip_id", "delta_ms"),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Slip clip",
        ),
        lambda params, dry: _clip_slip(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "clip.roll",
            "Roll the edit point between two adjacent clips.",
            "clip",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "left_clip_id": {"type": "integer"},
                    "right_clip_id": {"type": "integer"},
                    "delta_ms": {"type": "integer"},
                },
                required=("track_id", "left_clip_id", "right_clip_id", "delta_ms"),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Roll edit",
        ),
        lambda params, dry: _clip_roll(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "clip.slide",
            "Slide a clip between contiguous neighbours.",
            "clip",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "delta_ms": {"type": "integer"},
                },
                required=("track_id", "clip_id", "delta_ms"),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Slide clip",
        ),
        lambda params, dry: _clip_slide(registry, params, dry),
    )
    registry.register_adapter_action(
        "clip.nudge",
        "Move a video clip by a relative time delta.",
        "clip",
        "nudge_clip",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "delta_ms": {"type": "integer"},
                "allow_overlap": {"type": "boolean"},
            },
            required=("track_id", "clip_id", "delta_ms"),
        ),
        required=("track_id", "clip_id", "delta_ms"),
        undo_label="Nudge clip",
        dry_summary="clip would be nudged",
    )
    registry.register(
        ActionSpec(
            "clip.nudge_frames",
            "Move a video clip by a whole-frame delta.",
            "clip",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "frames": {"type": "integer"},
                    "fps": {"type": "number"},
                    "allow_overlap": {"type": "boolean"},
                },
                required=("track_id", "clip_id", "frames"),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Nudge clip by frames",
        ),
        lambda params, dry: _clip_nudge_frames(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "clip.set_speed",
            "Set a whole-clip speed override.",
            "clip",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "speed": {"type": "number", "minimum": 0.05, "maximum": 16.0},
                },
                required=("track_id", "clip_id", "speed"),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Set clip speed",
        ),
        lambda params, dry: _clip_set_speed(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "clip.set_fade",
            "Set clip fade-in and fade-out durations.",
            "clip",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "fade_in_ms": {"type": "integer", "minimum": 0},
                    "fade_out_ms": {"type": "integer", "minimum": 0},
                    "replace_existing": {"type": "boolean"},
                },
                required=("track_id", "clip_id"),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Set clip fade",
        ),
        lambda params, dry: _clip_set_fade(registry, params, dry),
    )


def _timeline_split(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    missing = [key for key in ("track_id", "at_ms") if key not in params]
    if missing:
        return error_result("timeline.split", f"missing params: {', '.join(missing)}", dry_run=dry_run)
    if dry_run:
        return registry._dry_result("timeline.split", params, "clip would be split")
    return ok_result(
        "timeline.split",
        registry.adapter.split_clip(track_id=_as_int(params.get("track_id")), at_ms=_as_int(params.get("at_ms"))),
        changed=True,
    )


def _clip_trim(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    missing = [key for key in ("track_id", "clip_id") if key not in params]
    if missing:
        return error_result("clip.trim", f"missing params: {', '.join(missing)}", dry_run=dry_run)
    if dry_run:
        return registry._dry_result("clip.trim", params, "clip source range would be trimmed")
    return ok_result(
        "clip.trim",
        registry.adapter.trim_clip(
            track_id=_as_int(params.get("track_id")),
            clip_id=_as_int(params.get("clip_id")),
            source_in_ms=_as_int(params["source_in_ms"]) if "source_in_ms" in params else None,
            source_out_ms=_as_int(params["source_out_ms"]) if "source_out_ms" in params else None,
        ),
        changed=True,
    )


def _clip_ripple_trim(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    missing = [key for key in ("track_id", "clip_id", "delta_ms") if key not in params]
    if missing:
        return error_result("clip.ripple_trim", f"missing params: {', '.join(missing)}", dry_run=dry_run)
    try:
        result = registry.adapter.ripple_trim_clip(
            track_id=_as_int(params.get("track_id")),
            clip_id=_as_int(params.get("clip_id")),
            edge=str(params.get("edge") or "right"),
            delta_ms=_as_int(params.get("delta_ms")),
            ripple_linked_audio=bool(params.get("ripple_linked_audio", True)),
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        return error_result("clip.ripple_trim", str(exc), dry_run=dry_run)
    return ok_result("clip.ripple_trim", result, dry_run=bool(dry_run), changed=False if dry_run else bool(result.get("changed")))


def _timeline_precision_trim(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    missing = [key for key in ("track_id", "clip_id") if key not in params]
    if missing:
        return error_result("timeline.precision_trim", f"missing params: {', '.join(missing)}", dry_run=dry_run)

    def _optional_int(key: str) -> int | None:
        return _as_int(params[key]) if key in params else None

    try:
        result = registry.adapter.precision_trim_clip(
            track_id=_as_int(params.get("track_id")),
            clip_id=_as_int(params.get("clip_id")),
            timeline_in_ms=_optional_int("timeline_in_ms"),
            source_in_ms=_optional_int("source_in_ms"),
            source_out_ms=_optional_int("source_out_ms"),
            left_delta_ms=_optional_int("left_delta_ms"),
            right_delta_ms=_optional_int("right_delta_ms"),
            slip_delta_ms=_optional_int("slip_delta_ms"),
            ripple=bool(params.get("ripple", False)),
            ripple_linked_audio=bool(params.get("ripple_linked_audio", True)),
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        return error_result("timeline.precision_trim", str(exc), dry_run=dry_run)
    return ok_result("timeline.precision_trim", result, dry_run=bool(dry_run), changed=False if dry_run else bool(result.get("changed")))


def _timeline_trim_to_playhead(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    try:
        result = registry.adapter.trim_to_playhead(
            edge=str(params.get("edge") or "auto"),
            track_id=_as_int(params.get("track_id"), -1) if "track_id" in params else None,
            clip_id=_as_int(params.get("clip_id"), -1) if "clip_id" in params else None,
            at_ms=_as_int(params.get("at_ms"), -1) if "at_ms" in params else None,
            ripple=bool(params.get("ripple", False)),
            ripple_linked_audio=bool(params.get("ripple_linked_audio", True)),
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        return error_result("timeline.trim_to_playhead", str(exc), dry_run=dry_run)
    return ok_result("timeline.trim_to_playhead", result, dry_run=bool(dry_run), changed=False if dry_run else bool(result.get("changed")))


def _timeline_ripple_delete(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    missing = [key for key in ("track_id", "clip_id") if key not in params]
    if missing:
        return error_result("timeline.ripple_delete", f"missing params: {', '.join(missing)}", dry_run=dry_run)
    if dry_run:
        return registry._dry_result("timeline.ripple_delete", params, "clip would be ripple deleted")
    return ok_result(
        "timeline.ripple_delete",
        registry.adapter.delete_clip(track_id=_as_int(params.get("track_id")), clip_id=_as_int(params.get("clip_id")), ripple=True),
        changed=True,
    )


def _timeline_cleanup_edges(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    try:
        result = registry.adapter.cleanup_timeline_edges(
            track_id=_as_int(params.get("track_id"), -1) if "track_id" in params else None,
            frame_ms=_as_int(params.get("frame_ms"), 33),
            close_gaps=bool(params.get("close_gaps", True)),
            trim_overlaps=bool(params.get("trim_overlaps", True)),
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        return error_result("timeline.cleanup_edges", str(exc), dry_run=dry_run)
    return ok_result("timeline.cleanup_edges", result, dry_run=bool(dry_run), changed=False if dry_run else bool(result.get("action_count")))


def _timeline_range_delete_common(registry: Any, action_id: str, params: Mapping[str, Any], dry_run: bool, *, ripple: bool | None = None) -> ActionResult:
    try:
        result = registry.adapter.range_delete(
            start_ms=_as_int(params.get("start_ms"), -1) if "start_ms" in params else None,
            end_ms=_as_int(params.get("end_ms"), -1) if "end_ms" in params else None,
            track_id=_as_int(params.get("track_id"), -1) if "track_id" in params else None,
            ripple=bool(params.get("ripple", False)) if ripple is None else bool(ripple),
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        return error_result(action_id, str(exc), dry_run=dry_run)
    return ok_result(action_id, result, dry_run=bool(dry_run), changed=False if dry_run else bool(result.get("deleted_clip_count")))


def _timeline_range_delete(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    return _timeline_range_delete_common(registry, "timeline.range_delete", params, dry_run, ripple=None)


def _timeline_lift(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    return _timeline_range_delete_common(registry, "timeline.lift", params, dry_run, ripple=False)


def _timeline_extract(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    return _timeline_range_delete_common(registry, "timeline.extract", params, dry_run, ripple=True)


def _clip_delete(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    missing = [key for key in ("track_id", "clip_id") if key not in params]
    if missing:
        return error_result("clip.delete", f"missing params: {', '.join(missing)}", dry_run=dry_run)
    if dry_run:
        return registry._dry_result("clip.delete", params, "clip would be deleted")
    return ok_result(
        "clip.delete",
        registry.adapter.delete_clip(track_id=_as_int(params.get("track_id")), clip_id=_as_int(params.get("clip_id")), ripple=False),
        changed=True,
    )


def _clip_duplicate(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    missing = [key for key in ("track_id", "clip_id") if key not in params]
    if missing:
        return error_result("clip.duplicate", f"missing params: {', '.join(missing)}", dry_run=dry_run)
    if dry_run:
        return registry._dry_result("clip.duplicate", params, "clip would be duplicated")
    return ok_result(
        "clip.duplicate",
        registry.adapter.duplicate_clip(
            track_id=_as_int(params.get("track_id")),
            clip_id=_as_int(params.get("clip_id")),
            at_ms=_as_int(params["at_ms"]) if "at_ms" in params else None,
        ),
        changed=True,
    )


def _clip_copy(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    if dry_run:
        try:
            records = registry.adapter._clipboard_records_from_request(
                clips=params.get("clips") if isinstance(params.get("clips"), Sequence) else None,
                use_selection=bool(params.get("use_selection", True)),
                include_linked_audio=bool(params.get("include_linked_audio", True)),
            )
        except Exception as exc:
            return error_result("clip.copy", str(exc), dry_run=True)
        linked_count = sum(1 for row in records if isinstance(row.get("linked_audio"), Mapping))
        return ok_result("clip.copy", {"kind": "video_clips", "count": len(records), "linked_audio_count": linked_count}, dry_run=True, changed=False)
    return ok_result(
        "clip.copy",
        registry.adapter.copy_clips(
            clips=params.get("clips") if isinstance(params.get("clips"), Sequence) else None,
            use_selection=bool(params.get("use_selection", True)),
            include_linked_audio=bool(params.get("include_linked_audio", True)),
        ),
        changed=True,
    )


def _clip_cut_to_clipboard(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    if dry_run:
        try:
            records = registry.adapter._clipboard_records_from_request(
                clips=params.get("clips") if isinstance(params.get("clips"), Sequence) else None,
                use_selection=bool(params.get("use_selection", True)),
                include_linked_audio=bool(params.get("include_linked_audio", True)),
            )
        except Exception as exc:
            return error_result("clip.cut_to_clipboard", str(exc), dry_run=True)
        linked_count = sum(1 for row in records if isinstance(row.get("linked_audio"), Mapping))
        return ok_result(
            "clip.cut_to_clipboard",
            {
                "kind": "video_clips",
                "count": len(records),
                "linked_audio_count": linked_count,
                "would_delete_count": len(records),
                "would_delete_audio_count": linked_count,
            },
            dry_run=True,
            changed=False,
        )
    return ok_result(
        "clip.cut_to_clipboard",
        registry.adapter.cut_clips_to_clipboard(
            clips=params.get("clips") if isinstance(params.get("clips"), Sequence) else None,
            use_selection=bool(params.get("use_selection", True)),
            include_linked_audio=bool(params.get("include_linked_audio", True)),
        ),
        changed=True,
    )


def _clip_paste(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    at_ms = _as_int(params.get("at_ms")) if "at_ms" in params else None
    target_track_id = _as_int(params.get("target_track_id")) if "target_track_id" in params else None
    include_linked_audio = bool(params.get("include_linked_audio", True))
    if dry_run:
        records = registry.adapter._clipboard_records()
        if not records:
            return error_result("clip.paste", "clipboard is empty", dry_run=True)
        base_ms = min(_as_int(row.get("timeline_in_ms"), 0) for row in records)
        paste_base = registry.adapter._current_playhead_ms() if at_ms is None else max(0, _as_int(at_ms))
        linked_count = sum(1 for row in records if include_linked_audio and isinstance(row.get("linked_audio"), Mapping))
        return ok_result(
            "clip.paste",
            {"count": len(records), "linked_audio_count": linked_count, "base_ms": paste_base, "source_base_ms": base_ms},
            dry_run=True,
            changed=False,
        )
    return ok_result(
        "clip.paste",
        registry.adapter.paste_clips(at_ms=at_ms, target_track_id=target_track_id, include_linked_audio=include_linked_audio),
        changed=True,
    )


def _timeline_clipboard_edit_common(registry: Any, action_id: str, params: Mapping[str, Any], dry_run: bool, *, mode: str) -> ActionResult:
    try:
        result = registry.adapter.paste_clipboard_edit(
            mode=mode,
            at_ms=_as_int(params.get("at_ms")) if "at_ms" in params else None,
            target_track_id=_as_int(params.get("target_track_id")) if "target_track_id" in params else None,
            include_linked_audio=bool(params.get("include_linked_audio", True)),
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        return error_result(action_id, str(exc), dry_run=dry_run)
    return ok_result(action_id, result, dry_run=bool(dry_run), changed=False if dry_run else bool(result.get("count")))


def _timeline_insert_clipboard(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    return _timeline_clipboard_edit_common(registry, "timeline.insert_clipboard", params, dry_run, mode="insert")


def _timeline_overwrite_clipboard(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    return _timeline_clipboard_edit_common(registry, "timeline.overwrite_clipboard", params, dry_run, mode="overwrite")


def _timeline_three_point_common(registry: Any, action_id: str, params: Mapping[str, Any], dry_run: bool, *, mode: str) -> ActionResult:
    try:
        result = registry.adapter.three_point_edit(
            mode=mode,
            at_ms=_as_int(params.get("at_ms")) if "at_ms" in params else None,
            record_out_ms=_as_int(params.get("record_out_ms")) if "record_out_ms" in params else None,
            target_track_id=_as_int(params.get("target_track_id")) if "target_track_id" in params else None,
            source_in_ms=_as_int(params.get("source_in_ms")) if "source_in_ms" in params else None,
            source_out_ms=_as_int(params.get("source_out_ms")) if "source_out_ms" in params else None,
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        return error_result(action_id, str(exc), dry_run=dry_run)
    return ok_result(action_id, result, dry_run=bool(dry_run), changed=False if dry_run else bool(result.get("clip_id")))


def _timeline_three_point_insert(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    return _timeline_three_point_common(registry, "timeline.three_point_insert", params, dry_run, mode="insert")


def _timeline_three_point_overwrite(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    return _timeline_three_point_common(registry, "timeline.three_point_overwrite", params, dry_run, mode="overwrite")


def _clip_move_snapped(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    missing = [key for key in ("track_id", "clip_id", "at_ms") if key not in params]
    if missing:
        return error_result("clip.move_snapped", f"missing params: {', '.join(missing)}", dry_run=dry_run)
    raw_targets = params.get("extra_snap_targets")
    extra_targets: list[int] = []
    if isinstance(raw_targets, Sequence) and not isinstance(raw_targets, (str, bytes, bytearray)):
        extra_targets = [_as_int(value, 0) for value in raw_targets]
    result = registry.adapter.move_clip_snapped(
        track_id=_as_int(params.get("track_id")),
        clip_id=_as_int(params.get("clip_id")),
        at_ms=_as_int(params.get("at_ms")),
        snap_ms=_as_int(params.get("snap_ms", 200), 200),
        include_playhead=bool(params.get("include_playhead", True)),
        include_markers=bool(params.get("include_markers", True)),
        extra_snap_targets=extra_targets,
        dry_run=bool(dry_run),
    )
    return ok_result("clip.move_snapped", result, dry_run=bool(dry_run), changed=False if dry_run else bool(result.get("changed")))


def _clip_move_linked(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    missing = [key for key in ("track_id", "clip_id", "delta_ms") if key not in params]
    if missing:
        return error_result("clip.move_linked", f"missing params: {', '.join(missing)}", dry_run=dry_run)
    try:
        result = registry.adapter.move_linked_clip(
            track_id=_as_int(params.get("track_id")),
            clip_id=_as_int(params.get("clip_id")),
            delta_ms=_as_int(params.get("delta_ms")),
            strict_links=bool(params.get("strict_links", True)),
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        return error_result("clip.move_linked", str(exc), dry_run=dry_run)
    return ok_result(
        "clip.move_linked",
        result,
        dry_run=bool(dry_run),
        changed=False if dry_run else bool(result.get("video_move_count") or result.get("linked_audio_count")),
    )


def _clip_nudge_frames(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    missing = [key for key in ("track_id", "clip_id", "frames") if key not in params]
    if missing:
        return error_result("clip.nudge_frames", f"missing params: {', '.join(missing)}", dry_run=dry_run)
    frames = _as_int(params.get("frames"), 0)
    fps = max(1.0, _as_float(params.get("fps"), 30.0))
    delta_ms = int(round(frames * 1000.0 / fps))
    if dry_run:
        return ok_result(
            "clip.nudge_frames",
            {
                "track_id": _as_int(params.get("track_id")),
                "clip_id": _as_int(params.get("clip_id")),
                "frames": frames,
                "fps": fps,
                "frame_delta_ms": delta_ms,
            },
            dry_run=True,
            changed=False,
        )
    try:
        result = registry.adapter.nudge_clip(
            track_id=_as_int(params.get("track_id")),
            clip_id=_as_int(params.get("clip_id")),
            delta_ms=delta_ms,
            allow_overlap=bool(params.get("allow_overlap", False)),
        )
    except Exception as exc:
        return error_result("clip.nudge_frames", str(exc), dry_run=dry_run)
    return ok_result("clip.nudge_frames", {**result, "frames": frames, "fps": fps, "frame_delta_ms": delta_ms}, changed=True)


def _clip_slip(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    missing = [key for key in ("track_id", "clip_id", "delta_ms") if key not in params]
    if missing:
        return error_result("clip.slip", f"missing params: {', '.join(missing)}", dry_run=dry_run)
    result = registry.adapter.slip_clip(
        track_id=_as_int(params.get("track_id")),
        clip_id=_as_int(params.get("clip_id")),
        delta_ms=_as_int(params.get("delta_ms")),
        dry_run=bool(dry_run),
    )
    return ok_result("clip.slip", result, dry_run=bool(dry_run), changed=False if dry_run else bool(result.get("changed")))


def _clip_roll(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    missing = [key for key in ("track_id", "left_clip_id", "right_clip_id", "delta_ms") if key not in params]
    if missing:
        return error_result("clip.roll", f"missing params: {', '.join(missing)}", dry_run=dry_run)
    result = registry.adapter.roll_edit(
        track_id=_as_int(params.get("track_id")),
        left_clip_id=_as_int(params.get("left_clip_id")),
        right_clip_id=_as_int(params.get("right_clip_id")),
        delta_ms=_as_int(params.get("delta_ms")),
        dry_run=bool(dry_run),
    )
    return ok_result("clip.roll", result, dry_run=bool(dry_run), changed=False if dry_run else bool(result.get("changed")))


def _clip_slide(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    missing = [key for key in ("track_id", "clip_id", "delta_ms") if key not in params]
    if missing:
        return error_result("clip.slide", f"missing params: {', '.join(missing)}", dry_run=dry_run)
    result = registry.adapter.slide_clip(
        track_id=_as_int(params.get("track_id")),
        clip_id=_as_int(params.get("clip_id")),
        delta_ms=_as_int(params.get("delta_ms")),
        dry_run=bool(dry_run),
    )
    return ok_result("clip.slide", result, dry_run=bool(dry_run), changed=False if dry_run else bool(result.get("changed")))


def _clip_set_speed(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    missing = [key for key in ("track_id", "clip_id", "speed") if key not in params]
    if missing:
        return error_result("clip.set_speed", f"missing params: {', '.join(missing)}", dry_run=dry_run)
    if dry_run:
        return registry._dry_result("clip.set_speed", params, "clip speed would change")
    return ok_result(
        "clip.set_speed",
        registry.adapter.set_clip_speed(
            track_id=_as_int(params.get("track_id")),
            clip_id=_as_int(params.get("clip_id")),
            speed=_as_float(params.get("speed"), 1.0),
        ),
        changed=True,
    )


def _clip_set_fade(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    missing = [key for key in ("track_id", "clip_id") if key not in params]
    if missing:
        return error_result("clip.set_fade", f"missing params: {', '.join(missing)}", dry_run=dry_run)
    if dry_run:
        return registry._dry_result("clip.set_fade", params, "clip fades would change")
    return ok_result(
        "clip.set_fade",
        registry.adapter.set_clip_fade(
            track_id=_as_int(params.get("track_id")),
            clip_id=_as_int(params.get("clip_id")),
            fade_in_ms=_as_int(params.get("fade_in_ms", 0)),
            fade_out_ms=_as_int(params.get("fade_out_ms", 0)),
            replace_existing=bool(params.get("replace_existing", True)),
        ),
        changed=True,
    )
