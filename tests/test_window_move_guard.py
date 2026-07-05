from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_timeline_tool_button_animation_suspends_for_window_move():
    from app.video_editor_window import _AnimatedTimelineToolButton

    app = _app()
    btn = _AnimatedTimelineToolButton("select", "cursor")
    btn.setCheckable(True)
    try:
        btn.setChecked(True)
        app.processEvents()
        assert btn._anim_timer.isActive()

        btn.set_animation_suspended(True)

        assert not btn._anim_timer.isActive()

        btn.set_animation_suspended(False)

        assert btn._anim_timer.isActive()
    finally:
        btn.deleteLater()
        app.processEvents()


def test_preset_tile_hover_timers_suspend_for_window_move():
    from app.video_editor_window import _StudioPresetTile

    app = _app()
    tile = _StudioPresetTile(
        "Soft Pop",
        "FX",
        palette_seed="soft-pop",
        tooltip="Soft Pop",
        preview_kind="effect",
        preview_payload={"video_filters": {"brightness": 8}},
    )
    try:
        tile._hovered = True
        tile._anim_timer.start()
        tile._preview_timer.start()
        tile._live_preview_timer.start()

        tile.set_window_move_suspended(True)

        assert not tile._anim_timer.isActive()
        assert not tile._preview_timer.isActive()
        assert not tile._live_preview_timer.isActive()

        tile.set_window_move_suspended(False)

        assert tile._anim_timer.isActive()
    finally:
        tile.deleteLater()
        app.processEvents()


def test_preset_preview_swatch_timer_suspends_for_window_move():
    from app.video_editor_window import _PresetPreviewSwatch

    app = _app()
    swatch = _PresetPreviewSwatch(("#FF7B5C", "#8A7CFF", "#63D7FF"), label="Demo")
    try:
        swatch.show()
        app.processEvents()
        assert swatch._timer.isActive()

        swatch.set_window_move_suspended(True)

        assert not swatch._timer.isActive()

        swatch.set_window_move_suspended(False)

        assert swatch._timer.isActive()
    finally:
        swatch.close()
        swatch.deleteLater()
        app.processEvents()


def test_window_move_guard_qa_report_passes():
    from tools.qa_window_move_guard import run_window_move_guard_qa

    report = run_window_move_guard_qa()

    assert report["ok"], report["failures"]
    assert report["summary"]["checks"] >= 8
    assert report["checks"]["video_editor_guard_suspends_surfaces"]
