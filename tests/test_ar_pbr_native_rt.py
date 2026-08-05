from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


def _cube_descriptor() -> dict:
    vertices = [
        [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
        [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
    ]
    triangles = [
        [0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4], [2, 3, 7], [2, 7, 6],
        [1, 2, 6], [1, 6, 5], [3, 0, 4], [3, 4, 7],
    ]
    return {"geometries": [{"vertices": vertices, "triangles": triangles}]}


def test_native_rt_vertex_packet_layout() -> None:
    from app.ar_pbr.native_rt import pack_model_view_vertices

    source = np.zeros((3, 29), dtype=np.float32)
    source[:, 0:3] = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    source[:, 3:6] = [0, 1, 0]
    source[:, 6:9] = [0.2, 0.4, 0.8]
    source[:, 10] = 0.25
    source[:, 11] = 0.75
    packed = pack_model_view_vertices(source)

    assert packed.shape == (3, 11)
    assert packed.dtype == np.float32
    assert np.allclose(packed[:, 0:9], source[:, 0:9])
    assert np.allclose(packed[:, 9], 0.75)
    assert np.allclose(packed[:, 10], 0.25)


def test_native_dxr_source_uses_real_ray_queries_and_stays_out_of_painter() -> None:
    shader = Path("native/ar_pbr_dxr_helper/Raytrace.hlsl").read_text(encoding="utf-8")
    bridge = Path("app/ar_pbr/native_rt.py").read_text(encoding="utf-8")
    native = Path("native/ar_pbr_dxr_helper/TigerStudioDxrHelper.cpp").read_text(encoding="utf-8")

    assert "RayQuery<" in shader
    assert "RaytracingAccelerationStructure" in shader
    assert "D3D12_RAYTRACING_ACCELERATION_STRUCTURE_TYPE_BOTTOM_LEVEL" in native
    assert "D3D12_RAYTRACING_ACCELERATION_STRUCTURE_TYPE_TOP_LEVEL" in native
    assert "app.painter" not in bridge
    assert "app.drawing" not in bridge
    assert "shell=True" not in bridge


def test_native_dxr_helper_renders_real_gpu_frame_when_installed(tmp_path) -> None:
    from app.ar_pbr.native_rt import default_native_rt_helper_path, render_descriptor_native_rt

    helper = default_native_rt_helper_path()
    if not helper.is_file():
        pytest.skip("native DXR helper is an optional platform build artifact")
    output = tmp_path / "dxr_cube.png"
    hdri = Path("resources/ar_pbr/hdri/studio_small_09_1k.hdr")
    result = render_descriptor_native_rt(
        _cube_descriptor(),
        output_path=output,
        helper_path=helper,
        hdri_path=hdri if hdri.is_file() else None,
        camera_visible=False,
        reflection_visible=True,
        width=256,
        height=192,
        samples=1,
    )

    assert result["ok"] is True
    assert result["hardware_ray_tracing"] is True
    assert result["native"]["api"] == "dxr"
    assert result["native"]["raytracing_tier"] in {"1.0", "1.1"}
    assert result["triangle_count"] == 12
    if hdri.is_file():
        assert result["environment_size"] == [1024, 512]
    assert output.is_file() and output.stat().st_size > 100
