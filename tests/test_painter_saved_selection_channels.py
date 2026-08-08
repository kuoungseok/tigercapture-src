from __future__ import annotations

import hashlib
import json
import os
import zipfile

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _mask(values: list[int]):
    from PySide6.QtGui import QImage

    return QImage(
        bytes(values),
        len(values),
        1,
        len(values),
        QImage.Format.Format_Alpha8,
    ).copy()


def _values(mask) -> list[int]:
    from PySide6.QtGui import QImage

    image = mask.convertToFormat(QImage.Format.Format_Alpha8)
    return list(bytes(image.constBits())[: image.width()])


def _write_archive(path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def test_saved_selection_channel_exact_save_and_load_operations() -> None:
    from app.painter_saved_selection_channels import (
        SavedSelectionChannel,
        combine_saved_selection_mask,
        load_saved_selection_mask,
        normalize_saved_selection_channels,
    )

    saved = _mask([0, 64, 128, 255])
    incoming = _mask([255, 128, 64, 0])
    assert _values(combine_saved_selection_mask(saved, incoming, "replace")) == [
        255, 128, 64, 0,
    ]
    assert _values(combine_saved_selection_mask(saved, incoming, "add")) == [
        255, 128, 128, 255,
    ]
    assert _values(combine_saved_selection_mask(saved, incoming, "subtract")) == [
        0, 0, 64, 255,
    ]
    assert _values(combine_saved_selection_mask(saved, incoming, "intersect")) == [
        0, 64, 64, 0,
    ]
    assert _values(load_saved_selection_mask(None, saved, "new", invert=True)) == [
        255, 191, 127, 0,
    ]
    with pytest.raises(ValueError, match="duplicated"):
        normalize_saved_selection_channels(
            [
                SavedSelectionChannel("saved-selection-1", "Edges", saved),
                SavedSelectionChannel("saved-selection-1", "Other", incoming),
            ],
            4,
            1,
        )
    with pytest.raises(ValueError, match="dimensions must match"):
        normalize_saved_selection_channels(
            [SavedSelectionChannel("saved-selection-1", "Edges", saved)],
            8,
            1,
        )


def test_saved_selection_channel_action_undo_and_v4_round_trip(tmp_path) -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 1, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    active_layer_id = dialog._active_paint_layer_id
    assert dialog.save_selection_channel_btn.isEnabled()
    assert not dialog.load_selection_channel_btn.isEnabled()
    first = _mask([0, 64, 128, 255, 0, 64, 128, 255])
    dialog._selection_pixel_mask = QImage(first)
    dialog.canvas.set_selection_pixel_mask(first)
    saved = registry.execute(
        "paint.selection.save_channel",
        {"name": "Edge softness", "operation": "new"},
    ).to_dict()
    assert saved["ok"]
    channel_id = saved["result"]["saved_selection_channel_id"]
    assert channel_id == "saved-selection-1"
    assert saved["result"]["saved_selection_channels"] == [{
        "channel_id": channel_id,
        "name": "Edge softness",
        "width": 8,
        "height": 1,
        "format": "Alpha8",
        "display_mode": "masked_areas",
        "overlay_color": "#ff0000",
        "overlay_opacity_percent": 50,
    }]
    assert _values(dialog._saved_selection_channels[0].mask) == _values(first)
    assert dialog._saved_selection_channel_serial == 1
    assert dialog.load_selection_channel_btn.isEnabled()
    assert dialog._active_paint_layer_id == active_layer_id
    assert any(
        dialog._channel_list.item(index).data(Qt.ItemDataRole.UserRole) == channel_id
        for index in range(dialog._channel_list.count())
    )
    dialog._undo()
    assert dialog._saved_selection_channels == []
    assert dialog._saved_selection_channel_serial == 0
    dialog._redo()
    assert dialog._saved_selection_channels[0].channel_id == channel_id
    assert dialog._saved_selection_channel_serial == 1

    second = _mask([255, 128, 64, 0, 255, 128, 64, 0])
    dialog._selection_pixel_mask = QImage(second)
    dialog.canvas.set_selection_pixel_mask(second)
    updated = registry.execute(
        "paint.selection.save_channel",
        {"channel_id": channel_id, "operation": "intersect"},
    ).to_dict()
    assert updated["ok"]
    assert _values(dialog._saved_selection_channels[0].mask) == [
        0, 64, 64, 0, 0, 64, 64, 0,
    ]
    assert dialog._active_paint_layer_id == active_layer_id

    before_invalid = QImage(dialog._saved_selection_channels[0].mask)
    undo_before_invalid = len(dialog._undo_stack)
    invalid = registry.execute(
        "paint.selection.save_channel",
        {"name": "", "operation": "new"},
    ).to_dict()
    assert not invalid["ok"]
    assert dialog._saved_selection_channels[0].mask == before_invalid
    assert len(dialog._undo_stack) == undo_before_invalid

    empty_selection = _mask([0] * 8)
    dialog._selection_pixel_mask = QImage(empty_selection)
    dialog.canvas.set_selection_pixel_mask(empty_selection)
    empty_save = registry.execute(
        "paint.selection.save_channel",
        {"name": "Empty", "operation": "new"},
    ).to_dict()
    assert not empty_save["ok"]
    assert len(dialog._saved_selection_channels) == 1
    assert len(dialog._undo_stack) == undo_before_invalid

    dialog._selection_pixel_mask = None
    dialog.canvas.clear_selection()
    loaded = registry.execute(
        "paint.selection.load_channel",
        {"channel_id": channel_id, "operation": "new", "invert": True},
    ).to_dict()
    assert loaded["ok"]
    assert _values(dialog._selection_pixel_mask) == [
        255, 191, 191, 255, 255, 191, 191, 255,
    ]
    assert dialog._active_paint_layer_id == active_layer_id
    dialog._undo()
    assert dialog._selection_pixel_mask is None
    dialog._redo()
    assert _values(dialog._selection_pixel_mask) == [
        255, 191, 191, 255, 255, 191, 191, 255,
    ]

    output = tmp_path / "saved-selection-channel.tspaint"
    dialog.save_document_to_path(output)
    with zipfile.ZipFile(output, "r") as archive:
        stored = json.loads(archive.read("document.json"))
        assert stored["schema"] == "tigerstudio.painter.document.v5"
        assert stored["format_version"] == 5
        row = stored["channels"]["saved_selection_channels"][0]
        assert row["channel_id"] == channel_id
        assert row["name"] == "Edge softness"
        assert row["mask_asset"].startswith(
            "asset://assets/selection-channels/"
        )
        assert row["mask_asset"].removeprefix("asset://") in archive.namelist()

    restored = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 1, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    report = restored.open_document_from_path(output)
    assert report["format_version"] == 5
    assert restored._saved_selection_channel_serial == 1
    assert restored._saved_selection_channels[0].channel_id == channel_id
    assert restored._saved_selection_channels[0].name == "Edge softness"
    assert restored._saved_selection_channels[0].mask == before_invalid
    assert restored._selected_channel == channel_id

    corrupt = tmp_path / "saved-selection-channel-invalid-serial.tspaint"
    with zipfile.ZipFile(output, "r") as archive:
        original_entries = {
            name: archive.read(name) for name in archive.namelist()
        }
    entries = dict(original_entries)
    corrupt_document = json.loads(entries["document.json"])
    corrupt_document["channels"]["saved_selection_channels"][0][
        "channel_id"
    ] = "saved-selection-7"
    entries["document.json"] = json.dumps(
        corrupt_document,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    _write_archive(corrupt, entries)

    before_corrupt_mask = QImage(restored._saved_selection_channels[0].mask)
    before_corrupt_undo = len(restored._undo_stack)
    restored._output_settings = dict(restored._output_settings)
    restored._output_settings["ppi"] = 96.0
    before_corrupt_output_settings = dict(restored._output_settings)
    with pytest.raises(ValueError, match="serial is inconsistent"):
        restored.open_document_from_path(corrupt)
    assert restored._saved_selection_channel_serial == 1
    assert restored._saved_selection_channels[0].channel_id == channel_id
    assert restored._saved_selection_channels[0].mask == before_corrupt_mask
    assert len(restored._undo_stack) == before_corrupt_undo
    assert restored._output_settings == before_corrupt_output_settings

    duplicate_corrupt = tmp_path / "saved-selection-channel-duplicate.tspaint"
    entries = dict(original_entries)
    corrupt_document = json.loads(entries["document.json"])
    duplicate_row = dict(
        corrupt_document["channels"]["saved_selection_channels"][0]
    )
    duplicate_row["name"] = "Other edge"
    corrupt_document["channels"]["saved_selection_channels"].append(
        duplicate_row
    )
    entries["document.json"] = json.dumps(
        corrupt_document,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    _write_archive(duplicate_corrupt, entries)
    with pytest.raises(ValueError, match="duplicated"):
        restored.open_document_from_path(duplicate_corrupt)
    assert restored._saved_selection_channels[0].mask == before_corrupt_mask
    assert len(restored._undo_stack) == before_corrupt_undo
    assert restored._output_settings == before_corrupt_output_settings

    missing_corrupt = tmp_path / "saved-selection-channel-missing-mask.tspaint"
    entries = dict(original_entries)
    corrupt_document = json.loads(entries["document.json"])
    corrupt_document["channels"]["saved_selection_channels"][0][
        "mask_asset"
    ] = "asset://assets/selection-channels/missing.png"
    entries["document.json"] = json.dumps(
        corrupt_document,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    _write_archive(missing_corrupt, entries)
    with pytest.raises(ValueError, match="mask asset is missing"):
        restored.open_document_from_path(missing_corrupt)
    assert restored._saved_selection_channels[0].mask == before_corrupt_mask
    assert len(restored._undo_stack) == before_corrupt_undo
    assert restored._output_settings == before_corrupt_output_settings

    selected_corrupt = tmp_path / "saved-selection-channel-invalid-selected.tspaint"
    entries = dict(original_entries)
    corrupt_document = json.loads(entries["document.json"])
    corrupt_document["channels"]["selected"] = "saved-selection-9"
    entries["document.json"] = json.dumps(
        corrupt_document,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    _write_archive(selected_corrupt, entries)
    with pytest.raises(ValueError, match="channel does not exist"):
        restored.open_document_from_path(selected_corrupt)
    assert restored._saved_selection_channels[0].mask == before_corrupt_mask
    assert len(restored._undo_stack) == before_corrupt_undo
    assert restored._output_settings == before_corrupt_output_settings

    dimension_corrupt = tmp_path / "saved-selection-channel-invalid-size.tspaint"
    entries = dict(original_entries)
    corrupt_document = json.loads(entries["document.json"])
    channel_entry = corrupt_document["channels"]["saved_selection_channels"][0][
        "mask_asset"
    ].removeprefix("asset://")
    short_mask_path = tmp_path / "short-mask.png"
    assert _mask([0, 64, 128, 255]).save(str(short_mask_path), "PNG")
    entries[channel_entry] = short_mask_path.read_bytes()
    for manifest_row in corrupt_document["asset_manifest"]:
        if manifest_row.get("entry") == channel_entry:
            manifest_row["size"] = len(entries[channel_entry])
            manifest_row["sha256"] = hashlib.sha256(
                entries[channel_entry]
            ).hexdigest()
            break
    entries["document.json"] = json.dumps(
        corrupt_document,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    _write_archive(dimension_corrupt, entries)
    with pytest.raises(ValueError, match="dimensions must match"):
        restored.open_document_from_path(dimension_corrupt)
    assert restored._saved_selection_channel_serial == 1
    assert restored._saved_selection_channels[0].channel_id == channel_id
    assert restored._saved_selection_channels[0].mask == before_corrupt_mask
    assert len(restored._undo_stack) == before_corrupt_undo
    assert restored._output_settings == before_corrupt_output_settings
    restored.close()
    dialog.close()
    app.processEvents()


def test_saved_selection_channel_direct_edit_visibility_and_view_contract(
    tmp_path,
) -> None:
    app = _app()
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap
    from app.painter_saved_selection_channels import (
        saved_selection_channel_view_image,
    )

    source = _mask([0, 64, 128, 255])
    grayscale = saved_selection_channel_view_image(
        source,
        4,
        1,
        composite_visible=False,
    )
    assert [grayscale.pixelColor(x, 0).red() for x in range(4)] == [
        0,
        64,
        128,
        255,
    ]
    overlay = saved_selection_channel_view_image(
        source,
        4,
        1,
        composite_visible=True,
    )
    assert overlay.pixelColor(0, 0).alpha() == 128
    assert overlay.pixelColor(3, 0).alpha() == 0

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "#203040"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    dialog.canvas.select_rectangle(0.0, 0.0, 0.5, 1.0)
    initial_selection = dialog._sync_pixel_selection_from_canvas()
    assert initial_selection is not None
    dialog._selection_pixel_mask = QImage(initial_selection)
    channel_id = dialog._save_selection_channel(name="Editable", operation="new")
    layer_before = dialog._paint_layer_raster(
        dialog._active_paint_layer_id,
        create=False,
    )
    layer_before = QImage(layer_before) if layer_before is not None else None
    selection_before = QImage(dialog._selection_pixel_mask)
    assert dialog._channel_visibility[channel_id] is False

    shown = registry.execute(
        "paint.channel.set_visible",
        {"channel": channel_id, "visible": True},
    ).to_dict()
    assert shown["ok"]
    assert dialog._channel_visibility[channel_id] is True
    assert len(dialog.canvas._saved_selection_channel_view_images) == 1
    dialog._set_selected_channel(channel_id)
    action_mask_before = QImage(dialog._saved_selection_channels[0].mask)
    action_strokes_before = dialog.canvas.embedded_strokes()
    action_undo_before = len(dialog._undo_stack)
    action_edit = registry.execute(
        "paint.stroke.draw",
        {
            "undo_label": "Edit alpha from Action",
            "strokes": [{
                "points": [
                    {"x": 0.70, "y": 0.45},
                    {"x": 0.80, "y": 0.55},
                ],
                "color": "#FFFFFF",
                "opacity": 100,
                "width": 3,
                "style": "round",
                "layer_id": dialog._active_paint_layer_id,
            }],
        },
    ).to_dict()
    assert action_edit["ok"]
    assert action_edit["result"]["stroke_draw"]["target"] == {
        "kind": "saved_selection_channel",
        "channel_id": channel_id,
    }
    assert dialog._saved_selection_channels[0].mask != action_mask_before
    assert dialog.canvas.embedded_strokes() == action_strokes_before
    assert len(dialog._undo_stack) == action_undo_before + 1
    dialog._undo()
    assert dialog._saved_selection_channels[0].mask == action_mask_before
    assert dialog.canvas.embedded_strokes() == action_strokes_before
    undo_before = len(dialog._undo_stack)

    def edit(color, *, source_tool="pen", opacity=255):
        dialog._on_stroke_added(Stroke(
            points=[(0.75, 0.5)],
            color=color,
            opacity=opacity,
            width_px=3.0,
            source_tool=source_tool,
        ))
        return dialog._saved_selection_channels[0].mask.pixelColor(6, 4).alpha()

    assert edit((255, 255, 255)) == 255
    assert edit((0, 0, 0)) == 0
    assert edit((128, 128, 128)) == 128
    assert edit((255, 255, 255), source_tool="eraser") == 0
    no_op_undo = len(dialog._undo_stack)
    assert edit((255, 255, 255), source_tool="eraser", opacity=0) == 0
    assert len(dialog._undo_stack) == no_op_undo == undo_before + 4
    dialog._undo()
    assert dialog._saved_selection_channels[0].mask.pixelColor(6, 4).alpha() == 128
    dialog._redo()
    assert dialog._saved_selection_channels[0].mask.pixelColor(6, 4).alpha() == 0
    assert dialog._selection_pixel_mask == selection_before
    assert dialog._paint_layer_raster(
        dialog._active_paint_layer_id,
        create=False,
    ) == layer_before
    assert dialog.canvas.embedded_strokes() == []
    wrong_size_clipboard = QImage(4, 4, QImage.Format.Format_ARGB32)
    wrong_size_clipboard.fill(QColor("#FFFFFF"))
    QApplication.clipboard().setImage(wrong_size_clipboard)
    dialog._set_selected_channel("RGB")
    paste_undo_before = len(dialog._undo_stack)
    paste_mask_before = QImage(dialog._saved_selection_channels[0].mask)
    assert not dialog._paste_channel_image(channel_id)
    assert len(dialog._undo_stack) == paste_undo_before
    assert dialog._saved_selection_channels[0].mask == paste_mask_before
    assert dialog._selected_channel == "RGB"
    dialog._set_selected_channel(channel_id)

    output = tmp_path / "saved-selection-direct-edit.tspaint"
    dialog.save_document_to_path(output)
    restored = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    restored.open_document_from_path(output)
    assert restored._selected_channel == channel_id
    assert restored._channel_visibility[channel_id] is True
    assert len(restored.canvas._saved_selection_channel_view_images) == 1
    assert restored._saved_selection_channels[0].mask.pixelColor(6, 4).alpha() == 0

    with zipfile.ZipFile(output, "r") as archive:
        original_entries = {
            name: archive.read(name) for name in archive.namelist()
        }
    before_invalid_mask = QImage(restored._saved_selection_channels[0].mask)
    before_invalid_visibility = dict(restored._channel_visibility)
    before_invalid_undo = len(restored._undo_stack)
    for suffix, visibility, message in (
        ("unknown", {"RGB": True, "mystery": True}, "visibility entry is invalid"),
        ("coerced", {"RGB": True, channel_id: 1}, "visibility entry is invalid"),
        ("array", [], "visibility must be an object"),
        ("string", "", "visibility must be an object"),
        ("zero", 0, "visibility must be an object"),
        ("null", None, "visibility must be an object"),
    ):
        corrupt = tmp_path / f"saved-selection-visibility-{suffix}.tspaint"
        entries = dict(original_entries)
        document = json.loads(entries["document.json"])
        document["channels"]["visibility"] = visibility
        entries["document.json"] = json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        _write_archive(corrupt, entries)
        with pytest.raises(ValueError, match=message):
            restored.open_document_from_path(corrupt)
        assert restored._saved_selection_channels[0].mask == before_invalid_mask
        assert restored._channel_visibility == before_invalid_visibility
        assert len(restored._undo_stack) == before_invalid_undo
    restored.close()
    dialog.close()
    app.processEvents()


def test_saved_selection_channel_mouse_eraser_emits_channel_stroke() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from app.drawing import DrawingCanvas

    canvas = DrawingCanvas(get_time_ms=lambda: 0, get_strokes=lambda: [])
    canvas.setFixedSize(64, 64)
    canvas.set_document_size(64, 64)
    canvas.set_saved_selection_channel_edit_enabled(True)
    canvas.set_tool("eraser")
    emitted = []
    erased = []
    canvas.stroke_added.connect(emitted.append)
    canvas.stroke_erased_at.connect(erased.append)
    canvas.show()
    app.processEvents()
    QTest.mousePress(
        canvas,
        Qt.MouseButton.LeftButton,
        pos=QPoint(20, 20),
    )
    QTest.mouseMove(canvas, QPoint(36, 36), delay=1)
    QTest.mouseRelease(
        canvas,
        Qt.MouseButton.LeftButton,
        pos=QPoint(36, 36),
    )
    app.processEvents()
    assert len(emitted) == 1
    assert emitted[0].source_tool == "eraser"
    assert len(emitted[0].points) >= 2
    assert erased == []
    canvas.close()


def test_saved_selection_channel_options_selected_areas_and_v5_migration(
    tmp_path,
    monkeypatch,
) -> None:
    app = _app()
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QColorDialog, QInputDialog
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap
    from app.painter_saved_selection_channels import (
        SavedSelectionChannel,
        duplicate_saved_selection_channel,
        rename_saved_selection_channel,
        saved_selection_channel_view_image,
        set_saved_selection_channel_options,
    )

    source = _mask([0, 64, 128, 255])
    configured = set_saved_selection_channel_options(
        [SavedSelectionChannel("saved-selection-1", "Options", source)],
        "saved-selection-1",
        display_mode="selected_areas",
        overlay_color="#00FF00",
        overlay_opacity_percent=25,
    )[0]
    assert configured.mask == source
    assert configured.display_mode == "selected_areas"
    assert configured.overlay_color == "#00ff00"
    assert configured.overlay_opacity_percent == 25
    renamed = rename_saved_selection_channel(
        [configured],
        "saved-selection-1",
        "Renamed Options",
    )[0]
    duplicated = duplicate_saved_selection_channel(
        [renamed],
        "saved-selection-1",
        "saved-selection-2",
        "Options copy",
    )[1]
    assert renamed.mask == source
    assert duplicated.mask == source
    assert (
        renamed.display_mode,
        renamed.overlay_color,
        renamed.overlay_opacity_percent,
    ) == ("selected_areas", "#00ff00", 25)
    assert (
        duplicated.display_mode,
        duplicated.overlay_color,
        duplicated.overlay_opacity_percent,
    ) == ("selected_areas", "#00ff00", 25)
    grayscale = saved_selection_channel_view_image(
        configured.mask,
        4,
        1,
        composite_visible=False,
        display_mode=configured.display_mode,
        overlay_color=configured.overlay_color,
        overlay_opacity_percent=configured.overlay_opacity_percent,
    )
    assert [grayscale.pixelColor(x, 0).red() for x in range(4)] == [
        255,
        191,
        127,
        0,
    ]
    overlay = saved_selection_channel_view_image(
        configured.mask,
        4,
        1,
        composite_visible=True,
        display_mode=configured.display_mode,
        overlay_color=configured.overlay_color,
        overlay_opacity_percent=configured.overlay_opacity_percent,
    )
    assert overlay.pixelColor(0, 0).alpha() == 0
    assert overlay.pixelColor(3, 0).getRgb() == (0, 255, 0, 64)

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "#203040"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    dialog.canvas.select_rectangle(0.0, 0.0, 0.5, 1.0)
    dialog._selection_pixel_mask = dialog._sync_pixel_selection_from_canvas()
    channel_id = dialog._save_selection_channel(name="Options", operation="new")
    mask_before_options = QImage(dialog._saved_selection_channels[0].mask)
    undo_before = len(dialog._undo_stack)
    changed = registry.execute(
        "paint.selection.channel.options.set",
        {
            "channel_id": channel_id,
            "display_mode": "selected_areas",
            "overlay_color": "#00FF00",
            "overlay_opacity_percent": 25,
        },
    ).to_dict()
    assert changed["ok"]
    assert len(dialog._undo_stack) == undo_before + 1
    row = dialog._saved_selection_channels[0]
    assert row.mask == mask_before_options
    assert (
        row.display_mode,
        row.overlay_color,
        row.overlay_opacity_percent,
    ) == ("selected_areas", "#00ff00", 25)
    assert dialog.options_selection_channel_btn.isEnabled()
    no_op_undo = len(dialog._undo_stack)
    no_op = registry.execute(
        "paint.selection.channel.options.set",
        {
            "channel_id": channel_id,
            "display_mode": "selected_areas",
            "overlay_color": "#00ff00",
            "overlay_opacity_percent": 25,
        },
    ).to_dict()
    assert not no_op["ok"]
    assert "would not change" in str(no_op.get("error") or "")
    assert len(dialog._undo_stack) == no_op_undo
    dialog._set_selected_channel("RGB")
    assert not dialog.options_selection_channel_btn.isEnabled()
    dialog._set_selected_channel(channel_id)
    prompt_undo = len(dialog._undo_stack)
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        lambda *args, **kwargs: ("Selected Areas", True),
    )
    monkeypatch.setattr(
        QColorDialog,
        "getColor",
        lambda *args, **kwargs: QColor("#00ff00"),
    )
    monkeypatch.setattr(
        QInputDialog,
        "getInt",
        lambda *args, **kwargs: (25, True),
    )
    assert dialog._prompt_saved_selection_channel_options() is False
    assert len(dialog._undo_stack) == prompt_undo
    dialog._undo()
    assert dialog._saved_selection_channels[0].display_mode == "masked_areas"
    dialog._redo()
    assert dialog._saved_selection_channels[0].display_mode == "selected_areas"

    dialog._set_selected_channel(channel_id)

    def edit(color):
        dialog._on_stroke_added(Stroke(
            points=[(0.75, 0.5)],
            color=color,
            opacity=255,
            width_px=3.0,
            source_tool="pen",
        ))
        return dialog._saved_selection_channels[0].mask.pixelColor(6, 4).alpha()

    assert edit((0, 0, 0)) == 255
    assert edit((255, 255, 255)) == 0

    output = tmp_path / "saved-selection-options-v5.tspaint"
    dialog.save_document_to_path(output)
    with zipfile.ZipFile(output, "r") as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    stored = json.loads(entries["document.json"])
    assert stored["schema"] == "tigerstudio.painter.document.v5"
    assert stored["format_version"] == 5
    stored_row = stored["channels"]["saved_selection_channels"][0]
    assert (
        stored_row["display_mode"],
        stored_row["overlay_color"],
        stored_row["overlay_opacity_percent"],
    ) == ("selected_areas", "#00ff00", 25)

    restored = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    restored.open_document_from_path(output)
    restored_row = restored._saved_selection_channels[0]
    assert (
        restored_row.display_mode,
        restored_row.overlay_color,
        restored_row.overlay_opacity_percent,
    ) == ("selected_areas", "#00ff00", 25)

    before_invalid_row = restored._saved_selection_channels[0]
    before_invalid_mask = QImage(before_invalid_row.mask)
    before_invalid_options = (
        before_invalid_row.display_mode,
        before_invalid_row.overlay_color,
        before_invalid_row.overlay_opacity_percent,
    )
    before_invalid_undo = len(restored._undo_stack)
    for suffix, mutate, message in (
        (
            "missing",
            lambda row: row.pop("display_mode"),
            "options are missing",
        ),
        (
            "mode",
            lambda row: row.__setitem__("display_mode", "unknown"),
            "display mode is unsupported",
        ),
        (
            "color",
            lambda row: row.__setitem__("overlay_color", "green"),
            "must be #RRGGBB",
        ),
        (
            "bool-opacity",
            lambda row: row.__setitem__("overlay_opacity_percent", True),
            "must be an integer",
        ),
        (
            "range-opacity",
            lambda row: row.__setitem__("overlay_opacity_percent", 101),
            "from 0 through 100",
        ),
    ):
        corrupt = tmp_path / f"saved-selection-options-v5-{suffix}.tspaint"
        corrupt_entries = dict(entries)
        corrupt_document = json.loads(corrupt_entries["document.json"])
        mutate(corrupt_document["channels"]["saved_selection_channels"][0])
        corrupt_entries["document.json"] = json.dumps(
            corrupt_document,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        _write_archive(corrupt, corrupt_entries)
        with pytest.raises((TypeError, ValueError), match=message):
            restored.open_document_from_path(corrupt)
        current = restored._saved_selection_channels[0]
        assert current.mask == before_invalid_mask
        assert (
            current.display_mode,
            current.overlay_color,
            current.overlay_opacity_percent,
        ) == before_invalid_options
        assert len(restored._undo_stack) == before_invalid_undo

    for suffix, invalid_collection in (
        ("object-collection", {}),
        ("string-collection", ""),
        ("number-collection", 0),
        ("null-collection", None),
    ):
        corrupt = tmp_path / f"saved-selection-options-v5-{suffix}.tspaint"
        corrupt_entries = dict(entries)
        corrupt_document = json.loads(corrupt_entries["document.json"])
        corrupt_document["channels"]["saved_selection_channels"] = (
            invalid_collection
        )
        corrupt_entries["document.json"] = json.dumps(
            corrupt_document,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        _write_archive(corrupt, corrupt_entries)
        with pytest.raises(
            ValueError,
            match="saved selection channels must be a list",
        ):
            restored.open_document_from_path(corrupt)
        current = restored._saved_selection_channels[0]
        assert current.mask == before_invalid_mask
        assert (
            current.display_mode,
            current.overlay_color,
            current.overlay_opacity_percent,
        ) == before_invalid_options
        assert len(restored._undo_stack) == before_invalid_undo

    missing_serial = tmp_path / "saved-selection-options-v5-missing-serial.tspaint"
    missing_serial_entries = dict(entries)
    missing_serial_document = json.loads(missing_serial_entries["document.json"])
    missing_serial_document["channels"].pop("saved_selection_channel_serial")
    missing_serial_entries["document.json"] = json.dumps(
        missing_serial_document,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    _write_archive(missing_serial, missing_serial_entries)
    with pytest.raises(ValueError, match="channel serial is missing"):
        restored.open_document_from_path(missing_serial)
    assert restored._saved_selection_channels[0].mask == before_invalid_mask
    assert len(restored._undo_stack) == before_invalid_undo

    legacy = tmp_path / "saved-selection-options-v4.tspaint"
    legacy_entries = dict(entries)
    legacy_document = json.loads(legacy_entries["document.json"])
    legacy_document["schema"] = "tigerstudio.painter.document.v4"
    legacy_document["format_version"] = 4
    legacy_row = legacy_document["channels"]["saved_selection_channels"][0]
    legacy_row.pop("display_mode")
    legacy_row.pop("overlay_color")
    legacy_row.pop("overlay_opacity_percent")
    legacy_entries["document.json"] = json.dumps(
        legacy_document,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    _write_archive(legacy, legacy_entries)
    restored.open_document_from_path(legacy)
    migrated = restored._saved_selection_channels[0]
    assert (
        migrated.display_mode,
        migrated.overlay_color,
        migrated.overlay_opacity_percent,
    ) == ("masked_areas", "#ff0000", 50)
    restored.close()
    dialog.close()
    app.processEvents()


def test_saved_selection_channel_lifecycle_actions_and_round_trip(tmp_path) -> None:
    app = _app()
    from PySide6.QtGui import QImage
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_saved_selection_channels import (
        SavedSelectionChannel,
        delete_saved_selection_channel,
        duplicate_saved_selection_channel,
        rename_saved_selection_channel,
        reorder_saved_selection_channel,
    )

    source_mask = _mask([0, 64, 128, 255])
    pure_rows = [SavedSelectionChannel("saved-selection-1", "Edges", source_mask)]
    renamed = rename_saved_selection_channel(
        pure_rows,
        "saved-selection-1",
        "Contour",
    )
    assert renamed[0].channel_id == "saved-selection-1"
    assert _values(renamed[0].mask) == [0, 64, 128, 255]
    duplicated = duplicate_saved_selection_channel(
        renamed,
        "saved-selection-1",
        "saved-selection-2",
        "Contour inverted",
        invert=True,
    )
    assert [row.channel_id for row in duplicated] == [
        "saved-selection-1",
        "saved-selection-2",
    ]
    assert _values(duplicated[1].mask) == [255, 191, 127, 0]
    with pytest.raises(TypeError, match="boolean"):
        duplicate_saved_selection_channel(
            renamed,
            "saved-selection-1",
            "saved-selection-3",
            "Invalid",
            invert=1,  # type: ignore[arg-type]
        )
    duplicated[1].mask.fill(0)
    assert _values(duplicated[0].mask) == [0, 64, 128, 255]
    reordered = reorder_saved_selection_channel(
        duplicated,
        "saved-selection-2",
        "saved-selection-1",
        "before",
    )
    assert [row.channel_id for row in reordered] == [
        "saved-selection-2",
        "saved-selection-1",
    ]
    remaining, fallback = delete_saved_selection_channel(
        reordered,
        "saved-selection-2",
    )
    assert [row.channel_id for row in remaining] == ["saved-selection-1"]
    assert fallback == "saved-selection-1"

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(4, 1, "#203040"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    dialog._selection_pixel_mask = QImage(source_mask)
    dialog.canvas.set_selection_pixel_mask(source_mask)
    active_layer_id = dialog._active_paint_layer_id
    background_before = dialog._bg_pixmap_source.toImage()
    selection_before = QImage(dialog._selection_pixel_mask)
    for button in (
        dialog.duplicate_selection_channel_btn,
        dialog.move_selection_channel_up_btn,
        dialog.move_selection_channel_down_btn,
        dialog.delete_selection_channel_btn,
    ):
        assert not button.isEnabled()

    first = registry.execute(
        "paint.selection.save_channel",
        {"name": "Edges", "operation": "new"},
    ).to_dict()
    assert first["ok"]
    first_id = first["result"]["saved_selection_channel_id"]
    assert dialog.duplicate_selection_channel_btn.isEnabled()
    assert dialog.delete_selection_channel_btn.isEnabled()
    assert not dialog.move_selection_channel_up_btn.isEnabled()
    assert not dialog.move_selection_channel_down_btn.isEnabled()
    second = registry.execute(
        "paint.selection.channel.duplicate",
        {"channel_id": first_id, "name": "Edges inverted", "invert": True},
    ).to_dict()
    assert second["ok"]
    second_id = second["result"]["saved_selection_channel_id"]
    assert dialog._saved_selection_channel_serial == 2
    dialog._undo()
    assert [row.channel_id for row in dialog._saved_selection_channels] == [first_id]
    assert dialog._saved_selection_channel_serial == 1
    dialog._redo()
    assert [row.channel_id for row in dialog._saved_selection_channels] == [
        first_id,
        second_id,
    ]
    assert dialog._saved_selection_channel_serial == 2
    third = registry.execute(
        "paint.selection.channel.duplicate",
        {"channel_id": first_id, "name": "Edges copy"},
    ).to_dict()
    assert third["ok"]
    third_id = third["result"]["saved_selection_channel_id"]
    assert dialog.move_selection_channel_up_btn.isEnabled()
    assert not dialog.move_selection_channel_down_btn.isEnabled()
    dialog._set_selected_channel(first_id)
    assert not dialog.move_selection_channel_up_btn.isEnabled()
    assert dialog.move_selection_channel_down_btn.isEnabled()
    dialog._set_selected_channel("RGB")
    assert not dialog.duplicate_selection_channel_btn.isEnabled()
    assert not dialog.delete_selection_channel_btn.isEnabled()
    dialog._set_selected_channel(third_id)
    assert [row.channel_id for row in dialog._saved_selection_channels] == [
        first_id,
        second_id,
        third_id,
    ]
    assert _values(dialog._saved_selection_channels[1].mask) == [255, 191, 127, 0]

    reordered_action = registry.execute(
        "paint.selection.channel.reorder",
        {
            "channel_id": third_id,
            "target_channel_id": second_id,
            "placement": "before",
        },
    ).to_dict()
    assert reordered_action["ok"]
    assert [row.channel_id for row in dialog._saved_selection_channels] == [
        first_id,
        third_id,
        second_id,
    ]
    dialog._undo()
    assert [row.channel_id for row in dialog._saved_selection_channels] == [
        first_id,
        second_id,
        third_id,
    ]
    dialog._redo()
    assert [row.channel_id for row in dialog._saved_selection_channels] == [
        first_id,
        third_id,
        second_id,
    ]
    renamed_action = registry.execute(
        "paint.selection.channel.rename",
        {"channel_id": third_id, "name": "Backup"},
    ).to_dict()
    assert renamed_action["ok"]
    assert dialog._saved_selection_channels[1].name == "Backup"
    dialog._undo()
    assert dialog._saved_selection_channels[1].name == "Edges copy"
    dialog._redo()
    assert dialog._saved_selection_channels[1].name == "Backup"

    deleted = registry.execute(
        "paint.selection.channel.delete",
        {"channel_id": third_id},
    ).to_dict()
    assert deleted["ok"]
    assert [row.channel_id for row in dialog._saved_selection_channels] == [
        first_id,
        second_id,
    ]
    assert dialog._selected_channel == second_id
    dialog._undo()
    assert [row.channel_id for row in dialog._saved_selection_channels] == [
        first_id,
        third_id,
        second_id,
    ]
    assert dialog._selected_channel == third_id
    dialog._redo()
    assert dialog._selected_channel == second_id

    assert dialog._active_paint_layer_id == active_layer_id
    assert dialog._bg_pixmap_source.toImage() == background_before
    assert dialog._selection_pixel_mask == selection_before
    output = tmp_path / "saved-selection-lifecycle.tspaint"
    dialog.save_document_to_path(output)
    restored = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(4, 1, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    restored.open_document_from_path(output)
    assert [
        (row.channel_id, row.name, _values(row.mask))
        for row in restored._saved_selection_channels
    ] == [
        (first_id, "Edges", [0, 64, 128, 255]),
        (second_id, "Edges inverted", [255, 191, 127, 0]),
    ]
    assert restored._selected_channel == second_id
    restored.close()
    dialog.close()
    app.processEvents()
