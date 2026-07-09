from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication as _QApplication, QFileDialog, QMessageBox, QWidget

from app.audio_tracks import AUDIO_EXTS, VIDEO_EXTS, is_video_path
from app.capcut_features import capcut_disabled_reason, capcut_feature_disabled, capcut_feature_enabled
from app.subtitles import Subtitle
from app.typography import TextClip
from app.video_editor_media_proxy import _probe_video_dimensions
from app.video_editor_screenstudio_dialogs import ScreenStudioPolishDialog as _ScreenStudioPolishDialog
from app import video_editor_export_workflow as _export_workflow
from app.video_editor_workbench_section_scroll import make_workbench_section_scroll_area


class _WindowModuleProxy:
    def __init__(self, name: str, fallback):
        self._name = name
        self._fallback = fallback

    def _target(self):
        module = sys.modules.get("app.video_editor_window")
        if module is not None:
            return getattr(module, self._name, self._fallback)
        return self._fallback

    def __getattr__(self, attr: str):
        return getattr(self._target(), attr)

    def __call__(self, *args, **kwargs):
        return self._target()(*args, **kwargs)


QApplication = _WindowModuleProxy("QApplication", _QApplication)
ScreenStudioPolishDialog = _WindowModuleProxy("ScreenStudioPolishDialog", _ScreenStudioPolishDialog)


def _capcut_feature_enabled(feature_id: str) -> bool:
    try:
        from app.capcut_features import capcut_feature_enabled

        return bool(capcut_feature_enabled(feature_id))
    except Exception:
        return False


def _capcut_feature_disabled(feature_id: str) -> bool:
    return not _capcut_feature_enabled(feature_id)


def _capcut_disabled_reason(feature_id: str) -> str:
    try:
        from app.capcut_features import capcut_disabled_reason

        return str(capcut_disabled_reason(feature_id))
    except Exception:
        return f"{feature_id} is temporarily sealed."


def _screenstudio_simple_mode_enabled(self) -> bool:
    settings = getattr(self, "_project_settings", {}) or {}
    simple_ui = dict(settings.get("screenstudio_simple_mode_ui") or {})
    return bool(
        settings.get("screenstudio_simple_mode")
        or simple_ui.get("layout") == "simple_screen_studio"
    )


def _apply_screenstudio_simple_mode_ui(self) -> None:
    simple = self._screenstudio_simple_mode_enabled()
    standard_btn = getattr(self, "workspace_standard_btn", None)
    simple_btn = getattr(self, "workspace_simple_btn", None)
    for button, checked in ((standard_btn, not simple), (simple_btn, simple)):
        if button is not None and button.isChecked() != checked:
            old = button.blockSignals(True)
            button.setChecked(checked)
            button.blockSignals(old)
    btn = getattr(self, "screenstudio_advanced_btn", None)
    if btn is not None:
        btn.setVisible(simple)
    if not simple:
        self._set_screenstudio_advanced_visible(True, persist=False, quiet=True)
        return
    settings = getattr(self, "_project_settings", {}) or {}
    visible = bool(settings.get("screenstudio_advanced_visible", False))
    self._set_screenstudio_advanced_visible(visible, persist=False, quiet=True)


def _on_workspace_mode_selected(self, simple: bool) -> None:
    simple = bool(simple)
    settings = dict(getattr(self, "_project_settings", {}) or {})
    simple_ui = dict(settings.get("screenstudio_simple_mode_ui") or {})
    settings["screenstudio_simple_mode"] = simple
    if simple:
        simple_ui["layout"] = "simple_screen_studio"
        settings["screenstudio_advanced_visible"] = False
    else:
        simple_ui["layout"] = "standard"
        settings["screenstudio_advanced_visible"] = True
    settings["screenstudio_simple_mode_ui"] = simple_ui
    self._project_settings = settings
    if hasattr(self._player, "set_project_settings"):
        self._player.set_project_settings(settings)
    self._apply_screenstudio_simple_mode_ui()
    self._flash_status(
        "Workspace: Simple - Media Pool and Workbench stay visible"
        if simple
        else "Workspace: Standard - full editor panels shown"
    )


def _on_screenstudio_advanced_toggled(self, checked: bool) -> None:
    self._set_screenstudio_advanced_visible(bool(checked), persist=True)


def _load_screenstudio_cursor_sidecar_for_clip(clip) -> int:
    try:
        from app.screenstudio_polish import load_cursor_sidecar

        events = load_cursor_sidecar(getattr(clip, "source_path", None))
        if not events:
            return 0
        clip.cursor_events = [event.to_dict() for event in events[:2000]]
        return len(clip.cursor_events)
    except Exception:
        return 0


def _screenstudio_default_polish_payload(self) -> dict:
    from app.screenstudio_polish import (
        normalize_screenstudio_polish,
        screenstudio_starter_defaults,
    )

    settings = dict(getattr(self, "_project_settings", {}) or {})
    payload = settings.get("screenstudio_polish")
    if payload:
        return normalize_screenstudio_polish(payload)
    return screenstudio_starter_defaults(
        str(settings.get("starter_template_id") or "screen-recording-demo")
    )


def _screenstudio_cursor_for_handle(handle: str):
    if handle in {"nw", "se"}:
        return Qt.CursorShape.SizeFDiagCursor
    if handle in {"ne", "sw"}:
        return Qt.CursorShape.SizeBDiagCursor
    if handle in {"n", "s"}:
        return Qt.CursorShape.SizeVerCursor
    if handle in {"e", "w"}:
        return Qt.CursorShape.SizeHorCursor
    if handle == "move":
        return Qt.CursorShape.SizeAllCursor
    return Qt.CursorShape.ArrowCursor


def _set_screenstudio_advanced_visible(self, visible: bool, *, persist: bool = False, quiet: bool = False) -> None:
    visible = bool(visible)
    splitter = getattr(self, "_main_dock_splitter", None)
    left = getattr(self, "_left_dock_scroll", None)
    right = getattr(self, "_right_dock_host", None)
    if splitter is not None:
        try:
            sizes = list(splitter.sizes())
        except Exception:
            sizes = []
        if visible:
            restore = list(getattr(self, "_screenstudio_advanced_splitter_sizes", []) or [])
            if len(restore) < 2 or restore[0] <= 0 or restore[1] <= 0:
                restore = [188, 1240]
            try:
                splitter.setSizes(restore)
            except Exception:
                pass
        else:
            if len(sizes) >= 2 and sizes[0] > 8 and sizes[1] > 8:
                self._screenstudio_advanced_splitter_sizes = sizes
            total = max(760, sum(sizes) if sizes else max(760, self.width()))
            compact = total < 1100
            left_w = 176 if compact else 188
            center_w = max(560 if compact else 760, total - left_w)
            try:
                splitter.setSizes([left_w, center_w])
            except Exception:
                pass
    right_shell = getattr(self, "_right_dock_scroll", None) or right
    for widget in (left, right_shell):
        if widget is not None:
            widget.setVisible(True)
    for attr in (
        "_media_pool_section_host",
        "_actor_library_section_host",
        "_workbench_section_host",
    ):
        widget = getattr(self, attr, None)
        if widget is not None:
            widget.setVisible(True)
    for attr in (
        "_effects_library_section_host",
        "_title_presets_section_host",
        "_transitions_section_host",
        "_workflow_presets_section_host",
        "_creator_assist_section_host",
        "_ai_script_edit_section_host",
        "_render_queue_section_host",
        "_audio_workspace_section_host",
        "_subtitle_section_host",
    ):
        widget = getattr(self, attr, None)
        if widget is not None:
            widget.setVisible(visible)
    btn = getattr(self, "screenstudio_advanced_btn", None)
    if btn is not None:
        old = btn.blockSignals(True)
        btn.setChecked(visible)
        btn.blockSignals(old)
        btn.setText("Panels")
        btn.setToolTip(
            "Hide secondary preset/render/audio panels" if visible
            else "Show preset libraries, Render Queue, Audio, and Subtitles. Media Pool and Workbench stay visible."
        )
        btn.setProperty("active", "true" if visible else "false")
        btn.style().unpolish(btn)
        btn.style().polish(btn)
    if persist:
        settings = dict(getattr(self, "_project_settings", {}) or {})
        settings["screenstudio_advanced_visible"] = visible
        self._project_settings = settings
        if hasattr(self._player, "set_project_settings"):
            self._player.set_project_settings(settings)
    self._refresh_command_bar_responsive()
    if not quiet:
        self._flash_status("Secondary panels shown" if visible else "Secondary panels hidden; Media Pool and Workbench stay visible")

def _creator_assist_project_summary(self) -> dict:
    video_tracks = []
    for track in getattr(self, "_tracks", []) or []:
        clips = []
        for clip in getattr(track, "clips", []) or []:
            start = int(getattr(clip, "timeline_in_ms", getattr(clip, "offset_ms", 0)) or 0)
            out = int(getattr(clip, "timeline_out_ms", start) or start)
            if out <= start:
                out = start + int(getattr(clip, "effective_length_ms", 0) or getattr(clip, "duration_ms", 0) or 0)
            clips.append({
                "source_path": str(getattr(clip, "source_path", "") or ""),
                "timeline_in_ms": start,
                "source_in_ms": int(getattr(clip, "source_in_ms", 0) or 0),
                "source_out_ms": int(getattr(clip, "source_out_ms", 0) or 0),
                "source_duration_ms": int(getattr(clip, "source_duration_ms", 0) or 0),
                "duration_ms": max(0, out - start),
            })
        video_tracks.append({"id": int(getattr(track, "id", 0) or 0), "clips": clips})

    audio_tracks = []
    for track in getattr(self, "_audio_tracks", []) or []:
        clips = []
        for clip in getattr(track, "clips", []) or []:
            clips.append({
                "source_path": str(getattr(clip, "source_path", "") or ""),
                "offset_ms": int(getattr(clip, "offset_ms", 0) or 0),
                "duration_ms": int(getattr(clip, "effective_length_ms", 0) or getattr(clip, "duration_ms", 0) or 0),
            })
        audio_tracks.append({"id": int(getattr(track, "id", 0) or 0), "clips": clips})

    subtitles = []
    transcript_segments = []
    try:
        for sub in self._subtitle_panel.subtitles():
            row = {
                "start_ms": int(getattr(sub, "start_ms", 0) or 0),
                "end_ms": int(getattr(sub, "end_ms", 0) or 0),
                "text": str(getattr(sub, "text", "") or ""),
            }
            if row["text"].strip():
                subtitles.append(row)
                transcript_segments.append(dict(row))
    except Exception:
        pass

    settings = dict(getattr(self, "_project_settings", {}) or {})
    media_items = self._creator_assist_media_items()
    duration_ms = self._creator_assist_project_end_ms()
    source_path = ""
    for item in media_items:
        if item.get("kind") == "video":
            source_path = str(item.get("path") or "")
            break
    if not source_path:
        for track in getattr(self, "_tracks", []) or []:
            path = getattr(track, "source_path", None)
            if path:
                source_path = str(path)
                break
    return {
        "duration_ms": duration_ms,
        "duration_s": duration_ms / 1000.0 if duration_ms else 0.0,
        "video_tracks": video_tracks,
        "audio_tracks": audio_tracks,
        "subtitles": subtitles,
        "transcript_segments": transcript_segments,
        "media_items": media_items,
        "has_audio": bool(audio_tracks or any(item.get("kind") == "audio" for item in media_items)),
        "dialogue": bool(transcript_segments or audio_tracks),
        "screen_recording": str(settings.get("starter_template_id") or "").startswith("screen") or any(
            "screen-recording" in (item.get("tags") or []) for item in media_items
        ),
        "project_path": str(getattr(self, "_project_path", "") or ""),
        "source_path": source_path,
    }

