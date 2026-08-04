from __future__ import annotations

import os

import pytest


_APP = None


def _app():
    global _APP
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    _APP = QApplication.instance() or QApplication([])
    return _APP


def _dialog(size: int = 64):
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    return PaintDialog(
        background_pixmap=create_blank_paint_pixmap(size, size, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )


@pytest.mark.parametrize("invalid_size", [(0, 64), (19.9, 64), (True, 64)])
def test_history_restore_rejects_invalid_dimensions_before_mutating_state(
    invalid_size,
) -> None:
    app = _app()
    dialog = _dialog()
    original_size = dialog._canvas_document_size
    original_layer_ids = [layer.layer_id for layer in dialog._paint_layers]
    original_active_id = dialog._active_paint_layer_id
    snapshot = list(dialog._snapshot_state())
    snapshot[3] = []
    snapshot[4] = "mutated-active-layer"
    snapshot[11] = invalid_size

    with pytest.raises((TypeError, ValueError)):
        dialog._restore_state(tuple(snapshot))

    assert dialog._canvas_document_size == original_size
    assert [layer.layer_id for layer in dialog._paint_layers] == original_layer_ids
    assert dialog._active_paint_layer_id == original_active_id
    assert dialog._restoring_state is False
    dialog.close(); dialog.deleteLater(); app.processEvents()


@pytest.mark.parametrize(
    "method_name",
    [
        "_system_clipboard_has_paint_payload",
        "_system_clipboard_has_image_payload",
        "_payload_from_system_clipboard",
        "_system_clipboard_image",
    ],
)
def test_system_clipboard_read_failures_are_exposed_and_success_clears(
    monkeypatch, method_name: str,
) -> None:
    app = _app()
    import app.drawing as drawing

    dialog = _dialog()

    class BrokenApplication:
        @staticmethod
        def clipboard():
            raise OSError("clipboard read unavailable")

    monkeypatch.setattr(drawing, "QApplication", BrokenApplication)
    assert getattr(dialog, method_name)() in {False, None}
    assert "OSError: clipboard read unavailable" in dialog.painter_action_state()[
        "operational_errors"
    ]["clipboard_read"]

    class EmptyClipboard:
        @staticmethod
        def mimeData():
            return None

    class WorkingApplication:
        @staticmethod
        def clipboard():
            return EmptyClipboard()

    monkeypatch.setattr(drawing, "QApplication", WorkingApplication)
    assert getattr(dialog, method_name)() in {False, None}
    assert dialog.painter_action_state()["operational_errors"]["clipboard_read"] == ""
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_system_clipboard_write_and_image_asset_failures_are_exposed(
    monkeypatch, tmp_path,
) -> None:
    app = _app()
    import app.drawing as drawing
    from PySide6.QtGui import QImage

    dialog = _dialog()
    monkeypatch.setattr(
        dialog,
        "_payload_to_clipboard_document",
        lambda _payload: {"kind": "strokes"},
    )

    class BrokenClipboard:
        @staticmethod
        def setMimeData(_mime):
            raise OSError("clipboard write unavailable")

    class BrokenApplication:
        @staticmethod
        def clipboard():
            return BrokenClipboard()

    monkeypatch.setattr(drawing, "QApplication", BrokenApplication)
    dialog._write_payload_to_system_clipboard({"kind": "strokes"})
    assert "OSError: clipboard write unavailable" in dialog.painter_action_state()[
        "operational_errors"
    ]["clipboard_write"]

    class WorkingClipboard:
        written = None

        @classmethod
        def setMimeData(cls, mime):
            cls.written = mime

    class WorkingApplication:
        @staticmethod
        def clipboard():
            return WorkingClipboard()

    monkeypatch.setattr(drawing, "QApplication", WorkingApplication)
    dialog._write_payload_to_system_clipboard({"kind": "strokes"})
    assert WorkingClipboard.written is not None
    assert dialog.painter_action_state()["operational_errors"]["clipboard_write"] == ""

    blocked_directory = tmp_path / "not-a-directory"
    blocked_directory.write_bytes(b"occupied")
    monkeypatch.setattr(drawing, "PAINT_CLIPBOARD_IMAGE_DIR", blocked_directory)
    image = QImage(2, 2, QImage.Format.Format_ARGB32)
    image.fill(0)
    assert dialog._write_clipboard_image_asset(image) is None
    assert "FileExistsError" in dialog.painter_action_state()["operational_errors"][
        "clipboard_image_asset"
    ]
    writable_directory = tmp_path / "clipboard-assets"
    monkeypatch.setattr(drawing, "PAINT_CLIPBOARD_IMAGE_DIR", writable_directory)
    written = dialog._write_clipboard_image_asset(image)
    assert written is not None and written.is_file()
    assert dialog.painter_action_state()["operational_errors"][
        "clipboard_image_asset"
    ] == ""
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_reference_image_asset_write_failure_is_exposed_and_success_clears(
    monkeypatch, tmp_path,
) -> None:
    app = _app()
    import app.drawing as drawing
    from PySide6.QtGui import QImage

    dialog = _dialog()
    image = QImage(2, 2, QImage.Format.Format_ARGB32)
    image.fill(0xFF224466)

    blocked_directory = tmp_path / "not-a-reference-directory"
    blocked_directory.write_bytes(b"occupied")
    monkeypatch.setattr(drawing, "PAINT_REFERENCE_IMAGE_DIR", blocked_directory)
    assert dialog._write_reference_image_asset(image) is None
    assert "FileExistsError" in dialog.painter_action_state()["operational_errors"][
        "reference_image_asset"
    ]

    writable_directory = tmp_path / "reference-assets"
    monkeypatch.setattr(drawing, "PAINT_REFERENCE_IMAGE_DIR", writable_directory)
    written = dialog._write_reference_image_asset(image)
    assert written is not None and written.is_file()
    assert dialog.painter_action_state()["operational_errors"][
        "reference_image_asset"
    ] == ""
    dialog.close(); dialog.deleteLater(); app.processEvents()


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 0), (" 12 ", 12), (-1, -1), (True, None), (1.5, None), ("1.5", None), (None, None)],
)
def test_brush_preset_index_parser_accepts_only_explicit_integral_forms(
    value, expected,
) -> None:
    from app.drawing import PaintDialog

    assert PaintDialog._brush_preset_index(value) == expected


