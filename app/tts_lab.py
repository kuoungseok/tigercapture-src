"""Standalone Voice Lab UI widgets."""
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.style import FONT_FAMILY, editor_scrollbar_qss


_VOICE_LAB_LOGO_PATH = Path(__file__).resolve().parent.parent / "resources" / "branding" / "voice_lab_logo.png"


class TtsLabPage(QWidget):
    """Setup-first page for the local Style-Bert-VITS2 provider."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("VoiceLabPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(420)
        self.setStyleSheet(self._qss())
        self._sidecar_process: subprocess.Popen | None = None

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
        self._install_btn = self._button("Install", "Show the safe install plan for Style-Bert-VITS2 local TTS.")
        self._connect_btn = self._button("Connect", "Choose an existing Style-Bert-VITS2 folder.")
        self._start_btn = self._button("Start server", "Start server_fastapi.py for the connected TTS sidecar.")
        self._guide_btn = self._button("Guide", "Open the local TTS install folder or setup guide.")
        self._refresh_btn = self._button("Refresh", "Refresh local TTS sidecar status.")
        self._install_btn.clicked.connect(self.show_install_plan)
        self._connect_btn.clicked.connect(self.connect_existing)
        self._start_btn.clicked.connect(self.start_server)
        self._guide_btn.clicked.connect(self.open_guide)
        self._refresh_btn.clicked.connect(self.refresh)
        for button in (self._install_btn, self._connect_btn, self._start_btn, self._guide_btn, self._refresh_btn):
            button_layout.addWidget(button, 1)
        card_layout.addWidget(button_row)

        voice_row = QWidget(self)
        voice_layout = QHBoxLayout(voice_row)
        voice_layout.setContentsMargins(0, 0, 0, 0)
        voice_layout.setSpacing(5)
        voice_label = QLabel("Voice", voice_row)
        voice_label.setObjectName("SoundFieldLabel")
        self._voice_combo = QComboBox(voice_row)
        self._voice_combo.setObjectName("SoundPresetCombo")
        self._voice_combo.setMinimumHeight(24)
        self._subtitle_track_btn = self._button(
            "Subtitles -> Track",
            "Generate TTS wav files from project subtitles. If the local server is off, Voice Lab starts it and waits.",
        )
        self._subtitle_track_btn.clicked.connect(self.generate_subtitle_track)
        voice_layout.addWidget(voice_label)
        voice_layout.addWidget(self._voice_combo, 1)
        voice_layout.addWidget(self._subtitle_track_btn, 1)
        card_layout.addWidget(voice_row)

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
            "QLabel#SoundCardTitle { color:#DDE2EA; font-size:10px; font-weight:720; background:transparent; }"
            "QLabel#SoundSubtitle { color:#929AA6; font-size:9px; background:transparent; }"
            "QLabel#SoundFieldLabel { color:#A3ABB7; font-size:9px; font-weight:560; background:transparent; }"
            "QPushButton#SoundPresetButton {"
            "background:rgba(255,255,255,5); color:#C7CEDA; border:1px solid rgba(178,186,202,22);"
            "border-radius:5px; padding:5px 8px; font-size:9px; font-weight:680;"
            "}"
            "QPushButton#SoundPresetButton:hover {"
            "background:rgba(255,255,255,11); border-color:rgba(220,225,238,62); color:#FFFFFF;"
            "}"
            "QPushButton#SoundPresetButton:disabled { color:rgba(199,206,218,72); border-color:rgba(178,186,202,12); }"
            "QComboBox#SoundPresetCombo {"
            "background:rgba(255,255,255,5); color:#D7DAE7; border:1px solid rgba(178,186,202,24);"
            "border-radius:5px; padding:3px 7px; font-size:9px; min-height:20px;"
            "}"
            "QComboBox#SoundPresetCombo:hover { background:rgba(255,255,255,10); border-color:rgba(220,225,238,62); }"
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
        logo = QLabel(parent)
        logo.setObjectName("VoiceLabLogo")
        logo.setMinimumHeight(66)
        logo.setMaximumHeight(106)
        logo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if _VOICE_LAB_LOGO_PATH.exists():
            pixmap = QPixmap(str(_VOICE_LAB_LOGO_PATH))
            if not pixmap.isNull():
                logo.setPixmap(
                    pixmap.scaled(
                        QSize(380, 100),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                layout.addWidget(logo)
                return
        fallback = QLabel("Voice Lab", parent)
        fallback.setObjectName("SoundCardTitle")
        layout.addWidget(fallback)

    def _button(self, text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName("SoundPresetButton")
        button.setMinimumHeight(24)
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
        ready = bool(view.get("ready"))
        root = str(view.get("root") or "")
        endpoint = str(view.get("endpoint") or "")
        server_running = False
        server_note = "Server: install/connect TTS first."
        if ready:
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
        self._start_btn.setEnabled(ready)
        self._subtitle_track_btn.setEnabled(ready and self._voice_combo.count() > 0)

    def _refresh_voice_combo(self, model_names: list[Any]) -> None:
        selected = str(self._voice_combo.currentData() or self._voice_combo.currentText() or "")
        names = [str(name) for name in model_names if str(name or "").strip()]
        self._voice_combo.blockSignals(True)
        self._voice_combo.clear()
        for name in names:
            self._voice_combo.addItem(name, name)
        preferred = selected
        if not preferred:
            preferred = next((name for name in names if name.casefold() == "zoe"), names[0] if names else "")
        if preferred:
            idx = self._voice_combo.findData(preferred)
            self._voice_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._voice_combo.blockSignals(False)

    def show_install_plan(self) -> None:
        try:
            from app.tts_setup import tts_install_plan

            plan = tts_install_plan()
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
        start_dir = Path(r"D:\TTS\sbv2\Style-Bert-VITS2")
        selected = QFileDialog.getExistingDirectory(
            self,
            "Connect Style-Bert-VITS2",
            str(start_dir if start_dir.exists() else Path.home()),
        )
        if not selected:
            return
        try:
            from app.tts_setup import connect_installed_tts

            result = connect_installed_tts(selected)
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

            view = tts_setup_view_model()
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
        self._server_label.setText(
            "Server: checking. If it is offline, Voice Lab will start Style-Bert-VITS2 and wait before generating."
        )
        QApplication.processEvents()
        result = registry.execute(
            "tts.subtitle.generate_to_timeline",
            {
                "model_name": model_name,
                "track_name": "TTS Dialogue",
                "replace_existing": True,
                "auto_start_server": True,
                "server_wait_timeout_s": 120.0,
            },
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
            f"Generated {payload.get('clip_count', 0)} subtitle voice clip(s) on {payload.get('track_name', 'TTS Dialogue')}.",
        )

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

    def start_server(self) -> None:
        try:
            from app.tts_setup import tts_server_start_plan

            plan = tts_server_start_plan()
        except Exception as exc:
            self._status_label.setText(f"Could not prepare TTS server start: {exc}")
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
