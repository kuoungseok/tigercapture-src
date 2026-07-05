from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
from PySide6.QtCore import Qt

from app.project_player import ProjectPlayer, _screenstudio_owner_for_preview
from app.simple_video_player import PlayerState


class _FakeDecoder:
    fps = 10.0
    total_frames = 25
    frame_size = (2, 2)

    def open(self) -> bool:
        return True

    def seek_to_frame(self, _idx: int) -> None:
        pass

    def read_rgb(self):
        return np.zeros((2, 2, 3), dtype=np.uint8)

    def release(self) -> None:
        pass


class _CountingDecoder(_FakeDecoder):
    def __init__(self):
        self.read_count = 0

    def read_rgb(self):
        self.read_count += 1
        return super().read_rgb()


def test_single_source_refresh_syncs_duration_before_clip_view(monkeypatch, tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"placeholder")

    calls: list[Path] = []

    def fake_open_decoder(path, hdr_info=None):
        calls.append(Path(path))
        return _FakeDecoder()

    monkeypatch.setattr("app.video_decoder.open_decoder", fake_open_decoder)
    track = SimpleNamespace(
        id=1,
        source_path=source,
        duration_ms=0,
        offset_ms=0,
        cuts=[],
        clips=[],
        clips_explicit=False,
        pip_enabled=False,
    )
    player = ProjectPlayer()
    try:
        player.refresh_tracks([track])
        assert calls == [source]
        assert track.duration_ms == 2500
        assert player.duration() == 2500
        assert len(player._clips_view[1]) == 1
        assert player._active_clip_at(0) is not None
    finally:
        player.release()


def test_refresh_tracks_passes_project_preview_decode_height(monkeypatch, tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"placeholder")

    calls: list[dict] = []

    def fake_open_decoder(path, hdr_info=None, preview_height=None):
        calls.append({
            "path": Path(path),
            "hdr_info": hdr_info,
            "preview_height": preview_height,
        })
        return _FakeDecoder()

    monkeypatch.setattr("app.video_decoder.open_decoder", fake_open_decoder)
    track = SimpleNamespace(
        id=1,
        source_path=source,
        duration_ms=0,
        offset_ms=0,
        cuts=[],
        clips=[],
        clips_explicit=False,
        pip_enabled=False,
    )
    player = ProjectPlayer()
    try:
        player.set_project_settings({"preview_decode_height": 540})

        player.refresh_tracks([track])

        assert calls == [{
            "path": source,
            "hdr_info": None,
            "preview_height": 540,
        }]
    finally:
        player.release()


def test_preview_render_does_not_import_editor_window_for_zoom_helpers(monkeypatch, tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"placeholder")

    def fake_open_decoder(path, hdr_info=None, preview_height=None):
        return _FakeDecoder()

    monkeypatch.setattr("app.video_decoder.open_decoder", fake_open_decoder)
    monkeypatch.delitem(sys.modules, "app.video_editor_window", raising=False)
    track = SimpleNamespace(
        id=1,
        source_path=source,
        duration_ms=0,
        offset_ms=0,
        cuts=[],
        clips=[],
        clips_explicit=False,
        pip_enabled=False,
    )
    player = ProjectPlayer()
    try:
        player.refresh_tracks([track])

        assert "app.video_editor_window" not in sys.modules
    finally:
        player.release()


def test_repeated_same_position_uses_last_preview_frame_cache(monkeypatch, tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"placeholder")
    decoder = _CountingDecoder()

    def fake_open_decoder(path, hdr_info=None, preview_height=None):
        return decoder

    monkeypatch.setattr("app.video_decoder.open_decoder", fake_open_decoder)
    track = SimpleNamespace(
        id=1,
        source_path=source,
        duration_ms=0,
        offset_ms=0,
        cuts=[],
        clips=[],
        clips_explicit=False,
        pip_enabled=False,
    )
    player = ProjectPlayer()
    try:
        player.refresh_tracks([track])
        assert decoder.read_count == 1

        player.set_position(0)

        assert decoder.read_count == 1
    finally:
        player.release()


def test_refresh_tracks_can_skip_immediate_preview_render(monkeypatch, tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"placeholder")
    decoder = _CountingDecoder()

    def fake_open_decoder(path, hdr_info=None, preview_height=None):
        return decoder

    monkeypatch.setattr("app.video_decoder.open_decoder", fake_open_decoder)
    track = SimpleNamespace(
        id=1,
        source_path=source,
        duration_ms=0,
        offset_ms=0,
        cuts=[],
        clips=[],
        clips_explicit=False,
        pip_enabled=False,
    )
    player = ProjectPlayer()
    try:
        player.refresh_tracks([track], render_immediately=False)

        assert player.duration() == 2500
        assert decoder.read_count == 0

        player.set_position(0)

        assert decoder.read_count == 1
    finally:
        player.release()


