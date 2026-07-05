"""Phase 1 unit tests — clip API + legacy-track migration.

Pure-Python: no Qt or ffmpeg involvement. Run with::

    python -m pytest tests/test_timeline_model.py -v

The tests exercise the slice of behaviour that Phase 1.5 (renderer
rewire) will rely on:

- ``VideoTrack.split_at`` produces two independent halves whose
  combined output duration equals the original.
- Trim / move respect their boundary invariants.
- ``migrate_legacy_video_track`` round-trips a single-source legacy
  track with cuts into a clip-list track that plays the same frames
  in the same project-time order.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.timeline_model import (
    ColorNode,
    CutSegment,
    FadeSegment,
    NodeGraph,
    SpeedSegment,
    Timeline,
    VideoClip,
    VideoTrack,
    ZoomActor,
    migrate_legacy_video_track,
    zoom_ease_value,
    zoom_motion_blur_amount,
    zoom_window_at,
)
from app.screenstudio_polish import (
    CursorEvent,
    apply_cursor_fx_rgb,
    apply_screen_frame_style_rgb,
    apply_screenstudio_polish_to_clip,
    cursor_state_at,
    infer_action_points,
    normalize_screenstudio_polish,
    plan_auto_zoom_actors,
    screenstudio_apply_manual_zoom_edit,
    screenstudio_build_share_link,
    screenstudio_default_export_settings,
    screenstudio_default_export_result_readiness,
    screenstudio_default_result_beauty_score,
    screenstudio_default_golden_video_probe,
    screenstudio_export_completion_summary,
    screenstudio_audio_defaults,
    screenstudio_share_manifest_path,
    screenstudio_write_local_share_manifest,
    screenstudio_interaction_report,
    screenstudio_fx_enabled,
    screenstudio_polish_parity_report,
    screenstudio_polish_preset,
    screenstudio_manual_zoom_editor_report,
    screenstudio_simple_mode_profile,
    screenstudio_sidecar_report,
    screenstudio_starter_defaults,
    screenstudio_zoom_timing_profile,
    smooth_cursor_events,
    static_cursor_hidden_intervals,
)
from app.recorder import _hotkey_label_from_pressed


# ---------------------------------------------------------------------------
#  Fixtures: a stand-in legacy track + a fake ColorGrade so tests never
#  pull in the real color_grading module (which depends on numpy).
# ---------------------------------------------------------------------------


@dataclass
class _FakeGrade:
    brightness: int = 0
    contrast: int = 0

    def is_identity(self) -> bool:
        return self.brightness == 0 and self.contrast == 0


@dataclass
class _LegacyTrack:
    """Mimics the public surface of video_track_legacy.VideoTrack so
    migrate_legacy_video_track can read it via duck-typing."""

    id: int = 0
    source_path: Path | None = None
    duration_ms: int = 0
    offset_ms: int = 0
    cuts: list = field(default_factory=list)
    fades: list = field(default_factory=list)
    zoom_actors: list = field(default_factory=list)
    typography_actors: list = field(default_factory=list)
    color_grade: object = None


def _make_clip(
    *, timeline_in_ms: int = 0, source_in_ms: int = 0, source_out_ms: int = 10_000,
    source_duration_ms: int = 10_000,
) -> VideoClip:
    """Build a VideoClip with an identity NodeGraph that doesn't pull
    in the real ColorGrade (and therefore numpy)."""
    return VideoClip(
        id=1,
        source_path=Path("/fake/test.mp4"),
        source_duration_ms=source_duration_ms,
        timeline_in_ms=timeline_in_ms,
        source_in_ms=source_in_ms,
        source_out_ms=source_out_ms,
        node_graph=NodeGraph(color=ColorNode(grade=_FakeGrade())),
    )


# ---------------------------------------------------------------------------
#  VideoClip derived properties
# ---------------------------------------------------------------------------


class TestVideoClipDerived:
    def test_effective_length_full_source(self):
        c = _make_clip(source_in_ms=0, source_out_ms=0,
                       source_duration_ms=8000)
        assert c.effective_length_ms == 8000
        assert c.timeline_out_ms == c.timeline_in_ms + 8000

    def test_effective_length_with_trim(self):
        c = _make_clip(source_in_ms=2000, source_out_ms=7000,
                       source_duration_ms=10000)
        assert c.effective_length_ms == 5000

    def test_timeline_to_source_ms(self):
        c = _make_clip(timeline_in_ms=4000, source_in_ms=1000)
        assert c.timeline_to_source_ms(4500) == 1500
        assert c.timeline_to_source_ms(4000) == 1000

    def test_contains_timeline_ms_boundaries(self):
        c = _make_clip(timeline_in_ms=2000, source_out_ms=3000,
                       source_duration_ms=3000)
        # Window is [2000, 5000)
        assert c.contains_timeline_ms(2000)
        assert c.contains_timeline_ms(4999)
        assert not c.contains_timeline_ms(5000)
        assert not c.contains_timeline_ms(1999)


class TestScreenStudioPolish:
    def test_auto_zoom_uses_click_metadata(self):
        events = [
            CursorEvent(900, 0.20, 0.30, "move"),
            CursorEvent(1500, 0.72, 0.44, "click"),
        ]
        actors = plan_auto_zoom_actors(
            duration_ms=5000,
            frame_w=1000,
            frame_h=500,
            cursor_events=events,
        )
        assert actors
        actor = actors[0]
        assert actor.is_configured()
        assert actor.start_ms <= 1500 <= actor.end_ms
        click_x = int(0.72 * 1000)
        assert actor.target_x < click_x < actor.target_x + actor.target_w
        assert actor.target_x + actor.target_w <= 1000

    def test_auto_zoom_fallback_without_metadata(self):
        actors = plan_auto_zoom_actors(duration_ms=8000, frame_w=1200, frame_h=800)
        assert len(actors) >= 2
        assert all(a.is_configured() for a in actors)

    def test_zoom_timing_profile_expands_for_long_recordings(self):
        short = screenstudio_zoom_timing_profile(duration_ms=8000, event_count=5, action_count=3)
        long = screenstudio_zoom_timing_profile(duration_ms=90_000, event_count=30, action_count=18)

        assert short["max_actors"] <= 3
        assert long["max_actors"] >= 6
        assert long["rhythm_gap_ms"] >= 5000
        assert long["zoom_duration_ms"] <= 2100

    def test_long_recording_auto_zoom_uses_rhythmic_pacing(self):
        events = [
            CursorEvent(1000, 0.16, 0.28, "click"),
            CursorEvent(2400, 0.20, 0.30, "release"),
            CursorEvent(4500, 0.24, 0.34, "click"),
            CursorEvent(18_000, 0.62, 0.42, "hotkey", True, "Ctrl + K"),
            CursorEvent(32_000, 0.74, 0.50, "click"),
            CursorEvent(48_000, 0.42, 0.60, "drag"),
            CursorEvent(65_000, 0.35, 0.52, "release"),
            CursorEvent(82_000, 0.68, 0.34, "click"),
        ]

        actors = plan_auto_zoom_actors(
            duration_ms=90_000,
            frame_w=1920,
            frame_h=1080,
            cursor_events=events,
        )

        assert len(actors) >= 6
        point_times = [int(getattr(actor, "screenstudio_point_ms", 0) or 0) for actor in actors]
        assert max(point_times) >= 65_000
        assert min(right - left for left, right in zip(point_times, point_times[1:])) >= 4000

    def test_auto_zoom_prefers_click_over_nearby_motion(self):
        points = infer_action_points(
            [
                CursorEvent(1000, 0.25, 0.25, "move"),
                CursorEvent(1180, 0.72, 0.44, "click"),
                CursorEvent(1800, 0.76, 0.46, "release"),
            ],
            duration_ms=3200,
            max_points=5,
        )

        assert points
        assert points[0].kind == "click"
        assert len(points) <= 2

    def test_auto_zoom_uses_dwell_when_user_pauses_without_click(self):
        events = [
            CursorEvent(200, 0.18, 0.34, "move"),
            CursorEvent(900, 0.68, 0.42, "move"),
            CursorEvent(1500, 0.681, 0.421, "move"),
            CursorEvent(2300, 0.682, 0.422, "move"),
            CursorEvent(3600, 0.40, 0.52, "move"),
        ]

        points = infer_action_points(events, duration_ms=5000, max_points=3)
        actors = plan_auto_zoom_actors(
            duration_ms=5000,
            frame_w=1280,
            frame_h=720,
            cursor_events=events,
            max_actors=3,
        )

        assert points
        assert points[0].kind == "dwell"
        assert 1400 <= points[0].t_ms <= 2400
        assert actors
        dwell_x = int(points[0].x_norm * 1280)
        assert actors[0].target_x < dwell_x < actors[0].target_x + actors[0].target_w

    def test_auto_zoom_merges_same_spot_click_release(self):
        points = infer_action_points(
            [
                CursorEvent(900, 0.52, 0.50, "click"),
                CursorEvent(1320, 0.535, 0.505, "release"),
            ],
            duration_ms=4000,
            max_points=3,
        )

        assert len(points) == 1
        assert points[0].kind == "click"

    def test_auto_zoom_skips_late_candidate_when_it_would_overlap(self):
        actors = plan_auto_zoom_actors(
            duration_ms=5200,
            frame_w=1080,
            frame_h=1920,
            cursor_events=[
                CursorEvent(260, 0.50, 0.18, "click"),
                CursorEvent(1040, 0.55, 0.38, "drag"),
                CursorEvent(1540, 0.58, 0.50, "release"),
                CursorEvent(2940, 0.46, 0.68, "hotkey", True, "Shift + F1"),
                CursorEvent(4100, 0.42, 0.82, "click"),
            ],
        )

        assert len(actors) == 2
        windows = [(a.start_ms, a.end_ms) for a in actors]
        assert windows[0][1] <= windows[1][0]

    def test_cursor_smoothing_and_static_hide(self):
        events = [
            CursorEvent(0, 0.10, 0.10),
            CursorEvent(100, 0.90, 0.10),
            CursorEvent(1100, 0.901, 0.101),
            CursorEvent(1900, 0.902, 0.101),
        ]
        smoothed = smooth_cursor_events(events, smoothing=0.8)
        assert smoothed[1].x_norm < 0.90
        hidden = static_cursor_hidden_intervals(events, hide_after_ms=700)
        assert hidden == [(800, 1900)]

    def test_cursor_motion_uses_screenstudio_ease(self):
        events = [
            CursorEvent(0, 0.0, 0.5, "move"),
            CursorEvent(1000, 1.0, 0.5, "move"),
        ]

        linear = cursor_state_at(events, 250, smoothing=0.0, motion_easing="linear")
        eased = cursor_state_at(events, 250, smoothing=0.0, motion_easing="smooth")

        assert linear is not None
        assert eased is not None
        assert linear["x_norm"] == pytest.approx(0.25)
        assert eased["x_norm"] < linear["x_norm"]

    def test_cursor_click_hold_settles_before_following_motion(self):
        events = [
            CursorEvent(100, 0.20, 0.40, "click"),
            CursorEvent(500, 0.80, 0.40, "move"),
        ]

        held = cursor_state_at(events, 180, smoothing=0.0, click_hold_ms=220)
        released = cursor_state_at(events, 360, smoothing=0.0, click_hold_ms=220)
        no_hold = cursor_state_at(events, 180, smoothing=0.0, click_hold_ms=0)

        assert held is not None
        assert released is not None
        assert no_hold is not None
        assert held["x_norm"] == pytest.approx(0.20)
        assert no_hold["x_norm"] > held["x_norm"] + 0.03
        assert released["x_norm"] > held["x_norm"]

    def test_cursor_loop_back_returns_to_start_near_end(self):
        events = [
            CursorEvent(0, 0.10, 0.30, "move"),
            CursorEvent(3000, 0.82, 0.64, "move"),
        ]

        before_loop = cursor_state_at(
            events,
            4600,
            smoothing=0.0,
            duration_ms=6000,
            loop_cursor=True,
            loop_return_ms=1000,
            hide_after_ms=10_000,
        )
        near_end = cursor_state_at(
            events,
            5850,
            smoothing=0.0,
            duration_ms=6000,
            loop_cursor=True,
            loop_return_ms=1000,
            hide_after_ms=10_000,
        )

        assert before_loop is not None
        assert near_end is not None
        assert before_loop["x_norm"] == pytest.approx(0.82)
        assert near_end["x_norm"] < 0.24
        assert near_end["y_norm"] < 0.38

    def test_screenstudio_ready_defaults_drive_starter_and_export(self):
        payload = screenstudio_starter_defaults("screen-recording-demo")
        export = screenstudio_default_export_settings(
            {
                "starter_template_id": "screen-recording-demo",
                "canvas_width": 1920,
                "canvas_height": 1080,
                "fps": 30.0,
                "screenstudio_polish": payload,
            }
        )

        assert payload["preset_id"] == "screenstudio_ready"
        assert payload["cursor"]["cursor_smoothing"] >= 0.8
        assert payload["cursor"]["loop_cursor"] is True
        assert payload["screen"]["shadow"] >= 0.6
        assert export["screenstudio_ready"] is True
        assert export["format_id"] == "mp4"
        assert export["quality_id"] == "high"
        assert export["intent_id"] == "web_demo"
        assert "website" in export["destinations"]
        assert export["fps"] == 60.0
        assert export["resolution"] == (1920, 1080)
        assert export["clipboard_ready"] is True
        assert export["share_package_ready"] is True
        assert export["share_link_ready"] is False
        assert "copy_path" in export["post_export_actions"]
        assert "local_share_package" in export["post_export_actions"]

    def test_screenstudio_export_intents_pick_delivery_defaults(self):
        social = screenstudio_default_export_settings(
            {
                "starter_template_id": "vertical-shorts",
                "canvas_width": 1080,
                "canvas_height": 1920,
                "fps": 30.0,
            }
        )
        roundtrip = screenstudio_default_export_settings(
            {
                "starter_template_id": "actor-showcase",
                "canvas_width": 1920,
                "canvas_height": 1080,
                "fps": 24.0,
            }
        )
        explicit = screenstudio_default_export_settings(
            {
                "screenstudio_export_intent": "social_vertical",
                "canvas_width": 1920,
                "canvas_height": 1080,
                "fps": 24.0,
            }
        )

        assert social["intent_id"] == "social_vertical"
        assert social["fps"] == 60.0
        assert "shorts" in social["destinations"]
        assert roundtrip["format_id"] == "mov"
        assert roundtrip["quality_id"] == "best"
        assert roundtrip["clipboard_ready"] is False
        assert roundtrip["share_package_ready"] is True
        assert explicit["intent_id"] == "social_vertical"
        assert explicit["fps"] == 60.0
        assert explicit["clipboard_ready"] is True

    def test_import_cursor_metadata_auto_applies_default_polish(self, monkeypatch):
        from app.video_editor_window import VideoEditorWindow

        clip = _make_clip(source_out_ms=4200, source_duration_ms=4200)
        clip.cursor_events = [
            {"t_ms": 600, "x_norm": 0.30, "y_norm": 0.40, "kind": "move"},
            {"t_ms": 1200, "x_norm": 0.70, "y_norm": 0.42, "kind": "click"},
            {"t_ms": 2100, "x_norm": 0.72, "y_norm": 0.44, "kind": "release"},
        ]
        track = SimpleNamespace(id=1, clips=[clip])
        seen_settings: list[dict] = []
        dummy = SimpleNamespace(
            _project_settings={"starter_template_id": "screen-recording-demo"},
            _player=SimpleNamespace(set_project_settings=lambda settings: seen_settings.append(dict(settings))),
        )
        dummy._load_screenstudio_cursor_sidecar_for_clip = lambda _clip: 0
        dummy._screenstudio_default_polish_payload = (
            lambda: VideoEditorWindow._screenstudio_default_polish_payload(dummy)
        )
        dummy._clip_preview_frame_size = lambda _track, _clip: (1280, 720)

        added = VideoEditorWindow._maybe_apply_default_screenstudio_polish_to_clip(dummy, track, clip)
        note = VideoEditorWindow._screenstudio_export_badge_note(
            SimpleNamespace(
                _tracks=[track],
                _project_settings=getattr(dummy, "_project_settings", {}),
                _export_format_id="mp4",
                _export_quality_id="high",
                _export_resolution=(1920, 1080),
                _export_fps=60.0,
            )
        )

        assert added >= 1
        assert clip.screenstudio_polish["preset_id"] == "screenstudio_ready"
        assert clip.screenstudio_polish["auto_zoom_actor_ids"]
        assert seen_settings
        assert "Screen Studio Web Demo" in note
        assert "MP4/high" in note
        assert "1920x1080" in note
        assert "60fps" in note
        assert "polish OK" in note

    def test_export_button_tooltip_exposes_screenstudio_readiness(self):
        from app.video_editor_window import VideoEditorWindow

        class _FakeButton:
            def __init__(self):
                self.tooltip = ""

            def setToolTip(self, value):
                self.tooltip = value

        dummy = SimpleNamespace(
            export_btn=_FakeButton(),
            _tracks=[],
            _project_settings={
                "starter_template_id": "vertical-shorts",
                "canvas_width": 1080,
                "canvas_height": 1920,
                "fps": 60.0,
                "screenstudio_polish": screenstudio_starter_defaults("vertical-shorts"),
            },
            _export_format_id="mp4",
            _export_quality_id="high",
            _export_resolution=(1080, 1920),
            _export_fps=60.0,
        )
        dummy._screenstudio_export_badge_note = lambda: VideoEditorWindow._screenstudio_export_badge_note(dummy)

        VideoEditorWindow._refresh_export_button_tooltip(dummy)

        assert "Social Vertical" in dummy.export_btn.tooltip
        assert "MP4/high" in dummy.export_btn.tooltip
        assert "1080x1920" in dummy.export_btn.tooltip
        assert "60fps" in dummy.export_btn.tooltip
        assert "handoff clipboard + local share" in dummy.export_btn.tooltip

    def test_post_export_handoff_copies_path_for_share_ready_exports(self, monkeypatch, tmp_path):
        import app.video_editor_window as video_editor_window
        from app.video_editor_window import VideoEditorWindow

        class _FakeClipboard:
            def __init__(self):
                self.text = ""

            def setText(self, value):
                self.text = value

        fake_clipboard = _FakeClipboard()
        monkeypatch.setattr(
            video_editor_window,
            "QApplication",
            SimpleNamespace(clipboard=lambda: fake_clipboard),
        )
        out = tmp_path / "demo.mp4"
        dummy = SimpleNamespace(
            _project_settings={
                "starter_template_id": "screen-recording-demo",
                "canvas_width": 1920,
                "canvas_height": 1080,
                "fps": 60.0,
                "screenstudio_polish": screenstudio_starter_defaults("screen-recording-demo"),
            }
        )
        dummy._screenstudio_write_local_share_package = (
            lambda output_path, defaults: VideoEditorWindow._screenstudio_write_local_share_package(
                dummy, output_path, defaults
            )
        )
        out.write_bytes(b"fake export bytes")

        note = VideoEditorWindow._screenstudio_post_export_handoff_note(dummy, out)
        manifest = out.with_name(out.name + ".share.json")
        payload = json.loads(manifest.read_text(encoding="utf-8"))

        assert fake_clipboard.text == str(out)
        assert "copied to clipboard" in note
        assert "Local share package ready" in note
        assert str(manifest) in note
        assert payload["kind"] == "screenstudio_local_share_package"
        assert payload["file_name"] == out.name
        assert payload["intent_id"] == "web_demo"
        assert payload["clipboard_ready"] is True
        assert payload["share_package_ready"] is True

    def test_export_completion_summary_reports_actions_and_manifest(self, tmp_path):
        out = tmp_path / "demo.mp4"
        out.write_bytes(b"fake export bytes")
        defaults = screenstudio_default_export_settings(
            {
                "starter_template_id": "screen-recording-demo",
                "canvas_width": 1920,
                "canvas_height": 1080,
                "fps": 60.0,
                "screenstudio_polish": screenstudio_starter_defaults("screen-recording-demo"),
            }
        )
        manifest = screenstudio_write_local_share_manifest(out, defaults)

        summary = screenstudio_export_completion_summary(out, defaults, notes=["ready"])

        assert manifest == screenstudio_share_manifest_path(out)
        assert summary["status"] == "ready"
        assert summary["output_exists"] is True
        assert summary["share_manifest_exists"] is True
        assert summary["file_name"] == "demo.mp4"
        assert summary["size_bytes"] > 0
        assert "Reveal output" in summary["action_labels"]
        assert "Copy path" in summary["action_labels"]
        assert "Local share manifest" in summary["action_labels"]
        assert summary["handoff_label"] == "clipboard + local share"
        assert summary["notes"] == ["ready"]

    def test_screenstudio_share_provider_builds_manifest_and_completion_link(self, tmp_path):
        out = tmp_path / "demo.mp4"
        out.write_bytes(b"fake export bytes")
        defaults = screenstudio_default_export_settings(
            {
                "starter_template_id": "screen-recording-demo",
                "canvas_width": 1920,
                "canvas_height": 1080,
                "fps": 60.0,
                "screenstudio_share_provider": "workspace-share",
                "screenstudio_share_base_url": "https://share.example.test/s",
            }
        )

        manifest = screenstudio_write_local_share_manifest(out, defaults)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        share = screenstudio_build_share_link(out, defaults)
        completion = screenstudio_export_completion_summary(out, defaults)

        assert defaults["share_link_ready"] is True
        assert defaults["share_provider"] == "workspace-share"
        assert "copy_share_link" in defaults["post_export_actions"]
        assert share["ok"] is True
        assert share["share_url"].startswith("https://share.example.test/s/")
        assert payload["share_url"] == share["share_url"]
        assert payload["share_provider"] == "workspace-share"
        assert completion["share_url"] == share["share_url"]
        assert completion["handoff_label"] == "share link"
        assert "Share link" in completion["action_labels"]

    def test_manual_zoom_edit_policy_snaps_and_clamps_actor(self):
        actor = ZoomActor(
            id=7,
            start_ms=1000,
            end_ms=3000,
            target_x=100,
            target_y=100,
            target_w=800,
            target_h=450,
        )

        moved = screenstudio_apply_manual_zoom_edit(
            actor,
            "move",
            delta_ms=88,
            duration_ms=6000,
            snap_targets=[1100, 6000],
        )
        assert moved["ok"] is True
        assert actor.start_ms == 1100
        assert actor.end_ms == 3100

        resized = screenstudio_apply_manual_zoom_edit(
            actor,
            "resize_r",
            delta_ms=-5000,
            duration_ms=6000,
            orig_start_ms=actor.start_ms,
            orig_end_ms=actor.end_ms,
        )
        assert resized["ok"] is True
        assert actor.end_ms - actor.start_ms >= 520

        faded = screenstudio_apply_manual_zoom_edit(actor, "fade_in", value_ms=9999, duration_ms=6000)
        assert faded["ok"] is True
        assert actor.zoom_in_ms + actor.zoom_out_ms <= actor.end_ms - actor.start_ms

        target = screenstudio_apply_manual_zoom_edit(
            actor,
            "target_rect",
            target_rect=(-120, -40, 3000, 1600),
            frame_w=1920,
            frame_h=1080,
        )
        assert target["ok"] is True
        assert actor.target_x == 0
        assert actor.target_y == 0
        assert actor.target_x + actor.target_w <= 1920
        assert actor.target_y + actor.target_h <= 1080

        report = screenstudio_manual_zoom_editor_report()
        assert report["ok"] is True
        assert report["score"] == 100

    def test_default_export_result_readiness_requires_polished_cursor_metadata(self):
        settings = {
            "starter_template_id": "screen-recording-demo",
            "canvas_width": 1920,
            "canvas_height": 1080,
            "fps": 60.0,
            "screenstudio_polish": screenstudio_starter_defaults("screen-recording-demo"),
        }
        ready = screenstudio_default_export_result_readiness(
            settings,
            cursor_metadata_count=1,
            polished_clip_count=1,
            auto_zoom_count=2,
        )
        missing_zoom = screenstudio_default_export_result_readiness(
            settings,
            cursor_metadata_count=1,
            polished_clip_count=0,
            auto_zoom_count=0,
        )

        assert ready["ok"] is True
        assert ready["checks"]["delivery_defaults"] is True
        assert ready["checks"]["frame_style"] is True
        assert ready["checks"]["cursor_fx"] is True
        assert ready["checks"]["handoff"] is True
        assert ready["checks"]["auto_zoom"] is True
        assert missing_zoom["ok"] is False
        assert missing_zoom["checks"]["auto_zoom"] is False

    def test_simple_mode_profile_hides_advanced_surfaces_for_screen_recording(self):
        profile = screenstudio_simple_mode_profile(
            {
                "starter_template_id": "screen-recording-demo",
                "screenstudio_polish": screenstudio_starter_defaults("screen-recording-demo"),
            }
        )
        full = screenstudio_simple_mode_profile({"starter_template_id": "blank", "screenstudio_simple_mode": False})

        assert profile["enabled"] is True
        assert profile["score"] == 100
        assert "preview" in profile["primary_surfaces"]
        assert "workbench" in profile["hidden_by_default"]
        assert profile["recommended_layout"] == "simple_screen_studio"
        assert full["enabled"] is False
        assert full["hidden_by_default"] == []

    def test_default_result_beauty_score_gates_no_tuning_screen_recording(self):
        settings = {
            "starter_template_id": "screen-recording-demo",
            "canvas_width": 1920,
            "canvas_height": 1080,
            "fps": 60.0,
            "screenstudio_polish": screenstudio_starter_defaults("screen-recording-demo"),
        }
        ready = screenstudio_default_result_beauty_score(
            settings,
            cursor_metadata_count=1,
            polished_clip_count=1,
            auto_zoom_count=2,
        )
        missing_zoom = screenstudio_default_result_beauty_score(
            settings,
            cursor_metadata_count=1,
            polished_clip_count=0,
            auto_zoom_count=0,
        )
        full_quality = screenstudio_default_result_beauty_score(
            {
                **settings,
                "screenstudio_audio_defaults_ready": True,
                "screenstudio_golden_video_ready": True,
            },
            cursor_metadata_count=1,
            polished_clip_count=1,
            auto_zoom_count=2,
        )

        assert ready["ok"] is True
        assert ready["score"] >= ready["threshold"]
        assert ready["checks"]["simple_mode"] is True
        assert ready["checks"]["motion_defaults"] is True
        assert ready["checks"]["audio_defaults"] is True
        assert ready["checks"]["golden_video"] is False
        assert ready["score"] == 97
        assert missing_zoom["ok"] is False
        assert "auto_zoom" in missing_zoom["failed"]
        assert full_quality["score"] == 100

    def test_screenstudio_audio_defaults_follow_starter_intent(self):
        default_audio = screenstudio_audio_defaults("screen-recording-demo")
        actor_audio = screenstudio_audio_defaults("actor-showcase")
        export = screenstudio_default_export_settings(
            {
                "starter_template_id": "screen-recording-demo",
                "canvas_width": 1920,
                "canvas_height": 1080,
                "fps": 60.0,
                "screenstudio_polish": screenstudio_starter_defaults("screen-recording-demo"),
            }
        )

        assert default_audio["enabled"] is True
        assert default_audio["voice_normalize"] is True
        assert default_audio["noise_cleanup"] is True
        assert default_audio["loudness_target_id"] == "shortform"
        assert actor_audio["loudness_target_id"] == "podcast"
        assert export["audio_defaults_ready"] is True

    def test_default_golden_video_probe_validates_visible_polish_path(self):
        probe = screenstudio_default_golden_video_probe(
            {
                "starter_template_id": "screen-recording-demo",
                "screenstudio_polish": screenstudio_starter_defaults("screen-recording-demo"),
            }
        )

        assert probe["ok"] is True
        assert probe["checks"]["frame_style_visible"] is True
        assert probe["checks"]["cursor_click_visible"] is True
        assert probe["checks"]["auto_zoom_planned"] is True
        assert probe["checks"]["parity_ok"] is True
        assert probe["frame_style_delta"] > 0
        assert probe["cursor_click_delta"] > 0

    def test_apply_polish_replaces_previous_auto_zoom_ids(self):
        clip = _make_clip(source_out_ms=6000, source_duration_ms=6000)
        first = apply_screenstudio_polish_to_clip(clip, cursor_events=[CursorEvent(1500, 0.6, 0.4, "click")])
        first_start = clip.zoom_actors[0].start_ms
        second = apply_screenstudio_polish_to_clip(clip, cursor_events=[CursorEvent(2500, 0.3, 0.5, "click")])
        assert first > 0
        assert second > 0
        assert len(clip.zoom_actors) == second
        assert clip.zoom_actors[0].start_ms != first_start
        assert len(clip.screenstudio_polish.get("auto_zoom_actor_ids", [])) == second

    def test_cursor_fx_draws_pixels_from_metadata(self):
        rgb = np.zeros((80, 120, 3), dtype=np.uint8)
        owner = SimpleNamespace(
            cursor_events=[
                {"t_ms": 0, "x_norm": 0.50, "y_norm": 0.40, "kind": "move"},
                {"t_ms": 120, "x_norm": 0.52, "y_norm": 0.42, "kind": "click"},
            ],
            screenstudio_polish={},
        )

        out = apply_cursor_fx_rgb(rgb, 140, owner=owner)

        assert out.shape == rgb.shape
        assert int(out.sum()) > 0

    def test_cursor_fx_lazy_loads_sidecar_for_video_frames(self, tmp_path):
        video = tmp_path / "capture.mp4"
        video.write_bytes(b"fake")
        sidecar = tmp_path / "capture.mp4.cursor.json"
        sidecar.write_text(
            json.dumps(
                {
                    "events": [
                        {"t_ms": 100, "x_norm": 0.50, "y_norm": 0.50, "kind": "click"},
                        {"t_ms": 620, "x_norm": 0.60, "y_norm": 0.55, "kind": "release"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        rgb = np.zeros((96, 128, 3), dtype=np.uint8)
        owner = SimpleNamespace(source_path=video, cursor_events=[], screenstudio_polish={})

        assert screenstudio_fx_enabled(owner)
        out = apply_cursor_fx_rgb(rgb, 100, owner=owner)

        assert int(out.sum()) > 0
        assert owner.cursor_events

    def test_screen_frame_style_only_when_polish_payload_exists(self):
        rgb = np.full((90, 160, 3), 80, dtype=np.uint8)
        cursor_only = SimpleNamespace(
            cursor_events=[{"t_ms": 0, "x_norm": 0.5, "y_norm": 0.5}],
            screenstudio_polish={},
        )
        unchanged = apply_screen_frame_style_rgb(rgb, owner=cursor_only)
        np.testing.assert_array_equal(unchanged, rgb)

        polished = SimpleNamespace(
            cursor_events=[],
            screenstudio_polish={"screen": {"padding": 0.12, "shadow": 0.5}},
        )
        styled = apply_screen_frame_style_rgb(rgb, owner=polished)

        assert styled.shape == rgb.shape
        assert not np.array_equal(styled, rgb)

    def test_screenstudio_preset_payload_is_complete(self):
        payload = normalize_screenstudio_polish(
            {"preset_id": "cursor_focus", "cursor": {"cursor_scale": 1.8}}
        )

        assert payload["preset_id"] == "cursor_focus"
        assert payload["cursor"]["cursor_scale"] == 1.8
        assert payload["cursor"]["click_ring_ms"] > 0
        assert payload["cursor"]["click_hold_ms"] > 0
        assert payload["screen"]["background"] == "cursor-focus"
        assert payload["screen"]["zoom_scale"] > 1.0

    def test_apply_polish_uses_custom_zoom_controls(self):
        clip = _make_clip(source_out_ms=6000, source_duration_ms=6000)
        added = apply_screenstudio_polish_to_clip(
            clip,
            cursor_events=[CursorEvent(3000, 0.5, 0.5, "click")],
            screen_polish={"zoom_scale": 1.25, "zoom_duration_ms": 900},
            cursor_polish={"hide_static_after_ms": 250},
            preset_id="product_demo",
        )

        assert added == 1
        actor = clip.zoom_actors[0]
        assert actor.end_ms - actor.start_ms == 900
        assert actor.target_w > 0
        assert clip.screenstudio_polish["preset_id"] == "product_demo"
        assert clip.screenstudio_polish["cursor"]["hide_static_after_ms"] == 250
        assert clip.screenstudio_polish["screen"]["zoom_scale"] == 1.25

    def test_auto_zoom_candidates_can_be_disabled(self):
        events = [
            CursorEvent(900, 0.25, 0.35, "click"),
            CursorEvent(3600, 0.70, 0.48, "release"),
            CursorEvent(6500, 0.42, 0.52, "hotkey", True, "Ctrl + S"),
        ]
        all_actors = plan_auto_zoom_actors(duration_ms=9000, cursor_events=events)
        reduced = plan_auto_zoom_actors(
            duration_ms=9000,
            cursor_events=events,
            disabled_point_indexes=[1],
        )
        clip = _make_clip(source_out_ms=9000, source_duration_ms=9000)
        added = apply_screenstudio_polish_to_clip(
            clip,
            cursor_events=events,
            disabled_zoom_candidate_indexes=[1],
        )

        assert len(all_actors) >= 2
        assert len(reduced) == len(all_actors) - 1
        assert added == len(reduced)
        assert {getattr(actor, "screenstudio_point_index", -1) for actor in reduced} == {0, 2}

    def test_auto_zoom_candidates_can_be_directly_overridden(self):
        events = [
            CursorEvent(1600, 0.45, 0.35, "click"),
            CursorEvent(4400, 0.70, 0.60, "release"),
        ]
        overrides = {
            0: {
                "start_ms": 500,
                "end_ms": 1500,
                "target_x": 20,
                "target_y": 30,
                "target_w": 320,
                "target_h": 180,
            }
        }
        actors = plan_auto_zoom_actors(
            duration_ms=6000,
            frame_w=1280,
            frame_h=720,
            cursor_events=events,
            candidate_overrides=overrides,
        )
        report = screenstudio_interaction_report(
            events,
            duration_ms=6000,
            frame_w=1280,
            frame_h=720,
            include_parity=False,
            zoom_candidate_overrides=overrides,
        )
        clip = _make_clip(source_out_ms=6000, source_duration_ms=6000)
        added = apply_screenstudio_polish_to_clip(
            clip,
            frame_w=1280,
            frame_h=720,
            cursor_events=events,
            zoom_candidate_overrides=overrides,
        )

        assert actors
        assert actors[0].start_ms == 500
        assert actors[0].end_ms == 1500
        assert actors[0].target_x == 20
        assert actors[0].target_y == 30
        assert actors[0].target_w == 320
        assert actors[0].target_h == 180
        assert report["zoom_candidates"][0]["frame_w"] == 1280
        assert report["zoom_candidates"][0]["target_w"] == 320
        assert added >= 1
        assert clip.zoom_actors[0].target_w == 320

    def test_screenstudio_zoom_style_controls_easing_and_blur(self):
        actor = ZoomActor(
            id=1,
            start_ms=1000,
            end_ms=3000,
            target_x=250,
            target_y=120,
            target_w=500,
            target_h=320,
            zoom_in_ms=500,
            zoom_out_ms=500,
            easing="smooth_pop",
            motion_blur=0.24,
        )
        smooth_mid = zoom_ease_value(0.5, "smooth_pop")
        linear_mid = zoom_ease_value(0.5, "linear")
        window = zoom_window_at(actor, 1250, 1000, 640)

        assert smooth_mid > linear_mid
        assert window is not None
        assert window[2] < 750
        assert zoom_motion_blur_amount(actor, 1250) > 0.0
        assert zoom_motion_blur_amount(actor, 2000) == 0.0

    def test_screenstudio_presets_stamp_zoom_style_on_generated_actors(self):
        clip = _make_clip(source_out_ms=6000, source_duration_ms=6000)
        added = apply_screenstudio_polish_to_clip(
            clip,
            frame_w=1280,
            frame_h=720,
            cursor_events=[CursorEvent(2200, 0.7, 0.4, "click")],
            screen_polish={
                "zoom_scale": 1.55,
                "zoom_duration_ms": 1400,
                "zoom_easing": "cinematic",
                "zoom_motion_blur": 0.32,
                "zoom_focus_bias": 0.30,
            },
        )
        report = screenstudio_interaction_report(
            [CursorEvent(2200, 0.7, 0.4, "click")],
            duration_ms=6000,
            frame_w=1280,
            frame_h=720,
            include_parity=False,
            project_settings={
                "screenstudio_polish": {
                    "screen": {
                        "zoom_easing": "cinematic",
                        "zoom_motion_blur": 0.32,
                        "zoom_focus_bias": 0.30,
                    }
                }
            },
        )

        assert added == 1
        assert clip.zoom_actors[0].easing == "cinematic"
        assert clip.zoom_actors[0].motion_blur == pytest.approx(0.32)
        assert report["zoom_candidates"][0]["easing"] == "cinematic"
        assert report["zoom_candidates"][0]["motion_blur"] == pytest.approx(0.32)

    def test_screen_frame_background_palette_changes_output(self):
        rgb = np.full((72, 128, 3), 96, dtype=np.uint8)
        base = screenstudio_polish_preset("clean_tutorial")
        warm = screenstudio_polish_preset("product_demo")

        clean_out = apply_screen_frame_style_rgb(rgb, project_settings={"screenstudio_polish": base})
        warm_out = apply_screen_frame_style_rgb(rgb, project_settings={"screenstudio_polish": warm})

        assert clean_out.shape == rgb.shape
        assert warm_out.shape == rgb.shape
        assert not np.array_equal(clean_out, warm_out)

    def test_cursor_state_tracks_drag_release_and_key_events(self):
        events = [
            CursorEvent(0, 0.20, 0.40, "click"),
            CursorEvent(120, 0.35, 0.45, "drag"),
            CursorEvent(220, 0.50, 0.50, "drag"),
            CursorEvent(280, 0.52, 0.52, "hotkey", True, "Ctrl + K"),
            CursorEvent(360, 0.55, 0.54, "release"),
        ]

        drag_state = cursor_state_at(events, 260, drag_trail_ms=500)
        key_state = cursor_state_at(events, 300, drag_trail_ms=500)
        release_state = cursor_state_at(events, 380, click_ring_ms=500)

        assert drag_state is not None
        assert len(drag_state["trail"]) >= 2
        assert key_state is not None
        assert key_state["key"] is not None
        assert key_state["key"]["label"] == "Ctrl + K"
        assert events[3].to_dict()["label"] == "Ctrl + K"
        assert release_state is not None
        assert release_state["click"]["kind"] == "release"

    def test_cursor_click_fx_draws_prominent_frame_marker(self):
        rgb = np.full((180, 320, 3), 24, dtype=np.uint8)
        owner = SimpleNamespace(
            cursor_events=[
                {"t_ms": 100, "x_norm": 0.50, "y_norm": 0.50, "kind": "click"},
            ],
            screenstudio_polish={
                "cursor": {
                    "click_ring_color": "#FF7A59",
                    "cursor_focus_glow": 0.28,
                    "click_ring_strength": 1.35,
                }
            },
        )

        out = apply_cursor_fx_rgb(rgb, 180, owner=owner)

        assert out.shape == rgb.shape
        assert not np.array_equal(out, rgb)
        center = out[74:106, 144:176].astype(np.int16)
        corner = out[0:32, 0:32].astype(np.int16)
        assert float(center.mean()) - float(corner.mean()) > 18.0

    def test_cursor_click_fx_uses_preset_accent_color(self):
        rgb = np.full((180, 320, 3), 26, dtype=np.uint8)
        owner = SimpleNamespace(
            cursor_events=[
                {"t_ms": 100, "x_norm": 0.50, "y_norm": 0.50, "kind": "click"},
            ],
            screenstudio_polish={
                "cursor": {
                    "click_ring_color": "#4BD9D9",
                    "cursor_focus_glow": 0.30,
                    "click_ring_strength": 1.45,
                    "cursor_scale": 1.6,
                }
            },
        )

        out = apply_cursor_fx_rgb(rgb, 130, owner=owner)

        center = out[68:112, 138:182].astype(np.float32)
        assert float(center[:, :, 1].mean()) > float(center[:, :, 0].mean()) + 18.0
        assert float(center[:, :, 2].mean()) > float(center[:, :, 0].mean()) + 18.0

    def test_hotkey_formatter_ignores_plain_text_and_keeps_tutorial_chords(self):
        assert _hotkey_label_from_pressed({0x43}) == ""
        assert _hotkey_label_from_pressed({0x11, 0x43}) == "Ctrl + C"
        assert _hotkey_label_from_pressed({0x10, 0x70}) == "Shift + F1"
        assert _hotkey_label_from_pressed({0x74}) == "F5"

    def test_auto_zoom_edge_framing_expands_crop(self):
        actors = plan_auto_zoom_actors(
            duration_ms=3000,
            frame_w=1000,
            frame_h=500,
            cursor_events=[CursorEvent(1200, 0.02, 0.50, "click")],
            zoom_scale=2.0,
        )

        assert actors
        actor = actors[0]
        assert actor.target_x == 0
        assert actor.target_w > 500

    def test_screen_frame_corner_radius_changes_output(self):
        rgb = np.full((90, 160, 3), 110, dtype=np.uint8)
        square = {"screen": {"padding": 0.10, "shadow": 0.0, "corner_radius": 0.0}}
        rounded = {"screen": {"padding": 0.10, "shadow": 0.0, "corner_radius": 0.10}}

        square_out = apply_screen_frame_style_rgb(rgb, project_settings={"screenstudio_polish": square})
        rounded_out = apply_screen_frame_style_rgb(rgb, project_settings={"screenstudio_polish": rounded})

        assert square_out.shape == rounded_out.shape
        assert not np.array_equal(square_out, rounded_out)

    def test_screenstudio_parity_report_matches_preview_export(self):
        owner = SimpleNamespace(
            cursor_events=[
                {"t_ms": 0, "x_norm": 0.2, "y_norm": 0.3, "kind": "click"},
                {"t_ms": 180, "x_norm": 0.5, "y_norm": 0.5, "kind": "drag"},
                {"t_ms": 420, "x_norm": 0.7, "y_norm": 0.4, "kind": "release"},
            ],
            screenstudio_polish=screenstudio_polish_preset("cursor_focus"),
        )

        report = screenstudio_polish_parity_report(owner=owner, frame_size=(96, 54))

        assert report["ok"]
        assert report["requires_prerender"]
        assert all(sample["match"] for sample in report["samples"])

    def test_screenstudio_interaction_report_summarizes_capture_readiness(self):
        report = screenstudio_interaction_report(
            [
                {"t_ms": 0, "x_norm": 0.2, "y_norm": 0.3, "kind": "click"},
                {"t_ms": 180, "x_norm": 0.5, "y_norm": 0.5, "kind": "drag"},
                {"t_ms": 420, "x_norm": 0.7, "y_norm": 0.4, "kind": "release"},
                {"t_ms": 520, "x_norm": 0.7, "y_norm": 0.4, "kind": "hotkey", "label": "Ctrl + S"},
            ],
            duration_ms=1600,
            frame_w=1280,
            frame_h=720,
        )

        assert report["ok"]
        assert report["counts"]["hotkey"] == 1
        assert report["hotkey_labels"] == ["Ctrl + S"]
        assert report["auto_zoom_count"] >= 1
        assert report["zoom_candidates"]
        assert report["zoom_candidates"][0]["enabled"] is True
        assert report["zoom_timing_profile"]["max_actors"] >= 1
        assert report["parity_ok"]

        disabled = screenstudio_interaction_report(
            [
                {"t_ms": 900, "x_norm": 0.2, "y_norm": 0.3, "kind": "click"},
                {"t_ms": 3600, "x_norm": 0.7, "y_norm": 0.4, "kind": "release"},
                {"t_ms": 6500, "x_norm": 0.6, "y_norm": 0.6, "kind": "hotkey", "label": "Ctrl + S"},
            ],
            duration_ms=9000,
            include_parity=False,
            disabled_zoom_candidate_indexes=[0],
        )
        assert disabled["zoom_candidates"][0]["enabled"] is False
        assert disabled["auto_zoom_count"] < len(disabled["zoom_candidates"])

    def test_interaction_report_exposes_long_recording_zoom_timing(self):
        events = [
            {"t_ms": 1000, "x_norm": 0.16, "y_norm": 0.28, "kind": "click"},
            {"t_ms": 2400, "x_norm": 0.20, "y_norm": 0.30, "kind": "release"},
            {"t_ms": 4500, "x_norm": 0.24, "y_norm": 0.34, "kind": "click"},
            {"t_ms": 18_000, "x_norm": 0.62, "y_norm": 0.42, "kind": "hotkey", "label": "Ctrl + K"},
            {"t_ms": 32_000, "x_norm": 0.74, "y_norm": 0.50, "kind": "click"},
            {"t_ms": 48_000, "x_norm": 0.42, "y_norm": 0.60, "kind": "drag"},
            {"t_ms": 65_000, "x_norm": 0.35, "y_norm": 0.52, "kind": "release"},
            {"t_ms": 82_000, "x_norm": 0.68, "y_norm": 0.34, "kind": "click"},
        ]

        report = screenstudio_interaction_report(
            events,
            duration_ms=90_000,
            frame_w=1920,
            frame_h=1080,
            include_parity=False,
        )

        assert report["zoom_timing_profile"]["max_actors"] >= 6
        assert report["zoom_timing_profile"]["rhythm_gap_ms"] >= 5000
        assert report["auto_zoom_count"] >= 6

    def test_screenstudio_sidecar_report_reads_media_sidecar(self, tmp_path):
        video = tmp_path / "capture.mp4"
        video.write_bytes(b"fake")
        sidecar = tmp_path / "capture.mp4.cursor.json"
        sidecar.write_text(
            json.dumps(
                {
                    "events": [
                        {"t_ms": 0, "x_norm": 0.2, "y_norm": 0.3, "kind": "click"},
                        {"t_ms": 120, "x_norm": 0.4, "y_norm": 0.5, "kind": "drag"},
                        {"t_ms": 260, "x_norm": 0.5, "y_norm": 0.5, "kind": "release"},
                        {"t_ms": 420, "x_norm": 0.5, "y_norm": 0.5, "kind": "hotkey", "label": "Ctrl + S"},
                    ]
                }
            ),
            encoding="utf-8",
        )

        report = screenstudio_sidecar_report(video, duration_ms=1200, include_parity=False)
        missing = screenstudio_sidecar_report(tmp_path / "missing.mp4", duration_ms=1200)

        assert report["ok"]
        assert report["parity_checked"] is False
        assert report["counts"]["hotkey"] == 1
        assert report["hotkey_labels"] == ["Ctrl + S"]
        assert missing["warnings"] == ["missing_cursor_sidecar"]


# ---------------------------------------------------------------------------
#  Track edit operations
# ---------------------------------------------------------------------------


class TestTrackSplit:
    def test_split_preserves_total_duration(self):
        clip = _make_clip(source_out_ms=10_000, source_duration_ms=10_000)
        track = VideoTrack(id=0, clips=[clip])
        before = clip.effective_length_ms

        left, right = track.split_at(4000)

        assert len(track.clips) == 2
        assert left.effective_length_ms + right.effective_length_ms == before

    def test_split_at_correct_source_ms(self):
        clip = _make_clip(source_in_ms=1000, source_out_ms=9000,
                          source_duration_ms=10_000)
        track = VideoTrack(id=0, clips=[clip])
        # Project time 3000 → source ms 1000 + (3000 - 0) = 4000
        left, right = track.split_at(3000)

        assert left.source_in_ms == 1000
        assert left.source_out_ms == 4000
        assert right.source_in_ms == 4000
        assert right.source_out_ms == 9000
        assert right.timeline_in_ms == 3000

    def test_split_partitions_actors_by_time(self):
        clip = _make_clip(source_out_ms=10_000, source_duration_ms=10_000)
        clip.fades = [
            FadeSegment(start_ms=500, end_ms=1500, kind="in"),
            FadeSegment(start_ms=8000, end_ms=9000, kind="out"),
        ]
        clip.zoom_actors = [
            ZoomActor(id=1, start_ms=200, end_ms=800,
                      target_x=0, target_y=0, target_w=100, target_h=100),
            ZoomActor(id=2, start_ms=6000, end_ms=7000,
                      target_x=0, target_y=0, target_w=100, target_h=100),
        ]
        track = VideoTrack(id=0, clips=[clip])

        left, right = track.split_at(5000)

        assert len(left.fades) == 1
        assert left.fades[0].kind == "in"
        assert len(right.fades) == 1
        assert right.fades[0].kind == "out"
        assert len(left.zoom_actors) == 1
        assert left.zoom_actors[0].id == 1
        assert len(right.zoom_actors) == 1
        assert right.zoom_actors[0].id == 2

    def test_split_copies_node_graph_independently(self):
        clip = _make_clip()
        track = VideoTrack(id=0, clips=[clip])

        left, right = track.split_at(5000)

        # Mutate the right half's grade — the left half must not change.
        right.node_graph.color.grade.brightness = 50
        assert left.node_graph.color.grade.brightness == 0

    def test_split_outside_clip_raises(self):
        clip = _make_clip(timeline_in_ms=2000, source_out_ms=3000,
                          source_duration_ms=3000)
        track = VideoTrack(id=0, clips=[clip])
        # Window is [2000, 5000); 1000 and 5000 are outside.
        with pytest.raises(ValueError):
            track.split_at(1000)
        with pytest.raises(ValueError):
            track.split_at(5000)
        # Boundary points are also rejected (no zero-length halves).
        with pytest.raises(ValueError):
            track.split_at(2000)


class TestTrackTrim:
    def test_trim_left_clamps_at_zero(self):
        clip = _make_clip(source_in_ms=200, source_out_ms=5000,
                          source_duration_ms=10_000, timeline_in_ms=1000)
        track = VideoTrack(id=0, clips=[clip])

        track.trim_left(clip, -500)  # would push below 0

        assert clip.source_in_ms == 0
        # Project-timeline left edge moved by the actual delta (-200).
        assert clip.timeline_in_ms == 800

    def test_trim_left_keeps_right_edge(self):
        clip = _make_clip(source_in_ms=0, source_out_ms=5000,
                          source_duration_ms=10_000, timeline_in_ms=1000)
        track = VideoTrack(id=0, clips=[clip])
        right_before = clip.timeline_out_ms

        track.trim_left(clip, 1000)  # in-point moves later by 1s

        assert clip.source_in_ms == 1000
        assert clip.timeline_out_ms == right_before  # right edge unchanged

    def test_trim_right_clamps_to_source_duration(self):
        clip = _make_clip(source_in_ms=0, source_out_ms=8000,
                          source_duration_ms=10_000)
        track = VideoTrack(id=0, clips=[clip])

        track.trim_right(clip, 5000)  # would push past 10_000

        assert clip.effective_source_out_ms == 10_000

    def test_trim_right_cannot_invert(self):
        clip = _make_clip(source_in_ms=4000, source_out_ms=5000,
                          source_duration_ms=10_000)
        track = VideoTrack(id=0, clips=[clip])

        track.trim_right(clip, -10_000)

        assert clip.effective_source_out_ms > clip.source_in_ms


class TestTrackMove:
    def test_move_clip_rejects_overlap(self):
        a = _make_clip(timeline_in_ms=0, source_out_ms=5000,
                       source_duration_ms=5000)
        b = _make_clip(timeline_in_ms=5000, source_out_ms=5000,
                       source_duration_ms=5000)
        track = VideoTrack(id=0, clips=[a, b])

        # Try to drop b into a's window.
        ok = track.move_clip(b, 2000)

        assert ok is False
        assert b.timeline_in_ms == 5000  # unchanged

    def test_move_clip_into_gap(self):
        a = _make_clip(timeline_in_ms=0, source_out_ms=2000,
                       source_duration_ms=2000)
        b = _make_clip(timeline_in_ms=10_000, source_out_ms=2000,
                       source_duration_ms=2000)
        track = VideoTrack(id=0, clips=[a, b])

        ok = track.move_clip(b, 5000)

        assert ok is True
        assert b.timeline_in_ms == 5000
        # Track stays sorted after a successful move.
        assert [c.timeline_in_ms for c in track.clips] == [0, 5000]

    def test_move_clip_clamps_to_zero(self):
        clip = _make_clip(timeline_in_ms=2000, source_out_ms=2000,
                          source_duration_ms=2000)
        track = VideoTrack(id=0, clips=[clip])

        track.move_clip(clip, -500)

        assert clip.timeline_in_ms == 0


class TestTrackDelete:
    def test_delete_removes_only_target(self):
        a = _make_clip(timeline_in_ms=0, source_out_ms=2000,
                       source_duration_ms=2000)
        b = _make_clip(timeline_in_ms=2000, source_out_ms=2000,
                       source_duration_ms=2000)
        track = VideoTrack(id=0, clips=[a, b])

        track.delete_clip(a)

        assert track.clips == [b]


# ---------------------------------------------------------------------------
#  Legacy migration
# ---------------------------------------------------------------------------


class TestMigrateLegacy:
    def _src(self) -> Path:
        return Path("/fake/source.mp4")

    def test_empty_track_yields_empty_clips(self):
        legacy = _LegacyTrack(id=0)
        new = migrate_legacy_video_track(legacy)
        assert new.id == 0
        assert new.clips == []

    def test_no_cuts_yields_single_clip(self):
        legacy = _LegacyTrack(
            id=3, source_path=self._src(), duration_ms=8000,
            offset_ms=2000, color_grade=_FakeGrade(),
        )
        new = migrate_legacy_video_track(legacy)
        assert len(new.clips) == 1
        c = new.clips[0]
        assert c.source_path == self._src()
        assert c.source_in_ms == 0
        assert c.source_out_ms == 8000
        assert c.timeline_in_ms == 2000
        assert c.timeline_out_ms == 10_000

    def test_one_cut_in_middle_yields_two_clips(self):
        legacy = _LegacyTrack(
            source_path=self._src(), duration_ms=10_000,
            cuts=[CutSegment(start_ms=3000, end_ms=5000)],
            color_grade=_FakeGrade(),
        )
        new = migrate_legacy_video_track(legacy)
        assert len(new.clips) == 2
        a, b = new.clips
        # First clip: source [0, 3000), project [0, 3000)
        assert (a.source_in_ms, a.source_out_ms) == (0, 3000)
        assert (a.timeline_in_ms, a.timeline_out_ms) == (0, 3000)
        # Second clip: source [5000, 10000), project [3000, 8000)
        assert (b.source_in_ms, b.source_out_ms) == (5000, 10_000)
        assert (b.timeline_in_ms, b.timeline_out_ms) == (3000, 8000)

    def test_cut_at_start_drops_first_range(self):
        legacy = _LegacyTrack(
            source_path=self._src(), duration_ms=10_000,
            cuts=[CutSegment(start_ms=0, end_ms=2000)],
        )
        new = migrate_legacy_video_track(legacy)
        assert len(new.clips) == 1
        c = new.clips[0]
        assert (c.source_in_ms, c.source_out_ms) == (2000, 10_000)
        assert c.timeline_in_ms == 0  # left edge of project is unchanged

    def test_actors_partition_across_cut(self):
        legacy = _LegacyTrack(
            source_path=self._src(), duration_ms=10_000,
            cuts=[CutSegment(start_ms=4000, end_ms=6000)],
            fades=[FadeSegment(start_ms=500, end_ms=1500, kind="in"),
                   FadeSegment(start_ms=8000, end_ms=9000, kind="out")],
        )
        new = migrate_legacy_video_track(legacy)
        a, b = new.clips
        assert [f.kind for f in a.fades] == ["in"]
        assert [f.kind for f in b.fades] == ["out"]

    def test_grade_is_independent_per_clip_after_migration(self):
        legacy = _LegacyTrack(
            source_path=self._src(), duration_ms=10_000,
            cuts=[CutSegment(start_ms=4000, end_ms=6000)],
            color_grade=_FakeGrade(brightness=10),
        )
        new = migrate_legacy_video_track(legacy)
        a, b = new.clips
        b.node_graph.color.grade.brightness = 99
        assert a.node_graph.color.grade.brightness == 10

    def test_does_not_mutate_legacy(self):
        cuts = [CutSegment(start_ms=4000, end_ms=6000)]
        legacy = _LegacyTrack(
            source_path=self._src(), duration_ms=10_000, cuts=cuts,
        )
        migrate_legacy_video_track(legacy)
        # The original legacy fields must be untouched.
        assert legacy.cuts is cuts
        assert legacy.duration_ms == 10_000


# ---------------------------------------------------------------------------
#  Timeline container
# ---------------------------------------------------------------------------


class TestTimeline:
    def test_duration_ignores_empty_lanes(self):
        tl = Timeline(
            video_tracks=[VideoTrack(id=0)],  # empty lane
            audio_tracks=[],
        )
        assert tl.duration_ms == 0

    def test_duration_takes_longest_video_lane(self):
        a = VideoTrack(id=0, clips=[
            _make_clip(timeline_in_ms=0, source_out_ms=2000,
                       source_duration_ms=2000),
        ])
        b = VideoTrack(id=1, clips=[
            _make_clip(timeline_in_ms=0, source_out_ms=5000,
                       source_duration_ms=5000),
        ])
        tl = Timeline(video_tracks=[a, b])
        assert tl.duration_ms == 5000


# ---------------------------------------------------------------------------
#  Phase 1.5b: project_player._build_clips_view byte-equivalence
# ---------------------------------------------------------------------------


@dataclass
class _PPLegacyTrack:
    """Mirror of the project_player input shape (legacy single-source
    VideoTrack). Just the fields ``_build_clips_view`` reads."""

    id: int = 0
    source_path: Path | None = None
    duration_ms: int = 0
    offset_ms: int = 0
    cuts: list = field(default_factory=list)


class TestClipsViewBuilder:
    """Phase 1.5b cache fed to ``_render_frame_at`` must be a
    byte-equivalent re-expression of the legacy track. No ripple-
    delete: cut regions leave **gaps** between clips so the project-
    timeline length doesn't change versus today."""

    def setup_method(self):
        from app.project_player import _build_clips_view
        self._build = _build_clips_view

    def test_no_source_yields_empty(self):
        assert self._build(_PPLegacyTrack(id=0)) == []

    def test_no_cuts_yields_one_clip_at_offset(self):
        t = _PPLegacyTrack(
            id=0, source_path=Path("/x.mp4"),
            duration_ms=8000, offset_ms=2000,
        )
        clips = self._build(t)
        assert len(clips) == 1
        c = clips[0]
        assert c.timeline_in_ms == 2000
        assert c.timeline_out_ms == 10_000
        assert c.source_in_ms == 0
        assert c.source_out_ms == 8000

    def test_cut_in_middle_preserves_gap(self):
        t = _PPLegacyTrack(
            id=1, source_path=Path("/y.mp4"),
            duration_ms=10_000, offset_ms=0,
            cuts=[CutSegment(start_ms=4000, end_ms=6000)],
        )
        clips = self._build(t)
        assert len(clips) == 2
        a, b = clips
        # Project [0, 4000) — first clip, identical to legacy
        assert (a.timeline_in_ms, a.timeline_out_ms) == (0, 4000)
        # GAP at project [4000, 6000) — no clip there. This is the
        # critical invariant: the legacy renderer skipped frames
        # during cuts but the project timeline length stayed at
        # ``duration_ms``; we preserve that, no ripple-delete.
        assert (b.timeline_in_ms, b.timeline_out_ms) == (6000, 10_000)
        assert (b.source_in_ms, b.source_out_ms) == (6000, 10_000)
        # Project ms inside the cut window matches no clip → renderer
        # falls through to whatever underlies, exactly like before.
        for t_ms in (4000, 5000, 5999):
            assert next((c for c in clips if c.contains_timeline_ms(t_ms)), None) is None

    def test_cut_at_start_drops_first_range(self):
        t = _PPLegacyTrack(
            id=0, source_path=Path("/z.mp4"),
            duration_ms=10_000, offset_ms=0,
            cuts=[CutSegment(start_ms=0, end_ms=2000)],
        )
        clips = self._build(t)
        assert len(clips) == 1
        c = clips[0]
        # Source starts at 2000 (we cut [0,2000)); project still 0-based
        # but window opens at 2000 — same as legacy where playhead
        # crossing 0..2000 simply rendered nothing for this track.
        assert c.source_in_ms == 2000
        assert c.timeline_in_ms == 2000

    def test_overlapping_cuts_collapse(self):
        # Two cuts that overlap should produce the same surviving
        # range as one merged cut would.
        t = _PPLegacyTrack(
            id=0, source_path=Path("/q.mp4"), duration_ms=10_000,
            cuts=[
                CutSegment(start_ms=2000, end_ms=5000),
                CutSegment(start_ms=4000, end_ms=7000),  # overlaps
            ],
        )
        clips = self._build(t)
        assert len(clips) == 2
        a, b = clips
        assert (a.timeline_in_ms, a.timeline_out_ms) == (0, 2000)
        assert (b.timeline_in_ms, b.timeline_out_ms) == (7000, 10_000)

    def test_clip_id_stable_across_rebuilds(self):
        """Track ID is encoded into clip IDs so debuggers / log lines
        can correlate. Same track with same content → same clip ids."""
        t = _PPLegacyTrack(
            id=7, source_path=Path("/x.mp4"), duration_ms=4000,
        )
        a = self._build(t)
        b = self._build(t)
        assert [c.id for c in a] == [c.id for c in b]
        # And the encoding is ``track_id * 1000 + index``
        assert a[0].id == 7 * 1000 + 0


