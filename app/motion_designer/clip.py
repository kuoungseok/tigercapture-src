"""Main-timeline Motion Clip schema."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .schema import new_motion_id


@dataclass(slots=True)
class MotionClip:
    id: str = field(default_factory=lambda: new_motion_id("motion_clip"))
    composition_id: str = ""
    name: str = "Motion Clip"
    start_ms: int = 0
    duration_ms: int = 5000
    source_in_ms: int = 0
    time_scale: float = 1.0
    loop: bool = False
    enabled: bool = True
    opacity: float = 1.0
    z_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.duration_ms

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "composition_id": self.composition_id, "name": self.name,
                "start_ms": int(self.start_ms), "end_ms": int(self.end_ms), "duration_ms": int(self.duration_ms),
                "source_in_ms": int(self.source_in_ms), "time_scale": float(self.time_scale), "loop": self.loop,
                "enabled": self.enabled, "opacity": float(self.opacity), "z_index": int(self.z_index),
                "metadata": dict(self.metadata)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MotionClip":
        start = int(data.get("start_ms", 0) or 0)
        duration = int(data.get("duration_ms", 0) or 0)
        if duration <= 0:
            duration = max(1, int(data.get("end_ms", start + 5000) or start + 5000) - start)
        return cls(
            id=str(data.get("id") or new_motion_id("motion_clip")),
            composition_id=str(data.get("composition_id") or ""), name=str(data.get("name") or "Motion Clip"),
            start_ms=start, duration_ms=duration, source_in_ms=int(data.get("source_in_ms", 0) or 0),
            time_scale=float(data.get("time_scale", 1.0) or 1.0), loop=bool(data.get("loop", False)),
            enabled=bool(data.get("enabled", True)), opacity=max(0.0, min(1.0, float(data.get("opacity", 1.0)))),
            z_index=int(data.get("z_index", 0) or 0), metadata=dict(data.get("metadata") or {}),
        )
