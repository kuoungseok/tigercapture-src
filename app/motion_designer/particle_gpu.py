"""GPU instance packets for shape particles."""
from __future__ import annotations

from hashlib import sha256
import math
from typing import Iterable

from .particles import simulate_particles
from .schema import MotionLayer
from .vector_gpu import VectorGpuInstance, VectorGpuMesh, VectorGpuPacket
from .vector_shapes import evaluate_source_param


def _triangle(vertices: list[float], points: Iterable[tuple[float, float]]) -> None:
    for x, y in points:
        vertices.extend((float(x), float(y), 1.0, 1.0, 1.0, 1.0))


def _mesh(shape: str) -> VectorGpuMesh:
    vertices: list[float] = []
    if shape == "square":
        _triangle(vertices, [(-.5, -.5), (.5, -.5), (.5, .5), (-.5, -.5), (.5, .5), (-.5, .5)])
    elif shape == "triangle":
        _triangle(vertices, [(0.0, -.5), (.5, .5), (-.5, .5)])
    else:
        segments = 24
        for index in range(segments):
            start = index / segments * math.tau
            end = (index + 1) / segments * math.tau
            _triangle(vertices, [(0.0, 0.0), (math.cos(start) * .5, math.sin(start) * .5),
                                 (math.cos(end) * .5, math.sin(end) * .5)])
    key = sha256(f"motion_particle_shape_v1:{shape}".encode("ascii")).hexdigest()
    return VectorGpuMesh(key, tuple(vertices), len(vertices) // 18)


def build_particle_gpu_packet(layer: MotionLayer, time_ms: float) -> tuple[VectorGpuPacket | None, str]:
    if layer.layer_type != "particle" or layer.source.kind != "particle":
        return None, "non_particle_layer"
    if layer.effects or layer.masks:
        return None, "layer_effect_or_mask"
    particle = evaluate_source_param(layer.source.params, "particle", time_ms, {})
    particle = particle if isinstance(particle, dict) else {}
    shape = str(particle.get("shape") or "circle").lower()
    if shape not in {"circle", "square", "triangle"}:
        return None, "sprite_particle_gpu_pending"
    width = max(1.0, float(evaluate_source_param(layer.source.params, "width", time_ms, 1280.0)))
    height = max(1.0, float(evaluate_source_param(layer.source.params, "height", time_ms, 720.0)))
    instances = []
    for state in simulate_particles(layer, time_ms):
        angle = math.radians(state.rotation_deg)
        cosine, sine = math.cos(angle) * state.size, math.sin(angle) * state.size
        red, green, blue, alpha = state.color
        instances.append(VectorGpuInstance(
            (cosine, sine, -sine, cosine, state.position[0], state.position[1]),
            state.opacity,
            (red * alpha, green * alpha, blue * alpha, alpha),
        ))
    return VectorGpuPacket(_mesh(shape), tuple(instances), width, height), ""


__all__ = ["build_particle_gpu_packet"]