def test_live2d_actor_tracks_prewarm_renderer(monkeypatch):
    import app.live2d.warmup as warmup

    calls: list[tuple] = []

    class _FakeLive2DClip:
        model_path = "avatar.model3.json"
        start_ms = 100
        duration_ms = 500

        def render_frame(self, width, height, pos_ms):
            calls.append(("render", int(width), int(height), int(pos_ms)))
            return None

        def reset(self):
            calls.append(("reset",))

    monkeypatch.setattr(warmup, "warm_live2d_runtime", lambda: (True, "ready"))
    player = ProjectPlayer()
    try:
        player.set_live2d_actor_tracks([SimpleNamespace(clips=[_FakeLive2DClip()])])
    finally:
        player.release()

    assert calls == [("render", 1280, 720, 101), ("reset",)]


def test_live2d_actor_tracks_prewarm_can_be_disabled(monkeypatch):
    import app.live2d.warmup as warmup

    calls: list[tuple] = []

    class _FakeLive2DClip:
        model_path = "avatar.model3.json"
        start_ms = 0
        duration_ms = 500

        def render_frame(self, width, height, pos_ms):
            calls.append(("render", int(width), int(height), int(pos_ms)))
            return None

    monkeypatch.setenv("TIGERCAPTURE_DISABLE_LIVE2D_PREWARM", "1")
    monkeypatch.setattr(warmup, "warm_live2d_runtime", lambda: (True, "ready"))
    player = ProjectPlayer()
    try:
        player.set_live2d_actor_tracks([SimpleNamespace(clips=[_FakeLive2DClip()])])
    finally:
        player.release()

    assert calls == []


def test_play_until_previews_range_and_restores_playhead(monkeypatch, tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"placeholder")

    def fake_open_decoder(path, hdr_info=None, preview_height=None):
        return _FakeDecoder()

    monkeypatch.setattr("app.video_decoder.open_decoder", fake_open_decoder)
    track = SimpleNamespace(
        id=1,
        source_path=source,
        duration_ms=0,
        offset_ms=0,
        cuts=[],
        clips=[],
        clips_explicit=False,
        pip_enabled=False,
    )
    player = ProjectPlayer()
    try:
        player.refresh_tracks([track])
        player.set_position(0)

        player.play_until(90, return_to_ms=0)
        player._tick()
        player._tick()
        player._tick()

        assert player.state() is PlayerState.PAUSED
        assert player.position() == 0
    finally:
        player.release()


def test_window_move_guard_relaxes_and_restores_preview_timer():
    player = ProjectPlayer()
    try:
        player._timer.setTimerType(Qt.TimerType.PreciseTimer)
        player._timer.setInterval(17)

        player.set_window_move_guard(True)

        assert player._window_move_guard_active is True
        assert player._timer.timerType() == Qt.TimerType.CoarseTimer
        assert player._timer.interval() >= 100

        player.set_window_move_guard(False)

        assert player._window_move_guard_active is False
        assert player._timer.timerType() == Qt.TimerType.PreciseTimer
        assert player._timer.interval() == 17
    finally:
        player.release()


def test_alpha_composite_rgba_array_over_rgb():
    base = np.zeros((2, 2, 3), dtype=np.uint8)
    overlay = np.zeros((2, 2, 4), dtype=np.uint8)
    overlay[0, 1] = [255, 0, 0, 128]
    overlay[1, 0] = [0, 255, 0, 255]

    out = ProjectPlayer._alpha_composite_rgba_array(base, overlay)

    np.testing.assert_array_equal(out[0, 0], [0, 0, 0])
    np.testing.assert_array_equal(out[0, 1], [128, 0, 0])
    np.testing.assert_array_equal(out[1, 0], [0, 255, 0])


def test_screenstudio_preview_owner_falls_back_to_track_cursor_metadata():
    clip = SimpleNamespace(
        cursor_events=[],
        screenstudio_polish={},
        source_path=Path("demo.mp4"),
        source_duration_ms=3000,
        source_in_ms=0,
        source_out_ms=3000,
    )
    track = SimpleNamespace(
        cursor_events=[{"t_ms": 120, "x_norm": 0.25, "y_norm": 0.4, "kind": "click"}],
        screenstudio_polish={"cursor": {"click_ring_color": "#FF7A59"}},
    )

    owner = _screenstudio_owner_for_preview(clip, track)

    assert owner is not clip
    assert owner.cursor_events == track.cursor_events
    assert owner.screenstudio_polish == track.screenstudio_polish
    assert owner.source_path == clip.source_path