# ---------------------------------------------------------------------------
#  Phase 1.5d Step C: cut_clip_window — split a clip on a source window
# ---------------------------------------------------------------------------


class TestCutClipWindow:
    """``cut_clip_window`` is the editor's ``_cut_selection_in_track``
    core, lifted to a pure function so we can drive it without Qt.
    The selection is in track-local source ms and the function returns
    the new ``track.clips`` list."""

    def setup_method(self):
        from app.video_editor_window import cut_clip_window
        self._cut = cut_clip_window

    def _src_clip(
        self, *, source_in_ms=0, source_out_ms=10_000, timeline_in_ms=0,
        clip_id=1, source_duration_ms=10_000,
    ):
        from app.timeline_model import VideoClip
        return VideoClip(
            id=clip_id, source_path=Path("/x.mp4"),
            source_duration_ms=source_duration_ms,
            timeline_in_ms=timeline_in_ms,
            source_in_ms=source_in_ms, source_out_ms=source_out_ms,
        )

    def test_cut_in_middle_of_single_clip_yields_two_halves(self):
        clip = self._src_clip()
        result = self._cut([clip], 4000, 6000, track_offset_ms=0)
        assert len(result) == 2
        a, b = result
        assert (a.source_in_ms, a.source_out_ms) == (0, 4000)
        assert (a.timeline_in_ms, a.timeline_out_ms) == (0, 4000)
        assert (b.source_in_ms, b.source_out_ms) == (6000, 10_000)
        assert (b.timeline_in_ms, b.timeline_out_ms) == (6000, 10_000)

    def test_cut_with_track_offset_shifts_right_half_in_project(self):
        # Track offset 2000 → clip lives at project [2000, 12000).
        # Cut at source [4000, 6000) → right half should sit at
        # project_in = offset + 6000 = 8000, project_out = 12000.
        clip = self._src_clip(timeline_in_ms=2000)
        result = self._cut([clip], 4000, 6000, track_offset_ms=2000)
        assert len(result) == 2
        a, b = result
        assert (a.timeline_in_ms, a.timeline_out_ms) == (2000, 6000)
        assert (b.timeline_in_ms, b.timeline_out_ms) == (8000, 12_000)

    def test_cut_at_clip_start_drops_left_half(self):
        clip = self._src_clip()
        result = self._cut([clip], 0, 2000, track_offset_ms=0)
        assert len(result) == 1
        c = result[0]
        assert (c.source_in_ms, c.source_out_ms) == (2000, 10_000)

    def test_cut_at_clip_end_drops_right_half(self):
        clip = self._src_clip()
        result = self._cut([clip], 8000, 10_000, track_offset_ms=0)
        assert len(result) == 1
        c = result[0]
        assert (c.source_in_ms, c.source_out_ms) == (0, 8000)

    def test_cut_outside_clip_passes_clip_through(self):
        clip = self._src_clip(source_in_ms=4000, source_out_ms=6000)
        # Cut at [0, 1000) is outside the clip's source window
        assert self._cut([clip], 0, 1000, 0) == [clip]
        # Cut at [9000, 10_000) is also outside
        assert self._cut([clip], 9000, 10_000, 0) == [clip]

    def test_cut_engulfing_clip_drops_it(self):
        clip = self._src_clip(source_in_ms=4000, source_out_ms=6000)
        result = self._cut([clip], 3000, 7000, track_offset_ms=0)
        assert result == []

    def test_second_cut_on_already_split_track_partitions_correctly(self):
        # Start with one clip, cut in middle, then cut the right half again.
        clip = self._src_clip()
        first = self._cut([clip], 4000, 6000, track_offset_ms=0)
        assert len(first) == 2
        # Second cut at source [7000, 8000) — only the right half overlaps
        second = self._cut(first, 7000, 8000, track_offset_ms=0)
        assert len(second) == 3
        # First clip unchanged
        assert (second[0].source_in_ms, second[0].source_out_ms) == (0, 4000)
        # Right half got cut into two pieces
        assert (second[1].source_in_ms, second[1].source_out_ms) == (6000, 7000)
        assert (second[2].source_in_ms, second[2].source_out_ms) == (8000, 10_000)

    def test_does_not_mutate_input(self):
        clip = self._src_clip()
        original = [clip]
        self._cut(original, 4000, 6000, 0)
        assert original == [clip]
        # The clip object itself is also unchanged.
        assert (clip.source_in_ms, clip.source_out_ms) == (0, 10_000)

    def test_result_is_sorted_by_timeline_in(self):
        # Two clips, cut spanning both
        c1 = self._src_clip(
            clip_id=1, source_in_ms=0, source_out_ms=4000, timeline_in_ms=0,
        )
        c2 = self._src_clip(
            clip_id=2, source_in_ms=6000, source_out_ms=10_000, timeline_in_ms=6000,
        )
        # Cut at source [2000, 8000) — both clips overlap
        result = self._cut([c1, c2], 2000, 8000, track_offset_ms=0)
        assert all(
            result[i].timeline_in_ms <= result[i + 1].timeline_in_ms
            for i in range(len(result) - 1)
        )


