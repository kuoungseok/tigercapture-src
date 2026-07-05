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

from tools.qa_workbench_node_action_flow import _default_media, _force_viewer_frame, _save_widget, _wait  # noqa: E402


def _first_video_row(editor: Any):
    rows = getattr(editor, "_track_rows", {}) or {}
    if isinstance(rows, dict):
        for row in rows.values():
            track = getattr(row, "track", None)
            if getattr(track, "clips", None):
                return row
    return None


def _clip_target_pos(row: Any, *, edge: bool = False):
    from PySide6.QtCore import QPoint

    clips = list(getattr(getattr(row, "track", None), "clips", []) or [])
    if not clips:
        return QPoint(max(20, row.width() // 3), max(20, row.height() // 2))
    clip = clips[0]
    rect = row._clip_rect(clip)
    x = rect.right() - 2 if edge else rect.left() + min(max(28, rect.width() // 3), max(28, rect.width() - 8))
    y = rect.center().y()
    return QPoint(int(x), int(y))


def _mime_for(kind: str):
    from PySide6.QtCore import QMimeData

    from app.video_editor_preset_cards import (
        EDITOR_PRESET_MIME_TYPE,
        EFFECT_PRESET_MIME_TYPE,
        TITLE_PRESET_MIME_TYPE,
        TRANSITION_MIME_TYPE,
    )

    md = QMimeData()
    if kind == "effect":
        payload = {
            "video_filters": {"sharpen": 0.25, "vignette": 0.18},
            "__preset_meta": {"id": "qa_soft_focus", "name": "Soft Focus", "kind": "effect"},
        }
        md.setData(EFFECT_PRESET_MIME_TYPE, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    elif kind == "transition":
        payload = {"type": "dissolve", "ms": 650, "name": "Cross Dissolve"}
        md.setData(TRANSITION_MIME_TYPE, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    elif kind == "title":
        payload = {
            "id": "qa_lower_third",
            "name": "Lower Third",
            "text": "Lower third text",
            "duration_ms": 3200,
            "font_size": 42,
        }
        md.setData(TITLE_PRESET_MIME_TYPE, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    elif kind == "workflow":
        payload = {
            "id": "qa_short_form",
            "name": "Short-form Hook Caption",
            "kind": "template",
            "payload": {
                "sequence": [
                    {"kind": "title", "preset_id": "hook", "at_ms": 0, "duration_ms": 1200},
                    {"kind": "effect", "preset_id": "punch", "at_ms": 800, "duration_ms": 1600},
                    {"kind": "caption_style", "preset_id": "caption", "at_ms": 1600, "duration_ms": 2200},
                ]
            },
        }
        md.setData(EDITOR_PRESET_MIME_TYPE, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    else:
        raise ValueError(f"unknown guide kind: {kind}")
    return md


def _set_drop_guide(row: Any, kind: str) -> None:
    md = _mime_for(kind)
    if kind == "transition":
        pos = _clip_target_pos(row, edge=True)
        row._update_transition_drop_target(pos)
        row._update_drop_guide(pos, md)
    elif kind == "effect":
        pos = _clip_target_pos(row, edge=False)
        row._update_effect_drop_target(pos, md)
        row._update_drop_guide(pos, md)
    else:
        pos = _clip_target_pos(row, edge=False)
        row._clear_effect_drop_target()
        row._update_drop_guide(pos, md)
    row.update()


def _save_row_crop(row: Any, path: Path, *, width: int = 560) -> bool:
    try:
        from PySide6.QtCore import QRect

        pixmap = row.grab()
        gx = int(getattr(row, "_drop_guide_x", 0) or (pixmap.width() // 3))
        x = max(0, min(max(0, pixmap.width() - width), gx - 96))
        crop = pixmap.copy(QRect(x, 0, min(width, pixmap.width() - x), pixmap.height()))
        path.parent.mkdir(parents=True, exist_ok=True)
        return bool(crop.save(str(path), "PNG"))
    except Exception:
        return False


def run_preset_drop_guide_capture(
    *,
    out_dir: str | Path = ROOT / "debugCapture" / "ui_renewal_preset_drop_guides",
    language: str = "ko",
) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    from app.actions import build_default_action_registry
    from app.font_fallback import apply_ui_font
    from app.i18n import initialize, set_language
    from app.style import APP_QSS
    from app.video_editor_window import VideoEditorWindow

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
    checks: dict[str, bool] = {}
    artifacts: dict[str, str] = {}
    media_path = _default_media()
    try:
        try:
            editor._autosave_timer.stop()
            editor._do_autosave = lambda *_args, **_kwargs: None
        except Exception:
            pass
        editor.resize(1480, 920)
        editor.show()
        _wait(app, 260)

        registry = build_default_action_registry(editor)
        imported = registry.execute(
            "media.import_to_timeline",
            {
                "path": str(media_path),
                "kind": "video",
                "at_ms": 0,
                "duration_ms": 40000,
                "name": "Drop guide source",
            },
        ).to_dict()
        checks["timeline_imported"] = bool(imported.get("ok", False))
        track_id = int((imported.get("result") or {}).get("track_id") or 0)
        duration_ms = int((imported.get("result") or {}).get("duration_ms") or 40000)
        split_at = min(max(4200, duration_ms // 8 if duration_ms else 8000), 9000)
        split = registry.execute("timeline.split", {"track_id": track_id, "at_ms": split_at}).to_dict()
        checks["timeline_split"] = bool(split.get("ok", False))
        registry.execute("timeline.set_playhead", {"ms": 8000}).to_dict()
        checks["preview_frame_ready"] = bool(_force_viewer_frame(editor, Path(media_path), 8000, out))
        _wait(app, 260)

        row = _first_video_row(editor)
        checks["video_row_found"] = bool(row is not None)
        if row is not None:
            for kind in ("effect", "transition", "title", "workflow"):
                try:
                    row._clear_drop_guide()
                    row._clear_effect_drop_target()
                    row._drop_target_clip_id = None
                    _set_drop_guide(row, kind)
                    _wait(app, 90)
                    png = out / f"timeline_drop_guide_{kind}.png"
                    checks[f"{kind}_guide"] = _save_widget(row, png)
                    artifacts[f"timeline_drop_guide_{kind}"] = str(png.resolve())
                    crop = out / f"timeline_drop_guide_{kind}_crop.png"
                    checks[f"{kind}_guide_crop"] = _save_row_crop(row, crop)
                    artifacts[f"timeline_drop_guide_{kind}_crop"] = str(crop.resolve())
                except Exception:
                    checks[f"{kind}_guide"] = False
                    checks[f"{kind}_guide_crop"] = False
    finally:
        editor.close()
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()

    ok = all(checks.values())
    report = {
        "ok": bool(ok),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "language": active_language,
        "media": str(media_path),
        "checks": checks,
        "artifacts": artifacts,
    }
    report_path = out / "preset_drop_guides_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report"] = str(report_path.resolve())
    return report


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Capture timeline preset drop guide states.")
    parser.add_argument("--out-dir", default=str(ROOT / "debugCapture" / "ui_renewal_preset_drop_guides"))
    parser.add_argument("--language", default="ko")
    args = parser.parse_args()
    report = run_preset_drop_guide_capture(out_dir=args.out_dir, language=args.language)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
