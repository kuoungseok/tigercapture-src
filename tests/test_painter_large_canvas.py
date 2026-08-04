from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _image(width: int, height: int, color: int = 0xFF315A89):
    from PySide6.QtGui import QImage
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color); return image


def test_dirty_rect_uploads_only_intersecting_tiles_and_reconstructs() -> None:
    from app.painter_large_canvas import RetainedTileCache

    source = _image(1024, 768)
    cache = RetainedTileCache(tile_size=256, budget_bytes=32 * 1024 * 1024)
    initial = cache.update_layer("paint", source)
    assert initial["updated_tiles"] == 12
    changed = source.copy(); changed.setPixelColor(300, 300, 0xFFFF4411)
    delta = cache.update_layer("paint", changed, dirty_rect=(296, 296, 16, 16))
    assert delta["updated_tiles"] == 1
    assert cache.reconstruct("paint") == changed
    assert cache.telemetry()["bounded"] is True


def test_retained_gpu_uploader_reuses_handle_and_falls_back_on_failure() -> None:
    from app.painter_large_canvas import RetainedTileCache

    calls = []
    def upload(key, image, old):
        calls.append((key, old)); return old or len(calls) + 100
    cache = RetainedTileCache(tile_size=256, budget_bytes=4 * 1024 * 1024, gpu_uploader=upload)
    cache.update_layer("layer", _image(256, 256))
    cache.update_layer("layer", _image(256, 256, 0xFF884422), dirty_rect=(4, 4, 4, 4))
    assert calls[0][1] == 0 and calls[1][1] == 101
    assert cache.telemetry()["gpu_tile_count"] == 1
    assert cache.backend == "retained_gpu_texture_tiles"

    def fail(*_args): raise RuntimeError("context lost")
    fallback = RetainedTileCache(gpu_uploader=fail)
    fallback.update_layer("layer", _image(64, 64))
    assert fallback.backend == "bounded_qimage_tile_fallback"
    assert fallback.telemetry()["gpu_failures"] == 1
    assert fallback.telemetry()["last_gpu_error"] == "RuntimeError: context lost"

    class LostContext:
        closed = False
        def __call__(self, *_args): raise RuntimeError("lost")
        def telemetry(self): return {"active": True, "textures": 9, "fbo": True}
        def close(self): self.closed = True
    from app.painter_large_canvas import LargeCanvasRuntime
    owner = LostContext(); runtime = LargeCanvasRuntime(gpu_uploader=owner)
    runtime.update_layer("layer", _image(64, 64))
    lost = runtime.telemetry()
    assert lost["cpu_fallback"] is True
    assert lost["gpu"]["active"] is False
    assert owner.closed is True

    class MidLoss(LostContext):
        calls = 0
        def __call__(self, _key, _image, old):
            self.calls += 1
            if self.calls == 3: raise RuntimeError("lost after partial upload")
            return old or self.calls
    partial_owner = MidLoss(); partial = LargeCanvasRuntime(tile_size=64, gpu_uploader=partial_owner)
    partial.update_layer("layer", _image(192, 64))
    partial_status = partial.telemetry()
    assert partial_status["tiles"]["tile_count"] == 3
    assert partial_status["tiles"]["gpu_tile_count"] == 0
    assert partial_status["gpu"]["active"] is False and partial_status["cpu_fallback"] is True