# ---------------------------------------------------------------------------
#  Phase 1.5e: build_segments_from_clips matches build_segments for the
#  legacy single-source-with-cuts shape, and emits the right ranges for
#  user-split clip lists.
# ---------------------------------------------------------------------------


class TestBuildSegmentsFromClips:
    """``build_segments_from_clips`` is the export-time replacement
    for the legacy ``build_segments(duration_ms, cuts, speed_segments)``.
    For a track that came from the legacy single-source path, both
    must produce the same ``(start_ms, end_ms, speed)`` ranges so the
    exported MP4 is byte-equivalent (identical filter graph)."""

    def setup_method(self):
        from app.video_exporter import (
            build_segments,
            build_segments_from_clips,
        )
        self._legacy = build_segments
        self._new = build_segments_from_clips

    def _src_clip(
        self, *, source_in_ms=0, source_out_ms=10_000, timeline_in_ms=0,
        clip_id=1, source_duration_ms=10_000,
    ):
        from app.timeline_model import VideoClip
        return VideoClip(
            id=clip_id, source_path=Path("/x.mp4"),
            source_duration_ms=source_duration_ms,
            timeline_in_ms=timeline_in_ms,
            source_in_ms=source_in_ms, source_out_ms=source_out_ms,
        )

    def test_empty_clips_yields_empty(self):
        assert self._new([], []) == []

    def test_single_clip_no_speed_matches_legacy_no_cuts(self):
        # Legacy: duration=8000, no cuts, no speeds → [(0, 8000, 1.0)]
        # New: one clip [0, 8000] → same.
        legacy = self._legacy(8000, [], [])
        new = self._new([self._src_clip(source_out_ms=8000)], [])
        assert legacy == new

    def test_legacy_cuts_match_clip_view(self):
        from app.timeline_model import (
            CutSegment, build_legacy_clips_view,
        )
        # Legacy track: duration 10_000 with cut [3000, 5000)
        legacy = self._legacy(
            10_000,
            [CutSegment(3000, 5000)],
            [],
        )
        # Build the equivalent clip view from the same legacy data and
        # feed it to the new function — outputs must match.
        @dataclass
        class _T:
            id: int = 0
            source_path: Path | None = Path("/x.mp4")
            duration_ms: int = 10_000
            offset_ms: int = 0
            cuts: list = field(default_factory=lambda: [CutSegment(3000, 5000)])
        clips = build_legacy_clips_view(_T())
        new = self._new(clips, [])
        assert legacy == new

    def test_user_split_clips_emit_their_source_windows(self):
        # Clip 1: source [0, 3000), clip 2: source [5000, 10_000) — i.e.
        # the post-cut shape Phase 1.5d's ``cut_clip_window`` produces.
        c1 = self._src_clip(
            source_in_ms=0, source_out_ms=3000, timeline_in_ms=0,
        )
        c2 = self._src_clip(
            source_in_ms=5000, source_out_ms=10_000, timeline_in_ms=5000,
        )
        new = self._new([c1, c2], [])
        assert new == [(0, 3000, 1.0), (5000, 10_000, 1.0)]

    def test_clips_in_unsorted_input_emitted_in_project_order(self):
        # User dragged clip2 to the LEFT of clip1 — project-time order
        # is now [clip2, clip1] even though the list was built
        # [clip1, clip2]. Output should reflect the drag.
        c1 = self._src_clip(
            clip_id=1, source_in_ms=0, source_out_ms=3000, timeline_in_ms=5000,
        )
        c2 = self._src_clip(
            clip_id=2, source_in_ms=6000, source_out_ms=8000, timeline_in_ms=0,
        )
        new = self._new([c1, c2], [])
        # c2 (later in list, earlier on timeline) plays first.
        assert new == [(6000, 8000, 1.0), (0, 3000, 1.0)]

    def test_speed_segments_apply_to_clip_ranges(self):
        from app.timeline_model import SpeedSegment
        # Clip [0, 8000), speed [3000, 5000) at 2.0x
        c = self._src_clip(source_out_ms=8000)
        new = self._new(
            [c],
            [SpeedSegment(start_ms=3000, end_ms=5000, speed=2.0)],
        )
        # Expect three pieces: normal [0, 3000), fast [3000, 5000),
        # normal [5000, 8000).
        assert new == [
            (0, 3000, 1.0),
            (3000, 5000, 2.0),
            (5000, 8000, 1.0),
        ]


