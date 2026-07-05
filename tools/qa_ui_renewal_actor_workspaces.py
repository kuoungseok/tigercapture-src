from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Feature evidence screenshots are captured from QWidget.grab() in an
# offscreen process. Keep preview delivery on the owning QImage/QLabel path so
# GPU child surfaces do not appear as black rectangles in the captured editor.
os.environ.setdefault("TIGERCAPTURE_PREVIEW_QIMAGE", "1")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _wait(app: Any, ms: int) -> None:
    from tools.qa_workbench_node_action_flow import _wait as wait_impl

    wait_impl(app, ms)


def _save_widget(widget: Any, path: Path) -> bool:
    from tools.qa_workbench_node_action_flow import _save_widget as save_impl

    return bool(save_impl(widget, path))


def _hide_editor_transients(editor: Any) -> None:
    """Hide temporary status/toast overlays so evidence captures show the UI."""
    for attr in ("_status_banner", "_workflow_apply_toast"):
        widget = getattr(editor, attr, None)
        if widget is None:
            continue
        try:
            widget.hide()
        except Exception:
            pass
        if attr == "_workflow_apply_toast":
            try:
                setattr(editor, attr, None)
            except Exception:
                pass
    timer = getattr(editor, "_status_banner_timer", None)
    if timer is not None:
        try:
            timer.stop()
        except Exception:
            pass


def _hide_live2d_viewer_transients(viewer: Any) -> None:
    """Hide temporary Live2D loading chrome before product evidence capture."""
    for attr in ("_loading_panel", "_loading_bar", "_cancel_load_btn"):
        widget = getattr(viewer, attr, None)
        if widget is None:
            continue
        try:
            widget.hide()
        except Exception:
            pass
    status = getattr(viewer, "_status_lbl", None)
    if status is not None:
        try:
            status.setText("")
        except Exception:
            pass


def _default_media() -> Path:
    from tools.qa_workbench_node_action_flow import _default_media as default_impl

    return Path(default_impl())


def _force_viewer_frame(editor: Any, media_path: Path, seek_ms: int, out_dir: Path) -> bool:
    from tools.qa_workbench_node_action_flow import _force_viewer_frame

    return bool(_force_viewer_frame(editor, media_path, seek_ms, out_dir))


