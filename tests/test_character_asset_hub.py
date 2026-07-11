from __future__ import annotations

import os
import json
import struct
from pathlib import Path


def _write_vrm0_glb(path: Path) -> None:
    gltf = {
        "asset": {"version": "2.0"},
        "extensions": {
            "VRM": {
                "meta": {"title": "Hub Avatar", "author": "QA"},
                "humanoid": {"humanBones": [{"bone": "hips"}, {"bone": "head"}]},
                "blendShapeMaster": {"blendShapeGroups": [{"name": "A"}, {"name": "Blink"}]},
            }
        },
    }
    payload = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    padding = (4 - (len(payload) % 4)) % 4
    payload += b" " * padding
    total = 12 + 8 + len(payload)
    path.write_bytes(
        b"glTF"
        + struct.pack("<II", 2, total)
        + struct.pack("<II", len(payload), 0x4E4F534A)
        + payload
    )


def _make_character_pack(root: Path) -> dict[str, Path]:
    live2d = root / "Live2D" / "Avatar"
    live2d.mkdir(parents=True)
    (live2d / "avatar.moc3").write_bytes(b"MOC3" + bytes([5, 0, 0, 0]))
    (live2d / "texture_00.png").write_bytes(b"png")
    (live2d / "motions").mkdir()
    (live2d / "motions" / "idle.motion3.json").write_text("{}", encoding="utf-8")
    model3 = live2d / "avatar.model3.json"
    model3.write_text(
        json.dumps(
            {
                "Version": 3,
                "FileReferences": {
                    "Moc": "avatar.moc3",
                    "Textures": ["texture_00.png"],
                    "Motions": {"Idle": [{"File": "motions/idle.motion3.json", "Name": "idle"}]},
                    "Expressions": [{"Name": "smile", "File": "expressions/smile.exp3.json"}],
                },
            }
        ),
        encoding="utf-8",
    )

    spine = root / "Spine" / "Hero"
    spine.mkdir(parents=True)
    spine_json = spine / "hero.json"
    spine_json.write_text(
        json.dumps(
            {
                "skeleton": {"spine": "4.1"},
                "bones": [{"name": "root"}],
                "slots": [{"name": "slot", "bone": "root"}],
                "skins": [{"name": "default"}, {"name": "party"}],
                "animations": {"idle": {}, "run": {}},
            }
        ),
        encoding="utf-8",
    )
    (spine / "hero.atlas").write_text("hero.png\nsize: 64,64\n\nslot\nbounds: 0,0,32,32\n", encoding="utf-8")
    (spine / "hero.png").write_bytes(b"png")

    mmd = root / "MMD" / "Idol"
    mmd.mkdir(parents=True)
    pmx = mmd / "idol.pmx"
    pmx.write_bytes(b"PMX dummy")
    vmd = mmd / "dance.vmd"
    vmd.write_bytes(b"Vocaloid Motion Data 0002")

    vrm = root / "VRM"
    vrm.mkdir()
    vrm_path = vrm / "avatar.vrm"
    _write_vrm0_glb(vrm_path)

    return {"live2d": model3, "spine": spine_json, "mmd": pmx, "vmd": vmd, "vrm": vrm_path}


def _by_kind(report: dict) -> dict[str, list[dict]]:
    rows: dict[str, list[dict]] = {}
    for asset in report["assets"]:
        rows.setdefault(asset["kind"], []).append(asset)
    return rows


def _ensure_qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_character_asset_hub_scans_mixed_folder_and_builds_timeline_payloads(tmp_path):
    from app.character_asset_hub import scan_character_asset_folder

    paths = _make_character_pack(tmp_path)
    report = scan_character_asset_folder(tmp_path)
    rows = _by_kind(report)

    assert report["ok"] is True
    assert report["counts"] == {"live2d": 1, "spine": 1, "mmd": 1, "vrm": 1}
    assert report["timeline_addable_count"] == 4

    live2d = rows["live2d"][0]
    assert live2d["path"] == str(paths["live2d"].resolve())
    assert live2d["render"]["capable"] is True
    assert live2d["timeline_add"]["action"] == "actor.add"
    assert live2d["timeline_add"]["params"]["kind"] == "live2d"
    assert any(row["role"] == "expression" and row["required"] is False for row in live2d["missing_files"])

    spine = rows["spine"][0]
    assert spine["render"]["capable"] is True
    assert spine["features"]["animations"] == ["idle", "run"]
    assert spine["features"]["skins"] == ["default", "party"]
    assert spine["timeline_add"]["params"]["atlas_path"].endswith("hero.atlas")

    mmd = rows["mmd"][0]
    assert mmd["timeline_add"]["action"] == "mmd.actor.add"
    assert mmd["timeline_add"]["params"]["motion_path"] == str(paths["vmd"].resolve())
    assert mmd["recommended_transform"]["origin"] == "feet_ground_contact"

    vrm = rows["vrm"][0]
    assert vrm["profile"]["ok"] is True
    assert vrm["features"]["vseeface_compatible"] is True
    assert vrm["timeline_add"]["action"] == "vtuber.vseeface_select_vrm0_avatar"


def test_character_asset_hub_user_flow_and_thumbnail_generation(tmp_path):
    from app.character_asset_hub import (
        simulate_character_asset_hub_user_flow,
        write_character_asset_hub_thumbnails,
    )

    _make_character_pack(tmp_path)
    flow = simulate_character_asset_hub_user_flow(tmp_path, start_ms=1200, duration_ms=2400)
    assert flow["ok"] is True
    assert flow["step_count"] == 4
    assert {step["action"] for step in flow["timeline_steps"]} == {
        "actor.add",
        "mmd.actor.add",
        "vtuber.vseeface_select_vrm0_avatar",
    }
    assert all(step["params"].get("start_ms", 1200) == 1200 for step in flow["timeline_steps"] if step["action"] != "vtuber.vseeface_select_vrm0_avatar")

    with_thumbs = write_character_asset_hub_thumbnails(flow["scan"], tmp_path / "thumbs")
    for asset in with_thumbs["assets"]:
        thumb_path = Path(asset["thumbnail"]["path"])
        assert thumb_path.is_file()
        assert "<svg" in thumb_path.read_text(encoding="utf-8")


def test_character_asset_hub_dialog_scans_cards_and_emits_existing_actions(tmp_path):
    _ensure_qapp()
    from app.character_asset_hub_window import CharacterAssetHubDialog

    _make_character_pack(tmp_path)
    dialog = CharacterAssetHubDialog(tmp_path)
    events: list[tuple[str, dict]] = []
    dialog.action_requested.connect(lambda action, params: events.append((str(action), dict(params))))
    try:
        cards = dialog.cards()
        assert len(cards) == 4
        addable = [
            card
            for card in cards
            if bool((card.record.get("timeline_add") or {}).get("enabled"))
        ]
        assert len(addable) == 4

        addable[0]._emit_action()
        assert events
        assert events[0][0] in {
            "actor.add",
            "mmd.actor.add",
            "vtuber.vseeface_select_vrm0_avatar",
        }
        assert Path(events[0][1]["path"]).exists()

        addable[0]._emit_template_action("template-character-intro-short")
        assert events[-1][0] == "character.template.apply"
        assert events[-1][1]["template_id"] == "template-character-intro-short"
        assert events[-1][1]["asset_record"]["path"]
    finally:
        dialog.deleteLater()
