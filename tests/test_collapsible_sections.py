from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_collapsible_asset_and_side_sections_keep_headers_visible():
    from PySide6.QtWidgets import QPushButton

    from app.video_editor_window import VideoEditorWindow

    app = _app()
    win = VideoEditorWindow()
    win.resize(1650, 930)
    win.show()
    for _ in range(4):
        app.processEvents()

    sections = [
        ("_actor_library_section_host", "_actor_library_panel", 88),
        ("_effects_library_section_host", "_effects_preset_panel", 120),
        ("_title_presets_section_host", "_title_presets_panel", 120),
        ("_transitions_section_host", "_transitions_panel", 120),
        ("_workflow_presets_section_host", "_workflow_presets_panel", 120),
        ("_render_queue_section_host", "_render_queue_panel", 34),
        ("_audio_workspace_section_host", "_audio_workspace_label", 20),
    ]
    try:
        for host_attr, controlled_attr, min_open_body_height in sections:
            host = getattr(win, host_attr)
            controlled = getattr(win, controlled_attr)
            toggle = host.findChild(QPushButton, "SectionDisclosure")
            assert toggle is not None

            if not controlled.isVisible():
                toggle.click()
                app.processEvents()
            assert host.isVisible()
            assert controlled.isVisible()
            assert controlled.height() >= min_open_body_height
            assert toggle.property("stateText") == "Hide"
            assert "Hide" in toggle.toolTip()

            toggle.click()
            app.processEvents()
            assert host.isVisible()
            assert not controlled.isVisible()
            assert toggle.property("stateText") == "Show"
            assert "Show" in toggle.toolTip()
            assert host.minimumHeight() >= 34
    finally:
        win.close()
        win.deleteLater()
        app.processEvents()


def test_left_library_sections_expand_when_secondary_splitter_is_small():
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QPushButton

    from app.video_editor_window import VideoEditorWindow

    app = _app()
    win = VideoEditorWindow()
    win.resize(1280, 720)
    win.show()
    for _ in range(4):
        app.processEvents()

    try:
        splitter = win._left_dock_sections_splitter
        splitter.setSizes([640, 42])
        app.processEvents()

        host = win._effects_library_section_host
        body = win._effects_preset_panel
        toggle = host.findChild(QPushButton, "SectionDisclosure")
        assert toggle is not None
        if toggle.isChecked():
            toggle.click()
            app.processEvents()
        assert not body.isVisible()

        header = win._effects_library_header
        pos = header.rect().center()
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            pos,
            pos,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        app.sendEvent(header, event)
        for _ in range(4):
            app.processEvents()

        assert toggle.isChecked()
        assert body.isVisible()
        assert body.height() >= 120
        assert win._left_secondary_sections_host.minimumHeight() >= host.minimumHeight()
        assert splitter.minimumHeight() > win._media_pool_section_host.minimumHeight() + 120
    finally:
        win.close()
        win.deleteLater()
        app.processEvents()


def test_right_workbench_sections_expand_when_secondary_splitter_is_small():
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QPushButton

    from app.video_editor_window import VideoEditorWindow

    app = _app()
    win = VideoEditorWindow()
    win.resize(1280, 720)
    win.show()
    for _ in range(6):
        app.processEvents()

    try:
        splitter = win._right_dock_sections_splitter
        splitter.setSizes([640, 42])
        app.processEvents()

        host = win._ai_script_edit_section_host
        toggle = host.findChild(QPushButton, "SectionDisclosure")
        assert toggle is not None
        if toggle.isChecked():
            toggle.click()
            app.processEvents()
        assert host.minimumHeight() <= 51

        header = host.layout().itemAt(0).widget()
        assert header is not None
        pos = header.rect().center()
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            pos,
            pos,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        app.sendEvent(header, event)
        for _ in range(6):
            app.processEvents()

        assert toggle.isChecked()
        assert host.minimumHeight() >= 320
        assert win._right_secondary_sections_host.minimumHeight() >= host.minimumHeight()
        assert splitter.minimumHeight() > win._workbench_section_host.minimumHeight() + 120
    finally:
        win.close()
        win.deleteLater()
        app.processEvents()


def test_effect_preset_expanded_preview_swatch_is_not_clipped():
    from PySide6.QtWidgets import QPushButton, QWidget

    from app.video_editor_window import VideoEditorWindow

    app = _app()
    win = VideoEditorWindow()
    win.resize(1280, 720)
    win.show()
    for _ in range(4):
        app.processEvents()

    try:
        host = win._effects_library_section_host
        toggle = host.findChild(QPushButton, "SectionDisclosure")
        assert toggle is not None
        if not toggle.isChecked():
            toggle.click()
        for _ in range(8):
            app.processEvents()

        panel = win._effects_preset_panel
        inspector = panel.findChild(QWidget, "PresetInspectorPanel")
        assert inspector is not None
        swatch_slot = inspector.findChild(QWidget, "PresetInspectorSwatchSlot")
        assert swatch_slot is not None
        swatches = [
            widget
            for widget in inspector.findChildren(QWidget)
            if widget.__class__.__name__ == "PresetPreviewSwatch"
        ]
        assert swatches
        assert inspector.height() >= inspector.minimumSizeHint().height()
        assert swatch_slot.height() >= swatches[0].height()
    finally:
        win.close()
        win.deleteLater()
        app.processEvents()
