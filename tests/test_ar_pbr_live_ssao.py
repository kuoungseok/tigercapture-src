from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read_repo_file(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_editor_preview_pbr_shader_consumes_screen_ao_uniforms() -> None:
    source = _read_repo_file("app/opengl_preview.py")

    assert "uniform float u_screen_ao_strength;" in source
    assert "float screen_space_ao_factor(vec3 normal, vec3 view_dir, vec3 world_pos)" in source
    assert "float ambient_ao = ao * (u_screen_ao_ambient == 1 ? screen_ao : 1.0);" in source
    assert "normalize_packet_ambient_occlusion_settings(item, lighting)" in source
    assert '_set_pbr_uniform1f_gl(gl, "u_screen_ao_strength", ao_strength)' in source
    assert '_set_pbr_uniform1i_gl(gl, "u_screen_ao_diffuse", ao_diffuse)' in source


def test_standalone_ar_pbr_viewer_shader_consumes_screen_ao_uniforms() -> None:
    source = _read_repo_file("tools/ar_pbr_gpu_window.py")

    assert "uniform float u_screen_ao_strength;" in source
    assert "float screen_space_ao_factor(vec3 normal, vec3 view_dir, vec3 world_pos)" in source
    assert "float ambient_ao = ao * (u_screen_ao_ambient == 1 ? screen_ao : 1.0);" in source
    assert 'ambient_occlusion = ambient_occlusion_diagnostics(self.state)' in source
    assert 'GL.glUniform1f(GL.glGetUniformLocation(self.program, "u_screen_ao_strength"), ao_strength)' in source
    assert 'GL.glUniform1i(GL.glGetUniformLocation(self.program, "u_screen_ao_diffuse")' in source


def test_packet_ambient_occlusion_lookup_matches_live_and_export_payloads() -> None:
    from app.ar_pbr.ambient_occlusion import normalize_packet_ambient_occlusion_settings

    item_level = normalize_packet_ambient_occlusion_settings(
        {
            "ambient_occlusion_rendering": {
                "enabled": True,
                "mode": "screen",
                "strength": 0.72,
                "radius": 6.0,
                "distance": 0.8,
                "diffuse": True,
                "specular": True,
            },
            "pbr_lighting": {
                "ao_strength": 0.0,
                "ambient_occlusion_mode": "off",
            },
        }
    )
    flat_lighting = normalize_packet_ambient_occlusion_settings(
        {
            "pbr_lighting": {
                "ambient_occlusion_mode": "screen",
                "ao_strength": 0.44,
                "ao_radius": 5.0,
                "ao_distance": 0.6,
                "ao_specular": True,
            }
        }
    )

    assert item_level["enabled"] is True
    assert item_level["strength"] == 0.72
    assert item_level["radius"] == 6.0
    assert item_level["specular"] is True
    assert flat_lighting["enabled"] is True
    assert flat_lighting["strength"] == 0.44
    assert flat_lighting["radius"] == 5.0
    assert flat_lighting["specular"] is True


def test_gpu_preview_packet_ssao_bakes_into_export_rasterizer(tmp_path) -> None:
    import numpy as np
    from PIL import Image

    from app.ar_pbr.export_packet_renderer import rasterize_gpu_preview_items
    from app.ar_pbr.gpu_preview import build_gpu_preview_items

    asset = tmp_path / "ao_model.glb"
    asset.write_bytes(b"glTF")
    texture = tmp_path / "ao_base.png"
    Image.new("RGB", (4, 4), (218, 122, 56)).save(texture)
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
                "name": "AoPaint",
                "base_color": [0.85, 0.48, 0.22, 1.0],
                "base_texture": str(texture),
                "roughness": 0.42,
                "metallic": 0.0,
                "reflectance": 0.45,
            }
        ],
    }
    track = {
        "id": "ao_track",
        "type": "ar_pbr_object",
        "asset_path": str(asset),
        "start_ms": 0,
        "end_ms": 1000,
        "render": {
            "render_profile": "marmoset_pbr",
            "lighting": {
                "ao_strength": 1.15,
                "ao_radius": 6.0,
                "ao_distance": 0.55,
                "ao_specular": True,
                "ibl_exposure": 1.0,
                "direct_strength": 0.8,
            },
        },
    }

    items, packet_diag = build_gpu_preview_items(
        frame_size=(96, 96),
        time_ms=100,
        ar_tracks=[track],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        settings={
            "asset_descriptors": {str(asset): descriptor},
            "camera_z": 3.0,
        },
    )
    assert packet_diag["pbr_triangle_count"] == 1
    assert items[0]["ambient_occlusion_rendering"]["strength"] == 1.15
    assert items[0]["pbr_lighting"]["ao_strength"] == 1.15

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    ao_out, ao_diag = rasterize_gpu_preview_items(base, items, settings={"camera_z": 3.0})

    no_ao_items = [dict(items[0])]
    no_ao_items[0]["ambient_occlusion_rendering"] = {
        **dict(items[0]["ambient_occlusion_rendering"]),
        "enabled": False,
        "mode": "off",
        "strength": 0.0,
    }
    no_ao_items[0]["pbr_lighting"] = {
        **dict(items[0]["pbr_lighting"]),
        "ambient_occlusion_mode": "off",
        "ambient_occlusion_enabled": False,
        "ao_strength": 0.0,
    }
    no_ao_out, no_ao_diag = rasterize_gpu_preview_items(base, no_ao_items, settings={"camera_z": 3.0})

    assert ao_diag["pbr_sampled_triangle_count"] == 1
    assert ao_diag["pbr_ambient_occlusion_rendering"]["strength"] == 1.15
    assert ao_diag["pbr_ambient_occlusion_applied"] is True
    assert ao_diag["pbr_ambient_occlusion_changed_pixels"] > 0
    assert no_ao_diag["pbr_ambient_occlusion_applied"] is False
    assert np.any(np.asarray(ao_out) != np.asarray(no_ao_out))


