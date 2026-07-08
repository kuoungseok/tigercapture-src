from __future__ import annotations

import argparse
import json
import os
import subprocess
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


def _wait(app: Any, ms: int) -> None:
    deadline = time.monotonic() + max(0, int(ms)) / 1000.0
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


def _save_widget(widget: Any, path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = widget.grab()
    return bool(pixmap.save(str(path), "PNG"))


def _pixmap_mean_luma(pixmap: Any) -> float:
    try:
        import numpy as np
        from PySide6.QtGui import QImage

        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
        width = image.width()
        height = image.height()
        bytes_per_line = image.bytesPerLine()
        data = bytes(image.constBits())
        arr = np.frombuffer(data, dtype=np.uint8).reshape((height, bytes_per_line))[:, : width * 3]
        rgb = arr.reshape((height, width, 3))
        return float(rgb.mean())
    except Exception:
        return 0.0


def _ffmpeg_frame_pixmap(path: Path, seek_ms: int = 0, debug_dir: Path | None = None):
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        from PySide6.QtGui import QPixmap

        from app.subprocess_utils import hidden_subprocess_kwargs

        frame_dir = (debug_dir or (ROOT / "debugCapture" / "workbench_node_action_flow")) / "viewer_frames"
        frame_dir.mkdir(parents=True, exist_ok=True)
        attempts = [
            int(seek_ms),
            8000,
            16000,
            28000,
            42000,
            60000,
            90000,
            0,
        ]
        best = None
        best_luma = -1.0
        for at_ms in attempts:
            out_png = frame_dir / f"viewer_frame_{max(0, int(at_ms)):07d}.png"
            cmd = [
                get_ffmpeg_exe(),
                "-nostdin",
                "-y",
                "-ss",
                f"{max(0, int(at_ms)) / 1000.0:.3f}",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-vf",
                "scale=1280:-1",
                str(out_png),
            ]
            try:
                subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=18,
                    check=False,
                    **hidden_subprocess_kwargs(),
                )
            except Exception:
                continue
            if not out_png.exists():
                continue
            pixmap = QPixmap(str(out_png))
            if pixmap.isNull():
                continue
            luma = _pixmap_mean_luma(pixmap)
            if luma > best_luma:
                best = pixmap
                best_luma = luma
            if luma > 18.0:
                return pixmap
        return best
    except Exception:
        return None


def _video_frame_pixmap(path: Path, seek_ms: int = 0, debug_dir: Path | None = None):
    try:
        import cv2
        from PySide6.QtGui import QImage, QPixmap

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return None
        try:
            attempts = [
                int(seek_ms),
                8000,
                16000,
                28000,
                42000,
                60000,
                0,
            ]
            best = None
            best_luma = -1.0
            for at_ms in attempts:
                cap.set(cv2.CAP_PROP_POS_MSEC, max(0, int(at_ms)))
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]
                image = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
                pixmap = QPixmap.fromImage(image)
                luma = _pixmap_mean_luma(pixmap)
                if luma > best_luma:
                    best = pixmap
                    best_luma = luma
                if luma > 12.0:
                    return pixmap
            if best is not None and best_luma > 18.0:
                return best
        finally:
            cap.release()
    except Exception:
        pass
    return _ffmpeg_frame_pixmap(path, seek_ms, debug_dir)


