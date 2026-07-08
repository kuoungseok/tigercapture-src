"""Source/Record monitor workbench contracts.

The editor already has Source/Record monitor actions.  This module turns those
raw states into a product-facing view model so UI, AI actions, MCP, and QA can
agree on the same 3-point editing affordances.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


SOURCE_RECORD_SCHEMA = "tigerstudio.nle.source_record_workbench.v1"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _duration_label(ms: int) -> str:
    total = max(0, _int(ms, 0)) // 1000
    minutes, seconds = divmod(total, 60)
    return f"{minutes}:{seconds:02d}"


def build_source_record_workbench(
    *,
    source_monitor: Mapping[str, Any] | None = None,
    record_monitor: Mapping[str, Any] | None = None,
    track_targets: Mapping[str, Any] | None = None,
    playhead_ms: int = 0,
    edit_points: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a UI-ready Source/Record monitor state contract."""

    source = dict(source_monitor or {})
    record = dict(record_monitor or {})
    targets = dict(track_targets or {})
    source_loaded = _bool(source.get("loaded"))
    source_duration = max(0, _int(source.get("source_duration_ms", source.get("duration_ms", 0)), 0))
    source_in = max(0, _int(source.get("source_in_ms"), 0))
    source_out = _int(source.get("source_out_ms"), source_duration)
    if source_duration > 0:
        source_out = max(source_in, min(source_duration, source_out or source_duration))
    source_range = max(0, source_out - source_in)
    record_has_in = _bool(record.get("has_in"))
    record_has_out = _bool(record.get("has_out"))
    record_in = max(0, _int(record.get("in_ms"), _int(playhead_ms, 0))) if record_has_in else max(0, _int(playhead_ms, 0))
    record_out = max(record_in, _int(record.get("out_ms"), record_in + source_range)) if record_has_out else record_in + source_range
    record_range = max(0, record_out - record_in)
    video_targets = [int(value) for value in list(targets.get("video") or []) if _int(value, -1) >= 0]
    audio_targets = [int(value) for value in list(targets.get("audio") or []) if _int(value, -1) >= 0]
    can_insert = source_loaded and source_range > 0 and bool(video_targets or source.get("kind") == "video")
    can_overwrite = can_insert and record_range > 0
    edit_rows = [dict(row) for row in list(edit_points or []) if isinstance(row, Mapping)]
    next_edit = None
    previous_edit = None
    playhead = max(0, _int(playhead_ms, 0))
    for row in sorted(edit_rows, key=lambda item: _int(item.get("ms"), 0)):
        ms = _int(row.get("ms"), 0)
        if ms > playhead and next_edit is None:
            next_edit = dict(row)
        if ms < playhead:
            previous_edit = dict(row)
    return {
        "schema": SOURCE_RECORD_SCHEMA,
        "playhead_ms": playhead,
        "source": {
            "loaded": source_loaded,
            "media_id": str(source.get("media_id") or ""),
            "name": str(source.get("name") or ""),
            "path": str(source.get("path") or ""),
            "kind": str(source.get("kind") or "video"),
            "duration_ms": source_duration,
            "in_ms": source_in,
            "out_ms": source_out,
            "range_ms": source_range,
            "range_label": _duration_label(source_range),
        },
        "record": {
            "has_in": record_has_in,
            "has_out": record_has_out,
            "in_ms": record_in,
            "out_ms": record_out,
            "range_ms": record_range,
            "range_label": _duration_label(record_range),
        },
        "patching": {
            "video_targets": video_targets,
            "audio_targets": audio_targets,
            "has_video_target": bool(video_targets),
            "has_audio_target": bool(audio_targets),
        },
        "commands": {
            "insert_enabled": can_insert,
            "overwrite_enabled": can_overwrite,
            "load_source_enabled": True,
            "mark_source_in_enabled": source_loaded,
            "mark_source_out_enabled": source_loaded,
            "mark_record_in_enabled": True,
            "mark_record_out_enabled": True,
        },
        "keyboard": {
            "jkl_transport": True,
            "mark_in": "I",
            "mark_out": "O",
            "insert": ",",
            "overwrite": ".",
        },
        "edit_navigation": {
            "previous": previous_edit,
            "next": next_edit,
            "count": len(edit_rows),
        },
        "readiness": {
            "three_point_ready": can_insert,
            "overwrite_ready": can_overwrite,
            "needs_source": not source_loaded,
            "needs_video_target": source_loaded and not bool(video_targets),
        },
    }


