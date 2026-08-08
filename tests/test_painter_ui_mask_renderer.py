from __future__ import annotations

import os
import time


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _gradient_mask_document():
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_masks import create_ui_mask

    document, mask = add_ui_object(
        create_ui_document(200, 100, name="Pixel Mask"),
        kind="rectangle",
        name="Alpha Gradient Mask",
        x=0,
        y=0,
        width=200,
        height=100,
        style={
            "fills": [
                {
                    "type": "linear",
                    "visible": True,
                    "opacity": 1.0,
                    "gradient": {
                        "type": "linear",
                        "start": {"x": 0.0, "y": 0.5},
                        "end": {"x": 1.0, "y": 0.5},
                        "width": {"x": 0.0, "y": 1.0},
                        "stops": [
                            {"position": 0.0, "color": "#FFFFFFFF"},
                            {"position": 1.0, "color": "#FFFFFF00"},
                        ],
                    },
                }
            ],
            "stroke": "#00000000",
            "stroke_width": 0,
        },
        content={
            "figma_mask": {
                "type": "alpha",
                "requires_raster_alpha": True,
                "workspace_rendering": "pixel_alpha",
            }
        },
    )
    document, target = add_ui_object(
        document,
        kind="frame",
        name="Target",
        x=0,
        y=0,
        width=200,
        height=100,
        style={
            "fill": "#00000000",
            "stroke": "#00000000",
            "stroke_width": 0,
        },
    )
    document, child = add_ui_object(
        document,
        kind="rectangle",
        name="Target Child",
        parent_id=target["id"],
        x=0,
        y=0,
        width=200,
        height=100,
        style={
            "fill": "#FF0000FF",
            "stroke": "#00000000",
            "stroke_width": 0,
        },
    )
    document, _mask = create_ui_mask(
        document,
        mask["id"],
        target_ids=[target["id"]],
    )
    return document, mask, target, child


def test_pixel_mask_alpha_and_luminance_conversion() -> None:
    _app()
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.painter_ui_mask_renderer import apply_ui_pixel_mask

    target = QImage(3, 1, QImage.Format.Format_ARGB32_Premultiplied)
    target.fill(QColor("#FF0000"))
    luminance = QImage(3, 1, QImage.Format.Format_ARGB32_Premultiplied)
    luminance.setPixelColor(0, 0, QColor(0, 0, 0, 255))
    luminance.setPixelColor(1, 0, QColor(128, 128, 128, 255))
    luminance.setPixelColor(2, 0, QColor(255, 255, 255, 255))

    result = apply_ui_pixel_mask(
        target,
        luminance,
        mode="luminance",
    )
    assert result.pixelColor(0, 0).alpha() == 0
    assert 126 <= result.pixelColor(1, 0).alpha() <= 129
    assert result.pixelColor(2, 0).alpha() == 255

    alpha_source = QImage(3, 1, QImage.Format.Format_ARGB32_Premultiplied)
    alpha_source.fill(0)
    painter = QPainter(alpha_source)
    painter.fillRect(0, 0, 1, 1, QColor(255, 255, 255, 255))
    painter.fillRect(1, 0, 1, 1, QColor(255, 255, 255, 128))
    painter.end()
    alpha_result = apply_ui_pixel_mask(
        target,
        alpha_source,
        mode="alpha",
    )
    assert alpha_result.pixelColor(0, 0).alpha() == 255
    assert 126 <= alpha_result.pixelColor(1, 0).alpha() <= 129
    assert alpha_result.pixelColor(2, 0).alpha() == 0


