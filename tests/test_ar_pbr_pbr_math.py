import numpy as np


def test_pbr_math_srgb_roundtrip_and_energy_bounds():
    from app.ar_pbr.pbr_math import (
        cook_torrance_direct,
        energy_conserving_diffuse_weight,
        fresnel_schlick,
        linear_to_srgb,
        material_f0,
        srgb_to_linear,
    )

    srgb = np.asarray([[[0.04, 0.25, 0.8], [1.0, 0.5, 0.1]]], dtype=np.float32)
    linear = srgb_to_linear(srgb)
    roundtrip = linear_to_srgb(linear)

    assert np.allclose(roundtrip, srgb, atol=0.01)

    albedo = srgb_to_linear(np.asarray([[[0.8, 0.3, 0.1]]], dtype=np.float32))
    roughness = np.asarray([[0.35]], dtype=np.float32)
    metallic = np.asarray([[0.2]], dtype=np.float32)
    reflectance = np.asarray([[0.5]], dtype=np.float32)
    f0 = material_f0(albedo, metallic, reflectance)
    fresnel = fresnel_schlick(np.asarray([[0.7]], dtype=np.float32), f0)
    kd = energy_conserving_diffuse_weight(fresnel, metallic)
    direct = cook_torrance_direct(
        albedo=albedo,
        f0=f0,
        roughness=roughness,
        metallic=metallic,
        ndotl=np.asarray([[0.8]], dtype=np.float32),
        ndotv=np.asarray([[0.75]], dtype=np.float32),
        ndoth=np.asarray([[0.9]], dtype=np.float32),
        vdoth=np.asarray([[0.85]], dtype=np.float32),
        light_strength=1.2,
        ao=np.asarray([[0.95]], dtype=np.float32),
    )

    assert np.all(f0 >= 0.0)
    assert np.all(f0 <= 1.0)
    assert np.all(kd >= 0.0)
    assert np.all(kd <= 1.0)
    assert direct.shape == (1, 1, 3)
    assert np.isfinite(direct).all()
    assert float(direct.max()) > 0.0


def test_ar_pbr_color_management_tone_mapping_contract():
    from app.ar_pbr.tone_mapping import apply_display_transform, normalize_color_management_settings

    agx = normalize_color_management_settings({
        "tone_mapping": "AgX",
        "tone_exposure": 1.25,
        "tone_white_balance": 4800,
        "tone_gamma": 2.4,
    })
    reinhard = normalize_color_management_settings({"tone_map": "reinhard"})

    assert agx["schema"] == "tigerstudio.ar_pbr.color_management.v1"
    assert agx["tone_mapping"] == "agx"
    assert agx["tone_mapping_mode"] == 1
    assert agx["tone_exposure"] == 1.25
    assert agx["tone_white_balance"] == 4800.0
    assert agx["tone_gamma"] == 2.4
    assert len(agx["tone_white_balance_rgb"]) == 3
    assert agx["render_pass_safe"] is True
    assert agx["alpha_policy"] == "preserve_linear_alpha"
    assert reinhard["tone_mapping_mode"] == 2

    rgb = np.asarray([[[0.25, 1.5, 6.0]]], dtype=np.float32)
    mapped_agx = apply_display_transform(rgb, agx)
    mapped_reinhard = apply_display_transform(rgb, reinhard)

    assert mapped_agx.shape == rgb.shape
    assert np.isfinite(mapped_agx).all()
    assert np.all(mapped_agx >= 0.0)
    assert np.all(mapped_agx <= 1.0)
    assert not np.allclose(mapped_agx, mapped_reinhard)


