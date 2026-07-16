from __future__ import annotations

import os
import time
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QSizePolicy, QWidget

from app.audio_tracks import AudioClip, AudioTrack
from app.audio_tool_dock_specs import (
    AUDIO_TOOL_DOCK_BUTTON_MAX_HEIGHT,
    AUDIO_TOOL_DOCK_BUTTON_MIN_HEIGHT,
)
from app.composer_panel import ComposerPanel, ComposerWindow
from app.sound_editor_panel import (
    SOUND_EDITOR_ADVANCED_LAB_HOST_HEIGHT,
    SOUND_EDITOR_ADVANCED_VISIBLE_SCROLL_HEIGHT,
    SOUND_EDITOR_PANEL_ADVANCED_MIN_HEIGHT,
    SOUND_EDITOR_PANEL_MIXER_MIN_HEIGHT,
    SOUND_EDITOR_PANEL_MIN_HEIGHT,
    SoundEditStateStore,
    SoundEditorDockWindow,
    SoundEditorPanel,
)
from app.sound_editor_visual_widgets import _MiniWaveformStrip, _SoundJogShuttle05


def _app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


class _FakeWheelEvent:
    def __init__(
        self,
        *,
        delta_y: int,
        delta_x: int = 0,
        pos: QPointF | None = None,
        modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    ) -> None:
        self._delta = QPoint(int(delta_x), int(delta_y))
        self._pos = pos or QPointF(320.0, 130.0)
        self._modifiers = modifiers
        self.accepted = False

    def angleDelta(self) -> QPoint:
        return self._delta

    def pixelDelta(self) -> QPoint:
        return QPoint(0, 0)

    def position(self) -> QPointF:
        return self._pos

    def modifiers(self):
        return self._modifiers

    def accept(self) -> None:
        self.accepted = True


def test_sound_edit_state_store_preserves_media_pool_clip_edits(tmp_path: Path) -> None:
    path_a = tmp_path / "voice_a.wav"
    path_b = tmp_path / "voice_b.wav"
    path_a.write_bytes(b"a")
    path_b.write_bytes(b"b")
    store = SoundEditStateStore()

    clip_a = store.media_clip(path_a, duration_ms=1200)
    clip_a.gain = 0.42
    clip_b = store.media_clip(path_b, duration_ms=3400)
    clip_b.gain = 1.25

    assert store.media_clip(path_a).gain == 0.42
    assert store.media_clip(path_b).gain == 1.25
    assert store.media_clip(path_a) is clip_a
    assert store.recent_keys()[0] == SoundEditStateStore.media_key(path_a)


def test_sound_editor_panel_keeps_media_and_timeline_states_separate(tmp_path: Path) -> None:
    _app()
    media_path = tmp_path / "pool.wav"
    timeline_path = tmp_path / "timeline.wav"
    media_path.write_bytes(b"media")
    timeline_path.write_bytes(b"timeline")
    media_clip = AudioClip(id=1, source_path=media_path, duration_ms=1000, trim_end_ms=1000)
    timeline_clip = AudioClip(id=2, source_path=timeline_path, duration_ms=2000, trim_end_ms=2000)
    panel = SoundEditorPanel()

    panel.set_clip(media_clip, context_label="Media Pool Audio", context_key="media:pool")
    panel._set_fx("eq", ("low", "gain"), 3.5)
    panel._set_attr("gain", 0.65)

    panel.set_clip(timeline_clip, context_label="Timeline Audio", context_key="timeline:1:2")
    panel._set_fx("comp", "enabled", True)
    panel._set_fx("comp", "threshold", -28.0)
    panel._set_attr("gain", 1.15)

    panel.set_clip(media_clip, context_label="Media Pool Audio", context_key="media:pool")

    assert media_clip.gain == 0.65
    assert media_clip.effects["eq"]["low"]["gain"] == 3.5
    assert not media_clip.effects["comp"]["enabled"]
    assert timeline_clip.gain == 1.15
    assert timeline_clip.effects["comp"]["enabled"]
    assert timeline_clip.effects["comp"]["threshold"] == -28.0


def test_sound_editor_dock_window_uses_renewed_panel_without_load_button(tmp_path: Path) -> None:
    _app()
    audio_path = tmp_path / "timeline.wav"
    audio_path.write_bytes(b"timeline")
    clip = AudioClip(id=7, source_path=audio_path, duration_ms=3000, trim_end_ms=3000)

    window = SoundEditorDockWindow(clip)

    assert window.current_clip() is clip
    assert window.clip is clip
    assert window.findChild(SoundEditorPanel) is not None
    assert "Load" not in window.windowTitle()


def test_sound_editor_advanced_lab_button_uses_separate_dock_row() -> None:
    _app()
    panel = SoundEditorPanel()

    lab_buttons = [
        button
        for button in panel.findChildren(QPushButton)
        if button.property("role") == "advanced_audio_lab"
    ]

    assert len(lab_buttons) == 1
    button = lab_buttons[0]
    assert button.text() == "SOUND LAB"
    assert button.objectName() == "SoundLabDockButton"
    assert button.parentWidget().objectName() == "SoundLabDockRow"
    assert button.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert button.minimumHeight() == AUDIO_TOOL_DOCK_BUTTON_MIN_HEIGHT
    assert button.maximumHeight() == AUDIO_TOOL_DOCK_BUTTON_MAX_HEIGHT
    assert button.icon().isNull()


def test_sound_editor_dock_window_keeps_full_mixer_context(tmp_path: Path) -> None:
    _app()
    from types import SimpleNamespace

    audio_path = tmp_path / "dock_mixer.wav"
    audio_path.write_bytes(b"dock")
    clip = AudioClip(id=71, source_path=audio_path, duration_ms=3000, trim_end_ms=3000)
    track_a = SimpleNamespace(id=2, label="Voice", bus_id="dialogue", volume=0.86, pan=-0.08, muted=False, solo=False, clips=[clip])
    track_b = SimpleNamespace(id=3, label="Music", bus_id="music", volume=0.62, pan=-0.3, muted=True, solo=False, clips=[])

    window = SoundEditorDockWindow(clip, track=track_a, mixer_tracks=[track_a, track_b])
    panel = window.findChild(SoundEditorPanel)
    assert panel is not None

    assert "mixer" not in panel._tab_buttons
    assert panel._mixer_dock.isHidden() is False
    assert len(panel._mixer_strips) == 2
    assert panel._mixer_strips[2].property("active") is True
    assert panel._mixer_strips[3]._mute.isChecked() is True
    assert panel._mixer_strips[3]._name.text().startswith("Music")
    masters = [child for child in panel.findChildren(QWidget, "SoundMixerMasterStrip") if not child.isHidden()]
    assert len(masters) == 1
    assert masters[0].findChild(QWidget, "SoundMixerStereoVu") is not None
    assert panel._mixer_strips[2]._title.text() == "A1"