def _apply_creator_assist_bundle(self) -> None:
    if capcut_feature_disabled("apply_bundle"):
        self._flash_status(capcut_disabled_reason("apply_bundle"))
        return
    bundle = dict(getattr(self, "_creator_assist_bundle", {}) or {})
    if not bundle:
        bundle = self._analyze_creator_assist()
    if not bundle:
        return
    options = self._creator_assist_selected_options()
    if not any(options.values()):
        self._flash_status("Creator Assist: select at least one option")
        return
    subtitle_count = self._apply_creator_assist_subtitles(bundle, emit_changed=False) if options.get("subtitles") else 0
    marker_count = self._apply_creator_assist_markers(bundle) if options.get("markers") else 0
    settings_applied = False
    if options.get("settings"):
        self._apply_creator_assist_settings(bundle)
        settings_applied = True
    self._capcut_creator_package = {
        key: dict(bundle.get(key) or {})
        for key in (
            "publish_package",
            "edit_recipe",
            "publish_variants",
            "review_panel",
            "publish_handoff",
            "ltx_storyboard",
            "ltx_storyboard_edit_plan",
            "ltx_storyboard_apply_payload",
            "ltx_storyboard_effect_materialization",
            "ltx_storyboard_variations",
            "ltx_storyboard_template_recommendations",
        )
        if isinstance(bundle.get(key), dict)
    }
    self._capcut_short_ranges = [
        row for row in list(bundle.get("timeline_markers") or [])
        if isinstance(row, dict)
        and not bool(row.get("storyboard_marker"))
        and str(row.get("source") or "").casefold() != "ltx_storyboard"
    ]
    self._capcut_render_queue_jobs = list(bundle.get("render_queue_jobs") or [])
    storyboard_result = {"zoom_windows": 0, "callouts": 0, "templates": 0, "targets": 0}
    if options.get("storyboard"):
        storyboard_result = self._stage_creator_assist_storyboard_effects(bundle)
    queue_result = {"added": 0, "skipped": 0}
    if options.get("queue_exports"):
        queue_result = self._stage_creator_assist_render_jobs(bundle)
    storyboard_applied = any(int(storyboard_result.get(key, 0) or 0) > 0 for key in ("zoom_windows", "callouts", "templates"))
    if subtitle_count or marker_count or settings_applied or storyboard_applied:
        if subtitle_count:
            try:
                self._update_subtitle_overlay(self._player.position())
            except Exception:
                pass
        self._register_change("creator assist apply")
    panel = getattr(self, "_creator_assist_panel", None)
    if panel is not None and hasattr(panel, "set_last_result"):
        try:
            panel.set_last_result(
                {
                    "subtitles": subtitle_count,
                    "markers": marker_count,
                    "settings": 1 if settings_applied else 0,
                    "queued": int(queue_result.get("added", 0) or 0),
                    "storyboard_zoom_windows": int(storyboard_result.get("zoom_windows", 0) or 0),
                    "storyboard_callouts": int(storyboard_result.get("callouts", 0) or 0),
                    "storyboard_templates": int(storyboard_result.get("templates", 0) or 0),
                }
            )
        except Exception:
            pass
    self._flash_status(
        f"Creator Assist ?곸슜: ?먮쭑 {subtitle_count}媛? ?쇱툩 留덉빱 {marker_count}媛? "
        f"queued {int(queue_result.get('added', 0) or 0)}"
    )

def _stage_creator_assist_storyboard_effects(self, bundle: dict | None = None) -> dict:
    payload = dict(bundle or getattr(self, "_creator_assist_bundle", {}) or {})
    effects = dict(payload.get("ltx_storyboard_effect_materialization") or {})
    counts = {"zoom_windows": 0, "callouts": 0, "templates": 0, "targets": 0}
    settings = dict(getattr(self, "_project_settings", {}) or {})
    creator = dict(settings.get("creator_assist") or {})
    creator["ltx_storyboard_effect_materialization"] = effects
    creator["ltx_storyboard_effect_counts"] = dict(effects.get("counts") or {})
    settings["creator_assist"] = creator
    self._project_settings = settings
    player = getattr(self, "_player", None)
    if hasattr(player, "set_project_settings"):
        try:
            player.set_project_settings(settings)
        except Exception:
            pass
    zoom_rows = [row for row in (effects.get("zoom_windows") or []) if isinstance(row, dict)]
    callout_rows = [row for row in (effects.get("callouts") or []) if isinstance(row, dict)]
    template_rows = [row for row in (effects.get("template_links") or []) if isinstance(row, dict)]
    if not zoom_rows and not callout_rows and not template_rows:
        return counts
    try:
        targets = list(self._screenstudio_polish_targets())
    except Exception:
        targets = []
    if not targets:
        return counts
    from app.timeline_model import ZoomActor

    for _target_index, (_track, clip) in enumerate(targets):
        if clip is None:
            continue
        counts["targets"] += 1
        frame_w, frame_h = self._frame_size_for_storyboard_clip(clip)
        existing_clip_zoom = [
            z for z in list(getattr(clip, "zoom_actors", []) or [])
            if not str(getattr(z, "ltx_storyboard_effect_id", "") or "")
        ]
        max_id = max((int(getattr(z, "id", 0) or 0) for z in existing_clip_zoom), default=0)
        created: list[ZoomActor] = []
        for row in zoom_rows:
            actor = self._storyboard_zoom_actor_for_clip(row, clip, frame_w, frame_h, max_id + len(created) + 1)
            if actor is not None:
                created.append(actor)
        if not created:
            for row in zoom_rows:
                actor = self._storyboard_zoom_actor_for_clip(
                    row,
                    clip,
                    frame_w,
                    frame_h,
                    max_id + len(created) + 1,
                    force_clip_local=True,
                )
                if actor is not None:
                    created.append(actor)
        if not created:
            created = []
        clip.zoom_actors = sorted(existing_clip_zoom + created, key=lambda z: int(getattr(z, "start_ms", 0) or 0))
        visual_zoom_created = self._sync_storyboard_zoom_visual_actors(_track, clip, created)
        polish = dict(getattr(clip, "screenstudio_polish", {}) or {})
        staged_ids = [int(getattr(actor, "id", 0) or 0) for actor in created]
        polish.setdefault("source", "creator_assist_ltx_storyboard")
        polish["ltx_storyboard_auto_zoom_actor_ids"] = staged_ids
        polish["ltx_storyboard_visual_zoom_actor_ids"] = visual_zoom_created
        polish["ltx_storyboard_effect_counts"] = dict(effects.get("counts") or {})
        clip.screenstudio_polish = polish
        counts["zoom_windows"] += len(created)
        counts["callouts"] += self._stage_storyboard_callout_actors(_track, clip, callout_rows)
    template_result = _stage_creator_assist_storyboard_templates(self, bundle, targets=targets)
    counts["templates"] = int(template_result.get("applied", 0) or 0)
    if counts["zoom_windows"] or counts["callouts"] or counts["templates"]:
        try:
            self._refresh_player_tracks()
        except Exception:
            pass
        for row in getattr(self, "_track_rows", {}).values():
            try:
                row.update()
            except Exception:
                pass
        return counts


def _storyboard_template_aliases() -> dict[str, str]:
    return {
        "tutorial-click-polish": "template-screenstudio-click-to-cut",
        "screenstudio-wallpaper": "template-screenstudio-wallpaper-demo",
        "product-review-clean": "template-screenstudio-product-walkthrough",
        "gameplay-stream-pop": "template-gaming-highlight-screen",
        "caption-word-pop": "template-screenstudio-short-export",
        "podcast-chapter-soft": "template-podcast-chapter",
        "beauty-before-after": "template-before-after",
    }


def _storyboard_template_target_for_ms(targets: list, ms: int):
    if not targets:
        return None, None
    try:
        pos = int(ms)
    except Exception:
        pos = 0
    fallback = targets[0]
    for track, clip in targets:
        if clip is None:
            continue
        start = int(getattr(clip, "timeline_in_ms", 0) or 0)
        end = int(getattr(clip, "timeline_out_ms", start) or start)
        if start <= pos < end:
            return track, clip
    return fallback


def _storyboard_template_links_from_bundle(bundle: dict) -> list[dict]:
    effects = dict((bundle or {}).get("ltx_storyboard_effect_materialization") or {})
    links = [dict(row) for row in (effects.get("template_links") or []) if isinstance(row, dict)]
    if links:
        return links
    recommendations = dict((bundle or {}).get("ltx_storyboard_template_recommendations") or {})
    out: list[dict] = []
    for row in recommendations.get("cards") or []:
        if not isinstance(row, dict):
            continue
        template_id = str(row.get("template_id") or row.get("id") or "").strip()
        if not template_id:
            continue
        out.append({
            "id": str(row.get("id") or template_id),
            "template_id": template_id,
            "shot_id": str(row.get("shot_id") or ""),
            "start_ms": int(row.get("start_ms", 0) or 0),
            "end_ms": int(row.get("end_ms", 0) or 0),
            "source": "ltx_storyboard_template_recommendation",
        })
    return out


def _storyboard_source_window_for_clip(row: dict, clip, *, force_clip_local: bool = False) -> tuple[int, int] | None:
    try:
        start_project = int(row.get("start_ms", 0) or 0)
        end_project = int(row.get("end_ms", start_project + 1200) or start_project + 1200)
    except Exception:
        return None
    clip_in = int(getattr(clip, "timeline_in_ms", 0) or 0)
    clip_out = int(getattr(clip, "timeline_out_ms", clip_in + getattr(clip, "effective_length_ms", 0)) or clip_in)
    if force_clip_local:
        source_base = int(getattr(clip, "source_in_ms", 0) or 0)
        source_start = source_base + max(0, start_project)
        source_end = source_base + max(start_project + 1, end_project)
    else:
        overlap_start = max(start_project, clip_in)
        overlap_end = min(end_project, clip_out)
        if overlap_end <= overlap_start:
            return None
        try:
            source_start = int(clip.timeline_to_source_ms(overlap_start))
            source_end = int(clip.timeline_to_source_ms(overlap_end))
        except Exception:
            source_start = int(getattr(clip, "source_in_ms", 0) or 0) + max(0, overlap_start - clip_in)
            source_end = int(getattr(clip, "source_in_ms", 0) or 0) + max(source_start + 1, overlap_end - clip_in)
    source_in = int(getattr(clip, "source_in_ms", 0) or 0)
    source_out = int(getattr(clip, "effective_source_out_ms", 0) or source_end)
    source_start = max(source_in, min(source_start, max(source_in, source_out - 1)))
    source_end = max(source_start + 1, min(source_end, source_out if source_out > 0 else source_end))
    if source_end <= source_start:
        return None
    return int(source_start), int(source_end)


def _storyboard_project_window_for_track_actor(row: dict, clip) -> tuple[int, int] | None:
    window = _storyboard_source_window_for_clip(row, clip)
    if window is None:
        window = _storyboard_source_window_for_clip(row, clip, force_clip_local=True)
    if window is None:
        return None
    source_start, source_end = window
    try:
        clip_in = int(getattr(clip, "timeline_in_ms", 0) or 0)
        source_in = int(getattr(clip, "source_in_ms", 0) or 0)
        return clip_in + max(0, source_start - source_in), clip_in + max(1, source_end - source_in)
    except Exception:
        return int(source_start), int(source_end)