def test_ar_pbr_hybrid_rendering_gi_denoise_contract():
    from app.ar_pbr.hybrid_rendering import (
        apply_hybrid_gi,
        denoise_float_rgb,
        normalize_hybrid_render_settings,
    )

    cfg = normalize_hybrid_render_settings({
        "hybrid_accumulation": True,
        "accumulation_samples": 12,
        "diffuse_gi_strength": 0.4,
        "specular_gi_strength": 0.25,
        "denoise_strength": 0.5,
    })

    assert cfg["schema"] == "tigerstudio.ar_pbr.hybrid_rendering.v1"
    assert cfg["enabled"] is True
    assert cfg["mode"] == "hybrid"
    assert cfg["sample_count"] == 12
    assert cfg["sample_gain"] > 0.0
    assert cfg["diffuse_gi_strength"] == 0.4
    assert cfg["specular_gi_strength"] == 0.25
    assert cfg["denoise_strength"] == 0.5
    assert normalize_hybrid_render_settings(cfg)["enabled"] is True

    rgb = np.full((3, 3, 3), 0.12, dtype=np.float32)
    albedo = np.full((3, 3, 3), 0.35, dtype=np.float32)
    env = np.full((3, 3, 3), 0.5, dtype=np.float32)
    scalar = np.full((3, 3), 0.45, dtype=np.float32)
    fresnel = np.full((3, 3, 3), 0.08, dtype=np.float32)
    out = apply_hybrid_gi(
        rgb,
        albedo=albedo,
        diffuse_env=env,
        spec_env=env,
        diffuse_weight=np.full((3, 3, 3), 0.75, dtype=np.float32),
        fresnel=fresnel,
        roughness=scalar,
        metallic=np.full((3, 3), 0.1, dtype=np.float32),
        ao=np.ones((3, 3), dtype=np.float32),
        settings=cfg,
    )

    assert out.shape == rgb.shape
    assert float(out.mean()) > float(rgb.mean())

    noisy = rgb.copy()
    noisy[1, 1] = 0.9
    denoised = denoise_float_rgb(noisy, np.ones((3, 3), dtype=np.float32), cfg)
    assert denoised.shape == noisy.shape
    assert float(denoised[1, 1].mean()) < float(noisy[1, 1].mean())


def test_ar_pbr_transmission_refraction_contract():
    from app.ar_pbr.transmission import (
        apply_screen_space_refraction,
        normalize_transmission_settings,
    )

    cfg = normalize_transmission_settings({
        "transmission": 0.6,
        "refraction_strength": 0.5,
        "refraction_depth_px": 4.0,
        "ior": 1.52,
        "thickness": 0.25,
        "absorption_color": [0.8, 0.95, 1.0],
        "absorption_distance": 1.5,
        "roughness_blur_strength": 0.3,
    })

    assert cfg["schema"] == "tigerstudio.ar_pbr.transmission.v1"
    assert cfg["enabled"] is True
    assert cfg["mode"] == "transmission"
    assert cfg["transmission"] == 0.6
    assert cfg["refraction_strength"] == 0.5
    assert cfg["ior"] == 1.52
    assert normalize_transmission_settings(cfg)["enabled"] is True

    rgb = np.full((5, 5, 3), 0.12, dtype=np.float32)
    background = np.zeros((5, 5, 4), dtype=np.float32)
    background[:, :, 0] = np.linspace(0.0, 1.0, 5, dtype=np.float32)[None, :]
    background[:, :, 1] = 0.35
    background[:, :, 2] = 0.85
    background[:, :, 3] = 1.0
    nx = np.ones((5, 5), dtype=np.float32)
    ny = np.zeros((5, 5), dtype=np.float32)
    roughness = np.full((5, 5), 0.25, dtype=np.float32)

    refracted = apply_screen_space_refraction(
        rgb,
        alpha=np.ones((5, 5), dtype=np.float32),
        background_rgba=background,
        normal_xy=(nx, ny),
        roughness=roughness,
        settings=cfg,
    )

    assert refracted.shape == rgb.shape
    assert np.isfinite(refracted).all()
    assert not np.allclose(refracted, rgb)
    assert float(refracted[:, :, 2].mean()) > float(rgb[:, :, 2].mean())


def test_ar_pbr_clearcoat_layer_contract():
    from app.ar_pbr.clearcoat import apply_clearcoat_layer, normalize_clearcoat_settings

    cfg = normalize_clearcoat_settings({
        "clearcoat_strength": 0.55,
        "clearcoat_roughness": 0.09,
        "clearcoat_ior": 1.56,
        "clearcoat_tint": [1.0, 0.94, 0.88],
    })

    assert cfg["schema"] == "tigerstudio.ar_pbr.clearcoat.v1"
    assert cfg["enabled"] is True
    assert cfg["mode"] == "clearcoat"
    assert cfg["strength"] == 0.55
    assert cfg["roughness"] == 0.09
    assert cfg["ior"] == 1.56
    assert cfg["f0"] > 0.0
    assert normalize_clearcoat_settings(cfg)["enabled"] is True

    rgb = np.full((3, 3, 3), 0.16, dtype=np.float32)
    coat = apply_clearcoat_layer(
        rgb,
        spec_env=np.full((3, 3, 3), 0.7, dtype=np.float32),
        ndotv=np.full((3, 3), 0.75, dtype=np.float32),
        ndotl=np.full((3, 3), 0.8, dtype=np.float32),
        ndoth=np.full((3, 3), 0.9, dtype=np.float32),
        vdoth=np.full((3, 3), 0.85, dtype=np.float32),
        roughness=np.full((3, 3), 0.35, dtype=np.float32),
        metallic=np.zeros((3, 3), dtype=np.float32),
        ao=np.ones((3, 3), dtype=np.float32),
        direct_strength=1.1,
        settings=cfg,
    )

    assert coat.shape == rgb.shape
    assert np.isfinite(coat).all()
    assert float(coat.mean()) > float(rgb.mean())


