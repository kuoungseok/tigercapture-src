from tools.qa_ar_pbr_asset_support_matrix import run_asset_support_matrix


def test_asset_support_matrix_reports_expected_levels(tmp_path, monkeypatch):
    good = tmp_path / "good.glb"
    bad = tmp_path / "bad.glb"
    good.write_bytes(b"placeholder")
    bad.write_bytes(b"placeholder")

    def fake_import_asset(path, *, settings=None, project_root=None):
        if str(path).endswith("good.glb"):
            descriptor = {
                "source_path": str(path),
                "source_ext": ".glb",
                "import_state": "ready",
                "backend": "internal_gltf",
                "geometries": [{"triangle_count": 1, "triangles": [[0, 1, 2]]}],
                "materials": [{"name": "mat", "base_texture": "mat.png"}],
                "texture_count": 1,
                "animation_count": 0,
                "skeletal_mesh_count": 0,
                "skin_count": 0,
            }
            return descriptor, {"imported": True, "fallback": False, "backend": "internal_gltf"}
        descriptor = {
            "source_path": str(path),
            "source_ext": ".glb",
            "import_state": "placeholder",
            "backend": "placeholder",
            "geometries": [],
            "materials": [],
        }
        return descriptor, {
            "imported": False,
            "fallback": True,
            "backend": "placeholder",
            "warnings": ["KHR_draco_mesh_compression"],
        }

    monkeypatch.setattr("app.ar_pbr.importer.import_asset", fake_import_asset)

    report = run_asset_support_matrix(
        root=tmp_path,
        candidates=[
            {"id": "good", "path": "good.glb", "expected_levels": ["ready"]},
            {
                "id": "bad",
                "path": "bad.glb",
                "expected_levels": ["unsupported"],
                "expected_issues": ["unsupported_required_compression"],
            },
        ],
    )

    assert report["status"] == "pass"
    assert report["summary"]["pass_count"] == 2
    assert report["rows"][0]["support_level"] == "ready"
    assert report["rows"][1]["support_level"] == "unsupported"
