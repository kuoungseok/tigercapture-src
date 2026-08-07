from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from PIL import Image
import pytest


def test_texture_lab_srgb_transfer_matches_iec_reference_points() -> None:
    from app.ar_pbr.texture_map_lab import _linear_to_srgb, _srgb_to_linear

    encoded = np.asarray([0.0, 0.04045, 0.5, 1.0], dtype=np.float32)
    linear = _srgb_to_linear(encoded)
    assert linear[1] == pytest.approx(0.0031308, abs=1.0e-6)
    assert linear[2] == pytest.approx(0.21404114, abs=1.0e-6)
    assert np.allclose(_linear_to_srgb(linear), encoded, atol=1.0e-6)


def test_surface_maps_from_height_reuses_texture_lab_normal_and_realtime_ao() -> None:
    from app.ar_pbr.texture_map_lab import generate_surface_maps_from_height

    height = np.zeros((64, 96), dtype=np.float32)
    height[22:42, 18:78] = 0.72
    maps = generate_surface_maps_from_height(
        height,
        {
            "normal_strength": 6.0,
            "normal_format": "unreal_directx",
            "normal_filter": "sobel",
            "ao_strength": 0.85,
            "ao_radius_px": 4.0,
        },
        realtime=True,
    )
    assert set(maps) == {"height", "normal", "ao", "cavity", "curvature"}
    assert maps["normal"].shape == (64, 96, 3)
    assert float(np.std(maps["normal"][..., 0])) > 0.001
    assert float(np.min(maps["ao"])) < 1.0


def test_cpu_pbr_ndotl_is_normal_format_invariant() -> None:
    from app.ar_pbr.texture_map_lab import (
        _preview_array_for_mode,
        normal_map_from_height,
        normalize_texture_map_settings,
    )

    height = np.zeros((72, 96), dtype=np.float32)
    height[18:54, 22:74] = np.linspace(0.1, 0.9, 52, dtype=np.float32)[None, :]
    base = np.full((72, 96, 3), (0.52, 0.28, 0.12), dtype=np.float32)
    scalar = np.full((72, 96), 0.45, dtype=np.float32)

    def preview(normal_format: str) -> np.ndarray:
        settings = normalize_texture_map_settings(
            {
                "normal_format": normal_format,
                "preview_light_azimuth": 31.0,
                "preview_light_elevation": 42.0,
            }
        )
        maps = {
            "base_color": base,
            "normal": normal_map_from_height(height, settings),
            "roughness": scalar,
            "metallic": np.zeros_like(scalar),
            "ao": np.ones_like(scalar),
        }
        return _preview_array_for_mode(maps, settings, "material")

    assert np.allclose(
        preview("unreal_directx"),
        preview("opengl"),
        atol=1.0e-6,
    )


def _sample_image(path) -> None:
    h, w = 24, 32
    y = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    x = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
    r = np.tile(x, (h, 1))
    g = np.tile(y, (1, w))
    b = 0.35 + 0.25 * np.sin(x * np.pi * 4.0)
    rgb = np.dstack([r, g, np.tile(b, (h, 1))])
    rgb[6:14, 10:22, :] *= 0.42
    Image.fromarray(np.clip(rgb * 255.0 + 0.5, 0, 255).astype(np.uint8), mode="RGB").save(path)


def _qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_texture_map_lab_generates_unreal_ready_maps(tmp_path) -> None:
    from app.ar_pbr.texture_map_lab import generate_texture_maps

    image_path = tmp_path / "source.png"
    _sample_image(image_path)

    payload = generate_texture_maps(image_path, {"normal_strength": 3.0})

    assert payload["schema_id"] == "tigerstudio.ar_pbr.texture_map_lab.v4"
    assert payload["size"] == [32, 24]
    maps = payload["maps"]
    assert {
        "base_color",
        "base_color_source",
        "base_color_estimate",
        "normal",
        "ao",
        "roughness",
        "metallic",
        "irradiance",
        "delight_shading",
        "height",
        "cavity",
        "curvature",
        "f0",
        "f90_mask",
    } <= set(maps)
    assert maps["base_color"].shape == (24, 32, 3)
    assert maps["base_color_source"].shape == (24, 32, 3)
    assert maps["base_color_estimate"].shape == (24, 32, 3)
    assert maps["normal"].shape == (24, 32, 3)
    assert maps["roughness"].shape == (24, 32)
    assert maps["curvature"].shape == (24, 32)
    assert maps["f0"].shape == (24, 32, 3)
    assert maps["f90_mask"].shape == (24, 32)
    assert maps["irradiance"].shape == (24, 32)
    assert maps["delight_shading"].shape == (24, 32)
    assert float(np.mean(maps["normal"][..., 2])) > 0.7
    assert float(np.max(maps["metallic"])) == 0.0
    assert 0.02 <= float(np.mean(maps["f0"])) <= 0.08
    assert 0.0 <= float(np.min(maps["f90_mask"])) <= float(np.max(maps["f90_mask"])) <= 1.0
    assert payload["algorithms"]["ambient_occlusion"]["method"] == "heightfield_horizon"
    assert payload["algorithms"]["f0"]["method"] == "metalness_to_substrate_f0"
    assert payload["backend"]["active"] in {"cpu", "torch_cuda"}
    assert payload["settings_fingerprint"]


