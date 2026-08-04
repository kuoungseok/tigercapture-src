from __future__ import annotations

import os

from PySide6.QtGui import QColor, QImage


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_polygon_mask_preserves_partial_alpha_and_applies_per_pixel() -> None:
    from app.painter_layer_masks import apply_alpha8_mask, polygon_alpha8_mask

    mask = polygon_alpha8_mask(
        20,
        10,
        [(0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)],
        inside=128,
    )
    source = QImage(20, 10, QImage.Format.Format_ARGB32_Premultiplied)
    source.fill(QColor(240, 30, 20, 255))
    output = apply_alpha8_mask(source, mask)
    assert output.pixelColor(2, 5).alpha() in range(127, 130)
    assert output.pixelColor(17, 5).alpha() == 0


def test_gradient_mask_retains_continuous_8_bit_values() -> None:
    from app.painter_layer_masks import linear_gradient_alpha8_mask

    mask = linear_gradient_alpha8_mask(101, 1, (0.0, 0.0), (1.0, 0.0))
    left = mask.pixelColor(0, 0).alpha()
    middle = mask.pixelColor(50, 0).alpha()
    right = mask.pixelColor(100, 0).alpha()
    assert left <= 2
    assert 120 <= middle <= 135
    assert right >= 252


def test_mask_brush_can_hide_and_reveal_without_binary_polygon_loss() -> None:
    from app.painter_layer_masks import alpha8_mask, paint_mask_circle

    mask = alpha8_mask(32, 32, 255)
    hidden = paint_mask_circle(mask, (16, 16), 6, 0)
    revealed = paint_mask_circle(hidden, (16, 16), 2, 180)
    assert hidden.pixelColor(16, 16).alpha() == 0
    assert 175 <= revealed.pixelColor(16, 16).alpha() <= 185
    assert revealed.pixelColor(2, 2).alpha() == 255


def test_painter_layer_mask_undo_redo_restores_raster_asset() -> None:
    _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 32, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_recovery_timer.stop()
    dialog.canvas.set_selection_snapshot(
        [(0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)]
    )
    layer_id = dialog._active_paint_layer_id
    assert dialog._create_layer_mask("selection") is True
    assert dialog._paint_layer_mask(layer_id) is not None
    dialog._undo()
    assert dialog._paint_layer_mask(layer_id) is None
    dialog._redo()
    restored = dialog._paint_layer_mask(layer_id)
    assert restored is not None
    assert restored.pixelColor(8, 16).alpha() == 255
    assert restored.pixelColor(56, 16).alpha() == 0


