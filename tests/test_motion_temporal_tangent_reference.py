from __future__ import annotations

from app.motion_designer.graph_editing import update_keyframe_tangent
from app.motion_designer.keyframes import evaluate_property
from app.motion_designer.schema import AnimatedProperty, Keyframe, MotionLayer
from app.motion_designer.temporal_interpolation import TEMPORAL_AUTO_CONTRACT


def _auto_property(rows: list[tuple[int, float]]) -> AnimatedProperty:
    keys = [Keyframe(time_ms=time, value=value, interpolation="bezier") for time, value in rows]
    for key in keys:
        key.metadata.update({
            "tangent_mode": "standard_auto",
            "tangent_contract": TEMPORAL_AUTO_CONTRACT,
        })
    return AnimatedProperty(default=rows[0][1], keyframes=keys)


def test_standard_auto_uses_neighbor_times_and_remains_monotone() -> None:
    prop = _auto_property([(0, 0.0), (100, 1.0), (1000, 2.0)])
    samples = [evaluate_property(prop, time) for time in range(0, 1001, 10)]
    assert samples == sorted(samples)
    assert min(samples) >= 0.0
    assert max(samples) <= 2.0
    assert evaluate_property(prop, 50) != 0.5


def test_standard_auto_flattens_a_sign_change_without_overshoot() -> None:
    prop = _auto_property([(0, 0.0), (500, 10.0), (1000, 0.0)])
    samples = [evaluate_property(prop, time) for time in range(0, 1001, 5)]
    assert min(samples) >= 0.0
    assert max(samples) <= 10.0
    assert evaluate_property(prop, 499) <= 10.0
    assert evaluate_property(prop, 501) <= 10.0


def test_standard_auto_evaluates_vector_components_independently() -> None:
    keys = [
        Keyframe(time_ms=0, value=[0.0, 0.0], interpolation="bezier"),
        Keyframe(time_ms=250, value=[10.0, 100.0], interpolation="bezier"),
        Keyframe(time_ms=1000, value=[20.0, 0.0], interpolation="bezier"),
    ]
    for key in keys:
        key.metadata["tangent_contract"] = TEMPORAL_AUTO_CONTRACT
    prop = AnimatedProperty(value_type="vector2", default=[0.0, 0.0], keyframes=keys)
    value = evaluate_property(prop, 500)
    assert 10.0 < value[0] < 20.0
    assert 0.0 < value[1] < 100.0


def test_continuous_mode_links_handle_direction_but_broken_does_not() -> None:
    layer = MotionLayer()
    key = Keyframe(time_ms=500, value=1.0, interpolation="bezier")
    layer.transform.opacity.keyframes = [
        Keyframe(time_ms=0, value=0.0), key, Keyframe(time_ms=1000, value=0.0),
    ]
    linked = update_keyframe_tangent(
        layer, "opacity", key.id, mode="continuous", out_tangent=[0.2, 0.4],
    )
    assert linked["out_tangent"] == [0.2, 0.4]
    assert linked["in_tangent"] == [0.8, 0.6]
    broken = update_keyframe_tangent(
        layer,
        "opacity",
        key.id,
        mode="broken",
        in_tangent=[0.9, 0.1],
        out_tangent=[0.3, 0.8],
    )
    assert broken["in_tangent"] == [0.9, 0.1]
    assert broken["out_tangent"] == [0.3, 0.8]


def test_legacy_auto_alias_retains_tiger_smooth_contract() -> None:
    layer = MotionLayer()
    key = Keyframe(time_ms=0, value=0.0)
    layer.transform.opacity.keyframes = [key, Keyframe(time_ms=1000, value=1.0)]
    updated = update_keyframe_tangent(layer, "opacity", key.id, mode="auto")
    assert updated["metadata"]["tangent_mode"] == "tiger_smooth"
    assert updated["metadata"]["tangent_contract"] == "legacy_tiger_smooth_temporal_bezier_v1"
