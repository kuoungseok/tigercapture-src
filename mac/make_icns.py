"""Generate mac/resources/tigercapture.icns from the same Pillow art used for
the Windows .ico.

macOS .icns expects a specific set of sizes (with @2x variants). We
build an .iconset directory then hand it to Apple's ``iconutil`` —
that's the recommended path and produces a file Finder / Info.plist
accept without warnings.

Run from a macOS shell:
    python3 make_icns.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).parent
OUT = HERE / "resources" / "tigercapture.icns"

# (size, scale) → filename pattern required by iconutil
ICONSET_ENTRIES = [
    (16, 1), (16, 2),
    (32, 1), (32, 2),
    (128, 1), (128, 2),
    (256, 1), (256, 2),
    (512, 1), (512, 2),
]


def _make_image(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = max(4, size // 6)
    draw.rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=(229, 70, 70, 255)
    )

    margin = max(2, size // 10)
    inner_r = max(2, radius // 2)
    draw.rounded_rectangle(
        (margin, margin, size - 1 - margin, size - 1 - margin),
        radius=inner_r,
        outline=(255, 255, 255, 220),
        width=max(1, size // 32),
    )

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
    # macOS system fonts
    candidates = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/SFCompact.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "DejaVuSans-Bold.ttf",
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, target)
        except OSError:
            continue
    return ImageFont.load_default()


def _iconutil_available() -> bool:
    return shutil.which("iconutil") is not None


def main() -> int:
    if sys.platform != "darwin":
        print("make_icns.py must run on macOS (needs iconutil).", file=sys.stderr)
        return 2
    if not _iconutil_available():
        print("iconutil not found. Install Xcode Command Line Tools.", file=sys.stderr)
        return 2

    OUT.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "tigercapture.iconset"
        iconset.mkdir()

        for base, scale in ICONSET_ENTRIES:
            pixel_size = base * scale
            img = _make_image(pixel_size)
            if scale == 1:
                fname = f"icon_{base}x{base}.png"
            else:
                fname = f"icon_{base}x{base}@2x.png"
            img.save(iconset / fname, format="PNG")

        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(OUT)],
            check=True,
        )

    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
