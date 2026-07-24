"""Render a fast, six-shot Morning Coffee concept advertisement."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.motion_designer.export_pipeline import MotionProfileExporter
from app.motion_designer.schema import Keyframe, MotionBehaviorRef, MotionComposition, MotionLayer, SourceRef


ASSET_DIR = ROOT / "outputs" / "motion_ai" / "morning_coffee"
OUTPUT_DIR = ASSET_DIR / "active_ad"
WIDTH = 1280
HEIGHT = 720
FPS = 30.0
DURATION_MS = 10_000


@dataclass(frozen=True)
class Shot:
    path: Path
    start_ms: int
    end_ms: int
    title: str
    support: str
    side: str
    accent: str
    position_from: tuple[float, float]
    position_to: tuple[float, float]
    scale_from: float
    scale_to: float
    rotation_from: float
    rotation_to: float


SHOTS = (
    Shot(ASSET_DIR / "shot_01_beans.png", 0, 1_600, "WAKE\nTHE SENSES", "ROASTED / READY / ALIVE", "left", "#FF9D2E",
         (650, 360), (620, 345), 1.05, 1.19, -0.8, 0.8),
    Shot(ASSET_DIR / "shot_02_pour.png", 1_300, 3_050, "POUR\nTHE ENERGY", "PRECISION IN EVERY DROP", "right", "#00C2D1",
         (620, 365), (660, 345), 1.10, 1.23, 1.0, -0.6),
    Shot(ASSET_DIR / "shot_03_espresso.png", 2_750, 4_550, "CREMA\nIN MOTION", "RICH BODY / CLEAN FINISH", "right", "#FFB000",
         (635, 350), (675, 370), 1.04, 1.18, -0.7, 0.7),
    Shot(ASSET_DIR / "shot_04_swirl.png", 4_250, 6_100, "HEAT\nMEETS AROMA", "SILK / SPIN / BALANCE", "left", "#00D6B4",
         (660, 350), (625, 370), 1.07, 1.24, 1.2, -1.0),
    Shot(ASSET_DIR / "shot_05_city.png", 5_800, 7_800, "OWN\nTHE MORNING", "YOUR CITY / YOUR PACE", "left", "#FF6B35",
         (645, 360), (610, 345), 1.05, 1.20, -0.5, 0.9),
    Shot(ASSET_DIR / "morning_coffee_hero.png", 7_500, 10_000, "START\nBRIGHT", "MAKE THE FIRST MOMENT YOURS", "left", "#00C2D1",
         (650, 365), (625, 345), 1.03, 1.12, 0.4, -0.3),
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _fade(duration_ms: int, enter_ms: int = 220, exit_ms: int = 250) -> list[MotionBehaviorRef]:
    return [
        MotionBehaviorRef(kind="fade", start_ms=0, end_ms=min(enter_ms, duration_ms),
                          params={"direction": "in", "easing": "ease_out", "hold_after": True}),
        MotionBehaviorRef(kind="fade", start_ms=max(0, duration_ms - exit_ms), end_ms=duration_ms,
                          params={"direction": "out", "easing": "ease_in", "hold_after": True}),
    ]


def _image_layer(shot: Shot, index: int) -> MotionLayer:
    duration = shot.end_ms - shot.start_ms
    direction = -1.0 if index % 2 else 1.0
    layer = MotionLayer(
        name=f"Shot {index + 1} / {shot.title.replace(chr(10), ' ')}",
        layer_type="image",
        source=SourceRef(kind="image", uri=str(shot.path.resolve()),
                         params={"width": WIDTH, "height": HEIGHT, "fit": "cover"}),
        in_ms=shot.start_ms,
        out_ms=shot.end_ms,
        behaviors=[
            *_fade(duration),
            MotionBehaviorRef(kind="slide", start_ms=0, end_ms=300,
                              params={"direction": "in", "distance": [direction * 92.0, 0.0],
                                      "easing": "ease_out", "hold_after": True}),
        ],
        metadata={"role": "campaign_shot", "shot_index": index + 1, "ai_generated": True},
    )
    layer.transform.position.keyframes = [
        Keyframe(time_ms=0, value=list(shot.position_from), interpolation="bezier"),
        Keyframe(time_ms=duration, value=list(shot.position_to), interpolation="bezier"),
    ]
    layer.transform.scale.keyframes = [
        Keyframe(time_ms=0, value=[shot.scale_from, shot.scale_from], interpolation="bezier"),
        Keyframe(time_ms=duration, value=[shot.scale_to, shot.scale_to], interpolation="bezier"),
    ]
    layer.transform.rotation.keyframes = [
        Keyframe(time_ms=0, value=shot.rotation_from, interpolation="bezier"),
        Keyframe(time_ms=duration, value=shot.rotation_to, interpolation="bezier"),
    ]
    return layer


def _shade_layer(shot: Shot, index: int) -> MotionLayer:
    dark = "#D40B0D10"
    clear = "#000B0D10"
    stops = ([
        {"position": 0.0, "color": dark},
        {"position": 0.52, "color": "#8C0B0D10"},
        {"position": 0.78, "color": clear},
        {"position": 1.0, "color": clear},
    ] if shot.side == "left" else [
        {"position": 0.0, "color": clear},
        {"position": 0.22, "color": clear},
        {"position": 0.52, "color": "#8C0B0D10"},
        {"position": 1.0, "color": dark},
    ])
    layer = MotionLayer(
        name=f"Shot {index + 1} Contrast",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "primitive": "rectangle", "width": WIDTH, "height": HEIGHT,
            "fill": "#00000000", "stroke_width": 0.0,
            "gradient": {"type": "linear", "start": [0.0, 0.5], "end": [1.0, 0.5], "stops": stops},
        }),
        in_ms=shot.start_ms,
        out_ms=shot.end_ms,
        behaviors=_fade(shot.end_ms - shot.start_ms, 180, 220),
        metadata={"role": "text_contrast", "shot_index": index + 1},
    )
    layer.transform.position.default = [WIDTH / 2, HEIGHT / 2]
    return layer


def _text_layer(shot: Shot, index: int, *, support: bool = False) -> MotionLayer:
    right = shot.side == "right"
    start = shot.start_ms + (160 if support else 70)
    end = shot.end_ms - 80
    duration = end - start
    font_size = 21 if support else 72
    width = 570 if support else 600
    height = 58 if support else 230
    x = WIDTH - 76 if right else 76
    y = 445 if support else 300
    text = shot.support if support else shot.title
    layer = MotionLayer(
        name=f"Shot {index + 1} {'Support' if support else 'Title'}",
        layer_type="text",
        source=SourceRef(kind="typography", params={
            "text": text,
            "font_family": "Segoe UI",
            "font_size": font_size,
            "font_weight": 500 if support else 700,
            "fill": "#FFF8EF" if not support else "#F0E2D1",
            "stroke_width": 0.0,
            "alignment": "right" if right else "left",
            "width": width,
            "height": height,
            "line_height": 0.94 if not support else 1.0,
            "letter_spacing": 0.0,
        }),
        in_ms=start,
        out_ms=end,
        behaviors=[
            *_fade(duration, 260, 220),
            MotionBehaviorRef(kind="slide", start_ms=0, end_ms=360,
                              params={"direction": "in", "distance": [(-1 if right else 1) * 130.0, 0.0],
                                      "easing": "ease_out", "hold_after": True}),
        ],
        metadata={"role": "kinetic_copy", "shot_index": index + 1},
    )
    layer.transform.anchor.default = [1.0 if right else 0.0, 0.5]
    layer.transform.position.default = [float(x), float(y)]
    return layer


def _shot_decor(shot: Shot, index: int) -> list[MotionLayer]:
    right = shot.side == "right"
    x = WIDTH - 76 if right else 76
    anchor = [1.0 if right else 0.0, 0.5]
    duration = shot.end_ms - shot.start_ms
    line = MotionLayer(
        name=f"Shot {index + 1} Accent",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "primitive": "rectangle", "width": 138, "height": 7,
            "fill": shot.accent, "stroke_width": 0.0,
        }),
        in_ms=shot.start_ms + 40,
        out_ms=shot.end_ms - 80,
        behaviors=[
            MotionBehaviorRef(kind="scale", start_ms=0, end_ms=340,
                              params={"from": 0.06, "overshoot": 0.08, "easing": "ease_out", "hold_after": True}),
            *_fade(max(1, duration - 120), 140, 200),
        ],
        metadata={"role": "accent", "shot_index": index + 1},
    )
    line.transform.anchor.default = anchor
    line.transform.position.default = [float(x), 172.0]

    counter = MotionLayer(
        name=f"Shot {index + 1} Counter",
        layer_type="text",
        source=SourceRef(kind="typography", params={
            "text": f"0{index + 1}  /  06",
            "font_family": "Segoe UI", "font_size": 18, "font_weight": 600,
            "fill": shot.accent, "stroke_width": 0.0,
            "alignment": "right" if right else "left", "width": 220, "height": 44,
        }),
        in_ms=shot.start_ms,
        out_ms=shot.end_ms,
        behaviors=_fade(duration, 160, 180),
        metadata={"role": "counter", "shot_index": index + 1},
    )
    counter.transform.anchor.default = anchor
    counter.transform.position.default = [float(x), 124.0]
    return [line, counter]


def _transition_layers(cut_ms: int, index: int, color: str) -> list[MotionLayer]:
    start = cut_ms - 80
    duration = 280
    flash = MotionLayer(
        name=f"Cut {index} Flash",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "primitive": "rectangle", "width": WIDTH, "height": HEIGHT,
            "fill": color, "stroke_width": 0.0,
        }),
        in_ms=start,
        out_ms=start + duration,
        blend_mode="screen",
        behaviors=[MotionBehaviorRef(kind="fade", start_ms=0, end_ms=duration,
                                    params={"direction": "out", "easing": "ease_out", "hold_after": True})],
        metadata={"role": "transition_flash", "cut_index": index},
    )
    flash.transform.position.default = [WIDTH / 2, HEIGHT / 2]
    flash.transform.opacity.default = 0.34

    sweep = MotionLayer(
        name=f"Cut {index} Diagonal Sweep",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "primitive": "rectangle", "width": 620, "height": 66,
            "fill": color, "stroke_width": 0.0,
        }),
        in_ms=start,
        out_ms=start + 420,
        blend_mode="screen",
        metadata={"role": "transition_sweep", "cut_index": index},
    )
    sweep.transform.position.keyframes = [
        Keyframe(time_ms=0, value=[-400, 360], interpolation="bezier"),
        Keyframe(time_ms=420, value=[1_680, 360], interpolation="bezier"),
    ]
    sweep.transform.rotation.default = -9.0 if index % 2 else 9.0
    sweep.transform.opacity.default = 0.62
    return [flash, sweep]


def build_composition() -> MotionComposition:
    composition = MotionComposition(
        name="Morning Coffee / Active Campaign",
        width=WIDTH,
        height=HEIGHT,
        fps=FPS,
        duration_ms=DURATION_MS,
    )
    composition.metadata.update({
        "demo": "morning_coffee_active_ad",
        "campaign_style": "kinetic six-shot premium beverage commercial",
        "asset_count": len(SHOTS),
        "audio": "silent_concept_cut",
    })
    for index, shot in enumerate(SHOTS):
        composition.layers.append(_image_layer(shot, index))
        composition.layers.append(_shade_layer(shot, index))
        composition.layers.extend(_shot_decor(shot, index))
        composition.layers.append(_text_layer(shot, index))
        composition.layers.append(_text_layer(shot, index, support=True))

    for index, shot in enumerate(SHOTS[1:], start=1):
        composition.layers.extend(_transition_layers(shot.start_ms, index, shot.accent))

    pulse = MotionLayer(
        name="Final Cup Pulse",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "primitive": "ellipse", "width": 250, "height": 250,
            "fill": "#00000000", "stroke": "#00C2D1", "stroke_width": 4.0,
        }),
        in_ms=8_050,
        out_ms=9_350,
        blend_mode="screen",
        behaviors=[
            MotionBehaviorRef(kind="pop", start_ms=0, end_ms=1_000,
                              params={"from": 0.15, "overshoot": 0.04, "hold_after": True}),
            MotionBehaviorRef(kind="fade", start_ms=500, end_ms=1_300,
                              params={"direction": "out", "hold_after": True}),
        ],
        metadata={"role": "final_product_pulse"},
    )
    pulse.transform.position.default = [912.0, 413.0]
    pulse.transform.opacity.default = 0.72
    composition.layers.append(pulse)
    return composition


def main() -> int:
    missing = [str(shot.path) for shot in SHOTS if not shot.path.is_file()]
    if missing:
        raise FileNotFoundError("Missing campaign assets: " + ", ".join(missing))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    composition = build_composition()
    _write_json(OUTPUT_DIR / "composition.json", composition.to_dict())
    _write_json(OUTPUT_DIR / "scenario.json", {
        "title": "Morning Coffee / Wake the Senses",
        "duration_ms": DURATION_MS,
        "logline": "Coffee moves from raw energy to a personal morning ritual in six accelerating visual beats.",
        "shots": [
            {
                "index": index + 1,
                "asset": str(shot.path.resolve()),
                "start_ms": shot.start_ms,
                "end_ms": shot.end_ms,
                "title": shot.title.replace("\n", " "),
                "support": shot.support,
                "motion": "crossfade + slide + zoom + rotation",
            }
            for index, shot in enumerate(SHOTS)
        ],
        "transition_count": len(SHOTS) - 1,
        "audio": "silent concept cut",
    })

    app = QApplication.instance() or QApplication([])
    exporter = MotionProfileExporter()
    previews: list[str] = []
    for index, time_ms in enumerate((700, 2_100, 3_500, 5_100, 6_600, 8_600), start=1):
        path = OUTPUT_DIR / f"preview_{index}_{time_ms}ms.png"
        exporter.export(composition, "png_still", path, time_ms=time_ms)
        previews.append(str(path.resolve()))
    video = OUTPUT_DIR / "morning_coffee_active_ad.mp4"
    result = exporter.export(composition, "h264_mp4", video, fps=FPS)
    app.processEvents()
    manifest = {
        "ok": True,
        "video": str(video.resolve()),
        "video_bytes": video.stat().st_size,
        "resolution": [WIDTH, HEIGHT],
        "fps": FPS,
        "duration_ms": DURATION_MS,
        "frame_count": result["frame_count"],
        "image_count": len(SHOTS),
        "transition_count": len(SHOTS) - 1,
        "layer_count": len(composition.layers),
        "previews": previews,
        "export": result,
    }
    _write_json(OUTPUT_DIR / "render_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
