from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from app.drawing_editor_object_import import (
    PaintImportObject,
    collect_editor_paint_objects,
    render_paint_import_object,
)
from app.typography import TextClip, TextStyle


def test_collect_editor_paint_objects_includes_typography_and_ar_pbr() -> None:
    typo = TextClip(
        start_ms=100,
        end_ms=2100,
        text="Tokyo night title",
        style=TextStyle(position_x=0.35, position_y=0.22, font_size=64, color="#FFE7A3"),
    )
    video_track = SimpleNamespace(
        id=7,
        offset_ms=1000,
        duration_ms=5000,
        source_path="scene.mp4",
        clips=[],
        typography_actors=[typo],
    )
    ar_track = {
        "id": "ar_pbr_001",
        "asset_path": "external/assets/models/motorcycle.glb",
        "start_ms": 900,
        "end_ms": 3200,
        "placement": {"image_point": [0.62, 0.70]},
        "transform": {"scale": [2.0, 2.0, 2.0]},
    }
    owner = SimpleNamespace(
        _tracks=[video_track],
        _ar_pbr_tracks=[ar_track],
        _mmd_tracks=[],
        _spine_actor_tracks=[],
        _live2d_actor_tracks=[],
    )

    rows = collect_editor_paint_objects(owner, time_ms=1200)

    assert [row.kind for row in rows] == ["ar_pbr_actor", "typography_actor"]
    assert all(row.active for row in rows)
    typography = next(row for row in rows if row.kind == "typography_actor")
    assert typography.payload["text"] == "Tokyo night title"
    assert typography.start_ms == 1100
    assert typography.end_ms == 3100


def test_render_typography_import_object_creates_transparent_png(tmp_path: Path) -> None:
    obj = PaintImportObject(
        id="typography_1",
        kind="typography_actor",
        label="Hello Paint",
        x_norm=0.2,
        y_norm=0.3,
        width_norm=0.5,
        height_norm=0.12,
        payload={
            "text": "Hello Paint",
            "style": {
                "font_size": 48,
                "font_family": "Arial",
                "color": "#FFFFFF",
                "background_color": "#0F172A",
                "background_radius": 16,
            },
        },
    )

    report = render_paint_import_object(obj, canvas_size=(1280, 720), output_dir=tmp_path)

    png = Path(report["png_path"])
    assert png.is_file()
    assert report["rect_norm"]["w"] == 0.5
    image = Image.open(png)
    assert image.mode == "RGBA"
    assert image.size[0] >= 240
    assert image.getbbox() is not None
