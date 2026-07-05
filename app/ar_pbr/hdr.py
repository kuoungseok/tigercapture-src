"""Small Radiance HDR loader for AR/PBR IBL previews."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
from typing import BinaryIO

import numpy as np


@dataclass(frozen=True)
class HdrImage:
    pixels: np.ndarray
    width: int
    height: int
    path: str
    format: str


def _read_line(stream: BinaryIO) -> bytes:
    line = stream.readline()
    if not line:
        raise ValueError("unexpected EOF while reading HDR header")
    return line.rstrip(b"\r\n")


def _parse_resolution(line: str) -> tuple[int, int]:
    parts = line.split()
    if len(parts) != 4:
        raise ValueError(f"unsupported HDR resolution line: {line!r}")
    if parts[0] not in {"-Y", "+Y"} or parts[2] not in {"+X", "-X"}:
        raise ValueError(f"unsupported HDR orientation: {line!r}")
    height = int(parts[1])
    width = int(parts[3])
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid HDR dimensions: {width}x{height}")
    return width, height


def _read_header(stream: BinaryIO) -> tuple[int, int, dict[str, str]]:
    first = _read_line(stream).decode("ascii", errors="replace")
    if not first.startswith("#?RADIANCE") and not first.startswith("#?RGBE"):
        raise ValueError("not a Radiance RGBE HDR file")
    metadata: dict[str, str] = {"signature": first}
    resolution = ""
    while True:
        raw = _read_line(stream)
        line = raw.decode("ascii", errors="replace")
        if not line:
            continue
        if line.startswith("-Y ") or line.startswith("+Y "):
            resolution = line
            break
        if "=" in line:
            key, value = line.split("=", 1)
            metadata[key.strip()] = value.strip()
    width, height = _parse_resolution(resolution)
    return width, height, metadata


def _read_flat_scanline(stream: BinaryIO, width: int, first_pixel: bytes | None = None) -> np.ndarray:
    expected = width * 4
    if first_pixel:
        raw = first_pixel + stream.read(expected - len(first_pixel))
    else:
        raw = stream.read(expected)
    if len(raw) != expected:
        raise ValueError("unexpected EOF while reading HDR pixel data")
    return np.frombuffer(raw, dtype=np.uint8).reshape(width, 4).copy()


def _read_rle_scanline(stream: BinaryIO, width: int) -> np.ndarray:
    header = stream.read(4)
    if len(header) != 4:
        raise ValueError("unexpected EOF while reading HDR scanline")
    if width < 8 or width > 32767 or header[0] != 2 or header[1] != 2 or (header[2] & 0x80):
        return _read_flat_scanline(stream, width, first_pixel=header)
    encoded_width = (header[2] << 8) | header[3]
    if encoded_width != width:
        raise ValueError(f"HDR scanline width mismatch: {encoded_width} != {width}")

    channels = np.empty((4, width), dtype=np.uint8)
    for channel in range(4):
        x = 0
        while x < width:
            code_raw = stream.read(1)
            if not code_raw:
                raise ValueError("unexpected EOF inside HDR RLE data")
            code = code_raw[0]
            if code > 128:
                count = code - 128
                value = stream.read(1)
                if not value:
                    raise ValueError("unexpected EOF inside HDR RLE run")
                if x + count > width:
                    raise ValueError("HDR RLE run exceeds scanline width")
                channels[channel, x:x + count] = value[0]
                x += count
            else:
                count = code
                values = stream.read(count)
                if len(values) != count:
                    raise ValueError("unexpected EOF inside HDR RLE literals")
                if x + count > width:
                    raise ValueError("HDR RLE literals exceed scanline width")
                channels[channel, x:x + count] = np.frombuffer(values, dtype=np.uint8)
                x += count
    return channels.T.copy()


def _rgbe_to_float(rgbe: np.ndarray) -> np.ndarray:
    rgb = rgbe[:, :, :3].astype(np.float32)
    exponent = rgbe[:, :, 3].astype(np.int32)
    out = np.zeros_like(rgb, dtype=np.float32)
    mask = exponent > 0
    if np.any(mask):
        scale = np.ldexp(np.ones(np.count_nonzero(mask), dtype=np.float32), exponent[mask] - (128 + 8))
        out[mask] = rgb[mask] * scale[:, None]
    return out


def load_radiance_hdr(path: str | Path) -> HdrImage:
    hdr_path = Path(path)
    with hdr_path.open("rb") as stream:
        width, height, metadata = _read_header(stream)
        rgbe = np.empty((height, width, 4), dtype=np.uint8)
        for y in range(height):
            rgbe[y] = _read_rle_scanline(stream, width)
    pixels = np.ascontiguousarray(_rgbe_to_float(rgbe), dtype=np.float32)
    if not np.isfinite(pixels).all():
        raise ValueError("HDR file produced non-finite pixel values")
    return HdrImage(
        pixels=pixels,
        width=width,
        height=height,
        path=str(hdr_path),
        format=metadata.get("FORMAT", "32-bit_rle_rgbe"),
    )


def image_stats(image: HdrImage) -> dict[str, float | int | str]:
    pixels = image.pixels
    luminance = pixels[:, :, 0] * 0.2126 + pixels[:, :, 1] * 0.7152 + pixels[:, :, 2] * 0.0722
    return {
        "path": image.path,
        "format": image.format,
        "width": image.width,
        "height": image.height,
        "min_luminance": float(luminance.min(initial=0.0)),
        "mean_luminance": float(luminance.mean()) if luminance.size else 0.0,
        "max_luminance": float(luminance.max(initial=0.0)),
        "max_stop": float(math.log2(max(float(luminance.max(initial=0.0)), 1e-8))),
    }
