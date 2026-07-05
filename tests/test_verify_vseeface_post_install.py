def test_post_install_status_blocks_until_virtual_camera_registered():
    from tools.verify_vseeface_post_install import STATUS_BLOCKED_REGISTRATION, STATUS_READY, determine_post_install_status

    blocked = determine_post_install_status({"virtual_camera": {"registered": False}})
    ready = determine_post_install_status({"virtual_camera": {"registered": True}})

    assert blocked == STATUS_BLOCKED_REGISTRATION
    assert ready == STATUS_READY


def test_post_install_status_treats_missing_preflight_as_blocked():
    from tools.verify_vseeface_post_install import STATUS_BLOCKED_REGISTRATION, determine_post_install_status

    assert determine_post_install_status({}) == STATUS_BLOCKED_REGISTRATION


def test_post_install_reports_black_virtual_camera_frame(monkeypatch, tmp_path):
    from tools import verify_vseeface_post_install as verifier

    monkeypatch.setattr(verifier, "inspect_capture_backends", lambda _root: {"virtual_camera": {"registered": True}})
    monkeypatch.setattr(verifier, "default_vseeface_settings_path", lambda: tmp_path / "settings.ini")
    monkeypatch.setattr(verifier, "write_vseeface_sidecar_settings", lambda *_args, **_kwargs: type("Result", (), {"to_dict": lambda self: {}})())
    monkeypatch.setattr(verifier, "run_video_source", lambda **_kwargs: {"ok": True})
    monkeypatch.setattr(
        verifier,
        "probe_virtual_camera_frames",
        lambda **_kwargs: {
            "ok": False,
            "errors": ["virtual_camera_black_frame"],
            "ffmpeg_camera": {"opened": True, "sample_path": "black.png"},
        },
    )

    report = verifier.run_post_install_verification(
        video=tmp_path / "face.mp4",
        avatar_vrm=tmp_path / "avatar.vrm",
        vseeface_exe=tmp_path / "VSeeFace.exe",
        port=39540,
        duration_seconds=1.0,
        fps=10.0,
        crop=None,
        launch_vseeface=False,
        skip_video_send=False,
        wait_seconds=0.1,
        camera_max_index=0,
        out_dir=tmp_path,
    )

    assert report["status"] == verifier.STATUS_CAPTURE_BLACK
    assert report["next_action"] == "fix_vseeface_rendering_or_start_scene"
