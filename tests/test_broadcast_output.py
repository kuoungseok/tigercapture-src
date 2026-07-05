def test_broadcast_output_builds_rtmp_ffmpeg_command():
    from app.broadcast_output import BroadcastOutputProfile, build_ffmpeg_broadcast_command
    from app.broadcast_scene import BroadcastCanvas

    cmd = build_ffmpeg_broadcast_command(
        BroadcastOutputProfile(kind="rtmp", target="rtmp://localhost/live/test", video_bitrate_kbps=4500),
        BroadcastCanvas(width=1280, height=720, fps=60.0),
        ffmpeg_exe="ffmpeg-test",
    )

    assert cmd[0] == "ffmpeg-test"
    assert ["-f", "rawvideo"] == cmd[4:6]
    assert "1280x720" in cmd
    assert "60" in cmd
    assert "-tune" in cmd
    assert "zerolatency" in cmd
    assert cmd[-2:] == ["-f", "flv"] or cmd[-3:-1] == ["-f", "flv"]
    assert cmd[-1] == "rtmp://localhost/live/test"


def test_broadcast_output_preflight_rejects_missing_rtmp_target():
    from app.broadcast_output import broadcast_output_preflight
    from app.broadcast_scene import BroadcastCanvas

    diag = broadcast_output_preflight(
        {"kind": "rtmp", "target": "https://example.com/not-rtmp"},
        BroadcastCanvas(width=1920, height=1080, fps=30.0),
        ffmpeg_exe="ffmpeg-test",
    )

    assert diag["ok"] is False
    assert diag["command"] == []
    assert "rtmp output requires" in diag["errors"][0]


def test_broadcast_output_builds_recording_command():
    from app.broadcast_output import broadcast_output_preflight

    diag = broadcast_output_preflight(
        {"kind": "recording", "target": "capture.mp4", "low_latency": False},
        {"width": 640, "height": 360, "fps": 29.97},
        ffmpeg_exe="ffmpeg-test",
    )

    assert diag["ok"] is True
    assert "-tune" not in diag["command"]
    assert "640x360" in diag["command"]
    assert "29.97" in diag["command"]
    assert diag["command"][-1].endswith("capture.mp4")


def test_broadcast_output_rejects_audio_without_source():
    from app.broadcast_output import broadcast_output_preflight

    diag = broadcast_output_preflight(
        {"kind": "recording", "target": "capture.mp4", "include_audio": True},
        {"width": 320, "height": 180},
        ffmpeg_exe="ffmpeg-test",
    )

    assert diag["ok"] is False
    assert "live audio requires" in diag["errors"][0]


def test_broadcast_output_builds_silent_audio_ffmpeg_command():
    from app.broadcast_output import broadcast_output_preflight

    diag = broadcast_output_preflight(
        {
            "kind": "recording",
            "target": "capture.mp4",
            "include_audio": True,
            "audio_source_kind": "silence",
            "audio_sample_rate": 48000,
            "audio_channels": 2,
        },
        {"width": 320, "height": 180, "fps": 30},
        ffmpeg_exe="ffmpeg-test",
    )

    cmd = diag["command"]
    assert diag["ok"] is True
    assert "-an" not in cmd
    assert ["-f", "lavfi"] == cmd[14:16]
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" in cmd
    assert "-c:a" in cmd
    assert "aac" in cmd


def test_broadcast_output_builds_dshow_audio_command():
    from app.broadcast_output import build_ffmpeg_broadcast_command

    cmd = build_ffmpeg_broadcast_command(
        {
            "kind": "rtmp",
            "target": "rtmp://localhost/live/test",
            "include_audio": True,
            "audio_source_kind": "dshow_device",
            "audio_device_name": "Microphone",
        },
        {"width": 1280, "height": 720, "fps": 30},
        ffmpeg_exe="ffmpeg-test",
    )

    assert ["-f", "dshow", "-i", "audio=Microphone"] == cmd[14:18]
    assert "-map" in cmd
    assert "1:a:0?" in cmd


def test_broadcast_output_accepts_project_audio_bus_after_mixdown():
    from app.broadcast_output import broadcast_output_preflight

    diag = broadcast_output_preflight(
        {
            "kind": "recording",
            "target": "capture.mp4",
            "include_audio": True,
            "audio_source_kind": "project_audio_bus",
            "audio_file": "live_bus.wav",
        },
        {"width": 320, "height": 180, "fps": 30},
        ffmpeg_exe="ffmpeg-test",
    )

    cmd = diag["command"]
    assert diag["ok"] is True
    assert ["-stream_loop", "-1", "-i", "live_bus.wav"] == cmd[14:18]
    assert "1:a:0?" in cmd


