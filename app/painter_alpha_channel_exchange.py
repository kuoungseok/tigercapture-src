"""PSD/TIFF interchange helpers for Painter saved-selection alpha channels."""
from __future__ import annotations

import hashlib
import struct
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from PySide6.QtGui import QImage


PSD_RGB_COLOR_CHANNELS = 3
PSD_MERGED_TRANSPARENCY_CHANNELS = 1
PSD_MAX_CHANNELS = 56
TIFF_EXTRA_SAMPLE_UNSPECIFIED = 0
TIFF_EXTRA_SAMPLE_UNASSOCIATED_ALPHA = 2


def _alpha8_bytes(mask: QImage, width: int, height: int) -> bytes:
    if not isinstance(mask, QImage) or mask.isNull():
        raise ValueError("Saved selection channel mask is missing")
    if mask.width() != width or mask.height() != height:
        raise ValueError(
            "Saved selection channel mask must match document pixel dimensions"
        )
    converted = mask.convertToFormat(QImage.Format.Format_Alpha8)
    raw = bytes(converted.constBits())
    stride = converted.bytesPerLine()
    return b"".join(
        raw[row * stride : row * stride + width]
        for row in range(height)
    )


def qimage_from_alpha8_bytes(data: bytes, width: int, height: int) -> QImage:
    expected = width * height
    if len(data) != expected:
        raise ValueError("Alpha channel byte count does not match pixel dimensions")
    return QImage(
        bytes(data),
        width,
        height,
        width,
        QImage.Format.Format_Alpha8,
    ).copy()


def saved_selection_exchange_records(
    channels: Iterable[Any],
    width: int,
    height: int,
) -> list[dict[str, Any]]:
    from app.painter_saved_selection_channels import (
        normalize_saved_selection_channel_display_mode,
        normalize_saved_selection_channel_id,
        normalize_saved_selection_channel_overlay_color,
        normalize_saved_selection_channel_overlay_opacity,
        normalize_saved_selection_name,
    )

    records: list[dict[str, Any]] = []
    names: set[str] = set()
    for channel in list(channels or []):
        channel_id = normalize_saved_selection_channel_id(
            getattr(channel, "channel_id", "")
        )
        name = normalize_saved_selection_name(getattr(channel, "name", ""))
        folded = name.casefold()
        if folded in names:
            raise ValueError("Saved selection channel names must be unique")
        names.add(folded)
        pixels = _alpha8_bytes(getattr(channel, "mask", None), width, height)
        records.append(
            {
                "channel_id": channel_id,
                "name": name,
                "pixels": pixels,
                "sha256": hashlib.sha256(pixels).hexdigest(),
                "display_mode": normalize_saved_selection_channel_display_mode(
                    getattr(channel, "display_mode", "")
                ),
                "overlay_color": normalize_saved_selection_channel_overlay_color(
                    getattr(channel, "overlay_color", "")
                ),
                "overlay_opacity_percent": (
                    normalize_saved_selection_channel_overlay_opacity(
                        getattr(channel, "overlay_opacity_percent", None)
                    )
                ),
            }
        )
    return records


def attach_saved_selection_channels_to_psd(
    psd: Any,
    channels: Iterable[Any],
    *,
    composite: Image.Image,
) -> list[dict[str, Any]]:
    """Attach merged transparency plus named selection channels to a PSD."""
    from psd_tools.constants import Resource
    from psd_tools.psd.image_resources import (
        AlphaIdentifiers,
        AlphaNamesUnicode,
        ImageResource,
    )

    width, height = int(psd.width), int(psd.height)
    records = saved_selection_exchange_records(channels, width, height)
    total_channels = (
        PSD_RGB_COLOR_CHANNELS
        + PSD_MERGED_TRANSPARENCY_CHANNELS
        + len(records)
    )
    if total_channels > PSD_MAX_CHANNELS:
        raise ValueError(
            f"PSD supports at most {PSD_MAX_CHANNELS} merged image channels"
        )
    merged = composite.convert("RGBA")
    if merged.size != (width, height):
        raise ValueError("PSD composite must match document pixel dimensions")

    psd.image_resources[Resource.ALPHA_IDENTIFIERS] = ImageResource(
        key=Resource.ALPHA_IDENTIFIERS,
        data=AlphaIdentifiers([0, *range(1, len(records) + 1)]),
    )
    psd.image_resources[Resource.ALPHA_NAMES_UNICODE] = ImageResource(
        key=Resource.ALPHA_NAMES_UNICODE,
        data=AlphaNamesUnicode([record["name"] for record in records]),
    )
    psd._record.header.channels = total_channels
    psd._record.image_data.set_data(
        [channel.tobytes() for channel in merged.split()]
        + [record["pixels"] for record in records],
        psd._record.header,
    )
    layer_info = psd._record.layer_and_mask_information.layer_info
    if layer_info is not None and layer_info.layer_count > 0:
        # Adobe PSD: a negative layer count marks the first merged alpha
        # channel as composite transparency rather than a saved selection.
        layer_info.layer_count = -layer_info.layer_count
    psd._updated = False
    return records


