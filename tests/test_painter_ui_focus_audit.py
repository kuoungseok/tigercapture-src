from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_focus_audit_reports_tab_label_and_ring_coverage() -> None:
    _app()
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLineEdit, QPushButton, QVBoxLayout, QWidget

    from app.painter_ui_focus_audit import inspect_painter_ui_focus

    root = QWidget()
    layout = QVBoxLayout(root)
    save = QPushButton("Save")
    search = QLineEdit()
    search.setPlaceholderText("Search")
    blocked = QPushButton("")
    blocked.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    layout.addWidget(save)
    layout.addWidget(search)
    layout.addWidget(blocked)
    root.show()
    _app().processEvents()
    report = inspect_painter_ui_focus(root)
    assert report["control_count"] == 3
    assert report["focus_ring_count"] == 3
    assert report["issue_count"] == 1
    assert report["issues"][0]["issue_codes"] == [
        "not_in_tab_order",
        "missing_accessible_label",
    ]


def test_focus_audit_dialog_has_compact_columns() -> None:
    _app()
    from app.painter_ui_focus_audit_dialog import PainterUIFocusAuditDialog

    dialog = PainterUIFocusAuditDialog()
    dialog.set_report(
        {
            "control_count": 2,
            "tab_focus_count": 2,
            "focus_ring_count": 2,
            "issue_count": 0,
            "controls": [
                {
                    "id": "save",
                    "kind": "QPushButton",
                    "label": "Save",
                    "tab_focus": True,
                    "focus_ring": True,
                    "status": "covered",
                    "issue_codes": [],
                }
            ],
        }
    )
    assert dialog.tree.topLevelItemCount() == 1
    dialog.resize(420, 480)
    dialog.show()
    _app().processEvents()
    assert dialog.tree.isColumnHidden(1) is True
    assert dialog.tree.isColumnHidden(3) is True


def test_focus_audit_action_is_registered_read_only() -> None:
    from app.actions.registry import ActionRegistry

    row = next(
        item
        for item in ActionRegistry(owner=None).list_actions()
        if item["id"] == "paint.ui.focus_audit.inspect"
    )
    assert row["mutating"] is False


def test_visible_ui_design_surface_has_complete_focus_contract() -> None:
    _app()
    from PySide6.QtWidgets import QAbstractButton

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_focus_audit import inspect_painter_ui_focus

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(
            900,
            600,
            "transparent",
        ),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1360, 900)
    dialog.show()
    dialog._set_canvas_workspace_mode("ui_design")
    _app().processEvents()
    report = inspect_painter_ui_focus(dialog)
    assert report["status"] == "covered", [
        (row["id"], row["kind"], row["issue_codes"])
        for row in report["issues"]
    ]
    assert report["control_count"] >= 20
    assert report["tab_focus_count"] == report["control_count"]
    assert report["labelled_count"] == report["control_count"]
    quick_actions = next(
        button
        for button in dialog.findChildren(QAbstractButton)
        if "Quick Actions" in button.toolTip()
    )
    quick_actions.setFocus()
    _app().processEvents()
    assert quick_actions.hasFocus() is True
    assert (
        'canvasWorkspaceMode="ui_design"] QPushButton:focus'
        in dialog.styleSheet()
    )
