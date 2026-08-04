from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_transactional_directory_export_commits_and_remaps_paths(tmp_path: Path) -> None:
    from app.painter_export_transaction import transactional_directory_export

    target = tmp_path / "maps"

    def produce(stage: Path):
        first = stage / "base.png"
        second = stage / "nested" / "normal.png"
        second.parent.mkdir()
        first.write_bytes(b"base")
        second.write_bytes(b"normal")
        return {"output_dir": str(stage), "files": {"base": str(first), "normal": str(second)}}

    report = transactional_directory_export(target, produce)

    assert (target / "base.png").read_bytes() == b"base"
    assert (target / "nested" / "normal.png").read_bytes() == b"normal"
    assert report["output_dir"] == str(target)
    assert report["files"]["normal"] == str(target / "nested" / "normal.png")
    assert report["transaction"]["committed"] is True
    assert report["transaction"]["file_count"] == 2
    assert list(tmp_path.glob(".maps.tiger-stage-*")) == []


def test_generation_failure_never_touches_destination(tmp_path: Path) -> None:
    from app.painter_export_transaction import (
        PainterExportTransactionError,
        transactional_directory_export,
    )

    target = tmp_path / "maps"
    target.mkdir()
    existing = target / "base.png"
    existing.write_bytes(b"old")

    def fail(stage: Path):
        (stage / "base.png").write_bytes(b"new")
        (stage / "partial.png").write_bytes(b"partial")
        raise RuntimeError("generation failed exactly")

    with pytest.raises(PainterExportTransactionError, match="generation failed exactly") as caught:
        transactional_directory_export(target, fail)

    assert caught.value.operation == "generate"
    assert caught.value.error_type == "RuntimeError"
    assert existing.read_bytes() == b"old"
    assert not (target / "partial.png").exists()
    assert list(tmp_path.glob(".maps.tiger-stage-*")) == []


def test_commit_failure_rolls_back_existing_and_new_files(monkeypatch, tmp_path: Path) -> None:
    import app.painter_export_transaction as transaction
    from app.painter_export_transaction import (
        PainterExportTransactionError,
        transactional_directory_export,
    )

    target = tmp_path / "maps"
    target.mkdir()
    existing = target / "a.png"
    unrelated = target / "unrelated.txt"
    existing.write_bytes(b"old-a")
    unrelated.write_bytes(b"keep")

    def produce(stage: Path):
        (stage / "a.png").write_bytes(b"new-a")
        (stage / "b.png").write_bytes(b"new-b")
        return {"output_dir": str(stage)}

    real_replace = os.replace
    failed = False

    def fail_second_install(source, destination):
        nonlocal failed
        source_path = Path(source)
        destination_path = Path(destination)
        if not failed and source_path.name == "b.png" and destination_path.parent == target:
            failed = True
            raise OSError("commit failed exactly")
        return real_replace(source, destination)

    monkeypatch.setattr(transaction.os, "replace", fail_second_install)
    with pytest.raises(PainterExportTransactionError, match="commit failed exactly") as caught:
        transactional_directory_export(target, produce)

    assert caught.value.operation == "commit"
    assert caught.value.rollback_errors == []
    assert existing.read_bytes() == b"old-a"
    assert not (target / "b.png").exists()
    assert unrelated.read_bytes() == b"keep"
    assert list(tmp_path.glob(".maps.tiger-stage-*")) == []