def test_texture_map_lab_supports_in_memory_preview_backend_status(tmp_path) -> None:
    from app.ar_pbr.texture_map_lab import (
        generate_texture_maps_from_image,
        render_plane_preview_from_generated,
        select_texture_map_backend,
    )

    image_path = tmp_path / "source.png"
    _sample_image(image_path)
    image = Image.open(image_path).convert("RGB")
    generated = generate_texture_maps_from_image(image, {"preview_light_elevation": 12.0}, max_size=32)
    out = tmp_path / "preview_from_generated.png"
    preview = render_plane_preview_from_generated(
        generated,
        {"preview_light_elevation": 80.0},
        output_path=out,
        width=64,
    )
    backend = select_texture_map_backend("torch_cuda")

    assert out.exists()
    assert generated["size"] == [32, 24]
    assert preview["backend"]["active"] in {"cpu", "torch_cuda"}
    assert backend["status"]["install_guidance"]["recommended_backend"] == "torch_cuda"
    assert backend["status"]["preview_renderer"]["cpu_preview"] is False


def test_texture_lab_gpu_preview_status_is_cpu_free() -> None:
    from app.ar_pbr.texture_map_gpu_preview import texture_lab_gpu_preview_status

    status = texture_lab_gpu_preview_status()

    assert status["renderer"] == "opengl_offscreen_texture_lab"
    assert status["cpu_preview"] is False
    assert "material" in status["supported_modes"]
    assert "unreal_orm" in status["supported_packed_layouts"]
    assert status["height_map_preview"] is True
    assert status["parallax_occlusion_mapping"] is True
    assert status["parallax_max_steps"] == 64


def test_texture_lab_defaults_expose_height_driven_pom_preview() -> None:
    from app.ar_pbr.texture_map_lab import normalize_texture_map_settings

    settings = normalize_texture_map_settings({})

    assert settings["preview_parallax_enabled"] is True
    assert settings["preview_parallax_strength"] > 0.0
    assert settings["preview_parallax_depth"] > 0.0
    assert settings["preview_parallax_steps"] >= 16

    from app.actions.ar_pbr_texture_lab_namespace import texture_lab_settings_schema

    action_properties = texture_lab_settings_schema()["properties"]
    assert action_properties["preview_parallax_enabled"]["type"] == "boolean"
    assert action_properties["preview_parallax_steps"]["maximum"] == 64


def test_texture_lab_export_manifest_connects_height_to_renderer(tmp_path) -> None:
    from app.ar_pbr.texture_map_lab import export_texture_maps

    image_path = tmp_path / "source.png"
    _sample_image(image_path)
    result = export_texture_maps(image_path, tmp_path / "maps", max_size=16)

    assert Path(result["files"]["height"]).exists()
    height16_path = Path(result["precision_files"]["height_16"])
    assert height16_path.exists()
    height16 = np.asarray(Image.open(height16_path))
    assert height16.dtype in {np.dtype(np.uint16), np.dtype(np.int32)}
    assert int(np.max(height16)) > 255
    usage = result["material_usage"]
    assert usage["height_map"] == result["files"]["height"]
    assert usage["height_map_16"] == result["precision_files"]["height_16"]
    assert usage["height_precision_bits"] == 16
    assert usage["height_semantics"] == "black_low_white_high"
    assert usage["recommended_rendering"]["parallax_mode"] == "pom"
    assert usage["recommended_rendering"]["parallax_enabled"] is True
    assert usage["recommended_rendering"]["parallax_steps"] >= 16
    assert usage["tessellation"]["supported_by_texture"] is True
    assert result["source_size"] == [32, 24]
    assert result["processing_size"] == [16, 12]
    assert result["max_size"] == 16
    assert result["resampled"] is True


def test_texture_lab_cpu_preview_can_stay_in_memory(tmp_path) -> None:
    from app.ar_pbr.texture_map_lab import generate_texture_maps, render_plane_preview_from_generated

    image_path = tmp_path / "source.png"
    forbidden_output = tmp_path / "preview_should_not_exist.png"
    _sample_image(image_path)
    generated = generate_texture_maps(image_path, max_size=64, backend="cpu", allow_cpu=True)

    payload = render_plane_preview_from_generated(
        generated,
        output_path=forbidden_output,
        width=96,
        allow_cpu_preview=True,
        write_output=False,
    )

    assert payload["preview_path"] == ""
    assert payload["preview_image"].size[0] == 96
    assert forbidden_output.exists() is False


def test_texture_lab_torch_f0_matches_shared_cpu_formula_when_cuda_available(tmp_path) -> None:
    from app.ar_pbr.texture_map_lab import generate_texture_maps, texture_map_backend_status

    if not texture_map_backend_status()["backends"]["torch_cuda"]["available"]:
        pytest.skip("torch CUDA is unavailable")
    image_path = tmp_path / "source.png"
    _sample_image(image_path)
    settings = {
        "substrate_reflectance": 0.5,
        "metallic_value": 0.0,
        "delight_enabled": True,
        "delight_strength": 0.8,
        "delight_radius_px": 6.0,
        "delight_contrast_preservation": 0.3,
    }
    cpu = generate_texture_maps(image_path, settings, backend="cpu", allow_cpu=True)
    gpu = generate_texture_maps(image_path, settings, backend="torch_cuda", allow_cpu=False)

    assert np.allclose(cpu["maps"]["f0"], gpu["maps"]["f0"], atol=1.0e-6)
    estimate_delta = np.abs(
        cpu["maps"]["base_color_estimate"] - gpu["maps"]["base_color_estimate"]
    )
    assert float(np.mean(estimate_delta)) < 1.0e-5
    assert float(np.max(estimate_delta)) < 1.0e-4
    assert np.allclose(
        cpu["maps"]["delight_shading"],
        gpu["maps"]["delight_shading"],
        atol=1.0e-4,
    )
    assert gpu["maps"]["irradiance"] is gpu["maps"]["delight_shading"]