def test_gradient_layer_mask_document_round_trip_preserves_composite_pixels(tmp_path) -> None:
    _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_layer_masks import linear_gradient_alpha8_mask

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(101, 8, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_recovery_timer.stop()
    assert dialog._fill_document("solid", color1="#E05030")
    layer = dialog._active_paint_layer()
    layer.mask_enabled = True
    dialog._set_paint_layer_mask(
        layer.layer_id,
        linear_gradient_alpha8_mask(101, 8, (0.0, 0.0), (1.0, 0.0)),
    )
    before = dialog._painter_composite_pil(include_background=False)
    path = tmp_path / "gradient-mask.tspaint"
    dialog.save_document_to_path(path)

    restored = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    restored._painter_recovery_timer.stop()
    restored.open_document_from_path(path)
    after = restored._painter_composite_pil(include_background=False)
    assert after.tobytes() == before.tobytes()
    assert after.getpixel((0, 4))[3] <= 2
    assert 120 <= after.getpixel((50, 4))[3] <= 135
    assert after.getpixel((100, 4))[3] >= 252


def test_apply_layer_mask_bakes_identical_pixels_and_is_undoable() -> None:
    _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_layer_masks import linear_gradient_alpha8_mask

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(101, 8, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_recovery_timer.stop()
    assert dialog._fill_document("solid", color1="#4090D0")
    layer = dialog._active_paint_layer()
    layer.mask_enabled = True
    dialog._set_paint_layer_mask(
        layer.layer_id,
        linear_gradient_alpha8_mask(101, 8, (0.0, 0.0), (1.0, 0.0)),
    )
    before = dialog._painter_composite_pil(include_background=False).tobytes()
    assert dialog._apply_selected_layer_mask(layer.layer_id) is True
    assert dialog._painter_composite_pil(include_background=False).tobytes() == before
    assert dialog._paint_layer_mask(layer.layer_id) is None
    assert layer.mask_enabled is False
    dialog._undo()
    restored_layer = dialog._paint_layer_by_id(layer.layer_id)
    assert restored_layer is not None and restored_layer.mask_enabled is True
    assert dialog._paint_layer_mask(layer.layer_id) is not None
    assert dialog._painter_composite_pil(include_background=False).tobytes() == before


def test_layer_all_transform_respects_mask_link_and_explicit_mask_target() -> None:
    _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_layer_masks import alpha8_mask, paint_mask_circle

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 32, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_recovery_timer.stop()
    layer = dialog._active_paint_layer()
    layer.mask_enabled = True
    dialog._set_paint_layer_mask(
        layer.layer_id,
        paint_mask_circle(alpha8_mask(64, 32, 0), (12, 16), 3, 255),
    )
    assert dialog._preview_selection_transform(target="layer_all", translate_x=16) is True
    moved = dialog._paint_layer_mask(layer.layer_id)
    assert moved is not None and moved.pixelColor(28, 16).alpha() > 200
    dialog._cancel_selection_transform()
    layer.mask_linked = False
    assert dialog._preview_selection_transform(target="layer_all", translate_x=16) is False
    unchanged = dialog._paint_layer_mask(layer.layer_id)
    assert unchanged is not None and unchanged.pixelColor(12, 16).alpha() > 200
    assert dialog._preview_selection_transform(target="layer_mask", translate_x=16) is True
    explicit = dialog._paint_layer_mask(layer.layer_id)
    assert explicit is not None and explicit.pixelColor(28, 16).alpha() > 200
    dialog._cancel_selection_transform()


def test_raster_mask_actions_are_registered() -> None:
    from app.actions.registry import ActionRegistry

    registry = ActionRegistry()
    action_ids = {row["id"] for row in registry.list_actions()}
    assert {
        "paint.layer.mask.paint",
        "paint.layer.mask.gradient",
        "paint.layer.mask.apply",
    } <= action_ids


def test_layer_clipboard_round_trip_keeps_alpha8_mask() -> None:
    _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_layer_masks import linear_gradient_alpha8_mask

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 32, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_recovery_timer.stop()
    layer = dialog._active_paint_layer()
    layer.mask_enabled = True
    dialog._set_paint_layer_mask(
        layer.layer_id,
        linear_gradient_alpha8_mask(64, 32, (0.0, 0.0), (1.0, 0.0)),
    )
    payload = dialog._payload_for_layer(layer.layer_id)
    assert payload is not None
    document = dialog._payload_to_clipboard_document(payload)
    assert document is not None and document["schema"].endswith(".v2")
    restored_payload = dialog._payload_from_clipboard_document(document)
    assert restored_payload is not None
    restored_mask = restored_payload["mask_raster"]
    assert restored_mask.pixelColor(0, 16).alpha() <= 2
    assert restored_mask.pixelColor(63, 16).alpha() >= 252
    before_ids = {row.layer_id for row in dialog._paint_layers}
    dialog._paste_payload(restored_payload)
    pasted_layer = next(row for row in dialog._paint_layers if row.layer_id not in before_ids)
    pasted_mask = dialog._paint_layer_mask(pasted_layer.layer_id)
    assert pasted_mask is not None
    assert 120 <= pasted_mask.pixelColor(32, 16).alpha() <= 135


def test_image_canvas_resize_and_flip_transform_raster_mask_pixels() -> None:
    _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_layer_masks import linear_gradient_alpha8_mask

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_recovery_timer.stop()
    layer = dialog._active_paint_layer()
    layer.mask_enabled = True
    dialog._set_paint_layer_mask(
        layer.layer_id,
        linear_gradient_alpha8_mask(64, 64, (0.0, 0.0), (1.0, 0.0)),
    )
    assert dialog._resize_image_document(128, 64) is True
    resized = dialog._paint_layer_mask(layer.layer_id)
    assert resized is not None and resized.size().toTuple() == (128, 64)
    assert resized.pixelColor(0, 32).alpha() <= 2
    assert resized.pixelColor(127, 32).alpha() >= 252

    assert dialog._resize_canvas_document(160, 80) is True
    expanded = dialog._paint_layer_mask(layer.layer_id)
    assert expanded is not None and expanded.size().toTuple() == (160, 80)
    assert expanded.pixelColor(4, 40).alpha() == 0
    assert expanded.pixelColor(143, 40).alpha() >= 252
    assert expanded.pixelColor(155, 40).alpha() == 0

    assert dialog._flip_canvas(horizontal=True) is True
    flipped = dialog._paint_layer_mask(layer.layer_id)
    assert flipped is not None
    assert flipped.pixelColor(16, 40).alpha() >= 252
    assert flipped.pixelColor(143, 40).alpha() <= 2
