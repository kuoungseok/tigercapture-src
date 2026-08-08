import pytest

from app.ar_pbr.importer import import_asset
from app.ar_pbr.sample_assets import default_ar_pbr_binary_fbx_asset
from tools.ar_pbr_gpu_window import GPU_VERTEX_STRIDE_FLOAT_COUNT, build_vertex_buffer


DURABLE_BINARY_FBX = default_ar_pbr_binary_fbx_asset()


@pytest.mark.skipif(not DURABLE_BINARY_FBX.exists(), reason="durable AR/PBR binary FBX sample not present")
def test_durable_binary_fbx_imports_preview_geometry():
    descriptor, diagnostics = import_asset(DURABLE_BINARY_FBX)

    assert diagnostics["imported"] is True
    assert diagnostics["backend"] == "internal_binary_fbx"
    assert descriptor["mesh_count"] >= 1
    assert descriptor["material_count"] >= 1
    assert descriptor["geometries"]
    assert descriptor["geometries"][0]["vertices"]
    assert descriptor["geometries"][0]["triangles"]


@pytest.mark.skipif(not DURABLE_BINARY_FBX.exists(), reason="durable AR/PBR binary FBX sample not present")
def test_durable_binary_fbx_builds_smooth_gpu_preview_buffer():
    descriptor, diagnostics = import_asset(
        DURABLE_BINARY_FBX,
        settings={"max_triangles_per_geometry": 200000},
    )

    vertices, mesh_diag = build_vertex_buffer(descriptor)

    assert diagnostics["backend"] == "internal_binary_fbx"
    assert len(vertices) > 1000
    assert vertices.shape[1] == GPU_VERTEX_STRIDE_FLOAT_COUNT
    assert mesh_diag["normal_mode"] == "fbx_layer_normals_or_smooth"
    assert mesh_diag["shading_model"] == "hdr_ibl_pbr_textured_normal_mapped_shadow_mapped"
    assert mesh_diag["vertex_stride_float_count"] == GPU_VERTEX_STRIDE_FLOAT_COUNT
    assert mesh_diag["draw_ranges"]
    assert mesh_diag["skipped_triangle_count"] >= 0


@pytest.mark.skipif(not DURABLE_BINARY_FBX.exists(), reason="durable AR/PBR binary FBX sample not present")
def test_durable_binary_fbx_imports_uvs_and_normals():
    descriptor, diagnostics = import_asset(
        DURABLE_BINARY_FBX,
        settings={"max_triangles_per_geometry": 5000},
    )

    geometry = descriptor["geometries"][0]

    assert diagnostics["backend"] == "internal_binary_fbx"
    assert geometry["uvs"]
    assert geometry["normals"]
    assert len(geometry["uvs"]) == len(geometry["vertices"])
    assert len(geometry["normals"]) == len(geometry["vertices"])
