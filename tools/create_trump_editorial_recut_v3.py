"""Render a premium four-act financial editorial motion piece."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.contact_composite import prepare_contact_composite
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.performance_gate import run_motion_performance_gate
from app.motion_designer.schema import MotionComposition, MotionEffectRef, AnimatedProperty
from tools import create_trump_headline_collage_10s as base


OUTPUT_DIR = ROOT / "debugCapture" / "motion_ai_showcase" / "trump_editorial_recut_v3"
TACTILE_PLATE = base.ASSET_DIR / "editorial_tactile_plate_2026.png"
MARKS_ALPHA = base.ASSET_DIR / "editorial_marks_alpha_2026.png"
WIDTH = 1280
HEIGHT = 720
DURATION_MS = 10_000
FPS = 30.0
FRAME_TIMES = (300, 1200, 2300, 3400, 4500, 5800, 7100, 8200, 9400)


def _contact_sheet(frames: list[Path], output: Path) -> Path:
    columns = 3
    tile_width = 400
    tile_height = 250
    label_height = 28
    rows = (len(frames) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * tile_width, rows * (tile_height + label_height)), "#101214")
    draw = ImageDraw.Draw(sheet)
    for index, frame_path in enumerate(frames):
        with Image.open(frame_path) as loaded:
            frame = loaded.convert("RGB")
        frame.thumbnail((tile_width, tile_height), Image.Resampling.LANCZOS)
        column = index % columns
        row = index // columns
        x = column * tile_width + (tile_width - frame.width) // 2
        y = row * (tile_height + label_height) + (tile_height - frame.height) // 2
        sheet.paste(frame, (x, y))
        draw.text(
            (column * tile_width + 10, row * (tile_height + label_height) + tile_height + 5),
            f"{FRAME_TIMES[index] / 1000:.1f}s",
            fill="#EEE7DA",
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    return output


def _duotone_portrait(source: Path, output: Path) -> Path:
    with Image.open(source) as loaded:
        rgba = loaded.convert("RGBA")
    alpha = rgba.getchannel("A")
    gray = ImageEnhance.Contrast(rgba.convert("L")).enhance(1.7)
    cream = Image.new("RGB", rgba.size, "#EEE5D5")
    red = Image.new("RGB", rgba.size, "#A91D17")
    duotone = Image.composite(red, cream, gray.point(lambda value: 255 if value < 116 else 0))
    lines = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(lines)
    for y in range(0, rgba.height, 7):
        draw.line((0, y, rgba.width, y), fill=(17, 14, 12, 42), width=2)
    result = Image.alpha_composite(Image.merge("RGBA", (*duotone.split(), alpha)), lines)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output)
    return output


def _grain_texture(output: Path) -> Path:
    import random

    rng = random.Random(20260802)
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for _ in range(28_000):
        x = rng.randrange(WIDTH)
        y = rng.randrange(HEIGHT)
        value = rng.choice((0, 255))
        draw.point((x, y), fill=(value, value, value, rng.randrange(3, 15)))
    image = image.filter(ImageFilter.GaussianBlur(0.25))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return output


def _split_editorial_marks(source: Path, output_dir: Path) -> dict[str, Path]:
    regions = {
        "red_brush": (40, 45, 875, 315),
        "grease_oval": (900, 25, 1600, 325),
        "paper_tape": (55, 350, 875, 590),
        "halftone_burst": (920, 315, 1605, 650),
        "red_stamp": (45, 620, 820, 920),
        "black_arrow": (900, 620, 1605, 925),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Path] = {}
    with Image.open(source) as loaded:
        image = loaded.convert("RGBA")
        for name, bounds in regions.items():
            crop = image.crop(bounds)
            alpha = crop.getchannel("A")
            content = alpha.getbbox()
            if content is None:
                raise ValueError(f"generated editorial mark is empty: {name}")
            crop = crop.crop(content)
            target = output_dir / f"{name}.png"
            crop.save(target)
            results[name] = target
    return results


def _visible(start: int, end: int, *, fade: int = 160) -> tuple[tuple[int, float], ...]:
    return (
        (0, 0.0),
        (max(0, start - 1), 0.0),
        (start + fade, 1.0),
        (max(start + fade, end - fade), 1.0),
        (end, 0.0),
        (DURATION_MS, 0.0),
    )


def _surface(name: str, fill: str, start: int) -> object:
    return base._shape(
        name,
        width=WIDTH,
        height=HEIGHT,
        fill=fill,
        position=(WIDTH / 2, HEIGHT / 2),
        opacity_keys=((0, 0.0), (max(0, start - 1), 0.0), (start, 1.0), (DURATION_MS, 1.0)),
        metadata={"role": "scene_surface"},
    )


def build_composition() -> MotionComposition:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not TACTILE_PLATE.is_file() or not MARKS_ALPHA.is_file():
        raise FileNotFoundError("generated 2026 editorial resource pack is missing")
    contact = prepare_contact_composite(
        foreground_path=base.TRUMP,
        background_path=base.NEWSPAPER,
        output_dir=OUTPUT_DIR / "contact",
        edge_strength=0.9,
        light_match_strength=0.16,
        shadow_opacity=0.20,
    )
    portrait = Path(contact["foreground_path"])
    shadow = Path(contact["shadow_path"])
    duotone = _duotone_portrait(portrait, OUTPUT_DIR / "assets" / "trump_duotone.png")
    grain = _grain_texture(OUTPUT_DIR / "assets" / "editorial_grain.png")
    marks = _split_editorial_marks(MARKS_ALPHA, OUTPUT_DIR / "assets" / "marks")
    clipping_specs = (
        ("MARKETS PRICE A NEW ERA", 71, "#A91D17"),
        ("POLICY MOVES CAPITAL", 72, "#211B17"),
        ("TRADE RETURNS TO CENTER", 73, "#A91D17"),
        ("VOLATILITY BECOMES THE STORY", 74, "#211B17"),
    )
    clippings = [
        base._make_clipping(
            OUTPUT_DIR / "assets" / f"clipping_{index + 1}.png",
            title,
            seed=seed,
            accent=accent,
        )
        for index, (title, seed, accent) in enumerate(clipping_specs)
    ]

    composition = MotionComposition(
        name="The Price of Power / Editorial Recut V3",
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
        duration_ms=DURATION_MS,
        metadata={
            "showcase": "trump_editorial_recut_v3",
            "editorial_disclaimer": "Fictional editorial motion-graphics concept.",
            "visual_system": "2026 tactile mixed media / dynamic type / four-act edit",
            "contact_composite": contact,
            "generated_resources": {
                "tactile_plate": str(TACTILE_PLATE.resolve()),
                "editorial_marks": {key: str(path.resolve()) for key, path in marks.items()},
            },
        },
    )

    # Act 1: a restrained newspaper macro rather than an immediate portrait.
    composition.layers.append(base._image_layer(
        "Act 1 / Broadsheet Macro",
        TACTILE_PLATE,
        position=(640, 360),
        position_keys=((0, [570, 405]), (1900, [655, 350])),
        scale=(1.05, 1.05),
        scale_keys=((0, [1.18, 1.18]), (1900, [1.04, 1.04])),
        rotation_keys=((0, -1.4), (1900, 0.2)),
        fit="cover",
        metadata={"role": "act_1_broadsheet", "depth_z": -1.0},
    ))
    composition.layers.append(base._shape(
        "Act 1 / Black Crop",
        width=WIDTH,
        height=152,
        fill="#E50C0B0A",
        position=(640, 102),
        position_keys=((0, [640, -120]), (420, [640, 102])),
        opacity_keys=_visible(0, 2100, fade=220),
    ))
    composition.layers.append(base._text(
        "Act 1 / Edition",
        "SPECIAL EDITION  /  WASHINGTON + WALL STREET",
        position=(640, 76),
        width=1080,
        height=40,
        size=23,
        fill="#E8DED0",
        family="Bahnschrift",
        weight=500,
        opacity_keys=_visible(180, 2050),
    ))
    composition.layers.append(base._text(
        "Act 1 / Question",
        "WHO SETS THE PRICE OF POWER?",
        position=(640, 365),
        width=1140,
        height=120,
        size=76,
        fill="#17130F",
        family="Georgia",
        scale_keys=((0, [1.12, 1.12]), (350, [1.12, 1.12]), (1450, [1.0, 1.0])),
        opacity_keys=_visible(280, 2050, fade=250),
        metadata={"role": "act_1_headline"},
    ))

    # Act 2: asymmetrical portrait and type, leaving the face clear.
    composition.layers.append(_surface("Act 2 / Charcoal Surface", "#F20D1013", 1900))
    portrait_motion = ((0, [1460, 430]), (1900, [1460, 430]), (2380, [915, 430]), (3900, [885, 426]))
    portrait_scale = ((0, [0.72, 0.72]), (1900, [0.72, 0.72]), (2380, [0.84, 0.84]), (3900, [0.88, 0.88]))
    portrait_alpha = _visible(1900, 4200, fade=180)
    composition.layers.append(base._image_layer(
        "Act 2 / Portrait Shadow", shadow,
        position=(915, 430), position_keys=portrait_motion,
        scale=(0.84, 0.84), scale_keys=portrait_scale,
        opacity_keys=portrait_alpha,
        metadata={"role": "contact_shadow", "preview_export_assets_shared": True},
    ))
    composition.layers.append(base._image_layer(
        "Act 2 / Trump Portrait", portrait,
        position=(915, 430), position_keys=portrait_motion,
        scale=(0.84, 0.84), scale_keys=portrait_scale,
        opacity_keys=portrait_alpha,
        metadata={"role": "central_subject", "edge_decontaminated": True, "depth_z": 0.8},
    ))
    composition.layers.append(base._shape(
        "Act 2 / Red Spine", width=12, height=430, fill="#D6B62018",
        position=(112, 370),
        scale_keys=((0, [1, 0]), (2050, [1, 0]), (2440, [1, 1])),
        opacity_keys=_visible(1980, 4180),
    ))
    composition.layers.append(base._text(
        "Act 2 / Power", "POWER\nPRICED IN",
        position=(385, 330), width=560, height=225, size=91,
        fill="#F2E9DC", family="Georgia",
        position_keys=((0, [-480, 330]), (2050, [-480, 330]), (2460, [385, 330])),
        opacity_keys=_visible(2020, 4150),
        metadata={"role": "act_2_headline"},
    ))
    composition.layers.insert(-1, base._image_layer(
        "Act 2 / Dry Red Brush", marks["red_brush"],
        position=(375, 345),
        scale=(0.62, 0.62),
        scale_keys=((0, [0.0, 0.62]), (2110, [0.0, 0.62]), (2520, [0.62, 0.62])),
        rotation_keys=((0, -4.0), (2520, -2.0)),
        opacity_keys=_visible(2050, 4150, fade=100),
        metadata={"role": "responsive_analog_mark"},
    ))
    composition.layers.append(base._text(
        "Act 2 / Deck",
        "Markets react before policy becomes history.",
        position=(385, 500), width=540, height=54, size=24,
        fill="#B9B0A5", family="Bahnschrift", weight=400,
        position_keys=((0, [345, 530]), (2380, [345, 530]), (2740, [385, 500])),
        opacity_keys=_visible(2250, 4100),
    ))

    # Act 3: an editorial dashboard made from real cut-paper layers.
    composition.layers.append(_surface("Act 3 / Paper Surface", "#FFF0E8D9", 3950))
    composition.layers.append(base._image_layer(
        "Act 3 / Tactile Plate", TACTILE_PLATE,
        position=(640, 360),
        position_keys=((0, [665, 350]), (3950, [665, 350]), (7100, [620, 370])),
        scale=(1.03, 1.03),
        scale_keys=((0, [1.09, 1.09]), (3950, [1.09, 1.09]), (7100, [1.02, 1.02])),
        opacity_keys=((0, 0.0), (3949, 0.0), (4050, 0.72), (7050, 0.72), (7140, 0.0)),
        fit="cover",
        metadata={"role": "act_3_generated_mixed_media_plate", "depth_z": -1.0},
    ))
    composition.layers.append(base._text(
        "Act 3 / Index", "01 / CAPITAL   02 / POLICY   03 / TRADE   04 / VOLATILITY",
        position=(640, 62), width=1160, height=38, size=20,
        fill="#29221D", family="Bahnschrift", weight=600,
        opacity_keys=_visible(4050, 7050),
    ))
    targets = ((250, 205, -5.0), (620, 198, 3.0), (1015, 215, -3.5), (450, 493, 2.0))
    for index, (path, target) in enumerate(zip(clippings, targets)):
        x, y, angle = target
        start = 4100 + index * 310
        origin_x = -420 if index % 2 == 0 else 1700
        layer = base._image_layer(
            f"Act 3 / Clipping {index + 1}", path,
            position=(x, y),
            position_keys=((0, [origin_x, y - 80]), (start - 1, [origin_x, y - 80]),
                           (start + 310, [x + 12, y - 8]), (start + 470, [x, y])),
            scale=(0.88, 0.88),
            scale_keys=((0, [0.68, 0.68]), (start - 1, [0.68, 0.68]),
                        (start + 310, [0.98, 0.98]), (start + 470, [0.88, 0.88])),
            rotation_keys=((0, angle * 4), (start - 1, angle * 4),
                           (start + 310, angle - 2), (start + 470, angle)),
            opacity_keys=_visible(start, 7120, fade=80),
            metadata={"role": "torn_newspaper_clipping", "depth_z": index * 0.25},
        )
        layer.effects.append(MotionEffectRef(
            kind="paper_fold",
            params={"strength": AnimatedProperty(default=0.16), "angle": AnimatedProperty(default=angle * 4)},
        ))
        composition.layers.append(layer)
        composition.layers.append(base._image_layer(
            f"Act 3 / Tape {index + 1}", marks["paper_tape"],
            position=(x, y - 76),
            scale=(0.24, 0.24),
            scale_keys=((0, [0.0, 0.24]), (start + 420, [0.0, 0.24]), (start + 560, [0.24, 0.24])),
            rotation_keys=((0, angle - 2.0), (start + 560, angle - 2.0)),
            opacity_keys=_visible(start + 420, 7120, fade=60),
            metadata={"role": "physical_tape_layer", "article_index": index + 1},
        ))
    composition.layers.append(base._image_layer(
        "Act 3 / Grease Pencil Emphasis", marks["grease_oval"],
        position=(930, 525),
        scale=(0.56, 0.56),
        scale_keys=((0, [0.35, 0.35]), (5480, [0.35, 0.35]), (5750, [0.60, 0.60]), (5940, [0.56, 0.56])),
        rotation_keys=((0, -8.0), (5750, 2.0), (5940, -1.0)),
        opacity_keys=_visible(5460, 7100, fade=80),
        metadata={"role": "responsive_analog_mark"},
    ))
    composition.layers.append(base._text(
        "Act 3 / Market Number", "+2.3%",
        position=(930, 505), width=530, height=150, size=128,
        fill="#B62018", family="Bahnschrift",
        scale_keys=((0, [0.4, 0.4]), (5350, [0.4, 0.4]), (5650, [1.08, 1.08]), (5800, [1.0, 1.0])),
        opacity_keys=_visible(5300, 7080, fade=90),
        metadata={"role": "data_callout"},
    ))
    composition.layers.append(base._text(
        "Act 3 / Market Label", "ONE HEADLINE. BILLIONS IN MOTION.",
        position=(930, 600), width=540, height=40, size=22,
        fill="#332B25", family="Bahnschrift", weight=500,
        opacity_keys=_visible(5550, 7050),
    ))
    composition.layers.append(base._image_layer(
        "Act 3 / Direction Arrow", marks["black_arrow"],
        position=(785, 604),
        position_keys=((0, [690, 604]), (5700, [690, 604]), (6000, [785, 604])),
        scale=(0.22, 0.22),
        opacity_keys=_visible(5680, 7050, fade=100),
        metadata={"role": "responsive_analog_mark"},
    ))

    # Act 4: a brief duotone impact followed by a restrained final cover.
    composition.layers.append(_surface("Act 4 / Signal Red", "#FFB62018", 6900))
    composition.layers.append(base._image_layer(
        "Act 4 / Halftone Impact", marks["halftone_burst"],
        position=(660, 380),
        scale=(1.15, 1.15),
        scale_keys=((0, [0.1, 0.1]), (6900, [0.1, 0.1]), (7200, [1.35, 1.35]), (7600, [1.15, 1.15])),
        rotation_keys=((0, -14.0), (7200, 4.0), (7600, 0.0)),
        opacity_keys=_visible(6900, 8420, fade=60),
        metadata={"role": "halftone_impact_layer"},
    ))
    composition.layers.append(base._image_layer(
        "Act 4 / Duotone Portrait", duotone,
        position=(640, 445),
        position_keys=((0, [640, 770]), (6900, [640, 770]), (7280, [640, 445]), (8300, [675, 430])),
        scale=(1.02, 1.02),
        scale_keys=((0, [0.86, 0.86]), (6900, [0.86, 0.86]), (7280, [1.03, 1.03]), (8300, [1.10, 1.10])),
        opacity_keys=_visible(6900, 8420, fade=80),
        metadata={"role": "duotone_impact_subject"},
    ))
    composition.layers.append(base._text(
        "Act 4 / Breaking", "THE STORY\nMOVES FIRST",
        position=(320, 325), width=560, height=230, size=82,
        fill="#FFF1E8D9", family="Georgia",
        position_keys=((0, [-450, 325]), (7000, [-450, 325]), (7380, [320, 325])),
        opacity_keys=_visible(7000, 8400, fade=100),
    ))
    composition.layers.append(_surface("Final / Black Cover", "#FC090B0D", 8300))
    composition.layers.append(base._image_layer(
        "Final / Portrait", portrait,
        position=(950, 440),
        position_keys=((0, [1160, 440]), (8300, [1160, 440]), (8780, [950, 440])),
        scale=(0.78, 0.78),
        scale_keys=((0, [0.70, 0.70]), (8300, [0.70, 0.70]), (8780, [0.78, 0.78])),
        opacity_keys=((0, 0.0), (8350, 0.0), (8780, 1.0), (DURATION_MS, 1.0)),
        metadata={"role": "final_subject", "edge_decontaminated": True},
    ))
    composition.layers.append(base._text(
        "Final / Kicker", "THE DAILY LEDGER  /  SPECIAL REPORT",
        position=(350, 190), width=540, height=40, size=20,
        fill="#B62018", family="Bahnschrift", weight=600,
        opacity_keys=((0, 0.0), (8450, 0.0), (8840, 1.0), (DURATION_MS, 1.0)),
    ))
    final_title = base._text(
        "Final / Title", "THE PRICE\nOF POWER",
        position=(350, 345), width=570, height=230, size=88,
        fill="#F2E9DC", family="Georgia",
        position_keys=((0, [310, 385]), (8400, [310, 385]), (8900, [350, 345])),
        opacity_keys=((0, 0.0), (8400, 0.0), (8900, 1.0), (DURATION_MS, 1.0)),
        metadata={"role": "final_headline"},
    )
    final_title.source.params["text_animation"] = {
        "in": "cascade-in", "hold": "none", "out": "none",
        "in_duration_ms": 620, "out_duration_ms": 0,
        "unit": "word", "stagger_ms": 80,
        "selector_start": 0.0, "selector_end": 1.0,
        "reverse": False, "intensity": 0.85,
    }
    composition.layers.append(final_title)
    composition.layers.append(base._shape(
        "Final / Rule", width=500, height=4, fill="#DDB62018",
        position=(350, 492),
        scale_keys=((0, [0, 1]), (8750, [0, 1]), (9300, [1, 1])),
        opacity_keys=((0, 0.0), (8750, 0.0), (9000, 1.0), (DURATION_MS, 1.0)),
    ))
    composition.layers.append(base._text(
        "Final / Disclaimer", "FICTIONAL EDITORIAL MOTION CONCEPT  /  10 SECONDS",
        position=(350, 535), width=570, height=36, size=17,
        fill="#9F978E", family="Bahnschrift", weight=400,
        opacity_keys=((0, 0.0), (9000, 0.0), (9450, 1.0), (DURATION_MS, 1.0)),
    ))
    grain_layer = base._image_layer(
        "Global / Fine Print Grain", grain,
        position=(640, 360),
        opacity_keys=((0, 0.30), (DURATION_MS, 0.30)),
        fit="cover",
        metadata={"role": "global_print_grain", "camera_2_5d_excluded": True},
    )
    grain_layer.blend_mode = "overlay"
    composition.layers.append(grain_layer)
    return composition


def render_stills() -> dict:
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    composition = build_composition()
    composition_path = OUTPUT_DIR / "trump_editorial_recut_v3.motion.json"
    composition_path.write_text(json.dumps(composition.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    renderer = MotionExportRenderer(cache_capacity=12)
    frames = [
        renderer.save_png(composition, time_ms, OUTPUT_DIR / f"frame_{time_ms:05d}ms.png")
        for time_ms in FRAME_TIMES
    ]
    sheet = _contact_sheet(frames, OUTPUT_DIR / "contact_sheet.png")
    return {
        "composition_model": composition,
        "composition": str(composition_path.resolve()),
        "contact_sheet": str(sheet.resolve()),
        "frames": [str(path.resolve()) for path in frames],
        "layer_count": len(composition.layers),
    }


def render_showcase() -> dict:
    stills = render_stills()
    composition = stills.pop("composition_model")
    renderer = MotionExportRenderer(cache_capacity=12)
    video = renderer.export_mp4(composition, OUTPUT_DIR / "trump_editorial_recut_v3.mp4", fps=FPS)
    performance = run_motion_performance_gate(
        composition,
        sample_times_ms=(1200, 3000, 5200, 7600, 9400),
        iterations=2,
        width=320,
        height=180,
        cache_max_bytes=32 * 1024 * 1024,
    )
    report = {
        "schema": "tigerstudio.motion.trump_editorial_recut.v3",
        "ok": video.is_file() and video.stat().st_size > 0 and performance["ok"],
        "video": str(video.resolve()),
        "video_bytes": video.stat().st_size,
        "composition": stills["composition"],
        "contact_sheet": stills["contact_sheet"],
        "frames": stills["frames"],
        "duration_ms": DURATION_MS,
        "fps": FPS,
        "layer_count": stills["layer_count"],
        "performance": performance,
        "design_changes": [
            "four distinct acts instead of one static portrait stack",
            "face-safe asymmetric typography",
            "black red cream financial editorial palette",
            "duotone print impact shot",
            "full-screen scene replacement surfaces",
            "contact-corrected portrait and restrained final cover",
        ],
    }
    (OUTPUT_DIR / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stills-only", action="store_true")
    args = parser.parse_args()
    if args.stills_only:
        report = render_stills()
        report.pop("composition_model", None)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    report = render_showcase()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