def test_sound_editor_panel_refreshes_waveform_strip(tmp_path: Path) -> None:
    _app()
    import numpy as np

    audio_path = tmp_path / "waveform.wav"
    audio_path.write_bytes(b"waveform")
    clip = AudioClip(id=8, source_path=audio_path, duration_ms=4000, trim_end_ms=4000)
    x = np.linspace(0, 1, 320, dtype=np.float32)
    clip.waveform = np.vstack([np.sin(x * 40.0), np.sin(x * 40.0) * 0.8]).astype(np.float32)
    panel = SoundEditorPanel()

    panel.set_clip(clip, context_label="Timeline Audio", context_key="timeline:1:8")
    panel.refresh_waveform()
    pixmap = panel.grab()

    assert not pixmap.isNull()
    assert panel.findChild(QWidget, "SoundSpectrumStrip") is not None


def test_sound_editor_panel_draws_compact_spectrum_strip(tmp_path: Path) -> None:
    _app()
    import numpy as np

    audio_path = tmp_path / "spectrum.wav"
    audio_path.write_bytes(b"spectrum")
    clip = AudioClip(id=80, source_path=audio_path, duration_ms=4000, trim_end_ms=4000)
    x = np.linspace(0, 1, 640, dtype=np.float32)
    clip.waveform = np.vstack([
        np.sin(x * 120.0) * 0.6,
        np.sin(x * 80.0) * 0.45,
    ]).astype(np.float32)
    clip.spectrum_bins = np.linspace(0.05, 1.0, 64, dtype=np.float32)
    panel = SoundEditorPanel()

    panel.set_clip(clip, context_label="Timeline Audio", context_key="timeline:1:80")
    panel.refresh_waveform()

    spectrum = panel.findChild(QWidget, "SoundSpectrumStrip")
    assert spectrum is not None
    assert not spectrum.grab().isNull()


def test_sound_editor_panel_embeds_reference_05_jog_shuttle(tmp_path: Path) -> None:
    _app()
    import numpy as np

    audio_path = tmp_path / "jog.wav"
    audio_path.write_bytes(b"jog")
    clip = AudioClip(id=83, source_path=audio_path, duration_ms=5000, trim_end_ms=5000)
    x = np.linspace(0, 1, 512, dtype=np.float32)
    clip.waveform = np.vstack([
        np.sin(x * 52.0) * 0.5,
        np.sin(x * 48.0) * 0.42,
    ]).astype(np.float32)
    panel = SoundEditorPanel()

    panel.set_clip(clip, context_label="Timeline Audio", context_key="timeline:1:83")
    jog = panel.findChild(QWidget, "SoundJogShuttle05")
    assert jog is not None
    assert not jog.grab().isNull()
    assert len(panel._jog_shuttle._aux_dial_rects()) == 8
    assert [spec[0] for spec in panel._jog_shuttle._aux_dial_specs()] == [
        "GAIN", "PAN", "IN", "OUT", "SPD", "PCH", "AI", "LVL",
    ]

    panel._jog_shuttle._set_position_ms(2400)
    panel._jog_shuttle._set_playing(True)

    assert getattr(clip, "_se_jog_ms") == 2400
    assert getattr(clip, "_se_jog_playing") is True


def test_sound_editor_jog_shuttle_exposes_play_pause_button(tmp_path: Path) -> None:
    _app()
    audio_path = tmp_path / "jog_play.wav"
    audio_path.write_bytes(b"jog")
    clip = AudioClip(id=831, source_path=audio_path, duration_ms=5000, trim_end_ms=5000)
    jog = _SoundJogShuttle05()
    events: list[bool] = []
    jog.playing_changed.connect(events.append)

    jog.set_clip(clip)
    jog._play_btn.click()

    assert events[-1] is True
    assert getattr(clip, "_se_jog_playing") is True
    assert jog._play_btn.property("playing") is True

    jog._play_btn.click()

    assert events[-1] is False
    assert getattr(clip, "_se_jog_playing") is False
    assert jog._play_btn.property("playing") is False


def test_sound_editor_jog_shuttle_led_afterglow_decays_after_stop(tmp_path: Path) -> None:
    _app()
    audio_path = tmp_path / "jog_afterglow.wav"
    audio_path.write_bytes(b"jog")
    clip = AudioClip(id=8320, source_path=audio_path, duration_ms=5000, trim_end_ms=5000)
    jog = _SoundJogShuttle05()

    jog.set_clip(clip)
    jog._set_position_ms(2400, emit=False)
    jog._set_playing(True)
    for _ in range(3):
        jog._tick_slot_animation()

    assert max(jog._slot_glow_values) >= 0.95

    jog._set_playing(False)

    assert jog._slot_anim_timer.isActive()
    before = max(jog._slot_glow_values)
    jog._tick_slot_animation()

    assert max(jog._slot_glow_values) <= before

    for _ in range(44):
        jog._tick_slot_animation()

    assert max(jog._slot_glow_values) < 0.03
    assert not jog._slot_anim_timer.isActive()


def test_sound_editor_waveform_detail_controls_zoom_strip(tmp_path: Path) -> None:
    app = _app()
    import numpy as np

    audio_path = tmp_path / "wave_zoom.wav"
    audio_path.write_bytes(b"zoom")
    clip = AudioClip(id=832, source_path=audio_path, duration_ms=8000, trim_end_ms=8000)
    x = np.linspace(0, 1, 2048, dtype=np.float32)
    clip.waveform = np.vstack([
        np.sin(x * 300.0) * 0.55,
        np.sin(x * 247.0) * 0.42,
    ]).astype(np.float32)
    panel = SoundEditorPanel()
    panel.resize(900, 720)
    panel.show()

    panel.set_clip(clip, context_label="Timeline Audio", context_key="timeline:1:832")
    panel._set_waveform_zoom(4.0)
    app.processEvents()

    assert panel._waveform_strip.zoom_factor() == 4.0
    assert getattr(clip, "_se_waveform_zoom") == 4.0
    assert panel._waveform_zoom_buttons[4.0].property("selected") is True
    assert panel._waveform_strip.geometry().top() > panel._jog_shuttle.geometry().bottom()
    assert panel._waveform_zoom_buttons[4.0].parent() is panel._waveform_strip
    assert panel._waveform_strip.minimumHeight() >= 80
    assert not panel._waveform_strip.grab().isNull()


