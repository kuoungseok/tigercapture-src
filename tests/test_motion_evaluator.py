from app.motion_designer.evaluator import evaluate_composition, remap_layer_time
from app.motion_designer.keyframes import evaluate_property
from app.motion_designer.schema import AnimatedProperty, Keyframe, MotionBehaviorRef, MotionComposition, MotionLayer


def test_hold_linear_bezier_and_vector_values_are_deterministic() -> None:
    hold = AnimatedProperty(value_type="enum", default="a", keyframes=[
        Keyframe(time_ms=0, value="a", interpolation="hold"), Keyframe(time_ms=1000, value="b")])
    linear = AnimatedProperty(value_type="vector2", keyframes=[
        Keyframe(time_ms=0, value=[0, 10]), Keyframe(time_ms=1000, value=[10, 30])])
    bezier = AnimatedProperty(keyframes=[
        Keyframe(time_ms=0, value=0, interpolation="bezier", out_tangent=(0.2, 0.0)),
        Keyframe(time_ms=1000, value=1, in_tangent=(0.8, 1.0))])
    assert evaluate_property(hold, 999) == "a"
    assert evaluate_property(linear, 500) == [5.0, 20.0]
    first = evaluate_property(bezier, 250)
    assert first == evaluate_property(bezier, 250)
    assert 0.0 < first < 0.25


def test_parent_hierarchy_behavior_and_time_modes() -> None:
    parent = MotionLayer(id="parent", name="Parent", out_ms=2000)
    parent.transform.position.default = [100.0, 20.0]
    child = MotionLayer(id="child", parent_id="parent", out_ms=2000)
    child.transform.position.default = [10.0, 5.0]
    child.behaviors.append(MotionBehaviorRef(kind="wiggle", start_ms=0, end_ms=2000,
                                              params={"amplitude": 8.0, "frequency": 2.0, "seed": 0.3}))
    loop = MotionLayer(id="loop", in_ms=0, out_ms=1000, source_in_ms=100, time_scale=1.0,
                       metadata={"time_mode": "loop"})
    composition = MotionComposition(duration_ms=2000, layers=[parent, child, loop])
    first = {item.id: item for item in evaluate_composition(composition, 250)}
    second = {item.id: item for item in evaluate_composition(composition, 250)}
    assert first["child"].matrix == second["child"].matrix
    assert first["child"].matrix[4:] == (110.0, 25.0)
    assert remap_layer_time(loop, 1250) == 350.0


def test_solo_and_active_range() -> None:
    normal = MotionLayer(id="normal", out_ms=1000)
    solo = MotionLayer(id="solo", out_ms=1000, solo=True)
    result = {item.id: item for item in evaluate_composition(MotionComposition(layers=[normal, solo]), 500)}
    assert result["normal"].active is False
    assert result["solo"].active is True
