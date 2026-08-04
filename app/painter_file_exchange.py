"""Production-oriented Painter image interchange and export preflight.

The module deliberately keeps the supported layered-PSD contract narrow.  A
feature is either represented natively, explicitly baked, or blocks export;
silently dropping Painter document semantics is never allowed.
"""
from __future__ import annotations

import io
import struct
import zlib
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageCms


FLAT_FORMATS = {"jpeg", "webp", "tiff", "png"}
BIT_DEPTHS = {8, 16}
PSD_NATIVE_BLEND_MODES = {
    "normal", "darken", "multiply", "color_burn", "linear_burn", "lighten",
    "screen", "color_dodge", "linear_dodge", "overlay", "soft_light",
    "hard_light", "difference", "exclusion", "subtract", "divide", "hue",
    "saturation", "color", "luminosity",
}


def srgb_icc_bytes() -> bytes:
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def normalize_format(path: str | Path, format_name: str = "") -> str:
    value = str(format_name or Path(path).suffix.lstrip(".")).strip().casefold()
    aliases = {"jpg": "jpeg", "tif": "tiff"}
    return aliases.get(value, value)


def exchange_preflight(
    layers: Iterable[Any],
    *,
    format_name: str,
    bit_depth: int = 8,
    color_mode: str = "RGB",
    bake_unsupported: bool = False,
) -> dict[str, Any]:
    fmt = normalize_format("", format_name)
    depth = int(bit_depth or 8)
    errors: list[str] = []
    warnings: list[str] = []
    unsupported: list[dict[str, str]] = []
    if fmt not in FLAT_FORMATS | {"psd"}:
        errors.append(f"Unsupported export format: {format_name}")
    if depth not in BIT_DEPTHS:
        errors.append(f"Unsupported bit depth: {depth}")
    if depth == 16 and fmt not in {"png", "tiff"}:
        errors.append(f"{fmt.upper()} does not support this Painter 16-bit export path")
    mode = str(color_mode or "RGB").strip().upper()
    if mode == "CMYK":
        errors.append("CMYK conversion is not implemented; export through an explicit printer-profile conversion step")
    elif mode not in {"RGB", "RGBA", "SRGB"}:
        errors.append(f"Unsupported output color mode: {color_mode}")
    if fmt == "psd":
        for layer in list(layers or []):
            layer_id = str(getattr(layer, "layer_id", "") or "")
            node_type = str(getattr(layer, "node_type", "paint") or "paint")
            reasons: list[str] = []
            if node_type == "adjustment":
                reasons.append("adjustment_layer")
            if bool(getattr(layer, "clipping", False)):
                reasons.append("clipping_mask")
            if bool(getattr(layer, "mask", [])):
                reasons.append("layer_mask")
            if str(getattr(layer, "layer_type", "standard") or "standard") == "material":
                reasons.append("material_channels")
            blend = str(getattr(layer, "blend_mode", "normal") or "normal")
            if blend not in PSD_NATIVE_BLEND_MODES:
                reasons.append(f"blend_mode:{blend}")
            for reason in reasons:
                unsupported.append({"layer_id": layer_id, "reason": reason})
        if unsupported:
            message = f"{len(unsupported)} layered PSD feature(s) require baking"
            (warnings if bake_unsupported else errors).append(message)
    return {
        "schema": "tigerstudio.painter.exchange-preflight.v1",
        "ok": not errors,
        "format": fmt,
        "bit_depth": depth,
        "color_mode": mode,
        "profile": "sRGB IEC61966-2.1",
        "profile_boundary": "default-srgb; explicit source/output ICC transform is required for conversion",
        "soft_proof": {
            "mode": "informational_srgb",
            "output_profile": "sRGB IEC61966-2.1",
            "cmyk_conversion_supported": False,
            "warning": "Printer-profile and CMYK appearance must be proofed in a color-managed finishing application.",
        },
        "unsupported": unsupported,
        "unsupported_policy": "bake" if bake_unsupported else "blocked",
        "warnings": warnings,
        "errors": errors,
    }


