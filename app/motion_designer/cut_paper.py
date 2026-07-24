"""Editable cut-paper motion rig built from native Motion layers."""
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, pi, radians, sin
from random import Random
from typing import Any

from .schema import (
    AnimatedProperty,
    Keyframe,
    MotionComposition,
    MotionLayer,
    MotionMaskRef,
    MotionTransform,
    SourceRef,
)
from .vector_shapes import VectorPath, VectorPoint


@dataclass(frozen=True, slots=True)
class CutPaperRig:
    overlay: MotionLayer
    piece: MotionLayer
    edge_shadow: MotionLayer
    paper_fiber: MotionLayer
    scissors: MotionLayer

    @property
    def layers(self) -> list[MotionLayer]:
        return [
            self.overlay,
            self.piece,
            self.edge_shadow,
            self.paper_fiber,
            self.scissors,
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "tigerstudio.motion.cut_paper_rig.v1",
            "layer_ids": [layer.id for layer in self.layers],
            "roles": [str(layer.metadata.get("role") or "") for layer in self.layers],
        }


def _animated(
    default: Any,
    rows: list[tuple[int, Any]],
    value_type: str,
    *,
    interpolation: str = "bezier",
) -> AnimatedProperty:
    return AnimatedProperty(
        value_type=value_type,
        default=default,
        keyframes=[
            Keyframe(
                time_ms=int(time_ms),
                value=value,
                interpolation=interpolation,
                out_tangent=(0.2, 0.0),
                in_tangent=(0.8, 1.0),
            )
            for time_ms, value in rows
        ],
    )


def jagged_oval_path(
    *,
    center_x: float,
    center_y: float,
    radius_x: float,
    radius_y: float,
    seed: int = 17,
    points: int = 48,
    jitter: float = 0.035,
) -> VectorPath:
    """Create a deterministic, subtly irregular closed paper-cut contour."""
    rng = Random(int(seed))
    count = max(16, int(points))
    noise = [rng.uniform(-1.0, 1.0) for _ in range(count)]
    smoothed = [
        (noise[(index - 1) % count] + noise[index] * 2.0 + noise[(index + 1) % count])
        / 4.0
        for index in range(count)
    ]
    result: list[VectorPoint] = []
    for index in range(count):
        angle = -pi * 0.5 + index * 2.0 * pi / count
        amount = 1.0 + smoothed[index] * max(0.0, float(jitter))
        result.append(
            VectorPoint(
                (
                    float(center_x) + cos(angle) * float(radius_x) * amount,
                    float(center_y) + sin(angle) * float(radius_y) * amount,
                )
            )
        )
    return VectorPath(points=result, closed=True)


def _transform_point(layer: MotionLayer, point: tuple[float, float]) -> list[float]:
    params = layer.source.params
    width = float(params.get("width", 1.0) or 1.0)
    height = float(params.get("height", 1.0) or 1.0)
    position = list(layer.transform.position.default or [width * 0.5, height * 0.5])
    scale = list(layer.transform.scale.default or [1.0, 1.0])
    rotation = radians(float(layer.transform.rotation.default or 0.0))
    local_x = (float(point[0]) - width * 0.5) * float(scale[0])
    local_y = (float(point[1]) - height * 0.5) * float(scale[1])
    return [
        float(position[0]) + local_x * cos(rotation) - local_y * sin(rotation),
        float(position[1]) + local_x * sin(rotation) + local_y * cos(rotation),
    ]


def _path_samples(path: VectorPath, count: int) -> list[tuple[float, float]]:
    points = [point.position for point in path.points]
    if not points:
        return []
    result = []
    for index in range(max(2, int(count))):
        progress = index / max(1, count - 1)
        source_index = min(len(points) - 1, int(progress * len(points)))
        result.append(points[source_index])
    return result


def _clone_source_layer(layer: MotionLayer, *, name: str, role: str) -> MotionLayer:
    clone = MotionLayer.from_dict(layer.to_dict())
    clone.id = ""
    clone.name = name
    clone.parent_id = ""
    clone.effects = []
    clone.masks = []
    clone.behaviors = []
    clone.metadata = {
        "role": role,
        "cut_paper_source_layer_id": layer.id,
        "cut_paper_rig": True,
    }
    return MotionLayer.from_dict(clone.to_dict())


