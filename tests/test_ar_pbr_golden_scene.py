from __future__ import annotations

import numpy as np


def test_ar_pbr_golden_scene_builds_p0_rendering_contract(tmp_path):
    from app.ar_pbr.gpu_preview import build_gpu_preview_items
    from tools.qa_ar_pbr_golden_scene import build_ar_pbr_golden_scene, compare_image_arrays

    scene = build_ar_pbr_golden_scene(out_dir=tmp_path, width=128, height=80)
    assert scene["schema"] == "tigerstudio.ar_pbr.golden_scene.v1"
    assert scene["lighting"]["tone_mapping"] == "agx"
    assert scene["lighting"]["shadow_filter"] == "pcss"
    assert scene["lighting"]["shadow_light_type"] == "spot"
    assert scene["lighting"]["hybrid_accumulation"] is True
    assert scene["lighting"]["ray_gi_detail"]["max_bounces"] == 6
    assert scene["lighting"]["ray_gi_detail"]["light_sampling_mode"] == "mis"
    assert "transmission" in scene["lighting"]["ray_gi_detail"]["denoise_channels"]
    assert scene["lighting"]["ao_strength"] == 0.38
    assert scene["lighting"]["transmission"] == 0.42
    assert scene["lighting"]["clearcoat_strength"] == 0.46
    assert scene["lighting"]["parallax_strength"] == 0.50
    assert scene["lighting"]["displacement_height_strength"] == 0.52
    assert scene["lighting"]["vector_displacement_strength"] == 0.20
    assert scene["lighting"]["bevel_strength"] == 0.44
    assert scene["lighting"]["material_layer_blend"] == 0.38
    assert scene["lighting"]["triplanar_strength"] == 1.0
    assert scene["lighting"]["subsurface_strength"] == 0.34
    assert scene["lighting"]["hair_groom_strength"] == 0.37
    assert scene["lighting"]["cloth_sheen_strength"] == 0.36
    assert scene["lighting"]["glint_strength"] == 0.34
    assert scene["lighting"]["caustics_strength"] == 0.40
    assert scene["lighting"]["anisotropic_strength"] == 0.42
    assert scene["lighting"]["thin_film_strength"] == 0.50
    assert scene["lighting"]["detail_normal_strength"] == 0.46
    assert scene["lighting"]["micro_roughness_strength"] == 0.36
    assert scene["lighting"]["depth_of_field_strength"] == 0.62
    assert scene["lighting"]["bloom_strength"] == 0.32
    assert scene["lighting"]["lens_distortion_strength"] == 0.16
    assert scene["lighting"]["chromatic_aberration_px"] == 2.2
    assert scene["lighting"]["lens_flare_strength"] == 0.36
    assert scene["lighting"]["aperture_flare_strength"] == 0.28
    assert scene["lighting"]["lens_dirt_strength"] == 0.17
    assert scene["lighting"]["lens_scratch_strength"] == 0.13
    assert scene["lighting"]["motion_blur_samples"] == 5
    assert scene["lighting"]["render_passes_enabled"] is True
    assert "normal" in scene["lighting"]["render_pass_names"]
    assert scene["descriptor"]["animation_count"] == 1
    assert len(scene["texture_paths"]) == 9

    items, diag = build_gpu_preview_items(
        frame_size=(128, 80),
        time_ms=scene["time_ms"],
        ar_tracks=scene["ar_tracks"],
        camera_solution=scene["camera_solution"],
        depth_frame=scene["depth_frame"],
        settings=scene["settings"],
    )

    assert len(items) == 1
    assert diag["pbr_triangle_count"] >= 1
    assert diag["texture_map_count"] == 9
    assert diag["live_depth_texture_triangle_count"] >= 1
    assert diag["shadow_triangle_count"] >= 1
    assert diag["reflection_triangle_count"] >= 1
    assert diag["gpu_renderer"]["render_profile"] == "marmoset_pbr"
    assert diag["gpu_renderer"]["color_management"] == "agx"
    assert diag["gpu_renderer"]["hybrid_rendering"] == "hybrid"
    assert diag["gpu_renderer"]["hybrid_accumulation_samples"] == 16
    assert diag["gpu_renderer"]["ray_gi_detail"] == "hybrid"
    assert diag["gpu_renderer"]["ray_gi_bounces"] == 6
    assert diag["gpu_renderer"]["ray_gi_light_sampling"] == "mis"
    assert diag["gpu_renderer"]["ambient_occlusion_rendering"] == "screen"
    assert diag["gpu_renderer"]["transmission_rendering"] in {"transmission", "refraction", "glass"}
    assert diag["gpu_renderer"]["clearcoat_rendering"] == "clearcoat"
    assert diag["gpu_renderer"]["parallax_rendering"] == "parallax"
    assert diag["gpu_renderer"]["displacement_rendering"] == "displacement"
    assert diag["gpu_renderer"]["displacement_fallback"] == "parallax_mapping"
    assert diag["gpu_renderer"]["bevel_rendering"] == "bevel"
    assert diag["gpu_renderer"]["material_layering"] == "layered"
    assert diag["gpu_renderer"]["udim"] == "texture_plan_udim_tiles_ready"
    assert diag["gpu_renderer"]["udim_tile_count"] == 2
    assert diag["gpu_renderer"]["triplanar_rendering"] == "triplanar"
    assert diag["gpu_renderer"]["subsurface_rendering"] == "subsurface"
    assert diag["gpu_renderer"]["hair_groom_rendering"] == "hair"
    assert diag["gpu_renderer"]["cloth_sheen_rendering"] == "sheen"
    assert diag["gpu_renderer"]["glint_sparkle_rendering"] == "sparkle"
    assert diag["gpu_renderer"]["caustics_rendering"] == "caustics"
    assert diag["gpu_renderer"]["caustics_samples"] == 24
    assert diag["gpu_renderer"]["anisotropic_rendering"] == "anisotropic"
    assert diag["gpu_renderer"]["thin_film_strength"] == 0.5
    assert diag["gpu_renderer"]["microsurface_rendering"] == "microsurface"
    assert diag["gpu_renderer"]["detail_normal_strength"] == 0.46
    assert diag["gpu_renderer"]["micro_roughness_strength"] == 0.36
    assert diag["gpu_renderer"]["depth_of_field_rendering"] == "depth_of_field"
    assert diag["gpu_renderer"]["post_effects_rendering"] == "post_effects"
    assert diag["gpu_renderer"]["lens_effects_rendering"] == "lens_effects"
    assert diag["gpu_renderer"]["lens_flare_rendering"] == "lens_flare"
    assert diag["gpu_renderer"]["motion_blur"] == "final_export_shutter_sample_contract"
    assert diag["gpu_renderer"]["motion_blur_samples"] == 5
    assert diag["gpu_renderer"]["render_passes"] == "packet_render_pass_export_contract"
    assert diag["gpu_renderer"]["render_pass_count"] >= 19
    assert items[0]["pbr_lighting"]["shadow_filter"] == "pcss"
    assert items[0]["pbr_lighting"]["shadow_light_type"] == "spot"
    assert items[0]["pbr_lighting"]["tone_mapping"] == "agx"
    assert items[0]["pbr_lighting"]["hybrid_accumulation_enabled"] is True
    assert items[0]["pbr_lighting"]["ray_gi_detail_enabled"] is True
    assert items[0]["pbr_lighting"]["ray_gi_max_bounces"] == 6
    assert items[0]["pbr_lighting"]["ray_gi_diffuse_bounces"] == 3
    assert items[0]["pbr_lighting"]["ray_gi_specular_bounces"] == 4
    assert items[0]["pbr_lighting"]["ray_gi_refraction_bounces"] == 5
    assert items[0]["pbr_lighting"]["ray_gi_light_sampling_mode"] == "mis"
    assert items[0]["pbr_lighting"]["ray_gi_light_sample_count"] == 24
    assert items[0]["pbr_lighting"]["ray_gi_environment_sample_count"] == 48
    assert items[0]["pbr_lighting"]["ray_gi_denoise_channels"] == ["beauty", "diffuse", "specular", "transmission"]
    assert items[0]["pbr_lighting"]["ambient_occlusion_enabled"] is True
    assert items[0]["pbr_lighting"]["ao_strength"] == 0.38
    assert items[0]["pbr_lighting"]["ao_specular"] is True
    assert items[0]["pbr_lighting"]["transmission_enabled"] is True
    assert items[0]["pbr_lighting"]["refraction_strength"] == 0.55
    assert items[0]["pbr_lighting"]["clearcoat_enabled"] is True
    assert items[0]["pbr_lighting"]["clearcoat_strength"] == 0.46
    assert items[0]["pbr_lighting"]["parallax_enabled"] is True
    assert items[0]["pbr_lighting"]["parallax_strength"] == 0.5
    assert items[0]["pbr_lighting"]["displacement_enabled"] is True
    assert items[0]["pbr_lighting"]["displacement_height_strength"] == 0.52
    assert items[0]["pbr_lighting"]["vector_displacement_strength"] == 0.2
    assert items[0]["pbr_lighting"]["bevel_enabled"] is True
    assert items[0]["pbr_lighting"]["bevel_strength"] == 0.44
    assert items[0]["pbr_lighting"]["material_layer_enabled"] is True
    assert items[0]["pbr_lighting"]["material_layer_blend"] == 0.38
    assert items[0]["pbr_lighting"]["triplanar_enabled"] is True
    assert items[0]["pbr_lighting"]["triplanar_scale"] == 1.45
    assert items[0]["pbr_lighting"]["subsurface_enabled"] is True
    assert items[0]["pbr_lighting"]["subsurface_strength"] == 0.34
    assert items[0]["pbr_lighting"]["hair_groom_enabled"] is True
    assert items[0]["pbr_lighting"]["hair_groom_strength"] == 0.37
    assert items[0]["pbr_lighting"]["cloth_sheen_enabled"] is True
    assert items[0]["pbr_lighting"]["cloth_sheen_strength"] == 0.36
    assert items[0]["pbr_lighting"]["glint_enabled"] is True
    assert items[0]["pbr_lighting"]["glint_strength"] == 0.34
    assert items[0]["pbr_lighting"]["caustics_enabled"] is True
    assert items[0]["pbr_lighting"]["caustics_strength"] == 0.4
    assert items[0]["pbr_lighting"]["anisotropic_enabled"] is True
    assert items[0]["pbr_lighting"]["anisotropic_strength"] == 0.42
    assert items[0]["pbr_lighting"]["thin_film_enabled"] is True
    assert items[0]["pbr_lighting"]["thin_film_strength"] == 0.5
    assert items[0]["pbr_lighting"]["microsurface_enabled"] is True
    assert items[0]["pbr_lighting"]["detail_normal_enabled"] is True
    assert items[0]["pbr_lighting"]["detail_normal_strength"] == 0.46
    assert items[0]["pbr_lighting"]["micro_roughness_enabled"] is True
    assert items[0]["pbr_lighting"]["micro_roughness_strength"] == 0.36
    assert items[0]["pbr_lighting"]["depth_of_field_enabled"] is True
    assert items[0]["pbr_lighting"]["depth_of_field_strength"] == 0.62
    assert items[0]["pbr_lighting"]["dof_focus_depth"] == 0.12
    assert items[0]["pbr_lighting"]["post_effects_enabled"] is True
    assert items[0]["pbr_lighting"]["bloom_enabled"] is True
    assert items[0]["pbr_lighting"]["bloom_strength"] == 0.32
    assert items[0]["pbr_lighting"]["vignette_enabled"] is True
    assert items[0]["pbr_lighting"]["grain_enabled"] is True
    assert items[0]["pbr_lighting"]["sharpen_enabled"] is True
    assert items[0]["pbr_lighting"]["lens_effects_enabled"] is True
    assert items[0]["pbr_lighting"]["lens_distortion_strength"] == 0.16
    assert items[0]["pbr_lighting"]["chromatic_aberration_enabled"] is True
    assert items[0]["pbr_lighting"]["chromatic_aberration_px"] == 2.2
    assert items[0]["pbr_lighting"]["lens_flare_enabled"] is True
    assert items[0]["pbr_lighting"]["lens_flare_strength"] == 0.36
    assert items[0]["pbr_lighting"]["aperture_flare_enabled"] is True
    assert items[0]["pbr_lighting"]["lens_dirt_enabled"] is True
    assert items[0]["pbr_lighting"]["lens_scratch_enabled"] is True
    assert items[0]["pbr_lighting"]["motion_blur_enabled"] is True
    assert items[0]["pbr_lighting"]["motion_blur_samples"] == 5
    assert items[0]["pbr_lighting"]["render_passes_enabled"] is True
    assert "object_id" in items[0]["pbr_lighting"]["render_pass_names"]
    assert items[0]["hybrid_rendering"]["sample_count"] == 16
    assert items[0]["ray_gi_detail"]["schema"] == "tigerstudio.ar_pbr.ray_gi_detail.v1"
    assert items[0]["ray_gi_detail"]["enabled"] is True
    assert items[0]["ray_gi_detail"]["max_bounces"] == 6
    assert items[0]["ray_gi_detail"]["light_sampling_mode"] == "mis"
    assert items[0]["ambient_occlusion_rendering"]["schema"] == "tigerstudio.ar_pbr.ambient_occlusion.v1"
    assert items[0]["ambient_occlusion_rendering"]["strength"] == 0.38
    assert items[0]["transmission_rendering"]["schema"] == "tigerstudio.ar_pbr.transmission.v1"
    assert items[0]["transmission_rendering"]["transmission"] == 0.42
    assert items[0]["clearcoat_rendering"]["schema"] == "tigerstudio.ar_pbr.clearcoat.v1"
    assert items[0]["clearcoat_rendering"]["strength"] == 0.46
    assert items[0]["parallax_rendering"]["schema"] == "tigerstudio.ar_pbr.parallax.v1"
    assert items[0]["parallax_rendering"]["strength"] == 0.5
    assert items[0]["displacement_rendering"]["schema"] == "tigerstudio.ar_pbr.displacement.v1"
    assert items[0]["displacement_rendering"]["height_strength"] == 0.52
    assert items[0]["displacement_rendering"]["vector_strength"] == 0.2
    assert items[0]["bevel_rendering"]["schema"] == "tigerstudio.ar_pbr.bevel.v1"
    assert items[0]["bevel_rendering"]["strength"] == 0.44
    assert items[0]["material_layering"]["schema"] == "tigerstudio.ar_pbr.material_layering.v1"
    assert items[0]["material_layering"]["blend"] == 0.38
    assert items[0]["triplanar_rendering"]["schema"] == "tigerstudio.ar_pbr.triplanar.v1"
    assert items[0]["triplanar_rendering"]["scale"] == 1.45
    assert items[0]["subsurface_rendering"]["schema"] == "tigerstudio.ar_pbr.subsurface.v1"
    assert items[0]["subsurface_rendering"]["strength"] == 0.34
    assert items[0]["hair_groom_rendering"]["schema"] == "tigerstudio.ar_pbr.hair_groom.v1"
    assert items[0]["hair_groom_rendering"]["strength"] == 0.37
    assert items[0]["cloth_sheen_rendering"]["schema"] == "tigerstudio.ar_pbr.cloth_sheen.v1"
    assert items[0]["cloth_sheen_rendering"]["strength"] == 0.36
    assert items[0]["glint_sparkle_rendering"]["schema"] == "tigerstudio.ar_pbr.glint_sparkle.v1"
    assert items[0]["glint_sparkle_rendering"]["strength"] == 0.34
    assert items[0]["caustics_rendering"]["schema"] == "tigerstudio.ar_pbr.caustics.v1"
    assert items[0]["caustics_rendering"]["strength"] == 0.4
    assert items[0]["anisotropic_rendering"]["schema"] == "tigerstudio.ar_pbr.anisotropic_material.v1"
    assert items[0]["anisotropic_rendering"]["anisotropy"] == 0.58
    assert items[0]["anisotropic_rendering"]["thin_film_strength"] == 0.5
    assert items[0]["microsurface_rendering"]["schema"] == "tigerstudio.ar_pbr.microsurface.v1"
    assert items[0]["microsurface_rendering"]["detail_normal_strength"] == 0.46
    assert items[0]["microsurface_rendering"]["micro_roughness_strength"] == 0.36
    assert items[0]["depth_of_field_rendering"]["schema"] == "tigerstudio.ar_pbr.depth_of_field.v1"
    assert items[0]["depth_of_field_rendering"]["strength"] == 0.62
    assert items[0]["post_effects_rendering"]["schema"] == "tigerstudio.ar_pbr.post_effects.v1"
    assert items[0]["post_effects_rendering"]["bloom_strength"] == 0.32
    assert items[0]["lens_effects_rendering"]["schema"] == "tigerstudio.ar_pbr.lens_effects.v1"
    assert items[0]["lens_effects_rendering"]["distortion_enabled"] is True
    assert items[0]["lens_effects_rendering"]["chromatic_aberration_enabled"] is True
    assert items[0]["lens_flare_rendering"]["schema"] == "tigerstudio.ar_pbr.lens_flare.v1"
    assert items[0]["lens_flare_rendering"]["flare_enabled"] is True
    assert items[0]["lens_flare_rendering"]["aperture_flare_enabled"] is True
    assert items[0]["lens_flare_rendering"]["lens_dirt_enabled"] is True
    assert items[0]["lens_flare_rendering"]["lens_scratch_enabled"] is True
    assert items[0]["motion_blur"]["schema"] == "tigerstudio.ar_pbr.motion_blur.v1"
    assert items[0]["motion_blur"]["enabled"] is True
    assert items[0]["render_passes"]["schema"] == "tigerstudio.ar_pbr.render_passes.v1"
    assert items[0]["render_passes"]["enabled"] is True
    assert items[0]["pbr_triangles"][0]["maps"]["base_udim_tile_count"] == "2"
    assert "1002" in items[0]["pbr_triangles"][0]["maps"]["base_udim_tiles"]
    assert items[0]["color_management"]["schema"] == "tigerstudio.ar_pbr.color_management.v1"

    metrics = compare_image_arrays(
        scene["base_frame"],
        np.zeros_like(scene["base_frame"]),
        threshold=12,
    )
    assert metrics["changed_pixels"] > 0
    assert metrics["mean_abs_diff"] > 0.0


