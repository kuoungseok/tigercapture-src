from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    ("scale", "width", "height"),
    [
        ("1.0", 360, 900),
        ("1.0", 300, 650),
        ("1.5", 360, 900),
    ],
    ids=["normal", "compact", "150-percent"],
)
def test_m3_component_ui_renders_across_capture_gates(
    tmp_path: Path,
    scale: str,
    width: int,
    height: int,
) -> None:
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "capture"
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["QT_SCALE_FACTOR"] = scale

    completed = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "qa_painter_ui_m3_dpi_capture.py"),
            "--output",
            str(output),
            "--inspector-width",
            str(width),
            "--inspector-height",
            str(height),
        ],
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    report = json.loads(
        (output / "painter_ui_m3_dpi_capture.json").read_text(encoding="utf-8")
    )
    assert report["passed"] is True
    expected_dpr = float(scale)
    assert report["inspector"]["device_pixel_ratio"] == expected_dpr
    assert report["preferred_instances_dialog"]["device_pixel_ratio"] == expected_dpr
    assert report["canvas"]["device_pixel_ratio"] == expected_dpr
    assert report["loaded_font_count"] >= 1
    assert report["visible_component_controls"] == [
        "Icon",
        "Label",
        "Show icon",
    ]
    assert all(
        row["visible"] and row["inside_horizontal_viewport"]
        for row in report["component_control_geometry"].values()
    )
    assert (output / "painter_ui_m3_inspector_150.png").stat().st_size > 1000
    assert (
        output / "painter_ui_m3_preferred_instances_150.png"
    ).stat().st_size > 1000
    for state in ("default", "hover", "pressed"):
        assert (
            output / f"painter_ui_m3_button_{state}.png"
        ).stat().st_size > 1000
    interactive = report["interactive_button"]
    assert interactive["hover_state_component_id"] == interactive[
        "hover_component_id"
    ]
    assert interactive["pressed_state_component_id"] == interactive[
        "pressed_component_id"
    ]