def _storyboard_callout_position(row: dict) -> tuple[float, float]:
    position = str(row.get("position") or "").casefold()
    if position == "safe_top":
        return 0.5, 0.18
    if position == "lower_third":
        return 0.5, 0.76
    return 0.5, 0.72


def _storyboard_callout_actor(row: dict, start_ms: int, end_ms: int) -> TextClip | None:
    if end_ms <= start_ms:
        return None
    label = str(row.get("text") or row.get("label") or "Shot callout").strip()
    if not label:
        label = "Shot callout"
    accent = str(row.get("accent") or "#8A7CFF")
    actor = TextClip(start_ms=int(start_ms), end_ms=int(end_ms))
    actor.text = label[:96]
    actor.style.font_size = 46
    actor.style.font_weight = 800
    actor.style.color = "#FFFFFF"
    actor.style.outline_color = "#0D1020"
    actor.style.outline_width = 2
    actor.style.shadow_color = "#000000"
    actor.style.shadow_offset_x = 0
    actor.style.shadow_offset_y = 8
    actor.style.shadow_blur = 18
    actor.style.background_color = accent
    actor.style.background_padding = 18
    actor.style.background_radius = 16
    actor.style.position_x, actor.style.position_y = _storyboard_callout_position(row)
    actor.animation.in_animation = "pop-in"
    actor.animation.out_animation = "fade-out"
    actor.animation.in_duration = 0.22
    actor.animation.out_duration = 0.28
    try:
        actor.ltx_storyboard_effect_id = str(row.get("id") or "")
        actor.ltx_storyboard_shot_id = str(row.get("shot_id") or "")
        actor.ltx_storyboard_source = "ltx_storyboard_callout"
        actor.ltx_storyboard_review_only = bool(row.get("review_only", True))
    except Exception:
        pass
    return actor


def _storyboard_zoom_actor_for_clip(row: dict, clip, frame_w: int, frame_h: int, actor_id: int, *, force_clip_local: bool = False):
    from app.timeline_model import ZoomActor

    frame_w = max(16, int(frame_w or 1920))
    frame_h = max(16, int(frame_h or 1080))
    try:
        start_project = int(row.get("start_ms", 0) or 0)
        end_project = int(row.get("end_ms", start_project + 1200) or start_project + 1200)
    except Exception:
        return None
    clip_in = int(getattr(clip, "timeline_in_ms", 0) or 0)
    clip_out = int(getattr(clip, "timeline_out_ms", clip_in + getattr(clip, "effective_length_ms", 0)) or clip_in)
    if force_clip_local:
        source_base = int(getattr(clip, "source_in_ms", 0) or 0)
        source_start = source_base + max(0, start_project)
        source_end = source_base + max(start_project + 1, end_project)
    else:
        overlap_start = max(start_project, clip_in)
        overlap_end = min(end_project, clip_out)
        if overlap_end <= overlap_start:
            return None
        try:
            source_start = int(clip.timeline_to_source_ms(overlap_start))
            source_end = int(clip.timeline_to_source_ms(overlap_end))
        except Exception:
            source_start = int(getattr(clip, "source_in_ms", 0) or 0) + max(0, overlap_start - clip_in)
            source_end = int(getattr(clip, "source_in_ms", 0) or 0) + max(source_start + 1, overlap_end - clip_in)
    source_in = int(getattr(clip, "source_in_ms", 0) or 0)
    source_out = int(getattr(clip, "effective_source_out_ms", 0) or source_end)
    source_start = max(source_in, min(source_start, max(source_in, source_out - 1)))
    source_end = max(source_start + 1, min(source_end, source_out if source_out > 0 else source_end))
    if source_end <= source_start:
        return None
    target_w = max(16, min(frame_w, int(round(frame_w * float(row.get("target_w_norm", 0.84) or 0.84)))))
    target_h = max(16, min(frame_h, int(round(frame_h * float(row.get("target_h_norm", 0.84) or 0.84)))))
    center_x = max(0.0, min(1.0, float(row.get("target_x_norm", 0.5) or 0.5))) * frame_w
    center_y = max(0.0, min(1.0, float(row.get("target_y_norm", 0.46) or 0.46))) * frame_h
    target_x = max(0, min(frame_w - target_w, int(round(center_x - target_w / 2))))
    target_y = max(0, min(frame_h - target_h, int(round(center_y - target_h / 2))))
    actor = ZoomActor(
        id=int(actor_id),
        start_ms=int(source_start),
        end_ms=int(source_end),
        target_x=target_x,
        target_y=target_y,
        target_w=target_w,
        target_h=target_h,
        zoom_in_ms=max(80, int(row.get("zoom_in_ms", 420) or 420)),
        zoom_out_ms=max(80, int(row.get("zoom_out_ms", 460) or 460)),
        easing=str(row.get("easing") or "smooth_pop"),
        motion_blur=float(row.get("motion_blur", 0.0) or 0.0),
    )
    try:
        actor.ltx_storyboard_effect_id = str(row.get("id") or "")
        actor.ltx_storyboard_shot_id = str(row.get("shot_id") or "")
        actor.ltx_storyboard_camera_motion = str(row.get("camera_motion") or "")
        actor.ltx_storyboard_review_only = bool(row.get("review_only", True))
    except Exception:
        pass
    return actor


def _stage_creator_assist_storyboard_templates(
    self,
    bundle: dict | None = None,
    *,
    targets: list | None = None,
    limit: int = 4,
) -> dict:
    payload = dict(bundle or getattr(self, "_creator_assist_bundle", {}) or {})
    links = _storyboard_template_links_from_bundle(payload)
    result = {"applied": 0, "skipped": 0, "missing": 0, "attempted": 0, "preset_ids": []}
    if not links:
        return result
    if targets is None:
        try:
            targets = list(self._screenstudio_polish_targets())
        except Exception:
            targets = []
    if not targets:
        result["skipped"] = len(links)
        return result
    try:
        from app.preset_library import preset_by_id
    except Exception:
        result["skipped"] = len(links)
        return result
    aliases = _storyboard_template_aliases()
    settings = dict(getattr(self, "_project_settings", {}) or {})
    creator = dict(settings.get("creator_assist") or {})
    applied_keys = set(str(key) for key in (creator.get("ltx_storyboard_applied_template_keys") or []))
    applied_rows = [dict(row) for row in (creator.get("ltx_storyboard_applied_templates") or []) if isinstance(row, dict)]
    seen_presets: set[str] = set()
    previous_forced_track = getattr(self, "_workflow_forced_track_id", None)
    previous_forced_ms = getattr(self, "_workflow_forced_ms", None)
    previous_target_mode = getattr(self, "_workflow_target_mode", None)
    previous_selected = list(getattr(self, "_selected_clips", []) or [])
    previous_active_track = getattr(self, "_active_track_id", None)
    try:
        for row in links:
            raw_template_id = str(row.get("template_id") or "").strip()
            if not raw_template_id:
                result["skipped"] += 1
                continue
            preset_ids = [raw_template_id]
            alias = aliases.get(raw_template_id)
            if alias:
                preset_ids.append(alias)
            preset = None
            preset_id = ""
            for candidate in preset_ids:
                candidate_preset = preset_by_id(candidate)
                if candidate_preset is None:
                    continue
                if str(getattr(candidate_preset, "kind", "") or "") != "template":
                    continue
                preset = candidate_preset
                preset_id = str(getattr(candidate_preset, "id", "") or candidate)
                break
            if preset is None:
                result["missing"] += 1
                continue
            if preset_id in seen_presets:
                result["skipped"] += 1
                continue
            start_ms = max(0, int(row.get("start_ms", 0) or 0))
            track, clip = _storyboard_template_target_for_ms(targets, start_ms)
            if track is None or clip is None:
                result["skipped"] += 1
                continue
            key = (
                f"{preset_id}:"
                f"{int(getattr(track, 'id', -1))}:"
                f"{int(getattr(clip, 'id', -1))}:"
                f"{start_ms}"
            )
            if key in applied_keys:
                result["skipped"] += 1
                seen_presets.add(preset_id)
                continue
            result["attempted"] += 1
            self._workflow_forced_track_id = int(getattr(track, "id", -1))
            self._workflow_forced_ms = start_ms
            self._workflow_target_mode = "auto"
            try:
                self._active_track_id = int(getattr(track, "id", -1))
                self._selected_clips = [(int(getattr(track, "id", -1)), int(getattr(clip, "id", -1)))]
            except Exception:
                pass
            try:
                changed = bool(self._apply_editor_preset_object(preset, depth=0, at_ms=start_ms))
            except Exception:
                changed = False
            if not changed:
                result["skipped"] += 1
                continue
            applied_keys.add(key)
            seen_presets.add(preset_id)
            result["applied"] += 1
            result["preset_ids"].append(preset_id)
            applied_rows.append({
                "key": key,
                "preset_id": preset_id,
                "source_template_id": raw_template_id,
                "shot_id": str(row.get("shot_id") or ""),
                "start_ms": start_ms,
                "target_track_id": int(getattr(track, "id", -1)),
                "target_clip_id": int(getattr(clip, "id", -1)),
            })
            if result["applied"] >= max(1, int(limit)):
                break
    finally:
        if previous_forced_track is None:
            try:
                delattr(self, "_workflow_forced_track_id")
            except Exception:
                pass
        else:
            self._workflow_forced_track_id = previous_forced_track
        if previous_forced_ms is None:
            try:
                delattr(self, "_workflow_forced_ms")
            except Exception:
                pass
        else:
            self._workflow_forced_ms = previous_forced_ms
        if previous_target_mode is None:
            try:
                delattr(self, "_workflow_target_mode")
            except Exception:
                pass
        else:
            self._workflow_target_mode = previous_target_mode
        self._selected_clips = previous_selected
        if previous_active_track is not None:
            self._active_track_id = previous_active_track
    creator["ltx_storyboard_applied_template_keys"] = sorted(applied_keys)
    creator["ltx_storyboard_applied_templates"] = applied_rows[-32:]
    settings["creator_assist"] = creator
    self._project_settings = settings
    player = getattr(self, "_player", None)
    if hasattr(player, "set_project_settings"):
        try:
            player.set_project_settings(settings)
        except Exception:
            pass
    return result


def _stage_storyboard_callout_actors(self, track, clip, callout_rows: list[dict]) -> int:
    if track is None or clip is None:
        return 0
    target_clip_id = str(getattr(clip, "id", "") or "")
    existing = [
        actor for actor in list(getattr(track, "typography_actors", []) or [])
        if (
            str(getattr(actor, "ltx_storyboard_source", "") or "") != "ltx_storyboard_callout"
            or str(getattr(actor, "ltx_storyboard_target_clip_id", "") or "") != target_clip_id
        )
    ]
    created: list[TextClip] = []
    for row in callout_rows:
        window = _storyboard_project_window_for_track_actor(row, clip)
        if window is None:
            continue
        actor = _storyboard_callout_actor(row, window[0], window[1])
        if actor is not None:
            try:
                actor.ltx_storyboard_target_clip_id = target_clip_id
            except Exception:
                pass
            created.append(actor)
    if not created:
        track.typography_actors = sorted(existing, key=lambda c: int(getattr(c, "start_ms", 0) or 0))
        return 0
    track.typography_actors = sorted(existing + created, key=lambda c: int(getattr(c, "start_ms", 0) or 0))
    return len(created)

