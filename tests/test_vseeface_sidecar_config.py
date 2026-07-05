from pathlib import Path


def test_build_sidecar_settings_values_names_openseeface_endpoint(tmp_path):
    from app.vtuber.vseeface_sidecar_config import build_sidecar_settings_values

    avatar = tmp_path / "Milica.vrm"
    values = build_sidecar_settings_values(avatar_vrm=avatar, openseeface_port=39540)

    assert values["AvatarFile"] == str(avatar)
    assert values["AvatarDirectory"] == str(tmp_path)
    assert values["CameraName"] == "[OpenSeeFace tracking]"
    assert values["IP"] == "127.0.0.1"
    assert values["Port"] == "39540"
    assert values["TrackLeapMotion"] == "0"
    assert values["KeepVirtualCamEnabled"] == "1"


def test_build_sidecar_settings_values_can_leave_virtual_camera_manual(tmp_path):
    from app.vtuber.vseeface_sidecar_config import build_sidecar_settings_values

    values = build_sidecar_settings_values(
        avatar_vrm=tmp_path / "Milica.vrm",
        enable_virtual_camera=False,
    )

    assert "KeepVirtualCamEnabled" not in values


def test_write_vseeface_settings_collapses_duplicate_openseedemo_sections(tmp_path):
    from app.vtuber.vseeface_sidecar_config import read_openseedemo_settings, write_vseeface_sidecar_settings

    settings = tmp_path / "settings.ini"
    settings.write_text(
        "[OpenSeeDemo]\n"
        "Blackmagic=0\n"
        "AvatarFile=old.vrm\n"
        "[Other]\n"
        "Keep=1\n"
        "[OpenSeeDemo]\n"
        "Port=1\n",
        encoding="utf-8",
    )

    result = write_vseeface_sidecar_settings(settings, {"AvatarFile": "new.vrm", "Port": "39540"})
    text = settings.read_text(encoding="ascii")

    assert result.encoding == "ascii"
    assert result.duplicate_sections_removed == 1
    assert text.count("[OpenSeeDemo]") == 1
    assert "[Other]" in text
    assert read_openseedemo_settings(settings)["AvatarFile"] == "new.vrm"
    assert read_openseedemo_settings(settings)["Port"] == "39540"
    assert Path(result.backup_path).is_file()


def test_write_vseeface_settings_uses_utf16_for_non_ascii_paths(tmp_path):
    from app.vtuber.vseeface_sidecar_config import read_openseedemo_settings, write_vseeface_sidecar_settings

    settings = tmp_path / "settings.ini"
    avatar_path = tmp_path / "멜리카.vrm"

    result = write_vseeface_sidecar_settings(settings, {"AvatarFile": str(avatar_path)}, backup=False)

    assert result.encoding == "utf-16"
    assert settings.read_bytes().startswith(b"\xff\xfe")
    assert read_openseedemo_settings(settings)["AvatarFile"] == str(avatar_path)


def test_configure_vseeface_sidecar_cli_can_disable_virtual_camera_key(tmp_path):
    from app.vtuber.vseeface_sidecar_config import read_openseedemo_settings
    from tools.configure_vseeface_sidecar import main

    settings = tmp_path / "settings.ini"
    avatar = tmp_path / "avatar.vrm"
    avatar.write_bytes(b"vrm")

    rc = main([
        "--settings",
        str(settings),
        "--avatar-vrm",
        str(avatar),
        "--openseeface-port",
        "39542",
        "--disable-virtual-camera",
        "--no-backup",
    ])

    values = read_openseedemo_settings(settings)
    assert rc == 0
    assert values["AvatarFile"] == str(avatar)
    assert values["Port"] == "39542"
    assert "KeepVirtualCamEnabled" not in values
