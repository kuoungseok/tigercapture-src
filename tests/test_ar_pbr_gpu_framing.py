import math

import numpy as np
import pytest

pytest.importorskip("PySide6")

import tools.ar_pbr_gpu_window as gpu_window
from tools.ar_pbr_gpu_window import (
    FRAG_SHADER,
    GROUND_FRAG_SHADER,
    GpuState,
    SHADOW_PCF_KERNEL,
    _fit_zoom_to_projected_bounds,
    _screen_pan_delta,
    _resolve_material_texture_plan,
    build_vertex_buffer,
    bevel_diagnostics,
    catcher_diagnostics,
    clearcoat_diagnostics,
    color_management_diagnostics,
    hybrid_rendering_diagnostics,
    material_layering_diagnostics,
    parallax_diagnostics,
    shadow_filter_diagnostics,
    surface_diagnostics,
    transmission_diagnostics,
)


def test_gpu_view_fit_uses_projected_bounds_not_fixed_zoom():
    mesh_diag = {
        "normalized_bounds": {
            "min": [-0.1681755334, -0.2810079753, -0.4999999404],
            "max": [0.1681755334, 0.2810079157, 0.5],
        }
    }
    state = GpuState(pitch=-10.0, yaw=72.0, roll=0.0, camera_z=3.25)

    zoom, diag = _fit_zoom_to_projected_bounds(
        mesh_diag,
        state,
        viewport_width=900,
        viewport_height=620,
        padding=0.06,
    )

    assert zoom > 1.75
    assert math.isclose(diag["actual_half_extent_ndc"], diag["target_half_extent_ndc"], abs_tol=1e-5)
    assert diag["method"] == "projected_bounds_corners_analytic"


def test_gpu_screen_pan_delta_tracks_view_plane_direction():
    pan_x, pan_y = _screen_pan_delta(
        100,
        -50,
        viewport_width=1000,
        viewport_height=500,
        camera_z=3.0,
    )

    assert pan_x > 0.0
    assert pan_y > 0.0
    assert pan_x > pan_y