def _sync_storyboard_zoom_visual_actors(self, track, clip, clip_zoom_actors: list) -> list[int]:
    if track is None:
        return []
    target_clip_id = str(getattr(clip, "id", "") or "")
    existing = [
        z for z in list(getattr(track, "zoom_actors", []) or [])
        if (
            not str(getattr(z, "ltx_storyboard_effect_id", "") or "")
            or str(getattr(z, "ltx_storyboard_target_clip_id", "") or "") != target_clip_id
        )
    ]
    max_id = max((int(getattr(z, "id", 0) or 0) for z in existing), default=0)
    created = []
    clip_in = int(getattr(clip, "timeline_in_ms", 0) or 0)
    source_in = int(getattr(clip, "source_in_ms", 0) or 0)
    try:
        import copy as _copy
    except Exception:
        _copy = None
    for src in clip_zoom_actors:
        try:
            actor = _copy.deepcopy(src) if _copy is not None else src
            actor.id = max_id + len(created) + 1
            actor.start_ms = clip_in + max(0, int(getattr(src, "start_ms", 0) or 0) - source_in)
            actor.end_ms = clip_in + max(1, int(getattr(src, "end_ms", 0) or 0) - source_in)
            actor.ltx_storyboard_target_clip_id = target_clip_id
        except Exception:
            actor = None
        if actor is not None:
            created.append(actor)
    if created:
        track.zoom_actors = sorted(existing + created, key=lambda z: int(getattr(z, "start_ms", 0) or 0))
    else:
        track.zoom_actors = sorted(existing, key=lambda z: int(getattr(z, "start_ms", 0) or 0))
    return [int(getattr(actor, "id", 0) or 0) for actor in created]

def _frame_size_for_storyboard_clip(self, clip) -> tuple[int, int]:
    source = getattr(clip, "source_path", None)
    if source is not None:
        try:
            w, h = _probe_video_dimensions(Path(source))
            if w > 0 and h > 0:
                return int(w), int(h)
        except Exception:
            pass
    resolution = getattr(self, "_export_resolution", None)
    if isinstance(resolution, tuple) and len(resolution) == 2:
        try:
            w, h = int(resolution[0]), int(resolution[1])
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass
    return 1920, 1080



def _copy_creator_assist_publish_text(self) -> None:
    if capcut_feature_disabled("creator_assist"):
        self._flash_status(capcut_disabled_reason("creator_assist"))
        return
    bundle = dict(getattr(self, "_creator_assist_bundle", {}) or {})
    handoff = dict(bundle.get("publish_handoff") or self._capcut_creator_package.get("publish_handoff") or {})
    payloads = dict(handoff.get("clipboard_payloads") or {})
    text = "\n\n".join(
        part for part in (
            str(payloads.get("title") or ""),
            str(payloads.get("description") or ""),
            str(payloads.get("hashtags") or ""),
        )
        if part.strip()
    )
    if not text:
        self._flash_status("Creator Assist: 蹂듭궗??寃뚯떆 臾몄븞???놁뒿?덈떎")
        return
    QApplication.clipboard().setText(text)
    self._flash_status("Creator Assist 寃뚯떆 臾몄븞??蹂듭궗?덉뒿?덈떎")

def _screenstudio_polish_targets(self) -> list[tuple["VideoTrack", object]]:
    selected_pairs = list(getattr(self, "_selected_clips", []) or [])
    targets: list[tuple["VideoTrack", object]] = []
    seen: set[tuple[int, int]] = set()
    for tid, cid in selected_pairs:
        track, clip = self._find_video_clip(int(tid), int(cid))
        if track is None or clip is None:
            continue
        key = (int(getattr(track, "id", -1)), int(getattr(clip, "id", -1)))
        if key not in seen:
            targets.append((track, clip))
            seen.add(key)
    if targets:
        return targets
    for track in getattr(self, "_tracks", []) or []:
        for clip in getattr(track, "clips", []) or []:
            if getattr(clip, "source_path", None) is not None:
                targets.append((track, clip))
    return targets

def _screenstudio_project_polish_payload(self) -> dict:
    from app.screenstudio_polish import normalize_screenstudio_polish
    settings = getattr(self, "_project_settings", {}) or {}
    return normalize_screenstudio_polish(settings.get("screenstudio_polish", {}) or {})


def _screenstudio_local_zoom_overrides(screen_payload: dict | None, target_index: int) -> dict[int, dict]:
    raw = dict((screen_payload or {}).get("zoom_candidate_overrides", {}) or {})
    prefix = f"{int(target_index)}:"
    out: dict[int, dict] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        key_s = str(key)
        if not key_s.startswith(prefix):
            continue
        try:
            point_index = int(key_s.split(":", 1)[1])
        except Exception:
            continue
        cleaned: dict[str, int] = {}
        for name in ("start_ms", "end_ms", "target_x", "target_y", "target_w", "target_h"):
            if name not in value:
                continue
            try:
                cleaned[name] = int(value[name])
            except Exception:
                continue
        if cleaned:
            out[point_index] = cleaned
    return out



def _set_screenstudio_polish_payload(
    self,
    payload: dict | None,
    *,
    refresh: bool = True,
    mark_dirty: bool = True,
) -> None:
    from app.screenstudio_polish import normalize_screenstudio_polish
    settings = dict(getattr(self, "_project_settings", {}) or {})
    settings["screenstudio_polish"] = normalize_screenstudio_polish(payload or {})
    self._project_settings = settings
    if hasattr(self._player, "set_project_settings"):
        self._player.set_project_settings(settings)
    if refresh:
        try:
            self._player.refresh_current_frame()
        except Exception:
            try:
                self._refresh_player_tracks()
            except Exception:
                pass
    if mark_dirty:
        self._autosave_dirty = True
        self._screenstudio_polish_dirty_since_register = True


def _same_media_path(left, right) -> bool:
    if left is None or right is None:
        return False
    try:
        return Path(left).resolve() == Path(right).resolve()
    except Exception:
        return str(left) == str(right)



def _find_first_video_clip_by_source_path(self, source_path: str | Path | None):
    if source_path is None:
        return None, None
    for track in getattr(self, "_tracks", []) or []:
        for clip in getattr(track, "clips", []) or []:
            clip_source = getattr(clip, "source_path", None)
            original_source = getattr(clip, "_original_source_path", None)
            if (
                _same_media_path(clip_source, source_path)
                or _same_media_path(original_source, source_path)
            ):
                return track, clip
    return None, None

def _open_auto_polish_for_media_path(self, source_path: str) -> None:
    path = Path(str(source_path or ""))
    self._screenstudio_forced_media_path = path
    track, clip = self._find_first_video_clip_by_source_path(path)
    if track is not None and clip is not None:
        try:
            self._set_active_track(int(getattr(track, "id")))
        except Exception:
            pass
        self._select_workflow_video_clip(track, clip)
        try:
            self._player.set_position(int(getattr(clip, "timeline_in_ms", 0) or 0))
        except Exception:
            pass
        self._flash_status(f"Auto Polish focused: {path.name}")
    else:
        self._flash_status("Auto Polish metadata found. Drag this media to the timeline to generate zooms.")
    self._open_screenstudio_polish_panel(path)

def _screenstudio_auto_polish_report(self, polish_payload: dict | None = None) -> dict:
    targets = self._screenstudio_polish_targets()
    if not targets:
        forced_path = getattr(self, "_screenstudio_forced_media_path", None)
        if forced_path is not None:
            try:
                from app.screenstudio_polish import screenstudio_sidecar_report

                media_report = screenstudio_sidecar_report(
                    forced_path,
                    duration_ms=0,
                    include_parity=False,
                )
                normalized_payload = polish_payload or self._screenstudio_project_polish_payload()
                screen_payload = dict((normalized_payload or {}).get("screen", {}) or {})
                disabled_keys = set(str(v) for v in (screen_payload.get("disabled_zoom_candidate_keys", []) or []))
                overrides = _screenstudio_local_zoom_overrides(screen_payload, 0)
                rows = []
                for candidate in media_report.get("zoom_candidates", []) or []:
                    row = dict(candidate)
                    point_index = int(row.get("point_index", 0) or 0)
                    key = f"0:{point_index}"
                    if point_index in overrides:
                        row.update(overrides[point_index])
                    row["target_index"] = 0
                    row["clip_name"] = Path(forced_path).name
                    row["key"] = key
                    row["enabled"] = key not in disabled_keys and bool(row.get("enabled", True))
                    rows.append(row)
                warnings = list(media_report.get("warnings") or [])
                if "media_not_on_timeline" not in warnings:
                    warnings.append("media_not_on_timeline")
                media_report.update(
                    {
                        "target_count": 0,
                        "zoom_candidates": rows,
                        "warnings": warnings,
                        "ok": False,
                    }
                )
                return media_report
            except Exception:
                pass
        return {
            "ok": False,
            "readiness": 0,
            "target_count": 0,
            "event_count": 0,
            "counts": {},
            "hotkey_labels": [],
            "auto_zoom_count": 0,
            "zoom_candidates": [],
            "parity_ok": False,
            "warnings": ["no_video_targets"],
        }
    try:
        from app.screenstudio_polish import (
            load_cursor_sidecar,
            normalize_cursor_events,
            screenstudio_interaction_report,
        )
    except Exception as exc:
        return {
            "ok": False,
            "readiness": 0,
            "target_count": len(targets),
            "event_count": 0,
            "counts": {},
            "hotkey_labels": [],
            "auto_zoom_count": 0,
            "zoom_candidates": [],
            "parity_ok": False,
            "warnings": [f"screenstudio_report_unavailable:{exc}"],
        }

    total_events = 0
    total_zoom = 0
    readiness_values: list[int] = []
    counts: dict[str, int] = {}
    labels: list[str] = []
    warnings: list[str] = []
    zoom_candidates: list[dict] = []
    parity_ok = True
    normalized_payload = polish_payload or self._screenstudio_project_polish_payload()
    settings = {"screenstudio_polish": normalized_payload}
    screen_payload = dict((normalized_payload or {}).get("screen", {}) or {})
    disabled_keys = set(str(v) for v in (screen_payload.get("disabled_zoom_candidate_keys", []) or []))
    for target_index, (track, clip) in enumerate(targets):
        events = load_cursor_sidecar(getattr(clip, "source_path", None))
        if not events:
            events = normalize_cursor_events(getattr(clip, "cursor_events", []) or [])
        frame_w, frame_h = _clip_preview_frame_size(track, clip)
        duration = int(
            getattr(clip, "effective_length_ms", 0)
            or getattr(clip, "source_duration_ms", 0)
            or getattr(track, "duration_ms", 0)
            or 0
        )
        local_disabled: list[int] = []
        prefix = f"{target_index}:"
        for key in disabled_keys:
            if not key.startswith(prefix):
                continue
            try:
                local_disabled.append(int(key.split(":", 1)[1]))
            except Exception:
                continue
        local_overrides = _screenstudio_local_zoom_overrides(screen_payload, target_index)
        report = screenstudio_interaction_report(
            events,
            duration_ms=duration,
            frame_w=frame_w,
            frame_h=frame_h,
            project_settings=settings,
            include_parity=True,
            disabled_zoom_candidate_indexes=local_disabled,
            zoom_candidate_overrides=local_overrides,
        )
        total_events += int(report.get("event_count", 0) or 0)
        total_zoom += int(report.get("auto_zoom_count", 0) or 0)
        readiness_values.append(int(report.get("readiness", 0) or 0))
        parity_ok = parity_ok and bool(report.get("parity_ok"))
        for key, value in (report.get("counts", {}) or {}).items():
            counts[str(key)] = counts.get(str(key), 0) + int(value or 0)
        for label in report.get("hotkey_labels", []) or []:
            if label not in labels:
                labels.append(str(label))
        for warning in report.get("warnings", []) or []:
            if warning not in warnings:
                warnings.append(str(warning))
        clip_name = Path(str(getattr(clip, "source_path", "") or "")).name
        if not clip_name:
            clip_name = f"clip {getattr(clip, 'id', target_index + 1)}"
        for candidate in report.get("zoom_candidates", []) or []:
            row = dict(candidate)
            try:
                point_index = int(row.get("point_index", 0) or 0)
            except Exception:
                point_index = 0
            key = f"{target_index}:{point_index}"
            row["target_index"] = target_index
            row["clip_id"] = int(getattr(clip, "id", -1) or -1)
            row["track_id"] = int(getattr(track, "id", -1) or -1)
            row["clip_name"] = clip_name
            row["key"] = key
            row["enabled"] = key not in disabled_keys and bool(row.get("enabled", True))
            zoom_candidates.append(row)
    readiness = int(round(sum(readiness_values) / max(1, len(readiness_values))))
    return {
        "ok": not warnings and parity_ok,
        "readiness": readiness,
        "target_count": len(targets),
        "event_count": total_events,
        "counts": counts,
        "hotkey_labels": labels[:12],
        "auto_zoom_count": total_zoom,
        "zoom_candidates": zoom_candidates,
        "parity_ok": bool(parity_ok),
        "warnings": warnings,
    }

