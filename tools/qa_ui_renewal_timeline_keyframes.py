from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from tools.qa_workbench_node_action_flow import (  # noqa: E402
    _default_media,
    _force_viewer_frame,
    _save_widget,
    _wait,
)


def run_timeline_keyframe_capture(
    *,
    media: str | Path | None = None,
    out_dir: str | Path = ROOT / "debugCapture" / "ui_renewal_timeline_keyframes",
    language: str = "ko",
) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    from app.font_fallback import apply_ui_font
    from app.i18n import initialize, set_language
    from app.style import APP_QSS
    from app.video_editor_window import VideoEditorWindow

    media_path = Path(media).expanduser() if media else _default_media()
    if not media_path.is_absolute():
        media_path = ROOT / media_path
    out = Path(out_dir)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    app.setStyleSheet(APP_QSS)
    active_language = initialize()
    if language:
        set_language(language)
        active_language = language

    editor = VideoEditorWindow()
    steps: list[dict[str, Any]] = []
    artifacts: dict[str, str] = {}
    checks: dict[str, bool] = {}
    try:
        try:
            editor._autosave_timer.stop()
            editor._do_autosave = lambda *_args, **_kwargs: None
        except Exception:
            pass
        editor.resize(1480, 920)
        editor.show()
        _wait(app, 240)

        registry = editor._ensure_python_action_registry()
        imported = registry.execute(
            "media.import_to_timeline",
            {"path": str(media_path), "kind": "video", "at_ms": 0},
        ).to_dict()
        steps.append({"action": "media.import_to_timeline", **imported})
        track_id = int((imported.get("result") or {}).get("track_id") or 0)
        clip_id = int((imported.get("result") or {}).get("clip_id") or 0)
        duration_ms = int((imported.get("result") or {}).get("duration_ms") or 0)
        checks["media_imported"] = bool(imported.get("ok") and track_id and clip_id)
        _wait(app, 260)

        state = registry.execute(
            "track.set_state",
            {
                "kind": "video",
                "track_id": track_id,
                "pip_enabled": True,
                "pip_x": 0.62,
                "pip_y": 0.42,
                "pip_scale": 0.34,
                "pip_opacity": 0.82,
            },
        ).to_dict()
        steps.append({"action": "track.set_state", **state})
        checks["pip_state_action"] = bool(state.get("ok"))

        track = editor._find_track(track_id)
        key_span = max(3600, min(9000, duration_ms if duration_ms > 0 else 9000))
        keyframes = [
            {"ms": 0, "x": 0.48, "y": 0.44, "scale": 0.28, "opacity": 1.0},
            {"ms": int(key_span * 0.36), "x": 0.62, "y": 0.39, "scale": 0.36, "opacity": 0.9},
            {"ms": int(key_span * 0.72), "x": 0.70, "y": 0.50, "scale": 0.31, "opacity": 0.66},
        ]
        if track is not None:
            track.pip_keyframes = keyframes
        checks["pip_keyframes_attached"] = bool(track is not None and len(getattr(track, "pip_keyframes", []) or []) == 3)

        selected = registry.execute(
            "selection.set",
            {"kind": "video", "track_id": track_id, "clip_id": clip_id},
        ).to_dict()
        steps.append({"action": "selection.set", **selected})
        checks["selection"] = bool(selected.get("ok"))

        if hasattr(editor, "_refresh_pip_panel"):
            editor._refresh_pip_panel()
        row = getattr(editor, "_track_rows", {}).get(track_id)
        if row is not None:
            row.update()

        seek_ms = keyframes[1]["ms"]
        try:
            editor._player.set_position(seek_ms)
        except Exception:
            pass
        _wait(app, 600)
        checks["viewer_frame_visible"] = _force_viewer_frame(editor, media_path, seek_ms, out)
        _wait(app, 120)

        editor_png = out / "editor_timeline_keyframes_action.png"
        timeline_png = out / "timeline_keyframes_action.png"
        timeline_host = getattr(editor, "_timeline_section_host", None) or editor
        checks["editor_screenshot"] = _save_widget(editor, editor_png)
        checks["timeline_screenshot"] = _save_widget(timeline_host, timeline_png)
        artifacts["editor_timeline_keyframes"] = str(editor_png.resolve())
        artifacts["timeline_keyframes"] = str(timeline_png.resolve())
    finally:
        editor.close()
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()

    ok = all(
        checks.get(key, False)
        for key in (
            "media_imported",
            "pip_state_action",
            "pip_keyframes_attached",
            "selection",
            "viewer_frame_visible",
            "editor_screenshot",
            "timeline_screenshot",
        )
    )
    report = {
        "ok": bool(ok),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "language": active_language,
        "media": str(media_path),
        "checks": checks,
        "steps": steps,
        "artifacts": artifacts,
        "keyframes": keyframes,
    }
    report_path = out / "timeline_keyframes_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report"] = str(report_path.resolve())
    return report


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Capture renewed timeline keyframe markers with real media.")
    parser.add_argument("--media", default="")
    parser.add_argument("--out-dir", default=str(ROOT / "debugCapture" / "ui_renewal_timeline_keyframes"))
    parser.add_argument("--language", default="ko")
    args = parser.parse_args()
    report = run_timeline_keyframe_capture(
        media=args.media or None,
        out_dir=args.out_dir,
        language=args.language,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