def test_texture_lab_gpu_preview_smoke_when_context_available(tmp_path) -> None:
    _qt_app()
    from app.ar_pbr.texture_map_lab import (
        TextureMapGpuRequiredError,
        generate_texture_maps,
        render_plane_preview_from_generated,
    )

    image_path = tmp_path / "source.png"
    out = tmp_path / "gpu_preview.png"
    _sample_image(image_path)
    generated = generate_texture_maps(image_path, {"preview_environment": 0.45}, max_size=64, allow_cpu=True)

    try:
        payload = render_plane_preview_from_generated(
            generated,
            {"preview_environment": 0.45},
            output_path=out,
            width=96,
            allow_cpu_preview=False,
        )
    except TextureMapGpuRequiredError as exc:
        pytest.skip(f"OpenGL Texture Lab preview unavailable in this environment: {exc}")

    assert out.exists()
    assert payload["backend"]["preview_renderer"] == "opengl_offscreen_texture_lab"
    assert payload["backend"]["cpu_preview"] is False
    assert payload["diagnostics"]["gpu_preview"]["cpu_preview"] is False


def test_texture_lab_gpu_sphere_uses_wrapped_material_maps_when_context_available(tmp_path) -> None:
    _qt_app()
    from app.ar_pbr.texture_map_lab import (
        TextureMapGpuRequiredError,
        generate_texture_maps,
        render_plane_preview_from_generated,
    )

    image_path = tmp_path / "sphere_source.png"
    out = tmp_path / "gpu_sphere_preview.png"
    _sample_image(image_path)
    generated = generate_texture_maps(image_path, max_size=64, allow_cpu=True)

    try:
        payload = render_plane_preview_from_generated(
            generated,
            preview_shape="sphere",
            preview_mode="material",
            output_path=out,
            width=128,
            height=128,
            allow_cpu_preview=False,
        )
    except TextureMapGpuRequiredError as exc:
        pytest.skip(f"OpenGL Texture Lab sphere preview unavailable in this environment: {exc}")

    preview = np.asarray(Image.open(out).convert("RGB"), dtype=np.float32)
    center = preview[24:104, 24:104]
    corners = np.concatenate(
        [preview[:12, :12].reshape(-1, 3), preview[-12:, -12:].reshape(-1, 3)],
        axis=0,
    )
    assert payload["preview_shape"] == "sphere"
    assert payload["diagnostics"]["gpu_preview"]["shape"] == "sphere"
    assert center.std() > 1.0
    assert float(center.mean()) > float(corners.mean()) + 5.0


def test_texture_map_lab_delight_reduces_baked_lighting_gradient(tmp_path) -> None:
    from app.ar_pbr.texture_map_lab import generate_texture_maps, render_plane_preview_from_generated

    h, w = 48, 96
    y = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    x = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
    material = np.dstack(
        [
            np.full((h, w), 0.20, dtype=np.float32) + np.tile(np.sin(x * np.pi * 14.0), (h, 1)) * 0.025,
            np.full((h, w), 0.58, dtype=np.float32) + np.tile(np.cos(y * np.pi * 7.0), (1, w)) * 0.035,
            np.full((h, w), 0.15, dtype=np.float32),
        ]
    )
    baked_light = np.linspace(0.35, 1.15, w, dtype=np.float32)[None, :, None]
    rgb = np.clip(material * baked_light, 0.0, 1.0)
    image_path = tmp_path / "baked_grass_photo.png"
    Image.fromarray(np.clip(rgb * 255.0 + 0.5, 0, 255).astype(np.uint8), mode="RGB").save(image_path)

    baseline = generate_texture_maps(image_path, {"delight_enabled": False}, max_size=96)
    delighted = generate_texture_maps(
        image_path,
        {
            "delight_enabled": True,
            "delight_strength": 0.90,
            "delight_radius_px": 18.0,
            "delight_contrast_preservation": 0.0,
        },
        max_size=96,
    )

    baseline_luma = (
        baseline["maps"]["base_color"][..., 0] * 0.2126
        + baseline["maps"]["base_color"][..., 1] * 0.7152
        + baseline["maps"]["base_color"][..., 2] * 0.0722
    )
    delighted_luma = (
        delighted["maps"]["base_color_estimate"][..., 0] * 0.2126
        + delighted["maps"]["base_color_estimate"][..., 1] * 0.7152
        + delighted["maps"]["base_color_estimate"][..., 2] * 0.0722
    )
    baseline_side_delta = abs(float(np.mean(baseline_luma[:, :16])) - float(np.mean(baseline_luma[:, -16:])))
    delighted_side_delta = abs(float(np.mean(delighted_luma[:, :16])) - float(np.mean(delighted_luma[:, -16:])))

    assert delighted_side_delta < baseline_side_delta * 0.65
    assert np.allclose(delighted["maps"]["base_color_source"], delighted["maps"]["base_color"])
    assert np.mean(
        np.abs(delighted["maps"]["base_color_source"] - delighted["maps"]["base_color_estimate"])
    ) > 0.02
    assert np.allclose(delighted["maps"]["height"], baseline["maps"]["height"], atol=1.0e-6)
    assert delighted["maps"]["delight_shading"].shape == (h, w)
    assert float(np.std(delighted["maps"]["delight_shading"])) > 0.18
    assert delighted["algorithms"]["delight"]["enabled"] is True
    assert delighted["algorithms"]["delight"]["validation"] == "not_photometrically_validated"
    assert delighted["algorithms"]["delight"]["surface_maps_use_estimate"] is False
    assert delighted["base_color_provenance"]["estimate_applied"] is False
    assert delighted["base_color_provenance"]["confidence"] is None

    applied = generate_texture_maps(
        image_path,
        {
            "delight_enabled": True,
            "delight_apply_to_base_color": True,
            "delight_strength": 0.90,
            "delight_radius_px": 18.0,
            "delight_contrast_preservation": 0.0,
        },
        max_size=96,
    )
    assert np.allclose(applied["maps"]["base_color"], applied["maps"]["base_color_estimate"])
    assert np.allclose(applied["maps"]["height"], baseline["maps"]["height"], atol=1.0e-6)
    assert applied["base_color_provenance"]["estimate_applied"] is True

    compare = render_plane_preview_from_generated(
        delighted,
        {"delight_enabled": True},
        preview_mode="delight_compare",
        output_path=tmp_path / "compare.png",
        width=192,
    )
    compare_image = Image.open(compare["preview_path"]).convert("RGB")
    assert compare["preview_mode"] == "delight_compare"
    assert compare_image.width == 192
    assert compare_image.height >= 64
    albedo = render_plane_preview_from_generated(
        delighted,
        {"delight_enabled": True},
        preview_mode="albedo",
        output_path=tmp_path / "albedo.png",
        width=96,
    )
    assert albedo["preview_mode"] == "albedo"
    assert Image.open(albedo["preview_path"]).size[0] == 96
    intrinsic = render_plane_preview_from_generated(
        delighted,
        {"delight_enabled": True},
        preview_mode="intrinsic_channels",
        output_path=tmp_path / "intrinsic.png",
        width=240,
    )
    intrinsic_image = Image.open(intrinsic["preview_path"]).convert("RGB")
    assert intrinsic["preview_mode"] == "intrinsic_channels"
    assert intrinsic_image.width == 240
    assert intrinsic_image.height >= 64


