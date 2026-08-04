"""Deterministic layer-aware motion choreography for decomposed images."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
from typing import Any, Iterable, Mapping, Sequence


MOTION_VARIANTS = ("auto", "clean", "dynamic", "collage")


def _value(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _metadata(item: Any) -> dict[str, Any]:
    return dict(_value(item, "metadata", {}) or {})


def infer_motion_variant(
    *,
    requested: str = "auto",
    prompt: str = "",
    motion_style: str = "",
) -> str:
    normalized = str(requested or "auto").strip().casefold()
    if normalized not in MOTION_VARIANTS:
        raise ValueError(f"unsupported layered motion variant: {requested}")
    if normalized != "auto":
        return normalized
    text = f"{prompt} {motion_style}".casefold()
    if any(token in text for token in ("collage", "comic", "poster", "콜라주", "팝아트")):
        return "collage"
    if any(token in text for token in ("dynamic", "active", "impact", "fast", "화려", "역동", "강렬")):
        return "dynamic"
    return "clean"


def _stable_unit(value: str, offset: int = 0) -> float:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    index = offset % (len(digest) - 1)
    number = int.from_bytes(digest[index:index + 2], "big")
    return number / 65535.0


@dataclass(slots=True)
class CameraMotionCue:
    end_offset_ratio: tuple[float, float]
    end_scale: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "end_offset_ratio": list(self.end_offset_ratio),
            "end_scale": float(self.end_scale),
        }


@dataclass(slots=True)
class LayerMotionCue:
    element_id: str
    start_ms: int
    settle_ms: int
    start_offset_ratio: tuple[float, float]
    end_offset_ratio: tuple[float, float]
    start_scale: float
    end_scale: float
    start_rotation: float
    end_rotation: float
    behavior: str
    behavior_params: dict[str, Any]
    fade_in: bool
    lock_to_background: bool
    lock_to_parent: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "start_ms": int(self.start_ms),
            "settle_ms": int(self.settle_ms),
            "start_offset_ratio": list(self.start_offset_ratio),
            "end_offset_ratio": list(self.end_offset_ratio),
            "start_scale": float(self.start_scale),
            "end_scale": float(self.end_scale),
            "start_rotation": float(self.start_rotation),
            "end_rotation": float(self.end_rotation),
            "behavior": self.behavior,
            "behavior_params": dict(self.behavior_params),
            "fade_in": bool(self.fade_in),
            "lock_to_background": bool(self.lock_to_background),
            "lock_to_parent": bool(self.lock_to_parent),
        }


@dataclass(slots=True)
class MotionChoreographyPlan:
    variant: str
    camera: CameraMotionCue
    layers: list[LayerMotionCue]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "camera": self.camera.to_dict(),
            "layers": [item.to_dict() for item in self.layers],
            "warnings": list(self.warnings),
        }

    def by_element_id(self) -> dict[str, LayerMotionCue]:
        return {item.element_id: item for item in self.layers}


def _delay_for_index(
    index: int,
    *,
    duration_ms: int,
    base_step_ms: int,
    audio_hits_ms: Sequence[int],
) -> int:
    fallback = min(max(0, duration_ms - 280), 90 + index * base_step_ms)
    usable = sorted(
        int(value)
        for value in audio_hits_ms
        if 0 <= int(value) <= max(0, duration_ms - 180)
    )
    if not usable:
        return fallback
    return usable[index % len(usable)]


def plan_motion_choreography(
    elements: Iterable[Any],
    *,
    duration_ms: int,
    max_camera_travel_ratio: float,
    requested_variant: str = "auto",
    prompt: str = "",
    motion_style: str = "",
    audio_hits_ms: Sequence[int] = (),
    max_simultaneous_motion: int = 3,
) -> MotionChoreographyPlan:
    variant = infer_motion_variant(
        requested=requested_variant,
        prompt=prompt,
        motion_style=motion_style,
    )
    profiles = {
        "clean": {
            "camera": 0.008,
            "camera_scale": 1.055,
            "travel": 0.014,
            "rotation": 0.25,
            "step": 140,
            "overshoot": 0.035,
        },
        "dynamic": {
            "camera": 0.014,
            "camera_scale": 1.095,
            "travel": 0.036,
            "rotation": 0.9,
            "step": 110,
            "overshoot": 0.12,
        },
        "collage": {
            "camera": 0.018,
            "camera_scale": 1.115,
            "travel": 0.052,
            "rotation": 2.2,
            "step": 82,
            "overshoot": 0.16,
        },
    }
    profile = profiles[variant]
    camera_direction_length = math.hypot(1.0, 0.5)
    camera_travel = min(
        float(profile["camera"]),
        max(0.0, min(0.12, float(max_camera_travel_ratio)))
        / camera_direction_length,
    )
    camera = CameraMotionCue(
        end_offset_ratio=(-camera_travel, camera_travel * 0.5),
        end_scale=float(profile["camera_scale"]),
    )
    rows = [item for item in elements if str(_value(item, "role", "")) != "text"]
    cues: list[LayerMotionCue] = []
    for index, item in enumerate(rows):
        element_id = str(_value(item, "id", "") or f"element_{index + 1:02d}")
        role = str(_value(item, "role", "secondary_element") or "secondary_element")
        metadata = _metadata(item)
        lock_to_background = bool(metadata.get("motion_lock_to_background"))
        lock_to_parent = bool(metadata.get("parent_id")) and bool(metadata.get("rigid"))
        if lock_to_background or lock_to_parent:
            cues.append(LayerMotionCue(
                element_id=element_id,
                start_ms=0,
                settle_ms=0,
                start_offset_ratio=(0.0, 0.0),
                end_offset_ratio=camera.end_offset_ratio if lock_to_background else (0.0, 0.0),
                start_scale=1.0,
                end_scale=camera.end_scale if lock_to_background else 1.0,
                start_rotation=0.0,
                end_rotation=0.0,
                behavior="hold",
                behavior_params={},
                fade_in=False,
                lock_to_background=lock_to_background,
                lock_to_parent=lock_to_parent,
            ))
            continue

        depth = max(0.0, min(1.0, float(_value(item, "depth", 0.5))))
        depth_weight = 0.55 + depth * 0.8
        angle = _stable_unit(element_id, 0) * math.tau
        direction_x = math.cos(angle)
        direction_y = math.sin(angle)
        travel = float(profile["travel"]) * depth_weight
        if role == "primary_subject":
            travel *= 0.42
        end_offset = (
            travel * direction_x,
            travel * direction_y * 0.55,
        )
        start_offset = (
            -end_offset[0] * (0.25 if role == "primary_subject" else 0.65),
            -end_offset[1] * (0.25 if role == "primary_subject" else 0.65),
        )
        delay = (
            0
            if role == "primary_subject"
            else _delay_for_index(
                index,
                duration_ms=duration_ms,
                base_step_ms=int(profile["step"]),
                audio_hits_ms=audio_hits_ms,
            )
        )
        settle = min(max(1, duration_ms - 1), delay + (420 if variant == "clean" else 520))
        sign = -1.0 if _stable_unit(element_id, 3) < 0.5 else 1.0
        rotation = float(profile["rotation"]) * depth_weight * sign
        start_scale = 1.0 if role == "primary_subject" else 0.96 if variant == "clean" else 0.88
        end_scale = 1.025 + depth_weight * (0.012 if variant == "clean" else 0.027)
        cues.append(LayerMotionCue(
            element_id=element_id,
            start_ms=delay,
            settle_ms=settle,
            start_offset_ratio=start_offset,
            end_offset_ratio=end_offset,
            start_scale=start_scale,
            end_scale=end_scale,
            start_rotation=0.0 if role == "primary_subject" else -rotation * 0.55,
            end_rotation=rotation,
            behavior="fade" if variant == "clean" and role != "primary_subject" else "pop",
            behavior_params={
                "from": 1.0 if role == "primary_subject" else 0.78,
                "overshoot": (
                    0.025
                    if role == "primary_subject"
                    else float(profile["overshoot"])
                ),
                "hide_before": True,
                "hold_before": True,
                "hold_after": True,
                "easing": "ease_out",
            },
            fade_in=role != "primary_subject",
            lock_to_background=False,
            lock_to_parent=False,
        ))

    independent = [
        item for item in cues
        if not item.lock_to_background and not item.lock_to_parent
    ]
    signatures = {
        (
            round(item.end_offset_ratio[0], 4),
            round(item.end_offset_ratio[1], 4),
            item.start_ms,
        )
        for item in independent
    }
    warnings: list[str] = []
    if len(independent) > 1 and len(signatures) == 1:
        warnings.append("Independent layers received identical motion signatures.")
    limit = max(1, int(max_simultaneous_motion))
    active: list[int] = []
    for cue in sorted(independent, key=lambda item: (item.start_ms, item.element_id)):
        active = [value for value in active if value > cue.start_ms]
        if len(active) >= limit:
            original_duration = max(1, cue.settle_ms - cue.start_ms)
            cue.start_ms = min(active)
            cue.settle_ms = min(
                max(1, int(duration_ms) - 1),
                cue.start_ms + original_duration,
            )
            active = [value for value in active if value > cue.start_ms]
        active.append(cue.settle_ms)
    if any(
        sum(row.start_ms <= time_ms < row.settle_ms for row in independent) > limit
        for time_ms in sorted({row.start_ms for row in independent})
    ):
        warnings.append("Simultaneous motion limit could not be satisfied within the shot duration.")
    return MotionChoreographyPlan(
        variant=variant,
        camera=camera,
        layers=cues,
        warnings=warnings,
    )


__all__ = [
    "MOTION_VARIANTS",
    "CameraMotionCue",
    "LayerMotionCue",
    "MotionChoreographyPlan",
    "infer_motion_variant",
    "plan_motion_choreography",
]
