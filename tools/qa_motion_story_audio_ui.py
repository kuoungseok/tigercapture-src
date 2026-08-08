"""Capture real Story workspace evidence for Voice/Composer beat binding."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.motion_designer.schema import MotionComposition
from app.motion_designer.story_direction import add_story_beat, inspect_story
from app.motion_designer.ui.window import MotionDesignerWindow


OUTPUT = ROOT / "debugCapture" / "motion_story_audio_ui"


def main() -> int:
    app = QApplication.instance() or QApplication([])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    composition = MotionComposition(
        name="Story Audio QA",
        width=1280,
        height=720,
        duration_ms=6000,
    )
    add_story_beat(
        composition,
        role="hook",
        start_ms=300,
        end_ms=1800,
        purpose="Open with the promise",
    )
    composition.metadata["audio_timing_sources"] = {
        "voice-qa": {
            "id": "voice-qa",
            "kind": "voice",
            "sentences": [{"text": "Make the first second matter"}],
        },
        "music-qa": {
            "id": "music-qa",
            "kind": "composer",
            "bpm": 124,
            "audio_path": "story-pulse.wav",
            "metadata": {"genre": "electronic"},
        },
    }
    window = MotionDesignerWindow(composition)
    window.resize(1520, 920)
    window.show()
    window.left_tabs.setCurrentWidget(window.story)
    window.story.beats.setCurrentRow(0)
    music_index = next(
        index
        for index in range(window.story.audio_source.count())
        if window.story.audio_source.itemText(index).startswith("Music")
    )
    window.story.audio_source.setCurrentIndex(music_index)
    window.story.bind_audio.click()
    app.processEvents()

    screenshot = OUTPUT / "story_audio_binding_workspace.png"
    capture_ok = window.grab().save(str(screenshot), "PNG")
    story = inspect_story(window.controller.composition)
    report = {
        "schema": "tigerstudio.motion.story_audio_ui_qa.v1",
        "ok": bool(
            capture_ok
            and screenshot.is_file()
            and screenshot.stat().st_size > 0
            and window.story.audio_source.count() == 2
            and len(story["audio_bindings"]) == 1
            and "[Music]" in window.story.beats.item(0).text()
        ),
        "source_count": window.story.audio_source.count(),
        "binding": story["audio_bindings"][0],
        "beat_label": window.story.beats.item(0).text(),
        "screenshot": str(screenshot),
        "source": "real_qt_motion_designer_window",
    }
    (OUTPUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    window.close()
    app.processEvents()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
