"""Extract the user-provided tiger pixel-art from the composite reference
sheet and package it as a multi-resolution Windows .ico.

The reference sheet ``debugCapture/타이거.png`` contains four hand-tuned
tigers (labelled 16x16 / 32x32 / 64x64 / 128x128) on a dark canvas, plus
some unrelated cursor art at the bottom. We crop each tiger tightly,
centre it on a square transparent canvas, resize to its declared target
size, and bundle them all into ``tigercapture.ico``.

Run from repo root:
    .venv/Scripts/python.exe resources/icon_draft/make_tiger.py
Outputs:
    resources/icon_draft/preview_<N>.png
    resources/icon_draft/tigercapture.ico
"""

from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "debugCapture" / "타이거.png"
OUT = Path(__file__).parent

# Y-bands for each tiger inside the composite sheet, found by scanning
# row densities. Each tuple is (target_size, y_start, y_end) in source
# pixel coordinates.
BANDS = [
    (16,   56,  126),
    (32,  195,  320),
    (64,  374,  579),
    (128, 620, 1049),
]

# Background of the reference sheet is dark grey (~24,24,24). Any pixel
# that is significantly brighter than that is "tiger content".
BG_THRESHOLD = 50


def _crop_tiger(arr: np.ndarray, y0: int, y1: int) -> Image.Image:
    """Find the tiger inside the given Y band and return its tight RGBA
    crop with the dark sheet background turned transparent."""
    band = arr[y0:y1 + 1]
    # Mask: is this pixel part of the tiger?
    not_bg = (
        (band[:, :, 0] > BG_THRESHOLD)
        | (band[:, :, 1] > BG_THRESHOLD)
        | (band[:, :, 2] > BG_THRESHOLD)
    )
    # The size label sits to the left of the tiger — restrict to the
    # right half of the sheet to skip it.
    not_bg[:, :200] = False

    cols = not_bg.any(axis=0)
    rows = not_bg.any(axis=1)
    xs = np.where(cols)[0]
    ys = np.where(rows)[0]
    if len(xs) == 0 or len(ys) == 0:
        raise RuntimeError(f"no tiger found in band y=[{y0},{y1}]")

    x0, x1 = int(xs.min()), int(xs.max())
    ry0, ry1 = int(ys.min()), int(ys.max())
    crop = band[ry0:ry1 + 1, x0:x1 + 1].copy()

    # Make the dark sheet background fully transparent.
    bg_mask = (
        (crop[:, :, 0] <= BG_THRESHOLD)
        & (crop[:, :, 1] <= BG_THRESHOLD)
        & (crop[:, :, 2] <= BG_THRESHOLD)
    )
    crop[bg_mask, 3] = 0
    return Image.fromarray(crop, "RGBA")


def _square_pad(img: Image.Image, pad_ratio: float = 0.0) -> Image.Image:
    """Centre the image on a square transparent canvas. ``pad_ratio``
    adds extra empty margin (e.g. 0.05 = 5% breathing room)."""
    w, h = img.size
    side = max(w, h)
    side = int(side * (1.0 + pad_ratio))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - w) // 2, (side - h) // 2), img)
    return canvas


def _resize_pixel_art(img: Image.Image, target: int) -> Image.Image:
    """Resize pixel-art crop to ``target`` × ``target``. The source is
    a non-integer upscale, so plain NEAREST distorts the grid — LANCZOS
    gives a much cleaner result for the small icon sizes."""
    return img.resize((target, target), Image.Resampling.LANCZOS)


def main() -> None:
    src = Image.open(SRC).convert("RGBA")
    arr = np.array(src)

    images_by_size: dict[int, Image.Image] = {}
    for target, y0, y1 in BANDS:
        crop = _crop_tiger(arr, y0, y1)
        squared = _square_pad(crop, pad_ratio=0.06)
        out_img = _resize_pixel_art(squared, target)
        out_img.save(OUT / f"preview_{target}.png")
        images_by_size[target] = out_img

    # Fill in the standard icon sizes Windows uses by upscaling the
    # 128 master with LANCZOS. 256 is required for high-DPI; 48 and 24
    # are fallbacks for older shell variants.
    master = images_by_size[128]
    for extra in (24, 48, 256):
        if extra not in images_by_size:
            images_by_size[extra] = master.resize(
                (extra, extra), Image.Resampling.LANCZOS,
            )
            images_by_size[extra].save(OUT / f"preview_{extra}.png")

    sizes = sorted(images_by_size.keys())
    images = [images_by_size[s] for s in sizes]
    images[0].save(
        OUT / "tigercapture.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f"wrote {len(sizes)} previews + tigercapture.ico to {OUT}")
    print(f"sizes: {sizes}")


if __name__ == "__main__":
    main()