def test_gpu_compositor_failures_are_typed_before_qimage_fallback() -> None:
    from app.painter_large_canvas import LargeCanvasRuntime

    class BrokenCompositor:
        closed = False

        def __call__(self, _key, _image, old):
            return old or 17

        def composite_tile_records(self, *_args):
            raise RuntimeError("tile compositor context lost")

        def composite_normal_layers(self, *_args):
            raise RuntimeError("normal compositor context lost")

        def close(self):
            self.closed = True

        def telemetry(self):
            return {"active": not self.closed}

    source = _image(64, 64)
    tile_owner = BrokenCompositor()
    tile_runtime = LargeCanvasRuntime(
        tile_size=64, gpu_uploader=tile_owner
    )
    tile_runtime.update_layer("paint", source)
    assert tile_runtime.render_layer_image("paint", source) == source
    tile_status = tile_runtime.telemetry()
    assert tile_status["tiles"]["last_gpu_error"] == (
        "RuntimeError: tile compositor context lost"
    )
    assert tile_status["cpu_fallback"] is True
    assert tile_status["display"]["last"]["fallback_reason"] == (
        "RuntimeError: tile compositor context lost"
    )

    normal_owner = BrokenCompositor()
    normal_runtime = LargeCanvasRuntime(
        tile_size=64, gpu_uploader=normal_owner
    )
    output, report = normal_runtime.composite_normal_layers(
        [(source, 1.0)], 64, 64
    )
    assert not output.isNull()
    assert report["fallback"] is True
    assert report["reason"] == "RuntimeError: normal compositor context lost"
    normal_status = normal_runtime.telemetry()
    assert normal_status["tiles"]["last_gpu_error"] == (
        "RuntimeError: normal compositor context lost"
    )
    assert normal_status["cpu_fallback"] is True


def test_gpu_cleanup_failures_are_typed_after_handles_are_invalidated() -> None:
    from app.painter_large_canvas import LargeCanvasRuntime, RetainedTileCache

    def upload(_key, _image, old):
        return old or 23

    def fail_delete(_handle):
        raise RuntimeError("injected texture delete failure")

    cache = RetainedTileCache(
        tile_size=64,
        gpu_uploader=upload,
        gpu_deleter=fail_delete,
    )
    cache.update_layer("paint", _image(64, 64))
    assert cache.remove_layer("paint") == 1
    status = cache.telemetry()
    assert status["tile_count"] == 0
    assert status["gpu_tile_count"] == 0
    assert status["gpu_cleanup_failures"] == 1
    assert status["last_gpu_cleanup_error"] == (
        "RuntimeError: injected texture delete failure"
    )

    class BrokenOwner:
        def __call__(self, *_args):
            raise RuntimeError("injected upload failure")

        def close(self):
            raise RuntimeError("injected owner close failure")

        def telemetry(self):
            return {"active": True}

    runtime = LargeCanvasRuntime(gpu_uploader=BrokenOwner())
    runtime.update_layer("paint", _image(64, 64))
    runtime_status = runtime.telemetry()
    assert runtime_status["cpu_fallback"] is True
    assert runtime_status["gpu"]["active"] is False
    assert runtime_status["gpu"]["cleanup_error"] == (
        "RuntimeError: injected owner close failure"
    )


def test_canvas_gpu_failures_select_qpainter_and_expose_reason(monkeypatch) -> None:
    import builtins
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication
    from app.drawing import DrawingCanvas, Stroke

    app = QApplication.instance() or QApplication([])
    canvas = DrawingCanvas(lambda: 0, lambda: [])
    stroke = Stroke(points=[(0.1, 0.5), (0.9, 0.5)], width_px=8)
    target = QImage(96, 64, QImage.Format.Format_ARGB32_Premultiplied)
    target.fill(Qt.GlobalColor.transparent)
    painter = QPainter(target)
    original_import = builtins.__import__

    def fail_painter_gl(name, *args, **kwargs):
        if name == "app.painter_opengl":
            raise ModuleNotFoundError("injected canvas OpenGL absence")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_painter_gl)
    try:
        assert canvas._paint_strokes_with_gpu_cache(
            painter, [stroke], 96, 64, 0
        ) is False
    finally:
        painter.end()
    status = canvas._painter_canvas_renderer_status
    assert status["active"] == "qpainter"
    assert status["renderer"] == "painter_canvas_qpainter_strokes_v1"
    assert status["reason"] == (
        "ModuleNotFoundError: injected canvas OpenGL absence"
    )
    canvas.deleteLater(); app.processEvents()


