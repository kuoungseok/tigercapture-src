from __future__ import annotations

import os

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.actions.registry import ActionRegistry
from app.motion_designer.evaluator import remap_layer_time
from app.motion_designer.schema import (
    AnimatedProperty,
    Keyframe,
    MotionComposition,
    MotionLayer,
)
from app.motion_designer.graph_editing import (
    set_roving_keyframes,
    update_keyframe_tangent,
)
from app.motion_designer.time_remap import (
    apply_time_remap_preset,
    layer_time_remap,
    time_remap_diagnostics,
)
from app.motion_designer.validation import validate_composition


def _layer() -> MotionLayer:
    return MotionLayer(
        id="clip",
        name="Clip",
        layer_type="image",
        in_ms=100,
        out_ms=1100,
        source_in_ms=250,
    )


def test_time_remap_presets_cover_linear_reverse_freeze_and_speed_ramp() -> None:
    layer = _layer()
    apply_time_remap_preset(layer, "linear")
    assert remap_layer_time(layer, 100) == 250.0
    assert remap_layer_time(layer, 1100) == 1250.0
    apply_time_remap_preset(layer, "reverse")
    assert remap_layer_time(layer, 100) == 1250.0
    assert remap_layer_time(layer, 1100) == 250.0
    reverse = time_remap_diagnostics(layer)
    assert reverse["segments"][0]["reverse"] is True
    apply_time_remap_preset(layer, "freeze")
    assert remap_layer_time(layer, 100) == remap_layer_time(layer, 900)
    assert time_remap_diagnostics(layer)["segments"][0]["freeze"] is True
    apply_time_remap_preset(layer, "speed_ramp")
    values = [remap_layer_time(layer, time) for time in (100, 350, 600, 850, 1100)]
    assert values == sorted(values)
    assert validate_composition(MotionComposition(
        id="time",
        duration_ms=1200,
        layers=[layer],
    )).ok


def test_time_remap_actions_set_inspect_preset_and_clear() -> None:
    class Owner:
        def __init__(self):
            self._motion_compositions = {}

    registry = ActionRegistry(Owner())
    created = registry.execute(
        "motion.composition.create",
        {"duration_ms": 1200},
    )
    composition_id = created.result["payload"]["composition"]["id"]
    assert registry.execute(
        "motion.layer.add",
        {"composition_id": composition_id, "layer": _layer().to_dict()},
    ).ok
    assert registry.execute(
        "motion.time_remap.set",
        {
            "composition_id": composition_id,
            "layer_id": "clip",
            "keyframes": [
                {"time_ms": 0, "value": 900},
                {"time_ms": 1000, "value": 100},
            ],
        },
    ).ok
    inspected = registry.execute(
        "motion.time_remap.inspect",
        {"composition_id": composition_id, "layer_id": "clip"},
    )
    assert inspected.ok and inspected.result["segments"][0]["reverse"]
    assert registry.execute(
        "motion.time_remap.preset",
        {
            "composition_id": composition_id,
            "layer_id": "clip",
            "preset": "freeze",
        },
    ).ok
    assert registry.execute(
        "motion.time_remap.clear",
        {"composition_id": composition_id, "layer_id": "clip"},
    ).ok


def test_time_remap_ui_preset_exposes_source_time_graph() -> None:
    from app.motion_designer.ui.window import MotionDesignerWindow

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    composition = MotionComposition(
        id="time_ui",
        duration_ms=1200,
        layers=[_layer()],
    )
    window = MotionDesignerWindow(composition)
    window._select_layer("clip")
    window._apply_time_remap_preset("speed_ramp")
    layer = window.controller.composition.layers[0]
    assert layer_time_remap(layer) is not None
    current = window.timeline.graph_properties.currentItem()
    assert str(current.data(Qt.ItemDataRole.UserRole)) == "time_remap"
    assert window.timeline.graph_editor.property is not None
    window.close()
    app.processEvents()