def test_invalid_brush_preset_index_does_not_apply_and_catalog_failure_propagates(
    monkeypatch,
) -> None:
    app = _app()
    dialog = _dialog()
    applied = []
    monkeypatch.setattr(dialog, "_apply_brush_library_preset", applied.append)

    dialog._apply_brush_preset_by_index(True)
    dialog._apply_brush_preset_by_index("not-an-index")
    dialog._apply_brush_preset_by_index(10**9)
    assert applied == []

    def fail_catalog():
        raise RuntimeError("catalog corruption")

    monkeypatch.setattr(dialog, "_brush_presets_catalog", fail_catalog)
    with pytest.raises(RuntimeError, match="catalog corruption"):
        dialog._apply_brush_preset_by_index(0)
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_canvas_interaction_hook_failure_is_fail_closed_and_reported() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    dialog = _dialog()
    dialog.canvas.resize(64, 64)
    dialog.canvas.set_tool("pen")

    def fail_hook(phase, *_args):
        raise RuntimeError(f"{phase} interaction failed")

    dialog.canvas.set_interaction_hook(fail_hook)
    QTest.mousePress(
        dialog.canvas,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(20, 20),
    )
    assert dialog.canvas._current_points == []
    assert dialog.canvas._interaction_active is False
    assert "RuntimeError: press interaction failed" in dialog.painter_action_state()[
        "operational_errors"
    ]["canvas_interaction"]

    QTest.mouseMove(dialog.canvas, QPoint(24, 24))
    assert dialog.canvas._current_points == []
    assert "RuntimeError: move interaction failed" in dialog.painter_action_state()[
        "operational_errors"
    ]["canvas_interaction"]

    dialog.canvas.set_interaction_hook(lambda *_args: True)
    QTest.mousePress(
        dialog.canvas,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(20, 20),
    )
    assert dialog.painter_action_state()["operational_errors"]["canvas_interaction"] == ""
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_all_optional_canvas_callbacks_report_failure_without_mutating_strokes(monkeypatch) -> None:
    app = _app()
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QContextMenuEvent, QMouseEvent
    from PySide6.QtTest import QTest

    import app.color_workflow as color_workflow

    dialog = _dialog()
    canvas = dialog.canvas
    canvas.resize(96, 72)
    canvas.set_tool("select")
    dialog.show()
    app.processEvents()
    initial_strokes = list(canvas._embedded_strokes)

    canvas._extra_paint_hook = lambda *_args: (_ for _ in ()).throw(
        RuntimeError("extra paint failed exactly")
    )
    canvas.repaint()
    app.processEvents()
    assert canvas.interaction_error() == "RuntimeError: extra paint failed exactly"
    canvas._extra_paint_hook = None

    canvas.set_click_hook(
        lambda *_args: (_ for _ in ()).throw(RuntimeError("click failed exactly"))
    )
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
    assert canvas.interaction_error() == "RuntimeError: click failed exactly"
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))

    canvas.set_click_hook(None)
    canvas.set_interaction_hook(
        lambda phase, *_args: (_ for _ in ()).throw(RuntimeError(f"{phase} failed exactly"))
    )
    double_event = QMouseEvent(
        QEvent.Type.MouseButtonDblClick,
        QPointF(20, 20),
        QPointF(20, 20),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseDoubleClickEvent(double_event)
    assert canvas.interaction_error() == "RuntimeError: double failed exactly"

    canvas.set_interaction_hook(None)
    canvas.set_click_hook(
        lambda *_args: (_ for _ in ()).throw(RuntimeError("double click failed exactly"))
    )
    canvas.mouseDoubleClickEvent(double_event)
    assert canvas.interaction_error() == "RuntimeError: double click failed exactly"

    canvas.set_click_hook(None)
    canvas.set_rect_hook(
        lambda *_args: (_ for _ in ()).throw(RuntimeError("rect release failed exactly"))
    )
    canvas._rect_drag_start = QPointF(5, 5)
    canvas._rect_drag_current = QPointF(35, 35)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(35, 35))
    assert canvas.interaction_error() == "RuntimeError: rect release failed exactly"

    canvas.set_rect_hook(None)
    canvas.set_interaction_hook(
        lambda phase, *_args: (_ for _ in ()).throw(RuntimeError(f"{phase} failed exactly"))
    )
    canvas._interaction_active = True
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(30, 30))
    assert canvas.interaction_error() == "RuntimeError: release failed exactly"
    assert canvas._interaction_active is False

    canvas._color_window_payload = {"unchanged": True}
    canvas._color_window_drag_origin = {"origin": True}
    canvas._color_window_drag_handle = "move"
    canvas._color_window_drag_start = QPointF(10, 10)
    monkeypatch.setattr(
        color_workflow,
        "edit_tracking_window",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("window edit failed exactly")),
    )
    canvas._update_color_window_drag(QPointF(20, 20), commit=False)
    assert canvas._color_window_payload == {"unchanged": True}
    assert canvas.interaction_error() == "ValueError: window edit failed exactly"

    class EditedWindow:
        def to_dict(self):
            return {"edited": True}

    monkeypatch.setattr(color_workflow, "edit_tracking_window", lambda *_args, **_kwargs: EditedWindow())
    canvas._color_window_change_hook = lambda *_args: (_ for _ in ()).throw(
        RuntimeError("window callback failed exactly")
    )
    canvas._update_color_window_drag(QPointF(20, 20), commit=True)
    assert canvas._color_window_payload == {"edited": True}
    assert canvas.interaction_error() == "RuntimeError: window callback failed exactly"

    monkeypatch.setattr(
        dialog,
        "_show_canvas_context_menu",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("menu failed exactly")),
    )
    context_event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        QPoint(10, 10),
        QPoint(10, 10),
    )
    assert dialog.eventFilter(canvas, context_event) is False
    assert dialog.painter_action_state()["operational_errors"]["canvas_context_menu"] == (
        "RuntimeError: menu failed exactly"
    )
    assert canvas._embedded_strokes == initial_strokes

    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_path_point_normalization_rejects_nonfinite_and_malformed_values() -> None:
    app = _app()
    dialog = _dialog()
    points = dialog._normalise_path_points(
        [
            (0.25, 0.75),
            (float("nan"), 0.5),
            (0.5, float("inf")),
            ("bad", 0.5),
            None,
            {"x": -0.5, "y": 1.5},
        ]
    )
    assert points == [(0.25, 0.75), (0.0, 1.0)]
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_invalid_embedded_brush_dab_rejects_mode_change_and_reports_error() -> None:
    app = _app()
    dialog = _dialog()
    dialog._brush_dynamics = {
        **dialog._brush_dynamics,
        "enabled": True,
        "mode": "paint",
        "dab_image_path": "",
        "dab_png_base64": "not-valid-base64%%",
    }
    before = dict(dialog._brush_dynamics)

    assert dialog._set_brush_dynamics_mode("smudge") is False
    assert dialog._brush_dynamics == before
    assert "brush_dab" in dialog.painter_action_state()["operational_errors"]
    assert dialog.painter_action_state()["operational_errors"]["brush_dab"]

    dialog._brush_dynamics = {
        **before,
        "dab_png_base64": "",
    }
    assert dialog._set_brush_dynamics_mode("smudge") is True
    assert dialog._brush_dynamics["mode"] == "smudge"
    assert dialog.painter_action_state()["operational_errors"]["brush_dab"] == ""
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_gpu_capability_probe_failure_is_exposed_and_success_clears(monkeypatch) -> None:
    app = _app()
    import app.painter_opengl as painter_opengl

    dialog = _dialog()

    def fail_probe():
        raise RuntimeError("GPU capability probe failed")

    monkeypatch.setattr(painter_opengl, "painter_canvas_gpu_capabilities", fail_probe)
    failed = dialog.painter_action_state()
    assert failed["operational_errors"]["gpu_capabilities"] == (
        "RuntimeError: GPU capability probe failed"
    )
    assert failed["gpu"]["capabilities"]["persistent_stroke_atlas"][
        "enabled"
    ] is False

    monkeypatch.setattr(
        painter_opengl,
        "painter_canvas_gpu_capabilities",
        lambda: {
            "remote_safe": False,
            "persistent_stroke_atlas": {"enabled": True},
        },
    )
    recovered = dialog.painter_action_state()
    assert recovered["operational_errors"]["gpu_capabilities"] == ""
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_invalid_optional_opengl_preview_color_uses_declared_default_only() -> None:
    from app.painter_opengl import _hex_to_rgba

    assert _hex_to_rgba("#GGGGGG", 0.5) == (
        242 / 255.0,
        242 / 255.0,
        242 / 255.0,
        0.5,
    )

    class BrokenColor:
        def __str__(self):
            raise RuntimeError("preview color implementation failed")

    with pytest.raises(RuntimeError, match="preview color implementation failed"):
        _hex_to_rgba(BrokenColor(), 0.5)


