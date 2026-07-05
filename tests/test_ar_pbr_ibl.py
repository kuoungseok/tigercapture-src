import math
from pathlib import Path

import numpy as np


def _rgbe_pixel(rgb):
    r, g, b = [max(0.0, float(v)) for v in rgb]
    peak = max(r, g, b)
    if peak <= 1.0e-9:
        return bytes((0, 0, 0, 0))
    exponent = int(math.floor(math.log2(peak)) + 1)
    scale = 2.0 ** (8 - exponent)
    return bytes((
        max(0, min(255, int(round(r * scale)))),
        max(0, min(255, int(round(g * scale)))),
        max(0, min(255, int(round(b * scale)))),
        max(0, min(255, exponent + 128)),
    ))


def _write_test_hdr(path: Path, *, width: int = 8, height: int = 4) -> Path:
    rows = []
    for y in range(height):
        for x in range(width):
            u = x / max(1, width - 1)
            v = y / max(1, height - 1)
            rows.append(_rgbe_pixel((0.18 + u * 2.4, 0.25 + v * 1.2, 0.42 + (1.0 - u) * 0.8)))
    payload = b"".join(rows)
    path.write_bytes(
        b"#?RADIANCE\n"
        b"FORMAT=32-bit_rle_rgbe\n"
        b"\n"
        + f"-Y {height} +X {width}\n".encode("ascii")
        + payload
    )
    return path


def test_ibl_probe_builds_irradiance_prefilter_and_brdf_lut(tmp_path):
    from app.ar_pbr.ibl import IBL_SCHEMA, load_ibl_probe

    hdr = _write_test_hdr(tmp_path / "studio_test_1k.hdr")
    probe = load_ibl_probe(
        hdr,
        irradiance_size=(8, 4),
        irradiance_samples=12,
        max_prefilter_levels=4,
        brdf_lut_size=12,
        brdf_samples=12,
    )

    assert probe is not None
    assert probe.available is True
    assert probe.environment.shape == (4, 8, 3)
    assert probe.irradiance_map.shape == (4, 8, 3)
    assert len(probe.prefiltered_levels) >= 2
    assert probe.brdf_lut.shape == (12, 12, 2)
    assert probe.source_max_luminance > 0.0

    normal_sample = probe.sample_irradiance(np.array([[0.0]], dtype=np.float32), 1.0, 0.0)
    spec_sample = probe.sample_prefiltered(0.0, 0.0, 1.0, np.array([[0.65]], dtype=np.float32))
    brdf_sample = probe.sample_brdf(np.array([[0.7]], dtype=np.float32), np.array([[0.4]], dtype=np.float32))

    assert normal_sample.shape == (1, 1, 3)
    assert spec_sample.shape == (1, 1, 3)
    assert brdf_sample.shape == (1, 1, 2)
    assert float(brdf_sample[:, :, 0].mean()) > 0.0

    diag = probe.diagnostics()
    assert diag["schema"] == IBL_SCHEMA
    assert diag["prefilter_level_count"] == len(probe.prefiltered_levels)
    assert diag["brdf_lut_resolution"] == [12, 12]


def test_packet_export_uses_shared_ibl_probe_for_pbr(tmp_path):
    from PIL import Image

    from app.ar_pbr.export_packet_renderer import render_gpu_packet_export_frame

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "ibl_body.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "body.png"
    hdri = _write_test_hdr(tmp_path / "wide_street_01_1k.hdr")
    Image.new("RGBA", (8, 8), (220, 85, 35, 255)).save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "name": "BodyPaint",
                "base_color": [1.0, 0.35, 0.12, 1.0],
                "base_texture": str(texture),
                "roughness": 0.38,
                "metallic": 0.25,
                "reflectance": 0.55,
            }
        ],
    }

    _out, diag = render_gpu_packet_export_frame(
        base,
        time_ms=10,
        ar_tracks=[{
            "id": "ibl_body",
            "type": "ar_pbr_object",
            "asset_path": str(asset),
            "start_ms": 0,
            "end_ms": 1000,
            "shadow_catcher": False,
            "reflection_catcher": False,
            "render": {
                "lighting": {
                    "hdri_path": str(hdri),
                    "ibl_exposure": 1.0,
                    "ibl_rotation": 0.15,
                }
            },
        }],
        camera_solution={"id": "cam", "frame_size": [96, 96]},
        settings={"asset_descriptors": {str(asset): descriptor}, "camera_z": 3.0},
    )

    assert diag["mode"] == "gpu_packet_export"
    assert diag["pbr_sampled_triangle_count"] == 1
    assert diag["pbr_irradiance_ibl"] is True
    assert diag["pbr_prefiltered_ibl"] is True
    assert diag["pbr_brdf_lut"] is True
    assert diag["pbr_brdf_lut_sampled_pixels"] > 0
    assert diag["pbr_ibl_probe"]["schema"] == "tigerstudio.ar_pbr.ibl_probe.v1"


def test_live_gl_preview_shader_exposes_shared_ibl_probe_contract():
    import app.opengl_preview as preview

    shader = preview._AR_PBR_TEXTURE_FRAGMENT_SHADER

    assert "uniform sampler2D u_irradiance_tex" in shader
    assert "uniform sampler2D u_prefilter_tex" in shader
    assert "uniform sampler2D u_brdf_lut_tex" in shader
    assert "sample_irradiance(n)" in shader
    assert "sample_prefiltered_env(reflect_dir, roughness)" in shader
    assert "sample_brdf_lut(ndotv, roughness)" in shader


def test_live_gl_preview_encodes_prefilter_atlas_without_gl_context():
    import app.opengl_preview as preview

    levels = (
        np.ones((4, 8, 3), dtype=np.float32) * 0.25,
        np.ones((2, 4, 3), dtype=np.float32) * 0.75,
        np.ones((1, 2, 3), dtype=np.float32) * 1.25,
    )

    atlas, count = preview._ARPBRDirectGLPainter._prefilter_atlas_rgba(levels)
    lut = preview._ARPBRDirectGLPainter._encoded_lut_rgba(np.ones((4, 4, 2), dtype=np.float32) * 0.5)

    assert count == 3
    assert atlas.ndim == 3
    assert atlas.shape[2] == 4
    assert atlas.shape[0] == 4 * count
    assert int(atlas[:, :, 3].min()) == 255
    assert lut.shape == (4, 4, 4)
    assert int(lut[:, :, 0].mean()) in {127, 128}


def test_model_view_gpu_shader_exposes_shared_ibl_probe_contract():
    import tools.ar_pbr_gpu_window as gpu_window

    shader = gpu_window.FRAG_SHADER

    assert "uniform sampler2D u_irradiance" in shader
    assert "uniform sampler2D u_prefilter" in shader
    assert "uniform sampler2D u_brdf_lut" in shader
    assert "sample_irradiance(n)" in shader
    assert "sample_prefiltered_env(reflect_dir, roughness)" in shader
    assert "sample_brdf_lut(ndotv, roughness)" in shader
