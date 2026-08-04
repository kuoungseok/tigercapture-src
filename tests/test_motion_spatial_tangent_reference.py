from __future__ import annotations

from app.motion_designer.graph_editing import update_keyframe_spatial_tangent
from app.motion_designer.keyframes import evaluate_property
from app.motion_designer.schema import Keyframe, MotionComposition, MotionLayer
from app.motion_designer.spatial_interpolation import SPATIAL_BEZIER_CONTRACT
from app.motion_designer.ui.window import MotionDocumentController


def _layer() -> tuple[MotionLayer, list[Keyframe]]:
    layer = MotionLayer()
    rows = [
        Keyframe(time_ms=0, value=[0.0, 0.0], interpolation="linear"),
        Keyframe(time_ms=500, value=[100.0, 0.0], interpolation="linear"),
        Keyframe(time_ms=1000, value=[200.0, 100.0], interpolation="linear"),
    ]
    layer.transform.position.keyframes = rows
    return layer, rows


def test_spatial_bezier_curves_position_without_changing_key_times() -> None:
    layer, rows = _layer()
    update_keyframe_spatial_tangent(
        layer, "position", rows[0].id, mode="broken", out_tangent=[0.0, 100.0],
    )
    update_keyframe_spatial_tangent(
        layer, "position", rows[1].id, mode="broken", in_tangent=[0.0, 100.0],
    )
    assert layer.transform.position.metadata["spatial_interpolation"] == SPATIAL_BEZIER_CONTRACT
    midpoint = evaluate_property(layer.transform.position, 250)
    assert midpoint[0] == 50.0
    assert midpoint[1] == 75.0
    assert [key.time_ms for key in rows] == [0, 500, 1000]


def test_auto_spatial_tangent_uses_neighbor_direction() -> None:
    layer, rows = _layer()
    updated = update_keyframe_spatial_tangent(layer, "position", rows[1].id, mode="auto")
    assert updated["metadata"]["spatial_tangent_mode"] == "auto"
    assert updated["metadata"]["spatial_out_tangent"] == [200.0 / 6.0, 100.0 / 6.0]
    assert updated["metadata"]["spatial_in_tangent"] == [-200.0 / 6.0, -100.0 / 6.0]


def test_continuous_spatial_handles_are_collinear_and_broken_are_independent() -> None:
    layer, rows = _layer()
    continuous = update_keyframe_spatial_tangent(
        layer, "position", rows[1].id, mode="continuous", out_tangent=[30.0, -12.0],
    )
    assert continuous["metadata"]["spatial_in_tangent"] == [-30.0, 12.0]
    broken = update_keyframe_spatial_tangent(
        layer,
        "position",
        rows[1].id,
        mode="broken",
        in_tangent=[-5.0, 20.0],
        out_tangent=[40.0, 3.0],
    )
    assert broken["metadata"]["spatial_in_tangent"] == [-5.0, 20.0]
    assert broken["metadata"]["spatial_out_tangent"] == [40.0, 3.0]


def test_desktop_controller_exposes_spatial_path_tangent_mutation() -> None:
    layer, rows = _layer()
    composition = MotionComposition(duration_ms=1000, layers=[layer])
    controller = MotionDocumentController(composition, lambda _composition: None)
    controller.update_keyframe_spatial_tangent(
        layer.id, "position", rows[1].id, "auto",
    )
    updated = controller.composition.layers[0].transform.position
    assert updated.metadata["spatial_interpolation"] == SPATIAL_BEZIER_CONTRACT
    assert updated.keyframes[1].metadata["spatial_tangent_mode"] == "auto"
