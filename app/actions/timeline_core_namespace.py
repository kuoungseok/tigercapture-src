"""Core timeline transport, range, zoom, snap, gap, and history actions."""
from __future__ import annotations

from typing import Any, Mapping

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


def register_timeline_core_actions(registry: Any) -> None:
    """Register non-clip timeline transport, range, zoom, snap, gap, and history actions."""
    registry.register(
        ActionSpec(
            "timeline.set_playhead",
            "Move the timeline playhead.",
            "timeline",
            params_schema=schema_object({"ms": {"type": "integer", "minimum": 0}}, required=("ms",)),
            mutating=True,
            requires_owner=True,
            undo_label="Set playhead",
        ),
        lambda params, dry: _timeline_set_playhead(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.play",
            "Start timeline playback.",
            "timeline",
            mutating=True,
            requires_owner=True,
            undo_label="Play timeline",
        ),
        lambda params, dry: _timeline_play(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.pause",
            "Pause timeline playback.",
            "timeline",
            mutating=True,
            requires_owner=True,
            undo_label="Pause timeline",
        ),
        lambda params, dry: _timeline_pause(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.stop",
            "Stop timeline playback.",
            "timeline",
            mutating=True,
            requires_owner=True,
            undo_label="Stop timeline",
        ),
        lambda params, dry: _timeline_stop(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.step_frames",
            "Move the playhead by a signed frame count.",
            "timeline",
            params_schema=schema_object(
                {
                    "frames": {"type": "integer"},
                    "fps": {"type": "number", "minimum": 1},
                },
                required=("frames",),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Step frames",
        ),
        lambda params, dry: _timeline_step_frames(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.set_shuttle_rate",
            "Set positive shuttle playback rate, or pause with zero/negative rate.",
            "timeline",
            params_schema=schema_object({"rate": {"type": "number"}}, required=("rate",)),
            mutating=True,
            requires_owner=True,
            undo_label="Set shuttle rate",
        ),
        lambda params, dry: _timeline_set_shuttle_rate(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.set_in",
            "Set the global timeline In marker.",
            "timeline",
            params_schema=schema_object({"ms": {"type": "integer", "minimum": 0}}, required=("ms",)),
            mutating=True,
            requires_owner=True,
            undo_label="Set timeline In",
        ),
        lambda params, dry: _timeline_set_in(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.set_out",
            "Set the global timeline Out marker.",
            "timeline",
            params_schema=schema_object({"ms": {"type": "integer", "minimum": 0}}, required=("ms",)),
            mutating=True,
            requires_owner=True,
            undo_label="Set timeline Out",
        ),
        lambda params, dry: _timeline_set_out(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.clear_in_out",
            "Clear the global timeline In/Out range.",
            "timeline",
            mutating=True,
            requires_owner=True,
            undo_label="Clear timeline In/Out",
        ),
        lambda params, dry: _timeline_clear_in_out(registry, params, dry),
    )
    registry.register_adapter_action(
        "timeline.set_in_out_from_selection",
        "Set global timeline In/Out markers from the selected video clip span.",
        "timeline",
        "set_in_out_from_selection",
        mutating=True,
        requires_owner=True,
        undo_label="Set In/Out from selection",
        dry_summary="timeline In/Out would be set from selection",
    )
    registry.register(
        ActionSpec(
            "timeline.jump_in_out",
            "Move the playhead to the global timeline In or Out marker.",
            "timeline",
            params_schema=schema_object({"edge": {"type": "string"}}),
            mutating=True,
            requires_owner=True,
            undo_label="Jump to timeline In/Out",
        ),
        lambda params, dry: _timeline_jump_in_out(registry, params, dry),
    )
    registry.register_adapter_action(
        "timeline.track_targets",
        "Return active timeline track targets.",
        "timeline",
        "track_targets",
        mutating=False,
        changed=False,
        dry_summary="timeline track targets would be listed",
    )
    registry.register_adapter_action(
        "timeline.track_target.set",
        "Enable or disable a timeline track target.",
        "timeline",
        "set_track_target",
        params_schema=schema_object(
            {
                "kind": {"type": "string", "enum": ["video", "audio"]},
                "track_id": {"type": "integer"},
                "enabled": {"type": "boolean"},
                "exclusive": {"type": "boolean"},
            },
            required=("track_id",),
            additional_properties=True,
        ),
        required=("track_id",),
        undo_label="Set track target",
        dry_summary="timeline track target would change",
    )
    registry.register_adapter_action(
        "timeline.track_target.clear",
        "Clear timeline track targets.",
        "timeline",
        "clear_track_targets",
        params_schema=schema_object(
            {"kind": {"type": "string", "enum": ["video", "audio", "all"]}},
            additional_properties=True,
        ),
        undo_label="Clear track targets",
        dry_summary="timeline track targets would clear",
    )
    registry.register(
        ActionSpec(
            "timeline.jump_edit_point",
            "Move the playhead to the next or previous edit point.",
            "timeline",
            params_schema=schema_object(
                {
                    "direction": {"type": "string", "enum": ["next", "previous", "prev"]},
                    "from_ms": {"type": "integer", "minimum": 0},
                    "track_kind": {"type": "string", "enum": ["video", "audio", "all"]},
                    "track_id": {"type": "integer"},
                    "include_markers": {"type": "boolean"},
                    "tolerance_ms": {"type": "integer", "minimum": 0},
                }
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Jump edit point",
        ),
        lambda params, dry: _timeline_jump_edit_point(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.play_range",
            "Play a bounded timeline range and optionally restore the playhead.",
            "timeline",
            params_schema=schema_object(
                {
                    "start_ms": {"type": "integer", "minimum": 0},
                    "end_ms": {"type": "integer", "minimum": 1},
                    "return_to_ms": {"type": "integer", "minimum": 0},
                    "restore_playhead": {"type": "boolean"},
                },
                required=("start_ms", "end_ms"),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Play timeline range",
        ),
        lambda params, dry: _timeline_play_range(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.play_clip_range",
            "Audition the selected, explicit, or current clip range and restore the playhead afterward.",
            "timeline",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "at_ms": {"type": "integer", "minimum": 0},
                    "restore_playhead": {"type": "boolean"},
                }
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Play clip range",
        ),
        lambda params, dry: _timeline_play_clip_range(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.set_zoom",
            "Set timeline zoom in pixels per second.",
            "timeline",
            params_schema=schema_object({"px_per_sec": {"type": "number", "minimum": 1}}, required=("px_per_sec",)),
            mutating=True,
            requires_owner=True,
            undo_label="Set timeline zoom",
        ),
        lambda params, dry: _timeline_set_zoom(registry, params, dry),
    )
    registry.register_adapter_action(
        "timeline.fit",
        "Fit timeline contents to the visible timeline width.",
        "timeline",
        "fit_timeline",
        params_schema=schema_object({"visible_width": {"type": "integer", "minimum": 120}}),
        undo_label="Fit timeline",
        dry_summary="timeline zoom would fit visible content",
    )
    registry.register_adapter_action(
        "timeline.snap.get",
        "Return timeline snapping settings.",
        "timeline",
        "snap_settings",
        mutating=False,
        changed=False,
        dry_summary="timeline snap settings would be read",
    )
    registry.register_adapter_action(
        "timeline.snap.set",
        "Set timeline snapping settings.",
        "timeline",
        "set_snap_settings",
        params_schema=schema_object(
            {
                "enabled": {"type": "boolean"},
                "snap_ms": {"type": "integer", "minimum": 0},
                "include_clip_edges": {"type": "boolean"},
                "include_playhead": {"type": "boolean"},
                "include_markers": {"type": "boolean"},
                "include_edit_points": {"type": "boolean"},
            },
            additional_properties=True,
        ),
        undo_label="Set timeline snap",
        dry_summary="timeline snap settings would change",
    )
    registry.register_adapter_action(
        "timeline.snap.toggle",
        "Toggle timeline snapping.",
        "timeline",
        "toggle_snap",
        params_schema=schema_object({"enabled": {"type": "boolean"}}, additional_properties=True),
        undo_label="Toggle timeline snap",
        dry_summary="timeline snap would toggle",
    )
    registry.register_adapter_action(
        "timeline.edge_issues",
        "List timeline micro gaps and overlaps.",
        "timeline",
        "timeline_edge_issues",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "frame_ms": {"type": "integer", "minimum": 1},
            },
            additional_properties=True,
        ),
        mutating=False,
        changed=False,
        dry_summary="timeline edge issues would be listed",
    )
    registry.register_adapter_action(
        "timeline.gaps",
        "List timeline gaps between clips.",
        "timeline",
        "timeline_gaps",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "min_gap_ms": {"type": "integer", "minimum": 1},
            },
            additional_properties=True,
        ),
        mutating=False,
        changed=False,
        dry_summary="timeline gaps would be listed",
    )
    registry.register(
        ActionSpec(
            "timeline.close_gap",
            "Close one timeline gap on the targeted video track.",
            "timeline",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "at_ms": {"type": "integer", "minimum": 0},
                    "gap_index": {"type": "integer", "minimum": 0},
                    "min_gap_ms": {"type": "integer", "minimum": 1},
                }
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Close timeline gap",
        ),
        lambda params, dry: _timeline_close_gap(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.close_all_gaps",
            "Close all timeline gaps on targeted video tracks.",
            "timeline",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "min_gap_ms": {"type": "integer", "minimum": 1},
                }
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Close all timeline gaps",
        ),
        lambda params, dry: _timeline_close_all_gaps(registry, params, dry),
    )
    registry.register_adapter_action(
        "history.undo",
        "Undo the previous editor history step.",
        "history",
        "undo_history",
        undo_label="Undo",
        dry_summary="previous editor history step would be restored",
    )
    registry.register_adapter_action(
        "history.redo",
        "Redo the next editor history step.",
        "history",
        "redo_history",
        undo_label="Redo",
        dry_summary="next editor history step would be restored",
    )


