from __future__ import annotations

import os
from pathlib import Path

import pytest


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
    assert report["format_version"] == 5
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


def test_truncated_recovery_archive_is_not_offered_for_restore(tmp_path) -> None:
    from app.painter_autosave import (
        inspect_recovery_archive,
        list_recovery_snapshots,
        save_recovery_snapshot,
    )

    saved = save_recovery_snapshot("truncated", _payload(), root=tmp_path)
    recovery_path = saved["recovery_path"]
    with open(recovery_path, "wb") as handle:
        handle.write(b"PK\x03\x04truncated")
    integrity = inspect_recovery_archive(recovery_path)
    assert integrity["valid"] is False
    assert list_recovery_snapshots(root=tmp_path) == []


def test_valid_but_tampered_recovery_archive_is_rewritten_not_skipped(tmp_path) -> None:
    import zipfile

    from app.painter_autosave import (
        inspect_recovery_archive,
        list_recovery_snapshots,
        save_recovery_snapshot,
    )

    first = save_recovery_snapshot("tampered", _payload(), root=tmp_path)
    archive_path = first["recovery_path"]
    with zipfile.ZipFile(archive_path, "a") as archive:
        archive.writestr("tamper-marker.txt", b"changed but structurally valid")

    integrity = inspect_recovery_archive(
        archive_path,
        expected_sha256=first["archive_sha256"],
    )
    assert integrity["valid"] is False
    assert integrity["reason"] == "archive_hash_mismatch"
    assert list_recovery_snapshots(root=tmp_path) == []

    repaired = save_recovery_snapshot("tampered", _payload(), root=tmp_path)
    assert repaired["skipped"] is False
    assert inspect_recovery_archive(
        archive_path,
        expected_sha256=repaired["archive_sha256"],
    )["valid"] is True
    assert len(list_recovery_snapshots(root=tmp_path)) == 1


def test_recovery_source_path_change_updates_manifest_and_keep_is_strict(tmp_path) -> None:
    import pytest

    from app.painter_autosave import save_recovery_snapshot

    first = save_recovery_snapshot(
        "source-change", _payload(), source_path="first.tspaint", root=tmp_path
    )
    second = save_recovery_snapshot(
        "source-change", _payload(), source_path="second.tspaint", root=tmp_path
    )
    assert first["skipped"] is False
    assert second["skipped"] is False
    assert second["source_path"] == "second.tspaint"
    with pytest.raises((TypeError, ValueError)):
        save_recovery_snapshot("bad-keep", _payload(), root=tmp_path, keep=-1)
    with pytest.raises((TypeError, ValueError)):
        save_recovery_snapshot("bad-keep", _payload(), root=tmp_path, keep=True)


def test_recovery_manifest_cannot_redirect_restore_outside_its_pair(tmp_path) -> None:
    import json

    from app.painter_autosave import list_recovery_snapshots, save_recovery_snapshot

    saved = save_recovery_snapshot("redirect", _payload(), root=tmp_path)
    manifest_path = saved["manifest_path"]
    manifest = json.loads(open(manifest_path, encoding="utf-8").read())
    manifest["recovery_path"] = str(tmp_path.parent / "outside.tspaint")
    open(manifest_path, "w", encoding="utf-8").write(json.dumps(manifest))

    assert list_recovery_snapshots(root=tmp_path) == []