def test_video_exporter_bakes_ar_pbr_ssao_into_export_frame(tmp_path, monkeypatch) -> None:
    import numpy as np
    from PIL import Image

    from app.video_exporter import VideoExportThread

    monkeypatch.setenv("TIGERCAPTURE_AR_PBR_EXPORT_RENDERER", "packet")
    asset = tmp_path / "export_ao_model.glb"
    source = tmp_path / "source.mp4"
    out_path = tmp_path / "out.mp4"
    texture = tmp_path / "export_ao_base.png"
    asset.write_bytes(b"glTF")
    source.write_bytes(b"placeholder")
    Image.new("RGB", (4, 4), (210, 118, 72)).save(texture)
    descriptor = {
        "source_path": str(asset),
        "source_ext": ".glb",
        "import_state": "ready",
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
                "name": "ExportAoPaint",
                "base_color": [0.82, 0.46, 0.28, 1.0],
                "base_texture": str(texture),
                "roughness": 0.4,
                "metallic": 0.0,
                "reflectance": 0.45,
            }
        ],
    }
    track = {
        "id": "export_ao_track",
        "type": "ar_pbr_object",
        "asset_path": str(asset),
        "start_ms": 0,
        "end_ms": 1000,
        "occlusion": False,
        "render": {
            "render_profile": "marmoset_pbr",
            "lighting": {
                "ao_strength": 1.1,
                "ao_radius": 5.0,
                "ao_distance": 0.55,
                "ao_specular": True,
                "direct_strength": 0.8,
                "ibl_exposure": 1.0,
            },
        },
    }
    exporter = VideoExportThread(
        source_path=source,
        out_path=out_path,
        segments=[(0, 1000, 1.0)],
        ar_pbr_tracks=[track],
        ar_pbr_asset_descriptors={str(asset): descriptor},
    )
    base = np.zeros((96, 96, 3), dtype=np.uint8)

    baked = exporter._apply_ar_pbr_export_cpu(base, 100)
    diagnostics = exporter._ar_pbr_last_export_diagnostics

    assert diagnostics["mode"] == "gpu_packet_export"
    assert diagnostics["rendered_track_count"] == 1
    assert diagnostics["pbr_ambient_occlusion_rendering"]["strength"] == 1.1
    assert diagnostics["pbr_ambient_occlusion_applied"] is True
    assert diagnostics["pbr_ambient_occlusion_changed_pixels"] > 0
    assert np.any(np.asarray(baked) != base)