def test_workbench_sound_editor_keeps_top_audio_blocks_separated(tmp_path: Path) -> None:
    app = _app()
    import numpy as np
    from app.workbench_panel import WorkbenchPanel

    audio_path = tmp_path / "workbench_audio.wav"
    audio_path.write_bytes(b"audio")
    clip = AudioClip(id=836, source_path=audio_path, duration_ms=48000, trim_end_ms=48000)
    x = np.linspace(0, 1, 4096, dtype=np.float32)
    clip.waveform = np.vstack([
        np.sin(x * 900.0) * 0.45,
        np.sin(x * 820.0) * 0.36,
    ]).astype(np.float32)
    track = AudioTrack(id=5, label="A1", clips=[clip])
    panel = WorkbenchPanel()
    panel.resize(744, 620)
    panel.show()

    panel.set_audio_clip(track, clip)
    app.processEvents()

    sound = panel._sound_editor_panel
    scroll = panel._sound_editor_scroll
    assert scroll.isVisible() is True
    assert scroll.widget() is sound
    assert panel._composer_dock.isVisible() is True
    assert panel._composer_button.isVisible() is True
    assert panel._composer_button.isCheckable() is False
    assert panel._composer_button.text() == "COMPOSER"
    assert panel._composer_button.minimumHeight() == AUDIO_TOOL_DOCK_BUTTON_MIN_HEIGHT
    assert panel._composer_button.maximumHeight() == AUDIO_TOOL_DOCK_BUTTON_MAX_HEIGHT
    assert panel._composer_button.icon().isNull()
    assert panel._voice_lab_button.isVisible() is True
    assert panel._voice_lab_button.text() == "VOICE LAB"
    assert panel._voice_lab_button.minimumHeight() == AUDIO_TOOL_DOCK_BUTTON_MIN_HEIGHT
    assert panel._voice_lab_button.maximumHeight() == AUDIO_TOOL_DOCK_BUTTON_MAX_HEIGHT
    assert panel._voice_lab_button.icon().isNull()
    assert panel._unreal_link_button.isVisible() is True
    assert panel._unreal_link_button.text() == "UNREAL LINK"
    assert panel._unreal_link_button.minimumHeight() == AUDIO_TOOL_DOCK_BUTTON_MIN_HEIGHT
    assert panel._unreal_link_button.maximumHeight() == AUDIO_TOOL_DOCK_BUTTON_MAX_HEIGHT
    assert panel._unreal_link_button.icon().isNull()
    assert sound._advanced_btn.text() == "SOUND LAB"
    assert sound._advanced_btn.minimumHeight() == panel._composer_button.minimumHeight()
    assert sound._advanced_btn.maximumHeight() == panel._composer_button.maximumHeight()
    assert sound._advanced_btn.icon().isNull()
    assert scroll.geometry().top() < panel._composer_dock.geometry().top()
    assert scroll.height() >= panel._tab_stack.height() - panel._composer_dock.height() - 12
    assert sound.minimumHeight() >= SOUND_EDITOR_PANEL_MIN_HEIGHT
    assert sound.height() >= SOUND_EDITOR_PANEL_MIN_HEIGHT
    assert scroll.verticalScrollBar().maximum() > 0
    assert sound._waveform_strip.geometry().top() > sound._jog_shuttle.geometry().bottom()
    assert sound._spectrum_strip.geometry().top() > sound._waveform_strip.geometry().bottom()
    assert sound._tabs_bar.geometry().top() > sound._spectrum_strip.geometry().bottom()

    collapsed_scroll_max = scroll.verticalScrollBar().maximum()
    sound._set_advanced_lab_expanded(True)
    app.processEvents()

    assert sound.minimumHeight() >= SOUND_EDITOR_PANEL_ADVANCED_MIN_HEIGHT
    assert sound._advanced_lab_host.isVisible() is True
    assert scroll.minimumHeight() >= SOUND_EDITOR_ADVANCED_VISIBLE_SCROLL_HEIGHT
    assert scroll.minimumHeight() < SOUND_EDITOR_PANEL_ADVANCED_MIN_HEIGHT
    assert panel._tab_stack.minimumHeight() >= SOUND_EDITOR_ADVANCED_VISIBLE_SCROLL_HEIGHT
    assert panel.minimumHeight() > SOUND_EDITOR_ADVANCED_VISIBLE_SCROLL_HEIGHT
    assert scroll.verticalScrollBar().maximum() > collapsed_scroll_max

    sound._set_advanced_lab_expanded(False)
    app.processEvents()

    assert sound.minimumHeight() == SOUND_EDITOR_PANEL_MIXER_MIN_HEIGHT
    assert sound._advanced_lab_host.isVisible() is False
    panel._composer_button.click()
    app.processEvents()

    assert getattr(panel, "_composer_scroll", None) is None
    assert isinstance(panel._composer_window, ComposerWindow)
    assert panel._composer_window.isVisible() is True
    assert panel._composer_panel is panel._composer_window.composer_panel()
    assert panel._composer_dock.findChildren(ComposerPanel) == []
    assert scroll.isVisible() is True
    assert sound.isVisible() is True
    assert scroll.geometry().top() < panel._composer_dock.geometry().top()

    panel.close()


def test_workbench_sound_editor_expansion_grows_parent_section(tmp_path: Path) -> None:
    app = _app()
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    from app.workbench_panel import WorkbenchPanel

    audio_path = tmp_path / "workbench_parent_audio.wav"
    audio_path.write_bytes(b"audio")
    clip = AudioClip(id=837, source_path=audio_path, duration_ms=48000, trim_end_ms=48000)
    track = AudioTrack(id=6, label="A1", clips=[clip])
    host = QWidget()
    host.setObjectName("WorkbenchSectionHost")
    host.setMinimumHeight(500)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    panel = WorkbenchPanel(host)
    layout.addWidget(panel)
    host.resize(744, 620)
    host.show()

    panel.set_audio_clip(track, clip)
    app.processEvents()
    base_host_min = host.minimumHeight()

    panel._sound_editor_panel._set_advanced_lab_expanded(True)
    app.processEvents()

    assert host.minimumHeight() > base_host_min
    assert host.minimumHeight() >= panel.minimumHeight()
    assert panel._sound_editor_scroll.minimumHeight() >= SOUND_EDITOR_ADVANCED_VISIBLE_SCROLL_HEIGHT
    assert panel._sound_editor_scroll.minimumHeight() < SOUND_EDITOR_PANEL_ADVANCED_MIN_HEIGHT

    panel._sound_editor_panel._set_advanced_lab_expanded(False)
    app.processEvents()

    assert host.minimumHeight() == base_host_min

    host.close()


