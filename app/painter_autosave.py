"""Crash-safe recovery snapshots for standalone Tiger Studio Painter."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import operator
import tempfile
import time
import zipfile
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Mapping

from app.painter_document_io import (
    PainterDocumentError,
    load_painter_document,
    save_painter_document,
)
from app.paths import runtime_data_dir


SCHEMA = "tigerstudio.painter.recovery.v2"
LEGACY_SCHEMA_V1 = "tigerstudio.painter.recovery.v1"
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="painter-recovery")
RECOVERY_WRITER_CONTRACT = {
    "schema": "tigerstudio.painter.recovery_writer.v1",
    "max_workers": 1,
    "reason": "serialize_atomic_snapshot_replacement_per_process",
    "throughput_threshold_claim": False,
    "universal_recovery_latency_claim": False,
}
RECOVERY_RETENTION_CONTRACT = {
    "schema": "tigerstudio.painter.recovery_retention.v1",
    "default_snapshots": 12,
    "source": "tiger_authored_local_recovery_retention_policy",
    "universal_recovery_capacity_claim": False,
}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _recovery_keep_count(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeError("Painter recovery keep count must be a non-negative integer")
    try:
        count = operator.index(value)
    except TypeError as exc:
        raise TypeError(
            "Painter recovery keep count must be a non-negative integer"
        ) from exc
    if count < 0:
        raise ValueError("Painter recovery keep count must be non-negative")
    return count


def _canonical_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _recovery_manifest_sha256(value: Mapping[str, Any]) -> str:
    payload = {
        key: item
        for key, item in value.items()
        if key != "manifest_sha256"
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_recovery_manifest_identity(
    value: Any,
    *,
    recovery_path: Path,
    manifest_path: Path,
) -> bool:
    if not isinstance(value, dict):
        return False
    if not isinstance(value.get("session_id"), str) or not value["session_id"]:
        return False
    if _key(value["session_id"]) != manifest_path.stem:
        return False
    if not isinstance(value.get("source_path"), str):
        return False
    if not _canonical_sha256(value.get("content_sha256")):
        return False
    saved_at = value.get("saved_at")
    if isinstance(saved_at, bool) or not isinstance(saved_at, (int, float)):
        return False
    try:
        saved_at_value = float(saved_at)
    except (OverflowError, ValueError):
        return False
    if not math.isfinite(saved_at_value) or saved_at_value < 0.0:
        return False
    for key in ("document_revision", "bytes", "asset_count"):
        item = value.get(key)
        if isinstance(item, bool):
            return False
        try:
            item = operator.index(item)
        except TypeError:
            return False
        if item < 0:
            return False
    try:
        stored_recovery = value.get("recovery_path")
        stored_manifest = value.get("manifest_path")
        if not isinstance(stored_recovery, str) or not isinstance(stored_manifest, str):
            return False
        return (
            Path(stored_recovery).resolve() == recovery_path.resolve()
            and Path(stored_manifest).resolve() == manifest_path.resolve()
        )
    except (OSError, RuntimeError, ValueError):
        return False


def _valid_recovery_manifest(
    value: Any,
    *,
    recovery_path: Path,
    manifest_path: Path,
) -> bool:
    return (
        isinstance(value, dict)
        and value.get("schema") == SCHEMA
        and _valid_recovery_manifest_identity(
            value,
            recovery_path=recovery_path,
            manifest_path=manifest_path,
        )
        and _canonical_sha256(value.get("archive_sha256"))
        and _canonical_sha256(value.get("manifest_sha256"))
        and value["manifest_sha256"] == _recovery_manifest_sha256(value)
    )


def _valid_legacy_recovery_manifest(
    value: Any,
    *,
    recovery_path: Path,
    manifest_path: Path,
) -> bool:
    if not (
        isinstance(value, dict)
        and value.get("schema") == LEGACY_SCHEMA_V1
        and _valid_recovery_manifest_identity(
            value,
            recovery_path=recovery_path,
            manifest_path=manifest_path,
        )
    ):
        return False
    try:
        with tempfile.TemporaryDirectory(
            prefix="tiger-painter-legacy-recovery-"
        ) as extraction_root:
            load_painter_document(
                recovery_path,
                asset_root=extraction_root,
            )
    except PainterDocumentError:
        return False
    return True


def inspect_recovery_archive(
    path: str | Path,
    *,
    expected_sha256: str = "",
) -> dict[str, Any]:
    """Check ZIP structure/CRC before a snapshot is offered for restore."""
    target = Path(path)
    report = {
        "schema": "tigerstudio.painter.recovery.integrity.v1",
        "path": str(target.resolve()),
        "valid": False,
        "reason": "missing",
        "bad_crc_entry": "",
        "archive_sha256": "",
        "hash_matches": False,
    }
    if not target.is_file():
        return report
    try:
        archive_sha256 = _file_sha256(target)
        expected = str(expected_sha256 or "").strip().casefold()
        if expected and archive_sha256 != expected:
            return {
                **report,
                "reason": "archive_hash_mismatch",
                "archive_sha256": archive_sha256,
            }
        with zipfile.ZipFile(target, "r") as archive:
            if "document.json" not in archive.namelist():
                return {**report, "reason": "document_entry_missing"}
            bad_entry = archive.testzip()
            if bad_entry:
                return {**report, "reason": "crc_failure", "bad_crc_entry": bad_entry}
            payload = json.loads(archive.read("document.json").decode("utf-8"))
            if not isinstance(payload, dict) or not str(payload.get("schema") or ""):
                return {**report, "reason": "document_schema_missing"}
    except (
        OSError,
        RuntimeError,
        ValueError,
        UnicodeDecodeError,
        zipfile.BadZipFile,
        json.JSONDecodeError,
    ) as exc:
        return {**report, "reason": f"{type(exc).__name__}: {exc}"}
    return {
        **report,
        "valid": True,
        "reason": "ok",
        "archive_sha256": archive_sha256,
        "hash_matches": bool(expected),
    }


def painter_recovery_dir(root: str | Path | None = None) -> Path:
    path = Path(root) if root is not None else runtime_data_dir() / "painter" / "recovery"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _key(session_id: str) -> str:
    value = str(session_id or "").strip()
    if not value:
        raise ValueError("Painter recovery session_id is required")
    return hashlib.blake2b(value.encode("utf-8"), digest_size=12).hexdigest()


def _paths(session_id: str, root: str | Path | None) -> tuple[Path, Path]:
    base = painter_recovery_dir(root) / _key(session_id)
    return base.with_suffix(".tspaint"), base.with_suffix(".json")


def _content_hash(
    document: Mapping[str, Any],
    background_png: bytes | None,
    layer_raster_pngs: Mapping[str, bytes] | None = None,
    layer_mask_pngs: Mapping[str, bytes] | None = None,
    selection_mask_png: bytes | None = None,
    saved_selection_channel_pngs: Mapping[str, bytes] | None = None,
) -> str:
    encoded = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    digest = hashlib.sha256(encoded)
    if background_png:
        digest.update(background_png)
    for layer_id, data in sorted(dict(layer_raster_pngs or {}).items()):
        digest.update(str(layer_id).encode("utf-8"))
        digest.update(bytes(data))
    for layer_id, data in sorted(dict(layer_mask_pngs or {}).items()):
        digest.update(b"layer-mask:")
        digest.update(str(layer_id).encode("utf-8"))
        digest.update(bytes(data))
    if selection_mask_png:
        digest.update(bytes(selection_mask_png))
    for channel_id, data in sorted(dict(saved_selection_channel_pngs or {}).items()):
        digest.update(b"saved-selection-channel:")
        digest.update(str(channel_id).encode("utf-8"))
        digest.update(bytes(data))
    return digest.hexdigest()


def save_recovery_snapshot(
    session_id: str,
    document: Mapping[str, Any],
    *,
    source_path: str = "",
    background_png: bytes | None = None,
    layer_raster_pngs: Mapping[str, bytes] | None = None,
    layer_mask_pngs: Mapping[str, bytes] | None = None,
    selection_mask_png: bytes | None = None,
    saved_selection_channel_pngs: Mapping[str, bytes] | None = None,
    root: str | Path | None = None,
    keep: int = 12,
) -> dict[str, Any]:
    """Atomically replace one session snapshot and its small manifest."""

    keep_count = _recovery_keep_count(keep)
    recovery_path, manifest_path = _paths(session_id, root)
    payload = copy.deepcopy(dict(document))
    content_sha256 = _content_hash(
        payload,
        background_png,
        layer_raster_pngs,
        layer_mask_pngs,
        selection_mask_png,
        saved_selection_channel_pngs,
    )
    if manifest_path.is_file() and recovery_path.is_file():
        try:
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = {}
        if not _valid_recovery_manifest(
            previous,
            recovery_path=recovery_path,
            manifest_path=manifest_path,
        ):
            previous = {}
        previous_archive_sha256 = str(previous.get("archive_sha256") or "")
        integrity = inspect_recovery_archive(
            recovery_path,
            expected_sha256=previous_archive_sha256,
        )
        if (
            previous.get("content_sha256") == content_sha256
            and previous.get("source_path") == str(source_path or "")
            and bool(previous_archive_sha256)
            and integrity["valid"]
        ):
            return {**previous, "skipped": True}
    save_report = save_painter_document(
        recovery_path,
        payload,
        background_png=background_png,
        layer_raster_pngs=layer_raster_pngs,
        layer_mask_pngs=layer_mask_pngs,
        selection_mask_png=selection_mask_png,
        saved_selection_channel_pngs=saved_selection_channel_pngs,
    )
    saved_at = time.time()
    archive_sha256 = _file_sha256(recovery_path)
    ui_document = payload.get("ui_document")
    manifest = {
        "schema": SCHEMA,
        "session_id": str(session_id),
        "source_path": str(source_path or ""),
        "recovery_path": str(recovery_path.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "saved_at": saved_at,
        "content_sha256": content_sha256,
        "archive_sha256": archive_sha256,
        "document_revision": int(
            (ui_document if isinstance(ui_document, dict) else {}).get(
                "revision", 0
            )
            or 0
        ),
        "bytes": int(save_report.get("bytes") or 0),
        "asset_count": int(save_report.get("asset_count") or 0),
        "skipped": False,
        "writer_contract": dict(RECOVERY_WRITER_CONTRACT),
        "retention_contract": dict(RECOVERY_RETENTION_CONTRACT),
    }
    manifest["manifest_sha256"] = _recovery_manifest_sha256(manifest)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{manifest_path.name}.",
        suffix=".tmp",
        dir=str(manifest_path.parent),
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, manifest_path)
    finally:
        temporary.unlink(missing_ok=True)
    prune_recovery_snapshots(root=root, keep=keep_count)
    return manifest


def submit_recovery_snapshot(
    session_id: str,
    document: Mapping[str, Any],
    **kwargs: Any,
) -> Future:
    """Persist an immutable snapshot on the single recovery writer."""

    payload = copy.deepcopy(dict(document))
    background = kwargs.pop("background_png", None)
    background = bytes(background) if background else None
    raster_pngs = {
        str(layer_id): bytes(data)
        for layer_id, data in dict(kwargs.pop("layer_raster_pngs", None) or {}).items()
    }
    mask_pngs = {
        str(layer_id): bytes(data)
        for layer_id, data in dict(kwargs.pop("layer_mask_pngs", None) or {}).items()
    }
    selection_mask = kwargs.pop("selection_mask_png", None)
    selection_mask = bytes(selection_mask) if selection_mask else None
    saved_selection_channel_pngs = {
        str(channel_id): bytes(data)
        for channel_id, data in dict(
            kwargs.pop("saved_selection_channel_pngs", None) or {}
        ).items()
    }
    return _EXECUTOR.submit(
        save_recovery_snapshot,
        session_id,
        payload,
        background_png=background,
        layer_raster_pngs=raster_pngs,
        layer_mask_pngs=mask_pngs,
        selection_mask_png=selection_mask,
        saved_selection_channel_pngs=saved_selection_channel_pngs,
        **kwargs,
    )


def list_recovery_snapshots(
    *,
    root: str | Path | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for manifest_path in painter_recovery_dir(root).glob("*.json"):
        try:
            row = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        recovery_path = manifest_path.with_suffix(".tspaint")
        if not recovery_path.is_file():
            continue
        current_manifest = _valid_recovery_manifest(
            row,
            recovery_path=recovery_path,
            manifest_path=manifest_path,
        )
        legacy_manifest = False
        if not current_manifest:
            legacy_manifest = _valid_legacy_recovery_manifest(
                row,
                recovery_path=recovery_path,
                manifest_path=manifest_path,
            )
        if not current_manifest and not legacy_manifest:
            continue
        integrity = inspect_recovery_archive(
            recovery_path,
            expected_sha256=(
                str(row.get("archive_sha256") or "")
                if current_manifest
                else ""
            ),
        )
        if not integrity["valid"]:
            continue
        row["integrity"] = integrity
        row["legacy_manifest"] = legacy_manifest
        row["legacy_unverified_source_path"] = bool(
            legacy_manifest and row.get("source_path")
        )
        if legacy_manifest:
            row["source_path"] = ""
        row["manifest_path"] = str(manifest_path.resolve())
        rows.append(row)
    rows.sort(key=lambda row: float(row.get("saved_at") or 0), reverse=True)
    return rows


def load_recovery_snapshot(
    recovery_path: str | Path,
    *,
    asset_root: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload, load_report = load_painter_document(
        recovery_path, asset_root=asset_root
    )
    return payload, {
        "schema": "tigerstudio.painter.recovery.load_report.v1",
        **load_report,
    }


def discard_recovery_snapshot(
    session_id: str,
    *,
    root: str | Path | None = None,
) -> bool:
    recovery_path, manifest_path = _paths(session_id, root)
    existed = recovery_path.exists() or manifest_path.exists()
    recovery_path.unlink(missing_ok=True)
    manifest_path.unlink(missing_ok=True)
    return existed


def prune_recovery_snapshots(
    *,
    root: str | Path | None = None,
    keep: int = 12,
) -> int:
    keep_count = _recovery_keep_count(keep)
    rows = list_recovery_snapshots(root=root)
    removed = 0
    for row in rows[keep_count:]:
        Path(str(row["recovery_path"])).unlink(missing_ok=True)
        Path(str(row["manifest_path"])).unlink(missing_ok=True)
        removed += 1
    return removed


__all__ = [
    "SCHEMA",
    "LEGACY_SCHEMA_V1",
    "RECOVERY_RETENTION_CONTRACT",
    "discard_recovery_snapshot",
    "list_recovery_snapshots",
    "load_recovery_snapshot",
    "inspect_recovery_archive",
    "painter_recovery_dir",
    "prune_recovery_snapshots",
    "save_recovery_snapshot",
    "submit_recovery_snapshot",
]
