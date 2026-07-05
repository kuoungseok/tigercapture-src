from __future__ import annotations

import argparse
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


def run_cut_edit_workspace_capture(
    *,
    media: str | Path | None = None,
    out_dir: str | Path = ROOT / "debugCapture" / "ui_renewal_cut_edit_workspace",
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
        _wait(app, 280)

        split_at = min(max(4200, duration_ms // 8 if duration_ms else 4200), 9000)
        split = registry.execute("timeline.split", {"track_id": track_id, "at_ms": split_at}).to_dict()
        steps.append({"action": "timeline.split", **split})
        right_clip_id = int((split.get("result") or {}).get("right_clip_id") or 0)
        checks["timeline_split"] = bool(split.get("ok") and right_clip_id)

        marker = registry.execute(
            "timeline.marker.add",
            {"id": "cut-review-point", "ms": split_at, "label": "Cut Review", "color": "#D8C89E"},
        ).to_dict()
        steps.append({"action": "timeline.marker.add", **marker})
        checks["timeline_marker"] = bool(marker.get("ok"))

        # Add a transition to the first edit point so the same capture shows
        # cut, transition, and selected clip state without any synthetic UI.
        transition = registry.execute(
            "transition.apply",
            {
                "track_id": track_id,
                "clip_id": clip_id,
                "transition_type": "dissolve",
                "duration_ms": 520,
            },
        ).to_dict()
        steps.append({"action": "transition.apply", **transition})
        checks["transition"] = bool(transition.get("ok"))

        selected = registry.execute(
            "selection.set",
            {"kind": "video", "track_id": track_id, "clip_id": right_clip_id or clip_id},
        ).to_dict()
        steps.append({"action": "selection.set", **selected})
        checks["selection"] = bool(selected.get("ok"))

        focus = registry.execute(
            "ui.focus_surface",
            {"surface": "timeline", "kind": "video", "track_id": track_id, "clip_id": right_clip_id or clip_id},
        ).to_dict()
        steps.append({"action": "ui.focus_surface", **focus})
        checks["focus_timeline"] = bool(focus.get("ok"))

        try:
            editor._player.set_position(split_at)
        except Exception:
            pass
        _wait(app, 560)
        checks["viewer_frame_visible"] = _force_viewer_frame(editor, media_path, split_at, out)

        review_framing: dict[str, Any] = {}
        try:
            frame_for_review = getattr(editor, "_apply_timeline_review_framing", None)
            if callable(frame_for_review):
                review_framing = dict(
                    frame_for_review(center_ms=split_at, span_ms=12000, notify=False) or {}
                )
        except Exception as exc:
            review_framing = {"ok": False, "error": str(exc)}
        checks["review_timeline_framing"] = bool(review_framing.get("ok"))
        steps.append(
            {
                "action": "ui.timeline.review_framing",
                "ok": bool(review_framing.get("ok")),
                "result": review_framing,
            }
        )

        row = getattr(editor, "_track_rows", {}).get(track_id)
        if row is not None:
            row.update()
        ruler = getattr(editor, "_timeline_ruler", None)
        if ruler is not None:
            ruler.update()
        _wait(app, 140)

        track = editor._find_track(track_id) if hasattr(editor, "_find_track") else None
        clips = list(getattr(track, "clips", []) or []) if track is not None else []
        checks["two_clips_visible_model"] = len(clips) >= 2
        checks["adjacent_edit_point"] = any(
            int(getattr(left, "timeline_out_ms", -100)) == int(getattr(right, "timeline_in_ms", -200))
            for left, right in zip(clips, clips[1:])
        )
        workbench = getattr(editor, "_workbench_panel", None)
        edit_card = getattr(workbench, "_edit_point_evidence_card", None) if workbench is not None else None
        checks["workbench_edit_point_card"] = bool(edit_card is not None and edit_card.isVisible())

        timeline_png = out / "timeline_cut_edit_action.png"
        editor_png = out / "editor_cut_edit_action.png"
        viewer_png = out / "viewer_cut_edit_action.png"
        timeline_host = getattr(editor, "_timeline_section_host", None) or editor
        viewer_host = getattr(editor, "_preview_host", None) or editor
        checks["timeline_screenshot"] = _save_widget(timeline_host, timeline_png)
        checks["editor_screenshot"] = _save_widget(editor, editor_png)
        checks["viewer_screenshot"] = _save_widget(viewer_host, viewer_png)
        artifacts["timeline_cut_edit"] = str(timeline_png.resolve())
        artifacts["editor_cut_edit"] = str(editor_png.resolve())
        artifacts["viewer_cut_edit"] = str(viewer_png.resolve())
    finally:
        editor.close()
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()

    ok = all(
        checks.get(key, False)
        for key in (
            "media_imported",
            "timeline_split",
            "timeline_marker",
            "transition",
            "selection",
            "focus_timeline",
            "viewer_frame_visible",
            "review_timeline_framing",
            "two_clips_visible_model",
            "adjacent_edit_point",
            "workbench_edit_point_card",
            "timeline_screenshot",
            "editor_screenshot",
            "viewer_screenshot",
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
        "split_at_ms": split_at,
        "timeline_review_framing": review_framing,
    }
    report_path = out / "cut_edit_workspace_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report"] = str(report_path.resolve())
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture renewed timeline cut/edit point workspace with real media.")
    parser.add_argument("--media", default="")
    parser.add_argument("--out-dir", default=str(ROOT / "debugCapture" / "ui_renewal_cut_edit_workspace"))
    parser.add_argument("--language", default="ko")
    args = parser.parse_args()
    report = run_cut_edit_workspace_capture(
        media=args.media or None,
        out_dir=args.out_dir,
        language=args.language,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
