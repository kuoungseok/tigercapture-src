"""Render M26 story/platform evidence through the shared Motion renderer."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from time import perf_counter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageDraw
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.export_renderer import MotionExportRenderer  # noqa: E402
from app.motion_designer.schema import (  # noqa: E402
    AnimatedProperty,
    Keyframe,
    MotionComposition,
    MotionLayer,
    SourceRef,
)
from app.motion_designer.story_direction import (  # noqa: E402
    add_story_beat,
    apply_platform_variant,
    bind_story_audio,
    plan_platform_variant,
    preflight_platform,
    preflight_story,
    update_story,
)


DURATION_MS = 15_000
SAMPLE_TIMES = (700, 4200, 8600, 13_800)
PLATFORMS = ("landscape_16_9", "vertical_9_16", "square_1_1")


def _shape(
    name: str,
    role: str,
    fill: str,
    size: tuple[int, int],
    position: tuple[float, float],
) -> MotionLayer:
    layer = MotionLayer(
        name=name,
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "primitive": "rectangle",
                "width": size[0],
                "height": size[1],
                "fill": fill,
                "stroke": "#00000000",
                "stroke_width": 0,
                "corner_radius": 26,
            },
        ),
        out_ms=DURATION_MS,
        metadata={"story_role": role},
    )
    layer.transform.position.default = list(position)
    return layer


def _text(
    name: str,
    role: str,
    value: str,
    size: tuple[int, int],
    position: tuple[float, float],
    font_size: int,
    fill: str,
) -> MotionLayer:
    layer = MotionLayer(
        name=name,
        layer_type="text",
        source=SourceRef(
            kind="text",
            params={
                "text": value,
                "font_family": "Arial",
                "font_size": font_size,
                "font_weight": 800,
                "fill": fill,
                "alignment": "center",
                "width": size[0],
                "height": size[1],
            },
        ),
        out_ms=DURATION_MS,
        metadata={"story_role": role},
    )
    layer.transform.position.default = list(position)
    return layer


def _source_composition() -> MotionComposition:
    background = _shape(
        "Night Background",
        "background",
        "#0b1020",
        (1920, 1080),
        (960, 540),
    )
    accent = _shape(
        "Energy Accent",
        "content",
        "#ef5943",
        (920, 620),
        (580, 590),
    )
    accent.transform.rotation.default = -9.0
    character = _shape(
        "Morning Character",
        "character",
        "#f3c969",
        (520, 700),
        (960, 560),
    )
    character.source.params["primitive"] = "ellipse"
    character.transform.position = AnimatedProperty(
        value_type="vector2",
        default=[960.0, 560.0],
        keyframes=[
            Keyframe(time_ms=0, value=[870.0, 590.0], interpolation="bezier"),
            Keyframe(time_ms=7600, value=[1020.0, 530.0], interpolation="bezier"),
            Keyframe(time_ms=15_000, value=[960.0, 560.0], interpolation="bezier"),
        ],
    )
    headline = _text(
        "Headline",
        "headline",
        "WAKE THE CITY",
        (1100, 140),
        (960, 190),
        82,
        "#ffffff",
    )
    subtitle = _text(
        "Subtitle",
        "subtitle",
        "Energy arrives before the first sip.",
        (900, 100),
        (960, 830),
        44,
        "#d8e6ff",
    )
    cta_plate = _shape(
        "CTA Plate",
        "content",
        "#40d8b5",
        (500, 104),
        (960, 930),
    )
    cta = _text(
        "CTA",
        "cta",
        "START MOVING",
        (480, 90),
        (960, 930),
        46,
        "#07131b",
    )
    composition = MotionComposition(
        name="Wake The City",
        width=1920,
        height=1080,
        duration_ms=DURATION_MS,
        layers=[
            background,
            accent,
            character,
            headline,
            subtitle,
            cta_plate,
            cta,
        ],
    )
    update_story(
        composition,
        {
            "message": "Energy arrives before the first sip.",
            "audience": "Morning commuters",
            "character_continuity": {
                "hero": "Morning Character",
                "wardrobe_lock": "gold",
                "screen_direction": "left_to_right",
            },
        },
    )
    ranges = (
        ("hook", 0, 1600, "Stop the scroll", "surprise"),
        ("setup", 1600, 3400, "Name the morning", "recognition"),
        ("desire", 3400, 5200, "Create momentum", "anticipation"),
        ("conflict", 5200, 7000, "Break inertia", "tension"),
        ("reveal", 7000, 9000, "Reveal the energy", "delight"),
        ("proof", 9000, 11_000, "Show movement", "confidence"),
        ("payoff", 11_000, 13_200, "Own the city", "triumph"),
        ("cta", 13_200, 15_000, "Convert", "resolve"),
    )
    for index, (role, start, end, purpose, emotion) in enumerate(ranges):
        beat = add_story_beat(
            composition,
            role=role,
            start_ms=start,
            end_ms=end,
            purpose=purpose,
            emotion=emotion,
            character="Hero",
            copy="START MOVING" if role == "cta" else "",
            visual=f"Scene {index + 1}",
            scene_id=f"scene_{index + 1:02d}",
            layer_ids=[character.id, headline.id if index < 2 else subtitle.id],
        )
        state = composition.metadata["story_direction"]
        state["beats"][-1]["screen_direction"] = "left_to_right"
        if role == "hook":
            bind_story_audio(
                composition,
                beat_id=beat["id"],
                source_kind="music",
                source_id="music_lab_wake_126",
                cue_ms=0,
                label="126 BPM rise",
                tempo_bpm=126,
            )
        if role == "cta":
            bind_story_audio(
                composition,
                beat_id=beat["id"],
                source_kind="voice",
                source_id="voice_lab_start_moving",
                cue_ms=start + 120,
                label="Start moving",
            )
    return composition


def _annotated_thumbnail(path: Path, label: str) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image.thumbnail((420, 420), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (440, 470), "#0a0c11")
    x = (canvas.width - image.width) // 2
    y = 38 + (420 - image.height) // 2
    canvas.paste(image, (x, y))
    draw = ImageDraw.Draw(canvas)
    draw.text((14, 12), label, fill="#ffffff")
    return canvas


def _contact_sheet(rows: list[tuple[Path, str]], output: Path) -> None:
    thumbnails = [_annotated_thumbnail(path, label) for path, label in rows]
    sheet = Image.new("RGB", (440 * 4, 470 * 3), "#080a0e")
    for index, image in enumerate(thumbnails):
        sheet.paste(image, ((index % 4) * 440, (index // 4) * 470))
    sheet.save(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(ROOT / "debugCapture" / "motion_story_platform_qa"),
    )
    args = parser.parse_args()
    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    QApplication.instance() or QApplication([])
    renderer = MotionExportRenderer()
    source = _source_composition()
    source_snapshot = source.to_dict()
    story_report = preflight_story(source)
    if not story_report["ok"]:
        raise RuntimeError(story_report)

    frames: list[tuple[Path, str]] = []
    rows: list[dict] = []
    source_layer_ids = [layer.id for layer in source.layers]
    for platform in PLATFORMS:
        plan = plan_platform_variant(source, platform)
        variant = apply_platform_variant(source, plan, approved=True)
        preflight = preflight_platform(variant, platform=platform)
        if not preflight["ok"]:
            raise RuntimeError(preflight)
        if [layer.id for layer in variant.layers] != source_layer_ids:
            raise RuntimeError("platform reflow lost stable layer identity")
        timings: list[float] = []
        for time_ms in SAMPLE_TIMES:
            started = perf_counter()
            image = renderer.render_frame(variant, time_ms, use_cache=False)
            timings.append((perf_counter() - started) * 1000.0)
            path = output_dir / f"{platform}_{time_ms:05d}.png"
            if not image.save(str(path), "PNG"):
                raise RuntimeError(f"failed to save {path}")
            frames.append((path, f"{platform} / {time_ms / 1000:.1f}s"))
        rows.append({
            "platform": platform,
            "composition_id": variant.id,
            "size": [variant.width, variant.height],
            "plan_id": plan["id"],
            "diff_summary": plan["diff_summary"],
            "preflight": preflight,
            "frame_times_ms": [round(item, 3) for item in timings],
            "stable_id_loss": 0,
        })
    if source.to_dict() != source_snapshot:
        raise RuntimeError("platform QA mutated the source composition")
    contact_sheet = output_dir / "contact_sheet.png"
    _contact_sheet(frames, contact_sheet)
    report = {
        "schema": "tigerstudio.motion.story_platform.qa.v1",
        "ok": True,
        "duration_ms": DURATION_MS,
        "variant_count": len(rows),
        "frame_count": len(frames),
        "story_preflight": story_report,
        "source_unchanged": True,
        "contact_sheet": str(contact_sheet),
        "rows": rows,
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