def test_large_canvas_gpu_creation_failure_is_exposed(monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication
    from app import painter_opengl
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])

    class BrokenUploader:
        def __init__(self):
            raise RuntimeError("injected retained uploader creation failure")

    monkeypatch.setattr(painter_opengl, "PainterRetainedGLTileUploader", BrokenUploader)
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(96, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    status = dialog._painter_large_canvas_runtime_instance().telemetry()
    assert status["cpu_fallback"] is True
    assert status["gpu"]["active"] is False
    assert status["gpu"]["creation_error"] == (
        "RuntimeError: injected retained uploader creation failure"
    )
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_null_gpu_compositor_result_falls_back_and_close_failure_is_typed() -> None:
    from PySide6.QtGui import QImage
    from app.painter_large_canvas import LargeCanvasRuntime

    class NullOwner:
        def __call__(self, _key, _image, old):
            return old or 41

        def composite_tile_records(self, *_args):
            return QImage(), {"renderer": "broken_null_gpu"}

        def close(self):
            raise RuntimeError("injected normal close failure")

        def telemetry(self):
            return {"active": True}

    owner = NullOwner()
    runtime = LargeCanvasRuntime(tile_size=64, gpu_uploader=owner)
    source = _image(64, 64)
    runtime.update_layer("paint", source)
    assert runtime.render_layer_image("paint", source) == source
    status = runtime.telemetry()
    assert status["cpu_fallback"] is True
    assert status["display"]["last"]["backend"] == "retained_qimage_tile_display"
    assert "invalid image" in status["tiles"]["last_gpu_error"]

    second = LargeCanvasRuntime(tile_size=64, gpu_uploader=NullOwner())
    second.update_layer("paint", source)
    second.close()
    close_status = second.telemetry()
    assert close_status["cpu_fallback"] is True
    assert close_status["gpu"]["active"] is False
    assert close_status["gpu"]["cleanup_error"] == (
        "RuntimeError: injected normal close failure"
    )


def test_tile_lru_and_async_material_queue_are_bounded() -> None:
    from app.painter_large_canvas import DirtyMaterialTileQueue, RetainedTileCache

    cache = RetainedTileCache(tile_size=64, budget_bytes=64 * 64 * 4 * 2)
    cache.update_layer("layer", _image(256, 64))
    status = cache.telemetry()
    assert status["tile_count"] == 2 and status["evictions"] == 2 and status["bounded"]
    queue = DirtyMaterialTileQueue(max_tasks=5)
    queue.schedule(("height", "normal", "ao"), ((0, 0), (1, 0), (2, 0)))
    queue.schedule(("height",), ((2, 0),))
    assert queue.telemetry() == {"queued": 5, "max_tasks": 5, "dropped": 5, "bounded": True}
    rows = queue.drain(lambda kind, tx, ty: (kind, tx, ty), limit=3)
    assert len(rows) == 3 and queue.telemetry()["queued"] == 2


def test_undo_memory_budget_prunes_old_full_snapshots() -> None:
    from app.painter_large_canvas import UndoMemoryBudget

    stack = [{"raster": _image(1024, 1024, 0xFF000000 + index)} for index in range(4)]
    labels = [f"Edit {index}" for index in range(4)]
    budget = UndoMemoryBudget(6 * 1024 * 1024)
    report = budget.enforce(stack, labels)
    assert len(stack) == len(labels) == 1
    assert labels == ["Edit 3"]
    assert report["bounded"] and report["evicted_states"] == 3
    assert budget.telemetry()["state_count"] == len(stack)
    assert budget.telemetry()["accounting"] == "owned_logical_history_payload_bytes"
    assert budget.telemetry()["process_memory_claim"] is False


def test_history_payload_measurement_uses_actual_qimage_and_python_sizes() -> None:
    from dataclasses import dataclass
    from app.painter_large_canvas import measure_history_payload_bytes

    image = _image(13, 7)
    assert measure_history_payload_bytes(image) >= image.sizeInBytes()

    @dataclass
    class Payload:
        values: list[int]

    small = measure_history_payload_bytes(Payload([1]))
    large = measure_history_payload_bytes(Payload(list(range(1000))))
    assert large > small


def test_large_canvas_runtime_schedules_material_and_wet_tiles() -> None:
    from app.painter_large_canvas import LargeCanvasRuntime

    runtime = LargeCanvasRuntime(tile_size=256, tile_budget_mb=8, undo_budget_mb=8)
    report = runtime.update_layer("material", _image(1024, 1024), dirty_rect=(250, 250, 20, 20), material=True, wet=True)
    assert report["updated_tiles"] == 4
    assert runtime.material_tasks.telemetry()["queued"] == 16
    runtime.cache_brush_stamp("bristle-oil", _image(128, 128))
    runtime.update_material_map("normal", _image(1024, 1024), dirty_rect=(250, 250, 20, 20))
    status = runtime.telemetry()
    assert status["tiles"]["bounded"] and status["material_tasks"]["bounded"] and status["remote_safe"]
    assert status["brush_stamp_atlas"]["tile_count"] == 1
    assert status["material_map_tiles"]["tile_count"] == 4
    assert runtime.material_executor.wait(5.0) is True
    executor = runtime.telemetry()["material_executor"]
    assert executor["submitted"] == 4 and executor["completed"] == 4
    assert executor["failed"] == 0 and executor["bounded"] is True
    assert status["wet_canvas_tiles"]["tile_count"] == 3
    assert status["wet_canvas_tiles"]["evictions"] == 1
    assert status["compositor"]["silent_fallback"] is False
    bottom = _image(64, 64, 0xFF204060); top = _image(64, 64, 0x80FF4000)
    composed, compositor = runtime.composite_normal_layers([(bottom, 1.0), (top, 0.5)], 64, 64)
    assert not composed.isNull()
    assert compositor["renderer"] == "painter_qpainter_normal_compositor_v1"
    assert compositor["fallback"] is True
    runtime.close()


def test_material_tile_executor_rejects_stale_and_cancelled_revisions() -> None:
    import time
    from app.painter_large_canvas import MaterialTileExecutor

    def slow(kind, tx, ty, revision, payload, width, height):
        time.sleep(0.02)
        return {"kind": kind, "tx": tx, "ty": ty, "revision": revision, "bytes": len(payload), "width": width, "height": height}

    executor = MaterialTileExecutor(max_workers=1, processor=slow)
    image = _image(128, 64)
    first = executor.submit_image("normal", image, ((0, 0), (1, 0)), 64)
    second = executor.submit_image("normal", image, ((0, 0),), 64)
    assert second["revision"] == first["revision"] + 1
    assert executor.wait(5.0) is True
    status = executor.telemetry()
    assert status["stale"] == 2 and status["completed"] == 1
    executor.submit_image("ao", image, ((0, 0),), 64)
    executor.cancel_kind("ao")
    assert executor.wait(5.0) is True
    assert executor.telemetry()["stale"] >= 3
    executor.close()


def test_material_tile_executor_exposes_bounded_failure_causes() -> None:
    from app.painter_large_canvas import MaterialTileExecutor

    def fail(kind, tx, ty, revision, payload, width, height):
        raise RuntimeError(f"decode failed for {kind}:{tx},{ty}@{revision}")

    executor = MaterialTileExecutor(max_workers=1, processor=fail)
    executor.submit_image("normal", _image(64, 64), ((0, 0),), 64)
    assert executor.wait(5.0) is True
    status = executor.telemetry()
    assert status["failed"] == 1
    assert len(status["recent_errors"]) == 1
    error = status["recent_errors"][0]
    assert error["type"] == "RuntimeError"
    assert "decode failed" in error["message"]
    assert error["kind"] == "normal"
    assert error["tile"] == [0, 0]
    assert error["revision"] == 1
    assert status["completed"] == 0
    assert status["error_capacity"] >= len(status["recent_errors"])
    executor.close()


def test_canvas_runtime_sync_failure_is_exposed_and_success_clears_it() -> None:
    from PySide6.QtWidgets import QApplication
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(96, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )

    class BrokenRuntime:
        def sync_layer_images(self, _images):
            raise RuntimeError("retained tile synchronization failed")

    dialog._painter_large_canvas_runtime = BrokenRuntime()
    dialog._sync_canvas_layer_view()
    assert dialog._painter_large_canvas_view_sync_error == (
        "RuntimeError: retained tile synchronization failed"
    )
    assert dialog._painter_operational_errors["canvas_layer_view"] == (
        "RuntimeError: retained tile synchronization failed"
    )

    dialog._painter_large_canvas_runtime = None
    dialog._sync_canvas_layer_view()
    assert dialog._painter_large_canvas_view_sync_error == ""
    assert dialog.painter_action_state()["operational_errors"]["canvas_layer_view"] == ""
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_pbr_material_cache_failure_is_exposed_and_success_clears_it(monkeypatch) -> None:
    from PIL import Image
    from PySide6.QtWidgets import QApplication

    from app.ar_pbr import texture_map_lab
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(32, 24, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._pbr_source_image = lambda **_kwargs: (
        Image.new("RGBA", (8, 8), (64, 96, 128, 255)),
        {"width": 8, "height": 8, "source_width": 8, "fingerprint": "test"},
    )
    monkeypatch.setattr(
        texture_map_lab,
        "generate_texture_maps_from_image",
        lambda *_args, **_kwargs: {"maps": {"height": object()}},
    )
    monkeypatch.setattr(
        texture_map_lab,
        "texture_map_settings_fingerprint",
        lambda _settings: "settings",
    )
    monkeypatch.setattr(
        texture_map_lab,
        "texture_map_to_image",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("material cache upload failed")),
    )
    dialog._pbr_preview_generated_maps(max_size=8, settings={}, allow_cpu=True)
    assert dialog.painter_action_state()["operational_errors"]["pbr_material_cache"] == (
        "RuntimeError: material cache upload failed"
    )

    dialog._pbr_preview_maps_cache = None
    monkeypatch.setattr(
        texture_map_lab,
        "texture_map_to_image",
        lambda *_args, **_kwargs: Image.new("RGBA", (8, 8), (0, 0, 0, 255)),
    )
    dialog._pbr_preview_generated_maps(max_size=8, settings={}, allow_cpu=True)
    assert dialog.painter_action_state()["operational_errors"]["pbr_material_cache"] == ""
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_brush_material_profile_failure_is_exposed_and_success_clears_it(monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication

    import app.painter_material_paint as material_paint
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(32, 24, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    preset = {"name": "Failure Probe", "width": 8, "opacity": 100, "style": "round"}
    monkeypatch.setattr(
        material_paint,
        "brush_material_capability",
        lambda _style: (_ for _ in ()).throw(RuntimeError("material profile lookup failed")),
    )
    dialog._apply_brush_library_preset(preset)
    assert dialog.painter_action_state()["operational_errors"]["brush_material_profile"] == (
        "RuntimeError: material profile lookup failed"
    )

    monkeypatch.setattr(
        material_paint,
        "brush_material_capability",
        lambda _style: {"compatible": False},
    )
    dialog._apply_brush_library_preset(preset)
    assert dialog.painter_action_state()["operational_errors"]["brush_material_profile"] == ""
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_optional_painter_feature_failures_are_typed_and_preserve_document_state(monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication

    import app.painter_opengl as painter_opengl
    import app.painter_reference_board as reference_board
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_3d_blockout import default_blockout_scene

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 48, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    original_layers = [
        (layer.layer_id, layer.name, layer.visible, layer.opacity)
        for layer in dialog._paint_layers
    ]
    original_palette = list(dialog._document_palette_colors)

    class FailedFuture:
        def done(self):
            return True

        def result(self):
            raise RuntimeError("wet worker failed exactly")

    dialog.canvas._wet_canvas_future = FailedFuture()
    dialog.canvas._wet_canvas_future_layer = dialog._active_paint_layer_id
    dialog.canvas._poll_wet_canvas_future()
    assert dialog.canvas._wet_canvas_reports[dialog._active_paint_layer_id]["reason"] == (
        "RuntimeError: wet worker failed exactly"
    )

    monkeypatch.setattr(
        PaintDialog,
        "_selected_reference_payload",
        lambda _self: {"path": "missing-reference.png"},
    )
    monkeypatch.setattr(
        reference_board,
        "sample_reference_color",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("sample decode failed exactly")),
    )
    dialog._sample_selected_reference_color()
    assert dialog.painter_action_state()["operational_errors"]["reference_color_sample"] == (
        "OSError: sample decode failed exactly"
    )
    assert "sample decode failed exactly" in dialog._tool_status_label.text()

    monkeypatch.setattr(
        reference_board,
        "extract_reference_palette",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("palette decode failed exactly")),
    )
    dialog._extract_selected_reference_palette()
    assert dialog.painter_action_state()["operational_errors"]["reference_palette_extract"] == (
        "ValueError: palette decode failed exactly"
    )
    assert "palette decode failed exactly" in dialog._tool_status_label.text()
    assert dialog._document_palette_colors == original_palette

    monkeypatch.setattr(
        painter_opengl,
        "render_blockout_scene_opengl_qimage",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("GL preview failed exactly")),
    )
    pixmap = dialog._render_3d_blockout_pixmap(
        default_blockout_scene(),
        64,
        48,
        include_gizmo=False,
    )
    assert not pixmap.isNull()
    assert dialog._painter_3d_blockout_renderer_status["fallback"] is True
    assert dialog.painter_action_state()["operational_errors"]["blockout_opengl_preview"] == (
        "RuntimeError: GL preview failed exactly"
    )

    monkeypatch.setattr(
        dialog,
        "_pbr_preview_generated_maps",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("PBR preview failed exactly")),
    )
    dialog._refresh_pbr_texture_preview()
    assert dialog.painter_action_state()["operational_errors"]["pbr_texture_preview"] == (
        "RuntimeError: PBR preview failed exactly"
    )

    dialog._painter_recovery_future = FailedFuture()
    dialog._painter_recovery_observed_future = None
    recovery = dialog._observe_painter_recovery_writer()
    assert recovery["last_error"] == "RuntimeError: wet worker failed exactly"
    assert recovery["last_error_detail"]["type"] == "RuntimeError"
    assert recovery["last_error_detail"]["message"] == "wet worker failed exactly"
    assert [
        (layer.layer_id, layer.name, layer.visible, layer.opacity)
        for layer in dialog._paint_layers
    ] == original_layers

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_parent_and_resource_cleanup_failures_preserve_primary_state(monkeypatch, tmp_path) -> None:
    from pathlib import Path

    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QApplication, QMessageBox

    import app.ar_pbr.texture_map_lab_window as texture_lab_window
    import app.background_removal as background_removal
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 48, "#336699"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    monkeypatch.setattr(dialog, "_available_painter_geometry", lambda _parent=None: QRect(0, 0, 800, 600))

    class InvalidParent:
        def window(self):
            raise RuntimeError("parent wrapper destroyed exactly")

    dialog._configure_initial_painter_window_size(InvalidParent())
    assert dialog.painter_action_state()["operational_errors"]["initial_window_parent_geometry"] == (
        "RuntimeError: parent wrapper destroyed exactly"
    )

    class PreviousRuntime:
        def close(self):
            raise OSError("previous runtime close failed exactly")

    dialog._painter_large_canvas_runtime = PreviousRuntime()
    large_canvas = dialog.configure_painter_large_canvas(
        tile_size=256,
        tile_budget_mb=64,
        undo_budget_mb=64,
    )
    assert large_canvas["gpu"]["cleanup_error"] == "OSError: previous runtime close failed exactly"
    assert dialog.painter_action_state()["operational_errors"]["large_canvas_previous_cleanup"] == (
        "OSError: previous runtime close failed exactly"
    )

    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: warnings.append(str(_args[-1])))

    class Signal:
        def connect(self, _callback):
            return None

    class NewTextureWindow:
        destroyed = Signal()

        def __init__(self, *_args):
            self.destroyed = Signal()

        def setAttribute(self, *_args):
            return None

        def show(self):
            return None

        def raise_(self):
            return None

        def activateWindow(self):
            return None

    class PreviousTextureWindow:
        def close(self):
            raise RuntimeError("previous texture window close failed exactly")

    monkeypatch.setattr(texture_lab_window, "ArPbrTextureMapLabWindow", NewTextureWindow)
    monkeypatch.setattr(
        dialog,
        "_write_pbr_source_image",
        lambda: {"pbr_source_path": str(tmp_path / "source.png")},
    )
    dialog._pbr_texture_lab_window = PreviousTextureWindow()
    dialog._open_pbr_texture_lab_window()
    assert dialog.painter_action_state()["operational_errors"]["pbr_texture_lab_previous_close"] == (
        "RuntimeError: previous texture window close failed exactly"
    )
    assert dialog.painter_action_state()["operational_errors"]["pbr_texture_lab_open"] == ""

    monkeypatch.setattr(
        dialog,
        "_write_pbr_source_image",
        lambda: (_ for _ in ()).throw(ValueError("PBR source failed exactly")),
    )
    dialog._open_pbr_texture_lab_window()
    assert dialog.painter_action_state()["operational_errors"]["pbr_texture_lab_open"] == (
        "ValueError: PBR source failed exactly"
    )
    assert "ValueError: PBR source failed exactly" in warnings[-1]

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        background_removal.BackgroundRemovalParams,
        "_get_mask",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("cutout segmentation failed exactly")),
    )
    original_unlink = Path.unlink

    def fail_cutout_cleanup(path, *args, **kwargs):
        if path.name.startswith("cutout_source_"):
            raise OSError("temporary unlink failed exactly")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_cutout_cleanup)
    sticker_count = len(dialog._stickers)
    dialog._create_cutout_sticker()
    state = dialog.painter_action_state()["operational_errors"]
    assert state["cutout_operation"] == "RuntimeError: cutout segmentation failed exactly"
    assert "OSError: temporary unlink failed exactly" in state["cutout_temporary_cleanup"]
    assert "RuntimeError: cutout segmentation failed exactly" in warnings[-1]
    assert len(dialog._stickers) == sticker_count

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_complete_retained_tiles_are_consumed_by_display_and_incomplete_cache_falls_back() -> None:
    from PySide6.QtGui import QPainter
    from app.painter_large_canvas import LargeCanvasRuntime

    class DisplayOwner:
        def __init__(self):
            self.next_handle = 1
            self.display_calls = 0
        def __call__(self, _key, _image, old):
            if old:
                return old
            value = self.next_handle
            self.next_handle += 1
            return value
        def delete(self, _handle):
            return None
        def composite_tile_records(self, records, width, height, tile_size):
            self.display_calls += 1
            result = _image(width, height, 0)
            result.fill(0)
            painter = QPainter(result)
            for tx, ty, record in records:
                painter.drawImage(tx * tile_size, ty * tile_size, record.image)
            painter.end()
            return result, {"renderer": "test_gpu_tile_consumer", "tile_texture_reads": len(records)}
        def telemetry(self):
            return {"active": True, "display_calls": self.display_calls}

    source = _image(256, 128, 0xFF336699)
    source.setPixelColor(130, 70, 0xFFFF3311)
    owner = DisplayOwner()
    runtime = LargeCanvasRuntime(tile_size=64, tile_budget_mb=8, gpu_uploader=owner, gpu_deleter=owner.delete)
    runtime.update_layer("paint", source)
    rendered = runtime.render_layer_image("paint", source)
    assert rendered == source
    status = runtime.telemetry()
    assert status["display"]["gpu_tile_calls"] == 1
    assert status["tiles"]["display_reads"] == 8
    assert owner.display_calls == 1

    tiny = LargeCanvasRuntime(tile_size=64, tile_budget_mb=3)
    tiny.tiles.budget_bytes = 64 * 64 * 4
    tiny.update_layer("paint", source)
    fallback = tiny.render_layer_image("paint", source)
    assert fallback == source
    assert tiny.telemetry()["display"]["source_fallbacks"] == 1
    assert tiny.telemetry()["display"]["last"]["complete_tiles"] is False