def test_texture_map_lab_marigold_iid_is_separate_and_explicit(tmp_path, monkeypatch) -> None:
    from app.ar_pbr.texture_map_lab import generate_texture_maps
    import app.ar_pbr.marigold_iid as iid_module

    image_path = tmp_path / "source.png"
    _sample_image(image_path)

    def fake_iid(image, settings):
        width, height = image.size
        return {
            "albedo": np.full((height, width, 3), (0.25, 0.5, 0.75), dtype=np.float32),
            "shading": np.full((height, width, 3), 0.6, dtype=np.float32),
            "residual": np.full((height, width, 3), 0.1, dtype=np.float32),
            "metadata": {
                "backend": "marigold_iid_lighting",
                "checkpoint": settings["iid_checkpoint"],
                "equation": "I = A * S + R",
                "conversion": "official_diffusers_visualize_intrinsics",
            },
        }

    monkeypatch.setattr(iid_module, "run_marigold_iid_lighting", fake_iid)
    baseline = generate_texture_maps(image_path, {"delight_enabled": False}, backend="cpu", allow_cpu=True)
    generated = generate_texture_maps(
        image_path,
        {"delight_enabled": True, "delight_method": "marigold_iid_lighting"},
        backend="cpu",
        allow_cpu=True,
    )

    assert np.allclose(generated["maps"]["base_color"], generated["maps"]["base_color_source"])
    assert np.allclose(generated["maps"]["base_color_estimate"], (0.25, 0.5, 0.75))
    assert np.allclose(generated["maps"]["iid_shading"], 0.6)
    assert np.allclose(generated["maps"]["iid_residual"], 0.1)
    assert np.allclose(generated["maps"]["height"], baseline["maps"]["height"])
    assert generated["base_color_provenance"]["method"] == "marigold_iid_lighting"
    assert generated["base_color_provenance"]["estimate_applied"] is False
    assert generated["algorithms"]["delight"]["equation"] == "I = A * S + R"

    applied = generate_texture_maps(
        image_path,
        {
            "delight_enabled": True,
            "delight_method": "marigold_iid_lighting",
            "delight_apply_to_base_color": True,
        },
        backend="cpu",
        allow_cpu=True,
    )
    assert np.allclose(applied["maps"]["base_color"], applied["maps"]["base_color_estimate"])
    assert np.allclose(applied["maps"]["height"], baseline["maps"]["height"])
    assert applied["base_color_provenance"]["export_source"] == "marigold_iid_lighting_albedo"


def test_marigold_iid_uses_official_target_properties_visualizer(monkeypatch) -> None:
    from contextlib import nullcontext
    import app.ar_pbr.marigold_iid as iid_module

    calls = {}

    class FakeGenerator:
        def __init__(self, device):
            calls["generator_device"] = device

        def manual_seed(self, seed):
            calls["seed"] = seed
            return self

    class FakeTorch:
        Generator = FakeGenerator

        @staticmethod
        def inference_mode():
            return nullcontext()

    class FakeProcessor:
        def visualize_intrinsics(self, prediction, target_properties):
            calls["prediction"] = prediction
            calls["target_properties"] = target_properties
            return [{
                "albedo": Image.new("RGB", (8, 6), (64, 128, 192)),
                "shading": Image.new("RGB", (8, 6), (128, 128, 128)),
                "residual": Image.new("RGB", (8, 6), (16, 32, 48)),
            }]

    class FakeOutput:
        prediction = np.zeros((3, 6, 8, 3), dtype=np.float32)

    class FakePipe:
        target_properties = {"target_names": ["albedo", "shading", "residual"]}
        image_processor = FakeProcessor()

        def __call__(self, image, **kwargs):
            calls["kwargs"] = kwargs
            return FakeOutput()

    monkeypatch.setattr(iid_module, "_pipeline", lambda checkpoint, allow_download: (FakePipe(), FakeTorch(), checkpoint))
    result = iid_module.run_marigold_iid_lighting(
        Image.new("RGB", (8, 6), "white"),
        {
            "iid_checkpoint": iid_module.MARIGOLD_IID_CHECKPOINT,
            "iid_denoise_steps": 4,
            "iid_ensemble_size": 1,
            "iid_processing_resolution": 768,
            "iid_seed": 17,
        },
    )

    assert calls["target_properties"] is FakePipe.target_properties
    assert calls["kwargs"]["num_inference_steps"] == 4
    assert calls["kwargs"]["processing_resolution"] == 768
    assert calls["kwargs"]["match_input_resolution"] is True
    assert calls["seed"] == 17
    assert result["albedo"].shape == (6, 8, 3)
    assert result["metadata"]["conversion"] == "official_diffusers_visualize_intrinsics"


