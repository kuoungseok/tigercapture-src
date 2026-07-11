from pathlib import Path

import pytest


def test_default_facetracker_uses_external_sidecar_location():
    from app.vtuber.openseeface_video_source import DEFAULT_FACETRACKER

    normalized = DEFAULT_FACETRACKER.as_posix()
    assert "/external/tools/vseeface/VSeeFace/" in normalized
    assert normalized.endswith("/VSeeFace_Data/StreamingAssets/Binary/facetracker.exe")


def test_build_facetracker_command_uses_raw_rgb_and_endpoint():
    from app.vtuber.openseeface_video_source import build_facetracker_command

    command = build_facetracker_command(
        facetracker=Path("facetracker.exe"),
        host="127.0.0.1",
        port=39540,
        width=640,
        height=360,
        fps=24,
        model=3,
        detection_threshold=0.35,
        try_hard=True,
        log_data=Path("data.csv"),
        log_output=Path("output.txt"),
    )

    assert command[:3] == ["facetracker.exe", "--raw-rgb", "1"]
    assert command[command.index("--ip") + 1] == "127.0.0.1"
    assert command[command.index("--port") + 1] == "39540"
    assert command[command.index("--width") + 1] == "640"
    assert command[command.index("--height") + 1] == "360"
    assert command[command.index("--fps") + 1] == "24"
    assert command[command.index("--detection-threshold") + 1] == "0.35"
    assert command[command.index("--try-hard") + 1] == "1"
    assert command[command.index("--log-data") + 1] == "data.csv"


def test_parse_crop_clamps_to_valid_normalized_region():
    from app.vtuber.openseeface_video_source import parse_crop

    assert parse_crop("0.9,0.8,0.5,0.5") == pytest.approx((0.9, 0.8, 0.1, 0.2))
    assert parse_crop("") is None


def test_tracking_row_count_ignores_header_and_blank_rows(tmp_path):
    from app.vtuber.openseeface_video_source import _count_tracking_rows

    csv_path = tmp_path / "openseeface.csv"
    csv_path.write_text("Frame,FPS,Success3D\n,,\n", encoding="utf-8")

    assert _count_tracking_rows(csv_path) == 0

    csv_path.write_text("Frame,FPS,Success3D\n,,\n1,15,True\n", encoding="utf-8")

    assert _count_tracking_rows(csv_path) == 1