def test_sound_editor_waveform_playhead_tracks_preview_position(tmp_path: Path) -> None:
    app = _app()
    import numpy as np

    audio_path = tmp_path / "wave_playhead.wav"
    audio_path.write_bytes(b"playhead")
    clip = AudioClip(id=833, source_path=audio_path, duration_ms=8000, trim_end_ms=8000)
    x = np.linspace(0, 1, 2048, dtype=np.float32)
    clip.waveform = np.vstack([
        np.sin(x * 180.0) * 0.55,
        np.sin(x * 150.0) * 0.42,
    ]).astype(np.float32)
    panel = SoundEditorPanel()
    panel.resize(900, 720)
    panel.show()

    panel.set_clip(clip, context_label="Timeline Audio", context_key="timeline:1:833")
    panel._set_waveform_zoom(8.0)
    panel._on_preview_player_position(6200)
    app.processEvents()

    assert panel._waveform_strip._playhead_source_ms == 6200
    assert panel._jog_shuttle._position_ms == 6200
    assert panel._waveform_strip._scroll_norm > 0.0
    assert not panel._waveform_strip.grab().isNull()


def test_sound_editor_waveform_marks_low_level_gaps(tmp_path: Path) -> None:
    app = _app()
    import numpy as np

    audio_path = tmp_path / "wave_gap.wav"
    audio_path.write_bytes(b"gap")
    clip = AudioClip(id=834, source_path=audio_path, duration_ms=4000, trim_end_ms=4000)
    wave = np.ones(1600, dtype=np.float32) * 0.55
    wave[420:560] = 0.0
    wave[980:1120] = 0.0
    clip.waveform = np.vstack([wave, wave * 0.8]).astype(np.float32)
    strip = _MiniWaveformStrip()
    strip.resize(900, 104)
    strip.show()

    strip.set_clip(clip)
    app.processEvents()
    pixmap = strip.grab()

    assert not pixmap.isNull()
    assert strip.dropout_count() >= 2


def test_sound_editor_preview_drop_diagnostics_mark_waveform(tmp_path: Path) -> None:
    app = _app()
    import numpy as np

    audio_path = tmp_path / "preview_drop.wav"
    audio_path.write_bytes(b"drop")
    clip = AudioClip(id=835, source_path=audio_path, duration_ms=4000, trim_end_ms=4000)
    x = np.linspace(0, 1, 2048, dtype=np.float32)
    clip.waveform = np.vstack([
        np.sin(x * 120.0) * 0.5,
        np.sin(x * 110.0) * 0.42,
    ]).astype(np.float32)
    panel = SoundEditorPanel()
    panel.resize(900, 720)
    panel.show()

    panel.set_clip(clip, context_label="Timeline Audio", context_key="timeline:1:835")
    panel._jog_shuttle._playing = True
    panel._preview_last_source_ms = 1000
    panel._preview_last_wall_ms = time.monotonic() * 1000.0 - 520.0
    panel._preview_seek_guard_until_ms = 0.0
    panel._record_preview_timing(1090)
    app.processEvents()

    assert panel._waveform_strip.playback_drop_count() == 1
    assert panel._waveform_strip._playback_drop_marks[-1] == 1090
    assert not panel._waveform_strip.grab().isNull()


def test_sound_editor_no_longer_embeds_composer_tab() -> None:
    _app()
    panel = SoundEditorPanel()

    assert "music" not in panel._tab_buttons
    panel._set_tab("music")
    assert panel._stack.currentIndex() == 0


def test_composer_panel_shows_arrangement_view(tmp_path: Path) -> None:
    app = _app()
    from app.music_composer import compose_music

    composition = compose_music(
        prompt="tech demo music",
        duration_ms=30000,
        genre="electronic",
        mood="confident",
        key="C minor",
        bpm=124,
    ).to_dict()
    panel = ComposerPanel()
    panel.resize(760, 720)
    panel.show()
    music_events = []
    panel.music_lab_action_requested.connect(lambda action, params: music_events.append((action, params)))
    panel.set_music_composition(composition)
    panel._music_arrangement.set_selection(role="chords", section_name="build")
    app.processEvents()

    arranger = panel.findChild(QWidget, "ComposerArrangementView")
    assert arranger is not None
    assert arranger.isVisible()
    assert not arranger.grab().isNull()
    payload = panel._music_selection_payload()
    assert payload["composition_id"] == composition["id"]
    assert payload["role"] == "chords"
    assert payload["section_name"] == "build"
    assert payload["section_duration_ms"] > 0
    assert payload["note_count"] > 0
    assert payload["chord_progression"]
    assert "Selected: Pad / build" in panel._music_selection_label.text()
    assert "Chords:" in panel._music_note_hint.text()
    assert panel._music_preview_btn.text() == "Preview"

    panel._request_music_preview()

    assert music_events[-1][0] == "music.render.preview"
    assert music_events[-1][1]["composition_id"] == composition["id"]
    assert music_events[-1][1]["backend"] == "sample_production"


def test_composer_arrangement_mouse_wheel_zooms_time_axis(tmp_path: Path) -> None:
    app = _app()
    from app.music_composer import compose_music

    composition = compose_music(
        prompt="wheel zoom music",
        duration_ms=60000,
        genre="electronic",
        mood="confident",
        key="C minor",
        bpm=124,
    ).to_dict()
    panel = ComposerPanel()
    panel.resize(760, 720)
    panel.show()
    panel.set_music_composition(composition)
    app.processEvents()

    arranger = panel._music_arrangement
    arranger.resize(720, 300)
    assert arranger._timeline_zoom == 1.0

    zoom_in = _FakeWheelEvent(delta_y=120, pos=QPointF(430.0, 140.0))
    arranger.wheelEvent(zoom_in)

    assert zoom_in.accepted
    assert arranger._timeline_zoom > 1.0
    assert arranger._timeline_scroll_s > 0.0
    zoomed = arranger._timeline_zoom
    scrolled = arranger._timeline_scroll_s

    pan_right = _FakeWheelEvent(delta_x=120, delta_y=0, pos=QPointF(430.0, 140.0))
    arranger.wheelEvent(pan_right)

    assert pan_right.accepted
    assert arranger._timeline_zoom == zoomed
    assert arranger._timeline_scroll_s > scrolled

    zoom_out = _FakeWheelEvent(delta_y=-120, pos=QPointF(430.0, 140.0))
    arranger.wheelEvent(zoom_out)

    assert zoom_out.accepted
    assert 1.0 <= arranger._timeline_zoom < zoomed


