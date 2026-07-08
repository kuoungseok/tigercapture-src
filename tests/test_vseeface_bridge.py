import json
import struct
import zipfile


def _write_vrm(path, *, profile: str):
    if profile == "VRM0":
        extensions = {
            "VRM": {
                "meta": {"title": "Milica Test", "author": "unit-test"},
                "humanoid": {"humanBones": [{"bone": "hips", "node": 0}]},
                "blendShapeMaster": {"blendShapeGroups": [{"name": "Joy"}]},
            }
        }
        used = ["VRM"]
    else:
        extensions = {
            "VRMC_vrm": {
                "specVersion": "1.0",
                "meta": {"name": "VRM1 Test", "authors": ["unit-test"]},
                "humanoid": {"humanBones": {"hips": {"node": 0}}},
            }
        }
        used = ["VRMC_vrm"]
    gltf = {
        "asset": {"version": "2.0"},
        "extensionsUsed": used,
        "extensions": extensions,
        "nodes": [{"name": "hips"}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    json_chunk = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(json_chunk) % 4:
        json_chunk += b" "
    total_len = 12 + 8 + len(json_chunk)
    path.write_bytes(
        b"glTF"
        + struct.pack("<II", 2, total_len)
        + struct.pack("<I4s", len(json_chunk), b"JSON")
        + json_chunk
    )
    return path


def test_vrm_profile_marks_vrm0_as_vseeface_compatible(tmp_path):
    from app.vtuber.vrm_profile import inspect_vrm_profile

    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")

    profile = inspect_vrm_profile(vrm)

    assert profile["ok"] is True
    assert profile["profile"] == "VRM0"
    assert profile["title"] == "Milica Test"
    assert profile["vseeface_compatible"] is True


def test_vrm_profile_marks_vrm1_as_not_vseeface_compatible(tmp_path):
    from app.vtuber.vrm_profile import inspect_vrm_profile

    vrm = _write_vrm(tmp_path / "avatar_vrm1.vrm", profile="VRM1")

    profile = inspect_vrm_profile(vrm)

    assert profile["ok"] is True
    assert profile["profile"] == "VRM1"
    assert profile["vseeface_compatible"] is False
    assert "vseeface_requires_vrm0" in profile["warnings"]


def test_vseeface_bridge_contract_is_external_sidecar_only():
    from app.vtuber.vseeface_bridge import INTEGRATION_MODE, default_milica_vrm, default_vseeface_exe, default_vseeface_install_dir, vseeface_bridge_contract

    contract = vseeface_bridge_contract()

    assert INTEGRATION_MODE == "external_sidecar"
    assert contract["integration_mode"] == "external_sidecar"
    assert any("do not embed VSeeFace" in item for item in contract["non_goals"])
    assert contract["broadcast_source_type"] == "vseeface"
    assert contract["default_framing"] == "bust_up"
    assert "openseeface_video" in contract["input_modes"]
    assert "internal_vrm_renderer" in contract["fallback_modes"]
    assert default_vseeface_install_dir("E:/project").as_posix() == "E:/project/external/tools/vseeface"
    assert default_vseeface_exe("E:/project").as_posix() == "E:/project/external/tools/vseeface/VSeeFace/VSeeFace.exe"
    assert default_milica_vrm("E:/project").as_posix() == "E:/project/external/assets/vtuber/booth_milica/Milica1.3free/Milica_v1.3.vrm"


def test_vseeface_bridge_preflight_accepts_exe_and_vrm0(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, vseeface_bridge_preflight

    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")
    config = VSeeFaceBridgeConfig(vseeface_exe=str(exe), avatar_vrm=str(vrm))

    diag = vseeface_bridge_preflight(config)

    assert diag["ok"] is True
    assert diag["integration_mode"] == "external_sidecar"
    assert diag["exe_exists"] is True
    assert diag["vrm"]["vseeface_compatible"] is True
    assert diag["launch"]["command"][0] == str(exe)


def test_vseeface_bridge_status_exposes_install_flow_when_exe_missing(tmp_path):
    from app.vtuber.vseeface_bridge import (
        VSeeFaceBridgeConfig,
        build_vseeface_bridge_status,
        build_vseeface_install_status,
    )

    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")
    config = VSeeFaceBridgeConfig(vseeface_exe=str(tmp_path / "missing" / "VSeeFace.exe"), avatar_vrm=str(vrm))

    status = build_vseeface_bridge_status(config)

    assert status["state"] == "blocked"
    dependency = status["view"]["dependency"]
    assert dependency["schema"] == "tigerstudio.vtuber.vseeface_bridge.install.v1"
    assert dependency["installed"] is False
    steps = status["setup_flow"]["steps"]
    assert steps[0]["id"] == "vseeface_install"
    install_action = next(action for action in status["actions"] if action["id"] == "install_vseeface_sidecar")
    install_plan = install_action["plan"]
    assert install_plan["auto_run"] is False
    assert install_plan["steps"][0]["registry_action"] == "vtuber.vseeface_install_plan"
    tool_step = next(step for step in install_plan["steps"] if step["kind"] == "tool")
    assert tool_step["args"][0] == "tools\\install_vseeface_sidecar.py"

    clean_status = build_vseeface_install_status({"vseeface_exe": str(tmp_path / "clean" / "VSeeFace.exe")}, root=tmp_path, downloads_dir=tmp_path)
    assert clean_status["state"] == "missing"
    assert clean_status["actions"][0]["primary"] is True


def test_vseeface_sidecar_installer_extracts_local_zip(tmp_path):
    from tools.install_vseeface_sidecar import install_vseeface_sidecar

    source_root = tmp_path / "zip_src" / "VSeeFace"
    source_root.mkdir(parents=True)
    (source_root / "VSeeFace.exe").write_bytes(b"MZ")
    (source_root / "VSeeFace_Data").mkdir()
    (source_root / "VSeeFace_Data" / "settings.txt").write_text("ok", encoding="utf-8")
    archive = tmp_path / "VSeeFace-test.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in source_root.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(tmp_path / "zip_src"))

    report = install_vseeface_sidecar(
        source_zip=archive,
        download_url="",
        install_dir=tmp_path / "install",
    )

    assert report["ok"] is True
    assert report["status"] == "installed"
    assert (tmp_path / "install" / "VSeeFace" / "VSeeFace.exe").is_file()


def test_vseeface_broadcast_source_carries_bridge_metadata(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_broadcast_source

    config = VSeeFaceBridgeConfig(
        vseeface_exe="C:/Tools/VSeeFace/VSeeFace.exe",
        avatar_vrm="C:/Avatars/Milica.vrm",
    )

    source = build_vseeface_broadcast_source(config)

    assert source["id"] == "vseeface"
    assert source["type"] == "vseeface"
    assert source["transform"]["fit"] == "contain"
    assert source["settings"]["integration_mode"] == "external_sidecar"
    assert source["settings"]["capture_method"] == "window_capture"
    assert source["settings"]["framing_preset"] == "bust_up"
    assert source["settings"]["camera"]["composition"] == "head_to_mid_chest"
    assert source["settings"]["camera"]["lower_frame"] == "mid_chest"
    assert source["settings"]["camera"]["pitch_deg"] == -6.0
    assert source["settings"]["vseeface_exe"].endswith("VSeeFace.exe")
    assert source["settings"]["tracking"]["receive_port"] == 39539
    assert source["settings"]["input"]["mode"] == "webcam"
    assert source["settings"]["suppress_black_frame"] is True
    assert source["settings"]["capture_status"] == "not_probed"
    assert source["settings"]["capture_ready"] is None


def test_vseeface_broadcast_source_marks_black_virtual_camera_unready():
    from app.vtuber.vseeface_bridge import (
        CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK,
        VSeeFaceBridgeConfig,
        build_vseeface_broadcast_source,
    )

    config = VSeeFaceBridgeConfig.from_mapping({
        "capture": {"method": "virtual_camera"},
    })

    source = build_vseeface_broadcast_source(
        config,
        capture_diagnostics={
            "status": CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK,
            "errors": [CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK],
            "virtual_camera": {"errors": [CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK]},
        },
    )

    health = source["settings"]["capture_health"]
    assert source["settings"]["capture_ready"] is False
    assert source["settings"]["capture_status"] == CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK
    assert health["ready"] is False
    assert health["fallback_behavior"] == "suppress_black_frame"
    assert health["fallback"]["mode"] == "internal_vrm_renderer"
    assert health["fallback"]["source_id"] == "internal_vrm_fallback"
    assert "fix_vseeface_rendering_or_start_scene" in health["recommendations"]


def test_vseeface_broadcast_source_infers_virtual_camera_from_post_install_report():
    from app.vtuber.vseeface_bridge import CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK, VSeeFaceBridgeConfig, build_vseeface_broadcast_source

    source = build_vseeface_broadcast_source(
        VSeeFaceBridgeConfig.from_mapping({}),
        capture_diagnostics={
            "schema": "tigerstudio.vtuber.vseeface_post_install_verification.v1",
            "ok": False,
            "status": CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK,
            "virtual_camera": {
                "errors": [CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK],
                "ffmpeg_camera": {"opened": True},
            },
        },
    )

    assert source["settings"]["capture_method"] == "virtual_camera"
    assert source["settings"]["capture_health"]["method"] == "virtual_camera"
    assert source["settings"]["capture_status"] == CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK


def test_vseeface_internal_fallback_source_exposes_renderer_quality(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_broadcast_scene

    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")
    scene = build_vseeface_broadcast_scene(
        VSeeFaceBridgeConfig.from_mapping({
            "avatar_vrm": str(vrm),
            "capture": {"method": "virtual_camera"},
        }),
        capture_diagnostics={
            "status": "virtual_camera_black_frame",
            "virtual_camera": {"errors": ["virtual_camera_black_frame"]},
        },
        width=1920,
        height=1080,
        fps=30,
    )

    fallback = next(source for source in scene["sources"] if source["type"] == "internal_vrm")
    renderer = fallback["settings"]["renderer"]
    assert renderer["family"] == "vtuber_vrm"
    assert renderer["renderer"] == "vrm_mtoon_gpu"
    assert renderer["render_profile"] == "vrm_mtoon"
    assert renderer["pbr_renderer"] is False
    assert renderer["ar_pbr_preview"] is False
    quality = fallback["settings"]["renderer"]["quality"]
    assert quality["renderer"] == "vrm_mtoon_gpu"
    assert quality["renderer_family"] == "vtuber_vrm"
    assert quality["render_profile"] == "vrm_mtoon"
    assert quality["pbr_renderer"] is False
    assert quality["ar_pbr_preview"] is False
    assert quality["broadcast_ready"] is True
    assert "vrm_mtoon_gpu_renderer_not_selected" not in quality["claim_blockers"]
    assert quality["software_renderer_disabled"] is True


def test_vseeface_bridge_status_reports_virtual_camera_registration_required(tmp_path):
    from app.vtuber.vseeface_bridge import (
        CAPTURE_STATUS_BLOCKED_REGISTRATION,
        VSeeFaceBridgeConfig,
        build_vseeface_bridge_status,
    )

    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")
    status = build_vseeface_bridge_status(
        VSeeFaceBridgeConfig(vseeface_exe=str(exe), avatar_vrm=str(vrm)),
        capture_diagnostics={
            "schema": "tigerstudio.vtuber.vseeface_post_install_verification.v1",
            "ok": False,
            "status": CAPTURE_STATUS_BLOCKED_REGISTRATION,
            "preflight": {
                "virtual_camera": {
                    "registered": False,
                    "requires_admin_registration": True,
                },
            },
            "errors": ["vseeface_camera_not_registered"],
        },
    )

    assert status["ok"] is True
    assert status["state"] == "degraded"
    assert status["capture"]["method"] == "virtual_camera"
    assert status["capture"]["status"] == CAPTURE_STATUS_BLOCKED_REGISTRATION
    assert status["view"]["badge"] == {"text": "Camera setup required", "tone": "blocked"}
    assert status["view"]["summary"] == "VSeeFaceCamera is not registered; Program Output falls back to the internal VRM renderer."
    assert status["actions"][0]["id"] == "use_internal_vrm_fallback"
    assert status["actions"][0]["primary"] is True
    assert status["actions"][1]["id"] == "register_vseeface_camera"
    assert status["actions"][1]["blocking"] is True
    assert status["actions"][1]["auto_run"] is False
    assert status["actions"][1]["plan"]["requires_admin"] is True
    assert status["actions"][1]["plan"]["steps"][1]["id"] == "launch_admin_registration"
    assert status["actions"][1]["plan"]["steps"][1]["requires_admin"] is True
    assert status["view"]["primary_action"]["requires_admin"] is False
    assert status["view"]["fallback"]["active"] is True
    assert status["setup_flow"]["current_step_id"] == "capture_backend"
    assert status["setup_flow"]["requires_admin"] is True
    assert status["view"]["setup_flow"]["current_title"] == "Capture backend"


def test_vseeface_bridge_status_reports_virtual_camera_capture_failed(tmp_path):
    from app.vtuber.vseeface_bridge import (
        CAPTURE_STATUS_VIRTUAL_CAMERA_FAILED,
        VSeeFaceBridgeConfig,
        build_vseeface_bridge_status,
    )

    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")
    status = build_vseeface_bridge_status(
        VSeeFaceBridgeConfig(vseeface_exe=str(exe), avatar_vrm=str(vrm)),
        capture_diagnostics={
            "schema": "tigerstudio.vtuber.vseeface_post_install_verification.v1",
            "ok": False,
            "status": CAPTURE_STATUS_VIRTUAL_CAMERA_FAILED,
            "errors": ["virtual_camera_capture_failed"],
        },
    )

    assert status["state"] == "degraded"
    assert status["view"]["badge"] == {"text": "Capture failed", "tone": "warning"}
    assert status["actions"][0]["id"] == "use_internal_vrm_fallback"
    assert status["actions"][1]["id"] == "confirm_vseeface_camera_enabled"
    assert status["actions"][1]["plan"]["requires_admin"] is False
    assert status["actions"][1]["plan"]["steps"][0]["kind"] == "manual"


def test_vseeface_capture_status_accepts_ready_window_probe():
    from app.vtuber.vseeface_bridge import summarize_vseeface_capture_status

    health = summarize_vseeface_capture_status(
        {"ok": True, "status": "window_capture_ready", "usable_window_capture": True},
        method="window_capture",
    )

    assert health["ready"] is True
    assert health["status"] == "ready"
    assert health["ui"]["label"] == "Ready"


def test_vseeface_capture_status_ui_maps_black_frame_for_product_ui():
    from app.vtuber.vseeface_bridge import CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK, vseeface_capture_status_ui

    ui = vseeface_capture_status_ui(CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK, ready=False)

    assert ui == {
        "label": "Black frame",
        "severity": "blocked",
        "action": "fix_vseeface_rendering_or_start_scene",
    }


def test_vseeface_broadcast_scene_payload_degrades_when_capture_is_black():
    from app.broadcast_scene import broadcast_scene_diagnostics
    from app.vtuber.vseeface_bridge import (
        CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK,
        VSeeFaceBridgeConfig,
        build_vseeface_broadcast_scene,
    )

    scene = build_vseeface_broadcast_scene(
        VSeeFaceBridgeConfig.from_mapping({"capture": {"method": "virtual_camera"}}),
        width=1280,
        height=720,
        fps=60,
        capture_diagnostics={
            "status": CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK,
            "errors": [CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK],
        },
    )

    diag = broadcast_scene_diagnostics(scene, {})

    assert scene["canvas"]["width"] == 1280
    assert scene["canvas"]["fps"] == 60.0
    assert [source["id"] for source in scene["sources"]] == ["background", "vseeface", "internal_vrm_fallback"]
    assert scene["sources"][1]["settings"]["capture_ready"] is False
    assert scene["sources"][1]["settings"]["fallback_source_id"] == "internal_vrm_fallback"
    assert scene["sources"][2]["type"] == "internal_vrm"
    assert scene["sources"][2]["settings"]["requires_vseeface_capture"] is False
    assert diag["ok"] is True
    assert diag["missing_frame_sources"] == []
    assert diag["degraded_frame_sources"] == ["vseeface"]


def test_vseeface_bridge_status_reports_ready_with_valid_setup_and_capture(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_bridge_status

    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")
    config = VSeeFaceBridgeConfig(vseeface_exe=str(exe), avatar_vrm=str(vrm))

    status = build_vseeface_bridge_status(
        config,
        capture_diagnostics={"ok": True, "status": "window_capture_ready", "usable_window_capture": True},
    )

    assert status["ok"] is True
    assert status["state"] == "ready"
    assert status["ui"]["label"] == "Ready"
    assert status["actions"][0]["id"] == "use_capture_source"
    assert status["actions"][0]["primary"] is True
    assert status["view"]["badge"]["text"] == "Ready"
    assert status["view"]["primary_action"]["id"] == "use_capture_source"
    assert status["preflight"]["ok"] is True
    assert status["scene_diagnostics"]["ok"] is True
    assert status["setup_flow"]["ready"] is True
    assert status["setup_flow"]["progress"] == 1.0
    assert status["view"]["setup_flow"]["ready"] is True


def test_vseeface_bridge_status_reports_needs_probe_with_probe_action(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_bridge_status

    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")

    status = build_vseeface_bridge_status(VSeeFaceBridgeConfig(vseeface_exe=str(exe), avatar_vrm=str(vrm)))

    assert status["ok"] is True
    assert status["state"] == "needs_probe"
    assert status["ui"]["action"] == "run_capture_probe"
    assert status["actions"][0]["id"] == "run_capture_probe"
    assert status["actions"][0]["kind"] == "tool"
    assert status["actions"][0]["plan"]["steps"][0]["id"] == "capture_backend_preflight"
    assert status["actions"][0]["plan"]["steps"][1]["id"] == "post_install_verify"
    assert status["view"]["show_debug"] is False
    assert status["view"]["badge"]["tone"] == "info"


def test_vseeface_bridge_status_reports_degraded_for_black_capture(tmp_path):
    from app.vtuber.vseeface_bridge import (
        CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK,
        VSeeFaceBridgeConfig,
        build_vseeface_bridge_status,
    )

    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")
    face_video = tmp_path / "face.mp4"
    face_video.write_bytes(b"not-a-real-video-for-contract-test")
    config = VSeeFaceBridgeConfig.from_mapping({
        "vseeface_exe": str(exe),
        "avatar_vrm": str(vrm),
        "capture": {"method": "virtual_camera"},
    })

    status = build_vseeface_bridge_status(
        config,
        capture_diagnostics={
            "ok": False,
            "status": CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK,
            "errors": [CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK],
        },
    )

    assert status["ok"] is True
    assert status["state"] == "degraded"
    assert status["ui"]["label"] == "Black frame"
    assert [action["id"] for action in status["actions"]][:2] == [
        "use_internal_vrm_fallback",
        "fix_vseeface_rendering_or_start_scene",
    ]
    assert status["actions"][0]["auto_run"] is False
    assert status["view"]["badge"] == {"text": "Black frame", "tone": "blocked"}
    assert status["view"]["primary_action"]["id"] == "use_internal_vrm_fallback"
    assert status["view"]["fallback"] == {
        "mode": "internal_vrm_renderer",
        "active": True,
        "source_id": "internal_vrm_fallback",
        "label": "Internal VRM fallback",
        "program_output": True,
        "requires_vseeface_capture": False,
    }
    assert status["view"]["cards"][2]["tone"] == "warning"
    assert "preflight" not in status["view"]
    assert status["scene_diagnostics"]["missing_frame_sources"] == []
    assert status["scene_diagnostics"]["degraded_frame_sources"] == ["vseeface"]


def test_vseeface_bridge_status_reports_blocked_when_exe_is_missing(tmp_path, monkeypatch):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_bridge_status

    monkeypatch.setattr(
        "app.vtuber.vseeface_bridge.default_vseeface_install_dir",
        lambda root=None: tmp_path / "absent_sidecar",
    )
    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")
    status = build_vseeface_bridge_status(VSeeFaceBridgeConfig(vseeface_exe=str(tmp_path / "missing.exe"), avatar_vrm=str(vrm)))

    assert status["ok"] is False
    assert status["state"] == "blocked"
    assert status["ui"]["label"] == "Setup required"
    assert status["ui"]["action"] == "select_vseeface_exe"
    assert status["actions"][0]["id"] in {"select_vseeface_exe", "connect_installed_vseeface_sidecar", "install_vseeface_sidecar"}
    assert status["actions"][0]["blocking"] is True
    assert status["view"]["badge"]["text"] == "Setup required"
    assert status["view"]["primary_action"]["id"] in {"select_vseeface_exe", "connect_installed_vseeface_sidecar", "install_vseeface_sidecar"}
    assert status["setup_flow"]["current_step_id"] == "vseeface_install"
    assert status["setup_flow"]["steps"][0]["id"] == "vseeface_install"
    assert status["setup_flow"]["steps"][0]["state"] == "current"
    assert status["setup_flow"]["steps"][1]["id"] == "vseeface_exe"
    assert status["view"]["setup_flow"]["current_title"] == "VSeeFace install"


def test_vseeface_bridge_status_reports_blocked_for_vrm1_avatar(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_bridge_status

    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm(tmp_path / "avatar_vrm1.vrm", profile="VRM1")

    status = build_vseeface_bridge_status(VSeeFaceBridgeConfig(vseeface_exe=str(exe), avatar_vrm=str(vrm)))

    assert status["ok"] is False
    assert status["state"] == "blocked"
    assert status["ui"]["action"] == "select_vrm0_avatar"
    assert status["actions"][0]["id"] == "select_vrm0_avatar"
    assert status["view"]["cards"][0]["text"] == "Avatar must be VRM0 for VSeeFace."


def test_vseeface_capture_framing_aliases_normalize_to_broadcast_presets():
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig

    config = VSeeFaceBridgeConfig.from_mapping({
        "capture": {
            "framing": "waist-up",
        },
    })

    assert config.capture.framing_preset == "half_body"
    assert config.capture.to_dict()["camera"]["composition"] == "head_to_waist"


def test_vseeface_tracking_defaults_to_vseeface_receiver_port():
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig

    config = VSeeFaceBridgeConfig.from_mapping({})

    assert config.tracking.target_host == "127.0.0.1"
    assert config.tracking.receive_port == 39539
    assert config.tracking.send_port == 39540


def test_vseeface_openseeface_video_input_config_normalizes_crop_and_port():
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig

    config = VSeeFaceBridgeConfig.from_mapping({
        "input": {
            "mode": "openseeface-video",
            "video": "debugCapture/trump_face_source.mp4",
            "port": 39542,
            "fps": 12,
            "crop": "0.32,0.05,0.36,0.75",
            "try_hard": True,
        },
    })

    payload = config.to_dict()["input"]
    assert payload["mode"] == "openseeface_video"
    assert payload["video_path"].endswith("trump_face_source.mp4")
    assert payload["openseeface_port"] == 39542
    assert payload["fps"] == 12.0
    assert payload["crop"] == [0.32, 0.05, 0.36, 0.75]
    assert payload["try_hard"] is True


def test_vseeface_input_sources_include_camera_media_pool_and_timeline_clip():
    from app.vtuber.vseeface_bridge import build_vseeface_input_source_options

    snapshot = {
        "media_pool": [
            {"id": "media_1", "path": "C:/media/face.mp4", "name": "face.mp4", "kind": "video"},
            {"id": "media_2", "path": "C:/media/song.wav", "name": "song.wav", "kind": "audio"},
        ],
        "video_tracks": [
            {
                "id": 3,
                "index": 0,
                "clips": [
                    {
                        "id": 7,
                        "source_path": "C:/media/talk.mov",
                        "name": "talk.mov",
                        "timeline_in_ms": 1000,
                        "timeline_out_ms": 5000,
                        "source_in_ms": 250,
                        "source_out_ms": 4250,
                    }
                ],
            }
        ],
    }

    sources = build_vseeface_input_source_options(
        project_snapshot=snapshot,
        camera_devices=[{"id": "webcam0", "name": "USB Camera", "index": 0}],
        selected={"source_kind": "timeline_video_clip", "track_id": 3, "clip_id": 7},
    )

    ids = [item["id"] for item in sources["options"]]
    assert ids == ["camera:webcam0", "media_pool:media_1", "timeline:3:7"]
    assert sources["selected_id"] == "timeline:3:7"
    assert sources["counts"] == {"camera_devices": 1, "media_pool_videos": 1, "timeline_video_clips": 1}
    selected_input = sources["selected"]["input"]
    assert selected_input["mode"] == "openseeface_video"
    assert selected_input["source_kind"] == "timeline_video_clip"
    assert selected_input["video_path"] == "C:/media/talk.mov"
    assert selected_input["timeline_in_ms"] == 1000


def test_vseeface_input_sources_expose_camera_reconnect_state():
    from app.vtuber.vseeface_bridge import build_vseeface_input_source_options

    sources = build_vseeface_input_source_options(
        camera_devices=[
            {"id": "webcam0", "name": "USB Camera", "index": 0},
        ],
        selected={"source_kind": "camera_device", "camera_device_id": "webcam0"},
        input_diagnostics={
            "inputs": {
                "camera:webcam0": {
                    "status": "disconnected",
                    "errors": ["camera_unavailable"],
                    "recommendations": ["reconnect_usb_camera"],
                }
            }
        },
    )

    selected = sources["selected"]
    assert sources["selected_id"] == "camera:webcam0"
    assert selected["status"] == "unavailable"
    assert selected["tone"] == "blocked"
    assert selected["diagnostics"]["errors"] == ["camera_unavailable"]
    assert selected["actions"][0]["id"] == "reconnect_tracking_input_source"
    assert sources["diagnostics"]["has_reconnectable_camera"] is True
    assert "selected_tracking_input_unavailable" in sources["warnings"]


def test_vseeface_input_sources_recommend_video_fallback_when_camera_unavailable():
    from app.vtuber.vseeface_bridge import build_vseeface_input_source_options

    sources = build_vseeface_input_source_options(
        project_snapshot={
            "media_pool": [
                {"id": "face_take", "path": "C:/media/face_take.mp4", "name": "face_take.mp4", "kind": "video"},
            ],
            "video_tracks": [],
        },
        camera_devices=[{"id": "webcam0", "name": "USB Camera", "index": 0, "available": False}],
        selected={"source_kind": "camera_device", "camera_device_id": "webcam0"},
    )

    assert sources["selected_id"] == "camera:webcam0"
    assert sources["selected"]["status"] == "unavailable"
    assert sources["fallback"]["id"] == "media_pool:face_take"
    assert sources["fallback"]["action"]["id"] == "select_tracking_input_source"
    assert sources["fallback"]["action"]["source_id"] == "media_pool:face_take"
    assert sources["diagnostics"]["fallback_available"] is True
    assert sources["diagnostics"]["recommended_fallback_label"] == "face_take.mp4"
    assert "tracking_input_fallback_available" in sources["warnings"]


def test_vseeface_bridge_status_view_reports_tracking_input_black_frame(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_bridge_status

    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")
    config = VSeeFaceBridgeConfig.from_mapping({
        "vseeface_exe": str(exe),
        "avatar_vrm": str(vrm),
        "input": {
            "source_kind": "camera_device",
            "camera_device_id": "webcam0",
        },
    })

    status = build_vseeface_bridge_status(
        config,
        camera_devices=[{"id": "webcam0", "name": "USB Camera", "index": 0}],
        input_diagnostics={
            "inputs": {
                "camera:webcam0": {
                    "status": "black_frame",
                    "warnings": ["tracking_input_black_frame"],
                }
            }
        },
    )

    assert status["input_sources"]["selected"]["status"] == "black_frame"
    assert status["view"]["input_source"]["status"] == "black_frame"
    assert status["view"]["input_source"]["tone"] == "blocked"
    assert status["view"]["cards"][3]["tone"] == "blocked"
    assert status["view"]["input_source"]["actions"][0]["id"] == "reconnect_tracking_input_source"


def test_vseeface_bridge_status_view_exposes_tracking_input_fallback(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_bridge_status

    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")
    face_video = tmp_path / "face_take.mp4"
    face_video.write_bytes(b"not-a-real-video-for-contract-test")
    config = VSeeFaceBridgeConfig.from_mapping({
        "vseeface_exe": str(exe),
        "avatar_vrm": str(vrm),
        "input": {
            "source_kind": "camera_device",
            "camera_device_id": "webcam0",
        },
    })

    status = build_vseeface_bridge_status(
        config,
        camera_devices=[{"id": "webcam0", "name": "USB Camera", "index": 0, "available": False}],
        project_snapshot={
            "media_pool": [
                {"id": "face_take", "path": str(face_video), "name": "face_take.mp4", "kind": "video"},
            ],
            "video_tracks": [],
        },
    )

    view = status["view"]["input_source"]
    assert view["status"] == "unavailable"
    assert view["fallback_available"] is True
    assert view["recommended_fallback_id"] == "media_pool:face_take"
    assert view["recommended_fallback_label"] == "face_take.mp4"
    assert view["recommended_fallback_action"]["source_id"] == "media_pool:face_take"


def test_vseeface_input_sources_flag_missing_media_pool_video():
    from app.vtuber.vseeface_bridge import build_vseeface_input_source_options

    sources = build_vseeface_input_source_options(
        project_snapshot={
            "media_pool": [
                {
                    "id": "missing_face",
                    "path": "C:/missing/face.mp4",
                    "name": "face.mp4",
                    "kind": "video",
                    "exists": False,
                }
            ]
        },
        selected={"source_kind": "media_pool_video", "media_pool_id": "missing_face"},
    )

    selected = sources["selected"]
    assert selected["status"] == "missing"
    assert selected["tone"] == "blocked"
    assert selected["actions"][0]["id"] == "select_tracking_input_source"
    assert "selected_tracking_input_missing" in sources["warnings"]


def test_vseeface_bridge_status_exposes_tracking_input_view(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_bridge_status

    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")
    face_video = tmp_path / "face.mp4"
    face_video.write_bytes(b"not-a-real-video-for-contract-test")
    config = VSeeFaceBridgeConfig.from_mapping({
        "vseeface_exe": str(exe),
        "avatar_vrm": str(vrm),
        "input": {
            "source_kind": "media_pool_video",
            "media_pool_id": "media_face",
        },
    })
    snapshot = {
        "media_pool": [
            {"id": "media_face", "path": str(face_video), "name": "face.mp4", "kind": "video"},
        ],
        "video_tracks": [],
    }

    status = build_vseeface_bridge_status(config, project_snapshot=snapshot)

    assert status["input_sources"]["selected_id"] == "media_pool:media_face"
    assert status["view"]["input_source"]["label"] == "face.mp4"
    assert status["view"]["input_source"]["media_pool_video_count"] == 1
    assert status["scene"]["sources"][1]["settings"]["input"]["video_path"] == str(face_video)
    assert "openseeface_input_video_missing" not in status["preflight"]["warnings"]
    assert status["view"]["cards"][3]["id"] == "input"
    assert status["view"]["cards"][3]["text"] == "Media pool: face.mp4"
    assert any(action["id"] == "select_tracking_input_source" for action in status["actions"])


def test_vseeface_bridge_status_includes_read_only_sidecar_settings_preview(tmp_path):
    from app.vtuber.vseeface_action_plan import build_vseeface_action_preview
    from app.vtuber.vseeface_bridge import (
        ACTION_APPLY_SIDECAR_SETTINGS,
        VSeeFaceBridgeConfig,
        build_vseeface_bridge_status,
    )

    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")
    config = VSeeFaceBridgeConfig.from_mapping({
        "vseeface_exe": str(exe),
        "avatar_vrm": str(vrm),
        "capture": {"method": "virtual_camera"},
        "input": {
            "mode": "openseeface_video",
            "video_path": str(tmp_path / "face.mp4"),
            "openseeface_port": 39542,
        },
    })

    status = build_vseeface_bridge_status(config)

    sidecar = status["sidecar_settings"]
    view = status["view"]["sidecar_settings"]
    assert sidecar["read_only"] is True
    assert sidecar["would_write"] is False
    assert sidecar["values"]["AvatarFile"] == str(vrm)
    assert sidecar["values"]["Port"] == "39542"
    assert sidecar["values"]["KeepVirtualCamEnabled"] == "1"
    assert view["avatar_file"] == str(vrm)
    assert view["openseeface_endpoint"] == {"host": "127.0.0.1", "port": "39542"}
    assert view["virtual_camera_kept_enabled"] is True
    assert status["view"]["cards"][3]["id"] == "input"
    assert status["view"]["cards"][4]["id"] == "sidecar"
    assert status["view"]["cards"][4]["text"] == "OpenSeeFace 127.0.0.1:39542"
    sidecar_action = next(action for action in status["view"]["secondary_actions"] if action["id"] == ACTION_APPLY_SIDECAR_SETTINGS)
    assert sidecar_action["registry_action"] == "vtuber.vseeface_sidecar_apply_plan"
    assert sidecar_action["form"]["params"][0]["name"] == "settings_path"

    action_preview = build_vseeface_action_preview(status, action_id=ACTION_APPLY_SIDECAR_SETTINGS)
    assert action_preview["ok"] is True
    assert action_preview["auto_run"] is False
    assert "file_write_requires_user_confirmation" in action_preview["warnings"]
    assert action_preview["steps"][0]["registry_action"] == "vtuber.vseeface_sidecar_apply_plan"
    assert action_preview["steps"][1]["id"] == "write_sidecar_settings"
    assert action_preview["steps"][1]["auto_run"] is False


def test_vseeface_sidecar_apply_plan_matches_settings_preview(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_sidecar_apply_plan

    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")
    settings = tmp_path / "settings.ini"
    config = VSeeFaceBridgeConfig.from_mapping({
        "avatar_vrm": str(vrm),
        "capture": {"method": "virtual_camera"},
        "input": {
            "openseeface_host": "127.0.0.1",
            "openseeface_port": 39542,
        },
    })

    plan = build_vseeface_sidecar_apply_plan(
        config,
        settings_path=settings,
        out_path=tmp_path / "report.json",
    )

    args = plan["steps"][0]["args"]
    assert plan["ok"] is True
    assert plan["auto_run"] is False
    assert plan["requires_user_initiation"] is True
    assert plan["settings_preview"]["values"]["AvatarFile"] == str(vrm)
    assert plan["settings_preview"]["values"]["KeepVirtualCamEnabled"] == "1"
    assert "--disable-virtual-camera" not in args
    assert str(settings) in args
    assert str(vrm) in args
    assert "39542" in args
    assert not settings.exists()


def test_vseeface_sidecar_workflow_summarizes_read_only_ui_flow(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_sidecar_workflow

    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")
    settings = tmp_path / "settings.ini"
    config = VSeeFaceBridgeConfig.from_mapping({
        "avatar_vrm": str(vrm),
        "capture": {"method": "virtual_camera"},
        "input": {"openseeface_port": 39542},
    })

    workflow = build_vseeface_sidecar_workflow(config, settings_path=settings)
    confirmed = build_vseeface_sidecar_workflow(config, settings_path=settings, confirm=True)

    assert workflow["ok"] is True
    assert workflow["read_only"] is True
    assert workflow["state"] == "confirmation_required"
    assert workflow["execution_gate"]["execute_allowed"] is False
    assert workflow["executor_dry_run"]["executed"] is False
    assert workflow["view"]["tone"] == "warning"
    assert workflow["view"]["openseeface_endpoint"] == {"host": "127.0.0.1", "port": "39542"}
    assert workflow["view"]["actions"][2]["registry_action"] == "vtuber.vseeface_sidecar_execution_gate"
    assert workflow["view"]["progress"] == 0.75
    assert workflow["view"]["steps"][0]["state"] == "done"
    assert workflow["view"]["steps"][2]["state"] == "current"
    assert workflow["view"]["next_action"]["id"] == "confirm_sidecar_settings"
    assert confirmed["state"] == "ready_to_execute"
    assert confirmed["view"]["would_run"] is True
    assert confirmed["view"]["progress"] == 1.0
    assert confirmed["view"]["steps"][2]["state"] == "done"
    assert confirmed["view"]["steps"][3]["state"] == "done"
    assert confirmed["view"]["next_action"]["registry_action"] == "vtuber.vseeface_sidecar_executor_dry_run"
    assert not settings.exists()


def test_vseeface_probe_action_uses_selected_project_video_input(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_bridge_status

    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm(tmp_path / "milica.vrm", profile="VRM0")
    face_video = tmp_path / "face.mp4"
    face_video.write_bytes(b"face")
    config = VSeeFaceBridgeConfig.from_mapping({
        "vseeface_exe": str(exe),
        "avatar_vrm": str(vrm),
        "input": {
            "source_kind": "timeline_video_clip",
            "track_id": 2,
            "clip_id": 5,
            "fps": 12,
            "crop": "0.1,0.2,0.3,0.4",
            "openseeface_port": 39542,
        },
    })
    snapshot = {
        "media_pool": [],
        "video_tracks": [
            {
                "id": 2,
                "clips": [
                    {"id": 5, "source_path": str(face_video), "name": "face.mp4"},
                ],
            }
        ],
    }

    status = build_vseeface_bridge_status(config, project_snapshot=snapshot)

    assert status["state"] == "needs_probe"
    plan = status["actions"][0]["plan"]
    verify_step = plan["steps"][1]
    args = verify_step["args"]
    assert verify_step["id"] == "post_install_verify"
    assert "--skip-video-send" not in args
    assert args[args.index("--video") + 1] == str(face_video)
    assert args[args.index("--port") + 1] == "39542"
    assert args[args.index("--fps") + 1] == "12.0"
    assert args[args.index("--crop") + 1] == "0.1,0.2,0.3,0.4"
