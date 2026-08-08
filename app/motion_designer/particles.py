"""Deterministic particle simulation shared by preview, export, and actions."""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import random
from typing import Any, Mapping, Sequence

from .schema import MotionLayer, SourceRef
from .vector_shapes import evaluate_source_param


PARTICLE_SOURCE_KIND = "particle"
EMITTER_KINDS = {"point", "box", "circle", "path"}
PARTICLE_SHAPES = {"circle", "square", "triangle", "sprite"}
PARTICLE_BLEND_MODES = {"normal", "add", "screen"}
MAX_PARTICLES_HARD_LIMIT = 20000


@dataclass(frozen=True, slots=True)
class ParticleState:
    id: int
    birth_time_ms: float
    age_ms: float
    life_progress: float
    position: tuple[float, float]
    rotation_deg: float
    size: float
    opacity: float
    color: tuple[float, float, float, float]
    depth: float


def default_particle_params(width: int = 1280, height: int = 720) -> dict[str, Any]:
    return {
        "width": int(width),
        "height": int(height),
        "emitter": {"kind": "point", "position": [width * 0.5, height * 0.5], "size": [240.0, 120.0],
                    "radius": 120.0, "path": []},
        "birth_rate": 36.0,
        "bursts": [{"time_ms": 0, "count": 24}],
        "lifetime_ms": 1800.0,
        "lifetime_variance": 0.2,
        "velocity": {"speed": 150.0, "speed_variance": 0.35, "angle_deg": -90.0, "spread_deg": 70.0},
        "gravity": [0.0, 110.0],
        "turbulence": {"strength": 18.0, "frequency": 1.4},
        "particle": {
            "shape": "circle", "size_start": 18.0, "size_end": 4.0,
            "opacity_start": 1.0, "opacity_end": 0.0,
            "color_start": "#69e0c4", "color_end": "#f1c75b00",
            "rotation_speed": 35.0, "sprite_uri": "",
        },
        "seed": 1337,
        "max_particles": 2000,
        "depth_sort": "back_to_front",
    }


def create_particle_layer(*, width: int = 1280, height: int = 720, duration_ms: int = 5000,
                          name: str = "Particle Emitter", params: Mapping[str, Any] | None = None) -> MotionLayer:
    values = default_particle_params(width, height)
    if params:
        values.update(dict(params))
    layer = MotionLayer(
        name=name, layer_type=PARTICLE_SOURCE_KIND,
        source=SourceRef(kind=PARTICLE_SOURCE_KIND, params=values),
        out_ms=max(1, int(duration_ms)),
    )
    layer.transform.position.default = [width * 0.5, height * 0.5]
    return layer


def update_particle_params(layer: MotionLayer, changes: Mapping[str, Any]) -> None:
    if layer.layer_type != PARTICLE_SOURCE_KIND or layer.source.kind != PARTICLE_SOURCE_KIND:
        raise ValueError("particle settings require a particle layer")

    def merge(target: dict[str, Any], incoming: Mapping[str, Any]) -> None:
        for key, value in incoming.items():
            if isinstance(value, Mapping) and isinstance(target.get(key), Mapping):
                nested = dict(target[key])
                merge(nested, value)
                target[str(key)] = nested
            else:
                target[str(key)] = value

    params = dict(layer.source.params)
    merge(params, changes)
    layer.source.params = params


def _sequence(value: Any, fallback: Sequence[float], size: int = 2) -> list[float]:
    source = value if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else fallback
    result = [float(item) for item in source[:size]]
    while len(result) < size:
        result.append(float(fallback[len(result)]))
    return result


def _color(value: Any, fallback: str = "#ffffff") -> tuple[float, float, float, float]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        channels = [float(item) for item in value]
        scale = 255.0 if channels and max(channels) > 1.0 else 1.0
        while len(channels) < 4:
            channels.append(scale)
        return tuple(max(0.0, min(1.0, item / scale)) for item in channels[:4])
    text = str(value or fallback).strip().lstrip("#")
    if len(text) in {3, 4}:
        text = "".join(char * 2 for char in text)
    if len(text) == 6:
        text += "ff"
    try:
        return tuple(int(text[index:index + 2], 16) / 255.0 for index in range(0, 8, 2))
    except (ValueError, TypeError):
        return _color(fallback, "#ffffff") if value != fallback else (1.0, 1.0, 1.0, 1.0)


