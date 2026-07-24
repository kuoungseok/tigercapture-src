"""Render a true single-image object-separation Motion Designer showcase."""
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

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.image_decomposition import (
    DecomposedImageElement,
    decompose_image,
)
from app.motion_designer.image_decomposition_edits import (
    replace_decomposition_background,
)
from app.motion_designer.schema import (
    AnimatedProperty,
    Keyframe,
    MotionComposition,
    MotionLayer,
    MotionTransform,
    SourceRef,
)

ASSET_DIR = ROOT / "sample_assets" / "motion_ai_showcase" / "night_shift"
OUTPUT_DIR = ROOT / "debugCapture" / "motion_ai_showcase" / "omni_object_motion"
SOURCE = ASSET_DIR / "single_source_character_car.png"
BACKGROUND_PLATE = ASSET_DIR / "single_source_clean_background.png"
WIDTH = 720
HEIGHT = 1280
DURATION_MS = 6000
FRAME_TIMES = [0, 450, 1200, 2400, 3800, 5400]
OBJECT_HINTS = [
    {
        "id": "character",
        "label": "character",
        "bbox": [0.01, 0.23, 0.38, 0.64],
        "foreground_points": [
            [0.13, 0.38],
            [0.08, 0.52],
            [0.20, 0.54],
            [0.08, 0.66],
            [0.21, 0.66],
            [0.06, 0.76],
            [0.20, 0.75],
            [0.055, 0.805],
            [0.19, 0.785],
        ],
        "background_points": [
            [0.145, 0.685],
            [0.145, 0.735],
            [0.145, 0.785],
            [0.365, 0.645],
        ],
    },
    {
        "id": "car",
        "label": "car",
        "bbox": [0.35, 0.47, 0.65, 0.35],
    },
]


def _animated(
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
                out_tangent=(0.2, 0.0),
                in_tangent=(0.8, 1.0),
            )
            for time_ms, value in rows
        ],
    )


def _source_animation(default: float, rows: Iterable[tuple[int, float]]) -> dict:
    return _animated(default, rows, value_type="scalar").to_dict()


def _transform(
    *,
    position: tuple[float, float],
    position_keys: Iterable[tuple[int, list[float]]] = (),
    scale_keys: Iterable[tuple[int, list[float]]] = (),
    rotation_keys: Iterable[tuple[int, float]] = (),
    opacity_keys: Iterable[tuple[int, float]] = (),
) -> MotionTransform:
    return MotionTransform(
        position=_animated(list(position), position_keys, value_type="vector2"),
        scale=_animated([1.0, 1.0], scale_keys, value_type="vector2"),
        rotation=_animated(0.0, rotation_keys, value_type="scalar"),
        opacity=_animated(1.0, opacity_keys, value_type="scalar"),
        anchor=AnimatedProperty(value_type="vector2", default=[0.5, 0.5]),
    )


def _image_layer(
    name: str,
    uri: str | Path,
    *,
    width: int,
    height: int,
    position: tuple[float, float],
    crop: tuple[int, int, int, int] | None = None,
    position_keys: Iterable[tuple[int, list[float]]] = (),
    scale_keys: Iterable[tuple[int, list[float]]] = (),
    rotation_keys: Iterable[tuple[int, float]] = (),
    opacity_keys: Iterable[tuple[int, float]] = (),
    tilt_x: dict | float = 0.0,
    tilt_y: dict | float = 0.0,
    perspective: float = 2.8,
) -> MotionLayer:
    params: dict[str, Any] = {
        "width": width,
        "height": height,
        "fit": "contain",
        "tilt_x": tilt_x,
        "tilt_y": tilt_y,
        "perspective": perspective,
    }
    if crop is not None:
        params["crop"] = list(crop)
    return MotionLayer(
        name=name,
        layer_type="image",
        source=SourceRef(kind="image", uri=str(Path(uri).resolve()), params=params),
        transform=_transform(
            position=position,
            position_keys=position_keys,
            scale_keys=scale_keys,
            rotation_keys=rotation_keys,
            opacity_keys=opacity_keys,
        ),
        out_ms=DURATION_MS,
        metadata={
            "showcase": "omni_object_motion",
            "object_separated": crop is not None,
        },
    )