def test_invalid_color_power_window_payload_is_not_installed_and_is_reported() -> None:
    app = _app()
    dialog = _dialog()
    dialog.canvas.set_color_power_window_editor(
        {"x": "not-a-number", "y": 0.5, "w": 0.25, "h": 0.25},
        lambda *_args: None,
        active=True,
    )
    assert dialog.canvas._color_window_payload is None
    assert dialog.painter_action_state()["operational_errors"]["canvas_interaction"]

    dialog.canvas.set_color_power_window_editor(
        {"x": 0.5, "y": 0.5, "w": 0.25, "h": 0.25},
        lambda *_args: None,
        active=True,
    )
    assert dialog.canvas._color_window_payload is not None
    assert dialog.painter_action_state()["operational_errors"]["canvas_interaction"] == ""

    class BrokenWindow(dict):
        def get(self, *_args, **_kwargs):
            raise RuntimeError("tracking-window implementation failed")

    with pytest.raises(RuntimeError, match="tracking-window implementation failed"):
        dialog.canvas.set_color_power_window_editor(
            BrokenWindow(), lambda *_args: None, active=True
        )
    dialog.canvas._color_window_payload = BrokenWindow({"x": 0.5})
    with pytest.raises(RuntimeError, match="tracking-window implementation failed"):
        dialog.canvas._color_window_rect()
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_invalid_pbr_scalar_uses_declared_default_reports_and_recovers() -> None:
    app = _app()
    from app.drawing import PAINTER_PBR_DEFAULTS

    dialog = _dialog()
    dialog._pbr_sliders = {}
    dialog._pbr_texture_settings["normal_strength"] = float("nan")
    assert dialog._pbr_slider_value("normal_strength") == float(
        PAINTER_PBR_DEFAULTS["normal_strength"]
    )
    assert "must be finite" in dialog.painter_action_state()["operational_errors"][
        "pbr_slider_value"
    ]

    dialog._pbr_texture_settings["normal_strength"] = "1.75"
    assert dialog._pbr_slider_value("normal_strength") == 1.75
    assert dialog.painter_action_state()["operational_errors"]["pbr_slider_value"] == ""

    with pytest.raises(KeyError, match="Unknown Painter PBR numeric setting"):
        dialog._pbr_slider_value("not_a_declared_pbr_setting")

    class BrokenSettings(dict):
        def get(self, *_args, **_kwargs):
            raise RuntimeError("PBR settings store corrupted")

    dialog._pbr_texture_settings = BrokenSettings()
    with pytest.raises(RuntimeError, match="settings store corrupted"):
        dialog._pbr_slider_value("normal_strength")
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_qt_alpha_and_gpu_capability_failures_use_declared_fallbacks(
    monkeypatch,
) -> None:
    app = _app()
    from PySide6.QtGui import QPixmap
    from app import painter_opengl
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "#FFFFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    original_alpha_probe = QPixmap.hasAlphaChannel

    def fail_alpha_probe(_pixmap):
        raise RuntimeError("injected QPixmap alpha probe failure")

    monkeypatch.setattr(QPixmap, "hasAlphaChannel", fail_alpha_probe)
    displayed = dialog._display_background_pixmap()
    assert not displayed.isNull()
    assert dialog.painter_action_state()["operational_errors"][
        "background_alpha_probe"
    ] == "RuntimeError: injected QPixmap alpha probe failure"
    monkeypatch.setattr(QPixmap, "hasAlphaChannel", original_alpha_probe)
    dialog._display_background_pixmap()
    assert dialog.painter_action_state()["operational_errors"][
        "background_alpha_probe"
    ] == ""

    def fail_capabilities():
        raise RuntimeError("injected GPU capability failure")

    monkeypatch.setattr(
        painter_opengl, "painter_canvas_gpu_capabilities", fail_capabilities
    )
    state = dialog.painter_action_state()
    gpu = state["gpu"]["capabilities"]
    assert gpu["persistent_stroke_atlas"]["enabled"] is False
    assert gpu["persistent_stroke_atlas"]["fallback_renderer"] == (
        "painter_canvas_qpainter_strokes_v1"
    )
    assert state["operational_errors"]["gpu_capabilities"] == (
        "RuntimeError: injected GPU capability failure"
    )
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_canvas_host_coordinate_mapping_uses_global_qt_fallback_and_reports() -> None:
    app = _app()
    from PySide6.QtCore import QPoint

    dialog = _dialog()
    global_point = QPoint(320, 240)

    class IncompatibleChild:
        @staticmethod
        def mapTo(_host, _point):
            raise RuntimeError("injected incompatible Qt parent mapping")

        @staticmethod
        def mapToGlobal(_point):
            return QPoint(global_point)

    expected = dialog._canvas_host.mapFromGlobal(global_point)
    mapped = dialog._point_in_canvas_host(IncompatibleChild(), QPoint(3, 7))
    assert mapped == expected
    assert dialog.painter_action_state()["operational_errors"][
        "coordinate_mapping"
    ] == "RuntimeError: injected incompatible Qt parent mapping"
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_advanced_brush_settings_survive_stroke_history_and_document_payload() -> None:
    app = _app()
    from app.drawing import Stroke

    dialog = _dialog()
    settings = dialog._set_brush_dynamics(
        {
            "enabled": True,
            "dual_brush_enabled": True,
            "dual_brush_seed": 17,
            "dual_brush_strength": 83,
            "noise_enabled": True,
            "noise_seed": 19,
            "noise_scale": 61,
            "wet_edges_enabled": True,
            "wet_edge_pooling": 67,
            "wet_edge_pigment": 91,
            "wet_edge_water": 79,
            "protect_texture": True,
            "document_texture": {
                "pattern_id": "paper/cold-press",
                "strength": 54,
            },
        }
    )
    stroke = Stroke(
        points=[(0.1, 0.5), (0.9, 0.5)],
        brush_seed=811,
        brush_dynamics=dict(settings),
    )
    dialog._on_stroke_added(stroke)
    assert dialog.canvas.embedded_strokes()[-1].brush_dynamics == settings

    dialog._undo()
    assert dialog.canvas.embedded_strokes() == []
    dialog._redo()
    replayed = dialog.canvas.embedded_strokes()[-1]
    assert replayed.brush_dynamics == settings

    payload = dialog._painter_document_payload()
    restored = dialog._strokes_from_clipboard_list(payload["strokes"])
    assert restored[-1].brush_dynamics == settings
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_dynamic_dab_budget_degrade_is_exposed_without_mutating_document() -> None:
    app = _app()
    from app.drawing import Stroke
    from app.painter_brush_dynamics import PAINTER_DYNAMIC_DAB_BUDGET

    dialog = _dialog()
    points = [
        (0.0 if index % 2 == 0 else 1.0, index / 39.0)
        for index in range(40)
    ]
    authored = {
        "enabled": True,
        "scatter_count": 8,
        "buildup": 100,
        "scatter": 100,
    }
    stroke = Stroke(
        points=points,
        width_px=0.5,
        brush_spacing=1,
        brush_seed=37,
        brush_dynamics=dict(authored),
    )
    dialog._on_stroke_added(stroke)
    state = dialog.painter_action_state()["brush"]["engine"]["workload"]
    assert state["degraded"] is True
    assert state["degraded_stroke_count"] == 1
    assert state["max_estimated_dabs"] > PAINTER_DYNAMIC_DAB_BUDGET
    assert state["max_rendered_dabs"] == PAINTER_DYNAMIC_DAB_BUDGET
    assert dialog.canvas.embedded_strokes()[-1].brush_dynamics == authored
    dialog.close(); dialog.deleteLater(); app.processEvents()


