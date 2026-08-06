from __future__ import annotations

import copy
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _dialog(width: int = 8, height: int = 8, *, standalone: bool = True):
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(
            width,
            height,
            "transparent",
        ),
        initial_strokes=[],
        time_ms=0,
        standalone=standalone,
    )
    dialog.show()
    _app().processEvents()
    return dialog


def _set_left_half_selection(dialog) -> None:
    dialog.canvas.select_rectangle(0.0, 0.0, 0.5, 1.0)
    dialog._selection_pixel_mask = dialog._sync_pixel_selection_from_canvas()


def test_open_document_identity_and_cross_document_save_load_atomicity() -> None:
    _app()
    from PySide6.QtGui import QImage
    from app.actions.registry import ActionRegistry
    from app.painter_open_documents import inspect_open_painter_documents

    source = _dialog()
    destination = _dialog()
    mismatch = _dialog(9, 8)
    try:
        source_id = source._painter_runtime_document_id
        destination_id = destination._painter_runtime_document_id
        mismatch_id = mismatch._painter_runtime_document_id
        assert source_id != destination_id != mismatch_id
        inspected = inspect_open_painter_documents()
        indexed = {row["document_id"]: row for row in inspected["documents"]}
        assert indexed[source_id]["width"] == 8
        assert indexed[destination_id]["height"] == 8

        _set_left_half_selection(source)
        source_selection = QImage(source._selection_pixel_mask)
        source_content = (
            copy.deepcopy(source._paint_layers),
            copy.deepcopy(source.canvas._get_strokes()),
            source._background_layer_present,
            source._background_color.name(),
        )
        destination_content = (
            copy.deepcopy(destination._paint_layers),
            copy.deepcopy(destination.canvas._get_strokes()),
            destination._background_layer_present,
            destination._background_color.name(),
        )
        source_undo = len(source._undo_stack)
        destination_undo = len(destination._undo_stack)
        source_registry = ActionRegistry(owner=source)
        saved = source_registry.execute(
            "paint.selection.save_channel_to_document",
            {
                "destination_document_id": destination_id,
                "name": "From source",
                "channel_id": "",
                "operation": "new",
            },
        ).to_dict()
        assert saved["ok"]
        assert len(source._undo_stack) == source_undo
        assert len(destination._undo_stack) == destination_undo + 1
        assert source._selection_pixel_mask == source_selection
        assert len(source._saved_selection_channels) == 0
        assert len(destination._saved_selection_channels) == 1
        transferred = destination._saved_selection_channels[0]
        assert transferred.mask == source_selection
        assert transferred.name == "From source"
        assert transferred.display_mode == "masked_areas"
        assert (
            source._paint_layers,
            source.canvas._get_strokes(),
            source._background_layer_present,
            source._background_color.name(),
        ) == source_content
        assert (
            destination._paint_layers,
            destination.canvas._get_strokes(),
            destination._background_layer_present,
            destination._background_color.name(),
        ) == destination_content
        assert saved["result"]["source"]["document_id"] == source_id
        assert saved["result"]["destination"]["document_id"] == destination_id

        before_mismatch_source = len(source._undo_stack)
        before_mismatch_destination = len(mismatch._undo_stack)
        failed = source_registry.execute(
            "paint.selection.save_channel_to_document",
            {
                "destination_document_id": mismatch_id,
                "name": "Wrong size",
                "channel_id": "",
                "operation": "new",
            },
        ).to_dict()
        assert not failed["ok"]
        assert "identical pixel dimensions" in str(failed.get("error") or "")
        assert len(source._undo_stack) == before_mismatch_source
        assert len(mismatch._undo_stack) == before_mismatch_destination
        assert mismatch._saved_selection_channels == []

        source.canvas.clear_selection()
        source._selection_pixel_mask = None
        source_selected_channel = source._selected_channel
        load_undo = len(source._undo_stack)
        loaded = source_registry.execute(
            "paint.selection.load_channel_from_document",
            {
                "source_document_id": destination_id,
                "channel_id": transferred.channel_id,
                "operation": "new",
                "invert": False,
            },
        ).to_dict()
        assert loaded["ok"]
        assert source._selection_pixel_mask == source_selection
        assert source._selected_channel == source_selected_channel
        assert len(source._undo_stack) == load_undo + 1
        assert len(destination._undo_stack) == destination_undo + 1
        assert (
            source._paint_layers,
            source.canvas._get_strokes(),
            source._background_layer_present,
            source._background_color.name(),
        ) == source_content
        assert (
            destination._paint_layers,
            destination.canvas._get_strokes(),
            destination._background_layer_present,
            destination._background_color.name(),
        ) == destination_content
        source._undo()
        assert source._selection_pixel_mask is None
        source._redo()
        assert source._selection_pixel_mask == source_selection
    finally:
        source.close()
        destination.close()
        mismatch.close()


