def test_live_target_troubleshooting_builds_youtube_auth_checklist():
    from app.broadcast_troubleshooting import build_live_target_troubleshooting

    plan = build_live_target_troubleshooting(
        {"target_id": "youtube_live"},
        {
            "state": "error",
            "platform_error_kind": "platform_auth",
            "platform_error_message": "Platform rejected the stream.",
            "stderr_tail": "Server returned 403 Forbidden",
        },
    )

    assert plan["schema"] == "tigerstudio.broadcast.live_target_troubleshooting.v1"
    assert plan["target_id"] == "youtube_live"
    assert plan["error_kind"] == "platform_auth"
    assert plan["primary_action"] == "refresh_stream_key"
    assert any("YouTube Live Control Room" in step for step in plan["checks"])
    assert plan["panel"]["schema"] == "tigerstudio.broadcast.live_target_troubleshooting_panel.v1"
    assert plan["panel"]["primary"]["kind"] == "open_url"
    assert plan["panel"]["primary"]["url"] == "https://studio.youtube.com"
    assert plan["check_items"][0]["status"] == "pending"
    assert plan["safe_to_retry"] is False


def test_live_target_troubleshooting_handles_discord_window_share():
    from app.broadcast_troubleshooting import build_live_target_troubleshooting

    plan = build_live_target_troubleshooting({"target_id": "discord_video_call"}, {"state": "manual_output"})

    assert plan["primary_action"] == "share_program_output"
    assert plan["severity"] == "info"
    assert any("Program Output" in step for step in plan["checks"])
    assert plan["panel"]["primary"]["kind"] == "show_window_share_steps"
    assert any(
        item["action"].get("action_id") == "broadcast.virtual_camera.obs_bridge_plan"
        for item in plan["check_items"]
    )


def test_live_target_troubleshooting_marks_experimental_rtmp_access():
    from app.broadcast_troubleshooting import build_live_target_troubleshooting

    plan = build_live_target_troubleshooting(
        {"target_id": "instagram_live"},
        {"state": "error", "platform_error_kind": "stream_closed"},
    )

    assert plan["platform"]["experimental"] is True
    assert any("external encoder" in step or "producer access" in step for step in plan["checks"])
