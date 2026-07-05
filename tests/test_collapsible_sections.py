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
    win.show()
    app.processEvents()

    sections = [
        ("_effects_library_section_host", "_effects_preset_panel"),
        ("_title_presets_section_host", "_title_presets_panel"),
        ("_transitions_section_host", "_transitions_panel"),
        ("_workflow_presets_section_host", "_workflow_presets_panel"),
        ("_render_queue_section_host", "_render_queue_panel"),
        ("_audio_workspace_section_host", "_audio_workspace_label"),
    ]
    try:
        for host_attr, controlled_attr in sections:
            host = getattr(win, host_attr)
            controlled = getattr(win, controlled_attr)
            toggle = host.findChild(QPushButton, "SectionDisclosure")
            assert toggle is not None

            if not controlled.isVisible():
                toggle.click()
                app.processEvents()
            assert host.isVisible()
            assert controlled.isVisible()
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