def test_ar_pbr_parallax_uv_contract():
    from app.ar_pbr.parallax import apply_parallax_uv, normalize_parallax_settings

    cfg = normalize_parallax_settings({
        "displacement": {
            "enabled": True,
            "strength": 0.6,
            "depth": 0.05,
            "center": 0.5,
            "steps": 5,
        }
    })

    assert cfg["schema"] == "tigerstudio.ar_pbr.parallax.v1"
    assert cfg["enabled"] is True
    assert cfg["mode"] == "parallax"
    assert cfg["strength"] == 0.6
    assert cfg["depth"] == 0.05
    assert cfg["center"] == 0.5
    assert cfg["steps"] == 5
    assert cfg["silhouette_policy"] == "no_geometry_silhouette_displacement"
    assert normalize_parallax_settings(cfg)["enabled"] is True

    u = np.full((2, 2), 0.5, dtype=np.float32)
    v = np.full((2, 2), 0.5, dtype=np.float32)
    height = np.asarray([[0.2, 0.8], [0.5, 1.0]], dtype=np.float32)
    out_u, out_v = apply_parallax_uv(
        u,
        v,
        height=height,
        tangent_view_xy=(
            np.ones((2, 2), dtype=np.float32),
            np.ones((2, 2), dtype=np.float32) * 0.5,
        ),
        settings=cfg,
    )

    assert out_u.shape == u.shape
    assert out_v.shape == v.shape
    assert float(out_u[0, 1]) > float(u[0, 1])
    assert float(out_v[0, 1]) < float(v[0, 1])
    assert np.allclose(out_u[1, 0], u[1, 0])


def test_ar_pbr_bevel_shader_normal_contract():
    from app.ar_pbr.bevel import apply_bevel_normal, bevel_edge_mask, normalize_bevel_settings

    cfg = normalize_bevel_settings({
        "rounded_edges": {
            "enabled": True,
            "strength": 0.58,
            "radius": 0.06,
            "edge_width": 0.12,
            "samples": 5,
        }
    })

    assert cfg["schema"] == "tigerstudio.ar_pbr.bevel.v1"
    assert cfg["enabled"] is True
    assert cfg["mode"] == "bevel"
    assert cfg["strength"] == 0.58
    assert cfg["radius"] == 0.06
    assert cfg["edge_width"] == 0.12
    assert cfg["samples"] == 5
    assert cfg["geometry_policy"] == "no_topology_bevel"
    assert normalize_bevel_settings(cfg)["enabled"] is True

    w0 = np.asarray([[0.01, 0.33], [0.80, 0.10]], dtype=np.float32)
    w1 = np.asarray([[0.80, 0.34], [0.10, 0.80]], dtype=np.float32)
    w2 = 1.0 - w0 - w1
    mask = bevel_edge_mask(w0, w1, w2, cfg)
    assert float(mask[0, 0]) > float(mask[0, 1])

    nx = np.zeros((2, 2), dtype=np.float32)
    ny = np.zeros((2, 2), dtype=np.float32)
    nz = np.ones((2, 2), dtype=np.float32)
    out = apply_bevel_normal(
        nx,
        ny,
        nz,
        barycentric=(w0, w1, w2),
        tangent=(np.ones((2, 2), dtype=np.float32), np.zeros((2, 2), dtype=np.float32), np.zeros((2, 2), dtype=np.float32)),
        bitangent=(np.zeros((2, 2), dtype=np.float32), np.ones((2, 2), dtype=np.float32), np.zeros((2, 2), dtype=np.float32)),
        settings=cfg,
    )
    out_len = np.sqrt(out[0] * out[0] + out[1] * out[1] + out[2] * out[2])
    assert np.allclose(out_len, 1.0, atol=1e-5)
    assert abs(float(out[0][0, 0])) > abs(float(out[0][0, 1]))


