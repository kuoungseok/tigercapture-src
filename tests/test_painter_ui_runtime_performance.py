from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_runtime_measurement_classifier_has_warning_and_block_gates() -> None:
    from app.painter_ui_runtime_performance import (
        classify_runtime_measurement,
    )

    assert classify_runtime_measurement(9.9, 10.0, 20.0) == "covered"
    assert classify_runtime_measurement(10.0, 10.0, 20.0) == "warning"
    assert classify_runtime_measurement(20.0, 10.0, 20.0) == "blocked"


def test_runtime_performance_runs_real_core_paths() -> None:
    _app()
    from app.painter_ui_runtime_performance import (
        SCHEMA,
        run_painter_ui_runtime_performance,
    )

    report = run_painter_ui_runtime_performance(
        object_count=25,
        iterations=1,
    )
    assert report["schema"] == SCHEMA
    assert report["object_count"] == 25
    assert report["iterations"] == 1
    assert {row["id"] for row in report["cases"]} == {
        "normalize",
        "responsive",
        "layout_diagnostics",
        "quick_actions",
        "canvas_initial_load",
        "pan_zoom",
        "selection_refresh",
        "viewport_resize",
    }
    assert all(len(row["samples_ms"]) == 1 for row in report["cases"])
    assert report["measurement_policy"]["clock"] == "time.perf_counter"
    assert (
        report["measurement_policy"]["claim_scope"]
        == "local_machine_runtime_only"
    )


def test_runtime_performance_dialog_empty_and_compact_states() -> None:
    _app()
    from PySide6.QtWidgets import QPushButton

    from app.painter_i18n import painter_text
    from app.painter_ui_runtime_performance import (
        run_painter_ui_runtime_performance,
    )
    from app.painter_ui_runtime_performance_dialog import (
        PainterUIRuntimePerformanceDialog,
    )

    dialog = PainterUIRuntimePerformanceDialog()
    assert dialog.tree.topLevelItemCount() == 0
    dialog.set_report(
        run_painter_ui_runtime_performance(
            object_count=25,
            iterations=1,
        )
    )
    assert dialog.tree.topLevelItemCount() == 8
    dialog.resize(420, 500)
    dialog.show()
    _app().processEvents()
    assert dialog.tree.isColumnHidden(2) is True
    assert dialog.tree.isColumnHidden(3) is True

    emitted: list[bool] = []
    dialog.run_requested.connect(lambda: emitted.append(True))
    button = next(
        row
        for row in dialog.findChildren(QPushButton)
        if row.text() == painter_text("Run benchmark")
    )
    button.click()
    assert emitted == [True]


def test_runtime_performance_action_and_quick_action() -> None:
    _app()
    from app.actions.registry import ActionRegistry
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_quick_actions import search_painter_ui_quick_actions

    action = next(
        row
        for row in ActionRegistry(owner=None).list_actions()
        if row["id"] == "paint.ui.runtime_performance.run"
    )
    assert action["mutating"] is False
    result = ActionRegistry(owner=object()).execute(
        "paint.ui.runtime_performance.run",
        {"object_count": 25, "iterations": 1},
    ).to_dict()
    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["case_count"] == 8

    quick = search_painter_ui_quick_actions(
        create_ui_document(390, 844),
        "runtime performance",
    )
    row = next(
        item
        for item in quick["results"]
        if item["id"] == "document.runtime_performance"
    )
    assert row["operation"] == {"type": "runtime_performance"}


def test_workspace_reuses_resolved_layout_for_selection_only_changes() -> None:
    _app()
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_object,
    )
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, row = add_ui_object(
        create_ui_document(390, 844),
        kind="rectangle",
        x=40,
        y=60,
        width=120,
        height=80,
    )
    overlay = PainterUIDesignOverlay()
    overlay.set_document(document)
    resolved = overlay._resolved_geometry

    overlay.set_document(select_ui_object(document, row["id"]))

    assert overlay._resolved_geometry is resolved
    assert overlay._effective_document["selection"]["object_id"] == row["id"]