def test_rollback_failure_is_explicit_and_preserves_recovery_staging(monkeypatch, tmp_path: Path) -> None:
    import app.painter_export_transaction as transaction
    from app.painter_export_transaction import (
        PainterExportTransactionError,
        transactional_directory_export,
    )

    target = tmp_path / "maps"
    target.mkdir()
    (target / "a.png").write_bytes(b"old-a")

    def produce(stage: Path):
        (stage / "a.png").write_bytes(b"new-a")
        (stage / "b.png").write_bytes(b"new-b")
        return {}

    real_replace = os.replace
    install_failed = False

    def fail_commit_and_restore(source, destination):
        nonlocal install_failed
        source_path = Path(source)
        destination_path = Path(destination)
        if not install_failed and source_path.name == "b.png" and destination_path.parent == target:
            install_failed = True
            raise OSError("commit failed exactly")
        if install_failed and "backup" in source_path.parts and destination_path.name == "a.png":
            raise PermissionError("restore denied exactly")
        return real_replace(source, destination)

    monkeypatch.setattr(transaction.os, "replace", fail_commit_and_restore)
    with pytest.raises(PainterExportTransactionError) as caught:
        transactional_directory_export(target, produce)

    error = caught.value
    assert error.operation == "commit"
    assert error.error_type == "OSError"
    assert any("PermissionError: restore denied exactly" in row for row in error.rollback_errors)
    assert error.recovery_dir
    assert Path(error.recovery_dir).is_dir()
    assert (Path(error.recovery_dir) / "backup" / "a.png").read_bytes() == b"old-a"


def test_painter_pbr_public_export_routes_generation_through_transaction(tmp_path: Path) -> None:
    from app.drawing import PaintDialog
    from app.painter_export_transaction import PainterExportTransactionError

    target = tmp_path / "maps"
    target.mkdir()
    existing = target / "existing.png"
    existing.write_bytes(b"old")

    class FakeDialog:
        def _export_pbr_maps_uncommitted_to_path(self, staging_dir, **_kwargs):
            (staging_dir / "partial.png").write_bytes(b"partial")
            raise RuntimeError("PBR map generation failed exactly")

    with pytest.raises(PainterExportTransactionError, match="PBR map generation failed exactly"):
        PaintDialog.export_pbr_maps_to_path(FakeDialog(), target)

    assert existing.read_bytes() == b"old"
    assert not (target / "partial.png").exists()
    assert list(tmp_path.glob(".maps.tiger-stage-*")) == []


def test_pbr_export_dialog_reports_transaction_failure_without_success(monkeypatch, tmp_path: Path) -> None:
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from app.drawing import PaintDialog
    from app.painter_export_transaction import PainterExportTransactionError

    target = tmp_path / "maps"
    warnings: list[str] = []
    information: list[str] = []

    class FakeDialog:
        def __init__(self):
            self.errors = {}

        def _set_painter_operational_error(self, key, error):
            self.errors[key] = "" if error is None else f"{type(error).__name__}: {error}"

        def export_pbr_maps_to_path(self, *_args, **_kwargs):
            raise PainterExportTransactionError(
                "commit",
                OSError("PBR transaction failed exactly"),
            )

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *_args: str(target))
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: warnings.append(str(_args[-1])))
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: information.append(str(_args[-1])))
    fake = FakeDialog()

    PaintDialog._export_pbr_texture_maps(fake, packed=False)

    assert "PainterExportTransactionError: commit failed: OSError: PBR transaction failed exactly" == (
        fake.errors["pbr_map_export"]
    )
    assert "PBR transaction failed exactly" in warnings[-1]
    assert information == []


def test_pbr_export_dialog_reports_committed_cleanup_failure_without_plain_success(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from app.drawing import PaintDialog

    target = tmp_path / "maps"
    recovery = tmp_path / ".maps.tiger-stage-recovery"
    recovery.mkdir()
    warnings: list[str] = []
    information: list[str] = []

    class FakeDialog:
        def __init__(self):
            self.errors = {}

        def _set_painter_operational_error(self, key, error):
            if error is None or error == "":
                self.errors[key] = ""
            elif isinstance(error, BaseException):
                self.errors[key] = f"{type(error).__name__}: {error}"
            else:
                self.errors[key] = str(error)

        def export_pbr_maps_to_path(self, *_args, **_kwargs):
            return {
                "output_dir": str(target),
                "transaction": {
                    "committed": True,
                    "cleanup_completed": False,
                    "cleanup_error": {
                        "type": "OSError",
                        "message": "success cleanup denied exactly",
                    },
                    "recovery_dir": str(recovery),
                },
            }

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *_args: str(target))
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: warnings.append(str(_args[-1])))
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: information.append(str(_args[-1])))
    fake = FakeDialog()

    PaintDialog._export_pbr_texture_maps(fake, packed=False)

    assert fake.errors["pbr_map_export"] == ""
    assert fake.errors["pbr_map_export_cleanup"] == (
        f"OSError: success cleanup denied exactly; recovery staging: {recovery}"
    )
    assert "maps were committed" in warnings[-1]
    assert "OSError: success cleanup denied exactly" in warnings[-1]
    assert str(recovery) in warnings[-1]
    assert information == []


