from __future__ import annotations

import json


def test_live2d_candidate_ignores_vtube_settings_json(tmp_path):
    from app.live2d.compat import is_live2d_candidate
    from tools.test_live2d_resources import discover_candidates

    model = tmp_path / "avatar.model3.json"
    model.write_text(
        json.dumps({
            "Version": 3,
            "FileReferences": {
                "Moc": "avatar.moc3",
                "Textures": ["avatar.4096/texture_00.png"],
            },
        }),
        encoding="utf-8",
    )
    vtube = tmp_path / "avatar.vtube.json"
    vtube.write_text(
        json.dumps({
            "Version": 1,
            "FileReferences": {
                "Icon": "icon.png",
                "Model": "avatar.model3.json",
                "IdleAnimation": "idle.motion3.json",
            },
        }),
        encoding="utf-8",
    )

    candidates, bundles = discover_candidates(tmp_path)

    assert is_live2d_candidate(model)
    assert not is_live2d_candidate(vtube)
    assert candidates == [model]
    assert bundles == []


def test_live2d_child_payload_parser_handles_native_log_interleaving():
    from tools.test_live2d_resources import RESULT_PREFIX, _extract_child_payload

    stdout = (
        "[INFO] load motion without newline "
        + RESULT_PREFIX
        + '{"status": "pass", "runtime": "model.model3.json"}'
        + "\n[INFO] native cleanup after result\n"
    )

    payload = _extract_child_payload(stdout)

    assert payload == {"status": "pass", "runtime": "model.model3.json"}
