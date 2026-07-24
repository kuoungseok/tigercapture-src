from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from PIL import Image


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

    assert payload["schema_id"] == "tigerstudio.ar_pbr.texture_map_lab.v1"
    assert payload["size"] == [32, 24]
    maps = payload["maps"]
    assert {
        "base_color",
        "normal",
        "ao",
        "roughness",
        "metallic",
        "height",
        "cavity",
        "curvature",
        "f0",
        "f90_mask",
    } <= set(maps)
    assert maps["base_color"].shape == (24, 32, 3)
    assert maps["normal"].shape == (24, 32, 3)
    assert maps["roughness"].shape == (24, 32)
    assert maps["curvature"].shape == (24, 32)
    assert maps["f0"].shape == (24, 32, 3)
    assert maps["f90_mask"].shape == (24, 32)
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

    image_path = tmp_path / "source.png"
    preview_path = tmp_path / "preview.png"
    out_dir = tmp_path / "maps"
    _sample_image(image_path)
    registry = build_default_action_registry(None)

    preview = registry.execute(
        "ar_pbr.texture_lab.preview",
        {"image_path": str(image_path), "output_path": str(preview_path), "width": 96},
    ).to_dict()
    export = registry.execute(
        "ar_pbr.texture_lab.export",
        {"image_path": str(image_path), "output_dir": str(out_dir), "packed_layouts": ["arm"]},
    ).to_dict()
    backend = registry.execute("ar_pbr.texture_lab.backend_status").to_dict()
    plan = registry.execute("ar_pbr.texture_lab.substrate_plan").to_dict()

    assert preview["ok"] is True
    assert preview_path.exists()
    assert export["ok"] is True
    assert export["changed"] is True
    assert (out_dir / "source_arm.png").exists()
    assert backend["ok"] is True
    assert backend["result"]["status"]["install_guidance"]["recommended_backend"] == "torch_cuda"
    assert plan["ok"] is True
    assert plan["result"]["target"] == "Unreal Engine Substrate Slab BSDF"


def test_texture_map_lab_window_supports_clipboard_copy_and_paste(tmp_path) -> None:
    app = _qt_app()
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication

    from app.ar_pbr.texture_map_lab_window import ArPbrTextureMapLabWindow

    image_path = tmp_path / "source.png"
    _sample_image(image_path)
    window = ArPbrTextureMapLabWindow(image_path)
    window.refresh_preview()
    assert window._preview.thumbnail_count() >= 10
    assert window._advanced_map_checks["f0"].isChecked() is False

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
    assert window._last_preview_path is not None
    window.close()