def test_marigold_iid_status_and_install_plan_are_offline_and_durable() -> None:
    from app.ar_pbr.marigold_iid import marigold_iid_install_plan, marigold_iid_status

    status = marigold_iid_status()
    plan = marigold_iid_install_plan("C:/Tiger/Python/python.exe")

    assert status["checkpoint_id"] == "prs-eth/marigold-iid-lighting-v1-1"
    assert "external\\models\\marigold-iid-lighting-v1-1" in status["checkpoint_dir"]
    assert "debugCapture" not in status["checkpoint_dir"]
    assert plan["dependency_program"] == "C:/Tiger/Python/python.exe"
    assert any(arg.startswith("diffusers") for arg in plan["dependency_args"])
    assert "snapshot_download" in " ".join(plan["download_args"])
    assert plan["license"].startswith("OpenRAIL++")


def test_texture_map_lab_exports_separate_and_packed_maps(tmp_path) -> None:
    from app.ar_pbr.texture_map_lab import export_texture_maps

    image_path = tmp_path / "source.png"
    out_dir = tmp_path / "out"
    _sample_image(image_path)

    payload = export_texture_maps(
        image_path,
        out_dir,
        {"roughness_bias": 0.61},
        packed_layouts=("unreal_orm", "gltf_mr", "arm"),
    )

    assert (out_dir / "source_base_color.png").exists()
    assert (out_dir / "source_normal.png").exists()
    assert (out_dir / "source_curvature.png").exists()
    assert not (out_dir / "source_f0.png").exists()
    assert not (out_dir / "source_f90_mask.png").exists()
    assert (out_dir / "source_unreal_orm.png").exists()
    assert (out_dir / "source_gltf_mr.png").exists()
    assert (out_dir / "source_arm.png").exists()
    manifest = json.loads((out_dir / "source_pbr_manifest.json").read_text(encoding="utf-8"))
    assert manifest["substrate"]["base_color_workflow"]["substrate"]["helper"] == (
        "Substrate Metalness-To-DiffuseAlbedo-F0"
    )
    assert manifest["packed_layouts"]["unreal_orm"]["channels"] == {
        "R": "ambient_occlusion",
        "G": "roughness",
        "B": "metallic",
    }
    assert manifest["packed_layouts"]["gltf_mr"]["channels"]["G"] == "roughness"
    assert manifest["algorithms"]["curvature"]["method"] == "signed_heightfield_laplacian"
    assert manifest["substrate"]["optional_substrate_maps"]["f0"]["default_export"] is False


def test_texture_map_lab_exports_optional_substrate_maps(tmp_path) -> None:
    from app.ar_pbr.texture_map_lab import export_texture_maps

    image_path = tmp_path / "source.png"
    out_dir = tmp_path / "out"
    _sample_image(image_path)

    payload = export_texture_maps(
        image_path,
        out_dir,
        {"substrate_reflectance": 0.35, "f90_mask_strength": 0.75},
        maps=("base_color", "f0", "f90_mask"),
        packed_layouts=(),
    )

    assert (out_dir / "source_base_color.png").exists()
    assert (out_dir / "source_f0.png").exists()
    assert (out_dir / "source_f90_mask.png").exists()
    assert "f0" in payload["files"]
    assert "f90_mask" in payload["files"]
    manifest = json.loads((out_dir / "source_pbr_manifest.json").read_text(encoding="utf-8"))
    assert manifest["unreal_texture_import_settings"]["f0"]["sRGB"] is False


def test_texture_map_lab_heightfield_horizon_ao_darkens_recesses(tmp_path) -> None:
    from app.ar_pbr.texture_map_lab import generate_texture_maps

    h, w = 48, 48
    rgb = np.full((h, w, 3), 0.72, dtype=np.float32)
    y, x = np.ogrid[:h, :w]
    basin = ((x - 24) ** 2 + (y - 24) ** 2) <= 12 ** 2
    inner = ((x - 24) ** 2 + (y - 24) ** 2) <= 6 ** 2
    rgb[basin] = 0.34
    rgb[inner] = 0.18
    image_path = tmp_path / "basin.png"
    Image.fromarray(np.clip(rgb * 255.0 + 0.5, 0, 255).astype(np.uint8), mode="RGB").save(image_path)

    payload = generate_texture_maps(
        image_path,
        {
            "ao_strength": 1.0,
            "ao_radius_px": 10.0,
            "ao_samples": 8,
            "ao_steps": 8,
            "ao_height_scale": 18.0,
            "cavity_strength": 1.0,
        },
    )
    maps = payload["maps"]
    center_ao = float(maps["ao"][24, 24])
    flat_ao = float(maps["ao"][5, 5])
    rim_cavity = float(maps["cavity"][24, 18])
    flat_cavity = float(maps["cavity"][5, 5])
    rim_curvature = float(maps["curvature"][24, 18])

    assert center_ao < flat_ao - 0.08
    assert rim_cavity < flat_cavity - 0.25
    assert rim_curvature < 0.5
    assert payload["algorithms"]["ambient_occlusion"]["source"] == "heightfield_horizon_search"


