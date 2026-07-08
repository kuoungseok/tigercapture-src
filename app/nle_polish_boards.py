"""Product polish boards for conservative NLE implementation readiness."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


NLE_POLISH_SCHEMA = "tigerstudio.nle.polish_board.v1"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _clip_rows(snapshot: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for track in list(snapshot.get(key) or []):
        if not isinstance(track, Mapping):
            continue
        for clip in list(track.get("clips") or []):
            if isinstance(clip, Mapping):
                rows.append(clip)
    return rows


def _media_rows(snapshot: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [row for row in list(snapshot.get("media_pool") or []) if isinstance(row, Mapping)]


def _action_set(action_ids: Sequence[str] | None) -> set[str]:
    return {str(row) for row in (action_ids or ()) if str(row or "").strip()}


def build_nle_core_safety_matrix(action_ids: Sequence[str] | None = None) -> dict[str, Any]:
    actions = _action_set(action_ids)
    rows = [
        {
            "id": "dry_run_preview",
            "label": "Preview before timeline mutation",
            "ready": {"timeline.three_point_insert", "timeline.three_point_overwrite", "timeline.ripple_delete"} <= actions,
        },
        {
            "id": "destructive_confirm",
            "label": "Destructive edits require explicit review/confirm",
            "ready": {"timeline.extract", "timeline.lift", "timeline.ripple_delete", "clip.delete"} <= actions,
        },
        {
            "id": "undo_recovery",
            "label": "Undo recovery surfaces are registered",
            "ready": {"timeline.undo_review_board", "timeline.undo_recovery_playbook", "timeline.undo_stability_dashboard"} <= actions,
        },
        {
            "id": "real_corpus_gate",
            "label": "Real project claim gate is visible",
            "ready": {"nle.real_corpus.workbench", "nle.real_corpus.validation_preflight", "timeline.nle_target_gap"} <= actions,
        },
    ]
    ready_count = sum(1 for row in rows if bool(row.get("ready")))
    return {
        "schema": NLE_POLISH_SCHEMA,
        "kind": "core_safety_matrix",
        "ready": ready_count == len(rows),
        "summary": {"ready_count": ready_count, "total": len(rows)},
        "rows": rows,
        "readiness": {
            "core_safety_matrix_ready": ready_count == len(rows),
            "dry_run_preview_ready": bool(rows[0]["ready"]),
            "claim_gate_visible": bool(rows[-1]["ready"]),
        },
        "commands": {
            "show_missing_contracts_enabled": ready_count < len(rows),
            "open_real_corpus_workbench_enabled": "nle.real_corpus.workbench" in actions,
        },
    }


def build_source_record_usability_board(action_ids: Sequence[str] | None = None) -> dict[str, Any]:
    actions = _action_set(action_ids)
    rows = [
        ("dual_monitor_layout", "source_record.monitor_layout"),
        ("patch_matrix", "source_record.patch_matrix"),
        ("apply_board", "source_record.apply_board"),
        ("keyboard_overlay", "source_record.keyboard_overlay"),
        ("decision_preview", "source_record.edit_decision_preview"),
    ]
    cards = [{"id": row_id, "action_id": action_id, "ready": action_id in actions} for row_id, action_id in rows]
    return {
        "schema": NLE_POLISH_SCHEMA,
        "kind": "source_record_usability_board",
        "ready": all(bool(row.get("ready")) for row in cards),
        "cards": cards,
        "layout": {
            "left": "Source Monitor",
            "right": "Record Monitor",
            "bottom": "Patch matrix + Insert/Overwrite review",
        },
        "commands": {
            "show_dual_monitor_enabled": "source_record.monitor_layout" in actions,
            "show_apply_board_enabled": "source_record.apply_board" in actions,
            "show_keyboard_overlay_enabled": "source_record.keyboard_overlay" in actions,
        },
        "readiness": {
            "source_record_usability_ready": all(bool(row.get("ready")) for row in cards),
            "jkl_transport_visible": "source_record.keyboard_overlay" in actions,
            "review_before_apply_visible": "source_record.apply_board" in actions,
        },
    }


def build_multicam_export_parity_board(
    snapshot: Mapping[str, Any] | None = None,
    *,
    action_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    actions = _action_set(action_ids)
    video_clips = _clip_rows(snapshot, "video_tracks")
    angles = {
        str(row.get("camera_id") or row.get("angle") or row.get("source_path") or "")
        for row in video_clips
    }
    angles.discard("")
    rows = [
        {"id": "angle_bins", "ready": "timeline.multicam.angle_bins" in actions},
        {"id": "sync_quality", "ready": "timeline.multicam.sync_quality_board" in actions},
        {"id": "waveform_sync", "ready": "timeline.multicam.waveform_sync_board" in actions},
        {"id": "live_switch_dashboard", "ready": "timeline.multicam.live_switch_dashboard" in actions},
        {"id": "export_handoff", "ready": "timeline.multicam.export_handoff" in actions},
    ]
    ready = all(bool(row.get("ready")) for row in rows)
    return {
        "schema": NLE_POLISH_SCHEMA,
        "kind": "multicam_export_parity_board",
        "ready": ready,
        "summary": {
            "angle_count": len(angles),
            "clip_count": len(video_clips),
            "ready_contract_count": sum(1 for row in rows if bool(row.get("ready"))),
        },
        "rows": rows,
        "export_checks": [
            "active angle decision list is available",
            "sync confidence rows are visible",
            "waveform offsets are visible when present",
            "export handoff payload is available before baking",
        ],
        "commands": {
            "open_live_switch_dashboard_enabled": "timeline.multicam.live_switch_dashboard" in actions,
            "open_export_handoff_enabled": "timeline.multicam.export_handoff" in actions,
        },
        "readiness": {
            "multicam_export_parity_board_ready": ready,
            "real_footage_review_required": True,
        },
    }


def build_proxy_apply_review_board(snapshot: Mapping[str, Any] | None = None) -> dict[str, Any]:
    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    media = _media_rows(snapshot)
    proxy_states: dict[str, int] = {}
    for row in media:
        state = str(row.get("proxy_state") or "unknown")
        proxy_states[state] = proxy_states.get(state, 0) + 1
    stale_count = proxy_states.get("stale", 0) + proxy_states.get("missing", 0)
    ready_count = proxy_states.get("ready", 0) + proxy_states.get("active", 0) + proxy_states.get("fresh", 0)
    return {
        "schema": NLE_POLISH_SCHEMA,
        "kind": "proxy_apply_review_board",
        "ready": bool(media),
        "summary": {
            "media_count": len(media),
            "ready_proxy_count": ready_count,
            "stale_proxy_count": stale_count,
            "proxy_states": proxy_states,
        },
        "review_rows": [
            {"id": "safe_background_jobs", "count": stale_count, "requires_review": stale_count > 0},
            {"id": "fresh_proxy_usage", "count": ready_count, "requires_review": False},
        ],
        "commands": {
            "start_safe_background_jobs_enabled": stale_count > 0,
            "review_proxy_conflicts_enabled": bool(media),
            "show_stale_proxy_warning_enabled": stale_count > 0,
        },
        "readiness": {
            "proxy_apply_review_ready": bool(media),
            "stale_proxy_warning_ready": True,
            "safe_background_apply_ready": bool(media),
        },
    }


def build_conform_apply_review_board(snapshot: Mapping[str, Any] | None = None) -> dict[str, Any]:
    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    media = _media_rows(snapshot)
    video_clips = _clip_rows(snapshot, "video_tracks")
    audio_clips = _clip_rows(snapshot, "audio_tracks")
    missing = [
        row
        for row in media
        if bool(row.get("offline")) or str(row.get("proxy_state") or "").lower() == "missing"
    ]
    return {
        "schema": NLE_POLISH_SCHEMA,
        "kind": "conform_apply_review_board",
        "ready": bool(media or video_clips or audio_clips),
        "summary": {
            "media_count": len(media),
            "timeline_clip_count": len(video_clips) + len(audio_clips),
            "missing_or_offline_count": len(missing),
        },
        "review_rows": [
            {"id": "offline_media", "count": len(missing), "tone": "warning" if missing else "ok"},
            {"id": "timeline_clips", "count": len(video_clips) + len(audio_clips), "tone": "ready"},
        ],
        "commands": {
            "open_offline_browser_enabled": True,
            "open_relink_candidates_enabled": True,
            "batch_apply_requires_review": True,
        },
        "readiness": {
            "conform_apply_review_ready": bool(media or video_clips or audio_clips),
            "offline_browser_visible": True,
            "batch_apply_review_required": True,
        },
    }


def build_undo_long_session_plan(action_ids: Sequence[str] | None = None) -> dict[str, Any]:
    actions = _action_set(action_ids)
    phases = [
        {"id": "mutation_preview", "action_id": "timeline.undo_review_board"},
        {"id": "recovery_playbook", "action_id": "timeline.undo_recovery_playbook"},
        {"id": "stability_dashboard", "action_id": "timeline.undo_stability_dashboard"},
        {"id": "real_corpus_workbench", "action_id": "nle.real_corpus.workbench"},
    ]
    for row in phases:
        row["ready"] = str(row.get("action_id")) in actions
    return {
        "schema": NLE_POLISH_SCHEMA,
        "kind": "undo_long_session_plan",
        "ready": all(bool(row.get("ready")) for row in phases),
        "phases": phases,
        "session_recipe": [
            "open a registered real project",
            "perform split/trim/ripple/delete/insert/overwrite mutations",
            "assert undo/redo after every destructive mutation",
            "save/reopen and verify recovery state",
        ],
        "commands": {
            "open_undo_review_enabled": "timeline.undo_review_board" in actions,
            "open_real_corpus_workbench_enabled": "nle.real_corpus.workbench" in actions,
        },
        "readiness": {
            "undo_long_session_plan_ready": all(bool(row.get("ready")) for row in phases),
            "operator_real_project_required": True,
        },
    }


def build_storyline_gesture_polish_board(action_ids: Sequence[str] | None = None) -> dict[str, Any]:
    actions = _action_set(action_ids)
    checks = [
        ("anchor_overlay", "timeline.connected_clips.anchor_overlay"),
        ("role_filter", "timeline.role_lanes.filter_model"),
        ("drag_preview", "timeline.magnetic_storyline.drag_preview"),
        ("audition_compare", "timeline.audition.compare"),
        ("role_focus", "timeline.role_lanes.focus"),
    ]
    rows = [{"id": row_id, "action_id": action_id, "ready": action_id in actions} for row_id, action_id in checks]
    return {
        "schema": NLE_POLISH_SCHEMA,
        "kind": "storyline_gesture_polish_board",
        "ready": all(bool(row.get("ready")) for row in rows),
        "rows": rows,
        "gesture_language": {
            "snap": "magnetic field lines",
            "blocked": "hatch/stop tone",
            "connected_clip": "anchor line and role color",
            "audition": "card strip and active take marker",
        },
        "commands": {
            "show_anchor_overlay_enabled": "timeline.connected_clips.anchor_overlay" in actions,
            "show_drag_preview_enabled": "timeline.magnetic_storyline.drag_preview" in actions,
            "show_audition_cards_enabled": "timeline.audition.compare" in actions,
        },
        "readiness": {
            "storyline_gesture_polish_ready": all(bool(row.get("ready")) for row in rows),
            "audition_visual_review_ready": "timeline.audition.compare" in actions,
        },
    }


__all__ = [
    "NLE_POLISH_SCHEMA",
    "build_conform_apply_review_board",
    "build_multicam_export_parity_board",
    "build_nle_core_safety_matrix",
    "build_proxy_apply_review_board",
    "build_source_record_usability_board",
    "build_storyline_gesture_polish_board",
    "build_undo_long_session_plan",
]
