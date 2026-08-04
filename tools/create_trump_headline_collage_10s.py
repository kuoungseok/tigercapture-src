"""Render a 10-second kinetic newspaper collage around a Trump portrait."""
from __future__ import annotations

import json
import os
from pathlib import Path
import random
import sys
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFilter, ImageFont

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.advanced_presets import apply_advanced_preset
from app.motion_designer.choreography_director import plan_choreography_candidates
from app.motion_designer.contact_composite import prepare_contact_composite
from app.motion_designer.performance_gate import run_motion_performance_gate
from app.motion_designer.schema import (
    AnimatedProperty,
    Keyframe,
    MotionBehaviorRef,
    MotionComposition,
    MotionEffectRef,
    MotionLayer,
    MotionTransform,
    SourceRef,
)


ASSET_DIR = ROOT / "sample_assets" / "motion_ai_showcase" / "wall_street_trump"
OUTPUT_DIR = ROOT / "debugCapture" / "motion_ai_showcase" / "trump_headline_collage_10s"
NEWSPAPER = ASSET_DIR / "financial_broadsheet_plate.png"
TRUMP = ASSET_DIR / "trump_official_transparent_2025_prepared.png"
WIDTH = 1280
HEIGHT = 720
FPS = 30.0
DURATION_MS = 10_000
FRAME_TIMES = [250, 1200, 2200, 3300, 4700, 6200, 7900, 9400]


def _font(size: int, *, serif: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont:
    font_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    choices = (
        ["georgiab.ttf", "timesbd.ttf"] if serif and bold else
        ["georgia.ttf", "times.ttf"] if serif else
        ["bahnschrift.ttf", "arialbd.ttf"] if bold else
        ["segoeui.ttf", "arial.ttf"]
    )
    for filename in choices:
        path = font_dir / filename
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _animated(
    default: Any,
    rows: Iterable[tuple[int, Any]],
    value_type: str,
    *,
    interpolation: str = "bezier",
) -> AnimatedProperty:
    return AnimatedProperty(
        value_type=value_type,
        default=default,
        keyframes=[
            Keyframe(
                time_ms=int(time_ms),
                value=value,
                interpolation=interpolation,
                out_tangent=(0.18, 0.0),
                in_tangent=(0.78, 1.0),
            )
            for time_ms, value in rows
        ],
    )


def _transform(
    *,
    position: tuple[float, float],
    position_keys: Iterable[tuple[int, list[float]]] = (),
    scale: tuple[float, float] = (1.0, 1.0),
    scale_keys: Iterable[tuple[int, list[float]]] = (),
    rotation: float = 0.0,
    rotation_keys: Iterable[tuple[int, float]] = (),
    opacity: float = 1.0,
    opacity_keys: Iterable[tuple[int, float]] = (),
) -> MotionTransform:
    return MotionTransform(
        position=_animated(list(position), position_keys, "vector2"),
        scale=_animated(list(scale), scale_keys, "vector2"),
        rotation=_animated(rotation, rotation_keys, "scalar"),
        opacity=_animated(opacity, opacity_keys, "scalar"),
        anchor=AnimatedProperty(value_type="vector2", default=[0.5, 0.5]),
    )


def _shape(
    name: str,
    *,
    width: float,
    height: float,
    fill: str,
    position: tuple[float, float],
    position_keys: Iterable[tuple[int, list[float]]] = (),
    scale_keys: Iterable[tuple[int, list[float]]] = (),
    rotation_keys: Iterable[tuple[int, float]] = (),
    opacity_keys: Iterable[tuple[int, float]] = (),
    radius: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> MotionLayer:
    return MotionLayer(
        name=name,
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "primitive": "rectangle",
            "width": width,
            "height": height,
            "radius": radius,
            "fill": fill,
            "stroke": "#00000000",
            "stroke_width": 0.0,
        }),
        transform=_transform(
            position=position,
            position_keys=position_keys,
            scale_keys=scale_keys,
            rotation_keys=rotation_keys,
            opacity_keys=opacity_keys,
        ),
        out_ms=DURATION_MS,
        metadata=metadata or {},
    )


