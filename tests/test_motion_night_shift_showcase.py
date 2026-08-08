from pathlib import Path

from tools.create_night_shift_motion_showcase import build_composition


def test_night_shift_showcase_is_layered_and_uses_durable_sources() -> None:
    composition = build_composition()

    assert (composition.width, composition.height) == (720, 1280)
    assert composition.duration_ms == 7000
    assert len(composition.layers) == 19

    image_layers = [
        layer for layer in composition.layers if layer.layer_type == "image"
    ]
    assert len(image_layers) == 4
    assert all(Path(layer.source.uri).is_file() for layer in image_layers)
    assert all("sample_assets" in layer.source.uri for layer in image_layers)
    assert all("debugCapture" not in layer.source.uri for layer in image_layers)
    assert all(layer.transform.position.keyframes for layer in image_layers[1:])

    text = {
        str(layer.source.params.get("text") or "")
        for layer in composition.layers
        if layer.layer_type == "text"
    }
    assert {"NIGHT", "SHIFT", "TIGER STUDIO"} <= text