def test_shared_tile_policy_reaches_caches_gpu_compositor_capabilities_and_telemetry() -> None:
    from PySide6.QtGui import QImage

    from app.painter_large_canvas import (
        DEFAULT_TILE_SIZE,
        MAX_TILE_SIZE,
        MIN_TILE_SIZE,
        LargeCanvasRuntime,
    )
    from app.painter_opengl import painter_canvas_gpu_capabilities

    class TileConsumer:
        def __init__(self):
            self.composite_tile_size = None

        def __call__(self, _key, _image, old):
            return old or 1

        def delete(self, _handle):
            return None

        def composite_tile_records(self, records, width, height, tile_size):
            self.composite_tile_size = tile_size
            result = QImage(width, height, QImage.Format_ARGB32)
            result.fill(0)
            return result, {"renderer": "tile-policy-probe", "tile_texture_reads": len(records)}

        def telemetry(self):
            return {"active": True}

    owner = TileConsumer()
    runtime = LargeCanvasRuntime(
        tile_size=64,
        tile_budget_mb=8,
        gpu_uploader=owner,
        gpu_deleter=owner.delete,
    )
    source = _image(128, 64, 0xFF336699)
    runtime.update_layer("paint", source)
    runtime.render_layer_image("paint", source)

    status = runtime.telemetry()
    assert runtime.tiles.tile_size == 64
    assert runtime.brush_stamps.tile_size == 64
    assert runtime.material_maps.tile_size == 64
    assert runtime.wet_canvas.tile_size == 64
    assert owner.composite_tile_size == 64
    assert status["tiles"]["tile_size"] == 64
    capabilities = painter_canvas_gpu_capabilities()["retained_document_tiles"]
    assert capabilities["tile_size"] == DEFAULT_TILE_SIZE
    assert capabilities["default_tile_size"] == DEFAULT_TILE_SIZE
    assert capabilities["supported_tile_size"] == [MIN_TILE_SIZE, MAX_TILE_SIZE]
    assert capabilities["runtime_tile_size_forwarded_to_compositor"] is True