def test_composer_arrangement_scrolls_many_tracks_with_preview_focus(tmp_path: Path) -> None:
    app = _app()
    sections = [
        {"name": "intro", "start_ms": 0, "duration_ms": 16000},
        {"name": "build", "start_ms": 16000, "duration_ms": 16000},
        {"name": "main", "start_ms": 32000, "duration_ms": 32000},
        {"name": "outro", "start_ms": 64000, "duration_ms": 16000},
    ]
    tracks = [
        {
            "id": f"violins_{idx:02d}",
            "role": f"violins_{idx:02d}",
            "clips": [{"section_name": "main", "notes": [{"pitch": 60 + idx % 12, "start_ms": 0, "duration_ms": 500}]}],
        }
        for idx in range(24)
    ]
    composition = {
        "id": "scroll-focus-test",
        "duration_ms": 80000,
        "genre": "orchestral",
        "mood": "cinematic",
        "key": "D minor",
        "sections": sections,
        "tracks": tracks,
    }
    panel = ComposerPanel()
    panel.resize(760, 720)
    panel.show()
    panel.set_music_composition(composition)
    app.processEvents()

    arranger = panel._music_arrangement
    arranger.resize(720, 260)
    metrics = arranger._layout_metrics()
    assert metrics["track_scroll_max"] > 0
    assert len(metrics["lanes"]) < len(metrics["all_lanes"])

    label_pos = QPointF(metrics["rect"].left() + 20.0, metrics["grid_y"] + 24.0)
    scroll_down = _FakeWheelEvent(delta_y=-120, pos=label_pos)
    arranger.wheelEvent(scroll_down)

    assert scroll_down.accepted
    assert arranger._track_scroll_index == 1

    arranger._timeline_zoom = 4.0
    arranger._timeline_scroll_s = 0.0
    arranger.set_playback_position_ms(52000, follow=True)

    assert arranger._playback_position_s == 52.0
    assert arranger._timeline_scroll_s > 0.0
    assert arranger._section_at_time(52.0)[0] == "main"
    assert arranger._block_pattern_phase(0.25) == 0.75

    arranger.set_playback_position_ms(None)
    assert arranger._block_pattern_phase(0.25) == 0.25


def test_composer_panel_ai_provider_selects_production_mix(tmp_path: Path) -> None:
    app = _app()
    from app.music_composer import compose_music

    composition = compose_music(
        prompt="stable audio music",
        duration_ms=30000,
        genre="electronic",
        mood="confident",
        key="A minor",
        bpm=128,
    ).to_dict()
    panel = ComposerPanel()
    panel.resize(760, 720)
    panel.show()
    music_events = []
    panel.music_lab_action_requested.connect(lambda action, params: music_events.append((action, params)))
    panel.set_music_composition(composition)

    panel._music_ai_provider.setCurrentText("Stable Audio 3.0")
    app.processEvents()

    assert panel._music_render_backend.currentText() == "AI production"
    assert panel._music_roles.currentText() == "mix only"
    assert "Stable Audio 3.0" in panel._music_provider_status.text()

    panel._request_music_preview()

    assert music_events[-1][0] == "music.render.preview"
    assert music_events[-1][1]["composition_id"] == composition["id"]
    assert music_events[-1][1]["backend"] == "production"
    assert music_events[-1][1]["ai_provider"] == "stable_audio_3"
    assert music_events[-1][1]["render_stems"] is False

    panel._request_music_generate()

    assert music_events[-1][0] == "music.compose_to_timeline"
    assert music_events[-1][1]["backend"] == "production"
    assert music_events[-1][1]["ai_provider"] == "stable_audio_3"
    assert music_events[-1][1]["create_mix"] is True


def test_composer_panel_sample_production_backend(tmp_path: Path) -> None:
    app = _app()
    panel = ComposerPanel()
    panel.resize(760, 720)
    panel.show()
    music_events = []
    panel.music_lab_action_requested.connect(lambda action, params: music_events.append((action, params)))
    panel._music_render_backend.setCurrentText("sample prod")
    panel._music_sample_library.setCurrentText("soundfont only")
    app.processEvents()

    panel._request_music_generate()

    assert music_events[-1][0] == "music.compose_to_timeline"
    assert music_events[-1][1]["backend"] == "sample_production"
    assert music_events[-1][1]["sample_library_policy"] == "soundfont_only"
    assert "ai_provider" not in music_events[-1][1]


def test_composer_panel_exposes_sample_asset_connection(tmp_path: Path) -> None:
    app = _app()
    from app.music_composer import compose_music

    composition = compose_music(
        prompt="sample asset connection test",
        duration_ms=16000,
        genre="electronic",
        mood="confident",
        key="C minor",
        bpm=124,
    ).to_dict()
    panel = ComposerPanel()
    panel.resize(760, 720)
    panel.show()
    music_events = []
    panel.music_lab_action_requested.connect(lambda action, params: music_events.append((action, params)))
    panel.set_music_composition(composition)
    app.processEvents()

    assert panel._music_sample_library.accessibleName() == "Composer sample library policy"
    assert "Installed:" in panel._music_sample_status.text()

    panel._music_sample_library.setCurrentText("diagnostic synth")
    panel._request_music_preview()

    assert music_events[-1][0] == "music.render.preview"
    assert music_events[-1][1]["sample_library_policy"] == "procedural_only"


def test_composer_panel_master_fx_reuses_sound_editor_effect_action(tmp_path: Path) -> None:
    app = _app()
    from app.music_composer import compose_music

    composition = compose_music(
        prompt="composer master fx",
        duration_ms=16000,
        genre="electronic",
        mood="confident",
        key="C minor",
        bpm=124,
    ).to_dict()
    panel = ComposerPanel()
    panel.resize(760, 760)
    panel.show()
    music_events = []
    panel.music_lab_action_requested.connect(lambda action, params: music_events.append((action, params)))
    panel.set_music_composition(composition)
    app.processEvents()

    assert panel.findChild(QWidget, "ComposerMasterFxPanel") is not None

    panel._music_roles.setCurrentText("mix only")
    panel._apply_master_fx_preset("wide")
    panel._request_apply_master_fx()

    action, params = music_events[-1]
    assert action == "music.apply_master_fx"
    assert params["composition_id"] == composition["id"]
    assert params["role"] == "mix"
    assert params["effects"]["ai_master"]["enabled"] is True
    assert params["effects"]["ai_master"]["width"] == 138
    assert params["effects"]["reverb"]["enabled"] is True
    assert params["effects"]["loudness"]["enabled"] is True
    assert set(params["effects"]) == {"ai_master", "reverb", "loudness"}


