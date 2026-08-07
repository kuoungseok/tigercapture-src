"""Decode Figma ``vectorNetworkBlob`` payloads into SVG path data.

REST publishes vector shapes as flattened ``fillGeometry`` path strings, but a
``.fig`` archive stores the editable vector network instead: a list of vertices,
a list of cubic-Bezier segments referencing those vertices, and a list of
regions that group segments into closed loops. The blob bytes live in
``Message.blobs`` and ``VectorData.vectorNetworkBlob`` holds the index.

The layout is little-endian and fixed-width::

    u4 vertex_count, u4 segment_count, u4 region_count
    vertex[]  : u4 flags, f4 x, f4 y
    segment[] : u4 flags, u4 start_idx, f4 start_tx, f4 start_ty,
                          u4 end_idx,   f4 end_tx,   f4 end_ty
    region[]  : u4 winding_rule, u4 loop_count,
                loop[] : u4 segment_index_count, u4 segment_indices[]

Tangents are offsets from their vertex; a segment whose four tangent values are
zero is a straight line. Like the rest of the ``.fig`` reader this layout is
reverse engineered, so every parse failure is reported rather than raised.
"""
from __future__ import annotations

import struct
from typing import Any, Mapping, Sequence

__all__ = [
    "VectorNetwork",
    "VectorNetworkError",
    "parse_vector_network",
    "vector_network_fill_paths",
]


class VectorNetworkError(ValueError):
    pass


_HEADER = struct.Struct("<III")
_VERTEX = struct.Struct("<Iff")
_SEGMENT = struct.Struct("<IIffIff")
_UINT = struct.Struct("<I")

_WINDING_RULES = {0: "NONZERO", 1: "EVENODD"}

# Guards against a misread length prefix allocating unbounded memory.
_MAX_ELEMENTS = 1 << 22


class VectorNetwork:
    """Vertices, segments and regions recovered from one blob."""

    __slots__ = ("vertices", "segments", "regions")

    def __init__(
        self,
        vertices: list[tuple[float, float]],
        segments: list[tuple[int, float, float, int, float, float]],
        regions: list[tuple[str, list[list[int]]]],
    ) -> None:
        self.vertices = vertices
        self.segments = segments
        self.regions = regions

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"VectorNetwork(vertices={len(self.vertices)}, "
            f"segments={len(self.segments)}, regions={len(self.regions)})"
        )


def _check_count(count: int, label: str) -> None:
    if count > _MAX_ELEMENTS:
        raise VectorNetworkError(f"Implausible {label} count {count}; the blob is likely truncated")


def parse_vector_network(blob: bytes | bytearray | memoryview) -> VectorNetwork:
    data = bytes(blob)
    if len(data) < _HEADER.size:
        raise VectorNetworkError("Blob is too small to contain a vector network header")
    vertex_count, segment_count, region_count = _HEADER.unpack_from(data, 0)
    for count, label in (
        (vertex_count, "vertex"),
        (segment_count, "segment"),
        (region_count, "region"),
    ):
        _check_count(count, label)

    offset = _HEADER.size
    required = offset + vertex_count * _VERTEX.size + segment_count * _SEGMENT.size
    if required > len(data):
        raise VectorNetworkError(
            f"Blob needs {required} bytes for {vertex_count} vertices and "
            f"{segment_count} segments but holds {len(data)}"
        )

    vertices: list[tuple[float, float]] = []
    for _ in range(vertex_count):
        _flags, x, y = _VERTEX.unpack_from(data, offset)
        vertices.append((x, y))
        offset += _VERTEX.size

    segments: list[tuple[int, float, float, int, float, float]] = []
    for _ in range(segment_count):
        _flags, start, start_tx, start_ty, end, end_tx, end_ty = _SEGMENT.unpack_from(data, offset)
        segments.append((start, start_tx, start_ty, end, end_tx, end_ty))
        offset += _SEGMENT.size

    regions: list[tuple[str, list[list[int]]]] = []
    for _ in range(region_count):
        if offset + 8 > len(data):
            raise VectorNetworkError("Blob ends before its region table")
        (winding,) = _UINT.unpack_from(data, offset)
        (loop_count,) = _UINT.unpack_from(data, offset + 4)
        offset += 8
        _check_count(loop_count, "loop")
        loops: list[list[int]] = []
        for _ in range(loop_count):
            if offset + 4 > len(data):
                raise VectorNetworkError("Blob ends before a region loop length")
            (index_count,) = _UINT.unpack_from(data, offset)
            offset += 4
            _check_count(index_count, "loop segment")
            if offset + index_count * 4 > len(data):
                raise VectorNetworkError("Blob ends before a region loop body")
            loops.append(list(_UINT.unpack_from(data, offset + i * 4)[0] for i in range(index_count)))
            offset += index_count * 4
        regions.append((_WINDING_RULES.get(winding, "NONZERO"), loops))

    return VectorNetwork(vertices, segments, regions)


def _format(value: float) -> str:
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _point(x: float, y: float) -> str:
    return f"{_format(x)} {_format(y)}"