def _text_layer() -> MotionLayer:
    return MotionLayer(
        name="Object Motion Title",
        layer_type="text",
        source=SourceRef(kind="typography", params={
            "text": "ONE IMAGE / TWO OBJECTS",
            "font_family": "Bahnschrift",
            "font_size": 31,
            "font_weight": 700,
            "fill": "#f5f7f8",
            "stroke": "#081016",
            "stroke_width": 1.2,
            "alignment": "center",
            "width": 650,
            "height": 88,
            "tracking": 2.0,
        }),
        transform=_transform(
            position=(360, 110),
            position_keys=((0, [360, 70]), (650, [360, 110])),
            opacity_keys=((0, 0.0), (320, 0.0), (720, 1.0), (5000, 1.0), (5600, 0.0)),
        ),
        out_ms=DURATION_MS,
    )


def _element_by_label(
    elements: list[DecomposedImageElement],
    label: str,
) -> DecomposedImageElement:
    element = next(
        (
            item
            for item in elements
            if str(item.metadata.get("semantic_label") or "").casefold()
            == label.casefold()
        ),
        None,
    )
    if element is None:
        raise RuntimeError(f"segmentation did not produce the {label!r} object")
    return element


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
        force=True,
    )
    decomposition = replace_decomposition_background(
        decomposition,
        BACKGROUND_PLATE,
        provider="generated_reviewed_background_plate",
    )
    character = _element_by_label(decomposition.elements, "character")
    car = _element_by_label(decomposition.elements, "car")
    character_center = (
        character.bbox[0] + character.bbox[2] * 0.5,
        character.bbox[1] + character.bbox[3] * 0.5,
    )
    car_center = (
        car.bbox[0] + car.bbox[2] * 0.5,
        car.bbox[1] + car.bbox[3] * 0.5,
    )

    composition = MotionComposition(
        name="Single Image / Character + Car Object Motion",
        width=WIDTH,
        height=HEIGHT,
        fps=30.0,
        duration_ms=DURATION_MS,
        metadata={
            "showcase": "omni_object_motion",
            "source_image": str(SOURCE.resolve()),
            "segmentation_provider": decomposition.diagnostics.get("segmentation_backend"),
            "background_provider": decomposition.diagnostics.get("inpaint", {}).get("provider"),
            "object_hints": OBJECT_HINTS,
        },
    )
    layers = [
        _image_layer(
            "Clean Background Plate",
            decomposition.background_path,
            width=WIDTH,
            height=HEIGHT,
            position=(WIDTH / 2, HEIGHT / 2),
            scale_keys=((0, [1.0, 1.0]), (5999, [1.045, 1.045])),
        ),
        _image_layer(
            "Separated Car",
            car.rgba_path,
            width=car.bbox[2],
            height=car.bbox[3],
            crop=car.bbox,
            position=car_center,
            position_keys=(
                (0, list(car_center)),
                (800, [car_center[0] - 18, car_center[1] + 4]),
                (2100, [car_center[0] + 34, car_center[1] - 16]),
                (3400, [car_center[0] - 12, car_center[1] + 6]),
                (5200, [car_center[0] + 48, car_center[1] - 8]),
                (5999, list(car_center)),
            ),
            scale_keys=(
                (0, [1.0, 1.0]),
                (2100, [1.11, 1.11]),
                (3400, [0.96, 0.96]),
                (5200, [1.13, 1.13]),
                (5999, [1.0, 1.0]),
            ),
            rotation_keys=((0, 0.0), (2100, -2.4), (3400, 1.4), (5200, -1.2), (5999, 0.0)),
            opacity_keys=((0, 0.0), (180, 0.0), (430, 1.0), (5999, 1.0)),
            tilt_x=_source_animation(0.0, ((0, 0.0), (2100, 5.0), (3400, -3.0), (5200, 4.0), (5999, 0.0))),
            tilt_y=_source_animation(0.0, ((0, 0.0), (2100, -10.0), (3400, 7.0), (5200, -8.0), (5999, 0.0))),
        ),
        _image_layer(
            "Separated Character",
            character.rgba_path,
            width=character.bbox[2],
            height=character.bbox[3],
            crop=character.bbox,
            position=character_center,
            position_keys=(
                (0, list(character_center)),
                (900, [character_center[0] + 12, character_center[1] - 8]),
                (2200, [character_center[0] + 38, character_center[1] - 25]),
                (3500, [character_center[0] - 14, character_center[1] + 2]),
                (5200, [character_center[0] + 22, character_center[1] - 18]),
                (5999, list(character_center)),
            ),
            scale_keys=(
                (0, [1.0, 1.0]),
                (2200, [1.075, 1.075]),
                (3500, [0.98, 0.98]),
                (5200, [1.09, 1.09]),
                (5999, [1.0, 1.0]),
            ),
            rotation_keys=((0, 0.0), (2200, 2.2), (3500, -1.5), (5200, 1.0), (5999, 0.0)),
            opacity_keys=((0, 0.0), (180, 0.0), (430, 1.0), (5999, 1.0)),
            tilt_x=_source_animation(0.0, ((0, 0.0), (2200, -4.0), (3500, 3.0), (5200, -3.0), (5999, 0.0))),
            tilt_y=_source_animation(0.0, ((0, 0.0), (2200, 9.0), (3500, -7.0), (5200, 8.0), (5999, 0.0))),
        ),
        _image_layer(
            "Original First Frame",
            SOURCE,
            width=WIDTH,
            height=HEIGHT,
            position=(WIDTH / 2, HEIGHT / 2),
            opacity_keys=((0, 1.0), (180, 1.0), (430, 0.0), (5999, 0.0)),
        ),
        _text_layer(),
    ]
    composition.layers = layers
    return composition, decomposition.to_dict()


