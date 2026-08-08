"""Data contracts for Tiger Studio's dependency-free AEP inspector."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class AepSafetyLimits:
    max_file_bytes: int = 512 * 1024 * 1024
    max_chunk_bytes: int = 256 * 1024 * 1024
    max_chunks: int = 250_000
    max_depth: int = 64
    max_strings: int = 20_000
    max_string_chars: int = 4_096


@dataclass(frozen=True, slots=True)
class AepChunk:
    tag: str
    size: int
    offset: int
    payload_offset: int
    depth: int
    list_type: str | None = None
    children: tuple["AepChunk", ...] = ()
    opaque: bool = False

    @property
    def payload_end(self) -> int:
        return self.payload_offset + self.size

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def to_summary(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "tag": self.tag,
            "size": self.size,
            "offset": self.offset,
            "depth": self.depth,
        }
        if self.list_type is not None:
            value["list_type"] = self.list_type
        if self.opaque:
            value["opaque"] = True
        if self.children:
            value["children"] = [child.to_summary() for child in self.children]
        return value


@dataclass(frozen=True, slots=True)
class AepDocument:
    source_path: str
    data: bytes = field(repr=False)
    root: AepChunk
    xmp_offset: int
    xmp_text: str

    @property
    def file_size(self) -> int:
        return len(self.data)

    def payload(self, chunk: AepChunk) -> memoryview:
        return memoryview(self.data)[chunk.payload_offset : chunk.payload_end]


class AepParseError(ValueError):
    """Raised when an AEP violates the structural or safety contract."""
