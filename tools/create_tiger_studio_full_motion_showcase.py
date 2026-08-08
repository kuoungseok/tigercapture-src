"""Build and render a 15-second Tiger Studio feature showcase."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.motion_designer.cut_paper import build_cut_paper_rig
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.image_decomposition import decompose_image
from app.motion_designer.image_decomposition_edits import replace_decomposition_background
from app.motion_designer.particles import create_particle_layer
from app.motion_designer.schema import (
    AnimatedProperty,
    Keyframe,
    MotionComposition,
    MotionEffectRef,
    MotionLayer,
    MotionTransform,
    SourceRef,
)

ASSET_DIR = ROOT / "sample_assets" / "motion_ai_showcase" / "night_shift"
OUTPUT_DIR = ROOT / "debugCapture" / "motion_ai_showcase" / "tiger_studio_full_15s"
SOURCE = ASSET_DIR / "single_source_character_car.png"
BACKGROUND = ASSET_DIR / "single_source_clean_background.png"
SINGER = ASSET_DIR / "virtual_singer.png"
EDITOR = ASSET_DIR / "editor_workspace.png"
SOUND = ASSET_DIR / "sound_console.png"
WIDTH = 720
HEIGHT = 1280
DURATION_MS = 15_000
FPS = 24.0
FRAME_TIMES = [350, 1_700, 3_300, 5_500, 8_300, 10_100, 11_900, 14_200]
OBJECT_HINTS = [
    {
        "id": "character",
        "label": "character",
        "bbox": [0.01, 0.23, 0.38, 0.64],
        "foreground_points": [
            [0.13, 0.38], [0.08, 0.52], [0.20, 0.54], [0.08, 0.66],
            [0.21, 0.66], [0.06, 0.76], [0.20, 0.75], [0.055, 0.805],
        ],
        "background_points": [[0.145, 0.685], [0.145, 0.735], [0.145, 0.785]],
    },
    {"id": "car", "label": "car", "bbox": [0.35, 0.47, 0.65, 0.35]},
]


def _animated(
    default: Any,
    rows: Iterable[tuple[int, Any]] = (),
    *,
    value_type: str = "scalar",
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
                in_tangent=(0.82, 1.0),
            )
            for time_ms, value in rows
        ],
    )


def _transform(
    *,
    position: tuple[float, float],
    time_origin: int = 0,
    position_keys: Iterable[tuple[int, list[float]]] = (),
    scale: tuple[float, float] = (1.0, 1.0),
    scale_keys: Iterable[tuple[int, list[float]]] = (),
    rotation: float = 0.0,
    rotation_keys: Iterable[tuple[int, float]] = (),
    opacity: float = 1.0,
    opacity_keys: Iterable[tuple[int, float]] = (),
) -> MotionTransform:
    def local(rows: Iterable[tuple[int, Any]]) -> list[tuple[int, Any]]:
        return [
            (max(0, int(time_ms) - int(time_origin)), value)
            for time_ms, value in rows
        ]

    return MotionTransform(
        position=_animated(list(position), local(position_keys), value_type="vector2"),
        scale=_animated(list(scale), local(scale_keys), value_type="vector2"),
        rotation=_animated(rotation, local(rotation_keys)),
        opacity=_animated(opacity, local(opacity_keys)),
        anchor=AnimatedProperty(value_type="vector2", default=[0.5, 0.5]),
    )


def _image(
    name: str,
    uri: str | Path,
    *,
    width: int,
    height: int,
    position: tuple[float, float],
    fit: str = "cover",
    crop: tuple[int, int, int, int] | None = None,
    in_ms: int = 0,
    out_ms: int = DURATION_MS,
    position_keys: Iterable[tuple[int, list[float]]] = (),
    scale: tuple[float, float] = (1.0, 1.0),
    scale_keys: Iterable[tuple[int, list[float]]] = (),
    rotation: float = 0.0,
    rotation_keys: Iterable[tuple[int, float]] = (),
    opacity_keys: Iterable[tuple[int, float]] = (),
    tilt_x: float = 0.0,
    tilt_y: float = 0.0,
    radius: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> MotionLayer:
    params: dict[str, Any] = {
        "width": int(width),
        "height": int(height),
        "fit": fit,
        "radius": float(radius),
        "tilt_x": float(tilt_x),
        "tilt_y": float(tilt_y),
        "perspective": 2.8,
    }
    if crop is not None:
        params["crop"] = list(crop)
    return MotionLayer(
        name=name,
        layer_type="image",
        source=SourceRef(kind="image", uri=str(Path(uri).resolve()), params=params),
        transform=_transform(
            position=position,
            time_origin=in_ms,
            position_keys=position_keys,
            scale=scale,
            scale_keys=scale_keys,
            rotation=rotation,
            rotation_keys=rotation_keys,
            opacity_keys=opacity_keys,
        ),
        in_ms=in_ms,
        out_ms=out_ms,
        metadata=dict(metadata or {}),
    )


def _shape(
    name: str,
    *,
    width: int,
    height: int,
    position: tuple[float, float],
    fill: str,
    primitive: str = "rectangle",
    radius: float = 0.0,
    in_ms: int = 0,
    out_ms: int = DURATION_MS,
    position_keys: Iterable[tuple[int, list[float]]] = (),
    scale_keys: Iterable[tuple[int, list[float]]] = (),
    rotation: float = 0.0,
    rotation_keys: Iterable[tuple[int, float]] = (),
    opacity_keys: Iterable[tuple[int, float]] = (),
    blend_mode: str = "normal",
) -> MotionLayer:
    layer = MotionLayer(
        name=name,
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "primitive": primitive,
            "width": width,
            "height": height,
            "fill": fill,
            "stroke": "#00000000",
            "stroke_width": 0.0,
            "radius": radius,
        }),
        transform=_transform(
            position=position,
            time_origin=in_ms,
            position_keys=position_keys,
            scale_keys=scale_keys,
            rotation=rotation,
            rotation_keys=rotation_keys,
            opacity_keys=opacity_keys,
        ),
        in_ms=in_ms,
        out_ms=out_ms,
        blend_mode=blend_mode,
    )
    return layer


def _text(
    name: str,
    text: str,
    *,
    position: tuple[float, float],
    width: int,
    height: int,
    size: float,
    fill: str = "#F4F6F8",
    weight: int = 700,
    align: str = "center",
    in_ms: int = 0,
    out_ms: int = DURATION_MS,
    position_keys: Iterable[tuple[int, list[float]]] = (),
    scale_keys: Iterable[tuple[int, list[float]]] = (),
    rotation: float = 0.0,
    rotation_keys: Iterable[tuple[int, float]] = (),
    opacity_keys: Iterable[tuple[int, float]] = (),
    animation_in: str = "slide-up-in",
    animation_hold: str = "none",
    animation_out: str = "fade-out",
    unit: str = "word",
    metadata: dict[str, Any] | None = None,
) -> MotionLayer:
    return MotionLayer(
        name=name,
        layer_type="text",
        source=SourceRef(kind="typography", params={
            "text": text,
            "font_family": "Bahnschrift",
            "font_size": float(size),
            "font_weight": int(weight),
            "fill": fill,
            "stroke": "#C0080B10",
            "stroke_width": 1.2,
            "shadow_color": "#98000000",
            "shadow_offset_x": 4.0,
            "shadow_offset_y": 5.0,
            "alignment": align,
            "width": width,
            "height": height,
            "tracking": 0.0,
            "text_animation": {
                "in": animation_in,
                "hold": animation_hold,
                "out": animation_out,
                "unit": unit,
                "stagger_ms": 52,
                "in_duration_ms": 520,
                "out_duration_ms": 360,
                "intensity": 1.0,
            },
        }),
        transform=_transform(
            position=position,
            time_origin=in_ms,
            position_keys=position_keys,
            scale_keys=scale_keys,
            rotation=rotation,
            rotation_keys=rotation_keys,
            opacity_keys=opacity_keys,
        ),
        in_ms=in_ms,
        out_ms=out_ms,
        metadata=dict(metadata or {}),
    )


def _effect(kind: str, **params: float) -> MotionEffectRef:
    return MotionEffectRef(
        kind=kind,
        params={
            name: AnimatedProperty(default=float(value))
            for name, value in params.items()
        },
    )


def _element_by_label(decomposition, label: str):
    return next(
        item
        for item in decomposition.elements
        if str(item.metadata.get("semantic_label") or "").casefold() == label.casefold()
    )


def _paper_plate(path: Path) -> Path:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#E8E2D5")
    draw = ImageDraw.Draw(image)
    for y in range(0, HEIGHT, 44):
        color = "#D8D1C4" if (y // 44) % 2 else "#EEE8DC"
        draw.rectangle((0, y, WIDTH, y + 22), fill=color)
    draw.rectangle((52, 70, WIDTH - 52, 210), fill="#161A20")
    draw.text((84, 106), "TIGER STUDIO / CREATIVE FILE", fill="#F5F1E8")
    for index in range(7):
        top = 275 + index * 112
        draw.rectangle((62, top, 658, top + 8), fill="#34383B")
        draw.rectangle((62, top + 24, 560 - index * 20, top + 35), fill="#9B958A")
        draw.rectangle((62, top + 50, 625, top + 57), fill="#C2BAAD")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def build_composition() -> tuple[MotionComposition, dict[str, Any]]:
    decomposition = decompose_image(
        SOURCE,
        width=WIDTH,
        height=HEIGHT,
        max_elements=4,
        include_depth=False,
        segmentation_mode="basic",
        object_hints=OBJECT_HINTS,
        inpaint_mode="fast",
        reconstruct_text=False,
        cache_root=OUTPUT_DIR / "cache",
        force=False,
    )
    decomposition = replace_decomposition_background(
        decomposition,
        BACKGROUND,
        provider="reviewed_clean_background",
    )
    character = _element_by_label(decomposition, "character")
    car = _element_by_label(decomposition, "car")
    char_center = (
        character.bbox[0] + character.bbox[2] * 0.5,
        character.bbox[1] + character.bbox[3] * 0.5,
    )
    car_center = (
        car.bbox[0] + car.bbox[2] * 0.5,
        car.bbox[1] + car.bbox[3] * 0.5,
    )
    composition = MotionComposition(
        name="Tiger Studio / Create After Dark",
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
        duration_ms=DURATION_MS,
        metadata={
            "schema": "tigerstudio.motion.full_showcase.v1",
            "campaign": "create_after_dark",
            "source_image": str(SOURCE.resolve()),
            "features": [
                "layered_object_motion",
                "perspective_tilt",
                "kinetic_typography",
                "particles",
                "track_matte",
                "cut_paper",
                "preview_export_parity",
            ],
        },
    )
    layers: list[MotionLayer] = []
    layers.append(_shape(
        "Black Base", width=WIDTH, height=HEIGHT, position=(360, 640), fill="#080B10",
    ))

    # Beat 1: fast photographic cold open.
    opening = _image(
        "Opening Source",
        SOURCE,
        width=WIDTH,
        height=HEIGHT,
        position=(360, 640),
        in_ms=0,
        out_ms=3_500,
        scale_keys=((0, [1.16, 1.16]), (3_450, [1.03, 1.03])),
        position_keys=((0, [380, 665]), (3_450, [350, 620])),
        opacity_keys=((0, 0.0), (120, 1.0), (3_050, 1.0), (3_450, 0.0)),
    )
    opening.effects.extend([
        _effect("saturation", amount=1.18),
        _effect("brightness_contrast", brightness=-0.04, contrast=1.12),
    ])
    layers.append(opening)
    layers.append(_shape(
        "Opening Cyan Slash",
        width=610,
        height=18,
        position=(360, 338),
        fill="#D91FE0D0",
        rotation=-8.0,
        in_ms=0,
        out_ms=3_400,
        scale_keys=((0, [0.03, 1.0]), (620, [1.0, 1.0]), (2_950, [1.0, 1.0]), (3_300, [0.05, 1.0])),
        opacity_keys=((0, 0.0), (120, 1.0), (3_100, 1.0), (3_350, 0.0)),
        blend_mode="screen",
    ))
    layers.extend([
        _text(
            "NIGHT",
            "NIGHT",
            position=(360, 465),
            width=650,
            height=190,
            size=138,
            in_ms=0,
            out_ms=3_300,
            position_keys=((0, [210, 465]), (520, [360, 465]), (2_850, [360, 465]), (3_250, [510, 465])),
            opacity_keys=((0, 0.0), (180, 1.0), (2_950, 1.0), (3_250, 0.0)),
            animation_in="cascade-in",
            animation_hold="hold-pulse",
            unit="character",
        ),
        _text(
            "SHIFT",
            "SHIFT",
            position=(360, 615),
            width=650,
            height=190,
            size=138,
            fill="#69E8DE",
            in_ms=0,
            out_ms=3_350,
            position_keys=((0, [510, 615]), (620, [360, 615]), (2_900, [360, 615]), (3_300, [210, 615])),
            opacity_keys=((0, 0.0), (240, 1.0), (2_980, 1.0), (3_300, 0.0)),
            animation_in="fold-paper-in",
            animation_hold="hold-sway",
            unit="character",
        ),
        _text(
            "Opening Subline",
            "ONE IMAGE. EVERY LAYER IN MOTION.",
            position=(360, 770),
            width=650,
            height=70,
            size=27,
            fill="#F3B36B",
            weight=500,
            in_ms=0,
            out_ms=3_350,
            opacity_keys=((0, 0.0), (850, 0.0), (1_220, 1.0), (2_950, 1.0), (3_300, 0.0)),
            animation_in="slide-up-in",
            unit="word",
        ),
    ])
    opening_particles = create_particle_layer(
        width=WIDTH,
        height=HEIGHT,
        duration_ms=3_400,
        name="Opening Sparks",
        params={
            "emitter": {"kind": "box", "position": [360, 680], "size": [600, 850], "radius": 0, "path": []},
            "birth_rate": 8.0,
            "bursts": [{"time_ms": 280, "count": 45}, {"time_ms": 2_420, "count": 30}],
            "lifetime_ms": 1_150.0,
            "velocity": {"speed": 85, "speed_variance": 0.5, "angle_deg": -90, "spread_deg": 150},
            "gravity": [0, 18],
            "particle": {
                "shape": "triangle",
                "size_start": 12,
                "size_end": 1,
                "opacity_start": 0.9,
                "opacity_end": 0.0,
                "color_start": "#69E8DE",
                "color_end": "#F3B36B00",
                "rotation_speed": 180,
                "sprite_uri": "",
            },
            "seed": 771,
            "max_particles": 220,
        },
    )
    opening_particles.in_ms = 0
    opening_particles.out_ms = 3_400
    opening_particles.blend_mode = "screen"
    layers.append(opening_particles)

    # Beat 2: one source becomes independently directed layers.
    layers.append(_image(
        "Clean City Plate",
        decomposition.background_path,
        width=WIDTH,
        height=HEIGHT,
        position=(360, 640),
        in_ms=2_950,
        out_ms=8_350,
        scale_keys=((2_950, [1.08, 1.08]), (8_250, [1.0, 1.0])),
        opacity_keys=((2_950, 0.0), (3_300, 1.0), (7_950, 1.0), (8_300, 0.0)),
    ))
    car_layer = _image(
        "Separated Car",
        car.rgba_path,
        width=car.bbox[2],
        height=car.bbox[3],
        position=car_center,
        crop=car.bbox,
        fit="contain",
        in_ms=2_950,
        out_ms=8_350,
        position_keys=(
            (2_950, [car_center[0] + 190, car_center[1] + 60]),
            (3_700, [car_center[0] + 12, car_center[1]]),
            (5_600, [car_center[0] - 35, car_center[1] - 12]),
            (7_700, [car_center[0] + 28, car_center[1] - 28]),
            (8_300, [car_center[0] + 120, car_center[1] - 15]),
        ),
        scale_keys=((2_950, [0.82, 0.82]), (3_700, [1.0, 1.0]), (5_600, [1.13, 1.13]), (7_700, [1.02, 1.02])),
        rotation_keys=((2_950, -5.0), (3_700, 0.0), (5_600, 2.0), (7_700, -1.4)),
        opacity_keys=((2_950, 0.0), (3_250, 1.0), (8_000, 1.0), (8_300, 0.0)),
        tilt_x=4.0,
        tilt_y=-8.0,
        metadata={"role": "separated_object", "semantic_label": "car"},
    )
    car_layer.effects.append(_effect("unsharp_mask", radius=1.2, amount=0.55))
    layers.append(car_layer)
    character_layer = _image(
        "Separated Character",
        character.rgba_path,
        width=character.bbox[2],
        height=character.bbox[3],
        position=char_center,
        crop=character.bbox,
        fit="contain",
        in_ms=2_950,
        out_ms=8_350,
        position_keys=(
            (2_950, [char_center[0] - 150, char_center[1] + 35]),
            (3_650, list(char_center)),
            (5_500, [char_center[0] + 26, char_center[1] - 28]),
            (7_650, [char_center[0] - 16, char_center[1] - 10]),
            (8_300, [char_center[0] - 100, char_center[1] - 8]),
        ),
        scale_keys=((2_950, [0.86, 0.86]), (3_650, [1.0, 1.0]), (5_500, [1.08, 1.08]), (7_650, [1.02, 1.02])),
        rotation_keys=((2_950, 4.0), (3_650, 0.0), (5_500, -2.2), (7_650, 1.0)),
        opacity_keys=((2_950, 0.0), (3_250, 1.0), (8_000, 1.0), (8_300, 0.0)),
        tilt_x=-3.0,
        tilt_y=7.0,
        metadata={"role": "separated_object", "semantic_label": "character"},
    )
    character_layer.effects.append(_effect("unsharp_mask", radius=1.0, amount=0.45))
    layers.append(character_layer)
    layers.extend([
        _text(
            "Separate",
            "SEPARATE",
            position=(360, 138),
            width=650,
            height=110,
            size=61,
            fill="#69E8DE",
            in_ms=3_150,
            out_ms=5_150,
            position_keys=((3_150, [360, 80]), (3_650, [360, 138]), (4_800, [360, 138]), (5_100, [360, 95])),
            opacity_keys=((3_150, 0.0), (3_450, 1.0), (4_850, 1.0), (5_100, 0.0)),
            animation_in="cascade-in",
            unit="character",
        ),
        _text(
            "Animate",
            "ANIMATE",
            position=(360, 138),
            width=650,
            height=110,
            size=61,
            fill="#F3B36B",
            in_ms=4_900,
            out_ms=6_800,
            opacity_keys=((4_900, 0.0), (5_200, 1.0), (6_450, 1.0), (6_750, 0.0)),
            animation_in="fold-paper-in",
            animation_hold="hold-wave",
            unit="character",
        ),
        _text(
            "Direct",
            "DIRECT",
            position=(360, 138),
            width=650,
            height=110,
            size=61,
            fill="#F4F6F8",
            in_ms=6_550,
            out_ms=8_300,
            opacity_keys=((6_550, 0.0), (6_850, 1.0), (7_950, 1.0), (8_250, 0.0)),
            animation_in="bounce-in",
            unit="character",
        ),
    ])
    layers.append(_shape(
        "Object Divider",
        width=560,
        height=7,
        position=(360, 218),
        fill="#D9FFFFFF",
        in_ms=3_100,
        out_ms=8_250,
        scale_keys=((3_100, [0.0, 1.0]), (3_700, [1.0, 1.0]), (7_900, [1.0, 1.0]), (8_220, [0.0, 1.0])),
        opacity_keys=((3_100, 0.0), (3_300, 1.0), (7_950, 1.0), (8_220, 0.0)),
        blend_mode="screen",
    ))

    # Beat 3: editorial panels and an actual text track matte.
    layers.append(_shape(
        "Panel Scene Back",
        width=WIDTH,
        height=HEIGHT,
        position=(360, 640),
        fill="#F20B0F16",
        in_ms=7_850,
        out_ms=11_450,
        opacity_keys=((7_850, 0.0), (8_150, 1.0), (11_100, 1.0), (11_400, 0.0)),
    ))
    panel_specs = [
        ("Voice Panel", SINGER, (164, 555), 310, 520, -7.0, -8.0, 8_000),
        ("Edit Panel", EDITOR, (430, 430), 470, 300, 4.5, 7.0, 8_200),
        ("Music Panel", SOUND, (450, 865), 440, 330, -4.0, -6.0, 8_400),
    ]
    for index, (name, uri, position, width, height, rotation, tilt_y, start) in enumerate(panel_specs):
        panel = _image(
            name,
            uri,
            width=width,
            height=height,
            position=position,
            fit="cover",
            radius=16,
            in_ms=7_850,
            out_ms=11_450,
            position_keys=((start, [position[0] + (160 if index % 2 else -160), position[1] + 80]), (start + 520, list(position)), (10_850, list(position)), (11_350, [position[0] + (90 if index % 2 else -90), position[1] - 50])),
            scale_keys=((start, [0.75, 0.75]), (start + 520, [1.0, 1.0]), (10_850, [1.03, 1.03]), (11_350, [0.84, 0.84])),
            rotation=rotation,
            rotation_keys=((start, rotation * 1.7), (start + 520, rotation), (10_850, -rotation * 0.4), (11_350, rotation * 1.4)),
            opacity_keys=((7_850, 0.0), (start, 0.0), (start + 300, 1.0), (11_050, 1.0), (11_380, 0.0)),
            tilt_x=-3.0 if index == 1 else 2.0,
            tilt_y=tilt_y,
            metadata={"role": "media_panel"},
        )
        panel.effects.append(_effect("unsharp_mask", radius=1.1, amount=0.5))
        layers.append(panel)
    layers.extend([
        _text(
            "Panel Voice Label",
            "VOICE",
            position=(140, 285),
            width=250,
            height=68,
            size=32,
            fill="#69E8DE",
            in_ms=8_000,
            out_ms=11_300,
            opacity_keys=((8_000, 0.0), (8_450, 1.0), (10_900, 1.0), (11_250, 0.0)),
        ),
        _text(
            "Panel Motion Label",
            "MOTION",
            position=(500, 228),
            width=320,
            height=68,
            size=32,
            fill="#F4F6F8",
            in_ms=8_100,
            out_ms=11_300,
            opacity_keys=((8_100, 0.0), (8_600, 1.0), (10_900, 1.0), (11_250, 0.0)),
        ),
        _text(
            "Panel Music Label",
            "MUSIC",
            position=(510, 1_075),
            width=280,
            height=68,
            size=32,
            fill="#F3B36B",
            in_ms=8_250,
            out_ms=11_300,
            opacity_keys=((8_250, 0.0), (8_750, 1.0), (10_900, 1.0), (11_250, 0.0)),
        ),
    ])
    matte = _text(
        "Create Matte",
        "CREATE",
        position=(360, 665),
        width=700,
        height=250,
        size=128,
        fill="#FFFFFF",
        in_ms=8_250,
        out_ms=11_250,
        scale_keys=((8_250, [0.72, 0.72]), (9_050, [1.0, 1.0]), (10_650, [1.08, 1.08]), (11_200, [1.25, 1.25])),
        animation_in="cascade-in",
        animation_hold="hold-pulse",
        unit="character",
    )
    layers.append(matte)
    matte_fill = _image(
        "Create Image Matte Fill",
        SINGER,
        width=WIDTH,
        height=HEIGHT,
        position=(360, 640),
        fit="cover",
        in_ms=8_250,
        out_ms=11_250,
        scale_keys=((8_250, [1.0, 1.0]), (11_200, [1.12, 1.12])),
        opacity_keys=((8_250, 0.0), (8_600, 0.94), (10_900, 0.94), (11_200, 0.0)),
        metadata={"matte_layer_id": matte.id, "matte_mode": "alpha", "role": "track_matte_fill"},
    )
    matte_fill.blend_mode = "screen"
    matte_fill.effects.extend([
        _effect("brightness_contrast", brightness=0.12, contrast=1.35),
        _effect("saturation", amount=1.35),
        _effect("glow", threshold=0.42, radius=7.0, intensity=0.55),
    ])
    layers.append(matte_fill)
    matte_outline = _text(
        "Create Matte Outline",
        "CREATE",
        position=(360, 665),
        width=700,
        height=250,
        size=128,
        fill="#08000000",
        in_ms=8_250,
        out_ms=11_250,
        scale_keys=((8_250, [0.72, 0.72]), (9_050, [1.0, 1.0]), (10_650, [1.08, 1.08]), (11_200, [1.25, 1.25])),
        opacity_keys=((8_250, 0.0), (8_600, 1.0), (10_900, 1.0), (11_200, 0.0)),
        animation_in="cascade-in",
        animation_hold="hold-pulse",
        unit="character",
    )
    matte_outline.source.params["stroke"] = "#D969E8DE"
    matte_outline.source.params["stroke_width"] = 2.4
    matte_outline.source.params["shadow_color"] = "#00000000"
    layers.append(matte_outline)

    # Beat 4: paper cut reveals the final product card.
    paper_path = _paper_plate(OUTPUT_DIR / "paper_plate.png")
    paper = _image(
        "Creative File Paper",
        paper_path,
        width=WIDTH,
        height=HEIGHT,
        position=(360, 640),
        in_ms=0,
        out_ms=DURATION_MS,
        opacity_keys=((0, 0.0), (10_700, 0.0), (10_980, 1.0), (14_999, 1.0)),
        metadata={"role": "cut_paper_source"},
    )
    layers.append(paper)
    layers.append(_shape(
        "Final Surface",
        width=WIDTH,
        height=HEIGHT,
        position=(360, 640),
        fill="#FF080B10",
        in_ms=10_600,
        out_ms=DURATION_MS,
        opacity_keys=((10_600, 0.0), (10_900, 1.0), (14_999, 1.0)),
    ))
    layers.append(_shape(
        "Final Cyan Ring",
        width=390,
        height=390,
        position=(360, 495),
        fill="#001FE0D0",
        primitive="ellipse",
        in_ms=10_700,
        out_ms=DURATION_MS,
        scale_keys=((10_700, [0.15, 0.15]), (12_600, [1.0, 1.0]), (13_600, [1.08, 1.08]), (14_999, [1.0, 1.0])),
        opacity_keys=((10_700, 0.0), (12_100, 1.0), (14_999, 1.0)),
        blend_mode="screen",
    ))
    layers.extend([
        _text(
            "Final Tiger",
            "TIGER",
            position=(360, 440),
            width=680,
            height=180,
            size=132,
            fill="#F4F6F8",
            in_ms=10_700,
            out_ms=DURATION_MS,
            scale_keys=((10_700, [0.68, 0.68]), (12_650, [1.0, 1.0]), (14_999, [1.0, 1.0])),
            opacity_keys=((10_700, 0.0), (12_050, 0.0), (12_650, 1.0), (14_999, 1.0)),
            animation_in="cascade-in",
            animation_hold="hold-pulse",
            animation_out="none",
            unit="character",
        ),
        _text(
            "Final Studio",
            "STUDIO",
            position=(360, 585),
            width=680,
            height=160,
            size=98,
            fill="#69E8DE",
            in_ms=10_700,
            out_ms=DURATION_MS,
            opacity_keys=((10_700, 0.0), (12_250, 0.0), (12_850, 1.0), (14_999, 1.0)),
            animation_in="fold-paper-in",
            animation_out="none",
            unit="character",
        ),
        _text(
            "Final Promise",
            "EDIT / ANIMATE / VOICE / PUBLISH",
            position=(360, 755),
            width=660,
            height=70,
            size=25,
            fill="#F3B36B",
            weight=500,
            in_ms=10_700,
            out_ms=DURATION_MS,
            opacity_keys=((10_700, 0.0), (12_800, 0.0), (13_350, 1.0), (14_999, 1.0)),
            animation_in="slide-up-in",
            animation_out="none",
            unit="word",
        ),
        _text(
            "Final Tagline",
            "ONE CREATIVE WORKSPACE",
            position=(360, 838),
            width=650,
            height=70,
            size=24,
            fill="#BFC8D2",
            weight=500,
            in_ms=10_700,
            out_ms=DURATION_MS,
            opacity_keys=((10_700, 0.0), (13_150, 0.0), (13_650, 1.0), (14_999, 1.0)),
            animation_in="cascade-in",
            animation_out="none",
            unit="character",
        ),
    ])
    cut_rig = build_cut_paper_rig(
        composition,
        paper,
        center_x=360,
        center_y=610,
        radius_x=260,
        radius_y=350,
        start_ms=11_050,
        cut_duration_ms=1_300,
        release_duration_ms=620,
        seed=109,
    )
    cut_rig.piece.transform.opacity = _animated(
        0.0,
        (
            (0, 0.0),
            (10_979, 0.0),
            (10_980, 1.0),
            (12_350, 1.0),
            (12_890, 0.92),
            (12_970, 0.0),
        ),
    )
    layers.extend(cut_rig.layers)
    final_particles = create_particle_layer(
        width=WIDTH,
        height=HEIGHT,
        duration_ms=DURATION_MS,
        name="Final Signal Burst",
        params={
            "emitter": {"kind": "circle", "position": [360, 610], "size": [1, 1], "radius": 210, "path": []},
            "birth_rate": 0.0,
            "bursts": [{"time_ms": 1_750, "count": 88}],
            "lifetime_ms": 1_900.0,
            "velocity": {"speed": 130, "speed_variance": 0.48, "angle_deg": -90, "spread_deg": 360},
            "gravity": [0, 20],
            "particle": {
                "shape": "triangle",
                "size_start": 14,
                "size_end": 1,
                "opacity_start": 0.95,
                "opacity_end": 0.0,
                "color_start": "#69E8DE",
                "color_end": "#F3B36B00",
                "rotation_speed": 210,
                "sprite_uri": "",
            },
            "seed": 909,
            "max_particles": 180,
        },
    )
    final_particles.in_ms = 10_700
    final_particles.out_ms = DURATION_MS
    final_particles.blend_mode = "screen"
    layers.append(final_particles)
    composition.layers = layers
    composition.metadata["cut_paper_rig"] = cut_rig.to_dict()
    return composition, decomposition.to_dict()


def _contact_sheet(paths: list[Path], labels: list[str], output: Path) -> Path:
    images = [Image.open(path).convert("RGB") for path in paths]
    thumb_width = 240
    thumb_height = round(thumb_width * HEIGHT / WIDTH)
    label_height = 34
    canvas = Image.new(
        "RGB",
        (thumb_width * 4, (thumb_height + label_height) * 2),
        "#0A0D12",
    )
    draw = ImageDraw.Draw(canvas)
    for index, (image, label) in enumerate(zip(images, labels)):
        thumb = image.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        x = (index % 4) * thumb_width
        y = (index // 4) * (thumb_height + label_height)
        canvas.paste(thumb, (x, y))
        draw.text((x + 9, y + thumb_height + 9), label, fill="#F4F6F8")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return output


def render_showcase(*, fps: float = FPS) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    _application = QApplication.instance() or QApplication([])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    composition, decomposition = build_composition()
    composition_path = OUTPUT_DIR / "tiger_studio_full_15s.motion.json"
    composition_path.write_text(
        json.dumps(composition.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    scenario = {
        "schema": "tigerstudio.motion.full_showcase_scenario.v1",
        "title": "Create After Dark",
        "duration_ms": DURATION_MS,
        "beats": [
            {"range": "0.0-3.3", "action": "Photographic cold open, kinetic type, sparks"},
            {"range": "3.0-8.3", "action": "Character/car extraction and independent 2.5D direction"},
            {"range": "7.9-11.4", "action": "Media panels, perspective cards, image-filled text matte"},
            {"range": "10.7-15.0", "action": "Cut-paper reveal, particle burst, Tiger Studio end card"},
        ],
    }
    (OUTPUT_DIR / "scenario.json").write_text(
        json.dumps(scenario, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    renderer = MotionExportRenderer(cache_capacity=12)
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
        OUTPUT_DIR / "tiger_studio_full_15s.mp4",
        fps=fps,
    )
    report = {
        "schema": "tigerstudio.motion.full_showcase_report.v1",
        "ok": bool(video.is_file() and video.stat().st_size > 0),
        "composition": str(composition_path.resolve()),
        "video": str(video.resolve()),
        "video_bytes": video.stat().st_size if video.is_file() else 0,
        "contact_sheet": str(contact_sheet.resolve()),
        "duration_ms": DURATION_MS,
        "fps": fps,
        "layer_count": len(composition.layers),
        "frame_times_ms": FRAME_TIMES,
        "features": composition.metadata["features"],
        "decomposition_provider": decomposition["diagnostics"].get("segmentation_backend"),
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