def print_geometry(output_settings: dict | None, width: int, height: int) -> dict[str, Any]:
    from app.painter_output import normalize_output_settings

    normalized = normalize_output_settings(output_settings, pixel_width=width, pixel_height=height)
    if normalized["mode"] != "print":
        return {"mode": "screen", "canvas_px": [width, height], "trim_rect_px": [0, 0, width, height], "safe_rect_px": [0, 0, width, height]}
    bleed = float(normalized["bleed_mm"] if normalized["include_bleed"] else 0.0)
    full_w = max(0.001, float(normalized["width_mm"]) + bleed * 2.0)
    full_h = max(0.001, float(normalized["height_mm"]) + bleed * 2.0)
    bx = int(round(width * bleed / full_w)); by = int(round(height * bleed / full_h))
    sx = int(round(width * float(normalized["safe_margin_mm"]) / full_w))
    sy = int(round(height * float(normalized["safe_margin_mm"]) / full_h))
    trim = [bx, by, max(0, width - bx * 2), max(0, height - by * 2)]
    safe = [bx + sx, by + sy, max(0, width - (bx + sx) * 2), max(0, height - (by + sy) * 2)]
    return {"mode": "print", "canvas_px": [width, height], "trim_rect_px": trim, "safe_rect_px": safe, "bleed_px": [bx, by], "settings": normalized}


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def _rgba16_values(image: Image.Image | np.ndarray) -> np.ndarray:
    if isinstance(image, Image.Image):
        return np.asarray(image.convert("RGBA"), dtype=np.uint16) * 257
    values = np.asarray(image)
    if values.ndim != 3 or values.shape[2] not in {3, 4}:
        raise ValueError("16-bit color input must be an RGB or RGBA array")
    if np.issubdtype(values.dtype, np.floating):
        values = np.uint16(np.clip(values, 0.0, 1.0) * 65535.0 + 0.5)
    elif values.dtype.kind == "u" and values.dtype.itemsize == 1:
        values = values.astype(np.uint16) * 257
    elif values.dtype.kind == "u" and values.dtype.itemsize == 2:
        values = values.astype(np.uint16, copy=True)
    else:
        raise ValueError(
            "16-bit color integer input must use uint8 or uint16 channels"
        )
    if values.shape[2] == 3:
        alpha = np.full((*values.shape[:2], 1), 65535, dtype=np.uint16)
        values = np.concatenate((values, alpha), axis=2)
    return values


def _write_png16(path: Path, image: Image.Image | np.ndarray, *, icc: bytes, ppi: int) -> None:
    rgba = _rgba16_values(image)
    height, width = rgba.shape[:2]
    raw = b"".join(b"\0" + row.astype(">u2", copy=False).tobytes() for row in rgba)
    ppm = max(1, int(round(float(ppi) / 0.0254)))
    payload = bytearray(b"\x89PNG\r\n\x1a\n")
    payload += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 16, 6, 0, 0, 0))
    payload += _png_chunk(b"iCCP", b"sRGB IEC61966-2.1\0\0" + zlib.compress(icc))
    payload += _png_chunk(b"pHYs", struct.pack(">IIB", ppm, ppm, 1))
    payload += _png_chunk(b"IDAT", zlib.compress(raw, 6))
    payload += _png_chunk(b"IEND", b"")
    path.write_bytes(payload)


def _write_png16_gray(path: Path, values: np.ndarray, *, icc: bytes, ppi: int) -> None:
    gray = np.uint16(np.clip(np.asarray(values, dtype=np.float64), 0.0, 1.0) * 65535.0 + 0.5)
    if gray.ndim != 2:
        raise ValueError("16-bit height data must be a two-dimensional scalar map")
    height, width = gray.shape
    rgb = np.repeat(gray[..., None], 3, axis=2)
    raw = b"".join(b"\0" + row.astype(">u2", copy=False).tobytes() for row in rgb)
    ppm = max(1, int(round(float(ppi) / 0.0254)))
    payload = bytearray(b"\x89PNG\r\n\x1a\n")
    payload += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 16, 2, 0, 0, 0))
    payload += _png_chunk(b"iCCP", b"sRGB IEC61966-2.1\0\0" + zlib.compress(icc))
    payload += _png_chunk(b"pHYs", struct.pack(">IIB", ppm, ppm, 1))
    payload += _png_chunk(b"IDAT", zlib.compress(raw, 6))
    payload += _png_chunk(b"IEND", b"")
    path.write_bytes(payload)


