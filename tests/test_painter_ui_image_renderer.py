from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_image_draw_plans_cover_all_fit_modes() -> None:
    from PySide6.QtCore import QRectF, QSizeF

    from app.painter_ui_image_renderer import image_draw_plan

    source = QSizeF(200, 100)
    target = QRectF(0, 0, 100, 100)
    fit = image_draw_plan(source, target, {"image_fit": "fit"})
    assert fit == [(QRectF(0, 25, 100, 50), QRectF(0, 0, 200, 100))]

    fill = image_draw_plan(source, target, {"image_fit": "fill"})
    assert fill == [(QRectF(target), QRectF(50, 0, 100, 100))]

    stretch = image_draw_plan(source, target, {"image_fit": "stretch"})
    assert stretch == [(QRectF(target), QRectF(0, 0, 200, 100))]

    tile = image_draw_plan(
        QSizeF(20, 10),
        QRectF(0, 0, 45, 25),
        {"image_fit": "tile"},
    )
    assert len(tile) == 9
    assert tile[-1] == (QRectF(40, 20, 5, 5), QRectF(0, 0, 5, 5))


def test_nine_slice_plan_preserves_edges_and_bounds_small_targets() -> None:
    from PySide6.QtCore import QRectF, QSizeF

    from app.painter_ui_image_renderer import image_draw_plan

    content = {
        "nine_slice_enabled": True,
        "nine_slice": {"left": 10, "top": 12, "right": 20, "bottom": 18},
    }
    plan = image_draw_plan(QSizeF(100, 80), QRectF(0, 0, 240, 160), content)
    assert len(plan) == 9
    assert plan[0] == (QRectF(0, 0, 10, 12), QRectF(0, 0, 10, 12))
    assert plan[4] == (QRectF(10, 12, 210, 130), QRectF(10, 12, 70, 50))
    assert plan[-1] == (QRectF(220, 142, 20, 18), QRectF(80, 62, 20, 18))

    small = image_draw_plan(QSizeF(100, 80), QRectF(0, 0, 15, 12), content)
    assert len(small) == 4
    assert sum(row[0].width() for row in (small[0], small[1])) == 15.0
    assert max(rect.right() for rect, _source in small) == 15.0
    assert max(rect.bottom() for rect, _source in small) == 12.0


def test_draw_ui_image_renders_real_source_and_missing_source_falls_back(
    tmp_path,
) -> None:
    app = _app()
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.painter_ui_image_renderer import draw_ui_image

    source_path = tmp_path / "ui-source.png"
    source = QImage(20, 10, QImage.Format.Format_ARGB32)
    source.fill(QColor("#28A878"))
    assert source.save(str(source_path), "PNG")

    output = QImage(100, 100, QImage.Format.Format_ARGB32)
    output.fill(QColor("#101010"))
    painter = QPainter(output)
    assert draw_ui_image(
        painter,
        QRectF(0, 0, 100, 100),
        {"source_path": str(source_path), "image_fit": "fit"},
    )
    painter.end()
    assert output.pixelColor(50, 50).name() == "#28a878"
    assert output.pixelColor(50, 10).name() == "#101010"

    missing = QPainter(output)
    assert not draw_ui_image(
        missing,
        QRectF(0, 0, 100, 100),
        {"source_path": str(tmp_path / "missing.png")},
    )
    missing.end()
    app.processEvents()


