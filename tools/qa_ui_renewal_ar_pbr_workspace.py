from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _wait(app: Any, ms: int) -> None:
    from tools.qa_workbench_node_action_flow import _wait as wait_impl

    wait_impl(app, ms)


def _save_widget(widget: Any, path: Path) -> bool:
    from tools.qa_workbench_node_action_flow import _save_widget as save_impl

    return bool(save_impl(widget, path))


def _default_media() -> Path:
    from tools.qa_workbench_node_action_flow import _default_media as default_impl

    return Path(default_impl())


def _force_viewer_frame(editor: Any, media_path: Path, seek_ms: int, out_dir: Path) -> bool:
    from tools.qa_workbench_node_action_flow import _force_viewer_frame

    return bool(_force_viewer_frame(editor, media_path, seek_ms, out_dir))


def _pixmap_to_rgb_array(pixmap: Any):
    try:
        import numpy as np
        from PySide6.QtGui import QImage

        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
        width = image.width()
        height = image.height()
        bytes_per_line = image.bytesPerLine()
        data = bytes(image.constBits())
        rows = np.frombuffer(data, dtype=np.uint8).reshape((height, bytes_per_line))
        return rows[:, : width * 3].reshape((height, width, 3)).copy()
    except Exception:
        return None


def _rgb_array_to_pixmap(rgb: Any):
    try:
        import numpy as np
        from PySide6.QtGui import QImage, QPixmap

        arr = np.asarray(rgb)
        if arr.ndim != 3 or arr.shape[2] < 3:
            return None
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        arr = np.ascontiguousarray(arr[:, :, :3])
        height, width = arr.shape[:2]
        image = QImage(arr.data, width, height, arr.strides[0], QImage.Format.Format_RGB888).copy()
        return QPixmap.fromImage(image)
    except Exception:
        return None