def read_psd_saved_selection_channels(psd: Any) -> list[dict[str, Any]]:
    """Read non-transparency merged alpha channels from an RGB PSD."""
    from psd_tools.api.utils import EXPECTED_CHANNELS, get_transparency_index
    from psd_tools.constants import Resource

    color_channels = EXPECTED_CHANNELS.get(psd.color_mode)
    if color_channels != PSD_RGB_COLOR_CHANNELS:
        raise ValueError("Painter PSD alpha import currently requires RGB color mode")
    if psd.depth != 8:
        raise ValueError(
            "Painter PSD alpha import currently requires 8-bit channel depth"
        )
    transparency_index = get_transparency_index(psd)
    identifiers = list(
        psd.image_resources.get_data(Resource.ALPHA_IDENTIFIERS) or []
    )
    if identifiers and len(identifiers) != psd.channels - color_channels:
        raise ValueError("PSD alpha identifier count is inconsistent")
    extra_indices = [
        index
        for index in range(color_channels, psd.channels)
        if index != transparency_index
    ]
    names = list(
        psd.image_resources.get_data(Resource.ALPHA_NAMES_UNICODE)
        or psd.image_resources.get_data(Resource.ALPHA_NAMES_PASCAL)
        or []
    )
    if len(names) > len(extra_indices):
        raise ValueError("PSD alpha name count exceeds extra channel count")
    rows: list[dict[str, Any]] = []
    for ordinal, channel_index in enumerate(extra_indices, start=1):
        image = psd.topil(channel=channel_index, apply_icc=False)
        if image is None:
            raise ValueError("PSD alpha channel could not be decoded")
        pixels = image.convert("L").tobytes()
        name = str(names[ordinal - 1]).strip() if ordinal <= len(names) else ""
        if not name:
            name = f"Alpha {ordinal}"
        rows.append(
            {
                "name": name,
                "channel_index": channel_index,
                "width": psd.width,
                "height": psd.height,
                "pixels": pixels,
                "sha256": hashlib.sha256(pixels).hexdigest(),
            }
        )
    return rows