# ---------------------------------------------------------------------------
#  Phase 7: Sony jog/shuttle math helpers
# ---------------------------------------------------------------------------


class TestShuttleSpeedMapping:
    """The shuttle dial maps a -150°..+150° rotation to one of the 6
    Sony PVW-2800 gears in each direction (and a centre dead-zone for
    pause). The mapping is discrete so the wheel snaps audibly to
    each gear instead of producing analog rates."""

    def setup_method(self):
        from app.jog_shuttle import (
            _shuttle_speed_for_angle, _SHUTTLE_RANGE_DEG, _SHUTTLE_STEPS,
        )
        self._fn = _shuttle_speed_for_angle
        self._range = _SHUTTLE_RANGE_DEG
        self._steps = _SHUTTLE_STEPS

    def test_centre_is_pause(self):
        assert self._fn(0) == 0.0

    def test_dead_zone_around_centre(self):
        # ±12.5° (= range / steps / 2 = 150/6/2) is paused so a tiny
        # cursor wobble doesn't kick the deck into motion.
        assert self._fn(5) == 0.0
        assert self._fn(-5) == 0.0
        assert self._fn(12) == 0.0

    def test_first_gear_just_past_dead_zone(self):
        # Dead-zone edge is 12.5° → past it = first Sony gear (±1×).
        assert self._fn(15) == 1.0
        assert self._fn(-15) == -1.0

    def test_top_gear_at_full_swing(self):
        assert self._fn(self._range) == self._steps[-1]
        assert self._fn(-self._range) == -self._steps[-1]

    def test_beyond_range_clamps_to_top_gear(self):
        assert self._fn(200) == self._steps[-1]
        assert self._fn(-1000) == -self._steps[-1]

    def test_each_gear_is_reachable(self):
        # Walk from 0..range and confirm every Sony step appears in the
        # output set (no gear is unreachable due to a math fencepost).
        seen = {self._fn(d) for d in range(0, int(self._range) + 1, 1)}
        for step in self._steps:
            assert step in seen


class TestWrapAngle:
    """Angle deltas wrap into [-180, 180] so a drag that crosses the
    12-o'clock seam doesn't suddenly flip sign."""

    def test_no_wrap_within_range(self):
        from app.jog_shuttle import _wrap_angle
        assert _wrap_angle(0) == 0
        assert _wrap_angle(90) == 90
        assert _wrap_angle(-90) == -90
        assert _wrap_angle(180) == 180

    def test_wraps_above_180(self):
        from app.jog_shuttle import _wrap_angle
        assert _wrap_angle(190) == -170
        assert _wrap_angle(360) == 0

    def test_wraps_below_neg_180(self):
        from app.jog_shuttle import _wrap_angle
        assert _wrap_angle(-190) == 170
        assert _wrap_angle(-360) == 0


# ---------------------------------------------------------------------------
#  HDR Phase 0: ffmpeg-stderr parser
# ---------------------------------------------------------------------------


class TestHDRProbeParser:
    """The HDR detection runs ffmpeg and parses its stderr. We can
    drive the parser directly with sample stream lines so the tests
    never depend on having a real video file or the ffmpeg binary."""

    def setup_method(self):
        from app.hdr_probe import _parse_hdr_from_ffmpeg_text
        self._parse = _parse_hdr_from_ffmpeg_text

    def test_hdr10_smpte2084(self):
        line = (
            "  Stream #0:0(und): Video: hevc (Main 10) (hev1 / 0x31766568), "
            "yuv420p10le(tv, bt2020nc/bt2020/smpte2084), 3840x2160 [SAR 1:1 DAR 16:9], "
            "10000 kb/s, 60 fps, 60 tbr, 90k tbn (default)"
        )
        info = self._parse(line)
        assert info.is_hdr is True
        assert info.transfer == "smpte2084"
        assert info.primaries == "bt2020"
        assert info.matrix == "bt2020nc"
        assert info.pix_fmt == "yuv420p10le"
        assert info.standard_label == "HDR10"

    def test_hlg_arib_std_b67(self):
        line = (
            "  Stream #0:0(und): Video: hevc (Main 10), "
            "yuv420p10le(tv, bt2020nc/bt2020/arib-std-b67), 1920x1080, 30 fps"
        )
        info = self._parse(line)
        assert info.is_hdr is True
        assert info.transfer == "arib-std-b67"
        assert info.standard_label == "HLG"

    def test_sdr_bt709(self):
        line = (
            "  Stream #0:0(und): Video: h264 (High), "
            "yuv420p(tv, bt709, progressive), 1920x1080, 4000 kb/s, 30 fps"
        )
        info = self._parse(line)
        assert info.is_hdr is False
        # bt709-only line has no transfer triple, just a single token —
        # parser leaves transfer empty, label is SDR.
        assert info.standard_label == "SDR"

    def test_bare_pixfmt_no_color_triple(self):
        # Some files (older clips) report only the pixel format without
        # the colour annotation. Detection must default to SDR.
        line = (
            "  Stream #0:0(und): Video: h264, yuv420p, 1280x720, 30 fps"
        )
        info = self._parse(line)
        assert info.is_hdr is False
        assert info.transfer == ""
        assert info.pix_fmt == "yuv420p"

    def test_no_video_stream_at_all(self):
        info = self._parse("only audio metadata here\nStream #0:0: Audio: aac")
        assert info.is_hdr is False
        assert info.raw_line == ""


# ---------------------------------------------------------------------------
#  Phase 5 Step A: SubtitleLayer / TypographyLayer base behaviour
# ---------------------------------------------------------------------------


@dataclass
class _Range:
    """Generic time-range item for testing ``_OverlayLayer``. Both
    ``Subtitle`` and ``TextClip`` share this duck-typed shape."""

    start_ms: int
    end_ms: int
    text: str = ""


class TestOverlayLayer:
    def setup_method(self):
        from app.overlay_layer import SubtitleLayer
        self._cls = SubtitleLayer

    def test_empty_layer(self):
        layer = self._cls()
        assert len(layer) == 0
        assert layer.items() == []
        assert layer.active_at(0) == []
        assert layer.first_active_at(0) is None

    def test_active_at_includes_start_excludes_end(self):
        layer = self._cls([_Range(1000, 3000, "a")])
        # half-open [start, end): 1000 in, 3000 out
        assert layer.first_active_at(999) is None
        assert layer.first_active_at(1000) is not None
        assert layer.first_active_at(2999) is not None
        assert layer.first_active_at(3000) is None

    def test_multiple_active_overlapping(self):
        a = _Range(0, 5000, "main")
        b = _Range(2000, 4000, "translation")
        layer = self._cls([a, b])
        assert layer.active_at(3000) == [a, b]
        assert layer.active_at(4500) == [a]
        assert layer.active_at(0) == [a]

    def test_add_keeps_layer_sorted(self):
        layer = self._cls()
        layer.add(_Range(5000, 7000, "later"))
        layer.add(_Range(1000, 3000, "earlier"))
        items = layer.items()
        assert [it.start_ms for it in items] == [1000, 5000]

    def test_remove_drops_match_only(self):
        a = _Range(0, 1000, "a")
        b = _Range(2000, 3000, "b")
        layer = self._cls([a, b])
        assert layer.remove(a) is True
        assert layer.items() == [b]
        # Removing again is a no-op (returns False) — not a crash.
        assert layer.remove(a) is False

    def test_replace_at_resorts(self):
        layer = self._cls([
            _Range(0, 1000, "a"),
            _Range(2000, 3000, "b"),
        ])
        # Replace the first one with something that should now sort last.
        layer.replace_at(0, _Range(5000, 6000, "moved"))
        items = layer.items()
        assert [it.text for it in items] == ["b", "moved"]

    def test_clear_empties_layer(self):
        layer = self._cls([_Range(0, 1000)])
        layer.clear()
        assert len(layer) == 0

    def test_replace_all_bulk_loads(self):
        layer = self._cls([_Range(0, 1000, "old")])
        layer.replace_all([_Range(5000, 6000, "new1"), _Range(2000, 3000, "new2")])
        # New items, sorted
        assert [it.text for it in layer.items()] == ["new2", "new1"]

    def test_on_change_fires_on_mutations(self):
        layer = self._cls()
        calls = []
        layer.on_change = lambda: calls.append(1)
        layer.add(_Range(0, 1000))
        layer.add(_Range(2000, 3000))
        layer.remove(layer.items()[0])
        layer.clear()
        assert len(calls) == 4

    def test_on_change_listener_failure_is_isolated(self):
        layer = self._cls()
        def bad():
            raise RuntimeError("listener bug")
        layer.on_change = bad
        # Should not propagate — layer mutation must succeed even if
        # the listener throws.
        layer.add(_Range(0, 1000))
        assert len(layer) == 1


# ---------------------------------------------------------------------------
#  Drag constraints (snap + collision)
# ---------------------------------------------------------------------------


