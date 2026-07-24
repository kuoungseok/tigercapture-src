"""Build and render the Night Shift layered Motion Designer showcase."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.schema import (
    AnimatedProperty,
    Keyframe,
    MotionComposition,
    MotionLayer,
    MotionTransform,
    SourceRef,
)


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "sample_assets" / "motion_ai_showcase" / "night_shift"
OUTPUT_DIR = ROOT / "debugCapture" / "motion_ai_showcase" / "night_shift"
DURATION_MS = 7000
WIDTH = 720
HEIGHT = 1280


def _keyframes(
    default: Any,
    rows: Iterable[tuple[int, Any]],
    *,
    value_type: str,
) -> AnimatedProperty:
    return AnimatedProperty(
        value_type=value_type,
        default=default,
        keyframes=[
            Keyframe(
                time_ms=int(time_ms),
                value=value,
                interpolation="bezier",
                out_tangent=(0.18, 0.0),
                in_tangent=(0.82, 1.0),
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
        position=_keyframes(list(position), position_keys, value_type="vector2"),
        scale=_keyframes(list(scale), scale_keys, value_type="vector2"),
        rotation=_keyframes(rotation, rotation_keys, value_type="scalar"),
        opacity=_keyframes(opacity, opacity_keys, value_type="scalar"),
        anchor=AnimatedProperty(value_type="vector2", default=[0.5, 0.5]),
    )


def _image_layer(
    name: str,
    filename: str,
    *,
    width: int,
    height: int,
    position: tuple[float, float],
    position_keys: Iterable[tuple[int, list[float]]] = (),
    scale_keys: Iterable[tuple[int, list[float]]] = (),
    rotation_keys: Iterable[tuple[int, float]] = (),
    opacity_keys: Iterable[tuple[int, float]] = (),
    radius: float = 0.0,
) -> MotionLayer:
    return MotionLayer(
        name=name,
        layer_type="image",
        source=SourceRef(
            kind="image",
            uri=str((ASSET_DIR / filename).resolve()),
            params={
                "width": width,
                "height": height,
                "fit": "cover",
                "radius": radius,
            },
        ),
        transform=_transform(
            position=position,
            position_keys=position_keys,
            scale_keys=scale_keys,
            rotation_keys=rotation_keys,
            opacity_keys=opacity_keys,
        ),
        out_ms=DURATION_MS,
        metadata={"showcase": "night_shift", "role": "image_card"},
    )


def _shape_layer(
    name: str,
    *,
    width: int,
    height: int,
    fill: str,
    position: tuple[float, float],
    stroke: str = "transparent",
    stroke_width: float = 0.0,
    radius: float = 0.0,
    in_ms: int = 0,
    position_keys: Iterable[tuple[int, list[float]]] = (),
    scale_keys: Iterable[tuple[int, list[float]]] = (),
    rotation_keys: Iterable[tuple[int, float]] = (),
    opacity_keys: Iterable[tuple[int, float]] = (),
) -> MotionLayer:
    return MotionLayer(
        name=name,
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "shape": "rectangle",
                "width": width,
                "height": height,
                "fill": fill,
                "stroke": stroke,
                "stroke_width": stroke_width,
                "radius": radius,
            },
        ),
        transform=_transform(
            position=position,
            position_keys=position_keys,
            scale_keys=scale_keys,
            rotation_keys=rotation_keys,
            opacity_keys=opacity_keys,
        ),
        in_ms=in_ms,
        out_ms=DURATION_MS,
        metadata={"showcase": "night_shift", "role": "graphic_accent"},
    )


def _text_layer(
    name: str,
    text: str,
    *,
    font_size: int,
    position: tuple[float, float],
    width: int = 660,
    height: int = 160,
    fill: str = "#f6f7f8",
    weight: int = 800,
    tracking: float = 0.0,
    in_ms: int = 0,
    position_keys: Iterable[tuple[int, list[float]]] = (),
    scale_keys: Iterable[tuple[int, list[float]]] = (),
    opacity_keys: Iterable[tuple[int, float]] = (),
) -> MotionLayer:
    return MotionLayer(
        name=name,
        layer_type="text",
        source=SourceRef(
            kind="typography",
            params={
                "text": text,
                "font_family": "Bahnschrift",
                "font_size": font_size,
                "font_weight": weight,
                "fill": fill,
                "alignment": "center",
                "width": width,
                "height": height,
                "line_height": 0.88,
                "tracking": tracking,
            },
        ),
        transform=_transform(
            position=position,
            position_keys=position_keys,
            scale_keys=scale_keys,
            opacity_keys=opacity_keys,
        ),
        in_ms=in_ms,
        out_ms=DURATION_MS,
        metadata={"showcase": "night_shift", "role": "native_typography"},
    )


def build_composition() -> MotionComposition:
    composition = MotionComposition(
        name="Night Shift / Tiger Studio",
        width=WIDTH,
        height=HEIGHT,
        fps=30.0,
        duration_ms=DURATION_MS,
        metadata={
            "showcase": "night_shift",
            "scenario": str((ASSET_DIR / "SCENARIO.md").resolve()),
            "delivery": "vertical_social_ad",
        },
    )
    layers: list[MotionLayer] = []

    layers.append(_image_layer(
        "Night City Car",
        "night_city_car.png",
        width=WIDTH,
        height=HEIGHT,
        position=(WIDTH / 2, HEIGHT / 2),
        scale_keys=((0, [1.02, 1.02]), (4900, [1.15, 1.15]), (6999, [1.2, 1.2])),
    ))
    layers.append(_shape_layer(
        "Background Grade",
        width=WIDTH,
        height=HEIGHT,
        fill="#8a03070a",
        position=(WIDTH / 2, HEIGHT / 2),
    ))
    layers.append(_shape_layer(
        "Top Cyan Rule",
        width=430,
        height=8,
        fill="#35e6e8",
        position=(250, 72),
        scale_keys=((0, [0.0, 1.0]), (420, [1.0, 1.0]), (4800, [1.0, 1.0])),
    ))
    layers.append(_text_layer(
        "Night",
        "NIGHT",
        font_size=132,
        position=(330, 180),
        position_keys=((0, [-260, 180]), (650, [330, 180]), (4650, [330, 180]), (5200, [-360, 180])),
        opacity_keys=((0, 0.0), (180, 1.0), (4800, 1.0), (5200, 0.0)),
    ))
    layers.append(_text_layer(
        "Shift",
        "SHIFT",
        font_size=132,
        position=(400, 315),
        fill="#f6aa3c",
        position_keys=((0, [980, 315]), (820, [400, 315]), (4700, [400, 315]), (5200, [1020, 315])),
        opacity_keys=((0, 0.0), (240, 1.0), (4800, 1.0), (5200, 0.0)),
    ))
    layers.append(_text_layer(
        "Opening Strapline",
        "AFTER DARK / BEFORE EXPORT",
        font_size=24,
        position=(360, 430),
        width=620,
        height=70,
        weight=500,
        tracking=2.0,
        opacity_keys=((0, 0.0), (820, 0.0), (1150, 1.0), (4600, 1.0), (5000, 0.0)),
    ))

    layers.append(_shape_layer(
        "Editor Card Plate",
        width=620,
        height=370,
        fill="#0b1118",
        stroke="#35e6e8",
        stroke_width=5,
        radius=18,
        position=(390, 610),
        position_keys=((0, [1040, 550]), (1500, [1040, 550]), (2050, [390, 610]), (2250, [350, 590]), (4700, [330, 570]), (5300, [-540, 500])),
        rotation_keys=((0, 12.0), (1500, 12.0), (2050, -4.0), (4700, -2.0), (5300, -10.0)),
        opacity_keys=((0, 0.0), (1450, 0.0), (1600, 1.0), (5000, 1.0), (5350, 0.0)),
    ))
    layers.append(_image_layer(
        "Editor Workspace",
        "editor_workspace.png",
        width=600,
        height=350,
        position=(390, 610),
        position_keys=((0, [1040, 550]), (1500, [1040, 550]), (2050, [390, 610]), (2250, [350, 590]), (4700, [330, 570]), (5300, [-540, 500])),
        rotation_keys=((0, 12.0), (1500, 12.0), (2050, -4.0), (4700, -2.0), (5300, -10.0)),
        opacity_keys=((0, 0.0), (1450, 0.0), (1600, 1.0), (5000, 1.0), (5350, 0.0)),
        radius=14,
    ))

    layers.append(_shape_layer(
        "Sound Card Plate",
        width=570,
        height=338,
        fill="#0b1118",
        stroke="#f6aa3c",
        stroke_width=5,
        radius=18,
        position=(285, 965),
        position_keys=((0, [-580, 1040]), (1850, [-580, 1040]), (2450, [285, 965]), (2650, [315, 985]), (4700, [300, 1000]), (5350, [980, 1060])),
        rotation_keys=((0, -13.0), (1850, -13.0), (2450, 5.0), (4700, 3.0), (5350, 12.0)),
        opacity_keys=((0, 0.0), (1800, 0.0), (1980, 1.0), (5050, 1.0), (5400, 0.0)),
    ))
    layers.append(_image_layer(
        "Sound Console",
        "sound_console.png",
        width=550,
        height=318,
        position=(285, 965),
        position_keys=((0, [-580, 1040]), (1850, [-580, 1040]), (2450, [285, 965]), (2650, [315, 985]), (4700, [300, 1000]), (5350, [980, 1060])),
        rotation_keys=((0, -13.0), (1850, -13.0), (2450, 5.0), (4700, 3.0), (5350, 12.0)),
        opacity_keys=((0, 0.0), (1800, 0.0), (1980, 1.0), (5050, 1.0), (5400, 0.0)),
        radius=14,
    ))

    layers.append(_shape_layer(
        "Singer Card Plate",
        width=430,
        height=610,
        fill="#090d12",
        stroke="#f4f6f8",
        stroke_width=7,
        radius=20,
        position=(492, 735),
        position_keys=((0, [500, 1580]), (2200, [500, 1580]), (2900, [492, 735]), (3120, [492, 690]), (4700, [500, 715]), (5450, [500, 1420])),
        scale_keys=((0, [0.78, 0.78]), (2200, [0.78, 0.78]), (2900, [1.0, 1.0]), (3120, [1.05, 1.05]), (4700, [1.0, 1.0])),
        rotation_keys=((0, -8.0), (2200, -8.0), (2900, 2.5), (3120, 0.0), (4700, -1.0)),
        opacity_keys=((0, 0.0), (2150, 0.0), (2350, 1.0), (5200, 1.0), (5500, 0.0)),
    ))
    layers.append(_image_layer(
        "Virtual Singer",
        "virtual_singer.png",
        width=410,
        height=590,
        position=(492, 735),
        position_keys=((0, [500, 1580]), (2200, [500, 1580]), (2900, [492, 735]), (3120, [492, 690]), (4700, [500, 715]), (5450, [500, 1420])),
        scale_keys=((0, [0.78, 0.78]), (2200, [0.78, 0.78]), (2900, [1.0, 1.0]), (3120, [1.05, 1.05]), (4700, [1.0, 1.0])),
        rotation_keys=((0, -8.0), (2200, -8.0), (2900, 2.5), (3120, 0.0), (4700, -1.0)),
        opacity_keys=((0, 0.0), (2150, 0.0), (2350, 1.0), (5200, 1.0), (5500, 0.0)),
        radius=14,
    ))
    layers.append(_shape_layer(
        "Impact Marker Cyan",
        width=180,
        height=14,
        fill="#35e6e8",
        position=(104, 1170),
        scale_keys=((0, [0.0, 1.0]), (2550, [0.0, 1.0]), (2750, [1.0, 1.0]), (4500, [1.0, 1.0]), (5100, [0.0, 1.0])),
        opacity_keys=((0, 0.0), (2500, 1.0), (5050, 1.0), (5300, 0.0)),
    ))
    layers.append(_shape_layer(
        "Impact Marker Amber",
        width=280,
        height=5,
        fill="#f6aa3c",
        position=(558, 1206),
        scale_keys=((0, [0.0, 1.0]), (2800, [0.0, 1.0]), (3100, [1.0, 1.0]), (4550, [1.0, 1.0]), (5100, [0.0, 1.0])),
        opacity_keys=((0, 0.0), (2750, 1.0), (5050, 1.0), (5300, 0.0)),
    ))

    layers.append(_shape_layer(
        "End Card Veil",
        width=WIDTH,
        height=HEIGHT,
        fill="#ed030507",
        position=(WIDTH / 2, HEIGHT / 2),
        in_ms=4900,
        opacity_keys=((0, 0.0), (650, 1.0)),
    ))
    layers.append(_text_layer(
        "End Card Title",
        "TIGER STUDIO",
        font_size=76,
        position=(360, 560),
        width=680,
        height=180,
        weight=700,
        tracking=4.0,
        in_ms=5350,
        position_keys=((0, [360, 650]), (520, [360, 560])),
        scale_keys=((0, [0.82, 0.82]), (520, [1.0, 1.0])),
        opacity_keys=((0, 0.0), (180, 0.0), (520, 1.0)),
    ))
    layers.append(_shape_layer(
        "End Card Divider",
        width=430,
        height=3,
        fill="#35e6e8",
        position=(360, 684),
        in_ms=5600,
        scale_keys=((0, [0.0, 1.0]), (480, [1.0, 1.0])),
        opacity_keys=((0, 0.0), (120, 1.0)),
    ))
    layers.append(_text_layer(
        "End Card Promise",
        "CREATE / ANIMATE / BROADCAST",
        font_size=26,
        position=(360, 758),
        width=650,
        height=90,
        weight=500,
        tracking=2.0,
        in_ms=5750,
        position_keys=((0, [360, 800]), (450, [360, 758])),
        opacity_keys=((0, 0.0), (450, 1.0)),
    ))
    layers.append(_text_layer(
        "End Card Detail",
        "ONE CREATIVE WORKSPACE",
        font_size=18,
        position=(360, 845),
        width=620,
        height=70,
        fill="#aeb8c2",
        weight=400,
        tracking=3.0,
        in_ms=6000,
        opacity_keys=((0, 0.0), (420, 1.0)),
    ))

    composition.layers = layers
    return composition


def _contact_sheet(paths: list[Path], output: Path) -> Path:
    images = [Image.open(path).convert("RGB") for path in paths]
    thumb_width = 240
    thumbs = [
        image.resize(
            (thumb_width, round(image.height * thumb_width / image.width)),
            Image.Resampling.LANCZOS,
        )
        for image in images
    ]
    label_height = 32
    sheet = Image.new(
        "RGB",
        (thumb_width * len(thumbs), thumbs[0].height + label_height),
        "#101419",
    )
    painter = ImageDraw.Draw(sheet)
    for index, image in enumerate(thumbs):
        x = index * thumb_width
        sheet.paste(image, (x, 0))
        painter.text((x + 8, image.height + 8), f"{FRAME_TIMES[index] / 1000:.1f}s", fill="#f4f6f8")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    return output


FRAME_TIMES = [0, 900, 1900, 3000, 4500, 6200]


def render_showcase(*, fps: float = 15.0) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    composition = build_composition()
    missing = [
        layer.source.uri
        for layer in composition.layers
        if layer.layer_type == "image" and not Path(layer.source.uri).is_file()
    ]
    if missing:
        raise FileNotFoundError(f"Missing showcase image assets: {missing}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    composition_path = OUTPUT_DIR / "night_shift.motion.json"
    composition_path.write_text(
        json.dumps(composition.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    renderer = MotionExportRenderer()
    frames = [
        renderer.save_png(composition, time_ms, OUTPUT_DIR / f"frame_{time_ms:04d}ms.png")
        for time_ms in FRAME_TIMES
    ]
    contact_sheet = _contact_sheet(frames, OUTPUT_DIR / "contact_sheet.png")
    video = renderer.export_mp4(
        composition,
        OUTPUT_DIR / "night_shift_dynamic.mp4",
        fps=fps,
    )
    report = {
        "schema": "tigerstudio.motion.showcase.v1",
        "ok": video.is_file() and video.stat().st_size > 0 and all(path.is_file() for path in frames),
        "name": composition.name,
        "scenario": str((ASSET_DIR / "SCENARIO.md").resolve()),
        "composition": str(composition_path.resolve()),
        "video": str(video.resolve()),
        "video_bytes": video.stat().st_size if video.is_file() else 0,
        "contact_sheet": str(contact_sheet.resolve()),
        "frames": [str(path.resolve()) for path in frames],
        "frame_times_ms": FRAME_TIMES,
        "layer_count": len(composition.layers),
        "fps": fps,
        "duration_ms": composition.duration_ms,
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
