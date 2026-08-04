from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_group_clipping_locks_and_merge_down_are_one_step_undoable() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(100, 100, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    bottom_id = dialog._active_paint_layer_id
    assert dialog._fill_document("solid", color1="#D04040")
    top = dialog._new_paint_layer("Top")
    assert dialog._fill_document("solid", color1="#3040D0")
    assert dialog._set_layer_opacity_value(top.layer_id, 50)
    merged = dialog._merge_down(top.layer_id)
    assert merged is not None
    assert len(dialog._paint_layers) == 1
    color = dialog._paint_layer_rasters[bottom_id].pixelColor(50, 50)
    assert 126 <= color.red() <= 130
    assert 55 <= color.green() <= 65
    assert 130 <= color.blue() <= 140
    dialog._undo()
    assert len(dialog._paint_layers) == 2
    assert dialog._paint_layer_by_id(top.layer_id) is not None

    group = dialog._new_paint_layer_group("Paint Group", layer_ids=[bottom_id, top.layer_id])
    assert dialog._paint_layer_by_id(bottom_id).parent_id == group.layer_id
    assert dialog._paint_layer_by_id(top.layer_id).parent_id == group.layer_id
    expanded_count = dialog._layer_list.count()
    assert dialog._set_layer_group_expanded(group.layer_id, False)
    assert dialog._layer_list.count() == expanded_count - 2
    collapsed_item = next(
        dialog._layer_list.item(i)
        for i in range(dialog._layer_list.count())
        if dialog._layer_list.item(i).data(256) == group.layer_id
    )
    assert collapsed_item.text().startswith("▸ ")
    assert dialog._set_layer_group_expanded(group.layer_id, True)
    assert dialog._set_layer_clipping(top.layer_id, True)
    assert dialog._set_layer_lock_channels(
        top.layer_id, pixels=True, transparency=True, position=True
    )
    locked = dialog._paint_layer_by_id(top.layer_id)
    assert locked.clipping is True
    assert locked.lock_pixels and locked.lock_transparency and locked.lock_position
    dialog._undo()
    unlocked = dialog._paint_layer_by_id(top.layer_id)
    assert not unlocked.lock_pixels
    assert not unlocked.lock_transparency
    assert not unlocked.lock_position
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_layer_tree_fields_round_trip_in_native_document(tmp_path) -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(80, 60, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    child = dialog._active_paint_layer()
    assert dialog._fill_document("solid", color1="#58A86C")
    group = dialog._new_paint_layer_group("Folder", layer_ids=[child.layer_id])
    child.clipping = True
    child.lock_position = True
    child.blend_mode = "soft_light"
    path = tmp_path / "layer_tree.tspaint"
    dialog.save_document_to_path(path)

    restored = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    restored.open_document_from_path(path)
    restored_group = restored._paint_layer_by_id(group.layer_id)
    restored_child = restored._paint_layer_by_id(child.layer_id)
    assert restored_group.node_type == "group"
    assert restored_child.parent_id == restored_group.layer_id
    assert restored_child.clipping is True
    assert restored_child.lock_position is True
    assert restored_child.blend_mode == "soft_light"
    for item in (dialog, restored):
        item.close()
        item.deleteLater()
    app.processEvents()


def test_m2_layer_actions_use_the_same_dialog_operations() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    base_id = dialog._active_paint_layer_id
    added = registry.execute("paint.layer.add", {"name": "Clipped Paint"}).to_dict()
    assert added["ok"]
    top_id = added["result"]["active_layer_id"]
    clipped = registry.execute(
        "paint.layer.set_clipping", {"layer_id": top_id, "clipping": True}
    ).to_dict()
    assert clipped["ok"] and clipped["result"]["layers"][-1]["clipping"] is True
    locked = registry.execute(
        "paint.layer.set_locks",
        {"layer_id": top_id, "pixels": True, "position": True},
    ).to_dict()
    assert locked["ok"]
    top_state = next(row for row in locked["result"]["layers"] if row["layer_id"] == top_id)
    assert top_state["locks"]["pixels"] and top_state["locks"]["position"]
    grouped = registry.execute(
        "paint.layer.group.create",
        {"name": "Action Group", "layer_ids": [base_id, top_id]},
    ).to_dict()
    assert grouped["ok"]
    assert any(row["node_type"] == "group" for row in grouped["result"]["layers"])
    flattened = registry.execute("paint.layer.flatten", {}).to_dict()
    assert flattened["ok"]
    assert len(flattened["result"]["layers"]) == 1
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_merge_respects_group_effects_and_inherited_visibility() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(32, 32, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    bottom = dialog._active_paint_layer()
    assert dialog._fill_document("solid", color1="#FF0000")
    top = dialog._new_paint_layer("Blue")
    assert dialog._fill_document("solid", color1="#0000FF")
    top.opacity = 50
    group = dialog._new_paint_layer_group(
        "Half Group", layer_ids=[bottom.layer_id, top.layer_id]
    )
    group.opacity = 50
    dialog._sync_canvas_layer_view()
    before = dialog._pbr_source_image()[0].tobytes()
    merged = dialog._merge_down(top.layer_id)
    assert merged is not None and merged.parent_id == group.layer_id
    assert dialog._pbr_source_image()[0].tobytes() == before

    dialog._undo()
    group = dialog._paint_layer_by_id(group.layer_id)
    group.visible = False
    root = dialog._new_paint_layer("Visible Root")
    assert dialog._fill_document("solid", color1="#222222")
    before = dialog._pbr_source_image()[0].tobytes()
    dialog._merge_visible()
    assert dialog._pbr_source_image()[0].tobytes() == before
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_layer_locks_block_pixel_mask_and_position_mutations() -> None:
    app = _app()
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtCore import QRect
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    layer = dialog._active_paint_layer()
    assert dialog._fill_document("solid", color1="#50A070")
    dialog.canvas.select_rectangle(0.0, 0.0, 0.5, 0.5)
    layer.lock_pixels = True
    dialog._cut_selected_layer()
    assert dialog._paint_layer_rasters[layer.layer_id].pixelColor(8, 8).alpha() == 255
    layer.lock_pixels = False
    layer.lock_transparency = True
    dialog._cut_selected_layer()
    assert dialog._paint_layer_rasters[layer.layer_id].pixelColor(8, 8).alpha() == 255
    layer.lock_transparency = False
    layer.mask = [(0, 0), (1, 0), (1, 1), (0, 1)]
    layer.mask_enabled = True
    layer.locked = True
    assert dialog._set_layer_mask_state(layer.layer_id, delete=True) is False
    assert len(layer.mask) == 4

    layer.locked = False
    layer.lock_position = True
    other = dialog._new_paint_layer("Other")
    dialog._update_layer_list()
    visual_before = [
        dialog._layer_list.item(i).data(256) for i in range(dialog._layer_list.count())
    ]
    model = dialog._layer_list.model()
    model.moveRow(model.index(-1, -1), 1, model.index(-1, -1), 0)
    app.processEvents()
    visual_after = [
        dialog._layer_list.item(i).data(256) for i in range(dialog._layer_list.count())
    ]
    assert visual_after == visual_before

    l_shape = QImage(64, 64, QImage.Format.Format_ARGB32_Premultiplied)
    l_shape.fill(0)
    painter = QPainter(l_shape)
    try:
        painter.fillRect(QRect(4, 4, 16, 52), QColor("white"))
        painter.fillRect(QRect(4, 40, 48, 16), QColor("white"))
    finally:
        painter.end()
    dialog._paint_layer_rasters[other.layer_id] = l_shape
    dialog._active_paint_layer_id = other.layer_id
    points = dialog._mask_points_from_active_layer_alpha()
    assert len(points) > 4
    dialog.close(); dialog.deleteLater(); app.processEvents()