def test_gpu_shadow_shaders_use_configurable_pcf_pcss_filter():
    assert "uniform float u_shadow_pcf_radius" in FRAG_SHADER
    assert "uniform float u_shadow_pcss_blocker_radius" in FRAG_SHADER
    assert "uniform float u_shadow_bias" in FRAG_SHADER
    assert "uniform float u_shadow_normal_bias" in FRAG_SHADER
    assert "uniform int u_shadow_filter_mode" in FRAG_SHADER
    assert "uniform float u_self_shadow_strength" in FRAG_SHADER
    assert "uniform float u_shadow_pcf_radius" in GROUND_FRAG_SHADER
    assert "uniform float u_shadow_pcss_blocker_radius" in GROUND_FRAG_SHADER
    assert "uniform float u_shadow_catcher_opacity" in GROUND_FRAG_SHADER
    assert "uniform float u_shadow_catcher_softness" in GROUND_FRAG_SHADER
    assert "uniform float u_shadow_catcher_matte_alpha" in GROUND_FRAG_SHADER
    assert "uniform float u_reflection_catcher_opacity" in GROUND_FRAG_SHADER
    assert "uniform float u_reflection_catcher_roughness" in GROUND_FRAG_SHADER
    assert "uniform float u_contact_reflection_strength" in GROUND_FRAG_SHADER
    assert "frag_color = vec4(rgb, alpha)" in GROUND_FRAG_SHADER
    assert "uniform int u_tone_mapping_mode" in FRAG_SHADER
    assert "uniform float u_tone_exposure" in FRAG_SHADER
    assert "uniform vec3 u_tone_white_balance" in FRAG_SHADER
    assert "uniform float u_tone_gamma" in FRAG_SHADER
    assert "apply_output_transform" in FRAG_SHADER
    assert "apply_output_transform" in GROUND_FRAG_SHADER
    assert "uniform int u_hybrid_sample_count" in FRAG_SHADER
    assert "uniform float u_diffuse_gi_strength" in FRAG_SHADER
    assert "uniform float u_specular_gi_strength" in FRAG_SHADER
    assert "diffuse_gi" in FRAG_SHADER
    assert "specular_gi" in FRAG_SHADER
    assert "uniform float u_transmission" in FRAG_SHADER
    assert "uniform float u_refraction_strength" in FRAG_SHADER
    assert "uniform float u_ior" in FRAG_SHADER
    assert "uniform vec3 u_absorption_color" in FRAG_SHADER
    assert "apply_transmission_refraction" in FRAG_SHADER
    assert "uniform float u_clearcoat_strength" in FRAG_SHADER
    assert "uniform float u_clearcoat_roughness" in FRAG_SHADER
    assert "uniform float u_clearcoat_ior" in FRAG_SHADER
    assert "uniform vec3 u_clearcoat_tint" in FRAG_SHADER
    assert "apply_clearcoat_layer" in FRAG_SHADER
    assert "uniform float u_parallax_strength" in FRAG_SHADER
    assert "uniform sampler2D u_height_map" in FRAG_SHADER
    assert "apply_parallax_uv" in FRAG_SHADER
    assert "uniform float u_bevel_strength" in FRAG_SHADER
    assert "uniform float u_bevel_radius" in FRAG_SHADER
    assert "apply_bevel_normal" in FRAG_SHADER
    assert "uniform float u_material_layer_blend" in FRAG_SHADER
    assert "uniform vec3 u_material_layer_color" in FRAG_SHADER
    assert "uniform int u_base_alpha_to_opacity" in FRAG_SHADER
    assert "apply_material_layer" in FRAG_SHADER
    assert "uniform float u_surface_override_strength" in FRAG_SHADER
    assert "uniform float u_surface_roughness" in FRAG_SHADER
    assert "uniform float u_surface_metallic" in FRAG_SHADER
    assert "uniform float u_surface_reflectance" in FRAG_SHADER
    assert "apply_surface_override" in FRAG_SHADER
    assert "u_shadow_pcf_radius" in FRAG_SHADER.split("float shadow_factor", 1)[1]
    assert "u_shadow_pcf_radius" in GROUND_FRAG_SHADER.split("float shadow_factor", 1)[1]
    assert "shadow_pcss" in FRAG_SHADER
    assert "ground_shadow_pcss" in GROUND_FRAG_SHADER
    assert "diffuse *= self_shadow" in FRAG_SHADER
    assert "fill *= mix(1.0, self_shadow" in FRAG_SHADER

    state = GpuState(
        shadow_filter="pcss",
        shadow_light_type="spot",
        shadow_pcf_radius=2.25,
        shadow_pcss_blocker_radius=3.5,
        shadow_bias=0.004,
        shadow_normal_bias=0.006,
        shadow_spot_inner_angle=25.0,
        shadow_spot_outer_angle=48.0,
        self_shadow_strength=0.7,
        shadow_catcher_opacity=0.82,
        shadow_catcher_softness=0.74,
        shadow_catcher_matte_alpha=0.12,
        reflection_catcher_opacity=0.59,
        reflection_catcher_roughness=0.78,
        reflection_catcher_softness=0.67,
        contact_reflection_strength=0.46,
        contact_reflection_falloff=0.61,
        tone_mapping="agx",
        tone_exposure=0.75,
        tone_white_balance=5200.0,
        tone_gamma=2.35,
        hybrid_sample_count=18,
        diffuse_gi_strength=0.36,
        specular_gi_strength=0.24,
        denoise_strength=0.42,
        transmission="0.48",
        refraction_strength=0.54,
        refraction_depth_px=8.0,
        ior=1.51,
        thickness=0.26,
        absorption_color=(0.82, 0.94, 1.0),
        absorption_distance=1.8,
        roughness_blur_strength=0.28,
        clearcoat_strength=0.49,
        clearcoat_roughness=0.07,
        clearcoat_ior=1.57,
        clearcoat_tint=(1.0, 0.95, 0.88),
        parallax_strength=0.51,
        parallax_depth=0.045,
        parallax_center=0.48,
        parallax_steps=5,
        bevel_strength=0.52,
        bevel_radius=0.058,
        bevel_edge_width=0.09,
        bevel_samples=4,
        material_layer_blend=0.43,
        material_layer_color=(0.91, 0.42, 0.16),
        material_layer_roughness=0.32,
        material_layer_metallic=0.17,
        material_layer_alpha=0.9,
        material_layer_emissive_strength=0.09,
        material_layer_mask_strength=0.81,
        surface_override_strength=0.66,
        surface_roughness=0.29,
        surface_metallic=0.21,
        surface_reflectance=0.47,
    )
    diag = shadow_filter_diagnostics(
        state,
        enable_shadow_map=True,
        shadow_supported=True,
        shadow_size=2048,
    )

    assert diag["schema"] == "tigerstudio.ar_pbr.shadow_filter.v1"
    assert diag["filter"] == "pcss"
    assert diag["light_type"] == "spot"
    assert diag["primary_shadow_model"] == "shadow_map"
    assert diag["contact_shadow_role"] == "helper_only"
    assert diag["pcf_kernel"] == SHADOW_PCF_KERNEL
    assert diag["pcf_radius_texels"] == 2.25
    assert diag["pcss_blocker_radius_texels"] == 3.5
    assert diag["bias"] == 0.004
    assert diag["normal_bias"] == 0.006
    assert diag["spot_inner_angle"] == 25.0
    assert diag["spot_outer_angle"] == 48.0
    assert diag["self_shadow_strength"] == 0.7
    catcher = catcher_diagnostics(state)
    assert catcher["schema"] == "tigerstudio.ar_pbr.catcher.v1"
    assert catcher["shadow_catcher"]["opacity"] == 0.82
    assert catcher["shadow_catcher"]["softness"] == 0.74
    assert catcher["shadow_catcher"]["matte_alpha"] == 0.12
    assert catcher["reflection_catcher"]["opacity"] == 0.59
    assert catcher["reflection_catcher"]["roughness"] == 0.78
    assert catcher["reflection_catcher"]["softness"] == 0.67
    assert catcher["reflection_catcher"]["contact_reflection_strength"] == 0.46
    color = color_management_diagnostics(state)
    assert color["schema"] == "tigerstudio.ar_pbr.color_management.v1"
    assert color["tone_mapping"] == "agx"
    assert color["tone_mapping_mode"] == 1
    assert color["tone_exposure"] == 0.75
    assert color["tone_white_balance"] == 5200.0
    assert color["tone_gamma"] == 2.35
    assert color["render_pass_safe"] is True
    hybrid = hybrid_rendering_diagnostics(state)
    assert hybrid["schema"] == "tigerstudio.ar_pbr.hybrid_rendering.v1"
    assert hybrid["enabled"] is True
    assert hybrid["sample_count"] == 18
    assert hybrid["diffuse_gi_strength"] == 0.36
    assert hybrid["specular_gi_strength"] == 0.24
    assert hybrid["denoise_strength"] == 0.42
    transmission = transmission_diagnostics(state)
    assert transmission["schema"] == "tigerstudio.ar_pbr.transmission.v1"
    assert transmission["enabled"] is True
    assert transmission["transmission"] == 0.48
    assert transmission["refraction_strength"] == 0.54
    assert transmission["ior"] == 1.51
    assert transmission["absorption_color"] == [0.82, 0.94, 1.0]
    clearcoat = clearcoat_diagnostics(state)
    assert clearcoat["schema"] == "tigerstudio.ar_pbr.clearcoat.v1"
    assert clearcoat["enabled"] is True
    assert clearcoat["strength"] == 0.49
    assert clearcoat["roughness"] == 0.07
    assert clearcoat["ior"] == 1.57
    assert clearcoat["tint"] == [1.0, 0.95, 0.88]
    parallax = parallax_diagnostics(state)
    assert parallax["schema"] == "tigerstudio.ar_pbr.parallax.v1"
    assert parallax["enabled"] is True
    assert parallax["mode"] == "parallax"
    assert parallax["strength"] == 0.51
    assert parallax["depth"] == 0.045
    assert parallax["center"] == 0.48
    assert parallax["steps"] == 5
    bevel = bevel_diagnostics(state)
    assert bevel["schema"] == "tigerstudio.ar_pbr.bevel.v1"
    assert bevel["enabled"] is True
    assert bevel["mode"] == "bevel"
    assert bevel["strength"] == 0.52
    assert bevel["radius"] == 0.058
    assert bevel["edge_width"] == 0.09
    assert bevel["samples"] == 4
    material_layer = material_layering_diagnostics(state)
    assert material_layer["schema"] == "tigerstudio.ar_pbr.material_layering.v1"
    assert material_layer["enabled"] is True
    assert material_layer["mode"] == "layered"
    assert material_layer["blend"] == 0.43
    assert material_layer["color"] == [0.91, 0.42, 0.16]
    assert material_layer["roughness"] == 0.32
    assert material_layer["metallic"] == 0.17
    surface = surface_diagnostics(state)
    assert surface["schema"] == "tigerstudio.ar_pbr.surface.v1"
    assert surface["override_strength"] == 0.66
    assert surface["roughness"] == 0.29
    assert surface["metallic"] == 0.21
    assert surface["reflectance"] == 0.47