def test_workbench_music_composition_opens_standalone_composer(tmp_path: Path) -> None:
    app = _app()
    from app.music_composer import compose_music
    from app.workbench_panel import WorkbenchPanel

    composition = compose_music(
        prompt="standalone composer",
        duration_ms=12000,
        genre="electronic",
        mood="clear",
    ).to_dict()
    panel = WorkbenchPanel()
    panel.resize(744, 620)
    panel.show()

    assert getattr(panel, "_composer_panel", None) is None

    panel.set_music_lab_composition(composition)
    app.processEvents()

    composer = panel._composer_panel
    assert isinstance(composer, ComposerPanel)
    assert panel._inspector_tab == "audio"
    assert isinstance(panel._composer_window, ComposerWindow)
    assert panel._composer_window.isVisible() is True
    assert getattr(panel, "_composer_scroll", None) is None
    assert panel._composer_button.isChecked() is False
    assert composer.findChild(QWidget, "ComposerArrangementView") is not None
    assert getattr(panel, "_sound_editor_scroll", None) is None or panel._sound_editor_scroll.isVisible() is False


def test_sound_editor_panel_expands_advanced_lab_inline(tmp_path: Path) -> None:
    app = _app()
    audio_path = tmp_path / "advanced.wav"
    audio_path.write_bytes(b"advanced")
    clip = AudioClip(id=81, source_path=audio_path, duration_ms=4000, trim_end_ms=4000)
    panel = SoundEditorPanel()
    panel.resize(420, 760)
    panel.show()
    events = []
    panel.advanced_lab_requested.connect(lambda track, current_clip: events.append((track, current_clip)))

    panel.set_clip(clip, track="track-a", context_label="Timeline Audio", context_key="timeline:1:81")
    collapsed_min_height = panel.minimumHeight()
    panel._request_advanced_lab()
    app.processEvents()

    assert events == []
    assert panel._advanced_expanded is True
    assert panel._advanced_lab_panel.isHidden() is False
    assert panel._advanced_lab_host.isVisible() is True
    assert panel._advanced_lab_host.minimumHeight() >= SOUND_EDITOR_ADVANCED_LAB_HOST_HEIGHT
    assert panel._advanced_lab_host.geometry().top() > panel._advanced_dock_row.geometry().bottom()
    assert panel.minimumHeight() >= SOUND_EDITOR_PANEL_ADVANCED_MIN_HEIGHT
    assert panel.minimumHeight() > collapsed_min_height
    assert panel._jog_shuttle.isVisible() is True
    assert panel._waveform_strip.isVisible() is True
    assert panel._spectrum_strip.isVisible() is True
    assert panel._tabs_bar.isVisible() is True
    assert panel._stack.isVisible() is True
    assert panel._advanced_lab_tab_buttons == {}
    assert panel.findChild(QWidget, "SoundLabTabs") is None
    assert panel.findChild(QWidget, "SoundLabInlineScroll") is not None
    assert panel._advanced_lab_scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOn
    assert not hasattr(panel, "_advanced_lab_stack")
    category_titles = [
        label.text()
        for label in panel.findChildren(QLabel, "SoundLabCategoryTitle")
    ]
    assert category_titles == []
    assert panel._advanced_lab_section_widgets["dialogue"].isVisible() is True
    assert panel._advanced_lab_section_widgets["timing"].isVisible() is True
    assert panel._advanced_lab_section_widgets["loudness"].isVisible() is True
    assert panel._advanced_lab_section_widgets["ai"].isVisible() is True
    assert panel._lab_dialogue_knobs.isVisible() is True
    assert panel._lab_timing_knobs.isVisible() is True
    assert panel._lab_loudness_knobs.isVisible() is True
    assert panel._lab_ai_knobs.isVisible() is True
    assert getattr(clip, "_se_advanced_lab_expanded") is True

    panel._set_advanced_lab_tab("timing")

    assert panel._advanced_lab_tab == "timing"
    assert panel._advanced_lab_section_widgets["dialogue"].isVisible() is True
    assert panel._advanced_lab_section_widgets["timing"].isVisible() is True
    assert panel._lab_dialogue_knobs.isVisible() is True
    assert panel._lab_timing_knobs.isVisible() is True

    panel._set_advanced_lab_expanded(False)
    app.processEvents()

    assert panel._advanced_expanded is False
    assert panel._advanced_lab_host.isVisible() is False
    assert panel._advanced_lab_host.maximumHeight() == 0
    assert panel.minimumHeight() == SOUND_EDITOR_PANEL_MIXER_MIN_HEIGHT


def test_sound_editor_inline_advanced_lab_updates_real_effect_state(tmp_path: Path) -> None:
    _app()
    audio_path = tmp_path / "advanced_controls.wav"
    audio_path.write_bytes(b"advanced")
    clip = AudioClip(id=82, source_path=audio_path, duration_ms=4000, trim_end_ms=4000)
    panel = SoundEditorPanel()

    panel.set_clip(clip, context_label="Timeline Audio", context_key="timeline:1:82")
    panel._set_advanced_lab_expanded(True)
    panel._dialogue_strength._slider.setValue(65)
    panel._noise_reduction._slider.setValue(85)
    panel._time_ratio._slider.setValue(132)
    panel._target_lufs._slider.setValue(-180)

    assert clip.effects["dialogue_cleanup"]["enabled"]
    assert clip.effects["dialogue_cleanup"]["strength"] == 0.65
    assert clip.effects["dialogue_cleanup"]["noise_reduction"] == 8.5
    assert clip.effects["time_stretch"]["enabled"]
    assert clip.effects["time_stretch"]["ratio"] == 1.32
    assert clip.effects["loudness"]["enabled"]
    assert clip.effects["loudness"]["target_i"] == -18.0