def test_texture_map_lab_packed_channels_match_source_maps(tmp_path) -> None:
    from app.ar_pbr.texture_map_lab import generate_texture_maps, pack_texture_channels

    image_path = tmp_path / "source.png"
    _sample_image(image_path)
    generated = generate_texture_maps(image_path, {"metallic_value": 0.25})
    maps = generated["maps"]

    packed = pack_texture_channels(maps, "unreal_orm")

    assert np.allclose(packed[..., 0], maps["ao"])
    assert np.allclose(packed[..., 1], maps["roughness"])
    assert np.allclose(packed[..., 2], maps["metallic"])


def test_texture_map_lab_plane_preview_and_substrate_plan(tmp_path) -> None:
    from app.ar_pbr.texture_map_lab import render_plane_preview, substrate_export_plan

    image_path = tmp_path / "source.png"
    out = tmp_path / "preview.png"
    _sample_image(image_path)

    payload = render_plane_preview(image_path, {"preview_environment": 0.35}, output_path=out, width=128)

    assert out.exists()
    preview = np.asarray(Image.open(out).convert("RGB"), dtype=np.float32)
    assert Image.open(out).size == (128, 96)
    assert preview.std() > 0.1
    assert payload["preview_mode"] == "material"
    assert payload["preview_shape"] == "plane"
    sphere_out = tmp_path / "sphere.png"
    sphere_payload = render_plane_preview(
        image_path,
        {"preview_environment": 0.35},
        output_path=sphere_out,
        preview_shape="sphere",
        width=128,
    )
    assert sphere_out.exists()
    sphere_preview = np.asarray(Image.open(sphere_out).convert("RGB"), dtype=np.float32)
    assert sphere_payload["preview_shape"] == "sphere"
    assert sphere_preview.std() > 0.1
    f0_payload = render_plane_preview(image_path, {}, output_path=tmp_path / "f0.png", preview_mode="f0", width=64)
    f90_payload = render_plane_preview(
        image_path,
        {},
        output_path=tmp_path / "f90.png",
        preview_mode="f90_mask",
        width=64,
    )
    assert f0_payload["preview_mode"] == "f0"
    assert f90_payload["preview_mode"] == "f90_mask"
    plan = substrate_export_plan({"normal_format": "opengl"})
    assert plan["normal"]["flip_green_channel_for_unreal"] is True
    assert plan["base_color_workflow"]["substrate"]["slab_inputs"]["F0"] == "helper.F0 or optional f0 map"


def test_texture_map_lab_actions_execute_without_editor_owner(tmp_path) -> None:
    from app.actions import build_default_action_registry
    from app.actions.ar_pbr_texture_lab_namespace import texture_lab_settings_schema

    image_path = tmp_path / "source.png"
    preview_path = tmp_path / "preview.png"
    out_dir = tmp_path / "maps"
    _sample_image(image_path)
    registry = build_default_action_registry(None)

    preview = registry.execute(
        "ar_pbr.texture_lab.preview",
        {
            "image_path": str(image_path),
            "output_path": str(preview_path),
            "preview_shape": "sphere",
            "width": 96,
            "allow_cpu": True,
        },
    ).to_dict()
    export = registry.execute(
        "ar_pbr.texture_lab.export",
        {"image_path": str(image_path), "output_dir": str(out_dir), "packed_layouts": ["arm"], "allow_cpu": True},
    ).to_dict()
    backend = registry.execute("ar_pbr.texture_lab.backend_status", {"allow_cpu": True}).to_dict()
    iid_status = registry.execute("ar_pbr.texture_lab.iid_status").to_dict()
    plan = registry.execute("ar_pbr.texture_lab.substrate_plan").to_dict()

    assert preview["ok"] is True
    assert preview_path.exists()
    assert preview["result"]["preview_shape"] == "sphere"
    assert export["ok"] is True
    assert export["changed"] is True
    assert (out_dir / "source_arm.png").exists()
    assert backend["ok"] is True
    assert backend["result"]["status"]["install_guidance"]["recommended_backend"] == "torch_cuda"
    assert iid_status["ok"] is True
    assert iid_status["result"]["checkpoint_id"] == "prs-eth/marigold-iid-lighting-v1-1"
    assert plan["ok"] is True
    assert plan["result"]["target"] == "Unreal Engine Substrate Slab BSDF"
    settings_props = texture_lab_settings_schema()["properties"]
    assert "delight_enabled" in settings_props
    assert "delight_apply_to_base_color" in settings_props
    assert settings_props["delight_method"]["enum"] == ["heuristic", "marigold_iid_lighting"]
    assert "preview_animate_light" in settings_props
    assert "substrate_mode" in settings_props


def test_texture_map_lab_actions_require_gpu_by_default(tmp_path, monkeypatch) -> None:
    from app.actions import build_default_action_registry

    image_path = tmp_path / "source.png"
    preview_path = tmp_path / "preview.png"
    _sample_image(image_path)
    monkeypatch.setenv("TIGERCAPTURE_TEXTURE_LAB_BACKEND", "cpu")
    monkeypatch.delenv("TIGERCAPTURE_TEXTURE_LAB_ALLOW_CPU", raising=False)
    registry = build_default_action_registry(None)

    preview = registry.execute(
        "ar_pbr.texture_lab.preview",
        {"image_path": str(image_path), "output_path": str(preview_path), "width": 96},
    ).to_dict()
    backend = registry.execute("ar_pbr.texture_lab.backend_status").to_dict()

    assert preview["ok"] is False
    assert "GPU backend" in preview["error"]
    assert backend["ok"] is True
    assert backend["result"]["active"] == "unavailable"
    assert backend["result"]["reason"] == "cpu_backend_disabled_by_policy"
    assert preview_path.exists() is False


