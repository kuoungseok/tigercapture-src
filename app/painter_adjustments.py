"""sRGB Painter adjustment/filter engine and named palette interchange."""
from __future__ import annotations

import colorsys
import io
import struct
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from PySide6.QtCore import QBuffer, QByteArray
from PySide6.QtGui import QImage


ADJUSTMENT_TYPES = (
    "levels", "curves", "brightness_contrast", "hue_saturation",
    "color_balance", "blur", "sharpen",
)


def adjustment_parameter_contracts() -> dict[str, dict[str, object]]:
    return {
        "levels": {"model": "tiger_srgb_levels_v1", "black": [0, 254, "8-bit level"], "white": [1, 255, "8-bit level"], "gamma": [0.1, 10.0, "unitless"], "output_black": [0, 254, "8-bit level"], "output_white": [1, 255, "8-bit level"], "photoshop_algorithm_parity_claim": False},
        "curves": {"model": "tiger_piecewise_linear_rgb_curve_v1", "points": [0, 255, "8-bit input/output level"], "photoshop_algorithm_parity_claim": False},
        "brightness_contrast": {"model": "pillow_linear_factor_v1", "brightness": [-100, 100, "relative percent"], "contrast": [-100, 100, "relative percent"], "photoshop_algorithm_parity_claim": False},
        "hue_saturation": {"model": "pillow_hsv_master_v1", "hue": [-180, 180, "degrees"], "saturation": [-100, 100, "relative percent"], "lightness": [-100, 100, "relative percent"], "photoshop_algorithm_parity_claim": False},
        "color_balance": {"model": "tiger_luma_weighted_rgb_balance_v1", "shadows_midtones_highlights": [-100, 100, "signed channel amount"], "photoshop_algorithm_parity_claim": False},
        "blur": {"model": "pillow_gaussian_blur_v1", "radius": [0.0, 250.0, "pixels"], "photoshop_algorithm_parity_claim": False},
        "sharpen": {"model": "pillow_unsharp_mask_v1", "radius": [0.1, 250.0, "pixels"], "amount": [0, 500, "percent"], "threshold": [0, 255, "8-bit level"], "photoshop_algorithm_parity_claim": False},
    }


def normalize_adjustment(kind: str, settings: dict | None = None) -> tuple[str, dict]:
    name = str(kind or "").strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {"brightness": "brightness_contrast", "hue": "hue_saturation", "unsharp": "sharpen"}
    name = aliases.get(name, name)
    if name not in ADJUSTMENT_TYPES:
        raise ValueError(f"Unsupported Painter adjustment: {kind}")
    values = dict(settings or {})
    defaults = {
        "levels": {"black": 0, "white": 255, "gamma": 1.0, "output_black": 0, "output_white": 255},
        "curves": {"points": [[0, 0], [255, 255]]},
        "brightness_contrast": {"brightness": 0, "contrast": 0},
        "hue_saturation": {"hue": 0, "saturation": 0, "lightness": 0},
        "color_balance": {"shadows": [0, 0, 0], "midtones": [0, 0, 0], "highlights": [0, 0, 0], "preserve_luminosity": True},
        "blur": {"radius": 2.0},
        "sharpen": {"radius": 1.5, "amount": 120, "threshold": 2},
    }[name]
    result = {**defaults, **values}
    if name == "levels":
        result["black"] = max(0, min(254, int(result["black"])))
        result["white"] = max(result["black"] + 1, min(255, int(result["white"])))
        result["gamma"] = max(0.1, min(10.0, float(result["gamma"])))
        result["output_black"] = max(0, min(254, int(result["output_black"])))
        result["output_white"] = max(result["output_black"] + 1, min(255, int(result["output_white"])))
    elif name == "curves":
        points = sorted(
            ([max(0, min(255, int(row[0]))), max(0, min(255, int(row[1])))]
             for row in list(result.get("points") or []) if isinstance(row, (list, tuple)) and len(row) >= 2),
            key=lambda row: row[0],
        )
        result["points"] = points or [[0, 0], [255, 255]]
    elif name == "brightness_contrast":
        for key in defaults:
            result[key] = max(-100, min(100, int(result[key])))
    elif name == "hue_saturation":
        result["hue"] = max(-180, min(180, int(result["hue"])))
        for key in ("saturation", "lightness"):
            result[key] = max(-100, min(100, int(result[key])))
    elif name == "color_balance":
        for key in ("shadows", "midtones", "highlights"):
            row = list(result.get(key) or [0, 0, 0])
            result[key] = [max(-100, min(100, int(row[i] if i < len(row) else 0))) for i in range(3)]
        result["preserve_luminosity"] = bool(result.get("preserve_luminosity", True))
    elif name == "blur":
        result["radius"] = max(0.0, min(250.0, float(result["radius"])))
    elif name == "sharpen":
        result["radius"] = max(0.1, min(250.0, float(result["radius"])))
        result["amount"] = max(0, min(500, int(result["amount"])))
        result["threshold"] = max(0, min(255, int(result["threshold"])))
    return name, result