def _sheet(paths: list[Path], output: Path, labels: list[str]) -> Path:
    images = [Image.open(path).convert("RGB") for path in paths]
    thumb_width = 220
    thumbs = [
        image.resize(
            (thumb_width, round(image.height * thumb_width / image.width)),
            Image.Resampling.LANCZOS,
        )
        for image in images
    ]
    label_height = 34
    canvas = Image.new(
        "RGB",
        (thumb_width * len(thumbs), max(item.height for item in thumbs) + label_height),
        "#101419",
    )
    painter = ImageDraw.Draw(canvas)
    for index, image in enumerate(thumbs):
        x = index * thumb_width
        canvas.paste(image, (x, 0))
        painter.text((x + 8, image.height + 9), labels[index], fill="#f4f6f8")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return output


def render_showcase(*, fps: float = 15.0) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    composition, decomposition = build_composition()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    composition_path = OUTPUT_DIR / "omni_object_motion.motion.json"
    composition_path.write_text(
        json.dumps(composition.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    decomposition_path = OUTPUT_DIR / "decomposition.json"
    decomposition_path.write_text(
        json.dumps(decomposition, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    renderer = MotionExportRenderer()
    frames = [
        renderer.save_png(composition, time_ms, OUTPUT_DIR / f"frame_{time_ms:04d}ms.png")
        for time_ms in FRAME_TIMES
    ]
    contact_sheet = _sheet(
        frames,
        OUTPUT_DIR / "contact_sheet.png",
        [f"{time_ms / 1000:.2f}s" for time_ms in FRAME_TIMES],
    )
    elements = {
        str(item.get("metadata", {}).get("semantic_label") or ""): item
        for item in decomposition["elements"]
    }
    separation_sheet = _sheet(
        [
            SOURCE,
            Path(elements["character"]["mask_path"]),
            Path(elements["car"]["mask_path"]),
            Path(decomposition["background_path"]),
        ],
        OUTPUT_DIR / "separation_sheet.png",
        ["SOURCE", "CHARACTER MASK", "CAR MASK", "CLEAN PLATE"],
    )
    video = renderer.export_mp4(
        composition,
        OUTPUT_DIR / "omni_object_motion.mp4",
        fps=fps,
    )
    report = {
        "schema": "tigerstudio.motion.object_separation_showcase.v1",
        "ok": (
            video.is_file()
            and video.stat().st_size > 0
            and len(decomposition["elements"]) >= 2
        ),
        "source": str(SOURCE.resolve()),
        "segmentation_provider": decomposition["diagnostics"].get("segmentation_backend"),
        "background_provider": decomposition["diagnostics"].get("inpaint", {}).get("provider"),
        "objects": [
            {
                "label": item.get("metadata", {}).get("semantic_label"),
                "bbox": item.get("bbox"),
                "mask_path": item.get("mask_path"),
                "rgba_path": item.get("rgba_path"),
            }
            for item in decomposition["elements"]
        ],
        "composition": str(composition_path.resolve()),
        "decomposition": str(decomposition_path.resolve()),
        "video": str(video.resolve()),
        "video_bytes": video.stat().st_size if video.is_file() else 0,
        "contact_sheet": str(contact_sheet.resolve()),
        "separation_sheet": str(separation_sheet.resolve()),
        "frame_times_ms": FRAME_TIMES,
        "layer_count": len(composition.layers),
        "fps": fps,
        "duration_ms": DURATION_MS,
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
