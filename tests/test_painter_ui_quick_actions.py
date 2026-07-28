from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document():
    from app.painter_ui_document import (
        add_ui_artboard,
        add_ui_component,
        add_ui_object,
        add_ui_token,
        create_ui_document,
        set_active_ui_artboard,
    )

    document = create_ui_document(800, 600, name="Desktop")
    desktop_id = document["active_artboard_id"]
    document, hero = add_ui_object(
        document,
        kind="rectangle",
        name="Hero Card",
        x=80,
        y=100,
        width=320,
        height=180,
    )
    document, component = add_ui_component(
        document,
        name="Primary Button",
        root_object_id=hero["id"],
    )
    document, token = add_ui_token(
        document,
        name="Brand Accent",
        kind="color",
        token_value="#4F7DFF",
    )
    document, mobile = add_ui_artboard(
        document,
        name="Mobile Checkout",
        width=390,
        height=844,
    )
    document = set_active_ui_artboard(document, desktop_id)
    return document, hero, component, token, mobile


def _result(report: dict, result_id: str) -> dict:
    return next(row for row in report["results"] if row["id"] == result_id)


def test_quick_action_search_combines_commands_and_document_assets() -> None:
    from app.painter_ui_quick_actions import search_painter_ui_quick_actions

    document, hero, component, token, mobile = _document()

    assert _result(
        search_painter_ui_quick_actions(document, "Hero"),
        f"layer.{hero['id']}",
    )["operation"]["type"] == "select_object"
    assert _result(
        search_painter_ui_quick_actions(document, "Checkout"),
        f"page.{mobile['id']}",
    )["operation"]["type"] == "activate_artboard"
    assert _result(
        search_painter_ui_quick_actions(document, "Primary Button"),
        f"component.{component['id']}",
    )["operation"]["type"] == "instantiate_component"
    assert _result(
        search_painter_ui_quick_actions(document, "Brand Accent"),
        f"token.{token['id']}",
    )["operation"]["type"] == "reveal_token"


def test_quick_action_context_disables_invalid_selection_commands() -> None:
    from app.painter_ui_document import select_ui_objects
    from app.painter_ui_quick_actions import search_painter_ui_quick_actions

    document, hero, _component, _token, _mobile = _document()
    document = select_ui_objects(document, [])
    report = search_painter_ui_quick_actions(document, "scale")
    assert _result(report, "selection.scale")["enabled"] is False

    document = select_ui_objects(
        document,
        [hero["id"]],
        primary_object_id=hero["id"],
    )
    report = search_painter_ui_quick_actions(document, "scale")
    assert _result(report, "selection.scale")["enabled"] is True


def test_quick_action_popover_is_transient_and_compact() -> None:
    app = _app()
    from PySide6.QtWidgets import QWidget

    from app.painter_ui_quick_action_popover import (
        PainterUIQuickActionPopover,
    )

    document, hero, _component, _token, _mobile = _document()
    host = QWidget()
    host.resize(390, 300)
    popover = PainterUIQuickActionPopover(host)
    requested: list[dict] = []
    popover.action_requested.connect(requested.append)

    host.show()
    popover.open_for_document(document, query="Hero")
    app.processEvents()

    assert popover.isVisible()
    assert popover.width() <= host.width() - 16
    assert popover.height() <= host.height() - 32
    assert popover.result_list.count() == 1
    item = popover.result_list.item(0)
    assert item.data(0x0100)["id"] == f"layer.{hero['id']}"

    popover._request_item(item)
    assert not popover.isVisible()
    assert requested[0]["operation"]["object_id"] == hero["id"]

    host.close()
    host.deleteLater()
    app.processEvents()


def test_quick_action_action_uses_the_shared_search_catalog() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, hero, _component, _token, _mobile = _document()
    dialog._painter_ui_document = document
    registry = ActionRegistry(owner=dialog)

    result = registry.execute(
        "paint.ui.quick_action.search",
        {"query": "Hero", "limit": 10},
    ).to_dict()

    assert result["ok"] is True
    assert result["result"]["schema"].endswith("quick_actions.v1")
    assert result["result"]["results"][0]["id"] == f"layer.{hero['id']}"
    assert dialog._painter_ui_document == document

    dialog.close()
    dialog.deleteLater()
    app.processEvents()
