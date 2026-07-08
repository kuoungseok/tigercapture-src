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


def _raise_text_overlay(editor: Any, at_ms: int) -> bool:
    try:
        canvas = getattr(editor, "_drawing_canvas", None)
        if canvas is not None:
            canvas.show()
            canvas.raise_()
            canvas.update()
        overlay = getattr(editor, "_update_text_clip_overlay", None)
        if callable(overlay):
            overlay(int(at_ms))
        label = getattr(editor, "_text_preview_label", None)
        if label is not None:
            label.raise_()
            label.update()
            return bool(label.isVisible() and label.text())
    except Exception:
        return False
    return False


def _visible_text_overlay_count(editor: Any) -> int:
    labels = list(getattr(editor, "_text_preview_labels", []) or [])
    if not labels:
        label = getattr(editor, "_text_preview_label", None)
        labels = [label] if label is not None else []
    count = 0
    for label in labels:
        try:
            if label is not None and label.isVisible() and str(label.text()).strip():
                count += 1
        except Exception:
            continue
    return count


def run_typography_workspace_capture(
    *,
    media: str | Path | None = None,
    out_dir: str | Path = ROOT / "debugCapture" / "ui_renewal_typography_workspace",
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

        end_ms = min(max(6500, duration_ms // 4 if duration_ms else 6500), 8800)
        text_layers = [
            {
                "text": "TIGER STUDIO",
                "start_ms": 400,
                "style": {
                    "font_family": "Noto Sans KR",
                    "font_size": 430,
                    "font_weight": 800,
                    "color": "#F8FAFC",
                    "position_x": 0.5,
                    "position_y": 0.18,
                    "letter_spacing": 2,
                    "shadow_color": "#000000",
                    "shadow_offset_y": 3,
                },
                "animation": {
                    "preset_id": "catalog-title",
                    "in_animation": "slide-up",
                    "out_animation": "fade-out",
                    "in_duration": 0.45,
                    "out_duration": 0.65,
                },
            },
            {
                "text": "Kinetic titles\nfor real edits",
                "start_ms": 650,
                "style": {
                    "font_family": "Noto Sans KR",
                    "font_size": 110,
                    "font_weight": 500,
                    "color": "#E5E7EB",
                    "position_x": 0.5,
                    "position_y": 0.36,
                    "letter_spacing": 1,
                    "shadow_color": "#000000",
                    "shadow_offset_y": 2,
                },
                "animation": {
                    "preset_id": "catalog-subtitle",
                    "in_animation": "fade-in",
                    "out_animation": "fade-out",
                    "in_duration": 0.35,
                    "out_duration": 0.55,
                },
            },
            {
                "text": "OPENING  /  BODY  /  SUBTITLE",
                "start_ms": 740,
                "style": {
                    "font_family": "Noto Sans KR",
                    "font_size": 56,
                    "font_weight": 600,
                    "color": "#BAE6FD",
                    "position_x": 0.5,
                    "position_y": 0.58,
                    "letter_spacing": 3,
                    "shadow_color": "#000000",
                    "shadow_offset_y": 2,
                },
                "animation": {
                    "preset_id": "catalog-style-sample",
                    "in_animation": "fade-in",
                    "out_animation": "fade-out",
                    "in_duration": 0.3,
                    "out_duration": 0.45,
                },
            },
            {
                "text": "서울의 밤  ·  東京の光",
                "start_ms": 800,
                "style": {
                    "font_family": "Noto Sans KR",
                    "font_size": 76,
                    "font_weight": 700,
                    "color": "#FDE68A",
                    "position_x": 0.5,
                    "position_y": 0.72,
                    "letter_spacing": 1,
                    "shadow_color": "#000000",
                    "shadow_offset_y": 2,
                },
                "animation": {
                    "preset_id": "catalog-multilingual",
                    "in_animation": "slide-up",
                    "out_animation": "fade-out",
                    "in_duration": 0.4,
                    "out_duration": 0.5,
                },
            },
            {
                "text": "LOWER THIRD  /  CAPTION  /  CTA",
                "start_ms": 950,
                "style": {
                    "font_family": "Noto Sans KR",
                    "font_size": 58,
                    "font_weight": 600,
                    "color": "#C7D2FE",
                    "position_x": 0.5,
                    "position_y": 0.84,
                    "letter_spacing": 2,
                    "background_color": "rgba(8, 12, 20, 120)",
                    "background_padding": 6,
                    "background_radius": 7,
                },
                "animation": {
                    "preset_id": "catalog-lower-third",
                    "in_animation": "fade-in",
                    "out_animation": "fade-out",
                    "in_duration": 0.25,
                    "out_duration": 0.4,
                },
            },
        ]
        text_ids: list[int] = []
        text_ok: list[bool] = []
        keyframe_ok: list[bool] = []
        for index, layer in enumerate(text_layers):
            text = registry.execute(
                "text.add",
                {
                    "track_id": track_id,
                    "clip_id": clip_id,
                    "text": layer["text"],
                    "start_ms": int(layer["start_ms"]),
                    "end_ms": end_ms,
                    "style": layer["style"],
                    "animation": layer["animation"],
                },
            ).to_dict()
            steps.append({"action": "text.add", "layer": index + 1, **text})
            text_id = int((text.get("result") or {}).get("text_id") or 0)
            text_ids.append(text_id)
            text_ok.append(bool(text.get("ok") and text_id))

            keyframes_payload = {
                "opacity": [
                    {"time_ms": int(layer["start_ms"]), "value": 0.0, "curve": "ease_out"},
                    {"time_ms": int(layer["start_ms"]) + 450, "value": 1.0, "curve": "smoothstep"},
                    {"time_ms": max(1500, end_ms - 900), "value": 1.0, "curve": "linear"},
                    {"time_ms": max(1600, end_ms - 250), "value": 0.0, "curve": "ease_in"},
                ],
                "scale": [
                    {"time_ms": int(layer["start_ms"]), "value": 0.9 + index * 0.015, "curve": "ease_out"},
                    {"time_ms": int(layer["start_ms"]) + 650, "value": 1.0, "curve": "smoothstep"},
                    {"time_ms": max(1600, end_ms - 250), "value": 1.025, "curve": "ease_in"},
                ],
                "position_y": [
                    {"time_ms": int(layer["start_ms"]), "value": float(layer["style"]["position_y"]) + 0.035, "curve": "ease_out"},
                    {"time_ms": int(layer["start_ms"]) + 700, "value": float(layer["style"]["position_y"]), "curve": "smoothstep"},
                ],
            }
            keyed = registry.execute(
                "text.set_keyframes",
                {
                    "track_id": track_id,
                    "clip_id": clip_id,
                    "text_id": text_id,
                    "keyframes": keyframes_payload,
                },
            ).to_dict()
            steps.append({"action": "text.set_keyframes", "layer": index + 1, **keyed})
            keyframe_ok.append(bool(keyed.get("ok")))
        checks["text_added"] = all(text_ok) and len(text_ids) >= 5
        checks["text_keyframes"] = all(keyframe_ok) and len(keyframe_ok) >= 5

        selected = registry.execute(
            "selection.set",
            {"kind": "video", "track_id": track_id, "clip_id": clip_id},
        ).to_dict()
        steps.append({"action": "selection.set", **selected})
        checks["selection"] = bool(selected.get("ok"))
        refresh_workbench = getattr(editor, "_refresh_workbench", None)
        if callable(refresh_workbench):
            refresh_workbench()
        panel = getattr(editor, "_workbench_panel", None)
        if panel is not None and hasattr(panel, "_set_inspector_tab"):
            panel._set_inspector_tab("fx")

        seek_ms = 1800
        try:
            editor._player.set_position(seek_ms)
        except Exception:
            pass
        _wait(app, 480)
        checks["viewer_frame_visible"] = _force_viewer_frame(editor, media_path, seek_ms, out)
        checks["text_overlay_visible"] = _raise_text_overlay(editor, seek_ms)
        visible_text_layers = _visible_text_overlay_count(editor)
        checks["multiple_text_overlay_visible"] = visible_text_layers >= 4

        track = editor._find_track(track_id) if hasattr(editor, "_find_track") else None
        actors = list(getattr(track, "typography_actors", []) or []) if track is not None else []
        checks["timeline_text_actor"] = len(actors) >= 5
        checks["timeline_keyframes_attached"] = sum(1 for row in actors if getattr(row, "keyframes", None)) >= 5
        row = getattr(editor, "_track_rows", {}).get(track_id)
        if row is not None:
            row.update()
        _wait(app, 160)

        preview_png = out / "viewer_typography_action.png"
        timeline_png = out / "timeline_typography_action.png"
        editor_png = out / "editor_typography_action.png"
        preview_host = getattr(editor, "_preview_host", None) or editor
        timeline_host = getattr(editor, "_timeline_section_host", None) or editor
        checks["preview_screenshot"] = _save_widget(preview_host, preview_png)
        checks["timeline_screenshot"] = _save_widget(timeline_host, timeline_png)
        checks["editor_screenshot"] = _save_widget(editor, editor_png)
        artifacts["viewer_typography"] = str(preview_png.resolve())
        artifacts["timeline_typography"] = str(timeline_png.resolve())
        artifacts["editor_typography"] = str(editor_png.resolve())
        artifacts["visible_text_layer_count"] = str(visible_text_layers)
    finally:
        editor.close()
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()

    ok = all(
        checks.get(key, False)
        for key in (
            "media_imported",
            "text_added",
            "text_keyframes",
            "selection",
            "viewer_frame_visible",
            "text_overlay_visible",
            "timeline_text_actor",
            "timeline_keyframes_attached",
            "multiple_text_overlay_visible",
            "preview_screenshot",
            "timeline_screenshot",
            "editor_screenshot",
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
    }
    report_path = out / "typography_workspace_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report"] = str(report_path.resolve())
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture renewed typography workspace with real editor actions.")
    parser.add_argument("--media", default="")
    parser.add_argument("--out-dir", default=str(ROOT / "debugCapture" / "ui_renewal_typography_workspace"))
    parser.add_argument("--language", default="ko")
    args = parser.parse_args()
    report = run_typography_workspace_capture(
        media=args.media or None,
        out_dir=args.out_dir,
        language=args.language,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
