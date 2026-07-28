"""Versioned single-file persistence for standalone Tiger Studio Painter."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


PAINTER_DOCUMENT_SCHEMA = "tigerstudio.painter.document.v1"
PAINTER_DOCUMENT_VERSION = 1
PAINTER_DOCUMENT_EXTENSION = ".tspaint"
_DOCUMENT_ENTRY = "document.json"
_MAX_DOCUMENT_BYTES = 16 * 1024 * 1024
_MAX_ASSET_BYTES = 512 * 1024 * 1024


class PainterDocumentError(ValueError):
    pass


def normalize_painter_document_path(path: str | Path) -> Path:
    output = Path(path)
    if output.suffix.casefold() != PAINTER_DOCUMENT_EXTENSION:
        output = output.with_suffix(PAINTER_DOCUMENT_EXTENSION)
    return output


def _safe_asset_name(path: Path, category: str, index: int) -> str:
    suffix = path.suffix.casefold()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        suffix = ".bin"
    digest = hashlib.blake2b(str(path).encode("utf-8"), digest_size=6).hexdigest()
    return f"assets/{category}/{index:03d}_{digest}{suffix}"


def _asset_uri(entry: str) -> str:
    return f"asset://{entry}"


def _embed_external_paths(document: dict[str, Any]) -> tuple[dict[str, bytes], list[str]]:
    assets: dict[str, bytes] = {}
    missing: list[str] = []

    def embed(row: dict[str, Any], key: str, category: str, index: int) -> None:
        raw = str(row.get(key) or "").strip()
        if not raw or raw.startswith("asset://"):
            return
        path = Path(raw)
        try:
            if not path.is_file():
                missing.append(raw)
                return
            entry = _safe_asset_name(path, category, index)
            assets[entry] = path.read_bytes()
            row[key] = _asset_uri(entry)
        except OSError:
            missing.append(raw)

    board = document.get("reference_board")
    if isinstance(board, dict):
        for index, row in enumerate(board.get("references") or []):
            if isinstance(row, dict):
                embed(row, "path", "references", index)
    for index, row in enumerate(document.get("stickers") or []):
        if isinstance(row, dict):
            embed(row, "png_path", "stickers", index)
    pbr = document.get("pbr")
    if isinstance(pbr, dict):
        embed(pbr, "source_path", "pbr", 0)
    ui_document = document.get("ui_document")
    if isinstance(ui_document, dict):
        image_index = 0
        for row in ui_document.get("objects") or []:
            if not isinstance(row, dict):
                continue
            content = row.get("content")
            if not isinstance(content, dict):
                continue
            if str(content.get("source_path") or "").strip():
                embed(
                    content,
                    "source_path",
                    "ui-images",
                    image_index,
                )
                image_index += 1
    return assets, missing


def save_painter_document(
    path: str | Path,
    document: Mapping[str, Any],
    *,
    background_png: bytes | None = None,
) -> dict[str, Any]:
    output = normalize_painter_document_path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = copy.deepcopy(dict(document))
    payload["schema"] = PAINTER_DOCUMENT_SCHEMA
    payload["format_version"] = PAINTER_DOCUMENT_VERSION
    assets, missing = _embed_external_paths(payload)
    if background_png:
        assets["assets/background.png"] = bytes(background_png)
        payload.setdefault("background", {})["asset"] = _asset_uri(
            "assets/background.png"
        )
    payload["asset_manifest"] = [
        {
            "entry": entry,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        for entry, data in sorted(assets.items())
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > _MAX_DOCUMENT_BYTES:
        raise PainterDocumentError("Painter document metadata is too large")
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=str(output.parent),
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            archive.writestr(_DOCUMENT_ENTRY, encoded)
            for entry, data in sorted(assets.items()):
                archive.writestr(entry, data)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)
    return {
        "schema": "tigerstudio.painter.document.save_report.v1",
        "path": str(output.resolve()),
        "format": PAINTER_DOCUMENT_SCHEMA,
        "format_version": PAINTER_DOCUMENT_VERSION,
        "asset_count": len(assets),
        "missing_external_assets": missing,
        "bytes": output.stat().st_size,
    }


def _safe_archive_entry(value: str) -> str:
    entry = PurePosixPath(str(value or ""))
    if entry.is_absolute() or ".." in entry.parts:
        raise PainterDocumentError(f"Unsafe Painter archive entry: {value}")
    return entry.as_posix()


def _resolve_asset_uris(value: Any, mapping: Mapping[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_asset_uris(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_asset_uris(item, mapping) for item in value]
    if isinstance(value, str) and value.startswith("asset://"):
        return mapping.get(value[8:], value)
    return value


def load_painter_document(
    path: str | Path,
    *,
    asset_root: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = Path(path)
    if not source.is_file():
        raise PainterDocumentError(f"Painter document does not exist: {source}")
    extraction_root = Path(
        asset_root
        or tempfile.mkdtemp(prefix=f"tigerstudio_painter_{source.stem}_")
    )
    extraction_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source, "r") as archive:
        try:
            info = archive.getinfo(_DOCUMENT_ENTRY)
        except KeyError as exc:
            raise PainterDocumentError("Painter document.json is missing") from exc
        if info.file_size > _MAX_DOCUMENT_BYTES:
            raise PainterDocumentError("Painter document metadata is too large")
        try:
            document = json.loads(archive.read(info).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PainterDocumentError("Painter document metadata is invalid") from exc
        if not isinstance(document, dict):
            raise PainterDocumentError("Painter document root must be an object")
        if document.get("schema") != PAINTER_DOCUMENT_SCHEMA:
            raise PainterDocumentError("Unsupported Painter document schema")
        version = int(document.get("format_version", 0) or 0)
        if version < 1 or version > PAINTER_DOCUMENT_VERSION:
            raise PainterDocumentError(
                f"Unsupported Painter document version: {version}"
            )
        total = 0
        mapping: dict[str, str] = {}
        for row in document.get("asset_manifest") or []:
            if not isinstance(row, dict):
                continue
            entry = _safe_archive_entry(str(row.get("entry") or ""))
            if not entry:
                continue
            try:
                asset_info = archive.getinfo(entry)
            except KeyError as exc:
                raise PainterDocumentError(
                    f"Painter asset is missing: {entry}"
                ) from exc
            total += int(asset_info.file_size)
            if total > _MAX_ASSET_BYTES:
                raise PainterDocumentError("Painter document assets are too large")
            data = archive.read(asset_info)
            expected = str(row.get("sha256") or "")
            if expected and hashlib.sha256(data).hexdigest() != expected:
                raise PainterDocumentError(f"Painter asset checksum failed: {entry}")
            target = extraction_root.joinpath(*PurePosixPath(entry).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            mapping[entry] = str(target.resolve())
    resolved = _resolve_asset_uris(document, mapping)
    return resolved, {
        "schema": "tigerstudio.painter.document.load_report.v1",
        "path": str(source.resolve()),
        "format": PAINTER_DOCUMENT_SCHEMA,
        "format_version": int(resolved["format_version"]),
        "asset_count": len(mapping),
        "asset_root": str(extraction_root.resolve()),
    }


__all__ = [
    "PAINTER_DOCUMENT_EXTENSION",
    "PAINTER_DOCUMENT_SCHEMA",
    "PAINTER_DOCUMENT_VERSION",
    "PainterDocumentError",
    "load_painter_document",
    "normalize_painter_document_path",
    "save_painter_document",
]