def test_gltf_blend_pbr_materials_keep_depth_write_by_default():
    material = {
        "name": "Outside",
        "alpha_mode": "BLEND",
        "base_texture_source": "gltf_pbr_base_color_texture",
        "pbr_available": True,
    }

    assert gpu_window._material_depth_write(material) is True
    assert gpu_window._material_alpha_bucket(material) == 0


def test_explicit_transparent_depth_policy_is_preserved():
    explicit_depth_off = {"alpha_mode": "BLEND", "depth_write": False}
    explicit_mtoon_off = {"alpha_mode": "BLEND", "mtoon_zwrite": 0}

    assert gpu_window._material_depth_write(explicit_depth_off) is False
    assert gpu_window._material_alpha_bucket(explicit_depth_off) == 1
    assert gpu_window._material_depth_write(explicit_mtoon_off) is False


def test_base_texture_alpha_only_drives_opacity_for_explicit_alpha_surfaces():
    body_maps = {
        "alpha_mode": "BLEND",
        "base": "Outside_BaseColor.png",
        "depth_write": "true",
    }
    decal_maps = {
        "alpha_mode": "BLEND",
        "base": "Decals_BaseColor.png",
        "depth_write": "true",
    }
    opacity_maps = {
        "alpha_mode": "BLEND",
        "base": "Glass_BaseColor.png",
        "opacity": "Glass_Opacity.png",
    }

    assert gpu_window._base_alpha_to_opacity("Outside", body_maps) is False
    assert gpu_window._base_alpha_to_opacity("Decals", decal_maps) is True
    assert gpu_window._base_alpha_to_opacity("Glass", opacity_maps) is True


