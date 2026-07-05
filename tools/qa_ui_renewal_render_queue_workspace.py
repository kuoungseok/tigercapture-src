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


def _install_temp_render_queue_store(editor: Any, out: Path) -> bool:
    panel = getattr(editor, "_render_queue_panel", None)
    if panel is None:
        return False
    try:
        from app.render_queue import RenderQueueStore

        panel._store = RenderQueueStore(out / "render_queue_store.json")
        panel._store.replace([])
        panel.refresh_from_store()
        return True
    except Exception:
        return False


def run_render_queue_workspace_capture(
    *,
    media: str | Path | None = None,
    out_dir: str | Path = ROOT / "debugCapture" / "ui_renewal_render_queue_workspace",
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

        checks["temp_render_queue_store"] = _install_temp_render_queue_store(editor, out)

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

        # Keep the export evidence tied to a real edit state, not a blank
        # project: color grade and split produce visible timeline/preview state.
        split_at = min(max(2400, duration_ms // 6 if duration_ms else 2400), 7000)
        split = registry.execute("timeline.split", {"track_id": track_id, "at_ms": split_at}).to_dict()
        steps.append({"action": "timeline.split", **split})
        checks["timeline_split"] = bool(split.get("ok"))

        grade = registry.execute(
            "clip.set_color_grade",
            {
                "track_id": track_id,
                "clip_id": clip_id,
                "grade": {
                    "exposure": 0.08,
                    "contrast": 1.09,
                    "temperature": -0.06,
                    "saturation": 1.05,
                },
                "merge": True,
            },
        ).to_dict()
        steps.append({"action": "clip.set_color_grade", **grade})
        checks["color_grade"] = bool(grade.get("ok"))

        selected = registry.execute(
            "selection.set",
            {"kind": "video", "track_id": track_id, "clip_id": clip_id},
        ).to_dict()
        steps.append({"action": "selection.set", **selected})
        checks["selection"] = bool(selected.get("ok"))

        stem = media_path.stem[:46]
        diagnostics = "\n".join(
            [
                "Professional Readiness: OK | media linked | timeline range set | GPU preview parity tracked",
                "Color Scope QA: OK | grade layer sampled | waveform within delivery range",
                "Audio Delivery QA: OK | target=shortform | LUFS=-14.0/-14.0 | peak=-1.0 dB",
                "Export Parity: OK | preview metadata and render settings aligned",
            ]
        )
        jobs = [
            {
                "label": f"{stem} / catalog master",
                "out_path": str(out / "exports" / f"{media_path.stem}_catalog_master.mp4"),
                "in_ms": 0,
                "out_ms": min(max(4500, split_at), max(duration_ms, 4500)),
                "source_path": str(media_path),
                "format_id": "mp4",
                "quality_id": "high",
                "diagnostics": diagnostics,
            },
            {
                "label": f"{stem} / vertical proof",
                "out_path": str(out / "exports" / f"{media_path.stem}_vertical_proof.webm"),
                "in_ms": max(0, split_at - 600),
                "out_ms": min(max(split_at + 3600, 5200), max(duration_ms, 5200)),
                "source_path": str(media_path),
                "format_id": "webm",
                "quality_id": "draft",
                "diagnostics": diagnostics,
            },
        ]
        staged = registry.execute("render.queue.stage", {"jobs": jobs, "open_panel": True}).to_dict()
        steps.append({"action": "render.queue.stage", **staged})
        checks["render_queue_stage"] = bool(staged.get("ok") and (staged.get("result") or {}).get("added", 0) >= 1)

        focus = registry.execute(
            "ui.focus_surface",
            {"surface": "render", "kind": "video", "track_id": track_id, "clip_id": clip_id},
        ).to_dict()
        steps.append({"action": "ui.focus_surface", **focus})
        checks["focus_render"] = bool(focus.get("ok"))

        seek_ms = min(max(1200, split_at // 2), max(0, duration_ms - 1000)) if duration_ms else 1200
        try:
            editor._player.set_position(seek_ms)
        except Exception:
            pass
        _wait(app, 600)
        checks["viewer_frame_visible"] = _force_viewer_frame(editor, media_path, seek_ms, out)

        panel = getattr(editor, "_render_queue_panel", None)
        store = getattr(panel, "_store", None) if panel is not None else None
        jobs_in_store = list(getattr(store, "jobs", []) or []) if store is not None else []
        checks["queue_has_jobs"] = len(jobs_in_store) >= 1
        table = getattr(panel, "_table", None) if panel is not None else None
        checks["queue_table_has_rows"] = bool(table is not None and table.rowCount() >= 1)
        if table is not None and table.rowCount() > 0:
            table.selectRow(0)
        if panel is not None:
            panel.update()
        _wait(app, 160)

        queue_png = out / "render_queue_panel_action.png"
        editor_png = out / "editor_render_queue_action.png"
        right_png = out / "right_dock_render_queue_action.png"
        right_host = getattr(editor, "_right_dock_host", None) or panel or editor
        checks["queue_screenshot"] = _save_widget(panel or editor, queue_png)
        checks["right_dock_screenshot"] = _save_widget(right_host, right_png)
        checks["editor_screenshot"] = _save_widget(editor, editor_png)
        artifacts["render_queue_panel"] = str(queue_png.resolve())
        artifacts["right_dock_render_queue"] = str(right_png.resolve())
        artifacts["editor_render_queue"] = str(editor_png.resolve())
    finally:
        editor.close()
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()

    ok = all(
        checks.get(key, False)
        for key in (
            "temp_render_queue_store",
            "media_imported",
            "timeline_split",
            "color_grade",
            "selection",
            "render_queue_stage",
            "focus_render",
            "viewer_frame_visible",
            "queue_has_jobs",
            "queue_table_has_rows",
            "queue_screenshot",
            "right_dock_screenshot",
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
    report_path = out / "render_queue_workspace_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report"] = str(report_path.resolve())
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture renewed render queue workspace with real editor actions.")
    parser.add_argument("--media", default="")
    parser.add_argument("--out-dir", default=str(ROOT / "debugCapture" / "ui_renewal_render_queue_workspace"))
    parser.add_argument("--language", default="ko")
    args = parser.parse_args()
    report = run_render_queue_workspace_capture(
        media=args.media or None,
        out_dir=args.out_dir,
        language=args.language,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
