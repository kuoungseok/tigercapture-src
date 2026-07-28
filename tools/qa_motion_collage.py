"""Render real M23 collage evidence through the shared Motion exporter."""
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

from app.motion_designer.collage import (  # noqa: E402
    create_collage_board,
    preflight_collage,
    replace_collage_item_source,
    set_collage_attachment,
    set_collage_edge,
    set_collage_painter_link,
    set_collage_scan_cleanup,
)
from app.motion_designer.craft_style import make_craft_style_effect  # noqa: E402
from app.motion_designer.export_renderer import MotionExportRenderer  # noqa: E402
from app.motion_designer.schema import (  # noqa: E402
    AnimatedProperty,
    Keyframe,
    MotionComposition,
    MotionLayer,
    SourceRef,
)


WIDTH = 640
HEIGHT = 360
DURATION_MS = 10_000
SAMPLE_TIMES = (800, 3300, 6200, 9000)


def _animated_position(
    layer: MotionLayer,
    start: tuple[float, float],
    end: tuple[float, float],
    delay_ms: int,
) -> None:
    layer.transform.position = AnimatedProperty(
        value_type="vector2",
        default=list(start),
        keyframes=[
            Keyframe(time_ms=delay_ms, value=list(start), interpolation="bezier"),
            Keyframe(time_ms=delay_ms + 850, value=list(end), interpolation="bezier"),
        ],
    )


def _shape(
    name: str,
    color: str,
    width: int,
    height: int,
    x: float,
    y: float,
) -> MotionLayer:
    layer = MotionLayer(
        name=name,
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "width": width,
                "height": height,
                "fill": color,
                "stroke": "#00000000",
                "stroke_width": 0,
            },
        ),
        out_ms=DURATION_MS,
    )
    layer.transform.position.default = [x, y]
    return layer


def _text(
    name: str,
    text: str,
    size: int,
    x: float,
    y: float,
    *,
    fill: str = "#ffffff",
    width: int = 520,
) -> MotionLayer:
    layer = MotionLayer(
        name=name,
        layer_type="text",
        source=SourceRef(
            kind="typography",
            params={
                "text": text,
                "font_family": "Arial",
                "font_size": size,
                "font_weight": 800,
                "fill": fill,
                "alignment": "center",
                "width": width,
                "height": max(70, size * 2),
            },
        ),
        out_ms=DURATION_MS,
    )
    layer.transform.position.default = [x, y]
    return layer


def _editorial() -> tuple[MotionComposition, str]:
    background = _shape("Ink Background", "#121318", WIDTH, HEIGHT, WIDTH / 2, HEIGHT / 2)
    red = _shape("Red Headline", "#dc3d2f", 290, 120, 205, 145)
    cream = _shape("Cream Article", "#eee4ce", 260, 150, 438, 220)
    title = _text("Headline", "BREAK THE FRAME", 38, 320, 150)
    composition = MotionComposition(
        name="Editorial Collage",
        width=WIDTH,
        height=HEIGHT,
        duration_ms=DURATION_MS,
        layers=[background, red, cream, title],
    )
    board = create_collage_board(
        composition,
        [red.id, cream.id, title.id],
        layout="editorial",
        seed=19,
    )
    for index, item in enumerate(board["items"]):
        set_collage_edge(
            composition,
            board["id"],
            item["id"],
            mode="torn" if index < 2 else "fiber",
            roughness=0.82,
            seed=19 + index,
        )
        set_collage_attachment(
            composition,
            board["id"],
            item["id"],
            kind=("tape", "staple", "pin")[index],
            angle=(-7.0, 9.0, 0.0)[index],
        )
    red.transform.position.default = [205, 145]
    cream.transform.position.default = [438, 220]
    title.transform.position.default = [320, 150]
    _animated_position(red, (-180, 145), tuple(red.transform.position.default), 200)
    _animated_position(cream, (820, 220), tuple(cream.transform.position.default), 620)
    _animated_position(title, (320, -100), tuple(title.transform.position.default), 1050)
    return composition, board["id"]