def test_transactional_file_export_preserves_existing_file_on_generation_failure(tmp_path: Path) -> None:
    from app.painter_export_transaction import (
        PainterExportTransactionError,
        transactional_file_export,
    )

    target = tmp_path / "art.png"
    target.write_bytes(b"old-art")

    def fail(staging: Path):
        staging.write_bytes(b"partial-new-art")
        raise OSError("single file generation failed exactly")

    with pytest.raises(PainterExportTransactionError, match="single file generation failed exactly"):
        transactional_file_export(target, fail)

    assert target.read_bytes() == b"old-art"
    assert list(tmp_path.glob(".art.tiger-stage-*.png")) == []


def test_transactional_file_export_commits_and_remaps_report(tmp_path: Path) -> None:
    from app.painter_export_transaction import transactional_file_export

    target = tmp_path / "art.png"

    def produce(staging: Path):
        staging.write_bytes(b"finished-art")
        return {"path": str(staging), "status": "written"}

    report = transactional_file_export(target, produce)

    assert target.read_bytes() == b"finished-art"
    assert report["path"] == str(target)
    assert report["transaction"]["committed"] is True


def test_document_public_export_preserves_existing_file_when_writer_fails(tmp_path: Path) -> None:
    from app.drawing import PaintDialog
    from app.painter_export_transaction import PainterExportTransactionError

    target = tmp_path / "art.png"
    target.write_bytes(b"old-document-export")

    class FakeDialog:
        def _export_document_uncommitted_to_path(self, staging_path, **_kwargs):
            Path(staging_path).write_bytes(b"partial-document-export")
            raise RuntimeError("document writer failed exactly")

    with pytest.raises(PainterExportTransactionError, match="document writer failed exactly"):
        PaintDialog.export_document_to_path(
            FakeDialog(),
            target,
            format_name="png",
        )

    assert target.read_bytes() == b"old-document-export"
    assert list(tmp_path.glob(".art.tiger-stage-*.png")) == []


def test_brush_bundle_export_preserves_existing_file_on_commit_failure(monkeypatch, tmp_path: Path) -> None:
    import app.painter_export_transaction as transaction
    from app.painter_export_transaction import PainterExportTransactionError
    from app.painter_palette import export_brush_bundle

    target = tmp_path / "brushes.tsbrushes"
    target.write_bytes(b"old-brush-bundle")
    real_replace = os.replace

    def fail_commit(source, destination):
        if Path(destination) == target:
            raise PermissionError("brush commit denied exactly")
        return real_replace(source, destination)

    monkeypatch.setattr(transaction.os, "replace", fail_commit)
    with pytest.raises(PainterExportTransactionError, match="brush commit denied exactly"):
        export_brush_bundle([{"name": "Ink", "style": "round"}], target)

    assert target.read_bytes() == b"old-brush-bundle"
    assert list(tmp_path.glob(".brushes.tiger-stage-*.tsbrushes")) == []


