"""Standalone Composer workbench panel.

Composer uses the existing music action backend, but it is deliberately not a
Sound Editor tab. The public signal names keep the older Music Lab bridge
compatible while the visible surface presents a dedicated composition tool.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QDesktopServices

from app.audio_tracks import default_effects_state
from app.sound_editor_panel import _MusicLabArrangementView, _SoundLabKnobStrip
from app.style import FONT_FAMILY, editor_scrollbar_qss


class ComposerPanel(QWidget):
    """Dedicated prompt-to-score panel for timeline music generation."""

    music_lab_action_requested = Signal(str, object)
    music_lab_selection_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ComposerPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(540)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setStyleSheet(self._qss())
        self._music_composition: dict[str, Any] | None = None
        self._music_selection: dict[str, Any] = {"role": "drums", "section_name": "main"}
        self._music_preview_player: Any = None
        self._music_preview_output: Any = None
        self._music_preview_loaded_path = ""
        self._composer_master_fx: dict[str, Any] = copy.deepcopy(default_effects_state())

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        banner = QLabel("COMPOSER", self)
        banner.setObjectName("ComposerBanner")
        banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        banner.setMinimumHeight(54)
        banner.setMaximumHeight(58)
        root.addWidget(banner)

        root.addWidget(self._build_composer_page(), 1)

    def _qss(self) -> str:
        return (
            f"QWidget#ComposerPanel {{ background:#101112; font-family:{FONT_FAMILY}; }}"
            "QLabel#ComposerBanner {"
            "background:rgba(126,215,154,7); color:#EAF2EE; border:1px solid rgba(126,215,154,42);"
            "border-radius:7px; padding:0px; font-size:28px; font-weight:760; letter-spacing:2px;"
            "}"
            "QFrame#ComposerCard { background:transparent; border:none; border-top:1px solid rgba(178,186,202,16); border-radius:0px; }"
            "QLabel#ComposerCardTitle { color:#DDE2EA; font-size:10px; font-weight:720; background:transparent; }"
            "QLabel#ComposerSubtitle { color:#929AA6; font-size:9px; background:transparent; }"
            "QLabel#ComposerFieldLabel { color:#A3ABB7; font-size:9px; font-weight:560; background:transparent; }"
            "QPushButton#ComposerButton {"
            "background:rgba(255,255,255,5); color:#C7CEDA; border:1px solid rgba(178,186,202,22);"
            "border-radius:5px; padding:5px 8px; font-size:9px; font-weight:680;"
            "}"
            "QPushButton#ComposerButton:hover {"
            "background:rgba(255,255,255,11); border-color:rgba(220,225,238,62); color:#FFFFFF;"
            "}"
            "QPushButton#ComposerPrimaryButton {"
            "background:rgba(126,215,154,16); color:#E8F4EC; border:1px solid rgba(126,215,154,82);"
            "border-radius:5px; padding:5px 10px; font-size:9px; font-weight:760;"
            "}"
            "QPushButton#ComposerPrimaryButton:hover { background:rgba(126,215,154,24); color:#FFFFFF; }"
            "QFrame#ComposerMasterFxPanel { background:rgba(255,255,255,3); border:1px solid rgba(178,186,202,16); border-radius:6px; }"
            "QWidget#SoundLabKnobStrip { background:transparent; border:none; }"
            "QLabel#SoundLabKnobStripTitle { color:#A3ABB7; font-size:9px; font-weight:720; background:transparent; }"
            "QLabel#SoundFieldLabel { color:#A3ABB7; font-size:9px; font-weight:560; background:transparent; }"
            "QLabel#SoundFieldValue { color:#D9E2E4; font-size:9px; font-weight:640; background:transparent; }"
            "QComboBox#ComposerCombo, QComboBox#ComposerAIProviderCombo {"
            "background:rgba(255,255,255,5); color:#D7DAE7; border:1px solid rgba(178,186,202,24);"
            "border-radius:5px; padding:3px 7px; font-size:9px; min-height:20px;"
            "}"
            "QLineEdit#ComposerLineEdit, QSpinBox#ComposerSpinBox {"
            "background:rgba(255,255,255,5); color:#D7DAE7; border:1px solid rgba(178,186,202,24);"
            "border-radius:5px; padding:4px 7px; font-size:9px; min-height:20px;"
            "}"
            "QComboBox#ComposerCombo:hover, QComboBox#ComposerAIProviderCombo:hover, "
            "QLineEdit#ComposerLineEdit:hover, QSpinBox#ComposerSpinBox:hover {"
            "background:rgba(255,255,255,10); border-color:rgba(220,225,238,62);"
            "}"
            + editor_scrollbar_qss("QWidget#ComposerPanel")
        )

    def _card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame(self)
        card.setObjectName("ComposerCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 7, 0, 7)
        layout.setSpacing(7)
        label = QLabel(title, card)
        label.setObjectName("ComposerCardTitle")
        layout.addWidget(label)
        return card, layout

    def _combo(self, values: list[str], handler) -> QComboBox:
        combo = QComboBox(self)
        combo.setObjectName("ComposerCombo")
        combo.addItems(values)
        combo.currentTextChanged.connect(handler)
        return combo

    @staticmethod
    def _set_combo_text(combo: QComboBox | None, value: Any) -> None:
        if combo is None:
            return
        text = str(value or "")
        combo.blockSignals(True)
        idx = combo.findText(text)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _build_composer_page(self) -> QWidget:
        page = QWidget(self)
        page.setObjectName("ComposerPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 0, 6, 7)
        layout.setSpacing(7)

        card, card_layout = self._card("Composer")
        self._music_prompt = QLineEdit(page)
        self._music_prompt.setObjectName("ComposerLineEdit")
        self._music_prompt.setPlaceholderText("Describe the score, cue, or background music")
        self._music_prompt.setText("30s cinematic tech demo BGM")
        self._music_prompt.setAccessibleName("Composer prompt")
        card_layout.addWidget(self._music_prompt)

        row = QWidget(page)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)
        self._music_genre = self._combo(
            ["cinematic electronic", "electronic", "lofi", "corporate electronic", "pop electronic"],
            lambda _text: self._refresh_music_arrangement(),
        )
        self._music_genre.setAccessibleName("Composer genre")
        self._music_mood = self._combo(
            ["confident", "epic", "chill", "clear", "bright", "tense"],
            lambda _text: self._refresh_music_arrangement(),
        )
        self._music_mood.setAccessibleName("Composer mood")
        self._music_duration = QSpinBox(page)
        self._music_duration.setObjectName("ComposerSpinBox")
        self._music_duration.setRange(4, 180)
        self._music_duration.setValue(30)
        self._music_duration.setSuffix(" s")
        self._music_duration.setAccessibleName("Composer duration")
        self._music_duration.valueChanged.connect(lambda _value: self._refresh_music_arrangement())
        self._music_bpm = QSpinBox(page)
        self._music_bpm.setObjectName("ComposerSpinBox")
        self._music_bpm.setRange(0, 180)
        self._music_bpm.setValue(0)
        self._music_bpm.setSpecialValueText("Auto BPM")
        self._music_bpm.setAccessibleName("Composer BPM")
        row_layout.addWidget(self._music_genre, 2)
        row_layout.addWidget(self._music_mood, 1)
        row_layout.addWidget(self._music_duration, 0)
        row_layout.addWidget(self._music_bpm, 0)
        card_layout.addWidget(row)

        roles_row = QWidget(page)
        roles_layout = QHBoxLayout(roles_row)
        roles_layout.setContentsMargins(0, 0, 0, 0)
        roles_layout.setSpacing(5)
        self._music_roles = self._combo(["stems", "mix only", "drums + bass", "pad only"], lambda _text: None)
        self._music_roles.currentTextChanged.connect(lambda _text: self._refresh_music_arrangement())
        self._music_roles.setAccessibleName("Composer render roles")
        self._music_key = self._combo(["auto key", "C minor", "D minor", "C major", "F major", "A minor"], lambda _text: None)
        self._music_key.currentTextChanged.connect(lambda _text: self._refresh_music_arrangement())
        self._music_key.setAccessibleName("Composer key")
        self._music_render_backend = self._combo(["sample prod", "AI production", "soundfont", "studio EDM", "auto renderer", "diagnostic synth"], lambda _text: None)
        self._music_render_backend.setAccessibleName("Composer render backend")
        roles_layout.addWidget(self._music_roles, 1)
        roles_layout.addWidget(self._music_key, 1)
        roles_layout.addWidget(self._music_render_backend, 0)
        card_layout.addWidget(roles_row)

        sample_row = QWidget(page)
        sample_layout = QHBoxLayout(sample_row)
        sample_layout.setContentsMargins(0, 0, 0, 0)
        sample_layout.setSpacing(5)
        self._music_sample_library = self._combo(
            ["auto samples", "sample kit first", "soundfont only", "diagnostic synth"],
            lambda _text: self._refresh_music_sample_library_status(),
        )
        self._music_sample_library.setAccessibleName("Composer sample library policy")
        self._music_sample_library.setToolTip("Choose how user-installed sample libraries are used by composition rendering.")
        self._music_sample_status = QLabel("", sample_row)
        self._music_sample_status.setObjectName("ComposerSubtitle")
        self._music_sample_status.setWordWrap(True)
        open_assets = QPushButton("Assets", sample_row)
        open_assets.setObjectName("ComposerButton")
        open_assets.setAccessibleName("Open Composer sample asset folder")
        open_assets.setToolTip("Open external/assets/music for user-installed SoundFonts, SFZ libraries, and drum kits.")
        open_assets.clicked.connect(self._open_music_sample_assets_folder)
        guide = QPushButton("Guide", sample_row)
        guide.setObjectName("ComposerButton")
        guide.setAccessibleName("Open Composer sample install guide")
        guide.setToolTip("Open the local install guide for optional sample libraries.")
        guide.clicked.connect(self._open_music_sample_install_guide)
        sample_layout.addWidget(self._music_sample_library, 0)
        sample_layout.addWidget(self._music_sample_status, 1)
        sample_layout.addWidget(open_assets, 0)
        sample_layout.addWidget(guide, 0)
        card_layout.addWidget(sample_row)
        self._refresh_music_sample_library_status()

        provider_row = QWidget(page)
        provider_layout = QHBoxLayout(provider_row)
        provider_layout.setContentsMargins(0, 0, 0, 0)
        provider_layout.setSpacing(5)
        self._music_ai_provider = self._combo(
            ["AI auto", "Stable Audio 3.0", "ACE-Step", "LMMS offline"],
            self._on_music_ai_provider_changed,
        )
        self._music_ai_provider.setObjectName("ComposerAIProviderCombo")
        self._music_ai_provider.setAccessibleName("Composer AI provider")
        self._music_ai_provider.setToolTip("Choose the production AI renderer used by Composer.")
        self._music_provider_status = QLabel("", provider_row)
        self._music_provider_status.setObjectName("ComposerSubtitle")
        self._music_provider_status.setWordWrap(True)
        provider_layout.addWidget(self._music_ai_provider, 0)
        provider_layout.addWidget(self._music_provider_status, 1)
        card_layout.addWidget(provider_row)
        self._refresh_music_provider_status()

        self._music_arrangement = _MusicLabArrangementView(page)
        self._music_arrangement.setObjectName("ComposerArrangementView")
        self._music_arrangement._arrangement_title = "Composer Arrange"
        self._music_arrangement.selection_changed.connect(self._on_music_arrangement_selected)
        card_layout.addWidget(self._music_arrangement, 1)

        edit_row = QWidget(page)
        edit_layout = QHBoxLayout(edit_row)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(5)
        self._music_selection_label = QLabel("Selected: Drums / main", edit_row)
        self._music_selection_label.setObjectName("ComposerSubtitle")
        self._music_regen_btn = QPushButton("Regenerate Selection", edit_row)
        self._music_regen_btn.setObjectName("ComposerButton")
        self._music_regen_btn.clicked.connect(self._request_music_regenerate_selection)
        self._music_shorter_btn = QPushButton("- Section", edit_row)
        self._music_shorter_btn.setObjectName("ComposerButton")
        self._music_shorter_btn.clicked.connect(lambda: self._request_music_section_resize(0.82))
        self._music_longer_btn = QPushButton("+ Section", edit_row)
        self._music_longer_btn.setObjectName("ComposerButton")
        self._music_longer_btn.clicked.connect(lambda: self._request_music_section_resize(1.18))
        edit_layout.addWidget(self._music_selection_label, 1)
        edit_layout.addWidget(self._music_regen_btn, 0)
        edit_layout.addWidget(self._music_shorter_btn, 0)
        edit_layout.addWidget(self._music_longer_btn, 0)
        card_layout.addWidget(edit_row)

        self._music_note_hint = QLabel("Arrangement preview follows rendered audio clips.", page)
        self._music_note_hint.setObjectName("ComposerSubtitle")
        self._music_note_hint.setWordWrap(True)
        card_layout.addWidget(self._music_note_hint)

        card_layout.addWidget(self._build_master_fx_panel(page))

        actions = QWidget(page)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(5)
        generate = QPushButton("Compose to Timeline", actions)
        generate.setObjectName("ComposerPrimaryButton")
        generate.setAccessibleName("Compose music to timeline")
        generate.setToolTip("Generate or update Composer stems on the timeline")
        generate.clicked.connect(self._request_music_generate)
        update = QPushButton("Re-render", actions)
        update.setObjectName("ComposerButton")
        update.setAccessibleName("Re-render Composer timeline music")
        update.clicked.connect(self._request_music_update)
        preview = QPushButton("Preview", actions)
        preview.setObjectName("ComposerButton")
        preview.setAccessibleName("Play Composer preview mix")
        preview.clicked.connect(self._request_music_preview)
        stop = QPushButton("Stop", actions)
        stop.setObjectName("ComposerButton")
        stop.setAccessibleName("Stop Composer preview")
        stop.clicked.connect(self._stop_music_preview)
        export = QPushButton("MIDI", actions)
        export.setObjectName("ComposerButton")
        export.setAccessibleName("Export Composer MIDI")
        export.clicked.connect(self._request_music_export_midi)
        self._music_generate_btn = generate
        self._music_preview_btn = preview
        self._music_stop_btn = stop
        self._music_update_btn = update
        self._music_export_btn = export
        for button in (generate, update, preview, stop, export):
            button.setMinimumHeight(26)
            actions_layout.addWidget(button, 1)
        card_layout.addWidget(actions)

        self._music_status = QLabel("Composer ready. Create editable timeline music from prompt, key, BPM, and sections.", page)
        self._music_status.setObjectName("ComposerSubtitle")
        self._music_status.setWordWrap(True)
        card_layout.addWidget(self._music_status)
        layout.addWidget(card)
        self._refresh_music_arrangement()
        return page

    def _build_master_fx_panel(self, parent: QWidget) -> QWidget:
        panel = QFrame(parent)
        panel.setObjectName("ComposerMasterFxPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(5)

        header = QWidget(panel)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(5)
        title = QLabel("Master FX", header)
        title.setObjectName("ComposerCardTitle")
        hint = QLabel("Sound Editor chain for rendered mix/stems", header)
        hint.setObjectName("ComposerSubtitle")
        hint.setWordWrap(True)
        self._master_fx_enabled = QPushButton("Off", header)
        self._master_fx_enabled.setObjectName("ComposerButton")
        self._master_fx_enabled.setCheckable(True)
        self._master_fx_enabled.setAccessibleName("Enable Composer Master FX")
        self._master_fx_enabled.toggled.connect(self._on_master_fx_enabled)
        header_layout.addWidget(title, 0)
        header_layout.addWidget(hint, 1)
        header_layout.addWidget(self._master_fx_enabled, 0)
        layout.addWidget(header)

        self._master_fx_knobs = _SoundLabKnobStrip("Composer master knobs", panel)
        self._master_fx_knobs.add_knob("air", "Air", minimum=0, maximum=8, default=0, color="green", formatter=lambda v: f"{v:.1f} dB")
        self._master_fx_knobs.add_knob("clarity", "Clarity", minimum=0, maximum=100, default=0, unit="%", color="blue", formatter=lambda v: f"{v:.0f}%")
        self._master_fx_knobs.add_knob("width", "Width", minimum=60, maximum=180, default=100, unit="%", color="#A98FD7", formatter=lambda v: f"{v:.0f}%")
        self._master_fx_knobs.add_knob("punch", "Punch", minimum=0, maximum=100, default=0, unit="%", color="orange", formatter=lambda v: f"{v:.0f}%")
        self._master_fx_knobs.add_knob("space", "Space", minimum=0, maximum=55, default=0, unit="%", color="green", formatter=lambda v: f"{v:.0f}%")
        self._master_fx_knobs.knob_changed.connect(self._on_master_fx_knob_changed)
        layout.addWidget(self._master_fx_knobs, 0)

        actions = QWidget(panel)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(5)
        preset_soft = QPushButton("Soft Master", actions)
        preset_soft.setObjectName("ComposerButton")
        preset_soft.clicked.connect(lambda: self._apply_master_fx_preset("soft"))
        preset_large = QPushButton("Wide Hall", actions)
        preset_large.setObjectName("ComposerButton")
        preset_large.clicked.connect(lambda: self._apply_master_fx_preset("wide"))
        apply = QPushButton("Apply to Music", actions)
        apply.setObjectName("ComposerPrimaryButton")
        apply.setAccessibleName("Apply Composer Master FX to Composer music")
        apply.clicked.connect(self._request_apply_master_fx)
        self._master_fx_apply_btn = apply
        actions_layout.addWidget(preset_soft, 0)
        actions_layout.addWidget(preset_large, 0)
        actions_layout.addStretch(1)
        actions_layout.addWidget(apply, 0)
        layout.addWidget(actions)
        return panel

    def _on_master_fx_enabled(self, enabled: bool) -> None:
        self._master_fx_enabled.setText("On" if enabled else "Off")
        ai = self._composer_master_fx.setdefault(
            "ai_master",
            copy.deepcopy(default_effects_state().get("ai_master", {})),
        )
        reverb = self._composer_master_fx.setdefault(
            "reverb",
            copy.deepcopy(default_effects_state().get("reverb", {})),
        )
        ai["enabled"] = bool(enabled)
        reverb["enabled"] = bool(enabled and float(reverb.get("mix") or 0.0) > 0.0)

    def _set_master_fx_value(self, fx_key: str, sub_key: str, value: Any) -> None:
        defaults = default_effects_state()
        state = self._composer_master_fx.setdefault(fx_key, copy.deepcopy(defaults.get(fx_key, {})))
        state[sub_key] = value
        if fx_key == "ai_master" and sub_key != "preset":
            state["preset"] = "Composer"
        if self._master_fx_enabled.isChecked():
            if fx_key == "reverb":
                state["enabled"] = float(state.get("mix") or 0.0) > 0.0
            else:
                state["enabled"] = True

    def _on_master_fx_knob_changed(self, key: str, value: float) -> None:
        if key == "air":
            self._set_master_fx_value("ai_master", "air", round(float(value), 1))
        elif key == "clarity":
            self._set_master_fx_value("ai_master", "clarity", round(float(value)))
        elif key == "width":
            self._set_master_fx_value("ai_master", "width", round(float(value)))
        elif key == "punch":
            self._set_master_fx_value("ai_master", "punch", round(float(value)))
        elif key == "space":
            self._set_master_fx_value("reverb", "mix", round(float(value)))

    def _apply_master_fx_preset(self, preset: str) -> None:
        if preset == "wide":
            values = {"air": 2.8, "clarity": 42, "width": 138, "punch": 24, "space": 28}
        else:
            values = {"air": 1.8, "clarity": 34, "width": 116, "punch": 18, "space": 14}
        self._master_fx_enabled.setChecked(True)
        self._master_fx_knobs.set_values({key: float(value) for key, value in values.items()})
        for key, value in (
            ("air", values["air"]),
            ("clarity", values["clarity"]),
            ("width", values["width"]),
            ("punch", values["punch"]),
        ):
            self._set_master_fx_value("ai_master", key, value)
        self._set_master_fx_value("reverb", "type", "Hall" if preset == "wide" else "Room")
        self._set_master_fx_value("reverb", "size", 44 if preset == "wide" else 28)
        self._set_master_fx_value("reverb", "decay_s", 2.2 if preset == "wide" else 1.3)
        self._set_master_fx_value("reverb", "damping", 54 if preset == "wide" else 62)
        self._set_master_fx_value("reverb", "mix", values["space"])
        self._music_status.setText(f"Composer Master FX preset ready: {'Wide Hall' if preset == 'wide' else 'Soft Master'}")

    def _master_fx_payload(self) -> dict[str, Any]:
        enabled = bool(self._master_fx_enabled.isChecked())
        payload: dict[str, Any] = {}
        ai = copy.deepcopy(self._composer_master_fx.get("ai_master") or default_effects_state().get("ai_master", {}))
        reverb = copy.deepcopy(self._composer_master_fx.get("reverb") or default_effects_state().get("reverb", {}))
        ai["enabled"] = bool(enabled and (
            abs(float(ai.get("air") or 0.0)) > 0.001
            or float(ai.get("clarity") or 0.0) > 0.001
            or abs(float(ai.get("width") or 100.0) - 100.0) > 0.001
            or float(ai.get("punch") or 0.0) > 0.001
            or float(ai.get("warmth") or 0.0) > 0.001
            or float(ai.get("excite") or 0.0) > 0.001
        ))
        ai["preset"] = str(ai.get("preset") or "Composer")
        reverb["enabled"] = bool(enabled and float(reverb.get("mix") or 0.0) > 0.0)
        loudness = copy.deepcopy(default_effects_state().get("loudness", {}))
        loudness.update({"enabled": bool(enabled), "target_i": -14.0, "true_peak": -1.0, "lra": 11.0, "target_id": "music"})
        payload["ai_master"] = ai
        payload["reverb"] = reverb
        payload["loudness"] = loudness
        return payload

    def _request_apply_master_fx(self) -> None:
        composition_id = str(self._music_selection_payload().get("composition_id") or "")
        _roles, create_mix = self._music_roles_param()
        role = "mix" if create_mix else "all"
        params: dict[str, Any] = {
            "role": role,
            "effects": self._master_fx_payload(),
            "merge": True,
            "focus_workbench": False,
        }
        if composition_id:
            params["composition_id"] = composition_id
        self._music_status.setText("Applying Sound Editor Master FX to Composer audio...")
        self.music_lab_action_requested.emit("music.apply_master_fx", params)

    def set_music_composition(self, composition: dict[str, Any] | None) -> None:
        self._music_composition = dict(composition or {}) if isinstance(composition, dict) else None
        self._music_arrangement.set_composition(self._music_composition)
        self._music_arrangement.set_playback_position_ms(None)
        self._music_selection = self._music_arrangement.selection()
        self._sync_music_controls_from_composition()
        self._refresh_music_arrangement()
        self._update_music_selection_ui()
        self._refresh_music_preview_controls()

    def refresh_music_lab_status(self, text: str) -> None:
        self._music_status.setText(str(text or ""))

    def _sync_music_controls_from_composition(self) -> None:
        composition = self._music_composition or {}
        if not composition:
            return
        self._music_prompt.setText(str(composition.get("prompt") or self._music_prompt.text()))
        self._set_combo_text(self._music_genre, composition.get("genre") or self._music_genre.currentText())
        self._set_combo_text(self._music_mood, composition.get("mood") or self._music_mood.currentText())
        self._set_combo_text(self._music_key, composition.get("key") or self._music_key.currentText())
        try:
            self._music_duration.blockSignals(True)
            self._music_duration.setValue(max(4, min(180, int(round(float(composition.get("duration_ms") or 30000) / 1000.0)))))
        finally:
            self._music_duration.blockSignals(False)
        try:
            self._music_bpm.setValue(max(0, min(180, int(composition.get("bpm") or 0))))
        except Exception:
            pass
        render_backend = composition.get("render_backend")
        backend = str(render_backend.get("backend") or "") if isinstance(render_backend, dict) else ""
        if isinstance(render_backend, dict):
            policy = str(render_backend.get("sample_library_policy") or "").strip().lower()
            if policy == "sample_kit_first":
                self._set_combo_text(self._music_sample_library, "sample kit first")
            elif policy == "soundfont_only":
                self._set_combo_text(self._music_sample_library, "soundfont only")
            elif policy == "procedural_only":
                self._set_combo_text(self._music_sample_library, "diagnostic synth")
            elif policy:
                self._set_combo_text(self._music_sample_library, "auto samples")
            self._refresh_music_sample_library_status()
        if backend == "fluidsynth_soundfont":
            self._set_combo_text(self._music_render_backend, "soundfont")
        elif backend == "sample_production":
            self._set_combo_text(self._music_render_backend, "sample prod")
        elif backend == "studio_edm":
            self._set_combo_text(self._music_render_backend, "studio EDM")
        elif backend == "local_synth":
            self._set_combo_text(self._music_render_backend, "diagnostic synth")
        elif backend == "production_external":
            self._set_combo_text(self._music_render_backend, "AI production")
            provider = str(render_backend.get("provider") or render_backend.get("requested_ai_provider") or "") if isinstance(render_backend, dict) else ""
            if provider == "stable_audio_3":
                self._set_combo_text(self._music_ai_provider, "Stable Audio 3.0")
            elif provider in {"acestep_api", "acestep"}:
                self._set_combo_text(self._music_ai_provider, "ACE-Step")
            elif provider == "lmms":
                self._set_combo_text(self._music_ai_provider, "LMMS offline")
            self._refresh_music_provider_status()

    def _on_music_arrangement_selected(self, selection) -> None:
        self._music_selection = dict(selection or {})
        self._update_music_selection_ui()
        self.music_lab_selection_changed.emit(self._music_selection_payload())

    def _music_selection_payload(self) -> dict[str, Any]:
        payload = dict(self._music_selection or {})
        composition = self._music_composition or {}
        if composition:
            payload["composition_id"] = str(composition.get("id") or payload.get("composition_id") or "")
        section = self._selected_section_row()
        payload["section_start_ms"] = int(section.get("start_ms") or 0) if section else 0
        payload["section_duration_ms"] = self._selected_section_duration_ms()
        payload["chord_progression"] = self._selected_chord_progression()
        payload["note_count"] = self._selected_note_count()
        payload["note_preview"] = self._selected_note_preview()
        return payload

    def _update_music_selection_ui(self) -> None:
        selection = self._music_selection_payload()
        role_text = str(selection.get("role") or "track")
        role = "Pad" if role_text.lower() == "chords" else role_text.title()
        section = str(selection.get("section_name") or "section")
        duration = int(selection.get("section_duration_ms") or 0)
        notes = int(selection.get("note_count") or 0)
        chords = [str(chord) for chord in list(selection.get("chord_progression") or []) if str(chord).strip()]
        note_preview = [str(note) for note in list(selection.get("note_preview") or []) if str(note).strip()]
        self._music_selection_label.setText(f"Selected: {role} / {section}  |  {duration / 1000.0:.1f}s")
        chord_text = " - ".join(chords[:4]) if chords else "auto chords"
        preview_text = ", ".join(note_preview[:6]) if note_preview else "no MIDI notes yet"
        self._music_note_hint.setText(
            f"Chords: {chord_text}  |  Notes: {notes} ({preview_text}). "
            "Regenerate or resize the selection, then Re-render refreshes timeline stems."
        )

    def _selected_section_row(self) -> dict[str, Any]:
        section_name = str((self._music_selection or {}).get("section_name") or "").lower()
        for row in list((self._music_composition or {}).get("sections") or []):
            if isinstance(row, dict) and str(row.get("name") or "").lower() == section_name:
                return row
        return {}

    def _selected_section_duration_ms(self) -> int:
        row = self._selected_section_row()
        if row:
            try:
                return max(1, int(row.get("duration_ms") or 0))
            except Exception:
                return 0
        return 0

    def _selected_chord_progression(self) -> list[str]:
        row = self._selected_section_row()
        return [str(chord) for chord in list(row.get("chord_progression") or []) if str(chord).strip()]

    def _selected_note_count(self) -> int:
        selection = self._music_selection or {}
        role = str(selection.get("role") or "").lower()
        if role == "pad":
            role = "chords"
        section_name = str(selection.get("section_name") or "").lower()
        total = 0
        for track in list((self._music_composition or {}).get("tracks") or []):
            if not isinstance(track, dict):
                continue
            track_role = str(track.get("role") or track.get("id") or "").lower()
            if role and track_role != role:
                continue
            for clip in list(track.get("clips") or []):
                if isinstance(clip, dict) and str(clip.get("section_name") or "").lower() == section_name:
                    total += len(list(clip.get("notes") or []))
        return total

    def _selected_note_preview(self) -> list[str]:
        selection = self._music_selection or {}
        role = str(selection.get("role") or "").lower()
        if role == "pad":
            role = "chords"
        section_name = str(selection.get("section_name") or "").lower()
        preview: list[str] = []
        for track in list((self._music_composition or {}).get("tracks") or []):
            if not isinstance(track, dict):
                continue
            track_role = str(track.get("role") or track.get("id") or "").lower()
            if role and track_role != role:
                continue
            for clip in list(track.get("clips") or []):
                if not isinstance(clip, dict) or str(clip.get("section_name") or "").lower() != section_name:
                    continue
                for note in list(clip.get("notes") or [])[:8]:
                    if isinstance(note, dict):
                        preview.append(str(note.get("pitch") or "?"))
                if preview:
                    return preview
        return preview

    def _refresh_music_arrangement(self) -> None:
        try:
            self._music_arrangement.set_arrangement(
                duration_s=int(self._music_duration.value()),
                mode=self._music_roles.currentText(),
                key=self._music_key.currentText(),
                genre=self._music_genre.currentText(),
                mood=self._music_mood.currentText(),
            )
            if self._music_composition:
                self._music_arrangement.set_composition(self._music_composition)
        except Exception:
            pass

    def _music_roles_param(self) -> tuple[list[str] | None, bool]:
        if self._music_ai_provider_key():
            return None, True
        value = str(self._music_roles.currentText()).strip().lower()
        if value == "mix only":
            return None, True
        if value == "drums + bass":
            return ["drums", "bass"], False
        if value == "pad only":
            return ["chords"], False
        return None, False

    def _music_compose_params(self) -> dict[str, Any]:
        roles, create_mix = self._music_roles_param()
        params: dict[str, Any] = {
            "prompt": self._music_prompt.text().strip() or "AI background music",
            "duration_ms": int(self._music_duration.value()) * 1000,
            "genre": self._music_genre.currentText(),
            "mood": self._music_mood.currentText(),
            "include_fx": True,
            "at_ms": 0,
            "auto_balance": True,
            "update_existing": True,
            "create_mix": create_mix,
        }
        params.update(self._music_backend_params())
        if roles:
            params["roles"] = roles
        bpm = int(self._music_bpm.value())
        if bpm > 0:
            params["bpm"] = bpm
        key = self._music_key.currentText()
        if key and key != "auto key":
            params["key"] = key
        return params

    def _music_backend_params(self) -> dict[str, Any]:
        value = str(self._music_render_backend.currentText()).strip().lower()
        provider = self._music_ai_provider_key()
        sample_policy = self._music_sample_library_policy()
        if provider:
            return {"backend": "production", "ai_provider": provider, "sample_library_policy": sample_policy}
        if value == "soundfont":
            return {"backend": "soundfont", "sample_library_policy": sample_policy}
        if value == "sample prod":
            return {"backend": "sample_production", "sample_library_policy": sample_policy}
        if value in {"production", "ai production"}:
            return {"backend": "production", "sample_library_policy": sample_policy}
        if value == "studio edm":
            return {"backend": "studio_edm", "sample_library_policy": sample_policy}
        if value in {"local v5", "diagnostic synth"}:
            return {"backend": "local_synth", "sample_library_policy": sample_policy}
        return {"backend": "auto", "sample_library_policy": sample_policy}

    def _music_sample_library_policy(self) -> str:
        text = str(self._music_sample_library.currentText()).strip().lower()
        if text == "sample kit first":
            return "sample_kit_first"
        if text == "soundfont only":
            return "soundfont_only"
        if text in {"internal synth", "diagnostic synth"}:
            return "procedural_only"
        return "auto"

    def _refresh_music_sample_library_status(self) -> None:
        try:
            from app.music_composer import music_render_backend_status

            status = music_render_backend_status()
            drum_count = len(list(status.get("drum_sample_kits") or []))
            soundfont_count = len(list(status.get("soundfonts") or []))
            self._music_sample_status.setText(f"Installed: {drum_count} drum kits | {soundfont_count} SoundFonts")
            dirs = status.get("sample_library_install_dirs") if isinstance(status.get("sample_library_install_dirs"), dict) else {}
            recommended = status.get("recommended_sample_libraries") or []
            rec_names = ", ".join(str(row.get("name") or "") for row in list(recommended)[:4] if isinstance(row, dict))
            tooltip_lines = [
                "Optional sample packs are user-installed external assets and are not bundled with TigerCapture.",
                f"Music asset root: {dirs.get('root', '')}",
            ]
            if rec_names:
                tooltip_lines.append(f"Examples: {rec_names}")
            self._music_sample_status.setToolTip("\n".join(tooltip_lines))
        except Exception as exc:
            self._music_sample_status.setText("Installed: unavailable")
            self._music_sample_status.setToolTip(str(exc))

    def _music_assets_root(self) -> Path:
        try:
            from app.music_composer import music_assets_root

            return music_assets_root()
        except Exception:
            return Path(__file__).resolve().parents[1] / "external" / "assets" / "music"

    def _open_music_sample_assets_folder(self) -> None:
        root = self._music_assets_root()
        for child in ("soundfonts", "sfz", "drum_kits"):
            try:
                (root / child).mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
        try:
            root.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(root)))
        except Exception as exc:
            self._music_status.setText(f"Could not open sample assets folder: {exc}")

    def _open_music_sample_install_guide(self) -> None:
        guide = self._music_assets_root() / "README.md"
        target = guide if guide.exists() else self._music_assets_root()
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        except Exception as exc:
            self._music_status.setText(f"Could not open sample install guide: {exc}")

    def _music_ai_provider_key(self) -> str:
        text = str(self._music_ai_provider.currentText()).strip().lower()
        if text == "stable audio 3.0":
            return "stable_audio_3"
        if text == "ace-step":
            return "acestep_api"
        if text == "lmms offline":
            return "lmms"
        return ""

    def _on_music_ai_provider_changed(self, _text: str) -> None:
        if self._music_ai_provider_key():
            self._set_combo_text(self._music_render_backend, "AI production")
            self._set_combo_text(self._music_roles, "mix only")
        self._refresh_music_provider_status()

    def _refresh_music_provider_status(self) -> None:
        provider = self._music_ai_provider_key()
        if provider == "stable_audio_3":
            self._music_provider_status.setText("Stable Audio 3.0 | external Space | mix WAV")
            self._music_provider_status.setToolTip("Prompts are sent to the configured Stable Audio 3.0 Hugging Face Space.")
        elif provider == "acestep_api":
            self._music_provider_status.setText("ACE-Step | local/API server | mix WAV")
            self._music_provider_status.setToolTip("Requires a healthy ACE-Step API server, default http://127.0.0.1:8001.")
        elif provider == "lmms":
            self._music_provider_status.setText("LMMS | offline fallback | mix WAV")
            self._music_provider_status.setToolTip("Uses the local LMMS production bridge without an AI cloud provider.")
        else:
            self._music_provider_status.setText("Provider follows config")
            self._music_provider_status.setToolTip("Production uses provider.json order and falls back locally when unavailable.")

    def _request_music_generate(self) -> None:
        self._music_status.setText("Composing timeline music...")
        self.music_lab_action_requested.emit("music.compose_to_timeline", self._music_compose_params())

    def _request_music_update(self) -> None:
        roles, create_mix = self._music_roles_param()
        params: dict[str, Any] = {
            "at_ms": 0,
            "create_mix": create_mix,
            "update_existing": True,
        }
        params.update(self._music_backend_params())
        composition_id = str(self._music_selection_payload().get("composition_id") or "")
        if composition_id:
            params["composition_id"] = composition_id
        if roles:
            params["roles"] = roles
        self._music_status.setText("Re-rendering Composer timeline tracks...")
        self.music_lab_action_requested.emit("music.render_to_timeline", params)

    def _request_music_export_midi(self) -> None:
        self._music_status.setText("Exporting Composer MIDI...")
        composition_id = str(self._music_selection_payload().get("composition_id") or "")
        params = {"composition_id": composition_id} if composition_id else {}
        self.music_lab_action_requested.emit("music.export_midi", params)

    def _music_preview_mix_path(self) -> Path | None:
        path_text = str((self._music_composition or {}).get("preview_mix_path") or "").strip()
        if not path_text:
            return None
        path = Path(path_text)
        return path if path.exists() else None

    def _refresh_music_preview_controls(self) -> None:
        path = self._music_preview_mix_path()
        enabled = path is not None
        self._music_preview_btn.setProperty("has_preview", enabled)
        self._music_preview_btn.setToolTip(
            f"Play preview mix: {path.name}" if enabled else "Render or compose music before preview playback"
        )
        self._music_stop_btn.setEnabled(True)
        if enabled:
            engine = str((self._music_composition or {}).get("render_engine") or "rendered preview")
            render_backend = (self._music_composition or {}).get("render_backend")
            quality = ""
            warning = ""
            if isinstance(render_backend, dict):
                quality = str(render_backend.get("quality_tier") or "")
                warning = str(render_backend.get("quality_warning") or "")
            suffix = f" | Quality: {quality}" if quality else ""
            if warning:
                suffix += f" | {warning}"
            self._music_status.setText(f"Preview ready: {path.name} | Renderer: {engine}{suffix}")

    def _ensure_music_preview_player(self) -> bool:
        if self._music_preview_player is not None:
            return True
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        except Exception as exc:
            self._music_status.setText(f"Composer preview playback is unavailable: {exc}")
            return False
        self._music_preview_output = QAudioOutput(self)
        self._music_preview_output.setVolume(0.85)
        self._music_preview_player = QMediaPlayer(self)
        self._music_preview_player.setAudioOutput(self._music_preview_output)
        self._music_preview_player.playbackStateChanged.connect(self._on_music_preview_state_changed)
        self._music_preview_player.positionChanged.connect(self._on_music_preview_position_changed)
        return True

    def _request_music_preview(self) -> None:
        path = self._music_preview_mix_path()
        if path is None:
            composition_id = str(self._music_selection_payload().get("composition_id") or "")
            if composition_id:
                self._music_status.setText("Rendering Composer preview mix...")
                params = {"composition_id": composition_id, "render_stems": False}
                params.update(self._music_backend_params())
                self.music_lab_action_requested.emit("music.render.preview", params)
            else:
                self._music_status.setText("Compose music first, then preview it here.")
            return
        if not self._ensure_music_preview_player() or self._music_preview_player is None:
            return
        resolved = str(path.resolve())
        if self._music_preview_loaded_path != resolved:
            self._music_preview_player.setSource(QUrl.fromLocalFile(resolved))
            self._music_preview_loaded_path = resolved
        try:
            from PySide6.QtMultimedia import QMediaPlayer
            if self._music_preview_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._music_preview_player.pause()
                self._music_status.setText(f"Paused Composer preview: {path.name}")
                return
        except Exception:
            pass
        self._music_preview_player.play()
        self._music_status.setText(f"Playing Composer preview: {path.name}")

    def _stop_music_preview(self) -> None:
        player = self._music_preview_player
        if player is not None:
            try:
                player.stop()
            except Exception:
                pass
        self._music_arrangement.set_playback_position_ms(None)
        self._music_status.setText("Composer preview stopped.")

    def _on_music_preview_state_changed(self, state) -> None:
        try:
            from PySide6.QtMultimedia import QMediaPlayer
            playing = state == QMediaPlayer.PlaybackState.PlayingState
        except Exception:
            playing = False
        self._music_preview_btn.setText("Pause" if playing else "Preview")

    def _on_music_preview_position_changed(self, position_ms: int) -> None:
        self._music_arrangement.set_playback_position_ms(int(position_ms or 0), follow=True)

    def _request_music_regenerate_selection(self) -> None:
        payload = self._music_selection_payload()
        composition_id = str(payload.get("composition_id") or "")
        section_name = str(payload.get("section_name") or "main")
        if not composition_id:
            self._music_status.setText("Compose music first, then regenerate a selected block.")
            return
        self._music_status.setText(f"Regenerating {section_name}...")
        params = {"composition_id": composition_id, "section_name": section_name, "intensity": 0.95}
        params.update(self._music_backend_params())
        self.music_lab_action_requested.emit("music.regenerate_section", params)

    def _request_music_section_resize(self, ratio: float) -> None:
        payload = self._music_selection_payload()
        composition_id = str(payload.get("composition_id") or "")
        section_name = str(payload.get("section_name") or "main")
        current = int(payload.get("section_duration_ms") or 0)
        if not composition_id or current <= 0:
            self._music_status.setText("Compose music first, then resize a selected section.")
            return
        duration = max(1000, int(round(current * float(ratio or 1.0))))
        self._music_status.setText(f"Resizing {section_name} to {duration / 1000.0:.1f}s...")
        params = {"composition_id": composition_id, "section_name": section_name, "duration_ms": duration}
        params.update(self._music_backend_params())
        self.music_lab_action_requested.emit("music.section.set", params)


class ComposerWindow(QWidget):
    """Top-level Composer shell launched from the Workbench Audio tab."""

    music_lab_action_requested = Signal(str, object)
    music_lab_selection_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setObjectName("ComposerWindow")
        self.setWindowTitle("Composer")
        self.setMinimumSize(860, 640)
        self.resize(1040, 760)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(0)
        self._composer_panel = ComposerPanel(self)
        self._composer_panel.music_lab_action_requested.connect(
            self.music_lab_action_requested.emit,
        )
        self._composer_panel.music_lab_selection_changed.connect(
            self.music_lab_selection_changed.emit,
        )
        root.addWidget(self._composer_panel, 1)

    def composer_panel(self) -> ComposerPanel:
        return self._composer_panel

    def set_music_composition(self, composition: dict | None) -> None:
        self._composer_panel.set_music_composition(composition)

    def refresh_music_lab_status(self, text: str) -> None:
        self._composer_panel.refresh_music_lab_status(str(text or ""))

    def closeEvent(self, event) -> None:  # pragma: no cover - window manager path
        event.ignore()
        self.hide()
