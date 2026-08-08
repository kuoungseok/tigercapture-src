from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_comment_toolbar_uses_dedicated_comment_mode() -> None:
    _app()
    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    toolbar = PainterUIFloatingToolbar()
    tools: list[str] = []
    quick: list[bool] = []
    toolbar.tool_requested.connect(tools.append)
    toolbar.quick_actions_requested.connect(lambda: quick.append(True))

    toolbar.comment_button.click()

    assert tools == ["comment"]
    assert quick == []
    assert toolbar.tool_buttons["comment"].isChecked()


def test_actions_button_opens_quick_actions_without_navigator() -> None:
    _app()
    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    toolbar = PainterUIFloatingToolbar()
    quick: list[bool] = []
    navigator: list[bool] = []
    toolbar.quick_actions_requested.connect(lambda: quick.append(True))
    toolbar.navigator_requested.connect(lambda: navigator.append(True))

    toolbar.resources_button.click()

    assert quick == [True]
    assert navigator == []
    assert toolbar.resources_button.accessibleName() == "Actions (Ctrl+/)"


def test_comment_pin_is_object_anchored_and_moves_with_object() -> None:
    _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_review import add_ui_review_comment
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, row = add_ui_object(
        create_ui_document(), kind="rectangle", x=40, y=50, width=120, height=80
    )
    document, comment = add_ui_review_comment(
        document, text="Anchor", object_id=row["id"], x=0.5, y=0.5
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 700)
    overlay.set_document(document)
    overlay.fit_artboard()
    before = overlay._comment_position(comment)

    moved = dict(document)
    moved["objects"] = [dict(item) for item in document["objects"]]
    moved["objects"][0]["x"] += 60
    overlay.set_document(moved)
    after = overlay._comment_position(comment)

    assert before is not None and after is not None
    assert after.x() > before.x()
    assert after.y() == before.y()


def test_comments_panel_replies_resolves_and_deletes() -> None:
    _app()
    from app.painter_ui_comments import PainterUICommentsPanel
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_review import add_ui_review_comment

    document, comment = add_ui_review_comment(create_ui_document(), text="Check spacing")
    panel = PainterUICommentsPanel()
    updates: list[tuple[str, object]] = []
    deletes: list[str] = []
    panel.comment_update_requested.connect(lambda key, value: updates.append((key, value)))
    panel.comment_remove_requested.connect(deletes.append)
    panel.set_document(document)
    panel.select_comment(comment["id"])
    panel.reply.setText("Fixed")
    panel._send_reply()
    panel._toggle_resolved()
    panel._delete()

    assert updates == [
        (comment["id"], {"reply": "Fixed", "author": "Reviewer"}),
        (comment["id"], {"resolved": True}),
    ]
    assert deletes == [comment["id"]]


def test_comment_region_and_pin_move_are_persisted() -> None:
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_review import add_ui_review_comment, update_ui_review_comment

    document, comment = add_ui_review_comment(
        create_ui_document(),
        text="Region",
        x=0.2,
        y=0.3,
        region={"x": 0.2, "y": 0.3, "width": 0.4, "height": 0.25},
    )
    assert comment["region"] == {
        "x": 0.2,
        "y": 0.3,
        "width": 0.4,
        "height": 0.25,
    }

    _document, moved = update_ui_review_comment(
        document,
        comment["id"],
        {"anchor": {"x": 0.8, "y": 0.7}, "region": None},
    )
    assert moved["anchor"] == {"x": 0.8, "y": 0.7}
    assert "region" not in moved


def test_quick_actions_include_comment_templates_assets_and_components() -> None:
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_quick_actions import search_painter_ui_quick_actions

    document = create_ui_document()
    document["components"] = [{"id": "component-1", "name": "Button"}]
    report = search_painter_ui_quick_actions(document, "", limit=100)
    ids = {row["id"] for row in report["results"]}

    assert "tool.comment" in ids
    assert "document.templates" in ids
    assert "document.assets" in ids
    assert "component.component-1" in ids