def test_backup_phase_failure_restores_files_before_any_install(monkeypatch, tmp_path: Path) -> None:
    import app.painter_export_transaction as transaction
    from app.painter_export_transaction import (
        PainterExportTransactionError,
        transactional_directory_export,
    )

    target = tmp_path / "maps"
    target.mkdir()
    (target / "a.png").write_bytes(b"old-a")
    (target / "b.png").write_bytes(b"old-b")

    def produce(stage: Path):
        (stage / "a.png").write_bytes(b"new-a")
        (stage / "b.png").write_bytes(b"new-b")
        return {}

    real_replace = os.replace

    def fail_second_backup(source, destination):
        source_path = Path(source)
        destination_path = Path(destination)
        if source_path == target / "b.png" and "backup" in destination_path.parts:
            raise PermissionError("second backup denied exactly")
        return real_replace(source, destination)

    monkeypatch.setattr(transaction.os, "replace", fail_second_backup)
    with pytest.raises(PainterExportTransactionError, match="second backup denied exactly") as caught:
        transactional_directory_export(target, produce)

    assert caught.value.rollback_errors == []
    assert (target / "a.png").read_bytes() == b"old-a"
    assert (target / "b.png").read_bytes() == b"old-b"
    assert list(tmp_path.glob(".maps.tiger-stage-*")) == []


def test_rollback_removal_failure_is_reported_with_recovery_staging(monkeypatch, tmp_path: Path) -> None:
    import app.painter_export_transaction as transaction
    from app.painter_export_transaction import PainterExportTransactionError, transactional_directory_export

    target = tmp_path / "maps"

    def produce(stage: Path):
        (stage / "a.png").write_bytes(b"new-a")
        (stage / "b.png").write_bytes(b"new-b")
        return {}

    real_replace = os.replace
    real_unlink = Path.unlink
    install_failed = False

    def fail_second_install(source, destination):
        nonlocal install_failed
        if not install_failed and Path(source).name == "b.png" and Path(destination).parent == target:
            install_failed = True
            raise OSError("second install failed exactly")
        return real_replace(source, destination)

    def fail_installed_remove(path, *args, **kwargs):
        if install_failed and path == target / "a.png":
            raise PermissionError("installed remove denied exactly")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(transaction.os, "replace", fail_second_install)
    monkeypatch.setattr(Path, "unlink", fail_installed_remove)
    with pytest.raises(PainterExportTransactionError) as caught:
        transactional_directory_export(target, produce)

    error = caught.value
    assert any("PermissionError: installed remove denied exactly" in row for row in error.rollback_errors)
    assert error.recovery_dir
    assert Path(error.recovery_dir).is_dir()