def test_sound_editor_advanced_lab_knobs_are_interactive_common_knobs(tmp_path: Path) -> None:
    _app()
    from app.knob_widget import KnobWidget

    audio_path = tmp_path / "advanced_knobs.wav"
    audio_path.write_bytes(b"advanced")
    clip = AudioClip(id=83, source_path=audio_path, duration_ms=4000, trim_end_ms=4000)
    panel = SoundEditorPanel()

    panel.set_clip(clip, context_label="Timeline Audio", context_key="timeline:1:83")
    panel._set_advanced_lab_expanded(True)
    panel._set_advanced_lab_tab("timing")

    timing_knobs = panel._lab_timing_knobs.findChildren(KnobWidget)
    assert len(timing_knobs) == 4
    assert panel._lab_timing_knobs.minimumHeight() >= KnobWidget.CELL_HEIGHT + 28

    freq = panel._lab_timing_knobs.knob("freq")
    threshold = panel._lab_timing_knobs.knob("threshold")
    stretch = panel._lab_timing_knobs.knob("stretch")
    assert freq is not None
    assert threshold is not None
    assert stretch is not None
    assert freq.objectName() == "SoundLabMasterKnob"
    assert freq.property("ledAfterglow") is True
    assert str(freq.property("dialTextureResource")).endswith("jog_dial_metal_sparse_base.png")

    freq.setValue(8200.0)
    threshold.setValue(-24.5)
    stretch.setValue(1.35)

    assert max(getattr(freq, "_slot_glow_values", [0.0])) > 0.0
    assert clip.effects["deesser"]["enabled"]
    assert clip.effects["deesser"]["freq"] == 8200
    assert clip.effects["deesser"]["threshold"] == -24.5
    assert clip.effects["time_stretch"]["enabled"]
    assert clip.effects["time_stretch"]["ratio"] == 1.35
    assert panel._lab_deesser_freq._slider.value() == 8200
    assert panel._lab_deesser_threshold._slider.value() == -245
    assert panel._time_ratio._slider.value() == 135


def test_sound_editor_advanced_lab_restores_ai_presets_and_uses_common_dial(tmp_path: Path) -> None:
    _app()
    audio_path = tmp_path / "ai_presets.wav"
    audio_path.write_bytes(b"ai")
    clip = AudioClip(id=84, source_path=audio_path, duration_ms=4000, trim_end_ms=4000)
    panel = SoundEditorPanel()

    panel.set_clip(clip, context_label="Timeline Audio", context_key="timeline:1:84")
    panel._set_advanced_lab_expanded(True)

    assert panel.findChild(QWidget, "SoundMacroJogBank") is None
    assert panel._lab_jog_shuttle.property("role") == "advanced_audio_lab_dial"
    assert panel._lab_jog_shuttle.findChild(QPushButton) is not None
    assert panel._lab_jog_shuttle.minimumHeight() >= 126
    assert panel.findChild(QWidget, "SoundLabTabs") is None
    assert panel.findChild(QWidget, "SoundLabInlineScroll") is not None
    assert panel._lab_ai_knobs is not None

    panel._apply_ai_preset("Suno v3")

    ai = clip.effects["ai_master"]
    assert ai["enabled"] is True
    assert ai["preset"] == "Suno v3"
    assert ai["air"] == 5.0
    assert ai["clarity"] == 60.0
    assert ai["width"] == 130.0
    assert panel._advanced_lab_tab == "ai"
    assert not panel._tab_buttons["ai"].isChecked()
    assert panel._ai_preset_buttons["Suno v3"].property("selected") is True

    panel._lab_ai_clarity._slider.setValue(73)

    assert clip.effects["ai_master"]["preset"] == "Custom"
    assert clip.effects["ai_master"]["clarity"] == 73


def test_sound_editor_eq_graph_updates_real_effect_state(tmp_path: Path) -> None:
    _app()
    audio_path = tmp_path / "eq_graph.wav"
    audio_path.write_bytes(b"eq")
    clip = AudioClip(id=9, source_path=audio_path, duration_ms=3000, trim_end_ms=3000)
    panel = SoundEditorPanel()

    panel.set_clip(clip, context_label="Timeline Audio", context_key="timeline:1:9")
    panel._set_eq_gain_from_graph(2, 6.27)

    assert clip.effects["eq"]["enabled"]
    assert clip.effects["eq"]["high"]["gain"] == 6.3


def test_sound_editor_dynamics_graph_updates_real_effect_state(tmp_path: Path) -> None:
    _app()
    audio_path = tmp_path / "dyn_graph.wav"
    audio_path.write_bytes(b"dyn")
    clip = AudioClip(id=10, source_path=audio_path, duration_ms=3000, trim_end_ms=3000)
    panel = SoundEditorPanel()

    panel.set_clip(clip, context_label="Timeline Audio", context_key="timeline:1:10")
    panel._set_dynamics_from_graph(-32.43, 8.76)

    assert clip.effects["comp"]["enabled"]
    assert clip.effects["comp"]["threshold"] == -32.4
    assert clip.effects["comp"]["ratio"] == 8.8


def test_sound_editor_fx_graph_updates_real_effect_state(tmp_path: Path) -> None:
    _app()
    audio_path = tmp_path / "fx_graph.wav"
    audio_path.write_bytes(b"fx")
    clip = AudioClip(id=11, source_path=audio_path, duration_ms=3000, trim_end_ms=3000)
    panel = SoundEditorPanel()

    panel.set_clip(clip, context_label="Timeline Audio", context_key="timeline:1:11")
    panel._set_fx_value_from_graph(0, 44.2)
    panel._set_fx_value_from_graph(1, 18.8)
    panel._set_fx_value_from_graph(2, 62.3)

    assert clip.effects["reverb"]["enabled"]
    assert clip.effects["delay"]["enabled"]
    assert clip.effects["deesser"]["enabled"]
    assert clip.effects["reverb"]["mix"] == 44.2
    assert clip.effects["delay"]["mix"] == 18.8
    assert clip.effects["deesser"]["reduction"] == 62.3


def test_sound_editor_ai_graph_updates_real_effect_state(tmp_path: Path) -> None:
    _app()
    audio_path = tmp_path / "ai_graph.wav"
    audio_path.write_bytes(b"ai")
    clip = AudioClip(id=12, source_path=audio_path, duration_ms=3000, trim_end_ms=3000)
    panel = SoundEditorPanel()

    panel.set_clip(clip, context_label="Timeline Audio", context_key="timeline:1:12")
    panel._set_ai_value_from_graph(0, 3.42)
    panel._set_ai_value_from_graph(1, 51.0)
    panel._set_ai_value_from_graph(2, 37.0)
    panel._set_ai_value_from_graph(3, 128.0)
    panel._set_ai_value_from_graph(4, 22.0)
    panel._set_ai_value_from_graph(5, 64.0)

    assert clip.effects["ai_master"]["enabled"]
    assert clip.effects["ai_master"]["air"] == 3.4
    assert clip.effects["ai_master"]["clarity"] == 51
    assert clip.effects["ai_master"]["warmth"] == 37
    assert clip.effects["ai_master"]["width"] == 128
    assert clip.effects["ai_master"]["punch"] == 22
    assert clip.effects["ai_master"]["excite"] == 64