def test_workspace_composites_linear_alpha_mask_as_pixels() -> None:
    _app()
    from PySide6.QtGui import QImage

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, mask, _target, child = _gradient_mask_document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(400, 240)
    overlay.set_document(document)
    overlay.fit_artboard(document["active_artboard_id"])
    rows = overlay._visible_objects()
    group = overlay._pixel_mask_group_by_target[child["id"]]
    base = QImage(
        overlay.width(),
        overlay.height(),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    base.fill(0)

    result, origin = overlay._render_pixel_mask_group(base, rows, group)
    rect = overlay._object_rect(overlay._effective_objects_by_id[mask["id"]])
    y = int(round(rect.center().y() - origin.y()))
    left = result.pixelColor(
        int(round(rect.left() + 4 - origin.x())),
        y,
    ).alpha()
    middle = result.pixelColor(
        int(round(rect.center().x() - origin.x())),
        y,
    ).alpha()
    right = result.pixelColor(
        int(round(rect.right() - 4 - origin.x())),
        y,
    ).alpha()

    assert left > 235
    assert 100 <= middle <= 155
    assert right < 20


def test_workspace_cropped_mask_matches_full_surface_reference() -> None:
    _app()
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QImage, QPainter

    from app.painter_ui_mask_renderer import apply_ui_pixel_mask
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, _mask, _target, child = _gradient_mask_document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(400, 240)
    overlay.set_document(document)
    overlay.fit_artboard(document["active_artboard_id"])
    rows = overlay._visible_objects()
    group = overlay._pixel_mask_group_by_target[child["id"]]

    def surface() -> QImage:
        image = QImage(
            overlay.width(),
            overlay.height(),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(0)
        return image

    target = surface()
    painter = QPainter(target)
    for row in rows:
        if row["id"] in set(group["target_ids"]):
            overlay._paint_scene_row(
                painter,
                row,
                surface=target,
                apply_object_mask=False,
            )
    painter.end()
    mask_surface = surface()
    painter = QPainter(mask_surface)
    for row in rows:
        if row["id"] in set(group["source_ids"]):
            overlay._paint_scene_row(
                painter,
                row,
                surface=mask_surface,
                apply_object_mask=False,
                render_mask_source=True,
                dim_outside_edit_scope=False,
            )
    painter.end()
    reference = apply_ui_pixel_mask(
        target,
        mask_surface,
        mode="alpha",
    )

    cropped, origin = overlay._render_pixel_mask_group(
        surface(),
        rows,
        group,
    )
    reconstructed = surface()
    painter = QPainter(reconstructed)
    painter.drawImage(QPointF(origin), cropped)
    painter.end()

    assert reconstructed == reference


def test_workspace_masks_composited_group_once() -> None:
    _app()
    from PySide6.QtGui import QImage

    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_masks import create_ui_mask
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, mask = add_ui_object(
        create_ui_document(100, 100),
        kind="rectangle",
        x=0,
        y=0,
        width=100,
        height=100,
        style={"fill": "#FFFFFF80", "stroke_width": 0},
        content={"figma_mask": {"type": "alpha"}},
    )
    document, first = add_ui_object(
        document,
        kind="rectangle",
        x=0,
        y=0,
        width=100,
        height=100,
        style={"fill": "#FF0000FF", "stroke_width": 0},
    )
    document, second = add_ui_object(
        document,
        kind="rectangle",
        x=0,
        y=0,
        width=100,
        height=100,
        style={"fill": "#FF0000FF", "stroke_width": 0},
    )
    document, _first = update_ui_object(
        document,
        first["id"],
        {"opacity": 0.5},
    )
    document, _second = update_ui_object(
        document,
        second["id"],
        {"opacity": 0.5},
    )
    document, _mask = create_ui_mask(
        document,
        mask["id"],
        target_ids=[first["id"], second["id"]],
    )

    overlay = PainterUIDesignOverlay()
    overlay.resize(240, 240)
    overlay.set_document(document)
    overlay.fit_artboard(document["active_artboard_id"])
    group = overlay._pixel_mask_group_by_target[first["id"]]
    base = QImage(
        overlay.width(),
        overlay.height(),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    base.fill(0)
    result, origin = overlay._render_pixel_mask_group(
        base,
        overlay._visible_objects(),
        group,
    )
    rect = overlay._object_rect(overlay._effective_objects_by_id[first["id"]])
    alpha = result.pixelColor(
        int(round(rect.center().x() - origin.x())),
        int(round(rect.center().y() - origin.y())),
    ).alpha()

    # Two 50% targets first composite to 75%, then the 50% source mask is
    # applied once: 0.75 * 0.5 ~= 0.375. Per-object masking would be ~0.438.
    assert 92 <= alpha <= 100


def test_asset_export_composites_linear_alpha_mask_as_pixels() -> None:
    _app()
    from app.painter_ui_asset_export import render_ui_artboard

    document, _mask, _target, _child = _gradient_mask_document()
    image = render_ui_artboard(
        document,
        document["active_artboard_id"],
    )
    left = image.pixelColor(4, 50)
    middle = image.pixelColor(100, 50)
    right = image.pixelColor(196, 50)

    assert left.red() > 240 and left.green() < 25
    assert middle.red() > 240 and 90 <= middle.green() <= 170
    assert right.red() > 235 and right.green() > 225 and right.blue() > 225


def test_4k_pixel_mask_uses_cropped_memory_budget() -> None:
    _app()
    from PySide6.QtGui import QImage

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_mask_renderer import (
        PIXEL_MASK_CROPPED_TEMP_BUDGET_BYTES,
        PIXEL_MASK_SINGLE_GROUP_TIME_BUDGET_MS,
    )
    from app.painter_ui_masks import create_ui_mask
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, mask = add_ui_object(
        create_ui_document(3840, 2160, name="4K Mask Budget"),
        kind="rectangle",
        x=2880,
        y=0,
        width=960,
        height=2160,
        style={
            "fills": [
                {
                    "type": "linear",
                    "visible": True,
                    "opacity": 1.0,
                    "gradient": {
                        "type": "linear",
                        "start": {"x": 0.0, "y": 0.5},
                        "end": {"x": 1.0, "y": 0.5},
                        "stops": [
                            {"position": 0.0, "color": "#FFFFFFFF"},
                            {"position": 1.0, "color": "#FFFFFF00"},
                        ],
                    },
                }
            ],
            "stroke_width": 0,
        },
        content={"figma_mask": {"type": "alpha"}},
    )
    document, target = add_ui_object(
        document,
        kind="frame",
        x=0,
        y=0,
        width=3840,
        height=2160,
        style={"fill": "#00000000", "stroke_width": 0},
    )
    document, child = add_ui_object(
        document,
        kind="rectangle",
        parent_id=target["id"],
        x=0,
        y=0,
        width=3840,
        height=2160,
        style={"fill": "#FF0000FF", "stroke_width": 0},
    )
    document, _mask = create_ui_mask(
        document,
        mask["id"],
        target_ids=[target["id"]],
    )

    overlay = PainterUIDesignOverlay()
    overlay.resize(3840, 2160)
    overlay.set_document(document)
    overlay.fit_artboard(document["active_artboard_id"])
    base = QImage(
        overlay.width(),
        overlay.height(),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    base.fill(0)
    group = overlay._pixel_mask_group_by_target[child["id"]]

    started = time.perf_counter()
    result, _origin = overlay._render_pixel_mask_group(
        base,
        overlay._visible_objects(),
        group,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    metrics = overlay._last_pixel_mask_render_metrics

    assert not result.isNull()
    assert metrics["crop_ratio"] < 0.30
    assert (
        metrics["estimated_peak_bytes"]
        <= PIXEL_MASK_CROPPED_TEMP_BUDGET_BYTES
    )
    assert elapsed_ms <= PIXEL_MASK_SINGLE_GROUP_TIME_BUDGET_MS
