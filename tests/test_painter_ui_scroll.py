from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _scroll_document(*, overflow: str = "vertical", clip: bool = True):
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )

    document = create_ui_document(800, 600)
    document, frame = add_ui_object(
        document,
        kind="frame",
        name="Scrollable",
        x=100,
        y=80,
        width=240,
        height=180,
    )
    document, frame = update_ui_object(
        document,
        frame["id"],
        {
            "clip_content": clip,
            "scroll": {"overflow": overflow},
        },
    )
    document, child = add_ui_object(
        document,
        kind="rectangle",
        name="Overflow child",
        parent_id=frame["id"],
        x=120,
        y=220,
        width=120,
        height=100,
    )
    return document, frame, child


def test_scroll_contract_normalizes_and_round_trips_document_schema() -> None:
    from app.painter_ui_document import UI_DOCUMENT_VERSION, normalize_ui_document

    document, frame, _child = _scroll_document(overflow="both")
    normalized = normalize_ui_document(document)
    row = next(row for row in normalized["objects"] if row["id"] == frame["id"])

    assert UI_DOCUMENT_VERSION == 31
    assert row["scroll"] == {
        "overflow": "both",
        "position": "scroll",
        "preserve_position": True,
    }


def test_scroll_diagnostics_enforce_clip_and_real_overflow_content() -> None:
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_layout_diagnostics import diagnose_ui_layout

    document, frame, child = _scroll_document(clip=True)
    for row in document["objects"]:
        if row["id"] == frame["id"]:
            row["clip_content"] = False
    report = diagnose_ui_layout(document)
    assert f"scroll_overflow_requires_clip_content:{frame['id']}" in report["errors"]

    for row in document["objects"]:
        if row["id"] == frame["id"]:
            row["clip_content"] = True
    document, _ = update_ui_object(document, child["id"], {"y": 100})
    report = diagnose_ui_layout(document)
    assert any(
        row["code"] == "scroll_overflow_has_no_overflow_content"
        and row["owner_id"] == frame["id"]
        for row in report["diagnostics"]
    )


def test_fixed_and_sticky_require_the_figma_parent_contracts() -> None:
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_scroll import inspect_ui_scroll

    document, frame, child = _scroll_document(overflow="horizontal")
    document, _ = update_ui_object(
        document,
        frame["id"],
        {"layout": {"mode": "horizontal"}},
    )
    for row in document["objects"]:
        if row["id"] == child["id"]:
            row["scroll"] = {"position": "fixed"}
    report = inspect_ui_scroll(document, child["id"])
    assert "fixed_in_auto_layout_requires_ignore_auto_layout" in report["reasons"]

    for row in document["objects"]:
        if row["id"] == child["id"]:
            row["scroll"] = {"position": "sticky"}
            row["layout"] = {"positioning": "absolute"}
    report = inspect_ui_scroll(document, child["id"])
    assert "sticky_requires_vertical_overflow" in report["reasons"]


def test_inspector_exposes_overflow_for_frames_and_position_for_children() -> None:
    _app()
    from app.painter_ui_inspector import PainterUIInspector

    document, frame, child = _scroll_document()
    inspector = PainterUIInspector()
    inspector.set_document(document)

    document["selection"] = {"object_ids": [frame["id"]], "primary_id": frame["id"]}
    inspector.set_document(document)
    assert not inspector.scroll_overflow_combo.isHidden()

    document["selection"] = {"object_ids": [child["id"]], "primary_id": child["id"]}
    inspector.set_document(document)
    assert not inspector.scroll_position_combo.isHidden()
    assert inspector.scroll_position_combo.isEnabled()


def test_html_prototype_nests_scroll_content_and_emits_overflow_css(tmp_path) -> None:
    from app.painter_ui_prototype import export_ui_prototype

    document, frame, child = _scroll_document()
    report = export_ui_prototype(document, tmp_path)
    page = (tmp_path / "index.html").read_text(encoding="utf-8")

    assert report["ok"] is True
    frame_marker = f'id="{frame["id"]}"'
    child_marker = f'id="{child["id"]}"'
    assert page.index(frame_marker) < page.index(child_marker)
    assert "overflow:hidden auto" in page
    assert 'data-scroll-position="scroll"' in page


def test_umg_preflight_exports_native_scrollbox_contract() -> None:
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    document, frame, _child = _scroll_document()
    exported = painter_ui_to_umg_document(document)
    layer = next(row for row in exported["Layers"] if row["Id"] == frame["id"])
    assert layer["ScrollOverflow"] == "Vertical"
    assert layer["ScrollPosition"] == "Scroll"
    report = preflight_painter_umg(document)
    assert report["ok"] is True


def test_umg_fixed_child_uses_overlay_contract_but_sticky_stays_blocked() -> None:
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    document, _frame, child = _scroll_document()
    document, _ = update_ui_object(
        document,
        child["id"],
        {
            "layout": {"positioning": "absolute"},
            "scroll": {"position": "fixed"},
        },
    )
    exported = painter_ui_to_umg_document(document)
    layer = next(row for row in exported["Layers"] if row["Id"] == child["id"])
    assert layer["ScrollPosition"] == "Fixed"
    assert preflight_painter_umg(document)["ok"] is True

    for row in document["objects"]:
        if row["id"] == child["id"]:
            row["scroll"] = {"position": "sticky"}
    report = preflight_painter_umg(document)
    blocker = next(row for row in report["blockers"] if row["object_id"] == child["id"])
    assert "prototype_sticky_requires_umg_runtime_binding" in blocker["reasons"]