def test_sound_editor_graph_double_click_reset_defaults(tmp_path: Path) -> None:
    _app()
    audio_path = tmp_path / "reset_graph.wav"
    audio_path.write_bytes(b"reset")
    clip = AudioClip(id=13, source_path=audio_path, duration_ms=3000, trim_end_ms=3000)
    panel = SoundEditorPanel()

    panel.set_clip(clip, context_label="Timeline Audio", context_key="timeline:1:13")
    panel._set_eq_gain_from_graph(2, 6.0)
    panel._set_dynamics_from_graph(-31.0, 9.0)
    panel._set_fx_value_from_graph(0, 55.0)
    panel._set_ai_value_from_graph(3, 144.0)

    panel._eq_graph._reset_handle(2)
    panel._dyn_graph._reset_handle(1)
    panel._fx_graph._reset_handle(0)
    panel._ai_graph._reset_handle(3)

    assert clip.effects["eq"]["high"]["gain"] == 0.0
    assert clip.effects["comp"]["threshold"] == -31.0
    assert clip.effects["comp"]["ratio"] == 4.0
    assert clip.effects["reverb"]["mix"] == 20.0
    assert clip.effects["ai_master"]["width"] == 100.0


def test_sound_editor_panel_exposes_legacy_detail_controls(tmp_path: Path) -> None:
    _app()
    from types import SimpleNamespace

    audio_path = tmp_path / "full_controls.wav"
    audio_path.write_bytes(b"full")
    clip = AudioClip(id=14, source_path=audio_path, duration_ms=5000, trim_end_ms=5000)
    track = SimpleNamespace(id=3, pan=0.0)
    panel = SoundEditorPanel()

    panel.set_clip(clip, track=track, context_label="Timeline Audio", context_key="timeline:3:14")
    panel._pan._slider.setValue(-35)
    panel._eq_mid_freq._slider.setValue(2200)
    panel._eq_mid_q._slider.setValue(16)
    panel._comp_attack._slider.setValue(90)
    panel._comp_release._slider.setValue(220)
    panel._comp_knee._slider.setValue(45)
    panel._gate_reduction._slider.setValue(70)
    panel._reverb_type.setCurrentText("Plate")
    panel._reverb_size._slider.setValue(52)
    panel._reverb_decay._slider.setValue(24)
    panel._reverb_damping._slider.setValue(38)
    panel._delay_time._slider.setValue(175)
    panel._delay_feedback._slider.setValue(31)
    panel._time_algorithm.setCurrentText("rubberband")

    assert track.pan == -0.35
    assert getattr(clip, "_se_pan") == -0.35
    assert clip.effects["eq"]["mid"]["freq"] == 2200
    assert clip.effects["eq"]["mid"]["q"] == 1.6
    assert clip.effects["comp"]["attack_ms"] == 9.0
    assert clip.effects["comp"]["release_ms"] == 220
    assert clip.effects["comp"]["knee_db"] == 4.5
    assert clip.effects["gate"]["reduction"] == 70
    assert clip.effects["reverb"]["type"] == "Plate"
    assert clip.effects["reverb"]["size"] == 52
    assert clip.effects["reverb"]["decay_s"] == 2.4
    assert clip.effects["reverb"]["damping"] == 38
    assert clip.effects["delay"]["time_ms"] == 175
    assert clip.effects["delay"]["feedback"] == 31
    assert clip.effects["time_stretch"]["algorithm"] == "rubberband"

    panel._apply_basic_preset("Podcast")
    panel._apply_eq_preset("Vocal Boost")
    panel._apply_dyn_preset("Voice Strong")
    panel._apply_fx_preset("Slap Delay")

    assert clip.fade_in_ms == 500
    assert clip.effects["eq"]["mid"]["gain"] == 4.0
    assert clip.effects["comp"]["ratio"] == 6.0
    assert clip.effects["delay"]["mix"] == 40.0


def test_sound_editor_mixer_dock_edits_track_strips(tmp_path: Path) -> None:
    _app()
    from types import SimpleNamespace

    audio_path = tmp_path / "mixer.wav"
    audio_path.write_bytes(b"mixer")
    clip = AudioClip(id=15, source_path=audio_path, duration_ms=2400, trim_end_ms=2400)
    track_a = SimpleNamespace(id=3, label="Voice", bus_id="dialogue", volume=1.0, pan=0.0, muted=False, solo=False, clips=[clip])
    track_b = SimpleNamespace(id=4, label="Music", bus_id="music", volume=0.8, pan=0.0, muted=False, solo=False, clips=[])
    panel = SoundEditorPanel()
    changed = []
    panel.mixer_track_changed.connect(lambda track: changed.append(track.id))

    panel.resize(900, 720)
    panel.set_clip(clip, track=track_a, context_label="Timeline Audio", context_key="timeline:3:15")
    panel.set_mixer_tracks([track_a, track_b], active_track_id=track_a.id)
    panel._set_tab("mixer")
    strip = panel._mixer_strips[4]

    strip._fader.setValue(62)
    strip._pan.setValue(-30)
    strip._mute.setChecked(True)
    strip._solo.setChecked(True)
    strip._insert_buttons["eq"].setChecked(True)
    strip._send_buttons["reverb"].click()
    strip._auto_write.setChecked(True)
    strip._type.click()

    assert "mixer" not in panel._tab_buttons
    assert panel._tab_buttons["basic"].isChecked()
    assert panel._mixer_dock.isHidden() is False
    assert panel._mixer_card.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert panel._mixer_scroll.maximumWidth() > 720
    assert panel._mixer_scroll.height() <= 234
    assert strip.width() <= 74
    assert strip.height() <= 226
    assert track_b.volume == 0.62
    assert track_b.pan == -0.3
    assert track_b.muted is True
    assert track_b.solo is True
    assert track_b.insert_slots[0]["id"] == "eq"
    assert track_b.insert_slots[0]["enabled"] is True
    assert track_b.sends["reverb"] == 0.25
    assert track_b.automation_read is True
    assert track_b.automation_write is True
    assert track_b.track_type == "sfx"
    assert panel._mixer_strips[4]._name.text().startswith("Music")
    masters = [child for child in panel.findChildren(QWidget, "SoundMixerMasterStrip") if not child.isHidden()]
    assert len(masters) == 1
    vu = masters[0].findChild(QWidget, "SoundMixerStereoVu")
    assert vu is not None
    assert not vu.grab().isNull()
    assert changed[-1] == 4
