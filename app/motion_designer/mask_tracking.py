"""Qt-free sampled tracking data used by Motion Designer masks."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .curves import interpolate_value


def _pair(value: Sequence[float] | None, default: tuple[float, float]) -> tuple[float, float]:
    values = list(value or default)
    if len(values) < 2:
        return default
    return float(values[0]), float(values[1])


@dataclass(slots=True)
class MotionTrackSample:
    time_ms: int = 0
    translate: tuple[float, float] = (0.0, 0.0)
    scale: tuple[float, float] = (1.0, 1.0)
    rotation: float = 0.0
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_ms": int(self.time_ms),
            "translate": list(self.translate),
            "scale": list(self.scale),
            "rotation": float(self.rotation),
            "confidence": float(self.confidence),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MotionTrackSample":
        return cls(
            time_ms=int(data.get("time_ms", 0) or 0),
            translate=_pair(data.get("translate"), (0.0, 0.0)),
            scale=_pair(data.get("scale"), (1.0, 1.0)),
            rotation=float(data.get("rotation", 0.0) or 0.0),
            confidence=max(0.0, min(1.0, float(data.get("confidence", 1.0) or 0.0))),
        )


@dataclass(slots=True)
class MotionTrackingCache:
    mode: str = "point"
    enabled: bool = True
    origin: tuple[float, float] = (0.0, 0.0)
    samples: list[MotionTrackSample] = field(default_factory=list)
    source_revision: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "enabled": bool(self.enabled),
            "origin": list(self.origin),
            "samples": [sample.to_dict() for sample in self.samples],
            "source_revision": self.source_revision,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "MotionTrackingCache":
        data = data if isinstance(data, Mapping) else {}
        mode = str(data.get("mode") or "point").lower()
        if mode not in {"point", "planar"}:
            mode = "point"
        samples = [
            MotionTrackSample.from_dict(item)
            for item in data.get("samples", [])
            if isinstance(item, Mapping)
        ]
        samples.sort(key=lambda sample: sample.time_ms)
        return cls(
            mode=mode,
            enabled=bool(data.get("enabled", True)),
            origin=_pair(data.get("origin"), (0.0, 0.0)),
            samples=samples,
            source_revision=str(data.get("source_revision") or ""),
            metadata=dict(data.get("metadata") or {}),
        )


def evaluate_tracking_cache(
    cache: MotionTrackingCache | Mapping[str, Any] | None,
    time_ms: float,
) -> MotionTrackSample:
    if not isinstance(cache, MotionTrackingCache):
        cache = MotionTrackingCache.from_dict(cache)
    if not cache.enabled or not cache.samples:
        return MotionTrackSample(time_ms=int(round(time_ms)))
    samples = cache.samples
    if time_ms <= samples[0].time_ms:
        return samples[0]
    if time_ms >= samples[-1].time_ms:
        return samples[-1]
    for left, right in zip(samples, samples[1:]):
        if left.time_ms <= time_ms <= right.time_ms:
            span = max(1.0, float(right.time_ms - left.time_ms))
            amount = (float(time_ms) - left.time_ms) / span
            if cache.mode == "point":
                scale = (1.0, 1.0)
                rotation = 0.0
            else:
                scale = tuple(interpolate_value(left.scale, right.scale, amount))
                rotation = float(interpolate_value(left.rotation, right.rotation, amount))
            return MotionTrackSample(
                time_ms=int(round(time_ms)),
                translate=tuple(interpolate_value(left.translate, right.translate, amount)),
                scale=scale,
                rotation=rotation,
                confidence=float(interpolate_value(left.confidence, right.confidence, amount)),
            )
    return samples[-1]
