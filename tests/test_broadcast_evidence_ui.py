def test_broadcast_evidence_status_lines_summarize_pending_manual_checks():
    from app.broadcast_evidence_ui import broadcast_evidence_status_lines

    lines = broadcast_evidence_status_lines(
        {
            "status_text": "Broadcast sale evidence: 3/5 passed. Pending: Private RTMP.",
            "summary": {
                "local_runtime_passed": 3,
                "local_runtime_required": 3,
                "manual_platform_pending": 2,
            },
            "operator_focus": {
                "id": "private_rtmp_ingest",
                "label": "Private/unlisted RTMP ingest test",
                "primary_cta": "Run a private/unlisted RTMP ingest test, then click Register RTMP in VTuber Studio.",
                "why_required": "This proves Program Output reaches a real service.",
                "safe_registration_hint": "Allowed evidence: redacted screenshot/log/notes.",
                "operator_steps": ["Open the shared VTuber Studio and choose YouTube, Twitch, or Custom RTMP."],
            },
            "youtube_only_flow": {"complete": False},
        }
    )

    assert lines[0].startswith("Broadcast sale evidence")
    assert lines[1] == "Local checks: 3/3 passed."
    assert "Manual platform checks left: 2." in lines
    assert any(line.startswith("Next: Run a private/unlisted RTMP ingest test") for line in lines)
    assert any("YouTube-only path" in line and "Discord/video-call is optional" in line for line in lines)
    assert any(line.startswith("Why:") for line in lines)
    assert any(line.startswith("Safe evidence:") for line in lines)
    assert any("VTuber Studio" in line for line in lines)


def test_broadcast_evidence_register_defaults_are_check_specific():
    from app.broadcast_evidence_ui import broadcast_evidence_register_defaults

    rtmp = broadcast_evidence_register_defaults("private_rtmp_ingest")
    youtube = broadcast_evidence_register_defaults("youtube_unlisted_viewer_playback")
    video_call = broadcast_evidence_register_defaults("discord_window_share")

    assert rtmp["title"] == "Register RTMP Evidence"
    assert "YouTube" in rtmp["platform"]
    assert youtube["title"] == "Register YouTube Viewer Evidence"
    assert youtube["platform"] == "YouTube"
    assert video_call["title"] == "Register Optional Video-Call Evidence"
    assert "stream keys" in youtube["confirm_label"]
    assert "YouTube watch/preview URLs" in youtube["confirm_label"]
    assert "YouTube watch/preview URLs" in youtube["description"]
    assert "Program Output" in youtube["safe_note_template"]
    assert "redacted" in youtube["safe_note_template"]
    assert "http" not in youtube["safe_note_template"].lower()
    assert "private chat" in youtube["confirm_label"]
    assert "real platform check" in youtube["description"]


def test_build_broadcast_evidence_registration_payload_strips_text():
    from app.broadcast_evidence_ui import build_broadcast_evidence_registration_payload

    payload = build_broadcast_evidence_registration_payload(
        check_id=" discord_window_share ",
        platform=" Discord ",
        evidence_path=" C:/redacted.png ",
        notes=" Program Output only. ",
        confirm_redacted=True,
    )

    assert payload == {
        "check_id": "discord_window_share",
        "platform": "Discord",
        "evidence_path": "C:/redacted.png",
        "notes": "Program Output only.",
        "confirm_redacted": True,
    }


def test_broadcast_evidence_registration_warning_blocks_private_urls():
    from app.broadcast_evidence_ui import (
        broadcast_evidence_registration_warning,
        build_broadcast_evidence_registration_payload,
    )

    unchecked = build_broadcast_evidence_registration_payload(
        check_id="youtube_unlisted_viewer_playback",
        platform="YouTube",
        notes="Preview played Program Output.",
        confirm_redacted=False,
    )
    private_url = build_broadcast_evidence_registration_payload(
        check_id="youtube_unlisted_viewer_playback",
        platform="YouTube",
        notes="Preview played: https://www.youtube.com/watch?v=PRIVATE",
        confirm_redacted=True,
    )
    clean = build_broadcast_evidence_registration_payload(
        check_id="youtube_unlisted_viewer_playback",
        platform="YouTube",
        notes="Private YouTube preview played Program Output; URL, account, and chat redacted.",
        confirm_redacted=True,
    )

    assert "redaction confirmation" in broadcast_evidence_registration_warning(unchecked)
    assert "Remove YouTube watch/preview links" in broadcast_evidence_registration_warning(private_url)
    assert broadcast_evidence_registration_warning(clean) == ""


def test_broadcast_evidence_wizard_summary_orders_user_steps():
    from app.broadcast_evidence_ui import broadcast_evidence_wizard_summary

    summary = broadcast_evidence_wizard_summary(
        {
            "sale_ready": False,
            "status_text": "Broadcast sale evidence: 3/5 passed.",
            "operator_summary": "Commercial broadcast claims are blocked by real-platform evidence.",
            "summary": {"passed": 3, "required": 5},
            "youtube_only_flow": {
                "available": True,
                "complete": False,
                "required_check_ids": ["private_rtmp_ingest", "youtube_unlisted_viewer_playback"],
                "optional_check_ids": ["discord_window_share"],
                "next_required_check": {
                    "id": "private_rtmp_ingest",
                    "primary_cta": "Run private RTMP, then click Register RTMP.",
                },
            },
            "items": [
                {"id": "record_file_local", "label": "Record Program Output", "kind": "local_runtime", "ok": True},
                {"id": "capture_composite_local", "label": "Capture composite", "kind": "local_runtime", "ok": True},
                {
                    "id": "private_rtmp_ingest",
                    "label": "Private RTMP",
                    "kind": "manual_platform",
                    "ok": False,
                    "primary_cta": "Run private RTMP, then click Register RTMP.",
                    "operator_steps": ["Open VTuber Studio."],
                },
                {
                    "id": "youtube_unlisted_viewer_playback",
                    "label": "YouTube viewer playback",
                    "kind": "manual_platform",
                    "ok": False,
                    "primary_cta": "Open YouTube preview, then click Register YouTube View.",
                },
            ],
        }
    )

    assert summary["passed"] == 3
    assert summary["required"] == 5
    assert summary["youtube_only_flow"]["available"] is True
    assert summary["youtube_only_flow"]["next_required_check"]["id"] == "private_rtmp_ingest"
    assert summary["next_step"]["id"] == "live2d_record_file_local"
    assert [step["id"] for step in summary["steps"]] == [
        "record_file_local",
        "live2d_record_file_local",
        "capture_composite_local",
        "private_rtmp_ingest",
        "youtube_unlisted_viewer_playback",
        "discord_window_share",
    ]
    assert any("Register RTMP" in str(step["primary_cta"]) for step in summary["steps"])
