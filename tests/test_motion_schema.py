from app.motion_designer.schema import Keyframe, MotionComposition, MotionLayer


def test_large_composition_round_trip_preserves_unknown_metadata() -> None:
    composition = MotionComposition(name="Large")
    for layer_index in range(100):
        layer = MotionLayer(name=f"Layer {layer_index}")
        layer.extras["future_layer_field"] = {"index": layer_index}
        for key_index in range(10):
            layer.transform.position.keyframes.append(
                Keyframe(time_ms=key_index * 100, value=[layer_index, key_index])
            )
        composition.layers.append(layer)
    composition.extras["future_composition_field"] = True

    restored = MotionComposition.from_dict(composition.to_dict())

    assert len(restored.layers) == 100
    assert sum(len(layer.transform.position.keyframes) for layer in restored.layers) == 1000
    assert restored.to_dict() == composition.to_dict()
