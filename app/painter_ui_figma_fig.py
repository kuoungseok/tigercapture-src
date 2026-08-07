"""Reader for Figma ``.fig`` archives.

A ``.fig`` file is either a ZIP container holding ``canvas.fig`` plus loose
image blobs, or the bare ``fig-kiwi`` payload itself. The payload carries an
8-byte prelude, a uint32 version, and a sequence of length-prefixed chunks. The
first chunk is the Kiwi schema, the second is the encoded document message.
Older files compress both chunks with raw deflate; newer files switch the
message chunk to zstd.

This module unwraps that container and hands the message to
:mod:`app.painter_ui_figma_kiwi`. Mapping the decoded node array onto the REST
node shape lives in :mod:`app.painter_ui_figma_fig_rest`.

The ``.fig`` layout is not a documented Figma contract; it is reverse
engineered, so callers must treat failures as expected and keep the REST import
path as the supported route.
"""
from __future__ import annotations

import io
import json
import struct
import zipfile
import zlib
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_figma_kiwi import KiwiError, KiwiSchema, decode_binary_schema

__all__ = [
    "FIG_CANVAS_ENTRY",
    "FIG_PRELUDES",
    "FigArchive",
    "PainterUIFigError",
    "decode_fig_payload",
    "read_fig_archive",
    "zstd_decompress",
]


class PainterUIFigError(ValueError):
    pass


FIG_CANVAS_ENTRY = "canvas.fig"

# Figma Design writes ``fig-kiwi``; FigJam boards write ``fig-jam.``. Both are
# exactly 8 bytes and share the chunk layout that follows.
FIG_PRELUDES: tuple[bytes, ...] = (b"fig-kiwi", b"fig-jam.")

_ZIP_MAGIC = b"PK\x03\x04"
_ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
_PRELUDE_SIZE = 8
_UINT32 = struct.Struct("<I")

# A single chunk larger than this almost certainly means the length prefix was
# misread, so fail loudly instead of trying to allocate the whole address space.
_MAX_CHUNK_BYTES = 1 << 31


def zstd_decompress(data: bytes) -> bytes:
    """Decompress zstd via the stdlib on 3.14+, else a permissive PyPI backend."""

    try:
        from compression import zstd as _stdlib_zstd
    except ImportError:
        pass
    else:
        return _stdlib_zstd.decompress(data)

    try:
        import zstandard
    except ImportError:
        pass
    else:
        # Figma does not write the content size into the frame header, so the
        # streaming reader is required rather than the one-shot decompress.
        with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(data)) as reader:
            return reader.read()

    try:
        import pyzstd
    except ImportError as exc:
        raise PainterUIFigError(
            "This .fig file uses zstd compression. Install 'zstandard' "
            "(pip install zstandard) or run on Python 3.14+, which ships "
            "compression.zstd in the standard library."
        ) from exc
    return pyzstd.decompress(data)


def _inflate_chunk(data: bytes, *, label: str) -> bytes:
    if not data:
        return b""
    if data[:4] == _ZSTD_MAGIC:
        try:
            return zstd_decompress(data)
        except PainterUIFigError:
            raise
        except Exception as exc:  # noqa: BLE001 - backend-specific failures vary
            raise PainterUIFigError(f"Could not zstd-decompress the {label} chunk: {exc}") from exc
    # Raw deflate (no zlib header) is what the reference writer emits. Fall back
    # to a zlib-wrapped stream, then to the literal bytes, because a few
    # exporters store small chunks uncompressed.
    for wbits in (-zlib.MAX_WBITS, zlib.MAX_WBITS):
        try:
            return zlib.decompress(data, wbits)
        except zlib.error:
            continue
    return data


def _split_chunks(payload: bytes) -> list[bytes]:
    offset = _PRELUDE_SIZE + 4
    chunks: list[bytes] = []
    total = len(payload)
    while offset + 4 <= total:
        (size,) = _UINT32.unpack_from(payload, offset)
        offset += 4
        if size > _MAX_CHUNK_BYTES:
            raise PainterUIFigError(f"Chunk length {size} is implausible; the payload is likely truncated")
        end = offset + size
        if end > total:
            raise PainterUIFigError(
                f"Chunk length {size} exceeds the remaining {total - offset} bytes"
            )
        chunks.append(payload[offset:end])
        offset = end
    return chunks