def build_cut_paper_rig(
    composition: MotionComposition,
    source_layer: MotionLayer,
    *,
    center_x: float,
    center_y: float,
    radius_x: float,
    radius_y: float,
    start_ms: int,
    cut_duration_ms: int = 1400,
    release_duration_ms: int = 700,
    seed: int = 17,
) -> CutPaperRig:
    """Build a five-layer editable cut-paper rig for one source layer."""
    start = max(0, int(start_ms))
    cut_end = min(composition.duration_ms, start + max(120, int(cut_duration_ms)))
    release_end = min(
        composition.duration_ms,
        cut_end + max(120, int(release_duration_ms)),
    )
    path = jagged_oval_path(
        center_x=center_x,
        center_y=center_y,
        radius_x=radius_x,
        radius_y=radius_y,
        seed=seed,
    )
    path_payload = path.to_dict()
    mask_common = {
        "path": AnimatedProperty(value_type="path", default=path_payload),
        "feather": AnimatedProperty(default=0.7),
        "expansion": AnimatedProperty(default=0.0),
    }

    overlay = _clone_source_layer(
        source_layer,
        name=f"{source_layer.name} / Cut Hole",
        role="cut_paper_hole_overlay",
    )
    overlay.masks = [
        MotionMaskRef(
            kind="path",
            mode="add",
            inverted=True,
            params={
                **mask_common,
                "opacity": _animated(
                    0.0,
                    [(0, 0.0), (cut_end - 1, 0.0), (cut_end, 1.0)],
                    "scalar",
                    interpolation="hold",
                ),
            },
            metadata={"cut_paper_role": "hole", "seed": int(seed)},
        )
    ]

    piece = _clone_source_layer(
        source_layer,
        name=f"{source_layer.name} / Cut Piece",
        role="cut_paper_piece",
    )
    piece.masks = [
        MotionMaskRef(
            kind="path",
            mode="add",
            params={
                **mask_common,
                "opacity": AnimatedProperty(default=1.0),
            },
            metadata={"cut_paper_role": "piece", "seed": int(seed)},
        )
    ]
    base_position = list(source_layer.transform.position.default)
    base_scale = list(source_layer.transform.scale.default)
    base_rotation = float(source_layer.transform.rotation.default or 0.0)
    piece.transform = MotionTransform.from_dict(source_layer.transform.to_dict())
    piece.transform.position = _animated(
        base_position,
        [
            (0, base_position),
            (cut_end, base_position),
            (
                release_end,
                [base_position[0] + radius_x * 0.18, base_position[1] + radius_y * 1.35],
            ),
        ],
        "vector2",
    )
    piece.transform.scale = _animated(
        base_scale,
        [
            (0, base_scale),
            (cut_end, base_scale),
            (release_end, [base_scale[0] * 1.035, base_scale[1] * 1.035]),
        ],
        "vector2",
    )
    piece.transform.rotation = _animated(
        base_rotation,
        [(0, base_rotation), (cut_end, base_rotation), (release_end, base_rotation + 17.0)],
        "scalar",
    )
    piece.transform.opacity = _animated(
        1.0,
        [(0, 1.0), (cut_end, 1.0), (release_end - 80, 0.92), (release_end, 0.0)],
        "scalar",
    )

    width = int(float(source_layer.source.params.get("width", composition.width)))
    height = int(float(source_layer.source.params.get("height", composition.height)))
    trim = _animated(
        {"start": 0.0, "end": 0.0, "offset": 0.0},
        [
            (0, {"start": 0.0, "end": 0.0, "offset": 0.0}),
            (start, {"start": 0.0, "end": 0.0, "offset": 0.0}),
            (cut_end, {"start": 0.0, "end": 1.0, "offset": 0.0}),
        ],
        "object",
        interpolation="linear",
    )
    guide_opacity = _animated(
        0.0,
        [
            (0, 0.0),
            (start, 1.0),
            (cut_end, 1.0),
            (min(release_end, cut_end + 180), 0.0),
        ],
        "scalar",
    )

    def guide_layer(name: str, role: str, stroke: str, stroke_width: float) -> MotionLayer:
        return MotionLayer(
            name=name,
            layer_type="shape",
            source=SourceRef(
                kind="shape",
                params={
                    "primitive": "path",
                    "width": width,
                    "height": height,
                    "path": path_payload,
                    "fill": "#00000000",
                    "stroke": stroke,
                    "stroke_width": stroke_width,
                    "cap": "round",
                    "join": "round",
                    "dash": [3.0, 2.0] if role == "cut_paper_fiber" else [],
                    "trim": trim.to_dict(),
                },
            ),
            transform=MotionTransform.from_dict(source_layer.transform.to_dict()),
            in_ms=source_layer.in_ms,
            out_ms=source_layer.out_ms,
            metadata={
                "role": role,
                "cut_paper_source_layer_id": source_layer.id,
                "cut_paper_rig": True,
            },
        )

    edge_shadow = guide_layer(
        f"{source_layer.name} / Cut Shadow",
        "cut_paper_edge_shadow",
        "#B8000000",
        8.0,
    )
    paper_fiber = guide_layer(
        f"{source_layer.name} / Paper Fiber",
        "cut_paper_fiber",
        "#E8F7F0E5",
        3.2,
    )
    edge_shadow.transform.opacity = guide_opacity
    paper_fiber.transform.opacity = guide_opacity

    samples = _path_samples(path, 22)
    scissor_positions: list[tuple[int, list[float]]] = []
    scissor_rotations: list[tuple[int, float]] = []
    for index, point in enumerate(samples):
        progress = index / max(1, len(samples) - 1)
        time_ms = round(start + (cut_end - start) * progress)
        next_point = samples[min(len(samples) - 1, index + 1)]
        mapped = _transform_point(source_layer, point)
        mapped_next = _transform_point(source_layer, next_point)
        angle = degrees(atan2(mapped_next[1] - mapped[1], mapped_next[0] - mapped[0]))
        scissor_positions.append((time_ms, mapped))
        scissor_rotations.append((time_ms, angle + 6.0))
    first_position = scissor_positions[0][1] if scissor_positions else [center_x, center_y]
    scissors = MotionLayer(
        name=f"{source_layer.name} / Scissors",
        layer_type="text",
        source=SourceRef(
            kind="typography",
            params={
                "text": "✂",
                "font_family": "Segoe UI Symbol",
                "font_size": 54,
                "font_weight": 600,
                "fill": "#F4EEE3",
                "stroke": "#1C1916",
                "stroke_width": 2.0,
                "shadow_color": "#7A000000",
                "shadow_offset_x": 4.0,
                "shadow_offset_y": 5.0,
                "alignment": "center",
                "width": 82,
                "height": 82,
            },
        ),
        transform=MotionTransform(
            position=_animated(first_position, scissor_positions, "vector2", interpolation="linear"),
            scale=AnimatedProperty(value_type="vector2", default=[1.0, 1.0]),
            rotation=_animated(0.0, scissor_rotations, "scalar", interpolation="linear"),
            opacity=_animated(
                0.0,
                [
                    (0, 0.0),
                    (max(0, start - 1), 0.0),
                    (start, 1.0),
                    (cut_end, 1.0),
                    (min(release_end, cut_end + 120), 0.0),
                ],
                "scalar",
            ),
            anchor=AnimatedProperty(value_type="vector2", default=[0.5, 0.5]),
        ),
        in_ms=0,
        out_ms=composition.duration_ms,
        metadata={
            "role": "cut_paper_scissors",
            "cut_paper_source_layer_id": source_layer.id,
            "cut_paper_rig": True,
        },
    )
    return CutPaperRig(overlay, piece, edge_shadow, paper_fiber, scissors)


__all__ = [
    "CutPaperRig",
    "build_cut_paper_rig",
    "jagged_oval_path",
]