def test_ar_pbr_material_layering_contract():
    from app.ar_pbr.material_layering import apply_material_layer, normalize_material_layering_settings

    cfg = normalize_material_layering_settings({
        "material_layer": {
            "enabled": True,
            "blend": 0.62,
            "color": [0.9, 0.35, 0.1],
            "roughness": 0.28,
            "metallic": 0.2,
            "alpha": 0.86,
            "emissive_strength": 0.15,
            "mask_strength": 0.75,
        }
    })

    assert cfg["schema"] == "tigerstudio.ar_pbr.material_layering.v1"
    assert cfg["enabled"] is True
    assert cfg["mode"] == "layered"
    assert cfg["blend"] == 0.62
    assert cfg["roughness"] == 0.28
    assert cfg["metallic"] == 0.2
    assert cfg["alpha"] == 0.86
    assert cfg["stack_policy"] == "one_layer_preview_approximation"
    assert normalize_material_layering_settings(cfg)["enabled"] is True

    albedo = np.full((2, 2, 3), 0.18, dtype=np.float32)
    roughness = np.full((2, 2), 0.65, dtype=np.float32)
    metallic = np.zeros((2, 2), dtype=np.float32)
    alpha = np.ones((2, 2), dtype=np.float32)
    emissive = np.zeros((2, 2, 3), dtype=np.float32)
    mask = np.asarray([[1.0, 0.0], [0.5, 1.0]], dtype=np.float32)

    out_albedo, out_roughness, out_metallic, out_alpha, out_emissive = apply_material_layer(
        albedo,
        roughness,
        metallic,
        alpha,
        emissive,
        mask=mask,
        settings=cfg,
    )

    assert out_albedo.shape == albedo.shape
    assert np.isfinite(out_albedo).all()
    assert float(out_albedo[0, 0, 0]) > float(albedo[0, 0, 0])
    assert float(out_roughness[0, 0]) < float(roughness[0, 0])
    assert float(out_metallic[0, 0]) > float(metallic[0, 0])
    assert float(out_alpha[0, 0]) < float(alpha[0, 0])
    assert float(out_emissive[0, 0].mean()) > 0.0
    assert np.allclose(out_albedo[0, 1], albedo[0, 1])


def test_ar_pbr_shaders_use_ggx_cook_torrance_contract():
    import app.opengl_preview as preview
    import tools.ar_pbr_gpu_window as gpu_window

    for shader in (preview._AR_PBR_TEXTURE_FRAGMENT_SHADER, gpu_window.FRAG_SHADER):
        assert "fresnel_schlick" in shader
        assert "distribution_ggx" in shader
        assert "geometry_smith" in shader
        assert "cook_torrance_direct" in shader
        assert "srgb_to_linear" in shader
        assert "linear_to_srgb" in shader
        assert "u_occlusion" in shader
        assert "u_emissive" in shader
        assert "u_opacity" in shader
        assert "u_alpha_cutoff" in shader
        assert "shadow_pcss" in shader or "pbr_shadow_pcss" in shader
        assert "u_shadow_filter_mode" in shader
        assert "u_tone_mapping_mode" in shader
        assert "u_tone_exposure" in shader
        assert "u_tone_white_balance" in shader
        assert "u_tone_gamma" in shader
        assert "apply_output_transform" in shader
        assert "u_hybrid_sample_count" in shader
        assert "u_diffuse_gi_strength" in shader
        assert "u_specular_gi_strength" in shader
        assert "diffuse_gi" in shader
        assert "specular_gi" in shader
        assert "u_transmission" in shader
        assert "u_refraction_strength" in shader
        assert "u_ior" in shader
        assert "u_absorption_color" in shader
        assert "apply_transmission_refraction" in shader
        assert "u_clearcoat_strength" in shader
        assert "u_clearcoat_roughness" in shader
        assert "u_clearcoat_ior" in shader
        assert "u_clearcoat_tint" in shader
        assert "apply_clearcoat_layer" in shader
        assert "u_parallax_strength" in shader
        assert "u_has_height" in shader
        assert "apply_parallax_uv" in shader
        assert "u_bevel_strength" in shader
        assert "u_bevel_radius" in shader
        assert "apply_bevel_normal" in shader
        assert "u_material_layer_blend" in shader
        assert "u_material_layer_color" in shader
        assert "apply_material_layer" in shader

    assert "u_shadow_light_type" in preview._AR_PBR_TEXTURE_FRAGMENT_SHADER
    assert "u_shadow_light_type" in preview._AR_PBR_TEXTURE_SHADOW_VERTEX_SHADER
    assert "uniform int u_flip_uv_v" in preview._AR_PBR_TEXTURE_FRAGMENT_SHADER
    assert "preview_albedo = pow" in preview._AR_PBR_TEXTURE_FRAGMENT_SHADER
    assert "base_visibility" in preview._AR_PBR_TEXTURE_FRAGMENT_SHADER


def test_software_renderer_uses_shared_pbr_math_contract():
    import inspect

    from app.ar_pbr import software_renderer

    source = inspect.getsource(software_renderer._shade_color)

    assert "cook_torrance_direct" in source
    assert "fresnel_schlick" in source
    assert "srgb_to_linear" in source
    assert "spec_power" not in source