def _open_screenstudio_polish_panel(self, media_path: str | Path | None = None) -> None:
    if isinstance(media_path, bool):
        media_path = None
    if media_path is None:
        self._screenstudio_forced_media_path = None
    else:
        self._screenstudio_forced_media_path = Path(media_path)
    dlg = getattr(self, "_screenstudio_polish_dialog", None)
    if dlg is not None and dlg.isVisible():
        try:
            self._refresh_preview_canvas_interaction_hook()
            dlg.set_readiness_report(self._screenstudio_auto_polish_report(dlg.payload()))
            dlg.raise_()
            dlg.activateWindow()
        except Exception:
            pass
        return
    dlg = ScreenStudioPolishDialog(self._screenstudio_project_polish_payload(), self)
    self._screenstudio_polish_dialog = dlg
    try:
        self._refresh_preview_canvas_interaction_hook()
    except Exception:
        pass
    def _on_polish_settings_changed(payload) -> None:
        self._set_screenstudio_polish_payload(
            payload,
            refresh=True,
            mark_dirty=True,
        )
        dlg.set_readiness_report(self._screenstudio_auto_polish_report(payload))
        try:
            self._drawing_canvas.update()
        except Exception:
            pass

    def _on_auto_polish_requested() -> None:
        self._apply_screenstudio_auto_polish(dlg.payload())
        dlg.set_readiness_report(self._screenstudio_auto_polish_report(dlg.payload()))
        try:
            self._drawing_canvas.update()
        except Exception:
            pass

    def _on_candidate_selected(row) -> None:
        if not isinstance(row, dict):
            return
        try:
            track_id = int(row.get("track_id", -1) or -1)
            clip_id = int(row.get("clip_id", -1) or -1)
            track = self._find_track(track_id)
            clip = None
            if track is not None:
                clip = next((c for c in getattr(track, "clips", []) or [] if int(getattr(c, "id", -1)) == clip_id), None)
            if clip is None:
                return
            local_ms = int(row.get("start_ms", row.get("point_ms", 0)) or 0)
            self._player.set_position(max(0, int(getattr(clip, "timeline_in_ms", 0) or 0) + local_ms))
            self._drawing_canvas.update()
        except Exception:
            pass

    dlg.settings_changed.connect(_on_polish_settings_changed)
    dlg.auto_polish_requested.connect(_on_auto_polish_requested)
    dlg.candidate_selected.connect(_on_candidate_selected)
    dlg.set_readiness_report(self._screenstudio_auto_polish_report(dlg.payload()))

    def _on_finished(_code: int) -> None:
        if getattr(self, "_screenstudio_polish_dialog", None) is dlg:
            self._screenstudio_polish_dialog = None
        self._screenstudio_candidate_drag = None
        try:
            self._refresh_preview_canvas_interaction_hook()
        except Exception:
            pass
        if dlg.is_dirty() and getattr(self, "_screenstudio_polish_dirty_since_register", False):
            self._register_change("screen studio polish settings")
            self._screenstudio_polish_dirty_since_register = False
        try:
            self._drawing_canvas.update()
        except Exception:
            pass

    dlg.finished.connect(_on_finished)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    self._flash_status("Auto Polish panel opened")


def _clip_preview_frame_size(track, clip) -> tuple[int, int]:
    source = getattr(clip, "source_path", None) or getattr(track, "source_path", None)
    if source is not None:
        try:
            import cv2
            cap = cv2.VideoCapture(str(source))
            try:
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                if w > 16 and h > 16:
                    return w, h
            finally:
                cap.release()
        except Exception:
            pass
    return 1920, 1080



def _apply_screenstudio_auto_polish(self, polish_payload: dict | None = None) -> None:
    targets = self._screenstudio_polish_targets()
    if not targets:
        self._flash_status("Import or select a video clip first")
        return
    from app.screenstudio_polish import (
        apply_screenstudio_polish_to_clip,
        load_cursor_sidecar,
        normalize_screenstudio_polish,
    )
    polish_payload = normalize_screenstudio_polish(
        polish_payload or self._screenstudio_project_polish_payload()
    )
    cursor_polish = dict(polish_payload.get("cursor", {}) or {})
    screen_polish = dict(polish_payload.get("screen", {}) or {})
    preset_id = str(polish_payload.get("preset_id") or "")
    disabled_keys = set(str(v) for v in (screen_polish.get("disabled_zoom_candidate_keys", []) or []))

    total_added = 0
    touched_track_ids: set[int] = set()
    first_focus_ms: int | None = None
    for target_index, (track, clip) in enumerate(targets):
        frame_w, frame_h = _clip_preview_frame_size(track, clip)
        events = load_cursor_sidecar(getattr(clip, "source_path", None))
        if events:
            clip.cursor_events = [event.to_dict() for event in events[:2000]]
        local_disabled: list[int] = []
        prefix = f"{target_index}:"
        for key in disabled_keys:
            if not key.startswith(prefix):
                continue
            try:
                local_disabled.append(int(key.split(":", 1)[1]))
            except Exception:
                continue
            local_overrides = _screenstudio_local_zoom_overrides(screen_polish, target_index)
        added = apply_screenstudio_polish_to_clip(
            clip,
            frame_w=frame_w,
            frame_h=frame_h,
            cursor_events=events,
            cursor_polish=cursor_polish,
            screen_polish=screen_polish,
            preset_id=preset_id,
            replace_previous=True,
            disabled_zoom_candidate_indexes=local_disabled,
            zoom_candidate_overrides=local_overrides,
        )
        if added <= 0:
            continue
        total_added += added
        touched_track_ids.add(int(getattr(track, "id", -1)))
        if first_focus_ms is None:
            generated_ids = set((getattr(clip, "screenstudio_polish", {}) or {}).get("auto_zoom_actor_ids", []))
            first_actor = next(
                (
                    z for z in getattr(clip, "zoom_actors", []) or []
                    if int(getattr(z, "id", 0) or 0) in {int(i) for i in generated_ids}
                ),
                None,
            )
            if first_actor is not None:
                first_focus_ms = int(getattr(clip, "timeline_in_ms", 0) or 0) + int(getattr(first_actor, "start_ms", 0) or 0)
    if total_added <= 0:
        self._flash_status("Auto Polish found no new zoom windows")
        return
    self._set_screenstudio_polish_payload(polish_payload, refresh=False, mark_dirty=True)
    for track_id in touched_track_ids:
        row = getattr(self, "_track_rows", {}).get(track_id)
        if row is not None:
            row.update()
    self._refresh_player_tracks()
    self._update_tracks_host_width()
    self._refresh_workbench()
    if first_focus_ms is not None:
        try:
            self._player.set_position(max(0, int(first_focus_ms)))
        except Exception:
            pass
    self._register_change("screen studio auto polish")
    self._screenstudio_polish_dirty_since_register = False
    self._flash_status(f"Auto Polish added {total_added} zoom window(s)")

def _screenstudio_export_badge_note(self) -> str:
    try:
        from app.screenstudio_polish import (
            screenstudio_default_export_settings,
            screenstudio_default_result_beauty_score,
        )

        project_settings = dict(getattr(self, "_project_settings", {}) or {})
        defaults = dict(project_settings.get("screenstudio_export_defaults") or {})
        if not defaults:
            defaults = screenstudio_default_export_settings(project_settings)
    except Exception:
        defaults = {}
        screenstudio_default_result_beauty_score = None
    intent = str(defaults.get("intent_label") or defaults.get("intent_id") or "Web Demo")
    fmt = str(defaults.get("format_id") or getattr(self, "_export_format_id", "mp4")).upper()
    quality = str(defaults.get("quality_id") or getattr(self, "_export_quality_id", "high"))
    fps_value = getattr(self, "_export_fps", None) or defaults.get("fps")
    try:
        fps_label = f"{float(fps_value):.0f}fps"
    except Exception:
        fps_label = "auto fps"
    res_value = getattr(self, "_export_resolution", None) or defaults.get("resolution")
    if isinstance(res_value, (tuple, list)) and len(res_value) >= 2:
        res_label = f"{int(res_value[0])}x{int(res_value[1])}"
    else:
        res_label = "Original"
    handoff = str(defaults.get("handoff_label") or "").strip()
    handoff_label = f" | handoff {handoff}" if handoff else ""
    prefix = f"Screen Studio {intent}: {fmt}/{quality} {res_label} {fps_label}{handoff_label}"
    video_clips = []
    for track in getattr(self, "_tracks", []) or []:
        for clip in getattr(track, "clips", []) or []:
            if getattr(clip, "source_path", None) is not None:
                video_clips.append(clip)
    metadata_count = 0
    polished_count = 0
    zoom_count = 0
    for clip in video_clips:
        has_events = bool(getattr(clip, "cursor_events", None))
        if not has_events:
            try:
                from app.screenstudio_polish import cursor_sidecar_candidates

                has_events = any(candidate.is_file() for candidate in cursor_sidecar_candidates(getattr(clip, "source_path", None)))
            except Exception:
                has_events = False
        if has_events:
            metadata_count += 1
        actor_ids = list((getattr(clip, "screenstudio_polish", {}) or {}).get("auto_zoom_actor_ids", []) or [])
        if actor_ids:
            polished_count += 1
            zoom_count += len(actor_ids)
    beauty_note = ""
    try:
        if screenstudio_default_result_beauty_score is not None:
            beauty = screenstudio_default_result_beauty_score(
                getattr(self, "_project_settings", {}) or {},
                cursor_metadata_count=metadata_count,
                polished_clip_count=polished_count,
                auto_zoom_count=zoom_count,
            )
            beauty_note = f" | beauty {int(beauty.get('score', 0) or 0)}/100"
            if not beauty.get("ok"):
                failed = ", ".join(str(item) for item in list(beauty.get("failed") or [])[:3])
                if failed:
                    beauty_note += f" needs {failed}"
    except Exception:
        beauty_note = ""
    if not video_clips:
        return f"{prefix}{beauty_note} | no video clips"
    project_ready = bool((getattr(self, "_project_settings", {}) or {}).get("screenstudio_polish"))
    if metadata_count and polished_count >= metadata_count:
        return f"{prefix}{beauty_note} | polish OK clips={polished_count}/{metadata_count} zooms={zoom_count}"
    if metadata_count:
        missing = max(0, metadata_count - polished_count)
        return f"{prefix}{beauty_note} | needs Auto Polish metadata={metadata_count} missing={missing}"
    if project_ready:
        return f"{prefix}{beauty_note} | project defaults ready, no cursor metadata"
    return f"{prefix}{beauty_note} | no cursor metadata"

