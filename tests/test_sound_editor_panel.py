from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget

from app.audio_tracks import AudioClip
from app.sound_editor_panel import SoundEditStateStore, SoundEditorDockWindow, SoundEditorPanel


def _app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


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

    panel._set_tab("mixer")

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
    panel._request_advanced_lab()
    app.processEvents()

    assert events == []
    assert panel._advanced_expanded is True
    assert panel._advanced_lab_panel.isHidden() is False
    assert panel._advanced_lab_host.isVisible() is True
    assert panel._jog_shuttle.isVisible() is True
    assert panel._waveform_strip.isVisible() is True
    assert panel._spectrum_strip.isVisible() is True
    assert panel._tabs_bar.isVisible() is True
    assert panel._stack.isVisible() is True
    assert getattr(clip, "_se_advanced_lab_expanded") is True


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


def test_sound_editor_advanced_lab_restores_ai_presets_and_jog_bank(tmp_path: Path) -> None:
    _app()
    audio_path = tmp_path / "ai_presets.wav"
    audio_path.write_bytes(b"ai")
    clip = AudioClip(id=84, source_path=audio_path, duration_ms=4000, trim_end_ms=4000)
    panel = SoundEditorPanel()

    panel.set_clip(clip, context_label="Timeline Audio", context_key="timeline:1:84")
    panel._set_advanced_lab_expanded(True)

    assert panel.findChild(QWidget, "SoundMacroJogBank") is not None
    assert len(panel._macro_jog_bank._specs()) == 12

    panel._apply_ai_preset("Suno v3")

    ai = clip.effects["ai_master"]
    assert ai["enabled"] is True
    assert ai["preset"] == "Suno v3"
    assert ai["air"] == 5.0
    assert ai["clarity"] == 60.0
    assert ai["width"] == 130.0
    assert panel._tab_buttons["ai"].isChecked()
    assert panel._ai_preset_buttons["Suno v3"].property("selected") is True


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


def test_sound_editor_mixer_tab_edits_track_strips(tmp_path: Path) -> None:
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

    assert panel._tab_buttons["mixer"].isChecked()
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