class TestDragConstraints:
    """``apply_drag_constraints`` is the engine behind snap-and-clamp
    when the user drags a clip. The semantics:

    1. Snap to other clips' in/out edges + project ms 0 within
       ``snap_ms`` tolerance.
    2. After snapping, if the position would overlap, clamp to the
       nearest non-overlapping spot.

    Pure function — no Qt required."""

    def setup_method(self):
        from app.timeline_model import apply_drag_constraints, apply_drag_constraints_detail
        self._fn = apply_drag_constraints
        self._detail = apply_drag_constraints_detail

    def _clip(
        self, *, source_in_ms=0, source_out_ms=2000, timeline_in_ms=0,
        clip_id=1,
    ):
        from app.timeline_model import VideoClip
        return VideoClip(
            id=clip_id, source_path=Path("/x.mp4"),
            source_duration_ms=source_out_ms,
            timeline_in_ms=timeline_in_ms,
            source_in_ms=source_in_ms,
            source_out_ms=source_out_ms,
        )

    def test_no_other_clips_passes_through(self):
        c = self._clip(timeline_in_ms=1000)
        assert self._fn([c], c, 5000, snap_ms=200) == 5000

    def test_snaps_to_zero_within_tolerance(self):
        c = self._clip(timeline_in_ms=1000)
        # Desired=120 ms, snap tolerance 200 ms → snap to 0.
        assert self._fn([c], c, 120, snap_ms=200) == 0
        # Desired=300 ms → outside tolerance, no snap.
        assert self._fn([c], c, 300, snap_ms=200) == 300

    def test_snaps_to_extra_playhead_or_marker_target(self):
        c = self._clip(timeline_in_ms=1000)
        assert self._fn(
            [c],
            c,
            4920,
            snap_ms=100,
            extra_snap_targets=[5000],
        ) == 5000

    def test_detail_reports_snap_target_and_edge(self):
        c = self._clip(timeline_in_ms=1000)
        detail = self._detail(
            [c],
            c,
            4920,
            snap_ms=100,
            extra_snap_targets=[5000],
        )

        assert detail.timeline_in_ms == 5000
        assert detail.requested_timeline_in_ms == 4920
        assert detail.snapped is True
        assert detail.snap_target_ms == 5000
        assert detail.snap_edge == "in"
        assert detail.snap_source == "marker/playhead"
        assert detail.collided is False

    def test_extra_target_snap_still_respects_collision(self):
        c = self._clip(clip_id=1, timeline_in_ms=1000, source_out_ms=2000)
        blocker = self._clip(clip_id=2, timeline_in_ms=5000, source_out_ms=2000)
        result = self._fn(
            [c, blocker],
            c,
            4920,
            snap_ms=100,
            extra_snap_targets=[5000],
        )
        assert result == 3000

    def test_detail_reports_snap_then_collision_clamp(self):
        c = self._clip(clip_id=1, timeline_in_ms=1000, source_out_ms=2000)
        blocker = self._clip(clip_id=2, timeline_in_ms=5000, source_out_ms=2000)
        detail = self._detail(
            [c, blocker],
            c,
            4920,
            snap_ms=100,
            extra_snap_targets=[5000],
        )

        assert detail.timeline_in_ms == 3000
        assert detail.snapped is True
        assert detail.snap_target_ms == 5000
        assert detail.collided is True
        assert detail.clamped is True
        assert detail.clamp_target_ms == 3000

    def test_snaps_in_edge_to_other_clip_in(self):
        # Other clip at [5000, 7000); dragged clip is 2000 ms long.
        # Drop in-edge at 4900 ms (~snap to 5000) → in stays at 5000…
        # but that overlaps the other clip [5000, 7000), so collision
        # clamp kicks in. Use a less-conflicting target instead.
        other = self._clip(clip_id=99, timeline_in_ms=5000, source_out_ms=2000)
        c = self._clip(clip_id=1, timeline_in_ms=0, source_out_ms=1000)
        # Desired 4920 → snap target 5000 (in-edge). 5000 + 1000 = 6000
        # which overlaps [5000, 7000), so collision clamps. The clamp
        # candidates are: park flush LEFT of other → 5000-1000 = 4000;
        # park flush RIGHT → 7000. Closer to 5000 is 4000.
        assert self._fn([c, other], c, 4920, snap_ms=200) == 4000

    def test_snaps_out_edge_to_other_clip_in(self):
        # Other clip at [5000, 7000); dragged clip 2000 ms long.
        # Drop with out-edge near 5000 → in-edge becomes 3000.
        other = self._clip(clip_id=99, timeline_in_ms=5000, source_out_ms=2000)
        c = self._clip(clip_id=1, timeline_in_ms=0, source_out_ms=2000)
        # Desired in-edge 3050; out-edge 5050 → snap out to 5000 →
        # in-edge becomes 3000. No overlap (out=5000 == other.in=5000).
        assert self._fn([c, other], c, 3050, snap_ms=200) == 3000

    def test_collision_clamps_to_nearest_gap(self):
        # Two existing clips: A at [0, 4000), B at [6000, 8000).
        # Dragged 1000 ms long, desired in 4500 (overlaps neither but
        # in the gap). Should pass through.
        a = self._clip(clip_id=1, timeline_in_ms=0, source_out_ms=4000)
        b = self._clip(clip_id=2, timeline_in_ms=6000, source_out_ms=2000)
        c = self._clip(clip_id=3, timeline_in_ms=10_000, source_out_ms=1000)
        result = self._fn([a, b, c], c, 4500, snap_ms=50)
        assert result == 4500

    def test_collision_blocks_when_no_gap_left(self):
        # Pack clips so [0..2000] and [2000..4000] cover everything.
        # Drag a third 1500 ms clip that's currently at 5000 to
        # somewhere fully inside [0, 4000) — should clamp to keep
        # current position because nowhere is free in that range.
        a = self._clip(clip_id=1, timeline_in_ms=0, source_out_ms=2000)
        b = self._clip(clip_id=2, timeline_in_ms=2000, source_out_ms=2000)
        # Make the dragged clip start outside the packed area.
        c = self._clip(clip_id=3, timeline_in_ms=5000, source_out_ms=1500)
        # Desired 1000 → would overlap. Candidates: park left of
        # a (= -1500 → clamped to 0; collides with a still); park
        # right of a (= 2000; collides with b); left of b (= 500;
        # collides with a); right of b (= 4000; FREE). Closest to
        # desired 1000: 4000.
        result = self._fn([a, b, c], c, 1000, snap_ms=50)
        assert result == 4000

    def test_self_does_not_block_self(self):
        # Dragging a clip to its OWN current position must not be
        # treated as a collision against itself.
        c = self._clip(timeline_in_ms=2000, source_out_ms=2000)
        assert self._fn([c], c, 2000, snap_ms=50) == 2000

    def test_negative_desired_clamps_to_zero(self):
        c = self._clip(timeline_in_ms=2000, source_out_ms=2000)
        assert self._fn([c], c, -5000, snap_ms=50) == 0


# ---------------------------------------------------------------------------
#  Option C: blade-at-playhead + ripple delete
# ---------------------------------------------------------------------------


class TestSplitAtProjectMs:
    """Industry-standard blade tool — split the clip under the
    playhead at the playhead's project-time position. The function
    is the engine the editor's B / Ctrl+K shortcut calls."""

    def setup_method(self):
        from app.timeline_model import split_clips_at_project_ms
        self._fn = split_clips_at_project_ms

    def _clip(
        self, *, source_in_ms=0, source_out_ms=10_000, timeline_in_ms=0,
        clip_id=1,
    ):
        from app.timeline_model import VideoClip
        return VideoClip(
            id=clip_id, source_path=Path("/x.mp4"),
            source_duration_ms=source_out_ms,
            timeline_in_ms=timeline_in_ms,
            source_in_ms=source_in_ms, source_out_ms=source_out_ms,
        )

    def test_split_inside_single_clip_yields_two_halves(self):
        clip = self._clip()
        result = self._fn([clip], 4000)
        assert len(result) == 2
        a, b = result
        assert (a.timeline_in_ms, a.timeline_out_ms) == (0, 4000)
        assert (b.timeline_in_ms, b.timeline_out_ms) == (4000, 10_000)
        # Source ranges partition the original window cleanly.
        assert (a.source_in_ms, a.source_out_ms) == (0, 4000)
        assert (b.source_in_ms, b.source_out_ms) == (4000, 10_000)

    def test_split_at_clip_boundary_is_noop(self):
        clip = self._clip()
        # Strictly-inside semantics: project_ms == timeline_in or
        # timeline_out doesn't split — matches DaVinci / Premiere.
        assert self._fn([clip], 0) == [clip]
        assert self._fn([clip], 10_000) == [clip]

    def test_split_outside_clip_passes_clips_through(self):
        c1 = self._clip(clip_id=1, timeline_in_ms=0, source_out_ms=2000)
        c2 = self._clip(clip_id=2, timeline_in_ms=4000, source_out_ms=2000)
        # 3000 falls in the gap — neither clip is touched.
        result = self._fn([c1, c2], 3000)
        assert result == [c1, c2]

    def test_split_with_offset_track_maps_source_correctly(self):
        # Clip at project [2000, 6000), source [1000, 5000). Split at
        # project 4000 → source 1000 + (4000-2000) = 3000.
        clip = self._clip(
            source_in_ms=1000, source_out_ms=5000, timeline_in_ms=2000,
        )
        result = self._fn([clip], 4000)
        assert len(result) == 2
        a, b = result
        assert (a.source_in_ms, a.source_out_ms) == (1000, 3000)
        assert (b.source_in_ms, b.source_out_ms) == (3000, 5000)

    def test_split_does_not_mutate_input(self):
        clip = self._clip()
        original = [clip]
        self._fn(original, 4000)
        assert original == [clip]
        assert (clip.source_in_ms, clip.source_out_ms) == (0, 10_000)


class TestRippleDeleteClips:
    """Ripple-delete — remove a clip and shift everything to the
    right of it left to close the gap. Standard DaVinci / Premiere
    behaviour for ``Shift+Delete`` on a clip selection."""

    def setup_method(self):
        from app.timeline_model import ripple_delete_clips
        self._fn = ripple_delete_clips

    def _clip(
        self, *, source_in_ms=0, source_out_ms=2000, timeline_in_ms=0,
        clip_id=1,
    ):
        from app.timeline_model import VideoClip
        return VideoClip(
            id=clip_id, source_path=Path("/x.mp4"),
            source_duration_ms=source_out_ms,
            timeline_in_ms=timeline_in_ms,
            source_in_ms=source_in_ms, source_out_ms=source_out_ms,
        )

    def test_empty_target_set_passes_through(self):
        a = self._clip(clip_id=1)
        assert self._fn([a], set()) == [a]

    def test_ripple_shifts_subsequent_clips_left(self):
        a = self._clip(clip_id=1, timeline_in_ms=0, source_out_ms=2000)
        b = self._clip(clip_id=2, timeline_in_ms=2000, source_out_ms=3000)
        c = self._clip(clip_id=3, timeline_in_ms=5000, source_out_ms=2000)
        # Delete b (3000 ms long). c should shift from 5000 → 2000.
        result = self._fn([a, b, c], {2})
        assert len(result) == 2
        a_new, c_new = result
        assert a_new.id == 1 and a_new.timeline_in_ms == 0
        assert c_new.id == 3 and c_new.timeline_in_ms == 2000

    def test_ripple_leaves_earlier_clips_alone(self):
        a = self._clip(clip_id=1, timeline_in_ms=0, source_out_ms=2000)
        b = self._clip(clip_id=2, timeline_in_ms=2000, source_out_ms=3000)
        # Delete b — a (which starts BEFORE b) shouldn't move.
        result = self._fn([a, b], {2})
        assert len(result) == 1
        assert result[0].id == 1 and result[0].timeline_in_ms == 0

    def test_ripple_multiple_targets_close_each_gap_in_order(self):
        a = self._clip(clip_id=1, timeline_in_ms=0, source_out_ms=1000)
        b = self._clip(clip_id=2, timeline_in_ms=1000, source_out_ms=1000)
        c = self._clip(clip_id=3, timeline_in_ms=2000, source_out_ms=1000)
        d = self._clip(clip_id=4, timeline_in_ms=3000, source_out_ms=1000)
        # Delete b and c — d should shift left by the combined 2000ms.
        result = self._fn([a, b, c, d], {2, 3})
        assert [r.id for r in result] == [1, 4]
        assert result[0].timeline_in_ms == 0
        assert result[1].timeline_in_ms == 1000

    def test_ripple_does_not_mutate_input(self):
        a = self._clip(clip_id=1)
        b = self._clip(clip_id=2, timeline_in_ms=2000)
        original = [a, b]
        self._fn(original, {2})
        assert original == [a, b]
        # a's timeline_in_ms is unchanged on the original.
        assert a.timeline_in_ms == 0