def _luxury() -> tuple[MotionComposition, str]:
    background = _shape("Charcoal", "#151411", WIDTH, HEIGHT, WIDTH / 2, HEIGHT / 2)
    card = _shape("Ivory Stock", "#e9dec5", 430, 245, WIDTH / 2, HEIGHT / 2)
    gold = _shape("Gold Rule", "#b68c3e", 350, 7, WIDTH / 2, 226)
    title = _text("Luxury Title", "ATELIER / 2026", 44, WIDTH / 2, 158, fill="#2b2924")
    composition = MotionComposition(
        name="Luxury Paper Title",
        width=WIDTH,
        height=HEIGHT,
        duration_ms=DURATION_MS,
        layers=[background, card, gold, title],
    )
    board = create_collage_board(
        composition,
        [card.id, gold.id, title.id],
        layout="luxury",
        seed=31,
    )
    item = board["items"][0]
    set_collage_edge(
        composition,
        board["id"],
        item["id"],
        mode="feather",
        roughness=0.2,
        feather=3.0,
        seed=31,
    )
    set_collage_attachment(
        composition,
        board["id"],
        item["id"],
        kind="fold",
        strength=0.22,
        angle=-18.0,
    )
    card.transform.position.default = [WIDTH / 2, HEIGHT / 2]
    gold.transform.position.default = [WIDTH / 2, 226]
    title.transform.position.default = [WIDTH / 2, 158]
    card.effects.append(make_craft_style_effect(preset="luxury_paper"))
    for index, layer in enumerate((card, gold, title)):
        layer.transform.opacity = AnimatedProperty(
            default=0.0,
            keyframes=[
                Keyframe(time_ms=300 + index * 350, value=0.0),
                Keyframe(time_ms=1200 + index * 350, value=1.0),
            ],
        )
    return composition, board["id"]


def _education(output_dir: Path) -> tuple[MotionComposition, str]:
    scan_path = output_dir / "generated_scan_note.png"
    scan = Image.new("RGBA", (340, 210), (224, 207, 169, 255))
    draw = ImageDraw.Draw(scan)
    draw.line((35, 58, 302, 58), fill=(38, 40, 42, 255), width=7)
    draw.line((35, 95, 272, 95), fill=(50, 51, 52, 255), width=5)
    draw.line((35, 132, 290, 132), fill=(45, 46, 47, 255), width=5)
    draw.ellipse((245, 145, 305, 195), outline=(180, 51, 42, 255), width=6)
    scan.save(scan_path)

    background = _shape("Classroom Blue", "#183952", WIDTH, HEIGHT, WIDTH / 2, HEIGHT / 2)
    note = MotionLayer(
        name="Scanned Notes",
        layer_type="image",
        source=SourceRef(
            kind="image",
            uri=str(scan_path),
            params={"width": 340, "height": 210, "fit": "cover"},
        ),
        out_ms=DURATION_MS,
    )
    note.transform.position.default = [245, 185]
    callout = _shape("Callout", "#f2b63d", 195, 92, 485, 135)
    title = _text("Lesson", "THREE STEPS", 26, 485, 135, fill="#162331", width=190)
    composition = MotionComposition(
        name="Education Cutaway",
        width=WIDTH,
        height=HEIGHT,
        duration_ms=DURATION_MS,
        layers=[background, note, callout, title],
    )
    board = create_collage_board(
        composition,
        [note.id, callout.id, title.id],
        layout="education",
        seed=47,
    )
    note_item = board["items"][0]
    set_collage_edge(
        composition,
        board["id"],
        note_item["id"],
        mode="fiber",
        roughness=0.68,
        seed=47,
    )
    set_collage_attachment(
        composition,
        board["id"],
        note_item["id"],
        kind="staple",
        angle=-11.0,
    )
    set_collage_scan_cleanup(
        composition,
        board["id"],
        note_item["id"],
        white_balance=0.72,
        paper_remove=0.12,
        ink_preserve=0.9,
    )
    note.transform.position.default = [245, 185]
    callout.transform.position.default = [485, 135]
    title.transform.position.default = [485, 135]
    _animated_position(note, (-220, 185), tuple(note.transform.position.default), 250)
    _animated_position(callout, (790, 135), tuple(callout.transform.position.default), 900)
    _animated_position(title, (790, 135), tuple(title.transform.position.default), 1150)
    return composition, board["id"]