def _write_tiff16(path: Path, image: Image.Image | np.ndarray, *, icc: bytes, ppi: int) -> None:
    rgba = _rgba16_values(image)
    height, width = rgba.shape[:2]
    pixels = rgba.astype("<u2", copy=False).tobytes()
    tags: list[tuple[int, int, int, bytes | int]] = []
    tags.extend([(256, 4, 1, width), (257, 4, 1, height)])
    tags.append((258, 3, 4, struct.pack("<HHHH", 16, 16, 16, 16)))
    tags.extend([(259, 3, 1, 1), (262, 3, 1, 2)])
    tags.append((273, 4, 1, 0))
    tags.extend([(277, 3, 1, 4), (278, 4, 1, height), (279, 4, 1, len(pixels))])
    rational = struct.pack("<II", max(1, int(ppi)), 1)
    tags.extend([(282, 5, 1, rational), (283, 5, 1, rational), (284, 3, 1, 1), (296, 3, 1, 2), (338, 3, 1, 2)])
    tags.append((34675, 7, len(icc), icc))
    count = len(tags); ifd_size = 2 + count * 12 + 4
    data_offset = 8 + ifd_size
    external = bytearray(); entries = bytearray()
    strip_entry_offset = None
    for tag, field_type, item_count, value in sorted(tags):
        entries += struct.pack("<HHI", tag, field_type, item_count)
        if tag == 273:
            strip_entry_offset = len(entries)
            entries += b"\0\0\0\0"
        elif isinstance(value, int):
            entries += (struct.pack("<H", value) + b"\0\0") if field_type == 3 else struct.pack("<I", value)
        else:
            while (data_offset + len(external)) % 2:
                external += b"\0"
            entries += struct.pack("<I", data_offset + len(external)); external += value
    pixel_offset = data_offset + len(external)
    if pixel_offset % 2:
        external += b"\0"; pixel_offset += 1
    assert strip_entry_offset is not None
    entries[strip_entry_offset:strip_entry_offset + 4] = struct.pack("<I", pixel_offset)
    path.write_bytes(b"II*\0" + struct.pack("<I", 8) + struct.pack("<H", count) + entries + b"\0\0\0\0" + external + pixels)


def _write_tiff16_gray(path: Path, values: np.ndarray, *, icc: bytes, ppi: int) -> None:
    gray = np.uint16(np.clip(np.asarray(values, dtype=np.float64), 0.0, 1.0) * 65535.0 + 0.5)
    if gray.ndim != 2:
        raise ValueError("16-bit height data must be a two-dimensional scalar map")
    height, width = gray.shape
    pixels = np.repeat(gray[..., None], 3, axis=2).astype("<u2", copy=False).tobytes()
    rational = struct.pack("<II", max(1, int(ppi)), 1)
    tags: list[tuple[int, int, int, bytes | int]] = [
        (256, 4, 1, width), (257, 4, 1, height), (258, 3, 3, struct.pack("<HHH", 16, 16, 16)),
        (259, 3, 1, 1), (262, 3, 1, 2), (273, 4, 1, 0),
        (277, 3, 1, 3), (278, 4, 1, height), (279, 4, 1, len(pixels)),
        (282, 5, 1, rational), (283, 5, 1, rational), (296, 3, 1, 2),
        (34675, 7, len(icc), icc),
    ]
    count = len(tags); data_offset = 8 + 2 + count * 12 + 4
    external = bytearray(); entries = bytearray(); strip_entry_offset = None
    for tag, field_type, item_count, value in sorted(tags):
        entries += struct.pack("<HHI", tag, field_type, item_count)
        if tag == 273:
            strip_entry_offset = len(entries); entries += b"\0\0\0\0"
        elif isinstance(value, int):
            entries += (struct.pack("<H", value) + b"\0\0") if field_type == 3 else struct.pack("<I", value)
        else:
            while (data_offset + len(external)) % 2:
                external += b"\0"
            entries += struct.pack("<I", data_offset + len(external)); external += value
    pixel_offset = data_offset + len(external)
    if pixel_offset % 2:
        external += b"\0"; pixel_offset += 1
    assert strip_entry_offset is not None
    entries[strip_entry_offset:strip_entry_offset + 4] = struct.pack("<I", pixel_offset)
    path.write_bytes(b"II*\0" + struct.pack("<I", 8) + struct.pack("<H", count) + entries + b"\0\0\0\0" + external + pixels)