class TestTimelinePolishEdits:
    """Commercial-style trim modes should be deterministic and undo-friendly."""

    def _clip(
        self,
        clip_id: int,
        *,
        timeline_in_ms: int,
        source_in_ms: int = 0,
        source_out_ms: int = 3000,
        source_duration_ms: int = 6000,
    ):
        from app.timeline_model import VideoClip

        return VideoClip(
            id=clip_id,
            source_path=Path(f"/fake/{clip_id}.mp4"),
            source_duration_ms=source_duration_ms,
            timeline_in_ms=timeline_in_ms,
            source_in_ms=source_in_ms,
            source_out_ms=source_out_ms,
            node_graph=NodeGraph(color=ColorNode(grade=_FakeGrade())),
        )

    def test_slip_keeps_timeline_edges_and_moves_source_window(self):
        from app.timeline_model import slip_clip_source_window

        clip = self._clip(1, timeline_in_ms=1000, source_in_ms=1000, source_out_ms=3000)

        slipped = slip_clip_source_window(clip, 750)

        assert (slipped.timeline_in_ms, slipped.timeline_out_ms) == (1000, 3000)
        assert (slipped.source_in_ms, slipped.source_out_ms) == (1750, 3750)
        assert (clip.source_in_ms, clip.source_out_ms) == (1000, 3000)

    def test_slip_clamps_to_source_bounds(self):
        from app.timeline_model import slip_clip_source_window

        clip = self._clip(1, timeline_in_ms=0, source_in_ms=3000, source_out_ms=5000)

        slipped = slip_clip_source_window(clip, 10_000)

        assert slipped.source_out_ms == slipped.source_duration_ms
        assert slipped.effective_length_ms == clip.effective_length_ms

    def test_roll_edit_keeps_outer_duration_and_adjusts_both_sources(self):
        from app.timeline_model import roll_edit_adjacent

        left = self._clip(1, timeline_in_ms=0, source_in_ms=0, source_out_ms=3000)
        right = self._clip(2, timeline_in_ms=3000, source_in_ms=1000, source_out_ms=4000)

        result = roll_edit_adjacent([left, right], 1, 2, 500)
        a, b = result

        assert (a.timeline_in_ms, a.timeline_out_ms) == (0, 3500)
        assert (b.timeline_in_ms, b.timeline_out_ms) == (3500, 6000)
        assert (a.source_in_ms, a.source_out_ms) == (0, 3500)
        assert (b.source_in_ms, b.source_out_ms) == (1500, 4000)
        assert right.timeline_in_ms == 3000

    def test_roll_edit_clamps_without_inverting_clips(self):
        from app.timeline_model import roll_edit_adjacent

        left = self._clip(1, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000)
        right = self._clip(2, timeline_in_ms=1000, source_in_ms=0, source_out_ms=1000)

        result = roll_edit_adjacent([left, right], 1, 2, -10_000)
        a, b = result

        assert a.effective_length_ms >= 1
        assert b.effective_length_ms >= 1
        assert a.timeline_out_ms == b.timeline_in_ms

    def test_slide_moves_middle_clip_and_preserves_block_span(self):
        from app.timeline_model import slide_clip_between_neighbors

        prev_clip = self._clip(1, timeline_in_ms=0, source_in_ms=0, source_out_ms=3000)
        middle = self._clip(2, timeline_in_ms=3000, source_in_ms=1000, source_out_ms=3000)
        next_clip = self._clip(3, timeline_in_ms=5000, source_in_ms=1000, source_out_ms=4000)

        result = slide_clip_between_neighbors([prev_clip, middle, next_clip], 2, 400)
        a, b, c = result

        assert (a.timeline_in_ms, c.timeline_out_ms) == (0, 8000)
        assert b.timeline_in_ms == 3400
        assert (b.source_in_ms, b.source_out_ms) == (1000, 3000)
        assert a.timeline_out_ms == b.timeline_in_ms
        assert b.timeline_out_ms == c.timeline_in_ms
        assert prev_clip.source_out_ms == 3000

    def test_slide_requires_contiguous_neighbors(self):
        from app.timeline_model import slide_clip_between_neighbors

        prev_clip = self._clip(1, timeline_in_ms=0, source_out_ms=2000)
        middle = self._clip(2, timeline_in_ms=3000, source_out_ms=2000)
        next_clip = self._clip(3, timeline_in_ms=5000, source_out_ms=2000)

        with pytest.raises(ValueError):
            slide_clip_between_neighbors([prev_clip, middle, next_clip], 2, 100)

    def test_detect_timeline_edge_issues_classifies_micro_and_large_edges(self):
        from app.timeline_model import detect_timeline_edge_issues

        a = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        b = self._clip(2, timeline_in_ms=1016, source_out_ms=1000)
        c = self._clip(3, timeline_in_ms=1900, source_out_ms=1000)
        d = self._clip(4, timeline_in_ms=5000, source_out_ms=1000)

        issues = detect_timeline_edge_issues([a, b, c, d], frame_ms=33)

        assert [issue["kind"] for issue in issues] == [
            "micro_gap",
            "overlap",
            "gap",
        ]
        assert issues[0]["auto_fixable"] == 1
        assert issues[1]["auto_fixable"] == 0
        assert issues[2]["duration_ms"] == 2100

    def test_cleanup_timeline_micro_edges_closes_one_frame_gaps(self):
        from app.timeline_model import cleanup_timeline_micro_edges

        a = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        b = self._clip(2, timeline_in_ms=1016, source_out_ms=1000)
        c = self._clip(3, timeline_in_ms=2016, source_out_ms=1000)

        cleaned, actions = cleanup_timeline_micro_edges([a, b, c], frame_ms=33)

        assert [clip.timeline_in_ms for clip in cleaned] == [0, 1000, 2000]
        assert actions == [{
            "kind": "close_micro_gap",
            "left_clip_id": 1,
            "right_clip_id": 2,
            "duration_ms": 16,
            "delta_ms": -16,
        }]
        assert b.timeline_in_ms == 1016
        assert c.timeline_in_ms == 2016

    def test_cleanup_timeline_micro_edges_trims_one_frame_overlap(self):
        from app.timeline_model import cleanup_timeline_micro_edges

        a = self._clip(1, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000)
        b = self._clip(2, timeline_in_ms=984, source_in_ms=0, source_out_ms=1000)

        cleaned, actions = cleanup_timeline_micro_edges([a, b], frame_ms=33)

        left, right = cleaned
        assert left.timeline_in_ms == 0
        assert left.timeline_out_ms == right.timeline_in_ms
        assert left.source_out_ms == 984
        assert right.timeline_in_ms == 984
        assert actions == [{
            "kind": "trim_micro_overlap",
            "left_clip_id": 1,
            "right_clip_id": 2,
            "duration_ms": 16,
            "delta_ms": -16,
        }]
        assert a.source_out_ms == 1000

    def test_cleanup_timeline_micro_edges_leaves_large_gaps_and_overlaps(self):
        from app.timeline_model import cleanup_timeline_micro_edges

        a = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        b = self._clip(2, timeline_in_ms=1200, source_out_ms=1000)
        c = self._clip(3, timeline_in_ms=2100, source_out_ms=1000)

        cleaned, actions = cleanup_timeline_micro_edges([a, b, c], frame_ms=33)

        assert [clip.timeline_in_ms for clip in cleaned] == [0, 1200, 2100]
        assert cleaned[1].source_out_ms == 1000
        assert actions == []

    def test_polish_edit_sequence_preserves_timeline_invariants(self):
        from app.timeline_model import (
            cleanup_timeline_micro_edges,
            detect_timeline_edge_issues,
            roll_edit_adjacent,
            slide_clip_between_neighbors,
            slip_clip_source_window,
        )

        clips = [
            self._clip(1, timeline_in_ms=0, source_in_ms=0, source_out_ms=3000),
            self._clip(2, timeline_in_ms=3000, source_in_ms=1000, source_out_ms=3000),
            self._clip(3, timeline_in_ms=5000, source_in_ms=2000, source_out_ms=5000),
        ]

        clips = roll_edit_adjacent(clips, 1, 2, 250)
        clips = [clips[0], slip_clip_source_window(clips[1], 300), clips[2]]
        clips = slide_clip_between_neighbors(clips, 2, -125)
        clips, actions = cleanup_timeline_micro_edges(clips, frame_ms=33)

        assert actions == []
        assert [clip.id for clip in clips] == [1, 2, 3]
        assert all(clip.source_in_ms < clip.source_out_ms for clip in clips)
        assert all(clip.timeline_in_ms < clip.timeline_out_ms for clip in clips)
        assert clips[0].timeline_out_ms == clips[1].timeline_in_ms
        assert clips[1].timeline_out_ms == clips[2].timeline_in_ms
        assert detect_timeline_edge_issues(clips, frame_ms=33) == []

    def test_editor_timeline_edge_summary_counts_auto_fixable_edges(self):
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        a = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        b = self._clip(2, timeline_in_ms=1016, source_out_ms=1000)
        c = self._clip(3, timeline_in_ms=2000, source_out_ms=1000)
        track = VideoTrack(id=2, clips=[a, b, c])

        summary = VideoEditorWindow._timeline_edge_issue_summary(
            [track],
            {"fps": 60.0},
        )

        assert summary["frame_ms"] == 17
        assert summary["issue_count"] == 2
        assert summary["auto_fixable_count"] == 2
        assert summary["micro_gap_count"] == 1
        assert summary["micro_overlap_count"] == 1
        assert summary["tracks"][0]["track_id"] == 2

    def test_editor_cleanup_timeline_micro_edges_updates_existing_clips(self):
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        a = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        b = self._clip(2, timeline_in_ms=1016, source_out_ms=1000)
        c = self._clip(3, timeline_in_ms=2000, source_out_ms=1000)
        track = VideoTrack(id=2, clips=[a, b, c])
        row_events: list[str] = []
        events: list[str] = []
        row = SimpleNamespace(
            _recalc_width=lambda: row_events.append("width"),
            update=lambda: row_events.append("update"),
        )
        editor = SimpleNamespace(
            _tracks=[track],
            _project_settings={"fps": 60.0},
            _track_rows={2: row},
            _refresh_player_tracks=lambda: events.append("refresh"),
            _update_tracks_host_width=lambda: events.append("host-width"),
            _update_timeline_status=lambda: events.append("status"),
            _register_change=lambda label: events.append(label),
            _flash_status=lambda msg: events.append(msg),
        )

        count = VideoEditorWindow._cleanup_timeline_micro_edges(editor, track_id=2)

        assert count == 2
        assert track.clips[0] is a
        assert [clip.timeline_in_ms for clip in track.clips] == [0, 1000, 1984]
        assert a.source_out_ms == 1000
        assert b.source_out_ms == 984
        assert row_events == ["width", "update"]
        assert events == [
            "refresh",
            "host-width",
            "status",
            "timeline micro-edge cleanup",
            "Cleaned 2 timeline micro edge(s)",
        ]

    def test_editor_cleanup_timeline_micro_edges_moves_linked_audio(self):
        from app.audio_tracks import AudioClip, AudioTrack
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        a = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        b = self._clip(2, timeline_in_ms=1016, source_out_ms=1000)
        c = self._clip(3, timeline_in_ms=2016, source_out_ms=1000)
        b.linked_audio_id = 20
        c.linked_audio_id = 30
        track = VideoTrack(id=2, clips=[a, b, c])
        audio_a = AudioClip(id=20, offset_ms=1016, duration_ms=1000)
        audio_b = AudioClip(id=30, offset_ms=2016, duration_ms=1000)
        audio_track = AudioTrack(id=7, clips=[audio_a, audio_b])
        row_events: list[str] = []
        events: list[str] = []

        class _Mixer:
            def update_track(self, track):
                events.append(f"mix-{track.id}")

        editor = SimpleNamespace(
            _tracks=[track],
            _audio_tracks=[audio_track],
            _project_settings={"fps": 60.0},
            _track_rows={},
            _audio_rows={7: SimpleNamespace(update=lambda: row_events.append("audio-row"))},
            _audio_mixer=_Mixer(),
            _refresh_player_tracks=lambda: events.append("refresh"),
            _update_tracks_host_width=lambda: events.append("host-width"),
            _update_timeline_status=lambda: events.append("status"),
            _register_change=lambda label: events.append(label),
            _flash_status=lambda msg: events.append(msg),
        )

        count = VideoEditorWindow._cleanup_timeline_micro_edges(editor, track_id=2)

        assert count == 1
        assert [clip.timeline_in_ms for clip in track.clips] == [0, 1000, 2000]
        assert [clip.offset_ms for clip in audio_track.clips] == [1000, 2000]
        assert row_events == ["audio-row"]
        assert events == [
            "mix-7",
            "refresh",
            "host-width",
            "status",
            "timeline micro-edge cleanup",
            "Cleaned 1 timeline micro edge(s); linked audio 2",
        ]

    def test_editor_cleanup_timeline_micro_edges_blocks_linked_audio_collision(self):
        from app.audio_tracks import AudioClip, AudioTrack
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        a = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        b = self._clip(2, timeline_in_ms=1016, source_out_ms=1000)
        b.linked_audio_id = 20
        track = VideoTrack(id=2, clips=[a, b])
        linked = AudioClip(id=20, offset_ms=1016, duration_ms=1000)
        obstacle = AudioClip(id=21, offset_ms=1000, duration_ms=10)
        audio_track = AudioTrack(id=7, clips=[obstacle, linked])
        events: list[str] = []
        editor = SimpleNamespace(
            _tracks=[track],
            _audio_tracks=[audio_track],
            _project_settings={"fps": 60.0},
            _track_rows={},
            _audio_rows={},
            _flash_status=lambda msg: events.append(msg),
        )

        count = VideoEditorWindow._cleanup_timeline_micro_edges(editor, track_id=2)

        assert count == 0
        assert b.timeline_in_ms == 1016
        assert linked.offset_ms == 1016
        assert events == ["Timeline cleanup blocked: linked audio would overlap or is missing"]

    def test_editor_cleanup_timeline_micro_edges_blocks_locked_track(self):
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        a = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        b = self._clip(2, timeline_in_ms=1016, source_out_ms=1000)
        track = VideoTrack(id=2, clips=[a, b], locked=True)
        events: list[str] = []
        editor = SimpleNamespace(
            _tracks=[track],
            _project_settings={"fps": 60.0},
            _track_rows={},
            _flash_status=lambda msg: events.append(msg),
        )

        count = VideoEditorWindow._cleanup_timeline_micro_edges(editor, track_id=2)

        assert count == 0
        assert b.timeline_in_ms == 1016
        assert events == ["Timeline cleanup blocked: selected track is locked"]

    def test_media_health_cleanup_action_routes_to_timeline_cleanup(self, monkeypatch):
        from app.video_editor_window import VideoEditorWindow
        import app.media_health_dialog as health_dialog
        import app.media_relink as media_relink
        import app.professional_readiness as readiness

        events: list[str] = []
        captured: dict = {}

        class _FakeHealthDialog:
            def __init__(self, report, _parent=None):
                captured["report"] = report
            def exec(self):
                events.append("dialog")
            def wants_timeline_cleanup(self):
                return True
            def wants_relink(self):
                return False

        monkeypatch.setattr(health_dialog, "MediaHealthDialog", _FakeHealthDialog)
        monkeypatch.setattr(
            media_relink,
            "build_media_health_report",
            lambda _doc, _roots: {"total_paths": 0, "status_counts": {}, "proxy_counts": {}},
        )
        monkeypatch.setattr(
            readiness,
            "build_professional_readiness_report",
            lambda _doc: {"score": 100, "issue_summary": {}},
        )
        editor = SimpleNamespace(
            _media_pool=None,
            _tracks=[],
            _audio_tracks=[],
            _spine_actor_tracks=[],
            _live2d_actor_tracks=[],
            _project_settings={"fps": 30.0},
            _project_path=None,
            _cleanup_timeline_micro_edges=lambda: events.append("cleanup"),
            _on_relink_project_media=lambda: events.append("relink"),
        )

        VideoEditorWindow._show_media_health(editor)

        assert events == ["dialog", "cleanup"]
        assert captured["report"]["timeline_edge_cleanup"]["frame_ms"] == 33

    def test_media_health_cleanup_reopens_with_fresh_report(self, monkeypatch):
        from app.video_editor_window import VideoEditorWindow
        import app.media_health_dialog as health_dialog
        import app.media_relink as media_relink
        import app.professional_readiness as readiness

        events: list[str] = []
        cleanup_requests = iter([True, False])

        class _FakeHealthDialog:
            def __init__(self, report, _parent=None):
                events.append(f"dialog-{report['status_counts'].get('pass', 0)}")
                self._wants_cleanup = next(cleanup_requests)
            def exec(self):
                events.append("exec")
            def wants_timeline_cleanup(self):
                return self._wants_cleanup
            def wants_relink(self):
                return False

        build_count = {"value": 0}

        def _build_report(_doc, _roots):
            build_count["value"] += 1
            return {
                "total_paths": 0,
                "status_counts": {"pass": build_count["value"]},
                "proxy_counts": {},
            }

        monkeypatch.setattr(health_dialog, "MediaHealthDialog", _FakeHealthDialog)
        monkeypatch.setattr(media_relink, "build_media_health_report", _build_report)
        monkeypatch.setattr(
            readiness,
            "build_professional_readiness_report",
            lambda _doc: {"score": 100, "issue_summary": {}},
        )
        editor = SimpleNamespace(
            _media_pool=None,
            _tracks=[],
            _audio_tracks=[],
            _spine_actor_tracks=[],
            _live2d_actor_tracks=[],
            _project_settings={"fps": 30.0},
            _project_path=None,
            _cleanup_timeline_micro_edges=lambda: events.append("cleanup") or 1,
            _on_relink_project_media=lambda: events.append("relink"),
        )

        VideoEditorWindow._show_media_health(editor)

        assert events == ["dialog-1", "exec", "cleanup", "dialog-2", "exec"]
        assert build_count["value"] == 2

    def test_linked_move_plan_moves_video_and_linked_audio(self):
        from app.audio_tracks import AudioClip, AudioTrack
        from app.timeline_model import VideoTrack, plan_linked_timeline_move

        video = self._clip(1, timeline_in_ms=1000, source_out_ms=1500)
        video.linked_audio_id = 10
        vtrack = VideoTrack(id=2, clips=[video])
        audio = AudioClip(id=10, offset_ms=1000, duration_ms=1500)
        atrack = AudioTrack(id=5, clips=[audio])

        plan = plan_linked_timeline_move([vtrack], [atrack], [(2, 1)], 250)

        assert plan.ok
        assert plan.video_starts == {(2, 1): 1250}
        assert plan.audio_offsets == {(5, 10): 1250}
        assert video.timeline_in_ms == 1000
        assert audio.offset_ms == 1000

    def test_linked_move_plan_blocks_video_collision_before_mutation(self):
        from app.audio_tracks import AudioTrack
        from app.timeline_model import VideoTrack, plan_linked_timeline_move

        moving = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        obstacle = self._clip(2, timeline_in_ms=1200, source_out_ms=1000)
        vtrack = VideoTrack(id=2, clips=[moving, obstacle])

        plan = plan_linked_timeline_move([vtrack], [AudioTrack(id=5)], [(2, 1)], 500)

        assert not plan.ok
        assert plan.blocked_reason == "video_collision"
        assert plan.details["clip_id"] == 1
        assert plan.details["other_clip_id"] == 2
        assert plan.details["attempted_start_ms"] == 500
        assert moving.timeline_in_ms == 0

    def test_linked_move_plan_blocks_linked_audio_collision(self):
        from app.audio_tracks import AudioClip, AudioTrack
        from app.timeline_model import VideoTrack, plan_linked_timeline_move

        video = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        video.linked_audio_id = 10
        vtrack = VideoTrack(id=2, clips=[video])
        linked = AudioClip(id=10, offset_ms=0, duration_ms=1000)
        obstacle = AudioClip(id=11, offset_ms=1200, duration_ms=1000)
        atrack = AudioTrack(id=5, clips=[linked, obstacle])

        plan = plan_linked_timeline_move([vtrack], [atrack], [(2, 1)], 500)

        assert not plan.ok
        assert plan.blocked_reason == "audio_collision"
        assert plan.details["clip_id"] == 10
        assert plan.details["other_clip_id"] == 11
        assert plan.details["track_id"] == 5
        assert linked.offset_ms == 0

    def test_linked_move_plan_blocks_missing_link_in_strict_mode(self):
        from app.audio_tracks import AudioTrack
        from app.timeline_model import VideoTrack, plan_linked_timeline_move

        video = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        video.linked_audio_id = 999
        vtrack = VideoTrack(id=2, clips=[video])

        plan = plan_linked_timeline_move([vtrack], [AudioTrack(id=5)], [(2, 1)], 100)

        assert not plan.ok
        assert plan.blocked_reason == "missing_linked_audio"

    def test_linked_move_plan_blocks_stale_selected_clip_in_strict_selection(self):
        from app.audio_tracks import AudioTrack
        from app.timeline_model import VideoTrack, plan_linked_timeline_move

        video = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        vtrack = VideoTrack(id=2, clips=[video])

        plan = plan_linked_timeline_move(
            [vtrack],
            [AudioTrack(id=5)],
            [(2, 1), (2, 999)],
            100,
            strict_selection=True,
        )

        assert not plan.ok
        assert plan.blocked_reason == "missing_video_clip"
        assert plan.details["track_id"] == 2
        assert plan.details["clip_id"] == 999
        assert video.timeline_in_ms == 0

    def test_linked_move_plan_blocks_shared_linked_audio(self):
        from app.audio_tracks import AudioClip, AudioTrack
        from app.timeline_model import VideoTrack, plan_linked_timeline_move

        left = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        right = self._clip(2, timeline_in_ms=1500, source_out_ms=1000)
        left.linked_audio_id = 10
        right.linked_audio_id = 10
        vtrack = VideoTrack(id=2, clips=[left, right])
        audio = AudioClip(id=10, offset_ms=0, duration_ms=2500)
        atrack = AudioTrack(id=5, clips=[audio])

        plan = plan_linked_timeline_move(
            [vtrack],
            [atrack],
            [(2, 1), (2, 2)],
            100,
        )

        assert not plan.ok
        assert plan.blocked_reason == "shared_linked_audio"
        assert plan.details["video_clip_id"] == 2
        assert plan.details["linked_audio_id"] == 10
        assert audio.offset_ms == 0

    def test_linked_move_plan_blocks_locked_video_track(self):
        from app.audio_tracks import AudioTrack
        from app.timeline_model import VideoTrack, plan_linked_timeline_move

        video = self._clip(1, timeline_in_ms=1000, source_out_ms=1000)
        vtrack = VideoTrack(id=2, clips=[video], locked=True)

        plan = plan_linked_timeline_move([vtrack], [AudioTrack(id=5)], [(2, 1)], 100)

        assert not plan.ok
        assert plan.blocked_reason == "locked_track"
        assert plan.details["track_id"] == 2
        assert plan.details["clip_id"] == 1
        assert video.timeline_in_ms == 1000

    def test_editor_drag_validator_blocks_before_trackrow_mutates(self):
        from app.audio_tracks import AudioClip, AudioTrack
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        video = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        video.linked_audio_id = 10
        vtrack = VideoTrack(id=2, clips=[video])
        linked = AudioClip(id=10, offset_ms=0, duration_ms=1000)
        obstacle = AudioClip(id=11, offset_ms=1200, duration_ms=1000)
        messages: list[str] = []
        editor = SimpleNamespace(
            _tracks=[vtrack],
            _audio_tracks=[AudioTrack(id=5, clips=[linked, obstacle])],
            _selected_clips=[(2, 1)],
            _flash_status=lambda msg: messages.append(msg),
        )

        result = VideoEditorWindow._validate_clip_drag_delta(editor, 2, {1}, 500)

        assert result["ok"] is False
        assert result["reason"] == "audio_collision"
        assert result["details"]["clip_id"] == 10
        assert result["details"]["other_clip_id"] == 11
        assert "linked audio" in messages[-1]
        assert "clip 10 overlaps clip 11" in messages[-1]
        assert video.timeline_in_ms == 0
        assert linked.offset_ms == 0

    def test_editor_drag_validator_reports_locked_track(self):
        from app.audio_tracks import AudioTrack
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        video = self._clip(1, timeline_in_ms=1000, source_out_ms=1000)
        vtrack = VideoTrack(id=2, clips=[video], locked=True)
        messages: list[str] = []
        editor = SimpleNamespace(
            _tracks=[vtrack],
            _audio_tracks=[AudioTrack(id=5)],
            _selected_clips=[(2, 1)],
            _flash_status=lambda msg: messages.append(msg),
        )

        result = VideoEditorWindow._validate_clip_drag_delta(editor, 2, {1}, 100)

        assert result["ok"] is False
        assert result["reason"] == "locked_track"
        assert result["details"]["track_id"] == 2
        assert "track is locked" in messages[-1]
        assert "clip 1 on track 2" in messages[-1]
        assert video.timeline_in_ms == 1000

    def test_editor_drag_validator_reports_stale_selection_before_mutation(self):
        from app.audio_tracks import AudioTrack
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        video = self._clip(1, timeline_in_ms=1000, source_out_ms=1000)
        vtrack = VideoTrack(id=2, clips=[video])
        messages: list[str] = []
        editor = SimpleNamespace(
            _tracks=[vtrack],
            _audio_tracks=[AudioTrack(id=5)],
            _selected_clips=[(2, 1), (2, 999)],
            _flash_status=lambda msg: messages.append(msg),
        )

        result = VideoEditorWindow._validate_clip_drag_delta(editor, 2, {1}, 100)

        assert result["ok"] is False
        assert result["reason"] == "missing_video_clip"
        assert result["details"]["clip_id"] == 999
        assert "selected clip is missing" in messages[-1]
        assert "clip 999 on track 2" in messages[-1]
        assert video.timeline_in_ms == 1000

    def test_blade_at_playhead_blocks_locked_track(self):
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        clip = self._clip(1, timeline_in_ms=0, source_out_ms=3000)
        track = VideoTrack(id=2, locked=True, clips=[clip])
        events: list[str] = []
        editor = SimpleNamespace(
            _tracks=[track],
            _track_rows={},
            _player=SimpleNamespace(position=lambda: 1000),
            _is_text_focus=lambda: False,
            _flash_status=lambda msg: events.append(msg),
            _refresh_player_tracks=lambda: events.append("refresh"),
            _register_change=lambda label: events.append(label),
        )

        VideoEditorWindow._blade_at_playhead(editor)

        assert track.clips == [clip]
        assert events == ["Blade blocked: locked track"]

    def test_blade_at_playhead_skips_locked_track_but_cuts_unlocked(self):
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        locked_clip = self._clip(1, timeline_in_ms=0, source_out_ms=3000)
        open_clip = self._clip(2, timeline_in_ms=0, source_out_ms=3000)
        locked_track = VideoTrack(id=2, locked=True, clips=[locked_clip])
        open_track = VideoTrack(id=3, locked=False, clips=[open_clip])
        events: list[str] = []
        editor = SimpleNamespace(
            _tracks=[locked_track, open_track],
            _track_rows={},
            _player=SimpleNamespace(position=lambda: 1000),
            _is_text_focus=lambda: False,
            _flash_status=lambda msg: events.append(msg),
            _refresh_player_tracks=lambda: events.append("refresh"),
            _register_change=lambda label: events.append(label),
        )

        VideoEditorWindow._blade_at_playhead(editor)

        assert locked_track.clips == [locked_clip]
        assert len(open_track.clips) == 2
        assert (open_track.clips[0].timeline_in_ms, open_track.clips[0].timeline_out_ms) == (0, 1000)
        assert (open_track.clips[1].timeline_in_ms, open_track.clips[1].timeline_out_ms) == (1000, 3000)
        assert events == ["refresh", "blade", "Blade skipped locked tracks"]

    def test_blade_track_at_ms_blocks_locked_track(self):
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        clip = self._clip(1, timeline_in_ms=0, source_out_ms=3000)
        track = VideoTrack(id=2, locked=True, clips=[clip])
        events: list[str] = []
        editor = SimpleNamespace(
            _find_track=lambda tid: track if int(tid) == 2 else None,
            _is_text_focus=lambda: False,
            _flash_status=lambda msg: events.append(msg),
            _refresh_player_tracks=lambda: events.append("refresh"),
            _register_change=lambda label: events.append(label),
        )

        VideoEditorWindow._blade_track_at_ms(editor, 2, 1000)

        assert track.clips == [clip]
        assert events == ["Blade blocked: track 2 is locked"]

    def test_timeline_nudge_step_supports_frame_ten_frame_and_second_steps(self):
        from app.video_editor_window import VideoEditorWindow

        settings = {"fps": 30.0}

        assert VideoEditorWindow._timeline_nudge_step_ms(settings) == 33
        assert VideoEditorWindow._timeline_nudge_step_ms(settings, ctrl=True) == 330
        assert VideoEditorWindow._timeline_nudge_step_ms(settings, shift=True) == 1000
        assert VideoEditorWindow._timeline_nudge_step_ms(
            settings, ctrl=True, shift=True,
        ) == 1000

    def test_timeline_nudge_status_names_frames_and_linked_audio(self):
        from app.video_editor_window import VideoEditorWindow

        msg = VideoEditorWindow._format_nudge_status(330, 2, 1, {"fps": 30.0})

        assert "2 clips" in msg
        assert "+10 frames (330 ms)" in msg
        assert "linked audio 1" in msg

    def test_bounded_seek_position_uses_project_duration(self):
        from app.video_editor_window import VideoEditorWindow

        assert VideoEditorWindow._bounded_seek_position(10_000, 5_000, 30_000) == 15_000
        assert VideoEditorWindow._bounded_seek_position(10_000, -15_000, 30_000) == 0
        assert VideoEditorWindow._bounded_seek_position(28_000, 5_000, 30_000) == 30_000
        assert VideoEditorWindow._bounded_seek_position(10_000, 5_000, -1) == 0

    def test_timeline_edit_points_include_video_audio_markers_and_actors(self):
        from app.video_editor_window import VideoEditorWindow

        video_track = SimpleNamespace(clips=[
            SimpleNamespace(timeline_in_ms=1000, timeline_out_ms=2000),
            SimpleNamespace(timeline_in_ms=4000, timeline_out_ms=5500),
        ])
        audio_track = SimpleNamespace(clips=[
            SimpleNamespace(offset_ms=500, effective_length_ms=250),
        ])
        spine_track = SimpleNamespace(clips=[
            SimpleNamespace(start_ms=3000, end_ms=3500),
        ])
        live2d_track = SimpleNamespace(clips=[
            SimpleNamespace(start_ms=6000, duration_ms=800),
        ])

        points = VideoEditorWindow._timeline_edit_points_ms(
            [video_track],
            [audio_track],
            [{"ms": 1500}],
            [spine_track],
            [live2d_track],
        )

        assert points == [
            0, 500, 750, 1000, 1500, 2000, 3000, 3500, 4000, 5500, 6000, 6800,
        ]

    def test_timeline_neighbor_edit_point_skips_current_cut(self):
        from app.video_editor_window import VideoEditorWindow

        points = [0, 1000, 2000, 3000]

        assert VideoEditorWindow._timeline_neighbor_edit_point(points, 2000, -1) == 1000
        assert VideoEditorWindow._timeline_neighbor_edit_point(points, 2000, 1) == 3000
        assert VideoEditorWindow._timeline_neighbor_edit_point(points, 0, -1) is None
        assert VideoEditorWindow._timeline_neighbor_edit_point(points, 3000, 1) is None

    def test_escape_returns_to_select_before_clearing_clip_selection(self):
        from app.video_editor_window import VideoEditorWindow

        calls: list[str] = []
        editor = SimpleNamespace(
            _timeline_tool_mode="blade",
            _selected_clips=[(2, 1)],
            _is_text_focus=lambda: False,
            _set_timeline_tool_mode=lambda mode: (
                setattr(editor, "_timeline_tool_mode", mode),
                calls.append(mode),
            ),
        )

        assert VideoEditorWindow._escape_timeline_context(editor) is True
        assert editor._timeline_tool_mode == "select"
        assert editor._selected_clips == [(2, 1)]
        assert calls == ["select"]

    def test_escape_clears_clip_selection_when_already_select_tool(self):
        from app.video_editor_window import VideoEditorWindow

        broadcasts: list[list[tuple[int, int]] | str] = []
        editor = SimpleNamespace(
            _timeline_tool_mode="select",
            _selected_clips=[(2, 1), (3, 4)],
            _is_text_focus=lambda: False,
            _broadcast_clip_selection=lambda: broadcasts.append(
                list(editor._selected_clips)
            ),
            _flash_status=lambda msg: broadcasts.append(msg),
        )

        assert VideoEditorWindow._escape_timeline_context(editor) is True
        assert editor._selected_clips == []
        assert broadcasts == [[], "Selection cleared"]

    def test_escape_ignores_text_focus(self):
        from app.video_editor_window import VideoEditorWindow

        editor = SimpleNamespace(
            _timeline_tool_mode="blade",
            _selected_clips=[(2, 1)],
            _is_text_focus=lambda: True,
        )

        assert VideoEditorWindow._escape_timeline_context(editor) is False
        assert editor._timeline_tool_mode == "blade"
        assert editor._selected_clips == [(2, 1)]

    def test_select_all_timeline_clips_selects_video_clips_in_track_order(self):
        from app.video_editor_window import VideoEditorWindow

        events: list[list[tuple[int, int]] | str] = []
        editor = SimpleNamespace(
            _tracks=[
                SimpleNamespace(id=2, clips=[
                    SimpleNamespace(id=10),
                    SimpleNamespace(id=11),
                ]),
                SimpleNamespace(id=3, clips=[SimpleNamespace(id=20)]),
            ],
            _selected_clips=[],
            _broadcast_clip_selection=lambda: events.append(
                list(editor._selected_clips)
            ),
            _flash_status=lambda msg: events.append(msg),
        )

        assert VideoEditorWindow._select_all_timeline_clips(editor) == 3
        assert editor._selected_clips == [(2, 10), (2, 11), (3, 20)]
        assert events == [
            [(2, 10), (2, 11), (3, 20)],
            "Selected 3 timeline clips",
        ]

    def test_select_all_timeline_clips_clears_stale_selection_when_empty(self):
        from app.video_editor_window import VideoEditorWindow

        events: list[list[tuple[int, int]] | str] = []
        editor = SimpleNamespace(
            _tracks=[SimpleNamespace(id=2, clips=[])],
            _selected_clips=[(2, 99)],
            _broadcast_clip_selection=lambda: events.append(
                list(editor._selected_clips)
            ),
            _flash_status=lambda msg: events.append(msg),
        )

        assert VideoEditorWindow._select_all_timeline_clips(editor) == 0
        assert editor._selected_clips == []
        assert events == [[], "No timeline clips to select"]

    def test_duplicate_selected_timeline_clips_keeps_spacing_after_obstacle(self):
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        a = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        b = self._clip(2, timeline_in_ms=2000, source_out_ms=1000)
        b.linked_audio_id = 40
        b.compound_group_id = 7
        b.compound_group_name = "Pair"
        obstacle = self._clip(3, timeline_in_ms=3000, source_out_ms=1000)
        track = VideoTrack(id=2, clips=[a, b, obstacle])
        next_ids = iter([10, 11])
        events: list[list[tuple[int, int]] | str] = []
        editor = SimpleNamespace(
            _tracks=[track],
            _selected_clips=[(2, 1), (2, 2)],
            _track_rows={},
            _next_clip_id=lambda: next(next_ids),
            _broadcast_clip_selection=lambda: events.append(
                list(editor._selected_clips)
            ),
            _refresh_player_tracks=lambda: events.append("refresh"),
            _update_tracks_host_width=lambda: events.append("width"),
            _register_change=lambda label: events.append(label),
            _flash_status=lambda msg: events.append(msg),
        )

        assert VideoEditorWindow._duplicate_selected_timeline_clips(editor) == 2

        by_id = {int(c.id): c for c in track.clips}
        assert by_id[10].timeline_in_ms == 4000
        assert by_id[11].timeline_in_ms == 6000
        assert by_id[11].linked_audio_id is None
        assert by_id[11].compound_group_id is None
        assert by_id[11].compound_group_name == ""
        assert editor._selected_clips == [(2, 10), (2, 11)]
        assert events == [
            [(2, 10), (2, 11)],
            "refresh",
            "width",
            "duplicate clips",
            "Duplicated 2 timeline clips",
        ]

    def test_duplicate_selected_timeline_clips_blocks_locked_track(self):
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        clip = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        track = VideoTrack(id=2, locked=True, clips=[clip])
        events: list[str] = []
        editor = SimpleNamespace(
            _tracks=[track],
            _selected_clips=[(2, 1)],
            _track_rows={},
            _next_clip_id=lambda: 10,
            _flash_status=lambda msg: events.append(msg),
        )

        assert VideoEditorWindow._duplicate_selected_timeline_clips(editor) == 0
        assert [c.id for c in track.clips] == [1]
        assert editor._selected_clips == [(2, 1)]
        assert events == ["Duplicate blocked: track 2 is locked"]

    def test_copy_paste_timeline_clips_at_playhead_preserves_offsets(self):
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        a = self._clip(1, timeline_in_ms=1000, source_out_ms=1000)
        b = self._clip(2, timeline_in_ms=2500, source_out_ms=1000)
        b.linked_audio_id = 40
        b.compound_group_id = 7
        b.compound_group_name = "Pair"
        track = VideoTrack(id=2, clips=[a, b])
        next_ids = iter([10, 11])
        events: list[list[tuple[int, int]] | str] = []
        editor = SimpleNamespace(
            _tracks=[track],
            _selected_clips=[(2, 1), (2, 2)],
            _track_rows={},
            _timeline_clipboard=None,
            _player=SimpleNamespace(position=lambda: 4000),
            _next_clip_id=lambda: next(next_ids),
            _broadcast_clip_selection=lambda: events.append(
                list(editor._selected_clips)
            ),
            _refresh_player_tracks=lambda: events.append("refresh"),
            _update_tracks_host_width=lambda: events.append("width"),
            _register_change=lambda label: events.append(label),
            _flash_status=lambda msg: events.append(msg),
        )

        assert VideoEditorWindow._copy_selected_timeline_clips(editor) == 2
        assert VideoEditorWindow._paste_timeline_clipboard(editor) == 2

        by_id = {int(c.id): c for c in track.clips}
        assert by_id[10].timeline_in_ms == 4000
        assert by_id[11].timeline_in_ms == 5500
        assert by_id[11].linked_audio_id is None
        assert by_id[11].compound_group_id is None
        assert by_id[11].compound_group_name == ""
        assert by_id[11].thumbnails == []
        assert editor._selected_clips == [(2, 10), (2, 11)]
        assert events == [
            "Copied 2 timeline clips",
            [(2, 10), (2, 11)],
            "refresh",
            "width",
            "paste clips",
            "Pasted 2 timeline clips",
        ]

    def test_paste_timeline_clipboard_shifts_whole_group_past_collision(self):
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        obstacle = self._clip(1, timeline_in_ms=500, source_out_ms=1000)
        track_a = VideoTrack(id=2, clips=[obstacle])
        track_b = VideoTrack(id=3, clips=[])
        source_a = self._clip(5, timeline_in_ms=0, source_out_ms=1000)
        source_b = self._clip(6, timeline_in_ms=1000, source_out_ms=1000)
        next_ids = iter([10, 11])
        editor = SimpleNamespace(
            _tracks=[track_a, track_b],
            _selected_clips=[],
            _track_rows={},
            _timeline_clipboard={
                "kind": "video_clips",
                "records": [
                    {"track_id": 2, "rel_start_ms": 0, "clip": source_a},
                    {"track_id": 3, "rel_start_ms": 1000, "clip": source_b},
                ],
            },
            _next_clip_id=lambda: next(next_ids),
            _broadcast_clip_selection=lambda: None,
            _refresh_player_tracks=lambda: None,
            _update_tracks_host_width=lambda: None,
            _register_change=lambda _label: None,
            _flash_status=lambda _msg: None,
        )

        assert VideoEditorWindow._paste_timeline_clipboard(editor, at_ms=0) == 2

        by_id_a = {int(c.id): c for c in track_a.clips}
        by_id_b = {int(c.id): c for c in track_b.clips}
        assert by_id_a[10].timeline_in_ms == 1500
        assert by_id_b[11].timeline_in_ms == 2500
        assert editor._selected_clips == [(2, 10), (3, 11)]

    def test_paste_timeline_clipboard_blocks_locked_target_track(self):
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        track = VideoTrack(id=2, locked=True, clips=[])
        source = self._clip(5, timeline_in_ms=0, source_out_ms=1000)
        events: list[str] = []
        editor = SimpleNamespace(
            _tracks=[track],
            _selected_clips=[],
            _timeline_clipboard={
                "kind": "video_clips",
                "records": [{"track_id": 2, "rel_start_ms": 0, "clip": source}],
            },
            _flash_status=lambda msg: events.append(msg),
        )

        assert VideoEditorWindow._paste_timeline_clipboard(editor, at_ms=0) == 0
        assert track.clips == []
        assert events == ["Paste blocked: track 2 is locked"]

    def test_ripple_delete_selected_blocks_locked_track(self):
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        clip = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        track = VideoTrack(id=2, locked=True, clips=[clip])
        events: list[str] = []
        editor = SimpleNamespace(
            _tracks=[track],
            _selected_clips=[(2, 1)],
            _track_rows={},
            _is_text_focus=lambda: False,
            _find_track=lambda tid: track if int(tid) == 2 else None,
            _flash_status=lambda msg: events.append(msg),
        )

        assert VideoEditorWindow._ripple_delete_selected(editor) is False
        assert track.clips == [clip]
        assert editor._selected_clips == [(2, 1)]
        assert events == ["Delete blocked: track 2 is locked"]

    def test_cut_selected_timeline_clips_copies_then_ripple_deletes(self):
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        a = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        b = self._clip(2, timeline_in_ms=1000, source_out_ms=1000)
        c = self._clip(3, timeline_in_ms=2000, source_out_ms=1000)
        track = VideoTrack(id=2, clips=[a, b, c])
        events: list[str] = []
        editor = SimpleNamespace(
            _tracks=[track],
            _selected_clips=[(2, 2)],
            _track_rows={},
            _timeline_clipboard=None,
            _is_text_focus=lambda: False,
            _find_track=lambda tid: track if int(tid) == 2 else None,
            _update_timeline_status=lambda: events.append("status"),
            _refresh_player_tracks=lambda: events.append("refresh"),
            _register_change=lambda label: events.append(label),
            _flash_status=lambda msg: events.append(msg),
        )

        assert VideoEditorWindow._cut_selected_timeline_clips(editor) == 1

        assert [int(c.id) for c in track.clips] == [1, 3]
        assert track.clips[1].timeline_in_ms == 1000
        assert editor._selected_clips == []
        assert editor._timeline_clipboard["kind"] == "video_clips"
        assert len(editor._timeline_clipboard["records"]) == 1
        assert int(editor._timeline_clipboard["records"][0]["clip"].id) == 2
        assert events == ["status", "refresh", "cut clips", "Cut 1 timeline clips"]

    def test_cut_selected_timeline_clips_blocks_locked_track_before_copy(self):
        from app.timeline_model import VideoTrack
        from app.video_editor_window import VideoEditorWindow

        clip = self._clip(1, timeline_in_ms=0, source_out_ms=1000)
        track = VideoTrack(id=2, locked=True, clips=[clip])
        events: list[str] = []
        old_clipboard = {"kind": "old"}
        editor = SimpleNamespace(
            _tracks=[track],
            _selected_clips=[(2, 1)],
            _timeline_clipboard=old_clipboard,
            _is_text_focus=lambda: False,
            _find_track=lambda tid: track if int(tid) == 2 else None,
            _flash_status=lambda msg: events.append(msg),
        )

        assert VideoEditorWindow._cut_selected_timeline_clips(editor) == 0
        assert track.clips == [clip]
        assert editor._selected_clips == [(2, 1)]
        assert editor._timeline_clipboard is old_clipboard
        assert events == ["Cut blocked: track 2 is locked"]

    def test_jkl_l_cycles_forward_shuttle_rates(self):
        from app.video_editor_window import VideoEditorWindow

        class _Player:
            def __init__(self):
                self.rates: list[float] = []
                self.plays = 0
            def set_shuttle_rate(self, rate):
                self.rates.append(float(rate))
            def play(self):
                self.plays += 1

        class _Label:
            def __init__(self):
                self.texts: list[str] = []
            def setText(self, text):
                self.texts.append(str(text))

        messages: list[str] = []
        editor = SimpleNamespace(
            _player=_Player(),
            _jkl_transport_rate=0.0,
            current_speed_label=_Label(),
            _is_text_focus=lambda: False,
            _flash_status=lambda msg: messages.append(msg),
        )

        assert VideoEditorWindow._apply_jkl_transport(editor, "l") is True
        assert VideoEditorWindow._apply_jkl_transport(editor, "l") is True

        assert editor._player.rates == [1.0, 2.0]
        assert editor._player.plays == 2
        assert editor._jkl_transport_rate == 2.0
        assert "2" in editor.current_speed_label.texts[-1]
        assert messages[-1] == "Shuttle forward 2x"

    def test_jkl_k_pauses_and_resets_transport_rate(self):
        from app.video_editor_window import VideoEditorWindow

        class _Player:
            def __init__(self):
                self.rates: list[float] = []
                self.pauses = 0
            def set_shuttle_rate(self, rate):
                self.rates.append(float(rate))
            def pause(self):
                self.pauses += 1

        messages: list[str] = []
        label = SimpleNamespace(setText=lambda _text: None)
        editor = SimpleNamespace(
            _player=_Player(),
            _jkl_transport_rate=8.0,
            current_speed_label=label,
            _is_text_focus=lambda: False,
            _flash_status=lambda msg: messages.append(msg),
        )

        assert VideoEditorWindow._apply_jkl_transport(editor, "k") is True
        assert editor._player.rates == [0.0]
        assert editor._player.pauses == 1
        assert editor._jkl_transport_rate == 0.0
        assert messages == ["Shuttle pause"]

    def test_jkl_j_reverse_jogs_back_and_accelerates(self):
        from app.video_editor_window import VideoEditorWindow

        class _Player:
            def __init__(self):
                self.pos = 5000
                self.rates: list[float] = []
                self.pauses = 0
            def set_shuttle_rate(self, rate):
                self.rates.append(float(rate))
            def pause(self):
                self.pauses += 1
            def position(self):
                return self.pos
            def duration(self):
                return 10_000
            def set_position(self, value):
                self.pos = int(value)

        visible: list[str] = []
        messages: list[str] = []
        editor = SimpleNamespace(
            _player=_Player(),
            _jkl_transport_rate=0.0,
            current_speed_label=SimpleNamespace(setText=lambda _text: None),
            _is_text_focus=lambda: False,
            _ensure_playhead_visible=lambda: visible.append("visible"),
            _flash_status=lambda msg: messages.append(msg),
        )

        assert VideoEditorWindow._apply_jkl_transport(editor, "j") is True
        assert editor._player.pos == 4000
        assert editor._jkl_transport_rate == -1.0

        assert VideoEditorWindow._apply_jkl_transport(editor, "j") is True
        assert editor._player.pos == 2000
        assert editor._jkl_transport_rate == -2.0
        assert editor._player.rates == [0.0, 0.0]
        assert editor._player.pauses == 2
        assert visible == ["visible", "visible"]
        assert messages[-1] == "Reverse jog -2x"

    def test_jkl_transport_ignores_text_focus(self):
        from app.video_editor_window import VideoEditorWindow

        editor = SimpleNamespace(
            _player=SimpleNamespace(),
            _jkl_transport_rate=0.0,
            _is_text_focus=lambda: True,
        )

        assert VideoEditorWindow._apply_jkl_transport(editor, "l") is False
        assert editor._jkl_transport_rate == 0.0

    def test_frame_step_uses_project_fps_and_pauses_transport(self):
        from app.video_editor_window import VideoEditorWindow

        class _Player:
            def __init__(self):
                self.pos = 1000
                self.rates: list[float] = []
                self.pauses = 0
            def set_shuttle_rate(self, rate):
                self.rates.append(float(rate))
            def pause(self):
                self.pauses += 1
            def position(self):
                return self.pos
            def duration(self):
                return 2000
            def set_position(self, value):
                self.pos = int(value)

        visible: list[str] = []
        messages: list[str] = []
        editor = SimpleNamespace(
            _player=_Player(),
            _project_settings={"fps": 25.0},
            _jkl_transport_rate=4.0,
            _is_text_focus=lambda: False,
            _ensure_playhead_visible=lambda: visible.append("visible"),
            _flash_status=lambda msg: messages.append(msg),
        )

        assert VideoEditorWindow._step_timeline_frames(editor, 1) is True
        assert editor._player.pos == 1040
        assert editor._player.rates == [0.0]
        assert editor._player.pauses == 1
        assert editor._jkl_transport_rate == 0.0
        assert visible == ["visible"]
        assert messages == ["Frame step +1"]

    def test_frame_step_clamps_to_project_bounds(self):
        from app.video_editor_window import VideoEditorWindow

        class _Player:
            def __init__(self):
                self.pos = 100
            def set_position(self, value):
                self.pos = int(value)
            def position(self):
                return self.pos
            def duration(self):
                return 500

        editor = SimpleNamespace(
            _player=_Player(),
            _project_settings={"fps": 30.0},
            _jkl_transport_rate=0.0,
            _is_text_focus=lambda: False,
        )

        assert VideoEditorWindow._step_timeline_frames(editor, -10) is True
        assert editor._player.pos == 0

    def test_frame_step_ignores_text_focus(self):
        from app.video_editor_window import VideoEditorWindow

        editor = SimpleNamespace(
            _player=SimpleNamespace(set_position=lambda _value: None),
            _jkl_transport_rate=0.0,
            _is_text_focus=lambda: True,
        )

        assert VideoEditorWindow._step_timeline_frames(editor, 1) is False
        assert editor._jkl_transport_rate == 0.0

    def test_timeline_zoom_clamps_to_editor_bounds(self):
        from app.video_editor_window import (
            DEFAULT_PX_PER_SEC,
            MAX_PX_PER_SEC,
            MIN_PX_PER_SEC,
            VideoEditorWindow,
        )

        assert VideoEditorWindow._clamp_timeline_zoom_px(-100) == MIN_PX_PER_SEC
        assert VideoEditorWindow._clamp_timeline_zoom_px(9999) == MAX_PX_PER_SEC
        assert VideoEditorWindow._clamp_timeline_zoom_px("bad") == DEFAULT_PX_PER_SEC
        assert VideoEditorWindow._clamp_timeline_zoom_px(42.5) == 42.5

    def test_timeline_scroll_for_visible_playhead_keeps_margin(self):
        from app.video_editor_window import VideoEditorWindow

        assert VideoEditorWindow._timeline_scroll_for_visible_playhead(
            current_scroll=100,
            viewport_width=500,
            content_x=260,
            max_scroll=1000,
        ) is None
        assert VideoEditorWindow._timeline_scroll_for_visible_playhead(
            current_scroll=300,
            viewport_width=500,
            content_x=320,
            max_scroll=1000,
            margin_px=80,
        ) == 240
        assert VideoEditorWindow._timeline_scroll_for_visible_playhead(
            current_scroll=0,
            viewport_width=500,
            content_x=480,
            max_scroll=1000,
            margin_px=80,
        ) == 60
        assert VideoEditorWindow._timeline_scroll_for_visible_playhead(
            current_scroll=900,
            viewport_width=500,
            content_x=1450,
            max_scroll=950,
            margin_px=80,
        ) == 950


