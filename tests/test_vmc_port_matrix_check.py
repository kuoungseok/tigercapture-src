import pytest
import socket


def test_parse_ports_deduplicates_and_validates_range():
    from tools.vmc_port_matrix_check import parse_ports

    assert parse_ports("39539, 39540,39539") == [39539, 39540]

    with pytest.raises(ValueError):
        parse_ports("0")


def test_summarize_report_flags_core_vmc_channels():
    from tools.vmc_port_matrix_check import summarize_report

    summary = summarize_report({
        "ok": True,
        "endpoint": {"port": 39539},
        "frame_count": 3,
        "sent_packets": 33,
        "received_packets": 33,
        "decoded_summary": {
            "message_count": 33,
            "bones": {"Head": {"rotation": [0, 0, 0, 1]}},
            "blends": {"A": 0.42},
        },
        "diagnostics": {"selected_backend": "mediapipe_tasks"},
        "errors": [],
    })

    assert summary["port"] == 39539
    assert summary["ok"] is True
    assert summary["decoded_packets"] == 33
    assert summary["head_bone"] is True
    assert summary["mouth_a"] == 0.42
    assert summary["backend"] == "mediapipe_tasks"


def test_loopback_check_reports_port_bind_failure_before_video_decode():
    from tools.vmc_udp_loopback_check import run_loopback_check

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        report = run_loopback_check(video="missing.mp4", port=port)

    assert report["ok"] is False
    assert "udp_loopback_bind_failed" in report["errors"]
    assert report["sent_packets"] == 0