def _text(
    name: str,
    text: str,
    *,
    position: tuple[float, float],
    width: int,
    height: int,
    size: int,
    fill: str,
    family: str = "Bahnschrift",
    weight: int = 700,
    position_keys: Iterable[tuple[int, list[float]]] = (),
    scale_keys: Iterable[tuple[int, list[float]]] = (),
    rotation_keys: Iterable[tuple[int, float]] = (),
    opacity_keys: Iterable[tuple[int, float]] = (),
    metadata: dict[str, Any] | None = None,
) -> MotionLayer:
    return MotionLayer(
        name=name,
        layer_type="text",
        source=SourceRef(kind="typography", params={
            "text": text,
            "font_family": family,
            "font_size": size,
            "font_weight": weight,
            "fill": fill,
            "stroke_width": 0.0,
            "alignment": "center",
            "width": width,
            "height": height,
            "line_height": 0.9,
            "letter_spacing": 0.0,
        }),
        transform=_transform(
            position=position,
            position_keys=position_keys,
            scale_keys=scale_keys,
            rotation_keys=rotation_keys,
            opacity_keys=opacity_keys,
        ),
        out_ms=DURATION_MS,
        metadata=metadata or {},
    )


def _image_layer(
    name: str,
    path: Path,
    *,
    position: tuple[float, float],
    position_keys: Iterable[tuple[int, list[float]]] = (),
    scale: tuple[float, float] = (1.0, 1.0),
    scale_keys: Iterable[tuple[int, list[float]]] = (),
    rotation_keys: Iterable[tuple[int, float]] = (),
    opacity_keys: Iterable[tuple[int, float]] = (),
    fit: str = "contain",
    metadata: dict[str, Any] | None = None,
) -> MotionLayer:
    with Image.open(path) as image:
        source_width, source_height = image.size
    return MotionLayer(
        name=name,
        layer_type="image",
        source=SourceRef(kind="image", uri=str(path.resolve()), params={
            "width": source_width,
            "height": source_height,
            "fit": fit,
        }),
        transform=_transform(
            position=position,
            position_keys=position_keys,
            scale=scale,
            scale_keys=scale_keys,
            rotation_keys=rotation_keys,
            opacity_keys=opacity_keys,
        ),
        out_ms=DURATION_MS,
        metadata=metadata or {},
    )


def _torn_polygon(width: int, height: int, rng: random.Random) -> list[tuple[int, int]]:
    inset = 18
    step = 30
    points: list[tuple[int, int]] = []
    for x in range(inset, width - inset + 1, step):
        points.append((x, inset + rng.randint(-8, 8)))
    for y in range(inset, height - inset + 1, step):
        points.append((width - inset + rng.randint(-8, 8), y))
    for x in range(width - inset, inset - 1, -step):
        points.append((x, height - inset + rng.randint(-8, 8)))
    for y in range(height - inset, inset - 1, -step):
        points.append((inset + rng.randint(-8, 8), y))
    return points


def _make_clipping(path: Path, headline: str, *, seed: int, accent: str) -> Path:
    width, height = 338, 178
    rng = random.Random(seed)
    polygon = _torn_polygon(width, height, rng)

    alpha = Image.new("L", (width, height), 0)
    ImageDraw.Draw(alpha).polygon(polygon, fill=255)
    shadow_alpha = alpha.filter(ImageFilter.GaussianBlur(8))
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    shadow.putalpha(shadow_alpha.point(lambda value: int(value * 0.48)))

    paper = Image.new("RGBA", (width, height), (233, 225, 210, 255))
    pd = ImageDraw.Draw(paper)
    for y in range(height):
        tone = 240 - int(19 * y / height)
        pd.line((0, y, width, y), fill=(tone, tone - 7, tone - 17, 255))
    for _ in range(850):
        x = rng.randrange(width)
        y = rng.randrange(height)
        tone = rng.choice((78, 96, 118, 145))
        pd.point((x, y), fill=(tone, tone - 8, tone - 15, rng.randint(10, 35)))

    title_font = _font(26, serif=True, bold=True)
    body_font = _font(9, serif=True)
    words = headline.split()
    split = max(1, (len(words) + 1) // 2)
    title = " ".join(words[:split]) + "\n" + " ".join(words[split:])
    pd.multiline_text((27, 23), title, fill="#181511", font=title_font, spacing=-2)
    pd.line((27, 86, width - 28, 86), fill=accent, width=4)
    for row in range(6):
        y = 101 + row * 10
        left = 28
        right = width - 30 - ((row * 23 + seed * 7) % 58)
        pd.rectangle((left, y, right, y + 3), fill="#544C43")
    pd.text((width - 95, height - 28), f"NO. {seed:02d}", fill="#514940", font=body_font)
    pd.line((25, height - 25, width - 112, height - 25), fill="#887B6B", width=1)
    paper.putalpha(alpha)

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(shadow, (6, 7))
    canvas.alpha_composite(paper)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)
    return path


