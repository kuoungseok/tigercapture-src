from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document() -> tuple[dict, dict[str, str]]:
    from app.painter_ui_document import (
        add_ui_interaction,
        add_ui_object,
        add_ui_token,
        create_ui_document,
        select_ui_object,
        update_ui_object,
    )

    document = create_ui_document(800, 600)
    ids: dict[str, str] = {}
    for name, fill, x in (
        ("Primary", "#34506F", 20),
        ("Secondary", "#34506F", 220),
        ("Other", "#783B45", 420),
    ):
        document, row = add_ui_object(
            document,
            kind="button",
            name=name,
            x=x,
            y=40,
            width=160,
            height=48,
            style={
                "fill": fill,
                "stroke": "#90A0B4",
                "stroke_width": 1,
                "font_family": "Inter",
                "font_size": 16,
                "font_weight": 600,
                "text_color": "#FFFFFF",
                "shadow": {"x": 0, "y": 2, "blur": 8, "color": "#00000044"},
            },
            content={"text": name},
        )
        ids[name] = row["id"]
    document, token = add_ui_token(
        document,
        name="Action Fill",
        token_value="#34506F",
    )
    for name in ("Primary", "Secondary"):
        document, _row = update_ui_object(
            document,
            ids[name],
            {
                "variant": "default",
                "token_bindings": {"style.fill": token["id"]},
            },
        )
        document, _interaction = add_ui_interaction(
            document,
            source_object_id=ids[name],
            trigger="click",
            action="navigate",
        )
    document = select_ui_object(document, ids["Primary"])
    return document, ids


def test_select_similar_inspects_all_supported_meaningful_criteria() -> None:
    from app.painter_ui_select_similar import inspect_ui_select_similar

    document, ids = _document()
    expected_pair = {ids["Primary"], ids["Secondary"]}
    expected_all = {*expected_pair, ids["Other"]}
    for criterion, expected in (
        ("fill", expected_pair),
        ("stroke", expected_all),
        ("text_style", expected_all),
        ("variant", expected_pair),
        ("token", expected_pair),
        ("effect", expected_all),
        ("interaction", expected_pair),
    ):
        report = inspect_ui_select_similar(document, criterion=criterion)
        assert report["available"] is True
        assert set(report["match_object_ids"]) == expected
    kind_report = inspect_ui_select_similar(document, criterion="kind")
    assert kind_report["match_count"] == 3
    component_report = inspect_ui_select_similar(
        document,
        criterion="component",
    )
    assert component_report["available"] is False
    assert component_report["match_object_ids"] == []


def test_select_similar_changes_only_transient_selection() -> None:
    from app.painter_ui_select_similar import select_similar_ui_objects

    document, ids = _document()
    revision = document["revision"]
    updated, report = select_similar_ui_objects(document, criterion="fill")

    assert report["match_count"] == 2
    assert updated["revision"] == revision
    assert set(updated["selection"]["object_ids"]) == {
        ids["Primary"],
        ids["Secondary"],
    }
    assert updated["selection"]["object_id"] == ids["Primary"]


def test_select_similar_action_and_ui_share_the_same_selection_service() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, ids = _document()
    dialog._painter_ui_document = document
    dialog._painter_document_dirty = False
    undo_count = len(dialog._undo_stack)
    dialog._refresh_painter_ui_overlay()

    registry = ActionRegistry(owner=dialog)
    inspected = registry.execute(
        "paint.ui.selection.similar.inspect",
        {"criterion": "fill"},
    ).to_dict()
    assert inspected["ok"] is True
    assert inspected["result"]["match_count"] == 2

    selected = registry.execute(
        "paint.ui.selection.similar.select",
        {"criterion": "fill"},
    ).to_dict()
    assert selected["ok"] is True
    assert set(
        selected["result"]["select_similar"]["match_object_ids"]
    ) == {ids["Primary"], ids["Secondary"]}
    assert dialog._painter_document_dirty is False
    assert len(dialog._undo_stack) == undo_count

    dialog._set_painter_ui_selection([ids["Primary"]], ids["Primary"])
    dialog._refresh_painter_ui_select_similar_menu()
    assert set(dialog._painter_ui_select_similar_actions) == {
        "kind",
        "fill",
        "stroke",
        "text_style",
        "component",
        "variant",
        "token",
        "effect",
        "interaction",
    }
    assert dialog._painter_ui_select_similar_actions["fill"].isEnabled()
    assert "(2)" in dialog._painter_ui_select_similar_actions["fill"].text()
    assert not dialog._painter_ui_select_similar_actions[
        "component"
    ].isEnabled()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_quick_actions_discover_select_similar_without_fixed_canvas_chrome() -> None:
    from app.painter_ui_quick_actions import search_painter_ui_quick_actions

    document, _ids = _document()
    report = search_painter_ui_quick_actions(document, "select same")
    rows = {row["id"]: row for row in report["results"]}

    assert {
        "selection.same_kind",
        "selection.same_fill",
        "selection.same_component",
    }.issubset(rows)
    assert rows["selection.same_fill"]["operation"] == {
        "type": "select_similar",
        "criterion": "fill",
    }
