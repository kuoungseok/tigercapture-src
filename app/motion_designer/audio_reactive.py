"""Audio envelope bindings and deterministic transform baking."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping

from .audio_analysis import AUDIO_CHANNELS, AudioAnalysisCache, analysis_value_at
from .behaviors import apply_behaviors
from .keyframes import evaluate_property
from .schema import Keyframe, MotionComposition, MotionLayer, new_motion_id


AUDIO_REACTIVE_KEY = "audio_reactive_bindings"
TRANSFORM_PROPERTIES = ("position", "scale", "rotation", "opacity", "anchor")


@dataclass(slots=True)
class AudioReactiveBinding:
    id: str = field(default_factory=lambda: new_motion_id("audio_binding"))
    analysis_id: str = ""
    channel: str = "amplitude"
    property_name: str = "scale"
    components: list[int] = field(default_factory=lambda: [0, 1])
    mode: str = "multiply"
    output_min: float = 1.0
    output_max: float = 1.25
    smoothing_ms: int = 60
    attack_ms: int = 30
    release_ms: int = 140
    invert: bool = False
    clamp: bool = True
    enabled: bool = True
    curve: list[list[float]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "analysis_id": self.analysis_id, "channel": self.channel,
            "property_name": self.property_name, "components": [int(value) for value in self.components],
            "mode": self.mode, "output_min": float(self.output_min), "output_max": float(self.output_max),
            "smoothing_ms": int(self.smoothing_ms), "attack_ms": int(self.attack_ms),
            "release_ms": int(self.release_ms), "invert": bool(self.invert), "clamp": bool(self.clamp),
            "enabled": bool(self.enabled), "curve": [[float(x), float(y)] for x, y in self.curve],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AudioReactiveBinding":
        return cls(
            id=str(data.get("id") or new_motion_id("audio_binding")),
            analysis_id=str(data.get("analysis_id") or ""),
            channel=str(data.get("channel") or "amplitude").lower(),
            property_name=str(data.get("property_name") or "scale").lower(),
            components=[int(value) for value in data.get("components", [0, 1])],
            mode=str(data.get("mode") or "multiply").lower(),
            output_min=float(data.get("output_min", 1.0)), output_max=float(data.get("output_max", 1.25)),
            smoothing_ms=max(0, int(data.get("smoothing_ms", 60) or 0)),
            attack_ms=max(0, int(data.get("attack_ms", 30) or 0)),
            release_ms=max(0, int(data.get("release_ms", 140) or 0)),
            invert=bool(data.get("invert", False)), clamp=bool(data.get("clamp", True)),
            enabled=bool(data.get("enabled", True)),
            curve=[[float(row[0]), float(row[1])] for row in data.get("curve", []) if len(row) >= 2],
            metadata=dict(data.get("metadata") or {}),
        )


def validate_binding(binding: AudioReactiveBinding) -> None:
    if binding.channel not in AUDIO_CHANNELS:
        raise ValueError(f"unknown audio channel: {binding.channel}")
    if binding.property_name not in TRANSFORM_PROPERTIES:
        raise ValueError(f"unsupported transform property: {binding.property_name}")
    if binding.mode not in {"replace", "add", "multiply"}:
        raise ValueError(f"unsupported audio reactive mode: {binding.mode}")


def _smoothed_values(cache: AudioAnalysisCache, binding: AudioReactiveBinding) -> list[float]:
    raw = [analysis_value_at(cache, binding.channel, sample.time_ms) for sample in cache.samples]
    if not raw:
        return []
    radius = max(0, int(round(binding.smoothing_ms / max(1, cache.hop_ms))))
    if radius:
        prefix = [0.0]
        for value in raw:
            prefix.append(prefix[-1] + value)
        raw = [(prefix[min(len(raw), index + radius + 1)] - prefix[max(0, index - radius)]) /
               max(1, min(len(raw), index + radius + 1) - max(0, index - radius))
               for index in range(len(raw))]
    output = [raw[0]]
    for value in raw[1:]:
        previous = output[-1]
        time_constant = binding.attack_ms if value > previous else binding.release_ms
        alpha = 1.0 if time_constant <= 0 else min(1.0, cache.hop_ms / float(time_constant))
        output.append(previous + (value - previous) * alpha)
    if binding.invert:
        output = [1.0 - value for value in output]
    if binding.clamp:
        output = [max(0.0, min(1.0, value)) for value in output]
    return output


def compile_binding(binding: AudioReactiveBinding, cache: AudioAnalysisCache | Mapping[str, Any]) -> AudioReactiveBinding:
    analysis = cache if isinstance(cache, AudioAnalysisCache) else AudioAnalysisCache.from_dict(cache)
    validate_binding(binding)
    values = _smoothed_values(analysis, binding)
    compiled = AudioReactiveBinding.from_dict(binding.to_dict())
    compiled.curve = [[sample.time_ms, value] for sample, value in zip(analysis.samples, values)]
    compiled.metadata = {**compiled.metadata, "analysis_signature": analysis.source_signature,
                         "compiled_hop_ms": analysis.hop_ms}
    return compiled


def binding_value_at(binding: AudioReactiveBinding | Mapping[str, Any], time_ms: float) -> float:
    item = binding if isinstance(binding, AudioReactiveBinding) else AudioReactiveBinding.from_dict(binding)
    curve = item.curve
    if not curve or time_ms < curve[0][0] or time_ms > curve[-1][0]:
        return 0.0
    low, high = 0, len(curve) - 1
    while low + 1 < high:
        middle = (low + high) // 2
        if curve[middle][0] <= time_ms:
            low = middle
        else:
            high = middle
    left, right = curve[low], curve[high]
    if right[0] <= left[0]:
        normalized = float(left[1])
    else:
        t = (float(time_ms) - left[0]) / (right[0] - left[0])
        normalized = float(left[1]) + (float(right[1]) - float(left[1])) * t
    return item.output_min + (item.output_max - item.output_min) * normalized


def layer_bindings(layer: MotionLayer) -> list[AudioReactiveBinding]:
    rows = layer.metadata.get(AUDIO_REACTIVE_KEY, [])
    return [AudioReactiveBinding.from_dict(row) for row in rows if isinstance(row, Mapping)]


def set_layer_bindings(layer: MotionLayer, bindings: list[AudioReactiveBinding]) -> None:
    layer.metadata[AUDIO_REACTIVE_KEY] = [binding.to_dict() for binding in bindings]


def _apply_value(current: float, amount: float, mode: str) -> float:
    if mode == "replace":
        return amount
    if mode == "add":
        return current + amount
    return current * amount


def apply_audio_reactive(values: MutableMapping[str, Any], layer: MotionLayer,
                         composition_time_ms: float) -> None:
    for binding in layer_bindings(layer):
        if not binding.enabled or not binding.curve:
            continue
        amount = binding_value_at(binding, composition_time_ms)
        current = values.get(binding.property_name)
        if isinstance(current, (list, tuple)):
            changed = [float(value) for value in current]
            components = binding.components or list(range(len(changed)))
            for component in components:
                if 0 <= component < len(changed):
                    changed[component] = _apply_value(changed[component], amount, binding.mode)
            values[binding.property_name] = changed
        elif current is not None:
            values[binding.property_name] = _apply_value(float(current), amount, binding.mode)


def evaluate_layer_transform(layer: MotionLayer, composition_time_ms: float,
                             *, include_audio: bool = True) -> dict[str, Any]:
    from .evaluator import remap_layer_time

    local_time = remap_layer_time(layer, composition_time_ms)
    values = {name: evaluate_property(prop, local_time) for name, prop in layer.transform.properties().items()}
    values["position"] = list(values["position"])
    values["scale"] = list(values["scale"])
    values["anchor"] = list(values["anchor"])
    apply_behaviors(values, layer.behaviors, local_time)
    if include_audio:
        apply_audio_reactive(values, layer, composition_time_ms)
    return values


def bake_audio_reactive(composition: MotionComposition, layer: MotionLayer, *, sample_fps: float | None = None) -> int:
    bindings = layer_bindings(layer)
    if not bindings:
        return 0
    fps = max(1.0, min(120.0, float(sample_fps or composition.fps)))
    step_ms = 1000.0 / fps
    times: list[int] = []
    cursor = max(0.0, float(layer.in_ms))
    end = min(float(composition.duration_ms), float(layer.out_ms))
    while cursor < end:
        times.append(int(round(cursor)))
        cursor += step_ms
    if not times or times[-1] != int(end):
        times.append(int(end))
    sampled = [(time, evaluate_layer_transform(layer, time, include_audio=True)) for time in times]
    for name, prop in layer.transform.properties().items():
        prop.keyframes = [Keyframe(time_ms=time, value=values[name], interpolation="linear",
                                   metadata={"baked_from": "audio_reactive"})
                          for time, values in sampled]
    baked = sum(len(prop.keyframes) for prop in layer.transform.properties().values())
    layer.behaviors = []
    layer.metadata.pop(AUDIO_REACTIVE_KEY, None)
    return baked


__all__ = [
    "AUDIO_REACTIVE_KEY", "AudioReactiveBinding", "apply_audio_reactive", "bake_audio_reactive",
    "binding_value_at", "compile_binding", "evaluate_layer_transform", "layer_bindings",
    "set_layer_bindings", "validate_binding",
]
