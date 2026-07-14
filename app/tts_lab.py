"""Standalone Voice Lab UI widgets."""
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

from PySide6.QtCore import QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QBrush, QDesktopServices, QFont, QPalette, QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListView,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.style import FONT_FAMILY, editor_scrollbar_qss


_VOICE_LAB_COMBO_POPUP_QSS = """
QWidget {
    background:#111316;
    color:#E9ECF7;
}
QFrame {
    background:#111316;
    color:#E9ECF7;
    border:1px solid rgba(178,186,202,52);
}
QAbstractItemView {
    background:#111316;
    color:#E9ECF7;
    border:1px solid rgba(178,186,202,52);
    border-radius:8px;
    padding:4px;
    outline:0px;
    selection-background-color:#5268FF;
    selection-color:#FFFFFF;
    font-size:12px;
    font-weight:650;
}
QAbstractItemView::item {
    min-height:28px;
    padding:5px 8px;
    border-radius:6px;
}
QAbstractItemView::item:hover {
    background:rgba(255,255,255,12);
}
QAbstractItemView::item:selected {
    background:#5268FF;
    color:#FFFFFF;
}
"""


class VoiceLabComboBox(QComboBox):
    """Combo box that restyles Qt's separate popup container on Windows."""

    def showPopup(self) -> None:  # pragma: no cover - exercised by real popup windows
        self._style_popup_container()
        super().showPopup()
        QTimer.singleShot(0, self._style_popup_container)

    def _style_popup_container(self) -> None:
        try:
            view = self.view()
            container = view.window()
            for widget in (container, view, view.viewport()):
                if widget is None:
                    continue
                widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                widget.setAutoFillBackground(True)
                widget.setStyleSheet(_VOICE_LAB_COMBO_POPUP_QSS)
                palette = widget.palette()
                palette.setColor(QPalette.ColorRole.Base, QColor("#111316"))
                palette.setColor(QPalette.ColorRole.Window, QColor("#111316"))
                palette.setColor(QPalette.ColorRole.Text, QColor("#E9ECF7"))
                palette.setColor(QPalette.ColorRole.WindowText, QColor("#E9ECF7"))
                palette.setColor(QPalette.ColorRole.Highlight, QColor("#5268FF"))
                palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
                widget.setPalette(palette)
        except Exception:
            pass