def build_source_record_edit_decision_preview(
    *,
    source_monitor: Mapping[str, Any] | None = None,
    record_monitor: Mapping[str, Any] | None = None,
    track_targets: Mapping[str, Any] | None = None,
    playhead_ms: int = 0,
    mode: str = "insert",
) -> dict[str, Any]:
    """Return a reviewed 3-point edit decision before timeline mutation."""

    workbench = build_source_record_workbench(
        source_monitor=source_monitor,
        record_monitor=record_monitor,
        track_targets=track_targets,
        playhead_ms=playhead_ms,
    )
    source = workbench.get("source") if isinstance(workbench.get("source"), Mapping) else {}
    record = workbench.get("record") if isinstance(workbench.get("record"), Mapping) else {}
    patching = workbench.get("patching") if isinstance(workbench.get("patching"), Mapping) else {}
    commands = workbench.get("commands") if isinstance(workbench.get("commands"), Mapping) else {}
    normalized_mode = str(mode or "insert").strip().lower()
    if normalized_mode not in {"insert", "overwrite"}:
        normalized_mode = "insert"
    source_range = _int(source.get("range_ms"), 0)
    record_range = _int(record.get("range_ms"), 0)
    target_video = list(patching.get("video_targets") or [])
    target_audio = list(patching.get("audio_targets") or [])
    warnings: list[str] = []
    if not bool(source.get("loaded")):
        warnings.append("source_not_loaded")
    if source_range <= 0:
        warnings.append("source_range_empty")
    if not target_video and str(source.get("kind") or "video") == "video":
        warnings.append("no_video_target")
    if normalized_mode == "overwrite" and record_range <= 0:
        warnings.append("record_range_empty")
    enabled = bool(commands.get("insert_enabled")) if normalized_mode == "insert" else bool(commands.get("overwrite_enabled"))
    safe_to_apply = enabled and not warnings
    record_in = _int(record.get("in_ms"), _int(playhead_ms, 0))
    duration = source_range if normalized_mode == "insert" else min(source_range, record_range or source_range)
    return {
        "schema": SOURCE_RECORD_SCHEMA,
        "kind": "source_record_edit_decision_preview",
        "mode": normalized_mode,
        "ready": safe_to_apply,
        "safe_to_apply": safe_to_apply,
        "warnings": warnings,
        "decision": {
            "source_media_id": str(source.get("media_id") or ""),
            "source_path": str(source.get("path") or ""),
            "source_in_ms": _int(source.get("in_ms"), 0),
            "source_out_ms": _int(source.get("in_ms"), 0) + duration,
            "record_in_ms": record_in,
            "record_out_ms": record_in + duration,
            "duration_ms": duration,
            "video_targets": target_video,
            "audio_targets": target_audio,
            "ripple_timeline": normalized_mode == "insert",
            "replace_existing": normalized_mode == "overwrite",
        },
        "ui": {
            "primary_label": "Insert" if normalized_mode == "insert" else "Overwrite",
            "duration_label": _duration_label(duration),
            "review_required": True,
        },
    }


