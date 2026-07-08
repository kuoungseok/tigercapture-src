from __future__ import annotations

import json


def test_ar_pbr_preview_window_loads_preset_scene_settings(tmp_path) -> None:
    from tools.ar_pbr_preview_window import _load_scene_settings_json

    preset = tmp_path / "preset.json"
    preset.write_text(
        json.dumps(
            {
                "view": {"yaw": 35.0},
                "scene_settings": {
                    "ambient_occlusion_mode": "screen",
                    "ao_strength": 1.25,
                    "ao_radius": 8.0,
                    "diffuse_gi_strength": 0.4,
                },
            }
        ),
        encoding="utf-8",
    )

    settings = _load_scene_settings_json(preset)

    assert settings["ambient_occlusion_mode"] == "screen"
    assert settings["ao_strength"] == 1.25
    assert settings["ao_radius"] == 8.0
    assert settings["diffuse_gi_strength"] == 0.4
