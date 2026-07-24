from __future__ import annotations

import json

import numpy as np
from PIL import Image


def _sample_image(path) -> None:
    rgb = np.zeros((24, 32, 3), dtype=np.uint8)
    rgb[:, :, 0] = 120
    rgb[:, :, 1] = np.linspace(70, 220, 32, dtype=np.uint8)[None, :]
    rgb[:, :, 2] = 180
    Image.fromarray(rgb, mode="RGB").save(path)


def test_substrate_slab_math_uses_metallic_as_helper_input() -> None:
    from app.ar_pbr.pbr_math import (
        cook_torrance_substrate_slab_direct,
        fresnel_schlick_f90,
        substrate_f90,
        substrate_metalness_to_diffuse_albedo_f0,
    )

    albedo = np.asarray([[[0.8, 0.35, 0.12], [0.4, 0.5, 0.65]]], dtype=np.float32)
    metallic = np.asarray([[1.0, 0.0]], dtype=np.float32)

    diffuse_albedo, f0 = substrate_metalness_to_diffuse_albedo_f0(
        albedo=albedo,
        metallic=metallic,
        reflectance=0.5,
    )
    f90 = substrate_f90(f0=f0, f90_color=(0.9, 0.95, 1.0), f90_mask=1.0, strength=0.8)
    fresnel_edge = fresnel_schlick_f90(np.zeros_like(metallic), f0, f90)
    direct = cook_torrance_substrate_slab_direct(
        diffuse_albedo=diffuse_albedo,
        f0=f0,
        f90=f90,
        roughness=np.full_like(metallic, 0.42),
        ndotl=np.full_like(metallic, 0.75),
        ndotv=np.full_like(metallic, 0.85),
        ndoth=np.full_like(metallic, 0.82),
        vdoth=np.full_like(metallic, 0.78),
        light_strength=1.0,
        ao=np.ones_like(metallic),
    )

    assert np.allclose(diffuse_albedo[0, 0], [0.0, 0.0, 0.0])
    assert np.all(f0[0, 0] > f0[0, 1])
    assert np.all(fresnel_edge <= 1.0)
    assert direct.shape == albedo.shape
    assert float(np.max(direct)) > 0.0


def test_texture_lab_substrate_mode_exports_substrate_maps_by_default(tmp_path) -> None:
    from app.ar_pbr.texture_map_lab import export_texture_maps

    image_path = tmp_path / "source.png"
    out_dir = tmp_path / "maps"
    _sample_image(image_path)

    export_texture_maps(
        image_path,
        out_dir,
        {"substrate_enabled": True, "substrate_reflectance": 0.45},
        packed_layouts=(),
    )
    manifest = json.loads((out_dir / "source_pbr_manifest.json").read_text(encoding="utf-8"))

    assert (out_dir / "source_base_color.png").exists()
    assert not (out_dir / "source_metallic.png").exists()
    assert (out_dir / "source_f0.png").exists()
    assert (out_dir / "source_f90_mask.png").exists()
    assert manifest["substrate"]["enabled"] is True
    assert manifest["substrate"]["metallic_policy"] == "disabled_as_direct_substrate_input_helper_conversion_only"


def test_gpu_packet_export_renders_substrate_maps(tmp_path) -> None:
    from app.ar_pbr.export_packet_renderer import render_gpu_packet_export_frame

    base_frame = np.zeros((64, 64, 3), dtype=np.uint8)
    asset = tmp_path / "substrate.glb"
    asset.write_bytes(b"placeholder")
    base = tmp_path / "body_base.png"
    f0 = tmp_path / "body_f0.png"
    f90_mask = tmp_path / "body_f90_mask.png"
    Image.new("RGB", (4, 4), (190, 140, 80)).save(base)
    Image.new("RGB", (4, 4), (55, 62, 72)).save(f0)
    Image.new("L", (4, 4), 210).save(f90_mask)
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
                "name": "SubstrateBody",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "base_texture": str(base),
                "f0_texture": str(f0),
                "f90_mask_texture": str(f90_mask),
                "roughness": 0.36,
                "metallic": 0.8,
                "pbr_available": True,
            }
        ],
    }

    out, diag = render_gpu_packet_export_frame(
        base_frame,
        time_ms=10,
        ar_tracks=[
            {
                "id": "ar_pbr_substrate",
                "type": "ar_pbr_object",
                "asset_path": str(asset),
                "start_ms": 0,
                "end_ms": 1000,
                "occlusion": False,
                "shadow_catcher": False,
                "reflection_catcher": False,
                "render": {"lighting": {"direct_strength": 1.0, "ibl_exposure": 0.4}},
            }
        ],
        camera_solution={
            "id": "cam",
            "frame_size": [64, 64],
            "intrinsics": {"fx": 70, "fy": 70, "cx": 32, "cy": 32},
        },
        settings={"asset_descriptors": {str(asset): descriptor}, "camera_z": 3.0},
    )

    assert out.sum() > 0
    assert diag["mode"] == "gpu_packet_export"
    assert diag["pbr_substrate_rendering"]["enabled"] is True
    assert diag["pbr_substrate_applied"] is True
    assert diag["pbr_substrate_f0_map_applied"] is True
    assert diag["pbr_substrate_f90_mask_map_applied"] is True
    assert diag["pbr_substrate_pixels"] > 0
    assert diag["packet_builder"]["gpu_renderer"]["substrate_rendering"] == "slab"
