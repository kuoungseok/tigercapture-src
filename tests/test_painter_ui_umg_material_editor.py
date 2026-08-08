from __future__ import annotations

import copy
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _process_deletes(app) -> None:
    from PySide6.QtCore import QCoreApplication, QEvent

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def _gradient(kind: str = "linear") -> dict:
    return {
        "type": kind,
        "start": {"x": 0.1, "y": 0.25},
        "end": {"x": 0.9, "y": 0.75},
        "stops": [
            {"position": 0.0, "color": "#F6F0E5FF"},
            {"position": 0.45, "color": "#878787FF"},
            {"position": 1.0, "color": "#151515FF"},
        ],
    }


def _rounded_card() -> dict:
    return {
        "Schema": "tigerstudio.umg.ui_material.v2",
        "Generator": "tiger_ui_rounded_card_sdf_custom_hlsl_v1",
        "Kind": "RoundedCard",
        "CoordinateSpace": "LocalUV",
        "Size": {"X": 320.0, "Y": 180.0},
        "FillKind": "Solid",
        "FillColor": "#3278D4FF",
        "Start": {"X": 0.0, "Y": 0.5},
        "End": {"X": 1.0, "Y": 0.5},
        "Width": {"X": 0.0, "Y": 1.0},
        "Stops": [
            {"Position": 0.0, "Color": "#3278D4FF"},
            {"Position": 1.0, "Color": "#2356A3FF"},
        ],
        "Opacity": 1.0,
        "CornerRadii": {"X": 34.0, "Y": 0.0, "Z": 20.0, "W": 8.0},
        "CornerSmoothing": 0.55,
        "Stroke": {
            "Width": 5.0,
            "Alignment": "Inside",
            "Color": "#E8F2FFFF",
        },
        "DropShadow": {
            "Enabled": True,
            "Color": "#00000099",
            "Offset": {"X": 7.0, "Y": 9.0},
            "Blur": 12.0,
            "Spread": 2.0,
        },
        "InnerShadow": {
            "Enabled": True,
            "Color": "#07162988",
            "Offset": {"X": 1.0, "Y": 3.0},
            "Blur": 6.0,
            "Spread": 1.0,
        },
        "VisualPadding": {
            "Left": 7.0,
            "Top": 5.0,
            "Right": 21.0,
            "Bottom": 23.0,
        },
    }


def test_umg_material_editor_exposes_fixed_graph_hlsl_and_spec() -> None:
    app = _app()
    from PySide6.QtWidgets import QDialog

    from app.painter_ui_umg_material_editor import (
        PainterUMGMaterialEditorDialog,
    )
    from app.unreal_umg_material import (
        gradient_custom_hlsl,
        umg_material_graph,
        umg_material_preview_style,
    )

    source = _gradient()
    expected_graph = umg_material_graph(source)
    dialog = PainterUMGMaterialEditorDialog(source)
    try:
        assert isinstance(dialog, QDialog)
        assert dialog.graph_spec() == expected_graph
        assert dialog.material_spec() == expected_graph["material"]
        assert dialog.preview_style() == umg_material_preview_style(
            expected_graph["material"]
        )
        assert dialog.validation_errors() == []
        assert len(dialog.scene.node_items) == 4
        assert set(dialog.scene.node_items) == {
            "uv",
            "parameters",
            "custom_hlsl",
            "output",
        }
        assert len(dialog.scene.connection_items) == 3
        assert dialog.hlsl_edit.isReadOnly()
        assert dialog.hlsl_edit.toPlainText() == gradient_custom_hlsl(
            expected_graph["material"]
        )

        copied = dialog.material_spec()
        copied["Kind"] = "ChangedOutsideDialog"
        assert dialog.material_spec()["Kind"] == "LinearGradient"
    finally:
        dialog.close()
        dialog.deleteLater()
        _process_deletes(app)