@pytest.mark.parametrize(
    "mutation",
    (
        "root_list",
        "saved_at_string",
        "saved_at_nan",
        "recovery_path_integer",
        "session_id_mismatch",
        "valid_source_path_mutation",
        "archive_sha_uppercase",
        "negative_bytes",
        "boolean_revision",
    ),
)
def test_corrupt_manifest_is_skipped_and_same_content_save_repairs_it(
    tmp_path,
    mutation: str,
) -> None:
    import json

    from app.painter_autosave import list_recovery_snapshots, save_recovery_snapshot

    healthy = save_recovery_snapshot("healthy", _payload(), root=tmp_path)
    damaged = save_recovery_snapshot("damaged", _payload(), root=tmp_path)
    manifest_path = Path(damaged["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if mutation == "root_list":
        changed: object = []
    else:
        if mutation == "saved_at_string":
            manifest["saved_at"] = "not-a-time"
        elif mutation == "saved_at_nan":
            manifest["saved_at"] = float("nan")
        elif mutation == "recovery_path_integer":
            manifest["recovery_path"] = 7
        elif mutation == "session_id_mismatch":
            manifest["session_id"] = "redirected-session"
        elif mutation == "valid_source_path_mutation":
            manifest["source_path"] = "plausible-but-not-saved.tspaint"
        elif mutation == "archive_sha_uppercase":
            manifest["archive_sha256"] = manifest["archive_sha256"].upper()
        elif mutation == "negative_bytes":
            manifest["bytes"] = -1
        elif mutation == "boolean_revision":
            manifest["document_revision"] = True
        changed = manifest
    manifest_path.write_text(json.dumps(changed), encoding="utf-8")

    rows = list_recovery_snapshots(root=tmp_path)
    assert [row["session_id"] for row in rows] == [healthy["session_id"]]

    repaired = save_recovery_snapshot("damaged", _payload(), root=tmp_path)
    assert repaired["skipped"] is False
    assert {
        row["session_id"] for row in list_recovery_snapshots(root=tmp_path)
    } == {"healthy", "damaged"}


def test_legacy_v1_manifest_remains_visible_and_next_save_upgrades_to_v2(
    tmp_path,
) -> None:
    import json

    from app.painter_autosave import (
        LEGACY_SCHEMA_V1,
        SCHEMA,
        list_recovery_snapshots,
        load_recovery_snapshot,
        save_recovery_snapshot,
    )

    saved = save_recovery_snapshot(
        "legacy-visible",
        _payload(),
        source_path="trusted-before-v1.tspaint",
        root=tmp_path,
    )
    manifest_path = Path(saved["manifest_path"])
    legacy = json.loads(manifest_path.read_text(encoding="utf-8"))
    legacy["schema"] = LEGACY_SCHEMA_V1
    legacy.pop("archive_sha256")
    legacy.pop("manifest_sha256")
    legacy.pop("retention_contract")
    manifest_path.write_text(json.dumps(legacy), encoding="utf-8")

    rows = list_recovery_snapshots(root=tmp_path)
    assert len(rows) == 1
    assert rows[0]["legacy_manifest"] is True
    assert rows[0]["legacy_unverified_source_path"] is True
    assert rows[0]["source_path"] == ""
    restored, report = load_recovery_snapshot(rows[0]["recovery_path"])
    assert restored["document"] == _payload()["document"]
    assert report["format_version"] == 5

    upgraded = save_recovery_snapshot(
        "legacy-visible",
        _payload(),
        root=tmp_path,
    )
    assert upgraded["skipped"] is False
    assert upgraded["schema"] == SCHEMA
    upgraded_on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert upgraded_on_disk["schema"] == SCHEMA
    assert len(upgraded_on_disk["archive_sha256"]) == 64
    assert len(upgraded_on_disk["manifest_sha256"]) == 64
    assert list_recovery_snapshots(root=tmp_path)[0]["legacy_manifest"] is False


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
    assert dialog._fill_document("solid", color1="#7A3FD1")
    from app.painter_layer_masks import linear_gradient_alpha8_mask

    layer_id = dialog._active_paint_layer_id
    layer = dialog._active_paint_layer()
    layer.mask_enabled = True
    dialog._set_paint_layer_mask(
        layer_id,
        linear_gradient_alpha8_mask(390, 844, (0.0, 0.0), (1.0, 0.0)),
    )
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
    restored_raster = dialog._paint_layer_raster(dialog._active_paint_layer_id)
    assert restored_raster is not None
    assert restored_raster.pixelColor(40, 40).name() == "#7a3fd1"
    restored_mask = dialog._paint_layer_mask(layer_id)
    assert restored_mask is not None
    assert restored_mask.pixelColor(0, 400).alpha() <= 2
    assert restored_mask.pixelColor(389, 400).alpha() >= 252
    from app.painter_i18n import painter_text

    assert painter_text("Recovered") in dialog.windowTitle()


def test_recovery_writer_failure_is_exposed_and_retryable(
    tmp_path,
    monkeypatch,
) -> None:
    from concurrent.futures import Future

    _app()
    from app import painter_autosave
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    failed = Future()
    disk_full = OSError(28, "디스크 공간이 부족합니다")
    disk_full.winerror = 112
    failed.set_exception(disk_full)
    succeeded = Future()
    succeeded.set_result({"skipped": False})
    submitted = iter((failed, succeeded))
    monkeypatch.setattr(
        painter_autosave,
        "submit_recovery_snapshot",
        lambda *args, **kwargs: next(submitted),
    )
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_recovery_timer.stop()

    assert dialog._schedule_painter_recovery_snapshot(force=True)["scheduled"] is True
    failed_state = dialog.painter_action_state()["recovery"]
    assert failed_state["writer_busy"] is False
    assert failed_state["last_error"].startswith("OSError:")
    assert failed_state["last_error_detail"] == {
        "type": "OSError",
        "message": "[Errno 28] 디스크 공간이 부족합니다",
        "errno": 28,
        "winerror": 112,
    }

    retry = dialog._schedule_painter_recovery_snapshot(force=True)
    assert retry["scheduled"] is True
    assert retry["previous_writer_error"].startswith("OSError:")
    recovered_state = dialog.painter_action_state()["recovery"]
    assert recovered_state["last_error"] == ""
    assert recovered_state["last_error_detail"] == {}


def test_disk_full_error_classifier_accepts_windows_and_posix_shapes() -> None:
    from tools.qa_painter_disk_full import _is_disk_full_detail, _is_disk_full_exception

    windows = OSError(28, "There is not enough space on the disk")
    windows.winerror = 112
    assert _is_disk_full_exception(windows) is True
    assert _is_disk_full_exception(OSError(28, "No space left on device")) is True
    assert _is_disk_full_exception(PermissionError("read only")) is False
    assert _is_disk_full_detail({"winerror": 112, "message": "디스크 공간이 부족합니다"}) is True
    assert _is_disk_full_detail({"errno": 28, "message": "localized"}) is True
    assert _is_disk_full_detail({"winerror": 5, "message": "access denied"}) is False


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


def test_document_composite_stroke_width_is_independent_of_editor_viewport() -> None:
    _app()
    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap

    stroke = Stroke(
        points=[(0.1, 0.2), (0.45, 0.72), (0.88, 0.3)],
        color=(248, 185, 65),
        opacity=235,
        width_px=14.0,
        brush_style="round",
        point_pressure=[0.25, 0.9, 0.4],
    )
    hashes = []
    for viewport in ((420, 320), (1180, 760)):
        dialog = PaintDialog(
            background_pixmap=create_blank_paint_pixmap(320, 180, "transparent"),
            initial_strokes=[stroke],
            time_ms=0,
            standalone=True,
        )
        dialog.resize(*viewport)
        image = dialog._painter_composite_pil(include_background=False).convert("RGBA")
        import hashlib

        hashes.append(hashlib.sha256(image.tobytes()).hexdigest())
        dialog.close()
    assert hashes[0] == hashes[1]
