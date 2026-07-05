from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.audio_tracks import AudioClip, AudioTrack, probe_audio_duration_ms
from app.i18n import tr
from app.icons import app_icon, icon_size
from app.style import (
    COLOR_ACCENT_BLUE,
    COLOR_BG_L3,
    COLOR_BG_L5,
    COLOR_BORDER_DEFAULT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_TERTIARY,
)
from app.video_editor_audio_shared import _block_signals, _format_ms
from app.video_editor_audio_waveform_widgets import ClipWaveformView, SpectrumExtractor, SpectrumView


class SoundEditorWindow(QWidget):
    """Knob-based per-clip audio editor (Phase 1/2 of SOUND_EDITOR_SPEC).

    Layout:
        TitleBar
        FileInfo        ??filename + duration + cuts/fades counts
        Waveform        ??full trimmed peaks + playhead + cut/fade markup
        TabBar          ??Basic (live), EQ / Dynamics / Effects / Advanced (placeholders)
        TabContent
            Basic       ??6 knobs (Volume, Pan, Fade In, Fade Out, Speed, Pitch)
                         + action row (Mute, Reverse, Reset All)
                         + preset row
        Transport       - play/pause + time + volume + Apply / Close

    The six Basic-tab knob values flow into the clip (fade_in_ms, fade_out_ms)
    and the track volume slider on the main timeline. Speed / Pitch / Pan are
    stashed on the clip for later wiring into the FFmpeg export filter.
    """

    # Preset definitions (Basic tab). Values match the spec.
    BASIC_PRESETS: dict[str, dict[str, float]] = {
        "Voice Recording": dict(volume=3, pan=0, fade_in=0.1, fade_out=0.3, speed=1.0, pitch=0),
        "Background Music": dict(volume=-6, pan=0, fade_in=1.5, fade_out=2.0, speed=1.0, pitch=0),
        "Game Audio":      dict(volume=0, pan=0, fade_in=0, fade_out=0.2, speed=1.0, pitch=0),
        "Podcast":         dict(volume=2, pan=0, fade_in=0.5, fade_out=0.5, speed=1.0, pitch=0),
    }

    def __init__(self, clip: "AudioClip", parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.clip = clip
        # Maps effect-id ("eq" / "comp" / etc.) ??its "Enabled" toggle
        # button. _set_fx uses this to sync the UI when a knob touch
        # auto-enables / disables the effect.
        self._fx_enable_buttons: dict[str, QPushButton] = {}
        name = clip.display_name or "(unnamed)"
        self.setWindowTitle(tr("veditor.sound_editor.title", name=name))
        self.resize(1040, 720)
        self.setStyleSheet(self._qss())

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_title_bar(name))
        root.addWidget(self._build_file_info())

        # Waveform + spectrum are a single analysis deck so the window
        # reads as an audio workspace instead of a tall plugin dialog.
        analysis_deck = QWidget()
        analysis_deck.setObjectName("SEAnalysisDeck")
        analysis_layout = QHBoxLayout(analysis_deck)
        analysis_layout.setContentsMargins(14, 12, 14, 12)
        analysis_layout.setSpacing(10)

        wf_wrap = QWidget()
        wf_wrap.setObjectName("SEWaveformSection")
        wf_layout = QVBoxLayout(wf_wrap)
        wf_layout.setContentsMargins(12, 12, 12, 12)
        self._waveform_view = ClipWaveformView(clip, wf_wrap)
        self._waveform_view.setMinimumHeight(120)
        wf_layout.addWidget(self._waveform_view)
        analysis_layout.addWidget(wf_wrap, stretch=3)

        scope_wrap = QWidget()
        scope_wrap.setObjectName("SEScopePanel")
        scope_layout = QVBoxLayout(scope_wrap)
        scope_layout.setContentsMargins(12, 12, 12, 12)
        scope_layout.setSpacing(8)
        scope_title = QLabel("SPECTRUM")
        scope_title.setObjectName("SEScopeTitle")
        scope_layout.addWidget(scope_title)
        self._spectrum_view = SpectrumView()
        self._spectrum_view.setMinimumHeight(120)
        scope_layout.addWidget(self._spectrum_view, stretch=1)
        analysis_layout.addWidget(scope_wrap, stretch=1)
        root.addWidget(analysis_deck)
        self._spectrum_extractor = None  # type: SpectrumExtractor | None
        if clip.source_path is not None:
            self._start_spectrum_extractor(clip.source_path)

        root.addWidget(self._build_tab_bar())
        root.addWidget(self._build_tab_content(), stretch=1)
        root.addWidget(self._build_transport())

        # ---- Local playback engine ----
        # Construct the QMediaPlayer + QAudioOutput up front so the
        # transport-volume slider has something to bind to, but defer
        # ``setSource(...)`` until first Play / scrub ??see
        # ``_ensure_player_source_loaded``. Eager setSource here
        # collided with the WaveformExtractor / SpectrumExtractor
        # init and aborted Qt's FFmpeg backend.
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

        self._player_output = QAudioOutput(self)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._player_output)
        self._player_source_loaded: bool = False
        self._player.playbackStateChanged.connect(self._on_playback_state)
        self._player.positionChanged.connect(self._on_player_position)
        self._player_output.setVolume(0.8)
        self._transport_volume_slider.setValue(80)

        # Wire waveform-view signals once all referenced slots exist.
        self._waveform_view.scrub_requested.connect(self._on_waveform_scrub)
        self._waveform_view.selection_changed.connect(self._on_waveform_selection)
        self._waveform_view.selection_cleared.connect(self._on_waveform_selection_cleared)
        self._waveform_view.marker_right_clicked.connect(self._on_marker_right_clicked)

    # -------- Spectrum helpers --------

    def _start_spectrum_extractor(self, path: "Path") -> None:
        """Launch a fresh SpectrumExtractor thread for *path*."""
        if self._spectrum_extractor is not None:
            self._spectrum_extractor.quit()
            self._spectrum_extractor.wait(500)
        ext = SpectrumExtractor(path)
        ext.ready.connect(self._spectrum_view.set_bins)
        ext.finished.connect(ext.deleteLater)
        self._spectrum_extractor = ext
        ext.start()

    def refresh_spectrum(self) -> None:
        """Restart the spectrum analysis (call after changing source_path)."""
        if self.clip.source_path is not None:
            self._start_spectrum_extractor(self.clip.source_path)
        else:
            self._spectrum_view.set_bins(None)

    # -------- QSS --------


    # -------- section builders --------

    def _build_title_bar(self, name: str) -> QWidget:
        bar = QWidget()
        bar.setObjectName("SETitleBar")
        bar.setFixedHeight(44)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 12, 0)
        icon = QLabel("A")
        icon.setStyleSheet("font-size: 16px;")
        title = QLabel(tr("veditor.sound_editor.header"))
        title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-weight: 600; font-size: 13px;")
        sub = QLabel(f"- {name}")
        sub.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 12px;")
        lay.addWidget(icon)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addStretch(1)
        return bar

    def _build_file_info(self) -> QWidget:
        info = QWidget()
        info.setObjectName("SEFileInfo")
        lay = QVBoxLayout(info)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(6)
        name = QLabel(self.clip.display_name or "(unnamed)")
        name.setStyleSheet("font-size: 15px; font-weight: 600;")
        lay.addWidget(name)

        meta_bits: list[str] = []
        if self.clip.duration_ms > 0:
            meta_bits.append(f"Duration {self.clip.duration_ms / 1000.0:.2f} s")
        meta_bits.append(f"Cuts: {len(self.clip.cuts)}")
        meta_bits.append(f"Fades: {len(self.clip.fades)}")
        if self.clip.source_path is not None:
            meta_bits.append(f"File: {self.clip.source_path.name}")
        meta = QLabel("   ".join(meta_bits))
        meta.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px; font-family: Consolas, monospace;"
        )
        meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(meta)
        return info


    def _build_tab_content(self) -> QWidget:
        from PySide6.QtWidgets import QStackedWidget

        self._tab_stack = QStackedWidget()
        self._tab_stack.setObjectName("SEContent")
        # Wrap every tab in a QScrollArea so when the sound editor is
        # resized short the tab content scrolls instead of clipping
        # knob rows / clamping section headers off-screen.
        self._tab_stack.addWidget(self._wrap_tab_in_scroll(self._build_basic_tab()))      # 0
        self._tab_stack.addWidget(self._wrap_tab_in_scroll(self._build_eq_tab()))          # 1
        self._tab_stack.addWidget(self._wrap_tab_in_scroll(self._build_dynamics_tab()))    # 2
        self._tab_stack.addWidget(self._wrap_tab_in_scroll(self._build_effects_tab()))     # 3
        self._tab_stack.addWidget(self._wrap_tab_in_scroll(self._build_advanced_tab()))    # 4
        self._tab_stack.addWidget(self._wrap_tab_in_scroll(self._build_ai_master_tab()))   # 5
        return self._tab_stack

    def _wrap_tab_in_scroll(self, tab_widget: QWidget) -> QWidget:
        """Wrap a sound-editor tab in a QScrollArea. Vertical scroll
        appears only when the tab's natural height exceeds the
        viewport (the editor lives in a fixed-size dialog so this
        kicks in the moment the user shrinks it)."""
        scroll = QScrollArea()
        scroll.setWidget(tab_widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        return scroll


    # ========= EQ tab =========

    EQ_PRESETS: dict[str, dict] = {
        "Flat":        {"low_g": 0, "mid_g": 0, "high_g": 0},
        "Vocal Boost": {"low_g": -2, "mid_g": 4, "high_g": 2},
        "Bass Boost":  {"low_g": 6, "mid_g": 0, "high_g": 0},
        "Podcast":     {"low_g": -3, "mid_g": 2, "high_g": 3},
        "Treble Cut":  {"low_g": 0, "mid_g": 0, "high_g": -4},
    }


    def _apply_eq_preset(self, name: str) -> None:
        p = self.EQ_PRESETS.get(name) or {}
        eq = self.clip.effects["eq"]
        eq["low"]["gain"]  = p.get("low_g", 0)
        eq["mid"]["gain"]  = p.get("mid_g", 0)
        eq["high"]["gain"] = p.get("high_g", 0)
        eq["enabled"] = True
        self._eq_enabled_btn.setChecked(True)
        self._eq_curve.refresh()
        self._rebuild_tab_ui()

    # ========= Dynamics tab =========

    DYN_PRESETS: dict[str, dict] = {
        "Voice Gentle": {"thr": -20, "ratio": 3, "atk": 5, "rel": 120, "makeup": 2, "knee": 4},
        "Voice Strong": {"thr": -24, "ratio": 6, "atk": 2, "rel": 80,  "makeup": 4, "knee": 2},
        "Podcast":      {"thr": -18, "ratio": 4, "atk": 5, "rel": 150, "makeup": 3, "knee": 3},
    }


    def _apply_dyn_preset(self, name: str) -> None:
        p = self.DYN_PRESETS.get(name) or {}
        c = self.clip.effects["comp"]
        c["threshold"] = p.get("thr", c["threshold"])
        c["ratio"]     = p.get("ratio", c["ratio"])
        c["attack_ms"] = p.get("atk", c["attack_ms"])
        c["release_ms"] = p.get("rel", c["release_ms"])
        c["makeup_db"] = p.get("makeup", c["makeup_db"])
        c["knee_db"]   = p.get("knee", c["knee_db"])
        c["enabled"] = True
        self._comp_enabled_btn.setChecked(True)
        self._rebuild_tab_ui()

    # ========= Effects tab =========

    FX_PRESETS: dict[str, dict] = {
        "Small Room":   {"type": "Room",   "size": 20, "decay": 0.8, "damp": 60, "mix": 20},
        "Concert Hall": {"type": "Hall",   "size": 80, "decay": 3.0, "damp": 30, "mix": 35},
        "Plate":        {"type": "Plate",  "size": 50, "decay": 2.0, "damp": 40, "mix": 30},
        "Spring":       {"type": "Spring", "size": 30, "decay": 1.5, "damp": 50, "mix": 25},
        "Slap Delay":   {"type": "Room",   "size": 15, "decay": 0.5, "damp": 50, "mix": 15,
                         "_delay": {"time_ms": 150, "feedback": 0, "mix": 40}},
    }


    def _apply_fx_preset(self, name: str) -> None:
        p = self.FX_PRESETS.get(name) or {}
        rev = self.clip.effects["reverb"]
        rev["type"] = p.get("type", rev["type"])
        rev["size"] = p.get("size", rev["size"])
        rev["decay_s"] = p.get("decay", rev["decay_s"])
        rev["damping"] = p.get("damp", rev["damping"])
        rev["mix"] = p.get("mix", rev["mix"])
        rev["enabled"] = True
        self._rev_enabled_btn.setChecked(True)
        # Slap Delay also drives the delay section.
        if "_delay" in p:
            d = self.clip.effects["delay"]
            d.update(p["_delay"])
            d["enabled"] = True
            self._delay_enabled_btn.setChecked(True)
        self._rebuild_tab_ui()

    # ========= Advanced tab =========


    def _refresh_markers_list(self) -> None:
        if not hasattr(self, "_markers_list"):
            return
        self._markers_list.clear()
        for i, m_ms in enumerate(self._markers()):
            from PySide6.QtWidgets import QListWidgetItem
            it = QListWidgetItem(f"#{i + 1}   {_format_ms(int(m_ms))}")
            it.setData(Qt.ItemDataRole.UserRole, int(m_ms))
            self._markers_list.addItem(it)

    def _on_marker_list_dblclick(self, item) -> None:
        ms = int(item.data(Qt.ItemDataRole.UserRole) or 0)
        try:
            self._player.setPosition(ms)
        except Exception:
            pass

    # ========= AI Master tab =========

    # Per-model tuning for AI-generated music. Values are percentages /
    # dB matching the AI Master knob ranges. ``width`` is bipolar with
    # 100 as the neutral center.
    AI_PRESETS: dict[str, dict] = {
        "Suno v3":    {"air": 5, "clarity": 60, "warmth": 40, "width": 130, "punch": 50, "excite": 70},
        "Suno v4":    {"air": 3, "clarity": 50, "warmth": 30, "width": 120, "punch": 40, "excite": 50},
        "Udio":       {"air": 4, "clarity": 45, "warmth": 35, "width": 110, "punch": 55, "excite": 60},
        "ACE-Step":   {"air": 6, "clarity": 55, "warmth": 50, "width": 140, "punch": 45, "excite": 75},
        "Generic AI": {"air": 4, "clarity": 50, "warmth": 40, "width": 120, "punch": 50, "excite": 60},
        "Custom":     {"air": 0, "clarity": 0,  "warmth": 0,  "width": 100, "punch": 0,  "excite": 0},
    }



    def _owning_audio_track(self):
        parent = self.parent()
        if parent is None:
            return None
        tracks = getattr(parent, "_audio_tracks", None) or []
        for track in tracks:
            if self.clip in getattr(track, "clips", []):
                return track
        return None

    def _apply_audio_library_preset(self, preset) -> None:
        from app.audio_tracks import default_effects_state
        from app.audio_workflow import apply_track_mix_preset
        from app.preset_library import apply_audio_preset_to_clip

        defaults = default_effects_state()
        if not isinstance(getattr(self.clip, "effects", None), dict):
            self.clip.effects = defaults
        else:
            for key, value in defaults.items():
                self.clip.effects.setdefault(key, value)

        if not apply_audio_preset_to_clip(self.clip, preset):
            return

        track = self._owning_audio_track()
        if track is not None:
            tags = {str(tag).lower() for tag in getattr(preset, "tags", ())}
            if "dialogue" in tags or "voice" in tags or "podcast" in tags:
                apply_track_mix_preset(track, {
                    "bus_id": "dialogue",
                    "label": getattr(track, "label", "") or "Dialogue",
                })
            elif "music" in tags:
                apply_track_mix_preset(track, {
                    "bus_id": "music",
                    "label": getattr(track, "label", "") or "Music",
                })
        self._refresh_timeline_row()
        self._rebuild_tab_ui()


    def _set_separation_busy(self, busy: bool) -> None:
        btn = getattr(self, "_stem_separate_btn", None)
        if btn is not None:
            btn.setEnabled(not busy)
            btn.setText(
                tr("veditor.sound_editor.stems.running")
                if busy else tr("veditor.sound_editor.stems.button")
            )
        combo = getattr(self, "_stem_method_combo", None)
        if combo is not None:
            combo.setEnabled(not busy)

    def _on_separate_vocals_clicked(self) -> None:
        if self.clip.source_path is None:
            return
        worker = getattr(self, "_stem_worker", None)
        if worker is not None and worker.isRunning():
            return

        out_root = QFileDialog.getExistingDirectory(
            self,
            tr("veditor.sound_editor.stems.choose_dir"),
            str(self.clip.source_path.parent),
        )
        if not out_root:
            return

        from PySide6.QtWidgets import QProgressDialog
        from app.audio_separation import AudioSeparationWorker, planned_separation_method

        prefer_demucs = True
        combo = getattr(self, "_stem_method_combo", None)
        if combo is not None:
            prefer_demucs = bool(combo.currentData())
        method_hint = planned_separation_method(prefer_demucs=prefer_demucs)

        self._stem_progress = QProgressDialog(
            f"{tr('veditor.sound_editor.stems.progress')}\n{method_hint}",
            tr("paint.btn.cancel"),
            0,
            0,
            self,
        )
        self._stem_progress.setWindowTitle(tr("veditor.sound_editor.stems.title"))
        self._stem_progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._stem_progress.setMinimumDuration(0)
        self._stem_progress.canceled.connect(self._cancel_stem_separation)
        self._stem_progress.show()

        self._set_separation_busy(True)
        self._stem_worker = AudioSeparationWorker(
            self.clip.source_path,
            out_root,
            parent=self,
            prefer_demucs=prefer_demucs,
        )
        self._stem_worker.done.connect(self._on_stem_separation_done)
        self._stem_worker.failed.connect(self._on_stem_separation_failed)
        self._stem_worker.cancelled.connect(self._on_stem_separation_cancelled)
        self._stem_worker.stage.connect(
            lambda msg: self._stem_progress.setLabelText(
                f"{tr('veditor.sound_editor.stems.progress')}\n{msg}"
            ) if getattr(self, "_stem_progress", None) is not None else None
        )
        self._stem_worker.finished.connect(self._stem_worker.deleteLater)
        self._stem_worker.finished.connect(lambda: setattr(self, "_stem_worker", None))
        self._stem_worker.start()

    def _cancel_stem_separation(self) -> None:
        worker = getattr(self, "_stem_worker", None)
        if worker is not None and worker.isRunning():
            worker.cancel()

    def _on_stem_separation_cancelled(self) -> None:
        dlg = getattr(self, "_stem_progress", None)
        if dlg is not None:
            dlg.close()
            self._stem_progress = None
        self._set_separation_busy(False)

    def _on_stem_separation_done(
        self,
        vocals_path: str,
        instrumental_path: str,
        method: str,
        note: str,
    ) -> None:
        dlg = getattr(self, "_stem_progress", None)
        if dlg is not None:
            dlg.close()
            self._stem_progress = None
        self._set_separation_busy(False)

        added = self._add_separated_stems_to_timeline(
            Path(vocals_path),
            Path(instrumental_path),
        )
        body_key = (
            "veditor.sound_editor.stems.success_body_timeline"
            if added else "veditor.sound_editor.stems.success_body"
        )
        QMessageBox.information(
            self,
            tr("veditor.sound_editor.stems.success_title"),
            tr(
                body_key,
                vocals=vocals_path,
                instrumental=instrumental_path,
                method=method,
                note=note or "",
            ),
        )

    def _on_stem_separation_failed(self, reason: str) -> None:
        dlg = getattr(self, "_stem_progress", None)
        if dlg is not None:
            dlg.close()
            self._stem_progress = None
        self._set_separation_busy(False)
        QMessageBox.warning(
            self,
            tr("veditor.sound_editor.stems.failed_title"),
            tr("veditor.sound_editor.stems.failed_body", reason=reason),
        )

    def _add_separated_stems_to_timeline(
        self,
        vocals_path: Path,
        instrumental_path: Path,
    ) -> bool:
        parent = self.parent()
        if parent is None:
            return False
        needed = (
            "_audio_tracks",
            "_insert_audio_track_widget",
            "_audio_mixer",
            "_start_waveform_extraction",
            "_refresh_player_tracks",
        )
        if not all(hasattr(parent, name) for name in needed):
            return False

        import copy as _copy

        def _make_track(path: Path, label: str):
            duration = probe_audio_duration_ms(path)
            if duration <= 0:
                return None
            tid = parent._next_track_id
            parent._next_track_id += 1
            trim_start = min(max(0, int(self.clip.trim_start_ms)), duration)
            trim_end = int(self.clip.trim_end_ms or duration)
            trim_end = min(max(trim_start, trim_end), duration)
            clip = AudioClip(
                id=parent._next_clip_id(),
                source_path=path,
                duration_ms=duration,
                offset_ms=int(getattr(self.clip, "offset_ms", 0)),
                trim_start_ms=trim_start,
                trim_end_ms=trim_end,
                fade_in_ms=int(getattr(self.clip, "fade_in_ms", 0)),
                fade_out_ms=int(getattr(self.clip, "fade_out_ms", 0)),
                fades=_copy.deepcopy(getattr(self.clip, "fades", [])),
                cuts=_copy.deepcopy(getattr(self.clip, "cuts", [])),
            )
            return AudioTrack(id=tid, clips=[clip], label=label), clip

        created = []
        for path, label in (
            (instrumental_path, tr("veditor.sound_editor.stems.instrumental_label")),
            (vocals_path, tr("veditor.sound_editor.stems.vocals_label")),
        ):
            item = _make_track(path, label)
            if item is not None:
                created.append(item)

        if not created:
            return False

        for track, clip in created:
            parent._audio_tracks.append(track)
            parent._insert_audio_track_widget(track)
            parent._audio_mixer.add_track(track)
            parent._start_waveform_extraction(clip)

        parent._refresh_player_tracks()
        if hasattr(parent, "_update_tracks_host_width"):
            parent._update_tracks_host_width()
        panel = getattr(parent, "_audio_mixer_panel", None)
        if panel is not None and hasattr(panel, "rebuild"):
            try:
                panel.rebuild(parent._audio_tracks)
            except Exception:
                pass
        if hasattr(parent, "_register_change"):
            try:
                parent._register_change("audio stem separation")
            except Exception:
                pass
        return True

    def _apply_ai_preset(self, name: str) -> None:
        p = self.AI_PRESETS.get(name) or {}
        ai = self.clip.effects["ai_master"]
        for key in ("air", "clarity", "warmth", "width", "punch", "excite"):
            if key in p:
                ai[key] = float(p[key])
        ai["preset"] = name
        # Auto-enable unless the user explicitly picked Custom at zero.
        if name != "Custom":
            ai["enabled"] = True
        self._refresh_timeline_row()
        self._rebuild_tab_ui()

    # ========= shared helpers =========

    def _fx_header(self, title: str, fx_key: str) -> tuple[QWidget, QPushButton]:
        """Returns (header_row_widget, enable_toggle_button)."""
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 4, 0, 2)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px; "
            f"font-weight: 700; letter-spacing: 1px;"
        )
        enabled_btn = QPushButton(tr("veditor.sound_editor.fx.enabled"))
        enabled_btn.setObjectName("SEActionBtn")
        enabled_btn.setCheckable(True)
        enabled_btn.setChecked(bool(self.clip.effects[fx_key].get("enabled")))
        enabled_btn.toggled.connect(lambda on, k=fx_key: self._set_fx(k, "enabled", on))
        row.addWidget(lbl)
        row.addStretch(1)
        row.addWidget(enabled_btn)
        # Register so _set_fx can keep the UI checkbox in sync when a
        # knob touch auto-enables the effect.
        self._fx_enable_buttons[fx_key] = enabled_btn
        return container, enabled_btn

    def _preset_row(self, names, callback) -> QHBoxLayout:
        r = QHBoxLayout()
        r.setSpacing(6)
        lbl = QLabel(tr("veditor.sound_editor.basic.presets"))
        lbl.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
            f"font-weight: 700; letter-spacing: 1px;"
        )
        r.addWidget(lbl)
        for name in names:
            b = QPushButton(name)
            b.setObjectName("SEPresetBtn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c, n=name: callback(n))
            r.addWidget(b)
        r.addStretch(1)
        return r

    @staticmethod
    def _fx_is_neutral(fx_key: str, fx_state: dict) -> bool:
        """Return True when ``fx_state`` represents the identity
        transform for ``fx_key`` ??i.e. running its filter would be
        an audible no-op. Drives auto-enable/disable in _set_fx."""
        if fx_key == "eq":
            for band in ("low", "mid", "high"):
                if abs(float((fx_state.get(band) or {}).get("gain", 0.0))) > 0.05:
                    return False
            return True
        if fx_key == "comp":
            return abs(float(fx_state.get("ratio", 1.0)) - 1.0) < 0.05
        if fx_key == "gate":
            return float(fx_state.get("reduction", 0.0)) < 0.5
        if fx_key == "reverb":
            return float(fx_state.get("mix", 0.0)) < 0.5
        if fx_key == "delay":
            return float(fx_state.get("mix", 0.0)) < 0.5
        if fx_key == "deesser":
            return float(fx_state.get("reduction", 0.0)) < 0.5
        if fx_key == "time_stretch":
            return abs(float(fx_state.get("ratio", 1.0)) - 1.0) < 0.01
        if fx_key == "dialogue_cleanup":
            return not bool(fx_state.get("enabled"))
        if fx_key == "loudness":
            return not bool(fx_state.get("enabled"))
        if fx_key == "ai_master":
            keys = ("air", "clarity", "warmth", "width", "punch", "excite")
            return all(
                abs(float(fx_state.get(k, 0.0))) < 0.5 for k in keys
            )
        return False

    def _set_fx(self, fx_key: str, sub_key, value) -> None:
        """Write a nested effect-state value. ``sub_key`` may be a
        string (top-level) or a tuple (band, field) for the 3-band EQ.

        Auto-enable/disable: when a knob touch (any sub_key other than
        ``enabled``) leaves the effect in its neutral state we mark it
        disabled, otherwise we enable it ??saves the user from having
        to remember the explicit toggle and matches the DAW convention
        of "knob away from zero = effect engaged"."""
        fx = self.clip.effects[fx_key]
        if isinstance(sub_key, tuple):
            a, b = sub_key
            fx[a][b] = value
        else:
            fx[sub_key] = value
        if sub_key != "enabled":
            desired = not self._fx_is_neutral(fx_key, fx)
            if bool(fx.get("enabled")) != desired:
                fx["enabled"] = desired
                btn = self._fx_enable_buttons.get(fx_key)
                if btn is not None:
                    with _block_signals(btn):
                        btn.setChecked(desired)
        # Refresh dependent views.
        if fx_key == "eq" and hasattr(self, "_eq_curve"):
            self._eq_curve.refresh()
        self._refresh_timeline_row()

    def _rebuild_tab_ui(self) -> None:
        """Preset application changes many knob values at once ??the
        simplest way to keep every widget in sync is to rebuild the
        affected tab. Called after preset application."""
        current = self._tab_stack.currentIndex()
        # Rebuild just the stack panels (preserves title/waveform).
        # Wrap each one in a scroll area, same as the initial build,
        # so user-shrunk windows still get scroll bars after a preset
        # rebuild instead of clipping.
        new_panels = [
            self._wrap_tab_in_scroll(self._build_basic_tab()),
            self._wrap_tab_in_scroll(self._build_eq_tab()),
            self._wrap_tab_in_scroll(self._build_dynamics_tab()),
            self._wrap_tab_in_scroll(self._build_effects_tab()),
            self._wrap_tab_in_scroll(self._build_advanced_tab()),
            self._wrap_tab_in_scroll(self._build_ai_master_tab()),
        ]
        # Swap in place.
        for i in range(self._tab_stack.count()):
            old = self._tab_stack.widget(0)
            self._tab_stack.removeWidget(old)
            old.deleteLater()
        for p in new_panels:
            self._tab_stack.addWidget(p)
        self._tab_stack.setCurrentIndex(current)



    # -------- state plumbing --------

    def _get_track_volume(self) -> float:
        """Find the parent AudioTrack's master volume, fall back to 1.0."""
        parent = self.parent()
        if parent is not None:
            tracks = getattr(parent, "_audio_tracks", None) or []
            for t in tracks:
                if self.clip in t.clips:
                    return float(t.volume)
        return 1.0

    def _get_track_pan(self) -> float:
        """Find the parent AudioTrack's pan (-1.0..+1.0), fall back to 0."""
        parent = self.parent()
        if parent is not None:
            tracks = getattr(parent, "_audio_tracks", None) or []
            for t in tracks:
                if self.clip in t.clips:
                    return float(getattr(t, "pan", 0.0))
        return 0.0

    def _set_track_pan(self, pan_normalised: float) -> None:
        """Mirror the knob's pan onto the track + the mixer strip.
        ``pan_normalised`` is -1.0..+1.0 (the format build_audio_filter
        + the mixer expect)."""
        parent = self.parent()
        if parent is None:
            return
        tracks = getattr(parent, "_audio_tracks", None) or []
        for t in tracks:
            if self.clip in t.clips:
                t.pan = float(pan_normalised)
                # Keep the mixer panel strip's pan slider in sync if
                # the panel is currently mounted. Like volume, we
                # avoid touching the player rebuild path ??apan only
                # runs at export, the preview ignores pan.
                panel = getattr(parent, "_audio_mixer_panel", None)
                if panel is not None and hasattr(panel, "sync_track_pan"):
                    try:
                        panel.sync_track_pan(t.id, t.pan)
                    except Exception:
                        pass
                break

    def _set_track_volume(self, vol_linear: float) -> None:
        parent = self.parent()
        if parent is None:
            return
        tracks = getattr(parent, "_audio_tracks", None) or []
        for t in tracks:
            if self.clip in t.clips:
                t.volume = float(vol_linear)
                # Update the row's slider readout. We deliberately do
                # NOT call `_audio_mixer.update_track(t)` here ??that
                # tears down and rebuilds the QMediaPlayers, which is
                # only needed on structural changes (source swap, clip
                # add/remove). For a volume tweak the AudioMixer's
                # 30 ms volume timer reads `t.volume` directly, so the
                # change reaches the output without a rebuild.
                row = parent._audio_rows.get(t.id)
                if row is not None:
                    with _block_signals(row._volume_slider):
                        row._volume_slider.setValue(int(round(t.volume * 100)))
                break

    @staticmethod
    def _track_volume_to_db(vol_linear: float) -> float:
        """Convert linear gain (0..1.5) to dB for UI display."""
        if vol_linear <= 0.0:
            return -60.0
        return max(-60.0, 20.0 * math.log10(vol_linear))

    @staticmethod
    def _db_to_track_volume(db: float) -> float:
        if db <= -60.0:
            return 0.0
        return 10.0 ** (db / 20.0)

    def _switch_tab(self, tab_id: str) -> None:
        idx = {
            "basic": 0, "eq": 1, "dynamics": 2, "effects": 3,
            "advanced": 4, "ai_master": 5,
        }.get(tab_id, 0)
        self._tab_stack.setCurrentIndex(idx)
        # Sync checked state (QButtonGroup should handle, but be defensive).
        for tid, btn in self._tab_buttons.items():
            btn.setChecked(tid == tab_id)

    # -------- knob handlers --------

    def _on_volume_knob(self, db: float) -> None:
        # Main timeline + export use the track's linear volume.
        linear = self._db_to_track_volume(db)
        self._set_track_volume(linear)
        # Local preview: drive the editor's own player output so the
        # user hears the change immediately. The local master (the
        # transport volume slider) multiplies on top, so we cap at 1.0
        # here ??the slider can still attenuate further.
        try:
            self._player_output.setVolume(max(0.0, min(1.0, linear)))
        except Exception:
            pass

    def _on_pan_knob(self, pan: float) -> None:
        # Knob domain is -100..+100; track.pan + the apan export filter
        # work in -1.0..+1.0. Writing to the track (not the clip) is
        # what actually feeds build_audio_filter ??the previous
        # clip._se_pan stash was a dead end.
        # Qt's QMediaPlayer / QAudioOutput has no pan API so the live
        # preview stays centered; pan only becomes audible after
        # export. This matches the AudioMixerPanel's strip pan slider.
        self._set_track_pan(pan / 100.0)

    def _on_fade_in_knob(self, sec: float) -> None:
        self.clip.fade_in_ms = int(round(sec * 1000))
        self._refresh_timeline_row()
        self._waveform_view.refresh()

    def _on_fade_out_knob(self, sec: float) -> None:
        self.clip.fade_out_ms = int(round(sec * 1000))
        self._refresh_timeline_row()
        self._waveform_view.refresh()

    def _on_speed_knob(self, rate: float) -> None:
        self.clip._se_speed = rate
        # QMediaPlayer supports playbackRate natively ??let the
        # local preview respond immediately to the Speed knob.
        try:
            self._player.setPlaybackRate(float(rate))
        except Exception:
            pass

    def _on_pitch_knob(self, semitones: float) -> None:
        # Real-time pitch shifting isn't available in QMediaPlayer; the
        # value is stashed for FFmpeg export (`asetrate` + `atempo` chain).
        # No audible local preview change for now.
        self.clip._se_pitch = semitones

    def _on_mute_toggled(self, muted: bool) -> None:
        # Implement mute as a volume-knob override: record the current
        # volume, swap to silence, and restore on un-mute.
        if muted:
            self._muted_restore_db = self._knob_volume.value()
            self._knob_volume.setValue(-60.0)
        else:
            restore = getattr(self, "_muted_restore_db", 0.0)
            self._knob_volume.setValue(restore)

    def _reset_basic_to_defaults(self) -> None:
        self._knob_volume.setValue(0.0)
        self._knob_pan.setValue(0.0)
        self._knob_fade_in.setValue(0.0)
        self._knob_fade_out.setValue(0.0)
        self._knob_speed.setValue(1.0)
        self._knob_pitch.setValue(0.0)
        self._btn_mute.setChecked(False)
        self._btn_reverse.setChecked(False)

    def _apply_preset(self, name: str) -> None:
        preset = self.BASIC_PRESETS.get(name)
        if preset is None:
            return
        self._knob_volume.setValue(preset["volume"])
        self._knob_pan.setValue(preset["pan"])
        self._knob_fade_in.setValue(preset["fade_in"])
        self._knob_fade_out.setValue(preset["fade_out"])
        self._knob_speed.setValue(preset["speed"])
        self._knob_pitch.setValue(preset["pitch"])

    # -------- transport --------

    def _toggle_play(self) -> None:
        from PySide6.QtMultimedia import QMediaPlayer
        # Lazy-load the source the first time the user hits Play ??
        # see the SoundEditorWindow __init__ comment for why the
        # eager path was unsafe on Qt 6.11 + Windows.
        self._ensure_player_source_loaded()
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _ensure_player_source_loaded(self) -> None:
        if getattr(self, "_player_source_loaded", False):
            return
        if self.clip.source_path is None:
            return
        from app.audio_tracks import _qmedia_safe_path
        sp = _qmedia_safe_path(self.clip.source_path)
        self._player.setSource(QUrl.fromLocalFile(sp))
        self._player_source_loaded = True

    def _on_player_position(self, pos_ms: int) -> None:
        dur = self._player.duration() or self.clip.duration_ms
        self._position_label.setText(
            f"{_format_ms(int(pos_ms))} / {_format_ms(int(dur))}"
        )
        self._waveform_view.set_playhead_source_ms(int(pos_ms))
        # Loop handling: if loop is on AND a selection exists, wrap the
        # playhead back to the selection start whenever it crosses the
        # selection end. Uses the waveform view's selection as the
        # single source of truth.
        if self._loop_btn.isChecked():
            sel = self._waveform_view.selection()
            if sel is not None and pos_ms >= sel[1]:
                try:
                    self._player.setPosition(int(sel[0]))
                except Exception:
                    pass

    def _on_playback_state(self, state) -> None:
        from PySide6.QtMultimedia import QMediaPlayer
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._play_btn.setText("")
        self._play_btn.setIcon(app_icon("pause" if playing else "play", size=16, color="#FFFFFF"))
        self._play_btn.setIconSize(icon_size(16))
        if not playing:
            if state == QMediaPlayer.PlaybackState.StoppedState:
                self._waveform_view.clear_playhead()

    # -------- markers + selection + loop --------

    def _markers(self) -> list[int]:
        if not hasattr(self.clip, "_se_markers") or self.clip._se_markers is None:
            self.clip._se_markers = []
        return self.clip._se_markers

    def _add_marker_at_playhead(self) -> None:
        pos = self._player.position()
        if pos <= 0:
            return
        # Dedup within 50 ms so repeated 'M' presses don't stack.
        markers = self._markers()
        for m in markers:
            if abs(m - pos) < 50:
                return
        markers.append(int(pos))
        markers.sort()
        self._waveform_view.refresh()
        self._refresh_markers_list()

    def _go_to_prev_marker(self) -> None:
        markers = self._markers()
        if not markers:
            return
        pos = self._player.position()
        # Previous marker = the latest one strictly before pos (minus a
        # small epsilon so hitting previous-marker twice in a row actually jumps back).
        target = None
        for m in markers:
            if m < pos - 200:
                target = m
        if target is None:
            target = markers[0]
        self._player.setPosition(int(target))

    def _go_to_next_marker(self) -> None:
        markers = self._markers()
        if not markers:
            return
        pos = self._player.position()
        for m in markers:
            if m > pos + 50:
                self._player.setPosition(int(m))
                return

    def _on_waveform_scrub(self, source_ms: int) -> None:
        # QMediaPlayer position is source-ms (absolute within the file).
        self._ensure_player_source_loaded()
        try:
            self._player.setPosition(int(source_ms))
        except Exception:
            pass

    def _on_waveform_selection(self, start_ms: int, end_ms: int) -> None:
        # Park the selection on the clip so the loop logic + future
        # clip-range effects (e.g. "apply EQ to selection") can read it.
        self.clip.selection_start_ms = max(0, int(start_ms) - self.clip.trim_start_ms)
        self.clip.selection_end_ms = max(0, int(end_ms) - self.clip.trim_start_ms)

    def _on_waveform_selection_cleared(self) -> None:
        self.clip.selection_start_ms = -1
        self.clip.selection_end_ms = -1

    def _on_marker_right_clicked(self, idx: int, global_pos: QPoint) -> None:
        markers = self._markers()
        if idx < 0 or idx >= len(markers):
            return
        menu = QMenu(self)
        act_delete = menu.addAction(tr("veditor.sound_editor.marker.delete"))
        chosen = menu.exec(global_pos)
        if chosen is act_delete:
            del markers[idx]
            self._waveform_view.refresh()
            self._refresh_markers_list()

    def _apply_and_close(self) -> None:
        # All knob mutations already flow live; "Apply" is effectively
        # the same as "Close" today. Left as a separate button so the
        # upcoming effects tabs (which stage changes) have somewhere to
        # hook into.
        self._refresh_timeline_row()
        self.close()

    # ---- audio quality dropdown ----

    def _refresh_audio_quality_btn_label(self) -> None:
        from app.audio_tracks import get_audio_quality_preset
        from app import tier
        q = get_audio_quality_preset(self._audio_export_quality_id)
        label = {
            "low": "Draft",
            "standard": "Std",
            "high": "High",
            "best": "Best",
        }.get(q.id, q.id.title())
        if tier.requires_pro(q.feature_id) and not tier.is_locked(q.feature_id):
            label = f"{label} Pro"
        self._audio_quality_btn.setText(
            f"{tr('veditor.export.quality.label')}: {label}  v"
        )

    def _build_audio_quality_menu(self) -> None:
        from app.audio_tracks import AUDIO_QUALITY_PRESETS
        from app import tier
        menu = QMenu(self._audio_quality_btn)
        menu.setObjectName("AudioQualityMenu")
        menu.setStyleSheet(
            f"QMenu#AudioQualityMenu {{ "
            f"background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; "
            f"border-radius: 6px; padding: 6px; font-size: 12px; }}"
            f"QMenu#AudioQualityMenu::item {{ "
            f"padding: 8px 18px 8px 36px; border-radius: 4px; "
            f"margin: 1px 0px; }}"
            f"QMenu#AudioQualityMenu::item:selected {{ "
            f"background-color: {COLOR_BG_L5}; }}"
            f"QMenu#AudioQualityMenu::item:checked {{ "
            f"background-color: {COLOR_ACCENT_BLUE}; "
            f"color: {COLOR_TEXT_PRIMARY}; font-weight: 600; }}"
            f"QMenu#AudioQualityMenu::indicator {{ "
            f"width: 16px; height: 16px; left: 10px; }}"
        )
        for q in AUDIO_QUALITY_PRESETS:
            badge = ""
            if tier.requires_pro(q.feature_id):
                badge = "PRO  " if tier.is_locked(q.feature_id) else "PRO  "
            label = f"{badge}{tr(q.name_key)}  -  {tr(q.desc_key)}"
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(q.id == self._audio_export_quality_id)
            act.triggered.connect(
                lambda _checked=False, qid=q.id: self._on_audio_quality_picked(qid)
            )
        self._audio_quality_btn.setMenu(menu)

    def _on_audio_quality_picked(self, quality_id: str) -> None:
        from app.audio_tracks import get_audio_quality_preset
        from app import tier
        q = get_audio_quality_preset(quality_id)
        if tier.is_locked(q.feature_id):
            self._show_audio_upsell(tr(q.name_key))
            self._build_audio_quality_menu()
            return
        self._audio_export_quality_id = quality_id
        self._refresh_audio_quality_btn_label()
        self._build_audio_quality_menu()

    def _show_audio_upsell(self, feature_label: str) -> None:
        """Modal upsell shown when a Free user picks a Pro-only audio
        format. Mirrors the video editor's upsell ??same i18n keys."""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            tr("upsell.title"),
            tr("upsell.body", feature=feature_label),
        )

    def _on_export_clicked(self) -> None:
        """Render the current clip (trim + cuts + fades + effects) to a
        standalone audio file. Free tier covers MP3 + WAV; Pro formats
        appear in the dialog with a "(PRO)" suffix and trigger an
        upsell when picked by a Free user."""
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog, QMessageBox

        from app.audio_tracks import CLIP_EXPORT_FORMATS, ClipExporter
        from app import tier

        if self.clip.source_path is None:
            return

        # Free formats first (they're the only ones a Free user can
        # actually pick), Pro formats after ??keeps the default useful
        # without hiding the upsell entirely.
        order = ["mp3", "wav", "flac", "alac", "aac", "ogg"]

        def _filter_for(key: str) -> str:
            base = CLIP_EXPORT_FORMATS[key]["filter"]
            fid = CLIP_EXPORT_FORMATS[key]["feature_id"]
            if tier.is_locked(fid):
                return base.replace("(*", "(PRO) (*")
            return base

        filters = [_filter_for(k) for k in order]
        all_filters = ";;".join(filters)

        src = Path(self.clip.source_path)
        # Default filename uses the first Free format (mp3) so save
        # dialogs land somewhere usable for everyone.
        default_name = str(src.with_name(f"{src.stem}_edited.mp3"))

        out_path, chosen_filter = QFileDialog.getSaveFileName(
            self,
            tr("veditor.sound_editor.export.dialog_title"),
            default_name,
            all_filters,
            filters[0],
        )
        if not out_path:
            return

        format_key = next(
            (k for k in order if _filter_for(k) == chosen_filter),
            "mp3",
        )

        # Pro-gating: if a Free user picked a locked format, show
        # upsell and abort instead of running the encode.
        feature_id = CLIP_EXPORT_FORMATS[format_key]["feature_id"]
        if tier.is_locked(feature_id):
            label = CLIP_EXPORT_FORMATS[format_key]["label"]
            self._show_audio_upsell(label)
            return

        # Make sure the extension on disk matches the chosen format ??
        # users sometimes type a wrong extension in the save dialog.
        out_path_obj = Path(out_path)
        expected_ext = CLIP_EXPORT_FORMATS[format_key]["ext"]
        if out_path_obj.suffix.lower() != expected_ext.lower():
            out_path_obj = out_path_obj.with_suffix(expected_ext)

        # Disable the button so the user can't spam it. Re-enabled in
        # the completion/failure slots.
        self._export_btn.setEnabled(False)
        self._export_btn.setText(tr("veditor.sound_editor.export.running"))

        self._clip_exporter = ClipExporter(
            self.clip, str(out_path_obj), format_key, parent=self,
            quality_id=getattr(self, "_audio_export_quality_id", "standard"),
        )

        def _on_done(path: str) -> None:
            self._export_btn.setEnabled(True)
            self._export_btn.setText(tr("veditor.sound_editor.export"))
            QMessageBox.information(
                self,
                tr("veditor.sound_editor.export.success_title"),
                tr("veditor.sound_editor.export.success_body", path=path),
            )

        def _on_failed(reason: str) -> None:
            self._export_btn.setEnabled(True)
            self._export_btn.setText(tr("veditor.sound_editor.export"))
            QMessageBox.warning(
                self,
                tr("veditor.sound_editor.export.failed_title"),
                tr("veditor.sound_editor.export.failed_body", reason=reason),
            )

        self._clip_exporter.done.connect(_on_done)
        self._clip_exporter.failed.connect(_on_failed)
        self._clip_exporter.start()

    def _refresh_timeline_row(self) -> None:
        # Light-weight: just schedule a repaint of the matching track
        # row. We intentionally skip `_audio_mixer.update_track(t)`
        # here ??FX state (EQ / dynamics / etc.) is applied during
        # FFmpeg export, not preview, so a player rebuild would just
        # burn CPU on every knob pixel.
        parent = self.parent()
        if parent is None:
            return
        for t in getattr(parent, "_audio_tracks", None) or []:
            if self.clip in t.clips:
                row = parent._audio_rows.get(t.id)
                if row is not None:
                    row.update()
                break

    def refresh_waveform(self) -> None:
        self._waveform_view.refresh()

    def closeEvent(self, event) -> None:
        worker = getattr(self, "_stem_worker", None)
        if worker is not None and worker.isRunning():
            QMessageBox.information(
                self,
                tr("veditor.sound_editor.stems.title"),
                tr("veditor.sound_editor.stems.close_blocked"),
            )
            event.ignore()
            return
        try:
            self._player.stop()
            self._player.setSource(QUrl())
        except Exception:
            pass
        # Quit any in-flight spectrum extractor before tear-down. If we
        # let the destructor run while the QThread is still in run(),
        # Qt logs "Destroyed while thread '' is still running" and on
        # Windows the process aborts (exit code 9). We give it a short
        # grace period ??the extractor is just an ffmpeg subprocess
        # piping ~8k samples, so it normally finishes well inside this
        # window; if it doesn't, terminate() is safer than corruption.
        ext = getattr(self, "_spectrum_extractor", None)
        if ext is not None:
            try:
                ext.quit()
                if not ext.wait(800):
                    ext.terminate()
                    ext.wait(200)
            except Exception:
                pass
        super().closeEvent(event)

from app import video_editor_audio_sound_window_ui as _audio_sound_window_ui

SoundEditorWindow._qss = _audio_sound_window_ui._qss
SoundEditorWindow._build_tab_bar = _audio_sound_window_ui._build_tab_bar
SoundEditorWindow._build_basic_tab = _audio_sound_window_ui._build_basic_tab
SoundEditorWindow._build_eq_tab = _audio_sound_window_ui._build_eq_tab
SoundEditorWindow._build_dynamics_tab = _audio_sound_window_ui._build_dynamics_tab
SoundEditorWindow._build_effects_tab = _audio_sound_window_ui._build_effects_tab
SoundEditorWindow._build_advanced_tab = _audio_sound_window_ui._build_advanced_tab
SoundEditorWindow._build_ai_master_tab = _audio_sound_window_ui._build_ai_master_tab
SoundEditorWindow._build_professional_audio_preset_section = _audio_sound_window_ui._build_professional_audio_preset_section
SoundEditorWindow._build_source_separation_section = _audio_sound_window_ui._build_source_separation_section
SoundEditorWindow._build_transport = _audio_sound_window_ui._build_transport