def _headline_slam(
    word: str,
    *,
    index: int,
    start: int,
    y: int,
    direction: int,
    fill: str,
) -> MotionLayer:
    end = start + 1120
    start_x = -500 if direction > 0 else 1780
    exit_x = 1780 if direction > 0 else -500
    tilt = -7.0 if direction > 0 else 7.0
    return _text(
        f"Kinetic Headline {index + 1} / {word}",
        word,
        position=(640, y),
        width=1050,
        height=150,
        size=126,
        fill=fill,
        position_keys=(
            (0, [start_x, y]),
            (start, [start_x, y]),
            (start + 250, [670 - 30 * direction, y]),
            (start + 420, [640, y]),
            (end - 230, [640, y]),
            (end, [exit_x, y]),
        ),
        scale_keys=(
            (0, [1.38, 1.38]),
            (start, [1.38, 1.38]),
            (start + 250, [1.08, 1.08]),
            (start + 420, [1.0, 1.0]),
            (end, [1.15, 1.15]),
        ),
        rotation_keys=((0, tilt), (start, tilt), (start + 420, 0.0), (end, -tilt)),
        opacity_keys=((0, 0.0), (start - 1, 0.0), (start, 1.0), (end - 120, 1.0), (end, 0.0)),
        metadata={"role": "kinetic_headline", "word": word},
    )