def _lerp(left: float, right: float, amount: float) -> float:
    return float(left) + (float(right) - float(left)) * amount


def _emitter_position(emitter: Mapping[str, Any], rng: random.Random) -> tuple[float, float]:
    center = _sequence(emitter.get("position"), (0.0, 0.0))
    kind = str(emitter.get("kind") or "point").lower()
    if kind == "box":
        width, height = _sequence(emitter.get("size"), (100.0, 100.0))
        return center[0] + rng.uniform(-width * 0.5, width * 0.5), center[1] + rng.uniform(-height * 0.5, height * 0.5)
    if kind == "circle":
        radius = max(0.0, float(emitter.get("radius", 100.0) or 0.0)) * math.sqrt(rng.random())
        angle = rng.random() * math.tau
        return center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius
    if kind == "path":
        points = [_sequence(item.get("position") if isinstance(item, Mapping) else item, (0.0, 0.0))
                  for item in emitter.get("path", [])]
        if len(points) >= 2:
            lengths = [math.dist(points[index - 1], points[index]) for index in range(1, len(points))]
            total = sum(lengths)
            distance = rng.random() * total if total > 0.0 else 0.0
            for index, length in enumerate(lengths, 1):
                if distance <= length or index == len(lengths):
                    amount = 0.0 if length <= 1e-9 else distance / length
                    return _lerp(points[index - 1][0], points[index][0], amount), _lerp(points[index - 1][1], points[index][1], amount)
                distance -= length
    return center[0], center[1]


def _birth_events(params: Mapping[str, Any], time_ms: float, maximum: int) -> list[tuple[float, int]]:
    events: list[tuple[float, int]] = []
    rate = max(0.0, float(evaluate_source_param(params, "birth_rate", time_ms, 0.0)))
    if rate > 0.0 and time_ms >= 0.0:
        count = min(maximum, int(math.floor(time_ms * rate / 1000.0)) + 1)
        events.extend((index * 1000.0 / rate, index) for index in range(count))
    serial = len(events)
    bursts = evaluate_source_param(params, "bursts", time_ms, [])
    for burst_index, burst in enumerate(bursts if isinstance(bursts, list) else []):
        if not isinstance(burst, Mapping):
            continue
        birth = max(0.0, float(burst.get("time_ms", 0.0) or 0.0))
        if birth > time_ms:
            continue
        count = max(0, int(burst.get("count", 0) or 0))
        for item_index in range(count):
            events.append((birth, serial + burst_index * 100000 + item_index))
            if len(events) >= maximum:
                break
        if len(events) >= maximum:
            break
    events.sort(key=lambda row: (row[0], row[1]))
    return events[:maximum]