def export_flat_image(
    path: str | Path,
    image: Image.Image | np.ndarray,
    *,
    format_name: str = "",
    bit_depth: int = 8,
    output_settings: dict | None = None,
    quality: int = 95,
    embed_icc: bool = True,
    source_icc: bytes | str | Path | None = None,
    output_icc: bytes | str | Path | None = None,
    rendering_intent: int = 1,
) -> dict[str, Any]:
    destination = Path(path)
    fmt = normalize_format(destination, format_name)
    preflight = exchange_preflight([], format_name=fmt, bit_depth=bit_depth)
    if not preflight["ok"]:
        raise ValueError("; ".join(preflight["errors"]))
    suffix = {"jpeg": ".jpg", "webp": ".webp", "tiff": ".tiff", "png": ".png"}[fmt]
    if destination.suffix.casefold() not in ({".jpg", ".jpeg"} if fmt == "jpeg" else {suffix, ".tif"} if fmt == "tiff" else {suffix}):
        destination = destination.with_suffix(suffix)
    destination.parent.mkdir(parents=True, exist_ok=True)
    high_precision = isinstance(image, np.ndarray) and (
        np.asarray(image).dtype == np.uint16 or np.issubdtype(np.asarray(image).dtype, np.floating)
    )
    if isinstance(image, Image.Image):
        rgba = image.convert("RGBA")
    else:
        values16 = _rgba16_values(image)
        rgba = Image.fromarray(np.uint8(values16 >> 8), "RGBA")
    from app.painter_color_management import (
        inspect_icc_profile,
        transform_rgba_profile,
    )

    source_profile = (
        bytes(source_icc)
        if isinstance(source_icc, (bytes, bytearray))
        else Path(source_icc).read_bytes()
        if source_icc is not None
        else srgb_icc_bytes()
    )
    output_profile = (
        bytes(output_icc)
        if isinstance(output_icc, (bytes, bytearray))
        else Path(output_icc).read_bytes()
        if output_icc is not None
        else srgb_icc_bytes()
    )
    source_profile_info = inspect_icc_profile(source_profile)
    output_profile_info = inspect_icc_profile(output_profile)
    if not source_profile_info["valid"] or not output_profile_info["valid"]:
        raise ValueError("Painter export requires valid ICC v2 or v4 source and output profiles")
    profile_transform = {
        "schema": "tigerstudio.painter.icc-transform.v1",
        "applied": False,
        "identity_profiles": source_profile_info["sha256"] == output_profile_info["sha256"],
        "pixel_changed": False,
        "alpha_preserved": True,
        "rendering_intent": int(rendering_intent),
        "source": source_profile_info,
        "output": output_profile_info,
    }
    if source_icc is not None or output_icc is not None:
        if high_precision and not profile_transform["identity_profiles"]:
            raise ValueError(
                "16-bit ICC conversion is unavailable in the current LittleCMS/Pillow path; "
                "convert before export or use an identical output profile"
            )
        rgba, profile_transform = transform_rgba_profile(
            rgba,
            source_profile=source_profile,
            output_profile=output_profile,
            rendering_intent=rendering_intent,
        )
    icc = output_profile if embed_icc else b""
    geometry = print_geometry(output_settings, rgba.width, rgba.height)
    ppi = int((geometry.get("settings") or {}).get("ppi", 96))
    if int(bit_depth) == 16:
        if fmt == "png":
            _write_png16(destination, image if high_precision else rgba, icc=icc, ppi=ppi)
        else:
            _write_tiff16(destination, image if high_precision else rgba, icc=icc, ppi=ppi)
    else:
        kwargs: dict[str, Any] = {"dpi": (ppi, ppi)}
        if icc:
            kwargs["icc_profile"] = icc
        if fmt == "jpeg":
            rgba.convert("RGB").save(destination, "JPEG", quality=max(1, min(100, int(quality))), subsampling=0, **kwargs)
        elif fmt == "webp":
            rgba.save(destination, "WEBP", quality=max(1, min(100, int(quality))), **kwargs)
        elif fmt == "tiff":
            rgba.save(destination, "TIFF", compression="tiff_deflate", **kwargs)
        else:
            rgba.save(destination, "PNG", **kwargs)
    inspected = inspect_flat_image(destination)
    if not bool((inspected.get("integrity") or {}).get("valid", False)):
        raise ValueError("Exported image failed structural/ICC integrity inspection")
    return {
        "schema": "tigerstudio.painter.image-export.v1", "path": str(destination.resolve()),
        "format": fmt, "bit_depth": int(bit_depth), "profile": "sRGB IEC61966-2.1",
        "source_precision_bits": 16 if high_precision else 8,
        "source_precision_kind": (
            "native_high_precision" if high_precision else "promoted_from_8bit"
        ),
        "new_precision_created": False,
        "profile_transform": profile_transform,
        "icc_embedded": bool(inspected["icc_embedded"]), "geometry": geometry,
        "preflight": preflight, "inspection": inspected,
    }