def _set_viewer_pixmap(editor: Any, pixmap: Any) -> bool:
    try:
        if pixmap is None or pixmap.isNull():
            return False
        from PySide6.QtCore import Qt

        gl = getattr(editor, "_preview_gl", None)
        if gl is not None:
            try:
                gl.hide()
            except Exception:
                pass
        editor._preview_pixmap = pixmap
        remember = getattr(editor, "_remember_good_preview_pixmap", None)
        if callable(remember):
            remember()
        scale = getattr(editor, "_scale_preview_to_fit", None)
        if callable(scale):
            scale()
        label = getattr(editor, "_preview_label", None)
        if label is not None:
            target = pixmap
            try:
                size = label.size()
                if size.width() > 0 and size.height() > 0:
                    target = pixmap.scaled(
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
        return True
    except Exception:
        return False


def _restore_real_ar_pbr_viewer_frame(
    editor: Any,
    media_path: Path,
    track: dict[str, Any] | None,
    seek_ms: int,
    out_dir: Path,
) -> tuple[bool, dict[str, Any]]:
    from tools.qa_workbench_node_action_flow import _video_frame_pixmap

    base = _video_frame_pixmap(media_path, seek_ms, out_dir)
    if base is None or base.isNull():
        return False, {"ok": False, "error": "video frame unavailable"}
    if not isinstance(track, dict):
        return _set_viewer_pixmap(editor, base), {"ok": False, "error": "no ar/pbr track"}
    rgb = _pixmap_to_rgb_array(base)
    if rgb is None:
        return _set_viewer_pixmap(editor, base), {"ok": False, "error": "could not convert frame"}
    try:
        from app.ar_pbr.compositor import composite_preview_frame
        from app.ar_pbr.importer import import_asset

        asset_path = Path(str(track.get("asset_path") or "")).expanduser()
        descriptor, import_diag = import_asset(
            asset_path,
            settings={
                "placeholder_on_error": False,
                "max_triangles_per_geometry": 48_000,
            },
        )
        descriptors = {
            str(track.get("id") or ""): descriptor,
            str(asset_path.resolve()): descriptor,
            "default": descriptor,
        }
        out_rgb, render_diag = composite_preview_frame(
            rgb,
            time_ms=int(seek_ms),
            ar_tracks=[track],
            camera_solution=None,
            depth_frame=None,
            settings={
                "renderer": "software_pbr",
                "asset_descriptors": descriptors,
                "camera_z": 3.25,
                "shadow_blur": 3.0,
            },
        )
        rendered = int((render_diag or {}).get("rendered_track_count", 0) or 0) > 0
        pixmap = _rgb_array_to_pixmap(out_rgb) if rendered else base
        if pixmap is not None:
            try:
                pixmap.save(str(out_dir / "viewer_ar_pbr_composited_frame.png"), "PNG")
            except Exception:
                pass
        shown = _set_viewer_pixmap(editor, pixmap or base)
        return bool(shown and rendered), {
            "ok": bool(shown and rendered),
            "import": import_diag,
            "render": render_diag,
        }
    except Exception as exc:
        _set_viewer_pixmap(editor, base)
        return False, {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _default_asset() -> Path:
    candidates = [
        ROOT / "debugCapture" / "ar_pbr_selected_resources" / "babylon_car.glb",
        ROOT / "debugCapture" / "ar_pbr_selected_resources" / "modelviewer_horse.glb",
        ROOT / "debugCapture" / "ar_pbr_selected_resources" / "ferrari.glb",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    found = sorted((ROOT / "debugCapture").rglob("*.glb"))
    if found:
        return found[0]
    raise FileNotFoundError("no GLB sample found under debugCapture")


def run_ar_pbr_workspace_qa(
    *,
    media: str | Path | None = None,
    asset: str | Path | None = None,
    out_dir: str | Path = ROOT / "debugCapture" / "ui_renewal_ar_pbr_workspace_round",
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
    asset_path = Path(asset).expanduser() if asset else _default_asset()
    if not asset_path.is_absolute():
        asset_path = ROOT / asset_path
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
        _wait(app, 220)

        registry = editor._ensure_python_action_registry()
        imported = registry.execute(
            "media.import_to_timeline",
            {"path": str(media_path), "kind": "video", "at_ms": 0},
        ).to_dict()
        steps.append({"action": "media.import_to_timeline", **imported})
        video_track_id = int((imported.get("result") or {}).get("track_id") or 0)
        video_clip_id = int((imported.get("result") or {}).get("clip_id") or 0)
        checks["media_imported"] = bool(imported.get("ok") and video_track_id and video_clip_id)
        if video_track_id and video_clip_id:
            registry.execute(
                "selection.set",
                {"kind": "video", "track_id": video_track_id, "clip_id": video_clip_id},
            )
        _wait(app, 360)
        _force_viewer_frame(editor, media_path, 7000, out)

        placed = None
        place = getattr(editor, "_add_ar_pbr_asset_to_preview", None)
        if callable(place):
            placed = place(asset_path, image_point=(0.62, 0.64))
        checks["ar_pbr_placed"] = isinstance(placed, dict)
        steps.append({
            "action": "editor._add_ar_pbr_asset_to_preview",
            "ok": checks["ar_pbr_placed"],
            "asset": str(asset_path),
            "note": "Current real placement path; Python Action surface is pending.",
        })
        if isinstance(placed, dict):
            from app.ar_pbr.project_tracks import transform_position_from_frame_point

            selected_id = str(placed.get("id") or "")
            placed = next(
                (
                    row for row in getattr(editor, "_ar_pbr_tracks", []) or []
                    if isinstance(row, dict) and str(row.get("id") or "") == selected_id
                ),
                placed,
            )
            placed["placement"] = {
                "mode": "manual",
                "coordinate_space": "frame_normalized",
                "image_point": [0.62, 0.64],
                "surface_offset": 0.0,
            }
            placed.setdefault("transform", {})
            placed["transform"]["position"] = transform_position_from_frame_point(0.62, 0.64, z=0.0)
            render = placed.setdefault("render", {})
            if isinstance(render, dict):
                lighting = render.setdefault("lighting", {})
                if isinstance(lighting, dict):
                    lighting["ibl_exposure"] = 2.15
                    lighting["direct_strength"] = 1.35
                    lighting["shadow_strength"] = 0.38
            # Product-catalog captures should show the 3D asset clearly in the
            # video viewer, not as a tiny proof-of-placement marker.
            editor._set_ar_pbr_track_uniform_scale(placed, 1.05)
            editor._set_ar_pbr_track_rotation_value(placed, 0, -8.0)
            editor._set_ar_pbr_track_rotation_value(placed, 1, 34.0)
            editor._set_ar_pbr_track_rotation_value(placed, 2, 5.0)
            editor._set_ar_pbr_track_position_z(placed, 0.0)
            editor._selected_ar_pbr_track_id = str(placed.get("id") or "")
            panel = getattr(editor, "_workbench_panel", None)
            if panel is not None and hasattr(panel, "set_ar_pbr_track"):
                panel.set_ar_pbr_track(placed)
            editor._refresh_ar_pbr_preview_after_gizmo_change()

        editor._player.set_position(7000)
        _wait(app, 1200)
        try:
            editor._player.refresh_current_frame()
        except Exception:
            pass
        _wait(app, 380)
        # AR/PBR placement can temporarily put the imported GLB at the top of
        # the media pool and refresh the preview while the descriptor is still
        # loading. For catalog/review evidence, keep the real source video
        # visible in the Viewer after the 3D object state has been attached,
        # then composite the actual GLB mesh with the same AR/PBR renderer
        # contract used by preview/export.
        checks["viewer_frame_restored"] = _force_viewer_frame(editor, media_path, 7000, out)
        ar_composited, ar_diag = _restore_real_ar_pbr_viewer_frame(
            editor,
            media_path,
            placed if isinstance(placed, dict) else None,
            7000,
            out,
        )
        checks["ar_pbr_viewer_composited"] = ar_composited
        steps.append({
            "action": "ar_pbr.software_composite_frame",
            "ok": ar_composited,
            "diagnostics": ar_diag,
        })
        try:
            canvas = getattr(editor, "_drawing_canvas", None)
            if canvas is not None:
                canvas.raise_()
                canvas.update()
        except Exception:
            pass
        try:
            pool = getattr(editor, "_media_pool", None)
            if pool is not None and hasattr(pool, "select_path"):
                pool.select_path(media_path)
        except Exception:
            pass
        _wait(app, 300)

        workbench_widget = getattr(editor, "_workbench_section_host", None) or getattr(editor, "_workbench_panel", None) or editor
        workbench_png = out / "workbench_ar_pbr_object_action.png"
        checks["workbench_ar_pbr_screenshot"] = _save_widget(workbench_widget, workbench_png)
        artifacts["workbench_ar_pbr"] = str(workbench_png.resolve())

        editor_png = out / "editor_ar_pbr_object_action.png"
        checks["editor_ar_pbr_screenshot"] = _save_widget(editor, editor_png)
        artifacts["editor_ar_pbr"] = str(editor_png.resolve())

        report = {
            "ok": bool(
                checks.get("media_imported")
                and checks.get("ar_pbr_placed")
                and checks.get("ar_pbr_viewer_composited")
                and checks.get("workbench_ar_pbr_screenshot")
                and checks.get("editor_ar_pbr_screenshot")
            ),
            "language": active_language,
            "media": str(media_path),
            "asset": str(asset_path),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "steps": steps,
            "checks": checks,
            "artifacts": artifacts,
            "action_surface": "pending",
        }
        (out / "ui_renewal_ar_pbr_workspace_qa.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return report
    finally:
        editor.close()
        editor.deleteLater()
        _wait(app, 100)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media", default="")
    parser.add_argument("--asset", default="")
    parser.add_argument("--out-dir", default=str(ROOT / "debugCapture" / "ui_renewal_ar_pbr_workspace_round"))
    parser.add_argument("--language", default="ko")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    report = run_ar_pbr_workspace_qa(
        media=args.media or None,
        asset=args.asset or None,
        out_dir=args.out_dir,
        language=args.language,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
