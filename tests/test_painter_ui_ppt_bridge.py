from __future__ import annotations

import os
from pathlib import Path


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(390, 844, name="Mobile UI")
    document, _card = add_ui_object(
        document,
        kind="rectangle",
        name="Card",
        x=24,
        y=80,
        width=342,
        height=220,
        style={"fill": "#EAF1FF", "radius": 12},
    )
    document, _heading = add_ui_object(
        document,
        kind="text",
        name="Heading",
        x=40,
        y=104,
        width=280,
        height=48,
        content={"text": "Painter to PPT"},
        style={
            "text_color": "#182033",
            "font_size": 28,
            "font_weight": 700,
        },
    )
    document, _ellipse = add_ui_object(
        document,
        kind="ellipse",
        name="Avatar",
        x=40,
        y=176,
        width=80,
        height=80,
        style={"fill": "#4F7CEC"},
    )
    return document


def test_ppt_preflight_distinguishes_native_and_baked() -> None:
    from app.painter_ui_ppt_bridge import (
        PPT_PREFLIGHT_SCHEMA,
        inspect_painter_ui_ppt,
    )

    report = inspect_painter_ui_ppt(_document())

    assert report["schema"] == PPT_PREFLIGHT_SCHEMA
    assert report["ok"] is True
    assert report["slide_count"] == 1
    assert report["counts"] == {"Native": 2, "Baked": 1, "Blocked": 0}


def test_painter_ui_builds_editable_deck_and_real_pptx(
    tmp_path: Path,
) -> None:
    from app.painter_ui_ppt_bridge import (
        PPT_BRIDGE_SCHEMA,
        painter_ui_to_ppt_deck,
    )
    from app.pptgen.writer_ooxml import write_pptx

    deck, report = painter_ui_to_ppt_deck(
        _document(),
        asset_dir=tmp_path / "assets",
        title="UI Presentation",
    )

    assert report["schema"] == PPT_BRIDGE_SCHEMA
    assert report["ok"] is True
    assert report["slide_count"] == 1
    assert report["element_count"] == 3
    assert len(report["baked_assets"]) == 1
    assert Path(report["baked_assets"][0]).is_file()
    assert {row.kind for row in deck.slides[0].elements} == {
        "shape",
        "text",
        "image",
    }
    for element in deck.slides[0].elements:
        assert element.metadata["painter_ui_object_id"] == element.id
        assert 0.0 <= element.x <= 1.0
        assert 0.0 <= element.y <= 1.0
    output = write_pptx(deck, tmp_path / "painter-ui.pptx")
    assert output.is_file()
    assert output.stat().st_size > 1000


def test_ppt_panel_requests_scope_without_mutating_document() -> None:
    _app()
    from app.painter_ui_production_panel import PainterUIProductionPanel

    panel = PainterUIProductionPanel()
    preflight: list[str] = []
    sent: list[str] = []
    panel.ppt_preflight_requested.connect(preflight.append)
    panel.ppt_send_requested.connect(sent.append)

    panel.ppt_scope_combo.setCurrentIndex(
        panel.ppt_scope_combo.findData("all_artboards")
    )
    panel.ppt_preflight_button.click()
    panel.ppt_send_button.click()

    assert preflight == ["all_artboards"]
    assert sent == ["all_artboards"]
    panel.close()


def test_ppt_actions_use_shared_bridge(tmp_path: Path, monkeypatch) -> None:
    _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_ppt_bridge import painter_ui_to_ppt_deck

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = _document()
    before_revision = dialog._painter_ui_document["revision"]
    calls: list[str] = []

    def fake_send(*, scope="active_artboard"):
        _deck, report = painter_ui_to_ppt_deck(
            dialog._painter_ui_document,
            scope=scope,
            asset_dir=tmp_path / "action-assets",
        )
        calls.append(scope)
        return {**report, "opened": True}

    monkeypatch.setattr(dialog, "_send_painter_ui_to_ppt", fake_send)
    registry = ActionRegistry(owner=dialog)
    action_ids = {row["id"] for row in registry.list_actions()}
    assert {"paint.ui.ppt.inspect", "paint.ui.ppt.send"}.issubset(action_ids)

    inspected = registry.execute(
        "paint.ui.ppt.inspect",
        {"scope": "active_artboard"},
    ).to_dict()
    sent = registry.execute(
        "paint.ui.ppt.send",
        {"scope": "active_artboard"},
    ).to_dict()

    assert inspected["ok"] is True and inspected["changed"] is False
    assert sent["ok"] is True and sent["changed"] is False
    assert calls == ["active_artboard"]
    assert dialog._painter_ui_document["revision"] == before_revision
    dialog.close()
