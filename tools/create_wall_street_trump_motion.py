"""Create an editable newspaper/Trump editorial motion-graphics showcase."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.cut_paper import build_cut_paper_rig
from app.motion_designer.schema import (
    AnimatedProperty,
    Keyframe,
    MotionComposition,
    MotionLayer,
    MotionTransform,
    SourceRef,
)


ASSET_DIR = ROOT / "sample_assets" / "motion_ai_showcase" / "wall_street_trump"
OUTPUT_DIR = ROOT / "debugCapture" / "motion_ai_showcase" / "wall_street_trump"
PORTRAIT_SOURCE = ASSET_DIR / "trump_official_transparent_2025.png"
NEWSPAPER_PLATE = ASSET_DIR / "financial_broadsheet_plate.png"
TRUMP_CUTOUT = ASSET_DIR / "trump_official_transparent_2025_prepared.png"
WIDTH = 1280
HEIGHT = 720
FPS = 30.0
DURATION_MS = 8_000
TIMING_SCALE = DURATION_MS / 12_000.0
FRAME_TIMES = [0, 700, 1500, 2300, 3600, 4800, 6400, 7800]


def _time(value: int) -> int:
    return min(DURATION_MS, max(0, round(int(value) * TIMING_SCALE)))


def _clip_out_time(value: int) -> int:
    return DURATION_MS if int(value) == DURATION_MS else _time(value)


def _font(size: int, *, serif: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont:
    windows = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    candidates = (
        ["georgiab.ttf", "timesbd.ttf"] if serif and bold else
        ["georgia.ttf", "times.ttf"] if serif else
        ["bahnschrift.ttf", "arialbd.ttf"] if bold else
        ["segoeui.ttf", "arial.ttf"]
    )
    for name in candidates:
        path = windows / name
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _draw_financial_broadsheet(path: Path) -> Path:
    canvas = Image.new("RGB", (WIDTH, HEIGHT), "#17120f")
    draw = ImageDraw.Draw(canvas)
    for y in range(HEIGHT):
        shade = int(20 + 20 * (y / HEIGHT))
        draw.line((0, y, WIDTH, y), fill=(shade, max(14, shade - 7), max(10, shade - 12)))
    draw.ellipse((-180, -150, 880, 920), fill="#30231a")
    draw.ellipse((570, -260, 1530, 790), fill="#211915")

    paper = Image.new("RGBA", (1120, 650), (232, 225, 211, 255))
    pd = ImageDraw.Draw(paper)
    for y in range(650):
        tone = 238 - int(18 * y / 650)
        pd.line((0, y, 1120, y), fill=(tone, tone - 6, tone - 15, 255))
    rng = np.random.default_rng(47)
    for _ in range(4200):
        x = int(rng.integers(0, 1120))
        y = int(rng.integers(0, 650))
        a = int(rng.integers(5, 20))
        pd.point((x, y), fill=(92, 78, 62, a))

    small = _font(10, serif=True)
    pd.text((49, 70), "MONEY  /  POWER  /  MARKETS  /  POLICY", fill="#35312c", font=small)
    pd.line((45, 92, 1070, 92), fill="#28231e", width=3)
    pd.line((45, 98, 1070, 98), fill="#28231e", width=1)

    column_x = [50, 265, 480, 695, 910]
    headlines = [
        "MARKETS ENTER\nA NEW PHASE",
        "CAPITAL MOVES\nON POLICY",
        "GLOBAL TRADE\nAT A TURN",
        "WALL STREET\nWATCHES",
        "THE WEEK\nIN NUMBERS",
    ]
    for idx, x in enumerate(column_x):
        pd.multiline_text((x, 118), headlines[idx], fill="#171717", font=_font(19, serif=True, bold=True), spacing=1)
        baseline = 170
        for row in range(23):
            length = 175 - ((row * 17 + idx * 11) % 48)
            pd.rectangle((x, baseline + row * 12, x + length, baseline + row * 12 + 3), fill="#575049")
        if idx in {1, 3}:
            chart_y = 470
            points = []
            for step in range(9):
                value = 34 + int(20 * math.sin(step * 0.9 + idx)) + step * 3
                points.append((x + step * 20, chart_y - value))
            pd.line(points, fill="#23211f", width=3)
            pd.line((x, chart_y, x + 175, chart_y), fill="#49433d", width=1)
    for x in (250, 465, 680, 895):
        pd.line((x, 110, x, 615), fill="#8b8379", width=1)

    paper = paper.rotate(-2.0, resample=Image.Resampling.BICUBIC, expand=True)
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((72, 54, 1224, 700), radius=8, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow)
    canvas.alpha_composite(paper, (83, 45))
    draw = ImageDraw.Draw(canvas)
    draw.line((640, 70, 655, 674), fill=(105, 91, 76, 95), width=3)
    canvas = canvas.filter(ImageFilter.GaussianBlur(0.35))
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(path, quality=96)
    return path


def _prepare_trump_cutout(source: Path, output: Path) -> Path:
    with Image.open(source) as loaded:
        image = loaded.convert("RGBA")
    alpha = image.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None:
        raise ValueError(f"Transparent portrait has no visible pixels: {source}")
    padding = 12
    bounds = (
        max(0, bounds[0] - padding),
        max(0, bounds[1] - padding),
        min(image.width, bounds[2] + padding),
        min(image.height, bounds[3] + padding),
    )
    image = image.crop(bounds)
    max_height = 1040
    if image.height > max_height:
        ratio = max_height / image.height
        image = image.resize(
            (max(1, round(image.width * ratio)), max_height),
            Image.Resampling.LANCZOS,
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return output


def _animated(default: Any, rows: Iterable[tuple[int, Any]], value_type: str) -> AnimatedProperty:
    return AnimatedProperty(
        value_type=value_type,
        default=default,
        keyframes=[
            Keyframe(
                time_ms=_time(time_ms),
                value=value,
                interpolation="bezier",
                out_tangent=(0.2, 0.0),
                in_tangent=(0.8, 1.0),
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
    stroke: str = "#00000000",
    stroke_width: float = 0.0,
    position: tuple[float, float],
    position_keys: Iterable[tuple[int, list[float]]] = (),
    scale_keys: Iterable[tuple[int, list[float]]] = (),
    rotation_keys: Iterable[tuple[int, float]] = (),
    opacity_keys: Iterable[tuple[int, float]] = (),
    in_ms: int = 0,
    out_ms: int = DURATION_MS,
    radius: float = 0.0,
    blend_mode: str = "normal",
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
            "stroke": stroke,
            "stroke_width": stroke_width,
        }),
        transform=_transform(
            position=position,
            position_keys=position_keys,
            scale_keys=scale_keys,
            rotation_keys=rotation_keys,
            opacity_keys=opacity_keys,
        ),
        in_ms=_time(in_ms),
        out_ms=_clip_out_time(out_ms),
        blend_mode=blend_mode,
        metadata=metadata or {},
    )


def _text(
    name: str,
    text: str,
    *,
    position: tuple[float, float],
    width: int,
    height: int,
    font_size: int,
    fill: str = "#14110E",
    font_family: str = "Georgia",
    weight: int = 700,
    alignment: str = "center",
    position_keys: Iterable[tuple[int, list[float]]] = (),
    scale_keys: Iterable[tuple[int, list[float]]] = (),
    rotation_keys: Iterable[tuple[int, float]] = (),
    opacity_keys: Iterable[tuple[int, float]] = (),
    in_ms: int = 0,
    out_ms: int = DURATION_MS,
    metadata: dict[str, Any] | None = None,
) -> MotionLayer:
    return MotionLayer(
        name=name,
        layer_type="text",
        source=SourceRef(kind="typography", params={
            "text": text,
            "font_family": font_family,
            "font_size": font_size,
            "font_weight": weight,
            "fill": fill,
            "stroke_width": 0.0,
            "alignment": alignment,
            "width": width,
            "height": height,
            "line_height": 0.94,
            "letter_spacing": 0.0,
        }),
        transform=_transform(
            position=position,
            position_keys=position_keys,
            scale_keys=scale_keys,
            rotation_keys=rotation_keys,
            opacity_keys=opacity_keys,
        ),
        in_ms=_time(in_ms),
        out_ms=_clip_out_time(out_ms),
        metadata=metadata or {},
    )


def _card_layers(
    index: int,
    headline: str,
    positions: list[tuple[int, list[float]]],
    rotations: list[tuple[int, float]],
    *,
    front: bool,
) -> list[MotionLayer]:
    name = f"Article {index + 1}"
    metadata = {
        "role": "orbiting_article",
        "article_index": index + 1,
        "depth_plane": "front" if front else "back",
        "fictional_copy": True,
    }
    orbit_scale = 1.08 if front else 0.82
    start_scale = orbit_scale * 0.52
    shadow_positions = [
        (time_ms, [point[0] + 10, point[1] + 12])
        for time_ms, point in positions
    ]
    shadow = _shape(
        f"{name} Shadow",
        width=290,
        height=138,
        fill="#72000000",
        position=tuple(shadow_positions[0][1]),
        position_keys=shadow_positions,
        scale_keys=((0, [start_scale, start_scale]), (900, [start_scale, start_scale]), (1900, [orbit_scale, orbit_scale])),
        rotation_keys=rotations,
        opacity_keys=((0, 0.0), (500, 0.0), (1250, 0.58), (11_200, 0.58), (11_850, 0.0)),
        in_ms=3300,
        radius=5.0,
        metadata={**metadata, "role": "orbiting_article_shadow"},
    )
    shape = _shape(
        f"{name} Paper",
        width=284,
        height=132,
        fill="#F4EEE3",
        stroke="#2C2722",
        stroke_width=2.0,
        position=tuple(positions[0][1]),
        position_keys=positions,
        scale_keys=((0, [start_scale, start_scale]), (900, [start_scale, start_scale]), (1900, [orbit_scale, orbit_scale])),
        rotation_keys=rotations,
        opacity_keys=((0, 0.0), (500, 0.0), (1250, 1.0), (11_200, 1.0), (11_850, 0.0)),
        in_ms=3300,
        radius=4.0,
        metadata=metadata,
    )
    local_positions = [(t, [p[0], p[1] - 2]) for t, p in positions]
    title = _text(
        f"{name} Headline",
        headline,
        position=tuple(local_positions[0][1]),
        width=250,
        height=92,
        font_size=21,
        position_keys=local_positions,
        scale_keys=((0, [start_scale, start_scale]), (900, [start_scale, start_scale]), (1900, [orbit_scale, orbit_scale])),
        rotation_keys=rotations,
        opacity_keys=((0, 0.0), (500, 0.0), (1250, 1.0), (11_200, 1.0), (11_850, 0.0)),
        in_ms=3300,
        metadata=metadata,
    )
    return [shadow, shape, title]


def build_composition() -> MotionComposition:
    newspaper = _draw_financial_broadsheet(NEWSPAPER_PLATE)
    cutout = _prepare_trump_cutout(PORTRAIT_SOURCE, TRUMP_CUTOUT)
    with Image.open(cutout) as person:
        person_width, person_height = person.size

    composition = MotionComposition(
        name="The Story at the Center / Editorial Motion",
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
        duration_ms=DURATION_MS,
        metadata={
            "showcase": "wall_street_trump_editorial_motion",
            "editorial_disclaimer": "Fictional editorial motion-graphics concept; not affiliated with The Wall Street Journal.",
            "portrait_source": "Wikimedia Commons / transparent 2025 official White House portrait (public domain)",
            "portrait_url": "https://commons.wikimedia.org/wiki/File:January_2025_Official_Presidential_Portrait_of_Donald_J._Trump_(Transparent_Version).png",
            "layer_strategy": "newspaper plate + person cutout + native article cards + native typography",
        },
    )

    newspaper_layer = MotionLayer(
        name="Open Financial Broadsheet",
        layer_type="image",
        source=SourceRef(kind="image", uri=str(newspaper.resolve()), params={
            "width": WIDTH,
            "height": HEIGHT,
            "fit": "cover",
        }),
        transform=_transform(
            position=(WIDTH / 2, HEIGHT / 2),
            position_keys=((0, [610, 380]), (2500, [640, 360]), (11_999, [650, 355])),
            scale_keys=((0, [1.22, 1.22]), (2500, [1.03, 1.03]), (11_999, [1.08, 1.08])),
            rotation_keys=((0, -2.0), (2500, 0.0), (11_999, 0.7)),
        ),
        out_ms=DURATION_MS,
        metadata={"role": "newspaper_background"},
    )
    composition.layers.append(newspaper_layer)

    composition.layers.append(_shape(
        "Editorial Vignette",
        width=WIDTH,
        height=HEIGHT,
        fill="#42000000",
        position=(WIDTH / 2, HEIGHT / 2),
        out_ms=DURATION_MS,
        metadata={"role": "contrast_vignette"},
    ))
    composition.layers.append(_text(
        "Masthead",
        "THE WALL STREET JOURNAL",
        position=(640, 96),
        width=1040,
        height=82,
        font_size=51,
        position_keys=((0, [640, 55]), (1200, [640, 96]), (11_999, [640, 96])),
        opacity_keys=((0, 0.0), (550, 0.0), (1250, 1.0), (11_000, 1.0), (11_700, 0.0)),
        metadata={"role": "editorial_masthead", "trademark_reference": True},
    ))
    composition.layers.append(_shape(
        "Masthead Rule",
        width=1000,
        height=3,
        fill="#1A1714",
        position=(640, 139),
        scale_keys=((0, [0.0, 1.0]), (1450, [0.0, 1.0]), (2250, [1.0, 1.0])),
        opacity_keys=((0, 0.0), (1300, 0.0), (1900, 1.0)),
        metadata={"role": "masthead_rule"},
    ))

    headlines = [
        "MARKETS REACT\nTO A NEW ERA",
        "GLOBAL TRADE\nAT A TURN",
        "WALL STREET\nWATCHES",
        "POWER, POLICY\nAND PRICES",
        "INVESTORS BRACE\nFOR VOLATILITY",
        "THE ECONOMY\nAT A CROSSROADS",
    ]
    orbit_points = [
        [(0, [210, 520]), (1900, [285, 545]), (3600, [250, 165]), (5200, [250, 360]), (6900, [250, 555]), (8300, [250, 165])],
        [(0, [1060, 510]), (1900, [980, 545]), (3600, [1030, 165]), (5200, [1030, 360]), (6900, [1030, 555]), (8300, [1030, 165])],
        [(0, [225, 220]), (1900, [260, 235]), (3600, [250, 360]), (5200, [250, 555]), (6900, [250, 165]), (8300, [250, 360])],
        [(0, [1045, 210]), (1900, [1000, 230]), (3600, [1030, 360]), (5200, [1030, 555]), (6900, [1030, 165]), (8300, [1030, 360])],
        [(0, [640, 600]), (1900, [650, 585]), (3600, [250, 555]), (5200, [250, 165]), (6900, [250, 360]), (8300, [250, 555])],
        [(0, [640, 160]), (1900, [650, 170]), (3600, [1030, 555]), (5200, [1030, 165]), (6900, [1030, 360]), (8300, [1030, 555])],
    ]
    cards: list[list[MotionLayer]] = []
    for index, headline in enumerate(headlines):
        positions = [(time_ms, point) for time_ms, point in orbit_points[index]]
        positions.extend([
            (
                10_000,
                [
                    250 if index % 2 == 0 else 1030,
                    165 + (index // 2) * 195,
                ],
            ),
            (11_999, [640, 360]),
        ])
        rotations = [
            (0, -10.0 + index * 4.0),
            (1900, -7.0 + index * 2.0),
            (5200, 9.0 - index * 3.0),
            (8300, -5.0 + index * 2.0),
            (10_000, 0.0),
            (11_999, 0.0),
        ]
        cards.append(_card_layers(index, headline, positions, rotations, front=index >= 3))

    for pair in cards[:3]:
        composition.layers.extend(pair)

    composition.layers.append(_text(
        "Kinetic Word Power",
        "POWER",
        position=(315, 382),
        width=470,
        height=115,
        font_size=92,
        fill="#A61D1713",
        font_family="Bahnschrift",
        weight=700,
        position_keys=((0, [-180, 382]), (3300, [-180, 382]), (4200, [315, 382]), (7600, [280, 370]), (9000, [-240, 370])),
        scale_keys=((0, [1.35, 1.35]), (3300, [1.35, 1.35]), (4200, [1.0, 1.0]), (7600, [1.06, 1.06])),
        rotation_keys=((0, -8.0), (3300, -8.0), (4200, -1.0), (7600, 1.5)),
        opacity_keys=((0, 0.0), (3000, 0.0), (3600, 0.84), (8300, 0.84), (9200, 0.0)),
        in_ms=2800,
        metadata={"role": "kinetic_editorial_word", "depth_plane": "mid_back"},
    ))
    composition.layers.append(_text(
        "Kinetic Word Policy",
        "POLICY",
        position=(970, 382),
        width=510,
        height=115,
        font_size=92,
        fill="#A61D1713",
        font_family="Bahnschrift",
        weight=700,
        position_keys=((0, [1480, 382]), (3500, [1480, 382]), (4400, [970, 382]), (7600, [1000, 395]), (9200, [1510, 395])),
        scale_keys=((0, [1.35, 1.35]), (3500, [1.35, 1.35]), (4400, [1.0, 1.0]), (7600, [1.06, 1.06])),
        rotation_keys=((0, 8.0), (3500, 8.0), (4400, 1.0), (7600, -1.5)),
        opacity_keys=((0, 0.0), (3200, 0.0), (3800, 0.84), (8300, 0.84), (9300, 0.0)),
        in_ms=3000,
        metadata={"role": "kinetic_editorial_word", "depth_plane": "mid_back"},
    ))

    person_layer = MotionLayer(
        name="Donald Trump Portrait Cutout",
        layer_type="image",
        source=SourceRef(kind="image", uri=str(cutout.resolve()), params={
            "width": person_width,
            "height": person_height,
            "fit": "contain",
        }),
        transform=_transform(
            position=(640, 470),
            position_keys=((0, [640, 620]), (3100, [640, 620]), (4200, [640, 470]), (7600, [625, 465]), (10_800, [640, 470])),
            scale_keys=((0, [0.54, 0.54]), (3000, [0.54, 0.54]), (4300, [0.79, 0.79]), (7800, [0.84, 0.84]), (10_800, [0.79, 0.79])),
            rotation_keys=((0, 0.0), (4300, -1.0), (6300, 1.6), (8300, -0.8), (10_800, 0.0)),
            opacity_keys=((0, 0.0), (2500, 0.0), (3550, 1.0), (11_400, 1.0), (11_950, 0.0)),
        ),
        out_ms=DURATION_MS,
        metadata={
            "role": "central_subject",
            "person": "Donald Trump",
            "source_license": "public_domain_official_us_government_work",
        },
    )
    composition.layers.append(person_layer)

    for pair in cards[3:]:
        composition.layers.extend(pair)

    composition.layers.append(_shape(
        "Market Ticker Band",
        width=WIDTH,
        height=54,
        fill="#D9141110",
        position=(640, 686),
        position_keys=((0, [640, 755]), (6300, [640, 755]), (7000, [640, 686]), (10_300, [640, 686]), (11_000, [640, 755])),
        opacity_keys=((0, 0.0), (6300, 0.0), (7000, 1.0), (10_300, 1.0), (11_000, 0.0)),
        metadata={"role": "market_ticker"},
    ))
    composition.layers.append(_text(
        "Market Ticker Copy",
        "DOW  +0.84%    S&P  +0.51%    USD  103.42    POLICY  /  TRADE  /  CAPITAL",
        position=(640, 686),
        width=1180,
        height=42,
        font_size=19,
        fill="#F5EFE6",
        font_family="Bahnschrift",
        weight=600,
        position_keys=((0, [850, 755]), (6300, [850, 755]), (7000, [700, 686]), (10_300, [540, 686]), (11_000, [430, 755])),
        opacity_keys=((0, 0.0), (6300, 0.0), (7000, 1.0), (10_300, 1.0), (11_000, 0.0)),
        metadata={"role": "fictional_market_ticker", "fictional_copy": True},
    ))

    composition.layers.append(_shape(
        "Final Black",
        width=WIDTH,
        height=HEIGHT,
        fill="#E00B0A09",
        position=(640, 360),
        opacity_keys=((0, 0.0), (10_350, 0.0), (11_050, 1.0), (11_999, 1.0)),
        metadata={"role": "final_title_plate"},
    ))
    composition.layers.append(_text(
        "Final Title",
        "THE STORY\nAT THE CENTER",
        position=(640, 333),
        width=1050,
        height=250,
        font_size=76,
        fill="#F3EEE6",
        font_family="Georgia",
        weight=700,
        scale_keys=((0, [0.84, 0.84]), (10_450, [0.84, 0.84]), (11_200, [1.0, 1.0])),
        opacity_keys=((0, 0.0), (10_350, 0.0), (10_950, 1.0), (11_999, 1.0)),
        metadata={"role": "final_title"},
    ))
    composition.layers.append(_text(
        "Final Disclaimer",
        "FICTIONAL EDITORIAL MOTION GRAPHIC  /  TIGER STUDIO",
        position=(640, 500),
        width=950,
        height=42,
        font_size=18,
        fill="#BEB6AA",
        font_family="Bahnschrift",
        weight=500,
        opacity_keys=((0, 0.0), (10_700, 0.0), (11_300, 1.0), (11_999, 1.0)),
        metadata={"role": "editorial_disclaimer"},
    ))

    composition.layers.remove(person_layer)
    newspaper_index = composition.layers.index(newspaper_layer)
    composition.layers.insert(newspaper_index + 1, person_layer)
    cut_rig = build_cut_paper_rig(
        composition,
        newspaper_layer,
        center_x=640,
        center_y=390,
        radius_x=265,
        radius_y=310,
        start_ms=380,
        cut_duration_ms=1220,
        release_duration_ms=620,
        seed=47,
    )
    composition.layers[newspaper_index + 2:newspaper_index + 2] = cut_rig.layers
    composition.metadata["cut_paper_rig"] = cut_rig.to_dict()
    return composition


def _contact_sheet(paths: list[Path], labels: list[str], output: Path) -> Path:
    images = [Image.open(path).convert("RGB") for path in paths]
    thumb_width = 320
    thumb_height = 180
    label_height = 34
    canvas = Image.new("RGB", (thumb_width * 4, (thumb_height + label_height) * 2), "#11100e")
    draw = ImageDraw.Draw(canvas)
    font = _font(15)
    for index, (image, label) in enumerate(zip(images, labels)):
        image = image.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        x = (index % 4) * thumb_width
        y = (index // 4) * (thumb_height + label_height)
        canvas.paste(image, (x, y))
        draw.text((x + 10, y + thumb_height + 8), label, fill="#F3EEE6", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return output


def render_showcase(*, fps: float = FPS) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    _application = QApplication.instance() or QApplication([])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    composition = build_composition()
    composition_path = OUTPUT_DIR / "wall_street_trump.motion.json"
    composition_path.write_text(
        json.dumps(composition.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    scenario = {
        "schema": "tigerstudio.motion.editorial_scenario.v1",
        "title": "The Story at the Center",
        "duration_ms": DURATION_MS,
        "beats": [
            {"time": "0.0-1.7", "action": "Macro newspaper reveal and masthead lock-up"},
            {"time": "0.4-1.6", "action": "Scissors trace an irregular paper-cut contour"},
            {"time": "1.6-2.2", "action": "The released paper piece falls away to reveal Trump"},
            {"time": "2.4-5.5", "action": "POWER and POLICY collide behind the portrait"},
            {"time": "2.9-5.5", "action": "Six depth-scaled article cards orbit around the subject"},
            {"time": "4.2-6.9", "action": "Financial ticker crosses the lower third"},
            {"time": "5.5-7.2", "action": "Articles settle into a structured newspaper grid"},
            {"time": "7.2-8.0", "action": "Editorial end card resolves"},
        ],
        "claims": "All article headlines and market numbers are fictional visual copy.",
    }
    (OUTPUT_DIR / "scenario.json").write_text(
        json.dumps(scenario, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    renderer = MotionExportRenderer()
    frames = [
        renderer.save_png(composition, time_ms, OUTPUT_DIR / f"frame_{time_ms:05d}ms.png")
        for time_ms in FRAME_TIMES
    ]
    sheet = _contact_sheet(
        frames,
        [f"{time_ms / 1000:.1f}s" for time_ms in FRAME_TIMES],
        OUTPUT_DIR / "contact_sheet.png",
    )
    video = renderer.export_mp4(
        composition,
        OUTPUT_DIR / "wall_street_trump_editorial_motion.mp4",
        fps=fps,
    )
    report = {
        "schema": "tigerstudio.motion.wall_street_trump_showcase.v1",
        "ok": video.is_file() and video.stat().st_size > 0,
        "composition": str(composition_path.resolve()),
        "scenario": str((OUTPUT_DIR / "scenario.json").resolve()),
        "video": str(video.resolve()),
        "video_bytes": video.stat().st_size if video.is_file() else 0,
        "contact_sheet": str(sheet.resolve()),
        "frames": [str(path.resolve()) for path in frames],
        "frame_times_ms": FRAME_TIMES,
        "layer_count": len(composition.layers),
        "editable_article_layer_count": 18,
        "cut_paper_layer_count": 5,
        "fps": fps,
        "duration_ms": DURATION_MS,
    }
    (OUTPUT_DIR / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    if not PORTRAIT_SOURCE.is_file():
        raise FileNotFoundError(PORTRAIT_SOURCE)
    report = render_showcase()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
