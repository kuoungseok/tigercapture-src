from __future__ import annotations

import copy
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _responsive_document() -> dict:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_responsive import set_ui_responsive_override

    document = create_ui_document(1440, 900, name="Responsive Card")
    document, card = add_ui_object(
        document,
        kind="frame",
        name="Card",
        x=40,
        y=40,
        width=520,
        height=240,
    )
    overrides = set_ui_responsive_override(
        card,
        breakpoint="mobile",
        orientation="portrait",
        changes={"width": 320, "height": 420},
    )
    for row in document["objects"]:
        if row["id"] == card["id"]:
            row["responsive_overrides"] = overrides
    return document


def test_responsive_preview_matrix_is_six_contexts_and_non_destructive() -> None:
    from app.painter_ui_responsive_preview import (
        build_ui_responsive_preview_matrix,
    )
    from app.painter_ui_themes import resolve_ui_theme_document

    document = _responsive_document()
    original = copy.deepcopy(document)
    previews, report = build_ui_responsive_preview_matrix(document)

    assert document == original
    assert report["preview_only"] is True
    assert report["context_count"] == 6
    assert len(previews) == 6
    assert {row["breakpoint"] for row in report["contexts"]} == {
        "desktop",
        "tablet",
        "mobile",
    }
    assert {row["orientation"] for row in report["contexts"]} == {
        "portrait",
        "landscape",
    }
    for preview, context in zip(previews, report["contexts"]):
        artboard = preview["artboards"][0]
        assert preview["revision"] == document["revision"]
        assert preview["selection"]["object_ids"] == []
        assert artboard["breakpoint"] == context["breakpoint"]
        assert artboard["orientation"] == context["orientation"]
        assert artboard["width"] == context["width"]
        assert artboard["height"] == context["height"]

    mobile = resolve_ui_theme_document(previews[4])
    desktop = resolve_ui_theme_document(previews[1])
    assert mobile["objects"][0]["width"] == 320.0
    assert mobile["objects"][0]["height"] == 420.0
    assert desktop["objects"][0]["width"] == 520.0
    assert desktop["objects"][0]["height"] == 240.0


def test_responsive_preview_panel_and_inspector_button_are_transient() -> None:
    app = _app()
    from app.painter_ui_inspector import PainterUIInspector
    from app.painter_ui_responsive_preview_panel import (
        PainterUIResponsivePreviewPanel,
    )

    document = _responsive_document()
    panel = PainterUIResponsivePreviewPanel()
    panel.set_document(document)
    panel.show()
    app.processEvents()
    assert len(panel.cards) == 6
    assert panel.report()["canonical_revision"] == document["revision"]
    assert all(card.preview._document["selection"]["object_ids"] == [] for card in panel.cards)

    inspector = PainterUIInspector()
    requests: list[bool] = []
    inspector.responsive_preview_requested.connect(lambda: requests.append(True))
    inspector.set_document(document)
    inspector.responsive_preview_button.click()
    assert requests == [True]

    panel.close()
    panel.deleteLater()
    inspector.deleteLater()
    app.processEvents()


def test_responsive_preview_action_is_read_only() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(1440, 900, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = _responsive_document()
    before = copy.deepcopy(dialog._painter_ui_document)
    undo_count = len(dialog._undo_stack)
    result = ActionRegistry(owner=dialog).execute(
        "paint.ui.responsive.preview_matrix.inspect",
        {},
    ).to_dict()

    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["context_count"] == 6
    assert dialog._painter_ui_document == before
    assert len(dialog._undo_stack) == undo_count
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