def _show_screenstudio_export_complete_dialog(
    self,
    output_path: Path,
    size: int,
    *,
    handoff_note: str = "",
    color_note: str = "",
    readiness_note: str = "",
) -> None:
    return _export_workflow._show_screenstudio_export_complete_dialog(
        self,
        output_path,
        size,
        handoff_note=handoff_note,
        color_note=color_note,
        readiness_note=readiness_note,
    )


def _import_screenstudio_srt_subtitles(self) -> None:
        """Import SRT subtitles with the Screen Studio starter caption style."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import SRT subtitles",
            str(Path.home() / "Videos"),
            "Subtitle files (*.srt);;All files (*.*)",
        )
        if not path:
            return
        srt_path = Path(path)
        text = ""
        for encoding in ("utf-8-sig", "utf-8", "cp949"):
            try:
                text = srt_path.read_text(encoding=encoding)
                break
            except Exception:
                text = ""
        if not text:
            QMessageBox.warning(self, "SRT", "SRT ?뚯씪???쎌쓣 ???놁뒿?덈떎.")
            return
        try:
            from app.screenstudio_parity import screenstudio_subtitle_rows_from_srt_text

            plan = screenstudio_subtitle_rows_from_srt_text(
                text,
                getattr(self, "_project_settings", {}) or {},
            )
            rows = list(plan.get("subtitle_rows", []) or [])
        except Exception as exc:
            QMessageBox.warning(self, "SRT", f"SRT ?뚯떛 ?ㅽ뙣: {exc}")
            return
        if not rows:
            QMessageBox.information(self, "SRT", "媛?몄삱 ?먮쭑 援ш컙???놁뒿?덈떎.")
            return
        imported: list[Subtitle] = []
        for row in rows:
            try:
                imported.append(
                    Subtitle(
                        text=str(row.get("text") or ""),
                        start_ms=int(row.get("start_ms", 0) or 0),
                        end_ms=int(row.get("end_ms", 0) or 0),
                        show_box=bool(row.get("show_box", True)),
                        style=dict(row.get("style", {}) or {}),
                    )
                )
            except Exception:
                continue
        if not imported:
            QMessageBox.information(self, "SRT", "媛?몄삱 ???덈뒗 ?먮쭑???놁뒿?덈떎.")
            return
        layer = self._subtitle_panel.layer
        layer.replace_all([*layer.items(), *imported])
        try:
            self._subtitle_panel._refresh_list()
        except Exception:
            pass
        try:
            self._subtitle_panel_toggle_btn.setChecked(True)
        except Exception:
            pass
        try:
            self._subtitle_panel.subtitles_changed.emit()
        except Exception:
            pass
        settings = dict(getattr(self, "_project_settings", {}) or {})
        settings["screenstudio_transcript_last_import"] = {
            "path": str(srt_path),
            "subtitle_rows": len(imported),
            "style_preset_id": plan.get("subtitle_style_preset_id"),
        }
        self._project_settings = settings
        if hasattr(self._player, "set_project_settings"):
            self._player.set_project_settings(settings)
        self._flash_status(f"Imported {len(imported)} Screen Studio subtitles")


def _screenstudio_candidate_interaction(self, phase: str, nx: float, ny: float, event: QMouseEvent) -> bool:
        dlg = getattr(self, "_screenstudio_polish_dialog", None)
        canvas = getattr(self, "_drawing_canvas", None)
        if dlg is None or not dlg.isVisible() or canvas is None:
            if canvas is not None:
                canvas.setCursor(Qt.CursorShape.ArrowCursor)
            self._screenstudio_candidate_drag = None
            return False
        canvas_w = max(1, int(canvas.width()))
        canvas_h = max(1, int(canvas.height()))
        point = QPoint(int(round(float(nx) * canvas_w)), int(round(float(ny) * canvas_h)))
        drag = getattr(self, "_screenstudio_candidate_drag", None)
        if phase == "press":
            hit = self._screenstudio_candidate_hit_test(point, canvas_w, canvas_h)
            if hit is None:
                canvas.setCursor(Qt.CursorShape.ArrowCursor)
                return False
            row, _rect, handle = hit
            key = str(row.get("key") or "")
            if not key:
                return False
            try:
                dlg.select_zoom_candidate_key(key)
            except Exception:
                pass
            state = dict(row)
            state["key"] = key
            state["handle"] = handle
            state["start_px"] = QPointF(point)
            self._screenstudio_candidate_drag = state
            canvas.setCursor(self._screenstudio_cursor_for_handle(handle))
            return True
        if phase == "move":
            if isinstance(drag, dict):
                values = self._screenstudio_candidate_drag_values(drag, float(nx), float(ny), canvas_w, canvas_h)
                try:
                    dlg.set_zoom_candidate_override(str(drag.get("key") or ""), values, emit=False)
                except Exception:
                    pass
                canvas.setCursor(self._screenstudio_cursor_for_handle(str(drag.get("handle") or "")))
                canvas.update()
                return True
            hit = self._screenstudio_candidate_hit_test(point, canvas_w, canvas_h)
            if hit is not None:
                _row, _rect, handle = hit
                canvas.setCursor(self._screenstudio_cursor_for_handle(handle))
                return True
            canvas.setCursor(Qt.CursorShape.ArrowCursor)
            return False
        if phase == "release":
            if isinstance(drag, dict):
                values = self._screenstudio_candidate_drag_values(drag, float(nx), float(ny), canvas_w, canvas_h)
                try:
                    dlg.set_zoom_candidate_override(str(drag.get("key") or ""), values, emit=False)
                    dlg.commit_zoom_candidate_override()
                except Exception:
                    pass
                self._screenstudio_candidate_drag = None
                canvas.setCursor(Qt.CursorShape.ArrowCursor)
                canvas.update()
                return True
        return False


# Extracted VideoEditorWindow Creator Assist helpers.
def _ensure_creator_assist_panel(self) -> list[QWidget]:
    if capcut_feature_disabled("creator_assist"):
        try:
            self._flash_status(capcut_disabled_reason("creator_assist"))
        except Exception:
            pass
        return []
    panel = getattr(self, "_creator_assist_panel", None)
    if panel is not None:
        wrapper = getattr(self, "_creator_assist_scroll_area", None)
        return [wrapper or panel]
    try:
        from app.creator_assist_panel import CreatorAssistPanel

        host = getattr(self, "_creator_assist_section_host", None)
        panel = CreatorAssistPanel(host)
        panel.setMinimumHeight(max(440, panel.sizeHint().height()))
        wrapper = make_workbench_section_scroll_area(
            host,
            panel,
            object_name="CreatorAssistScrollArea",
            min_content_height=440,
        )
        panel.analyze_requested.connect(self._analyze_creator_assist)
        panel.apply_requested.connect(self._apply_creator_assist_bundle)
        panel.preview_short_requested.connect(self._preview_creator_assist_short)
        panel.queue_exports_requested.connect(self._queue_creator_assist_exports)
        panel.copy_publish_requested.connect(self._copy_creator_assist_publish_text)
        panel.quick_create_requested.connect(self._apply_creator_assist_quick_create)
        self._creator_assist_panel = panel
        self._creator_assist_scroll_area = wrapper
        try:
            panel.set_bundle(dict(getattr(self, "_creator_assist_bundle", {}) or {}))
        except Exception:
            pass

        placeholder = getattr(self, "_creator_assist_placeholder", None)
        layout = host.layout() if host is not None else None
        if layout is not None and placeholder is not None:
            layout.replaceWidget(placeholder, wrapper)
            placeholder.hide()
            placeholder.setParent(None)
            placeholder.deleteLater()
        elif layout is not None:
            layout.addWidget(wrapper, stretch=1)
        panel.setVisible(True)
        wrapper.setVisible(True)
        return [wrapper]
    except Exception as exc:
        try:
            self._flash_status(f"Creator Assist load failed: {exc}")
        except Exception:
            pass
        placeholder = getattr(self, "_creator_assist_placeholder", None)
        return [placeholder] if placeholder is not None else []


def _open_creator_assist_panel(self) -> None:
    if capcut_feature_disabled("creator_assist"):
        self._flash_status(capcut_disabled_reason("creator_assist"))
        return
    if self._screenstudio_simple_mode_enabled():
        self._set_screenstudio_advanced_visible(True, persist=True, quiet=True)
    self._ensure_creator_assist_panel()
    self._set_collapsible_host_open(getattr(self, "_creator_assist_section_host", None), True)
    self._analyze_creator_assist()


def _creator_assist_project_end_ms(self) -> int:
    end_ms = 0
    try:
        end_ms = max(end_ms, int(self._player.duration()))
    except Exception:
        pass
    for track in getattr(self, "_tracks", []) or []:
        for clip in getattr(track, "clips", []) or []:
            start = int(getattr(clip, "timeline_in_ms", getattr(clip, "offset_ms", 0)) or 0)
            end = int(getattr(clip, "timeline_out_ms", start) or start)
            if end <= start:
                end = start + int(getattr(clip, "effective_length_ms", 0) or getattr(clip, "duration_ms", 0) or 0)
            end_ms = max(end_ms, end)
    for track in getattr(self, "_audio_tracks", []) or []:
        for clip in getattr(track, "clips", []) or []:
            start = int(getattr(clip, "offset_ms", 0) or 0)
            end_ms = max(end_ms, start + int(getattr(clip, "effective_length_ms", 0) or 0))
    return max(0, int(end_ms))


def _creator_assist_media_items(self) -> list[dict]:
    items: list[dict] = []
    pool = getattr(self, "_media_pool", None)
    paths = list(pool.items() if pool is not None and hasattr(pool, "items") else [])
    try:
        from app.media_pool import _probe_duration_ms as _probe_media_duration_ms
    except Exception:
        _probe_media_duration_ms = None
    for idx, raw in enumerate(paths):
        path = Path(raw)
        suffix = path.suffix.casefold()
        if suffix in VIDEO_EXTS:
            kind = "video"
        elif suffix in AUDIO_EXTS:
            kind = "audio"
        elif suffix in {".json", ".skel", ".atlas"}:
            kind = "actor"
        else:
            kind = "media"
        duration_ms = 0
        if callable(_probe_media_duration_ms):
            try:
                duration_ms = int(_probe_media_duration_ms(path) or 0)
            except Exception:
                duration_ms = 0
        name_text = path.name.casefold()
        tags = []
        if any(token in name_text for token in ("record", "capture", "?뱁솕", "screen")):
            tags.extend(["screen-recording", "tutorial"])
        if any(token in name_text for token in ("game", "play", "gameplay")):
            tags.extend(["gameplay", "short-form"])
        if suffix in VIDEO_EXTS:
            tags.append("video")
        if suffix in AUDIO_EXTS:
            tags.append("audio")
        items.append({
            "id": f"media-{idx + 1}",
            "name": path.name,
            "path": str(path),
            "kind": kind,
            "duration_s": duration_ms / 1000.0 if duration_ms > 0 else 0.0,
            "tags": list(dict.fromkeys(tags)),
        })
    return items


def _creator_assist_local_media_path(self, summary: dict | None = None) -> str:
    data = dict(summary or {})
    for item in data.get("media_items") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("kind") or "").casefold() not in {"video", "image"}:
            continue
        path = Path(str(item.get("path") or ""))
        try:
            if path.is_file():
                return str(path)
        except Exception:
            continue
    source_path = str(data.get("source_path") or "")
    if source_path:
        try:
            if Path(source_path).is_file():
                return source_path
        except Exception:
            pass
    return ""


def _creator_assist_merge_local_summary(summary: dict, local_summary: dict) -> dict:
    if not local_summary:
        return summary
    for key in ("subject_detections", "scene_ranges", "object_tags"):
        value = local_summary.get(key)
        if value:
            summary[key] = list(value) if isinstance(value, list) else value
    if local_summary.get("screen_recording"):
        summary["screen_recording"] = True
    if not summary.get("transcript_segments") and local_summary.get("transcript_segments"):
        summary["transcript_segments"] = list(local_summary.get("transcript_segments") or [])
        summary["dialogue"] = bool(summary["transcript_segments"])
    local_media = local_summary.get("media_items") or []
    if local_media and not summary.get("media_items"):
        summary["media_items"] = list(local_media)
    elif local_media and summary.get("media_items"):
        local_first = dict(local_media[0]) if isinstance(local_media[0], dict) else {}
        if local_first:
            enriched = []
            for item in summary.get("media_items") or []:
                row = dict(item)
                if str(row.get("path") or "") == str(local_first.get("path") or ""):
                    for key in ("object_tags", "tags", "people", "dialogue"):
                        if local_first.get(key) and not row.get(key):
                            row[key] = local_first[key]
                enriched.append(row)
            summary["media_items"] = enriched
    summary["local_ml_analysis"] = dict(local_summary.get("local_ml_analysis") or {})
    summary["local_ml_backend_status"] = dict(local_summary.get("local_ml_backend_status") or {})
    return summary


def _creator_deep_merge(base: dict, patch: dict) -> dict:
    for key, value in dict(patch or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _creator_deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _analyze_creator_assist(self) -> dict:
    if capcut_feature_disabled("creator_assist"):
        bundle = {
            "ok": False,
            "disabled": True,
            "reason": capcut_disabled_reason("creator_assist"),
            "review_panel": {"cards": []},
        }
        self._creator_assist_bundle = bundle
        self._flash_status("Creator Assist is disabled")
        return bundle
    try:
        from app.capcut_workflow import capcut_creator_apply_bundle

        summary = self._creator_assist_project_summary()
        local_summary = {}
        local_path = self._creator_assist_local_media_path(summary)
        if local_path and capcut_feature_enabled("local_ml"):
            try:
                from app.local_ml import local_ml_capcut_project_summary

                local_summary = local_ml_capcut_project_summary(
                    local_path,
                    include_transcript=False,
                    sample_count=3,
                )
                summary = _creator_assist_merge_local_summary(summary, local_summary)
            except Exception as exc:
                summary.setdefault("creator_assist_warnings", []).append(f"local_ml: {exc}")
        bundle = capcut_creator_apply_bundle(
            summary,
            summary.get("media_items") or [],
            platform="shorts",
            target_count=3,
        )
        if local_summary:
            notes = list(bundle.get("notes") or [])
            notes.append("Creator Assist used local visual analysis; no cloud API or model download was used.")
            bundle["notes"] = notes
            bundle["local_ml_analysis"] = dict(local_summary.get("local_ml_analysis") or {})
            bundle["local_ml_backend_status"] = dict(local_summary.get("local_ml_backend_status") or {})
    except Exception as exc:
        bundle = {"ok": False, "review_panel": {"cards": []}, "error": str(exc)}
        self._flash_status(f"Creator Assist failed: {exc}")
    self._creator_assist_bundle = dict(bundle or {})
    panel = getattr(self, "_creator_assist_panel", None)
    if panel is not None:
        panel.set_bundle(self._creator_assist_bundle)
    counts = ((self._creator_assist_bundle.get("review_panel") or {}).get("counts") or {})
    self._flash_status(
        f"Creator Assist 以鍮? ?쇱툩 ?꾨낫 {int(counts.get('short_candidates', 0) or 0)}媛?"
        f"caption beats {int(counts.get('caption_beats', 0) or 0)}"
    )
    return self._creator_assist_bundle


def _creator_assist_selected_options(self) -> dict[str, bool]:
    panel = getattr(self, "_creator_assist_panel", None)
    if panel is not None and hasattr(panel, "selected_apply_options"):
        try:
            return dict(panel.selected_apply_options())
        except Exception:
            pass
    return {
        "subtitles": True,
        "markers": True,
        "settings": True,
        "storyboard": True,
        "queue_exports": False,
    }


def _apply_creator_assist_quick_create(self) -> None:
    if capcut_feature_disabled("creator_assist"):
        self._flash_status(capcut_disabled_reason("creator_assist"))
        return
    panel = getattr(self, "_creator_assist_panel", None)
    if panel is not None and hasattr(panel, "set_busy"):
        try:
            panel.set_busy(True, "鍮좊Ⅸ ?쒖옉: 遺꾩꽍怨??곸슜??以鍮꾪븯??以?..")
        except Exception:
            pass
    if panel is not None and hasattr(panel, "select_quick_create_options"):
        try:
            panel.select_quick_create_options()
        except Exception:
            pass
    try:
        bundle = dict(getattr(self, "_creator_assist_bundle", {}) or {})
        if not bundle:
            bundle = self._analyze_creator_assist()
        if not bundle or bundle.get("disabled"):
            self._flash_status("Creator Assist 鍮좊Ⅸ ?쒖옉???ㅽ뻾?????놁뒿?덈떎")
            return
        self._apply_creator_assist_bundle()
        try:
            self._copy_creator_assist_publish_text()
        except Exception:
            pass
    finally:
        if panel is not None and hasattr(panel, "set_busy"):
            try:
                panel.set_busy(False)
            except Exception:
                pass


def _apply_creator_assist_subtitles(self, bundle: dict, *, emit_changed: bool = True) -> int:
    rows = [row for row in (bundle.get("subtitle_rows") or []) if isinstance(row, dict)]
    if not rows or not hasattr(self, "_subtitle_panel"):
        return 0
    from app.subtitles import Subtitle

    layer = self._subtitle_panel.layer
    existing = {
        (
            int(getattr(sub, "start_ms", 0) or 0),
            int(getattr(sub, "end_ms", 0) or 0),
            " ".join(str(getattr(sub, "text", "") or "").split()).casefold(),
        )
        for sub in layer.items()
    }
    added = 0
    for row in rows:
        text = " ".join(str(row.get("text", "") or "").split())
        if not text:
            continue
        start_ms = max(0, int(row.get("start_ms", 0) or 0))
        end_ms = max(start_ms + 500, int(row.get("end_ms", start_ms + 1800) or start_ms + 1800))
        key = (start_ms, end_ms, text.casefold())
        if key in existing:
            continue
        style = dict(row.get("style") or {})
        preset_id = str(row.get("style_preset_id") or style.get("preset_id") or "caption-capcut-word-pop")
        style["preset_id"] = preset_id
        style["source"] = "creator_assist"
        style["word_highlight"] = bool(row.get("word_highlight", "word" in preset_id or "karaoke" in preset_id))
        layer.add(Subtitle(start_ms=start_ms, end_ms=end_ms, text=text, show_box=bool(row.get("show_box", True)), style=style))
        existing.add(key)
        added += 1
    if added:
        self._subtitle_panel._refresh_list()
        if hasattr(self, "_subtitle_lane"):
            self._subtitle_lane.update()
        self._subtitle_panel_toggle_btn.setChecked(True)
        if emit_changed:
            self._subtitle_panel.subtitles_changed.emit()
    return added


def _apply_creator_assist_markers(self, bundle: dict) -> int:
    rows = [row for row in (bundle.get("timeline_markers") or []) if isinstance(row, dict)]
    if not rows:
        return 0
    kept = [
        marker for marker in getattr(self, "_timeline_markers", []) or []
        if str(marker.get("source") or "").casefold() not in {"capcut_creator_workflow", "creator_assist", "ltx_storyboard"}
        and not str(marker.get("id") or "").casefold().startswith("capcut-")
    ]
    added = 0
    for idx, row in enumerate(rows, start=1):
        start_ms = max(0, int(row.get("start_ms", row.get("ms", 0)) or 0))
        end_ms = max(start_ms + 1, int(row.get("end_ms", start_ms + 1) or start_ms + 1))
        kept.append({
            "ms": start_ms,
            "end_ms": end_ms,
            "color": str(row.get("color") or "#FF6F61"),
            "label": str(row.get("label") or f"Short {idx}"),
            "id": str(row.get("id") or f"capcut-short-{idx:02d}"),
            "score": row.get("score", 0),
            "reason": str(row.get("reason") or ""),
            "source": str(row.get("source") or ("ltx_storyboard" if row.get("storyboard_marker") else "creator_assist")),
            "storyboard_marker": bool(row.get("storyboard_marker")),
            "shot_id": str(row.get("shot_id") or ""),
        })
        added += 1
    self._timeline_markers = sorted(kept, key=lambda marker: int(marker.get("ms", 0) or 0))
    self._sync_markers_to_ruler()
    return added


def _apply_creator_assist_settings(self, bundle: dict) -> None:
    settings = dict(getattr(self, "_project_settings", {}) or {})
    patch = dict(bundle.get("project_settings_patch") or {})
    if patch:
        self._creator_deep_merge(settings, patch)
    settings.setdefault("creator_assist", {})
    settings["creator_assist"].update({
        "enabled": True,
        "source": "editor_panel",
        "last_platform": ((bundle.get("export_settings") or {}).get("platform") or "shorts"),
    })
    self._project_settings = settings
    export_settings = dict(bundle.get("export_settings") or {})
    if export_settings.get("format_id"):
        self._export_format_id = str(export_settings.get("format_id"))
    if export_settings.get("quality_id"):
        self._export_quality_id = str(export_settings.get("quality_id"))
    if export_settings.get("canvas_width") and export_settings.get("canvas_height"):
        self._export_resolution = (int(export_settings["canvas_width"]), int(export_settings["canvas_height"]))
    if export_settings.get("fps"):
        self._export_fps = float(export_settings["fps"])
    if hasattr(self._player, "set_project_settings"):
        self._player.set_project_settings(self._project_settings)
    for refresh in (
        "_refresh_format_btn_label",
        "_refresh_quality_btn_label",
        "_refresh_resolution_btn_label",
        "_refresh_fps_btn_label",
    ):
        fn = getattr(self, refresh, None)
        if callable(fn):
            try:
                fn()
            except Exception:
                pass


def _preview_creator_assist_short(self) -> None:
    if capcut_feature_disabled("creator_assist"):
        self._flash_status(capcut_disabled_reason("creator_assist"))
        return
    bundle = dict(getattr(self, "_creator_assist_bundle", {}) or {})
    markers = [row for row in (bundle.get("timeline_markers") or self._capcut_short_ranges or []) if isinstance(row, dict)]
    if not markers:
        bundle = self._analyze_creator_assist()
        markers = [row for row in (bundle.get("timeline_markers") or []) if isinstance(row, dict)]
    if not markers:
        self._flash_status("Creator Assist: 미리 볼 쇼츠 후보가 없습니다")
        return
    row = markers[0]
    start_ms = max(0, int(row.get("start_ms", row.get("ms", 0)) or 0))
    end_ms = max(start_ms + 1, int(row.get("end_ms", start_ms + 1) or start_ms + 1))
    self._set_global_in(start_ms)
    self._set_global_out(end_ms)
    self._player.set_position(start_ms)
    self._update_time_label()
    self._flash_status(f"쇼츠 미리보기: {row.get('label') or 'Short'}")

# ScreenStudio preview candidate overlay helpers moved out of VideoEditorWindow.
def _maybe_apply_default_screenstudio_polish_to_clip(
    self,
    track: "VideoTrack",
    clip,
    *,
    reason: str = "import",
) -> int:
    try:
        existing_payload = dict(getattr(clip, "screenstudio_polish", {}) or {})
        if existing_payload.get("auto_zoom_actor_ids"):
            return 0
        if not getattr(clip, "cursor_events", None):
            self._load_screenstudio_cursor_sidecar_for_clip(clip)
        events = list(getattr(clip, "cursor_events", []) or [])
        if not events:
            return 0
        from app.screenstudio_polish import (
            apply_screenstudio_polish_to_clip,
            normalize_screenstudio_polish,
        )

        payload = normalize_screenstudio_polish(self._screenstudio_default_polish_payload())
        frame_w, frame_h = self._clip_preview_frame_size(track, clip)
        added = apply_screenstudio_polish_to_clip(
            clip,
            frame_w=frame_w,
            frame_h=frame_h,
            cursor_events=events,
            cursor_polish=dict(payload.get("cursor", {}) or {}),
            screen_polish=dict(payload.get("screen", {}) or {}),
            preset_id=str(payload.get("preset_id") or ""),
            replace_previous=True,
        )
        if added <= 0:
            return 0
        settings = dict(getattr(self, "_project_settings", {}) or {})
        settings["screenstudio_polish"] = payload
        settings.setdefault("starter_template_id", str(payload.get("starter_template_id") or "screen-recording-demo"))
        self._project_settings = settings
        if hasattr(self._player, "set_project_settings"):
            self._player.set_project_settings(settings)
        return int(added)
    except Exception:
        return 0


def _register_screenstudio_real_recording_candidate(self, path: Path, *, reason: str = "") -> None:
    try:
        if not is_video_path(path):
            return
    except Exception:
        return
    try:
        from app.screenstudio_parity import screenstudio_register_real_recording

        report = screenstudio_register_real_recording(
            path,
            metadata={"reason": reason, "starter_template_id": str((getattr(self, "_project_settings", {}) or {}).get("starter_template_id") or "")},
        )
        settings = dict(getattr(self, "_project_settings", {}) or {})
        settings["screenstudio_real_corpus_last_register"] = report
        self._project_settings = settings
    except Exception:
        pass


def _screenstudio_preview_candidate_rows(self) -> list[dict]:
    dlg = getattr(self, "_screenstudio_polish_dialog", None)
    if dlg is None or not dlg.isVisible():
        return []
    try:
        rows = list(dlg.visible_zoom_candidates())
    except Exception:
        return []
    if not rows:
        return []
    pos = 0
    try:
        pos = int(self._player.position())
    except Exception:
        pass
    selected_key = ""
    try:
        selected_key = str(dlg._current_candidate_key())
    except Exception:
        selected_key = ""
    out: list[dict] = []
    for row in rows:
        row = dict(row)
        clip = None
        try:
            track_id = int(row.get("track_id", -1) or -1)
            clip_id = int(row.get("clip_id", -1) or -1)
            track = self._find_track(track_id)
            if track is not None:
                clip = next((c for c in getattr(track, "clips", []) or [] if int(getattr(c, "id", -1)) == clip_id), None)
        except Exception:
            clip = None
        if clip is not None:
            start_t = int(getattr(clip, "timeline_in_ms", 0) or 0) + int(row.get("start_ms", 0) or 0)
            end_t = int(getattr(clip, "timeline_in_ms", 0) or 0) + int(row.get("end_ms", 0) or 0)
            if pos < start_t or pos > end_t:
                continue
        row["_selected"] = bool(selected_key and selected_key == str(row.get("key") or ""))
        out.append(row)
    return out[:8]


def _screenstudio_candidate_canvas_rects(
    self,
    frame_rect: QRect,
    src_w: int,
    src_h: int,
) -> list[tuple[dict, QRect, int]]:
    rows = self._screenstudio_preview_candidate_rows()
    if not rows or src_w <= 0 or src_h <= 0 or frame_rect.width() <= 0 or frame_rect.height() <= 0:
        return []
    rects: list[tuple[dict, QRect, int]] = []
    for idx, row in enumerate(rows, start=1):
        try:
            fw = max(1, int(row.get("frame_w", src_w) or src_w))
            fh = max(1, int(row.get("frame_h", src_h) or src_h))
            x = int(row.get("target_x", 0) or 0)
            y = int(row.get("target_y", 0) or 0)
            w = int(row.get("target_w", fw) or fw)
            h = int(row.get("target_h", fh) or fh)
        except Exception:
            continue
        rx = frame_rect.x() + int(round(x / fw * frame_rect.width()))
        ry = frame_rect.y() + int(round(y / fh * frame_rect.height()))
        rw = max(8, int(round(w / fw * frame_rect.width())))
        rh = max(8, int(round(h / fh * frame_rect.height())))
        rect = QRect(rx, ry, rw, rh).intersected(frame_rect)
        if rect.width() > 4 and rect.height() > 4:
            rects.append((row, rect, idx))
    return rects


def _screenstudio_candidate_handle(rect: QRect, point: QPoint) -> str:
    if not rect.adjusted(-10, -10, 10, 10).contains(point):
        return ""
    margin = max(7, min(14, min(rect.width(), rect.height()) // 7))
    left = abs(point.x() - rect.left()) <= margin
    right = abs(point.x() - rect.right()) <= margin
    top = abs(point.y() - rect.top()) <= margin
    bottom = abs(point.y() - rect.bottom()) <= margin
    if left and top:
        return "nw"
    if right and top:
        return "ne"
    if left and bottom:
        return "sw"
    if right and bottom:
        return "se"
    if left:
        return "w"
    if right:
        return "e"
    if top:
        return "n"
    if bottom:
        return "s"
    if rect.contains(point):
        return "move"
    return ""


def _screenstudio_candidate_hit_test(self, point: QPoint, canvas_w: int, canvas_h: int) -> tuple[dict, QRect, str] | None:
    src_w, src_h = 0, 0
    pix = getattr(self, "_preview_pixmap", None)
    if pix is not None and not pix.isNull():
        src_w, src_h = int(pix.width()), int(pix.height())
    if src_w <= 0 or src_h <= 0:
        src_w, src_h = getattr(self, "_preview_gl_frame_size", (0, 0))
    rects = self._screenstudio_candidate_canvas_rects(
        QRect(0, 0, max(1, int(canvas_w)), max(1, int(canvas_h))),
        int(src_w or canvas_w or 1),
        int(src_h or canvas_h or 1),
    )
    for row, rect, _idx in reversed(rects):
        handle = self._screenstudio_candidate_handle(rect, point)
        if handle:
            return row, rect, handle
    return None


def _screenstudio_candidate_drag_values(self, state: dict, nx: float, ny: float, canvas_w: int, canvas_h: int) -> dict:
    fw = max(1, int(state.get("frame_w", 1) or 1))
    fh = max(1, int(state.get("frame_h", 1) or 1))
    start_px = state.get("start_px") or QPointF(0, 0)
    dx = int(round((float(nx) * max(1, canvas_w) - float(start_px.x())) / max(1, canvas_w) * fw))
    dy = int(round((float(ny) * max(1, canvas_h) - float(start_px.y())) / max(1, canvas_h) * fh))
    x = int(state.get("target_x", 0) or 0)
    y = int(state.get("target_y", 0) or 0)
    w = int(state.get("target_w", fw) or fw)
    h = int(state.get("target_h", fh) or fh)
    handle = str(state.get("handle", "move") or "move")
    min_w = max(8, min(fw, max(32, int(round(fw * 0.04)))))
    min_h = max(8, min(fh, max(32, int(round(fh * 0.04)))))
    left = x
    top = y
    right = x + w
    bottom = y + h
    if handle == "move":
        x = max(0, min(fw - w, x + dx))
        y = max(0, min(fh - h, y + dy))
    else:
        if "w" in handle:
            left = max(0, min(right - min_w, left + dx))
        if "e" in handle:
            right = max(left + min_w, min(fw, right + dx))
        if "n" in handle:
            top = max(0, min(bottom - min_h, top + dy))
        if "s" in handle:
            bottom = max(top + min_h, min(fh, bottom + dy))
        x = int(left)
        y = int(top)
        w = int(max(min_w, right - left))
        h = int(max(min_h, bottom - top))
        if x + w > fw:
            w = fw - x
        if y + h > fh:
            h = fh - y
    return {
        "start_ms": int(state.get("start_ms", 0) or 0),
        "end_ms": int(state.get("end_ms", 0) or 0),
        "target_x": int(max(0, x)),
        "target_y": int(max(0, y)),
        "target_w": int(max(1, w)),
        "target_h": int(max(1, h)),
    }


def _paint_screenstudio_candidate_canvas_overlay(self, painter: QPainter, canvas_w: int, canvas_h: int) -> None:
    src_w, src_h = 0, 0
    pix = getattr(self, "_preview_pixmap", None)
    if pix is not None and not pix.isNull():
        src_w, src_h = int(pix.width()), int(pix.height())
    if src_w <= 0 or src_h <= 0:
        src_w, src_h = getattr(self, "_preview_gl_frame_size", (0, 0))
    self._paint_screenstudio_candidate_overlay(
        painter,
        QRect(0, 0, max(1, int(canvas_w)), max(1, int(canvas_h))),
        int(src_w or canvas_w or 1),
        int(src_h or canvas_h or 1),
    )


def _paint_screenstudio_candidate_overlay(
    self,
    painter: QPainter,
    frame_rect: QRect,
    src_w: int,
    src_h: int,
) -> None:
    rects = self._screenstudio_candidate_canvas_rects(frame_rect, src_w, src_h)
    if not rects:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    for row, rect, idx in rects:
        selected = bool(row.get("_selected"))
        fill = QColor(139, 120, 255, 42 if selected else 24)
        border = QColor(255, 124, 92, 235 if selected else 178)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 10, 10)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border, 2.4 if selected else 1.6))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 10, 10)
        badge_rect = QRect(rect.x() + 8, max(frame_rect.y() + 6, rect.y() - 26), 82, 22)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 23, 38, 210))
        painter.drawRoundedRect(badge_rect, 9, 9)
        painter.setPen(QColor("#FFFFFF"))
        font = QFont(painter.font())
        font.setPointSize(max(8, font.pointSize()))
        font.setBold(True)
        painter.setFont(font)
        label = f"Zoom {idx}"
        if selected:
            label = f"* {label}"
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, label)
        if selected:
            handle_color = QColor("#FFFFFF")
            handle_fill = QColor(255, 124, 92, 230)
            painter.setPen(QPen(handle_color, 1.2))
            painter.setBrush(handle_fill)
            handle = 7
            for px, py in (
                (rect.left(), rect.top()),
                (rect.center().x(), rect.top()),
                (rect.right(), rect.top()),
                (rect.left(), rect.center().y()),
                (rect.right(), rect.center().y()),
                (rect.left(), rect.bottom()),
                (rect.center().x(), rect.bottom()),
                (rect.right(), rect.bottom()),
            ):
                painter.drawRoundedRect(QRect(int(px) - handle // 2, int(py) - handle // 2, handle, handle), 3, 3)
    painter.restore()
