"""Deterministic AR/PBR golden-scene QA across preview/export paths."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


GOLDEN_IMAGE_NAMES = (
    "live_preview.png",
    "full_gpu_export.png",
    "packet_export.png",
)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _make_base_frame(width: int, height: int) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width]
    r = 24 + (xx / max(1, width - 1) * 54).astype(np.uint8)
    g = 32 + (yy / max(1, height - 1) * 46).astype(np.uint8)
    b = np.full((height, width), 72, dtype=np.uint8)
    frame = np.dstack([r, g, b]).astype(np.uint8)
    band = (yy > height * 0.58) & (yy < height * 0.75)
    frame[band, 0] = np.clip(frame[band, 0].astype(np.int16) + 18, 0, 255).astype(np.uint8)
    frame[band, 1] = np.clip(frame[band, 1].astype(np.int16) + 10, 0, 255).astype(np.uint8)
    return np.ascontiguousarray(frame)


def _make_depth_frame(width: int, height: int) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width]
    depth = np.full((height, width), 0.92, dtype=np.float32)
    depth += (yy.astype(np.float32) / max(1, height - 1)) * 0.05
    occluder = (
        (xx > int(width * 0.44))
        & (xx < int(width * 0.58))
        & (yy > int(height * 0.22))
        & (yy < int(height * 0.70))
    )
    depth[occluder] = 0.18
    return np.ascontiguousarray(np.clip(depth, 0.0, 1.0))


def _save_image(path: Path, arr: np.ndarray) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.asarray(arr, dtype=np.uint8), "RGB").save(path)


def _load_image(path: Path, *, size: tuple[int, int] | None = None) -> np.ndarray:
    from PIL import Image

    img = Image.open(path).convert("RGB")
    if size is not None and img.size != size:
        img = img.resize(size, Image.Resampling.BILINEAR)
    return np.asarray(img, dtype=np.uint8)


def _to_rgb_array(image: Any, *, size: tuple[int, int] | None = None) -> np.ndarray:
    from PIL import Image

    if isinstance(image, Image.Image):
        img = image.convert("RGB")
    else:
        arr = np.asarray(image)
        if arr.ndim != 3 or arr.shape[2] not in {3, 4}:
            raise ValueError("image must be HxWx3 or HxWx4")
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr[:, :, :3], "RGB")
    if size is not None and img.size != size:
        img = img.resize(size, Image.Resampling.BILINEAR)
    return np.asarray(img, dtype=np.uint8)


def _qimage_to_rgb_array(qimage: Any, *, size: tuple[int, int] | None = None) -> np.ndarray:
    from PIL import Image
    from PySide6.QtGui import QImage

    converted = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
    width = int(converted.width())
    height = int(converted.height())
    arr = np.empty((height, width, 3), dtype=np.uint8)
    for y in range(height):
        for x in range(width):
            color = converted.pixelColor(x, y)
            arr[y, x, 0] = color.red()
            arr[y, x, 1] = color.green()
            arr[y, x, 2] = color.blue()
    img = Image.fromarray(arr, "RGB")
    if size is not None and img.size != size:
        img = img.resize(size, Image.Resampling.BILINEAR)
    return np.asarray(img, dtype=np.uint8)


def compare_image_arrays(a: Any, b: Any, *, threshold: int = 12) -> dict[str, Any]:
    left = np.asarray(a, dtype=np.uint8)
    right = np.asarray(b, dtype=np.uint8)
    if left.shape != right.shape:
        raise ValueError(f"image shape mismatch: {left.shape} != {right.shape}")
    diff = np.abs(left.astype(np.int16) - right.astype(np.int16))
    per_pixel = diff.max(axis=2)
    return {
        "width": int(left.shape[1]),
        "height": int(left.shape[0]),
        "mean_abs_diff": float(diff.mean()),
        "p95_abs_diff": float(np.percentile(diff, 95)),
        "max_abs_diff": int(diff.max()),
        "changed_pixels": int((per_pixel > int(threshold)).sum()),
        "changed_ratio": float((per_pixel > int(threshold)).mean()),
        "threshold": int(threshold),
    }


def _diff_image(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16)).astype(np.uint8)
    amplified = np.clip(diff.astype(np.uint16) * 4, 0, 255).astype(np.uint8)
    return amplified


def _write_scene_textures(asset_dir: Path) -> dict[str, str]:
    from PIL import Image

    asset_dir.mkdir(parents=True, exist_ok=True)
    yy, xx = np.mgrid[0:64, 0:64]
    checker = ((xx // 8 + yy // 8) % 2).astype(np.uint8)
    base = np.zeros((64, 64, 4), dtype=np.uint8)
    base[:, :, 0] = np.where(checker == 0, 210, 72).astype(np.uint8)
    base[:, :, 1] = np.clip(120 + xx * 2, 0, 255).astype(np.uint8)
    base[:, :, 2] = np.where(checker == 0, 72, 186).astype(np.uint8)
    base[:, :, 3] = 255
    base_tile_1002 = np.zeros((64, 64, 4), dtype=np.uint8)
    base_tile_1002[:, :, 0] = np.clip(182 + yy, 0, 255).astype(np.uint8)
    base_tile_1002[:, :, 1] = np.where(checker == 0, 68, 170).astype(np.uint8)
    base_tile_1002[:, :, 2] = np.clip(38 + xx // 2, 0, 255).astype(np.uint8)
    base_tile_1002[:, :, 3] = 255

    roughness = np.clip(42 + yy * 3, 0, 255).astype(np.uint8)
    metallic = np.clip(24 + checker * 86, 0, 255).astype(np.uint8)
    specular = np.clip(150 + xx, 0, 255).astype(np.uint8)
    occlusion = np.clip(210 - (yy // 2), 0, 255).astype(np.uint8)
    opacity = np.full((64, 64), 255, dtype=np.uint8)
    opacity[:, :5] = 210
    height = np.clip(118 + np.sin(xx / 5.0) * 48 + np.cos(yy / 6.0) * 36, 0, 255).astype(np.uint8)
    normal = np.zeros((64, 64, 3), dtype=np.uint8)
    normal[:, :, 0] = np.clip(128 + np.sin(xx / 7.0) * 28, 0, 255).astype(np.uint8)
    normal[:, :, 1] = np.clip(128 + np.cos(yy / 9.0) * 20, 0, 255).astype(np.uint8)
    normal[:, :, 2] = 255
    emissive = np.zeros((64, 64, 3), dtype=np.uint8)
    emissive[:, :, 0] = np.where((xx > 42) & (yy < 20), 180, 8).astype(np.uint8)
    emissive[:, :, 1] = np.where((xx > 42) & (yy < 20), 48, 4).astype(np.uint8)

    paths = {
        "base": asset_dir / "golden_base.<UDIM>.png",
        "roughness": asset_dir / "golden_roughness.png",
        "metallic": asset_dir / "golden_metallic.png",
        "specular": asset_dir / "golden_specular.png",
        "normal": asset_dir / "golden_normal.png",
        "occlusion": asset_dir / "golden_occlusion.png",
        "emissive": asset_dir / "golden_emissive.png",
        "opacity": asset_dir / "golden_opacity.png",
        "height": asset_dir / "golden_height.png",
    }
    Image.fromarray(base, "RGBA").save(asset_dir / "golden_base.1001.png")
    Image.fromarray(base_tile_1002, "RGBA").save(asset_dir / "golden_base.1002.png")
    Image.fromarray(roughness, "L").save(paths["roughness"])
    Image.fromarray(metallic, "L").save(paths["metallic"])
    Image.fromarray(specular, "L").save(paths["specular"])
    Image.fromarray(normal, "RGB").save(paths["normal"])
    Image.fromarray(occlusion, "L").save(paths["occlusion"])
    Image.fromarray(emissive, "RGB").save(paths["emissive"])
    Image.fromarray(opacity, "L").save(paths["opacity"])
    Image.fromarray(height, "L").save(paths["height"])
    return {key: str(path) for key, path in paths.items()}


def build_ar_pbr_golden_scene(
    *,
    out_dir: Path | str,
    width: int = 160,
    height: int = 96,
) -> dict[str, Any]:
    out_root = Path(out_dir)
    texture_paths = _write_scene_textures(out_root / "assets")
    try:
        from app.ar_pbr.hdri_presets import default_hdri_path

        hdri_path = str(default_hdri_path())
    except Exception:
        hdri_path = ""

    descriptor = {
        "source_path": str(out_root / "ar_pbr_golden_scene.glb"),
        "source_ext": ".glb",
        "bounds": {"center": [0.0, -0.08, -0.02], "size": [1.4, 1.5, 0.54]},
        "geometries": [
            {
                "id": "golden_mesh",
                "name": "golden_mesh",
                "model_id": "golden_model",
                "material_id": "mat_gold",
                "vertices": [
                    [-0.70, -0.48, 0.02],
                    [0.70, -0.46, -0.03],
                    [-0.62, 0.56, 0.16],
                    [0.66, 0.52, 0.02],
                    [-0.46, -0.86, -0.18],
                    [0.50, -0.84, -0.10],
                ],
                "uvs": [
                    [0.02, 0.08],
                    [0.96, 0.10],
                    [1.08, 0.94],
                    [1.92, 0.90],
                    [0.18, 0.00],
                    [0.82, 0.02],
                ],
                "triangles": [[0, 1, 2], [2, 1, 3], [4, 5, 0], [0, 5, 1]],
                "bounds": {"center": [0.0, -0.14, -0.01], "size": [1.4, 1.42, 0.34]},
            }
        ],
        "models": [
            {
                "id": "golden_model",
                "name": "GoldenModel",
                "translation": [0.0, 0.0, 0.0],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            }
        ],
        "materials": [
            {
                "id": "mat_gold",
                "name": "GoldenPaint",
                "base_color": [1.0, 0.62, 0.28, 0.97],
                "roughness": 0.31,
                "metallic": 0.24,
                "reflectance": 0.72,
                "pbr_available": True,
                "base_texture": texture_paths["base"],
                "roughness_texture": texture_paths["roughness"],
                "metallic_texture": texture_paths["metallic"],
                "specular_texture": texture_paths["specular"],
                "normal_texture": texture_paths["normal"],
                "occlusion_texture": texture_paths["occlusion"],
                "emissive_texture": texture_paths["emissive"],
                "opacity_texture": texture_paths["opacity"],
                "height_texture": texture_paths["height"],
                "alpha_mode": "MASK",
                "alpha_cutoff": 0.08,
                "emissive_factor": [0.28, 0.08, 0.025],
            }
        ],
        "texture_count": len(texture_paths),
        "animation_count": 1,
        "animation_clips": [
            {
                "id": "golden_sway",
                "name": "golden_sway",
                "duration_ms": 1000,
                "model_curves": {
                    "golden_model": {
                        "translation": {
                            "x": [
                                {"time_ms": 0, "value": 0.0},
                                {"time_ms": 1000, "value": 1.2},
                            ],
                            "y": [
                                {"time_ms": 0, "value": 0.0},
                                {"time_ms": 1000, "value": 0.0},
                            ],
                            "z": [
                                {"time_ms": 0, "value": 0.0},
                                {"time_ms": 1000, "value": 0.0},
                            ],
                        }
                    }
                },
            }
        ],
    }
    lighting = {
        "hdri_id": "wide_street_01",
        "hdri_path": hdri_path,
        "ibl_exposure": 1.35,
        "ibl_rotation": 0.16,
        "light_azimuth": 38.0,
        "light_elevation": 47.0,
        "direct_strength": 1.05,
        "shadow_strength": 0.76,
        "self_shadow_strength": 0.58,
        "shadow_filter": "pcss",
        "shadow_light_type": "spot",
        "shadow_map_size": 1024,
        "shadow_pcf_radius": 2.4,
        "shadow_pcss_blocker_radius": 3.3,
        "shadow_bias": 0.004,
        "shadow_normal_bias": 0.006,
        "shadow_spot_inner_angle": 25.0,
        "shadow_spot_outer_angle": 50.0,
        "shadow_catcher_opacity": 0.82,
        "shadow_catcher_softness": 0.72,
        "shadow_catcher_matte_alpha": 0.12,
        "reflection_catcher_opacity": 0.62,
        "reflection_catcher_roughness": 0.70,
        "reflection_catcher_softness": 0.66,
        "contact_reflection_strength": 0.48,
        "contact_reflection_falloff": 0.62,
        "tone_mapping": "agx",
        "tone_exposure": 0.35,
        "tone_white_balance": 5600,
        "tone_gamma": 2.3,
        "hybrid_accumulation": True,
        "accumulation_samples": 16,
        "diffuse_gi_strength": 0.32,
        "specular_gi_strength": 0.18,
        "denoise_strength": 0.36,
        "denoise_radius": 1,
        "ray_gi_detail": {
            "mode": "hybrid",
            "max_bounces": 6,
            "diffuse_bounces": 3,
            "specular_bounces": 4,
            "refraction_bounces": 5,
            "direct_radiance_clamp": 1.35,
            "indirect_radiance_clamp": 0.92,
            "advanced_light_sampling": True,
            "light_sampling_mode": "mis",
            "light_sample_count": 24,
            "environment_sample_count": 48,
            "denoise_channels": ["beauty", "diffuse", "specular", "transmission"],
            "denoise_albedo_guided": True,
            "denoise_normal_guided": True,
        },
        "ao_strength": 0.38,
        "ao_radius": 4.8,
        "ao_distance": 0.58,
        "ao_color": [0.02, 0.018, 0.015],
        "ao_specular": True,
        "transmission": 0.42,
        "refraction_strength": 0.55,
        "refraction_depth_px": 8.0,
        "ior": 1.48,
        "thickness": 0.22,
        "absorption_color": [0.82, 0.95, 1.0],
        "absorption_distance": 1.6,
        "roughness_blur_strength": 0.25,
        "clearcoat_strength": 0.46,
        "clearcoat_roughness": 0.10,
        "clearcoat_ior": 1.55,
        "clearcoat_tint": [1.0, 0.96, 0.90],
        "parallax_strength": 0.50,
        "parallax_depth": 0.045,
        "parallax_center": 0.50,
        "parallax_steps": 4,
        "displacement_height_strength": 0.52,
        "displacement_height_scale": 0.052,
        "displacement_height_center": 0.48,
        "vector_displacement_strength": 0.20,
        "vector_displacement_space": "tangent",
        "displacement_subdivision_mode": "adaptive",
        "displacement_max_offset": 0.10,
        "displacement_parallax_fallback": True,
        "bevel_strength": 0.44,
        "bevel_radius": 0.055,
        "bevel_edge_width": 0.09,
        "bevel_samples": 4,
        "material_layer_blend": 0.38,
        "material_layer_color": [0.95, 0.42, 0.16],
        "material_layer_roughness": 0.32,
        "material_layer_metallic": 0.18,
        "material_layer_alpha": 0.92,
        "material_layer_emissive_strength": 0.08,
        "material_layer_mask_strength": 0.85,
        "subsurface_strength": 0.34,
        "subsurface_color": [1.0, 0.58, 0.36],
        "subsurface_radius": 0.46,
        "subsurface_power": 2.4,
        "subsurface_wrap": 0.52,
        "subsurface_thickness": 0.16,
        "hair_groom_strength": 0.37,
        "hair_groom_tint": [1.0, 0.86, 0.52],
        "hair_primary_shift": 0.09,
        "hair_secondary_shift": -0.20,
        "hair_primary_roughness": 0.22,
        "hair_secondary_roughness": 0.46,
        "hair_secondary_strength": 0.55,
        "hair_anisotropy": 0.82,
        "hair_rim_strength": 0.20,
        "cloth_sheen_strength": 0.36,
        "cloth_sheen_color": [0.84, 0.90, 1.0],
        "cloth_sheen_roughness": 0.62,
        "cloth_sheen_edge_tint": [0.68, 0.80, 1.0],
        "cloth_sheen_fiber_strength": 0.28,
        "cloth_sheen_wrap": 0.36,
        "cloth_sheen_retroreflection": 0.31,
        "glint_strength": 0.34,
        "glint_color": [1.0, 0.94, 0.72],
        "glint_density": 0.46,
        "glint_scale": 42.0,
        "glint_threshold": 0.42,
        "glint_sharpness": 16.0,
        "glint_roughness_jitter": 0.58,
        "caustics_strength": 0.40,
        "caustics_quality": "high",
        "caustics_sample_count": 24,
        "caustics_scale": 36.0,
        "caustics_focus": 0.70,
        "caustics_radius": 0.84,
        "caustics_threshold": 0.10,
        "caustics_tint": [1.0, 0.91, 0.60],
        "caustics_seed": 37,
        "anisotropic_strength": 0.42,
        "anisotropy": 0.58,
        "anisotropic_rotation": 32.0,
        "anisotropic_tangent_weight": 0.76,
        "clearcoat_anisotropy": 0.30,
        "thin_film_enabled": True,
        "thin_film_strength": 0.50,
        "thin_film_thickness_nm": 510.0,
        "thin_film_ior": 1.40,
        "thin_film_tint": [1.0, 0.84, 0.58],
        "newton_rings_strength": 0.18,
        "newton_rings_scale": 21.0,
        "anisotropic_seed": 43,
        "detail_normal_strength": 0.46,
        "detail_normal_scale": 48.0,
        "detail_normal_blend": "reoriented",
        "detail_normal_seed": 31,
        "micro_roughness_strength": 0.36,
        "micro_roughness_scale": 54.0,
        "micro_roughness_contrast": 0.42,
        "gloss_variation_strength": 0.26,
        "gloss_bias": 0.07,
        "specular_micro_occlusion": 0.20,
        "depth_of_field_strength": 0.62,
        "dof_focus_depth": 0.12,
        "dof_focus_range": 0.03,
        "dof_max_blur_px": 4.0,
        "dof_near_blur": 0.55,
        "dof_far_blur": 1.0,
        "bloom_strength": 0.32,
        "bloom_radius": 2.8,
        "bloom_threshold": 0.42,
        "vignette_strength": 0.22,
        "vignette_radius": 0.66,
        "vignette_feather": 0.34,
        "grain_strength": 0.035,
        "grain_scale": 72.0,
        "grain_seed": 17,
        "sharpen_strength": 0.24,
        "sharpen_radius": 0.9,
        "lens_distortion_strength": 0.16,
        "lens_distortion_k2": 0.035,
        "chromatic_aberration_strength": 0.46,
        "chromatic_aberration_px": 2.2,
        "lens_edge_falloff": 1.15,
        "lens_flare_strength": 0.36,
        "lens_flare_threshold": 0.36,
        "lens_flare_radius": 4.8,
        "lens_flare_ghost_count": 4,
        "lens_flare_ghost_spacing": 0.38,
        "lens_flare_tint": [1.0, 0.86, 0.54],
        "aperture_flare_strength": 0.28,
        "aperture_flare_blades": 6,
        "aperture_flare_rotation_deg": 24.0,
        "aperture_flare_radius": 22.0,
        "lens_dirt_strength": 0.17,
        "lens_dirt_density": 0.44,
        "lens_dirt_scale": 86.0,
        "lens_scratch_strength": 0.13,
        "lens_scratch_density": 0.28,
        "lens_scratch_length": 0.68,
        "lens_flare_seed": 29,
        "motion_blur_enabled": True,
        "motion_blur_samples": 5,
        "motion_blur_shutter_angle": 240.0,
        "motion_blur_strength": 1.0,
        "render_passes_enabled": True,
        "render_pass_names": [
            "beauty",
            "alpha_mask",
            "depth",
            "normal",
            "position",
            "material_id",
            "object_id",
            "ambient_occlusion",
            "direct_lighting",
            "indirect_lighting",
            "diffuse",
            "specular",
            "albedo",
            "emissive",
            "roughness",
            "metallic",
            "transparency",
            "shadow",
            "reflection",
        ],
        "triplanar_strength": 1.0,
        "triplanar_scale": 1.45,
        "triplanar_blend_sharpness": 4.25,
        "triplanar_offset": [0.05, 0.12, 0.18],
        "ground_height": -0.58,
    }
    track = {
        "id": "ar_pbr_golden_scene",
        "type": "ar_pbr_object",
        "asset_path": str(out_root / "ar_pbr_golden_scene.glb"),
        "start_ms": 0,
        "end_ms": 1000,
        "transform": {
            "position": [0.04, 0.05, 0.0],
            "rotation": [8.0, -16.0, 3.0],
            "scale": [2.8, 2.45, 1.85],
        },
        "occlusion": True,
        "shadow_catcher": True,
        "reflection_catcher": True,
        "render": {
            "render_profile": "marmoset_pbr",
            "lighting": lighting,
        },
        "animation": {
            "clip": "golden_sway",
            "auto_play": True,
            "loop": True,
            "speed": 4.0,
        },
    }
    camera_solution = {
        "id": "ar_pbr_golden_camera",
        "frame_size": [int(width), int(height)],
        "intrinsics": {
            "fx": float(height) * 1.05,
            "fy": float(height) * 1.05,
            "cx": float(width) * 0.50,
            "cy": float(height) * 0.52,
        },
    }
    settings = {
        "asset_descriptors": {
            str(track["id"]): descriptor,
            str(track["asset_path"]): descriptor,
            "default": descriptor,
        },
        "ar_pbr_render_profile": "marmoset_pbr",
        "camera_z": 3.20,
        "occlusion_tolerance": 0.025,
        "gpu_triangle_limit": 4096,
        "packet_ssaa": 2,
        "frame_duration_ms": 1000.0 / 60.0,
        "enable_shadow_map": True,
        "texture_max_size": 512,
        "model_view": {
            "auto_fit": True,
            "fit_padding": 0.16,
            "draw_ground": True,
            "transparent_background": True,
            "show_environment_background": False,
            "camera_z": 4.2,
            "zoom": 1.0,
        },
    }
    return {
        "schema": "tigerstudio.ar_pbr.golden_scene.v1",
        "name": "ar_pbr_golden_scene",
        "frame_size": [int(width), int(height)],
        "base_frame": _make_base_frame(width, height),
        "depth_frame": _make_depth_frame(width, height),
        "time_ms": 40,
        "ar_tracks": [track],
        "camera_solution": camera_solution,
        "settings": settings,
        "descriptor": descriptor,
        "texture_paths": texture_paths,
        "lighting": lighting,
    }


def _process_events(app: Any, count: int = 8) -> None:
    from PySide6.QtTest import QTest

    for _ in range(max(1, int(count))):
        app.processEvents()
        QTest.qWait(20)


def _grab_nonempty_framebuffer(widget: Any, app: Any, *, attempts: int = 8) -> Any:
    image = None
    for _ in range(max(1, int(attempts))):
        app.processEvents()
        try:
            widget.repaint()
        except Exception:
            pass
        _process_events(app, 1)
        try:
            image = widget.grabFramebuffer()
        except Exception:
            image = None
        if image is not None and int(image.width()) > 0 and int(image.height()) > 0:
            return image
    return image


def render_live_preview_scene(scene: Mapping[str, Any], *, visible: bool = False) -> tuple[np.ndarray, dict[str, Any]]:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QSurfaceFormat
    from PySide6.QtWidgets import QApplication

    from app.ar_pbr.gpu_preview import build_gpu_preview_items
    from app.opengl_preview import OpenGLPreviewWidget

    width, height = (int(scene["frame_size"][0]), int(scene["frame_size"][1]))
    items, packet_diag = build_gpu_preview_items(
        frame_size=(width, height),
        time_ms=int(scene["time_ms"]),
        ar_tracks=list(scene["ar_tracks"]),
        camera_solution=scene["camera_solution"],
        depth_frame=scene["depth_frame"],
        settings=scene["settings"],
    )

    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(24)
    fmt.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication.instance() or QApplication(["ar_pbr_golden_scene_qa"])
    widget = OpenGLPreviewWidget()
    widget.setFixedSize(width, height)
    widget.resize(width, height)
    widget.setWindowTitle("Tiger Studio AR/PBR Golden Scene QA")
    if not visible:
        widget.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        widget.move(16, 16)
    widget.show()
    _process_events(app)
    try:
        widget.set_clip_effects(None)
        widget.set_spine_overlay_items([])
        widget.set_mmd_overlay_items([])
        widget.set_ar_pbr_overlay_items(items)
        widget.update_frame(np.ascontiguousarray(scene["base_frame"]), None)
        _process_events(app)
        image = _grab_nonempty_framebuffer(widget, app, attempts=10)
        if image is None or int(image.width()) <= 0 or int(image.height()) <= 0:
            raise RuntimeError("OpenGL framebuffer capture returned an empty image")
        arr = _qimage_to_rgb_array(image, size=(width, height))
        diag = {
            "ok": True,
            "mode": "live_gl_preview",
            "fallback": False,
            "rendered_track_count": int(packet_diag.get("rendered_track_count", 0) or 0),
            "packet_builder": packet_diag,
            "item_count": len(items),
            "framebuffer_size": [int(image.width()), int(image.height())],
        }
        return arr, diag
    except Exception as exc:
        return np.asarray(scene["base_frame"], dtype=np.uint8).copy(), {
            "ok": False,
            "mode": "live_gl_preview",
            "fallback": True,
            "errors": [f"{type(exc).__name__}: {exc}"],
            "packet_builder": packet_diag,
            "item_count": len(items),
        }
    finally:
        widget.hide()
        widget.deleteLater()
        _process_events(app, 2)


def render_packet_export_scene(scene: Mapping[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    from app.ar_pbr.export_packet_renderer import render_gpu_packet_export_frame

    width, height = (int(scene["frame_size"][0]), int(scene["frame_size"][1]))
    out, diag = render_gpu_packet_export_frame(
        scene["base_frame"],
        time_ms=int(scene["time_ms"]),
        ar_tracks=list(scene["ar_tracks"]),
        camera_solution=scene["camera_solution"],
        depth_frame=scene["depth_frame"],
        settings=scene["settings"],
    )
    return _to_rgb_array(out, size=(width, height)), dict(diag or {})


def render_full_gpu_export_scene(scene: Mapping[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    from app.ar_pbr.export_packet_renderer import render_offscreen_gpu_export_frame

    width, height = (int(scene["frame_size"][0]), int(scene["frame_size"][1]))
    out, diag = render_offscreen_gpu_export_frame(
        scene["base_frame"],
        time_ms=int(scene["time_ms"]),
        ar_tracks=list(scene["ar_tracks"]),
        camera_solution=scene["camera_solution"],
        depth_frame=scene["depth_frame"],
        settings=scene["settings"],
    )
    return _to_rgb_array(out, size=(width, height)), dict(diag or {})


def _baseline_compare(
    *,
    name: str,
    actual_path: Path,
    baseline_dir: Path | None,
    update_baseline: bool,
    max_mean_abs_diff: float,
    max_p95_abs_diff: float,
) -> dict[str, Any]:
    if baseline_dir is None:
        return {"name": name, "enabled": False, "status": "disabled", "ok": True}
    baseline_path = baseline_dir / name
    if update_baseline:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(actual_path, baseline_path)
        return {
            "name": name,
            "enabled": True,
            "status": "updated",
            "ok": True,
            "baseline": str(baseline_path),
            "actual": str(actual_path),
        }
    if not baseline_path.is_file():
        return {
            "name": name,
            "enabled": True,
            "status": "missing",
            "ok": True,
            "baseline": str(baseline_path),
            "actual": str(actual_path),
        }
    actual = _load_image(actual_path)
    baseline = _load_image(baseline_path, size=(actual.shape[1], actual.shape[0]))
    metrics = compare_image_arrays(actual, baseline, threshold=8)
    ok = (
        float(metrics["mean_abs_diff"]) <= float(max_mean_abs_diff)
        and float(metrics["p95_abs_diff"]) <= float(max_p95_abs_diff)
    )
    return {
        "name": name,
        "enabled": True,
        "status": "pass" if ok else "fail",
        "ok": bool(ok),
        "baseline": str(baseline_path),
        "actual": str(actual_path),
        "metrics": metrics,
        "thresholds": {
            "max_mean_abs_diff": float(max_mean_abs_diff),
            "max_p95_abs_diff": float(max_p95_abs_diff),
        },
    }


def _diagnostic_contract_checks(
    *,
    live_diag: Mapping[str, Any] | None,
    packet_diag: Mapping[str, Any] | None,
    full_diag: Mapping[str, Any] | None,
    require_live_preview: bool = True,
    require_full_gpu: bool = True,
) -> dict[str, bool]:
    live_packet_raw = live_diag.get("packet_builder") if isinstance(live_diag, Mapping) else {}
    live_packet = live_packet_raw if isinstance(live_packet_raw, Mapping) else {}
    packet_builder_raw = packet_diag.get("packet_builder") if isinstance(packet_diag, Mapping) else {}
    packet_builder = packet_builder_raw if isinstance(packet_builder_raw, Mapping) else {}
    packet_color_raw = packet_diag.get("pbr_color_management") if isinstance(packet_diag, Mapping) else {}
    packet_color = packet_color_raw if isinstance(packet_color_raw, Mapping) else {}
    packet_ray_gi_raw = packet_diag.get("pbr_ray_gi_detail") if isinstance(packet_diag, Mapping) else {}
    packet_ray_gi = packet_ray_gi_raw if isinstance(packet_ray_gi_raw, Mapping) else {}
    packet_caustics_raw = packet_diag.get("pbr_caustics_rendering") if isinstance(packet_diag, Mapping) else {}
    packet_caustics = packet_caustics_raw if isinstance(packet_caustics_raw, Mapping) else {}
    packet_anisotropic_raw = packet_diag.get("pbr_anisotropic_rendering") if isinstance(packet_diag, Mapping) else {}
    packet_anisotropic = packet_anisotropic_raw if isinstance(packet_anisotropic_raw, Mapping) else {}
    packet_displacement_raw = packet_diag.get("pbr_displacement_rendering") if isinstance(packet_diag, Mapping) else {}
    packet_displacement = packet_displacement_raw if isinstance(packet_displacement_raw, Mapping) else {}
    packet_micro_raw = packet_diag.get("pbr_microsurface_rendering") if isinstance(packet_diag, Mapping) else {}
    packet_micro = packet_micro_raw if isinstance(packet_micro_raw, Mapping) else {}
    packet_passes_raw = packet_diag.get("pbr_render_passes") if isinstance(packet_diag, Mapping) else {}
    packet_passes = packet_passes_raw if isinstance(packet_passes_raw, Mapping) else {}
    packet_pass_rows = packet_passes.get("passes") if isinstance(packet_passes.get("passes"), Mapping) else {}
    full_rows = full_diag.get("rows") if isinstance(full_diag, Mapping) and isinstance(full_diag.get("rows"), list) else []
    full_row = full_rows[0] if full_rows and isinstance(full_rows[0], Mapping) else {}
    full_catcher = full_row.get("catcher") if isinstance(full_row.get("catcher"), Mapping) else {}
    full_color = full_row.get("color_management") if isinstance(full_row.get("color_management"), Mapping) else {}
    full_hybrid = full_row.get("hybrid_rendering") if isinstance(full_row.get("hybrid_rendering"), Mapping) else {}
    full_ray_gi = full_row.get("ray_gi_detail") if isinstance(full_row.get("ray_gi_detail"), Mapping) else {}
    full_ao = full_row.get("ambient_occlusion_rendering") if isinstance(full_row.get("ambient_occlusion_rendering"), Mapping) else {}
    full_transmission = full_row.get("transmission_rendering") if isinstance(full_row.get("transmission_rendering"), Mapping) else {}
    full_clearcoat = full_row.get("clearcoat_rendering") if isinstance(full_row.get("clearcoat_rendering"), Mapping) else {}
    full_parallax = full_row.get("parallax_rendering") if isinstance(full_row.get("parallax_rendering"), Mapping) else {}
    full_displacement = full_row.get("displacement_rendering") if isinstance(full_row.get("displacement_rendering"), Mapping) else {}
    full_bevel = full_row.get("bevel_rendering") if isinstance(full_row.get("bevel_rendering"), Mapping) else {}
    full_material_layer = full_row.get("material_layering") if isinstance(full_row.get("material_layering"), Mapping) else {}
    full_subsurface = full_row.get("subsurface_rendering") if isinstance(full_row.get("subsurface_rendering"), Mapping) else {}
    full_hair = full_row.get("hair_groom_rendering") if isinstance(full_row.get("hair_groom_rendering"), Mapping) else {}
    full_cloth = full_row.get("cloth_sheen_rendering") if isinstance(full_row.get("cloth_sheen_rendering"), Mapping) else {}
    full_glint = full_row.get("glint_sparkle_rendering") if isinstance(full_row.get("glint_sparkle_rendering"), Mapping) else {}
    full_caustics = full_row.get("caustics_rendering") if isinstance(full_row.get("caustics_rendering"), Mapping) else {}
    full_anisotropic = full_row.get("anisotropic_rendering") if isinstance(full_row.get("anisotropic_rendering"), Mapping) else {}
    full_micro = full_row.get("microsurface_rendering") if isinstance(full_row.get("microsurface_rendering"), Mapping) else {}
    full_dof = full_row.get("depth_of_field_rendering") if isinstance(full_row.get("depth_of_field_rendering"), Mapping) else {}
    full_post = full_row.get("post_effects_rendering") if isinstance(full_row.get("post_effects_rendering"), Mapping) else {}
    full_lens = full_row.get("lens_effects_rendering") if isinstance(full_row.get("lens_effects_rendering"), Mapping) else {}
    full_flare = full_row.get("lens_flare_rendering") if isinstance(full_row.get("lens_flare_rendering"), Mapping) else {}
    full_motion = full_row.get("motion_blur") if isinstance(full_row.get("motion_blur"), Mapping) else {}
    full_udim = full_row.get("udim_rendering") if isinstance(full_row.get("udim_rendering"), Mapping) else {}
    full_triplanar = full_row.get("triplanar_rendering") if isinstance(full_row.get("triplanar_rendering"), Mapping) else {}
    full_shadow = full_row.get("shadow_filter") if isinstance(full_row.get("shadow_filter"), Mapping) else {}
    return {
        "live_preview_packet_pbr_triangles": (
            int(live_packet.get("pbr_triangle_count", 0) or 0) >= 1
            if require_live_preview else True
        ),
        "live_preview_color_management_agx": (
            str((live_packet.get("gpu_renderer") or {}).get("color_management") or "") == "agx"
            if require_live_preview else True
        ),
        "packet_export_pbr_sampled": int(packet_diag.get("pbr_sampled_triangle_count", 0) or 0) >= 1 if isinstance(packet_diag, Mapping) else False,
        "packet_export_packet_builder_pbr": int(packet_builder.get("pbr_triangle_count", 0) or 0) >= 1,
        "packet_export_tone_mapping_agx": str(packet_color.get("tone_mapping") or "") == "agx",
        "packet_export_hybrid_accumulation": bool((packet_diag.get("pbr_hybrid_rendering") or {}).get("enabled")) if isinstance(packet_diag, Mapping) else False,
        "packet_export_diffuse_specular_gi": (
            bool(packet_diag.get("pbr_diffuse_gi")) and bool(packet_diag.get("pbr_specular_gi"))
            if isinstance(packet_diag, Mapping) else False
        ),
        "packet_export_denoise": bool(packet_diag.get("pbr_denoise_applied")) if isinstance(packet_diag, Mapping) else False,
        "live_preview_ray_gi_detail": (
            str((live_packet.get("gpu_renderer") or {}).get("ray_gi_detail") or "") == "hybrid"
            and int((live_packet.get("gpu_renderer") or {}).get("ray_gi_bounces", 0) or 0) == 6
            and str((live_packet.get("gpu_renderer") or {}).get("ray_gi_light_sampling") or "") == "mis"
            if require_live_preview else True
        ),
        "packet_export_ray_gi_detail": (
            str(packet_ray_gi.get("schema") or "") == "tigerstudio.ar_pbr.ray_gi_detail.v1"
            and bool(packet_ray_gi.get("enabled"))
            and int(packet_ray_gi.get("max_bounces", 0) or 0) == 6
            and int(packet_ray_gi.get("diffuse_bounces", 0) or 0) == 3
            and int(packet_ray_gi.get("specular_bounces", 0) or 0) == 4
            and int(packet_ray_gi.get("refraction_bounces", 0) or 0) == 5
            and bool(packet_diag.get("pbr_ray_gi_direct_clamp_applied"))
            and bool(packet_diag.get("pbr_ray_gi_indirect_clamp_applied"))
            and str(packet_ray_gi.get("light_sampling_mode") or "") == "mis"
            and int(packet_ray_gi.get("light_sample_count", 0) or 0) == 24
            and "transmission" in list(packet_ray_gi.get("denoise_channels") or [])
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_screen_ao": (
            str((live_packet.get("gpu_renderer") or {}).get("ambient_occlusion_rendering") or "") == "screen"
            if require_live_preview else True
        ),
        "packet_export_screen_ao": (
            bool(packet_diag.get("pbr_ambient_occlusion_applied"))
            and bool((packet_diag.get("pbr_ambient_occlusion_rendering") or {}).get("enabled"))
            and int(packet_diag.get("pbr_ambient_occlusion_changed_pixels", 0) or 0) > 0
            and float((packet_diag.get("pbr_ambient_occlusion_pass") or {}).get("mean", 1.0) or 1.0) < 1.0
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_transmission_refraction": (
            str((live_packet.get("gpu_renderer") or {}).get("transmission_rendering") or "") in {"transmission", "refraction", "glass"}
            if require_live_preview else True
        ),
        "packet_export_refraction": (
            bool(packet_diag.get("pbr_refraction_applied"))
            and bool((packet_diag.get("pbr_transmission_rendering") or {}).get("enabled"))
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_clearcoat": (
            str((live_packet.get("gpu_renderer") or {}).get("clearcoat_rendering") or "") == "clearcoat"
            if require_live_preview else True
        ),
        "packet_export_clearcoat": (
            bool(packet_diag.get("pbr_clearcoat_applied"))
            and bool((packet_diag.get("pbr_clearcoat_rendering") or {}).get("enabled"))
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_parallax": (
            str((live_packet.get("gpu_renderer") or {}).get("parallax_rendering") or "") == "parallax"
            if require_live_preview else True
        ),
        "packet_export_parallax": (
            bool(packet_diag.get("pbr_parallax_applied"))
            and bool((packet_diag.get("pbr_parallax_rendering") or {}).get("enabled"))
            and int(packet_diag.get("pbr_parallax_pixels", 0) or 0) > 0
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_displacement_contract": (
            str((live_packet.get("gpu_renderer") or {}).get("displacement_rendering") or "") == "displacement"
            and str((live_packet.get("gpu_renderer") or {}).get("displacement_fallback") or "") == "parallax_mapping"
            if require_live_preview else True
        ),
        "packet_export_displacement": (
            bool(packet_diag.get("pbr_displacement_applied"))
            and str(packet_displacement.get("schema") or "") == "tigerstudio.ar_pbr.displacement.v1"
            and bool(packet_displacement.get("enabled"))
            and abs(float(packet_displacement.get("height_strength", 0.0) or 0.0) - 0.52) < 1e-6
            and int(packet_diag.get("pbr_displacement_pixels", 0) or 0) > 0
            and int(packet_diag.get("pbr_displacement_height_pixels", 0) or 0) > 0
            and float(packet_diag.get("pbr_displacement_max_offset", 0.0) or 0.0) > 0.0
            and bool(packet_diag.get("pbr_displacement_parallax_fallback"))
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_bevel_shader": (
            str((live_packet.get("gpu_renderer") or {}).get("bevel_rendering") or "") == "bevel"
            if require_live_preview else True
        ),
        "packet_export_bevel_shader": (
            bool(packet_diag.get("pbr_bevel_applied"))
            and bool((packet_diag.get("pbr_bevel_rendering") or {}).get("enabled"))
            and int(packet_diag.get("pbr_bevel_pixels", 0) or 0) > 0
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_material_layering": (
            str((live_packet.get("gpu_renderer") or {}).get("material_layering") or "") == "layered"
            if require_live_preview else True
        ),
        "packet_export_material_layering": (
            bool(packet_diag.get("pbr_material_layer_applied"))
            and bool((packet_diag.get("pbr_material_layering") or {}).get("enabled"))
            and int(packet_diag.get("pbr_material_layer_pixels", 0) or 0) > 0
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_subsurface_scattering": (
            str((live_packet.get("gpu_renderer") or {}).get("subsurface_rendering") or "") == "subsurface"
            if require_live_preview else True
        ),
        "packet_export_subsurface_scattering": (
            bool(packet_diag.get("pbr_subsurface_applied"))
            and bool((packet_diag.get("pbr_subsurface_rendering") or {}).get("enabled"))
            and int(packet_diag.get("pbr_subsurface_pixels", 0) or 0) > 0
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_hair_groom_shading": (
            str((live_packet.get("gpu_renderer") or {}).get("hair_groom_rendering") or "") == "hair"
            if require_live_preview else True
        ),
        "packet_export_hair_groom_shading": (
            bool(packet_diag.get("pbr_hair_groom_applied"))
            and bool((packet_diag.get("pbr_hair_groom_rendering") or {}).get("enabled"))
            and int(packet_diag.get("pbr_hair_groom_pixels", 0) or 0) > 0
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_cloth_sheen": (
            str((live_packet.get("gpu_renderer") or {}).get("cloth_sheen_rendering") or "") == "sheen"
            if require_live_preview else True
        ),
        "packet_export_cloth_sheen": (
            bool(packet_diag.get("pbr_cloth_sheen_applied"))
            and bool((packet_diag.get("pbr_cloth_sheen_rendering") or {}).get("enabled"))
            and int(packet_diag.get("pbr_cloth_sheen_pixels", 0) or 0) > 0
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_glint_sparkle": (
            str((live_packet.get("gpu_renderer") or {}).get("glint_sparkle_rendering") or "") == "sparkle"
            if require_live_preview else True
        ),
        "packet_export_glint_sparkle": (
            bool(packet_diag.get("pbr_glint_sparkle_applied"))
            and bool((packet_diag.get("pbr_glint_sparkle_rendering") or {}).get("enabled"))
            and int(packet_diag.get("pbr_glint_sparkle_pixels", 0) or 0) > 0
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_caustics": (
            str((live_packet.get("gpu_renderer") or {}).get("caustics_rendering") or "") == "caustics"
            and int((live_packet.get("gpu_renderer") or {}).get("caustics_samples", 0) or 0) == 24
            if require_live_preview else True
        ),
        "packet_export_caustics": (
            bool(packet_diag.get("pbr_caustics_applied"))
            and str(packet_caustics.get("schema") or "") == "tigerstudio.ar_pbr.caustics.v1"
            and bool(packet_caustics.get("enabled"))
            and int(packet_caustics.get("sample_count", 0) or 0) == 24
            and int(packet_diag.get("pbr_caustics_pixels", 0) or 0) > 0
            and float(packet_diag.get("pbr_caustics_max_intensity", 0.0) or 0.0) > 0.0
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_anisotropic_material": (
            str((live_packet.get("gpu_renderer") or {}).get("anisotropic_rendering") or "") == "anisotropic"
            and abs(float((live_packet.get("gpu_renderer") or {}).get("thin_film_strength", 0.0) or 0.0) - 0.50) < 1e-6
            if require_live_preview else True
        ),
        "packet_export_anisotropic_material": (
            bool(packet_diag.get("pbr_anisotropic_applied"))
            and str(packet_anisotropic.get("schema") or "") == "tigerstudio.ar_pbr.anisotropic_material.v1"
            and bool(packet_anisotropic.get("enabled"))
            and abs(float(packet_anisotropic.get("anisotropy", 0.0) or 0.0) - 0.58) < 1e-6
            and bool(packet_anisotropic.get("thin_film_enabled"))
            and int(packet_diag.get("pbr_anisotropic_pixels", 0) or 0) > 0
            and float(packet_diag.get("pbr_anisotropic_max_intensity", 0.0) or 0.0) > 0.0
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_microsurface": (
            str((live_packet.get("gpu_renderer") or {}).get("microsurface_rendering") or "") == "microsurface"
            and abs(float((live_packet.get("gpu_renderer") or {}).get("detail_normal_strength", 0.0) or 0.0) - 0.46) < 1e-6
            if require_live_preview else True
        ),
        "packet_export_microsurface": (
            bool(packet_diag.get("pbr_detail_normal_applied"))
            and bool(packet_diag.get("pbr_micro_roughness_applied"))
            and str(packet_micro.get("schema") or "") == "tigerstudio.ar_pbr.microsurface.v1"
            and bool(packet_micro.get("enabled"))
            and bool(packet_micro.get("detail_normal_enabled"))
            and bool(packet_micro.get("micro_roughness_enabled"))
            and abs(float(packet_micro.get("detail_normal_strength", 0.0) or 0.0) - 0.46) < 1e-6
            and abs(float(packet_micro.get("micro_roughness_strength", 0.0) or 0.0) - 0.36) < 1e-6
            and int(packet_diag.get("pbr_detail_normal_pixels", 0) or 0) > 0
            and int(packet_diag.get("pbr_micro_roughness_pixels", 0) or 0) > 0
            and float(packet_diag.get("pbr_detail_normal_max_delta", 0.0) or 0.0) > 0.0
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_depth_of_field": (
            str((live_packet.get("gpu_renderer") or {}).get("depth_of_field_rendering") or "") == "depth_of_field"
            if require_live_preview else True
        ),
        "packet_export_depth_of_field": (
            bool(packet_diag.get("pbr_depth_of_field_applied"))
            and bool((packet_diag.get("pbr_depth_of_field_rendering") or {}).get("enabled"))
            and int(packet_diag.get("pbr_depth_of_field_pixels", 0) or 0) > 0
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_post_effects": (
            str((live_packet.get("gpu_renderer") or {}).get("post_effects_rendering") or "") == "post_effects"
            if require_live_preview else True
        ),
        "packet_export_post_effects": (
            bool(packet_diag.get("pbr_post_effects_applied"))
            and bool((packet_diag.get("pbr_post_effects_rendering") or {}).get("enabled"))
            and bool(packet_diag.get("pbr_bloom_applied"))
            and bool(packet_diag.get("pbr_vignette_applied"))
            and bool(packet_diag.get("pbr_grain_applied"))
            and bool(packet_diag.get("pbr_sharpen_applied"))
            and int(packet_diag.get("pbr_post_effects_pixels", 0) or 0) > 0
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_lens_effects": (
            str((live_packet.get("gpu_renderer") or {}).get("lens_effects_rendering") or "") == "lens_effects"
            if require_live_preview else True
        ),
        "packet_export_lens_effects": (
            bool(packet_diag.get("pbr_lens_effects_applied"))
            and bool((packet_diag.get("pbr_lens_effects_rendering") or {}).get("enabled"))
            and bool(packet_diag.get("pbr_lens_distortion_applied"))
            and bool(packet_diag.get("pbr_chromatic_aberration_applied"))
            and int(packet_diag.get("pbr_lens_effects_pixels", 0) or 0) > 0
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_lens_flare": (
            str((live_packet.get("gpu_renderer") or {}).get("lens_flare_rendering") or "") == "lens_flare"
            if require_live_preview else True
        ),
        "packet_export_lens_flare": (
            bool(packet_diag.get("pbr_lens_flare_applied"))
            and bool((packet_diag.get("pbr_lens_flare_rendering") or {}).get("enabled"))
            and bool(packet_diag.get("pbr_flare_applied"))
            and bool(packet_diag.get("pbr_aperture_flare_applied"))
            and bool(packet_diag.get("pbr_lens_dirt_applied"))
            and bool(packet_diag.get("pbr_lens_scratch_applied"))
            and int(packet_diag.get("pbr_lens_flare_pixels", 0) or 0) > 0
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_motion_blur_contract": (
            str((live_packet.get("gpu_renderer") or {}).get("motion_blur") or "") == "final_export_shutter_sample_contract"
            and int((live_packet.get("gpu_renderer") or {}).get("motion_blur_samples", 0) or 0) == 5
            if require_live_preview else True
        ),
        "packet_export_motion_blur": (
            bool(packet_diag.get("pbr_motion_blur_applied"))
            and bool((packet_diag.get("pbr_motion_blur_rendering") or {}).get("enabled"))
            and int(packet_diag.get("pbr_motion_blur_sample_count", 0) or 0) == 5
            and int(packet_diag.get("pbr_motion_blur_changed_pixels", 0) or 0) > 0
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_render_passes": (
            str((live_packet.get("gpu_renderer") or {}).get("render_passes") or "") == "packet_render_pass_export_contract"
            and int((live_packet.get("gpu_renderer") or {}).get("render_pass_count", 0) or 0) >= 19
            if require_live_preview else True
        ),
        "packet_export_render_passes": (
            str(packet_passes.get("schema") or "") == "tigerstudio.ar_pbr.render_passes.output.v1"
            and bool(packet_passes.get("enabled"))
            and int(packet_passes.get("pass_count", 0) or 0) >= 19
            and int(packet_passes.get("written_count", 0) or 0) >= 19
            if isinstance(packet_diag, Mapping) else False
        ),
        "packet_export_render_pass_data": (
            all(
                str((packet_pass_rows.get(name) or {}).get("path") or "")
                and int((packet_pass_rows.get(name) or {}).get("changed_pixels", 0) or 0) > 0
                for name in ("beauty", "alpha_mask", "depth", "normal", "albedo", "roughness", "metallic", "ambient_occlusion", "object_id")
            )
            if isinstance(packet_pass_rows, Mapping) else False
        ),
        "live_preview_udim_tiles": (
            str((live_packet.get("gpu_renderer") or {}).get("udim") or "") == "texture_plan_udim_tiles_ready"
            if require_live_preview else True
        ),
        "packet_export_udim_tiles": (
            str((packet_diag.get("pbr_udim_rendering") or {}).get("schema") or "") == "tigerstudio.ar_pbr.udim.v1"
            and int(packet_diag.get("pbr_udim_sampled_pixels", 0) or 0) > 0
            and 1002 in [int(tile) for tile in (packet_diag.get("pbr_udim_sampled_tiles") or [])]
            if isinstance(packet_diag, Mapping) else False
        ),
        "live_preview_triplanar_projection": (
            str((live_packet.get("gpu_renderer") or {}).get("triplanar_rendering") or "") == "triplanar"
            if require_live_preview else True
        ),
        "packet_export_triplanar_projection": (
            bool(packet_diag.get("pbr_triplanar_applied"))
            and bool((packet_diag.get("pbr_triplanar_rendering") or {}).get("enabled"))
            and int(packet_diag.get("pbr_triplanar_pixels", 0) or 0) > 0
            if isinstance(packet_diag, Mapping) else False
        ),
        "packet_export_catchers_present": (
            int(packet_builder.get("shadow_triangle_count", 0) or 0) >= 1
            and int(packet_builder.get("reflection_triangle_count", 0) or 0) >= 1
        ),
        "full_gpu_export_rendered": (
            bool(full_diag.get("ok")) and int(full_diag.get("rendered_track_count", 0) or 0) >= 1
            if require_full_gpu and isinstance(full_diag, Mapping) else not require_full_gpu
        ),
        "full_gpu_export_no_packet_fallback": (
            not bool(full_diag.get("fallback"))
            if require_full_gpu and isinstance(full_diag, Mapping) else not require_full_gpu
        ),
        "full_gpu_export_shadow_map_contract": (
            bool(full_row.get("shadow_map_enabled"))
            and str(full_shadow.get("filter") or "") == "pcss"
            and str(full_shadow.get("light_type") or "") == "spot"
        ) if require_full_gpu else True,
        "full_gpu_export_catcher_contract": (
            str(full_catcher.get("schema") or "") == "tigerstudio.ar_pbr.catcher.v1"
            if require_full_gpu else True
        ),
        "full_gpu_export_tone_mapping_agx": (
            str(full_color.get("tone_mapping") or "") == "agx"
            if require_full_gpu else True
        ),
        "full_gpu_export_hybrid_accumulation": (
            bool(full_hybrid.get("enabled")) and int(full_hybrid.get("sample_count", 0) or 0) == 16
            if require_full_gpu else True
        ),
        "full_gpu_export_ray_gi_detail_contract": (
            str(full_ray_gi.get("schema") or "") == "tigerstudio.ar_pbr.ray_gi_detail.v1"
            and bool(full_ray_gi.get("enabled"))
            and int(full_ray_gi.get("max_bounces", 0) or 0) == 6
            and int(full_ray_gi.get("light_sample_count", 0) or 0) == 24
            and str(full_ray_gi.get("renderer") or "") == "full_gpu_helper_contract_only"
            if require_full_gpu else True
        ),
        "full_gpu_export_screen_ao": (
            bool(full_ao.get("enabled"))
            and str(full_ao.get("mode") or "") == "screen"
            and abs(float(full_ao.get("strength", 0.0) or 0.0) - 0.38) < 1e-6
            if require_full_gpu else True
        ),
        "full_gpu_export_transmission_refraction": (
            bool(full_transmission.get("enabled"))
            and abs(float(full_transmission.get("transmission", 0.0) or 0.0) - 0.42) < 1e-6
            if require_full_gpu else True
        ),
        "full_gpu_export_clearcoat": (
            bool(full_clearcoat.get("enabled"))
            and abs(float(full_clearcoat.get("strength", 0.0) or 0.0) - 0.46) < 1e-6
            if require_full_gpu else True
        ),
        "full_gpu_export_parallax": (
            bool(full_parallax.get("enabled"))
            and abs(float(full_parallax.get("strength", 0.0) or 0.0) - 0.50) < 1e-6
            if require_full_gpu else True
        ),
        "full_gpu_export_displacement_contract": (
            str(full_displacement.get("schema") or "") == "tigerstudio.ar_pbr.displacement.v1"
            and bool(full_displacement.get("enabled"))
            and abs(float(full_displacement.get("height_strength", 0.0) or 0.0) - 0.52) < 1e-6
            and abs(float(full_displacement.get("vector_strength", 0.0) or 0.0) - 0.20) < 1e-6
            and bool(full_displacement.get("parallax_fallback"))
            and str(full_displacement.get("renderer") or "") == "full_gpu_helper_contract_only"
            if require_full_gpu else True
        ),
        "full_gpu_export_bevel_shader": (
            bool(full_bevel.get("enabled"))
            and abs(float(full_bevel.get("strength", 0.0) or 0.0) - 0.44) < 1e-6
            if require_full_gpu else True
        ),
        "full_gpu_export_material_layering": (
            bool(full_material_layer.get("enabled"))
            and abs(float(full_material_layer.get("blend", 0.0) or 0.0) - 0.38) < 1e-6
            if require_full_gpu else True
        ),
        "full_gpu_export_subsurface_scattering": (
            bool(full_subsurface.get("enabled"))
            and abs(float(full_subsurface.get("strength", 0.0) or 0.0) - 0.34) < 1e-6
            if require_full_gpu else True
        ),
        "full_gpu_export_hair_groom_shading": (
            bool(full_hair.get("enabled"))
            and abs(float(full_hair.get("strength", 0.0) or 0.0) - 0.37) < 1e-6
            if require_full_gpu else True
        ),
        "full_gpu_export_cloth_sheen": (
            bool(full_cloth.get("enabled"))
            and abs(float(full_cloth.get("strength", 0.0) or 0.0) - 0.36) < 1e-6
            if require_full_gpu else True
        ),
        "full_gpu_export_glint_sparkle": (
            bool(full_glint.get("enabled"))
            and abs(float(full_glint.get("strength", 0.0) or 0.0) - 0.34) < 1e-6
            if require_full_gpu else True
        ),
        "full_gpu_export_caustics_contract": (
            str(full_caustics.get("schema") or "") == "tigerstudio.ar_pbr.caustics.v1"
            and bool(full_caustics.get("enabled"))
            and int(full_caustics.get("sample_count", 0) or 0) == 24
            and str(full_caustics.get("renderer") or "") == "full_gpu_helper_contract_only"
            if require_full_gpu else True
        ),
        "full_gpu_export_anisotropic_material_contract": (
            str(full_anisotropic.get("schema") or "") == "tigerstudio.ar_pbr.anisotropic_material.v1"
            and bool(full_anisotropic.get("enabled"))
            and abs(float(full_anisotropic.get("anisotropy", 0.0) or 0.0) - 0.58) < 1e-6
            and bool(full_anisotropic.get("thin_film_enabled"))
            and str(full_anisotropic.get("renderer") or "") == "full_gpu_helper_contract_only"
            if require_full_gpu else True
        ),
        "full_gpu_export_microsurface_contract": (
            str(full_micro.get("schema") or "") == "tigerstudio.ar_pbr.microsurface.v1"
            and bool(full_micro.get("enabled"))
            and bool(full_micro.get("detail_normal_enabled"))
            and bool(full_micro.get("micro_roughness_enabled"))
            and abs(float(full_micro.get("detail_normal_strength", 0.0) or 0.0) - 0.46) < 1e-6
            and abs(float(full_micro.get("micro_roughness_strength", 0.0) or 0.0) - 0.36) < 1e-6
            and str(full_micro.get("renderer") or "") == "full_gpu_helper_contract_only"
            if require_full_gpu else True
        ),
        "full_gpu_export_depth_of_field": (
            bool(full_dof.get("enabled"))
            and abs(float(full_dof.get("strength", 0.0) or 0.0) - 0.62) < 1e-6
            and abs(float(full_dof.get("focus_depth", 0.0) or 0.0) - 0.12) < 1e-6
            if require_full_gpu else True
        ),
        "full_gpu_export_post_effects": (
            bool(full_post.get("enabled"))
            and bool(full_post.get("bloom_enabled"))
            and bool(full_post.get("vignette_enabled"))
            and bool(full_post.get("grain_enabled"))
            and bool(full_post.get("sharpen_enabled"))
            and abs(float(full_post.get("bloom_strength", 0.0) or 0.0) - 0.32) < 1e-6
            and abs(float(full_post.get("vignette_strength", 0.0) or 0.0) - 0.22) < 1e-6
            if require_full_gpu else True
        ),
        "full_gpu_export_lens_effects_contract": (
            bool(full_lens.get("enabled"))
            and bool(full_lens.get("distortion_enabled"))
            and bool(full_lens.get("chromatic_aberration_enabled"))
            and abs(float(full_lens.get("distortion_strength", 0.0) or 0.0) - 0.16) < 1e-6
            and abs(float(full_lens.get("chromatic_aberration_px", 0.0) or 0.0) - 2.2) < 1e-6
            if require_full_gpu else True
        ),
        "full_gpu_export_lens_flare_contract": (
            bool(full_flare.get("enabled"))
            and bool(full_flare.get("flare_enabled"))
            and bool(full_flare.get("aperture_flare_enabled"))
            and bool(full_flare.get("lens_dirt_enabled"))
            and bool(full_flare.get("lens_scratch_enabled"))
            and int(full_flare.get("ghost_count", 0) or 0) == 4
            and int(full_flare.get("aperture_blades", 0) or 0) == 6
            and abs(float(full_flare.get("flare_strength", 0.0) or 0.0) - 0.36) < 1e-6
            if require_full_gpu else True
        ),
        "full_gpu_export_motion_blur_contract": (
            bool(full_motion.get("enabled"))
            and str(full_motion.get("mode") or "") == "final"
            and int(full_motion.get("sample_count", 0) or 0) == 5
            if require_full_gpu else True
        ),
        "full_gpu_export_udim_tiles": (
            bool(full_udim.get("enabled"))
            and int(full_udim.get("tile_count", 0) or 0) >= 2
            if require_full_gpu else True
        ),
        "full_gpu_export_triplanar_projection": (
            bool(full_triplanar.get("enabled"))
            and abs(float(full_triplanar.get("scale", 0.0) or 0.0) - 1.45) < 1e-6
            if require_full_gpu else True
        ),
    }


def run_ar_pbr_golden_scene_qa(
    *,
    out: Path | str,
    out_dir: Path | str | None = None,
    baseline_dir: Path | str | None = None,
    update_baseline: bool = False,
    width: int = 160,
    height: int = 96,
    render_live_preview: bool = True,
    render_full_gpu: bool = True,
    visible: bool = False,
) -> dict[str, Any]:
    report_path = Path(out)
    image_dir = Path(out_dir) if out_dir is not None else report_path.with_suffix("")
    image_dir.mkdir(parents=True, exist_ok=True)
    baseline_root = Path(baseline_dir) if baseline_dir is not None else None
    scene = build_ar_pbr_golden_scene(out_dir=image_dir, width=int(width), height=int(height))
    scene["settings"] = dict(scene.get("settings") or {})
    scene["settings"]["render_pass_output_dir"] = str(image_dir / "render_passes")
    base = np.asarray(scene["base_frame"], dtype=np.uint8)
    _save_image(image_dir / "base_frame.png", base)
    _save_image(image_dir / "depth_visualization.png", np.repeat((scene["depth_frame"] * 255.0).astype(np.uint8)[:, :, None], 3, axis=2))

    outputs: dict[str, np.ndarray] = {}
    diagnostics: dict[str, Any] = {}
    skips: list[dict[str, Any]] = []

    if render_live_preview:
        outputs["live_preview"] = base.copy()
        outputs["live_preview"], diagnostics["live_preview"] = render_live_preview_scene(scene, visible=bool(visible))
    else:
        skips.append({"renderer": "live_preview", "reason": "disabled"})
        diagnostics["live_preview"] = {"ok": False, "skipped": True, "mode": "live_gl_preview"}

    outputs["packet_export"], diagnostics["packet_export"] = render_packet_export_scene(scene)

    if render_full_gpu:
        outputs["full_gpu_export"] = base.copy()
        outputs["full_gpu_export"], diagnostics["full_gpu_export"] = render_full_gpu_export_scene(scene)
    else:
        skips.append({"renderer": "full_gpu_export", "reason": "disabled"})
        diagnostics["full_gpu_export"] = {"ok": False, "skipped": True, "mode": "full_model_view_gpu_export_service"}

    image_paths: dict[str, str] = {}
    metrics: dict[str, Any] = {}
    for name, arr in outputs.items():
        path = image_dir / f"{name}.png"
        _save_image(path, arr)
        image_paths[name] = str(path)
        metrics[f"{name}_vs_base"] = compare_image_arrays(arr, base, threshold=12)

    packet_passes = diagnostics.get("packet_export", {}).get("pbr_render_passes", {})
    packet_pass_rows = packet_passes.get("passes") if isinstance(packet_passes, Mapping) and isinstance(packet_passes.get("passes"), Mapping) else {}
    for pass_name, row in packet_pass_rows.items():
        if not isinstance(row, Mapping):
            continue
        path_text = str(row.get("path") or "")
        if path_text:
            image_paths[f"render_pass_{pass_name}"] = path_text

    pairwise: dict[str, Any] = {}
    pair_names = [
        ("live_preview", "packet_export"),
        ("full_gpu_export", "packet_export"),
        ("live_preview", "full_gpu_export"),
    ]
    for left, right in pair_names:
        if left not in outputs or right not in outputs:
            continue
        key = f"{left}_vs_{right}"
        pairwise[key] = compare_image_arrays(outputs[left], outputs[right], threshold=12)
        diff_path = image_dir / f"diff_{key}.png"
        _save_image(diff_path, _diff_image(outputs[left], outputs[right]))
        image_paths[f"diff_{key}"] = str(diff_path)

    baseline_results = []
    for image_name in GOLDEN_IMAGE_NAMES:
        stem = image_name[:-4]
        actual_path = image_dir / image_name
        if not actual_path.is_file() and (image_dir / f"{stem}.png").is_file():
            actual_path = image_dir / f"{stem}.png"
        if actual_path.is_file():
            baseline_results.append(_baseline_compare(
                name=image_name,
                actual_path=actual_path,
                baseline_dir=baseline_root,
                update_baseline=bool(update_baseline),
                max_mean_abs_diff=8.0,
                max_p95_abs_diff=32.0,
            ))

    contract_checks = _diagnostic_contract_checks(
        live_diag=diagnostics.get("live_preview"),
        packet_diag=diagnostics.get("packet_export"),
        full_diag=diagnostics.get("full_gpu_export"),
        require_live_preview=bool(render_live_preview),
        require_full_gpu=bool(render_full_gpu),
    )
    pixel_checks = {
        f"{name}_changed_base": int(row.get("changed_pixels", 0) or 0) >= 120
        for name, row in metrics.items()
        if name.endswith("_vs_base")
    }
    renderer_checks = {
        "live_preview_available": bool(diagnostics.get("live_preview", {}).get("ok")) if render_live_preview else True,
        "packet_export_available": bool(diagnostics.get("packet_export", {}).get("ok", True)),
        "full_gpu_export_available": (
            bool(diagnostics.get("full_gpu_export", {}).get("ok"))
            and not bool(diagnostics.get("full_gpu_export", {}).get("fallback"))
        ) if render_full_gpu else True,
    }
    baseline_checks = {
        "baseline_comparison": all(bool(row.get("ok", True)) for row in baseline_results),
    }
    checks = {**renderer_checks, **pixel_checks, **contract_checks, **baseline_checks}
    report = {
        "schema": "tigerstudio.ar_pbr.golden_scene_qa.v1",
        "ok": all(bool(value) for value in checks.values()),
        "out_dir": str(image_dir),
        "frame_size": [int(width), int(height)],
        "images": image_paths,
        "metrics": metrics,
        "pairwise": pairwise,
        "diagnostics": diagnostics,
        "checks": checks,
        "baseline": {
            "enabled": baseline_root is not None,
            "update": bool(update_baseline),
            "dir": str(baseline_root) if baseline_root is not None else "",
            "results": baseline_results,
        },
        "covered": [
            "live OpenGLPreviewWidget AR/PBR packet draw",
            "full GPU model-view export helper",
            "deterministic packet fallback export",
            "HDRI/IBL material-map PBR lighting",
            "depth occlusion packet path",
            "shadow catcher and reflection catcher diagnostics",
            "PCSS/spot shadow-map contract",
            "AgX display transform contract",
            "ray/hybrid GI bounce, clamp, light sampling, and denoise-channel diagnostics",
            "screen-space ambient occlusion diagnostics",
            "transmission/refraction packet and environment diagnostics",
            "clearcoat secondary specular layer diagnostics",
            "height-map parallax UV offset diagnostics",
            "height/vector geometry displacement contract with parallax realtime fallback diagnostics",
            "shader-only bevel rounded-edge normal diagnostics",
            "single overlay material layer diagnostics",
            "single-scatter subsurface approximation diagnostics",
            "dual-lobe anisotropic hair/groom diagnostics",
            "Charlie-style fabric cloth/sheen diagnostics",
            "deterministic microflake glint/sparkle diagnostics",
            "glass/specular caustic highlight approximation diagnostics",
            "general anisotropic reflection, clearcoat anisotropy, and thin-film diagnostics",
            "detail normal layering and advanced roughness/gloss microsurface diagnostics",
            "depth-banded AR overlay depth-of-field diagnostics",
            "beauty-pass bloom/vignette/grain/sharpen diagnostics",
            "camera/lens distortion and chromatic aberration diagnostics",
            "lens flare, aperture flare, dirt, and scratch diagnostics",
            "final-render shutter/sample motion blur diagnostics",
            "packet render pass exporter PNG artifact diagnostics",
            "UDIM tile-set texture-plan and packet export sampling diagnostics",
            "triplanar normal-weighted axis texture projection diagnostics",
            "optional PNG baseline comparison",
        ],
        "skips": skips,
    }
    _write_json(report_path, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render deterministic AR/PBR golden scene across live/full-GPU/packet paths.")
    parser.add_argument("--out", type=Path, default=ROOT / "debugCapture" / "ar_pbr_golden_scene_qa.json")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "debugCapture" / "ar_pbr_golden_scene")
    parser.add_argument("--baseline-dir", type=Path, default=None)
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--width", type=int, default=160)
    parser.add_argument("--height", type=int, default=96)
    parser.add_argument("--skip-live-preview", action="store_true")
    parser.add_argument("--skip-full-gpu", action="store_true")
    parser.add_argument("--visible", action="store_true")
    args = parser.parse_args(argv)
    report = run_ar_pbr_golden_scene_qa(
        out=args.out,
        out_dir=args.out_dir,
        baseline_dir=args.baseline_dir,
        update_baseline=bool(args.update_baseline),
        width=int(args.width),
        height=int(args.height),
        render_live_preview=not bool(args.skip_live_preview),
        render_full_gpu=not bool(args.skip_full_gpu),
        visible=bool(args.visible),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
