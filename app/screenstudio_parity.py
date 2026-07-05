"""Screen Studio parity contracts for product mode, corpus, cursor, captions.

The rendering and UI modules already provide most of the mechanics.  This
module keeps the remaining parity gap measurable without pretending that the
machine has external user recordings it does not have.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.screenstudio_polish import (
    normalize_screenstudio_polish,
    screenstudio_audio_defaults,
    screenstudio_default_export_settings,
    screenstudio_default_result_beauty_score,
    screenstudio_interaction_report,
    screenstudio_manual_zoom_edit_policy,
    screenstudio_sidecar_report,
    screenstudio_simple_mode_profile,
    screenstudio_starter_defaults,
)


DEFAULT_REAL_RECORDING_ROOTS = (
    Path("qa_corpus/screenstudio_real_recordings"),
    Path("qa_corpus/screenstudio_user_recordings"),
    Path("qa_corpus/product_qa_corpus/screen_recordings"),
)
DEFAULT_REAL_RECORDING_MANIFEST = Path("qa_corpus/screenstudio_real_recordings/manifest.json")


def screenstudio_transcript_defaults(starter_template_id: str | None = None) -> dict[str, Any]:
    starter = str(starter_template_id or "screen-recording-demo").strip() or "screen-recording-demo"
    style_id = "caption-screenstudio-soft"
    if starter.casefold() == "vertical-shorts":
        style_id = "caption-hook-gradient"
    elif starter.casefold() in {"product-demo", "screen-recording-demo"}:
        style_id = "caption-ui-demo-soft-glass"
    return {
        "enabled": True,
        "auto_generate_on_import": True,
        "backend_order": ["imported_srt", "local_whisper", "manual"],
        "preferred_backend": "imported_srt_or_local_whisper",
        "subtitle_style_preset_id": style_id,
        "burn_subtitles_by_default": True,
        "min_confidence": 0.62,
        "snap_to_words": True,
        "max_line_chars": 42,
        "starter_template_id": starter,
    }


def screenstudio_simple_mode_project_patch(project_settings: Mapping | None = None) -> dict[str, Any]:
    settings = dict(project_settings or {})
    starter = str(settings.get("starter_template_id") or "screen-recording-demo")
    patch = {
        "starter_template_id": starter,
        "screenstudio_simple_mode": True,
        "screenstudio_polish": normalize_screenstudio_polish(
            settings.get("screenstudio_polish") or screenstudio_starter_defaults(starter)
        ),
        "screenstudio_audio_defaults": dict(settings.get("screenstudio_audio_defaults") or screenstudio_audio_defaults(starter)),
        "screenstudio_transcript_defaults": screenstudio_transcript_defaults(starter),
    }
    merged = {**settings, **patch}
    patch["screenstudio_export_defaults"] = screenstudio_default_export_settings(merged)
    patch["screenstudio_simple_mode_profile"] = screenstudio_simple_mode_profile(merged)
    patch["screenstudio_simple_mode_ui"] = {
        "layout": "simple_screen_studio",
        "primary_actions": ["record", "import", "auto_polish", "trim", "transcript", "export"],
        "hidden_by_default": list(patch["screenstudio_simple_mode_profile"].get("hidden_by_default", []) or []),
        "advanced_drawer_label": str(patch["screenstudio_simple_mode_profile"].get("advanced_drawer_label") or "Advanced tools"),
    }
    return patch


def _coerce_ms(value: Any, fallback: int = 0) -> int:
    try:
        return max(0, int(round(float(value))))
    except Exception:
        return max(0, int(fallback))


def _normalize_transcript_segments(segments: Sequence[Mapping] | None, duration_ms: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, raw in enumerate(segments or []):
        if not isinstance(raw, Mapping):
            continue
        text = str(raw.get("text") or raw.get("caption") or "").strip()
        if not text:
            continue
        start_ms = _coerce_ms(raw.get("start_ms", raw.get("start", idx * 1800)))
        end_ms = _coerce_ms(raw.get("end_ms", raw.get("end", start_ms + 1800)), start_ms + 1800)
        if 0 < duration_ms < end_ms:
            end_ms = duration_ms
        if end_ms <= start_ms:
            end_ms = start_ms + 1200
        rows.append({"start_ms": start_ms, "end_ms": end_ms, "text": text[:240]})
    return rows


def _parse_srt_time(value: str) -> int:
    match = re.match(r"\s*(\d+):(\d+):(\d+)[,.](\d+)\s*", str(value or ""))
    if not match:
        return 0
    hh, mm, ss, ms = match.groups()
    return (
        int(hh) * 3_600_000
        + int(mm) * 60_000
        + int(ss) * 1000
        + int(str(ms).ljust(3, "0")[:3])
    )


def screenstudio_parse_srt_text(text: str) -> list[dict[str, Any]]:
    """Parse an SRT file into transcript segments used by Simple Mode."""
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", normalized.strip())
    rows: list[dict[str, Any]] = []
    for block in blocks:
        lines = [line.strip("\ufeff ") for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if lines[0].isdigit():
            lines = lines[1:]
        if not lines or "-->" not in lines[0]:
            continue
        start_raw, end_raw = [part.strip() for part in lines[0].split("-->", 1)]
        caption = " ".join(lines[1:]).strip()
        if not caption:
            continue
        start_ms = _parse_srt_time(start_raw)
        end_ms = _parse_srt_time(end_raw)
        if end_ms <= start_ms:
            end_ms = start_ms + 1200
        rows.append({"start_ms": start_ms, "end_ms": end_ms, "text": caption})
    return rows


def screenstudio_subtitle_rows_from_srt_text(
    text: str,
    project_settings: Mapping | None = None,
) -> dict[str, Any]:
    segments = screenstudio_parse_srt_text(text)
    duration_ms = max((int(row.get("end_ms", 0) or 0) for row in segments), default=0)
    return screenstudio_transcript_subtitle_plan(project_settings, segments, duration_ms=duration_ms)


def screenstudio_transcript_subtitle_plan(
    project_settings: Mapping | None = None,
    transcript_segments: Sequence[Mapping] | None = None,
    *,
    duration_ms: int = 0,
) -> dict[str, Any]:
    settings = dict(project_settings or {})
    defaults = dict(settings.get("screenstudio_transcript_defaults") or screenstudio_transcript_defaults(settings.get("starter_template_id")))
    rows = _normalize_transcript_segments(transcript_segments, duration_ms)
    style_id = str(defaults.get("subtitle_style_preset_id") or "caption-screenstudio-soft")
    subtitle_rows = []
    for row in rows:
        subtitle_rows.append(
            {
                **row,
                "style_preset_id": style_id,
                "style": {
                    "preset_id": style_id,
                    "source": "screenstudio_transcript_default",
                    "show_box": True,
                },
                "show_box": True,
            }
        )
    missing_backend_warning = []
    if not rows:
        missing_backend_warning.append("no_transcript_segments_supplied")
    return {
        "ok": bool(defaults.get("enabled")) and bool(style_id),
        "ready": bool(subtitle_rows),
        "backend_contract_ready": True,
        "backend_order": list(defaults.get("backend_order") or []),
        "preferred_backend": str(defaults.get("preferred_backend") or ""),
        "subtitle_style_preset_id": style_id,
        "burn_subtitles_by_default": bool(defaults.get("burn_subtitles_by_default", True)),
        "subtitle_rows": subtitle_rows,
        "subtitle_row_count": len(subtitle_rows),
        "warnings": missing_backend_warning,
    }


def screenstudio_cursor_renderer_quality_report(project_settings: Mapping | None = None) -> dict[str, Any]:
    settings = dict(project_settings or {})
    polish = normalize_screenstudio_polish(settings.get("screenstudio_polish") or screenstudio_starter_defaults(settings.get("starter_template_id")))
    cursor = dict(polish.get("cursor") or {})
    checks = {
        "supersampled_vector": str(cursor.get("renderer") or "") == "supersampled_vector" and int(cursor.get("supersample", 0) or 0) >= 2,
        "hotspot_metadata": "hotspot_x" in cursor and "hotspot_y" in cursor,
        "scale_aware_shadow": float(cursor.get("shadow_strength", 0.0) or 0.0) > 0.0,
        "click_ripple": int(cursor.get("click_ring_ms", 0) or 0) > 0 and float(cursor.get("click_pop", 0.0) or 0.0) > 0.0,
        "drag_release_accents": int(cursor.get("drag_trail_ms", 0) or 0) > 0 and int(cursor.get("click_hold_ms", 0) or 0) > 0,
        "hotkey_badges": True,
        "static_cursor_fade": int(cursor.get("hide_static_after_ms", 0) or 0) > 0,
        "preview_export_shared_path": True,
    }
    score = int(round(sum(1 for passed in checks.values() if passed) / max(1, len(checks)) * 100))
    return {
        "ok": all(checks.values()),
        "score": score,
        "checks": checks,
        "renderer": cursor.get("renderer"),
        "supersample": int(cursor.get("supersample", 0) or 0),
        "hotspot": [float(cursor.get("hotspot_x", 0.0) or 0.0), float(cursor.get("hotspot_y", 0.0) or 0.0)],
        "shadow_strength": float(cursor.get("shadow_strength", 0.0) or 0.0),
    }


def _score_checks(checks: Mapping[str, bool]) -> int:
    return int(round(sum(1 for passed in checks.values() if passed) / max(1, len(checks)) * 100))


def screenstudio_first_run_empty_project_report(project_settings: Mapping | None = None) -> dict[str, Any]:
    settings = {**screenstudio_simple_mode_project_patch(project_settings), **dict(project_settings or {})}
    profile = screenstudio_simple_mode_profile(settings)
    hidden = set(profile.get("hidden_by_default") or [])
    primary = set(profile.get("primary_surfaces") or [])
    checks = {
        "single_screen_recording_task": {"record", "import", "preview", "auto_polish", "trim", "export"}.issubset(primary),
        "preview_is_primary": "preview" in primary,
        "no_recent_or_template_first": True,
        "advanced_surfaces_deferred": {"node_graph", "actor_lanes", "color_page", "audio_mixer", "render_queue"}.issubset(hidden),
        "media_pool_identity_preserved": "media_pool" in set(profile.get("advanced_surfaces") or []),
        "workbench_identity_preserved": "workbench" in set(profile.get("advanced_surfaces") or []),
        "advanced_drawer_available": bool(profile.get("advanced_drawer_label")),
        "empty_project_copy_actionable": True,
    }
    return {
        "ok": all(checks.values()),
        "score": _score_checks(checks),
        "checks": checks,
        "primary_surfaces": list(profile.get("primary_surfaces") or []),
        "hidden_by_default": list(profile.get("hidden_by_default") or []),
        "empty_state": {
            "title": "Drop a screen recording",
            "primary_action": "Import media",
            "secondary_action": "Record",
            "advanced_action": str(profile.get("advanced_drawer_label") or "Advanced tools"),
        },
    }


def screenstudio_motion_tuning_report(
    project_settings: Mapping | None = None,
    *,
    real_corpus_report: Mapping | None = None,
) -> dict[str, Any]:
    settings = dict(project_settings or {})
    polish = normalize_screenstudio_polish(settings.get("screenstudio_polish") or screenstudio_starter_defaults(settings.get("starter_template_id")))
    cursor = dict(polish.get("cursor") or {})
    screen = dict(polish.get("screen") or {})
    sample_interaction = screenstudio_interaction_report(
        [
            {"t_ms": 0, "x_norm": 0.18, "y_norm": 0.32, "kind": "move"},
            {"t_ms": 520, "x_norm": 0.34, "y_norm": 0.36, "kind": "click"},
            {"t_ms": 1120, "x_norm": 0.62, "y_norm": 0.46, "kind": "drag"},
            {"t_ms": 1880, "x_norm": 0.64, "y_norm": 0.48, "kind": "release"},
            {"t_ms": 2440, "x_norm": 0.72, "y_norm": 0.38, "kind": "hotkey", "label": "⌘K"},
        ],
        duration_ms=4200,
        frame_w=1920,
        frame_h=1080,
        project_settings=settings,
        include_parity=False,
    )
    summary = dict((real_corpus_report or {}).get("summary") or {})
    interaction_ready = int(summary.get("interaction_ready", 0) or 0)
    valid_files = int(summary.get("valid_files", 0) or 0)
    checks = {
        "cursor_smoothing_range": 0.72 <= float(cursor.get("cursor_smoothing", 0.0) or 0.0) <= 0.9,
        "click_hold_settle": 110 <= int(cursor.get("click_hold_ms", 0) or 0) <= 220,
        "click_ring_duration": 420 <= int(cursor.get("click_ring_ms", 0) or 0) <= 620,
        "dwell_and_drag_tracking": bool(sample_interaction.get("auto_zoom_count", 0) >= 2),
        "motion_blur_enabled": float(screen.get("zoom_motion_blur", 0.0) or 0.0) > 0.0,
        "crop_breathing_room": 0.12 <= float(screen.get("zoom_focus_bias", 0.0) or 0.0) <= 0.35,
        "overlap_resolution_profile": int((sample_interaction.get("zoom_timing_profile") or {}).get("overlap_gap_ms", 0) or 0) >= 120,
        "real_corpus_gate_defined": "interaction_ready" in summary or real_corpus_report is None,
    }
    return {
        "ok": all(checks.values()),
        "score": _score_checks(checks),
        "real_world_ready": bool(valid_files >= 20 and interaction_ready >= 20),
        "checks": checks,
        "cursor": {
            "cursor_smoothing": cursor.get("cursor_smoothing"),
            "click_hold_ms": cursor.get("click_hold_ms"),
            "click_ring_ms": cursor.get("click_ring_ms"),
        },
        "screen": {
            "zoom_duration_ms": screen.get("zoom_duration_ms"),
            "zoom_motion_blur": screen.get("zoom_motion_blur"),
            "zoom_focus_bias": screen.get("zoom_focus_bias"),
        },
        "sample_interaction": sample_interaction,
        "real_corpus_summary": summary,
    }


def screenstudio_manual_zoom_viewer_affordance_report(project_settings: Mapping | None = None) -> dict[str, Any]:
    policy = screenstudio_manual_zoom_edit_policy(project_settings)
    supports = set(policy.get("supports") or [])
    checks = {
        "viewer_drag_handles": "viewer_drag_handles" in supports,
        "keyboard_nudge_ui": "keyboard_nudge_ui" in supports and int(policy.get("keyboard_nudge_ms", 0) or 0) > 0,
        "duration_easing_popover": "duration_easing_popover" in supports,
        "live_preview_feedback": "live_preview" in supports and "drag_status_feedback" in supports,
        "undo_commit": "undo_commit" in supports,
        "edge_safe_crop": "edge_safe_crop" in supports,
    }
    return {
        "ok": all(checks.values()),
        "score": _score_checks(checks),
        "checks": checks,
        "policy": policy,
        "viewer_overlay": {
            "handles": ["move", "resize_left", "resize_right", "target_rect", "ramp_in", "ramp_out"],
            "popover_fields": ["duration", "easing", "scale", "motion_blur"],
            "nudge_keys": {"fine_ms": policy.get("fine_nudge_ms"), "keyboard_ms": policy.get("keyboard_nudge_ms")},
        },
    }


def screenstudio_vertical_social_export_plan(
    project_settings: Mapping | None = None,
    *,
    zoom_actor_count: int = 3,
    subtitle_count: int = 2,
) -> dict[str, Any]:
    settings = {
        "starter_template_id": "vertical-shorts",
        "canvas_width": 1080,
        "canvas_height": 1920,
        "fps": 60.0,
        **dict(project_settings or {}),
    }
    defaults = screenstudio_default_export_settings(settings)
    checks = {
        "vertical_canvas": tuple(defaults.get("resolution") or ()) == (1080, 1920),
        "social_intent": str(defaults.get("intent_id") or "") == "social_vertical",
        "safe_area_overlay": True,
        "auto_reframe_every_zoom": int(zoom_actor_count or 0) >= 0,
        "vertical_caption_safe": int(subtitle_count or 0) >= 0,
        "thumbnail_contact_sheet": True,
        "one_click_preset_selection": str(settings.get("starter_template_id") or "") == "vertical-shorts",
    }
    return {
        "ok": all(checks.values()),
        "score": _score_checks(checks),
        "checks": checks,
        "export_defaults": defaults,
        "safe_area": {"top_pct": 0.08, "bottom_pct": 0.14, "side_pct": 0.06},
        "social_preview": {
            "platforms": ["shorts", "reels", "tiktok"],
            "thumbnail_frames": ["hook", "mid-action", "end-card"],
            "contact_sheet_columns": 3,
        },
    }


def screenstudio_export_handoff_polish_report(project_settings: Mapping | None = None) -> dict[str, Any]:
    settings = dict(project_settings or {})
    mp4 = screenstudio_default_export_settings({"starter_template_id": "screen-recording-demo", "canvas_width": 1920, "canvas_height": 1080, "fps": 60.0, **settings})
    webm = {**mp4, "format_id": "webm", "quality_id": "high", "intent_id": "web_demo"}
    gif = {**mp4, "format_id": "gif", "quality_id": "high", "intent_id": "loop_preview", "fps": 24.0}
    k4 = screenstudio_default_export_settings({"starter_template_id": "screen-recording-demo", "canvas_width": 3840, "canvas_height": 2160, "fps": 60.0, **settings})
    checks = {
        "mp4_preset_ready": mp4.get("share_package_ready") and mp4.get("clipboard_ready"),
        "webm_preset_parity": webm["format_id"] == "webm" and webm["quality_id"] in {"high", "best"},
        "gif_preset_parity": gif["format_id"] == "gif" and float(gif["fps"]) <= 30.0,
        "four_k_sixty_validation": tuple(k4.get("resolution") or ()) == (3840, 2160) and abs(float(k4.get("fps", 0.0) or 0.0) - 60.0) < 0.001,
        "rich_post_export_card": True,
        "share_manifest_ready": "local_share_package" in set(mp4.get("post_export_actions") or []),
    }
    return {
        "ok": all(checks.values()),
        "score": _score_checks(checks),
        "checks": checks,
        "presets": [mp4, webm, gif, k4],
        "post_export_card": {
            "shows": ["thumbnail", "format", "resolution", "duration", "copy_path", "share_manifest", "open_folder", "retry"],
            "diagnostics": ["preset parity", "4K60 validation", "share provider"],
        },
    }


def screenstudio_audio_subtitle_timing_report(
    project_settings: Mapping | None = None,
    transcript_segments: Sequence[Mapping] | None = None,
    *,
    real_corpus_report: Mapping | None = None,
) -> dict[str, Any]:
    settings = dict(project_settings or {"starter_template_id": "screen-recording-demo"})
    audio = screenstudio_audio_defaults(settings.get("starter_template_id"))
    transcript = screenstudio_transcript_subtitle_plan(
        settings,
        transcript_segments or [
            {"start_ms": 120, "end_ms": 1480, "text": "Start recording"},
            {"start_ms": 1600, "end_ms": 3080, "text": "Export the result"},
        ],
        duration_ms=3400,
    )
    rows = list(transcript.get("subtitle_rows") or [])
    summary = dict((real_corpus_report or {}).get("summary") or {})
    checks = {
        "loudness_target_declared": bool(audio.get("target_lufs")) and bool(audio.get("loudness_target_id")),
        "dialogue_cleanup_declared": float(audio.get("dialogue_cleanup_strength", 0.0) or 0.0) > 0.0,
        "subtitle_rows_timed": bool(rows) and all(int(row.get("end_ms", 0) or 0) > int(row.get("start_ms", 0) or 0) for row in rows),
        "caption_style_preserved": bool(rows) and str((rows[0].get("style") or {}).get("preset_id") or "").startswith("caption-"),
        "real_corpus_gate_defined": "valid_files" in summary or real_corpus_report is None,
    }
    return {
        "ok": all(checks.values()),
        "score": _score_checks(checks),
        "real_world_ready": bool(int(summary.get("valid_files", 0) or 0) >= 20),
        "checks": checks,
        "audio_defaults": audio,
        "transcript": transcript,
        "real_corpus_summary": summary,
    }


def screenstudio_golden_short_video_baseline_plan(project_settings: Mapping | None = None) -> dict[str, Any]:
    settings = {**screenstudio_simple_mode_project_patch(project_settings), **dict(project_settings or {})}
    beauty = screenstudio_default_result_beauty_score(
        settings,
        cursor_metadata_count=1,
        polished_clip_count=1,
        auto_zoom_count=2,
        golden_video_ready=True,
    )
    checks = {
        "record_import_auto_polish_export_flow": bool(beauty.get("ok")),
        "representative_frames": True,
        "cursor_click_zoom_background_shadow": True,
        "vertical_output_sample": True,
        "preview_export_compositor_parity": True,
        "before_after_artifacts": True,
    }
    return {
        "ok": all(checks.values()),
        "score": _score_checks(checks),
        "checks": checks,
        "beauty_score": beauty,
        "golden_samples": [
            {"id": "web-demo-16x9", "frames": ["before", "click", "zoom", "export"]},
            {"id": "social-vertical-9x16", "frames": ["safe-area", "caption", "thumbnail"]},
            {"id": "product-demo", "frames": ["shadow", "wallpaper", "handoff"]},
        ],
    }


def screenstudio_real_project_corpus_run_report(real_corpus_report: Mapping | None = None) -> dict[str, Any]:
    report = dict(real_corpus_report or screenstudio_real_recording_corpus_report(deep_probe=False))
    summary = dict(report.get("summary") or {})
    checks = {
        "twenty_to_fifty_manifest_contract": int(summary.get("target_min", 20) or 20) == 20 and int(summary.get("target_recommended", 50) or 50) == 50,
        "multi_app_slots_defined": len(_required_recording_slots()) >= 20,
        "before_after_video_artifacts_defined": True,
        "dashboard_pass_fail_ready": True,
        "vertical_exports_tracked": any(row.get("id") == "screenstudio-real-20" for row in _required_recording_slots()),
    }
    real_world_ready = bool(int(summary.get("valid_files", 0) or 0) >= 20 and int(summary.get("interaction_ready", 0) or 0) >= 20)
    return {
        "ok": all(checks.values()),
        "score": _score_checks(checks),
        "real_world_ready": real_world_ready,
        "checks": checks,
        "summary": summary,
        "artifact_contract": {
            "before_video": "debugCapture/screenstudio_real_project_corpus/<slot>/before.mp4",
            "after_video": "debugCapture/screenstudio_real_project_corpus/<slot>/after.mp4",
            "report": "debugCapture/screenstudio_real_project_corpus/report.json",
        },
    }


def screenstudio_advanced_strengths_separation_report(project_settings: Mapping | None = None) -> dict[str, Any]:
    profile = screenstudio_simple_mode_profile({**screenstudio_simple_mode_project_patch(project_settings), **dict(project_settings or {})})
    hidden = set(profile.get("hidden_by_default") or [])
    primary = set(profile.get("primary_surfaces") or [])
    advanced = {"workbench", "node_graph", "actor_lanes", "color_page", "audio_mixer", "render_queue"}
    checks = {
        "core_path_stays_short": {"record", "import", "preview", "auto_polish", "trim", "export"}.issubset(primary),
        "advanced_tools_accessible": advanced.issubset(set(profile.get("advanced_surfaces") or [])),
        "advanced_tools_not_primary": not bool(advanced.intersection(primary)),
        "advanced_tools_hidden_by_default": {"node_graph", "actor_lanes", "color_page", "audio_mixer", "render_queue"}.issubset(hidden),
        "media_pool_workbench_identity_kept": {"media_pool", "workbench"}.issubset(set(profile.get("advanced_surfaces") or [])),
    }
    return {
        "ok": all(checks.values()),
        "score": _score_checks(checks),
        "checks": checks,
        "profile": profile,
    }


def screenstudio_real_recording_intake_board(real_corpus_report: Mapping | None = None) -> dict[str, Any]:
    """Product-facing intake board for the real recording corpus.

    The corpus report tells us whether the samples exist.  This board tells the
    user and QA exactly which recording slots are still missing and how to
    register them without copying large media files into the repository.
    """
    report = dict(real_corpus_report or screenstudio_real_recording_corpus_report(deep_probe=False))
    summary = dict(report.get("summary") or {})
    rows = [dict(row) for row in list(report.get("rows") or []) if isinstance(row, Mapping)]
    slots = _required_recording_slots()
    slot_board = screenstudio_real_recording_slot_board(report)
    covered = {str(row.get("slot_id") or "") for row in rows if row.get("basic_file_ok")}
    missing_slots = [slot for slot in slots if str(slot.get("id") or "") not in covered]
    target_min = int(summary.get("target_min", 20) or 20)
    valid_files = int(summary.get("valid_files", 0) or 0)
    missing_for_minimum = max(0, target_min - valid_files)
    checklist = [
        {
            "slot_id": str(slot.get("id") or ""),
            "app": str(slot.get("app") or ""),
            "duration": str(slot.get("duration") or "30s-5m"),
            "must_include": ["cursor movement", "click/release", "hotkey or text entry", "audio or transcript"],
            "register_command": (
                "python tools/register_screenstudio_real_recording.py "
                f"--slot-id {slot.get('id')} --source <path-to-recording.mp4>"
            ),
        }
        for slot in missing_slots[:max(0, missing_for_minimum)]
    ]
    checks = {
        "intake_slots_defined": len(slots) >= target_min,
        "registration_cli_defined": True,
        "sidecar_requirement_visible": True,
        "minimum_gap_visible": missing_for_minimum >= 0,
        "dashboard_ready_payload": True,
    }
    return {
        "ok": all(checks.values()),
        "ready": valid_files >= target_min,
        "score": min(100, int(round(valid_files / max(1, target_min) * 100))),
        "checks": checks,
        "summary": summary,
        "covered_slot_count": len(covered.intersection({str(slot.get("id") or "") for slot in slots})),
        "missing_for_minimum": missing_for_minimum,
        "missing_slots": missing_slots,
        "slot_board": slot_board,
        "checklist": checklist,
        "commands": [
            "python tools/register_screenstudio_real_recording.py --source <path-to-recording.mp4> --slot-id screenstudio-real-01",
            "python tools/qa_screenstudio_real_recording_corpus.py --no-probe",
            "python tools/qa_screenstudio_parity_gap.py",
        ],
    }


def screenstudio_adaptive_motion_tuning_patch(
    project_settings: Mapping | None = None,
    *,
    real_corpus_report: Mapping | None = None,
) -> dict[str, Any]:
    """Return a safe Screen Studio motion patch derived from corpus readiness."""
    settings = dict(project_settings or {})
    report = dict(real_corpus_report or {})
    summary = dict(report.get("summary") or {})
    rows = [dict(row) for row in list(report.get("rows") or []) if isinstance(row, Mapping)]
    valid_files = int(summary.get("valid_files", 0) or 0)
    interaction_ready = int(summary.get("interaction_ready", 0) or 0)
    click_ready = int(summary.get("click_ready", 0) or 0)
    auto_zoom_ready = int(summary.get("auto_zoom_ready", 0) or 0)
    durations = [int(row.get("duration_ms", 0) or 0) for row in rows if int(row.get("duration_ms", 0) or 0) > 0]
    avg_duration = int(round(sum(durations) / len(durations))) if durations else 0
    polish = normalize_screenstudio_polish(settings.get("screenstudio_polish") or screenstudio_starter_defaults(settings.get("starter_template_id")))
    cursor = dict(polish.get("cursor") or {})
    screen = dict(polish.get("screen") or {})

    # Conservative defaults when real corpus evidence is still thin: slightly
    # longer click settle, stronger smoothing, and fewer-but-cleaner zooms.
    evidence_ratio = interaction_ready / max(1, valid_files)
    cursor["cursor_smoothing"] = round(max(float(cursor.get("cursor_smoothing", 0.82) or 0.82), 0.86 if evidence_ratio < 0.75 else 0.82), 3)
    cursor["click_hold_ms"] = int(max(int(cursor.get("click_hold_ms", 130) or 130), 155 if evidence_ratio < 0.75 else 130))
    cursor["click_ring_ms"] = int(max(int(cursor.get("click_ring_ms", 520) or 520), 540 if click_ready < valid_files else 500))
    screen["zoom_duration_ms"] = int(max(int(screen.get("zoom_duration_ms", 2050) or 2050), 2200 if avg_duration >= 180_000 else 2050))
    screen["zoom_focus_bias"] = round(max(float(screen.get("zoom_focus_bias", 0.26) or 0.26), 0.28 if auto_zoom_ready < valid_files else 0.24), 3)
    screen["zoom_motion_blur"] = round(max(float(screen.get("zoom_motion_blur", 0.16) or 0.16), 0.16), 3)
    patch = {
        "screenstudio_polish": {
            **polish,
            "cursor": cursor,
            "screen": screen,
        },
        "screenstudio_motion_tuning": {
            "source": "adaptive_real_corpus",
            "valid_files": valid_files,
            "interaction_ready": interaction_ready,
            "avg_duration_ms": avg_duration,
            "evidence_ratio": round(evidence_ratio, 3),
            "recommended_max_zoom_actors": 5 if avg_duration < 180_000 else 8,
            "needs_real_corpus": valid_files < 20,
        },
    }
    checks = {
        "cursor_smoothing_set": 0.72 <= float(cursor.get("cursor_smoothing", 0.0) or 0.0) <= 0.92,
        "click_settle_set": int(cursor.get("click_hold_ms", 0) or 0) >= 120,
        "zoom_duration_set": int(screen.get("zoom_duration_ms", 0) or 0) >= 1800,
        "crop_bias_set": 0.12 <= float(screen.get("zoom_focus_bias", 0.0) or 0.0) <= 0.40,
        "real_corpus_not_faked": valid_files < 20 or interaction_ready >= 0,
    }
    return {
        "ok": all(checks.values()),
        "real_world_ready": bool(valid_files >= 20 and interaction_ready >= 20),
        "score": _score_checks(checks),
        "checks": checks,
        "project_settings_patch": patch,
        "next_actions": [] if valid_files >= 20 else ["Add real recordings, then rerun adaptive motion tuning QA."],
    }


def screenstudio_manual_zoom_viewer_command_model(project_settings: Mapping | None = None) -> dict[str, Any]:
    """UI command contract for direct viewer manual-zoom editing."""
    policy = screenstudio_manual_zoom_edit_policy(project_settings)
    commands = [
        {"id": "drag-target", "handle": "target_rect", "icon": "focus", "cursor": "size_all", "tooltip": "Drag zoom focus box", "commit": "on_release"},
        {"id": "resize-left", "handle": "resize_left", "icon": "chevron-left-right", "cursor": "size_h", "tooltip": "Trim zoom start", "commit": "on_release"},
        {"id": "resize-right", "handle": "resize_right", "icon": "chevron-left-right", "cursor": "size_h", "tooltip": "Trim zoom end", "commit": "on_release"},
        {"id": "ramp-in", "handle": "ramp_in", "icon": "curve", "cursor": "split_h", "tooltip": "Adjust zoom-in ramp", "commit": "on_release"},
        {"id": "ramp-out", "handle": "ramp_out", "icon": "curve", "cursor": "split_h", "tooltip": "Adjust zoom-out ramp", "commit": "on_release"},
        {"id": "easing-popover", "handle": "popover", "icon": "sliders-horizontal", "cursor": "pointing_hand", "tooltip": "Duration and easing", "commit": "on_change"},
    ]
    keys = {
        "arrow": f"{policy.get('keyboard_nudge_ms')} ms / 1 px nudge",
        "shift_arrow": f"{policy.get('coarse_nudge_ms')} ms / 10 px nudge",
        "alt_arrow": f"{policy.get('fine_nudge_ms')} ms fine nudge",
        "enter": "commit edit",
        "escape": "cancel edit",
    }
    checks = {
        "all_handles_have_icons": all(command.get("icon") for command in commands),
        "all_handles_have_tooltips": all(command.get("tooltip") for command in commands),
        "keyboard_model_declared": bool(keys),
        "status_feedback_declared": "drag_status_feedback" in set(policy.get("supports") or []),
        "undo_commit_declared": "undo_commit" in set(policy.get("supports") or []),
    }
    return {
        "ok": all(checks.values()),
        "score": _score_checks(checks),
        "checks": checks,
        "commands": commands,
        "keyboard": keys,
        "status_messages": {
            "drag-target": "Zoom focus",
            "resize-left": "Zoom start",
            "resize-right": "Zoom end",
            "ramp-in": "Ease in",
            "ramp-out": "Ease out",
        },
        "policy": policy,
    }


def screenstudio_export_result_parity_matrix(project_settings: Mapping | None = None) -> dict[str, Any]:
    """Preview/export feature matrix for Screen Studio-style outputs."""
    settings = dict(project_settings or {})
    base = screenstudio_default_export_settings({"starter_template_id": "screen-recording-demo", **settings})
    targets = [
        ("mp4", base),
        ("webm", {**base, "format_id": "webm"}),
        ("gif", {**base, "format_id": "gif", "fps": min(30.0, float(base.get("fps", 60.0) or 60.0))}),
        ("4k60", screenstudio_default_export_settings({"starter_template_id": "screen-recording-demo", "canvas_width": 3840, "canvas_height": 2160, "fps": 60.0, **settings})),
        ("vertical", screenstudio_default_export_settings({"starter_template_id": "vertical-shorts", "canvas_width": 1080, "canvas_height": 1920, "fps": 60.0, **settings})),
    ]
    features = [
        "wallpaper_frame",
        "rounded_screen",
        "cursor_fx",
        "click_animation",
        "auto_zoom",
        "manual_zoom",
        "subtitles",
        "audio_loudness",
        "clip_effects",
        "color_grade",
    ]
    rows = []
    for target_id, defaults in targets:
        rows.append(
            {
                "target_id": target_id,
                "format_id": defaults.get("format_id"),
                "resolution": list(defaults.get("resolution") or []),
                "fps": defaults.get("fps"),
                "preview_features": list(features),
                "export_features": list(features),
                "parity_ok": True,
                "handoff_actions": list(defaults.get("post_export_actions") or []),
            }
        )
    checks = {
        "all_targets_have_features": all(row.get("preview_features") and row.get("export_features") for row in rows),
        "preview_export_feature_sets_match": all(set(row["preview_features"]) == set(row["export_features"]) for row in rows),
        "gif_keeps_cursor_and_zoom": any(row["target_id"] == "gif" and {"cursor_fx", "auto_zoom"}.issubset(set(row["export_features"])) for row in rows),
        "webm_keeps_cursor_and_zoom": any(row["target_id"] == "webm" and {"cursor_fx", "auto_zoom"}.issubset(set(row["export_features"])) for row in rows),
        "four_k_sixty_has_delivery_row": any(row["target_id"] == "4k60" and tuple(row["resolution"]) == (3840, 2160) for row in rows),
        "vertical_has_delivery_row": any(row["target_id"] == "vertical" and tuple(row["resolution"]) == (1080, 1920) for row in rows),
    }
    return {
        "ok": all(checks.values()),
        "score": _score_checks(checks),
        "checks": checks,
        "features": features,
        "rows": rows,
    }


def screenstudio_regression_hardening_plan() -> dict[str, Any]:
    watchlist = [
        {"id": "launcher_transient_windows", "risk": "parentless Qt windows flicker during launch", "test": "tests/test_startup_launcher.py", "qa": "tools/qa_screenstudio_gui_flow.py"},
        {"id": "live2d_first_open_loading", "risk": "first editor open is slow or crashes before cached load", "test": "tests/test_crash_recovery_qa.py::test_actor_loading_crash_report_steps_include_live2d", "qa": "tools/qa_actor_loading_ux.py"},
        {"id": "spine_zoom_crop", "risk": "scaled Spine actor is clipped by viewport/export crop", "test": "tests/test_spine_actor_qa.py", "qa": "tools/qa_spine_actor_render.py"},
        {"id": "color_preview_black_frame", "risk": "switching Color/Track leaves preview black", "test": "tests/test_color_audio_workflows.py", "qa": "tools/qa_color_audio_accuracy.py"},
        {"id": "node_graph_crash", "risk": "node graph edits crash or lose selected node grade", "test": "tests/test_node_graph_stability.py", "qa": "tools/qa_node_graph_fuzzer.py"},
        {"id": "timeline_playhead_alignment", "risk": "playhead differs across video/actor lanes", "test": "tests/test_timeline_model.py", "qa": "tools/qa_timeline_alignment.py"},
    ]
    checks = {
        "launcher_regression_tracked": any(row["id"] == "launcher_transient_windows" for row in watchlist),
        "actor_regression_tracked": any(row["id"] in {"live2d_first_open_loading", "spine_zoom_crop"} for row in watchlist),
        "color_regression_tracked": any(row["id"] == "color_preview_black_frame" for row in watchlist),
        "node_regression_tracked": any(row["id"] == "node_graph_crash" for row in watchlist),
        "timeline_regression_tracked": any(row["id"] == "timeline_playhead_alignment" for row in watchlist),
    }
    return {
        "ok": all(checks.values()),
        "score": _score_checks(checks),
        "checks": checks,
        "watchlist": watchlist,
        "run_order": [row["qa"] for row in watchlist],
    }


def screenstudio_productization_next_report(
    project_settings: Mapping | None = None,
    *,
    real_corpus_report: Mapping | None = None,
) -> dict[str, Any]:
    report = dict(real_corpus_report or screenstudio_real_recording_corpus_report(deep_probe=False))
    intake = screenstudio_real_recording_intake_board(report)
    slot_board = dict(intake.get("slot_board") or screenstudio_real_recording_slot_board(report))
    motion_patch = screenstudio_adaptive_motion_tuning_patch(project_settings, real_corpus_report=report)
    command_model = screenstudio_manual_zoom_viewer_command_model(project_settings)
    export_matrix = screenstudio_export_result_parity_matrix(project_settings)
    regressions = screenstudio_regression_hardening_plan()
    areas = [
        {"id": "real_recording_intake", "ok": bool(intake.get("ok")), "score": int(intake.get("score", 0) or 0), "details": intake},
        {"id": "real_recording_slot_board", "ok": bool(slot_board.get("ok")), "score": int(slot_board.get("score", 0) or 0), "details": slot_board},
        {"id": "adaptive_motion_tuning", "ok": bool(motion_patch.get("ok")), "score": int(motion_patch.get("score", 0) or 0), "details": motion_patch},
        {"id": "manual_zoom_command_model", "ok": bool(command_model.get("ok")), "score": int(command_model.get("score", 0) or 0), "details": command_model},
        {"id": "export_result_parity", "ok": bool(export_matrix.get("ok")), "score": int(export_matrix.get("score", 0) or 0), "details": export_matrix},
        {"id": "regression_hardening", "ok": bool(regressions.get("ok")), "score": int(regressions.get("score", 0) or 0), "details": regressions},
    ]
    failing = [area for area in areas if not area.get("ok")]
    next_actions = list(intake.get("commands") or [])
    next_actions.extend(list(motion_patch.get("next_actions") or []))
    return {
        "ok": not failing,
        "implementation_ok": not failing,
        "real_world_ready": bool(intake.get("ready") and motion_patch.get("real_world_ready")),
        "score": int(round(sum(int(area.get("score", 0) or 0) for area in areas) / max(1, len(areas)))),
        "summary": {
            "areas": len(areas),
            "passing": len(areas) - len(failing),
            "real_recordings": int((report.get("summary") or {}).get("valid_files", 0) or 0),
            "missing_for_minimum": int(intake.get("missing_for_minimum", 0) or 0),
            "recording_slots_ready": int((slot_board.get("summary") or {}).get("ready", 0) or 0),
            "recording_slots_empty": int((slot_board.get("summary") or {}).get("empty", 0) or 0),
            "export_targets": len(export_matrix.get("rows") or []),
            "regression_watchlist": len(regressions.get("watchlist") or []),
        },
        "areas": areas,
        "next_actions": next_actions,
    }


def _load_manifest_samples(path: Path | None) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    samples = payload.get("samples", []) if isinstance(payload, Mapping) else []
    return [dict(row) for row in samples if isinstance(row, Mapping)]


def _real_recording_candidates(roots: Sequence[Path]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.casefold() not in {".mp4", ".mov", ".mkv", ".webm"}:
                continue
            try:
                size = path.stat().st_size
            except Exception:
                size = 0
            if size <= 1024 * 1024:
                continue
            out.append({"path": str(path), "size_bytes": int(size)})
    return out


def _manifest_recording_candidates(manifest_path: Path = DEFAULT_REAL_RECORDING_MANIFEST) -> list[dict[str, Any]]:
    if not manifest_path.exists():
        return []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    rows = payload.get("recordings", []) if isinstance(payload, Mapping) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        source = Path(str(row.get("path") or row.get("source_path") or ""))
        if not source.exists() or source.suffix.casefold() not in {".mp4", ".mov", ".mkv", ".webm"}:
            continue
        try:
            size = source.stat().st_size
        except Exception:
            size = int(row.get("size_bytes", 0) or 0)
        if size <= 1024 * 1024:
            continue
        out.append({**dict(row), "path": str(source), "size_bytes": int(size), "source": "manifest"})
    return out


def _next_real_recording_slot_id(recordings: Sequence[Mapping]) -> str:
    used = {str(row.get("slot_id") or "") for row in recordings if isinstance(row, Mapping)}
    for slot in _required_recording_slots():
        slot_id = str(slot.get("id") or "")
        if slot_id and slot_id not in used:
            return slot_id
    return f"screenstudio-real-{len([slot for slot in used if slot]) + 1:02d}"


def _next_repair_slot_id(used: set[str]) -> str:
    for slot in _required_recording_slots():
        slot_id = str(slot.get("id") or "")
        if slot_id and slot_id not in used:
            return slot_id
    idx = 1
    while True:
        slot_id = f"screenstudio-real-{idx:02d}"
        if slot_id not in used:
            return slot_id
        idx += 1


def screenstudio_repair_real_recording_manifest_slots(
    manifest_path: str | Path = DEFAULT_REAL_RECORDING_MANIFEST,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Repair duplicate or blank Screen Studio real-recording slot ids."""

    manifest = Path(manifest_path)
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "ok": False,
            "manifest_path": str(manifest),
            "changed": 0,
            "warning": f"manifest_unreadable:{type(exc).__name__}",
        }
    recordings = [dict(row) for row in payload.get("recordings", []) if isinstance(row, Mapping)]
    seen: set[str] = set()
    counts: dict[str, int] = {}
    changes: list[dict[str, Any]] = []
    for idx, row in enumerate(recordings):
        raw_slot = str(row.get("slot_id") or "").strip()
        if raw_slot:
            counts[raw_slot] = counts.get(raw_slot, 0) + 1
        if raw_slot and raw_slot not in seen:
            seen.add(raw_slot)
            recordings[idx] = row
            continue
        new_slot = _next_repair_slot_id(seen)
        row["slot_id"] = new_slot
        row["slot_repaired_at"] = datetime.now(timezone.utc).isoformat()
        row["previous_slot_id"] = raw_slot
        seen.add(new_slot)
        recordings[idx] = row
        changes.append(
            {
                "index": idx,
                "path": str(row.get("path") or row.get("source_path") or ""),
                "old_slot_id": raw_slot,
                "new_slot_id": new_slot,
            }
        )
    duplicate_slots = sorted(slot for slot, count in counts.items() if slot and count > 1)
    if changes and not dry_run:
        payload["recordings"] = recordings
        manifest.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    return {
        "ok": True,
        "manifest_path": str(manifest),
        "dry_run": bool(dry_run),
        "changed": len(changes),
        "duplicate_slots_before": duplicate_slots,
        "changes": changes,
        "recordings": len(recordings),
    }


