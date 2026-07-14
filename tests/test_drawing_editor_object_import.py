from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from app.actions import build_default_action_registry
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


def test_paint_editor_object_actions_list_render_and_import(tmp_path: Path) -> None:
    typo = TextClip(
        start_ms=0,
        end_ms=2000,
        text="Action title",
        style=TextStyle(position_x=0.5, position_y=0.4, font_size=52),
    )
    owner = SimpleNamespace(
        _tracks=[
            SimpleNamespace(
                id=1,
                offset_ms=0,
                duration_ms=4000,
                source_path="scene.mp4",
                clips=[],
                typography_actors=[typo],
            )
        ],
        _ar_pbr_tracks=[],
        _mmd_tracks=[],
        _spine_actor_tracks=[],
        _live2d_actor_tracks=[],
        _stickers=[],
        _preview_pixmap=None,
        _register_change=lambda _label: None,
    )
    registry = build_default_action_registry(owner)
    action_ids = {row["id"] for row in registry.list_actions()}
    assert "paint.editor_objects.list" in action_ids
    assert "paint.editor_object.render" in action_ids
    assert "paint.editor_object.import" in action_ids

    listed = registry.execute_action("paint.editor_objects.list", {"time_ms": 250}).to_dict()
    assert listed["ok"]
    object_id = listed["result"]["objects"][0]["id"]

    rendered = registry.execute_action(
        "paint.editor_object.render",
        {"object_id": object_id, "time_ms": 250, "output_dir": str(tmp_path)},
    ).to_dict()
    assert rendered["ok"]
    assert Path(rendered["result"]["render"]["png_path"]).is_file()

    imported = registry.execute_action(
        "paint.editor_object.import",
        {"object_id": object_id, "time_ms": 250, "output_dir": str(tmp_path)},
    ).to_dict()
    assert imported["ok"]
    assert len(owner._stickers) == 1
    assert Path(owner._stickers[0].png_path).is_file()