def test_export_clip_effect_snapshot_falls_back_to_track_cursor_metadata():
    from app.timeline_model import VideoClip, VideoTrack
    from app.video_editor_window import VideoEditorWindow

    clip = VideoClip(
        id=1,
        source_path=Path("demo.mp4"),
        source_duration_ms=2000,
        timeline_in_ms=0,
        source_in_ms=0,
        source_out_ms=2000,
    )
    track = VideoTrack(id=1, clips=[clip])
    track.cursor_events = [{"t_ms": 100, "x_norm": 0.2, "y_norm": 0.3, "kind": "click"}]
    track.screenstudio_polish = {"cursor": {"click_ring_color": "#FF7A59"}}

    snapshots = VideoEditorWindow._snapshot_clip_effects_for_export(track)

    assert snapshots is not None
    owner = snapshots[0]
    assert owner.cursor_events == track.cursor_events
    assert owner.screenstudio_polish == track.screenstudio_polish


def test_spine_overlay_rgba_uses_array_renderer_path(monkeypatch):
    class _Clip:
        skel_path = "fake.skel"
        atlas_path = "fake.atlas"
        texture_path = "fake.png"
        anim_name = "idle"
        skin_name = "default"
        start_ms = 0
        duration_ms = 1000
        loop = True
        pos_x = 0.5
        pos_y = 0.5
        scale = 1.0

        @property
        def end_ms(self):
            return self.start_ms + self.duration_ms

        def render_frame_rgba(self, width, height, pos_ms, animated=True, fast_preview=False, use_gl=True):
            arr = np.zeros((max(1, int(height)), max(1, int(width)), 4), dtype=np.uint8)
            arr[:, :] = [0, 0, 255, 255]
            return arr

    class _Track:
        def __init__(self):
            self.clip = _Clip()

        def clips_at(self, pos_ms):
            return [self.clip]

    monkeypatch.setenv("TIGERCAPTURE_SPINE_ARRAY_COMPOSITOR", "1")
    player = ProjectPlayer()
    try:
        player.set_spine_actor_tracks([_Track()])
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)

        out = player._composite_spine_actors(rgb, 0, animate=True)

        assert out.shape == rgb.shape
        np.testing.assert_array_equal(out[0, 0], [0, 0, 255])
    finally:
        player.release()


def test_spine_preview_cache_pos_quantizes_by_default(monkeypatch):
    monkeypatch.delenv("TIGERCAPTURE_SPINE_PREVIEW_FPS", raising=False)

    assert ProjectPlayer._spine_preview_cache_pos_ms(1000, animate=False) == 1000
    assert ProjectPlayer._spine_preview_cache_pos_ms(1009, animate=True) == 1008

    monkeypatch.setenv("TIGERCAPTURE_SPINE_PREVIEW_FPS", "0")
    assert ProjectPlayer._spine_preview_cache_pos_ms(1009, animate=True) == 1009


def test_complex_spine_preview_uses_lower_cache_fps(monkeypatch):
    class _Clip:
        def preview_complexity_score(self):
            return 500

    monkeypatch.setenv("TIGERCAPTURE_SPINE_PREVIEW_FPS", "25")
    monkeypatch.setenv("TIGERCAPTURE_SPINE_COMPLEX_PREVIEW_FPS", "10")
    monkeypatch.setenv("TIGERCAPTURE_SPINE_COMPLEX_THRESHOLD", "100")
    player = ProjectPlayer()
    try:
        assert player._spine_preview_cache_pos_ms_for_active(1049, True, []) == 1040
        assert player._spine_preview_cache_pos_ms_for_active(1049, True, [_Clip()]) == 1000
    finally:
        player.release()


