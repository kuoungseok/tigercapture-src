"""QA for timeline-visible preset/effect markers.

Applied presets must remain visible on both roomy and short clips. This keeps
users from dragging an effect/title/transition and then wondering whether
anything happened.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _make_track():
    from app.timeline_model import VideoClip, VideoTrack

    wide = VideoClip(id=1, source_duration_ms=6000, timeline_in_ms=0, source_in_ms=0, source_out_ms=2200)
    wide.video_filters = {
        "enabled": True,
        "preset_meta": {"id": "clean-pop", "name": "Clean Pop"},
        "contrast": 0.15,
    }
    wide.chroma_key = {
        "enabled": True,
        "preset_meta": {"id": "soft-key", "name": "Soft Key"},
        "strength": 0.4,
    }
    wide.transition_out_type = "wipe_left"
    wide.transition_out_ms = 500
    wide.transition_preset_meta = {"id": "wipe-left", "name": "Wipe Left", "kind": "transition"}
    wide.color_grade = {"name": "Warm Pop", "temperature": 0.22}

    narrow = VideoClip(id=2, source_duration_ms=6000, timeline_in_ms=2600, source_in_ms=0, source_out_ms=2920)
    narrow.video_filters = {
        "enabled": True,
        "preset_meta": {"id": "micro-fx", "name": "Micro FX"},
        "sharpen": 0.4,
    }
    narrow.transition_out_type = "dissolve"
    narrow.transition_out_ms = 220
    narrow.transition_preset_meta = {"id": "tiny-cross", "name": "Tiny Cross", "kind": "transition"}

    track = VideoTrack(id=1, clips=[wide, narrow])
    track.offset_ms = 0
    track.source_path = None
    track.thumbnails = []
    track.speed_segments = []
    track.fades = []
    track.cuts = []
    track.zoom_actors = []
    try:
        from app.video_editor_window import TextClip

        title = TextClip(start_ms=250, end_ms=1650)
        title.text = "Preset Title"
        track.typography_actors = [title]
    except Exception:
        track.typography_actors = []
    return track


def _accent_pixel_count(image, rect) -> int:
    count = 0
    left = max(0, rect.left())
    right = min(image.width() - 1, rect.right())
    top = max(0, rect.top())
    bottom = min(image.height() - 1, rect.bottom())
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            color = image.pixelColor(x, y)
            channels = (color.red(), color.green(), color.blue())
            if (
                color.alpha() > 0
                and max(channels) >= 120
                and max(channels) - min(channels) >= 42
            ):
                count += 1
    return count


def run_timeline_preset_visibility_qa(
    *, out_dir: Path | str = Path("debugCapture/timeline_preset_visibility_qa")
) -> dict[str, Any]:
    app = _ensure_app()
    from app.i18n import initialize, set_language
    from app.video_editor_window import TrackRow

    initialize()
    set_language("en")
    out_path = ROOT / out_dir if not Path(out_dir).is_absolute() else Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    track = _make_track()
    row = TrackRow(track)
    row.set_px_per_sec(100.0)
    row.resize(720, max(92, row.sizeHint().height()))
    row.show()
    app.processEvents()

    wide, narrow = track.clips
    wide_entries = row._clip_effect_strip_entries(wide)
    narrow_entries = row._clip_effect_strip_entries(narrow)
    tooltip = row._clip_effect_tooltip(wide)
    wide_rect = row._clip_rect(wide)
    narrow_rect = row._clip_rect(narrow)
    shot = out_path / "timeline_preset_visibility.png"
    pix = row.grab()
    pix.save(str(shot))
    image = pix.toImage()
    wide_bottom = wide_rect.adjusted(4, max(0, wide_rect.height() - 24), -4, -2)
    narrow_bottom = narrow_rect.adjusted(1, max(0, narrow_rect.height() - 18), -1, -2)
    wide_pixels = _accent_pixel_count(image, wide_bottom)
    narrow_pixels = _accent_pixel_count(image, narrow_bottom)

    row.close()
    row.deleteLater()
    app.processEvents()

    checks = {
        "wide_entries": {entry[0] for entry in wide_entries} >= {"FX", "KEY", "TR", "COL"},
        "wide_title_entry": any(entry[0] == "T" for entry in wide_entries),
        "narrow_entries": {entry[0] for entry in narrow_entries} >= {"FX", "TR"},
        "tooltip_localized": tooltip.startswith("Applied clip elements") and "Click a badge" in tooltip,
        "wide_visible_pixels": wide_pixels >= 80,
        "narrow_visible_pixels": narrow_pixels >= 8,
        "screenshot": shot.exists(),
    }
    report = {
        "ok": all(checks.values()),
        "summary": {
            "checks": checks,
            "wide_pixels": wide_pixels,
            "narrow_pixels": narrow_pixels,
            "screenshot": str(shot),
        },
        "wide_entries": [list(row) for row in wide_entries],
        "narrow_entries": [list(row) for row in narrow_entries],
        "tooltip": tooltip,
    }
    (out_path / "timeline_preset_visibility_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Run timeline preset visibility QA.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/timeline_preset_visibility_qa"))
    args = parser.parse_args()
    report = run_timeline_preset_visibility_qa(out_dir=args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
