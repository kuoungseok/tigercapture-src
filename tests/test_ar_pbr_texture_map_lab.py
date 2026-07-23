from __future__ import annotations

import json

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


def test_texture_map_lab_generates_unreal_ready_maps(tmp_path) -> None:
    from app.ar_pbr.texture_map_lab import generate_texture_maps

    image_path = tmp_path / "source.png"
    _sample_image(image_path)

    payload = generate_texture_maps(image_path, {"normal_strength": 3.0})

    assert payload["schema_id"] == "tigerstudio.ar_pbr.texture_map_lab.v1"
    assert payload["size"] == [32, 24]
    maps = payload["maps"]
    assert {"base_color", "normal", "ao", "roughness", "metallic", "height", "cavity"} <= set(maps)
    assert maps["base_color"].shape == (24, 32, 3)
    assert maps["normal"].shape == (24, 32, 3)
    assert maps["roughness"].shape == (24, 32)
    assert float(np.mean(maps["normal"][..., 2])) > 0.7
    assert float(np.max(maps["metallic"])) == 0.0


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
    plan = substrate_export_plan({"normal_format": "opengl"})
    assert plan["normal"]["flip_green_channel_for_unreal"] is True
    assert plan["base_color_workflow"]["substrate"]["slab_inputs"]["F0"] == "helper.F0"


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
    plan = registry.execute("ar_pbr.texture_lab.substrate_plan").to_dict()

    assert preview["ok"] is True
    assert preview_path.exists()
    assert export["ok"] is True
    assert export["changed"] is True
    assert (out_dir / "source_arm.png").exists()
    assert plan["ok"] is True
    assert plan["result"]["target"] == "Unreal Engine Substrate Slab BSDF"