def test_texture_lab_gpu_install_plan_is_executable_contract() -> None:
    from app.ar_pbr.texture_map_lab import texture_lab_gpu_install_plan

    plan = texture_lab_gpu_install_plan("C:/Tiger/Python/python.exe")

    assert plan["backend"] == "torch_cuda"
    assert plan["install_program"] == "C:/Tiger/Python/python.exe"
    assert plan["install_args"][:5] == ["-m", "pip", "install", "torch", "torchvision"]
    assert "--index-url" in plan["install_args"]
    assert "download.pytorch.org" in plan["install_command"]
    assert plan["verify_program"] == "C:/Tiger/Python/python.exe"
    assert "torch.cuda.is_available" in " ".join(plan["verify_args"])
    assert "TIGERCAPTURE_TEXTURE_LAB_BACKEND" in plan["env_override"]


def test_texture_map_lab_window_supports_clipboard_copy_and_paste(tmp_path) -> None:
    app = _qt_app()
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication

    from app.ar_pbr.texture_map_lab_window import ArPbrTextureMapLabWindow

    image_path = tmp_path / "source.png"
    _sample_image(image_path)
    window = ArPbrTextureMapLabWindow(image_path, allow_cpu=True)
    window.refresh_preview()
    assert window._light_animation_timer.interval() == 16
    assert window.settings()["preview_light_azimuth"] == pytest.approx(-45.0)
    assert window.settings()["preview_light_elevation"] == pytest.approx(45.0)
    assert window._gpu_setup_button.text() == "Install GPU"
    assert window._ai_setup_button.text() == "Install AI IID"
    assert window._export_max_size() == 4096
    assert window.sizeHint().width() <= 1200
    assert window._preview.thumbnail_count() >= 10
    assert window._preview_shape_combo.currentData() == "plane"
    window._preview_shape_combo.setCurrentIndex(window._preview_shape_combo.findData("sphere"))
    window.refresh_preview()
    assert window._preview_heading is not None
    assert window._preview_heading.text().startswith("Sphere Preview")
    window._preview_shape_combo.setCurrentIndex(window._preview_shape_combo.findData("plane"))
    assert window._advanced_map_checks["f0"].isChecked() is False
    assert window._delight_check is not None
    assert window._delight_method_combo.currentData() == "heuristic"
    assert window._delight_apply_check is not None
    assert window._delight_apply_check.isEnabled() is False
    assert window._sliders["delight_strength"].isEnabled() is False
    window._delight_check.setChecked(True)
    assert window._sliders["delight_strength"].isEnabled() is True
    assert window._delight_apply_check.isEnabled() is True
    assert window._delight_apply_check.isChecked() is False
    window._delight_method_combo.setCurrentIndex(
        window._delight_method_combo.findData("marigold_iid_lighting")
    )
    assert window.settings()["delight_method"] == "marigold_iid_lighting"
    assert window._sliders["delight_strength"].isEnabled() is False
    window._delight_method_combo.setCurrentIndex(window._delight_method_combo.findData("heuristic"))
    assert window._preview_mode_combo.currentData() == "albedo"
    window._show_delight_compare_preview()
    assert window._preview_mode_combo.currentData() == "delight_compare"
    window._show_albedo_preview()
    assert window._preview_mode_combo.currentData() == "albedo"
    window._show_intrinsic_channels_preview()
    assert window._preview_mode_combo.currentData() == "intrinsic_channels"
    window.refresh_preview()
    assert window._preview_heading is not None
    assert window._preview_heading.text().endswith("Analysis Channels")

    copied = window.copy_preview_to_clipboard()
    assert copied["copied"] is True
    assert QApplication.clipboard().mimeData().hasImage()

    pasted_image = QImage(18, 12, QImage.Format.Format_ARGB32)
    pasted_image.fill(QColor("#336699"))
    QApplication.clipboard().setImage(pasted_image)
    pasted = window.paste_image_from_clipboard()
    app.processEvents()

    assert pasted["pasted"] is True
    assert pasted["source_kind"] == "clipboard_image"
    assert Path(pasted["source_path"]).exists()
    assert window.image_path == Path(pasted["source_path"])
    assert window._last_preview_path is None
    assert window._preview.preview_pixmap().isNull() is False
    window.close()


def test_texture_map_lab_paste_keeps_source_visible_without_gpu(tmp_path, monkeypatch) -> None:
    app = _qt_app()
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication

    from app.ar_pbr.texture_map_lab_window import ArPbrTextureMapLabWindow

    image_path = tmp_path / "source.png"
    _sample_image(image_path)
    monkeypatch.setenv("TIGERCAPTURE_TEXTURE_LAB_BACKEND", "cpu")
    monkeypatch.delenv("TIGERCAPTURE_TEXTURE_LAB_ALLOW_CPU", raising=False)
    window = ArPbrTextureMapLabWindow(image_path)

    pasted_image = QImage(24, 16, QImage.Format.Format_ARGB32)
    pasted_image.fill(QColor("#AA7733"))
    QApplication.clipboard().setImage(pasted_image)
    pasted = window.paste_image_from_clipboard()
    app.processEvents()

    assert pasted["pasted"] is True
    assert window._preview.preview_pixmap().isNull() is False
    assert window._preview.preview_pixmap().width() >= 64
    assert window._preview_heading is not None
    assert window._preview_heading.text() == "Source Preview"
    assert "Source preview ready" in window._status.text()
    window.close()