def _loop_path(
    network: VectorNetwork,
    loop: Sequence[int],
    scale_x: float,
    scale_y: float,
    *,
    close: bool,
) -> str:
    segments = network.segments
    vertices = network.vertices

    def vertex(index: int) -> tuple[float, float]:
        x, y = vertices[index]
        return x * scale_x, y * scale_y

    commands: list[str] = []
    current: int | None = None
    for position, segment_index in enumerate(loop):
        if segment_index >= len(segments):
            raise VectorNetworkError(f"Loop references segment {segment_index} beyond the table")
        start, start_tx, start_ty, end, end_tx, end_ty = segments[segment_index]
        if start >= len(vertices) or end >= len(vertices):
            raise VectorNetworkError("Segment references a vertex beyond the table")
        if position == 0:
            # Orient the first segment so its far end meets the next segment;
            # loops are stored as an unordered-direction chain.
            if len(loop) > 1 and loop[1] < len(segments):
                next_start, _a, _b, next_end, _c, _d = segments[loop[1]]
                if start in (next_start, next_end) and end not in (next_start, next_end):
                    start, end = end, start
                    start_tx, start_ty, end_tx, end_ty = end_tx, end_ty, start_tx, start_ty
            current = start
            commands.append(f"M{_point(*vertex(start))}")
        elif current == end:
            # Traverse this segment backwards so the chain stays connected.
            start, end = end, start
            start_tx, start_ty, end_tx, end_ty = end_tx, end_ty, start_tx, start_ty
        elif current != start:
            raise VectorNetworkError("Loop segments do not form a connected chain")

        end_x, end_y = vertex(end)
        if start_tx == 0.0 and start_ty == 0.0 and end_tx == 0.0 and end_ty == 0.0:
            commands.append(f"L{_point(end_x, end_y)}")
        else:
            start_x, start_y = vertex(start)
            c1 = (start_x + start_tx * scale_x, start_y + start_ty * scale_y)
            c2 = (end_x + end_tx * scale_x, end_y + end_ty * scale_y)
            commands.append(f"C{_point(*c1)} {_point(*c2)} {_point(end_x, end_y)}")
        current = end

    if not commands:
        return ""
    if close:
        commands.append("Z")
    return "".join(commands)


def _open_chains(network: VectorNetwork) -> list[list[int]]:
    """Group segments into connected runs for networks without regions."""

    remaining = list(range(len(network.segments)))
    chains: list[list[int]] = []
    while remaining:
        seed = remaining.pop(0)
        chain = [seed]
        start, _a, _b, end, _c, _d = network.segments[seed]
        head, tail = start, end
        extended = True
        while extended:
            extended = False
            for index in list(remaining):
                seg_start, _e, _f, seg_end, _g, _h = network.segments[index]
                if seg_start == tail or seg_end == tail:
                    tail = seg_end if seg_start == tail else seg_start
                    chain.append(index)
                    remaining.remove(index)
                    extended = True
                elif seg_start == head or seg_end == head:
                    head = seg_end if seg_start == head else seg_start
                    chain.insert(0, index)
                    remaining.remove(index)
                    extended = True
        chains.append(chain)
    return chains


def vector_network_fill_paths(
    network: VectorNetwork,
    *,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> list[dict[str, str]]:
    """Build REST-shaped ``fillGeometry`` rows from a vector network.

    Regions become closed subpaths grouped by winding rule. A network with no
    regions is an open path, so its connected runs are emitted unclosed.
    """

    rows: list[dict[str, str]] = []
    if network.regions:
        for winding_rule, loops in network.regions:
            subpaths = [
                _loop_path(network, loop, scale_x, scale_y, close=True)
                for loop in loops
                if loop
            ]
            path = "".join(subpath for subpath in subpaths if subpath)
            if path:
                rows.append({"path": path, "windingRule": winding_rule})
        return rows

    subpaths = [
        _loop_path(network, chain, scale_x, scale_y, close=False)
        for chain in _open_chains(network)
    ]
    path = "".join(subpath for subpath in subpaths if subpath)
    if path:
        rows.append({"path": path, "windingRule": "NONZERO"})
    return rows


def fig_vector_geometry(
    node: Mapping[str, Any],
    blobs: Sequence[Any],
    *,
    width: float,
    height: float,
) -> tuple[list[dict[str, str]], str]:
    """Resolve one node's ``vectorData`` into fill geometry rows.

    Returns the rows plus a warning string (empty when nothing went wrong).
    """

    vector_data = node.get("vectorData")
    if not isinstance(vector_data, Mapping):
        return [], ""
    index = vector_data.get("vectorNetworkBlob")
    if not isinstance(index, int) or isinstance(index, bool):
        return [], ""
    if index < 0 or index >= len(blobs):
        return [], f"fig_vector_blob_missing:{index}"
    entry = blobs[index]
    raw = entry.get("bytes") if isinstance(entry, Mapping) else entry
    if not isinstance(raw, (bytes, bytearray)):
        return [], f"fig_vector_blob_unreadable:{index}"

    # Vertices are authored against normalizedSize; the node may be scaled.
    normalized = vector_data.get("normalizedSize")
    scale_x = scale_y = 1.0
    if isinstance(normalized, Mapping):
        base_width = float(normalized.get("x") or 0.0)
        base_height = float(normalized.get("y") or 0.0)
        if base_width > 0.0 and width > 0.0:
            scale_x = width / base_width
        if base_height > 0.0 and height > 0.0:
            scale_y = height / base_height

    try:
        network = parse_vector_network(raw)
        return vector_network_fill_paths(network, scale_x=scale_x, scale_y=scale_y), ""
    except (VectorNetworkError, struct.error) as exc:
        return [], f"fig_vector_network_unparsed:{exc}"