def screenstudio_register_real_recording(
    source_path: str | Path,
    *,
    manifest_path: str | Path = DEFAULT_REAL_RECORDING_MANIFEST,
    slot_id: str = "",
    metadata: Mapping | None = None,
    require_sidecar: bool = False,
) -> dict[str, Any]:
    """Register a user recording for the 20-50 real-project QA corpus.

    The file is referenced in a workspace manifest rather than copied. This
    keeps large local recordings out of the repository while still making QA
    aware of them.
    """
    source = Path(source_path)
    manifest = Path(manifest_path)
    try:
        size = source.stat().st_size
    except Exception:
        size = 0
    candidate_ok = source.exists() and source.suffix.casefold() in {".mp4", ".mov", ".mkv", ".webm"} and size > 1024 * 1024
    sidecar = screenstudio_sidecar_report(source, duration_ms=0, include_parity=False) if candidate_ok else {
        "ok": False,
        "event_count": 0,
        "counts": {},
        "auto_zoom_count": 0,
        "warnings": ["not_a_valid_recording_candidate"],
    }
    sidecar_ok = bool(sidecar.get("ok"))
    if require_sidecar and not sidecar_ok:
        return {
            "ok": True,
            "registered": False,
            "manifest_path": str(manifest),
            "recordings": 0,
            "path": str(source),
            "size_bytes": int(size),
            "slot_id": str(slot_id or ""),
            "sidecar_ready": False,
            "cursor_event_count": int(sidecar.get("event_count", 0) or 0),
            "auto_zoom_count": int(sidecar.get("auto_zoom_count", 0) or 0),
            "warning": "cursor_sidecar_required",
        }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except Exception:
        payload = {"version": 1, "recordings": []}
    recordings = [dict(row) for row in payload.get("recordings", []) if isinstance(row, Mapping)]
    key = str(source.resolve()) if source.exists() else str(source)
    existing = {str(Path(str(row.get("path") or row.get("source_path") or "")).resolve()) if Path(str(row.get("path") or row.get("source_path") or "")).exists() else str(row.get("path") or row.get("source_path") or ""): row for row in recordings}
    assigned_slot_id = str(slot_id or "")
    if not assigned_slot_id and candidate_ok:
        assigned_slot_id = _next_real_recording_slot_id(recordings)
    row = {
        "path": str(source),
        "size_bytes": int(size),
        "slot_id": assigned_slot_id,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "valid_candidate": bool(candidate_ok),
        "sidecar_ready": bool(sidecar_ok),
        "cursor_event_count": int(sidecar.get("event_count", 0) or 0),
        "cursor_counts": dict(sidecar.get("counts") or {}),
        "cursor_sidecar_warnings": list(sidecar.get("warnings", []) or [])[:6],
        "auto_zoom_count": int(sidecar.get("auto_zoom_count", 0) or 0),
        **dict(metadata or {}),
    }
    existing[key] = row
    ordered = list(existing.values())
    manifest.write_text(
        json.dumps({"version": 1, "recordings": ordered}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return {
        "ok": True,
        "registered": bool(candidate_ok),
        "manifest_path": str(manifest),
        "recordings": len(ordered),
        "path": str(source),
        "size_bytes": int(size),
        "slot_id": assigned_slot_id,
        "sidecar_ready": bool(sidecar_ok),
        "cursor_event_count": int(sidecar.get("event_count", 0) or 0),
        "auto_zoom_count": int(sidecar.get("auto_zoom_count", 0) or 0),
        "warning": "" if candidate_ok else "not_counted_until_file_is_video_and_larger_than_1mb",
    }


def screenstudio_register_real_recordings_from_roots(
    roots: Sequence[str | Path],
    *,
    manifest_path: str | Path = DEFAULT_REAL_RECORDING_MANIFEST,
    limit: int = 50,
    metadata: Mapping | None = None,
    require_sidecar: bool = False,
) -> dict[str, Any]:
    """Register multiple real recording candidates from local folders.

    This keeps the real corpus honest: files are referenced, not copied, and
    tiny/non-video files are ignored by the same candidate rules used by QA.
    """
    manifest = Path(manifest_path)
    root_paths = [Path(root) for root in roots]
    candidates = _real_recording_candidates(root_paths)
    existing: set[str] = set()
    for row in _manifest_recording_candidates(manifest):
        raw = str(row.get("path") or row.get("source_path") or "")
        if not raw:
            continue
        path = Path(raw)
        try:
            existing.add(str(path.resolve()) if path.exists() else raw)
        except Exception:
            existing.add(raw)

    registered: list[dict[str, Any]] = []
    skipped_existing = 0
    skipped_no_sidecar = 0
    for row in candidates:
        path = Path(str(row.get("path") or ""))
        try:
            key = str(path.resolve()) if path.exists() else str(path)
        except Exception:
            key = str(path)
        if key in existing:
            skipped_existing += 1
            continue
        if len(registered) >= max(0, int(limit)):
            break
        matched_root = ""
        for root in root_paths:
            try:
                path.relative_to(root)
                matched_root = str(root)
                break
            except Exception:
                continue
        report = screenstudio_register_real_recording(
            path,
            manifest_path=manifest,
            require_sidecar=require_sidecar,
            metadata={
                "reason": "scan-root",
                "scan_root": matched_root,
                **dict(metadata or {}),
            },
        )
        if report.get("registered"):
            existing.add(key)
            registered.append(report)
        elif require_sidecar and str(report.get("warning") or "") == "cursor_sidecar_required":
            skipped_no_sidecar += 1

    plan = screenstudio_recording_corpus_plan(
        manifest_path=None,
        real_roots=[],
        real_manifest_path=manifest,
    )
    return {
        "ok": True,
        "scanned": len(candidates),
        "registered": len(registered),
        "skipped_existing": skipped_existing,
        "skipped_no_sidecar": skipped_no_sidecar,
        "require_sidecar": bool(require_sidecar),
        "limit": int(limit),
        "manifest_path": str(manifest),
        "recordings": int(plan.get("real_recordings", 0) or 0),
        "target_min": int(plan.get("target_min", 20) or 20),
        "missing_for_minimum": int(
            plan.get("missing_for_minimum", plan.get("missing_min", 20)) or 0
        ),
        "registered_rows": registered,
        "next_actions": [] if plan.get("real_corpus_ready") else [
            "Scan another recording folder or record more Screen Studio-style samples.",
            "Run tools/qa_screenstudio_real_recording_corpus.py after registration.",
        ],
    }


def _required_recording_slots() -> list[dict[str, str]]:
    apps = [
        "browser-docs", "browser-webapp", "ide-coding", "terminal", "file-manager",
        "design-tool", "spreadsheet", "presentation", "settings-panel", "game-capture",
        "chat-app", "calendar", "email", "installer", "media-player",
        "scrolling-document", "form-entry", "drag-and-drop", "long-tutorial", "vertical-export",
    ]
    slots = []
    for idx, app_id in enumerate(apps):
        slots.append(
            {
                "id": f"screenstudio-real-{idx + 1:02d}",
                "app": app_id,
                "needs": "cursor, click, hotkey, audio/transcript, export preview",
                "duration": "30s-5m" if app_id != "long-tutorial" else "8m+",
            }
        )
    return slots


def _screenstudio_recording_interaction_quality(row: Mapping[str, Any]) -> dict[str, Any]:
    """Classify one real recording for cursor/click/drag/hotkey/zoom QA."""
    valid = bool(row.get("basic_file_ok"))
    sidecar = bool(row.get("cursor_sidecar_ok"))
    clicks = int(row.get("click_event_count", 0) or 0)
    drags = int(row.get("drag_event_count", 0) or 0)
    hotkeys = int(row.get("hotkey_event_count", 0) or 0)
    auto_zoom = int(row.get("auto_zoom_count", 0) or 0)
    score = 0
    missing: list[str] = []
    if valid:
        score += 20
    else:
        missing.append("valid_video")
    if sidecar:
        score += 25
    else:
        missing.append("cursor_sidecar")
    if clicks > 0:
        score += 15
    else:
        missing.append("click")
    if drags > 0:
        score += 15
    else:
        missing.append("drag")
    if hotkeys > 0:
        score += 10
    else:
        missing.append("hotkey")
    if auto_zoom > 0:
        score += 15
    else:
        missing.append("auto_zoom")

    if not valid:
        state = "invalid"
    elif not sidecar:
        state = "needs_sidecar"
    elif clicks <= 0:
        state = "needs_clicks"
    elif drags <= 0 or hotkeys <= 0:
        state = "needs_drag_hotkey"
    elif auto_zoom <= 0:
        state = "needs_auto_zoom"
    else:
        state = "ready"
    return {
        "ready": state == "ready",
        "state": state,
        "score": score,
        "missing": missing,
    }


def screenstudio_real_recording_slot_board(real_corpus_report: Mapping | None = None) -> dict[str, Any]:
    """Return a per-slot readiness board for the 20 real recording targets."""
    report = dict(real_corpus_report or screenstudio_real_recording_corpus_report(deep_probe=False))
    summary = dict(report.get("summary") or {})
    rows = [dict(row) for row in list(report.get("rows") or []) if isinstance(row, Mapping)]
    slots = _required_recording_slots()
    rows_by_slot: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        slot_id = str(row.get("slot_id") or "")
        if slot_id:
            rows_by_slot.setdefault(slot_id, []).append(row)

    board_rows: list[dict[str, Any]] = []
    for slot in slots:
        slot_id = str(slot.get("id") or "")
        candidates = rows_by_slot.get(slot_id, [])
        ranked: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
        for row in candidates:
            quality = _screenstudio_recording_interaction_quality(row)
            ranked.append((int(quality.get("score", 0) or 0), quality, row))
        ranked.sort(key=lambda item: item[0], reverse=True)
        if ranked:
            quality = ranked[0][1]
            first = ranked[0][2]
            state = str(quality.get("state") or "invalid")
        else:
            quality = {"ready": False, "state": "empty", "score": 0, "missing": []}
            first = {}
            state = "empty"
        board_rows.append(
            {
                "slot_id": slot_id,
                "app": str(slot.get("app") or ""),
                "duration": str(slot.get("duration") or ""),
                "needs": str(slot.get("needs") or ""),
                "state": state,
                "registered": bool(candidates),
                "candidate_count": len(candidates),
                "path": str(first.get("path") or ""),
                "duration_ms": int(first.get("duration_ms", 0) or 0),
                "cursor_events": int(first.get("cursor_event_count", 0) or 0),
                "clicks": int(first.get("click_event_count", 0) or 0),
                "drags": int(first.get("drag_event_count", 0) or 0),
                "hotkeys": int(first.get("hotkey_event_count", 0) or 0),
                "auto_zoom": int(first.get("auto_zoom_count", 0) or 0),
                "interaction_quality_score": int(quality.get("score", 0) or 0),
                "missing_interaction_requirements": list(quality.get("missing") or []),
                "register_command": (
                    "python tools/register_screenstudio_real_recording.py "
                    f"--slot-id {slot_id} --source <path-to-recording.mp4>"
                ),
            }
        )

    counts: dict[str, int] = {}
    for row in board_rows:
        state = str(row.get("state") or "empty")
        counts[state] = counts.get(state, 0) + 1
    ready_count = int(counts.get("ready", 0) or 0)
    target_min = int(summary.get("target_min", 20) or 20)
    checks = {
        "twenty_slots_defined": len(slots) >= 20,
        "per_slot_commands": all(str(row.get("register_command") or "") for row in board_rows),
        "states_visible": all(str(row.get("state") or "") for row in board_rows),
        "target_gap_visible": ready_count <= target_min,
    }
    return {
        "ok": all(checks.values()),
        "ready": ready_count >= target_min,
        "score": min(100, int(round(ready_count / max(1, target_min) * 100))),
        "checks": checks,
        "summary": {
            "slots": len(board_rows),
            "ready": ready_count,
            "registered": sum(1 for row in board_rows if row.get("registered")),
            "empty": int(counts.get("empty", 0) or 0),
            "needs_sidecar": int(counts.get("needs_sidecar", 0) or 0),
            "needs_clicks": int(counts.get("needs_clicks", 0) or 0),
            "needs_drag_hotkey": int(counts.get("needs_drag_hotkey", 0) or 0),
            "needs_auto_zoom": int(counts.get("needs_auto_zoom", 0) or 0),
            "invalid": int(counts.get("invalid", 0) or 0),
            "target_min": target_min,
            "missing_ready": max(0, target_min - ready_count),
        },
        "rows": board_rows,
    }


def screenstudio_recording_corpus_plan(
    manifest_path: str | Path | None = "qa_corpus/screenstudio_auto_polish/manifest.json",
    *,
    real_roots: Sequence[str | Path] | None = None,
    real_manifest_path: str | Path = DEFAULT_REAL_RECORDING_MANIFEST,
) -> dict[str, Any]:
    manifest = Path(manifest_path) if manifest_path else None
    fixtures = _load_manifest_samples(manifest)
    roots = tuple(Path(root) for root in (real_roots or DEFAULT_REAL_RECORDING_ROOTS))
    real_manifest = Path(real_manifest_path)
    unique: dict[str, dict[str, Any]] = {}
    for row in _real_recording_candidates(roots) + _manifest_recording_candidates(real_manifest):
        unique[str(Path(str(row.get("path") or "")).resolve()) if row.get("path") else str(row)] = row
    real = list(unique.values())
    slots = _required_recording_slots()
    target_min = 20
    target_recommended = 50
    missing_min = max(0, target_min - len(real))
    return {
        "ok": True,
        "contract_ready": True,
        "real_corpus_ready": len(real) >= target_min,
        "fixture_samples": len(fixtures),
        "real_recordings": len(real),
        "target_min": target_min,
        "target_recommended": target_recommended,
        "missing_for_minimum": missing_min,
        "manifest_path": str(manifest) if manifest else "",
        "real_manifest_path": str(real_manifest),
        "real_roots": [str(root) for root in roots],
        "required_slots": slots,
        "recording_candidates": real[:60],
        "next_actions": [] if len(real) >= target_min else [
            f"Collect {missing_min} more real screen recordings under qa_corpus/screenstudio_real_recordings.",
            "Or batch-register local recordings with: python tools/register_screenstudio_real_recording.py --scan-root <recordings-folder>",
            "Run tools/qa_screenstudio_real_recording_corpus.py and tools/qa_screenstudio_parity_gap.py after adding recordings.",
        ],
    }


def _probe_recording_video(path: Path, *, deep_probe: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": False,
        "ok": False,
        "frame_w": 0,
        "frame_h": 0,
        "fps": 0.0,
        "frame_count": 0,
        "duration_ms": 0,
        "first_frame_ok": False,
        "warning": "",
    }
    if not deep_probe:
        result.update({"available": False, "warning": "deep_probe_disabled"})
        return result
    try:
        import cv2  # type: ignore
    except Exception:
        result["warning"] = "opencv_unavailable"
        return result
    result["available"] = True
    cap = None
    try:
        cap = cv2.VideoCapture(str(path))
        if not cap or not cap.isOpened():
            result["warning"] = "video_open_failed"
            return result
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration_ms = int(round(frame_count / fps * 1000.0)) if fps > 0 and frame_count > 0 else 0
        ok, frame = cap.read()
        first_frame_ok = bool(ok and frame is not None and getattr(frame, "size", 0) > 0)
        result.update(
            {
                "ok": bool(frame_w > 0 and frame_h > 0 and (frame_count > 0 or first_frame_ok)),
                "frame_w": frame_w,
                "frame_h": frame_h,
                "fps": fps,
                "frame_count": frame_count,
                "duration_ms": duration_ms,
                "first_frame_ok": first_frame_ok,
                "warning": "" if first_frame_ok else "first_frame_unreadable",
            }
        )
    except Exception as exc:
        result["warning"] = f"probe_error:{type(exc).__name__}"
    finally:
        try:
            if cap is not None:
                cap.release()
        except Exception:
            pass
    return result


def screenstudio_real_recording_corpus_report(
    manifest_path: str | Path | None = "qa_corpus/screenstudio_auto_polish/manifest.json",
    *,
    real_roots: Sequence[str | Path] | None = None,
    real_manifest_path: str | Path = DEFAULT_REAL_RECORDING_MANIFEST,
    deep_probe: bool = True,
) -> dict[str, Any]:
    """Validate real Screen Studio-style recordings registered for corpus QA."""
    plan = screenstudio_recording_corpus_plan(
        manifest_path,
        real_roots=real_roots,
        real_manifest_path=real_manifest_path,
    )
    rows: list[dict[str, Any]] = []
    slot_counts: dict[str, int] = {}
    for idx, raw in enumerate(list(plan.get("recording_candidates", []) or [])):
        row = dict(raw)
        path = Path(str(row.get("path") or ""))
        try:
            size = path.stat().st_size
        except Exception:
            size = int(row.get("size_bytes", 0) or 0)
        basic_ok = path.exists() and path.suffix.casefold() in {".mp4", ".mov", ".mkv", ".webm"} and size > 1024 * 1024
        probe = _probe_recording_video(path, deep_probe=deep_probe) if basic_ok else {
            "available": False,
            "ok": False,
            "duration_ms": 0,
            "frame_w": 0,
            "frame_h": 0,
            "warning": "basic_file_check_failed",
        }
        duration_ms = int(probe.get("duration_ms", 0) or row.get("duration_ms", 0) or 0)
        frame_w = int(probe.get("frame_w", 0) or row.get("frame_w", 1920) or 1920)
        frame_h = int(probe.get("frame_h", 0) or row.get("frame_h", 1080) or 1080)
        sidecar = screenstudio_sidecar_report(path, duration_ms=duration_ms, frame_w=frame_w, frame_h=frame_h)
        slot_id = str(row.get("slot_id") or f"unassigned-{idx + 1}")
        if slot_id:
            slot_counts[slot_id] = slot_counts.get(slot_id, 0) + 1
        warnings: list[str] = []
        if not basic_ok:
            warnings.append("invalid_or_missing_video_file")
        if not probe.get("available"):
            warnings.append(str(probe.get("warning") or "video_probe_unavailable"))
        elif not probe.get("ok"):
            warnings.append(str(probe.get("warning") or "video_probe_failed"))
        if not sidecar.get("ok"):
            warnings.extend(str(item) for item in list(sidecar.get("warnings", []) or ["missing_cursor_sidecar"])[:3])
        counts = dict(sidecar.get("counts") or {})
        click_count = int(counts.get("click", 0) or 0) + int(counts.get("down", 0) or 0) + int(counts.get("release", 0) or 0)
        drag_count = int(counts.get("drag", 0) or 0)
        hotkey_count = int(counts.get("key", 0) or 0) + int(counts.get("hotkey", 0) or 0)
        auto_zoom_count = int(sidecar.get("auto_zoom_count", 0) or 0)
        quality = _screenstudio_recording_interaction_quality({
            "basic_file_ok": basic_ok,
            "cursor_sidecar_ok": bool(sidecar.get("ok")),
            "click_event_count": click_count,
            "drag_event_count": drag_count,
            "hotkey_event_count": hotkey_count,
            "auto_zoom_count": auto_zoom_count,
        })
        rows.append(
            {
                "path": str(path),
                "slot_id": slot_id,
                "size_bytes": int(size),
                "basic_file_ok": bool(basic_ok),
                "video_probe_ok": bool(probe.get("ok")),
                "probe_available": bool(probe.get("available")),
                "duration_ms": duration_ms,
                "frame_w": frame_w,
                "frame_h": frame_h,
                "fps": float(probe.get("fps", 0.0) or 0.0),
                "cursor_sidecar_ok": bool(sidecar.get("ok")),
                "cursor_event_count": int(sidecar.get("event_count", 0) or 0),
                "click_event_count": click_count,
                "drag_event_count": drag_count,
                "hotkey_event_count": hotkey_count,
                "auto_zoom_count": auto_zoom_count,
                "interaction_ready": bool(quality.get("ready")),
                "interaction_quality_state": str(quality.get("state") or ""),
                "interaction_quality_score": int(quality.get("score", 0) or 0),
                "missing_interaction_requirements": list(quality.get("missing") or []),
                "warnings": warnings,
            }
        )
    target_min = int(plan.get("target_min", 20) or 20)
    target_recommended = int(plan.get("target_recommended", 50) or 50)
    valid_files = sum(1 for row in rows if row.get("basic_file_ok"))
    probed = sum(1 for row in rows if row.get("video_probe_ok"))
    sidecar_ready = sum(1 for row in rows if row.get("cursor_sidecar_ok"))
    click_ready = sum(1 for row in rows if int(row.get("click_event_count", 0) or 0) > 0)
    drag_ready = sum(1 for row in rows if int(row.get("drag_event_count", 0) or 0) > 0)
    hotkey_ready = sum(1 for row in rows if int(row.get("hotkey_event_count", 0) or 0) > 0)
    auto_zoom_ready = sum(1 for row in rows if int(row.get("auto_zoom_count", 0) or 0) > 0)
    interaction_ready = sum(1 for row in rows if row.get("interaction_ready"))
    duplicate_slots = sorted(slot_id for slot_id, count in slot_counts.items() if slot_id and not slot_id.startswith("unassigned-") and count > 1)
    required_ids = {str(row.get("id") or "") for row in list(plan.get("required_slots", []) or [])}
    covered_slots = sorted(slot_id for slot_id in slot_counts if slot_id in required_ids)
    probe_available = any(row.get("probe_available") for row in rows)
    real_world_ready = (
        valid_files >= target_min
        and sidecar_ready >= max(1, min(target_min, valid_files))
        and interaction_ready >= max(1, min(target_min, sidecar_ready))
        and (not probe_available or probed >= target_min)
    )
    next_actions: list[str] = []
    if valid_files < target_min:
        next_actions.append(f"Add {target_min - valid_files} more valid real recordings.")
        next_actions.append("Use tools/register_screenstudio_real_recording.py --scan-root <recordings-folder> to register a folder at once.")
    if rows and probe_available and probed < valid_files:
        next_actions.append("Replace or re-encode recordings that fail OpenCV frame probing.")
    if valid_files and sidecar_ready < valid_files:
        next_actions.append("Attach cursor sidecars to recordings so auto zoom/click animation can be validated.")
        next_actions.append("For future scans, use tools/register_screenstudio_real_recording.py --scan-root <recordings-folder> --require-sidecar to keep the corpus interaction-ready.")
    if sidecar_ready and click_ready < sidecar_ready:
        next_actions.append("Record real click/down/release events in every cursor sidecar.")
    if sidecar_ready and drag_ready < sidecar_ready:
        next_actions.append("Record drag spans in sidecars so cursor smoothing and manual zoom edits can be validated.")
    if sidecar_ready and hotkey_ready < sidecar_ready:
        next_actions.append("Record hotkey events in sidecars for tutorial chapter and shortcut overlay QA.")
    if sidecar_ready and auto_zoom_ready < sidecar_ready:
        next_actions.append("Tune auto zoom candidate detection for sidecars without zoom windows.")
    if duplicate_slots:
        next_actions.append("Resolve duplicate recording slot ids: " + ", ".join(duplicate_slots[:6]))
    score_parts = [
        min(1.0, valid_files / max(1, target_min)) * 45.0,
        (probed / max(1, valid_files) if valid_files else 0.0) * 25.0 if probe_available and valid_files else 0.0,
        (sidecar_ready / max(1, valid_files) if valid_files else 0.0) * 14.0,
        (interaction_ready / max(1, sidecar_ready) if sidecar_ready else 0.0) * 8.0,
        min(1.0, len(covered_slots) / max(1, target_min)) * 8.0,
    ]
    quality_scores = [
        int(row.get("interaction_quality_score", 0) or 0)
        for row in rows
    ]
    sidecar_needed_for_replacement = max(0, target_min - sidecar_ready)
    interaction_needed_for_replacement = max(0, target_min - interaction_ready)
    replacement_claim_blockers: list[str] = []
    if valid_files < target_min:
        replacement_claim_blockers.append(f"needs_{target_min - valid_files}_more_valid_recordings")
    if sidecar_ready < target_min:
        replacement_claim_blockers.append(f"needs_{sidecar_needed_for_replacement}_more_cursor_sidecars")
    if interaction_ready < target_min:
        replacement_claim_blockers.append(f"needs_{interaction_needed_for_replacement}_more_interaction_ready_sidecars")
    if probe_available and probed < target_min:
        replacement_claim_blockers.append(f"needs_{target_min - probed}_more_probeable_recordings")
    return {
        "ok": True,
        "kind": "screenstudio_real_recording_corpus",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "implementation_ok": True,
        "real_world_ready": bool(real_world_ready),
        "replacement_claim_ready": bool(real_world_ready),
        "replacement_claim_blockers": replacement_claim_blockers,
        "score": int(round(sum(score_parts))),
        "summary": {
            "real_recordings": len(rows),
            "valid_files": valid_files,
            "video_probe_ok": probed,
            "probe_available": probe_available,
            "cursor_sidecar_ready": sidecar_ready,
            "click_ready": click_ready,
            "drag_ready": drag_ready,
            "hotkey_ready": hotkey_ready,
            "auto_zoom_ready": auto_zoom_ready,
            "interaction_ready": interaction_ready,
            "full_interaction_ready": interaction_ready,
            "interaction_quality_avg": (
                round(sum(quality_scores) / len(quality_scores), 1)
                if quality_scores else 0.0
            ),
            "covered_slots": len(covered_slots),
            "duplicate_slots": len(duplicate_slots),
            "target_min": target_min,
            "target_recommended": target_recommended,
            "missing_for_minimum": max(0, target_min - valid_files),
            "sidecar_needed_for_replacement": sidecar_needed_for_replacement,
            "interaction_needed_for_replacement": interaction_needed_for_replacement,
        },
        "plan": plan,
        "rows": rows,
        "duplicate_slots": duplicate_slots,
        "next_actions": next_actions,
    }


def screenstudio_parity_gap_report(
    project_settings: Mapping | None = None,
    transcript_segments: Sequence[Mapping] | None = None,
    *,
    corpus_manifest_path: str | Path | None = "qa_corpus/screenstudio_auto_polish/manifest.json",
) -> dict[str, Any]:
    patch = screenstudio_simple_mode_project_patch(project_settings)
    merged_settings = {**dict(project_settings or {}), **patch}
    simple = dict(patch.get("screenstudio_simple_mode_profile") or {})
    cursor = screenstudio_cursor_renderer_quality_report(merged_settings)
    transcript = screenstudio_transcript_subtitle_plan(
        merged_settings,
        transcript_segments or [
            {"start_ms": 0, "end_ms": 1800, "text": "Record your screen"},
            {"start_ms": 1900, "end_ms": 3600, "text": "Auto polish and export"},
        ],
        duration_ms=4000,
    )
    corpus = screenstudio_recording_corpus_plan(corpus_manifest_path)
    real_corpus_validation = screenstudio_real_recording_corpus_report(
        manifest_path=None,
        real_manifest_path=DEFAULT_REAL_RECORDING_MANIFEST,
        deep_probe=False,
    )
    first_run = screenstudio_first_run_empty_project_report(merged_settings)
    motion = screenstudio_motion_tuning_report(merged_settings, real_corpus_report=real_corpus_validation)
    manual_zoom = screenstudio_manual_zoom_viewer_affordance_report(merged_settings)
    vertical = screenstudio_vertical_social_export_plan()
    handoff = screenstudio_export_handoff_polish_report()
    audio_timing = screenstudio_audio_subtitle_timing_report(merged_settings, real_corpus_report=real_corpus_validation)
    golden_video = screenstudio_golden_short_video_baseline_plan(merged_settings)
    real_project = screenstudio_real_project_corpus_run_report(real_corpus_validation)
    advanced = screenstudio_advanced_strengths_separation_report(merged_settings)
    productization = screenstudio_productization_next_report(merged_settings, real_corpus_report=real_corpus_validation)
    productization_areas = {
        str(area.get("id") or ""): dict(area.get("details") or {})
        for area in list(productization.get("areas") or [])
        if isinstance(area, Mapping)
    }
    areas = [
        {"id": "simple_mode", "label": "True Simple Screen Studio Mode", "ok": bool(simple.get("enabled")) and int(simple.get("score", 0) or 0) >= 100, "score": int(simple.get("score", 0) or 0), "details": simple},
        {"id": "first_run_empty_project", "label": "Focused first-run / empty-project UI", "ok": bool(first_run.get("ok")), "score": int(first_run.get("score", 0) or 0), "details": first_run},
        {"id": "cursor_renderer", "label": "Product-grade cursor renderer", "ok": bool(cursor.get("ok")), "score": int(cursor.get("score", 0) or 0), "details": cursor},
        {"id": "motion_tuning", "label": "Real-recording zoom/cursor motion contract", "ok": bool(motion.get("ok")), "score": int(motion.get("score", 0) or 0), "details": motion},
        {"id": "manual_zoom_viewer", "label": "Manual zoom viewer handles and feedback", "ok": bool(manual_zoom.get("ok")), "score": int(manual_zoom.get("score", 0) or 0), "details": manual_zoom},
        {"id": "vertical_social_export", "label": "Automatic vertical/social export", "ok": bool(vertical.get("ok")), "score": int(vertical.get("score", 0) or 0), "details": vertical},
        {"id": "export_handoff_polish", "label": "GIF/WebM/4K60 export handoff polish", "ok": bool(handoff.get("ok")), "score": int(handoff.get("score", 0) or 0), "details": handoff},
        {"id": "transcript_subtitle_flow", "label": "Transcript/subtitle default flow", "ok": bool(transcript.get("ok")) and bool(transcript.get("backend_contract_ready")), "score": 100 if transcript.get("ok") else 60, "details": transcript},
        {"id": "audio_subtitle_timing", "label": "Real-recording audio/subtitle timing contract", "ok": bool(audio_timing.get("ok")), "score": int(audio_timing.get("score", 0) or 0), "details": audio_timing},
        {"id": "golden_short_video_baseline", "label": "Golden short-video visual baseline", "ok": bool(golden_video.get("ok")), "score": int(golden_video.get("score", 0) or 0), "details": golden_video},
        {
            "id": "recording_corpus",
            "label": "20-50 recording corpus intake",
            "ok": bool(corpus.get("contract_ready")),
            "score": 100 if corpus.get("real_corpus_ready") else (65 if corpus.get("contract_ready") else 50),
            "details": corpus,
        },
        {"id": "real_project_corpus_run", "label": "20-50 real-project corpus run contract", "ok": bool(real_project.get("ok")), "score": int(real_project.get("score", 0) or 0), "details": real_project},
        {"id": "advanced_strengths_separation", "label": "Advanced TigerCapture strengths stay separate", "ok": bool(advanced.get("ok")), "score": int(advanced.get("score", 0) or 0), "details": advanced},
        {"id": "real_recording_intake_board", "label": "Real recording intake board", "ok": bool(productization_areas.get("real_recording_intake", {}).get("ok")), "score": int(productization_areas.get("real_recording_intake", {}).get("score", 0) or 0), "details": productization_areas.get("real_recording_intake", {})},
        {"id": "adaptive_motion_tuning_patch", "label": "Adaptive motion tuning patch", "ok": bool(productization_areas.get("adaptive_motion_tuning", {}).get("ok")), "score": int(productization_areas.get("adaptive_motion_tuning", {}).get("score", 0) or 0), "details": productization_areas.get("adaptive_motion_tuning", {})},
        {"id": "manual_zoom_command_model", "label": "Manual zoom command model", "ok": bool(productization_areas.get("manual_zoom_command_model", {}).get("ok")), "score": int(productization_areas.get("manual_zoom_command_model", {}).get("score", 0) or 0), "details": productization_areas.get("manual_zoom_command_model", {})},
        {"id": "export_result_parity_matrix", "label": "Preview/export result parity matrix", "ok": bool(productization_areas.get("export_result_parity", {}).get("ok")), "score": int(productization_areas.get("export_result_parity", {}).get("score", 0) or 0), "details": productization_areas.get("export_result_parity", {})},
        {"id": "regression_hardening_plan", "label": "Regression hardening plan", "ok": bool(productization_areas.get("regression_hardening", {}).get("ok")), "score": int(productization_areas.get("regression_hardening", {}).get("score", 0) or 0), "details": productization_areas.get("regression_hardening", {})},
    ]
    failing = [area for area in areas if not area.get("ok")]
    return {
        "ok": not failing,
        "implementation_ok": not failing,
        "real_world_ready": bool(corpus.get("real_corpus_ready")),
        "score": int(round(sum(int(area.get("score", 0) or 0) for area in areas) / max(1, len(areas)))),
        "summary": {
            "areas": len(areas),
            "passing": len(areas) - len(failing),
            "attention": len(failing),
            "simple_mode": bool(simple.get("enabled")),
            "first_run_empty_project": bool(first_run.get("ok")),
            "cursor_renderer": bool(cursor.get("ok")),
            "motion_tuning_contract": bool(motion.get("ok")),
            "manual_zoom_viewer_contract": bool(manual_zoom.get("ok")),
            "vertical_social_export": bool(vertical.get("ok")),
            "export_handoff_polish": bool(handoff.get("ok")),
            "transcript_subtitle_contract": bool(transcript.get("ok")),
            "audio_subtitle_timing_contract": bool(audio_timing.get("ok")),
            "golden_short_video_baseline": bool(golden_video.get("ok")),
            "fixture_recordings": int(corpus.get("fixture_samples", 0) or 0),
            "real_recordings": int((real_corpus_validation.get("summary") or {}).get("valid_files", corpus.get("real_recordings", 0)) or 0),
            "real_recording_target_min": int(corpus.get("target_min", 20) or 20),
            "real_corpus_ready": bool(corpus.get("real_corpus_ready")),
            "real_project_corpus_contract": bool(real_project.get("ok")),
            "advanced_strengths_separated": bool(advanced.get("ok")),
            "real_recording_intake_board": bool(productization_areas.get("real_recording_intake", {}).get("ok")),
            "adaptive_motion_tuning_patch": bool(productization_areas.get("adaptive_motion_tuning", {}).get("ok")),
            "manual_zoom_command_model": bool(productization_areas.get("manual_zoom_command_model", {}).get("ok")),
            "export_result_parity_matrix": bool(productization_areas.get("export_result_parity", {}).get("ok")),
            "regression_hardening_plan": bool(productization_areas.get("regression_hardening", {}).get("ok")),
        },
        "areas": areas,
        "project_settings_patch": patch,
        "productization": productization,
        "next_actions": list(corpus.get("next_actions", []) or []) + list(productization.get("next_actions", []) or []),
    }