def simulate_particles(layer: MotionLayer, time_ms: float) -> list[ParticleState]:
    params = layer.source.params
    maximum = max(0, min(MAX_PARTICLES_HARD_LIMIT, int(evaluate_source_param(params, "max_particles", time_ms, 2000))))
    seed = int(evaluate_source_param(params, "seed", time_ms, 0))
    lifetime = max(1.0, float(evaluate_source_param(params, "lifetime_ms", time_ms, 1000.0)))
    lifetime_variance = max(0.0, min(0.95, float(evaluate_source_param(params, "lifetime_variance", time_ms, 0.0))))
    emitter = evaluate_source_param(params, "emitter", time_ms, {})
    emitter = emitter if isinstance(emitter, Mapping) else {}
    velocity = evaluate_source_param(params, "velocity", time_ms, {})
    velocity = velocity if isinstance(velocity, Mapping) else {}
    gravity = _sequence(evaluate_source_param(params, "gravity", time_ms, [0.0, 0.0]), (0.0, 0.0))
    turbulence = evaluate_source_param(params, "turbulence", time_ms, {})
    turbulence = turbulence if isinstance(turbulence, Mapping) else {}
    particle = evaluate_source_param(params, "particle", time_ms, {})
    particle = particle if isinstance(particle, Mapping) else {}
    speed = float(velocity.get("speed", 100.0) or 0.0)
    speed_variance = max(0.0, float(velocity.get("speed_variance", 0.0) or 0.0))
    angle = float(velocity.get("angle_deg", -90.0) or 0.0)
    spread = float(velocity.get("spread_deg", 0.0) or 0.0)
    turbulence_strength = float(turbulence.get("strength", 0.0) or 0.0)
    turbulence_frequency = float(turbulence.get("frequency", 1.0) or 0.0)
    color_start = _color(particle.get("color_start"), "#ffffff")
    color_end = _color(particle.get("color_end"), "#ffffff00")
    states: list[ParticleState] = []
    for particle_id, (birth_time, birth_serial) in enumerate(_birth_events(params, float(time_ms), maximum)):
        rng = random.Random((seed * 1000003 + birth_serial * 9176 + 0x9E3779B9) & 0xFFFFFFFF)
        actual_lifetime = lifetime * (1.0 + rng.uniform(-lifetime_variance, lifetime_variance))
        age = float(time_ms) - birth_time
        if age < 0.0 or age >= actual_lifetime:
            continue
        progress = max(0.0, min(1.0, age / actual_lifetime))
        origin_x, origin_y = _emitter_position(emitter, rng)
        actual_speed = speed * (1.0 + rng.uniform(-speed_variance, speed_variance))
        actual_angle = math.radians(angle + rng.uniform(-spread * 0.5, spread * 0.5))
        velocity_x, velocity_y = math.cos(actual_angle) * actual_speed, math.sin(actual_angle) * actual_speed
        seconds = age / 1000.0
        phase = rng.random() * math.tau
        turbulence_x = math.sin(seconds * turbulence_frequency * math.tau + phase) * turbulence_strength
        turbulence_y = math.cos(seconds * turbulence_frequency * math.tau * 0.73 + phase) * turbulence_strength
        position = (
            origin_x + velocity_x * seconds + 0.5 * gravity[0] * seconds * seconds + turbulence_x,
            origin_y + velocity_y * seconds + 0.5 * gravity[1] * seconds * seconds + turbulence_y,
        )
        size = max(0.0, _lerp(float(particle.get("size_start", 16.0)), float(particle.get("size_end", 0.0)), progress))
        opacity = max(0.0, min(1.0, _lerp(float(particle.get("opacity_start", 1.0)), float(particle.get("opacity_end", 0.0)), progress)))
        color = tuple(_lerp(color_start[index], color_end[index], progress) for index in range(4))
        states.append(ParticleState(
            id=particle_id, birth_time_ms=birth_time, age_ms=age, life_progress=progress,
            position=position, rotation_deg=rng.uniform(0.0, 360.0) + float(particle.get("rotation_speed", 0.0)) * seconds,
            size=size, opacity=opacity, color=color, depth=rng.uniform(-1.0, 1.0),
        ))
    if str(evaluate_source_param(params, "depth_sort", time_ms, "back_to_front")) == "back_to_front":
        states.sort(key=lambda item: (item.depth, item.id))
    return states


def particle_diagnostics(layer: MotionLayer, time_ms: float) -> dict[str, Any]:
    params = layer.source.params
    states = simulate_particles(layer, time_ms)
    particle = params.get("particle") if isinstance(params.get("particle"), Mapping) else {}
    shape = str(particle.get("shape") or "circle").lower()
    sprite_uri = str(particle.get("sprite_uri") or "")
    return {
        "source_kind": PARTICLE_SOURCE_KIND,
        "particle_count": len(states),
        "seed": int(evaluate_source_param(params, "seed", time_ms, 0)),
        "shape": shape,
        "sprite_exists": bool(sprite_uri and Path(sprite_uri).is_file()),
        "gpu_preview_eligible": shape in {"circle", "square", "triangle"},
        "deterministic": True,
        "blend_mode": layer.blend_mode,
    }


__all__ = [
    "EMITTER_KINDS", "MAX_PARTICLES_HARD_LIMIT", "PARTICLE_BLEND_MODES", "PARTICLE_SHAPES",
    "PARTICLE_SOURCE_KIND", "ParticleState", "create_particle_layer", "default_particle_params",
    "particle_diagnostics", "simulate_particles", "update_particle_params",
]
