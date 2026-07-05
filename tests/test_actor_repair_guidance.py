from __future__ import annotations

import json


def test_actor_repair_guidance_explains_missing_spine_texture(tmp_path):
    from app.actor_compat_repair import actor_repair_guidance_report

    skel = tmp_path / "hero.json"
    skel.write_text(
        json.dumps({
            "skeleton": {"spine": "4.1"},
            "bones": [{"name": "root"}],
            "slots": [],
            "skins": {},
            "animations": {},
        }),
        encoding="utf-8",
    )
    atlas = tmp_path / "hero.atlas"
    atlas.write_text(
        "missing_page.png\nsize: 8,8\nformat: RGBA8888\n\nbody\n  xy: 0, 0\n  size: 8, 8\n",
        encoding="utf-8",
    )

    report = actor_repair_guidance_report("spine", str(atlas))

    assert report["kind"] == "spine"
    assert report["load_path"] == str(skel)
    assert report["path_changed"] is True
    assert report["warnings"]
    assert any("texture" in action.casefold() for action in report["actions"])
    assert report["ready_for_release_claim"] is False
    assert "Do not market this as all Unity/game-exported Live2D/Spine rigs compatible." in report["claim_guard"]


def test_actor_repair_guidance_surfaces_live2d_optional_mediapipe(tmp_path):
    from app.actor_compat_repair import actor_repair_guidance_report

    model = tmp_path / "hero.model3.json"
    (tmp_path / "hero.moc3").write_bytes(b"MOC3")
    model.write_text(
        json.dumps({
            "Version": 3,
            "FileReferences": {
                "Moc": "hero.moc3",
                "Textures": ["hero.2048/texture_00.png"],
                "Motions": {"Idle": [{"File": "idle.motion3.json"}]},
            },
        }),
        encoding="utf-8",
    )

    report = actor_repair_guidance_report(
        "live2d",
        str(model),
        status_row={
            "severity": "medium",
            "issue_codes": ["live2d_motion_ref_missing"],
            "risk_codes": ["live2d_many_motions"],
            "recommendation": "Relink missing Live2D motion references.",
        },
    )

    assert report["kind"] == "live2d"
    assert report["severity"] == "medium"
    assert "live2d_motion_ref_missing" in report["issue_codes"]
    assert any("Relink missing Live2D motion references." == action for action in report["actions"])
    assert report["optional_dependency_status"]["kind"] == "live2d"
    assert report["optional_dependency_status"]["optional_dependencies"][0]["id"] == "mediapipe_facemesh"
    assert report["ready_for_release_claim"] is False