def _qimage_to_pil(image: QImage) -> Image.Image:
    data = QByteArray(); buffer = QBuffer(data)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG"); buffer.close()
    result = Image.open(io.BytesIO(bytes(data))); result.load()
    return result.convert("RGBA")


def _pil_to_qimage(image: Image.Image) -> QImage:
    stream = io.BytesIO(); image.convert("RGBA").save(stream, "PNG")
    result = QImage(); result.loadFromData(stream.getvalue(), "PNG")
    return result.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)


def _adjust_rgb(image: Image.Image, kind: str, settings: dict) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    rgb = rgba.convert("RGB")
    if kind == "levels":
        array = np.asarray(rgb, dtype=np.float32)
        black, white = float(settings["black"]), float(settings["white"])
        normalized = np.clip((array - black) / max(1.0, white - black), 0.0, 1.0)
        normalized = normalized ** (1.0 / float(settings["gamma"]))
        low, high = float(settings["output_black"]), float(settings["output_white"])
        rgb = Image.fromarray(np.uint8(np.clip(low + normalized * (high - low), 0, 255)), "RGB")
    elif kind == "curves":
        points = settings["points"]
        lut = np.interp(np.arange(256), [row[0] for row in points], [row[1] for row in points])
        array = np.asarray(rgb, dtype=np.uint8)
        rgb = Image.fromarray(np.uint8(lut[array]), "RGB")
    elif kind == "brightness_contrast":
        brightness = max(0.0, 1.0 + float(settings["brightness"]) / 100.0)
        contrast = max(0.0, 1.0 + float(settings["contrast"]) / 100.0)
        rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
        rgb = ImageEnhance.Contrast(rgb).enhance(contrast)
    elif kind == "hue_saturation":
        hsv = np.array(rgb.convert("HSV"), dtype=np.float32)
        hsv[..., 0] = np.mod(hsv[..., 0] + float(settings["hue"]) / 360.0 * 256.0, 256.0)
        hsv[..., 1] = np.clip(hsv[..., 1] * (1.0 + float(settings["saturation"]) / 100.0), 0, 255)
        light = float(settings["lightness"]) / 100.0
        hsv[..., 2] = np.clip(hsv[..., 2] + (255.0 - hsv[..., 2]) * max(0.0, light) + hsv[..., 2] * min(0.0, light), 0, 255)
        rgb = Image.fromarray(np.uint8(hsv), "HSV").convert("RGB")
    elif kind == "color_balance":
        array = np.asarray(rgb, dtype=np.float32)
        original_luma = array[..., 0] * 0.2126 + array[..., 1] * 0.7152 + array[..., 2] * 0.0722
        luma = original_luma / 255.0
        shadows = np.clip((0.67 - luma) / 0.67, 0, 1) ** 2
        highlights = np.clip((luma - 0.33) / 0.67, 0, 1) ** 2
        midtones = np.clip(1.0 - shadows - highlights, 0, 1)
        delta = np.zeros_like(array)
        for weight, key in ((shadows, "shadows"), (midtones, "midtones"), (highlights, "highlights")):
            delta += weight[..., None] * np.asarray(settings[key], dtype=np.float32) * 1.28
        array = np.clip(array + delta, 0, 255)
        if settings["preserve_luminosity"]:
            new_luma = array[..., 0] * 0.2126 + array[..., 1] * 0.7152 + array[..., 2] * 0.0722
            array = np.clip(array + (original_luma - new_luma)[..., None], 0, 255)
        rgb = Image.fromarray(np.uint8(array), "RGB")
    elif kind == "blur":
        rgb = rgb.filter(ImageFilter.GaussianBlur(float(settings["radius"])))
    elif kind == "sharpen":
        rgb = rgb.filter(ImageFilter.UnsharpMask(
            radius=float(settings["radius"]), percent=int(settings["amount"]), threshold=int(settings["threshold"])
        ))
    output = rgb.convert("RGBA"); output.putalpha(alpha)
    return output


def apply_adjustment_qimage(
    image: QImage,
    kind: str,
    settings: dict | None = None,
    *,
    mask: QImage | None = None,
    opacity: float = 1.0,
) -> QImage:
    if image.isNull():
        return QImage(image)
    name, values = normalize_adjustment(kind, settings)
    original = _qimage_to_pil(image)
    adjusted = _adjust_rgb(original, name, values)
    amount = max(0.0, min(1.0, float(opacity)))
    if isinstance(mask, QImage) and not mask.isNull():
        mask_pil = _qimage_to_pil(mask).getchannel("A").resize(original.size, Image.Resampling.BILINEAR)
        weights = np.asarray(mask_pil, dtype=np.float32) * amount
        blend_mask = Image.fromarray(np.uint8(np.clip(weights, 0, 255)), "L")
    else:
        blend_mask = Image.new("L", original.size, int(round(amount * 255.0)))
    return _pil_to_qimage(Image.composite(adjusted, original, blend_mask))


