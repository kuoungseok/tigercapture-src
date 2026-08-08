"""Bounded RIFX reader for After Effects project files.

This module parses the generic container only. It never executes expressions,
scripts, plug-ins, fonts, or linked media.
"""
from __future__ import annotations

import struct
from pathlib import Path

from .model import AepChunk, AepDocument, AepParseError, AepSafetyLimits

_CONTAINER_TAGS = frozenset({"RIFX", "LIST"})
_RAW_CONTAINER_TAGS = frozenset({"fnam", "pdnm", "RCom", "tdsn"})
_OPAQUE_LIST_TYPES = frozenset({"btdk"})


class _Reader:
    def __init__(self, data: bytes, limits: AepSafetyLimits) -> None:
        self.data = data
        self.limits = limits
        self.chunk_count = 0

    def parse(self, source_path: str) -> AepDocument:
        if len(self.data) < 12:
            raise AepParseError("AEP is too small to contain a RIFX/Egg! header")
        if len(self.data) > self.limits.max_file_bytes:
            raise AepParseError(
                f"AEP exceeds the {self.limits.max_file_bytes}-byte safety limit"
            )
        root = self._read_chunk(0, len(self.data), depth=0, require_root=True)
        if root.tag != "RIFX" or root.list_type != "Egg!":
            raise AepParseError(
                f"expected RIFX/Egg! root, got {root.tag}/{root.list_type or '-'}"
            )
        xmp_offset = 8 + root.size
        xmp_bytes = self.data[xmp_offset:]
        xmp_text = xmp_bytes.decode("utf-8", errors="replace")
        return AepDocument(source_path, self.data, root, xmp_offset, xmp_text)

    def _read_chunk(
        self,
        offset: int,
        boundary: int,
        *,
        depth: int,
        require_root: bool = False,
    ) -> AepChunk:
        if depth > self.limits.max_depth:
            raise AepParseError(f"chunk nesting exceeds {self.limits.max_depth}")
        if offset + 8 > boundary:
            raise AepParseError(f"truncated chunk header at byte {offset}")
        self.chunk_count += 1
        if self.chunk_count > self.limits.max_chunks:
            raise AepParseError(f"chunk count exceeds {self.limits.max_chunks}")

        raw_tag = self.data[offset : offset + 4]
        tag = raw_tag.decode("latin-1")
        size = struct.unpack_from(">I", self.data, offset + 4)[0]
        if size > self.limits.max_chunk_bytes:
            raise AepParseError(
                f"chunk {tag!r} at {offset} exceeds the chunk safety limit"
            )
        payload_offset = offset + 8
        payload_end = payload_offset + size
        if payload_end > boundary:
            raise AepParseError(
                f"chunk {tag!r} at {offset} ends at {payload_end}, beyond {boundary}"
            )
        if require_root and tag != "RIFX":
            raise AepParseError(f"expected RIFX header, got {tag!r}")

        list_type: str | None = None
        children: tuple[AepChunk, ...] = ()
        opaque = False
        if tag in _CONTAINER_TAGS:
            if size < 4:
                raise AepParseError(f"container {tag!r} at {offset} has no list type")
            list_type = self.data[payload_offset : payload_offset + 4].decode("latin-1")
            opaque = list_type in _OPAQUE_LIST_TYPES
            if not opaque:
                children = self._read_children(
                    payload_offset + 4,
                    payload_end,
                    depth=depth + 1,
                )
        elif tag in _RAW_CONTAINER_TAGS:
            children = self._read_children(payload_offset, payload_end, depth=depth + 1)
        return AepChunk(
            tag=tag,
            size=size,
            offset=offset,
            payload_offset=payload_offset,
            depth=depth,
            list_type=list_type,
            children=children,
            opaque=opaque,
        )

    def _read_children(self, offset: int, boundary: int, *, depth: int) -> tuple[AepChunk, ...]:
        children: list[AepChunk] = []
        cursor = offset
        while cursor < boundary:
            child = self._read_chunk(cursor, boundary, depth=depth)
            children.append(child)
            cursor = child.payload_end + (child.size & 1)
        if cursor != boundary:
            raise AepParseError(
                f"chunk alignment drift: expected byte {boundary}, reached {cursor}"
            )
        return tuple(children)


def parse_aep_bytes(
    data: bytes,
    *,
    source_path: str = "<memory>",
    limits: AepSafetyLimits | None = None,
) -> AepDocument:
    return _Reader(bytes(data), limits or AepSafetyLimits()).parse(source_path)


def parse_aep_file(
    path: str | Path,
    *,
    limits: AepSafetyLimits | None = None,
) -> AepDocument:
    source = Path(path)
    if source.suffix.lower() != ".aep":
        raise AepParseError(f"expected an .aep file, got {source.name!r}")
    size = source.stat().st_size
    active_limits = limits or AepSafetyLimits()
    if size > active_limits.max_file_bytes:
        raise AepParseError(
            f"AEP exceeds the {active_limits.max_file_bytes}-byte safety limit"
        )
    return parse_aep_bytes(
        source.read_bytes(), source_path=str(source.resolve()), limits=active_limits
    )