def test_texture_map_lab_opens_without_a_source_image_and_accepts_a_paste(monkeypatch) -> None:
    app = _qt_app()
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication

    from app.ar_pbr.texture_map_lab_window import ArPbrTextureMapLabWindow

    monkeypatch.setenv("TIGERCAPTURE_TEXTURE_LAB_BACKEND", "cpu")
    monkeypatch.delenv("TIGERCAPTURE_TEXTURE_LAB_ALLOW_CPU", raising=False)
    window = ArPbrTextureMapLabWindow()

    assert window.image_path is None
    assert window.windowTitle() == "AR/PBR Texture Lab"
    assert "Ctrl+V" in window._subtitle.text()
    assert "Ctrl+V" in window._status.text()

    pasted_image = QImage(24, 16, QImage.Format.Format_ARGB32)
    pasted_image.fill(QColor("#AA7733"))
    QApplication.clipboard().setImage(pasted_image)
    pasted = window.paste_image_from_clipboard()
    app.processEvents()

    assert pasted["pasted"] is True
    assert window.image_path is not None
    assert window._preview.preview_pixmap().isNull() is False
    window.close()


def test_texture_map_lab_sphere_source_preview_works_without_gpu(tmp_path, monkeypatch) -> None:
    app = _qt_app()
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication

    from app.ar_pbr.texture_map_lab_window import ArPbrTextureMapLabWindow

    image_path = tmp_path / "source.png"
    _sample_image(image_path)
    monkeypatch.setenv("TIGERCAPTURE_TEXTURE_LAB_BACKEND", "cpu")
    monkeypatch.delenv("TIGERCAPTURE_TEXTURE_LAB_ALLOW_CPU", raising=False)
    window = ArPbrTextureMapLabWindow(image_path)
    sphere_index = window._preview_shape_combo.findData("sphere")
    assert sphere_index >= 0
    window._preview_shape_combo.setCurrentIndex(sphere_index)

    pasted_image = QImage(32, 32, QImage.Format.Format_ARGB32)
    pasted_image.fill(QColor("#3366CC"))
    QApplication.clipboard().setImage(pasted_image)
    window.paste_image_from_clipboard()
    app.processEvents()

    pixmap = window._preview.preview_pixmap()
    assert pixmap.isNull() is False
    assert pixmap.width() >= 64
    assert window._preview_heading is not None
    assert window._preview_heading.text().startswith("Sphere Source Preview")
    assert "Source preview ready" in window._status.text()
    window.close()


def test_texture_map_lab_unavailable_gpu_uses_immediate_source_preview(tmp_path, monkeypatch) -> None:
    app = _qt_app()
    import app.ar_pbr.texture_map_lab_window as lab_window_module
    from app.ar_pbr.texture_map_lab_window import ArPbrTextureMapLabWindow

    image_path = tmp_path / "source.png"
    _sample_image(image_path)
    monkeypatch.setattr(
        lab_window_module,
        "select_texture_map_backend",
        lambda *args, **kwargs: {
            "requested": "auto",
            "active": "unavailable",
            "allow_cpu": False,
            "reason": "gpu_backend_required",
            "status": {"backends": {"torch_cuda": {"module_installed": False, "available": False}}},
        },
    )
    monkeypatch.setattr(
        lab_window_module,
        "generate_texture_maps",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("GPU generation must not run")),
    )
    window = ArPbrTextureMapLabWindow(image_path)
    sphere_index = window._preview_shape_combo.findData("sphere")
    window._preview_shape_combo.setCurrentIndex(sphere_index)
    window.refresh_preview()
    app.processEvents()

    assert window._preview.preview_pixmap().isNull() is False
    assert window._preview_heading.text() == "Sphere Source Preview"
    assert "Source preview ready" in window._status.text()
    window.close()


def test_texture_map_lab_window_defers_render_without_blanketing_window_updates(tmp_path) -> None:
    app = _qt_app()
    from app.ar_pbr.texture_map_lab_window import ArPbrTextureMapLabWindow

    image_path = tmp_path / "source.png"
    _sample_image(image_path)
    window = ArPbrTextureMapLabWindow(image_path, allow_cpu=True)
    window.show()
    app.processEvents()

    window._begin_interactive_window_motion()

    window.queue_preview()
    window.refresh_preview()

    assert window._window_motion_active is True
    assert window._window_updates_frozen is False
    assert window._preview_refresh_deferred is True
    assert window._preview_timer.isActive() is False
    assert window.centralWidget().updatesEnabled() is True

    window._end_interactive_window_motion()
    app.processEvents()

    assert window._window_updates_frozen is False
    assert window.centralWidget().updatesEnabled() is True
    assert window._preview._interactive_paint is False
    assert window._window_motion_active is False
    assert window._preview_refresh_deferred is False
    window.close()


def test_texture_map_lab_preview_canvas_grab_contains_source_pixels_without_gpu(tmp_path, monkeypatch) -> None:
    app = _qt_app()
    from app.ar_pbr.texture_map_lab_window import ArPbrTextureMapLabWindow

    image_path = tmp_path / "source.png"
    _sample_image(image_path)
    monkeypatch.setenv("TIGERCAPTURE_TEXTURE_LAB_BACKEND", "cpu")
    monkeypatch.delenv("TIGERCAPTURE_TEXTURE_LAB_ALLOW_CPU", raising=False)
    window = ArPbrTextureMapLabWindow(image_path)
    window.show()
    app.processEvents()

    grab = window._preview.grab().toImage()
    sampled_colors = {
        grab.pixelColor(x, y).name()
        for y in range(0, grab.height(), max(1, grab.height() // 20))
        for x in range(0, grab.width(), max(1, grab.width() // 20))
    }

    assert window._preview.preview_pixmap().isNull() is False
    assert len(sampled_colors) > 4
    assert sampled_colors != {"#08090c"}
    window.close()
