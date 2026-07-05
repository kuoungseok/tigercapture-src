"""Launch the app-facing AR/PBR asset preview window."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

from app.actions import build_default_action_registry
from app.ar_pbr.preview_window import ArPbrAssetPreviewWindow


DEFAULT_ASSET = ROOT / "debugCapture" / "ar_pbr_external_assets" / "es_fbx" / "es.fbx"


def _coerce_setting_value(raw: str) -> object:
    text = str(raw).strip()
    lowered = text.casefold()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return float(text)
    except ValueError:
        return text


def _parse_setting_pairs(pairs: list[str] | None) -> dict[str, object]:
    settings: dict[str, object] = {}
    for entry in pairs or []:
        if "=" not in entry:
            raise SystemExit(f"--set expects key=value, got: {entry!r}")
        key, _, value = entry.partition("=")
        key = key.strip()
        if not key:
            raise SystemExit(f"--set key must not be empty: {entry!r}")
        settings[key] = _coerce_setting_value(value)
    return settings


class _ActionOwner:
    def __init__(self, window: ArPbrAssetPreviewWindow) -> None:
        self._ar_pbr_preview_windows = [window]
        self._ar_pbr_preview_window_registry = {}
        self._ar_pbr_tracks = []
        self._selected_ar_pbr_track_id = ""
        self._preview_gl = None
        self._preview_gl_frame_size = None
        self._player = None


def _configure_gl() -> None:
    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", default=str(DEFAULT_ASSET))
    parser.add_argument("--screenshot", default="")
    parser.add_argument("--screenshot-delay-ms", type=int, default=1600)
    parser.add_argument("--view-state-out", default="", help="Write current view and scene settings JSON on exit.")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--zoom", type=float, default=None)
    parser.add_argument("--zoom-factor", type=float, default=None)
    parser.add_argument("--camera-z", type=float, default=None)
    parser.add_argument("--pitch", type=float, default=None)
    parser.add_argument("--yaw", type=float, default=None)
    parser.add_argument("--roll", type=float, default=None)
    parser.add_argument("--pan-x", type=float, default=None)
    parser.add_argument("--pan-y", type=float, default=None)
    parser.add_argument("--pan-z", type=float, default=None)
    parser.add_argument("--hide-background", action="store_true")
    parser.add_argument(
        "--set",
        dest="settings",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Apply a scene-lighting setting (repeatable), e.g. --set tone_exposure=0.4 --set render_profile=marmoset_pbr",
    )
    args = parser.parse_args()
    scene_settings = _parse_setting_pairs(args.settings)

    _configure_gl()
    app = QApplication(sys.argv)
    window = ArPbrAssetPreviewWindow(Path(args.asset))
    window.resize(max(640, int(args.width)), max(480, int(args.height)))
    window.show()
    owner = _ActionOwner(window)
    registry = build_default_action_registry(owner)

    screenshot_path = Path(args.screenshot).expanduser().resolve() if str(args.screenshot or "").strip() else None
    view_state_path = Path(args.view_state_out).expanduser().resolve() if str(args.view_state_out or "").strip() else None
    attempts = {"count": 0}

    def _view_state_payload() -> dict[str, object]:
        state = getattr(window, "_state", None)
        view = {}
        if state is not None:
            view = {
                "pitch": float(getattr(state, "pitch", 0.0) or 0.0),
                "yaw": float(getattr(state, "yaw", 0.0) or 0.0),
                "roll": float(getattr(state, "roll", 0.0) or 0.0),
                "zoom": float(getattr(state, "zoom", 0.0) or 0.0),
                "camera_z": float(getattr(state, "camera_z", 0.0) or 0.0),
                "pan_x": float(getattr(state, "pan_x", 0.0) or 0.0),
                "pan_y": float(getattr(state, "pan_y", 0.0) or 0.0),
                "pan_z": float(getattr(state, "pan_z", 0.0) or 0.0),
            }
        lighting = {}
        getter = getattr(window, "lighting_settings", None)
        if callable(getter):
            try:
                lighting = dict(getter() or {})
            except Exception:
                lighting = {}
        return {
            "asset": str(Path(args.asset).expanduser()),
            "view": view,
            "scene_settings": lighting,
        }

    def _write_view_state() -> None:
        if view_state_path is None:
            return
        view_state_path.parent.mkdir(parents=True, exist_ok=True)
        view_state_path.write_text(json.dumps(_view_state_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(str(view_state_path))

    app.aboutToQuit.connect(_write_view_state)

    def _apply_action_and_capture() -> None:
        attempts["count"] += 1
        if (getattr(window, "_state", None) is None or getattr(window, "_gl_widget", None) is None) and attempts["count"] < 90:
            QTimer.singleShot(100, _apply_action_and_capture)
            return
        params = {
            "fit_first": True,
            "hide_environment_background": bool(args.hide_background),
        }
        for key, attr in (
            ("zoom", "zoom"),
            ("zoom_factor", "zoom_factor"),
            ("camera_z", "camera_z"),
            ("pitch", "pitch"),
            ("yaw", "yaw"),
            ("roll", "roll"),
            ("pan_x", "pan_x"),
            ("pan_y", "pan_y"),
            ("pan_z", "pan_z"),
        ):
            value = getattr(args, attr)
            if value is not None:
                params[key] = value
        result = registry.execute("ar_pbr.preview.view.set", params).to_dict()
        print(result)
        if scene_settings:
            settings_result = registry.execute("ar_pbr.preview.settings.set", dict(scene_settings)).to_dict()
            print(settings_result)
        if screenshot_path is None:
            return

        def _capture() -> None:
            try:
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                app.processEvents()
                pixmap = window.grab()
                if not pixmap.save(str(screenshot_path), "PNG"):
                    raise RuntimeError(f"failed to save screenshot: {screenshot_path}")
                print(str(screenshot_path))
            finally:
                app.quit()

        QTimer.singleShot(max(100, int(args.screenshot_delay_ms)), _capture)

    if screenshot_path is not None or bool(scene_settings) or any(
        value is not None
        for value in (
            args.zoom,
            args.zoom_factor,
            args.camera_z,
            args.pitch,
            args.yaw,
            args.roll,
            args.pan_x,
            args.pan_y,
            args.pan_z,
        )
    ) or args.hide_background:
        QTimer.singleShot(100, _apply_action_and_capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