def _timeline_set_playhead(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    if "ms" not in params:
        return error_result("timeline.set_playhead", "ms is required", dry_run=dry_run)
    if dry_run:
        return registry._dry_result("timeline.set_playhead", params, "playhead would move")
    return ok_result("timeline.set_playhead", registry.adapter.set_playhead(_as_int(params.get("ms"), 0)), changed=True)


def _timeline_play(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    if dry_run:
        return registry._dry_result("timeline.play", params, "timeline playback would start")
    return ok_result("timeline.play", registry.adapter.transport("play"), changed=True)


def _timeline_pause(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    if dry_run:
        return registry._dry_result("timeline.pause", params, "timeline playback would pause")
    return ok_result("timeline.pause", registry.adapter.transport("pause"), changed=True)


def _timeline_stop(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    if dry_run:
        return registry._dry_result("timeline.stop", params, "timeline playback would stop")
    return ok_result("timeline.stop", registry.adapter.transport("stop"), changed=True)


def _timeline_step_frames(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    if "frames" not in params:
        return error_result("timeline.step_frames", "frames is required", dry_run=dry_run)
    frames = _as_int(params.get("frames"), 0)
    fps = _as_float(params.get("fps", 30.0), 30.0)
    if dry_run:
        current = registry.adapter._current_playhead_ms()
        target = max(0, current + int(round((frames * 1000.0) / max(1.0, fps))))
        return ok_result(
            "timeline.step_frames",
            {"frames": frames, "fps": max(1.0, fps), "from_ms": current, "target_ms": target},
            dry_run=True,
            changed=False,
        )
    return ok_result("timeline.step_frames", registry.adapter.step_frames(frames, fps=fps), changed=True)


def _timeline_set_shuttle_rate(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    if "rate" not in params:
        return error_result("timeline.set_shuttle_rate", "rate is required", dry_run=dry_run)
    rate = _as_float(params.get("rate"), 1.0)
    if dry_run:
        return registry._dry_result("timeline.set_shuttle_rate", {"rate": rate}, "timeline shuttle rate would change")
    return ok_result("timeline.set_shuttle_rate", registry.adapter.transport("shuttle", rate=rate), changed=True)


def _timeline_set_in(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    if "ms" not in params:
        return error_result("timeline.set_in", "ms is required", dry_run=dry_run)
    if dry_run:
        return registry._dry_result("timeline.set_in", params, "timeline In marker would move")
    return ok_result("timeline.set_in", registry.adapter.set_in_out(in_ms=_as_int(params.get("ms"), 0)), changed=True)


def _timeline_set_out(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    if "ms" not in params:
        return error_result("timeline.set_out", "ms is required", dry_run=dry_run)
    if dry_run:
        return registry._dry_result("timeline.set_out", params, "timeline Out marker would move")
    return ok_result("timeline.set_out", registry.adapter.set_in_out(out_ms=_as_int(params.get("ms"), 0)), changed=True)


def _timeline_clear_in_out(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    if dry_run:
        return registry._dry_result("timeline.clear_in_out", params, "timeline In/Out range would clear")
    return ok_result("timeline.clear_in_out", registry.adapter.clear_in_out(), changed=True)


def _timeline_jump_in_out(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    try:
        result = registry.adapter.jump_in_out(edge=str(params.get("edge") or "in"), dry_run=bool(dry_run))
    except Exception as exc:
        return error_result("timeline.jump_in_out", str(exc), dry_run=dry_run)
    return ok_result("timeline.jump_in_out", result, dry_run=bool(dry_run), changed=False if dry_run else bool(result.get("moved")))


def _timeline_jump_edit_point(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    result = registry.adapter.jump_edit_point(
        direction=str(params.get("direction") or "next"),
        from_ms=_as_int(params.get("from_ms")) if "from_ms" in params else None,
        track_kind=str(params.get("track_kind") or "video"),
        track_id=_as_int(params.get("track_id")) if "track_id" in params else None,
        include_markers=bool(params.get("include_markers", False)),
        tolerance_ms=_as_int(params.get("tolerance_ms", 1), 1),
        dry_run=bool(dry_run),
    )
    return ok_result("timeline.jump_edit_point", result, dry_run=bool(dry_run), changed=False if dry_run else bool(result.get("moved")))


def _timeline_play_range(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    missing = [key for key in ("start_ms", "end_ms") if key not in params]
    if missing:
        return error_result("timeline.play_range", f"missing params: {', '.join(missing)}", dry_run=dry_run)
    start = _as_int(params.get("start_ms"), 0)
    end = _as_int(params.get("end_ms"), start + 1)
    return_to = _as_int(params.get("return_to_ms")) if "return_to_ms" in params else None
    restore = bool(params.get("restore_playhead", True))
    if dry_run:
        return ok_result(
            "timeline.play_range",
            {"start_ms": start, "end_ms": max(start + 1, end), "return_to_ms": return_to, "restore_playhead": restore},
            dry_run=True,
            changed=False,
        )
    return ok_result(
        "timeline.play_range",
        registry.adapter.play_range(start_ms=start, end_ms=end, return_to_ms=return_to, restore_playhead=restore),
        changed=True,
    )


def _timeline_play_clip_range(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    track_id = _as_int(params.get("track_id")) if "track_id" in params else None
    clip_id = _as_int(params.get("clip_id")) if "clip_id" in params else None
    at_ms = _as_int(params.get("at_ms")) if "at_ms" in params else None
    restore = bool(params.get("restore_playhead", True))
    if dry_run:
        try:
            audition = registry.adapter.clip_audition_range(track_id=track_id, clip_id=clip_id, at_ms=at_ms)
        except Exception as exc:
            return error_result("timeline.play_clip_range", str(exc), dry_run=True)
        return ok_result("timeline.play_clip_range", {"audition": audition, "restore_playhead": restore}, dry_run=True, changed=False)
    return ok_result(
        "timeline.play_clip_range",
        registry.adapter.play_clip_range(track_id=track_id, clip_id=clip_id, at_ms=at_ms, restore_playhead=restore),
        changed=True,
    )


def _timeline_set_zoom(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    if "px_per_sec" not in params:
        return error_result("timeline.set_zoom", "px_per_sec is required", dry_run=dry_run)
    if dry_run:
        return registry._dry_result("timeline.set_zoom", params, "timeline zoom would change")
    result = registry.adapter.set_zoom(_as_float(params.get("px_per_sec"), 40.0))
    return ok_result("timeline.set_zoom", result, changed=bool(result.get("changed")))


def _timeline_close_gap(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    try:
        result = registry.adapter.close_timeline_gap(
            track_id=_as_int(params.get("track_id"), -1) if "track_id" in params else None,
            at_ms=_as_int(params.get("at_ms"), -1) if "at_ms" in params else None,
            gap_index=_as_int(params.get("gap_index"), -1) if "gap_index" in params else None,
            min_gap_ms=_as_int(params.get("min_gap_ms"), 1),
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        return error_result("timeline.close_gap", str(exc), dry_run=dry_run)
    return ok_result("timeline.close_gap", result, dry_run=bool(dry_run), changed=False if dry_run else bool(result.get("shifted_clip_count")))


def _timeline_close_all_gaps(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    try:
        result = registry.adapter.close_all_timeline_gaps(
            track_id=_as_int(params.get("track_id"), -1) if "track_id" in params else None,
            min_gap_ms=_as_int(params.get("min_gap_ms"), 1),
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        return error_result("timeline.close_all_gaps", str(exc), dry_run=dry_run)
    return ok_result(
        "timeline.close_all_gaps",
        result,
        dry_run=bool(dry_run),
        changed=False if dry_run else bool(result.get("shifted_clip_count")),
    )
