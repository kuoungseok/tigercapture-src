from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_inspector_dock_window_preserves_the_canonical_widget() -> None:
    app = _app()
    from PySide6.QtWidgets import QWidget

    from app.painter_ui_inspector_dock import PainterUIInspectorDockWindow

    window = PainterUIInspectorDockWindow()
    content = QWidget()
    requested: list[bool] = []
    window.dock_requested.connect(lambda: requested.append(True))

    window.attach(content)
    assert window.scroll_area.widget() is content
    assert content.parent() is window.scroll_area.viewport()
    assert window.take() is content
    assert content.parent() is None

    window.attach(content)
    window.show()
    app.processEvents()
    window.close()
    app.processEvents()
    assert requested == [True]
    assert window.isVisible()

    window.hide()
    content.deleteLater()
    window.deleteLater()


def test_ui_inspector_resizes_detaches_and_restores_on_mode_change() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#F5F7FA"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1500, 900)
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.show()
    app.processEvents()

    assert dialog._paint_ui_inspector.is_auto_hide()
    assert dialog._paint_ui_inspector.is_collapsed()
    assert dialog._paint_inspector_frame.maximumWidth() == 36
    dialog._paint_ui_inspector.set_auto_hide(False)
    assert not dialog._paint_ui_inspector.is_collapsed()
    assert dialog._paint_ui_inspector.dock_button.isVisible()
    assert (
        dialog._set_painter_ui_inspector_width(
            340,
            user_initiated=True,
        )
        == 340
    )
    assert dialog._paint_inspector_frame.minimumWidth() == 340
    assert dialog._paint_inspector_frame.maximumWidth() == 340

    dialog._paint_ui_inspector.set_auto_hide(True)
    assert dialog._paint_inspector_frame.maximumWidth() == 36
    assert not dialog._paint_ui_inspector.dock_button.isVisible()
    dialog._paint_ui_inspector.set_auto_hide(False)
    assert dialog._paint_inspector_frame.minimumWidth() == 340

    dialog._detach_painter_ui_inspector()
    app.processEvents()
    window = dialog._painter_ui_inspector_dock_window
    assert dialog._painter_ui_inspector_detached is True
    assert (
        dialog._paint_ui_inspector.parent()
        is window.scroll_area.viewport()
    )
    assert window.isVisible()
    assert not dialog._paint_inspector_frame.isVisible()
    from app.i18n import current_language
    from app.painter_i18n import painter_text

    assert dialog._paint_ui_inspector.dock_button.toolTip() == painter_text(
        "Dock inspector",
        current_language(),
    )

    dialog._dock_painter_ui_inspector()
    app.processEvents()
    assert dialog._painter_ui_inspector_detached is False
    assert dialog._paint_ui_inspector.parent() is dialog._paint_inspector_controls
    assert dialog._paint_inspector_frame.isVisible()
    assert dialog._paint_inspector_frame.minimumWidth() == 340

    dialog._detach_painter_ui_inspector()
    dialog._set_canvas_workspace_mode("paint")
    app.processEvents()
    assert dialog._painter_ui_inspector_detached is False
    assert not window.isVisible()
    assert dialog._paint_inspector_frame.isVisible()

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_ui_inspector_presentation_action_switches_all_three_modes() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#F5F7FA"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1400, 900)
    registry = ActionRegistry(owner=dialog)

    auto = registry.execute(
        "paint.ui.inspector.presentation",
        {"mode": "auto_hide"},
    )
    assert auto.ok
    assert auto.result["inspector_presentation"] == {
        "mode": "auto_hide",
        "auto_hide": True,
        "detached": False,
    }
    assert dialog._paint_inspector_frame.maximumWidth() == 36

    pinned = registry.execute(
        "paint.ui.inspector.presentation",
        {"mode": "pinned"},
    )
    assert pinned.ok
    assert pinned.result["inspector_presentation"]["mode"] == "pinned"
    assert not dialog._paint_ui_inspector.is_collapsed()

    floating = registry.execute(
        "paint.ui.inspector.presentation",
        {"mode": "floating"},
    )
    app.processEvents()
    assert floating.ok
    assert floating.result["inspector_presentation"] == {
        "mode": "floating",
        "auto_hide": False,
        "detached": True,
    }
    assert dialog._painter_ui_inspector_dock_window.isVisible()

    dialog._dock_painter_ui_inspector()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