def test_cross_document_existing_channel_update_and_invalid_identity() -> None:
    _app()
    from PySide6.QtGui import QImage
    from app.actions.registry import ActionRegistry

    source = _dialog()
    destination = _dialog()
    try:
        _set_left_half_selection(destination)
        target_id = destination._save_selection_channel(
            name="Existing",
            operation="new",
        )
        before_options = destination._saved_selection_channels[0]
        destination._set_saved_selection_channel_options(
            target_id,
            display_mode="selected_areas",
            overlay_color="#123456",
            overlay_opacity_percent=75,
        )
        _set_left_half_selection(source)
        source.canvas.select_rectangle(0.5, 0.0, 0.5, 1.0)
        source._selection_pixel_mask = source._sync_pixel_selection_from_canvas()
        incoming = QImage(source._selection_pixel_mask)
        registry = ActionRegistry(owner=source)
        destination_undo = len(destination._undo_stack)
        updated = registry.execute(
            "paint.selection.save_channel_to_document",
            {
                "destination_document_id": destination._painter_runtime_document_id,
                "name": "",
                "channel_id": target_id,
                "operation": "replace",
            },
        ).to_dict()
        assert updated["ok"]
        row = destination._saved_selection_channels[0]
        assert row.mask == incoming
        assert row.name == before_options.name
        assert (
            row.display_mode,
            row.overlay_color,
            row.overlay_opacity_percent,
        ) == ("selected_areas", "#123456", 75)
        assert len(destination._undo_stack) == destination_undo + 1

        before_source_undo = len(source._undo_stack)
        invalid = registry.execute(
            "paint.selection.save_channel_to_document",
            {
                "destination_document_id": "painter-document-xyz",
                "name": "Invalid",
                "channel_id": "",
                "operation": "new",
            },
        ).to_dict()
        assert not invalid["ok"]
        assert len(source._undo_stack) == before_source_undo
    finally:
        source.close()
        destination.close()


def test_cross_document_save_and_load_ui_document_choosers(monkeypatch) -> None:
    app = _app()
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QInputDialog

    source = _dialog()
    channel_owner = _dialog()
    receiver = _dialog()
    try:
        _set_left_half_selection(source)
        expected = QImage(source._selection_pixel_mask)
        owner_suffix = channel_owner._painter_runtime_document_id[-8:]
        monkeypatch.setattr(
            QInputDialog,
            "getText",
            lambda *args, **kwargs: ("UI transfer", True),
        )

        def choose_destination(*args, **kwargs):
            items = list(args[3])
            return next(row for row in items if owner_suffix in row), True

        monkeypatch.setattr(QInputDialog, "getItem", choose_destination)
        owner_undo = len(channel_owner._undo_stack)
        assert source._prompt_save_selection_channel() is True
        assert len(channel_owner._undo_stack) == owner_undo + 1
        assert channel_owner._saved_selection_channels[0].mask == expected

        receiver._set_selected_channel("RGB")
        receiver._sync_saved_selection_channel_controls("RGB")
        assert receiver.load_selection_channel_btn.isEnabled()
        source_suffix = channel_owner._painter_runtime_document_id[-8:]

        def choose_source(*args, **kwargs):
            items = list(args[3])
            return next(row for row in items if source_suffix in row), True

        monkeypatch.setattr(QInputDialog, "getItem", choose_source)
        receiver_undo = len(receiver._undo_stack)
        loaded = receiver._load_selected_selection_channel()
        assert loaded is True, receiver._tool_status_label.text()
        assert receiver._selection_pixel_mask == expected
        assert receiver._selected_channel == "RGB"
        assert len(receiver._undo_stack) == receiver_undo + 1
    finally:
        source.close()
        channel_owner.close()
        receiver.close()
        app.processEvents()


def test_runtime_document_identity_lifecycle_and_closed_document_exclusion(
    tmp_path,
) -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.painter_open_documents import inspect_open_painter_documents

    active = _dialog()
    other = _dialog()
    try:
        active_id = active._painter_runtime_document_id
        other_id = other._painter_runtime_document_id
        registry = ActionRegistry(owner=active)
        inspected = registry.execute("paint.documents.inspect", {}).to_dict()
        assert inspected["ok"]
        assert inspected["result"]["active_document_id"] == active_id
        assert {
            row["document_id"] for row in inspected["result"]["documents"]
        } >= {active_id, other_id}
        state = active.painter_action_state()
        assert state["document"]["runtime_document_id"] == active_id
        assert state["document"]["native_format"] == "tigerstudio.painter.document.v5"

        path = tmp_path / "identity.tspaint"
        active.save_document_to_path(path)
        assert active._painter_runtime_document_id == active_id
        active.open_document_from_path(path)
        reopened_id = active._painter_runtime_document_id
        assert reopened_id != active_id

        other.close()
        app.processEvents()
        current_ids = {
            row["document_id"]
            for row in inspect_open_painter_documents()["documents"]
        }
        assert other_id not in current_ids
        assert reopened_id in current_ids
    finally:
        active.close()
        other.close()
        app.processEvents()


