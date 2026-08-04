from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


def test_m3_slot_pointer_capture_proves_visual_drop_and_undo(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "slot-capture"
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "qa_painter_ui_m3_slot_capture.py"),
            "--output",
            str(output),
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
        (output / "painter_ui_m3_slot_pointer_capture.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["passed"] is True
    assert report["pointer"]["interaction"] == "move"
    assert report["pointer"]["arc_handle_hit"] == ""
    assert report["drop_preview_id"] == report["slot_object_id"]
    assert report["dropped_parent_id"] == report["slot_object_id"]
    assert report["object_id"] in report["slot_child_ids"]
    assert report["visually_inside_slot"] is True
    assert report["undo_after_drop"] == report["undo_before"] + 1
    assert report["restored_parent_id"] == report["before_parent_id"]
    for name in ("before", "drag_preview", "after", "undo"):
        assert Path(report["captures"][name]["path"]).stat().st_size > 1000