def test_umg_material_editor_offscreen_render_zoom_and_pan_modes() -> None:
    app = _app()
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent

    from app.painter_ui_umg_material_editor import (
        PainterUMGMaterialEditorDialog,
    )

    dialog = PainterUMGMaterialEditorDialog(_gradient("radial"))
    try:
        dialog.show()
        _process_deletes(app)
        assert dialog.isVisible()
        assert not dialog.grab().isNull()
        assert "length(UV - Start.xy)" in dialog.hlsl_edit.toPlainText()

        view = dialog.graph_view
        zoom_before = view.zoom_level()
        wheel = QWheelEvent(
            QPointF(120.0, 90.0),
            QPointF(120.0, 90.0),
            QPoint(),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        app.sendEvent(view.viewport(), wheel)
        assert view.zoom_level() > zoom_before

        space_press = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Space,
            Qt.KeyboardModifier.NoModifier,
        )
        app.sendEvent(view, space_press)
        assert view.space_pan_active()
        space_release = QKeyEvent(
            QEvent.Type.KeyRelease,
            Qt.Key.Key_Space,
            Qt.KeyboardModifier.NoModifier,
        )
        app.sendEvent(view, space_release)
        assert not view.space_pan_active()

        middle_press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(80.0, 80.0),
            QPointF(80.0, 80.0),
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.MiddleButton,
            Qt.KeyboardModifier.NoModifier,
        )
        view.mousePressEvent(middle_press)
        assert view.cursor().shape() == Qt.CursorShape.ClosedHandCursor
        middle_release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(80.0, 80.0),
            QPointF(80.0, 80.0),
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        view.mouseReleaseEvent(middle_release)
        assert view.cursor().shape() == Qt.CursorShape.ArrowCursor
    finally:
        dialog.close()
        dialog.deleteLater()
        _process_deletes(app)


def test_umg_material_editor_renders_rounded_card_graph_style_and_hlsl() -> None:
    app = _app()
    from PySide6.QtCore import QPointF

    from app.painter_ui_umg_material_editor import (
        PainterUMGMaterialEditorPanel,
    )
    from app.unreal_umg_material import rounded_card_custom_hlsl

    panel = PainterUMGMaterialEditorPanel(_rounded_card())
    try:
        panel.resize(1100, 360)
        panel.show()
        app.processEvents()

        assert panel.material_spec()["Kind"] == "RoundedCard"
        assert panel.validation_errors() == []
        nodes = list(panel.graph_spec()["nodes"])
        searchable = " ".join(
            f"{row.get('id', '')} {row.get('type', '')} {row.get('label', '')}"
            for row in nodes
        ).casefold()
        for concept in (
            "geometry",
            "uv",
            "fill",
            "corner",
            "border",
            "shadow",
            "customhlsl",
            "output",
        ):
            assert concept in searchable
        assert len(panel.scene.node_items) >= 6
        assert len(panel.scene.connection_items) >= 5
        assert panel.hlsl_edit.isReadOnly()
        assert panel.hlsl_edit.toPlainText() == rounded_card_custom_hlsl(
            panel.material_spec()
        )

        style = panel.preview_style()
        assert style["corner_radii"] == {
            "top_left": 34.0,
            "top_right": 0.0,
            "bottom_right": 20.0,
            "bottom_left": 8.0,
        }
        assert style["corner_smoothing"] == 0.55
        assert style["stroke_width"] == 5.0
        assert style["stroke_align"] == "inside"
        assert {row["type"] for row in style["effects"]} == {
            "drop_shadow",
            "inner_shadow",
        }

        # The preview path itself uses the independent corner values: the
        # heavily rounded TL corner excludes its near-corner point, while the
        # square TR corner includes the corresponding point.
        path = panel.preview.shape_path()
        bounds = path.boundingRect()
        assert not path.contains(QPointF(bounds.left() + 2.0, bounds.top() + 2.0))
        assert path.contains(QPointF(bounds.right() - 2.0, bounds.top() + 2.0))
        assert not panel.preview.grab().isNull()

        state = {
            "graph": {"zoom": 1.35, "center": [240.0, 135.0]},
            "splitter_sizes": [610, 390],
            "inspector_tab": 1,
        }
        panel.set_view_state(state)
        app.processEvents()
        assert panel.inspector_tabs.currentIndex() == 1
        assert panel.view_state()["splitter_sizes"] == panel.splitter.sizes()
        assert panel.graph_view.zoom_level() == 1.35
    finally:
        panel.close()
        panel.deleteLater()
        _process_deletes(app)


def test_material_preview_corner_smoothing_changes_superellipse_path() -> None:
    app = _app()
    from PySide6.QtCore import QPointF

    from app.painter_ui_umg_material_editor import _MaterialPreview

    base_style = {
        "fill": "#3278D4FF",
        "corner_radii": {
            "top_left": 30.0,
            "top_right": 30.0,
            "bottom_right": 30.0,
            "bottom_left": 30.0,
        },
    }
    round_preview = _MaterialPreview(
        {**base_style, "corner_smoothing": 0.0}
    )
    squircle_preview = _MaterialPreview(
        {**base_style, "corner_smoothing": 1.0}
    )
    try:
        round_preview.resize(220, 120)
        squircle_preview.resize(220, 120)
        round_path = round_preview.shape_path()
        squircle_path = squircle_preview.shape_path()

        def coordinates(path) -> list[tuple[float, float]]:
            return [
                (
                    round(path.elementAt(index).x, 5),
                    round(path.elementAt(index).y, 5),
                )
                for index in range(path.elementCount())
            ]

        assert round_path.elementCount() > 40
        assert squircle_path.elementCount() > 40
        assert coordinates(round_path) != coordinates(squircle_path)

        # A power-4 squircle stays closer to the outer corner than the
        # conventional power-2 round corner at the same radius.
        bounds = round_path.boundingRect()
        corner_probe = QPointF(bounds.left() + 7.0, bounds.top() + 7.0)
        assert not round_path.contains(corner_probe)
        assert squircle_path.contains(corner_probe)
    finally:
        round_preview.deleteLater()
        squircle_preview.deleteLater()
        _process_deletes(app)


