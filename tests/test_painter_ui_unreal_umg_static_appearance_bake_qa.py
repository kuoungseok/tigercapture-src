from __future__ import annotations

from pathlib import Path

from PIL import Image


def test_synthetic_static_texture_qa_package_and_pixel_gate(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import package_painter_umg
    from app.unreal_umg_static_appearance_bake import (
        STATIC_TEXTURE_BAKE_INTENDED_GATE,
        STATIC_TEXTURE_BAKE_KIND,
        STATIC_TEXTURE_BAKE_SCHEMA,
    )
    from tools.qa_painter_ui_unreal_umg_static_appearance_bake import (
        CANVAS_HEIGHT,
        CANVAS_WIDTH,
        LAYER_HEIGHT,
        LAYER_WIDTH,
        LAYER_X,
        LAYER_Y,
        SOURCE_PROVENANCE,
        _capture_evidence,
        _fixture,
        _materialization_evidence,
        _reference_capture,
        _write_synthetic_exact_render,
    )

    source = _write_synthetic_exact_render(tmp_path / "synthetic_texture.png")
    document = _fixture(Path(source["path"]), effect="texture")
    effect = document["objects"][0]["style"]["effects"][0]
    exact = document["objects"][0]["content"]["figma_exact_render"]
    assert effect == {
        "type": "texture",
        "visible": True,
        "radius": 4.0,
        "noise_size": 8.0,
        "clip_to_shape": True,
        "noise_size_vector": {"x": 8.0, "y": 12.0},
    }
    assert source["provenance"] == SOURCE_PROVENANCE
    assert exact["provenance"] == {
        "classification": SOURCE_PROVENANCE,
        "actual_figma_request": False,
    }

    package = package_painter_umg(document, tmp_path / "texture_package")
    materialization = _materialization_evidence(package, effect="texture")
    assert materialization["ok"] is True, materialization
    assert materialization["effect"] == "texture"
    assert materialization["source_provenance"] == SOURCE_PROVENANCE
    assert materialization["not_a_figma_visual_golden"] is True
    assert materialization["schema_version"] == 15
    assert materialization["expected_contract"] == {
        "schema_version": 15,
        "kind": STATIC_TEXTURE_BAKE_KIND,
        "source_schema": STATIC_TEXTURE_BAKE_SCHEMA,
        "gate": STATIC_TEXTURE_BAKE_INTENDED_GATE,
        "conversion": "static_texture_png_bake",
        "mapping": "texture2d_image_fill_from_static_texture_bake",
        "artifact_status": "tigerstudio_umg_schema15_artifact",
        "materialized_status": "tigerstudio_umg_schema15_materialized",
    }
    assert materialization["texture_size"] == [LAYER_WIDTH, LAYER_HEIGHT]
    assert materialization["content_hash"] == materialization[
        "actual_content_hash"
    ]
    assert materialization["pixel_rgba_sha256"] == materialization[
        "actual_pixel_rgba_sha256"
    ]

    reference = _reference_capture(package, effect="texture")
    reference_path = tmp_path / "texture_reference.png"
    reference.save(reference_path)
    passed = _capture_evidence(reference_path, package, effect="texture")
    assert passed["ok"] is True, passed
    assert passed["effect"] == "texture"
    assert passed["exact_crop_pixel_hash"] is True
    assert passed["expected_crop_pixel_rgba_sha256"] == passed[
        "actual_crop_pixel_rgba_sha256"
    ]
    assert passed["capture_size"] == [CANVAS_WIDTH, CANVAS_HEIGHT]
    assert passed["alpha_bounds"] == [
        LAYER_X,
        LAYER_Y,
        LAYER_X + LAYER_WIDTH - 1,
        LAYER_Y + LAYER_HEIGHT - 1,
    ]


def test_synthetic_static_appearance_qa_package_and_pixel_gate(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import package_painter_umg
    from tools.qa_painter_ui_unreal_umg_static_appearance_bake import (
        CANVAS_HEIGHT,
        CANVAS_WIDTH,
        LAYER_HEIGHT,
        LAYER_WIDTH,
        LAYER_X,
        LAYER_Y,
        SOURCE_PROVENANCE,
        _capture_evidence,
        _fixture,
        _materialization_evidence,
        _reference_capture,
        _write_synthetic_exact_render,
    )

    source = _write_synthetic_exact_render(tmp_path / "synthetic.png")
    document = _fixture(Path(source["path"]))
    exact = document["objects"][0]["content"]["figma_exact_render"]
    assert source["provenance"] == SOURCE_PROVENANCE
    assert exact["provenance"] == {
        "classification": SOURCE_PROVENANCE,
        "actual_figma_request": False,
    }

    package = package_painter_umg(document, tmp_path / "package")
    materialization = _materialization_evidence(package)
    assert materialization["ok"] is True, materialization
    assert materialization["source_provenance"] == SOURCE_PROVENANCE
    assert materialization["not_a_figma_visual_golden"] is True
    assert materialization["schema_version"] == 14
    assert materialization["texture_size"] == [LAYER_WIDTH, LAYER_HEIGHT]
    assert materialization["content_hash"] == materialization[
        "actual_content_hash"
    ]
    assert materialization["pixel_rgba_sha256"] == materialization[
        "actual_pixel_rgba_sha256"
    ]

    reference = _reference_capture(package)
    reference_path = tmp_path / "reference.png"
    reference.save(reference_path)
    passed = _capture_evidence(reference_path, package)
    assert passed["ok"] is True, passed
    assert passed["capture_size"] == [CANVAS_WIDTH, CANVAS_HEIGHT]
    assert passed["alpha_bounds"] == [
        LAYER_X,
        LAYER_Y,
        LAYER_X + LAYER_WIDTH - 1,
        LAYER_Y + LAYER_HEIGHT - 1,
    ]

    shifted = Image.new(
        "RGBA",
        (CANVAS_WIDTH, CANVAS_HEIGHT),
        (0, 0, 0, 0),
    )
    with Image.open(materialization["texture_path"]) as source_image:
        shifted.alpha_composite(source_image.convert("RGBA"), (LAYER_X + 1, LAYER_Y))
    shifted_path = tmp_path / "shifted.png"
    shifted.save(shifted_path)
    shifted_evidence = _capture_evidence(shifted_path, package)
    assert shifted_evidence["ok"] is False
    assert "capture_appearance_bounds_mismatch" in shifted_evidence["errors"]

    corrupted = reference.copy()
    sample = (LAYER_X + LAYER_WIDTH // 2, LAYER_Y + LAYER_HEIGHT // 2)
    expected = corrupted.getpixel(sample)
    corrupted.putpixel(
        sample,
        (255 - expected[0], 255 - expected[1], 255 - expected[2], expected[3]),
    )
    corrupted_path = tmp_path / "corrupted.png"
    corrupted.save(corrupted_path)
    corrupted_evidence = _capture_evidence(corrupted_path, package)
    assert corrupted_evidence["ok"] is False
    assert "capture_sample_pixel_mismatch" in corrupted_evidence["errors"]


def test_installed_plugin_binary_gate_requires_exact_bundle_dlls(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_unreal_umg_static_appearance_bake import (
        REQUIRED_PLUGIN_DLLS,
        _installed_plugin_binary_evidence,
    )

    bundled = tmp_path / "bundled"
    installed = tmp_path / "installed"
    for root in (bundled, installed):
        binary_root = root / "Binaries" / "Win64"
        binary_root.mkdir(parents=True)
        for index, name in enumerate(REQUIRED_PLUGIN_DLLS):
            (binary_root / name).write_bytes(
                f"synthetic-dll-{index}".encode("ascii")
            )
    generation = {
        "plugin": {
            "source_path": str(bundled),
            "installed_path": str(installed),
            "bundled_version": "1.4.0",
            "installed_version": "1.4.0",
        }
    }
    passed = _installed_plugin_binary_evidence(generation)
    assert passed["ok"] is True
    assert all(row["bundled_sha256"] for row in passed["dlls"])
    assert all(
        row["bundled_sha256"] == row["installed_sha256"]
        for row in passed["dlls"]
    )

    changed = installed / "Binaries" / "Win64" / REQUIRED_PLUGIN_DLLS[0]
    changed.write_bytes(b"different-installed-dll")
    failed = _installed_plugin_binary_evidence(generation)
    assert failed["ok"] is False
    assert failed["dlls"][0]["ok"] is False


def test_installed_plugin_binary_gate_accepts_new_version_when_required(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_unreal_umg_static_appearance_bake import (
        REQUIRED_PLUGIN_DLLS,
        _installed_plugin_binary_evidence,
    )

    bundled = tmp_path / "bundled"
    installed = tmp_path / "installed"
    for root in (bundled, installed):
        binary_root = root / "Binaries" / "Win64"
        binary_root.mkdir(parents=True)
        for index, name in enumerate(REQUIRED_PLUGIN_DLLS):
            (binary_root / name).write_bytes(
                f"schema15-texture-dll-{index}".encode("ascii")
            )
    generation = {
        "plugin": {
            "source_path": str(bundled),
            "installed_path": str(installed),
            "bundled_version": "1.6.0",
            "installed_version": "1.6.0",
        }
    }

    passed = _installed_plugin_binary_evidence(
        generation,
        expected_plugin_version="1.6.0",
    )
    assert passed["ok"] is True
    assert passed["version_ok"] is True
    assert passed["expected_plugin_version"] == "1.6.0"

    wrong_contract = _installed_plugin_binary_evidence(
        generation,
        expected_plugin_version="1.4.0",
    )
    assert wrong_contract["ok"] is False
    assert wrong_contract["version_ok"] is False