def write_tiff_saved_selection_channels(
    path: str | Path,
    rgba: np.ndarray,
    records: Iterable[dict[str, Any]],
    *,
    bit_depth: int,
    icc: bytes,
    ppi: int,
) -> list[dict[str, Any]]:
    """Write one uncompressed chunky RGB TIFF with explicit extra samples."""
    destination = Path(path)
    values = np.asarray(rgba)
    if values.ndim != 3 or values.shape[2] != 4:
        raise ValueError("TIFF alpha exchange requires an RGBA array")
    if bit_depth == 8 and values.dtype != np.uint8:
        raise ValueError("8-bit TIFF alpha exchange requires uint8 RGBA")
    if bit_depth == 16 and values.dtype != np.uint16:
        raise ValueError("16-bit TIFF alpha exchange requires uint16 RGBA")
    if bit_depth not in {8, 16}:
        raise ValueError("TIFF alpha exchange supports 8-bit or 16-bit samples")
    height, width = values.shape[:2]
    rows = list(records)
    alpha_planes: list[np.ndarray] = []
    for row in rows:
        pixels = bytes(row["pixels"])
        if len(pixels) != width * height:
            raise ValueError("TIFF alpha channel byte count is inconsistent")
        plane = np.frombuffer(pixels, dtype=np.uint8).reshape(height, width)
        if bit_depth == 16:
            plane = plane.astype(np.uint16) * 257
        alpha_planes.append(plane)
    merged = np.concatenate(
        [values, *[plane[..., None] for plane in alpha_planes]],
        axis=2,
    )
    if bit_depth == 16:
        pixels = merged.astype("<u2", copy=False).tobytes()
    else:
        pixels = merged.tobytes()
    samples = merged.shape[2]
    bits = struct.pack("<" + "H" * samples, *([bit_depth] * samples))
    extra_values = [
        TIFF_EXTRA_SAMPLE_UNASSOCIATED_ALPHA,
        *([TIFF_EXTRA_SAMPLE_UNSPECIFIED] * len(rows)),
    ]
    extras = struct.pack("<" + "H" * len(extra_values), *extra_values)
    rational = struct.pack("<II", int(ppi), 1)
    tags: list[tuple[int, int, int, bytes | int]] = [
        (256, 4, 1, width),
        (257, 4, 1, height),
        (258, 3, samples, bits),
        (259, 3, 1, 1),
        (262, 3, 1, 2),
        (273, 4, 1, 0),
        (277, 3, 1, samples),
        (278, 4, 1, height),
        (279, 4, 1, len(pixels)),
        (282, 5, 1, rational),
        (283, 5, 1, rational),
        (284, 3, 1, 1),
        (296, 3, 1, 2),
        (338, 3, len(extra_values), extras),
    ]
    if icc:
        tags.append((34675, 7, len(icc), bytes(icc)))
    count = len(tags)
    data_offset = 8 + 2 + count * 12 + 4
    external = bytearray()
    entries = bytearray()
    strip_entry_offset: int | None = None
    field_widths = {3: 2, 4: 4, 5: 8, 7: 1}
    for tag, field_type, item_count, value in sorted(tags):
        entries += struct.pack("<HHI", tag, field_type, item_count)
        if tag == 273:
            strip_entry_offset = len(entries)
            entries += b"\0\0\0\0"
        elif isinstance(value, int):
            entries += (
                struct.pack("<H", value) + b"\0\0"
                if field_type == 3
                else struct.pack("<I", value)
            )
        else:
            payload = bytes(value)
            payload_size = field_widths[field_type] * item_count
            if len(payload) != payload_size:
                raise ValueError("TIFF tag payload size is inconsistent")
            if payload_size <= 4:
                entries += payload.ljust(4, b"\0")
            else:
                while (data_offset + len(external)) % 2:
                    external += b"\0"
                entries += struct.pack("<I", data_offset + len(external))
                external += payload
    pixel_offset = data_offset + len(external)
    if pixel_offset % 2:
        external += b"\0"
        pixel_offset += 1
    if strip_entry_offset is None:
        raise ValueError("TIFF strip offset tag is missing")
    entries[strip_entry_offset : strip_entry_offset + 4] = struct.pack(
        "<I", pixel_offset
    )
    destination.write_bytes(
        b"II*\0"
        + struct.pack("<I", 8)
        + struct.pack("<H", count)
        + entries
        + b"\0\0\0\0"
        + external
        + pixels
    )
    return rows


def _tiff_ifd_values(
    data: bytes,
    endian: str,
    entry: tuple[int, int, int, int],
) -> list[int]:
    _tag, field_type, count, value_or_offset = entry
    widths = {3: 2, 4: 4}
    if field_type not in widths:
        raise ValueError("TIFF alpha exchange tag type is unsupported")
    size = widths[field_type] * count
    packed_offset = struct.pack(f"{endian}I", value_or_offset)
    payload = (
        packed_offset[:size]
        if size <= 4
        else data[value_or_offset : value_or_offset + size]
    )
    if len(payload) != size:
        raise ValueError("TIFF alpha exchange tag is truncated")
    code = "H" if field_type == 3 else "I"
    return list(struct.unpack(endian + code * count, payload))


