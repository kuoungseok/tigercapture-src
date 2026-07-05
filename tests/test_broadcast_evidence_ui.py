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
                "operator_steps": ["Open the shared VTuber Studio and choose YouTube, Twitch, or Custom RTMP."],
            },
        }
    )

    assert lines[0].startswith("Broadcast sale evidence")
    assert lines[1] == "Local checks: 3/3 passed."
    assert lines[2] == "Manual platform checks left: 2."
    assert lines[3] == "Next: Private/unlisted RTMP ingest test"
    assert "VTuber Studio" in lines[4]


def test_broadcast_evidence_register_defaults_are_check_specific():
    from app.broadcast_evidence_ui import broadcast_evidence_register_defaults

    rtmp = broadcast_evidence_register_defaults("private_rtmp_ingest")
    discord = broadcast_evidence_register_defaults("discord_window_share")

    assert rtmp["title"] == "Register RTMP Evidence"
    assert "YouTube" in rtmp["platform"]
    assert discord["title"] == "Register Discord Evidence"
    assert discord["platform"] == "Discord"
    assert "stream keys" in discord["confirm_label"]


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