def test_gpu_vertex_buffer_respects_geometry_material_id_over_node_connections():
    descriptor = {
        "bounds": {"center": [0.5, 0.5, 0.0], "size": [1.0, 1.0, 1.0]},
        "materials": [
            {"id": "mat_red", "name": "RedPaint", "base_color": [1.0, 0.0, 0.0, 1.0]},
            {"id": "mat_blue", "name": "BluePaint", "base_color": [0.0, 0.0, 1.0, 1.0]},
        ],
        "geometries": [
            {
                "id": "geom_red",
                "model_id": "node_0",
                "material_id": "mat_red",
                "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                "triangles": [[0, 1, 2]],
            },
            {
                "id": "geom_blue",
                "model_id": "node_0",
                "material_id": "mat_blue",
                "vertices": [[1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]],
                "triangles": [[0, 1, 2]],
            },
        ],
        "connections": [
            {"child": "geom_red", "parent": "node_0", "type": "Geometry"},
            {"child": "geom_blue", "parent": "node_0", "type": "Geometry"},
            {"child": "mat_red", "parent": "node_0", "type": "Material"},
            {"child": "mat_blue", "parent": "node_0", "type": "Material"},
        ],
    }

    vertices, diag = build_vertex_buffer(descriptor)

    assert [row["material_name"] for row in diag["draw_ranges"]] == ["RedPaint", "BluePaint"]
    assert vertices[0, 6:10].tolist() == [1.0, 0.0, 0.0, 1.0]
    blue_start = int(diag["draw_ranges"][1]["start"])
    assert vertices[blue_start, 6:10].tolist() == [0.0, 0.0, 1.0, 1.0]


def test_gpu_vertex_buffer_uses_material_uv_set_transform_and_gltf_upload_flip():
    descriptor = {
        "source_format": "gltf",
        "source_ext": ".gltf",
        "backend": "internal_gltf",
        "bounds": {"center": [0, 0, 0], "size": [1, 1, 1]},
        "materials": [
            {
                "id": "mat_0",
                "name": "Atlas",
                "base_uv_set": 1,
                "base_uv_transform": {
                    "offset": [0.1, 0.2],
                    "scale": [0.5, 0.25],
                    "rotation": 0.0,
                },
            }
        ],
        "geometries": [
            {
                "id": "geom_0",
                "material_id": "mat_0",
                "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                "triangles": [[0, 1, 2]],
                "uvs": [[0.9, 0.9], [0.8, 0.8], [0.7, 0.7]],
                "uv_sets": {
                    "1": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
                },
            }
        ],
    }

    vertices, diag = build_vertex_buffer(descriptor)

    assert diag["uv_v_flipped_for_texture_upload"] is True
    assert diag["draw_ranges"][0]["uv_set"] == 1
    assert diag["draw_ranges"][0]["uv_v_flipped_for_texture_upload"] is True
    assert np.allclose(
        vertices[:3, 13:15],
        np.asarray([[0.1, 0.8], [0.6, 0.8], [0.1, 0.55]], dtype=np.float32),
    )