def _png_integrity(data: bytes) -> dict[str, Any]:
    errors: list[str] = []
    chunks: list[str] = []
    offset = 8
    saw_iend = False
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        errors.append("invalid PNG signature")
    while not errors and offset < len(data):
        if offset + 12 > len(data):
            errors.append("truncated PNG chunk header")
            break
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(data):
            errors.append("truncated PNG chunk payload")
            break
        payload = data[offset + 8 : offset + 8 + length]
        expected = struct.unpack(">I", data[offset + 8 + length : end])[0]
        actual = zlib.crc32(kind + payload) & 0xFFFFFFFF
        label = kind.decode("latin-1", "replace")
        chunks.append(label)
        if expected != actual:
            errors.append(f"PNG CRC mismatch: {label}")
            break
        offset = end
        if kind == b"IEND":
            saw_iend = True
            if offset != len(data):
                errors.append("trailing bytes after PNG IEND")
            break
    if chunks and chunks[0] != "IHDR":
        errors.append("PNG IHDR is not first")
    if not saw_iend:
        errors.append("PNG IEND missing")
    return {"container_valid": not errors, "chunks": chunks, "errors": errors}


def _tiff_integrity(data: bytes) -> dict[str, Any]:
    errors: list[str] = []
    byte_order = data[:2]
    endian = "<" if byte_order == b"II" else ">" if byte_order == b"MM" else ""
    if not endian:
        errors.append("invalid TIFF byte order")
        return {"container_valid": False, "chunks": [], "errors": errors}
    if len(data) < 8 or struct.unpack(f"{endian}H", data[2:4])[0] != 42:
        errors.append("invalid TIFF magic")
        return {"container_valid": False, "chunks": [], "errors": errors}
    ifd_offset = struct.unpack(f"{endian}I", data[4:8])[0]
    if ifd_offset < 8 or ifd_offset + 2 > len(data):
        errors.append("TIFF first IFD offset is out of bounds")
        return {"container_valid": False, "chunks": [], "errors": errors}
    entry_count = struct.unpack(f"{endian}H", data[ifd_offset:ifd_offset + 2])[0]
    ifd_end = ifd_offset + 2 + entry_count * 12 + 4
    if ifd_end > len(data):
        errors.append("truncated TIFF IFD")
    return {
        "container_valid": not errors,
        "chunks": ["IFD0"],
        "byte_order": "little" if endian == "<" else "big",
        "first_ifd_offset": int(ifd_offset),
        "first_ifd_entry_count": int(entry_count),
        "errors": errors,
    }


