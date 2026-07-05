import json
import struct


def _write_vrm0(path):
    gltf = {
        "asset": {"version": "2.0"},
        "extensionsUsed": ["VRM"],
        "extensions": {
            "VRM": {
                "meta": {"title": "Tool Test", "author": "unit-test"},
                "humanoid": {"humanBones": [{"bone": "hips", "node": 0}]},
            }
        },
        "nodes": [{"name": "hips"}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    chunk = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(chunk) % 4:
        chunk += b" "
    path.write_bytes(
        b"glTF"
        + struct.pack("<II", 2, 12 + 8 + len(chunk))
        + struct.pack("<I4s", len(chunk), b"JSON")
        + chunk
    )
    return path


def test_vseeface_bridge_status_tool_writes_degraded_report(tmp_path):
    from tools.vseeface_bridge_status import main

    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm0(tmp_path / "avatar.vrm")
    config = {
        "vseeface_exe": str(exe),
        "avatar_vrm": str(vrm),
        "capture": {"method": "virtual_camera"},
    }
    config_path = tmp_path / "bridge_config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    out = tmp_path / "status.json"

    rc = main([
        "--config",
        str(config_path),
        "--capture-status",
        "virtual_camera_black_frame",
        "--out",
        str(out),
    ])

    report = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 0
    assert report["state"] == "degraded"
    assert report["ui"]["label"] == "Black frame"
    assert report["actions"][0]["id"] == "use_internal_vrm_fallback"
    assert report["actions"][0]["auto_run"] is False
    assert report["actions"][0]["plan"]["auto_run"] is False
    assert report["actions"][0]["plan"]["steps"][0]["kind"] == "ui"
    assert report["actions"][0]["plan"]["steps"][0]["control"] == "scene_update"
    assert report["view"]["show_debug"] is False
    assert report["view"]["badge"] == {"text": "Black frame", "tone": "blocked"}
    assert report["view"]["primary_action"]["id"] == "use_internal_vrm_fallback"
    assert report["view"]["fallback"]["active"] is True
    assert report["scene_diagnostics"]["degraded_frame_sources"] == ["vseeface"]


def test_vseeface_bridge_status_tool_infers_capture_method_from_report(tmp_path):
    from tools.vseeface_bridge_status import main

    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm0(tmp_path / "avatar.vrm")
    config = {
        "vseeface_exe": str(exe),
        "avatar_vrm": str(vrm),
    }
    capture_report = {
        "schema": "tigerstudio.vtuber.vseeface_post_install_verification.v1",
        "ok": False,
        "status": "virtual_camera_black_frame",
        "virtual_camera": {
            "errors": ["virtual_camera_black_frame"],
            "ffmpeg_camera": {"opened": True},
        },
    }
    config_path = tmp_path / "bridge_config.json"
    report_path = tmp_path / "capture_report.json"
    out = tmp_path / "status.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    report_path.write_text(json.dumps(capture_report), encoding="utf-8")

    rc = main([
        "--config",
        str(config_path),
        "--capture-report",
        str(report_path),
        "--out",
        str(out),
    ])

    report = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 0
    assert report["capture"]["method"] == "virtual_camera"
    assert report["scene"]["sources"][1]["settings"]["capture_method"] == "virtual_camera"


def test_vseeface_bridge_status_tool_maps_registration_required_report(tmp_path):
    from tools.vseeface_bridge_status import main

    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm0(tmp_path / "avatar.vrm")
    config = {
        "vseeface_exe": str(exe),
        "avatar_vrm": str(vrm),
    }
    capture_report = {
        "schema": "tigerstudio.vtuber.vseeface_post_install_verification.v1",
        "ok": False,
        "status": "blocked_registration_required",
        "preflight": {
            "virtual_camera": {
                "registered": False,
                "requires_admin_registration": True,
            },
        },
        "errors": ["vseeface_camera_not_registered"],
        "next_action": "run_register_vseeface_camera_admin_bat_and_approve_uac",
    }
    config_path = tmp_path / "bridge_config.json"
    report_path = tmp_path / "capture_report.json"
    out = tmp_path / "status.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    report_path.write_text(json.dumps(capture_report), encoding="utf-8")

    rc = main([
        "--config",
        str(config_path),
        "--capture-report",
        str(report_path),
        "--out",
        str(out),
    ])

    report = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 0
    assert report["capture"]["status"] == "blocked_registration_required"
    assert report["view"]["badge"]["text"] == "Camera setup required"
    assert report["view"]["primary_action"]["id"] == "use_internal_vrm_fallback"
    assert report["view"]["primary_action"]["requires_admin"] is False
    register_action = next(action for action in report["actions"] if action["id"] == "register_vseeface_camera")
    assert register_action["plan"]["requires_admin"] is True
    assert register_action["plan"]["steps"][1]["id"] == "launch_admin_registration"


def test_vseeface_bridge_status_tool_reads_project_snapshot_for_input_choices(tmp_path):
    from tools.vseeface_bridge_status import main

    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm0(tmp_path / "avatar.vrm")
    config = {
        "vseeface_exe": str(exe),
        "avatar_vrm": str(vrm),
        "input": {
            "source_kind": "timeline_video_clip",
            "track_id": 2,
            "clip_id": 5,
        },
    }
    snapshot = {
        "media_pool": [
            {"id": "media_1", "path": "C:/media/face.mp4", "name": "face.mp4", "kind": "video"},
        ],
        "video_tracks": [
            {
                "id": 2,
                "index": 0,
                "clips": [
                    {"id": 5, "source_path": "C:/media/track_face.mov", "name": "track_face.mov", "timeline_in_ms": 0},
                ],
            }
        ],
    }
    config_path = tmp_path / "bridge_config.json"
    snapshot_path = tmp_path / "snapshot.json"
    out = tmp_path / "status.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    rc = main([
        "--config",
        str(config_path),
        "--project-snapshot",
        str(snapshot_path),
        "--camera-device",
        "webcam0=USB Camera",
        "--out",
        str(out),
    ])

    report = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 0
    assert report["input_sources"]["selected_id"] == "timeline:2:5"
    assert report["input_sources"]["counts"]["camera_devices"] == 1
    assert report["input_sources"]["counts"]["media_pool_videos"] == 1
    assert report["input_sources"]["counts"]["timeline_video_clips"] == 1
    assert report["view"]["input_source"]["label"].endswith("track_face.mov")