def build_source_record_patch_matrix(
    *,
    source_monitor: Mapping[str, Any] | None = None,
    record_monitor: Mapping[str, Any] | None = None,
    track_targets: Mapping[str, Any] | None = None,
    playhead_ms: int = 0,
    edit_points: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a Source/Record patching matrix for 3-point editing UI."""

    workbench = build_source_record_workbench(
        source_monitor=source_monitor,
        record_monitor=record_monitor,
        track_targets=track_targets,
        playhead_ms=playhead_ms,
        edit_points=edit_points,
    )
    source = workbench.get("source") if isinstance(workbench.get("source"), Mapping) else {}
    record = workbench.get("record") if isinstance(workbench.get("record"), Mapping) else {}
    patching = workbench.get("patching") if isinstance(workbench.get("patching"), Mapping) else {}
    commands = workbench.get("commands") if isinstance(workbench.get("commands"), Mapping) else {}
    insert = build_source_record_edit_decision_preview(
        source_monitor=source_monitor,
        record_monitor=record_monitor,
        track_targets=track_targets,
        playhead_ms=playhead_ms,
        mode="insert",
    )
    overwrite = build_source_record_edit_decision_preview(
        source_monitor=source_monitor,
        record_monitor=record_monitor,
        track_targets=track_targets,
        playhead_ms=playhead_ms,
        mode="overwrite",
    )
    video_targets = [int(value) for value in list(patching.get("video_targets") or []) if _int(value, -1) >= 0]
    audio_targets = [int(value) for value in list(patching.get("audio_targets") or []) if _int(value, -1) >= 0]
    source_kind = str(source.get("kind") or "video")
    rows = [
        {
            "kind": "video",
            "source_available": bool(source.get("loaded")) and source_kind in {"video", "image", "actor", "3d"},
            "target_ids": video_targets,
            "target_count": len(video_targets),
            "patched": bool(video_targets),
            "required": source_kind in {"video", "image", "actor", "3d"},
        },
        {
            "kind": "audio",
            "source_available": bool(source.get("loaded")) and source_kind in {"video", "audio"},
            "target_ids": audio_targets,
            "target_count": len(audio_targets),
            "patched": bool(audio_targets),
            "required": source_kind == "audio",
        },
    ]
    warnings: list[str] = []
    if not bool(source.get("loaded")):
        warnings.append("source_not_loaded")
    if _int(source.get("range_ms"), 0) <= 0:
        warnings.append("source_range_empty")
    if any(bool(row.get("required")) and not bool(row.get("patched")) for row in rows):
        warnings.append("required_track_not_patched")
    return {
        "schema": SOURCE_RECORD_SCHEMA,
        "kind": "source_record_patch_matrix",
        "ready": bool(commands.get("insert_enabled")) and not warnings,
        "source": dict(source),
        "record": dict(record),
        "rows": rows,
        "edit_cards": [
            {
                "mode": "insert",
                "enabled": bool(commands.get("insert_enabled")),
                "safe_to_apply": bool(insert.get("safe_to_apply")),
                "duration_ms": _int((insert.get("decision") or {}).get("duration_ms"), 0),
                "warnings": list(insert.get("warnings") or []),
            },
            {
                "mode": "overwrite",
                "enabled": bool(commands.get("overwrite_enabled")),
                "safe_to_apply": bool(overwrite.get("safe_to_apply")),
                "duration_ms": _int((overwrite.get("decision") or {}).get("duration_ms"), 0),
                "warnings": list(overwrite.get("warnings") or []),
            },
        ],
        "warnings": warnings,
        "commands": {
            "insert_enabled": bool(commands.get("insert_enabled")),
            "overwrite_enabled": bool(commands.get("overwrite_enabled")),
            "toggle_video_patch_enabled": True,
            "toggle_audio_patch_enabled": True,
            "show_patch_matrix_enabled": True,
        },
    }


def build_source_record_monitor_layout(
    *,
    source_monitor: Mapping[str, Any] | None = None,
    record_monitor: Mapping[str, Any] | None = None,
    track_targets: Mapping[str, Any] | None = None,
    playhead_ms: int = 0,
    edit_points: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a product-facing Source/Record visual layout contract.

    The workbench and patch matrix are the raw state.  This view model is the
    piece a Qt panel, popout, or AI review card can render without rediscovering
    how the two monitors, patching buttons, edit cards, and keyboard hints fit
    together.
    """

    workbench = build_source_record_workbench(
        source_monitor=source_monitor,
        record_monitor=record_monitor,
        track_targets=track_targets,
        playhead_ms=playhead_ms,
        edit_points=edit_points,
    )
    patch = build_source_record_patch_matrix(
        source_monitor=source_monitor,
        record_monitor=record_monitor,
        track_targets=track_targets,
        playhead_ms=playhead_ms,
        edit_points=edit_points,
    )
    insert = build_source_record_edit_decision_preview(
        source_monitor=source_monitor,
        record_monitor=record_monitor,
        track_targets=track_targets,
        playhead_ms=playhead_ms,
        mode="insert",
    )
    overwrite = build_source_record_edit_decision_preview(
        source_monitor=source_monitor,
        record_monitor=record_monitor,
        track_targets=track_targets,
        playhead_ms=playhead_ms,
        mode="overwrite",
    )
    source = workbench.get("source") if isinstance(workbench.get("source"), Mapping) else {}
    record = workbench.get("record") if isinstance(workbench.get("record"), Mapping) else {}
    return {
        "schema": SOURCE_RECORD_SCHEMA,
        "kind": "source_record_monitor_layout",
        "ready": bool(workbench.get("readiness", {}).get("three_point_ready")),
        "layout": {
            "panes": [
                {
                    "id": "source",
                    "title": "Source",
                    "loaded": bool(source.get("loaded")),
                    "time_range": {
                        "in_ms": _int(source.get("in_ms"), 0),
                        "out_ms": _int(source.get("out_ms"), 0),
                        "duration_ms": _int(source.get("range_ms"), 0),
                        "label": str(source.get("range_label") or ""),
                    },
                    "badges": ["SRC", str(source.get("kind") or "video").upper()],
                },
                {
                    "id": "record",
                    "title": "Record",
                    "loaded": True,
                    "time_range": {
                        "in_ms": _int(record.get("in_ms"), 0),
                        "out_ms": _int(record.get("out_ms"), 0),
                        "duration_ms": _int(record.get("range_ms"), 0),
                        "label": str(record.get("range_label") or ""),
                    },
                    "badges": ["REC"],
                },
            ],
            "patch_rows": list(patch.get("rows") or []),
            "edit_cards": [
                {
                    "id": "insert",
                    "label": "Insert",
                    "enabled": bool((insert.get("ui") or {}).get("primary_label")),
                    "safe_to_apply": bool(insert.get("safe_to_apply")),
                    "duration_ms": _int((insert.get("decision") or {}).get("duration_ms"), 0),
                    "warnings": list(insert.get("warnings") or []),
                },
                {
                    "id": "overwrite",
                    "label": "Overwrite",
                    "enabled": bool((overwrite.get("ui") or {}).get("primary_label")),
                    "safe_to_apply": bool(overwrite.get("safe_to_apply")),
                    "duration_ms": _int((overwrite.get("decision") or {}).get("duration_ms"), 0),
                    "warnings": list(overwrite.get("warnings") or []),
                },
            ],
        },
        "transport_hints": {
            "jkl_transport": True,
            "mark_in": "I",
            "mark_out": "O",
            "insert": ",",
            "overwrite": ".",
        },
        "warnings": sorted(set(list(patch.get("warnings") or []) + list(insert.get("warnings") or []) + list(overwrite.get("warnings") or []))),
        "commands": {
            "mark_source_in_enabled": bool((workbench.get("commands") or {}).get("mark_source_in_enabled")),
            "mark_source_out_enabled": bool((workbench.get("commands") or {}).get("mark_source_out_enabled")),
            "mark_record_in_enabled": bool((workbench.get("commands") or {}).get("mark_record_in_enabled")),
            "mark_record_out_enabled": bool((workbench.get("commands") or {}).get("mark_record_out_enabled")),
            "insert_enabled": bool((workbench.get("commands") or {}).get("insert_enabled")),
            "overwrite_enabled": bool((workbench.get("commands") or {}).get("overwrite_enabled")),
        },
    }


def build_source_record_apply_board(
    *,
    source_monitor: Mapping[str, Any] | None = None,
    record_monitor: Mapping[str, Any] | None = None,
    track_targets: Mapping[str, Any] | None = None,
    playhead_ms: int = 0,
    edit_points: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a review/apply board for 3-point edit decisions.

    The board keeps insert/overwrite destructive intent explicit: the UI can
    show both outcomes, warnings, target patching, and the exact action payload
    before a user or AI applies anything to the timeline.
    """

    layout = build_source_record_monitor_layout(
        source_monitor=source_monitor,
        record_monitor=record_monitor,
        track_targets=track_targets,
        playhead_ms=playhead_ms,
        edit_points=edit_points,
    )
    patch = build_source_record_patch_matrix(
        source_monitor=source_monitor,
        record_monitor=record_monitor,
        track_targets=track_targets,
        playhead_ms=playhead_ms,
        edit_points=edit_points,
    )
    previews = {
        mode: build_source_record_edit_decision_preview(
            source_monitor=source_monitor,
            record_monitor=record_monitor,
            track_targets=track_targets,
            playhead_ms=playhead_ms,
            mode=mode,
        )
        for mode in ("insert", "overwrite")
    }
    decisions: list[dict[str, Any]] = []
    for mode, preview in previews.items():
        decision = preview.get("decision") if isinstance(preview.get("decision"), Mapping) else {}
        warnings = list(preview.get("warnings") or [])
        action_id = "timeline.three_point_insert" if mode == "insert" else "timeline.three_point_overwrite"
        decisions.append(
            {
                "id": mode,
                "label": "Insert" if mode == "insert" else "Overwrite",
                "action_id": action_id,
                "safe_to_apply": bool(preview.get("safe_to_apply")),
                "destructive": mode == "overwrite",
                "requires_confirmation": mode == "overwrite",
                "duration_ms": _int(decision.get("duration_ms"), 0),
                "source_range": {
                    "in_ms": _int(decision.get("source_in_ms"), 0),
                    "out_ms": _int(decision.get("source_out_ms"), 0),
                },
                "record_range": {
                    "in_ms": _int(decision.get("record_in_ms"), 0),
                    "out_ms": _int(decision.get("record_out_ms"), 0),
                },
                "targets": {
                    "video": list(decision.get("video_targets") or []),
                    "audio": list(decision.get("audio_targets") or []),
                },
                "warnings": warnings,
                "action_params": {
                    "target_track_id": (list(decision.get("video_targets") or []) or [None])[0],
                    "target_audio_track_id": (list(decision.get("audio_targets") or []) or [None])[0],
                },
            }
        )
    recommended = next((row for row in decisions if row["id"] == "insert" and row["safe_to_apply"]), decisions[0])
    warnings = sorted(
        {
            str(warning)
            for row in decisions
            for warning in list(row.get("warnings") or [])
            if str(warning or "").strip()
        }
        | {str(warning) for warning in list(patch.get("warnings") or []) if str(warning or "").strip()}
    )
    return {
        "schema": SOURCE_RECORD_SCHEMA,
        "kind": "source_record_apply_board",
        "ready": any(bool(row.get("safe_to_apply")) for row in decisions),
        "review_required": True,
        "layout_ready": bool(layout.get("ready")),
        "patch_matrix_ready": bool(patch.get("ready")),
        "recommended_action": recommended["id"],
        "decisions": decisions,
        "warnings": warnings,
        "sections": [
            {
                "id": "monitors",
                "title": "Source / Record",
                "rows": list((layout.get("layout") or {}).get("panes") or []),
            },
            {
                "id": "patching",
                "title": "Patch targets",
                "rows": list(patch.get("rows") or []),
            },
            {
                "id": "apply",
                "title": "Review actions",
                "rows": decisions,
            },
        ],
        "commands": {
            "preview_insert_enabled": True,
            "preview_overwrite_enabled": True,
            "apply_insert_enabled": bool(previews["insert"].get("safe_to_apply")),
            "apply_overwrite_enabled": bool(previews["overwrite"].get("safe_to_apply")),
            "overwrite_requires_confirm_destructive": True,
        },
    }


def build_source_record_keyboard_overlay(
    *,
    source_monitor: Mapping[str, Any] | None = None,
    record_monitor: Mapping[str, Any] | None = None,
    track_targets: Mapping[str, Any] | None = None,
    playhead_ms: int = 0,
    edit_points: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return keyboard/transport hints for a Source/Record monitor panel."""

    layout = build_source_record_monitor_layout(
        source_monitor=source_monitor,
        record_monitor=record_monitor,
        track_targets=track_targets,
        playhead_ms=playhead_ms,
        edit_points=edit_points,
    )
    commands = layout.get("commands") if isinstance(layout.get("commands"), Mapping) else {}
    command_rows = [
        {"id": "jog_back", "label": "Jog back", "key": "J", "enabled": True, "group": "transport"},
        {"id": "play_pause", "label": "Play / pause", "key": "K", "enabled": True, "group": "transport"},
        {"id": "jog_forward", "label": "Jog forward", "key": "L", "enabled": True, "group": "transport"},
        {"id": "source_in", "label": "Source In", "key": "I", "enabled": bool(commands.get("mark_source_in_enabled")), "group": "source"},
        {"id": "source_out", "label": "Source Out", "key": "O", "enabled": bool(commands.get("mark_source_out_enabled")), "group": "source"},
        {"id": "record_in", "label": "Record In", "key": "Shift+I", "enabled": bool(commands.get("mark_record_in_enabled")), "group": "record"},
        {"id": "record_out", "label": "Record Out", "key": "Shift+O", "enabled": bool(commands.get("mark_record_out_enabled")), "group": "record"},
        {"id": "insert", "label": "Insert", "key": ",", "enabled": bool(commands.get("insert_enabled")), "group": "edit"},
        {"id": "overwrite", "label": "Overwrite", "key": ".", "enabled": bool(commands.get("overwrite_enabled")), "group": "edit"},
        {"id": "next_edit", "label": "Next edit", "key": "Down", "enabled": True, "group": "navigation"},
        {"id": "previous_edit", "label": "Previous edit", "key": "Up", "enabled": True, "group": "navigation"},
    ]
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in command_rows:
        groups.setdefault(str(row.get("group") or "misc"), []).append(dict(row))
    return {
        "schema": SOURCE_RECORD_SCHEMA,
        "kind": "source_record_keyboard_overlay",
        "ready": True,
        "layout_ready": bool(layout.get("ready")),
        "command_count": len(command_rows),
        "enabled_count": sum(1 for row in command_rows if bool(row.get("enabled"))),
        "groups": [
            {"id": key, "title": key.replace("_", " ").title(), "rows": rows}
            for key, rows in groups.items()
        ],
        "commands": {
            "show_keyboard_overlay_enabled": True,
            "jkl_transport_enabled": True,
            "mark_shortcuts_enabled": True,
            "apply_shortcuts_enabled": bool(commands.get("insert_enabled") or commands.get("overwrite_enabled")),
        },
        "readiness": {
            "keyboard_overlay_ready": True,
            "jkl_transport_visible": True,
            "mark_shortcuts_visible": True,
        },
    }


def source_record_contract_evidence(
    *,
    action_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    actions = {str(row) for row in list(action_ids or [])}
    required = {
        "source_record.workbench",
        "source_monitor.state",
        "source_monitor.load_media",
        "source_monitor.set_in",
        "source_monitor.set_out",
        "record_monitor.state",
        "record_monitor.set_in",
        "record_monitor.set_out",
        "timeline.three_point_insert",
        "timeline.three_point_overwrite",
        "source_record.edit_decision_preview",
        "source_record.patch_matrix",
        "source_record.monitor_layout",
        "source_record.apply_board",
        "source_record.keyboard_overlay",
    }
    return {
        "ok": required <= actions,
        "required_actions": sorted(required),
        "available_actions": sorted(required & actions),
        "edit_decision_preview_ready": "source_record.edit_decision_preview" in actions,
        "patch_matrix_ready": "source_record.patch_matrix" in actions,
        "monitor_layout_ready": "source_record.monitor_layout" in actions,
        "apply_board_ready": "source_record.apply_board" in actions,
        "keyboard_overlay_ready": "source_record.keyboard_overlay" in actions,
    }