def test_figma_affine_image_transform_samples_normalized_source_uv(
    tmp_path,
) -> None:
    _app()
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.painter_ui_image_renderer import draw_ui_image

    source_path = tmp_path / "figma-crop.png"
    source = QImage(100, 60, QImage.Format.Format_ARGB32)
    source.fill(QColor("#DD3344"))
    source.fill(QColor("#35B96B"))
    painter = QPainter(source)
    painter.fillRect(0, 0, 50, 60, QColor("#DD3344"))
    painter.end()
    assert source.save(str(source_path), "PNG")

    right_half = QImage(100, 60, QImage.Format.Format_ARGB32)
    right_half.fill(QColor("#101010"))
    painter = QPainter(right_half)
    assert draw_ui_image(
        painter,
        QRectF(0, 0, 100, 60),
        {
            "source_path": str(source_path),
            "image_fit": "stretch",
            # Figma REST transforms target-normalized positions into source
            # UVs, so this selects source U=0.5..1.0.
            "image_transform": [[0.5, 0.0, 0.5], [0.0, 1.0, 0.0]],
        },
    )
    painter.end()
    assert right_half.pixelColor(10, 30).name() == "#35b96b"
    assert right_half.pixelColor(90, 30).name() == "#35b96b"

    scaled_view = QImage(200, 120, QImage.Format.Format_ARGB32)
    scaled_view.fill(QColor("#101010"))
    painter = QPainter(scaled_view)
    painter.scale(2.0, 2.0)
    assert draw_ui_image(
        painter,
        QRectF(0, 0, 100, 60),
        {
            "source_path": str(source_path),
            "image_fit": "stretch",
            "image_transform": [[0.5, 0.0, 0.5], [0.0, 1.0, 0.0]],
        },
    )
    painter.end()
    assert scaled_view.pixelColor(20, 60).name() == "#35b96b"
    assert scaled_view.pixelColor(180, 60).name() == "#35b96b"

    left_half = QImage(100, 60, QImage.Format.Format_ARGB32)
    left_half.fill(QColor("#101010"))
    painter = QPainter(left_half)
    assert draw_ui_image(
        painter,
        QRectF(0, 0, 100, 60),
        {
            "source_path": str(source_path),
            "image_fit": "stretch",
            "image_transform": [[0.5, 0.0, 0.0], [0.0, 1.0, 0.0]],
        },
    )
    painter.end()
    assert left_half.pixelColor(10, 30).name() == "#dd3344"
    assert left_half.pixelColor(90, 30).name() == "#dd3344"


def test_figma_image_rotation_is_applied_before_fit_planning(tmp_path) -> None:
    _app()
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.painter_ui_image_renderer import draw_ui_image

    source_path = tmp_path / "figma-rotation.png"
    source = QImage(40, 20, QImage.Format.Format_ARGB32)
    source.fill(QColor("#E13D52"))
    painter = QPainter(source)
    painter.fillRect(20, 0, 20, 20, QColor("#3BAA70"))
    painter.end()
    assert source.save(str(source_path), "PNG")

    output = QImage(40, 40, QImage.Format.Format_ARGB32)
    output.fill(QColor("#101010"))
    painter = QPainter(output)
    assert draw_ui_image(
        painter,
        QRectF(0, 0, 40, 40),
        {
            "source_path": str(source_path),
            "image_fit": "stretch",
            "image_rotation": 90,
        },
    )
    painter.end()
    assert output.pixelColor(20, 6).name() != output.pixelColor(20, 34).name()
    assert {
        output.pixelColor(20, 6).name(),
        output.pixelColor(20, 34).name(),
    } == {"#e13d52", "#3baa70"}


def test_image_content_normalization_preserves_unrelated_metadata() -> None:
    from app.painter_ui_image_renderer import normalize_ui_image_content

    result = normalize_ui_image_content(
        {
            "source_path": "panel.png",
            "image_fit": "unknown",
            "tile_scale": 0,
            "nine_slice_enabled": True,
            "nine_slice": {"left": 4, "top": -3, "right": 7, "bottom": 8},
            "resource_id": "asset-panel",
        }
    )
    assert result["image_fit"] == "fit"
    assert result["tile_scale"] == 0.05
    assert result["nine_slice"] == {
        "left": 4.0,
        "top": 0.0,
        "right": 7.0,
        "bottom": 8.0,
    }
    assert result["resource_id"] == "asset-panel"


def test_workspace_image_object_uses_image_renderer(tmp_path) -> None:
    app = _app()
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    source_path = tmp_path / "workspace-image.png"
    source = QImage(32, 32, QImage.Format.Format_ARGB32)
    source.fill(QColor("#D95876"))
    assert source.save(str(source_path), "PNG")
    document = create_ui_document(100, 100)
    document, _row = add_ui_object(
        document,
        kind="image",
        x=10,
        y=10,
        width=80,
        height=80,
        content={"source_path": str(source_path), "image_fit": "stretch"},
    )
    row = document["objects"][0]
    overlay = PainterUIDesignOverlay()
    overlay.resize(240, 240)
    overlay.set_document(document)
    output = QImage(240, 240, QImage.Format.Format_ARGB32)
    output.fill(QColor("#000000"))
    painter = QPainter(output)
    overlay._paint_object(painter, row)
    painter.end()
    center = overlay._object_rect(row).center().toPoint()
    assert output.pixelColor(center).name() == "#d95876"
    overlay.deleteLater()
    app.processEvents()