def test_rollback_directory_cleanup_failure_is_reported_with_recovery_staging(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import app.painter_export_transaction as transaction
    from app.painter_export_transaction import PainterExportTransactionError, transactional_directory_export

    target = tmp_path / "maps"

    def produce(stage: Path):
        (stage / "nested").mkdir()
        (stage / "nested" / "a.png").write_bytes(b"new-a")
        (stage / "z.png").write_bytes(b"new-z")
        return {}

    real_replace = os.replace
    real_rmdir = Path.rmdir
    install_failed = False

    def fail_second_install(source, destination):
        nonlocal install_failed
        if not install_failed and Path(source).name == "z.png" and Path(destination).parent == target:
            install_failed = True
            raise OSError("second install failed exactly")
        return real_replace(source, destination)

    def fail_created_directory_remove(path, *args, **kwargs):
        if install_failed and path == target / "nested":
            raise PermissionError("created directory remove denied exactly")
        return real_rmdir(path, *args, **kwargs)

    monkeypatch.setattr(transaction.os, "replace", fail_second_install)
    monkeypatch.setattr(Path, "rmdir", fail_created_directory_remove)
    with pytest.raises(PainterExportTransactionError) as caught:
        transactional_directory_export(target, produce)

    error = caught.value
    assert error.rollback_errors[0] == (
        "remove directory nested: PermissionError: created directory remove denied exactly"
    )
    assert error.rollback_errors[1].startswith("remove directory maps: OSError:")
    assert error.recovery_dir
    assert Path(error.recovery_dir).is_dir()


def test_validation_failure_is_structured_and_cleans_staging(monkeypatch, tmp_path: Path) -> None:
    import app.painter_export_transaction as transaction
    from app.painter_export_transaction import PainterExportTransactionError, transactional_directory_export

    target = tmp_path / "maps"

    def produce(stage: Path):
        (stage / "a.png").write_bytes(b"new-a")
        return {}

    def fail_validation(_payload_dir):
        raise ValueError("validation failed exactly")

    monkeypatch.setattr(transaction, "_regular_staged_files", fail_validation)
    with pytest.raises(PainterExportTransactionError) as caught:
        transactional_directory_export(target, produce)

    assert str(caught.value) == "validate failed: ValueError: validation failed exactly"
    assert target.exists() is False
    assert list(tmp_path.glob(".maps.tiger-stage-*")) == []


def test_failed_stage_cleanup_failure_preserves_primary_error_and_recovery_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import app.painter_export_transaction as transaction
    from app.painter_export_transaction import PainterExportTransactionError, transactional_directory_export

    target = tmp_path / "maps"
    real_rmtree = transaction.shutil.rmtree

    def fail_generation(stage: Path):
        (stage / "partial.png").write_bytes(b"partial")
        raise RuntimeError("generation failed exactly")

    def fail_failed_stage_cleanup(path, *args, **kwargs):
        if Path(path).name.startswith(".maps.tiger-stage-"):
            raise OSError("failed stage cleanup denied exactly")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(transaction.shutil, "rmtree", fail_failed_stage_cleanup)
    with pytest.raises(PainterExportTransactionError) as caught:
        transactional_directory_export(target, fail_generation)

    error = caught.value
    assert error.error_type == "RuntimeError"
    assert error.error_message == "generation failed exactly"
    assert error.rollback_errors == [
        "cleanup staging: OSError: failed stage cleanup denied exactly"
    ]
    assert error.recovery_dir
    assert Path(error.recovery_dir).is_dir()
    assert target.exists() is False


def test_success_cleanup_failure_reports_committed_state_without_false_failure(monkeypatch, tmp_path: Path) -> None:
    import app.painter_export_transaction as transaction
    from app.painter_export_transaction import transactional_directory_export

    target = tmp_path / "maps"
    real_rmtree = transaction.shutil.rmtree

    def produce(stage: Path):
        (stage / "a.png").write_bytes(b"new-a")
        return {}

    def fail_success_cleanup(path, *args, **kwargs):
        if Path(path).name.startswith(".maps.tiger-stage-"):
            raise OSError("success cleanup denied exactly")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(transaction.shutil, "rmtree", fail_success_cleanup)
    report = transactional_directory_export(target, produce)

    assert (target / "a.png").read_bytes() == b"new-a"
    assert report["transaction"]["committed"] is True
    assert report["transaction"]["cleanup_completed"] is False
    assert report["transaction"]["cleanup_error"] == {
        "type": "OSError",
        "message": "success cleanup denied exactly",
    }
    assert Path(report["transaction"]["recovery_dir"]).is_dir()


def test_successful_rollback_removes_new_empty_destination_directory(monkeypatch, tmp_path: Path) -> None:
    import app.painter_export_transaction as transaction
    from app.painter_export_transaction import PainterExportTransactionError, transactional_directory_export

    target = tmp_path / "maps"
    real_replace = os.replace

    def produce(stage: Path):
        (stage / "a.png").write_bytes(b"new-a")
        (stage / "b.png").write_bytes(b"new-b")
        return {}

    def fail_second_install(source, destination):
        if Path(source).name == "b.png" and Path(destination).parent == target:
            raise OSError("second install failed exactly")
        return real_replace(source, destination)

    monkeypatch.setattr(transaction.os, "replace", fail_second_install)
    with pytest.raises(PainterExportTransactionError, match="second install failed exactly") as caught:
        transactional_directory_export(target, produce)

    assert caught.value.rollback_errors == []
    assert target.exists() is False
    assert list(tmp_path.glob(".maps.tiger-stage-*")) == []