def read_tiff_saved_selection_channels(
    path: str | Path,
) -> dict[str, Any]:
    """Read exact Alpha8-compatible unspecified TIFF extra samples."""
    source = Path(path)
    data = source.read_bytes()
    byte_order = data[:2]
    endian = "<" if byte_order == b"II" else ">" if byte_order == b"MM" else ""
    if not endian or len(data) < 8:
        raise ValueError("TIFF alpha exchange header is invalid")
    if struct.unpack(f"{endian}H", data[2:4])[0] != 42:
        raise ValueError("TIFF alpha exchange magic is invalid")
    ifd_offset = struct.unpack(f"{endian}I", data[4:8])[0]
    if ifd_offset < 8 or ifd_offset + 2 > len(data):
        raise ValueError("TIFF alpha exchange IFD offset is invalid")
    count = struct.unpack(
        f"{endian}H", data[ifd_offset : ifd_offset + 2]
    )[0]
    entries: dict[int, tuple[int, int, int, int]] = {}
    for index in range(count):
        offset = ifd_offset + 2 + index * 12
        if offset + 12 > len(data):
            raise ValueError("TIFF alpha exchange IFD is truncated")
        tag, field_type, item_count, value = struct.unpack(
            f"{endian}HHII", data[offset : offset + 12]
        )
        if tag in entries:
            raise ValueError("TIFF alpha exchange contains a duplicate IFD tag")
        entries[tag] = (tag, field_type, item_count, value)
    required = {256, 257, 258, 259, 262, 273, 277, 278, 279, 284, 338}
    if not required.issubset(entries):
        raise ValueError("TIFF alpha exchange tags are incomplete")
    required_field_types = {
        256: {3, 4},
        257: {3, 4},
        258: {3},
        259: {3},
        262: {3},
        273: {3, 4},
        277: {3},
        278: {3, 4},
        279: {3, 4},
        284: {3},
        338: {3},
    }
    for tag, allowed_types in required_field_types.items():
        if entries[tag][1] not in allowed_types:
            raise ValueError(
                f"TIFF alpha exchange tag {tag} has an invalid field type"
            )

    def one(tag: int) -> int:
        values = _tiff_ifd_values(data, endian, entries[tag])
        if len(values) != 1:
            raise ValueError("TIFF alpha exchange scalar tag is invalid")
        return values[0]

    width, height = one(256), one(257)
    samples = one(277)
    bits = _tiff_ifd_values(data, endian, entries[258])
    extras = _tiff_ifd_values(data, endian, entries[338])
    if width <= 0 or height <= 0 or samples < 4:
        raise ValueError("TIFF alpha exchange dimensions or samples are invalid")
    if len(bits) != samples or len(extras) != samples - 3:
        raise ValueError("TIFF alpha exchange sample metadata is inconsistent")
    if len(set(bits)) != 1 or bits[0] not in {8, 16}:
        raise ValueError("TIFF alpha exchange requires uniform 8-bit or 16-bit samples")
    if one(259) != 1 or one(262) != 2 or one(284) != 1:
        raise ValueError(
            "TIFF alpha exchange requires uncompressed chunky RGB samples"
        )
    if one(278) != height:
        raise ValueError("TIFF alpha exchange requires one full-height strip")
    strip_offset, strip_bytes = one(273), one(279)
    expected_bytes = width * height * samples * (bits[0] // 8)
    if strip_bytes != expected_bytes or strip_offset + strip_bytes > len(data):
        raise ValueError("TIFF alpha exchange strip byte count is invalid")
    raw = data[strip_offset : strip_offset + strip_bytes]
    dtype = np.dtype(endian + ("u1" if bits[0] == 8 else "u2"))
    values = np.frombuffer(raw, dtype=dtype).reshape(height, width, samples)
    rows: list[dict[str, Any]] = []
    for extra_index, extra_type in enumerate(extras):
        if extra_type != TIFF_EXTRA_SAMPLE_UNSPECIFIED:
            continue
        plane = values[..., PSD_RGB_COLOR_CHANNELS + extra_index]
        if bits[0] == 16:
            if np.any(plane % 257):
                raise ValueError(
                    "16-bit TIFF alpha channel cannot be represented exactly as Alpha8"
                )
            plane = plane // 257
        pixels = plane.astype(np.uint8).tobytes()
        ordinal = len(rows) + 1
        rows.append(
            {
                "name": f"Alpha {ordinal}",
                "sample_index": PSD_RGB_COLOR_CHANNELS + extra_index,
                "width": width,
                "height": height,
                "pixels": pixels,
                "sha256": hashlib.sha256(pixels).hexdigest(),
            }
        )
    icc_profile = b""
    if 34675 in entries:
        _tag, field_type, item_count, value_or_offset = entries[34675]
        if field_type != 7:
            raise ValueError("TIFF ICC tag must use the UNDEFINED field type")
        icc_profile = (
            struct.pack(f"{endian}I", value_or_offset)[:item_count]
            if item_count <= 4
            else data[value_or_offset : value_or_offset + item_count]
        )
        if len(icc_profile) != item_count:
            raise ValueError("TIFF ICC profile is truncated")
    return {
        "width": width,
        "height": height,
        "bit_depth": bits[0],
        "samples_per_pixel": samples,
        "extra_samples": extras,
        "saved_selection_channels": rows,
        "names_preserved": False,
        "icc_profile": icc_profile,
    }


__all__ = [
    "PSD_MAX_CHANNELS",
    "attach_saved_selection_channels_to_psd",
    "qimage_from_alpha8_bytes",
    "read_psd_saved_selection_channels",
    "read_tiff_saved_selection_channels",
    "saved_selection_exchange_records",
    "write_tiff_saved_selection_channels",
]