def inspect_flat_image(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    raw = source.read_bytes()
    suffix = source.suffix.casefold()
    integrity = (
        _png_integrity(raw)
        if suffix == ".png"
        else _tiff_integrity(raw)
        if suffix in {".tif", ".tiff"}
        else {
            "container_valid": True,
            "chunks": [],
            "errors": [],
        }
    )
    try:
        opened = Image.open(source)
        opened.load()
    except Exception as exc:
        decode_error = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        return {
            "path": str(source.resolve()),
            "format": suffix.lstrip("."),
            "width": 0,
            "height": 0,
            "mode": "",
            "bit_depth": 0,
            "has_alpha": False,
            "icc_embedded": False,
            "icc": None,
            "integrity": {
                **integrity,
                "decode_complete": False,
                "valid": False,
                "errors": [
                    *integrity["errors"],
                    f"decode failed: {decode_error['type']}: {decode_error['message']}",
                ],
                "decode_error": decode_error,
            },
        }
    with opened as image:
        bits = int(image.info.get("bitdepth", 0) or 0)
        if str(image.format or "").upper() == "PNG":
            header = source.read_bytes()[:25]
            if len(header) >= 25 and header[:8] == b"\x89PNG\r\n\x1a\n":
                bits = int(header[24])
        elif str(image.format or "").upper() == "TIFF":
            tag_bits = image.tag_v2.get(258)
            if isinstance(tag_bits, (tuple, list)) and tag_bits:
                bits = int(max(tag_bits))
            elif tag_bits:
                bits = int(tag_bits)
        if not bits:
            bits = 16 if image.mode.startswith("I;16") else 8
        icc_payload = bytes(image.info.get("icc_profile") or b"")
        icc_report = None
        if icc_payload:
            from app.painter_color_management import inspect_icc_profile

            icc_report = inspect_icc_profile(icc_payload)
        integrity_report = {
            **integrity,
            "decode_complete": True,
            "valid": bool(integrity["container_valid"])
            and (icc_report is None or bool(icc_report["valid"])),
        }
        return {
            "path": str(source.resolve()), "format": str(image.format or "").casefold(),
            "width": image.width, "height": image.height, "mode": image.mode,
            "bit_depth": bits, "has_alpha": "A" in image.getbands(),
            "icc_embedded": bool(image.info.get("icc_profile")),
            "icc": icc_report,
            "integrity": integrity_report,
        }


def export_height_map16(
    path: str | Path,
    values: np.ndarray,
    *,
    format_name: str = "png",
    ppi: int = 96,
) -> dict[str, Any]:
    destination = Path(path); fmt = normalize_format(destination, format_name)
    if fmt not in {"png", "tiff"}:
        raise ValueError("16-bit Material Height export supports PNG or TIFF")
    destination = destination.with_suffix(".png" if fmt == "png" else ".tiff")
    destination.parent.mkdir(parents=True, exist_ok=True)
    icc = srgb_icc_bytes()
    if fmt == "png":
        _write_png16_gray(destination, values, icc=icc, ppi=ppi)
    else:
        _write_tiff16_gray(destination, values, icc=icc, ppi=ppi)
    inspected = inspect_flat_image(destination)
    if not bool((inspected.get("integrity") or {}).get("valid", False)):
        raise ValueError("Exported height map failed structural/ICC integrity inspection")
    return {
        "schema": "tigerstudio.painter.material-height-export.v1",
        "path": str(destination.resolve()),
        "format": fmt,
        "bit_depth": 16,
        "source_precision_kind": "native_float_scalar",
        "new_precision_created": False,
        "icc_embedded": inspected["icc_embedded"],
        "inspection": inspected,
    }


def export_layered_psd(
    path: str | Path,
    layers: Iterable[dict[str, Any]],
    *,
    size: tuple[int, int],
    composite: Image.Image | None = None,
    bake_unsupported: bool = False,
) -> dict[str, Any]:
    from psd_tools import PSDImage
    from psd_tools.api.layers import Group, PixelLayer
    from psd_tools.constants import BlendMode, Resource
    from psd_tools.psd.image_resources import ImageResource

    rows = list(layers)
    layer_models = [row["model"] for row in rows]
    preflight = exchange_preflight(layer_models, format_name="psd", bake_unsupported=bake_unsupported)
    if not preflight["ok"]:
        raise ValueError("; ".join(preflight["errors"]))
    destination = Path(path).with_suffix(".psd"); destination.parent.mkdir(parents=True, exist_ok=True)
    # RGBA keeps an empty Painter canvas transparent. Creating an RGB document
    # gives psd-tools an opaque black merged backdrop even when every exported
    # pixel layer carries alpha.
    psd = PSDImage.new(
        "RGBA",
        (max(1, int(size[0])), max(1, int(size[1]))),
        color=(0, 0, 0, 0),
    )
    icc = srgb_icc_bytes()
    psd.image_resources[Resource.ICC_PROFILE] = ImageResource(
        key=Resource.ICC_PROFILE,
        data=icc,
    )
    if preflight["unsupported"]:
        if composite is None:
            raise ValueError("Baked PSD export requires a composite image")
        psd.create_pixel_layer(composite.convert("RGBA"), name="Baked Artwork")
        exported_names = ["Baked Artwork"]
    else:
        exported_names = []
        blend_lookup = {item.name.casefold(): item for item in BlendMode}
        blend_lookup.update({"normal": BlendMode.NORMAL, "linear_dodge": BlendMode.LINEAR_DODGE})
        by_parent: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_parent.setdefault(str(getattr(row["model"], "parent_id", "") or ""), []).append(row)

        def emit(parent, parent_id: str) -> None:
            # Painter and psd-tools both expose the collection in paint order:
            # bottom-to-top. Reversing this made an opaque bottom layer cover
            # every layer above it in the saved PSD composite.
            for row in by_parent.get(parent_id, []):
                model = row["model"]
                node_type = str(getattr(model, "node_type", "paint") or "paint")
                name = str(getattr(model, "name", "Layer") or "Layer")
                opacity = max(0, min(255, round(int(getattr(model, "opacity", 100)) * 2.55)))
                if node_type == "group":
                    created = Group.new(parent, name=name, open_folder=bool(getattr(model, "expanded", True)))
                    created.visible = bool(getattr(model, "visible", True)); created.opacity = opacity
                    created.blend_mode = blend_lookup.get(str(getattr(model, "blend_mode", "normal") or "normal"), BlendMode.NORMAL)
                    emit(created, str(getattr(model, "layer_id", "") or ""))
                else:
                    created = PixelLayer.frompil(row["image"].convert("RGBA"), parent=parent, name=name)
                    created.opacity = opacity
                    created.blend_mode = blend_lookup.get(str(getattr(model, "blend_mode", "normal") or "normal"), BlendMode.NORMAL)
                    created.visible = bool(getattr(model, "visible", True))
                exported_names.append(name)

        emit(psd, "")
    psd.save(destination)
    composite_parity = None
    if composite is not None:
        expected = np.asarray(composite.convert("RGBA"), dtype=np.int32)
        rendered_psd = PSDImage.open(destination)
        rendered_image = rendered_psd.composite(force=True)
        if rendered_image is None:
            raise ValueError("Saved PSD did not produce a composite preview")
        rendered = np.asarray(rendered_image.convert("RGBA"), dtype=np.int32)
        # Straight-alpha RGB is undefined where alpha is zero (some PSD readers
        # normalize those hidden channels to black). Compare premultiplied
        # visible color plus alpha so transparent padding cannot create a false
        # export failure while any visible mismatch is still blocked.
        expected_pm = expected.copy()
        rendered_pm = rendered.copy()
        expected_pm[..., :3] = (
            expected_pm[..., :3] * expected_pm[..., 3:4] + 127
        ) // 255
        rendered_pm[..., :3] = (
            rendered_pm[..., :3] * rendered_pm[..., 3:4] + 127
        ) // 255
        delta = np.abs(expected_pm - rendered_pm)
        # Repeated straight/premultiplied 8-bit alpha-over can introduce at
        # most one code-unit disagreement per visible pixel-layer stage when
        # two implementations round at different points. Derive the bound
        # from the exported graph instead of choosing a visual tolerance.
        visible_pixel_layers = 1 if preflight["unsupported"] else sum(
            1 for row in rows
            if str(getattr(row["model"], "node_type", "paint") or "paint") != "group"
            and bool(getattr(row["model"], "visible", True))
        )
        max_delta_lsb = max(1, visible_pixel_layers)
        composite_parity = {
            "max_channel_delta": int(delta.max()) if delta.size else 0,
            "changed_channels": int(np.count_nonzero(delta)),
            "max_delta_lsb": max_delta_lsb,
            "visible_pixel_layer_stages": visible_pixel_layers,
            "tolerance_contract": "8bit_one_lsb_per_visible_alpha_over_stage",
            "byte_identical_claim": False,
            "within_tolerance": bool(not delta.size or int(delta.max()) <= max_delta_lsb),
        }
        if not composite_parity["within_tolerance"]:
            raise ValueError(
                "Saved PSD composite differs from Painter artwork "
                f"(max channel delta {composite_parity['max_channel_delta']})"
            )
    reopened_icc = PSDImage.open(destination).image_resources.get_data(Resource.ICC_PROFILE, b"")
    from app.painter_color_management import inspect_icc_profile
    icc_report = inspect_icc_profile(bytes(reopened_icc)) if reopened_icc else None
    if not icc_report or not icc_report["valid"]:
        raise ValueError("Saved PSD did not preserve a valid embedded ICC profile")
    return {
        "schema": "tigerstudio.painter.psd-export.v1",
        "path": str(destination.resolve()),
        "width": psd.width,
        "height": psd.height,
        "layers": exported_names,
        "icc_embedded": True,
        "icc": icc_report,
        "preflight": preflight,
        "composite_parity": composite_parity,
        "inspection": inspect_layered_psd(destination),
    }


def inspect_layered_psd(path: str | Path) -> dict[str, Any]:
    from psd_tools import PSDImage
    from psd_tools.constants import Resource

    source = Path(path)
    raw = source.read_bytes()
    errors: list[str] = []
    if len(raw) < 26:
        errors.append("PSD header is shorter than 26 bytes")
    if raw[:4] != b"8BPS":
        errors.append("invalid PSD signature")
    version = struct.unpack(">H", raw[4:6])[0] if len(raw) >= 6 else 0
    if version not in {1, 2}:
        errors.append(f"unsupported PSD version: {version}")
    header = {
        "version": int(version),
        "channels": struct.unpack(">H", raw[12:14])[0] if len(raw) >= 14 else 0,
        "height": struct.unpack(">I", raw[14:18])[0] if len(raw) >= 18 else 0,
        "width": struct.unpack(">I", raw[18:22])[0] if len(raw) >= 22 else 0,
        "depth": struct.unpack(">H", raw[22:24])[0] if len(raw) >= 24 else 0,
        "color_mode": struct.unpack(">H", raw[24:26])[0] if len(raw) >= 26 else -1,
    }
    layers: list[str] = []
    icc_report = None
    decode_complete = False
    decode_error = None
    if not errors:
        try:
            psd = PSDImage.open(source)
            layers = [str(layer.name or "") for layer in psd.descendants()]
            composite = psd.composite(force=True)
            if composite is None:
                raise ValueError("PSD composite is unavailable")
            icc = bytes(psd.image_resources.get_data(Resource.ICC_PROFILE, b"") or b"")
            if icc:
                from app.painter_color_management import inspect_icc_profile
                icc_report = inspect_icc_profile(icc)
                if not icc_report["valid"]:
                    errors.append("embedded PSD ICC profile is invalid")
            decode_complete = True
        except Exception as exc:
            decode_error = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            errors.append(
                f"decode failed: {decode_error['type']}: {decode_error['message']}"
            )
    return {
        "schema": "tigerstudio.painter.psd-inspection.v1",
        "path": str(source.resolve()),
        "header": header,
        "layers": layers,
        "icc_embedded": icc_report is not None,
        "icc": icc_report,
        "integrity": {
            "decode_complete": decode_complete,
            "valid": not errors and decode_complete,
            "errors": errors,
            "decode_error": decode_error,
        },
    }


def import_layered_psd(path: str | Path) -> dict[str, Any]:
    from psd_tools import PSDImage

    source = Path(path)
    inspection = inspect_layered_psd(source)
    if not inspection["integrity"]["valid"]:
        raise ValueError("Invalid or corrupted PSD: " + "; ".join(inspection["integrity"]["errors"]))
    psd = PSDImage.open(source)
    rows: list[dict[str, Any]] = []
    def visit(container, parent_key: str = "") -> None:
        # psd-tools exposes the same bottom-to-top paint order as Painter.
        for index, layer in enumerate(container):
            key = f"psd-{len(rows) + 1}"
            is_group = bool(layer.is_group())
            raw_image = None
            if not is_group:
                saved_opacity = int(layer.opacity)
                try:
                    layer.opacity = 255
                    rendered = layer.composite(force=True)
                    raw_image = rendered.convert("RGBA") if rendered is not None else Image.new("RGBA", (psd.width, psd.height), (0, 0, 0, 0))
                finally:
                    layer.opacity = saved_opacity
            row = {
                "source_id": key, "parent_id": parent_key, "name": str(layer.name or "Layer"),
                "node_type": "group" if is_group else "paint", "visible": bool(layer.visible),
                "opacity": int(round(int(layer.opacity) / 2.55)),
                "blend_mode": str(getattr(layer.blend_mode, "name", "normal")).casefold(),
                "image": raw_image,
                "source_index": index,
            }
            rows.append(row)
            if is_group:
                visit(layer, key)
    visit(psd)
    return {"schema": "tigerstudio.painter.psd-import.v1", "path": str(source.resolve()), "width": psd.width, "height": psd.height, "layers": rows, "inspection": inspection}


__all__ = [
    "FLAT_FORMATS", "BIT_DEPTHS", "exchange_preflight", "print_geometry",
    "export_flat_image", "inspect_flat_image", "export_layered_psd", "inspect_layered_psd", "import_layered_psd",
    "export_height_map16", "srgb_icc_bytes",
]