def build_composition() -> MotionComposition:
    if not NEWSPAPER.is_file() or not TRUMP.is_file():
        missing = [str(path) for path in (NEWSPAPER, TRUMP) if not path.is_file()]
        raise FileNotFoundError(", ".join(missing))

    contact = prepare_contact_composite(
        foreground_path=TRUMP,
        background_path=NEWSPAPER,
        output_dir=OUTPUT_DIR / "contact_composite",
        edge_strength=0.88,
        light_match_strength=0.20,
        shadow_opacity=0.24,
    )
    contact_foreground = Path(contact["foreground_path"])
    contact_shadow = Path(contact["shadow_path"])

    clip_specs = [
        ("POWER RESHAPES THE AGENDA", 51, "#B12018"),
        ("MARKETS BRACE FOR VOLATILITY", 52, "#23201C"),
        ("POLICY MOVES AT FULL SPEED", 53, "#B12018"),
        ("TRADE RETURNS TO CENTER STAGE", 54, "#23201C"),
        ("INVESTORS WATCH EVERY SIGNAL", 55, "#B12018"),
        ("THE ECONOMY AT A CROSSROADS", 56, "#23201C"),
        ("CAPITAL FOLLOWS THE HEADLINE", 57, "#B12018"),
        ("A NEW ERA IN WASHINGTON", 58, "#23201C"),
    ]
    clipping_paths = [
        _make_clipping(
            OUTPUT_DIR / "clippings" / f"article_{index + 1:02d}.png",
            headline,
            seed=seed,
            accent=accent,
        )
        for index, (headline, seed, accent) in enumerate(clip_specs)
    ]

    composition = MotionComposition(
        name="The Price of Power / Trump Headline Collage",
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
        duration_ms=DURATION_MS,
        metadata={
            "showcase": "trump_headline_cut_paste_10s",
            "editorial_disclaimer": "Fictional editorial motion-graphics concept.",
            "layer_strategy": "newspaper plate + public-domain portrait + torn clipping PNG layers + kinetic typography",
        },
    )

    composition.layers.append(_image_layer(
        "Financial Broadsheet",
        NEWSPAPER,
        position=(640, 360),
        position_keys=((0, [615, 380]), (1600, [640, 360]), (8600, [650, 350]), (10_000, [640, 360])),
        scale=(1.18, 1.18),
        scale_keys=((0, [1.24, 1.24]), (1600, [1.05, 1.05]), (8600, [1.10, 1.10])),
        rotation_keys=((0, -2.5), (1600, 0.0), (8600, 0.8)),
        fit="cover",
        metadata={"role": "newspaper_background"},
    ))
    composition.layers.append(_shape(
        "Warm Newsprint Wash",
        width=WIDTH,
        height=HEIGHT,
        fill="#3A28150E",
        position=(640, 360),
        metadata={"role": "editorial_color_wash"},
    ))
    composition.layers.append(_text(
        "Opening Masthead",
        "THE DAILY LEDGER",
        position=(640, 95),
        width=1060,
        height=84,
        size=55,
        fill="#181410",
        family="Georgia",
        position_keys=((0, [640, 52]), (800, [640, 95]), (1900, [640, 95]), (2500, [640, 58])),
        opacity_keys=((0, 0.0), (320, 0.0), (850, 1.0), (2050, 1.0), (2500, 0.0)),
        metadata={"role": "fictional_masthead"},
    ))
    composition.layers.append(_shape(
        "Opening Rule",
        width=940,
        height=4,
        fill="#1B1713",
        position=(640, 137),
        scale_keys=((0, [0.0, 1.0]), (520, [0.0, 1.0]), (1150, [1.0, 1.0])),
        opacity_keys=((0, 0.0), (500, 0.0), (900, 1.0), (2100, 1.0), (2450, 0.0)),
    ))

    portrait_position_keys = (
        (0, [640, 665]),
        (1150, [640, 665]),
        (2050, [640, 435]),
        (7800, [640, 428]),
        (9000, [640, 440]),
    )
    portrait_scale_keys = (
        (0, [0.50, 0.50]),
        (1150, [0.50, 0.50]),
        (2050, [0.79, 0.79]),
        (2600, [0.75, 0.75]),
        (7800, [0.80, 0.80]),
    )
    portrait_rotation_keys = (
        (0, -2.0),
        (1150, -2.0),
        (2050, 0.8),
        (2600, 0.0),
        (7800, -0.6),
    )
    portrait_opacity_keys = ((0, 0.0), (1000, 0.0), (1500, 1.0), (10_000, 1.0))
    composition.layers.append(_image_layer(
        "Donald Trump Contact Shadow",
        contact_shadow,
        position=(640, 435),
        position_keys=portrait_position_keys,
        scale=(0.76, 0.76),
        scale_keys=portrait_scale_keys,
        rotation_keys=portrait_rotation_keys,
        opacity_keys=portrait_opacity_keys,
        metadata={
            "role": "subject_contact_shadow",
            "contact_composite_schema": contact["schema"],
            "preview_export_assets_shared": True,
        },
    ))
    composition.layers.append(_image_layer(
        "Donald Trump Portrait",
        contact_foreground,
        position=(640, 435),
        position_keys=portrait_position_keys,
        scale=(0.76, 0.76),
        scale_keys=portrait_scale_keys,
        rotation_keys=portrait_rotation_keys,
        opacity_keys=portrait_opacity_keys,
        metadata={
            "role": "central_subject",
            "person": "Donald Trump",
            "contact_composite_schema": contact["schema"],
            "edge_decontaminated": True,
            "local_light_matched": True,
            "preview_export_assets_shared": True,
        },
    ))

    headline_specs = [
        ("POWER", 1600, 245, 1, "#B21F17"),
        ("MARKETS", 2300, 385, -1, "#161310"),
        ("POLICY", 3000, 255, 1, "#B21F17"),
        ("TRADE", 3700, 420, -1, "#161310"),
    ]
    for index, (word, start, y, direction, fill) in enumerate(headline_specs):
        composition.layers.append(_headline_slam(
            word,
            index=index,
            start=start,
            y=y,
            direction=direction,
            fill=fill,
        ))

    targets = [
        (190, 175, -7.0, (-420, 80)),
        (1080, 170, 6.0, (1700, 70)),
        (180, 365, 4.0, (-420, 350)),
        (1090, 360, -5.0, (1700, 330)),
        (235, 565, -4.0, (-420, 760)),
        (1045, 565, 5.5, (1700, 780)),
        (480, 640, 3.0, (350, 930)),
        (825, 638, -3.0, (940, 930)),
    ]
    for index, (path, target) in enumerate(zip(clipping_paths, targets)):
        tx, ty, rotation, start_position = target
        start = 3200 + index * 430
        land = start + 440
        settle = start + 650
        layer = _image_layer(
            f"Torn Article {index + 1}",
            path,
            position=(tx, ty),
            position_keys=(
                (0, list(start_position)),
                (start - 1, list(start_position)),
                (land, [tx + (10 if index % 2 == 0 else -10), ty - 8]),
                (settle, [tx, ty]),
                (8600, [tx, ty]),
                (9200, [tx + (index % 3 - 1) * 12, ty + 7]),
            ),
            scale=(0.92, 0.92),
            scale_keys=(
                (0, [0.55, 0.55]),
                (start - 1, [0.55, 0.55]),
                (land, [1.05, 1.05]),
                (settle, [0.92, 0.92]),
                (9200, [0.95, 0.95]),
            ),
            rotation_keys=(
                (0, rotation * 5.0),
                (start - 1, rotation * 5.0),
                (land, rotation - (2.5 if index % 2 == 0 else -2.5)),
                (settle, rotation),
                (9200, rotation * 0.55),
            ),
            opacity_keys=((0, 0.0), (start - 1, 0.0), (start, 1.0), (10_000, 1.0)),
            metadata={
                "role": "torn_newspaper_clipping",
                "fictional_copy": True,
                "headline": clip_specs[index][0],
                "depth_z": -0.9 + index * 0.24,
                "motion_blur": {"enabled": True, "samples": 10, "shutter": 0.78},
            },
        )
        layer.effects.append(MotionEffectRef(
            kind="paper_fold",
            params={
                "strength": AnimatedProperty(default=0.18 + index * 0.012),
                "angle": AnimatedProperty(default=-22.0 + index * 6.0),
                "width": AnimatedProperty(default=34.0),
            },
        ))
        layer.behaviors.append(MotionBehaviorRef(
            kind="impact",
            start_ms=start,
            end_ms=min(DURATION_MS, start + 650),
            params={
                "scale_overshoot": 0.08,
                "rotation_kick": -3.0 if index % 2 == 0 else 3.0,
                "shake": 5.0,
                "frequency": 4.5,
                "damping": 7.0,
                "hold_after": True,
            },
        ))
        composition.layers.append(layer)

        tape_y = ty - 75
        composition.layers.append(_shape(
            f"Tape {index + 1}",
            width=78,
            height=20,
            fill="#BFD7C79E",
            position=(tx, tape_y),
            scale_keys=((0, [0.0, 1.0]), (settle - 1, [0.0, 1.0]), (settle + 150, [1.0, 1.0])),
            rotation_keys=((0, rotation - 3.0), (settle, rotation - 3.0)),
            opacity_keys=((0, 0.0), (settle - 1, 0.0), (settle, 0.78), (10_000, 0.78)),
            radius=1.0,
            metadata={"role": "paper_tape", "article_index": index + 1},
        ))

    breaking_matte = _text(
        "Breaking Track Matte",
        "BREAKING",
        position=(640, 360),
        width=1160,
        height=190,
        size=142,
        fill="#FFFFFFFF",
        family="Bahnschrift",
        scale_keys=((0, [0.72, 0.72]), (6750, [0.72, 0.72]), (7200, [1.0, 1.0]), (8250, [1.0, 1.0])),
        opacity_keys=((0, 0.0), (6650, 0.0), (7000, 1.0), (8150, 1.0), (8420, 0.0)),
        metadata={"role": "track_matte_source", "camera_2_5d_excluded": True},
    )
    breaking_fill = _shape(
        "Breaking Red Fill",
        width=WIDTH,
        height=230,
        fill="#D9B01E17",
        position=(640, 360),
        position_keys=((0, [-720, 360]), (6800, [-720, 360]), (7200, [640, 360]), (8150, [640, 360]), (8420, [1940, 360])),
        opacity_keys=((0, 0.0), (6750, 0.0), (7000, 1.0), (8250, 1.0), (8460, 0.0)),
        metadata={
            "role": "track_matte_fill",
            "matte_layer_id": breaking_matte.id,
            "matte_mode": "alpha",
            "motion_blur": {"enabled": True, "samples": 12, "shutter": 0.9},
            "camera_2_5d_excluded": True,
        },
    )
    composition.layers.extend([breaking_fill, breaking_matte])
    replicated_rule = _shape(
        "Replicated Editorial Rules",
        width=7,
        height=74,
        fill="#D9B01E17",
        position=(70, 360),
        opacity_keys=((0, 0.0), (6100, 0.0), (6500, 1.0), (8300, 1.0), (8600, 0.0)),
        metadata={
            "role": "generic_layer_replicator_demo",
            "replicator": {
                "enabled": True, "count": 8, "offset": [0.0, 43.0],
                "rotation": 0.0, "scale": [1.0, 0.94],
                "opacity_start": 1.0, "opacity_end": 0.18,
                "jitter": [2.0, 4.0], "seed": 47,
            },
            "camera_2_5d_excluded": True,
        },
    )
    composition.layers.append(replicated_rule)

    composition.layers.append(_shape(
        "Final Editorial Shade",
        width=WIDTH,
        height=HEIGHT,
        fill="#870B0908",
        position=(640, 360),
        opacity_keys=((0, 0.0), (8350, 0.0), (9000, 0.70), (10_000, 0.70)),
        metadata={"role": "final_title_shade", "camera_2_5d_excluded": True},
    ))
    final_title = _text(
        "Final Headline",
        "THE PRICE OF POWER",
        position=(640, 330),
        width=1100,
        height=120,
        size=88,
        fill="#F4EEE4",
        family="Georgia",
        scale_keys=((0, [0.82, 0.82]), (8500, [0.82, 0.82]), (9220, [1.0, 1.0])),
        opacity_keys=((0, 0.0), (8450, 0.0), (9000, 1.0), (10_000, 1.0)),
        metadata={"role": "final_headline", "camera_2_5d_excluded": True},
    )
    final_title.source.params["text_animation"] = {
        "in": "cascade-in", "hold": "none", "out": "none",
        "in_duration_ms": 780, "out_duration_ms": 0,
        "unit": "word", "stagger_ms": 90,
        "selector_start": 0.0, "selector_end": 1.0,
        "reverse": False, "intensity": 1.0,
    }
    composition.layers.append(final_title)
    composition.layers.append(_text(
        "Final Subhead",
        "A HEADLINE IN MOTION  /  FICTIONAL EDITORIAL CONCEPT",
        position=(640, 425),
        width=1050,
        height=48,
        size=20,
        fill="#D8CEC0",
        weight=500,
        position_keys=((0, [640, 455]), (8700, [640, 455]), (9300, [640, 425])),
        opacity_keys=((0, 0.0), (8700, 0.0), (9300, 1.0), (10_000, 1.0)),
        metadata={"role": "final_disclaimer", "camera_2_5d_excluded": True},
    ))
    apply_advanced_preset(
        composition,
        "editorial_camera_push",
        layer_ids=[
            layer.id for layer in composition.layers
            if not bool(layer.metadata.get("camera_2_5d_excluded", False))
        ],
        start_ms=400,
    )
    return composition


