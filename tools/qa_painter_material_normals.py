"""Render Painter material-brush color/height/normal/AO comparison proof."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _rgb_preview(channels: dict[str, object], color: tuple[int, int, int]) -> np.ndarray:
    coverage = np.asarray(channels["coverage"], dtype=np.float32)[..., None]
    shading = np.asarray(channels["shading"], dtype=np.float32)[..., None]
    base = np.asarray(color, dtype=np.float32)[None, None, :] / 255.0
    paper = np.full_like(base * coverage, 0.93)
    paint = np.clip(base * shading, 0.0, 1.0)
    return np.uint8(np.clip(paper * (1.0 - coverage) + paint * coverage, 0.0, 1.0) * 255.0)


def main() -> int:
    from app.drawing import PaintLayer, Stroke
    from app.painter_material_paint import rasterize_material_channels

    width, height = 300, 150
    rows = (
        ("Palette Knife", "palette_knife", (38, 118, 113)),
        ("Impasto Ridge", "impasto_oil", (201, 77, 43)),
        ("Bristle Oil", "bristle_oil", (216, 151, 48)),
        ("Dry Oil", "dry_oil", (58, 78, 130)),
    )
    labels = ("COLOR + LIGHT", "HEIGHT", "NORMAL (DX)", "AO")
    margin, label_h, gap = 16, 28, 8
    sheet_w = margin * 2 + width * 4 + gap * 3
    sheet_h = margin * 2 + label_h + len(rows) * (height + label_h + gap)
    sheet = Image.new("RGB", (sheet_w, sheet_h), (24, 25, 27))
    draw = ImageDraw.Draw(sheet)
    for column, label in enumerate(labels):
        draw.text((margin + column * (width + gap) + 6, margin + 7), label, fill=(238, 236, 230))

    layer = PaintLayer(
        "material-proof",
        "Material Proof",
        layer_type="material",
        material_settings={"thickness": 0.92, "roughness": 0.44},
    )
    for row, (name, style, color) in enumerate(rows):
        stroke = Stroke(
            points=[(0.08, 0.66), (0.27, 0.30), (0.51, 0.58), (0.73, 0.26), (0.92, 0.48)],
            color=color,
            width_px=42,
            brush_style=style,
            layer_id=layer.layer_id,
            material_enabled=True,
            material_load=0.95,
            material_thickness=0.92,
            material_wetness=0.24,
            material_gloss=0.42,
            material_roughness=0.44,
            brush_engine_version=2,
            point_pressure=[0.38, 0.94, 0.72, 1.0, 0.46],
            point_load=[1.0, 0.92, 0.74, 0.60, 0.42],
            point_tilt_x=[0.0, 0.35, 0.55, -0.25, -0.45],
            point_tilt_y=[0.0, -0.18, 0.22, 0.32, 0.10],
            point_rotation=[0.50, 0.62, 0.78, 0.34, 0.20],
            point_tangential_pressure=[0.0, 0.18, 0.30, -0.12, -0.25],
            bristle_count=16,
            brush_seed=20260731 + row,
            load_depletion=0.34,
        )
        channels = rasterize_material_channels(
            [stroke],
            [layer],
            width=width,
            height=height,
        )
        height_map = np.asarray(channels["height"], dtype=np.float32)
        height_display = np.uint8(np.clip(height_map / max(0.001, float(height_map.max())), 0.0, 1.0) * 255.0)
        normal_display = np.uint8(np.clip(channels["normal"], 0.0, 1.0) * 255.0)
        ao_display = np.uint8(np.clip(channels["ao"], 0.0, 1.0) * 255.0)
        tiles = (
            Image.fromarray(_rgb_preview(channels, color), mode="RGB"),
            Image.fromarray(height_display, mode="L").convert("RGB"),
            Image.fromarray(normal_display, mode="RGB"),
            Image.fromarray(ao_display, mode="L").convert("RGB"),
        )
        y = margin + label_h + row * (height + label_h + gap)
        draw.text((margin + 6, y + 6), name, fill=(240, 211, 160))
        tile_y = y + label_h
        for column, tile in enumerate(tiles):
            sheet.paste(tile, (margin + column * (width + gap), tile_y))

    output = ROOT / "debugCapture" / "painter_material" / "brush_normal_height_ao.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
