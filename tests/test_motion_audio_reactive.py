from app.motion_designer.audio_analysis import AudioAnalysisCache, AudioEnvelopeSample
from app.motion_designer.audio_reactive import (
    AudioReactiveBinding, bake_audio_reactive, compile_binding, set_layer_bindings,
)
from app.motion_designer.evaluator import evaluate_composition
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef


def _analysis() -> AudioAnalysisCache:
    return AudioAnalysisCache(
        source_signature="fixture", hop_ms=100,
        samples=[
            AudioEnvelopeSample(0, amplitude=0.0),
            AudioEnvelopeSample(100, amplitude=0.5),
            AudioEnvelopeSample(200, amplitude=1.0),
            AudioEnvelopeSample(300, amplitude=0.0),
            AudioEnvelopeSample(400, amplitude=0.0),
        ],
    )


def test_compiled_audio_binding_drives_preview_evaluator() -> None:
    layer = MotionLayer(name="Pulse", layer_type="shape", source=SourceRef(kind="shape"), out_ms=500)
    binding = compile_binding(AudioReactiveBinding(
        analysis_id="fixture", property_name="scale", channel="amplitude",
        mode="multiply", output_min=1.0, output_max=2.0,
        smoothing_ms=0, attack_ms=0, release_ms=0,
    ), _analysis())
    set_layer_bindings(layer, [binding])
    composition = MotionComposition(duration_ms=500, layers=[layer])
    assert evaluate_composition(composition, 0)[0].scale == [1.0, 1.0]
    assert evaluate_composition(composition, 200)[0].scale == [2.0, 2.0]
    assert evaluate_composition(composition, 250)[0].scale == [1.5, 1.5]


def test_audio_binding_attack_release_invert_and_bake_preserve_sampled_frames() -> None:
    layer = MotionLayer(name="Reactive", layer_type="shape", source=SourceRef(kind="shape"), out_ms=400)
    layer.transform.position.default = [100.0, 200.0]
    binding = compile_binding(AudioReactiveBinding(
        property_name="position", components=[1], channel="amplitude", mode="add",
        output_min=0.0, output_max=100.0, smoothing_ms=0, attack_ms=200, release_ms=300,
    ), _analysis())
    assert 0.0 < binding.curve[2][1] < 1.0
    assert binding.curve[3][1] > 0.0
    set_layer_bindings(layer, [binding])
    composition = MotionComposition(fps=10, duration_ms=400, layers=[layer])
    before = {time: evaluate_composition(composition, time)[0].position for time in (0, 100, 200, 300)}
    count = bake_audio_reactive(composition, layer, sample_fps=10)
    assert count == 25
    assert "audio_reactive_bindings" not in layer.metadata
    assert layer.behaviors == []
    for time, expected in before.items():
        assert evaluate_composition(composition, time)[0].position == expected


def test_inverted_binding_reverses_normalized_curve() -> None:
    binding = compile_binding(AudioReactiveBinding(
        property_name="opacity", mode="replace", output_min=0.0, output_max=1.0,
        invert=True, smoothing_ms=0, attack_ms=0, release_ms=0,
    ), _analysis())
    assert binding.curve[0][1] == 1.0
    assert binding.curve[2][1] == 0.0
