"""Same-filesystem staging and rollback for Painter multi-file exports."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Callable, Mapping


class PainterExportTransactionError(RuntimeError):
    """Export failure with explicit rollback/recovery diagnostics."""

    def __init__(
        self,
        operation: str,
        error: BaseException,
        *,
        rollback_errors: list[str] | None = None,
        recovery_dir: str = "",
    ) -> None:
        self.operation = str(operation)
        self.error_type = type(error).__name__
        self.error_message = str(error)
        self.rollback_errors = list(rollback_errors or [])
        self.recovery_dir = str(recovery_dir or "")
        detail = f"{self.operation} failed: {self.error_type}: {self.error_message}"
        if self.rollback_errors:
            detail += "; rollback failed: " + "; ".join(self.rollback_errors)
        if self.recovery_dir:
            detail += f"; recovery staging preserved at {self.recovery_dir}"
        super().__init__(detail)


def transactional_directory_export(
    destination: str | Path,
    producer: Callable[[Path], Mapping[str, Any]],
) -> dict[str, Any]:
    """Generate a file set off-target, then commit it with rollback.

    The staging directory is created beside ``destination`` so every
    ``os.replace`` commit and rollback stays on the destination filesystem.
    Existing destination files not produced by this transaction are untouched.
    """

    target = Path(destination).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    stage_root = Path(
        tempfile.mkdtemp(
            prefix=f".{target.name or 'painter-export'}.tiger-stage-",
            dir=str(target.parent),
        )
    )
    payload_dir = stage_root / "payload"
    backup_dir = stage_root / "backup"
    payload_dir.mkdir()
    try:
        staged_report = dict(producer(payload_dir))
    except Exception as exc:
        _raise_after_stage_cleanup("generate", exc, stage_root)

    try:
        staged_files = _regular_staged_files(payload_dir)
    except Exception as exc:
        _raise_after_stage_cleanup("validate", exc, stage_root)
    if not staged_files:
        _raise_after_stage_cleanup(
            "validate",
            RuntimeError("producer created no export files"),
            stage_root,
        )

    backed_up: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    created_dirs: list[Path] = []
    try:
        target_created = not target.exists()
        target.mkdir(parents=True, exist_ok=True)
        if target_created:
            created_dirs.append(target)
        for staged in staged_files:
            relative = staged.relative_to(payload_dir)
            final = target / relative
            _ensure_parent_dirs(final.parent, target, created_dirs)
            if final.exists():
                backup = backup_dir / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                os.replace(final, backup)
                backed_up.append((final, backup))
        for staged in staged_files:
            relative = staged.relative_to(payload_dir)
            final = target / relative
            os.replace(staged, final)
            installed.append(final)
    except Exception as exc:
        rollback_errors = _rollback_export(
            installed=installed,
            backed_up=backed_up,
            created_dirs=created_dirs,
        )
        if rollback_errors:
            raise PainterExportTransactionError(
                "commit",
                exc,
                rollback_errors=rollback_errors,
                recovery_dir=str(stage_root.resolve()),
            ) from exc
        _raise_after_stage_cleanup("commit", exc, stage_root)

    result = _remap_staged_paths(staged_report, payload_dir, target)
    transaction = {
        "schema": "tigerstudio.painter.export-transaction.v1",
        "committed": True,
        "same_filesystem_staging": True,
        "atomic_file_replace": True,
        "rollback_required": False,
        "file_count": len(staged_files),
        "cleanup_completed": True,
        "cleanup_error": None,
        "recovery_dir": "",
    }
    result["transaction"] = transaction
    try:
        shutil.rmtree(stage_root)
    except Exception as exc:
        transaction["cleanup_completed"] = False
        transaction["cleanup_error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        transaction["recovery_dir"] = str(stage_root.resolve())
    return result


def transactional_file_export(
    destination: str | Path,
    producer: Callable[[Path], Mapping[str, Any] | None],
) -> dict[str, Any]:
    """Generate one file beside its destination and atomically replace it."""

    target = Path(destination).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, staging_name = tempfile.mkstemp(
        prefix=f".{target.stem}.tiger-stage-",
        suffix=target.suffix,
        dir=str(target.parent),
    )
    os.close(descriptor)
    staging = Path(staging_name)
    staging.unlink()
    try:
        staged_report = dict(producer(staging) or {})
        if not staging.is_file():
            raise RuntimeError("producer created no export file")
        os.replace(staging, target)
    except Exception as exc:
        cleanup_errors: list[str] = []
        try:
            staging.unlink(missing_ok=True)
        except Exception as cleanup_exc:
            cleanup_errors.append(
                f"cleanup staging: {type(cleanup_exc).__name__}: {cleanup_exc}"
            )
        raise PainterExportTransactionError(
            "file_commit",
            exc,
            rollback_errors=cleanup_errors,
            recovery_dir=(str(staging.resolve()) if cleanup_errors else ""),
        ) from exc
    result = _remap_staged_paths(staged_report, staging, target)
    result["transaction"] = {
        "schema": "tigerstudio.painter.export-transaction.v1",
        "committed": True,
        "same_filesystem_staging": True,
        "atomic_file_replace": True,
        "rollback_required": False,
        "file_count": 1,
    }
    return result


def _regular_staged_files(payload_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(payload_dir.rglob("*"), key=lambda row: row.as_posix()):
        if path.is_symlink():
            raise ValueError(f"staged export cannot contain symbolic links: {path.name}")
        if path.is_file():
            files.append(path)
    return files


def _ensure_parent_dirs(parent: Path, target: Path, created_dirs: list[Path]) -> None:
    missing: list[Path] = []
    current = parent
    while current != target and not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir()
        created_dirs.append(directory)


def _rollback_export(
    *,
    installed: list[Path],
    backed_up: list[tuple[Path, Path]],
    created_dirs: list[Path],
) -> list[str]:
    errors: list[str] = []
    backup_by_final = {final: backup for final, backup in backed_up}
    for final in reversed(installed):
        try:
            final.unlink(missing_ok=True)
        except Exception as exc:
            errors.append(f"remove {final.name}: {type(exc).__name__}: {exc}")
        backup = backup_by_final.pop(final, None)
        if backup is not None:
            try:
                os.replace(backup, final)
            except Exception as exc:
                errors.append(f"restore {final.name}: {type(exc).__name__}: {exc}")
    for final, backup in reversed(backed_up):
        if final not in backup_by_final:
            continue
        try:
            os.replace(backup, final)
        except Exception as exc:
            errors.append(f"restore {final.name}: {type(exc).__name__}: {exc}")
    for directory in reversed(created_dirs):
        try:
            directory.rmdir()
        except OSError as exc:
            errors.append(f"remove directory {directory.name}: {type(exc).__name__}: {exc}")
    return errors


def _raise_after_stage_cleanup(
    operation: str,
    error: BaseException,
    stage_root: Path,
) -> None:
    try:
        shutil.rmtree(stage_root)
    except Exception as cleanup_exc:
        raise PainterExportTransactionError(
            operation,
            error,
            rollback_errors=[f"cleanup staging: {type(cleanup_exc).__name__}: {cleanup_exc}"],
            recovery_dir=str(stage_root.resolve()),
        ) from error
    raise PainterExportTransactionError(operation, error) from error


def _remap_staged_paths(value: Any, stage: Path, target: Path) -> Any:
    if isinstance(value, dict):
        return {key: _remap_staged_paths(row, stage, target) for key, row in value.items()}
    if isinstance(value, list):
        return [_remap_staged_paths(row, stage, target) for row in value]
    if isinstance(value, tuple):
        return tuple(_remap_staged_paths(row, stage, target) for row in value)
    if isinstance(value, str):
        try:
            relative = Path(value).relative_to(stage)
        except ValueError:
            return value
        return str(target / relative)
    return value


__all__ = [
    "PainterExportTransactionError",
    "transactional_directory_export",
    "transactional_file_export",
]
