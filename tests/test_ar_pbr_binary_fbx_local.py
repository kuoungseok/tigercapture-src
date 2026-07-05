from pathlib import Path

import pytest

from app.ar_pbr.importer import import_asset
from tools.ar_pbr_gpu_window import build_vertex_buffer


LOCAL_ES_FBX = Path("debugCapture/ar_pbr_external_assets/es_fbx/es.fbx")


@pytest.mark.skipif(not LOCAL_ES_FBX.exists(), reason="local es.fbx asset not present")
def test_local_binary_es_fbx_imports_preview_geometry():
    descriptor, diagnostics = import_asset(LOCAL_ES_FBX)

    assert diagnostics["imported"] is True
    assert diagnostics["backend"] == "internal_binary_fbx"
    assert descriptor["mesh_count"] >= 1
    assert descriptor["material_count"] >= 1
    assert descriptor["geometries"]
    assert descriptor["geometries"][0]["vertices"]
    assert descriptor["geometries"][0]["triangles"]


@pytest.mark.skipif(not LOCAL_ES_FBX.exists(), reason="local es.fbx asset not present")
def test_local_binary_es_fbx_builds_smooth_gpu_preview_buffer():
    descriptor, diagnostics = import_asset(
        LOCAL_ES_FBX,
        settings={"max_triangles_per_geometry": 200000},
    )

    vertices, mesh_diag = build_vertex_buffer(descriptor)

    assert diagnostics["backend"] == "internal_binary_fbx"
    assert len(vertices) > 1000
    assert vertices.shape[1] == 21
    assert mesh_diag["normal_mode"] == "fbx_layer_normals_or_smooth"
    assert mesh_diag["shading_model"] == "hdr_ibl_pbr_textured_normal_mapped_shadow_mapped"
    assert mesh_diag["vertex_stride_float_count"] == 21
    assert mesh_diag["draw_ranges"]
    assert mesh_diag["skipped_triangle_count"] >= 0


@pytest.mark.skipif(not LOCAL_ES_FBX.exists(), reason="local es.fbx asset not present")
def test_local_binary_es_fbx_imports_uvs_and_normals():
    descriptor, diagnostics = import_asset(
        LOCAL_ES_FBX,
        settings={"max_triangles_per_geometry": 5000},
    )

    geometry = descriptor["geometries"][0]

    assert diagnostics["backend"] == "internal_binary_fbx"
    assert geometry["uvs"]
    assert geometry["normals"]
    assert len(geometry["uvs"]) == len(geometry["vertices"])
    assert len(geometry["normals"]) == len(geometry["vertices"])
