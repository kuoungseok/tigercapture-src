from pathlib import Path


def test_hdri_presets_are_available_from_manifest():
    from app.ar_pbr.hdri_presets import hdri_presets

    presets = hdri_presets()
    ids = {preset.id for preset in presets}

    assert {"wide_street_01", "studio_small_09", "belfast_sunset", "cobblestone_street_night"} <= ids
    assert all(preset.path.exists() for preset in presets)
    assert all(preset.path.suffix.lower() in {".hdr", ".exr"} for preset in presets)


def test_default_hdri_path_resolves_to_downloaded_asset():
    from app.ar_pbr.hdri_presets import default_hdri_path

    path = default_hdri_path()

    assert isinstance(path, Path)
    assert path.exists()
    assert path.name.endswith("_1k.hdr")


def test_ar_pbr_lighting_schema_preserves_hdri_selection():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "hdri_id": "belfast_sunset",
        "hdri_path": "resources/ar_pbr/hdri/belfast_sunset_1k.hdr",
        "ibl_exposure": 1.7,
    })

    assert lighting["hdri_id"] == "belfast_sunset"
    assert lighting["hdri_path"].endswith("belfast_sunset_1k.hdr")
    assert lighting["ibl_exposure"] == 1.7