def test_gpu_vertex_buffer_uv_v_flip_mode_can_be_forced(monkeypatch):
    descriptor = {
        "source_format": "gltf",
        "source_ext": ".gltf",
        "bounds": {"center": [0, 0, 0], "size": [1, 1, 1]},
        "materials": [{"id": "mat_0", "name": "Atlas"}],
        "geometries": [
            {
                "id": "geom_0",
                "material_id": "mat_0",
                "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                "triangles": [[0, 1, 2]],
                "uvs": [[0.0, 0.0], [1.0, 0.25], [0.5, 1.0]],
            }
        ],
    }

    monkeypatch.setattr(gpu_window, "PREVIEW_UV_V_FLIP_MODE", "off")
    vertices_off, diag_off = gpu_window.build_vertex_buffer(descriptor)
    monkeypatch.setattr(gpu_window, "PREVIEW_UV_V_FLIP_MODE", "on")
    vertices_on, diag_on = gpu_window.build_vertex_buffer(descriptor)

    assert diag_off["uv_v_flipped_for_texture_upload"] is False
    assert diag_on["uv_v_flipped_for_texture_upload"] is True
    assert np.allclose(vertices_off[:3, 13:15], [[0.0, 0.0], [1.0, 0.25], [0.5, 1.0]])
    assert np.allclose(vertices_on[:3, 13:15], [[0.0, 1.0], [1.0, 0.75], [0.5, 0.0]])


def test_gpu_vertex_buffer_bakes_skeletal_animation_for_full_gpu_path():
    descriptor = {
        "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
        "models": [
            {"id": "mesh_model", "name": "Mesh", "translation": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]},
            {"id": "bone_1", "name": "Root", "kind": "LimbNode", "translation": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]},
        ],
        "bones": [{"id": "bone_1", "name": "Root"}],
        "skeletal_mesh_count": 1,
        "geometries": [
            {
                "model_id": "mesh_model",
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
                "skin_weights": [
                    [{"bone_id": "bone_1", "weight": 1.0}],
                    [{"bone_id": "bone_1", "weight": 1.0}],
                    [{"bone_id": "bone_1", "weight": 1.0}],
                ],
            }
        ],
        "materials": [{"base_color": [0.2, 0.8, 1.0, 1.0]}],
        "animation_clips": [{
            "id": "clip_001",
            "name": "BoneMove",
            "duration_ms": 1000.0,
            "model_curves": {
                "bone_1": {
                    "translation": {
                        "x": [[0.0, 0.0], [1000.0, 1.0]],
                    },
                },
            },
        }],
    }
    track = {
        "id": "ar_pbr_skel",
        "asset_path": "skeletal.fbx",
        "start_ms": 0,
        "end_ms": 2000,
        "animation": {"auto_play": True, "loop": False, "speed": 1.0},
    }

    first, first_diag = build_vertex_buffer(descriptor, track=track, time_ms=0)
    later, later_diag = build_vertex_buffer(descriptor, track=track, time_ms=500)

    assert first_diag["skeletal_geometry_count"] == 1
    assert later_diag["animated_geometry_count"] == 1
    assert later_diag["skeletal_animation_applied"] is True
    assert not np.array_equal(first[:, :3], later[:, :3])


def test_gpu_texture_plan_keeps_gltf_orm_channels(tmp_path):
    asset = tmp_path / "vehicle.glb"
    asset.write_bytes(b"placeholder")
    orm = tmp_path / "orm.png"
    orm.write_bytes(b"placeholder")
    descriptor = {
        "texture_count": 1,
        "materials": [
            {
                "id": "mat_0",
                "name": "VehiclePaint",
                "roughness_texture": "orm.png",
                "roughness_channel": "g",
                "metallic_texture": "orm.png",
                "metallic_channel": "b",
            }
        ],
    }

    plan, diag = _resolve_material_texture_plan(asset, descriptor)

    assert diag["status"] == "ready"
    assert plan["VehiclePaint"]["roughness_channel"] == "g"
    assert plan["VehiclePaint"]["metallic_channel"] == "b"


