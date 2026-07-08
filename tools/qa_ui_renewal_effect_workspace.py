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


def _image_nonblank(path: Path) -> bool:
    try:
        from PySide6.QtGui import QImage

        image = QImage(str(path)).convertToFormat(QImage.Format.Format_RGB888)
        if image.isNull():
            return False
        import numpy as np

        width = image.width()
        height = image.height()
        bytes_per_line = image.bytesPerLine()
        data = bytes(image.constBits())
        arr = np.frombuffer(data, dtype=np.uint8).reshape((height, bytes_per_line))[:, : width * 3]
        rgb = arr.reshape((height, width, 3))
        return float(rgb.std()) > 2.0 and float(rgb.mean()) > 3.0
    except Exception:
        return False


def _make_contact_sheet(images: list[tuple[str, Path]], out_path: Path) -> bool:
    try:
        from PySide6.QtCore import QRect, Qt
        from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

        thumbs: list[tuple[str, QPixmap]] = []
        for label, path in images:
            pix = QPixmap(str(path))
            if not pix.isNull():
                thumbs.append((label, pix))
        if not thumbs:
            return False

        cols = 2
        rows = (len(thumbs) + cols - 1) // cols
        cell_w = 560
        cell_h = 350
        pad = 24
        title_h = 34
        sheet = QPixmap(cols * cell_w + pad * 2, rows * cell_h + pad * 2)
        sheet.fill(QColor("#101112"))
        painter = QPainter(sheet)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        title_font = QFont("Segoe UI Variable", 10)
        title_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(title_font)
        for index, (label, pix) in enumerate(thumbs):
            col = index % cols
            row = index // cols
            x = pad + col * cell_w
            y = pad + row * cell_h
            painter.setPen(QColor("#C8CDD8"))
            painter.drawText(QRect(x, y, cell_w, title_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            target = pix.scaled(
                cell_w,
                cell_h - title_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            image_x = x + (cell_w - target.width()) // 2
            image_y = y + title_h + (cell_h - title_h - target.height()) // 2
            painter.drawPixmap(image_x, image_y, target)
        painter.end()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        return bool(sheet.save(str(out_path), "PNG"))
    except Exception:
        return False


def run_effect_workspace_capture(
    *,
    media: str | Path | None = None,
    out_dir: str | Path = ROOT / "debugCapture" / "ui_renewal_effect_workspace",
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
        _wait(app, 320)

        edit_clip_id = clip_id
        effect_window_end_ms = duration_ms
        if track_id and clip_id and duration_ms > 9000:
            split_at = min(7000, max(1200, duration_ms // 5))
            split = registry.execute(
                "timeline.split",
                {"track_id": track_id, "at_ms": split_at},
            ).to_dict()
            steps.append({"action": "timeline.split", **split})
            edit_clip_id = int((split.get("result") or {}).get("left_clip_id") or clip_id)
            effect_window_end_ms = int(split_at)
            checks["timeline_split"] = bool(split.get("ok"))

        effect = registry.execute(
            "clip.set_filter",
            {
                "track_id": track_id,
                "clip_id": edit_clip_id,
                "params": {
                    "enabled": True,
                    "sharpen": 0.28,
                    "vignette": 0.16,
                    "vignette_feather": 0.62,
                    "chroma_aberration": 0.03,
                },
                "merge": True,
            },
        ).to_dict()
        steps.append({"action": "clip.set_filter", **effect})
        checks["clip_filter"] = bool(effect.get("ok"))

        transition = registry.execute(
            "transition.apply",
            {
                "track_id": track_id,
                "clip_id": edit_clip_id,
                "transition_type": "dissolve",
                "duration_ms": 480,
            },
        ).to_dict()
        steps.append({"action": "transition.apply", **transition})
        checks["transition"] = bool(transition.get("ok"))

        graph_payload = {
            "nodes": [
                {
                    "id": "FX1",
                    "kind": "serial",
                    "label": "Video FX",
                    "x": -140.0,
                    "y": -22.0,
                    "user_color": "#8A8371",
                },
                {
                    "id": "TR1",
                    "kind": "serial",
                    "label": "Dissolve TR",
                    "x": 78.0,
                    "y": -22.0,
                    "user_color": "#8F7F5F",
                },
            ],
            "connections": [
                {"src_node": "IN", "src_port": "rgb_out", "dst_node": "FX1", "dst_port": "rgb_in"},
                {"src_node": "FX1", "src_port": "rgb_out", "dst_node": "TR1", "dst_port": "rgb_in"},
                {"src_node": "TR1", "src_port": "rgb_out", "dst_node": "OUT", "dst_port": "rgb_in"},
            ],
            "next_id": 3,
            "io_positions": {"IN": [-300.0, -18.0], "OUT": [300.0, -18.0]},
        }
        graph = registry.execute(
            "node.graph.set",
            {"track_id": track_id, "graph": graph_payload},
        ).to_dict()
        steps.append({"action": "node.graph.set", **graph})
        checks["node_graph"] = bool(graph.get("ok") and (graph.get("result") or {}).get("node_count", 0) >= 2)

        compare = registry.execute(
            "ui.viewer.compare.set",
            {"track_id": track_id, "mode": "split", "labels_enabled": True},
        ).to_dict()
        steps.append({"action": "ui.viewer.compare.set", **compare})
        checks["viewer_compare_split"] = bool(
            compare.get("ok") and str((compare.get("result") or {}).get("mode") or "").lower() == "split"
        )

        selected = registry.execute(
            "selection.set",
            {"kind": "video", "track_id": track_id, "clip_id": edit_clip_id},
        ).to_dict()
        steps.append({"action": "selection.set", **selected})
        checks["selection"] = bool(selected.get("ok"))
        _wait(app, 360)

        # Capture inside the clip that actually owns the applied filter and
        # transition. If the playhead is outside that first split clip, the
        # Viewer can legitimately show a different unfiltered clip or an
        # offscreen/decoder placeholder.
        seek_ms = 1400
        if effect_window_end_ms > 0:
            seek_ms = min(max(900, effect_window_end_ms // 2), max(0, effect_window_end_ms - 900))
        try:
            editor._player.set_position(seek_ms)
        except Exception:
            pass
        _wait(app, 700)
        checks["viewer_frame_visible"] = _force_viewer_frame(editor, media_path, seek_ms, out)

        if hasattr(editor, "_refresh_workbench"):
            editor._refresh_workbench()
        panel = getattr(editor, "_workbench_panel", None)
        if panel is not None and hasattr(panel, "_set_inspector_tab"):
            panel._set_inspector_tab("fx")
        try:
            graph_widget = panel.expose_node_graph_widget() if panel is not None else None
            if graph_widget is not None:
                graph_widget.fit_all()
        except Exception:
            pass
        _wait(app, 220)

        workbench_widget = getattr(editor, "_workbench_section_host", None) or panel or editor
        fx_host = getattr(panel, "_fx_summary_host", None) if panel is not None else None
        tab_stack = getattr(panel, "_tab_stack", None) if panel is not None else None
        tab_pages = getattr(panel, "_tab_pages", {}) if panel is not None else {}
        checks["fx_summary_visible"] = bool(fx_host is not None and fx_host.isVisible())
        checks["fx_tab_active"] = bool(
            tab_stack is not None
            and isinstance(tab_pages, dict)
            and tab_stack.currentWidget() is tab_pages.get("fx")
        )
        checks["viewer_frame_visible_final"] = _force_viewer_frame(editor, media_path, seek_ms, out)
        _wait(app, 80)

        workbench_png = out / "workbench_effect_stack_action.png"
        timeline_png = out / "timeline_effect_stack_action.png"
        editor_png = out / "editor_effect_stack_action.png"
        contact_png = out / "effect_workspace_contact_sheet.png"
        timeline_host = getattr(editor, "_timeline_section_host", None) or editor
        checks["workbench_screenshot"] = _save_widget(workbench_widget, workbench_png)
        checks["timeline_screenshot"] = _save_widget(timeline_host, timeline_png)
        checks["editor_screenshot"] = _save_widget(editor, editor_png)
        checks["workbench_screenshot_nonblank"] = _image_nonblank(workbench_png)
        checks["timeline_screenshot_nonblank"] = _image_nonblank(timeline_png)
        checks["editor_screenshot_nonblank"] = _image_nonblank(editor_png)
        checks["contact_sheet"] = _make_contact_sheet(
            [
                ("Full editor: real media, FX/TR selected", editor_png),
                ("Workbench: node graph and applied stack", workbench_png),
                ("Timeline: split clip, FX/TR badges, transition edge", timeline_png),
            ],
            contact_png,
        )
        checks["contact_sheet_nonblank"] = _image_nonblank(contact_png)
        artifacts["workbench_effect"] = str(workbench_png.resolve())
        artifacts["timeline_effect"] = str(timeline_png.resolve())
        artifacts["editor_effect"] = str(editor_png.resolve())
        artifacts["contact_sheet"] = str(contact_png.resolve())
    finally:
        editor.close()
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()

    ok = all(
        checks.get(key, False)
        for key in (
            "media_imported",
            "clip_filter",
            "transition",
            "node_graph",
            "selection",
            "viewer_frame_visible",
            "viewer_frame_visible_final",
            "fx_summary_visible",
            "fx_tab_active",
            "workbench_screenshot",
            "timeline_screenshot",
            "editor_screenshot",
            "workbench_screenshot_nonblank",
            "timeline_screenshot_nonblank",
            "editor_screenshot_nonblank",
            "contact_sheet",
            "contact_sheet_nonblank",
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
    report_path = out / "effect_workspace_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report"] = str(report_path.resolve())
    return report


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Capture the renewed effect workspace with real editor actions.")
    parser.add_argument("--media", default="")
    parser.add_argument("--out-dir", default=str(ROOT / "debugCapture" / "ui_renewal_effect_workspace"))
    parser.add_argument("--language", default="ko")
    args = parser.parse_args()
    report = run_effect_workspace_capture(
        media=args.media or None,
        out_dir=args.out_dir,
        language=args.language,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
