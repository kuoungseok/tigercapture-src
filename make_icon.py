"""Generate resources/bitdam.ico from scratch using Pillow.

Creates a simple rounded red square with "GC" text at multiple sizes and packs
them into a multi-resolution .ico file.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


SIZES = [16, 24, 32, 48, 64, 128, 256]
OUT = Path(__file__).parent / "resources" / "bitdam.ico"


def _make_image(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = max(4, size // 6)
    draw.rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=(229, 70, 70, 255)
    )

    # Inner "film strip" frame
    margin = max(2, size // 10)
    inner_r = max(2, radius // 2)
    draw.rounded_rectangle(
        (margin, margin, size - 1 - margin, size - 1 - margin),
        radius=inner_r,
        outline=(255, 255, 255, 220),
        width=max(1, size // 32),
    )

    # Little white dots along top and bottom to hint at film perforations
    dot_r = max(1, size // 32)
    y_top = margin - max(1, size // 20)
    y_bot = size - 1 - margin + max(1, size // 20)
    n_dots = 5
    step = (size - 2 * margin) / (n_dots + 1)
    for i in range(1, n_dots + 1):
        x = int(margin + step * i)
        draw.ellipse(
            (x - dot_r, y_top - dot_r, x + dot_r, y_top + dot_r),
            fill=(255, 255, 255, 255),
        )
        draw.ellipse(
            (x - dot_r, y_bot - dot_r, x + dot_r, y_bot + dot_r),
            fill=(255, 255, 255, 255),
        )

    # "GC" text roughly centered
    text = "GC"
    font = _best_font(size)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1]
    draw.text((tx, ty), text, fill=(255, 255, 255, 255), font=font)
    return img


def _best_font(size: int) -> ImageFont.ImageFont:
    target = max(10, int(size * 0.5))
    for name in ("arial.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, target)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    images = [_make_image(s) for s in SIZES]
    # Save largest as base and append smaller sizes as separate frames.
    # Pillow stores each as its own image in the ICO file.
    base = images[-1]
    base.save(OUT, format="ICO", append_images=images[:-1])
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