# ---------------------------------------------------------------------------
#  HDR Phase 1: decoder factory dispatch
# ---------------------------------------------------------------------------


class TestDecoderFactoryDispatch:
    """``open_decoder`` picks ``CV2Decoder`` for SDR / no-info, and
    ``FFmpegToneMapDecoder`` for HDR. We stub both so the test never
    spawns ffmpeg or opens a real cv2 stream — we just verify the
    dispatch logic + fallback chain."""

    def setup_method(self):
        from app import video_decoder
        self._mod = video_decoder

        # Save the originals so other tests aren't affected.
        self._orig_cv = video_decoder.CV2Decoder
        self._orig_ff = video_decoder.FFmpegToneMapDecoder

    def teardown_method(self):
        self._mod.CV2Decoder = self._orig_cv
        self._mod.FFmpegToneMapDecoder = self._orig_ff

    def _make_stub(self, *, opens: bool, label: str):
        class _Stub:
            def __init__(self, path):
                self.path = path
                self.label = label
            def open(self_inner):
                return opens
            def release(self_inner):
                pass
        return _Stub

    def test_dispatch_to_cv2_when_no_hdr_info(self):
        self._mod.CV2Decoder = self._make_stub(opens=True, label="cv2")
        d = self._mod.open_decoder("/x.mp4", hdr_info=None)
        assert d is not None
        assert d.label == "cv2"

    def test_dispatch_to_cv2_when_sdr(self):
        from app.hdr_probe import HDRInfo
        self._mod.CV2Decoder = self._make_stub(opens=True, label="cv2")
        d = self._mod.open_decoder(
            "/x.mp4", hdr_info=HDRInfo(is_hdr=False, transfer="bt709"),
        )
        assert d.label == "cv2"

    def test_dispatch_to_ffmpeg_when_hdr(self):
        from app.hdr_probe import HDRInfo
        self._mod.CV2Decoder = self._make_stub(opens=True, label="cv2")
        self._mod.FFmpegToneMapDecoder = self._make_stub(
            opens=True, label="ffmpeg",
        )
        d = self._mod.open_decoder(
            "/x.mp4", hdr_info=HDRInfo(is_hdr=True, transfer="smpte2084"),
        )
        assert d.label == "ffmpeg"

    def test_falls_back_to_cv2_when_ffmpeg_open_fails(self):
        from app.hdr_probe import HDRInfo
        self._mod.CV2Decoder = self._make_stub(opens=True, label="cv2")
        self._mod.FFmpegToneMapDecoder = self._make_stub(
            opens=False, label="ffmpeg",
        )
        d = self._mod.open_decoder(
            "/x.mp4", hdr_info=HDRInfo(is_hdr=True, transfer="smpte2084"),
        )
        # ffmpeg failed — cv2 fallback returned.
        assert d.label == "cv2"

    def test_returns_none_when_everything_fails(self):
        self._mod.CV2Decoder = self._make_stub(opens=False, label="cv2")
        self._mod.FFmpegToneMapDecoder = self._make_stub(
            opens=False, label="ffmpeg",
        )
        d = self._mod.open_decoder("/x.mp4", hdr_info=None)
        assert d is None

    def test_uses_fresh_existing_proxy_for_preview_decode(self, tmp_path):
        source = tmp_path / "clip.mp4"
        source.write_bytes(b"source")
        proxy_dir = tmp_path / "proxies"
        proxy_dir.mkdir()
        proxy = proxy_dir / "clip_proxy.mp4"
        proxy.write_bytes(b"proxy")

        self._mod.CV2Decoder = self._make_stub(opens=True, label="cv2")
        d = self._mod.open_decoder(source, hdr_info=None)

        assert d is not None
        assert Path(d.path) == proxy