def test_material_preview_radial_uses_rotated_asymmetric_width_basis() -> None:
    app = _app()
    import pytest

    from app.painter_ui_umg_material_editor import _MaterialPreview
    from app.unreal_umg_material import umg_material_preview_style

    gradient = {
        "type": "radial",
        "start": {"x": 0.32, "y": 0.34},
        "end": {"x": 0.82, "y": 0.52},
        "width": {"x": 0.16, "y": 0.88},
        "stops": [
            {"position": 0.0, "color": "#FFFFFFFF"},
            {"position": 0.45, "color": "#F43F5EFF"},
            {"position": 1.0, "color": "#172033FF"},
        ],
    }
    material = _rounded_card()
    material.update(
        {
            "FillKind": "RadialGradient",
            "Start": {"X": 0.32, "Y": 0.34},
            "End": {"X": 0.82, "Y": 0.52},
            "Width": {"X": 0.16, "Y": 0.88},
            "Stops": [
                {
                    "Position": row["position"],
                    "Color": row["color"],
                }
                for row in gradient["stops"]
            ],
        }
    )
    preview = _MaterialPreview(umg_material_preview_style(material))
    changed = copy.deepcopy(gradient)
    changed["width"] = {"x": 0.62, "y": 0.92}
    changed_material = copy.deepcopy(material)
    changed_material["Width"] = {"X": 0.62, "Y": 0.92}
    changed_preview = _MaterialPreview(
        umg_material_preview_style(changed_material)
    )
    try:
        for widget in (preview, changed_preview):
            widget.resize(260, 150)
            widget.show()
        app.processEvents()

        rect = preview._card_rect()
        brush = preview._fill_brush(rect)
        transform = brush.transform()
        start_x = rect.left() + 0.32 * rect.width()
        start_y = rect.top() + 0.34 * rect.height()
        end_x = rect.left() + 0.82 * rect.width()
        end_y = rect.top() + 0.52 * rect.height()
        width_x = rect.left() + 0.16 * rect.width()
        width_y = rect.top() + 0.88 * rect.height()
        assert transform.dx() == pytest.approx(start_x)
        assert transform.dy() == pytest.approx(start_y)
        assert transform.m11() == pytest.approx(end_x - start_x)
        assert transform.m12() == pytest.approx(end_y - start_y)
        assert transform.m21() == pytest.approx(width_x - start_x)
        assert transform.m22() == pytest.approx(width_y - start_y)

        changed_transform = changed_preview._fill_brush(
            changed_preview._card_rect()
        ).transform()
        assert changed_transform.m21() != pytest.approx(transform.m21())
        assert changed_transform.m22() != pytest.approx(transform.m22())
        assert preview.grab().toImage().bits().tobytes() != (
            changed_preview.grab().toImage().bits().tobytes()
        )
    finally:
        preview.close()
        changed_preview.close()
        preview.deleteLater()
        changed_preview.deleteLater()
        _process_deletes(app)


def test_embedded_material_panel_hide_only_emits_but_dialog_closes() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_umg_material_editor import (
        PainterUMGMaterialEditorDialog,
        PainterUMGMaterialEditorPanel,
    )

    panel = PainterUMGMaterialEditorPanel(_gradient())
    hidden_requested: list[bool] = []
    panel.close_requested.connect(lambda: hidden_requested.append(True))
    panel.resize(900, 280)
    panel.show()
    _process_deletes(app)
    assert panel.close_button.text() == "Hide graph"
    QTest.mouseClick(panel.close_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert hidden_requested == [True]
    assert panel.isVisible()

    dialog = PainterUMGMaterialEditorDialog(_gradient())
    dialog.show()
    app.processEvents()
    assert dialog.panel.close_button.text() == "Close"
    QTest.mouseClick(dialog.panel.close_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert not dialog.isVisible()

    panel.close()
    panel.deleteLater()
    dialog.deleteLater()
    _process_deletes(app)


def test_umg_material_editor_does_not_depend_on_video_graph_types() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "painter_ui_umg_material_editor.py"
    ).read_text(encoding="utf-8")

    assert "NodeGraphScene" not in source
    assert "NodeItem" not in source.replace("_MaterialNodeItem", "")
    assert "node_graph.theme" in source
