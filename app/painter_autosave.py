"""Crash-safe recovery snapshots for standalone Tiger Studio Painter."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Mapping

from app.painter_document_io import load_painter_document, save_painter_document
from app.paths import runtime_data_dir


SCHEMA = "tigerstudio.painter.recovery.v1"
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="painter-recovery")


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


def _content_hash(document: Mapping[str, Any], background_png: bytes | None) -> str:
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
    return digest.hexdigest()


def save_recovery_snapshot(
    session_id: str,
    document: Mapping[str, Any],
    *,
    source_path: str = "",
    background_png: bytes | None = None,
    root: str | Path | None = None,
    keep: int = 12,
) -> dict[str, Any]:
    """Atomically replace one session snapshot and its small manifest."""

    recovery_path, manifest_path = _paths(session_id, root)
    payload = copy.deepcopy(dict(document))
    content_sha256 = _content_hash(payload, background_png)
    if manifest_path.is_file() and recovery_path.is_file():
        try:
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = {}
        if previous.get("content_sha256") == content_sha256:
            return {**previous, "skipped": True}
    save_report = save_painter_document(
        recovery_path,
        payload,
        background_png=background_png,
    )
    saved_at = time.time()
    ui_document = payload.get("ui_document")
    manifest = {
        "schema": SCHEMA,
        "session_id": str(session_id),
        "source_path": str(source_path or ""),
        "recovery_path": str(recovery_path.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "saved_at": saved_at,
        "content_sha256": content_sha256,
        "document_revision": int(
            (ui_document if isinstance(ui_document, dict) else {}).get(
                "revision", 0
            )
            or 0
        ),
        "bytes": int(save_report.get("bytes") or 0),
        "asset_count": int(save_report.get("asset_count") or 0),
        "skipped": False,
    }
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, manifest_path)
    prune_recovery_snapshots(root=root, keep=keep)
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
    return _EXECUTOR.submit(
        save_recovery_snapshot,
        session_id,
        payload,
        background_png=background,
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
        recovery_path = Path(str(row.get("recovery_path") or ""))
        if row.get("schema") != SCHEMA or not recovery_path.is_file():
            continue
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
    rows = list_recovery_snapshots(root=root)
    removed = 0
    for row in rows[max(0, int(keep)) :]:
        Path(str(row["recovery_path"])).unlink(missing_ok=True)
        Path(str(row["manifest_path"])).unlink(missing_ok=True)
        removed += 1
    return removed


__all__ = [
    "SCHEMA",
    "discard_recovery_snapshot",
    "list_recovery_snapshots",
    "load_recovery_snapshot",
    "painter_recovery_dir",
    "prune_recovery_snapshots",
    "save_recovery_snapshot",
    "submit_recovery_snapshot",
]