# ---------------------------------------------------------------------------
#  HDR Phase 2: build_filter_graph tonemap insertion
# ---------------------------------------------------------------------------


class TestExportFilterGraphHDR:
    """``build_filter_graph`` should insert a tonemap chain for HDR
    sources so the exported MP4 matches the SDR preview the user
    saw. SDR sources must produce a byte-equivalent graph to the
    pre-Phase-2 version (no extra filter)."""

    def setup_method(self):
        from app.video_exporter import build_filter_graph
        self._fn = build_filter_graph

    def test_no_hdr_info_omits_tonemap(self):
        graph = self._fn([(0, 1000, 1.0)], hdr_info=None)
        assert "tonemap" not in graph
        assert "zscale" not in graph

    def test_sdr_hdr_info_omits_tonemap(self):
        from app.hdr_probe import HDRInfo
        graph = self._fn(
            [(0, 1000, 1.0)],
            hdr_info=HDRInfo(is_hdr=False, transfer="bt709"),
        )
        assert "tonemap" not in graph

    def test_hdr_hdr_info_inserts_tonemap(self):
        from app.hdr_probe import HDRInfo
        graph = self._fn(
            [(0, 1000, 1.0)],
            hdr_info=HDRInfo(is_hdr=True, transfer="smpte2084"),
        )
        # Tonemap must appear after concat (so all clips are
        # tonemapped together) and before any color grade overlay.
        assert "tonemap=hable" in graph
        assert "zscale=t=linear" in graph
        # Pixel format at the tonemap output is yuv420p so libx264
        # / libvpx / libaom can encode without extra ``-pix_fmt``.
        assert "format=yuv420p" in graph
        # The chain should appear after the ``[cv0]`` concat label.
        cv0_pos = graph.find("[cv0]")
        tonemap_pos = graph.find("tonemap=hable")
        assert cv0_pos != -1 and tonemap_pos != -1 and tonemap_pos > cv0_pos

    def test_hdr_tonemap_label_chains_to_grade(self):
        # When BOTH tonemap AND a (mock) color_grade run, the grade
        # input must be the tonemap output ``[cvtm]``, not raw concat.
        from app.hdr_probe import HDRInfo
        # A truthy color_grade-like object whose ``to_ffmpeg_filters``
        # the function calls — provide a stub via a fake module.
        class _StubGrade:
            def __init__(self):
                self.applied = False
        # ``to_ffmpeg_filters`` is imported INSIDE build_filter_graph,
        # so we test by checking the graph string mentions [cvtm] as
        # an input to whatever comes next. Without a real grade we
        # just verify the tonemap label is referenced as ``current``
        # — i.e. the literal string ``[cvtm]`` appears at least once
        # outside the tonemap definition itself.
        graph = self._fn(
            [(0, 1000, 1.0)],
            hdr_info=HDRInfo(is_hdr=True, transfer="smpte2084"),
        )
        # ``[cvtm]`` is the OUTPUT of the tonemap node. Its input is
        # ``[cv0]``. If anything follows, it should chain from
        # ``[cvtm]`` rather than re-using ``[cv0]``. Single-segment
        # SDR-no-overlays graph has no follow-up step, but we at
        # least verify the label was emitted.
        assert "[cvtm]" in graph


class TestExportFilterGraphHDRPassthrough:
    """Phase 2b: ``hdr_passthrough=True`` skips the SDR tonemap and
    pins the chain to 10-bit BT.2020 PQ output instead."""

    def setup_method(self):
        from app.video_exporter import build_filter_graph
        self._fn = build_filter_graph

    def test_passthrough_skips_tonemap(self):
        from app.hdr_probe import HDRInfo
        graph = self._fn(
            [(0, 1000, 1.0)],
            hdr_info=HDRInfo(is_hdr=True, transfer="smpte2084"),
            hdr_passthrough=True,
        )
        assert "tonemap=hable" not in graph
        # The 10-bit output format is pinned so the encoder receives
        # ``yuv420p10le`` regardless of source upstream defaults.
        assert "format=yuv420p10le" in graph
        # The new label this branch emits.
        assert "[cvhdr]" in graph

    def test_passthrough_irrelevant_for_sdr(self):
        from app.hdr_probe import HDRInfo
        graph = self._fn(
            [(0, 1000, 1.0)],
            hdr_info=HDRInfo(is_hdr=False, transfer="bt709"),
            hdr_passthrough=True,    # ignored for SDR sources
        )
        assert "[cvhdr]" not in graph
        assert "format=yuv420p10le" not in graph


class TestExportFormatHDRArgs:
    """``ExportFormat.build_video_args`` produces the libx265 HDR
    encoder args when ``hdr_passthrough=True`` is passed."""

    def setup_method(self):
        from app.video_exporter import EXPORT_FORMATS
        self._mp4 = next(f for f in EXPORT_FORMATS if f.id == "mp4")

    def test_default_path_is_libx264_8bit(self):
        from app.video_exporter import get_quality_preset
        args = self._mp4.build_video_args(get_quality_preset("standard"))
        assert "-c:v" in args
        cv_idx = args.index("-c:v")
        assert args[cv_idx + 1] == "libx264"
        assert "yuv420p" in args
        assert "yuv420p10le" not in args

    def test_hdr_passthrough_switches_to_libx265_10bit(self):
        from app.video_exporter import get_quality_preset
        args = self._mp4.build_video_args(
            get_quality_preset("standard"), hdr_passthrough=True,
        )
        cv_idx = args.index("-c:v")
        assert args[cv_idx + 1] == "libx265"
        assert "-pix_fmt" in args
        pix_idx = args.index("-pix_fmt")
        assert args[pix_idx + 1] == "yuv420p10le"
        # Container-level colour metadata so non-x265 players honour HDR.
        assert "-color_primaries" in args
        cp_idx = args.index("-color_primaries")
        assert args[cp_idx + 1] == "bt2020"
        assert "-color_trc" in args
        ct_idx = args.index("-color_trc")
        assert args[ct_idx + 1] == "smpte2084"
        # ``hvc1`` tag is the QuickTime-friendly variant.
        assert "-tag:v" in args
        tag_idx = args.index("-tag:v")
        assert args[tag_idx + 1] == "hvc1"
        # x265 params should carry the colorprim/transfer/matrix info
        # too (so every IDR is self-describing).
        assert "-x265-params" in args
        xp_idx = args.index("-x265-params")
        params = args[xp_idx + 1]
        assert "colorprim=bt2020" in params
        assert "transfer=smpte2084" in params
        assert "colormatrix=bt2020nc" in params


# ---------------------------------------------------------------------------
#  Undo / redo HistoryStack
# ---------------------------------------------------------------------------


class TestHistoryStack:
    """The bounded stack that backs Ctrl+Z / Ctrl+Shift+Z."""

    def setup_method(self):
        from app.history import HistoryStack
        self._cls = HistoryStack

    def test_empty_stack_cant_undo_or_redo(self):
        h = self._cls(max_undo_steps=10)
        assert not h.can_undo()
        assert not h.can_redo()
        assert h.undo() is None
        assert h.redo() is None

    def test_push_then_undo_returns_prior(self):
        h = self._cls()
        h.push("a", "initial")
        h.push("b", "edit 1")
        h.push("c", "edit 2")
        # 3 entries, cursor at 2 (= "c" current). Undo → "b".
        assert h.can_undo() and not h.can_redo()
        assert h.undo() == "b"
        assert h.can_undo() and h.can_redo()
        assert h.undo() == "a"
        assert not h.can_undo() and h.can_redo()
        assert h.undo() is None  # nothing further

    def test_redo_walks_back_forward(self):
        h = self._cls()
        for s in ("a", "b", "c"):
            h.push(s)
        h.undo()  # → b (cursor 1)
        h.undo()  # → a (cursor 0)
        assert h.redo() == "b"
        assert h.redo() == "c"
        assert h.redo() is None

    def test_push_after_undo_drops_redo_tail(self):
        h = self._cls()
        for s in ("a", "b", "c"):
            h.push(s)
        h.undo()  # cursor at 1 ("b")
        h.push("d", "branch")
        # "c" should be dropped — redo at this point is None.
        assert not h.can_redo()
        # Walk back to confirm the branch state is intact.
        assert h.undo() == "b"
        assert h.undo() == "a"

    def test_max_undo_steps_caps_history_depth(self):
        # 10 steps means up to 11 entries (initial + 10 changes).
        h = self._cls(max_undo_steps=10)
        for i in range(20):
            h.push(f"step{i}")
        assert h.depth() == 11
        # Latest entry is current → can_undo for 10 steps.
        steps = 0
        while h.can_undo():
            h.undo()
            steps += 1
        assert steps == 10

    def test_labels_round_trip(self):
        h = self._cls()
        h.push("a", "alpha")
        h.push("b", "beta")
        assert h.labels() == ["alpha", "beta"]

    def test_undo_redo_labels_follow_cursor(self):
        h = self._cls()
        h.push("a", "initial")
        h.push("b", "trim clip")
        h.push("c", "apply preset")

        assert h.undo_label() == "apply preset"
        assert h.redo_label() == ""
        assert h.undo() == "b"
        assert h.undo_label() == "trim clip"
        assert h.redo_label() == "apply preset"
        assert h.redo() == "c"
        assert h.undo_label() == "apply preset"
        assert h.redo_label() == ""

    def test_duplicate_snapshot_does_not_consume_undo_depth(self):
        h = self._cls(max_undo_steps=10)
        h.push({"clips": [1]}, "initial")
        h.push({"clips": [1]}, "no-op drag")
        h.push({"clips": [1, 2]}, "real edit")

        assert h.depth() == 2
        assert h.labels() == ["initial", "real edit"]
        assert h.undo() == {"clips": [1]}


class TestEditorSnapshot:
    """``capture_editor_snapshot`` / ``apply_editor_snapshot`` use a
    duck-typed ``editor`` so we can drive them with a stub instead of
    spinning up the real Qt editor."""

    def setup_method(self):
        from app import history
        self._h = history

    def _stub_editor(self):
        from app.video_editor_window import VideoTrack
        from app.overlay_layer import SubtitleLayer
        from app.subtitles import Subtitle

        class _StubPanel:
            class _Sig:
                def emit(self_inner): pass
            subtitles_changed = _Sig()
            def __init__(self_inner):
                self_inner.layer = SubtitleLayer()
            def _refresh_list(self_inner): pass

        class _Stub:
            def __init__(self_inner):
                self_inner._tracks = [VideoTrack(id=0)]
                self_inner._audio_tracks = []
                self_inner._subtitle_panel = _StubPanel()
                self_inner._active_track_id = 0
                self_inner._next_track_id = 1
                self_inner._next_audio_clip_id = 1
                self_inner._track_rows = {}
                self_inner._audio_rows = {}
                self_inner._selected_clips = []
                self_inner.selection_broadcasts = 0
            def _set_active_track(self_inner, tid):
                self_inner._active_track_id = tid
            def _broadcast_clip_selection(self_inner):
                self_inner.selection_broadcasts += 1

        return _Stub(), Subtitle

    def test_capture_then_restore_roundtrip(self):
        ed, Subtitle = self._stub_editor()
        # Mutate before capture: add a subtitle, set selection.
        ed._subtitle_panel.layer.add(Subtitle(0, 1000, "hello"))
        ed._tracks[0].selection_start_ms = 500
        ed._tracks[0].selection_end_ms = 800

        snap = self._h.capture_editor_snapshot(ed)

        # Mutate after capture — restore should undo all of it.
        ed._tracks[0].selection_start_ms = 0
        ed._tracks[0].selection_end_ms = 0
        ed._subtitle_panel.layer.clear()

        self._h.apply_editor_snapshot(ed, snap)

        assert ed._tracks[0].selection_start_ms == 500
        assert ed._tracks[0].selection_end_ms == 800
        assert len(ed._subtitle_panel.layer.items()) == 1
        assert ed._subtitle_panel.layer.items()[0].text == "hello"

    def test_snapshot_isolated_from_subsequent_mutations(self):
        ed, Subtitle = self._stub_editor()
        ed._subtitle_panel.layer.add(Subtitle(0, 1000, "v1"))
        snap = self._h.capture_editor_snapshot(ed)

        # Mutate the live state *after* capture; snapshot must be
        # immune (deep-copied) so it still represents v1.
        live_sub = ed._subtitle_panel.layer.items()[0]
        live_sub.text = "v2-mutated"

        # Restoring should give back "v1".
        ed._subtitle_panel.layer.clear()
        self._h.apply_editor_snapshot(ed, snap)
        assert ed._subtitle_panel.layer.items()[0].text == "v1"

    def test_snapshot_drops_clip_thumbnail_qt_render_cache(self):
        from app.timeline_model import VideoClip

        QPixmap = type(
            "QPixmap",
            (),
            {
                "__module__": "PySide6.QtGui",
                "__getstate__": lambda self: (_ for _ in ()).throw(TypeError("cannot pickle QPixmap")),
            },
        )
        ed, _ = self._stub_editor()
        clip = VideoClip(id=31)
        clip.thumbnails = [QPixmap()]
        ed._tracks[0].clips = [clip]

        snap = self._h.capture_editor_snapshot(ed)

        assert snap["video_tracks"][0]["clips"][0].thumbnails == []

    def test_apply_restores_deleted_video_track(self):
        ed, _ = self._stub_editor()
        snap = self._h.capture_editor_snapshot(ed)
        # Drop the track from the editor — applying the snapshot
        # should NOT crash, just silently skip the missing track.
        ed._tracks = []
        # Should be a no-op (no exception raised).
        self._h.apply_editor_snapshot(ed, snap)
        assert [track.id for track in ed._tracks] == [0]
        assert ed._active_track_id == 0

    def test_apply_removes_tracks_created_after_snapshot(self):
        from app.video_editor_window import VideoTrack

        ed, _ = self._stub_editor()
        snap = self._h.capture_editor_snapshot(ed)

        ed._tracks.append(VideoTrack(id=99))
        ed._active_track_id = 99

        self._h.apply_editor_snapshot(ed, snap)

        assert [track.id for track in ed._tracks] == [0]
        assert ed._active_track_id == 0

    def test_apply_restores_deleted_audio_track_and_active_id(self):
        from app.audio_tracks import AudioClip, AudioTrack

        ed, _ = self._stub_editor()
        clip = AudioClip(id=12, duration_ms=1000, trim_end_ms=1000)
        ed._audio_tracks = [AudioTrack(id=7, clips=[clip], label="Voice")]
        ed._active_track_id = 7
        snap = self._h.capture_editor_snapshot(ed)

        ed._audio_tracks = []
        ed._active_track_id = None

        self._h.apply_editor_snapshot(ed, snap)

        assert [track.id for track in ed._audio_tracks] == [7]
        assert ed._audio_tracks[0].label == "Voice"
        assert ed._audio_tracks[0].clips[0].id == 12
        assert ed._active_track_id == 7
        assert ed._next_track_id == 8
        assert ed._next_audio_clip_id == 13

    def test_snapshot_restores_clip_selection_and_filters_dead_clips(self):
        ed, _ = self._stub_editor()
        ed._tracks[0].clips = [
            SimpleNamespace(id=1, timeline_in_ms=0),
            SimpleNamespace(id=2, timeline_in_ms=1000),
        ]
        ed._selected_clips = [(0, 1), (0, 2)]

        snap = self._h.capture_editor_snapshot(ed)

        ed._tracks[0].clips = [SimpleNamespace(id=1, timeline_in_ms=0)]
        ed._selected_clips = []

        self._h.apply_editor_snapshot(ed, snap)

        assert ed._selected_clips == [(0, 1), (0, 2)]
        assert ed.selection_broadcasts == 1

        stale_snap = self._h.capture_editor_snapshot(ed)
        stale_snap["selected_clips"] = [(0, 1), (0, 999)]

        self._h.apply_editor_snapshot(ed, stale_snap)

        assert ed._selected_clips == [(0, 1)]
        assert ed.selection_broadcasts == 2

    def test_snapshot_restores_actor_lanes_markers_zoom_and_playhead(self):
        ed, _ = self._stub_editor()

        class _Player:
            def __init__(self):
                self.pos = 1200
                self.spine = None
                self.live2d = None
            def position(self):
                return self.pos
            def set_position(self, value):
                self.pos = int(value)
            def set_spine_actor_tracks(self, tracks):
                self.spine = tracks
            def set_live2d_actor_tracks(self, tracks):
                self.live2d = tracks

        ed._player = _Player()
        ed._timeline_markers = [{"ms": 500, "color": "#ff6600", "label": "hit"}]
        ed._spine_actor_tracks = [{"clips": [{"start_ms": 10}]}]
        ed._live2d_actor_tracks = [{"clips": [{"start_ms": 20}], "blends": []}]
        ed._px_per_sec = 88.0
        ed._track_rows = {}
        ed._audio_rows = {}
        ed._actor_lane_rows = []
        ed._live2d_lane_rows = []
        ed.marker_syncs = 0
        ed.player_refreshes = 0

        def _sync():
            ed.marker_syncs += 1

        def _refresh_player():
            ed.player_refreshes += 1

        ed._sync_markers_to_ruler = _sync
        ed._refresh_player_tracks = _refresh_player

        snap = self._h.capture_editor_snapshot(ed)

        ed._timeline_markers = []
        ed._spine_actor_tracks = []
        ed._live2d_actor_tracks = []
        ed._px_per_sec = 10.0
        ed._player.pos = 9999

        self._h.apply_editor_snapshot(ed, snap)

        assert ed._timeline_markers == [{"ms": 500, "color": "#ff6600", "label": "hit"}]
        assert ed._spine_actor_tracks == [{"clips": [{"start_ms": 10}]}]
        assert ed._live2d_actor_tracks == [{"clips": [{"start_ms": 20}], "blends": []}]
        assert ed._px_per_sec == 88.0
        assert ed._player.pos == 1200
        assert ed._player.spine == ed._spine_actor_tracks
        assert ed._player.live2d == ed._live2d_actor_tracks
        assert ed.marker_syncs == 1
        assert ed.player_refreshes == 1