def test_graph_tangent_modes_and_action_contract() -> None:
    layer = _layer()
    key = Keyframe(time_ms=0, value=[0.0, 0.0])
    layer.transform.position.keyframes = [
        key,
        Keyframe(time_ms=1000, value=[100.0, 50.0]),
    ]
    updated = update_keyframe_tangent(
        layer,
        "position",
        key.id,
        mode="broken",
        in_tangent=[0.8, 1.2],
        out_tangent=[0.2, -0.1],
    )
    assert updated["metadata"]["tangent_mode"] == "broken"
    assert updated["out_tangent"] == [0.2, -0.1]

    class Owner:
        def __init__(self):
            self._motion_compositions = {}

    registry = ActionRegistry(Owner())
    created = registry.execute(
        "motion.composition.create",
        {"duration_ms": 1200},
    )
    composition_id = created.result["payload"]["composition"]["id"]
    assert registry.execute(
        "motion.layer.add",
        {"composition_id": composition_id, "layer": layer.to_dict()},
    ).ok
    result = registry.execute(
        "motion.graph.tangent.update",
        {
            "composition_id": composition_id,
            "layer_id": "clip",
            "property_name": "position",
            "keyframe_id": key.id,
            "mode": "hold",
        },
    )
    assert result.ok
    assert result.result["payload"]["keyframe"]["interpolation"] == "hold"


def test_roving_keyframes_use_spatial_distance_and_action_contract() -> None:
    layer = _layer()
    rows = [
        Keyframe(time_ms=0, value=[0.0, 0.0]),
        Keyframe(time_ms=250, value=[10.0, 0.0]),
        Keyframe(time_ms=750, value=[90.0, 0.0]),
        Keyframe(time_ms=1000, value=[100.0, 0.0]),
    ]
    layer.transform.position.keyframes = rows
    result = set_roving_keyframes(
        layer,
        "position",
        [rows[1].id, rows[2].id],
    )
    assert [row["time_ms"] for row in result] == [0, 100, 900, 1000]
    assert result[1]["metadata"]["roving"] is True

    class Owner:
        def __init__(self):
            self._motion_compositions = {}

    registry = ActionRegistry(Owner())
    created = registry.execute(
        "motion.composition.create",
        {"duration_ms": 1200},
    )
    composition_id = created.result["payload"]["composition"]["id"]
    assert registry.execute(
        "motion.layer.add",
        {"composition_id": composition_id, "layer": layer.to_dict()},
    ).ok
    action = registry.execute(
        "motion.graph.roving.set",
        {
            "composition_id": composition_id,
            "layer_id": "clip",
            "property_name": "position",
            "keyframe_ids": [rows[1].id, rows[2].id],
            "enabled": False,
        },
    )
    assert action.ok


def test_graph_editor_direct_tangent_handle_emits_broken_value() -> None:
    from app.motion_designer.ui.graph_editor import GraphEditor

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    editor = GraphEditor()
    editor.resize(420, 180)
    editor.set_property(
        AnimatedProperty(
            value_type="scalar",
            default=0.0,
            keyframes=[
                Keyframe(
                    id="left",
                    time_ms=0,
                    value=0.0,
                    interpolation="bezier",
                ),
                Keyframe(
                    id="right",
                    time_ms=1000,
                    value=100.0,
                    interpolation="bezier",
                ),
            ],
        ),
        duration_ms=1000,
    )
    editor.show()
    app.processEvents()
    editor.grab()
    assert len(editor._tangent_markers) == 2
    emitted = []
    editor.tangent_changed.connect(
        lambda keyframe_id, side, value: emitted.append(
            (keyframe_id, side, value),
        ),
    )
    marker = editor._tangent_markers[0][0].toPoint()
    destination = marker + QPoint(18, -12)
    QTest.mousePress(editor, Qt.MouseButton.LeftButton, pos=marker)
    QTest.mouseMove(editor, destination)
    QTest.mouseRelease(editor, Qt.MouseButton.LeftButton, pos=destination)
    assert emitted and emitted[0][0:2] == ("left", "out")
    assert len(emitted[0][2]) == 2
    editor.close()
    app.processEvents()


def test_expression_pick_whip_dialog_filters_matching_property_types() -> None:
    from app.motion_designer.ui.expression_link_dialog import (
        ExpressionLinkDialog,
    )

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    target = MotionLayer(
        id="target",
        name="Target",
        layer_type="shape",
        out_ms=1000,
    )
    source = MotionLayer(
        id="source",
        name="Controller",
        layer_type="null",
        out_ms=1000,
    )
    dialog = ExpressionLinkDialog(
        MotionComposition(
            id="links",
            duration_ms=1000,
            layers=[target, source],
        ),
        "target",
        "position",
    )
    assert dialog.source_layer_id == "source"
    choices = {
        str(dialog.source_property.itemData(index))
        for index in range(dialog.source_property.count())
    }
    assert choices == {"position", "scale", "anchor"}
    dialog.close()
    app.processEvents()
