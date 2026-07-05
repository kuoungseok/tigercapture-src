from __future__ import annotations


def test_gpu_material_packets_emit_texture_and_pbr_rows() -> None:
    from app.ar_pbr.gpu_material_packets import PBR_TRIANGLE_FLOATS, build_material_triangle_packets

    material = {
        "name": "BodyPaint",
        "roughness": 0.36,
        "metallic": 0.2,
        "reflectance": 0.6,
    }
    geometry = {"id": "geo_body"}

    packets = build_material_triangle_packets(
        projected_points=((12.0, 14.0, 2.0), (40.0, 14.0, 2.0), (20.0, 42.0, 2.0)),
        world_points=((-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (0.0, 1.0, 0.0)),
        tri_uvs=[[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
        normal=(0.0, 0.0, 1.0),
        material=material,
        geometry=geometry,
        texture_path="body_base.png",
        texture_maps={"base": "body_base.png", "roughness": "body_rough.png"},
        rgba=(0.2, 0.7, 0.4, 1.0),
        width=96,
        height=96,
        avg_z=2.0,
        force_marmoset_pbr=True,
    )

    assert packets["texture_triangle"]["texture"] == "body_base.png"
    assert len(packets["texture_triangle"]["vertices"]) == 24
    assert packets["pbr_triangle"]["material_id"] == "BodyPaint"
    assert packets["pbr_triangle"]["maps"]["roughness"] == "body_rough.png"
    assert len(packets["pbr_triangle"]["vertices"]) == PBR_TRIANGLE_FLOATS
    assert packets["pbr_roughness"] == 0.36
    assert packets["marmoset_pbr_triangle"] is True


def test_gpu_material_packets_prefer_face_corner_uvs_and_transform() -> None:
    from app.ar_pbr.gpu_material_packets import geometry_uvs_for_material, material_uv_transform, triangle_uvs

    geometry = {
        "uvs": [[9.0, 9.0], [9.0, 9.0], [9.0, 9.0]],
        "triangle_uvs": [[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]],
    }
    material = {
        "uv_transform": {
            "offset": [0.25, 0.5],
            "scale": [2.0, 3.0],
            "rotation": 0.0,
        }
    }

    rows = geometry_uvs_for_material(geometry, material)
    uvs = triangle_uvs(geometry, 0, (0, 1, 2), rows, material_uv_transform(material))

    assert [[round(v, 4) for v in row] for row in uvs] == [[0.45, 1.1], [0.85, 1.7], [1.25, 2.3]]
