from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


def test_nested_change_to_product_capture_changes_visual_and_preserves_outer(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "nested-change-to"
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    completed = subprocess.run(
        [sys.executable,
         str(root / "tools" / "qa_painter_ui_m3_nested_change_to_capture.py"),
         "--output", str(output)],
        cwd=root, env=environment, check=False, capture_output=True,
        text=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(
        (output / "nested_change_to_capture.json").read_text(encoding="utf-8")
    )
    assert report["passed"] is True
    assert report["on_component_id"] == report["expected_on_component_id"]
    assert report["off_again_component_id"] == report["expected_off_component_id"]
    assert report["effective_outer_component_id"] == report["outer_component_id"]
    assert report["effective_nested_parent_id"] == report["outer_id"]
    assert report["effective_nested_opacity"] == 0.7
    assert report["on_fill"] == "#47C58E"
    assert report["off_again_fill"] == "#8A8F98"
    for name in ("off", "on", "off_again"):
        assert Path(report["captures"][name]["path"]).stat().st_size > 1000
