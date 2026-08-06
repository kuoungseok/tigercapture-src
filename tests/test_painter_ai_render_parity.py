from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_action_curve_smoothing_expands_sparse_control_points() -> None:
    from app.painter_stroke_geometry import smooth_action_points

    controls = [
        {"x": 0.10, "y": 0.55},
        {"x": 0.32, "y": 0.18},
        {"x": 0.68, "y": 0.82},
        {"x": 0.90, "y": 0.45},
    ]
    smoothed = smooth_action_points(controls, samples_per_segment=8)

    assert len(smoothed) > len(controls)
    assert smoothed[0]["x"] == controls[0]["x"]
    assert smoothed[0]["y"] == controls[0]["y"]
    assert smoothed[-1]["x"] == controls[-1]["x"]
    assert smoothed[-1]["y"] == controls[-1]["y"]
    assert all(0.0 <= row["x"] <= 1.0 and 0.0 <= row["y"] <= 1.0 for row in smoothed)


def test_paint_action_smooth_mode_stores_dense_curve() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(320, 240, "#101923"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()
    registry = ActionRegistry(owner=dialog)
    result = registry.execute_action(
        "paint.stroke.draw",
        {
            "strokes": [
                {
                    "layer_id": "paint-layer-1",
                    "path_mode": "smooth",
                    "style": "impasto_oil",
                    "width": 18,
                    "color": "#F4D76B",
                    "points": [
                        {"x": 0.10, "y": 0.55},
                        {"x": 0.32, "y": 0.18},
                        {"x": 0.68, "y": 0.82},
                        {"x": 0.90, "y": 0.45},
                    ],
                }
            ]
        },
    ).to_dict()

    assert result["ok"]
    stored = dialog.result_strokes()
    assert len(stored) == 1
    assert len(stored[0].points) > 4
    dialog.close()


def test_png_overlay_uses_canvas_bristle_renderer_for_material_oil() -> None:
    _app()
    from app.drawing import Stroke, compose_pil_paint_overlays

    image = compose_pil_paint_overlays(
        strokes=[
            Stroke(
                points=[(0.15, 0.50), (0.50, 0.50), (0.85, 0.50)],
                color=(244, 215, 107),
                opacity=255,
                width_px=30,
                brush_style="impasto_oil",
                brush_engine_version=2,
                bristle_count=18,
                material_enabled=True,
                point_pressure=[0.9, 1.0, 0.9],
                point_load=[1.0, 0.9, 0.8],
            )
        ],
        frame_size=(320, 180),
    )

    red, green, blue, alpha = image.getpixel((160, 90))
    assert red > 200
    assert green > 170
    assert blue > 70
    assert alpha > 230


def test_legacy_frame_burn_in_uses_exact_canonical_pressure_load_renderer() -> None:
    _app()
    from PIL import Image
    from app.drawing import (
        Stroke,
        compose_pil_frame_with_overlays,
        compose_pil_paint_overlays,
    )

    stroke = Stroke(
        points=[(0.15, 0.50), (0.50, 0.50), (0.85, 0.50)],
        color=(244, 215, 107),
        opacity=255,
        width_px=30,
        brush_style="impasto_oil",
        brush_engine_version=2,
        bristle_count=18,
        material_enabled=True,
        point_pressure=[0.2, 1.0, 0.4],
        point_load=[1.0, 0.5, 0.1],
    )
    frame = Image.new("RGBA", (320, 180), (0, 0, 0, 0))
    canonical = compose_pil_paint_overlays(
        strokes=[stroke],
        time_ms=0,
        frame_size=frame.size,
    )
    burned = compose_pil_frame_with_overlays(frame, [stroke], [], 0)

    assert burned.tobytes() == canonical.tobytes()

    changed = Stroke(**{
        **stroke.__dict__,
        "point_pressure": [1.0, 1.0, 1.0],
        "point_load": [0.0, 0.0, 0.0],
    })
    changed_burned = compose_pil_frame_with_overlays(frame, [changed], [], 0)
    assert changed_burned.tobytes() != burned.tobytes()


def test_gif_composed_frames_preserves_canonical_scale_time_and_source_stroke() -> None:
    _app()
    from types import SimpleNamespace

    from PIL import Image

    from app.drawing import Stroke, compose_pil_paint_overlays
    from app.gif_editor_window import GifEditorWindow

    stroke = Stroke(
        points=[(0.20, 0.50), (0.80, 0.50)],
        color=(80, 160, 240),
        opacity=255,
        width_px=12,
        brush_style="impasto_oil",
        brush_engine_version=2,
        bristle_count=10,
        material_enabled=True,
        point_pressure=[0.4, 0.9],
        point_load=[1.0, 0.2],
        start_ms=100,
        end_ms=200,
    )
    frames = [
        Image.new("RGBA", (256, 1440), (0, 0, 0, 0)),
        Image.new("RGBA", (256, 1440), (0, 0, 0, 0)),
    ]
    holder = SimpleNamespace(
        _frames=frames,
        _strokes=[stroke],
        _bubbles=[],
        _stickers=[],
        _subtitle_panel=SimpleNamespace(subtitles=lambda: []),
        _get_fps=lambda: 10,
    )

    composed = GifEditorWindow._composed_frames(holder)
    canonical_at_100 = compose_pil_paint_overlays(
        strokes=[stroke],
        time_ms=100,
        frame_size=frames[1].size,
        stroke_width_scale=2.0,
    )

    assert composed[0].getbbox() is None
    assert composed[1].tobytes() == canonical_at_100.tobytes()
    assert stroke.width_px == 12
