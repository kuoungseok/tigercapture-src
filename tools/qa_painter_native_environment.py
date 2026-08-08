from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _enum_value(value) -> int | str:
    try:
        return int(value.value)
    except (AttributeError, TypeError, ValueError):
        return str(value)


def _opengl_probe(root: Path) -> dict[str, object]:
    from PySide6.QtGui import (
        QColor,
        QImage,
        QOffscreenSurface,
        QOpenGLContext,
        QSurfaceFormat,
    )
    from PySide6.QtOpenGL import QOpenGLFramebufferObject

    context = QOpenGLContext()
    requested = QSurfaceFormat()
    requested.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    context.setFormat(requested)
    created = bool(context.create())
    surface = QOffscreenSurface()
    surface.setFormat(context.format())
    surface.create()
    made_current = bool(created and surface.isValid() and context.makeCurrent(surface))
    image_path = root / "native_gl_fbo.png"
    rendered = False
    error = ""
    if made_current:
        try:
            fbo = QOpenGLFramebufferObject(64, 64)
            bound = bool(fbo.bind())
            functions = context.functions()
            functions.glViewport(0, 0, 64, 64)
            functions.glClearColor(0.125, 0.5, 0.875, 1.0)
            functions.glClear(0x00004000)
            image = fbo.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            center = image.pixelColor(32, 32)
            rendered = bool(
                bound
                and not image.isNull()
                and center.blue() > center.red()
                and image.save(str(image_path), "PNG")
            )
            fbo.release()
        except Exception as exc:  # runtime/driver boundary: preserve diagnostic
            error = f"{type(exc).__name__}: {exc}"
        finally:
            context.doneCurrent()
    actual = context.format()
    return {
        "created": created,
        "valid": bool(context.isValid()),
        "surface_valid": bool(surface.isValid()),
        "made_current": made_current,
        "fbo_rendered": rendered,
        "artifact": str(image_path.resolve()) if image_path.is_file() else "",
        "actual_format": {
            "renderable_type": _enum_value(actual.renderableType()),
            "profile": _enum_value(actual.profile()),
            "version": [actual.majorVersion(), actual.minorVersion()],
            "red": actual.redBufferSize(),
            "green": actual.greenBufferSize(),
            "blue": actual.blueBufferSize(),
            "alpha": actual.alphaBufferSize(),
            "depth": actual.depthBufferSize(),
            "stencil": actual.stencilBufferSize(),
            "samples": actual.samples(),
        },
        "error": error,
        "limitations": [
            "This probe proves Qt context creation and FBO readback, not full Painter renderer consumption.",
            "GPU vendor/renderer strings are not claimed when the Qt binding does not expose them reliably.",
        ],
    }


def _text_probe(app, root: Path) -> dict[str, object]:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel

    label = QLabel("브러시 크기 34 px · 불투명도 46% · 레이어")
    label.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    label.setStyleSheet("background:#353535;color:#f4f4f4;padding:12px;font-size:14px")
    label.adjustSize()
    label.show()
    app.processEvents()
    pixmap = label.grab()
    path = root / "native_korean_text.png"
    saved = bool(pixmap.save(str(path), "PNG"))
    row = {
        "saved": saved,
        "logical_size": [label.width(), label.height()],
        "pixel_size": [pixmap.width(), pixmap.height()],
        "device_pixel_ratio": float(pixmap.devicePixelRatio()),
        "artifact": str(path.resolve()) if saved else "",
    }
    label.close()
    return row


