from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _payload(revision: int = 1) -> dict:
    from app.painter_ui_document import create_ui_document

    document = create_ui_document(390, 844)
    document["revision"] = revision
    return {
        "document": {"width": 390, "height": 844},
        "ui_document": document,
    }


def test_recovery_snapshot_round_trip_skip_and_discard(tmp_path) -> None:
    from app.painter_autosave import (
        discard_recovery_snapshot,
        list_recovery_snapshots,
        load_recovery_snapshot,
        save_recovery_snapshot,
    )

    first = save_recovery_snapshot(
        "session-a",
        _payload(),
        source_path="C:/work/design.tspaint",
        root=tmp_path,
    )
    assert first["skipped"] is False
    second = save_recovery_snapshot(
        "session-a",
        _payload(),
        source_path="C:/work/design.tspaint",
        root=tmp_path,
    )
    assert second["skipped"] is True
    rows = list_recovery_snapshots(root=tmp_path)
    assert len(rows) == 1
    loaded, report = load_recovery_snapshot(rows[0]["recovery_path"])
    assert loaded["ui_document"]["revision"] == 1
    assert report["format_version"] == 1
    assert discard_recovery_snapshot("session-a", root=tmp_path) is True
    assert list_recovery_snapshots(root=tmp_path) == []


def test_recovery_prunes_oldest_sessions(tmp_path) -> None:
    from app.painter_autosave import (
        list_recovery_snapshots,
        save_recovery_snapshot,
    )

    for index in range(3):
        save_recovery_snapshot(
            f"session-{index}",
            _payload(index + 1),
            root=tmp_path,
            keep=2,
        )
    rows = list_recovery_snapshots(root=tmp_path)
    assert len(rows) == 2
    assert {row["document_revision"] for row in rows} == {2, 3}


def test_painter_schedules_and_restores_recovery_snapshot(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    from app import painter_autosave
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    monkeypatch.setattr(
        painter_autosave,
        "runtime_data_dir",
        lambda: tmp_path,
    )
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(
            390,
            844,
            "transparent",
        ),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_recovery_timer.stop()
    dialog._painter_document_dirty = True
    scheduled = dialog._schedule_painter_recovery_snapshot(force=True)
    assert scheduled["scheduled"] is True
    saved = dialog._painter_recovery_future.result(timeout=10)
    assert saved["skipped"] is False
    rows = dialog._painter_recovery_rows()
    assert len(rows) == 1
    restored = dialog._restore_painter_recovery_snapshot(rows[0])
    assert restored["restored"] is True
    assert dialog._painter_document_path == ""
    assert dialog._painter_document_dirty is True
    from app.painter_i18n import painter_text

    assert painter_text("Recovered") in dialog.windowTitle()


def test_recovery_actions_are_registered() -> None:
    from app.actions.registry import ActionRegistry

    action_ids = {
        row["id"] for row in ActionRegistry(owner=None).list_actions()
    }
    assert {
        "paint.ui.recovery.inspect",
        "paint.ui.recovery.create",
        "paint.ui.recovery.restore",
        "paint.ui.recovery.discard",
    } <= action_ids