def _contact_sheet(paths: list[Path], output: Path) -> None:
    frames = [Image.open(path).convert("RGB") for path in paths]
    columns = len(SAMPLE_TIMES)
    rows = max(1, len(frames) // columns)
    sheet = Image.new("RGB", (WIDTH * columns, HEIGHT * rows), "#0c0d11")
    for index, frame in enumerate(frames):
        sheet.paste(frame, ((index % columns) * WIDTH, (index // columns) * HEIGHT))
    sheet.save(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(ROOT / "debugCapture" / "motion_collage_qa"),
    )
    args = parser.parse_args()
    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    QApplication.instance() or QApplication([])
    renderer = MotionExportRenderer()
    scenes = [
        _editorial(),
        _luxury(),
        _education(output_dir),
    ]
    frame_paths: list[Path] = []
    report_rows: list[dict] = []
    for composition, board_id in scenes:
        preflight = preflight_collage(composition, board_id)
        if not preflight["ok"]:
            raise RuntimeError(preflight)
        board = next(
            row for row in composition.metadata["collage_boards"]
            if row["id"] == board_id
        )
        first_item = board["items"][0]
        source_layer = next(
            layer for layer in composition.layers
            if layer.id == first_item["layer_id"]
        )
        stable_before = {
            "item_id": first_item["id"],
            "layer_id": source_layer.id,
            "parent_id": source_layer.parent_id,
            "timing": [source_layer.in_ms, source_layer.out_ms],
            "anchor": list(source_layer.transform.anchor.default),
        }
        set_collage_painter_link(
            composition,
            board_id,
            first_item["id"],
            document_id=f"qa-{composition.id}",
            object_id=f"paint-{first_item['id']}",
        )
        replace_collage_item_source(
            composition,
            board_id,
            first_item["id"],
            source_layer.source.to_dict(),
        )
        stable_after = {
            "item_id": first_item["id"],
            "layer_id": source_layer.id,
            "parent_id": source_layer.parent_id,
            "timing": [source_layer.in_ms, source_layer.out_ms],
            "anchor": list(source_layer.transform.anchor.default),
        }
        if stable_before != stable_after:
            raise RuntimeError("collage stable identity changed during source refresh")
        timings: list[float] = []
        for time_ms in SAMPLE_TIMES:
            started = perf_counter()
            image = renderer.render_frame(composition, time_ms, use_cache=False)
            timings.append((perf_counter() - started) * 1000.0)
            path = output_dir / f"{composition.name.lower().replace(' ', '_')}_{time_ms:05d}.png"
            if not image.save(str(path), "PNG"):
                raise RuntimeError(f"failed to save {path}")
            frame_paths.append(path)
        report_rows.append({
            "composition": composition.name,
            "board_id": board_id,
            "duration_ms": composition.duration_ms,
            "sample_times_ms": list(SAMPLE_TIMES),
            "frame_times_ms": [round(value, 3) for value in timings],
            "stable_id_loss": 0,
            "preflight": preflight,
        })
    contact = output_dir / "contact_sheet.png"
    _contact_sheet(frame_paths, contact)
    report = {
        "schema": "tigerstudio.motion.collage.qa.v1",
        "ok": True,
        "scene_count": len(scenes),
        "frame_count": len(frame_paths),
        "contact_sheet": str(contact),
        "rows": report_rows,
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
