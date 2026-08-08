"""Editable paper-paste rig assembled from native Motion layers and effects."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .schema import (
    AnimatedProperty,
    Keyframe,
    MotionBehaviorRef,
    MotionComposition,
    MotionEffectRef,
    MotionLayer,
    MotionTransform,
    SourceRef,
)


@dataclass(frozen=True, slots=True)
class PaperPasteRig:
    shadow: MotionLayer
    tape_left: MotionLayer
    tape_right: MotionLayer
    staple_left: MotionLayer
    staple_right: MotionLayer

    @property
    def layers(self) -> list[MotionLayer]:
        return [self.shadow, self.tape_left, self.tape_right, self.staple_left, self.staple_right]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "tigerstudio.motion.paper_paste_rig.v1",
            "layer_ids": [layer.id for layer in self.layers],
            "roles": [str(layer.metadata.get("role") or "") for layer in self.layers],
        }


def _animated(default: Any, rows: list[tuple[int, Any]], value_type: str = "scalar") -> AnimatedProperty:
    return AnimatedProperty(
        value_type=value_type,
        default=default,
        keyframes=[
            Keyframe(
                time_ms=max(0, int(time_ms)),
                value=value,
                interpolation="bezier",
                out_tangent=(0.16, 0.0),
                in_tangent=(0.78, 1.0),
            )
            for time_ms, value in rows
        ],
    )


def _attached_shape(
    source: MotionLayer,
    *,
    name: str,
    role: str,
    width: float,
    height: float,
    fill: str,
    position: tuple[float, float],
    rotation: float,
    start_ms: int,
    duration_ms: int,
    radius: float = 0.0,
) -> MotionLayer:
    settle = min(duration_ms, start_ms + 180)
    return MotionLayer(
        name=name,
        layer_type="shape",
        parent_id=source.id,
        source=SourceRef(kind="shape", params={
            "primitive": "rectangle",
            "width": width,
            "height": height,
            "radius": radius,
            "fill": fill,
            "stroke": "#00000000",
            "stroke_width": 0.0,
        }),
        transform=MotionTransform(
            position=AnimatedProperty(value_type="vector2", default=list(position)),
            scale=_animated(
                [1.0, 1.0],
                [(0, [0.0, 1.0]), (max(0, start_ms - 1), [0.0, 1.0]), (settle, [1.0, 1.0])],
                "vector2",
            ),
            rotation=AnimatedProperty(default=rotation),
            opacity=_animated(
                1.0,
                [(0, 0.0), (max(0, start_ms - 1), 0.0), (start_ms, 0.92)],
            ),
            anchor=AnimatedProperty(value_type="vector2", default=[0.5, 0.5]),
        ),
        out_ms=duration_ms,
        metadata={"role": role, "paper_source_layer_id": source.id, "paper_paste_rig": True},
    )


def build_paper_paste_rig(
    composition: MotionComposition,
    source: MotionLayer,
    *,
    start_ms: int,
    tape_color: str = "#BFD8C9A8",
    fold_strength: float = 0.32,
) -> PaperPasteRig:
    """Attach editable shadow, tape, staples, fold shading, and impact response."""
    params = source.source.params
    width = max(40.0, float(params.get("width", 320.0) or 320.0))
    height = max(40.0, float(params.get("height", 180.0) or 180.0))
    duration = composition.duration_ms
    start = max(0, min(duration - 1, int(start_ms)))

    shadow = MotionLayer(
        name=f"{source.name} / Paper Shadow",
        layer_type="shape",
        parent_id=source.id,
        source=SourceRef(kind="shape", params={
            "primitive": "rectangle",
            "width": width,
            "height": height,
            "radius": 2.0,
            "fill": "#74000000",
            "stroke": "#00000000",
            "stroke_width": 0.0,
        }),
        transform=MotionTransform(
            position=AnimatedProperty(value_type="vector2", default=[12.0, 14.0]),
            scale=AnimatedProperty(value_type="vector2", default=[1.0, 1.0]),
            rotation=AnimatedProperty(default=0.0),
            opacity=_animated(0.52, [(0, 0.0), (start, 0.0), (min(duration, start + 240), 0.52)]),
            anchor=AnimatedProperty(value_type="vector2", default=[0.5, 0.5]),
        ),
        effects=[
            MotionEffectRef(kind="gaussian_blur", params={"radius": AnimatedProperty(default=9.0)}),
        ],
        out_ms=duration,
        blend_mode="multiply",
        metadata={"role": "paper_contact_shadow", "paper_source_layer_id": source.id, "paper_paste_rig": True},
    )
    tape_left = _attached_shape(
        source, name=f"{source.name} / Tape Left", role="paper_tape",
        width=min(96.0, width * 0.28), height=24.0, fill=tape_color,
        position=(-width * 0.28, -height * 0.47), rotation=-8.0,
        start_ms=start + 190, duration_ms=duration, radius=1.0,
    )
    tape_right = _attached_shape(
        source, name=f"{source.name} / Tape Right", role="paper_tape",
        width=min(96.0, width * 0.28), height=24.0, fill=tape_color,
        position=(width * 0.28, -height * 0.47), rotation=7.0,
        start_ms=start + 250, duration_ms=duration, radius=1.0,
    )
    staple_left = _attached_shape(
        source, name=f"{source.name} / Staple Left", role="paper_staple",
        width=24.0, height=3.0, fill="#C9CBC9",
        position=(-width * 0.38, height * 0.42), rotation=-12.0,
        start_ms=start + 330, duration_ms=duration,
    )
    staple_right = _attached_shape(
        source, name=f"{source.name} / Staple Right", role="paper_staple",
        width=24.0, height=3.0, fill="#C9CBC9",
        position=(width * 0.38, height * 0.42), rotation=11.0,
        start_ms=start + 370, duration_ms=duration,
    )
    source.effects.append(MotionEffectRef(
        kind="paper_fold",
        params={
            "strength": AnimatedProperty(default=max(0.0, min(1.0, float(fold_strength)))),
            "angle": AnimatedProperty(default=-18.0),
            "width": AnimatedProperty(default=max(14.0, width * 0.11)),
        },
        metadata={"paper_paste_rig": True},
    ))
    source.behaviors.append(MotionBehaviorRef(
        kind="impact",
        start_ms=start,
        end_ms=min(duration, start + 620),
        params={
            "scale_overshoot": 0.12,
            "rotation_kick": -4.0,
            "shake": 9.0,
            "frequency": 4.5,
            "damping": 6.0,
            "hold_after": True,
        },
        metadata={"paper_paste_rig": True},
    ))
    source.metadata["motion_blur"] = {"enabled": True, "samples": 8, "shutter": 0.72}
    source.metadata["paper_paste_rig"] = True
    return PaperPasteRig(shadow, tape_left, tape_right, staple_left, staple_right)


__all__ = ["PaperPasteRig", "build_paper_paste_rig"]