def test_ar_pbr_golden_scene_packet_only_report_and_baseline(tmp_path):
    from tools.qa_ar_pbr_golden_scene import run_ar_pbr_golden_scene_qa

    baseline_dir = tmp_path / "baseline"
    first = run_ar_pbr_golden_scene_qa(
        out=tmp_path / "first.json",
        out_dir=tmp_path / "actual_first",
        baseline_dir=baseline_dir,
        update_baseline=True,
        width=128,
        height=80,
        render_live_preview=False,
        render_full_gpu=False,
    )

    assert first["ok"] is True
    assert (baseline_dir / "packet_export.png").is_file()
    assert first["checks"]["packet_export_pbr_sampled"] is True
    assert first["checks"]["packet_export_tone_mapping_agx"] is True
    assert first["checks"]["packet_export_hybrid_accumulation"] is True
    assert first["checks"]["packet_export_diffuse_specular_gi"] is True
    assert first["checks"]["packet_export_denoise"] is True
    assert first["checks"]["packet_export_ray_gi_detail"] is True
    assert first["checks"]["packet_export_screen_ao"] is True
    assert first["checks"]["packet_export_refraction"] is True
    assert first["checks"]["packet_export_clearcoat"] is True
    assert first["checks"]["packet_export_parallax"] is True
    assert first["checks"]["packet_export_displacement"] is True
    assert first["checks"]["packet_export_bevel_shader"] is True
    assert first["checks"]["packet_export_material_layering"] is True
    assert first["checks"]["packet_export_udim_tiles"] is True
    assert first["checks"]["packet_export_triplanar_projection"] is True
    assert first["checks"]["packet_export_subsurface_scattering"] is True
    assert first["checks"]["packet_export_hair_groom_shading"] is True
    assert first["checks"]["packet_export_cloth_sheen"] is True
    assert first["checks"]["packet_export_glint_sparkle"] is True
    assert first["checks"]["packet_export_caustics"] is True
    assert first["checks"]["packet_export_anisotropic_material"] is True
    assert first["checks"]["packet_export_microsurface"] is True
    assert first["checks"]["packet_export_depth_of_field"] is True
    assert first["checks"]["packet_export_post_effects"] is True
    assert first["checks"]["packet_export_lens_effects"] is True
    assert first["checks"]["packet_export_lens_flare"] is True
    assert first["checks"]["packet_export_motion_blur"] is True
    assert first["checks"]["packet_export_render_passes"] is True
    assert first["checks"]["packet_export_render_pass_data"] is True
    assert "render_pass_normal" in first["images"]
    assert first["metrics"]["packet_export_vs_base"]["changed_pixels"] >= 120

    second = run_ar_pbr_golden_scene_qa(
        out=tmp_path / "second.json",
        out_dir=tmp_path / "actual_second",
        baseline_dir=baseline_dir,
        update_baseline=False,
        width=128,
        height=80,
        render_live_preview=False,
        render_full_gpu=False,
    )

    assert second["ok"] is True
    assert second["baseline"]["enabled"] is True
    statuses = {row["name"]: row["status"] for row in second["baseline"]["results"]}
    assert statuses["packet_export.png"] == "pass"
