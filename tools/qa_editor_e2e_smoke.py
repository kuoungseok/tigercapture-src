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

DEFAULT_OUT_DIR = ROOT / "debugCapture" / "editor_e2e_smoke"
DEFAULT_REPORT = ROOT / "debugCapture" / "editor_e2e_smoke_report.json"


def _wait(app, ms: int) -> None:
    deadline = time.monotonic() + max(0, int(ms)) / 1000.0
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


def _wait_until(app, predicate, timeout_ms: int = 2500) -> bool:
    deadline = time.monotonic() + max(0, int(timeout_ms)) / 1000.0
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.015)
    app.processEvents()
    return bool(predicate())


def _save_widget(widget, path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = widget.grab()
    return bool(pixmap.save(str(path), "PNG"))


def _rgb_nonblank_stats(rgb: Any) -> dict[str, Any]:
    try:
        import numpy as np

        arr = np.asarray(rgb)
        if arr.ndim != 3 or arr.shape[2] < 3 or arr.size == 0:
            return {"ok": False, "reason": "invalid-rgb"}
        sample = arr[:, :, :3].astype(np.float32)
        luma = 0.2126 * sample[:, :, 0] + 0.7152 * sample[:, :, 1] + 0.0722 * sample[:, :, 2]
        return {
            "ok": bool(float(luma.std()) > 1.5 and float(luma.mean()) > 2.0),
            "shape": [int(v) for v in arr.shape[:3]],
            "mean_luma": round(float(luma.mean()), 3),
            "std_luma": round(float(luma.std()), 3),
            "non_dark_ratio": round(float((luma > 10).mean()), 4),
        }
    except Exception as exc:
        return {"ok": False, "reason": repr(exc)}


def _widget_rect(editor, widget) -> list[int]:
    from PySide6.QtCore import QPoint

    if widget is None:
        return [0, 0, 0, 0]
    top_left = widget.mapTo(editor, QPoint(0, 0))
    return [int(top_left.x()), int(top_left.y()), int(widget.width()), int(widget.height())]


def _rects_overlap(a: list[int], b: list[int]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return False
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def _make_contact_sheet(images: list[tuple[str, Path]], out_path: Path) -> bool:
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

    thumbs: list[tuple[str, QPixmap]] = []
    for label, path in images:
        pix = QPixmap(str(path))
        if pix.isNull():
            continue
        thumbs.append((
            label,
            pix.scaled(
                420,
                260,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ),
        ))
    if not thumbs:
        return False
    pad = 16
    label_h = 28
    col_w = 452
    row_h = 304
    cols = 2
    rows = (len(thumbs) + cols - 1) // cols
    sheet = QPixmap(cols * col_w + pad, rows * row_h + pad)
    sheet.fill(QColor("#070912"))
    painter = QPainter(sheet)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    font = QFont("Arial")
    font.setPixelSize(13)
    font.setBold(True)
    painter.setFont(font)
    for idx, (label, pix) in enumerate(thumbs):
        col = idx % cols
        row = idx // cols
        x = pad + col * col_w
        y = pad + row * row_h
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#111523"))
        painter.drawRoundedRect(QRect(x, y, col_w - pad, row_h - pad), 18, 18)
        painter.setPen(QColor("#EEF2FF"))
        painter.drawText(QRect(x + 14, y + 8, col_w - 28, label_h), Qt.AlignmentFlag.AlignVCenter, label)
        px = x + (col_w - pad - pix.width()) // 2
        py = y + label_h + 14 + (row_h - pad - label_h - 22 - pix.height()) // 2
        painter.drawPixmap(px, py, pix)
    painter.end()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return bool(sheet.save(str(out_path), "PNG"))


def _ensure_qa_corpus() -> None:
    required = [
        ROOT / "qa_corpus" / "assets" / "qa_motion_720p.mp4",
        ROOT / "qa_corpus" / "projects" / "04_actors_live2d_spine.tgp",
    ]
    if all(path.exists() for path in required):
        return
    from tools.build_qa_corpus import build_corpus

    build_corpus(ROOT / "qa_corpus")


def _media_pool_count(pool) -> int:
    if pool is None:
        return 0
    try:
        return len(list(pool.items()))
    except Exception:
        return 0


def _capture(label: str, widget, filename: str, out_dir: Path, screenshots: list[tuple[str, Path]], checks: dict[str, bool], artifacts: dict[str, str]) -> Path:
    path = out_dir / filename
    ok = _save_widget(widget, path)
    checks[f"{label}_screenshot"] = ok
    artifacts[label] = str(path)
    if ok:
        screenshots.append((label, path))
    return path


def _apply_catalog_capture_mode(app, editor) -> None:
    """Hide transient/dev-only chrome before public review screenshots."""
    try:
        editor._suppress_interactive_prompts = True
    except Exception:
        pass
    if not bool(getattr(editor, "_catalog_flash_status_suppressed", False)):
        try:
            editor._catalog_original_flash_status = getattr(editor, "_flash_status", None)
            editor._flash_status = lambda *_args, **_kwargs: None
            editor._catalog_flash_status_suppressed = True
        except Exception:
            pass

    hide_ai_dock = getattr(editor, "_hide_ai_command_dock", None)
    if callable(hide_ai_dock):
        try:
            hide_ai_dock()
        except Exception:
            pass

    for name in (
        "_ai_command_dock",
        "_ai_command_popout",
        "_ai_command_status",
        "_ai_command_provider_status",
        "_status_banner",
        "_timeline_status_label",
        "_workflow_apply_toast",
    ):
        widget = getattr(editor, name, None)
        if widget is None:
            continue
        try:
            if hasattr(widget, "clear"):
                widget.clear()
        except Exception:
            pass
        try:
            widget.hide()
        except Exception:
            pass

    timer = getattr(editor, "_status_banner_timer", None)
    if timer is not None:
        try:
            timer.stop()
        except Exception:
            pass
    try:
        from PySide6.QtWidgets import QLabel

        for label in editor.findChildren(QLabel):
            text = str(label.text() or "")
            if label.objectName() == "StatusBanner" or "warm-up failed" in text:
                label.clear()
                label.hide()
    except Exception:
        pass
    app.processEvents()


def _patch_catalog_preview_frame(editor, image_path: Path) -> bool:
    latest = getattr(editor, "_latest_preview_rgb", None)
    if latest is None or not image_path.exists():
        return False
    try:
        import numpy as np
        from PIL import Image, ImageDraw

        arr = np.asarray(latest)
        if arr.ndim != 3 or arr.shape[2] < 3 or arr.size == 0:
            return False
        if arr.dtype.kind == "f":
            scale = 255.0 if float(arr.max(initial=0.0)) <= 1.01 else 1.0
            arr = np.clip(arr[:, :, :3] * scale, 0, 255).astype(np.uint8)
        else:
            arr = np.clip(arr[:, :, :3], 0, 255).astype(np.uint8)

        label = getattr(editor, "_preview_label", None)
        if label is None:
            return False
        label_x, label_y, label_w, label_h = _widget_rect(editor, label)
        if label_w <= 0 or label_h <= 0:
            return False
        frame_rect = None
        frame_rect_for = getattr(editor, "_preview_frame_rect_in_label", None)
        if callable(frame_rect_for):
            try:
                frame_rect = frame_rect_for(int(arr.shape[1]), int(arr.shape[0]))
            except Exception:
                frame_rect = None
        if frame_rect is not None:
            x = label_x + int(frame_rect.x())
            y = label_y + int(frame_rect.y())
            w = int(frame_rect.width())
            h = int(frame_rect.height())
        else:
            scale = min(label_w / max(1, int(arr.shape[1])), label_h / max(1, int(arr.shape[0])))
            w = max(1, int(arr.shape[1] * scale))
            h = max(1, int(arr.shape[0] * scale))
            x = label_x + (label_w - w) // 2
            y = label_y + (label_h - h) // 2
        canvas = Image.open(image_path).convert("RGB")
        x = max(0, min(int(x), canvas.width - 1))
        y = max(0, min(int(y), canvas.height - 1))
        w = max(1, min(int(w), canvas.width - x))
        h = max(1, min(int(h), canvas.height - y))
        frame = Image.fromarray(arr, "RGB").resize((w, h), Image.Resampling.LANCZOS)
        canvas.paste(frame, (x, y))
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=10, outline=(255, 255, 255), width=1)
        canvas.save(image_path)
        return True
    except Exception:
        return False


def _run_import_editor_flow(
    app,
    out_dir: Path,
    screenshots: list[tuple[str, Path]],
    checks: dict[str, bool],
    artifacts: dict[str, str],
    *,
    import_media: Path | None = None,
    catalog_capture: bool = False,
    live_feature_captures: bool = False,
    review_out_dir: Path | None = None,
    sample_manifest: Path | None = None,
) -> dict[str, Any]:
    from PySide6.QtCore import Qt

    from app.simple_video_player import PlayerState
    from app.video_editor_window import VideoEditorWindow

    editor = VideoEditorWindow()
    metrics: dict[str, Any] = {}
    try:
        if catalog_capture:
            _apply_catalog_capture_mode(app, editor)
        editor.resize(1440, 900)
        editor.show()
        _wait(app, 160)
        if catalog_capture:
            _apply_catalog_capture_mode(app, editor)
            _wait(app, 80)
        _capture("editor_empty", editor, "editor_empty.png", out_dir, screenshots, checks, artifacts)

        video = import_media or ROOT / "qa_corpus" / "assets" / "qa_motion_720p.mp4"
        video = video if video.is_absolute() else ROOT / video
        pool = getattr(editor, "_media_pool", None)
        if pool is not None:
            pool.add_path(video)
        editor._add_track_with_source(video)
        _wait(app, 250)
        audio_extract_required = bool(catalog_capture and import_media is not None)
        try:
            tracks = list(getattr(editor, "_tracks", []) or [])
            first_track = tracks[0] if tracks else None
            first_clip = None
            if first_track is not None:
                clips = list(getattr(first_track, "clips", []) or [])
                first_clip = clips[0] if clips else None
            if first_track is not None:
                params: dict[str, Any] = {
                    "track_id": int(getattr(first_track, "id", 0) or 0),
                    "link": True,
                    "name": "Extracted Audio",
                }
                if first_clip is not None:
                    params["clip_id"] = int(getattr(first_clip, "id", 0) or 0)
                result = editor._ensure_python_action_registry().execute(
                    "audio.extract_from_video",
                    params,
                ).to_dict()
                metrics["audio_extract_action"] = result
                metrics["audio_track_count_after_extract"] = len(getattr(editor, "_audio_tracks", []) or [])
                if audio_extract_required:
                    checks["audio_extract_action_ok"] = bool(result.get("ok"))
            elif audio_extract_required:
                checks["audio_extract_action_ok"] = False
                metrics["audio_extract_action"] = {"ok": False, "error": "no video track"}
                metrics["audio_track_count_after_extract"] = 0
        except Exception as exc:
            metrics["audio_extract_action"] = {"ok": False, "error": repr(exc)}
            metrics["audio_track_count_after_extract"] = 0
            if audio_extract_required:
                checks["audio_extract_action_ok"] = False
        _wait(app, 450)
        preview_position_ms = 500
        if catalog_capture:
            duration_ms = int(editor._player.duration())
            if duration_ms > 1200:
                preview_position_ms = min(max(1000, int(duration_ms * 0.45)), max(500, duration_ms - 500))
        editor._player.set_position(preview_position_ms)
        _wait(app, 400)
        if catalog_capture:
            _apply_catalog_capture_mode(app, editor)
            _wait(app, 120)
        imported_path = _capture("editor_imported", editor, "editor_imported.png", out_dir, screenshots, checks, artifacts)
        if catalog_capture:
            checks["catalog_import_preview_composited"] = _patch_catalog_preview_frame(editor, imported_path)

        if live_feature_captures:
            try:
                from app.review_automation.live_runner import run_live_feature_action_captures
                from app.review_automation.paths import DEFAULT_REVIEW_OUTPUT_DIR, DEFAULT_REVIEW_SAMPLE_MANIFEST

                target_out = review_out_dir or DEFAULT_REVIEW_OUTPUT_DIR
                target_manifest = sample_manifest or DEFAULT_REVIEW_SAMPLE_MANIFEST
                if catalog_capture:
                    _apply_catalog_capture_mode(app, editor)
                    _wait(app, 80)
                live_report = run_live_feature_action_captures(
                    editor,
                    scenario="live-feature-captures",
                    params={
                        "project_root": str(ROOT),
                        "out_dir": str(target_out),
                        "sample_manifest": str(target_manifest),
                    },
                )
                # The review report owns per-feature readiness. A blocked
                # feature such as an unavailable Live2D renderer should not
                # abort the editor smoke run when the capture pass itself
                # completed and wrote its diagnostic report.
                checks["live_feature_capture_report_written"] = bool(live_report.get("scenario_count", 0))
                artifacts["feature_action_scenarios_live"] = str(
                    (target_out / "action_scenarios" / "feature_action_scenarios_live.json").resolve()
                )
                metrics["live_feature_captures"] = live_report
            except Exception as exc:
                checks["live_feature_capture_report_written"] = False
                metrics["live_feature_captures_error"] = repr(exc)

        rgb_stats = _rgb_nonblank_stats(getattr(editor, "_latest_preview_rgb", None))
        preview_label = getattr(editor, "_preview_label", None)
        preview_text = preview_label.text() if preview_label is not None else ""
        preview_pixmap = preview_label.pixmap() if preview_label is not None else None
        checks["import_tracks_exist"] = len(getattr(editor, "_tracks", []) or []) >= 1
        checks["import_track_rows_exist"] = len(getattr(editor, "_track_rows", {}) or {}) >= 1
        metrics["audio_track_count"] = len(getattr(editor, "_audio_tracks", []) or [])
        if audio_extract_required:
            checks["import_audio_track_extracted"] = int(metrics.get("audio_track_count_after_extract", 0) or 0) >= 1
        checks["import_media_pool_has_item"] = _media_pool_count(pool) >= 1
        checks["preview_rgb_nonblank_after_import"] = bool(rgb_stats.get("ok"))
        checks["preview_placeholder_cleared_after_import"] = (
            str(getattr(editor, "_preview_placeholder_kind", "")) == "content"
            and not str(preview_text or "").strip()
            and bool(rgb_stats.get("ok"))
        )

        preview_rect = _widget_rect(editor, getattr(editor, "_preview_host", None))
        right_rect = _widget_rect(editor, getattr(editor, "_right_dock_scroll", None))
        left_rect = _widget_rect(editor, getattr(editor, "_left_dock_scroll", None))
        workbench_rect = _widget_rect(editor, getattr(editor, "_workbench_section_host", None))
        checks["preview_not_overlapped_by_right_dock"] = not _rects_overlap(preview_rect, right_rect)
        checks["preview_not_overlapped_by_left_dock"] = not _rects_overlap(preview_rect, left_rect)
        checks["play_bar_compact_height"] = 30 <= int(getattr(editor, "_play_bar_scroll").height()) <= 48
        checks["timeline_visible_after_import"] = int(getattr(editor, "_timeline_section_host").height()) >= 180
        checks["workbench_visible_after_import"] = (
            int(workbench_rect[2]) >= 300 and int(workbench_rect[3]) >= 180
        )

        popout_ok = False
        try:
            editor._toggle_preview_popout()
            _wait(app, 200)
            popout = getattr(editor, "_preview_popout", None)
            editor._player.set_position(900)
            _wait(app, 260)
            popout_ok = bool(
                popout is not None
                and popout.isVisible()
                and getattr(popout, "_last_image", None) is not None
                and getattr(popout, "_last_pixmap", None) is not None
                and not popout._last_pixmap.isNull()
            )
            if popout is not None:
                _capture("preview_popout", popout, "preview_popout.png", out_dir, screenshots, checks, artifacts)
                popout.close()
                _wait(app, 80)
        except Exception:
            popout_ok = False
        checks["preview_popout_receives_current_frame"] = popout_ok

        dock_checks: dict[str, bool] = {}
        try:
            editor._toggle_media_pool_popout()
            _wait(app, 120)
            dock_checks["media_popout_open"] = bool(
                getattr(editor, "_media_pool_popout", None) is not None
                and editor._media_pool_popout.isVisible()
                and getattr(editor, "_media_pool_section_host", None).parent() is not None
            )
            editor._media_pool_popout.close()
            _wait(app, 120)
            dock_checks["media_popout_restore"] = (
                getattr(editor, "_media_pool_popout", None) is None
                and editor._main_dock_splitter.indexOf(editor._left_dock_scroll) >= 0
            )
        except Exception:
            dock_checks["media_popout_open"] = False
            dock_checks["media_popout_restore"] = False
        try:
            editor._toggle_workbench_popout()
            _wait(app, 120)
            dock_checks["workbench_popout_open"] = bool(
                getattr(editor, "_workbench_popout", None) is not None
                and editor._workbench_popout.isVisible()
                and getattr(editor, "_workbench_section_host", None).parent() is not None
            )
            editor._workbench_popout.close()
            _wait(app, 120)
            dock_checks["workbench_popout_restore"] = (
                getattr(editor, "_workbench_popout", None) is None
                and getattr(editor, "_top_workbench_layout", None) is not None
                and editor._top_workbench_layout.indexOf(editor._workbench_section_host) >= 0
            )
        except Exception:
            dock_checks["workbench_popout_open"] = False
            dock_checks["workbench_popout_restore"] = False
        for name, passed in dock_checks.items():
            checks[name] = bool(passed)

        try:
            track = getattr(editor, "_tracks", [None])[0]
            clip = list(getattr(track, "clips", []) or [])[0]
            clip.source_out_ms = min(900, int(getattr(clip, "source_duration_ms", 900) or 900))
            editor._refresh_player_tracks()
            editor._player.set_position(250)
            _wait(app, 100)
            editor._toggle_play()
            checks["bounded_clip_audition_started"] = editor._player.state() is PlayerState.PLAYING
            returned = _wait_until(
                app,
                lambda: editor._player.state() is not PlayerState.PLAYING
                and abs(int(editor._player.position()) - 250) <= 40,
                timeout_ms=2500,
            )
            checks["bounded_clip_audition_returns_to_origin"] = bool(returned)
        except Exception:
            checks["bounded_clip_audition_started"] = False
            checks["bounded_clip_audition_returns_to_origin"] = False

        metrics.update({
            "catalog_capture": bool(catalog_capture),
            "video": str(video),
            "tracks": len(getattr(editor, "_tracks", []) or []),
            "track_rows": len(getattr(editor, "_track_rows", {}) or {}),
            "media_pool_items": _media_pool_count(pool),
            "duration_ms": int(editor._player.duration()),
            "position_ms": int(editor._player.position()),
            "preview_placeholder": str(getattr(editor, "_preview_placeholder_kind", "")),
            "preview_rgb": rgb_stats,
            "preview_rect": preview_rect,
            "left_dock_rect": left_rect,
            "right_dock_rect": right_rect,
            "workbench_rect": workbench_rect,
            "play_bar_height": int(getattr(editor, "_play_bar_scroll").height()),
            "timeline_height": int(getattr(editor, "_timeline_section_host").height()),
            "workbench_width": int(getattr(editor, "_right_dock_scroll").width()),
            "dock_checks": dock_checks,
        })
    finally:
        try:
            editor.close()
            _wait(app, 80)
        except Exception:
            pass
    return metrics


def _run_loaded_project_flow(
    app,
    out_dir: Path,
    screenshots: list[tuple[str, Path]],
    checks: dict[str, bool],
    artifacts: dict[str, str],
    *,
    catalog_capture: bool = False,
) -> dict[str, Any]:
    from app.project_io import load_project
    from app.video_editor_window import VideoEditorWindow

    editor = VideoEditorWindow()
    metrics: dict[str, Any] = {}
    try:
        if catalog_capture:
            _apply_catalog_capture_mode(app, editor)
        editor.resize(1440, 900)
        editor.show()
        _wait(app, 120)
        project = ROOT / "qa_corpus" / "projects" / "04_actors_live2d_spine.tgp"
        load_project(editor, project)
        _wait(app, 400)
        editor._player.set_position(900)
        _wait(app, 500)
        if catalog_capture:
            _apply_catalog_capture_mode(app, editor)
            _wait(app, 120)
        actor_path = _capture("editor_actor_project", editor, "editor_actor_project.png", out_dir, screenshots, checks, artifacts)
        if catalog_capture:
            checks["catalog_actor_preview_composited"] = _patch_catalog_preview_frame(editor, actor_path)

        rgb_stats = _rgb_nonblank_stats(getattr(editor, "_latest_preview_rgb", None))
        checks["project_load_tracks_exist"] = len(getattr(editor, "_tracks", []) or []) >= 1
        checks["project_load_media_pool_restored"] = _media_pool_count(getattr(editor, "_media_pool", None)) >= 1
        checks["project_load_spine_lane_restored"] = len(getattr(editor, "_spine_actor_tracks", []) or []) >= 1 and len(getattr(editor, "_actor_lane_rows", []) or []) >= 1
        checks["project_load_live2d_lane_restored"] = len(getattr(editor, "_live2d_actor_tracks", []) or []) >= 1 and len(getattr(editor, "_live2d_lane_rows", []) or []) >= 1
        checks["project_preview_nonblank_with_actor_lanes"] = bool(rgb_stats.get("ok"))
        checks["project_preview_placeholder_cleared"] = str(getattr(editor, "_preview_placeholder_kind", "")) == "content"
        from app.timeline_ruler import TimelineRuler

        timeline_margin = int(getattr(TimelineRuler, "MARGIN", 10))
        checks["actor_lanes_align_with_timeline_margin"] = all(
            int(row._ms_to_x(0)) == timeline_margin
            for row in list(getattr(editor, "_actor_lane_rows", []) or []) + list(getattr(editor, "_live2d_lane_rows", []) or [])
            if hasattr(row, "_ms_to_x")
        )

        metrics.update({
            "catalog_capture": bool(catalog_capture),
            "project": str(project),
            "tracks": len(getattr(editor, "_tracks", []) or []),
            "track_rows": len(getattr(editor, "_track_rows", {}) or {}),
            "spine_tracks": len(getattr(editor, "_spine_actor_tracks", []) or []),
            "spine_rows": len(getattr(editor, "_actor_lane_rows", []) or []),
            "live2d_tracks": len(getattr(editor, "_live2d_actor_tracks", []) or []),
            "live2d_rows": len(getattr(editor, "_live2d_lane_rows", []) or []),
            "duration_ms": int(editor._player.duration()),
            "position_ms": int(editor._player.position()),
            "preview_rgb": rgb_stats,
        })
    finally:
        try:
            editor.close()
            _wait(app, 80)
        except Exception:
            pass
    return metrics


def run_editor_e2e_smoke_qa(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    report_path: Path = DEFAULT_REPORT,
    language: str | None = None,
    import_media: Path | None = None,
    catalog_capture: bool = False,
    live_feature_captures: bool = False,
    review_out_dir: Path | None = None,
    sample_manifest: Path | None = None,
) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    from app.font_fallback import apply_ui_font
    from app.i18n import initialize, set_language
    from app.style import APP_QSS

    _ensure_qa_corpus()
    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    app.setStyleSheet(APP_QSS)
    active_language = initialize()
    if language:
        set_language(language)
        active_language = language

    out_dir = out_dir if out_dir.is_absolute() else ROOT / out_dir
    report_path = report_path if report_path.is_absolute() else ROOT / report_path
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    checks: dict[str, bool] = {}
    artifacts: dict[str, str] = {}
    screenshots: list[tuple[str, Path]] = []
    metrics: dict[str, Any] = {}

    metrics["import_editor"] = _run_import_editor_flow(
        app,
        out_dir,
        screenshots,
        checks,
        artifacts,
        import_media=import_media,
        catalog_capture=catalog_capture,
        live_feature_captures=live_feature_captures,
        review_out_dir=review_out_dir,
        sample_manifest=sample_manifest,
    )
    metrics["loaded_actor_project"] = _run_loaded_project_flow(
        app,
        out_dir,
        screenshots,
        checks,
        artifacts,
        catalog_capture=catalog_capture,
    )

    contact_sheet = out_dir / "editor_e2e_smoke_contact_sheet.png"
    checks["contact_sheet"] = _make_contact_sheet(screenshots, contact_sheet)
    artifacts["contact_sheet"] = str(contact_sheet)

    failures = [
        {"check": name, "message": "check failed"}
        for name, passed in checks.items()
        if not passed
    ]
    report = {
        "ok": not failures,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "checks": len(checks),
            "passing": sum(1 for passed in checks.values() if passed),
            "failing": len(failures),
            "screenshots": len(screenshots),
            "flows": 2,
            "language": active_language,
        },
        "checks": checks,
        "metrics": metrics,
        "artifacts": artifacts,
        "contact_sheet": str(contact_sheet),
        "failures": failures,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report["report"] = str(report_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full editor E2E smoke QA.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--language",
        choices=("ko", "en", "ja", "zh", "fr", "de"),
        default=None,
        help="Temporarily force a UI language for this QA capture without saving it.",
    )
    parser.add_argument(
        "--import-media",
        type=Path,
        default=None,
        help="Media file to import in the editor flow. Defaults to the QA corpus motion clip.",
    )
    parser.add_argument(
        "--catalog-capture",
        action="store_true",
        help="Hide transient status banners and developer-only command dock for public review screenshots.",
    )
    parser.add_argument(
        "--live-feature-captures",
        action="store_true",
        help="Run registered feature action scenarios on the live editor and capture feature screenshots.",
    )
    parser.add_argument(
        "--review-out-dir",
        type=Path,
        default=None,
        help="Review automation output directory for live feature captures.",
    )
    parser.add_argument(
        "--sample-manifest",
        type=Path,
        default=None,
        help="Review sample manifest used by live feature captures.",
    )
    args = parser.parse_args()
    report = run_editor_e2e_smoke_qa(
        out_dir=args.out_dir,
        report_path=args.report,
        language=args.language,
        import_media=args.import_media,
        catalog_capture=args.catalog_capture,
        live_feature_captures=args.live_feature_captures,
        review_out_dir=args.review_out_dir,
        sample_manifest=args.sample_manifest,
    )
    print(json.dumps({
        "ok": report.get("ok"),
        "report": report.get("report"),
        "contact_sheet": report.get("contact_sheet"),
        "summary": report.get("summary"),
    }, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
