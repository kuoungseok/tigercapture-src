"""Capture the standalone MMD player window to a PNG for remote review."""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.font_fallback import apply_ui_font
from app.mmd.diagnostics import analyze_mmd_model
from app.mmd.player_window import MMD_PLAYER_DEFAULT_HEIGHT, MMD_PLAYER_DEFAULT_WIDTH, MMDPlayerWindow
from app.mmd.regression_profiles import (
    evaluate_mmd_regression_profile,
    mmd_regression_profile,
    mmd_regression_profile_ids,
    mmd_regression_profile_model_path,
)
from app.style import APP_QSS


OUT = ROOT / "debugCapture" / "mmd_player" / "mmd_player_capture.png"


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture the MMD player window")
    parser.add_argument("--mode", choices=("toon",), default="toon")
    parser.add_argument("--lighting", choices=("studio_soft", "golden_hour", "night_stage"), default="studio_soft")
    parser.add_argument("--profile", choices=mmd_regression_profile_ids(), default="", help="Use a known MMD regression capture profile")
    parser.add_argument("--out", default="")
    parser.add_argument("--report-out", default="", help="Optional JSON report path for the captured frame diagnostics")
    parser.add_argument("--model", default="")
    parser.add_argument("--vmd", default="")
    parser.add_argument("--yaw", type=float, default=None)
    parser.add_argument("--zoom", type=float, default=None)
    parser.add_argument("--bloom", type=float, default=None)
    parser.add_argument("--offset-x", type=float, default=None)
    parser.add_argument("--offset-y", type=float, default=None)
    parser.add_argument("--time-ms", type=int, default=None)
    parser.add_argument("--play", action="store_true")
    parser.add_argument("--pause", action="store_true")
    parser.add_argument("--delay-ms", type=int, default=1200)
    args = parser.parse_args()
    profile = mmd_regression_profile(args.profile) if args.profile else {}
    capture_defaults = dict(profile.get("capture") or {}) if isinstance(profile, dict) else {}
    model_path = args.model or (str(mmd_regression_profile_model_path(args.profile)) if args.profile else "")
    motion_path = args.vmd or str(profile.get("motion_path") or capture_defaults.get("vmd") or capture_defaults.get("motion") or "")
    out_path = Path(args.out or capture_defaults.get("out") or OUT)
    report_path = Path(args.report_out or capture_defaults.get("report_out") or "") if (args.report_out or capture_defaults.get("report_out")) else None
    lighting_key = str(capture_defaults.get("lighting") or args.lighting)
    yaw = args.yaw if args.yaw is not None else capture_defaults.get("yaw")
    zoom = args.zoom if args.zoom is not None else capture_defaults.get("zoom")
    bloom = args.bloom if args.bloom is not None else capture_defaults.get("bloom")
    offset_x = args.offset_x if args.offset_x is not None else capture_defaults.get("offset_x")
    offset_y = args.offset_y if args.offset_y is not None else capture_defaults.get("offset_y")
    time_ms = args.time_ms if args.time_ms is not None else capture_defaults.get("time_ms")
    pause = bool(args.pause or capture_defaults.get("pause"))
    play = bool(args.play or capture_defaults.get("play"))

    QCoreApplication.setApplicationName("TigerCapture MMD Player Capture")
    QCoreApplication.setOrganizationName("TigerCapture")
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setStyleSheet(APP_QSS)
    apply_ui_font(app)
    icon_path = ROOT / "resources" / "tigercapture.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MMDPlayerWindow(model_path or None, motion_path or None)
    lighting_index = window.lighting_combo.findData(lighting_key)
    if lighting_index >= 0:
        window.lighting_combo.setCurrentIndex(lighting_index)
    if pause and window._playing:
        window.toggle_play()
    elif play and not window._playing:
        window.toggle_play()
    if yaw is not None:
        window.yaw_slider.setValue(int(float(yaw)))
        window._yaw = float(yaw)
        window._refresh_preview()
    if zoom is not None:
        zoom_percent = max(35, min(220, int(round(float(zoom) * 100.0))))
        window.zoom_slider.setValue(zoom_percent)
        window._zoom = float(zoom_percent) / 100.0
        window._refresh_preview()
    if bloom is not None:
        bloom_percent = max(0, min(150, int(round(float(bloom) * 100.0))))
        window.bloom_slider.setValue(bloom_percent)
        window._bloom_strength = float(bloom_percent) / 100.0
        window._sync_bloom_label()
        window._refresh_preview()
    if time_ms is not None:
        window._set_time(max(0, min(int(time_ms), window.time_slider.maximum())))
    def apply_view_adjustment() -> None:
        if window._last_item is None or (offset_x is None and offset_y is None):
            return
        item = dict(window._last_item)
        if offset_x is not None:
            item["offset_x"] = float(offset_x)
        if offset_y is not None:
            item["offset_y"] = float(offset_y)
        window._last_item = item
        window.preview.set_mmd_overlay_items([item])
        window.preview.update_frame(window._base_frame, None)

    apply_view_adjustment()
    window.resize(MMD_PLAYER_DEFAULT_WIDTH, MMD_PLAYER_DEFAULT_HEIGHT)
    window.show()
    window.raise_()
    window.activateWindow()
    exit_code = {"value": 0}

    def capture() -> None:
        apply_view_adjustment()
        out = out_path
        out.parent.mkdir(parents=True, exist_ok=True)
        pixmap = window.grab()
        pixmap.save(str(out), "PNG")
        if report_path is not None:
            app.processEvents()
            diagnostics = dict((window.latest_render_item() or {}).get("diagnostics") or {})
            payload = {
                "ok": True,
                "screenshot": str(out),
                "profile_id": str(args.profile or ""),
                "model": str(model_path or ""),
                "motion": str(motion_path or ""),
                "diagnostics": diagnostics,
            }
            qa_report = None
            if args.profile and model_path:
                qa_report = analyze_mmd_model(
                    Path(model_path),
                    Path(motion_path) if motion_path else None,
                    sample_frames=None if motion_path else [0],
                )
                payload["qa_report"] = qa_report
            if args.profile:
                profile_result = evaluate_mmd_regression_profile(qa_report or {"diagnostics": diagnostics}, args.profile)
                payload["regression_profile"] = profile_result
                payload["ok"] = bool(profile_result.get("ok"))
                if not payload["ok"]:
                    exit_code["value"] = 1
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        app.quit()

    QTimer.singleShot(max(250, int(args.delay_ms)), capture)
    app.exec()
    return int(exit_code["value"])


if __name__ == "__main__":
    raise SystemExit(main())