def test_spine_preview_render_size_drops_when_live2d_overlap(monkeypatch):
    class _SpineClip:
        pass

    class _Live2DClip:
        start_ms = 100
        end_ms = 500

    class _Live2DTrack:
        clips = [_Live2DClip()]

    monkeypatch.delenv("TIGERCAPTURE_SPINE_PREVIEW_SCALE", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_SPINE_COMPLEX_PREVIEW_SCALE", raising=False)
    player = ProjectPlayer()
    try:
        player.set_live2d_actor_tracks([_Live2DTrack()])

        normal = player._spine_preview_render_size_for_active(1280, 720, 50, [_SpineClip()], True)
        overlapped = player._spine_preview_render_size_for_active(1280, 720, 200, [_SpineClip()], True)
        paused = player._spine_preview_render_size_for_active(1280, 720, 200, [_SpineClip()], False)

        assert normal == (480, 270)
        assert overlapped == (320, 180)
        assert paused == (640, 360)
    finally:
        player.release()


def test_spine_preview_render_size_drops_for_complex_clip(monkeypatch):
    class _SpineClip:
        def preview_complexity_score(self):
            return 1000

    monkeypatch.delenv("TIGERCAPTURE_SPINE_PREVIEW_SCALE", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_SPINE_PLAYBACK_PREVIEW_SCALE", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_SPINE_COMPLEX_PREVIEW_SCALE", raising=False)
    monkeypatch.setenv("TIGERCAPTURE_SPINE_COMPLEX_THRESHOLD", "900")
    player = ProjectPlayer()
    try:
        assert player._spine_preview_render_size_for_active(1280, 720, 50, [_SpineClip()], True) == (320, 180)
        assert player._spine_preview_render_size_for_active(1280, 720, 50, [_SpineClip()], False) == (640, 360)
    finally:
        player.release()


def test_spine_preview_render_size_uses_playback_scale_for_simple_clip(monkeypatch):
    class _SpineClip:
        pass

    monkeypatch.delenv("TIGERCAPTURE_SPINE_PREVIEW_SCALE", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_SPINE_PLAYBACK_PREVIEW_SCALE", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_SPINE_COMPLEX_PREVIEW_SCALE", raising=False)
    player = ProjectPlayer()
    try:
        assert player._spine_preview_render_size_for_active(1280, 720, 50, [_SpineClip()], True) == (480, 270)
        assert player._spine_preview_render_size_for_active(1280, 720, 50, [_SpineClip()], False) == (640, 360)
    finally:
        player.release()


def test_project_player_emits_qimage_by_default():
    player = ProjectPlayer()
    frames = []
    gpu_frames = []
    player.frame_ready.connect(lambda qimg: frames.append(qimg))
    player.gpu_frame_ready.connect(lambda rgb, grade: gpu_frames.append((rgb, grade)))
    try:
        rgb = np.zeros((4, 6, 3), dtype=np.uint8)

        player._emit_rgb_frame(rgb, None, "test=1", 0.0)

        assert len(gpu_frames) == 1
        assert len(frames) == 1
        assert frames[0].width() == 6
        assert frames[0].height() == 4
    finally:
        player.release()


def test_project_player_can_skip_qimage_for_gpu_only_preview():
    player = ProjectPlayer()
    frames = []
    gpu_frames = []
    player.frame_ready.connect(lambda qimg: frames.append(qimg))
    player.gpu_frame_ready.connect(lambda rgb, grade: gpu_frames.append((rgb, grade)))
    try:
        player.set_qimage_frame_enabled(False)
        rgb = np.zeros((4, 6, 3), dtype=np.uint8)

        player._emit_rgb_frame(rgb, None, "test=1", 0.0)

        assert len(gpu_frames) == 1
        assert frames == []
    finally:
        player.release()


def test_project_player_emits_combined_gpu_preview_metadata_without_dropping_grade():
    player = ProjectPlayer()
    gpu_frames = []
    player.gpu_frame_ready.connect(lambda rgb, grade: gpu_frames.append((rgb, grade)))
    try:
        player.set_qimage_frame_enabled(False)
        rgb = np.zeros((4, 6, 3), dtype=np.uint8)
        grade = object()
        clip_effects = {"filters": {"brightness": 0.1}, "chroma": None}
        spine_items = [{"anim_name": "idle", "time": 0.25}]
        ar_pbr_items = [{"kind": "ndc_color_triangles", "triangle_count": 1}]

        player._emit_rgb_frame(
            rgb,
            grade,
            "test=combined-gpu-metadata",
            0.0,
            gpu_meta={
                "clip_effects": clip_effects,
                "spine_items": spine_items,
                "ar_pbr_items": ar_pbr_items,
            },
        )

        assert len(gpu_frames) == 1
        _, payload = gpu_frames[0]
        assert payload["grade"] is grade
        assert payload["clip_effects"] is clip_effects
        assert payload["spine_items"] is spine_items
        assert payload["ar_pbr_items"] is ar_pbr_items
    finally:
        player.release()


def test_video_editor_dispatches_combined_gpu_metadata_to_gl_preview():
    from app.video_editor_window import VideoEditorWindow

    class _FakeGL:
        def __init__(self):
            self.visible = True
            self.blur = None
            self.clip_effects = None
            self.spine_items = None
            self.ar_pbr_items = None
            self.updated = None

        def isVisible(self):
            return self.visible

        def show(self):
            self.visible = True

        def set_blur(self, value):
            self.blur = value

        def set_clip_effects(self, effects):
            self.clip_effects = effects

        def set_spine_overlay_items(self, items):
            self.spine_items = items

        def set_ar_pbr_overlay_items(self, items):
            self.ar_pbr_items = items

        def update_frame(self, rgb, grade):
            self.updated = (rgb, grade)

    class _FakePopout:
        def __init__(self):
            self.frames = []

        def update_frame(self, qimg):
            self.frames.append(qimg)

    class _FakeWindow:
        def __init__(self):
            self._preview_gl = _FakeGL()
            self._preview_popout = _FakePopout()
            self._lut_cache = None
            self._color_page_window = None
            self._player = SimpleNamespace(position=lambda: 123)

        def _clear_preview_placeholder(self):
            self.placeholder_cleared = True

        def _preview_qimage_primary_active(self):
            return False

        def _ensure_preview_gl(self):
            return self._preview_gl

        def _sync_preview_gl_geometry(self):
            self.geometry_synced = True

        def _preview_tab_guard_active(self):
            return False

        def _active_renderable_clip_at_current_position(self):
            return False

        def _rgb_looks_like_blank_preview(self, _rgb):
            return False

        def _sync_overlay_to_video_rect(self):
            self.video_rect_synced = True

        def _sync_color_power_window_overlay(self):
            self.power_window_synced = True

        def _update_subtitle_overlay(self, pos):
            self.subtitle_pos = pos

        def _refresh_preview_qimage_mode(self):
            self.qimage_mode_refreshed = True

        def _qimage_from_preview_rgb(self, rgb):
            from PySide6.QtGui import QImage

            arr = np.ascontiguousarray(rgb)
            return QImage(
                arr.data,
                arr.shape[1],
                arr.shape[0],
                arr.strides[0],
                QImage.Format.Format_RGB888,
            ).copy()

    fake = _FakeWindow()
    rgb = np.zeros((4, 6, 3), dtype=np.uint8)
    grade = object()
    clip_effects = {"filters": {"contrast": 0.2}, "chroma": None}
    spine_items = [{"anim_name": "idle"}]
    ar_pbr_items = [{"kind": "ndc_color_triangles"}]

    VideoEditorWindow._on_gpu_frame_ready(
        fake,
        rgb,
        {
            "grade": grade,
            "clip_effects": clip_effects,
            "spine_items": spine_items,
            "ar_pbr_items": ar_pbr_items,
        },
    )

    assert fake._preview_gl.blur == 0.0
    assert fake._preview_gl.clip_effects is clip_effects
    assert fake._preview_gl.spine_items == spine_items
    assert fake._preview_gl.ar_pbr_items == ar_pbr_items
    assert fake._preview_gl.updated == (rgb, grade)
    assert len(fake._preview_popout.frames) == 1
    assert not fake._preview_popout.frames[0].isNull()
    assert fake.subtitle_pos == 123
    assert fake.video_rect_synced
    assert fake.power_window_synced


def test_video_editor_keeps_gl_preview_for_gpu_overlay_when_qimage_primary(monkeypatch):
    from app.video_editor_window import VideoEditorWindow

    monkeypatch.delenv("TIGERCAPTURE_PREVIEW_QIMAGE", raising=False)

    class _FakeGL:
        def __init__(self):
            self.visible = False
            self.hidden = False
            self.ar_pbr_items = None
            self.updated = None

        def isVisible(self):
            return self.visible

        def show(self):
            self.visible = True

        def hide(self):
            self.hidden = True
            self.visible = False

        def set_blur(self, _value):
            pass

        def set_ar_pbr_overlay_items(self, items):
            self.ar_pbr_items = items

        def update_frame(self, rgb, grade):
            self.updated = (rgb, grade)

    class _FakeWindow:
        def __init__(self):
            self._preview_gl = _FakeGL()
            self._preview_popout = None
            self._lut_cache = None
            self._color_page_window = None
            self._player = SimpleNamespace(position=lambda: 456)
            self.geometry_synced = False

        def _clear_preview_placeholder(self):
            pass

        def _preview_qimage_primary_active(self):
            return VideoEditorWindow._preview_qimage_primary_active(self)

        def _preview_cpu_frame_consumers_active(self):
            return True

        def _ensure_preview_gl(self):
            return self._preview_gl

        def _sync_preview_gl_geometry(self):
            self.geometry_synced = True

        def _preview_tab_guard_active(self):
            return False

        def _active_renderable_clip_at_current_position(self):
            return False

        def _rgb_looks_like_blank_preview(self, _rgb):
            return False

        def _sync_overlay_to_video_rect(self):
            pass

        def _sync_color_power_window_overlay(self):
            pass

        def _update_subtitle_overlay(self, _pos):
            pass

        def _refresh_preview_qimage_mode(self):
            pass

    fake = _FakeWindow()
    rgb = np.zeros((4, 6, 3), dtype=np.uint8)
    grade = object()
    ar_pbr_items = [{"kind": "ndc_color_triangles"}]

    VideoEditorWindow._on_gpu_frame_ready(
        fake,
        rgb,
        {"grade": grade, "ar_pbr_items": ar_pbr_items},
    )

    assert fake._preview_gl.visible is True
    assert fake._preview_gl.hidden is False
    assert fake.geometry_synced is True
    assert fake._preview_gl.ar_pbr_items == ar_pbr_items
    assert fake._preview_gl.updated == (rgb, grade)
    assert fake._preview_gl_overlay_required is True


def test_video_editor_placeholder_mode_hides_stale_gl_surface():
    from app.video_editor_window import VideoEditorWindow

    class _FakeLabel:
        def __init__(self):
            self.text = "old"
            self.pixmap = "old"
            self.updated = False
            self.stylesheet = ""

        def setText(self, text):
            self.text = text

        def setStyleSheet(self, value):
            self.stylesheet = value

        def setPixmap(self, value):
            self.pixmap = value

        def update(self):
            self.updated = True

    class _FakeGL:
        def __init__(self):
            self.hidden = False

        def isVisible(self):
            return True

        def hide(self):
            self.hidden = True

    fake = SimpleNamespace(
        _preview_placeholder_kind="content",
        _preview_pixmap=object(),
        _latest_preview_rgb=np.zeros((2, 2, 3), dtype=np.uint8),
        _preview_gl_frame_size=(2, 2),
        _preview_gl=_FakeGL(),
        _preview_label=_FakeLabel(),
        _draw_preview_placeholder=lambda _kind: "placeholder-pixmap",
    )

    VideoEditorWindow._set_preview_placeholder(fake, "empty")

    assert fake._preview_placeholder_kind == "empty"
    assert fake._preview_pixmap is None
    assert fake._latest_preview_rgb is None
    assert fake._preview_gl_frame_size == (0, 0)
    assert fake._preview_gl.hidden is True
    assert fake._preview_label.pixmap == "placeholder-pixmap"


def test_video_editor_clear_preview_placeholder_repaints_backing_label(monkeypatch):
    import app.video_editor_window as video_editor_window

    class _FakeLabel:
        def __init__(self):
            self.text = "stale"
            self.pixmap = "stale-placeholder"
            self.stylesheet = ""
            self.updated = False
            self.repainted = False

        def setText(self, text):
            self.text = text

        def setPixmap(self, value):
            self.pixmap = value

        def setStyleSheet(self, value):
            self.stylesheet = value

        def update(self):
            self.updated = True

        def repaint(self):
            self.repainted = True

    fake = SimpleNamespace(
        _preview_placeholder_kind="empty",
        _preview_label=_FakeLabel(),
    )

    monkeypatch.setattr(video_editor_window, "QPixmap", lambda: "empty-pixmap")

    video_editor_window.VideoEditorWindow._clear_preview_placeholder(fake)

    assert fake._preview_placeholder_kind == "content"
    assert fake._preview_label.text == ""
    assert fake._preview_label.pixmap == "empty-pixmap"
    assert "transparent" in fake._preview_label.stylesheet
    assert fake._preview_label.updated is True
    assert fake._preview_label.repainted is True


def test_video_editor_update_preview_placeholder_clears_for_visual_tracks(monkeypatch):
    import app.video_editor_window as video_editor_window

    class _FakeLabel:
        def __init__(self):
            self.text = "stale"
            self.pixmap = "stale-placeholder"
            self.stylesheet = ""
            self.updated = False
            self.repainted = False

        def setText(self, text):
            self.text = text

        def setPixmap(self, value):
            self.pixmap = value

        def setStyleSheet(self, value):
            self.stylesheet = value

        def update(self):
            self.updated = True

        def repaint(self):
            self.repainted = True

    fake = SimpleNamespace(
        _preview_placeholder_kind="empty",
        _preview_label=_FakeLabel(),
        _tracks=[SimpleNamespace(source_path=Path("movie.mp4"), clips=[])],
        _live2d_actor_tracks=[],
        _spine_actor_tracks=[],
        _ar_pbr_tracks=[],
        _mmd_tracks=[],
        _audio_tracks=[],
    )
    fake._preview_has_visual_content = lambda: video_editor_window.VideoEditorWindow._preview_has_visual_content(fake)
    fake._clear_preview_placeholder = lambda: video_editor_window.VideoEditorWindow._clear_preview_placeholder(fake)

    monkeypatch.setattr(video_editor_window, "QPixmap", lambda: "empty-pixmap")

    video_editor_window.VideoEditorWindow._update_preview_placeholder(fake)

    assert fake._preview_placeholder_kind == "content"
    assert fake._preview_label.pixmap == "empty-pixmap"
    assert fake._preview_label.updated is True
    assert fake._preview_label.repainted is True


def test_video_editor_import_preview_sync_refreshes_visual_frame(monkeypatch):
    import app.video_editor_window as video_editor_window

    class _FakeLabel:
        def setText(self, _text):
            pass

        def setPixmap(self, _value):
            pass

        def setStyleSheet(self, _value):
            pass

        def update(self):
            pass

        def repaint(self):
            pass

    class _FakePlayer:
        def __init__(self):
            self.refreshed = False

        def refresh_current_frame(self):
            self.refreshed = True

    class _FakeGL:
        def __init__(self):
            self.shown = False

        def show(self):
            self.shown = True

    fake = SimpleNamespace(
        _preview_placeholder_kind="empty",
        _preview_label=_FakeLabel(),
        _preview_gl=_FakeGL(),
        _player=_FakePlayer(),
        _tracks=[SimpleNamespace(source_path=Path("movie.mp4"), clips=[])],
        _live2d_actor_tracks=[],
        _spine_actor_tracks=[],
        _ar_pbr_tracks=[],
        _mmd_tracks=[],
    )
    fake._preview_has_visual_content = lambda: video_editor_window.VideoEditorWindow._preview_has_visual_content(fake)
    fake._clear_preview_placeholder = lambda: video_editor_window.VideoEditorWindow._clear_preview_placeholder(fake)
    fake._update_preview_placeholder = lambda: video_editor_window.VideoEditorWindow._update_preview_placeholder(fake)

    monkeypatch.setattr(video_editor_window, "QPixmap", lambda: "empty-pixmap")

    video_editor_window.VideoEditorWindow._refresh_visual_preview_after_timeline_change(fake)

    assert fake._preview_placeholder_kind == "content"
    assert fake._player.refreshed is True
    assert fake._preview_gl.shown is True


def test_project_player_defers_spine_overlay_to_gpu_metadata(monkeypatch):
    class _Clip:
        start_ms = 0
        end_ms = 1000

        def preview_render_state(self, width, height, pos_ms, animated=True):
            return {
                "skeleton": object(),
                "atlas": {"dummy": (0, 0, 0, 1, 1)},
                "pil_pages": [object()],
                "anim_name": "idle",
                "time": pos_ms / 1000.0,
                "scale": 1.0,
                "offset_x": 0.0,
                "offset_y": 0.0,
            }

    class _Track:
        def clips_at(self, pos_ms):
            return [_Clip()]

    monkeypatch.setenv("TIGERCAPTURE_SPINE_ZERO_READBACK", "1")
    player = ProjectPlayer()
    try:
        player.set_qimage_frame_enabled(False)
        player.set_spine_actor_tracks([_Track()])
        rgb = np.zeros((4, 6, 3), dtype=np.uint8)

        out, meta = player._apply_or_defer_spine_overlay(rgb, 100, True, "test=1", 0.0)

        assert out is rgb
        assert meta is not None
        assert len(meta["spine_items"]) == 1
        assert abs(meta["spine_items"][0]["time"] - 0.084) < 1e-6
    finally:
        player.release()


def test_project_player_defers_spine_overlay_with_live2d_by_default(monkeypatch):
    class _SpineClip:
        start_ms = 0
        end_ms = 1000

        def preview_render_state(self, width, height, pos_ms, animated=True):
            return {
                "skeleton": object(),
                "atlas": {"dummy": (0, 0, 0, 1, 1)},
                "pil_pages": [object()],
                "anim_name": "idle",
                "time": pos_ms / 1000.0,
                "scale": 1.0,
                "offset_x": 0.0,
                "offset_y": 0.0,
            }

        def render_frame(self, *args, **kwargs):
            raise AssertionError("direct GPU preview should not CPU-composite Spine")

    class _SpineTrack:
        def clips_at(self, pos_ms):
            return [_SpineClip()]

    live2d_clip = SimpleNamespace(start_ms=0, end_ms=1000)
    live2d_track = SimpleNamespace(clips=[live2d_clip])

    monkeypatch.setenv("TIGERCAPTURE_SPINE_ZERO_READBACK", "1")
    monkeypatch.delenv("TIGERCAPTURE_SPINE_DIRECT_WITH_LIVE2D", raising=False)
    player = ProjectPlayer()
    try:
        player.set_qimage_frame_enabled(False)
        player.set_spine_actor_tracks([_SpineTrack()])
        player.set_live2d_actor_tracks([live2d_track])
        rgb = np.zeros((4, 6, 3), dtype=np.uint8)

        out, meta = player._apply_or_defer_spine_overlay(rgb, 100, True, "test=1", 0.0)

        assert out is rgb
        assert meta is not None
        assert len(meta["spine_items"]) == 1
    finally:
        player.release()


def test_project_player_can_disable_direct_spine_with_live2d(monkeypatch):
    class _SpineClip:
        start_ms = 0
        end_ms = 1000

        def preview_render_state(self, width, height, pos_ms, animated=True):
            return {
                "skeleton": object(),
                "atlas": {"dummy": (0, 0, 0, 1, 1)},
                "pil_pages": [object()],
                "anim_name": "idle",
                "time": pos_ms / 1000.0,
                "scale": 1.0,
                "offset_x": 0.0,
                "offset_y": 0.0,
            }

        def render_frame(self, width, height, pos_ms, animated=True, fast_preview=True, use_gl=True):
            from PIL import Image
            return Image.new("RGBA", (int(width), int(height)), (255, 0, 0, 255))

    class _SpineTrack:
        def clips_at(self, pos_ms):
            return [_SpineClip()]

    live2d_clip = SimpleNamespace(start_ms=0, end_ms=1000)
    live2d_track = SimpleNamespace(clips=[live2d_clip])

    monkeypatch.setenv("TIGERCAPTURE_SPINE_ZERO_READBACK", "1")
    monkeypatch.setenv("TIGERCAPTURE_SPINE_DIRECT_WITH_LIVE2D", "0")
    player = ProjectPlayer()
    try:
        player.set_qimage_frame_enabled(False)
        player.set_spine_actor_tracks([_SpineTrack()])
        player.set_live2d_actor_tracks([live2d_track])
        rgb = np.zeros((4, 6, 3), dtype=np.uint8)

        out, meta = player._apply_or_defer_spine_overlay(rgb, 100, True, "test=1", 0.0)

        assert meta is None
        assert out is not rgb
        assert out[..., 0].max() == 255
    finally:
        player.release()


def test_project_player_reuses_spine_direct_overlay_state(monkeypatch):
    class _Clip:
        skel_path = "fake.skel"
        atlas_path = "fake.atlas"
        texture_path = "fake.png"
        anim_name = "idle"
        skin_name = "default"
        start_ms = 0
        duration_ms = 1000
        loop = True
        pos_x = 0.5
        pos_y = 0.5
        scale = 1.0

        @property
        def end_ms(self):
            return self.start_ms + self.duration_ms

        def __init__(self):
            self.calls = 0

        def preview_render_state(self, width, height, pos_ms, animated=True):
            self.calls += 1
            return {
                "skeleton": object(),
                "atlas": {"dummy": (0, 0, 0, 1, 1)},
                "pil_pages": [object()],
                "anim_name": "idle",
                "time": pos_ms / 1000.0,
                "scale": 1.0,
                "offset_x": 0.0,
                "offset_y": 0.0,
            }

    class _Track:
        def __init__(self, clip):
            self.clip = clip

        def clips_at(self, pos_ms):
            return [self.clip]

    monkeypatch.setenv("TIGERCAPTURE_SPINE_PREVIEW_FPS", "24")
    player = ProjectPlayer()
    clip = _Clip()
    try:
        player.set_spine_actor_tracks([_Track(clip)])

        first = player._spine_direct_overlay_items(1920, 1080, 100, True)
        second = player._spine_direct_overlay_items(1920, 1080, 104, True)

        assert first is second
        assert clip.calls == 1
    finally:
        player.release()


def test_project_player_can_defer_clip_effects_to_shader(monkeypatch):
    from app.chroma_key import ChromaKeyParams
    from app.video_filters import VideoFilterParams

    monkeypatch.setenv("TIGERCAPTURE_SHADER_CLIP_FX", "1")
    player = ProjectPlayer()
    try:
        player.set_qimage_frame_enabled(False)
        meta = player._clip_effects_shader_available(
            SimpleNamespace(transition_out_ms=0, transition_out_type="", timeline_out_ms=1000),
            VideoFilterParams(sharpen=0.4, vignette=0.2),
            ChromaKeyParams(enabled=True, key_hue=60),
            None,
            0,
            False,
        )

        assert meta is not None
        assert meta["filters"]["sharpen"] == 0.4
        assert meta["chroma"]["key_hue"] == 60.0
    finally:
        player.release()


def test_project_player_keeps_clip_effects_on_cpu_for_qimage_consumers():
    from app.video_filters import VideoFilterParams

    player = ProjectPlayer()
    try:
        player.set_qimage_frame_enabled(True)
        meta = player._clip_effects_shader_available(
            SimpleNamespace(transition_out_ms=0, transition_out_type="", timeline_out_ms=1000),
            VideoFilterParams(sharpen=0.4),
            None,
            None,
            0,
            False,
        )

        assert meta is None
    finally:
        player.release()
