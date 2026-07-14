from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_voice_lab_window_uses_text_wordmark_and_readable_combo_popups(monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel, QComboBox

    import app.tts_setup as tts_setup

    def _fake_view_model(provider_id: str = "") -> dict:
        return {
            "ready": True,
            "root": r"D:\TTS\sbv2\Style-Bert-VITS2",
            "endpoint": "http://127.0.0.1:5000",
            "provider_id": provider_id or "style_bert_vits2_sidecar",
            "provider_label": "Style-Bert-VITS2",
            "requires_server": True,
            "status_label": "Ready",
            "subtitle": "Local TTS",
            "model_names": ["koharune-ami", "zoe"],
            "providers": [
                {
                    "provider_id": "style_bert_vits2_sidecar",
                    "label": "Style-Bert-VITS2",
                    "available": True,
                    "setup_state": "ready",
                }
            ],
            "instructions": {"cards": []},
        }

    monkeypatch.setattr(tts_setup, "tts_setup_view_model", _fake_view_model)

    app = _app()
    from app.tts_lab import TtsLabPage

    page = TtsLabPage()
    page.show()
    for _ in range(3):
        app.processEvents()

    try:
        title = page.findChild(QLabel, "VoiceLabWordmark")
        assert title is not None
        assert title.text() == "VOICE LAB"
        assert title.minimumHeight() >= 72
        assert page.findChild(QLabel, "VoiceLabLogo") is None

        for combo in page.findChildren(QComboBox, "SoundPresetCombo"):
            assert combo.minimumHeight() >= 32
            popup_qss = combo.view().styleSheet()
            assert "#111316" in popup_qss
            assert "selection-background-color" in popup_qss
            assert combo.view().autoFillBackground() is True
            assert combo.view().viewport().testAttribute(Qt.WidgetAttribute.WA_StyledBackground) is True
            assert "#111316" in combo.view().viewport().styleSheet()

        assert page._install_btn.minimumHeight() >= 32
        assert page._dialogue_take_edit.minimumHeight() >= 92
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def test_voice_lab_popup_window_root_is_dark(monkeypatch):
    from PySide6.QtCore import Qt

    import app.tts_setup as tts_setup

    def _fake_view_model(provider_id: str = "") -> dict:
        return {
            "ready": False,
            "root": "",
            "endpoint": "",
            "provider_id": provider_id or "kokoro_local",
            "provider_label": "Kokoro",
            "requires_server": False,
            "status_label": "Setup needed",
            "subtitle": "Local TTS",
            "model_names": [],
            "providers": [
                {
                    "provider_id": "kokoro_local",
                    "label": "Kokoro",
                    "available": False,
                    "setup_state": "setup",
                }
            ],
            "instructions": {"cards": []},
        }

    monkeypatch.setattr(tts_setup, "tts_setup_view_model", _fake_view_model)

    app = _app()
    from app.tts_lab import TtsLabWindow

    win = TtsLabWindow()
    win.show()
    for _ in range(3):
        app.processEvents()

    try:
        assert win.testAttribute(Qt.WidgetAttribute.WA_StyledBackground) is True
        assert "QWidget#VoiceLabWindow" in win.styleSheet()
        assert "#101112" in win.styleSheet()
    finally:
        win.hide()
        win.deleteLater()
        app.processEvents()


def test_voice_lab_provider_combo_orders_ready_and_greys_unavailable(monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QBrush

    import app.tts_setup as tts_setup

    def _fake_view_model(provider_id: str = "") -> dict:
        return {
            "ready": True,
            "root": "",
            "endpoint": "",
            "provider_id": provider_id or "kokoro_local",
            "provider_label": "Kokoro",
            "requires_server": False,
            "status_label": "Ready",
            "subtitle": "Local TTS",
            "model_names": ["jf_alpha"],
            "providers": [
                {
                    "provider_id": "style_bert_vits2_sidecar",
                    "label": "Style-Bert-VITS2",
                    "available": False,
                    "installed": False,
                    "setup_state": "needs_install",
                    "reason": "Needs install",
                },
                {
                    "provider_id": "kokoro_local",
                    "label": "Kokoro",
                    "available": True,
                    "installed": True,
                    "setup_state": "ready",
                },
                {
                    "provider_id": "gpt_sovits_sidecar",
                    "label": "GPT-SoVITS",
                    "available": False,
                    "installed": True,
                    "setup_state": "needs_voice_preset",
                    "reason": "Needs voice preset",
                },
            ],
            "instructions": {"cards": []},
        }

    monkeypatch.setattr(tts_setup, "tts_setup_view_model", _fake_view_model)

    app = _app()
    from app.tts_lab import TtsLabPage

    page = TtsLabPage()
    page.show()
    for _ in range(3):
        app.processEvents()

    try:
        combo = page._provider_combo
        assert combo.itemData(0) == "kokoro_local"
        assert combo.itemData(0, Qt.ItemDataRole.UserRole + 1) is True
        assert combo.itemData(1, Qt.ItemDataRole.UserRole + 1) is False
        assert "Install" in combo.itemText(1) or "Setup needed" in combo.itemText(1)
        assert "Needs" in str(combo.itemData(1, Qt.ItemDataRole.ToolTipRole))
        brush = combo.itemData(1, Qt.ItemDataRole.ForegroundRole)
        assert isinstance(brush, QBrush)
        assert brush.color().name().lower() == "#818794"
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def test_voice_lab_unavailable_provider_selection_prompts_install(monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    import app.tts_setup as tts_setup

    def _fake_view_model(provider_id: str = "") -> dict:
        return {
            "ready": True,
            "root": "",
            "endpoint": "",
            "provider_id": provider_id or "kokoro_local",
            "provider_label": "Kokoro",
            "requires_server": False,
            "status_label": "Ready",
            "subtitle": "Local TTS",
            "model_names": ["jf_alpha"],
            "providers": [
                {
                    "provider_id": "kokoro_local",
                    "label": "Kokoro",
                    "available": True,
                    "installed": True,
                    "setup_state": "ready",
                },
                {
                    "provider_id": "gpt_sovits_sidecar",
                    "label": "GPT-SoVITS",
                    "available": False,
                    "installed": False,
                    "setup_state": "needs_install",
                    "reason": "Not downloaded",
                },
            ],
            "instructions": {"cards": []},
        }

    monkeypatch.setattr(tts_setup, "tts_setup_view_model", _fake_view_model)
    monkeypatch.setattr(
        tts_setup,
        "tts_install_plan",
        lambda provider_id="": {
            "title": "Download GPT-SoVITS sidecar",
            "target_root": "E:/fake/gpt-sovits",
            "estimated_download": "Large",
            "license_notice": "Optional sidecar",
            "commands": {"download": ["python", "install_gpt_sovits.py"]},
        },
    )
    selected = []
    monkeypatch.setattr(tts_setup, "save_tts_selected_provider", lambda provider_id: selected.append(provider_id) or True)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

    app = _app()
    from app.tts_lab import TtsLabPage

    page = TtsLabPage()
    captured = {}
    page._start_provider_install = lambda provider_id, plan, command: captured.update(
        {"provider_id": provider_id, "title": plan.get("title"), "command": command}
    )
    page.show()
    for _ in range(3):
        app.processEvents()

    try:
        page._provider_combo.setCurrentIndex(page._provider_combo.findData("gpt_sovits_sidecar"))
        for _ in range(3):
            app.processEvents()
        assert captured["provider_id"] == "gpt_sovits_sidecar"
        assert captured["command"] == ["python", "install_gpt_sovits.py"]
        assert selected == ["gpt_sovits_sidecar"]
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()