def srgb_gamut_report(values: Iterable[float], *, scale: float = 255.0) -> dict[str, object]:
    raw = [float(value) for value in values]
    normalized = [value / float(scale) for value in raw]
    clipped = [max(0.0, min(1.0, value)) for value in normalized]
    return {
        "profile": "sRGB IEC61966-2.1",
        "in_gamut": normalized == clipped,
        "input": raw,
        "clipped_rgb": [int(round(value * 255.0)) for value in clipped],
        "display_profile": "sRGB",
        "output_profile_boundary": "document-srgb-to-export-profile",
    }


def export_gpl(path: str | Path, groups: dict[str, list[dict[str, object]]]) -> Path:
    lines = ["GIMP Palette", "Name: Tiger Studio Painter", "Columns: 8", "#"]
    for group, colors in groups.items():
        lines.append(f"# Group: {group}")
        for row in colors:
            rgb = [max(0, min(255, int(v))) for v in list(row.get("rgb") or [0, 0, 0])[:3]]
            lines.append(f"{rgb[0]:3d} {rgb[1]:3d} {rgb[2]:3d}\t{str(row.get('name') or 'Color')}")
    destination = Path(path); destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination


def import_gpl(path: str | Path) -> dict[str, list[dict[str, object]]]:
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0].strip() != "GIMP Palette":
        raise ValueError("Invalid GPL palette")
    groups: dict[str, list[dict[str, object]]] = {"Palette": []}; active = "Palette"
    for line in lines[1:]:
        if line.startswith("# Group:"):
            active = line.split(":", 1)[1].strip() or "Palette"; groups.setdefault(active, []); continue
        if not line or line.startswith(("#", "Name:", "Columns:")):
            continue
        parts = line.split(None, 3)
        if len(parts) >= 3 and all(part.lstrip("+-").isdigit() for part in parts[:3]):
            groups[active].append({
                "rgb": [max(0, min(255, int(part))) for part in parts[:3]],
                "name": parts[3].strip() if len(parts) > 3 else "Color",
            })
            continue
        raise ValueError(f"Invalid GPL color row: {line}")
    result = {key: value for key, value in groups.items() if value}
    if not result:
        raise ValueError("GPL palette contains no colors")
    return result


def _ase_utf16(text: str) -> bytes:
    encoded = (str(text) + "\0").encode("utf-16-be")
    return struct.pack(">H", len(encoded) // 2) + encoded


def export_ase(path: str | Path, groups: dict[str, list[dict[str, object]]]) -> Path:
    blocks: list[bytes] = []
    for group, colors in groups.items():
        body = _ase_utf16(group); blocks.append(struct.pack(">HI", 0xC001, len(body)) + body)
        for row in colors:
            rgb = [max(0, min(255, int(v))) / 255.0 for v in list(row.get("rgb") or [0, 0, 0])[:3]]
            body = _ase_utf16(str(row.get("name") or "Color")) + b"RGB " + struct.pack(">fffH", *rgb, 0)
            blocks.append(struct.pack(">HI", 0x0001, len(body)) + body)
        blocks.append(struct.pack(">HI", 0xC002, 0))
    payload = b"ASEF" + struct.pack(">HHI", 1, 0, len(blocks)) + b"".join(blocks)
    destination = Path(path); destination.write_bytes(payload); return destination


def import_ase(path: str | Path) -> dict[str, list[dict[str, object]]]:
    data = memoryview(Path(path).read_bytes())
    if len(data) < 12 or bytes(data[:4]) != b"ASEF":
        raise ValueError("Invalid ASE palette")
    count = struct.unpack_from(">I", data, 8)[0]; offset = 12
    groups: dict[str, list[dict[str, object]]] = {"Palette": []}; active = "Palette"
    for _ in range(count):
        block_type, length = struct.unpack_from(">HI", data, offset); offset += 6
        body = data[offset:offset + length]; offset += length
        if block_type in {0xC001, 0x0001}:
            name_length = struct.unpack_from(">H", body, 0)[0]
            name = bytes(body[2:2 + name_length * 2]).decode("utf-16-be").rstrip("\0")
            cursor = 2 + name_length * 2
            if block_type == 0xC001:
                active = name or "Palette"; groups.setdefault(active, [])
            elif bytes(body[cursor:cursor + 4]) == b"RGB ":
                rgb = struct.unpack_from(">fff", body, cursor + 4)
                groups.setdefault(active, []).append({"name": name, "rgb": [int(round(max(0, min(1, v)) * 255)) for v in rgb]})
    result = {key: value for key, value in groups.items() if value}
    if not result:
        raise ValueError("ASE palette contains no RGB colors")
    return result


__all__ = [
    "ADJUSTMENT_TYPES", "adjustment_parameter_contracts", "normalize_adjustment", "apply_adjustment_qimage",
    "srgb_gamut_report", "export_gpl", "import_gpl", "export_ase", "import_ase",
]