def test_cross_document_rejects_same_document_and_no_change_without_undo() -> None:
    _app()
    from app.actions.registry import ActionRegistry

    source = _dialog()
    destination = _dialog()
    try:
        _set_left_half_selection(source)
        _set_left_half_selection(destination)
        target_id = destination._save_selection_channel(
            name="Unchanged",
            operation="new",
        )
        registry = ActionRegistry(owner=source)

        source_undo = len(source._undo_stack)
        same_document = registry.execute(
            "paint.selection.save_channel_to_document",
            {
                "destination_document_id": source._painter_runtime_document_id,
                "name": "Invalid",
                "channel_id": "",
                "operation": "new",
            },
        ).to_dict()
        assert not same_document["ok"]
        assert len(source._undo_stack) == source_undo

        destination_undo = len(destination._undo_stack)
        no_change = registry.execute(
            "paint.selection.save_channel_to_document",
            {
                "destination_document_id": destination._painter_runtime_document_id,
                "name": "",
                "channel_id": target_id,
                "operation": "replace",
            },
        ).to_dict()
        assert not no_change["ok"]
        assert "would not change" in str(no_change.get("error") or "")
        assert len(destination._undo_stack) == destination_undo
        assert len(source._undo_stack) == source_undo
    finally:
        source.close()
        destination.close()


def test_cross_document_rejects_embedded_closed_and_wrong_size_active_masks() -> None:
    app = _app()
    from PySide6.QtGui import QImage
    from app.actions.registry import ActionRegistry
    from app.painter_open_documents import (
        inspect_open_painter_documents,
        painter_open_document_descriptor,
    )

    source = _dialog()
    destination = _dialog()
    embedded = _dialog(standalone=False)
    try:
        inspected_ids = {
            row["document_id"]
            for row in inspect_open_painter_documents()["documents"]
        }
        assert source._painter_runtime_document_id in inspected_ids
        assert destination._painter_runtime_document_id in inspected_ids
        assert embedded._painter_runtime_document_id not in inspected_ids
        original_embedded_size = embedded._canvas_document_size
        for invalid_size in (
            (8.9, 8),
            ("8", 8),
            (True, 8),
            (8,),
            [8, 8],
            (0, 8),
        ):
            embedded._canvas_document_size = invalid_size
            with pytest.raises(ValueError, match="pixel dimensions"):
                painter_open_document_descriptor(embedded)
        embedded._canvas_document_size = original_embedded_size

        _set_left_half_selection(source)
        registry = ActionRegistry(owner=source)
        source.close()
        app.processEvents()
        destination_undo = len(destination._undo_stack)
        closed_source = registry.execute(
            "paint.selection.save_channel_to_document",
            {
                "destination_document_id": destination._painter_runtime_document_id,
                "name": "Closed source",
                "channel_id": "",
                "operation": "new",
            },
        ).to_dict()
        assert not closed_source["ok"]
        assert destination._saved_selection_channels == []
        assert len(destination._undo_stack) == destination_undo

        source.show()
        app.processEvents()
        corrupt = QImage(2, 1, QImage.Format.Format_Alpha8)
        corrupt.setPixelColor(0, 0, 0x00000000)
        corrupt.setPixelColor(1, 0, 0xFFFFFFFF)
        source._selection_pixel_mask = corrupt
        wrong_size = registry.execute(
            "paint.selection.save_channel_to_document",
            {
                "destination_document_id": destination._painter_runtime_document_id,
                "name": "Wrong-size mask",
                "channel_id": "",
                "operation": "new",
            },
        ).to_dict()
        assert not wrong_size["ok"]
        assert "must match" in str(wrong_size.get("error") or "")
        assert destination._saved_selection_channels == []
        assert len(destination._undo_stack) == destination_undo
    finally:
        source.close()
        destination.close()
        embedded.close()


def test_ui_revalidates_closed_destination_and_refreshes_load_eligibility(
    monkeypatch,
) -> None:
    app = _app()
    from PySide6.QtWidgets import QInputDialog

    source = _dialog()
    destination = _dialog()
    receiver = _dialog()
    try:
        _set_left_half_selection(source)
        monkeypatch.setattr(
            QInputDialog,
            "getText",
            lambda *args, **kwargs: ("Close race", True),
        )

        def close_chosen_destination(*args, **kwargs):
            items = list(args[3])
            chosen = next(
                row
                for row in items
                if destination._painter_runtime_document_id[-8:] in row
            )
            destination.close()
            app.processEvents()
            return chosen, True

        monkeypatch.setattr(QInputDialog, "getItem", close_chosen_destination)
        destination_undo = len(destination._undo_stack)
        assert source._prompt_save_selection_channel() is False
        assert destination._saved_selection_channels == []
        assert len(destination._undo_stack) == destination_undo

        destination.show()
        app.processEvents()
        _set_left_half_selection(destination)
        destination._save_selection_channel(name="External", operation="new")
        receiver._set_selected_channel("RGB")
        receiver._sync_saved_selection_channel_controls("RGB")
        assert receiver.load_selection_channel_btn.isEnabled()
        destination.close()
        app.processEvents()
        assert not receiver.load_selection_channel_btn.isEnabled()
    finally:
        source.close()
        destination.close()
        receiver.close()