def _default_live2d_model() -> Path:
    candidates = [
        ROOT / "resources" / "live2d_samples" / "CubismWebSamples" / "Samples" / "Resources" / "Hiyori" / "Hiyori.model3.json",
        ROOT / "resources" / "live2d_samples" / "CubismWebSamples" / "Samples" / "Resources" / "Haru" / "Haru.model3.json",
        ROOT / "resources" / "live2d_samples" / "hiyori_free" / "hiyori_free_t08.model3.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    found = sorted((ROOT / "resources" / "live2d_samples").rglob("*.model3.json"))
    if found:
        return found[0]
    raise FileNotFoundError("no Live2D model3 sample found under resources/live2d_samples")


def _find_live2d_clip(editor: Any, track_id: int, clip_index: int = 0) -> tuple[Any, Any]:
    for track in list(getattr(editor, "_live2d_actor_tracks", []) or []):
        if int(getattr(track, "id", -1) or -1) != int(track_id):
            continue
        clips = list(getattr(track, "clips", []) or [])
        if not clips:
            break
        return track, clips[max(0, min(int(clip_index), len(clips) - 1))]
    raise RuntimeError(f"Live2D actor clip not found: track_id={track_id} clip_index={clip_index}")


def run_actor_workspace_qa(
    *,
    media: str | Path | None = None,
    live2d_model: str | Path | None = None,
    out_dir: str | Path = ROOT / "debugCapture" / "ui_renewal_actor_workspace_round",
    language: str = "ko",
    open_live2d_viewer: bool = False,
    seek_ms: int = 8000,
) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    from app.font_fallback import apply_ui_font
    from app.i18n import initialize, set_language
    from app.style import APP_QSS
    from app.video_editor_window import VideoEditorWindow

    media_path = Path(media).expanduser() if media else _default_media()
    if not media_path.is_absolute():
        media_path = ROOT / media_path
    model_path = Path(live2d_model).expanduser() if live2d_model else _default_live2d_model()
    if not model_path.is_absolute():
        model_path = ROOT / model_path
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
    checks: dict[str, bool] = {}
    artifacts: dict[str, str] = {}
    try:
        try:
            editor._autosave_timer.stop()
            editor._do_autosave = lambda *_args, **_kwargs: None
        except Exception:
            pass
        editor.resize(1480, 920)
        editor.show()
        _wait(app, 200)

        registry = editor._ensure_python_action_registry()
        imported = registry.execute(
            "media.import_to_timeline",
            {"path": str(media_path), "kind": "video", "at_ms": 0},
        ).to_dict()
        steps.append({"action": "media.import_to_timeline", **imported})
        video_track_id = int((imported.get("result") or {}).get("track_id") or 0)
        video_clip_id = int((imported.get("result") or {}).get("clip_id") or 0)
        checks["media_imported"] = bool(imported.get("ok") and video_track_id and video_clip_id)
        _wait(app, 350)

        if video_track_id and video_clip_id:
            registry.execute(
                "selection.set",
                {"kind": "video", "track_id": video_track_id, "clip_id": video_clip_id},
            )
        seek_ms = max(0, int(seek_ms))
        _force_viewer_frame(editor, media_path, seek_ms, out)

        added = registry.execute(
            "actor.add",
            {
                "kind": "live2d",
                "path": str(model_path),
                "start_ms": 1200,
                "duration_ms": 8200,
                "pos_x": 0.68,
                "pos_y": 0.47,
                "scale": 0.86,
                "opacity": 0.96,
                "label": "Live2D actor lane",
            },
        ).to_dict()
        steps.append({"action": "actor.add", **added})
        actor_track_id = int((added.get("result") or {}).get("track_id") or 0)
        clip_index = int((added.get("result") or {}).get("clip_index") or 0)
        checks["live2d_actor_added"] = bool(added.get("ok") and actor_track_id)

        keyframes = {
            "pos_x": [
                {"time_ms": 0, "value": 0.62, "curve": "smoothstep"},
                {"time_ms": 4200, "value": 0.72, "curve": "smoothstep"},
                {"time_ms": 8200, "value": 0.58, "curve": "ease_out"},
            ],
            "scale": [
                {"time_ms": 0, "value": 0.78, "curve": "smoothstep"},
                {"time_ms": 4200, "value": 0.95, "curve": "smoothstep"},
                {"time_ms": 8200, "value": 0.86, "curve": "ease_out"},
            ],
            "opacity": [
                {"time_ms": 0, "value": 0.0, "curve": "ease_out"},
                {"time_ms": 900, "value": 1.0, "curve": "smoothstep"},
                {"time_ms": 7600, "value": 1.0, "curve": "linear"},
                {"time_ms": 8200, "value": 0.18, "curve": "ease_in"},
            ],
        }
        keyed = registry.execute(
            "actor.set_keyframes",
            {
                "kind": "live2d",
                "track_id": actor_track_id,
                "clip_index": clip_index,
                "keyframes": keyframes,
            },
        ).to_dict()
        steps.append({"action": "actor.set_keyframes", **keyed})
        checks["live2d_keyframes_set"] = bool(keyed.get("ok"))

        perf_added = registry.execute(
            "vtuber.performance_source.add_clip",
            {
                "path": str(media_path),
                "start_ms": 0,
                "duration_ms": 9000,
            },
        ).to_dict()
        steps.append({"action": "vtuber.performance_source.add_clip", **perf_added})
        checks["performance_source_track_added"] = bool(perf_added.get("ok"))

        perf_applied = registry.execute(
            "actor.live2d.apply_performance_source",
            {
                "track_id": actor_track_id,
                "clip_index": clip_index,
                "time_ms": 3600,
                "source_path": str(media_path),
                "analyze_video": False,
                "fit_duration": False,
                "replace_transform": False,
                "mocap_frames": [
                    {"time_ms": 0, "x_norm": 0.44, "y_norm": 0.50, "w_norm": 0.18, "h_norm": 0.24},
                    {"time_ms": 1300, "x_norm": 0.52, "y_norm": 0.46, "w_norm": 0.20, "h_norm": 0.26},
                    {"time_ms": 2700, "x_norm": 0.60, "y_norm": 0.48, "w_norm": 0.21, "h_norm": 0.27},
                    {"time_ms": 4200, "x_norm": 0.57, "y_norm": 0.51, "w_norm": 0.19, "h_norm": 0.25},
                    {"time_ms": 6200, "x_norm": 0.49, "y_norm": 0.47, "w_norm": 0.20, "h_norm": 0.24},
                    {"time_ms": 8200, "x_norm": 0.46, "y_norm": 0.49, "w_norm": 0.18, "h_norm": 0.23},
                ],
                "framing_payload": {
                    "schema": "tigerstudio.vtuber.source_framing_control.v1",
                    "time_ms": 3600,
                    "subject_type": "face_only",
                    "preset": "bust_up",
                    "final": {
                        "model_view": {
                            "zoom": 6.4,
                            "pan_x": 0.12,
                            "pan_y": -1.35,
                            "pan_z": 0.0,
                            "camera_z": 3.25,
                            "lower_occlusion_y": 0.68,
                        },
                        "track_rotation": [-5.0, 180.0, 0.0],
                    },
                },
            },
        ).to_dict()
        steps.append({"action": "actor.live2d.apply_performance_source", **perf_applied})
        checks["live2d_performance_source_applied"] = bool(perf_applied.get("ok"))

        track, clip = _find_live2d_clip(editor, actor_track_id, clip_index)
        select_actor = getattr(editor, "_select_live2d_clip_in_lane", None)
        if callable(select_actor):
            select_actor(clip)
        refresh_actor = getattr(editor, "_refresh_live2d_workbench_selection", None)
        if callable(refresh_actor):
            refresh_actor(clip)
        _wait(app, 220)

        checks["live2d_lane_rows_exist"] = bool(getattr(editor, "_live2d_lane_rows", []) or [])

        # Do not call _force_viewer_frame here: that helper writes a raw
        # source-video fallback into the Viewer and would hide the Live2D
        # overlay we are trying to prove. Let ProjectPlayer render the real
        # composited frame instead.
        try:
            editor._player.set_qimage_frame_enabled(True)
        except Exception:
            pass
        try:
            editor._player.set_live2d_actor_tracks(getattr(editor, "_live2d_actor_tracks", []) or [])
        except Exception:
            pass
        refresh_tracks = getattr(editor, "_refresh_player_tracks", None)
        if callable(refresh_tracks):
            refresh_tracks()
        try:
            editor._player.set_live2d_actor_tracks(getattr(editor, "_live2d_actor_tracks", []) or [])
        except Exception:
            pass
        editor._player.set_position(3600)
        _wait(app, 260)
        try:
            editor._player.refresh_current_frame()
        except Exception:
            pass
        _wait(app, 650)
        try:
            editor._refresh_live2d_workbench_selection(clip)
        except Exception:
            pass
        _wait(app, 120)
        _hide_editor_transients(editor)
        _wait(app, 40)

        workbench_target = getattr(
            getattr(editor, "_workbench_panel", None),
            "current_target",
            lambda: None,
        )()
        checks["live2d_workbench_target"] = bool(
            isinstance(workbench_target, tuple)
            and workbench_target
            and str(workbench_target[0]).lower() == "live2d"
        )
        preview_pixmap = getattr(editor, "_preview_pixmap", None)
        checks["live2d_preview_frame_available"] = bool(
            preview_pixmap is not None
            and not preview_pixmap.isNull()
            and preview_pixmap.width() > 0
            and preview_pixmap.height() > 0
        )

        workbench_widget = getattr(editor, "_workbench_section_host", None) or getattr(editor, "_workbench_panel", None) or editor
        workbench_png = out / "workbench_live2d_actor_action.png"
        checks["workbench_live2d_screenshot"] = _save_widget(workbench_widget, workbench_png)
        artifacts["workbench_live2d"] = str(workbench_png.resolve())

        editor_png = out / "editor_live2d_actor_action.png"
        checks["editor_live2d_screenshot"] = _save_widget(editor, editor_png)
        artifacts["editor_live2d"] = str(editor_png.resolve())

        if open_live2d_viewer:
            viewer_png = out / "live2d_viewer_action.png"
            try:
                open_editor = getattr(editor, "_on_live2d_clip_dclick", None)
                if callable(open_editor):
                    open_editor(clip)
                    _wait(app, 2600)
                viewer = getattr(editor, "_live2d_editor", None)
                checks["live2d_viewer_opened"] = bool(viewer is not None and viewer.isVisible())
                if viewer is not None:
                    for _ in range(8):
                        if not bool(getattr(viewer, "_loading_active", False)):
                            break
                        _wait(app, 250)
                    _hide_live2d_viewer_transients(viewer)
                    _wait(app, 80)
                    checks["live2d_viewer_screenshot"] = _save_widget(viewer, viewer_png)
                    artifacts["live2d_viewer"] = str(viewer_png.resolve())
            except Exception as exc:
                checks["live2d_viewer_opened"] = False
                steps.append({"action": "live2d.viewer.open", "ok": False, "error": repr(exc)})
        else:
            checks["live2d_viewer_opened"] = False
            checks["live2d_viewer_screenshot"] = False

        report = {
            "ok": bool(
                checks.get("media_imported")
                and checks.get("live2d_actor_added")
                and checks.get("live2d_keyframes_set")
                and checks.get("performance_source_track_added")
                and checks.get("live2d_performance_source_applied")
                and checks.get("live2d_workbench_target")
                and checks.get("live2d_preview_frame_available")
                and checks.get("editor_live2d_screenshot")
                and checks.get("workbench_live2d_screenshot")
            ),
            "language": active_language,
            "media": str(media_path),
            "seek_ms": int(seek_ms),
            "live2d_model": str(model_path),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "steps": steps,
            "checks": checks,
            "artifacts": artifacts,
            "open_live2d_viewer": bool(open_live2d_viewer),
        }
        (out / "ui_renewal_actor_workspace_qa.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return report
    finally:
        try:
            viewer = getattr(editor, "_live2d_editor", None)
            if viewer is not None:
                viewer.close()
        except Exception:
            pass
        editor.close()
        editor.deleteLater()
        _wait(app, 100)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media", default="")
    parser.add_argument("--live2d-model", default="")
    parser.add_argument("--out-dir", default=str(ROOT / "debugCapture" / "ui_renewal_actor_workspace_round"))
    parser.add_argument("--language", default="ko")
    parser.add_argument("--seek-ms", type=int, default=8000)
    parser.add_argument(
        "--open-live2d-viewer",
        action="store_true",
        help="Also open and capture the native Live2D viewer. This may be isolated in automation because the native runtime can crash during process shutdown.",
    )
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    report = run_actor_workspace_qa(
        media=args.media or None,
        live2d_model=args.live2d_model or None,
        out_dir=args.out_dir,
        language=args.language,
        open_live2d_viewer=bool(args.open_live2d_viewer),
        seek_ms=int(args.seek_ms),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