@pytest.mark.parametrize(
    "handler_name", ["_handle_channel_list_event", "_handle_layer_list_event"]
)
def test_invalid_optional_list_event_is_rejected_without_state_change(
    handler_name: str,
) -> None:
    app = _app()
    from PySide6.QtCore import QEvent, Qt

    dialog = _dialog()
    before_channels = dict(dialog._channel_visibility)
    before_layers = [(layer.layer_id, layer.visible) for layer in dialog._paint_layers]

    class MissingPositionEvent:
        @staticmethod
        def type():
            return QEvent.Type.MouseButtonPress

        @staticmethod
        def button():
            return Qt.MouseButton.LeftButton

    assert getattr(dialog, handler_name)(MissingPositionEvent()) is False
    assert dialog._channel_visibility == before_channels
    assert [(layer.layer_id, layer.visible) for layer in dialog._paint_layers] == before_layers

    class UnexpectedFailureEvent(MissingPositionEvent):
        @staticmethod
        def position():
            raise ValueError("unexpected event implementation failure")

    with pytest.raises(ValueError, match="unexpected event implementation failure"):
        getattr(dialog, handler_name)(UnexpectedFailureEvent())
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_lasso_mask_clips_fill_to_real_shape_not_bounding_box() -> None:
    app = _app()
    dialog = _dialog()
    assert dialog._select_lasso_points(
        [(0.1, 0.1), (0.9, 0.1), (0.1, 0.9)], polygonal=True
    )
    assert dialog._fill_document("solid", color1="#E2382A")
    raster = dialog._paint_layer_raster(dialog._active_paint_layer_id)
    assert raster.pixelColor(12, 12).red() > 200
    assert raster.pixelColor(52, 52).alpha() == 0
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_feather_alpha_weights_survive_fill_copy_and_cut(monkeypatch) -> None:
    app = _app()
    from PySide6.QtGui import QColor

    dialog = _dialog()
    monkeypatch.setattr(dialog, "_write_payload_to_system_clipboard", lambda _payload: None)
    dialog.canvas.select_rectangle(0.25, 0.25, 0.75, 0.75)
    dialog._sync_pixel_selection_from_canvas()
    assert dialog._modify_selection("feather", 4)
    mask = dialog._selection_pixel_mask
    sample = next(
        (x, y, mask.pixelColor(x, y).alpha())
        for y in range(mask.height())
        for x in range(mask.width())
        if 16 <= mask.pixelColor(x, y).alpha() <= 239
    )
    x, y, weight = sample

    assert dialog._fill_document("solid", color1="#E2382A")
    raster = dialog._paint_layer_raster(dialog._active_paint_layer_id)
    assert abs(raster.pixelColor(x, y).alpha() - weight) <= 2

    payload = dialog._selection_raster_payload(dialog._active_paint_layer_id)
    assert payload is not None
    copied_alpha = payload["raster"].pixelColor(x, y).alpha()
    assert 0 < copied_alpha < raster.pixelColor(x, y).alpha()

    raster.fill(QColor(20, 40, 60, 255))
    dialog._cut_selected_layer()
    cut = dialog._paint_layer_raster(dialog._active_paint_layer_id)
    assert abs(cut.pixelColor(x, y).alpha() - (255 - weight)) <= 2
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_m3_canvas_overlays_and_direct_handle_interactions() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter

    class Event:
        @staticmethod
        def modifiers():
            return Qt.KeyboardModifier.NoModifier

    dialog = _dialog()
    dialog.canvas.resize(64, 64)
    assert dialog._preview_crop((0.2, 0.2, 0.8, 0.8))
    overlay = QImage(64, 64, QImage.Format.Format_ARGB32_Premultiplied)
    overlay.fill(Qt.GlobalColor.transparent)
    painter = QPainter(overlay)
    dialog._paint_m3_edit_overlays(painter, 64, 64)
    painter.end()
    assert any(overlay.pixelColor(x, y).alpha() for x, y in ((1, 1), (13, 13), (32, 13)))
    assert dialog._handle_m3_canvas_interaction("press", 0.8, 0.8, Event())
    assert dialog._handle_m3_canvas_interaction("move", 0.7, 0.7, Event())
    assert dialog._handle_m3_canvas_interaction("release", 0.7, 0.7, Event())
    assert dialog._crop_preview_bounds == (0.2, 0.2, 0.7, 0.7)
    assert dialog._cancel_crop()

    dialog.canvas.select_rectangle(0.2, 0.2, 0.8, 0.8)
    dialog._sync_pixel_selection_from_canvas()
    assert dialog._fill_document("solid", color1="#438FD8")
    assert dialog._preview_selection_transform(pivot_x=0.4, pivot_y=0.4)
    assert dialog._handle_m3_canvas_interaction("press", 0.4, 0.4, Event())
    assert dialog._handle_m3_canvas_interaction("move", 0.55, 0.6, Event())
    assert dialog._handle_m3_canvas_interaction("release", 0.55, 0.6, Event())
    settings = dialog._pixel_transform_preview["settings"]
    assert (settings.pivot_x, settings.pivot_y) == (0.55, 0.6)
    assert dialog._cancel_selection_transform()

    assert dialog._create_path_from_points(
        [(0.2, 0.2), (0.8, 0.2), (0.5, 0.8)], closed=True
    )
    assert dialog._handle_m3_canvas_interaction("press", 0.2, 0.2, Event())
    assert dialog._handle_m3_canvas_interaction("move", 0.3, 0.3, Event())
    assert dialog._handle_m3_canvas_interaction("release", 0.3, 0.3, Event())
    assert dialog._saved_path_location("path:0")[1].points[0] == (0.3, 0.3)
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_color_range_preview_cancel_commit_and_undo() -> None:
    app = _app()
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QColor, QPainter

    dialog = _dialog()
    raster = dialog._paint_layer_raster(dialog._active_paint_layer_id, create=True)
    raster.fill(QColor("#252525"))
    painter = QPainter(raster)
    painter.fillRect(QRect(4, 4, 18, 18), QColor("#E04444"))
    painter.fillRect(QRect(42, 4, 18, 18), QColor("#E04444"))
    painter.end()
    dialog._sync_canvas_layer_view()
    assert dialog._preview_color_range(0.12, 0.12, tolerance=0, contiguous=True)
    mask = dialog._selection_pixel_mask
    assert mask.pixelColor(8, 8).alpha() == 255
    assert mask.pixelColor(48, 8).alpha() == 0
    assert dialog.painter_action_state()["selection"]["color_range_preview_active"]
    assert dialog._cancel_color_range_preview()
    assert dialog._selection_pixel_mask is None
    assert dialog._preview_color_range(0.12, 0.12, tolerance=0, contiguous=False)
    assert dialog._selection_pixel_mask.pixelColor(48, 8).alpha() == 255
    assert dialog._commit_color_range_preview()
    dialog._undo()
    assert dialog._selection_pixel_mask is None
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_transform_preview_cancel_commit_and_single_undo() -> None:
    app = _app()
    dialog = _dialog()
    dialog.canvas.select_rectangle(0.1, 0.1, 0.35, 0.35)
    dialog._sync_pixel_selection_from_canvas()
    assert dialog._fill_document("solid", color1="#2A8BE2")
    original = dialog._paint_layer_raster(dialog._active_paint_layer_id).copy()
    assert dialog._preview_selection_transform(translate_x=20, translate_y=10)
    assert dialog._cancel_selection_transform()
    restored = dialog._paint_layer_raster(dialog._active_paint_layer_id)
    assert bytes(restored.constBits()) == bytes(original.constBits())
    assert dialog._preview_selection_transform(translate_x=20, translate_y=10)
    assert dialog._commit_selection_transform()
    moved = dialog._paint_layer_raster(dialog._active_paint_layer_id)
    assert bytes(moved.constBits()) != bytes(original.constBits())
    dialog._undo()
    undone = dialog._paint_layer_raster(dialog._active_paint_layer_id)
    assert bytes(undone.constBits()) == bytes(original.constBits())
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_layer_all_transform_previews_raster_strokes_and_layer_mask() -> None:
    app = _app()
    from app.drawing import Stroke

    dialog = _dialog()
    layer = dialog._active_paint_layer()
    assert dialog._fill_document("solid", color1="#7D55D9")
    layer.mask = [(0.1, 0.1), (0.4, 0.1), (0.4, 0.4), (0.1, 0.4)]
    dialog.canvas.add_stroke_direct(Stroke(
        points=[(0.15, 0.2), (0.3, 0.25)], layer_id=layer.layer_id
    ))
    original_points = list(dialog.canvas.embedded_strokes()[0].points)
    original_mask = list(layer.mask)
    assert dialog._preview_selection_transform(target="layer_all", translate_x=8, translate_y=5)
    assert dialog.canvas.embedded_strokes()[0].points != original_points
    assert layer.mask != original_mask
    assert dialog._cancel_selection_transform()
    assert dialog.canvas.embedded_strokes()[0].points == original_points
    assert layer.mask == original_mask
    assert dialog._preview_selection_transform(target="layer_all", translate_x=8, translate_y=5)
    assert dialog._commit_selection_transform()
    dialog._undo()
    assert dialog.canvas.embedded_strokes()[0].points == original_points
    assert dialog._active_paint_layer().mask == original_mask
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_transform_respects_pixel_transparency_and_position_locks() -> None:
    app = _app()
    dialog = _dialog()
    assert dialog._fill_document("solid", color1="#8A6BD8")
    dialog._select_all()
    layer = dialog._active_paint_layer()
    layer.lock_pixels = True
    assert not dialog._preview_selection_transform(translate_x=2)
    layer.lock_pixels = False
    layer.lock_transparency = True
    assert not dialog._preview_selection_transform(translate_x=2)
    layer.lock_transparency = False
    layer.lock_position = True
    assert not dialog._preview_selection_transform(target="strokes", translate_x=2)
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_crop_preview_cancel_then_commit_crops_layer_raster_and_undo() -> None:
    app = _app()
    dialog = _dialog()
    assert dialog._fill_document("solid", color1="#36A76B")
    dialog.canvas.select_rectangle(0.25, 0.25, 0.75, 0.75)
    dialog._sync_pixel_selection_from_canvas()
    assert dialog._preview_crop(straighten_degrees=3.0)
    assert dialog._cancel_crop()
    assert dialog._canvas_document_size == (64, 64)
    assert dialog._preview_crop()
    assert dialog._commit_crop()
    assert dialog._canvas_document_size == (32, 32)
    assert dialog._paint_layer_raster(dialog._active_paint_layer_id).size().width() == 32
    dialog._undo()
    assert dialog._canvas_document_size == (64, 64)
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_bezier_path_edit_fill_duplicate_rename_and_reorder() -> None:
    app = _app()
    dialog = _dialog()
    assert dialog._create_path_from_points(
        [(0.15, 0.2), (0.85, 0.2), (0.5, 0.85)], closed=True
    )
    assert dialog._edit_path_anchor(
        "path:0", 1, "smooth", out_handle=(0.92, 0.5)
    )
    stroke = dialog._saved_path_location("path:0")[1]
    assert len(stroke.path_handles) == 3
    assert dialog._fill_saved_path("path:0", "#B455E0")
    assert dialog._paint_layer_raster(dialog._active_paint_layer_id).pixelColor(32, 30).alpha() > 0
    assert dialog._duplicate_path("path:0")
    assert dialog._rename_path("Silhouette", "path:1")
    before = [stroke.path_name for stroke in dialog.canvas.embedded_strokes() if stroke.source_tool == "path"]
    assert not dialog._reorder_path("path:1", -1)
    assert not dialog._reorder_path("path:1", 99)
    assert not dialog._reorder_path("path:1", 0.5)
    assert not dialog._reorder_path("path:99", 0)
    assert [stroke.path_name for stroke in dialog.canvas.embedded_strokes() if stroke.source_tool == "path"] == before
    assert dialog._reorder_path("path:1", 0)
    assert dialog._saved_path_location("path:0")[1].path_name == "Silhouette"
    dialog.close(); dialog.deleteLater(); app.processEvents()


def test_m3_action_surface_registers_and_executes_pixel_selection() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry

    dialog = _dialog()
    registry = ActionRegistry(owner=dialog)
    ids = {row["id"] for row in registry.list_actions()}
    assert {
        "paint.selection.lasso", "paint.selection.modify",
        "paint.selection.transform", "paint.crop.preview", "paint.crop.commit",
        "paint.path.anchor.edit", "paint.path.fill", "paint.path.stroke",
        "paint.path.duplicate", "paint.path.rename", "paint.path.reorder",
    } <= ids
    result = registry.execute("paint.selection.lasso", {
        "points": [[0.1, 0.1], [0.8, 0.1], [0.1, 0.8]],
        "polygonal": True,
    }).to_dict()
    assert result["ok"]
    assert result["result"]["selection"]["pixel_mask"] is True
    dialog.close(); dialog.deleteLater(); app.processEvents()