class TtsProviderInstallThread(QThread):
    finished_payload = Signal(dict)

    def __init__(self, command: list[str], *, cwd: str = "", provider_id: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._command = [str(part) for part in command if str(part)]
        self._cwd = str(cwd or "")
        self._provider_id = str(provider_id or "")

    def run(self) -> None:  # pragma: no cover - exercised through UI/manual install
        if not self._command:
            self.finished_payload.emit(
                {
                    "ok": False,
                    "provider_id": self._provider_id,
                    "error": "Install command is empty.",
                    "stdout": "",
                    "stderr": "",
                    "returncode": -1,
                }
            )
            return
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            completed = subprocess.run(
                self._command,
                cwd=self._cwd or None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=flags,
                check=False,
            )
            self.finished_payload.emit(
                {
                    "ok": int(completed.returncode or 0) == 0,
                    "provider_id": self._provider_id,
                    "returncode": int(completed.returncode or 0),
                    "stdout": str(completed.stdout or "")[-3000:],
                    "stderr": str(completed.stderr or "")[-3000:],
                    "error": "" if int(completed.returncode or 0) == 0 else f"Installer exited with code {completed.returncode}.",
                }
            )
        except Exception as exc:
            self.finished_payload.emit(
                {
                    "ok": False,
                    "provider_id": self._provider_id,
                    "error": str(exc),
                    "stdout": "",
                    "stderr": "",
                    "returncode": -1,
                }
            )


class TtsLabPage(QWidget):
    """Setup-first page for the local Style-Bert-VITS2 provider."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("VoiceLabPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(420)
        self.setStyleSheet(self._qss())
        self._sidecar_process: subprocess.Popen | None = None
        self._provider_install_thread: TtsProviderInstallThread | None = None
        self._last_training_model_name = ""
        self._refreshing_provider_combo = False
        self._provider_rows_by_id: dict[str, dict[str, Any]] = {}
        self._last_selected_provider_id = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 5, 6, 7)
        layout.setSpacing(6)

        card, card_layout = self._card("")
        self._add_logo_header(card_layout)
        self._status_label = QLabel("", self)
        self._status_label.setObjectName("SoundSubtitle")
        self._status_label.setWordWrap(True)
        self._detail_label = QLabel("", self)
        self._detail_label.setObjectName("SoundFieldLabel")
        self._detail_label.setWordWrap(True)
        self._server_label = QLabel("", self)
        self._server_label.setObjectName("SoundSubtitle")
        self._server_label.setWordWrap(True)
        card_layout.addWidget(self._status_label)
        card_layout.addWidget(self._detail_label)
        card_layout.addWidget(self._server_label)

        button_row = QWidget(self)
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(5)
        self._install_btn = self._button("Install", "Install the selected Voice Library when an automatic installer is available.")
        self._connect_btn = self._button("Connect", "Choose an existing Style-Bert-VITS2 folder.")
        self._start_btn = self._button("Start server", "Start server_fastapi.py for the connected TTS sidecar.")
        self._guide_btn = self._button("Guide", "Open the local TTS install folder or setup guide.")
        self._refresh_btn = self._button("Refresh", "Refresh local TTS sidecar status.")
        self._install_btn.clicked.connect(self.install_selected_provider)
        self._connect_btn.clicked.connect(self.connect_existing)
        self._start_btn.clicked.connect(self.start_server)
        self._guide_btn.clicked.connect(self.open_guide)
        self._refresh_btn.clicked.connect(self.refresh)
        for button in (self._install_btn, self._connect_btn, self._start_btn, self._guide_btn, self._refresh_btn):
            button_layout.addWidget(button, 1)
        card_layout.addWidget(button_row)

        provider_row = QWidget(self)
        provider_layout = QHBoxLayout(provider_row)
        provider_layout.setContentsMargins(0, 0, 0, 0)
        provider_layout.setSpacing(5)
        provider_label = QLabel("Voice Library", provider_row)
        provider_label.setObjectName("SoundFieldLabel")
        self._provider_combo = VoiceLabComboBox(provider_row)
        self._provider_combo.setObjectName("SoundPresetCombo")
        self._provider_combo.setMinimumHeight(32)
        self._style_combo_popup(self._provider_combo)
        self._provider_combo.setToolTip("Choose the local voice library used by Voice Lab.")
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(provider_label)
        provider_layout.addWidget(self._provider_combo, 1)
        card_layout.addWidget(provider_row)

        voice_row = QWidget(self)
        voice_layout = QHBoxLayout(voice_row)
        voice_layout.setContentsMargins(0, 0, 0, 0)
        voice_layout.setSpacing(5)
        voice_label = QLabel("Voice", voice_row)
        voice_label.setObjectName("SoundFieldLabel")
        self._voice_combo = VoiceLabComboBox(voice_row)
        self._voice_combo.setObjectName("SoundPresetCombo")
        self._voice_combo.setMinimumHeight(32)
        self._style_combo_popup(self._voice_combo)
        self._subtitle_track_btn = self._button(
            "Subtitles -> Track",
            "Generate TTS wav files from project subtitles. If the local server is off, Voice Lab starts it and waits.",
        )
        self._subtitle_track_btn.clicked.connect(self.generate_subtitle_track)
        voice_layout.addWidget(voice_label)
        voice_layout.addWidget(self._voice_combo, 1)
        voice_layout.addWidget(self._subtitle_track_btn, 1)
        card_layout.addWidget(voice_row)

        dialogue_label = QLabel("AI Dialogue Take", self)
        dialogue_label.setObjectName("SoundFieldLabel")
        self._dialogue_take_edit = QPlainTextEdit(self)
        self._dialogue_take_edit.setObjectName("SoundDialogueEdit")
        self._dialogue_take_edit.setPlaceholderText(
            "Type dialogue here. Use Japanese => Korean to speak JP while showing KR subtitles."
        )
        self._dialogue_take_edit.setMinimumHeight(92)
        self._dialogue_take_edit.setMaximumHeight(128)
        card_layout.addWidget(dialogue_label)
        card_layout.addWidget(self._dialogue_take_edit)

        take_row = QWidget(self)
        take_layout = QHBoxLayout(take_row)
        take_layout.setContentsMargins(0, 0, 0, 0)
        take_layout.setSpacing(5)
        self._dialogue_actor_combo = VoiceLabComboBox(take_row)
        self._dialogue_actor_combo.setObjectName("SoundPresetCombo")
        self._dialogue_actor_combo.setMinimumHeight(32)
        self._style_combo_popup(self._dialogue_actor_combo)
        self._dialogue_actor_combo.setToolTip("Live2D target. Auto uses the selected timeline actor or the first available Live2D actor.")
        self._dialogue_placement_combo = VoiceLabComboBox(take_row)
        self._dialogue_placement_combo.setObjectName("SoundPresetCombo")
        self._dialogue_placement_combo.setMinimumHeight(32)
        self._style_combo_popup(self._dialogue_placement_combo)
        self._dialogue_size_combo = VoiceLabComboBox(take_row)
        self._dialogue_size_combo.setObjectName("SoundPresetCombo")
        self._dialogue_size_combo.setMinimumHeight(32)
        self._style_combo_popup(self._dialogue_size_combo)
        self._dialogue_take_btn = self._button(
            "Generate Take",
            "Create subtitles, TTS, Live2D mouth/blink animation, and bottom-anchored placement.",
        )
        self._dialogue_take_btn.clicked.connect(self.generate_dialogue_take)
        take_layout.addWidget(self._dialogue_actor_combo, 2)
        take_layout.addWidget(self._dialogue_placement_combo, 1)
        take_layout.addWidget(self._dialogue_size_combo, 1)
        take_layout.addWidget(self._dialogue_take_btn, 1)
        card_layout.addWidget(take_row)

        training_row = QWidget(self)
        training_layout = QHBoxLayout(training_row)
        training_layout.setContentsMargins(0, 0, 0, 0)
        training_layout.setSpacing(5)
        train_label = QLabel("Model Maker", training_row)
        train_label.setObjectName("SoundFieldLabel")
        self._prepare_model_btn = self._button("Prepare", "Create Data/<model>/raw and optionally copy source voice clips.")
        self._dataset_ui_btn = self._button("Dataset UI", "Open Style-Bert-VITS2 Dataset UI for slicing and transcription.")
        self._train_ui_btn = self._button("Train UI", "Open Style-Bert-VITS2 Train UI for preprocessing and training.")
        self._register_model_btn = self._button("Register", "Validate a completed model_assets/<model> folder and refresh voices.")
        self._prepare_model_btn.clicked.connect(self.prepare_training_workspace)
        self._dataset_ui_btn.clicked.connect(self.launch_dataset_tool)
        self._train_ui_btn.clicked.connect(self.launch_train_tool)
        self._register_model_btn.clicked.connect(self.register_training_model)
        training_layout.addWidget(train_label)
        for button in (self._prepare_model_btn, self._dataset_ui_btn, self._train_ui_btn, self._register_model_btn):
            training_layout.addWidget(button, 1)
        card_layout.addWidget(training_row)

        self._steps_label = QLabel("", self)
        self._steps_label.setObjectName("SoundSubtitle")
        self._steps_label.setWordWrap(True)
        card_layout.addWidget(self._steps_label)
        layout.addWidget(card)
        layout.addStretch(1)
        self.refresh()

    def _qss(self) -> str:
        return (
            f"QWidget#VoiceLabPage {{ background:#101112; font-family:{FONT_FAMILY}; }}"
            "QFrame#SoundCard { background:transparent; border:none; border-top:1px solid rgba(178,186,202,16); border-radius:0px; }"
            "QLabel#VoiceLabWordmark { color:#F6F8FF; font-size:34px; font-weight:900; background:transparent; padding:12px 4px 10px 4px; }"
            "QLabel#SoundCardTitle { color:#DDE2EA; font-size:14px; font-weight:760; background:transparent; }"
            "QLabel#SoundSubtitle { color:#AEB6C5; font-size:12px; font-weight:560; background:transparent; }"
            "QLabel#SoundFieldLabel { color:#C8CEDA; font-size:12px; font-weight:660; background:transparent; }"
            "QPushButton#SoundPresetButton {"
            "background:rgba(255,255,255,5); color:#C7CEDA; border:1px solid rgba(178,186,202,22);"
            "border-radius:7px; padding:7px 10px; font-size:12px; font-weight:720;"
            "}"
            "QPushButton#SoundPresetButton:hover {"
            "background:rgba(255,255,255,11); border-color:rgba(220,225,238,62); color:#FFFFFF;"
            "}"
            "QPushButton#SoundPresetButton:disabled { color:rgba(199,206,218,72); border-color:rgba(178,186,202,12); }"
            "QComboBox#SoundPresetCombo {"
            "background:rgba(255,255,255,5); color:#D7DAE7; border:1px solid rgba(178,186,202,24);"
            "border-radius:7px; padding:5px 10px; font-size:12px; font-weight:650; min-height:30px;"
            "}"
            "QComboBox#SoundPresetCombo:hover { background:rgba(255,255,255,10); border-color:rgba(220,225,238,62); }"
            "QComboBox#SoundPresetCombo QAbstractItemView {"
            "background:#111316; color:#E9ECF7; border:1px solid rgba(178,186,202,52);"
            "selection-background-color:#5268FF; selection-color:#FFFFFF; outline:0px;"
            "font-size:12px; font-weight:650;"
            "}"
            "QPlainTextEdit#SoundDialogueEdit {"
            "background:rgba(255,255,255,5); color:#D7DAE7; border:1px solid rgba(178,186,202,24);"
            "border-radius:7px; padding:8px 10px; font-size:12px; selection-background-color:#486BFF;"
            "}"
            "QPlainTextEdit#SoundDialogueEdit:focus { border-color:rgba(125,180,255,92); background:rgba(255,255,255,8); }"
            + editor_scrollbar_qss("QWidget#VoiceLabPage")
        )

    def _card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame(self)
        card.setObjectName("SoundCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(6)
        if title:
            label = QLabel(title, card)
            label.setObjectName("SoundCardTitle")
            layout.addWidget(label)
        return card, layout

    def _add_logo_header(self, layout: QVBoxLayout) -> None:
        parent = layout.parentWidget() or self
        title = QLabel("VOICE LAB", parent)
        title.setObjectName("VoiceLabWordmark")
        title.setMinimumHeight(72)
        title.setMaximumHeight(96)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        font = QFont(title.font())
        font.setBold(True)
        font.setPixelSize(34)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4.0)
        title.setFont(font)
        layout.addWidget(title)

    def _style_combo_popup(self, combo: QComboBox) -> None:
        try:
            view = QListView(combo)
            view.setFrameShape(QFrame.Shape.NoFrame)
            combo.setView(view)
            view.setObjectName("VoiceLabComboPopup")
            view.setStyleSheet(_VOICE_LAB_COMBO_POPUP_QSS)
            view.setAutoFillBackground(True)
            viewport = view.viewport()
            viewport.setAutoFillBackground(True)
            viewport.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            viewport.setStyleSheet("background:#111316; color:#E9ECF7;")
            palette = view.palette()
            palette.setColor(QPalette.ColorRole.Base, QColor("#111316"))
            palette.setColor(QPalette.ColorRole.Window, QColor("#111316"))
            palette.setColor(QPalette.ColorRole.Text, QColor("#E9ECF7"))
            palette.setColor(QPalette.ColorRole.Highlight, QColor("#5268FF"))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
            view.setPalette(palette)
            viewport.setPalette(palette)
        except Exception:
            pass

    def _button(self, text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName("SoundPresetButton")
        button.setMinimumHeight(32)
        button.setToolTip(tooltip)
        button.setAccessibleName(text)
        return button

    def refresh(self) -> None:
        try:
            from app.tts_setup import tts_setup_view_model

            view = tts_setup_view_model()
        except Exception as exc:
            self._status_label.setText("TTS setup status unavailable")
            self._detail_label.setText(str(exc))
            self._steps_label.setText("")
            return
        self._refresh_provider_combo(list(view.get("providers") or []), str(view.get("provider_id") or ""))
        ready = bool(view.get("ready"))
        root = str(view.get("root") or "")
        endpoint = str(view.get("endpoint") or "")
        provider_id = str(view.get("provider_id") or "")
        provider_label = str(view.get("provider_label") or "Local TTS")
        requires_server = bool(view.get("requires_server", True))
        server_running = False
        server_note = f"{provider_label}: install/connect TTS first."
        if ready and not requires_server:
            server_note = f"{provider_label}: ready. This engine runs locally without a server."
        elif ready:
            try:
                from app.tts_sidecar_runtime import tts_endpoint_health

                health = tts_endpoint_health(endpoint, timeout_s=0.2)
                server_running = bool(health.get("running"))
                server_note = (
                    f"Server: running at {endpoint}."
                    if server_running
                    else f"Server: offline at {endpoint}. Subtitles -> Track will auto-start it and wait."
                )
            except Exception:
                server_note = f"Server: not checked. Subtitles -> Track will auto-start {endpoint} if needed."
        model_names = [str(name) for name in list(view.get("model_names") or [])[:4]]
        model_suffix = f" | Models: {', '.join(model_names)}" if model_names else ""
        self._refresh_voice_combo(list(view.get("model_names") or []))
        self._refresh_dialogue_take_choices()
        self._status_label.setText(
            f"{view.get('status_label', 'Setup needed')} | {view.get('subtitle', 'Local TTS')}{model_suffix}"
        )
        detail = str(view.get("detail") or "")
        if root:
            detail += f"\nRoot: {root}"
        if endpoint:
            detail += f"\nEndpoint: {endpoint}"
        self._detail_label.setText(detail.strip())
        self._server_label.setText(server_note)
        cards = list((view.get("instructions") or {}).get("cards") or [])
        self._steps_label.setText("\n".join(f"- {row.get('title', '')}: {row.get('body', '')}" for row in cards[:3]))
        self._install_btn.setEnabled(not ready)
        self._install_btn.setText("Install")
        self._connect_btn.setText("Connect")
        self._start_btn.setEnabled(ready and requires_server)
        self._start_btn.setVisible(requires_server)
        self._subtitle_track_btn.setEnabled(ready and self._voice_combo.count() > 0)
        self._dialogue_take_btn.setEnabled(ready and self._voice_combo.count() > 0)
        for button in (self._prepare_model_btn, self._dataset_ui_btn, self._train_ui_btn, self._register_model_btn):
            button.setEnabled(ready and provider_id == "style_bert_vits2_sidecar")
            button.setVisible(provider_id == "style_bert_vits2_sidecar")

    def _refresh_provider_combo(self, providers: list[Any], selected_provider_id: str) -> None:
        current = str(self._provider_combo.currentData() or "")
        rows = [dict(row) for row in providers if isinstance(row, dict) and str(row.get("provider_id") or "")]
        rows.sort(
            key=lambda row: (
                0 if bool(row.get("available")) else 1,
                0 if bool(row.get("installed")) else 1,
                0 if not bool(row.get("catalog_only")) else 1,
                str(row.get("label") or row.get("provider_id") or "").casefold(),
            )
        )
        self._provider_rows_by_id = {str(row.get("provider_id") or ""): row for row in rows}
        self._refreshing_provider_combo = True
        self._provider_combo.blockSignals(True)
        self._provider_combo.clear()
        for row in rows:
            provider_id = str(row.get("provider_id") or "")
            label = str(row.get("label") or provider_id)
            available = bool(row.get("available"))
            installed = bool(row.get("installed"))
            catalog_only = bool(row.get("catalog_only"))
            state = "ready" if available else str(row.get("setup_state") or ("installed" if installed else "install"))
            suffix = "Ready" if available else ("Planned" if catalog_only else ("Setup needed" if installed else "Install"))
            self._provider_combo.addItem(f"{label} - {suffix}", provider_id)
            index = self._provider_combo.count() - 1
            self._provider_combo.setItemData(index, available, Qt.ItemDataRole.UserRole + 1)
            self._provider_combo.setItemData(index, row, Qt.ItemDataRole.UserRole + 2)
            self._provider_combo.setItemData(index, str(row.get("reason") or state), Qt.ItemDataRole.ToolTipRole)
            self._provider_combo.setItemData(
                index,
                QBrush(QColor("#E9ECF7") if available else QColor("#818794")),
                Qt.ItemDataRole.ForegroundRole,
            )
        wanted = selected_provider_id or current
        idx = self._provider_combo.findData(wanted)
        if idx >= 0:
            self._provider_combo.setCurrentIndex(idx)
        elif self._provider_combo.count() > 0:
            self._provider_combo.setCurrentIndex(0)
        selected_now = str(self._provider_combo.currentData() or "")
        selected_row = self._provider_rows_by_id.get(selected_now) or {}
        if bool(selected_row.get("available")):
            self._last_selected_provider_id = selected_now
        elif not self._last_selected_provider_id:
            self._last_selected_provider_id = next((str(row.get("provider_id") or "") for row in rows if bool(row.get("available"))), selected_now)
        self._provider_combo.blockSignals(False)
        self._refreshing_provider_combo = False

    def _selected_provider_id(self) -> str:
        return str(self._provider_combo.currentData() or "")

    def _on_provider_changed(self, *_args: Any) -> None:
        if self._refreshing_provider_combo:
            return
        provider_id = self._selected_provider_id()
        if not provider_id:
            return
        row = dict(self._provider_rows_by_id.get(provider_id) or {})
        if row and not bool(row.get("available")):
            if self._confirm_install_for_provider(provider_id, row):
                return
            self._restore_provider_selection()
            return
        try:
            from app.tts_setup import save_tts_selected_provider

            save_tts_selected_provider(provider_id)
        except Exception as exc:
            self._status_label.setText(f"Could not select TTS engine: {exc}")
            return
        self._last_selected_provider_id = provider_id
        self.refresh()

    def _refresh_voice_combo(self, model_names: list[Any]) -> None:
        selected = str(self._voice_combo.currentData() or self._voice_combo.currentText() or "")
        names = [str(name) for name in model_names if str(name or "").strip()]
        self._voice_combo.blockSignals(True)
        self._voice_combo.clear()
        for name in names:
            self._voice_combo.addItem(name, name)
        preferred = selected
        if not preferred:
            preferred = next(
                (name for name in names if name.casefold() == "koharune-ami"),
                next((name for name in names if name.casefold() == "zoe"), names[0] if names else ""),
            )
        if preferred:
            idx = self._voice_combo.findData(preferred)
            self._voice_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._voice_combo.blockSignals(False)

    def _refresh_dialogue_take_choices(self) -> None:
        actor_selected = str(self._dialogue_actor_combo.currentData() or "")
        placement_selected = str(self._dialogue_placement_combo.currentData() or "")
        size_selected = str(self._dialogue_size_combo.currentData() or "")
        self._dialogue_actor_combo.blockSignals(True)
        self._dialogue_placement_combo.blockSignals(True)
        self._dialogue_size_combo.blockSignals(True)
        self._dialogue_actor_combo.clear()
        self._dialogue_placement_combo.clear()
        self._dialogue_size_combo.clear()
        self._dialogue_actor_combo.addItem("Auto Live2D", "")
        try:
            registry = self._resolve_action_registry()
            result = (
                registry.execute(
                    "tts.dialogue.plan_actor_take",
                    {
                        "provider_id": self._selected_provider_id(),
                        "dialogue_text": self._dialogue_take_edit.toPlainText(),
                    },
                ).to_dict()
                if registry is not None
                else {"ok": False}
            )
            payload = dict(result.get("result") or {}) if result.get("ok") else {}
        except Exception:
            payload = {}
        for target in list(payload.get("live2d_targets") or []):
            if not isinstance(target, dict):
                continue
            label = str(target.get("label") or target.get("id") or "Live2D")
            target_id = str(target.get("id") or "")
            self._dialogue_actor_combo.addItem(label, target_id)
        placements = list(payload.get("placement_presets") or [])
        sizes = list(payload.get("size_presets") or [])
        if not placements:
            placements = [
                {"id": "bottom_right", "label": "Bottom Right"},
                {"id": "bottom_left", "label": "Bottom Left"},
                {"id": "center_bottom", "label": "Center Bottom"},
            ]
        if not sizes:
            sizes = [
                {"id": "auto_fit", "label": "Auto Fit"},
                {"id": "bust_up", "label": "Bust Up"},
                {"id": "half_body", "label": "Half Body"},
            ]
        for row in placements:
            self._dialogue_placement_combo.addItem(str(row.get("label") or row.get("id")), str(row.get("id") or "bottom_right"))
        for row in sizes:
            self._dialogue_size_combo.addItem(str(row.get("label") or row.get("id")), str(row.get("id") or "auto_fit"))
        recommended = dict(payload.get("recommended") or {})
        self._set_combo_data(self._dialogue_actor_combo, actor_selected or str(recommended.get("actor_target_id") or ""))
        self._set_combo_data(self._dialogue_placement_combo, placement_selected or str(recommended.get("placement_preset") or "bottom_right"))
        self._set_combo_data(self._dialogue_size_combo, size_selected or str(recommended.get("size_preset") or "auto_fit"))
        self._dialogue_actor_combo.blockSignals(False)
        self._dialogue_placement_combo.blockSignals(False)
        self._dialogue_size_combo.blockSignals(False)

    def _set_combo_data(self, combo: QComboBox, data: str) -> None:
        idx = combo.findData(data)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        elif combo.count() > 0:
            combo.setCurrentIndex(0)

    def _restore_provider_selection(self) -> None:
        wanted = self._last_selected_provider_id
        if not wanted and self._provider_combo.count() > 0:
            wanted = str(self._provider_combo.itemData(0) or "")
        self._refreshing_provider_combo = True
        self._provider_combo.blockSignals(True)
        idx = self._provider_combo.findData(wanted)
        if idx >= 0:
            self._provider_combo.setCurrentIndex(idx)
        elif self._provider_combo.count() > 0:
            self._provider_combo.setCurrentIndex(0)
        self._provider_combo.blockSignals(False)
        self._refreshing_provider_combo = False

    def _install_command_from_plan(self, plan: dict[str, Any]) -> list[str]:
        commands = plan.get("commands") if isinstance(plan.get("commands"), dict) else {}
        for key in ("install_and_warmup", "install", "download"):
            command = commands.get(key) if isinstance(commands, dict) else None
            if isinstance(command, list) and command:
                return [str(part) for part in command if str(part)]
        return []

    def _confirm_install_for_provider(self, provider_id: str, row: dict[str, Any]) -> bool:
        try:
            from app.tts_setup import save_tts_selected_provider, tts_install_plan

            plan = tts_install_plan(provider_id=provider_id)
        except Exception as exc:
            QMessageBox.warning(self, "Voice Lab", f"Could not prepare install plan: {exc}")
            return False
        command = self._install_command_from_plan(plan)
        label = str(row.get("label") or plan.get("title") or provider_id)
        target = str(plan.get("target_root") or "")
        if bool(row.get("catalog_only")) or not bool(row.get("install_supported", True)):
            QMessageBox.information(
                self,
                "Voice Lab",
                (
                    f"{label} is listed in the Voice Library catalog.\n\n"
                    "Automatic install is not available yet because the Tiger Studio adapter is not implemented.\n\n"
                    f"{row.get('reason') or plan.get('estimated_download') or ''}"
                ),
            )
            self.show_install_plan(provider_id=provider_id)
            return False
        if not command:
            self.show_install_plan(provider_id=provider_id)
            return False
        answer = QMessageBox.question(
            self,
            "Voice Lab",
            (
                f"{label} is not ready.\n\n"
                f"Install now?\n\n"
                f"Target: {target}\n"
                f"Download: {plan.get('estimated_download', '')}\n\n"
                f"{plan.get('license_notice', '')}"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        try:
            save_tts_selected_provider(provider_id)
        except Exception:
            pass
        self._last_selected_provider_id = provider_id
        self._start_provider_install(provider_id, plan, command)
        return True

    def _start_provider_install(self, provider_id: str, plan: dict[str, Any], command: list[str]) -> None:
        if self._provider_install_thread is not None and self._provider_install_thread.isRunning():
            QMessageBox.information(self, "Voice Lab", "A voice library install is already running.")
            return
        target = str(plan.get("target_root") or "")
        cwd = str(Path(target).parent) if target else ""
        self._status_label.setText(f"Installing {plan.get('title', provider_id)}...")
        self._detail_label.setText(f"Command: {' '.join(command)}")
        self._install_btn.setEnabled(False)
        self._connect_btn.setEnabled(False)
        self._provider_install_thread = TtsProviderInstallThread(command, cwd=cwd, provider_id=provider_id, parent=self)
        self._provider_install_thread.finished_payload.connect(self._on_provider_install_finished)
        self._provider_install_thread.start()

    def _on_provider_install_finished(self, payload: dict[str, Any]) -> None:
        ok = bool(payload.get("ok"))
        provider_id = str(payload.get("provider_id") or self._selected_provider_id())
        self._provider_install_thread = None
        if ok:
            self._status_label.setText("Voice library install finished.")
            self._server_label.setText("Refreshing Voice Lab status.")
            self.refresh()
            QMessageBox.information(self, "Voice Lab", "Voice library install finished.")
            return
        error = str(payload.get("error") or "Voice library install failed.")
        stderr = str(payload.get("stderr") or "").strip()
        self._status_label.setText(error)
        self.refresh()
        QMessageBox.warning(self, "Voice Lab", f"{error}\n\n{stderr[-1200:]}")
        if provider_id:
            self._restore_provider_selection()

    def install_selected_provider(self) -> None:
        provider_id = self._selected_provider_id()
        row = dict(self._provider_rows_by_id.get(provider_id) or {})
        if row and bool(row.get("available")):
            self._status_label.setText(f"{row.get('label', 'Selected voice library')} is already ready.")
            return
        if row:
            self._confirm_install_for_provider(provider_id, row)
            return
        self.show_install_plan(provider_id=provider_id)

    def show_install_plan(self, *, provider_id: str = "") -> None:
        try:
            from app.tts_setup import tts_install_plan

            plan = tts_install_plan(provider_id=provider_id or self._selected_provider_id())
        except Exception as exc:
            self._status_label.setText(f"Could not prepare TTS install plan: {exc}")
            return
        steps = "\n".join(f"{idx + 1}. {row.get('label', '')}" for idx, row in enumerate(plan.get("steps") or []))
        message = (
            f"{plan.get('title', 'Install local TTS')}\n\n"
            f"Target: {plan.get('target_root', '')}\n"
            f"Download: {plan.get('estimated_download', '')}\n\n"
            f"{plan.get('license_notice', '')}\n\n{steps}"
        )
        QMessageBox.information(self, "Voice Lab TTS install", message)
        self.refresh()

    def connect_existing(self) -> None:
        provider_id = self._selected_provider_id()
        if provider_id == "kokoro_local":
            start_dir = Path(__file__).resolve().parents[1] / "external" / "tools" / "tts" / "kokoro"
            title = "Connect Kokoro"
        elif provider_id == "gpt_sovits_sidecar":
            start_dir = Path(__file__).resolve().parents[1] / "external" / "tools" / "tts" / "gpt-sovits"
            title = "Connect GPT-SoVITS"
        else:
            start_dir = Path(r"D:\TTS\sbv2\Style-Bert-VITS2")
            title = "Connect Style-Bert-VITS2"
        selected = QFileDialog.getExistingDirectory(
            self,
            title,
            str(start_dir if start_dir.exists() else Path.home()),
        )
        if not selected:
            return
        try:
            from app.tts_setup import connect_installed_tts_provider

            result = connect_installed_tts_provider(selected, provider_id=provider_id)
        except Exception as exc:
            QMessageBox.warning(self, "Voice Lab", f"Could not connect TTS: {exc}")
            return
        if not result.get("ok"):
            missing = ", ".join(result.get("missing") or [])
            QMessageBox.warning(self, "Voice Lab", f"Selected folder is not a complete TTS install.\nMissing: {missing}")
        self.refresh()

    def open_guide(self) -> None:
        try:
            from app.tts_setup import tts_setup_view_model

            view = tts_setup_view_model(provider_id=self._selected_provider_id())
            root = Path(str(view.get("root") or r"D:\TTS\sbv2\Style-Bert-VITS2"))
        except Exception:
            root = Path(r"D:\TTS\sbv2\Style-Bert-VITS2")
        target = root / "README.md" if (root / "README.md").exists() else root
        if not target.exists():
            target = Path(__file__).resolve().parents[1] / "external" / "tools" / "tts"
            try:
                target.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        except Exception as exc:
            self._status_label.setText(f"Could not open TTS guide: {exc}")

    def generate_subtitle_track(self) -> None:
        registry = self._resolve_action_registry()
        if registry is None:
            QMessageBox.warning(self, "Voice Lab", "Open Voice Lab inside the editor before generating subtitle audio.")
            return
        model_name = str(self._voice_combo.currentData() or self._voice_combo.currentText() or "")
        provider_id = self._selected_provider_id()
        self._server_label.setText(
            "TTS: preparing selected engine. Server will only be started when the selected engine needs one."
        )
        QApplication.processEvents()
        actor_target = self._first_live2d_actor_target()
        params = {
            "provider_id": provider_id,
            "model_name": model_name,
            "track_name": "TTS Dialogue",
            "replace_existing": True,
            "auto_start_server": True,
            "server_wait_timeout_s": 120.0,
        }
        if actor_target is not None:
            params.update(
                {
                    "apply_actor_lipsync": True,
                    "actor_track_id": actor_target[0],
                    "actor_clip_index": actor_target[1],
                    "lipsync_include_blink": True,
                }
            )
        result = registry.execute(
            "tts.subtitle.generate_to_timeline",
            params,
        ).to_dict()
        if not result.get("ok"):
            self._server_label.setText(
                "Server: could not become ready. Use Start server once, then retry Subtitles -> Track."
            )
            QMessageBox.warning(self, "Voice Lab", str(result.get("error") or "Subtitle TTS generation failed."))
            return
        payload = dict(result.get("result") or {})
        server = dict(payload.get("server") or {})
        self._server_label.setText(str(server.get("message") or "Server: ready."))
        QMessageBox.information(
            self,
            "Voice Lab",
            (
                f"Generated {payload.get('clip_count', 0)} subtitle voice clip(s) on "
                f"{payload.get('track_name', 'TTS Dialogue')}."
                + (
                    " Live2D mouth/blink keys were applied."
                    if dict(payload.get("actor_lipsync") or {}).get("applied")
                    else ""
                )
            ),
        )

    def generate_dialogue_take(self) -> None:
        registry = self._resolve_action_registry()
        if registry is None:
            QMessageBox.warning(self, "Voice Lab", "Open Voice Lab inside the editor before generating an AI Dialogue Take.")
            return
        text = self._dialogue_take_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Voice Lab", "Type dialogue first.")
            return
        model_name = str(self._voice_combo.currentData() or self._voice_combo.currentText() or "")
        provider_id = self._selected_provider_id()
        self._server_label.setText("Server: preparing AI Dialogue Take. Voice Lab will start TTS if needed.")
        QApplication.processEvents()
        result = registry.execute(
            "tts.dialogue.generate_actor_take",
            {
                "dialogue_text": text,
                "provider_id": provider_id,
                "model_name": model_name,
                "track_name": "AI Dialogue Take",
                "replace_existing": False,
                "auto_start_server": True,
                "server_wait_timeout_s": 120.0,
                "actor_target_id": str(self._dialogue_actor_combo.currentData() or ""),
                "placement_preset": str(self._dialogue_placement_combo.currentData() or "bottom_right"),
                "size_preset": str(self._dialogue_size_combo.currentData() or "auto_fit"),
                "apply_actor_lipsync": True,
                "apply_actor_placement": True,
                "lipsync_include_blink": True,
            },
        ).to_dict()
        if not result.get("ok"):
            self._server_label.setText("Server: AI Dialogue Take failed.")
            QMessageBox.warning(self, "Voice Lab", str(result.get("error") or "AI Dialogue Take generation failed."))
            return
        payload = dict(result.get("result") or {})
        tts = dict(payload.get("tts") or {})
        server = dict(tts.get("server") or {})
        self._server_label.setText(str(server.get("message") or "AI Dialogue Take generated."))
        placement = dict(payload.get("placement") or {})
        lipsync = dict(payload.get("actor_lipsync") or {})
        QMessageBox.information(
            self,
            "AI Dialogue Take",
            (
                f"Generated {tts.get('clip_count', 0)} voice clip(s) and "
                f"{payload.get('dialogue_line_count', 0)} subtitle line(s).\n"
                f"Live2D lip-sync: {'applied' if lipsync.get('applied') else lipsync.get('reason', 'not applied')}\n"
                f"Placement: {'measured' if placement.get('measured') else placement.get('reason', 'fallback')}"
            ),
        )
        self._refresh_dialogue_take_choices()

    def _ask_training_model_name(self) -> str:
        text, ok = QInputDialog.getText(
            self,
            "Voice model name",
            "Model name",
            text=self._last_training_model_name or "new_voice",
        )
        if not ok:
            return ""
        name = str(text or "").strip()
        if name:
            self._last_training_model_name = name
        return name

    def prepare_training_workspace(self) -> None:
        registry = self._resolve_action_registry()
        if registry is None:
            QMessageBox.warning(self, "Voice Lab", "Could not prepare the TTS action registry.")
            return
        model_name = self._ask_training_model_name()
        if not model_name:
            return
        source_dir = ""
        choice = QMessageBox.question(
            self,
            "Voice source clips",
            "Copy source audio clips into the training raw folder now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if choice == QMessageBox.StandardButton.Yes:
            selected = QFileDialog.getExistingDirectory(self, "Source voice clips", str(Path.home()))
            source_dir = str(selected or "")
        result = registry.execute(
            "tts.model.training.prepare_workspace",
            {"model_name": model_name, "source_audio_dir": source_dir},
        ).to_dict()
        if not result.get("ok"):
            QMessageBox.warning(self, "Voice Lab", str(result.get("error") or "Could not prepare model workspace."))
            return
        payload = dict(result.get("result") or {})
        self._server_label.setText(f"Model Maker: prepared {payload.get('model_name', model_name)}.")
        QMessageBox.information(
            self,
            "Voice Lab Model Maker",
            (
                f"Raw folder:\n{payload.get('raw_audio_dir', '')}\n\n"
                f"Copied clips: {payload.get('copied_count', 0)}\n\n"
                "Next: open Dataset UI to slice/transcribe, then Train UI to preprocess and train."
            ),
        )

    def launch_dataset_tool(self) -> None:
        self._launch_training_tool("tts.model.training.launch_dataset", "Dataset UI")

    def launch_train_tool(self) -> None:
        self._launch_training_tool("tts.model.training.launch_train", "Train UI")

    def _launch_training_tool(self, action_id: str, label: str) -> None:
        registry = self._resolve_action_registry()
        if registry is None:
            QMessageBox.warning(self, "Voice Lab", "Could not prepare the TTS action registry.")
            return
        model_name = self._last_training_model_name or self._ask_training_model_name()
        result = registry.execute(action_id, {"model_name": model_name}).to_dict()
        if not result.get("ok"):
            QMessageBox.warning(self, "Voice Lab", str(result.get("error") or f"Could not launch {label}."))
            return
        payload = dict(result.get("result") or {})
        self._server_label.setText(str(payload.get("message") or f"{label} started."))

    def register_training_model(self) -> None:
        registry = self._resolve_action_registry()
        if registry is None:
            QMessageBox.warning(self, "Voice Lab", "Could not prepare the TTS action registry.")
            return
        model_name = self._ask_training_model_name()
        if not model_name:
            return
        result = registry.execute("tts.model.training.register_result", {"model_name": model_name}).to_dict()
        if not result.get("ok"):
            QMessageBox.warning(self, "Voice Lab", str(result.get("error") or "Could not validate model."))
            return
        payload = dict(result.get("result") or {})
        self._server_label.setText(str(payload.get("message") or "Model checked."))
        self.refresh()
        QMessageBox.information(self, "Voice Lab Model Maker", str(payload.get("message") or "Model checked."))

    def _resolve_action_registry(self) -> Any | None:
        for owner in self._owner_candidates():
            ensure = getattr(owner, "_ensure_python_action_registry", None)
            if callable(ensure):
                try:
                    return ensure()
                except Exception:
                    pass
            if hasattr(owner, "_subtitle_panel") or hasattr(owner, "_audio_tracks"):
                try:
                    from app.actions import build_default_action_registry

                    return build_default_action_registry(owner)
                except Exception:
                    return None
        try:
            from app.actions import build_default_action_registry

            return build_default_action_registry(None)
        except Exception:
            return None

    def _owner_candidates(self) -> list[Any]:
        rows: list[Any] = []
        seen: set[int] = set()
        widget: Any | None = self
        for _ in range(32):
            if widget is None:
                break
            for candidate in (
                widget,
                getattr(widget, "_owner", None),
                getattr(widget, "owner", None),
                getattr(widget, "_editor", None),
                getattr(widget, "editor", None),
            ):
                if candidate is None:
                    continue
                key = id(candidate)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(candidate)
            widget = widget.parent() if hasattr(widget, "parent") else None
        return rows

    def _first_live2d_actor_target(self) -> tuple[int, int] | None:
        for owner in self._owner_candidates():
            for track in getattr(owner, "_live2d_actor_tracks", []) or []:
                clips = list(getattr(track, "clips", []) or [])
                if clips:
                    return int(getattr(track, "id", 0) or 0), 0
        return None

    def start_server(self) -> None:
        try:
            from app.tts_setup import tts_server_start_plan

            plan = tts_server_start_plan(provider_id=self._selected_provider_id())
        except Exception as exc:
            self._status_label.setText(f"Could not prepare TTS server start: {exc}")
            return
        if not plan.get("command") and not plan.get("requires_user_action", True):
            self._status_label.setText(str(plan.get("message") or "No server is needed for this TTS engine."))
            return
        if not plan.get("ready"):
            self._status_label.setText(str(plan.get("message") or "Install or connect TTS first."))
            return
        command = [str(part) for part in list(plan.get("command") or []) if str(part)]
        cwd = str(plan.get("cwd") or "")
        if len(command) < 2:
            self._status_label.setText("TTS server command is incomplete.")
            return
        if self._sidecar_process is not None and self._sidecar_process.poll() is None:
            self._status_label.setText(f"TTS server is already starting/running at {plan.get('endpoint', '')}.")
            return
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self._sidecar_process = subprocess.Popen(
                command,
                cwd=cwd or None,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            self._status_label.setText(f"TTS server starting at {plan.get('endpoint', '')}.")
        except Exception as exc:
            self._status_label.setText(f"Could not start TTS server: {exc}")


class TtsLabWindow(QWidget):
    """Top-level Voice Lab shell launched from the Workbench Audio tab."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setObjectName("VoiceLabWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QWidget#VoiceLabWindow { background:#101112; }")
        self.setWindowTitle("Voice Lab")
        self.setMinimumSize(760, 520)
        self.resize(900, 640)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(0)
        self._page = TtsLabPage(self)
        root.addWidget(self._page, 1)

    def voice_lab_page(self) -> TtsLabPage:
        return self._page

    def closeEvent(self, event) -> None:  # pragma: no cover - window manager path
        event.ignore()
        self.hide()


__all__ = ["TtsLabPage", "TtsLabWindow"]