def decode_fig_payload(payload: bytes) -> tuple[dict[str, Any], KiwiSchema, int]:
    """Decode a bare ``fig-kiwi`` payload into ``(message, schema, version)``."""

    if len(payload) < _PRELUDE_SIZE + 4:
        raise PainterUIFigError("Payload is too small to be a fig-kiwi document")
    prelude = payload[:_PRELUDE_SIZE]
    if prelude not in FIG_PRELUDES:
        readable = prelude.decode("ascii", "replace")
        raise PainterUIFigError(f"Unexpected prelude {readable!r}; expected one of {FIG_PRELUDES}")
    (version,) = _UINT32.unpack_from(payload, _PRELUDE_SIZE)

    chunks = _split_chunks(payload)
    if len(chunks) < 2:
        raise PainterUIFigError(f"Expected a schema and a data chunk, found {len(chunks)}")

    schema_bytes = _inflate_chunk(chunks[0], label="schema")
    try:
        schema = decode_binary_schema(schema_bytes)
    except KiwiError as exc:
        raise PainterUIFigError(f"Could not decode the embedded Kiwi schema: {exc}") from exc

    message_bytes = _inflate_chunk(chunks[1], label="message")
    root = "Message" if schema.definition("Message") is not None else ""
    if not root:
        raise PainterUIFigError(
            "The embedded schema has no 'Message' root; this build of the .fig "
            f"format is unsupported (definitions: {len(schema.definitions)})"
        )
    try:
        message = schema.decode(message_bytes, root=root)
    except KiwiError as exc:
        raise PainterUIFigError(f"Could not decode the .fig document message: {exc}") from exc
    return message, schema, version


class FigArchive:
    """Decoded ``.fig`` contents: the document message plus embedded blobs."""

    __slots__ = ("message", "schema", "version", "images", "meta", "source")

    def __init__(
        self,
        message: Mapping[str, Any],
        schema: KiwiSchema,
        version: int,
        *,
        images: Mapping[str, bytes] | None = None,
        meta: Mapping[str, Any] | None = None,
        source: str = "",
    ) -> None:
        self.message = dict(message)
        self.schema = schema
        self.version = version
        self.images = dict(images or {})
        self.meta = dict(meta or {})
        self.source = source

    @property
    def node_changes(self) -> list[Mapping[str, Any]]:
        rows = self.message.get("nodeChanges")
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, Mapping)]

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"FigArchive(version={self.version}, nodes={len(self.node_changes)}, "
            f"images={len(self.images)})"
        )


def _read_zip_container(data: bytes, *, source: str) -> FigArchive:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        canvas_name = ""
        for name in names:
            if name.rsplit("/", 1)[-1] == FIG_CANVAS_ENTRY:
                canvas_name = name
                break
        if not canvas_name:
            raise PainterUIFigError(
                f"The .fig ZIP has no {FIG_CANVAS_ENTRY} entry (found: {', '.join(names[:8])})"
            )
        payload = archive.read(canvas_name)
        prefix = canvas_name[: -len(FIG_CANVAS_ENTRY)]

        images: dict[str, bytes] = {}
        for name in names:
            if not name.startswith(f"{prefix}images/") or name.endswith("/"):
                continue
            images[name.rsplit("/", 1)[-1]] = archive.read(name)

        meta: dict[str, Any] = {}
        meta_name = f"{prefix}meta.json"
        if meta_name in names:
            try:
                parsed = json.loads(archive.read(meta_name).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                parsed = None
            if isinstance(parsed, Mapping):
                meta = dict(parsed)

    message, schema, version = decode_fig_payload(payload)
    return FigArchive(message, schema, version, images=images, meta=meta, source=source)


def read_fig_archive(path: str | Path) -> FigArchive:
    """Read a ``.fig`` file, whether it is a ZIP container or a bare payload."""

    resolved = Path(path).expanduser()
    try:
        data = resolved.read_bytes()
    except OSError as exc:
        raise PainterUIFigError(f"Could not read {resolved}: {exc}") from exc
    if not data:
        raise PainterUIFigError(f"{resolved} is empty")

    source = str(resolved)
    if data[:4] == _ZIP_MAGIC:
        return _read_zip_container(data, source=source)
    message, schema, version = decode_fig_payload(data)
    return FigArchive(message, schema, version, source=source)
