from __future__ import annotations

import numpy as np


def test_normalize_parallax_distinguishes_pom_from_single_offset() -> None:
    from app.ar_pbr.parallax import normalize_parallax_settings

    pom = normalize_parallax_settings(
        {
            "parallax_mode": "pom",
            "parallax_enabled": True,
            "parallax_strength": 0.6,
            "parallax_depth": 0.05,
            "parallax_steps": 32,
        }
    )
    simple = normalize_parallax_settings(
        {
            "parallax_mode": "parallax",
            "parallax_enabled": True,
            "parallax_strength": 0.6,
        }
    )

    assert pom["mode"] == "pom"
    assert pom["steps"] == 32
    assert pom["mapping_model"] == "height_map_parallax_occlusion_mapping"
    assert simple["mode"] == "parallax"
    assert simple["mapping_model"] == "height_map_tangent_space_uv_offset"


def test_parallax_occlusion_mapping_traces_height_texture() -> None:
    from app.ar_pbr.parallax import apply_parallax_occlusion_uv

    height = np.tile(np.linspace(0.0, 1.0, 32, dtype=np.float32), (32, 1))
    u = np.full((4, 4), 0.72, dtype=np.float32)
    v = np.full((4, 4), 0.50, dtype=np.float32)
    out_u, out_v = apply_parallax_occlusion_uv(
        u,
        v,
        height_texture=height,
        tangent_view=(
            np.full_like(u, 0.45),
            np.full_like(v, 0.12),
            np.full_like(u, 0.88),
        ),
        settings={
            "parallax_mode": "pom",
            "parallax_enabled": True,
            "parallax_strength": 0.8,
            "parallax_depth": 0.08,
            "parallax_steps": 32,
        },
    )

    assert np.all(np.isfinite(out_u))
    assert np.all(np.isfinite(out_v))
    assert float(np.max(np.abs(out_u - u))) > 0.001
    assert float(np.max(np.abs(out_v - v))) > 0.0001
    assert 0.0 <= float(out_u.min()) <= float(out_u.max()) <= 1.0
    assert 0.0 <= float(out_v.min()) <= float(out_v.max()) <= 1.0


def test_parallax_occlusion_mapping_off_is_noop() -> None:
    from app.ar_pbr.parallax import apply_parallax_occlusion_uv

    height = np.ones((8, 8), dtype=np.float32)
    u = np.asarray([[0.25, 0.75]], dtype=np.float32)
    v = np.asarray([[0.40, 0.60]], dtype=np.float32)
    out_u, out_v = apply_parallax_occlusion_uv(
        u,
        v,
        height_texture=height,
        tangent_view=(np.ones_like(u), np.ones_like(v), np.ones_like(u)),
        settings={"parallax_mode": "off"},
    )

    assert np.array_equal(out_u, u)
    assert np.array_equal(out_v, v)