def _contact_sheet(paths: list[Path], labels: list[str], output: Path) -> Path:
    thumbs: list[Image.Image] = []
    for path in paths:
        with Image.open(path) as source:
            thumbs.append(source.convert("RGB").resize((320, 180), Image.Resampling.LANCZOS))
    canvas = Image.new("RGB", (1280, 428), "#11100E")
    draw = ImageDraw.Draw(canvas)
    font = _font(15)
    for index, (thumb, label) in enumerate(zip(thumbs, labels)):
        x = (index % 4) * 320
        y = (index // 4) * 214
        canvas.paste(thumb, (x, y))
        draw.text((x + 10, y + 187), label, fill="#F4EEE4", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return output


def render_showcase() -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    _application = QApplication.instance() or QApplication([])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    composition = build_composition()
    composition_path = OUTPUT_DIR / "trump_headline_collage_10s.motion.json"
    composition_path.write_text(
        json.dumps(composition.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    scenario = {
        "schema": "tigerstudio.motion.editorial_scenario.v1",
        "title": "The Price of Power",
        "duration_ms": DURATION_MS,
        "beats": [
            {"time": "0.0-1.6", "action": "Financial broadsheet rushes into frame"},
            {"time": "1.0-2.3", "action": "Trump portrait rises through the page"},
            {"time": "1.6-4.8", "action": "POWER, MARKETS, POLICY and TRADE slam across frame"},
            {"time": "3.2-7.3", "action": "Eight torn article clippings fly in and overshoot"},
            {"time": "3.8-7.8", "action": "Tape strips pin each clipping around the face-safe area"},
            {"time": "7.8-9.0", "action": "Editorial collage settles into a composed page"},
            {"time": "9.0-10.0", "action": "THE PRICE OF POWER resolves over the collage"},
        ],
        "claims": "All headlines are fictional visual copy. Portrait uses a public-domain US government image.",
    }
    scenario_path = OUTPUT_DIR / "scenario.json"
    scenario_path.write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")

    choreography_elements = [
        {
            "id": layer.id,
            "metadata": {
                "role": layer.metadata.get("role"),
                "depth_z": layer.metadata.get("depth_z", 0.0),
            },
        }
        for layer in composition.layers
        if layer.metadata.get("role") in {"central_subject", "torn_newspaper_clipping"}
    ]
    choreography = plan_choreography_candidates(
        choreography_elements,
        duration_ms=DURATION_MS,
        max_camera_travel_ratio=0.018,
        prompt="Trump newspaper headline editorial cutout collage",
        motion_style="dynamic craft collage",
        audio_hits_ms=(1600, 2300, 3000, 3700, 4400, 5100, 5800, 6500, 7200, 9000),
        max_simultaneous_motion=3,
    )
    choreography_path = OUTPUT_DIR / "choreography_candidates.json"
    choreography_path.write_text(
        json.dumps(choreography, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    renderer = MotionExportRenderer()
    frames = [
        renderer.save_png(composition, time_ms, OUTPUT_DIR / f"frame_{time_ms:05d}ms.png")
        for time_ms in FRAME_TIMES
    ]
    contact_sheet = _contact_sheet(
        frames,
        [f"{time_ms / 1000:.2f}s" for time_ms in FRAME_TIMES],
        OUTPUT_DIR / "contact_sheet.png",
    )
    video = renderer.export_mp4(
        composition,
        OUTPUT_DIR / "trump_headline_collage_10s.mp4",
        fps=FPS,
    )
    performance = run_motion_performance_gate(
        composition,
        sample_times_ms=(1200, 4700, 7900, 9400),
        iterations=2,
        width=320,
        height=180,
        cache_max_bytes=32 * 1024 * 1024,
    )
    performance_path = OUTPUT_DIR / "performance_gate.json"
    performance_path.write_text(
        json.dumps(performance, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report = {
        "schema": "tigerstudio.motion.trump_headline_collage.v2",
        "ok": video.is_file() and video.stat().st_size > 0 and performance["ok"],
        "composition": str(composition_path.resolve()),
        "scenario": str(scenario_path.resolve()),
        "video": str(video.resolve()),
        "video_bytes": video.stat().st_size if video.is_file() else 0,
        "contact_sheet": str(contact_sheet.resolve()),
        "choreography_candidates": str(choreography_path.resolve()),
        "choreography_recommended_candidate_id": choreography["recommended_candidate_id"],
        "performance_gate": str(performance_path.resolve()),
        "performance_ok": performance["ok"],
        "render_backend_counts": performance["backend_counts"],
        "render_fallback_reason_counts": performance["fallback_reason_counts"],
        "frames": [str(path.resolve()) for path in frames],
        "frame_times_ms": FRAME_TIMES,
        "duration_ms": DURATION_MS,
        "fps": FPS,
        "layer_count": len(composition.layers),
        "torn_article_count": 8,
        "latest_pipeline_features": [
            "edge_decontamination",
            "local_light_match",
            "separate_contact_shadow",
            "track_matte",
            "generic_replicator",
            "paper_fold",
            "2_5d_camera_parallax",
            "kinetic_typography",
            "choreography_candidate_review",
            "deterministic_performance_gate",
        ],
    }
    (OUTPUT_DIR / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    report = render_showcase()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