def test_live_target_presets_cover_core_and_experimental_platforms():
    from app.broadcast_output import live_target_presets

    presets = live_target_presets()
    ids = {row["id"] for row in presets}
    by_id = {row["id"]: row for row in presets}

    assert {"record_file", "youtube_live", "twitch", "custom_rtmp", "discord_video_call"}.issubset(ids)
    assert {"tiktok_live", "instagram_live", "x_live"}.issubset(ids)
    assert by_id["record_file"]["label"] == "Local MP4"


def test_local_mp4_alias_maps_to_record_file_live_target():
    from app.broadcast_output import LiveTargetProfile, live_target_preflight, live_target_preset

    preset = live_target_preset("local_mp4")
    profile = LiveTargetProfile.from_mapping({"target_id": "local_mp4", "output_path": "show.mp4"})
    diag = live_target_preflight(profile, {"width": 1280, "height": 720, "fps": 30}, ffmpeg_exe="ffmpeg-test")

    assert preset.id == "record_file"
    assert profile.target_id == "record_file"
    assert diag["ok"] is True
    assert diag["target"]["label"] == "Local MP4"
    assert diag["command"][-1].endswith("show.mp4")


def test_youtube_live_target_preflight_builds_redacted_rtmp_command():
    from app.broadcast_output import live_target_preflight

    diag = live_target_preflight(
        {
            "target_id": "youtube_live",
            "stream_key": "SECRET-KEY",
            "video_bitrate_kbps": 4500,
        },
        {"width": 1280, "height": 720, "fps": 60},
        ffmpeg_exe="ffmpeg-test",
    )

    assert diag["ok"] is True
    assert diag["target"]["stream_key"] == "<session>"
    assert diag["target"]["stream_key_storage"] == "session"
    assert "SECRET-KEY" not in " ".join(str(part) for part in diag["command"])
    assert diag["command"][-1].endswith("/<stream_key>")


def test_live_target_project_settings_never_store_raw_stream_key():
    from app.broadcast_output import LiveTargetProfile

    settings = LiveTargetProfile.from_mapping(
        {
            "target_id": "twitch",
            "stream_key": "dont-save-me",
            "server_url": "rtmp://live.twitch.tv/app",
        }
    ).to_project_settings()

    assert "stream_key" not in settings
    assert settings["stream_key_present"] is False
    assert settings["server_url"] == "rtmp://live.twitch.tv/app"


def test_live_target_project_settings_keep_reconnect_policy():
    from app.broadcast_output import LiveTargetProfile

    settings = LiveTargetProfile.from_mapping(
        {
            "target_id": "youtube_live",
            "auto_reconnect": True,
            "max_retries": 5,
        }
    ).to_project_settings()

    assert settings["auto_reconnect"] is True
    assert settings["max_retries"] == 5


def test_discord_live_target_is_window_share_not_rtmp():
    from app.broadcast_output import live_target_preflight

    diag = live_target_preflight(
        {"target_id": "discord_video_call"},
        {"width": 1920, "height": 1080, "fps": 30},
        ffmpeg_exe="ffmpeg-test",
    )

    assert diag["ok"] is True
    assert diag["preset"]["output_kind"] == "window_share"
    assert diag["command"] == []
    assert "Program Output window" in " ".join(diag["warnings"])


def test_tiktok_live_target_requires_platform_issued_rtmp_values():
    from app.broadcast_output import live_target_preflight

    diag = live_target_preflight(
        {"target_id": "tiktok_live"},
        {"width": 1080, "height": 1920, "fps": 30},
        ffmpeg_exe="ffmpeg-test",
    )

    assert diag["ok"] is False
    assert any("server URL" in error for error in diag["errors"])
    assert any("stream key" in error for error in diag["errors"])
    assert diag["preset"]["experimental"] is True


def test_vertical_live_targets_recommend_vertical_canvas():
    from app.broadcast_output import recommended_canvas_for_live_target

    canvas = recommended_canvas_for_live_target(
        {"target_id": "instagram_live"},
        {"width": 1920, "height": 1080, "fps": 60},
    )

    assert canvas["width"] == 1080
    assert canvas["height"] == 1920
    assert canvas["orientation"] == "vertical"


def test_discord_live_target_returns_virtual_camera_plan():
    from app.broadcast_output import live_target_preflight

    diag = live_target_preflight(
        {"target_id": "discord_video_call"},
        {"width": 1920, "height": 1080, "fps": 30},
        ffmpeg_exe="ffmpeg-test",
    )

    assert diag["virtual_camera"]["manual_fallback"] is True
    assert diag["virtual_camera"]["selected_backend"] == "program_output_window_share"
