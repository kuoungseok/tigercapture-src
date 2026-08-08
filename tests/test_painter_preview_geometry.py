from __future__ import annotations

import pytest


def test_preview_dimensions_fail_instead_of_fabricating_one_pixel() -> None:
    from app.painter_preview_geometry import positive_preview_dimension

    assert positive_preview_dimension(512, field="width") == 512
    for invalid in (0, -1):
        with pytest.raises(ValueError, match="positive"):
            positive_preview_dimension(invalid, field="width")
    for invalid in (True, 1.0, "512", None):
        with pytest.raises(TypeError):
            positive_preview_dimension(invalid, field="width")


def test_preview_stroke_scaling_preserves_exact_positive_product() -> None:
    from app.painter_preview_geometry import scaled_preview_stroke_width

    assert scaled_preview_stroke_width(1.0, 0.1) == pytest.approx(0.1)
    assert scaled_preview_stroke_width(12.5, 0.5) == pytest.approx(6.25)
    for invalid in ((0, 1), (1, 0), (-1, 1)):
        with pytest.raises(ValueError, match="positive"):
            scaled_preview_stroke_width(*invalid)
    for invalid in ((True, 1), (1, "1"), (float("inf"), 1)):
        with pytest.raises((TypeError, ValueError)):
            scaled_preview_stroke_width(*invalid)


def test_preview_png_and_pil_paths_share_exact_subpixel_width(
    tmp_path, monkeypatch
) -> None:
    from app.drawing import (
        DrawingCanvas,
        Stroke,
        compose_pil_paint_overlays,
        render_strokes_to_png,
    )

    stroke = Stroke(points=[(0.1, 0.5), (0.9, 0.5)], width_px=1.0)
    assert DrawingCanvas._scaled_preview_stroke(stroke, 0.1).width_px == pytest.approx(
        0.1
    )

    widths: list[float] = []

    def capture_width(_painter, rendered_stroke, _width, _height, **_kwargs):
        widths.append(float(rendered_stroke.width_px))

    monkeypatch.setattr(DrawingCanvas, "_paint_stroke", staticmethod(capture_width))
    assert render_strokes_to_png(
        [stroke], 32, 16, str(tmp_path / "scaled.png"), width_scale=0.1
    )
    assert widths == [pytest.approx(0.1)]

    widths.clear()
    compose_pil_paint_overlays(
        strokes=[stroke],
        frame_size=(32, 16),
        stroke_width_scale=0.1,
    )
    assert widths == [pytest.approx(0.1)]

    with pytest.raises(ValueError, match="positive"):
        compose_pil_paint_overlays(
            strokes=[stroke],
            frame_size=(32, 16),
            stroke_width_scale=0.0,
        )