def test_dialog_4k_dirty_tile_and_action_telemetry() -> None:
    from PySide6.QtWidgets import QApplication
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(background_pixmap=create_blank_paint_pixmap(3840, 2160, "transparent"), initial_strokes=[], time_ms=0, standalone=True)
    dialog.configure_painter_large_canvas(tile_size=256, tile_budget_mb=64, undo_budget_mb=64)
    image = _image(3840, 2160)
    started = time.perf_counter(); dialog._set_paint_layer_raster(dialog._active_paint_layer_id, image)
    initial_ms = (time.perf_counter() - started) * 1000
    before = dialog.painter_large_canvas_status()["tiles"]["uploaded_tiles"]
    image.setPixelColor(1900, 1000, 0xFFFFAA22)
    dialog._set_paint_layer_raster(dialog._active_paint_layer_id, image, dirty_rect=(1896, 996, 12, 12))
    update = dialog.painter_large_canvas_status()["last_update"]
    status = dialog.painter_large_canvas_status()
    assert update["updated_tiles"] == 1
    assert status["tiles"]["uploaded_tiles"] == before + 1
    assert status["tiles"]["bytes"] <= status["tiles"]["budget_bytes"]
    assert status["budget_plan"]["required_main_tile_bytes"] == 3840 * 2160 * 4
    assert status["budget_plan"]["performance_threshold_claim"] is False
    assert initial_ms >= 0.0
    assert status["resource_policy_contract"]["performance_threshold_claim"] is False
    assert status["resource_policy_contract"]["universal_memory_safety_claim"] is False
    ids = {row["id"] for row in ActionRegistry(owner=dialog).list_actions()}
    assert {"paint.performance.status", "paint.performance.configure"} <= ids
    dialog.close(); app.processEvents()


def test_large_canvas_visual_gate_rejects_solid_and_accepts_spatial_pattern() -> None:
    from PySide6.QtGui import QColor, QImage
    from tools.qa_painter_large_canvas_runtime import _patterned_layer, _visual_content_metrics

    solid = QImage(512, 288, QImage.Format.Format_RGBA8888)
    solid.fill(QColor(59, 73, 86, 255))
    assert _visual_content_metrics(solid)["spatially_varied"] is False

    patterned = _patterned_layer(512, 288, 0)
    metrics = _visual_content_metrics(patterned)
    assert metrics["spatially_varied"] is True
    assert metrics["variation_contract"] == "sampled_nonuniformity_fact_not_quality_threshold"
    assert metrics["unique_sample_colors"] >= 16
