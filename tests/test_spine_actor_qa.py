from __future__ import annotations

import json
from types import SimpleNamespace


def test_spine_dependency_rows_strip_atlas_bom(tmp_path):
    from tools.qa_project_audit import _spine_dependency_rows

    atlas = tmp_path / "hero.atlas"
    texture = tmp_path / "hero.png"
    texture.write_bytes(b"png")
    atlas.write_text(
        "\ufeffhero.png\nsize: 64,64\nformat: RGBA8888\nfilter: Linear,Linear\n",
        encoding="utf-8",
    )

    rows = _spine_dependency_rows({"atlas_path": str(atlas)})

    assert rows == [{
        "kind": "spine_atlas_texture",
        "path": str(texture.resolve()),
        "exists": True,
    }]


def test_spine_actor_clip_falls_back_from_empty_default_skin():
    from app.spine_editor.actor_track import SpineActorClip

    class _Renderer:
        skeleton = SimpleNamespace(skins={
            "default": {},
            "small": {},
            "large": {},
        })

        def visual_bounds(self, skin_name):
            return {
                "default": None,
                "small": (0.0, 0.0, 10.0, 10.0),
                "large": (-20.0, -30.0, 120.0, 150.0),
            }.get(skin_name)

    clip = SpineActorClip(skin_name="default")

    assert clip._resolved_skin_name(_Renderer()) == "large"


def test_spine_screen_layout_centers_bounds_with_shared_margin():
    from app.spine_editor.layout import (
        SPINE_PREVIEW_FIT_MARGIN,
        compute_spine_screen_layout,
    )

    scale, offset_x, offset_y = compute_spine_screen_layout(
        (0.0, 0.0, 100.0, 100.0),
        1000,
        500,
        0.5,
        0.5,
        1.0,
    )

    expected_scale = 500 * SPINE_PREVIEW_FIT_MARGIN / 100
    assert round(scale, 4) == round(expected_scale, 4)
    assert round(1000 / 2 + offset_x + 50 * scale, 4) == 500.0
    assert round(500 / 2 - offset_y - 50 * scale, 4) == 250.0


def test_spine_editor_work_view_keeps_frame_fixed_while_actor_scales():
    from app.spine_editor.layout import compute_spine_editor_view_transform

    bounds = (-120.0, -40.0, 520.0, 620.0)
    work_zoom, _work_x, _work_y, frame_rect = compute_spine_editor_view_transform(
        bounds,
        640,
        360,
        0.82,
        0.45,
        2.8,
        mode="work",
        frame_aspect_ratio=16 / 9,
    )
    larger_zoom, _larger_x, _larger_y, larger_frame_rect = compute_spine_editor_view_transform(
        bounds,
        640,
        360,
        0.82,
        0.45,
        4.2,
        mode="work",
        frame_aspect_ratio=16 / 9,
    )

    assert round(larger_zoom / work_zoom, 4) == round(4.2 / 2.8, 4)
    assert frame_rect == larger_frame_rect
    assert 0.0 <= frame_rect[0] <= 640.0
    assert 0.0 <= frame_rect[1] <= 360.0
    assert frame_rect[0] + frame_rect[2] <= 640.0
    assert frame_rect[1] + frame_rect[3] <= 360.0
    assert round(frame_rect[2] / frame_rect[3], 4) == round(16 / 9, 4)


def test_spine_editor_final_view_converts_renderer_offsets_to_widget_origin():
    from app.spine_editor.layout import compute_spine_editor_view_transform

    bounds = (0.0, 0.0, 100.0, 100.0)
    zoom, origin_x, origin_y, frame_rect = compute_spine_editor_view_transform(
        bounds,
        1000,
        500,
        0.5,
        0.5,
        1.0,
        mode="final",
    )

    actor_center_x = origin_x + 50.0 * zoom
    actor_center_y = origin_y - 50.0 * zoom
    assert round(actor_center_x, 4) == 500.0
    assert round(actor_center_y, 4) == 250.0
    assert frame_rect == (0.0, 0.0, 1000.0, 500.0)


def test_spine_editor_frame_uses_requested_project_aspect_ratio():
    from app.spine_editor.layout import compute_spine_editor_view_transform

    bounds = (-160.0, -120.0, 460.0, 680.0)
    _work_zoom, _work_x, _work_y, frame_rect = compute_spine_editor_view_transform(
        bounds,
        960,
        540,
        0.50,
        0.50,
        4.2,
        mode="work",
        frame_aspect_ratio=9 / 16,
    )

    assert round(frame_rect[2] / frame_rect[3], 4) == round(9 / 16, 4)
    assert frame_rect[2] < frame_rect[3]


def test_spine_editor_resolves_project_canvas_aspect_ratio():
    from app.spine_editor.editor_window import _editor_output_aspect_ratio

    owner = SimpleNamespace(
        _project_settings={"canvas_width": 1080, "canvas_height": 1920},
        _export_resolution=(1920, 1080),
    )

    assert _editor_output_aspect_ratio(owner) == 1080 / 1920
    assert _editor_output_aspect_ratio(None) == 16 / 9


def test_spine_renderer_clips_large_offscreen_triangle_instead_of_dropping_it():
    from PIL import Image

    from app.spine_editor.spine_renderer import SpineRenderer

    canvas = Image.new("RGBA", (80, 60), (0, 0, 0, 0))
    src = Image.new("RGBA", (8, 8), (255, 80, 40, 255))

    SpineRenderer._render_triangle(
        canvas,
        src,
        [(0, 0), (8, 0), (0, 8)],
        [(-1000, -1000), (1000, -1000), (-1000, 1000)],
    )

    assert canvas.getbbox() is not None


def test_spine_renderer_composites_bbox_when_scaled_past_canvas_edges():
    from PIL import Image

    from app.spine_editor.spine_renderer import SpineRenderer

    canvas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    src = Image.new("RGBA", (16, 16), (120, 220, 255, 255))

    ok = SpineRenderer._composite_resized_bbox(
        canvas,
        src,
        -48,
        -32,
        140,
        120,
        Image.Resampling.BILINEAR,
    )

    assert ok is True
    assert canvas.getbbox() is not None


def test_spine_render_qa_candidates_prefer_same_stem_json(tmp_path):
    from tools.test_spine_resources import _candidates

    skel = tmp_path / "hero.skel"
    spine_json = tmp_path / "hero.json"
    skel.write_bytes(b"Spine 4.2 binary sample")
    spine_json.write_text(
        json.dumps({"skeleton": {"spine": "4.2"}, "bones": [], "slots": []}),
        encoding="utf-8",
    )

    assert _candidates(tmp_path) == [spine_json]
    assert _candidates(skel) == [spine_json]