def _painter_gpu_path_probe(app, root: Path) -> dict[str, object]:
    """Exercise the same DrawingCanvas paintEvent path used by the product."""
    from PySide6.QtCore import Qt
    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(320, 180, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    dialog.resize(640, 420)
    dialog.show()
    app.processEvents()
    dialog.canvas.add_stroke_direct(Stroke(
        points=[(0.08, 0.2), (0.25, 0.68), (0.48, 0.32), (0.76, 0.74), (0.92, 0.25)],
        color=(34, 145, 238),
        opacity=230,
        width_px=9.0,
        brush_style="round",
        point_pressure=[0.25, 0.5, 0.9, 0.65, 0.35],
    ))
    pixmap = dialog.canvas.grab()
    app.processEvents()
    state = dialog.painter_action_state()["gpu"]["canvas_renderer"]
    path = root / "native_painter_basic_stroke.png"
    saved = bool(pixmap.save(str(path), "PNG"))
    passed = bool(
        saved
        and state.get("active") == "opengl"
        and state.get("renderer") == "painter_canvas_opengl_persistent_stroke_atlas_v1"
        and state.get("source_renderer") == "painter_canvas_opengl_stroke_fbo_v1"
        and state.get("fallback") is False
    )
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
    return {
        "passed": passed,
        "renderer_state": state,
        "saved": saved,
        "artifact": str(path.resolve()) if saved else "",
        "scope": "basic round-stroke DrawingCanvas paintEvent path only",
        "not_proven": [
            "textured brushes",
            "wet canvas",
            "material paint",
            "layer masks",
            "zero-readback retained widget display",
        ],
    }


def _painter_retained_tile_probe(app, root: Path) -> dict[str, object]:
    """Prove retained GL tile handles are consumed into the Canvas raster input."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(512, 256, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    dialog.configure_painter_large_canvas(tile_size=128, tile_budget_mb=16, undo_budget_mb=16)
    source = QImage(512, 256, QImage.Format.Format_ARGB32_Premultiplied)
    source.fill(QColor(16, 32, 64, 255))
    for y in range(32, 224):
        for x in range(48, 464):
            source.setPixelColor(x, y, QColor((x * 3) % 256, (y * 5) % 256, (x + y) % 256, 80 + (x % 176)))
    dialog._set_paint_layer_raster(dialog._active_paint_layer_id, source)
    app.processEvents()
    displayed = dialog.canvas._layer_rasters.get(dialog._active_paint_layer_id, QImage())
    status = dialog.painter_large_canvas_status()
    import numpy as np
    source_rgba = source.convertToFormat(QImage.Format.Format_RGBA8888)
    displayed_rgba = displayed.convertToFormat(QImage.Format.Format_RGBA8888)
    expected = np.frombuffer(bytes(source_rgba.constBits()), dtype=np.uint8).reshape((source.height(), source.width(), 4))
    actual = np.frombuffer(bytes(displayed_rgba.constBits()), dtype=np.uint8).reshape((source.height(), source.width(), 4))
    variants = {
        "direct": actual,
        "flip_y": np.flipud(actual),
        "flip_x": np.fliplr(actual),
        "flip_xy": np.flipud(np.fliplr(actual)),
    }
    deltas = {name: int(np.abs(expected.astype(np.int16) - row.astype(np.int16)).max()) for name, row in variants.items()}
    expected_pm = expected.astype(np.int32)
    actual_pm = actual.astype(np.int32)
    expected_pm[..., :3] = (expected_pm[..., :3] * expected_pm[..., 3:4] + 127) // 255
    actual_pm[..., :3] = (actual_pm[..., :3] * actual_pm[..., 3:4] + 127) // 255
    premultiplied_delta = int(np.abs(expected_pm - actual_pm).max())
    alpha_delta = int(np.abs(expected[..., 3].astype(np.int16) - actual[..., 3].astype(np.int16)).max())
    parity = bool(premultiplied_delta <= 1 and alpha_delta == 0)
    path = root / "native_painter_retained_tiles.png"
    saved = bool(not displayed.isNull() and displayed.save(str(path), "PNG"))
    display = dict(status.get("display") or {})
    gpu = dict(status.get("gpu") or {})
    passed = bool(
        parity and saved
        and int(display.get("gpu_tile_calls", 0)) >= 1
        and int(gpu.get("display_texture_reads", 0)) >= 8
        and str((display.get("last") or {}).get("renderer")) == "painter_retained_gl_tile_display_v1"
    )
    dialog.close(); dialog.deleteLater(); app.processEvents()
    return {
        "passed": passed,
        "pixel_parity": parity,
        "pixel_max_deltas": deltas,
        "premultiplied_max_delta": premultiplied_delta,
        "alpha_max_delta": alpha_delta,
        "saved": saved,
        "artifact": str(path.resolve()) if saved else "",
        "display": display,
        "gpu": gpu,
        "tiles": dict(status.get("tiles") or {}),
        "scope": "512x256 complete retained tile set through PaintDialog Canvas input",
        "not_proven": ["zero-readback display", "8K budget", "advanced blend modes"],
    }


def main() -> int:
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication
    from app.painter_evidence_contract import evidence_record
    from app.painter_native_environment import (
        environment_overrides,
        is_native_qt_environment,
        korean_font_measurement,
        pointing_device_inventory,
        runtime_identity,
        screen_measurements,
    )

    app = QApplication.instance() or QApplication([])
    root = ROOT / "debugCapture" / "painter" / "native_environment"
    root.mkdir(parents=True, exist_ok=True)
    overrides = environment_overrides()
    platform_name = QGuiApplication.platformName()
    native = is_native_qt_environment(platform_name, overrides)
    screens = screen_measurements(app)
    high_dpi = bool(native and any(row["device_pixel_ratio"] > 1.0 for row in screens))
    font = korean_font_measurement(app)
    text_probe = _text_probe(app, root)
    gl = _opengl_probe(root)
    context_passed = bool(native and gl["valid"] and gl["made_current"] and gl["fbo_rendered"])
    painter_gpu = _painter_gpu_path_probe(app, root)
    retained_tiles = _painter_retained_tile_probe(app, root)
    painter_gpu_path_passed = bool(native and context_passed and painter_gpu["passed"])
    retained_tile_path_passed = bool(native and context_passed and retained_tiles["passed"])
    artifacts = [
        path for path in (text_probe["artifact"], gl["artifact"], painter_gpu["artifact"], retained_tiles["artifact"]) if path
    ]
    provenance = [
        evidence_record(
            "native-high-dpi-runtime",
            "native_runtime",
            passed=high_dpi and font["all_glyphs_supported"] and text_probe["saved"],
            producer="tools/qa_painter_native_environment.py",
            claims=("native_high_dpi",),
            command="python tools/qa_painter_native_environment.py",
            environment={"platform": platform_name, "overrides": overrides, "screens": screens},
            artifacts=[text_probe["artifact"]] if text_probe["artifact"] else (),
            limitations=("Requires an actual screen with devicePixelRatio > 1.0.",),
        ),
        evidence_record(
            "native-retained-tile-display",
            "native_runtime",
            passed=retained_tile_path_passed,
            producer="tools/qa_painter_native_environment.py",
            claims=("retained_gpu_tile_display_consumption",),
            command="python tools/qa_painter_native_environment.py",
            environment={"platform": platform_name, "overrides": overrides},
            artifacts=[retained_tiles["artifact"]] if retained_tiles["artifact"] else (),
            limitations=("The current GL tile display performs a full-frame readback.",),
        ),
        evidence_record(
            "native-opengl-fbo",
            "native_runtime",
            passed=painter_gpu_path_passed,
            producer="tools/qa_painter_native_environment.py",
            claims=("basic_stroke_gpu_path",),
            command="python tools/qa_painter_native_environment.py",
            environment={"platform": platform_name, "overrides": overrides},
            artifacts=[path for path in (gl["artifact"], painter_gpu["artifact"]) if path],
            limitations=tuple(gl["limitations"]) + (
                "The claim is limited to the basic round-stroke DrawingCanvas path.",
            ),
        ),
    ]
    report = {
        "schema": "tigerstudio.painter.native-environment-qa.v1",
        "classification": "native_runtime" if native else "simulated_environment",
        "native_environment": native,
        "runtime": runtime_identity(),
        "qt_platform": platform_name,
        "environment_overrides": overrides,
        "screens": screens,
        "korean_font": font,
        "text_probe": text_probe,
        "opengl": {**gl, "context_probe_passed": context_passed},
        "painter_gpu": painter_gpu,
        "retained_tiles": retained_tiles,
        "pointing_devices": pointing_device_inventory(),
        "physical_tablet_input_captured": False,
        "provenance": provenance,
        "passed": bool(high_dpi and painter_gpu_path_passed and retained_tile_path_passed and font["all_glyphs_supported"]),
        "artifacts": artifacts,
    }
    destination = root / "report.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "report": str(destination.resolve()),
        "native": native,
        "high_dpi": high_dpi,
        "korean": font["all_glyphs_supported"],
        "opengl_context": context_passed,
        "painter_gpu_path": painter_gpu_path_passed,
        "retained_tile_path": retained_tile_path_passed,
        "pointing_devices": len(report["pointing_devices"]),
        "passed": report["passed"],
    }, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
