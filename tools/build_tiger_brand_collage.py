"""Build a Tiger Studio lockup with real media clipped into the tiger mark.

This is intentionally deterministic.  Image generation is good for direction,
but final brand assets should use real Tiger Studio screenshots/video frames so
the interior collage does not carry the synthetic "AI UI" look.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW_SLIDES = Path(
    r"E:\ClaudeCodeApp\ReviewAutomationWorkspace\outputs\product_catalog_full\slides_en"
)
DEFAULT_VIDEO_DIR = Path(r"C:\Users\artmouse\Videos\TigerCapture\YouTube Imports")


def _default_assets() -> list[Path]:
    preferred = [
        "01_studio_overview.png",
        "02_studio_surface.png",
        "04_ppt_maker.png",
        "05_media_pool.png",
        "06_timeline.png",
        "09_typography.png",
        "11_color.png",
        "12_node_graph.png",
        "14_audio_workbench.png",
        "15_audio_curves.png",
        "16_live2d_spine.png",
        "17_vrm.png",
        "18_mmd.png",
        "19_ar_pbr.png",
        "21_export.png",
    ]
    return [DEFAULT_REVIEW_SLIDES / name for name in preferred if (DEFAULT_REVIEW_SLIDES / name).exists()]


def _default_videos() -> list[Path]:
    if not DEFAULT_VIDEO_DIR.exists():
        return []
    blocked = {"trump"}
    videos = []
    for path in sorted(DEFAULT_VIDEO_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
        name = path.name.casefold()
        if any(token in name for token in blocked):
            continue
        videos.append(path)
        if len(videos) >= 8:
            break
    return videos


def _video_frames(path: Path, *, max_frames: int = 3) -> list[Image.Image]:
    try:
        import cv2

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return []
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            positions = [30, 90, 150]
        else:
            positions = [max(0, min(total - 1, int(total * t))) for t in (0.18, 0.48, 0.76)]
        frames: list[Image.Image] = []
        for pos in positions[:max_frames]:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(pos))
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame).convert("RGB")
            img = ImageEnhance.Color(img).enhance(0.88)
            img = ImageEnhance.Contrast(img).enhance(1.12)
            frames.append(img)
        cap.release()
        return frames
    except Exception:
        return []


def _load_asset(path: Path) -> Image.Image | None:
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return None
    # The brand mark needs footage texture, not readable UI documents.
    img = ImageEnhance.Color(img).enhance(0.92)
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img = ImageEnhance.Sharpness(img).enhance(0.9)
    return img


def _tiger_mask(base: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int]]:
    rgb = np.asarray(base.convert("RGB"), dtype=np.int16)
    h, w = rgb.shape[:2]
    y_limit = int(h * 0.68)
    ys = np.arange(h)[:, None]
    luma = (rgb[:, :, 0] * 0.299 + rgb[:, :, 1] * 0.587 + rgb[:, :, 2] * 0.114)
    chroma = np.max(rgb, axis=2) - np.min(rgb, axis=2)
    # Only search the emblem area; the white typography below must stay fixed.
    raw = (ys < y_limit) & ((luma > 42) | ((luma > 26) & (chroma > 28)))
    mask = Image.fromarray((raw.astype(np.uint8) * 255), "L")
    # Close tiny holes, then threshold back to a hard emblem-area matte.  The
    # output must preserve the background and typography exactly, so avoid
    # expanded/soft spill outside the tiger.
    mask = mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    mask = mask.point(lambda p: 255 if p > 96 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        bbox = (int(w * 0.28), int(h * 0.05), int(w * 0.72), int(h * 0.66))
    return mask, bbox


def _fit_tile(img: Image.Image, size: tuple[int, int], *, focus_side: str = "center") -> Image.Image:
    w, h = img.size
    if focus_side == "left":
        centering = (0.28, 0.5)
    elif focus_side == "right":
        centering = (0.72, 0.5)
    else:
        centering = (0.5, 0.5)
    fitted = ImageOps.fit(img, size, method=Image.Resampling.LANCZOS, centering=centering)
    # Slightly de-identify readable screenshots while keeping real pixels.
    fitted = fitted.filter(ImageFilter.GaussianBlur(0.18))
    return fitted


def _build_collage(base_size: tuple[int, int], bbox: tuple[int, int, int, int], assets: list[Image.Image]) -> Image.Image:
    canvas = Image.new("RGB", base_size, (12, 13, 16))
    if not assets:
        return canvas

    rng = random.Random(4317)
    x0, y0, x1, y1 = bbox
    bw, bh = x1 - x0, y1 - y0
    cols, rows = 5, 4
    tile_w = int(np.ceil(bw / cols)) + 22
    tile_h = int(np.ceil(bh / rows)) + 22

    video_assets = assets[:12]
    slide_assets = assets[12:]
    abstract_assets = video_assets + slide_assets[:10] + slide_assets[13:]
    character_assets = slide_assets[10:13]
    if not abstract_assets:
        abstract_assets = assets

    for row in range(rows):
        for col in range(cols):
            px = x0 + int(col * bw / cols) - 10
            py = y0 + int(row * bh / rows) - 10
            is_center_axis = col in {2} and row in {1, 2}
            is_edge = col in {0, cols - 1} or row in {0, rows - 1}
            if is_edge and character_assets and rng.random() < 0.42:
                src = rng.choice(character_assets)
                focus = "left" if col < cols // 2 else "right"
            else:
                src = rng.choice(abstract_assets)
                focus = "center"
            if is_center_axis:
                src = rng.choice(abstract_assets[:8] or abstract_assets)
                focus = "center"
            tile = _fit_tile(src, (tile_w, tile_h), focus_side=focus)
            # Offset/rotate very gently for footage collage rhythm.
            if rng.random() < 0.35:
                tile = tile.rotate(rng.uniform(-2.0, 2.0), resample=Image.Resampling.BICUBIC, expand=False)
            canvas.paste(tile, (px, py))

    # Add a few real horizontal strips to read as timeline/film movement.
    strip_assets = abstract_assets[:]
    rng.shuffle(strip_assets)
    for i, src in enumerate(strip_assets[:5]):
        strip_h = max(18, int(bh * rng.uniform(0.035, 0.07)))
        strip_y = y0 + int(bh * rng.uniform(0.05, 0.92))
        strip = _fit_tile(src, (bw + 80, strip_h), focus_side="center")
        strip = ImageEnhance.Contrast(strip).enhance(1.22)
        overlay = Image.new("RGBA", base_size, (0, 0, 0, 0))
        overlay.paste(strip.convert("RGBA"), (x0 - 40, strip_y))
        alpha = 55 if i % 2 else 75
        overlay.putalpha(overlay.getchannel("A").point(lambda p, a=alpha: min(p, a)))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")

    canvas = ImageEnhance.Color(canvas).enhance(1.04)
    canvas = ImageEnhance.Contrast(canvas).enhance(1.16)
    return canvas


def _stripe_mask_from_base(base: Image.Image, tiger_mask: Image.Image) -> Image.Image:
    rgb = np.asarray(base.convert("RGB"), dtype=np.int16)
    luma = (rgb[:, :, 0] * 0.299 + rgb[:, :, 1] * 0.587 + rgb[:, :, 2] * 0.114)
    chroma = np.max(rgb, axis=2) - np.min(rgb, axis=2)
    tiger = np.asarray(tiger_mask, dtype=np.uint8) > 0
    # Preserve only the strong black tiger graphic language from the preferred
    # AI draft.  Avoid keeping its synthetic UI text/panels in the colored fill.
    raw = tiger & ((luma < 24) | ((luma < 38) & (chroma < 18)))
    mask = Image.fromarray((raw.astype(np.uint8) * 255), "L")
    mask = mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.45))
    return mask


def _edge_highlight_mask_from_base(base: Image.Image, tiger_mask: Image.Image) -> Image.Image:
    rgb = np.asarray(base.convert("RGB"), dtype=np.int16)
    luma = (rgb[:, :, 0] * 0.299 + rgb[:, :, 1] * 0.587 + rgb[:, :, 2] * 0.114)
    tiger = np.asarray(tiger_mask, dtype=np.uint8) > 0
    raw = tiger & (luma > 178)
    mask = Image.fromarray((raw.astype(np.uint8) * 255), "L")
    mask = mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.25))
    return mask.point(lambda p: int(min(255, p * 0.42)))


def _center_character_clear_mask(base_size: tuple[int, int], bbox: tuple[int, int, int, int], tiger_mask: Image.Image) -> Image.Image:
    """Soft mask over the center character area inside the tiger emblem.

    The preferred draft has a nice overall lockup, but a centered anime figure
    competes with the brand mark.  This mask lets real editor/timeline capture
    replace only that center figure while leaving the outer lockup untouched.
    """
    x0, y0, x1, y1 = bbox
    bw, bh = x1 - x0, y1 - y0
    cx = x0 + bw * 0.505
    cy = y0 + bh * 0.575
    rw = bw * 0.18
    rh = bh * 0.31
    mask = Image.new("L", base_size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        [int(cx - rw), int(cy - rh), int(cx + rw), int(cy + rh)],
        radius=max(18, int(min(rw, rh) * 0.38)),
        fill=255,
    )
    mask = mask.filter(ImageFilter.GaussianBlur(max(10, int(min(bw, bh) * 0.018))))
    return ImageChops.multiply(mask, tiger_mask)


def build(
    base_path: Path,
    out_path: Path,
    asset_paths: list[Path],
    video_paths: list[Path],
    *,
    clean_tiger: bool = False,
    preserve_composition: bool = False,
    preserve_strength: float = 0.34,
    preserve_mask_strength: float = 0.58,
    clear_center_character: bool = False,
) -> Path:
    base = Image.open(base_path).convert("RGBA")
    mask, bbox = _tiger_mask(base)
    video_assets: list[Image.Image] = []
    for path in video_paths:
        video_assets.extend(_video_frames(path))
    assets = video_assets + [_load_asset(path) for path in asset_paths]
    assets = [img for img in assets if img is not None]
    collage = _build_collage(base.size, bbox, assets).convert("RGBA")

    # Keep real media strong, but strictly clipped to the detected tiger paint.
    # Anything outside this mask must remain byte-for-byte visually unchanged.
    media_mask = mask.point(lambda p: int(min(255, p * 0.96)))
    if clean_tiger:
        # Fill the tiger with real footage only, then restore the preferred
        # black mask/stripe language from the base. This removes generated UI
        # labels while keeping the stronger tiger shape the user preferred.
        tiger_media = ImageEnhance.Color(collage).enhance(0.96)
        tiger_media = ImageEnhance.Contrast(tiger_media).enhance(1.02)
        composed = Image.composite(tiger_media, base, media_mask)
        stripe_mask = _stripe_mask_from_base(base, mask)
        if clear_center_character:
            center_clear_mask = _center_character_clear_mask(base.size, bbox, mask)
            softened_center = center_clear_mask.point(lambda p: max(0, 255 - int(p * 1.0)))
            stripe_mask = ImageChops.multiply(stripe_mask, softened_center)
        stripe_mask = stripe_mask.point(lambda p: int(min(150, p * 0.58)))
        black_ink = Image.new("RGBA", base.size, (0, 0, 0, 255))
        composed = Image.composite(black_ink, composed, stripe_mask)
        edge_mask = _edge_highlight_mask_from_base(base, mask)
        edge_mask = edge_mask.point(lambda p: int(min(70, p * 0.35)))
        ivory_ink = Image.new("RGBA", base.size, (238, 232, 218, 255))
        composed = Image.composite(ivory_ink, composed, edge_mask)
    elif preserve_composition:
        # Keep the user's preferred internal composition, but press real footage
        # texture into the tiger so generated-looking labels/UI panels recede.
        base_soft = base.filter(ImageFilter.GaussianBlur(0.18))
        footage = ImageEnhance.Color(collage).enhance(0.82).convert("RGBA")
        footage = ImageEnhance.Contrast(footage).enhance(0.94)
        blend_amount = max(0.0, min(1.0, float(preserve_strength)))
        mask_amount = max(0.0, min(1.0, float(preserve_mask_strength)))
        preserved = Image.blend(base_soft, footage, blend_amount)
        media_mask = mask.point(lambda p: int(min(235, p * mask_amount)))
        composed = Image.composite(preserved, base, media_mask)
        center_clear_mask = None
        if clear_center_character and assets:
            x0, y0, x1, y1 = bbox
            bw, bh = x1 - x0, y1 - y0
            patch = _fit_tile(assets[0], (int(bw * 0.42), int(bh * 0.58)), focus_side="center")
            patch = ImageEnhance.Color(patch).enhance(0.9)
            patch = ImageEnhance.Contrast(patch).enhance(1.06)
            patch = ImageEnhance.Brightness(patch).enhance(1.14)
            patch_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
            px = int(x0 + bw * 0.295)
            py = int(y0 + bh * 0.305)
            patch_layer.paste(patch.convert("RGBA"), (px, py))
            center_clear_mask = _center_character_clear_mask(base.size, bbox, mask)
            # Composite a real capture patch only where it has alpha.  The
            # previous version selected transparent patch-layer pixels across
            # the whole soft mask, which made the center look like a black hole.
            patch_alpha = patch_layer.getchannel("A")
            center_patch_mask = ImageChops.multiply(center_clear_mask, patch_alpha)
            composed = Image.composite(patch_layer, composed, center_patch_mask)

        stripe_mask = _stripe_mask_from_base(base, mask)
        stripe_mask = stripe_mask.point(lambda p: int(min(180, p * 0.45)))
        if clear_center_character and center_clear_mask is not None:
            softened_center = center_clear_mask.point(lambda p: max(0, 255 - int(p * 1.0)))
            stripe_mask = ImageChops.multiply(stripe_mask, softened_center)
        black_ink = Image.new("RGBA", base.size, (0, 0, 0, 255))
        composed = Image.composite(black_ink, composed, stripe_mask)

        edge_mask = _edge_highlight_mask_from_base(base, mask)
        edge_mask = edge_mask.point(lambda p: int(min(82, p * 0.45)))
        ivory_ink = Image.new("RGBA", base.size, (238, 232, 218, 255))
        composed = Image.composite(ivory_ink, composed, edge_mask)
    else:
        tiger_faded = Image.blend(base, collage, 0.86)
        composed = Image.composite(tiger_faded, base, media_mask)

        # Restore a low-opacity original mark on top so eyes/nose/stripe silhouette
        # remain brand-readable while the real collage dominates.
        mark_alpha = mask.point(lambda p: int(min(255, p * 0.11)))
        composed = Image.composite(base, composed, mark_alpha)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    composed.save(out_path)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Tiger Studio real-media tiger collage.")
    parser.add_argument("--base", type=Path, required=True, help="Tiger Studio lockup PNG.")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "resources" / "branding" / "tiger_studio_real_clip_collage.png",
    )
    parser.add_argument("--asset", type=Path, action="append", default=None, help="Real screenshot/image asset.")
    parser.add_argument("--video", type=Path, action="append", default=None, help="Real video clip for frame extraction.")
    parser.add_argument(
        "--no-default-videos",
        action="store_true",
        help="Do not add videos from the default YouTube Imports folder when --video is omitted.",
    )
    parser.add_argument(
        "--video-only",
        action="store_true",
        help="Use only video frames; skip default product screenshots so the tiger reads as footage, not UI/VRM.",
    )
    parser.add_argument(
        "--clean-tiger",
        action="store_true",
        help="Keep only black/edge tiger graphic masks from the base and replace the colored fill with real media.",
    )
    parser.add_argument(
        "--preserve-composition",
        action="store_true",
        help="Keep the base tiger composition while blending real video texture inside it to reduce synthetic UI artifacts.",
    )
    parser.add_argument(
        "--preserve-strength",
        type=float,
        default=0.34,
        help="Blend strength for real media when --preserve-composition is used.",
    )
    parser.add_argument(
        "--preserve-mask-strength",
        type=float,
        default=0.58,
        help="Tiger mask opacity for real media when --preserve-composition is used.",
    )
    parser.add_argument(
        "--clear-center-character",
        action="store_true",
        help="Replace the center character in the preferred composition with real editor/timeline capture.",
    )
    args = parser.parse_args()

    assets = [] if args.video_only else (list(args.asset or []) or _default_assets())
    videos = list(args.video or [])
    if not videos and not args.no_default_videos:
        videos = _default_videos()
    if not assets and not videos:
        raise SystemExit("No collage assets found. Pass --asset/--video or generate product catalog screenshots first.")
    out = build(
        args.base,
        args.out,
        assets,
        videos,
        clean_tiger=bool(args.clean_tiger),
        preserve_composition=bool(args.preserve_composition),
        preserve_strength=float(args.preserve_strength),
        preserve_mask_strength=float(args.preserve_mask_strength),
        clear_center_character=bool(args.clear_center_character),
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
