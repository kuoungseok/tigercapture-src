import numpy as np

from app.ar_pbr.compositor import composite_preview_frame
from app.ar_pbr.importer import import_asset
from app.ar_pbr.sample_scene import write_pbr_fbx_scene


def test_generated_pbr_fbx_scene_imports_multiple_materials(tmp_path):
    fbx_path = write_pbr_fbx_scene(tmp_path / "pbr_scene.fbx")

    descriptor, diag = import_asset(fbx_path)

    assert diag["imported"] is True
    assert descriptor["mesh_count"] == 3
    assert descriptor["material_count"] == 3
    assert descriptor["geometries"][0]["triangle_count"] == 2
    assert descriptor["geometries"][1]["triangle_count"] == 2
    assert descriptor["geometries"][2]["triangle_count"] == 6
    assert descriptor["materials"][1]["metallic"] == 1.0
    assert descriptor["materials"][1]["roughness"] == 0.22


def test_generated_pbr_fbx_scene_renders_nonblank(tmp_path):
    fbx_path = write_pbr_fbx_scene(tmp_path / "pbr_scene.fbx")
    descriptor, _ = import_asset(fbx_path)
    base = np.zeros((180, 260, 3), dtype=np.uint8)
    depth = np.ones((180, 260), dtype=np.float32)

    out, diag = composite_preview_frame(
        base,
        time_ms=0,
        ar_tracks=[
            {
                "id": "scene_smoke",
                "asset_path": str(fbx_path),
                "start_ms": 0,
                "end_ms": 1000,
                "transform": {
                    "position": [0.0, -0.05, 0.0],
                    "rotation": [-18.0, 0.0, 0.0],
                    "scale": [1.35, 1.35, 1.35],
                },
                "shadow_catcher": True,
                "reflection_catcher": True,
            }
        ],
        camera_solution={
            "id": "cam_scene",
            "frame_size": [260, 180],
            "intrinsics": {"fx": 240.0, "fy": 240.0, "cx": 130.0, "cy": 92.0},
        },
        depth_frame=depth,
        settings={
            "renderer": "software_pbr",
            "asset_descriptors": {str(fbx_path): descriptor},
            "camera_z": 3.0,
            "shadow_blur": 0,
            "preserve_scene_layout": True,
        },
    )

    assert diag["mode"] == "software_pbr"
    assert diag["rendered_track_count"] == 1
    assert diag["software_renderer"]["geometry_count"] == 3
    assert diag["software_renderer"]["triangle_count"] == 10
    assert int(out.sum()) > 0
    assert int(np.count_nonzero(out)) > 100
    assert out[:, :, 0].max() > out[:, :, 1].max()
