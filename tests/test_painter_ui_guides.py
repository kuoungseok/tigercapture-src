from __future__ import annotations

import os
import json


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_guide_mutations_preserve_lock_visibility_and_ruler_origin() -> None:
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_guides import (
        add_ui_guide,
        reset_ui_ruler_origin,
        set_ui_guides_locked,
        set_ui_guides_visibility,
        set_ui_ruler_origin,
        update_ui_guide,
    )

    document = create_ui_document(800, 600)
    document = add_ui_guide(
        document,
        orientation="vertical",
        position=100,
    )
    document = update_ui_guide(
        document,
        orientation="vertical",
        position=100,
        next_position=144,
    )
    document = set_ui_guides_locked(document, locked=True)
    document = set_ui_guides_visibility(document, visible=False)
    document = set_ui_ruler_origin(document, x=24, y=32)

    guides = document["artboards"][0]["guides"]
    assert guides["vertical"] == [144.0]
    assert guides["locked"] is True
    assert guides["visible"] is False
    assert guides["origin"] == {"x": 24.0, "y": 32.0}

    reset = reset_ui_ruler_origin(document)
    assert reset["artboards"][0]["guides"]["origin"] == {
        "x": 0.0,
        "y": 0.0,
    }
    from app.painter_ui_document import normalize_ui_document

    round_trip = normalize_ui_document(json.loads(json.dumps(document)))
    assert round_trip["artboards"][0]["guides"] == guides


def test_overlay_drags_existing_guide_and_returns_it_to_ruler() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import create_ui_document
    from app.painter_ui_guides import add_ui_guide
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document = add_ui_guide(
        create_ui_document(800, 600),
        orientation="vertical",
        position=100,
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 700)
    overlay.set_document(document)
    overlay.fit_artboard()
    overlay.show()
    app.processEvents()
    viewport, scale = overlay._artboard_viewport()
    start = QPoint(
        round(viewport.left() + 100 * scale),
        round(viewport.center().y()),
    )
    moved: list[tuple[str, float, float]] = []
    removed: list[tuple[str, float]] = []
    overlay.guide_update_requested.connect(
        lambda orientation, old, new: moved.append(
            (orientation, old, new)
        )
    )
    overlay.guide_remove_requested.connect(
        lambda orientation, position: removed.append(
            (orientation, position)
        )
    )

    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(overlay, QPoint(start.x() + 40, start.y()))
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=QPoint(start.x() + 40, start.y()),
    )
    assert moved
    assert moved[0][0] == "vertical"
    assert moved[0][1] == 100.0
    assert abs(moved[0][2] - (100.0 + 40.0 / scale)) < 1.0

    overlay.set_document(document)
    viewport, scale = overlay._artboard_viewport()
    start = QPoint(
        round(viewport.left() + 100 * scale),
        round(viewport.center().y()),
    )
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(overlay, QPoint(8, start.y()))
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=QPoint(8, start.y()),
    )
    assert removed == [("vertical", 100.0)]
    overlay.deleteLater()
    app.processEvents()


def test_overlay_ruler_corner_drags_origin_and_double_click_resets() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 700)
    overlay.set_document(create_ui_document(800, 600))
    overlay.fit_artboard()
    overlay.show()
    app.processEvents()
    origins: list[tuple[float, float]] = []
    resets: list[bool] = []
    overlay.ruler_origin_requested.connect(
        lambda x, y: origins.append((x, y))
    )
    overlay.ruler_origin_reset_requested.connect(lambda: resets.append(True))

    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=QPoint(8, 8),
    )
    QTest.mouseMove(overlay, QPoint(220, 180))
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=QPoint(220, 180),
    )
    assert len(origins) == 1
    viewport, scale = overlay._artboard_viewport()
    assert abs(origins[0][0] - (220 - viewport.left()) / scale) < 0.01
    assert abs(origins[0][1] - (180 - viewport.top()) / scale) < 0.01

    QTest.mouseDClick(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=QPoint(8, 8),
    )
    assert resets == [True]
    overlay.deleteLater()
    app.processEvents()


def test_guide_actions_share_document_mutations_and_undo() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    created = registry.execute(
        "paint.ui.guide.create",
        {"orientation": "horizontal", "position": 120},
    ).to_dict()
    assert created["ok"]
    moved = registry.execute(
        "paint.ui.guide.update",
        {
            "orientation": "horizontal",
            "position": 120,
            "next_position": 180,
        },
    ).to_dict()
    assert moved["ok"]
    locked = registry.execute(
        "paint.ui.guide.lock.set",
        {"locked": True},
    ).to_dict()
    assert locked["ok"]
    hidden = registry.execute(
        "paint.ui.guide.visibility.set",
        {"visible": False},
    ).to_dict()
    assert hidden["ok"]
    origin = registry.execute(
        "paint.ui.ruler.origin.set",
        {"x": 16, "y": 24},
    ).to_dict()
    assert origin["ok"]

    guides = origin["result"]["ui_design"]["document"]["artboards"][0][
        "guides"
    ]
    assert guides["horizontal"] == [180.0]
    assert guides["locked"] is True
    assert guides["visible"] is False
    assert guides["origin"] == {"x": 16.0, "y": 24.0}
    dialog._undo()
    assert dialog._painter_ui_document["artboards"][0]["guides"]["origin"] == {
        "x": 0.0,
        "y": 0.0,
    }
    dialog.deleteLater()
    app.processEvents()
