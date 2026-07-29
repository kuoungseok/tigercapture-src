from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_shortcut_map_keeps_mutually_exclusive_modes_out_of_conflicts() -> None:
    from app.painter_ui_shortcut_map import inspect_painter_shortcuts

    report = inspect_painter_shortcuts(
        [
            {
                "id": "ui.duplicate",
                "label": "Duplicate",
                "shortcut": "Ctrl+D",
                "scope": "ui_design",
            },
            {
                "id": "paint.deselect",
                "label": "Deselect",
                "shortcut": "Ctrl+D",
                "scope": "paint",
            },
        ]
    )
    assert report["conflict_count"] == 0
    assert report["rows"][0]["active"] is True
    assert report["rows"][1]["active"] is False


def test_shortcut_map_reports_overlapping_global_conflicts() -> None:
    from app.painter_ui_shortcut_map import inspect_painter_shortcuts

    report = inspect_painter_shortcuts(
        [
            {
                "id": "global.find",
                "label": "Find",
                "shortcut": "Ctrl+F",
                "scope": "global",
            },
            {
                "id": "ui.find",
                "label": "UI Find",
                "shortcut": "Ctrl+F",
                "scope": "ui_design",
            },
        ],
        conflicts_only=True,
    )
    assert report["conflict_count"] == 2
    assert report["conflict_pair_count"] == 1
    assert [row["id"] for row in report["rows"]] == [
        "global.find",
        "ui.find",
    ]


def test_shortcut_map_searches_labels_keys_scopes_and_sources() -> None:
    from app.painter_ui_shortcut_map import inspect_painter_shortcuts

    report = inspect_painter_shortcuts(query="ctrl+d")
    assert {row["id"] for row in report["rows"]} == {
        "ui.duplicate",
        "paint.deselect",
    }
    assert inspect_painter_shortcuts(query="3d")["visible_count"] == 1


def test_shortcut_inspect_action_is_read_only() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_document_dirty = False
    undo_count = len(dialog._undo_stack)
    result = ActionRegistry(owner=dialog).execute(
        "paint.ui.shortcut.inspect",
        {"query": "Ctrl+D"},
    ).to_dict()
    assert result["ok"] is True
    assert result["result"]["visible_count"] == 2
    assert dialog._painter_document_dirty is False
    assert len(dialog._undo_stack) == undo_count
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_ui_mode_disables_paint_only_qshortcuts() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._set_canvas_workspace_mode("ui_design")
    assert all(not shortcut.isEnabled() for shortcut in dialog._paint_shortcuts)
    assert all(
        not shortcut.isEnabled()
        for shortcut in dialog._painter_tool_shortcuts
    )
    dialog._set_canvas_workspace_mode("paint")
    assert all(shortcut.isEnabled() for shortcut in dialog._paint_shortcuts)
    assert all(
        shortcut.isEnabled()
        for shortcut in dialog._painter_tool_shortcuts
    )
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_quick_actions_exposes_shortcut_map() -> None:
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_quick_actions import search_painter_ui_quick_actions

    report = search_painter_ui_quick_actions(
        create_ui_document(390, 844),
        "keyboard shortcut",
    )
    row = next(
        item
        for item in report["results"]
        if item["id"] == "document.shortcut_map"
    )
    assert row["enabled"] is True
    assert row["operation"] == {"type": "shortcut_map"}
