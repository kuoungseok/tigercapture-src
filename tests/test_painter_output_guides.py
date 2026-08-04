from __future__ import annotations

import pytest


def test_output_guides_match_trim_bleed_and_safe_millimetres() -> None:
    from app.painter_output_guides import output_guide_geometry

    geometry = output_guide_geometry(
        {
            "mode": "print",
            "width_mm": 210,
            "height_mm": 297,
            "bleed_mm": 3,
            "safe_margin_mm": 5,
        },
        pixel_width=2551,
        pixel_height=3579,
    )
    assert geometry is not None
    trim_x, trim_y, trim_w, trim_h = geometry["trim_rect"]
    safe_x, safe_y, safe_w, safe_h = geometry["safe_rect"]

    assert trim_x == pytest.approx(2551 * 3 / 216)
    assert trim_y == pytest.approx(3579 * 3 / 303)
    assert trim_w == pytest.approx(2551 - trim_x * 2)
    assert trim_h == pytest.approx(3579 - trim_y * 2)
    assert safe_x - trim_x == pytest.approx(2551 * 5 / 216)
    assert safe_y - trim_y == pytest.approx(3579 * 5 / 303)
    assert safe_w == pytest.approx(trim_w - (safe_x - trim_x) * 2)
    assert safe_h == pytest.approx(trim_h - (safe_y - trim_y) * 2)


def test_output_guides_never_invert_for_oversized_safe_margin() -> None:
    from app.painter_output_guides import output_guide_geometry

    geometry = output_guide_geometry(
        {
            "mode": "print",
            "width_mm": 10,
            "height_mm": 8,
            "bleed_mm": 3,
            "safe_margin_mm": 100,
        },
        pixel_width=160,
        pixel_height=140,
    )
    assert geometry is not None
    trim = geometry["trim_rect"]
    safe = geometry["safe_rect"]

    assert trim[2] > 0.0 and trim[3] > 0.0
    assert safe[2] == 0.0 and safe[3] == 0.0
    assert safe[0] == pytest.approx(trim[0] + trim[2] / 2.0)
    assert safe[1] == pytest.approx(trim[1] + trim[3] / 2.0)


def test_trim_only_output_ignores_configured_bleed_for_guides_and_fallback_size() -> None:
    from app.painter_output import effective_ppi, normalize_output_settings
    from app.painter_output_guides import output_guide_geometry

    settings = {
        "mode": "print",
        "ppi": 300,
        "bleed_mm": 3,
        "include_bleed": False,
        "safe_margin_mm": 5,
    }
    normalized = normalize_output_settings(
        settings,
        pixel_width=2480,
        pixel_height=3508,
    )
    geometry = output_guide_geometry(
        normalized,
        pixel_width=2480,
        pixel_height=3508,
    )
    assert geometry is not None
    assert normalized["width_mm"] == pytest.approx(209.9733, abs=0.0001)
    assert normalized["height_mm"] == pytest.approx(297.0107, abs=0.0001)
    assert geometry["trim_rect"] == (0.0, 0.0, 2480.0, 3508.0)
    safe = geometry["safe_rect"]
    assert safe[0] == pytest.approx(2480 * 5 / normalized["width_mm"])
    assert safe[1] == pytest.approx(3508 * 5 / normalized["height_mm"])
    x_ppi, y_ppi = effective_ppi(normalized, 2480, 3508)
    assert x_ppi == pytest.approx(300.0, abs=0.01)
    assert y_ppi == pytest.approx(300.0, abs=0.01)


def test_screen_output_has_no_print_guides() -> None:
    from app.painter_output_guides import output_guide_geometry

    assert output_guide_geometry(
        {"mode": "screen", "bleed_mm": 3, "safe_margin_mm": 5},
        pixel_width=1920,
        pixel_height=1080,
    ) is None