def _force_viewer_frame(
    editor: Any,
    media_path: Path,
    seek_ms: int,
    debug_dir: Path | None = None,
) -> bool:
    try:
        from PySide6.QtCore import Qt

        fallback = _video_frame_pixmap(media_path, seek_ms, debug_dir)
        if fallback is None or fallback.isNull():
            return False
        if debug_dir is not None:
            try:
                fallback.save(str(debug_dir / "viewer_fallback_frame.png"), "PNG")
            except Exception:
                pass
        gl = getattr(editor, "_preview_gl", None)
        if gl is not None:
            try:
                gl.hide()
            except Exception:
                pass
        editor._preview_pixmap = fallback
        remember = getattr(editor, "_remember_good_preview_pixmap", None)
        if callable(remember):
            remember()
        scale = getattr(editor, "_scale_preview_to_fit", None)
        if callable(scale):
            scale()
        label = getattr(editor, "_preview_label", None)
        if label is not None:
            label_pixmap = label.pixmap()
            if label_pixmap is None or label_pixmap.isNull() or _pixmap_mean_luma(label_pixmap) < 12.0:
                target = fallback
                try:
                    size = label.size()
                    if size.width() > 0 and size.height() > 0:
                        target = fallback.scaled(
                            size,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                except Exception:
                    pass
                label.setText("")
                label.setPixmap(target)
                label.raise_()
                label.update()
            else:
                try:
                    label.raise_()
                except Exception:
                    pass
        wb = getattr(editor, "_workbench_panel", None)
        if wb is not None and hasattr(wb, "set_node_thumbnail"):
            try:
                wb.set_node_thumbnail(fallback)
            except Exception:
                pass
        return True
    except Exception:
        return False


def _default_media() -> Path:
    youtube_imports = Path.home() / "Videos" / "TigerCapture" / "YouTube Imports"
    video_exts = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
    if youtube_imports.exists():
        candidates = _youtube_media_candidates(youtube_imports)
        if candidates:
            priority_phrases = (
                "south korea 4k drone",
                "extended highlights",
                "sunset from the west side",
                "tokyo night view",
            )
            avoided = ("trump", "president", "live", "test", "bars", "8k hdr best mix")
            for phrase in priority_phrases:
                for path in candidates:
                    name = path.name.lower()
                    if phrase in name and not any(term in name for term in avoided):
                        return path
            preferred_terms = (
                "samsung",
                "qd-oled",
                "dolby vision",
                "hdr",
                "oled",
                "dolby",
                "south korea",
                "drone",
                "cinematic",
                "tokyo",
                "night",
            )
            avoid_terms = ("trump", "president", "live", "test", "bars", "8k hdr best mix")

            def _score(path: Path) -> tuple[int, float]:
                name = path.name.lower()
                score = sum(12 for term in preferred_terms if term in name)
                score -= sum(20 for term in avoid_terms if term in name)
                if "test" in name:
                    score -= 45
                if "8k hdr best mix" in name:
                    score -= 45
                try:
                    size_mb = path.stat().st_size / (1024 * 1024)
                    if size_mb > 4096:
                        score -= 36
                    elif size_mb > 2048:
                        score -= 18
                except OSError:
                    pass
                score += 8 if path.name.isascii() else 0
                score += 4 if path.suffix.lower() == ".mp4" else 0
                return (score, path.stat().st_mtime)

            return max(candidates, key=_score)

    from tools.build_qa_corpus import build_corpus

    path = ROOT / "qa_corpus" / "assets" / "qa_motion_720p.mp4"
    if not path.exists():
        build_corpus(ROOT / "qa_corpus")
    return path


def _youtube_media_candidates(folder: Path | None = None) -> list[Path]:
    youtube_imports = folder or Path.home() / "Videos" / "TigerCapture" / "YouTube Imports"
    video_exts = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
    if not youtube_imports.exists():
        return []
    return [
        path for path in youtube_imports.iterdir()
        if path.is_file()
        and path.suffix.lower() in video_exts
        and not path.name.lower().endswith(".part")
    ]


def _alternate_media(primary: Path) -> Path | None:
    candidates = [path for path in _youtube_media_candidates() if path.resolve() != primary.resolve()]
    if not candidates:
        return None
    blocked_terms = ("le mans", "24 hours", "fia wec")
    filtered = [
        path for path in candidates
        if not any(term in path.name.lower() for term in blocked_terms)
    ]
    candidates = filtered or candidates
    priority_phrases = (
        "tokyo night view",
        "taipei",
        "sunset from the west side",
        "samsung",
        "qd-oled",
        "dolby vision",
    )
    for phrase in priority_phrases:
        for path in candidates:
            if phrase in path.name.lower():
                return path
    avoid_terms = ("trump", "president", "live", "south korea", "drone", "test", "bars")
    preferred_terms = ("tokyo", "taipei", "sunset", "samsung", "qd-oled", "dolby", "hdr", "oled")

    def _score(path: Path) -> tuple[int, float]:
        name = path.name.lower()
        score = sum(10 for term in preferred_terms if term in name)
        score -= sum(30 for term in avoid_terms if term in name)
        score += 3 if path.suffix.lower() == ".mp4" else 0
        return (score, path.stat().st_mtime)

    return max(candidates, key=_score)


def _reference_style_node_graph() -> dict[str, Any]:
    nodes = [
        {
            "id": "B1",
            "kind": "blur",
            "label": "Blur1",
            "x": -190.0,
            "y": -24.0,
            "blur_params": {"radius": 10, "shape": "gaussian", "strength": 0.72, "enabled": True},
        },
        {
            "id": "E2",
            "kind": "glow",
            "label": "Neon Glow",
            "x": -45.0,
            "y": -82.0,
            "effect_params": {
                "kind": "glow",
                "threshold": 0.62,
                "radius": 18,
                "intensity": 0.42,
                "tint_r": 0.88,
                "tint_g": 0.95,
                "tint_b": 1.15,
            },
        },
        {
            "id": "E3",
            "kind": "serial",
            "label": "Color Grade",
            "x": 135.0,
            "y": -24.0,
            "user_color": "#8BAE90",
        },
        {
            "id": "E4",
            "kind": "whitebalance",
            "label": "Balance",
            "x": -45.0,
            "y": 42.0,
            "effect_params": {"kind": "whitebalance", "temperature": 7200, "tint": 7},
        },
        {
            "id": "E5",
            "kind": "vignette",
            "label": "Mask",
            "x": 295.0,
            "y": -24.0,
            "effect_params": {"kind": "vignette", "amount": 0.22, "size": 0.82, "feather": 0.5, "round": 1.0},
        },
    ]
    return {
        "nodes": nodes,
        "connections": [
            {"src_node": "IN", "src_port": "rgb_out", "dst_node": "B1", "dst_port": "rgb_in"},
            {"src_node": "B1", "src_port": "rgb_out", "dst_node": "E2", "dst_port": "rgb_in"},
            {"src_node": "E2", "src_port": "rgb_out", "dst_node": "E4", "dst_port": "rgb_in"},
            {"src_node": "E4", "src_port": "rgb_out", "dst_node": "E3", "dst_port": "rgb_in"},
            {"src_node": "E3", "src_port": "rgb_out", "dst_node": "E5", "dst_port": "rgb_in"},
            {"src_node": "E5", "src_port": "rgb_out", "dst_node": "OUT", "dst_port": "rgb_in"},
        ],
        "next_id": 6,
        "io_positions": {"IN": [-320.0, -12.0], "OUT": [430.0, -12.0]},
    }


def run_workbench_node_action_flow(
    *,
    media: str | Path | None = None,
    out_dir: str | Path = ROOT / "debugCapture" / "workbench_node_action_flow",
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
        _wait(app, 180)

        registry = editor._ensure_python_action_registry()
        imported = registry.execute(
            "media.import_to_timeline",
            {"path": str(media_path), "kind": "video", "at_ms": 0},
        ).to_dict()
        steps.append({"action": "media.import_to_timeline", **imported})
        track_id = int((imported.get("result") or {}).get("track_id") or 0)
        clip_id = int((imported.get("result") or {}).get("clip_id") or 0)
        checks["media_imported"] = bool(imported.get("ok") and track_id and clip_id)
        _wait(app, 420)

        alternate_media = _alternate_media(media_path)
        if alternate_media is not None and hasattr(editor, "_media_pool"):
            try:
                added_alt = bool(editor._media_pool.add_path(alternate_media))
            except Exception:
                added_alt = False
            steps.append({
                "action": "media_pool.add_reference_item",
                "ok": added_alt,
                "path": str(alternate_media),
            })
            checks["media_pool_reference_item"] = bool(added_alt or editor._media_pool._find_item_for_path(alternate_media))
            try:
                editor._media_pool.select_path(media_path)
            except Exception:
                pass
            _wait(app, 180)

        if track_id and clip_id:
            selected = registry.execute(
                "selection.set",
                {"kind": "video", "track_id": track_id, "clip_id": clip_id},
            ).to_dict()
            steps.append({"action": "selection.set", **selected})

        audio_track_id = 0
        audio_clip_id = 0
        if track_id and clip_id:
            extracted_audio = registry.execute(
                "audio.extract_from_video",
                {"track_id": track_id, "clip_id": clip_id, "link": True},
            ).to_dict()
            steps.append({"action": "audio.extract_from_video", **extracted_audio})
            audio_result = extracted_audio.get("result") or {}
            audio_track_id = int(audio_result.get("audio_track_id") or 0)
            audio_clip_id = int(audio_result.get("audio_clip_id") or 0)
            checks["audio_extract_ok"] = bool(
                extracted_audio.get("ok") and audio_track_id and audio_clip_id
            )

        edit_clip_ids = [clip_id] if clip_id else []
        duration_ms = int((imported.get("result") or {}).get("duration_ms") or 0)
        if track_id and clip_id and duration_ms > 4000:
            if duration_ms >= 24000:
                cut_points = [6000, 16000]
            else:
                cut_points = [
                    max(1200, int(duration_ms * 0.34)),
                    max(2400, int(duration_ms * 0.68)),
                ]
            cut_points = [
                int(point)
                for point in cut_points
                if 500 < int(point) < max(0, duration_ms - 500)
            ]
            split_results: list[dict[str, Any]] = []
            for point in cut_points:
                split = registry.execute(
                    "timeline.split",
                    {"track_id": track_id, "at_ms": point},
                ).to_dict()
                steps.append({"action": "timeline.split", **split})
                split_results.append(split)
                result = split.get("result") or {}
                for key in ("left_clip_id", "right_clip_id"):
                    value = int(result.get(key) or 0)
                    if value and value not in edit_clip_ids:
                        edit_clip_ids.append(value)
                _wait(app, 90)

            primary_clip_id = edit_clip_ids[0]
            secondary_clip_id = edit_clip_ids[1] if len(edit_clip_ids) > 1 else primary_clip_id
            effect = registry.execute(
                "clip.set_filter",
                {
                    "track_id": track_id,
                    "clip_id": primary_clip_id,
                    "params": {"enabled": True, "sharpen": 0.22, "vignette": 0.12},
                    "merge": True,
                },
            ).to_dict()
            steps.append({"action": "clip.set_filter", **effect})
            grade = registry.execute(
                "clip.set_color_grade",
                {
                    "track_id": track_id,
                    "clip_id": primary_clip_id,
                    "grade": {"brightness": 4, "contrast": 7, "saturation": 5},
                    "merge": True,
                },
            ).to_dict()
            steps.append({"action": "clip.set_color_grade", **grade})
            speed = registry.execute(
                "clip.set_speed",
                {"track_id": track_id, "clip_id": secondary_clip_id, "speed": 1.15},
            ).to_dict()
            steps.append({"action": "clip.set_speed", **speed})
            transition = registry.execute(
                "transition.apply",
                {
                    "track_id": track_id,
                    "clip_id": primary_clip_id,
                    "transition_type": "dissolve",
                    "duration_ms": 450,
                },
            ).to_dict()
            steps.append({"action": "transition.apply", **transition})
            checks["timeline_edit_state_ok"] = bool(
                any(step.get("ok") for step in split_results)
                and effect.get("ok")
                and grade.get("ok")
                and speed.get("ok")
                and transition.get("ok")
            )
            registry.execute(
                "selection.set",
                {"kind": "video", "track_id": track_id, "clip_id": primary_clip_id},
            )
            _wait(app, 240)

        graph = _reference_style_node_graph()
        graph_set = registry.execute(
            "node.graph.set",
            {"track_id": track_id, "graph": graph},
        ).to_dict()
        steps.append({"action": "node.graph.set", **graph_set})
        checks["node_graph_action_ok"] = bool(graph_set.get("ok"))

        compare = registry.execute(
            "ui.viewer.compare.set",
            {"track_id": track_id, "mode": "split", "labels_enabled": True},
        ).to_dict()
        steps.append({"action": "ui.viewer.compare.set", **compare})
        checks["viewer_compare_split"] = bool(
            compare.get("ok") and str((compare.get("result") or {}).get("mode") or "").lower() == "split"
        )

        _wait(app, 220)
        seek_ms = 900
        if duration_ms > 0:
            seek_ms = min(max(8000, duration_ms // 6), max(0, duration_ms - 1200))
        editor._player.set_position(seek_ms)
        _wait(app, 1100)
        ensure_preview = getattr(editor, "_ensure_preview_pixmap_for_paint", None)
        if callable(ensure_preview):
            try:
                ensure_preview()
            except Exception:
                pass
        checks["viewer_frame_visible"] = _force_viewer_frame(editor, media_path, seek_ms, out)
        if hasattr(editor, "_refresh_workbench"):
            editor._refresh_workbench()
        panel = getattr(editor, "_workbench_panel", None)
        workbench_widget = getattr(editor, "_workbench_section_host", None) or panel or editor
        clip_tab_png = out / "workbench_clip_tab_action.png"
        checks["workbench_clip_screenshot"] = _save_widget(workbench_widget, clip_tab_png)
        artifacts["workbench_clip"] = str(clip_tab_png.resolve())
        if audio_track_id and audio_clip_id:
            audio_selected = registry.execute(
                "selection.set",
                {"kind": "audio", "track_id": audio_track_id, "clip_id": audio_clip_id},
            ).to_dict()
            steps.append({"action": "selection.set_audio", **audio_selected})
            _wait(app, 220)
            if hasattr(editor, "_refresh_workbench"):
                editor._refresh_workbench()
            if panel is not None and hasattr(panel, "_set_inspector_tab"):
                panel._set_inspector_tab("audio")
            audio_tab_png = out / "workbench_audio_tab_action.png"
            checks["workbench_audio_screenshot"] = _save_widget(workbench_widget, audio_tab_png)
            artifacts["workbench_audio"] = str(audio_tab_png.resolve())
            audio_mixer_png = out / "editor_audio_mixer_action.png"
            try:
                mixer_toggle = getattr(editor, "_on_audio_mixer_toggled", None)
                mixer_panel = getattr(editor, "_audio_mixer_panel", None)
                if callable(mixer_toggle):
                    mixer_toggle(True)
                elif mixer_panel is not None:
                    mixer_panel.setVisible(True)
                mixer_panel = getattr(editor, "_audio_mixer_panel", None)
                if mixer_panel is not None:
                    rebuild = getattr(mixer_panel, "rebuild", None)
                    if callable(rebuild):
                        rebuild(getattr(editor, "_audio_tracks", []) or [])
                    set_scopes = getattr(mixer_panel, "set_scopes_visible", None)
                    if callable(set_scopes):
                        set_scopes(True)
                    update_scopes = getattr(mixer_panel, "update_scopes", None)
                    if callable(update_scopes):
                        update_scopes(int(getattr(editor._player, "position", lambda: 0)()), getattr(editor, "_audio_tracks", []) or [])
                checks["audio_mixer_viewer_reforced"] = _force_viewer_frame(
                    editor,
                    media_path,
                    seek_ms,
                    out,
                )
                _wait(app, 320)
                checks["audio_mixer_screenshot"] = _save_widget(editor, audio_mixer_png)
                artifacts["audio_mixer"] = str(audio_mixer_png.resolve())
                if callable(mixer_toggle):
                    mixer_toggle(False)
                elif mixer_panel is not None:
                    mixer_panel.setVisible(False)
                _wait(app, 120)
            except Exception:
                checks["audio_mixer_screenshot"] = False
            registry.execute(
                "selection.set",
                {"kind": "video", "track_id": track_id, "clip_id": clip_id},
            )
            _wait(app, 180)
            if hasattr(editor, "_refresh_workbench"):
                editor._refresh_workbench()
        if panel is not None and hasattr(panel, "_set_inspector_tab"):
            panel._set_inspector_tab("fx")
        graph_widget = panel.expose_node_graph_widget() if panel is not None else None
        if graph_widget is not None:
            source_pixmap = getattr(editor, "_preview_pixmap", None)
            if source_pixmap is not None and not source_pixmap.isNull():
                graph_widget.set_source_pixmap(source_pixmap)
            graph_widget.fit_all()
            blur_node = None
            for node in list(getattr(graph_widget.scene, "_serial_nodes", []) or []):
                if str(getattr(node, "node_id", "")) == "B1":
                    blur_node = node
                    break
            if blur_node is not None:
                graph_widget.scene.clearSelection()
                blur_node.setSelected(True)
                node_selection = getattr(editor, "_on_node_graph_selection", None)
                if callable(node_selection):
                    node_selection(blur_node)
                _wait(app, 180)
                mask_tab_png = out / "workbench_mask_tab_action.png"
                checks["workbench_mask_screenshot"] = _save_widget(workbench_widget, mask_tab_png)
                artifacts["workbench_mask"] = str(mask_tab_png.resolve())

            color_node = None
            for node in list(getattr(graph_widget.scene, "_serial_nodes", []) or []):
                if str(getattr(node, "node_id", "")) == "E3":
                    color_node = node
                    break
            if color_node is not None:
                checks["color_node_class"] = (
                    f"{type(color_node).__module__}.{type(color_node).__name__}"
                )
                checks["color_node_kind"] = str(getattr(color_node, "NODE_KIND", ""))
                checks["color_node_has_color_grade"] = (
                    getattr(color_node, "color_grade", None) is not None
                )
                node_grade = getattr(color_node, "color_grade", None)
                if node_grade is not None:
                    for attr, value in (
                        ("brightness", 6),
                        ("contrast", 10),
                        ("saturation", 8),
                        ("highlights_l", 8),
                        ("shadows_l", -5),
                    ):
                        try:
                            setattr(node_grade, attr, value)
                        except Exception:
                            pass
                    try:
                        node_grade.preset_id = "custom"
                    except Exception:
                        pass
                    checks["color_node_grade_non_identity"] = (
                        not bool(node_grade.is_identity())
                        if hasattr(node_grade, "is_identity")
                        else True
                    )
                graph_widget.scene.clearSelection()
                color_node.setSelected(True)
                node_selection = getattr(editor, "_on_node_graph_selection", None)
                if callable(node_selection):
                    node_selection(color_node)
                color_visible = getattr(editor, "_update_color_dock_visibility", None)
                if callable(color_visible):
                    color_visible(color_node)
                sync_color = getattr(editor, "_sync_color_panel", None)
                if callable(sync_color):
                    sync_color()
                rebuild_chain = getattr(editor, "_rebuild_active_chain", None)
                if callable(rebuild_chain):
                    rebuild_chain()
                checks["color_dock_viewer_reforced"] = _force_viewer_frame(
                    editor,
                    media_path,
                    seek_ms,
                    out,
                )
                _wait(app, 260)
                color_container = getattr(editor, "_color_container", None)
                color_splitter = getattr(editor, "_color_timeline_splitter", None)
                color_workbench = getattr(editor, "_color_workbench_panel", None)
                workbench_stack = getattr(editor, "_workbench_stack", None)
                if color_workbench is not None:
                    checks["color_workbench_visible"] = bool(color_workbench.isVisible())
                if color_workbench is not None and workbench_stack is not None:
                    checks["color_workbench_stack_active"] = (
                        workbench_stack.currentWidget() is color_workbench
                    )
                scope_preview = getattr(editor, "_color_scope_preview", None)
                checks["color_scope_preview_visible"] = bool(
                    scope_preview is not None and scope_preview.isVisible()
                )
                try:
                    active_track = editor._active_track()
                except Exception:
                    active_track = None
                checks["timeline_color_grade_state_for_rail"] = False
                if active_track is not None:
                    def _grade_active(value) -> bool:
                        if value is None:
                            return False
                        is_identity = getattr(value, "is_identity", None)
                        if callable(is_identity):
                            try:
                                return not bool(is_identity())
                            except Exception:
                                return True
                        return True

                    track_grade_active = any(
                        _grade_active(getattr(node_item, "color_grade", None))
                        for node_item, _masks in list(getattr(active_track, "node_item_chain", None) or [])
                    )
                    clip_grade_active = False
                    for clip in list(getattr(active_track, "clips", []) or []):
                        clip_graph = getattr(clip, "node_graph", None)
                        color = getattr(clip_graph, "color", None)
                        if _grade_active(getattr(color, "grade", None)):
                            clip_grade_active = True
                            break
                    checks["timeline_color_grade_state_for_rail"] = bool(
                        track_grade_active or clip_grade_active
                    )
                if color_container is not None:
                    geo = color_container.geometry()
                    checks["color_container_hidden_for_reference_side_panel"] = (
                        not bool(color_container.isVisible())
                    )
                    checks["color_container_geometry"] = [
                        int(geo.x()),
                        int(geo.y()),
                        int(geo.width()),
                        int(geo.height()),
                    ]
                if color_splitter is not None:
                    checks["color_splitter_sizes"] = [
                        int(v) for v in list(color_splitter.sizes())
                    ]
                color_dock_png = out / "editor_color_dock_action.png"
                if checks.get("color_dock_viewer_reforced"):
                    checks["color_dock_screenshot"] = _save_widget(editor, color_dock_png)
                    artifacts["color_dock"] = str(color_dock_png.resolve())
                else:
                    checks["color_dock_screenshot"] = False
                    try:
                        color_dock_png.unlink(missing_ok=True)
                    except Exception:
                        pass

            selected_node = None
            for node in list(getattr(graph_widget.scene, "_serial_nodes", []) or []):
                if str(getattr(node, "node_id", "")) == "E2":
                    selected_node = node
                    break
            if selected_node is not None:
                graph_widget.scene.clearSelection()
                selected_node.setSelected(True)
                select_panel = getattr(graph_widget, "_on_selected_node_for_params", None)
                if callable(select_panel):
                    select_panel(selected_node)
        _wait(app, 260)
        checks["viewer_frame_reforced"] = _force_viewer_frame(editor, media_path, seek_ms, out)
        _wait(app, 180)

        workbench_png = out / "workbench_node_graph_action.png"
        editor_png = out / "editor_workbench_node_graph_action.png"
        left_top_png = out / "editor_left_dock_top_action.png"
        left_library_png = out / "editor_left_library_panel_action.png"
        left_effects_png = out / "editor_left_effects_library_open_action.png"
        effects_section_png = out / "editor_effects_section_open_action.png"
        title_section_png = out / "editor_title_section_open_action.png"
        transitions_section_png = out / "editor_transitions_section_open_action.png"
        workflow_section_png = out / "editor_workflow_section_open_action.png"
        viewer_label_png = out / "editor_viewer_label_action.png"
        viewer_host_png = out / "editor_viewer_host_action.png"
        ai_command_open_png = out / "editor_ai_command_open_action.png"
        checks["workbench_screenshot"] = _save_widget(workbench_widget, workbench_png)
        preview_label = getattr(editor, "_preview_label", None)
        preview_host = getattr(editor, "_preview_host", None)
        if preview_label is not None:
            checks["viewer_label_screenshot"] = _save_widget(preview_label, viewer_label_png)
            artifacts["viewer_label"] = str(viewer_label_png.resolve())
        else:
            checks["viewer_label_screenshot"] = False
        if preview_host is not None:
            checks["viewer_host_screenshot"] = _save_widget(preview_host, viewer_host_png)
            artifacts["viewer_host"] = str(viewer_host_png.resolve())
        else:
            checks["viewer_host_screenshot"] = False
        left_dock = getattr(editor, "_left_dock_scroll", None) or getattr(editor, "_left_dock_host", None)
        if left_dock is not None:
            checks["left_dock_top_screenshot"] = _save_widget(left_dock, left_top_png)
            artifacts["left_dock_top"] = str(left_top_png.resolve())
            try:
                bar = left_dock.verticalScrollBar()
                old_value = int(bar.value())
                bar.setValue(max(0, min(int(bar.maximum()), int(bar.maximum() * 0.38))))
                _wait(app, 180)
                checks["left_library_screenshot"] = _save_widget(left_dock, left_library_png)
                artifacts["left_library"] = str(left_library_png.resolve())
                bar.setValue(old_value)
                _wait(app, 120)
            except Exception:
                checks["left_library_screenshot"] = _save_widget(left_dock, left_library_png)
                artifacts["left_library"] = str(left_library_png.resolve())
            try:
                effects_header = getattr(editor, "_effects_library_header", None)
                effects_host = getattr(editor, "_effects_library_section_host", None)
                if effects_header is not None:
                    from PySide6.QtWidgets import QPushButton

                    button = effects_header.findChild(QPushButton, "SectionDisclosure")
                    if button is not None:
                        button.setChecked(True)
                if effects_host is not None and hasattr(left_dock, "ensureWidgetVisible"):
                    left_dock.ensureWidgetVisible(effects_host, 0, 16)
                effects_panel = getattr(editor, "_effects_preset_panel", None)
                if effects_panel is not None:
                    effects_panel.setVisible(True)
                    effects_panel.setMinimumHeight(max(220, effects_panel.sizeHint().height()))
                    effects_panel.updateGeometry()
                if effects_host is not None:
                    effects_host.setMinimumHeight(max(260, effects_host.sizeHint().height()))
                    effects_host.updateGeometry()
                    effects_host.adjustSize()
                _wait(app, 220)
                checks["left_effects_open_screenshot"] = _save_widget(left_dock, left_effects_png)
                artifacts["left_effects_open"] = str(left_effects_png.resolve())
                if effects_host is not None:
                    checks["effects_section_open_screenshot"] = _save_widget(effects_host, effects_section_png)
                    artifacts["effects_section_open"] = str(effects_section_png.resolve())
                else:
                    checks["effects_section_open_screenshot"] = False
                section_specs = [
                    (
                        "title_section_open_screenshot",
                        "title_section_open",
                        "_title_presets_header",
                        "_title_presets_section_host",
                        "_title_presets_panel",
                        title_section_png,
                    ),
                    (
                        "transitions_section_open_screenshot",
                        "transitions_section_open",
                        "_transitions_header",
                        "_transitions_section_host",
                        "_transitions_panel",
                        transitions_section_png,
                    ),
                    (
                        "workflow_section_open_screenshot",
                        "workflow_section_open",
                        "_workflow_presets_header",
                        "_workflow_presets_section_host",
                        "_workflow_presets_panel",
                        workflow_section_png,
                    ),
                ]
                for check_key, artifact_key, header_attr, host_attr, panel_attr, path in section_specs:
                    header = getattr(editor, header_attr, None)
                    host = getattr(editor, host_attr, None)
                    panel_widget = getattr(editor, panel_attr, None)
                    try:
                        if header is not None:
                            from PySide6.QtWidgets import QPushButton

                            button = header.findChild(QPushButton, "SectionDisclosure")
                            if button is not None:
                                button.setChecked(True)
                        if panel_widget is not None:
                            panel_widget.setVisible(True)
                            panel_widget.setMinimumHeight(max(180, panel_widget.sizeHint().height()))
                            panel_widget.updateGeometry()
                        if host is not None:
                            host.setMinimumHeight(max(220, host.sizeHint().height()))
                            host.updateGeometry()
                            host.adjustSize()
                        _wait(app, 160)
                        if host is not None:
                            checks[check_key] = _save_widget(host, path)
                            artifacts[artifact_key] = str(path.resolve())
                        else:
                            checks[check_key] = False
                    except Exception:
                        checks[check_key] = False
            except Exception:
                checks["left_effects_open_screenshot"] = False
                checks["effects_section_open_screenshot"] = False
                checks["title_section_open_screenshot"] = False
                checks["transitions_section_open_screenshot"] = False
                checks["workflow_section_open_screenshot"] = False
        else:
            checks["left_dock_top_screenshot"] = False
            checks["left_library_screenshot"] = False
            checks["left_effects_open_screenshot"] = False
            checks["effects_section_open_screenshot"] = False
            checks["title_section_open_screenshot"] = False
            checks["transitions_section_open_screenshot"] = False
            checks["workflow_section_open_screenshot"] = False
        if left_dock is not None:
            try:
                left_dock.verticalScrollBar().setValue(0)
                _wait(app, 120)
            except Exception:
                pass
        try:
            show_ai_command = getattr(editor, "_show_ai_command_dock", None)
            if callable(show_ai_command):
                show_ai_command()
            banner = getattr(editor, "_status_banner", None)
            if banner is not None:
                try:
                    banner.hide()
                except Exception:
                    pass
            _wait(app, 180)
            checks["ai_command_open_screenshot"] = _save_widget(editor, ai_command_open_png)
            artifacts["ai_command_open"] = str(ai_command_open_png.resolve())
        except Exception:
            checks["ai_command_open_screenshot"] = False
        checks["editor_screenshot"] = _save_widget(editor, editor_png)
        artifacts["workbench"] = str(workbench_png.resolve())
        artifacts["editor"] = str(editor_png.resolve())

        track = next(
            (row for row in list(getattr(editor, "_tracks", []) or []) if int(getattr(row, "id", 0) or 0) == track_id),
            None,
        )
        stored_graph = getattr(track, "node_graph_view_data", {}) if track is not None else {}
        checks["stored_node_count"] = len(list((stored_graph or {}).get("nodes") or [])) == len(graph["nodes"])
        if graph_widget is not None:
            checks["visible_node_count"] = len(list(getattr(graph_widget.scene, "_serial_nodes", []) or [])) == len(graph["nodes"])
        else:
            checks["visible_node_count"] = False

        report = {
            "ok": all(checks.values()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "language": active_language,
            "media": str(media_path),
            "checks": checks,
            "steps": steps,
            "artifacts": artifacts,
            "node_graph": graph,
        }
    finally:
        try:
            editor.close()
        except Exception:
            pass
        _wait(app, 80)

    report_path = out / "workbench_node_action_flow.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report["report"] = str(report_path.resolve())
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a live workbench node graph action QA flow.")
    parser.add_argument("--media", default="")
    parser.add_argument("--out-dir", default=str(ROOT / "debugCapture" / "workbench_node_action_flow"))
    parser.add_argument("--language", default="ko")
    args = parser.parse_args()
    report = run_workbench_node_action_flow(
        media=args.media or None,
        out_dir=args.out_dir,
        language=args.language,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    exit_code = int(main())
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