def test_workspace_render_cache_rebuilds_for_same_revision_content() -> None:
    _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    first, _first_row = add_ui_object(
        create_ui_document(800, 600),
        kind="rectangle",
        x=100,
        y=100,
        width=200,
        height=120,
    )
    second, second_row = add_ui_object(
        create_ui_document(800, 600),
        kind="rectangle",
        x=300,
        y=200,
        width=120,
        height=80,
    )
    assert first["document_id"] == second["document_id"]
    assert first["revision"] == second["revision"]

    overlay = PainterUIDesignOverlay()
    overlay.set_document(first)
    resolved = overlay._resolved_geometry
    overlay.set_document(second)

    assert overlay._resolved_geometry is not resolved
    assert overlay._resolved_geometry[second_row["id"]]["x"] == 300.0


def test_workspace_render_cache_indexes_mask_targets() -> None:
    _app()
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_masks import create_ui_mask
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, mask_row = add_ui_object(
        create_ui_document(390, 844),
        kind="ellipse",
        x=20,
        y=20,
        width=100,
        height=100,
        style={
            "fill": "#000000FF",
            "stroke": "#00000000",
            "stroke_width": 0,
        },
    )
    document, target_row = add_ui_object(
        document,
        kind="frame",
        x=20,
        y=20,
        width=160,
        height=100,
    )
    document, child_row = add_ui_object(
        document,
        kind="rectangle",
        parent_id=target_row["id"],
        x=20,
        y=20,
        width=160,
        height=100,
    )
    document, _mask = create_ui_mask(
        document,
        mask_row["id"],
        target_ids=[target_row["id"]],
    )

    overlay = PainterUIDesignOverlay()
    overlay.resize(480, 900)
    overlay.set_document(document)
    overlay.fit_artboard(document["active_artboard_id"])
    source = overlay._mask_source_for_target(target_row["id"])
    child_source = overlay._mask_source_for_target(child_row["id"])

    assert source is not None
    assert source[0]["id"] == mask_row["id"]
    assert child_source is not None
    assert child_source[0]["id"] == mask_row["id"]

    mask = overlay._effective_objects_by_id[mask_row["id"]]
    child = overlay._effective_objects_by_id[child_row["id"]]
    mask_rect = overlay._object_rect(mask)

    mask_pixels = QImage(
        overlay.width(),
        overlay.height(),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    mask_pixels.fill(0)
    painter = QPainter(mask_pixels)
    overlay._paint_object(painter, mask)
    painter.end()
    center = mask_rect.center().toPoint()
    assert mask_pixels.pixelColor(center).alpha() == 0

    clipped_pixels = QImage(
        overlay.width(),
        overlay.height(),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    clipped_pixels.fill(0)
    painter = QPainter(clipped_pixels)
    painter.save()
    overlay._apply_object_mask(painter, child)
    painter.fillRect(clipped_pixels.rect(), QColor("#FF0000"))
    painter.restore()
    painter.end()

    outside_x = min(
        clipped_pixels.width() - 1,
        int(round(mask_rect.right())) + 8,
    )
    outside_y = max(
        0,
        min(clipped_pixels.height() - 1, int(round(mask_rect.center().y()))),
    )
    assert clipped_pixels.pixelColor(center).alpha() == 255
    assert clipped_pixels.pixelColor(outside_x, outside_y).alpha() == 0


def test_workspace_clips_zoomed_artboard_surface_to_the_view() -> None:
    """Zooming must not grow the rasterised surface with the zoom level."""

    _app()
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QImage

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, _row = add_ui_object(
        create_ui_document(1440, 900, name="Zoom"),
        kind="rectangle",
        x=60,
        y=60,
        width=400,
        height=240,
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay.set_document(document)
    board = overlay._document["artboards"][0]
    frame = QImage(
        overlay.size(),
        QImage.Format.Format_ARGB32_Premultiplied,
    )

    def paint(scale: float, pan: float = 0.0) -> None:
        overlay._view_scale = scale
        overlay._view_offset = QPointF(
            -float(board["x"]) * scale + 20.0 - pan,
            -float(board["y"]) * scale + 20.0,
        )
        overlay.render(frame)

    paint(4.0)
    assert overlay._last_paint_metrics["exact_cache_enabled"] is True
    surfaces = list(overlay._exact_artboard_cache.values())
    assert len(surfaces) == 1
    # The board is 5760x3600 at 400%; the surface only has to carry the 800x600
    # view plus its padding, so it must stay far below the whole board.
    assert surfaces[0].width() < 2_000
    assert surfaces[0].height() < 1_600

    # Panning inside a grid cell reuses the surface instead of rasterising a
    # new one for every pixel of movement.
    cached = {key: id(value) for key, value in overlay._exact_artboard_cache.items()}
    paint(4.0, pan=6.0)
    assert {
        key: id(value) for key, value in overlay._exact_artboard_cache.items()
    } == cached

    overlay.close()
    overlay.deleteLater()


def test_workspace_reuses_surfaces_while_the_view_keeps_moving() -> None:
    """A moving view must not rasterise; it stretches what it already has."""

    _app()
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QImage

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, _row = add_ui_object(
        create_ui_document(1440, 900, name="Gesture"),
        kind="rectangle",
        x=40,
        y=40,
        width=600,
        height=400,
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay.set_document(document)
    frame = QImage(
        overlay.size(),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    anchor = QPointF(400.0, 300.0)

    overlay.set_zoom_percent(100.0, anchor=anchor)
    overlay._end_view_gesture()
    overlay.render(frame)
    settled = dict(overlay._exact_artboard_cache)
    assert len(settled) == 1
    assert overlay._last_paint_metrics["approximate_artboard_count"] == 0

    # Every wheel notch of a burst is served from the settled surface.
    for _notch in range(6):
        overlay.set_zoom_percent(
            overlay.view_state()["zoom_percent"] * 1.2,
            anchor=anchor,
        )
        overlay.render(frame)
        assert overlay._last_paint_metrics["view_gesture_active"] is True
        assert (
            overlay._last_paint_metrics["approximate_artboard_count"] == 1
        )
        assert dict(overlay._exact_artboard_cache) == settled

    # Holding still rasterises the board for the scale it actually ended on.
    overlay._end_view_gesture()
    overlay.render(frame)
    assert overlay._last_paint_metrics["approximate_artboard_count"] == 0
    assert overlay._last_paint_metrics["exact_cache_enabled"] is True
    assert len(overlay._exact_artboard_cache) == 2

    overlay.close()
    overlay.deleteLater()


def test_workspace_defers_boards_it_has_never_rasterised_mid_gesture() -> None:
    _app()
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QImage

    from app.painter_ui_document import (
        add_ui_artboard,
        add_ui_object,
        create_ui_document,
        update_ui_artboard,
    )
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document = create_ui_document(600, 400, name="Deferred")
    document, _renamed = update_ui_artboard(
        document,
        document["active_artboard_id"],
        {"name": "First"},
    )
    document, _first = add_ui_object(
        document,
        kind="rectangle",
        artboard_id=document["active_artboard_id"],
        x=20,
        y=20,
        width=200,
        height=120,
    )
    document, second = add_ui_artboard(
        document,
        name="Second",
        width=600,
        height=400,
    )
    document, _second_row = add_ui_object(
        document,
        kind="rectangle",
        artboard_id=second["id"],
        x=20,
        y=20,
        width=200,
        height=120,
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(500, 400)
    overlay.set_document(document)
    frame = QImage(
        overlay.size(),
        QImage.Format.Format_ARGB32_Premultiplied,
    )

    overlay.fit_artboard(second["id"])
    overlay._end_view_gesture()
    overlay.render(frame)
    assert overlay._last_paint_metrics["visible_artboard_count"] == 1

    # Zooming out brings the other board into view.  It has no surface to be
    # stretched, so the moving frame leaves it to the settle frame rather than
    # rasterising it inside the gesture.
    overlay.set_zoom_percent(20.0)
    overlay.render(frame)
    assert overlay._last_paint_metrics["view_gesture_active"] is True
    assert overlay._last_paint_metrics["visible_artboard_count"] == 2
    assert overlay._last_paint_metrics["approximate_artboard_count"] == 1
    assert overlay._last_paint_metrics["deferred_artboard_count"] == 1

    overlay._end_view_gesture()
    overlay.render(frame)
    assert overlay._last_paint_metrics["deferred_artboard_count"] == 0
    assert overlay._last_paint_metrics["approximate_artboard_count"] == 0

    overlay.close()
    overlay.deleteLater()


def test_workspace_overview_uses_artboard_lod_cache_across_pan() -> None:
    _app()
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QImage

    from app.painter_ui_document import (
        add_ui_artboard,
        add_ui_object,
        create_ui_document,
        update_ui_artboard,
    )
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document = create_ui_document(800, 600)
    first_artboard_id = document["active_artboard_id"]
    document, _renamed = update_ui_artboard(
        document,
        first_artboard_id,
        {"name": "First"},
    )
    document, _first = add_ui_object(
        document,
        kind="rectangle",
        artboard_id=first_artboard_id,
        x=40,
        y=40,
        width=300,
        height=180,
    )
    document, second_artboard = add_ui_artboard(
        document,
        name="Second",
        width=800,
        height=600,
    )
    document, _second = add_ui_object(
        document,
        kind="text",
        artboard_id=second_artboard["id"],
        x=40,
        y=40,
        width=300,
        height=80,
        content={"text": "Overview"},
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(400, 300)
    overlay.set_document(document)
    overlay._view_scale = 0.03
    overlay._view_offset = QPointF(12.0, 12.0)
    image = QImage(
        overlay.size(),
        QImage.Format.Format_ARGB32_Premultiplied,
    )

    overlay.render(image)
    first_cache_ids = {
        key: id(value)
        for key, value in overlay._overview_artboard_cache.items()
    }
    assert overlay._last_paint_metrics["mode"] == "overview_lod"
    assert overlay._last_paint_metrics["visible_artboard_count"] == 2
    assert len(first_cache_ids) == 2

    overlay.pan_view(dx=8.0, dy=4.0)
    overlay.render(image)
    assert {
        key: id(value)
        for key, value in overlay._overview_artboard_cache.items()
    } == first_cache_ids


def test_workspace_exact_artboard_cache_survives_selection_refresh() -> None:
    _app()
    from PySide6.QtGui import QImage

    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_object,
        update_ui_artboard,
    )
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, row = add_ui_object(
        create_ui_document(800, 600),
        kind="rectangle",
        x=80,
        y=80,
        width=320,
        height=200,
    )
    document, _renamed = update_ui_artboard(
        document,
        document["active_artboard_id"],
        {"name": "Canvas"},
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(960, 720)
    overlay.set_document(document)
    overlay.fit_artboard(document["active_artboard_id"])
    image = QImage(
        overlay.size(),
        QImage.Format.Format_ARGB32_Premultiplied,
    )

    overlay.render(image)
    cache_ids = {
        key: id(value)
        for key, value in overlay._exact_artboard_cache.items()
    }
    assert overlay._last_paint_metrics["mode"] == "exact"
    assert overlay._last_paint_metrics["exact_cache_enabled"] is True
    assert len(cache_ids) == 1

    overlay.set_document(select_ui_object(document, row["id"]))
    overlay.render(image)
    assert {
        key: id(value)
        for key, value in overlay._exact_artboard_cache.items()
    } == cache_ids
