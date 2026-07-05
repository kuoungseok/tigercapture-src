from app.ar_pbr.asset_support import (
    asset_support_status_text,
    classify_asset_support,
    placeholder_asset_support,
    public_asset_support,
    summarize_asset_support,
)
from app.ar_pbr.importer import import_asset


def _descriptor(**updates):
    base = {
        "source_path": "sample.glb",
        "source_ext": ".glb",
        "source_format": "glb",
        "requires_runtime_conversion": False,
        "import_state": "ready",
        "backend": "internal_gltf",
        "geometries": [{"triangle_count": 12, "triangles": [[0, 1, 2]]}],
        "materials": [{"name": "paint", "base_texture": "paint.png", "roughness": 0.4, "metallic": 0.0}],
        "texture_count": 1,
        "animation_count": 0,
        "skeletal_mesh_count": 0,
        "skin_count": 0,
    }
    base.update(updates)
    return base


def test_static_gltf_asset_is_ready_for_full_gpu_pbr():
    report = classify_asset_support(_descriptor(), {"imported": True, "fallback": False})

    assert report["support_level"] == "ready"
    assert report["confidence"] == "high"
    assert report["asset_kind"] == "static_mesh"
    assert report["render_path"] == "full_gpu_pbr"
    assert report["ok_for_preview"] is True
    assert report["ok_for_export"] is True


def test_skeletal_gltf_asset_reports_cpu_baked_animation_path():
    report = classify_asset_support(
        _descriptor(
            animation_count=2,
            animation_clips=[{"name": "walk"}],
            skeletal_mesh_count=1,
            skin_count=1,
            geometries=[
                {
                    "triangle_count": 36,
                    "triangles": [[0, 1, 2]],
                    "skin_weights": [[1.0, 0.0, 0.0, 0.0]],
                }
            ],
        ),
        {"imported": True, "fallback": False},
    )

    assert report["support_level"] == "ready"
    assert report["asset_kind"] == "skeletal_mesh"
    assert report["render_path"] == "full_gpu_pbr_cpu_baked_skeletal"
    assert "skeletal_mesh" in report["feature_flags"]
    assert "animation_clips" in report["feature_flags"]


def test_fbx_static_asset_is_limited_but_exportable():
    report = classify_asset_support(
        _descriptor(
            source_path="scooter.fbx",
            source_ext=".fbx",
            source_format="fbx",
            requires_runtime_conversion=True,
            backend="internal_binary_fbx",
        ),
        {"imported": True, "fallback": False, "backend": "internal_binary_fbx"},
    )

    assert report["support_level"] == "limited"
    assert report["confidence"] == "medium"
    assert report["ok_for_preview"] is True
    assert report["ok_for_export"] is True
    assert "fbx_runtime_conversion_required" in report["issue_codes"]


def test_static_mesh_animation_is_supported_feature_not_error():
    report = classify_asset_support(
        _descriptor(animation_count=1, animation_clips=[{"name": "door"}]),
        {"imported": True, "fallback": False},
    )

    assert report["asset_kind"] == "animated_static_mesh"
    assert report["render_path"] == "full_gpu_pbr_cpu_baked_animation"
    assert "static_mesh_animation" in report["feature_flags"]
    assert "animation_without_skeletal_mesh" not in report["issue_codes"]


def test_compressed_required_gltf_is_unsupported_not_misreported_ready():
    report = classify_asset_support(
        _descriptor(import_state="placeholder", backend="placeholder", geometries=[], materials=[]),
        {
            "imported": False,
            "fallback": True,
            "warnings": [
                "internal glTF failed: ValueError: unsupported required glTF mesh compression extension(s): KHR_draco_mesh_compression"
            ],
        },
    )

    assert report["support_level"] == "unsupported"
    assert report["confidence"] == "none"
    assert report["ok_for_preview"] is False
    assert "unsupported_required_compression" in report["issue_codes"]
    assert "compressed_mesh_unsupported" in report["feature_flags"]


def test_importer_attaches_support_report_to_descriptor_and_diagnostics(tmp_path):
    asset = tmp_path / "missing_model.glb"

    descriptor, diagnostics = import_asset(asset, settings={"disable_descriptor_cache": True})

    assert descriptor["support"]["support_level"] == "placeholder"
    assert diagnostics["support"]["support_level"] == "placeholder"
    assert descriptor["support"]["ok_for_preview"] is False
    assert "placeholder" in summarize_asset_support(descriptor["support"])


def test_preview_support_status_text_is_product_facing():
    from app.ar_pbr.preview_window import _support_status_text

    assert _support_status_text({"support_level": "ready", "asset_kind": "skeletal_mesh"}) == "Ready: skeletal PBR"
    assert _support_status_text({
        "support_level": "limited",
        "asset_kind": "static_mesh",
        "issue_codes": ["fbx_runtime_conversion_required"],
    }) == "Limited: FBX conversion"
    assert _support_status_text({
        "support_level": "unsupported",
        "issue_codes": ["unsupported_required_compression"],
    }) == "Unsupported: compressed mesh"


def test_preview_render_profile_rows_only_show_marmoset_when_available():
    from app.ar_pbr.preview_window import _render_profile_combo_rows

    unavailable = _render_profile_combo_rows({
        "profiles": {
            "authored": {"available": True},
            "marmoset_pbr": {"available": False},
        }
    })
    available = _render_profile_combo_rows({
        "profiles": {
            "authored": {"available": True},
            "marmoset_pbr": {"available": True},
        }
    })

    assert [row["id"] for row in unavailable] == ["authored"]
    assert [row["id"] for row in available] == ["authored", "marmoset_pbr"]


def test_public_asset_support_hides_internal_issue_codes():
    report = classify_asset_support(
        _descriptor(
            source_path="scooter.fbx",
            source_ext=".fbx",
            source_format="fbx",
            requires_runtime_conversion=True,
            backend="internal_binary_fbx",
        ),
        {"imported": True, "fallback": False, "backend": "internal_binary_fbx"},
    )

    row = public_asset_support(report, asset_path="scooter.fbx", track_id="ar_pbr_001")

    assert row["label"] == "Limited: FBX conversion"
    assert row["message"].startswith("Usable now")
    assert "issue_codes" not in row
    assert "fbx_runtime_conversion_required" not in str(row)


def test_placeholder_support_reports_background_import_without_heavy_probe(tmp_path):
    asset = tmp_path / "model.glb"
    report = placeholder_asset_support(asset, state="loading")

    assert report["support_level"] == "placeholder"
    assert asset_support_status_text(report) == "Loading: checking 3D support"
    assert public_asset_support(report, asset_path=str(asset))["ok_for_preview"] is False