def test_gpu_texture_plan_expands_orm_emissive_opacity_contract(tmp_path):
    asset = tmp_path / "material_contract.glb"
    asset.write_bytes(b"placeholder")
    orm = tmp_path / "paint_orm.png"
    emissive = tmp_path / "paint_emissive.png"
    opacity = tmp_path / "paint_opacity.png"
    height = tmp_path / "paint_height.png"
    for path in (orm, emissive, opacity, height):
        path.write_bytes(b"placeholder")
    descriptor = {
        "texture_count": 4,
        "materials": [
            {
                "id": "mat_0",
                "name": "VehiclePaint",
                "orm_texture": "paint_orm.png",
                "emissive_texture": "paint_emissive.png",
                "opacity_texture": "paint_opacity.png",
                "height_texture": "paint_height.png",
                "opacity_channel": "a",
                "alpha_mode": "MASK",
                "alpha_cutoff": 0.42,
                "emissive_factor": [1.0, 0.25, 0.1],
            }
        ],
    }

    plan, diag = _resolve_material_texture_plan(asset, descriptor)
    maps = plan["VehiclePaint"]

    assert diag["status"] == "ready"
    assert diag["material_map_contract"] == [
        "base",
        "roughness",
        "metallic",
        "specular",
        "normal",
        "occlusion",
        "emissive",
        "opacity",
        "height",
    ]
    assert diag["orm_material_count"] == 1
    assert maps["occlusion"] == str(orm.resolve())
    assert maps["occlusion_channel"] == "r"
    assert maps["roughness"] == str(orm.resolve())
    assert maps["roughness_channel"] == "g"
    assert maps["metallic"] == str(orm.resolve())
    assert maps["metallic_channel"] == "b"
    assert maps["emissive"] == str(emissive.resolve())
    assert maps["opacity"] == str(opacity.resolve())
    assert maps["opacity_channel"] == "a"
    assert maps["height"] == str(height.resolve())
    assert maps["alpha_cutoff"] == "0.42"
    assert maps["emissive_factor"] == "1.0,0.25,0.1"


def test_gpu_texture_plan_expands_udim_tile_sets(tmp_path):
    asset = tmp_path / "udim_vehicle.glb"
    asset.write_bytes(b"placeholder")
    tile_1001 = tmp_path / "paint_base.1001.png"
    tile_1002 = tmp_path / "paint_base.1002.png"
    tile_1001.write_bytes(b"tile-1001")
    tile_1002.write_bytes(b"tile-1002")
    descriptor = {
        "texture_count": 2,
        "materials": [
            {
                "id": "mat_0",
                "name": "UDIMPaint",
                "base_texture": "paint_base.<UDIM>.png",
            }
        ],
    }

    plan, diag = _resolve_material_texture_plan(asset, descriptor)
    maps = plan["UDIMPaint"]

    assert diag["status"] == "ready"
    assert diag["udim_status"] == "ready"
    assert diag["udim_material_count"] == 1
    assert diag["udim_map_count"] == 1
    assert diag["udim_tile_count"] == 2
    assert maps["base"] == str(tile_1001.resolve())
    assert maps["base_udim_tile_count"] == "2"
    assert maps["base_udim_primary_tile"] == "1001"
    assert "1002" in maps["base_udim_tiles"]


def test_gpu_vertex_buffer_applies_marmoset_pbr_render_profile():
    descriptor = {
        "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
        "render_profiles": {
            "schema": "tigerstudio.ar_pbr.render_profiles.v1",
            "default_profile": "authored",
            "active_profile": "authored",
            "available_profiles": ["authored", "marmoset_pbr"],
            "profiles": {
                "authored": {"available": True},
                "marmoset_pbr": {"available": True},
            },
        },
        "geometries": [
            {
                "id": "geom_0",
                "material_id": "mat_0",
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
            }
        ],
        "materials": [
            {
                "id": "mat_0",
                "name": "Face",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "roughness": 0.38,
                "metallic": 0.22,
                "reflectance": 0.64,
                "shader_model": "vrm_mtoon",
                "source_shader": "VRM/MToon",
                "unlit": True,
                "base_texture_source": "gltf_pbr_base_color_texture",
                "pbr_available": True,
            }
        ],
    }

    authored, authored_diag = build_vertex_buffer(descriptor)
    pbr, pbr_diag = build_vertex_buffer(
        descriptor,
        track={"render": {"render_profile": "marmoset_pbr"}},
    )

    assert authored_diag["render_profile"] == "authored"
    assert authored[0, 10:13].tolist() == [1.0, 0.0, -1.0]
    assert pbr_diag["render_profile"] == "marmoset_pbr"
    assert np.allclose(pbr[0, 10:13], [0.38, 0.22, 0.64])
