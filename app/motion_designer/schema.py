"""Serializable Motion Designer composition schema."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .color_management import default_motion_metadata
from uuid import uuid4


MOTION_SCHEMA_VERSION = 1


def new_motion_id(prefix: str) -> str:
    return f"{str(prefix or 'motion').strip()}_{uuid4().hex}"


def _dict(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _extras(data: Mapping[str, Any], known: set[str]) -> dict[str, Any]:
    return {str(key): value for key, value in data.items() if key not in known}


def _number(data: Mapping[str, Any], key: str, default: int | float, cast):
    value = data.get(key, default)
    return cast(default if value is None else value)


@dataclass(slots=True)
class Keyframe:
    id: str = field(default_factory=lambda: new_motion_id("key"))
    time_ms: int = 0
    value: Any = 0.0
    interpolation: str = "linear"
    in_tangent: tuple[float, float] = (0.667, 1.0)
    out_tangent: tuple[float, float] = (0.333, 0.0)
    metadata: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.extras,
            "id": self.id,
            "time_ms": int(self.time_ms),
            "value": self.value,
            "interpolation": self.interpolation,
            "in_tangent": list(self.in_tangent),
            "out_tangent": list(self.out_tangent),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Keyframe":
        known = {"id", "time_ms", "value", "interpolation", "in_tangent", "out_tangent", "metadata"}
        in_tangent = list(data.get("in_tangent") or (0.667, 1.0))
        out_tangent = list(data.get("out_tangent") or (0.333, 0.0))
        return cls(
            id=str(data.get("id") or new_motion_id("key")),
            time_ms=int(data.get("time_ms", 0) or 0),
            value=data.get("value", 0.0),
            interpolation=str(data.get("interpolation") or "linear"),
            in_tangent=(float(in_tangent[0]), float(in_tangent[1])),
            out_tangent=(float(out_tangent[0]), float(out_tangent[1])),
            metadata=_dict(data.get("metadata") if isinstance(data.get("metadata"), Mapping) else None),
            extras=_extras(data, known),
        )


@dataclass(slots=True)
class AnimatedProperty:
    value_type: str = "scalar"
    default: Any = 0.0
    keyframes: list[Keyframe] = field(default_factory=list)
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.extras,
            "value_type": self.value_type,
            "default": self.default,
            "keyframes": [item.to_dict() for item in self.keyframes],
            "enabled": bool(self.enabled),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | Any, *, value_type: str = "scalar") -> "AnimatedProperty":
        if not isinstance(data, Mapping):
            return cls(value_type=value_type, default=data)
        known = {"value_type", "default", "keyframes", "enabled", "metadata"}
        return cls(
            value_type=str(data.get("value_type") or value_type),
            default=data.get("default", 0.0),
            keyframes=[Keyframe.from_dict(item) for item in data.get("keyframes", []) if isinstance(item, Mapping)],
            enabled=bool(data.get("enabled", True)),
            metadata=_dict(data.get("metadata") if isinstance(data.get("metadata"), Mapping) else None),
            extras=_extras(data, known),
        )


def animated(default: Any, value_type: str) -> AnimatedProperty:
    return AnimatedProperty(value_type=value_type, default=default)


@dataclass(slots=True)
class MotionTransform:
    position: AnimatedProperty = field(default_factory=lambda: animated([0.0, 0.0], "vector2"))
    scale: AnimatedProperty = field(default_factory=lambda: animated([1.0, 1.0], "vector2"))
    rotation: AnimatedProperty = field(default_factory=lambda: animated(0.0, "scalar"))
    opacity: AnimatedProperty = field(default_factory=lambda: animated(1.0, "scalar"))
    anchor: AnimatedProperty = field(default_factory=lambda: animated([0.5, 0.5], "vector2"))
    metadata: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    def properties(self) -> dict[str, AnimatedProperty]:
        return {
            "position": self.position,
            "scale": self.scale,
            "rotation": self.rotation,
            "opacity": self.opacity,
            "anchor": self.anchor,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.extras,
            **{name: prop.to_dict() for name, prop in self.properties().items()},
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "MotionTransform":
        data = data if isinstance(data, Mapping) else {}
        known = {"position", "scale", "rotation", "opacity", "anchor", "metadata"}
        return cls(
            position=AnimatedProperty.from_dict(data.get("position", [0.0, 0.0]), value_type="vector2"),
            scale=AnimatedProperty.from_dict(data.get("scale", [1.0, 1.0]), value_type="vector2"),
            rotation=AnimatedProperty.from_dict(data.get("rotation", 0.0), value_type="scalar"),
            opacity=AnimatedProperty.from_dict(data.get("opacity", 1.0), value_type="scalar"),
            anchor=AnimatedProperty.from_dict(data.get("anchor", [0.5, 0.5]), value_type="vector2"),
            metadata=_dict(data.get("metadata") if isinstance(data.get("metadata"), Mapping) else None),
            extras=_extras(data, known),
        )


@dataclass(slots=True)
class SourceRef:
    kind: str = "shape"
    uri: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    revision: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.extras,
            "kind": self.kind,
            "uri": self.uri,
            "params": dict(self.params),
            "revision": self.revision,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "SourceRef":
        data = data if isinstance(data, Mapping) else {}
        known = {"kind", "uri", "params", "revision", "metadata"}
        return cls(
            kind=str(data.get("kind") or "shape"),
            uri=str(data.get("uri") or ""),
            params=_dict(data.get("params") if isinstance(data.get("params"), Mapping) else None),
            revision=str(data.get("revision") or ""),
            metadata=_dict(data.get("metadata") if isinstance(data.get("metadata"), Mapping) else None),
            extras=_extras(data, known),
        )


@dataclass(slots=True)
class MotionEffectRef:
    id: str = field(default_factory=lambda: new_motion_id("effect"))
    kind: str = ""
    enabled: bool = True
    params: dict[str, AnimatedProperty] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "enabled": self.enabled,
                "params": {key: value.to_dict() for key, value in self.params.items()}, "metadata": dict(self.metadata)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MotionEffectRef":
        return cls(id=str(data.get("id") or new_motion_id("effect")), kind=str(data.get("kind") or ""),
                   enabled=bool(data.get("enabled", True)), params={str(key): AnimatedProperty.from_dict(value)
                   for key, value in (data.get("params") or {}).items()}, metadata=_dict(data.get("metadata")))


@dataclass(slots=True)
class MotionMaskRef:
    id: str = field(default_factory=lambda: new_motion_id("mask"))
    kind: str = "rectangle"
    mode: str = "alpha"
    inverted: bool = False
    params: dict[str, AnimatedProperty] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "mode": self.mode, "inverted": self.inverted,
                "params": {key: value.to_dict() for key, value in self.params.items()}, "metadata": dict(self.metadata)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MotionMaskRef":
        return cls(id=str(data.get("id") or new_motion_id("mask")), kind=str(data.get("kind") or "rectangle"),
                   mode=str(data.get("mode") or "alpha"), inverted=bool(data.get("inverted", False)),
                   params={str(key): AnimatedProperty.from_dict(value) for key, value in (data.get("params") or {}).items()},
                   metadata=_dict(data.get("metadata")))


@dataclass(slots=True)
class MotionBehaviorRef:
    id: str = field(default_factory=lambda: new_motion_id("behavior"))
    kind: str = "fade"
    enabled: bool = True
    start_ms: int = 0
    end_ms: int = 1000
    params: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "enabled": self.enabled, "start_ms": int(self.start_ms),
                "end_ms": int(self.end_ms), "params": dict(self.params), "metadata": dict(self.metadata)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MotionBehaviorRef":
        return cls(id=str(data.get("id") or new_motion_id("behavior")), kind=str(data.get("kind") or "fade"),
                   enabled=bool(data.get("enabled", True)), start_ms=int(data.get("start_ms", 0) or 0),
                   end_ms=int(data.get("end_ms", 1000) or 1000), params=_dict(data.get("params")),
                   metadata=_dict(data.get("metadata")))


@dataclass(slots=True)
class MotionLayer:
    id: str = field(default_factory=lambda: new_motion_id("layer"))
    name: str = "Layer"
    layer_type: str = "shape"
    source: SourceRef = field(default_factory=SourceRef)
    transform: MotionTransform = field(default_factory=MotionTransform)
    parent_id: str = ""
    in_ms: int = 0
    out_ms: int = 5000
    source_in_ms: int = 0
    time_scale: float = 1.0
    reverse: bool = False
    visible: bool = True
    locked: bool = False
    solo: bool = False
    blend_mode: str = "normal"
    effects: list[MotionEffectRef] = field(default_factory=list)
    masks: list[MotionMaskRef] = field(default_factory=list)
    behaviors: list[MotionBehaviorRef] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {**self.extras, "id": self.id, "name": self.name, "layer_type": self.layer_type,
                "source": self.source.to_dict(), "transform": self.transform.to_dict(), "parent_id": self.parent_id,
                "in_ms": int(self.in_ms), "out_ms": int(self.out_ms), "source_in_ms": int(self.source_in_ms),
                "time_scale": float(self.time_scale), "reverse": self.reverse, "visible": self.visible,
                "locked": self.locked, "solo": self.solo, "blend_mode": self.blend_mode,
                "effects": [item.to_dict() for item in self.effects], "masks": [item.to_dict() for item in self.masks],
                "behaviors": [item.to_dict() for item in self.behaviors], "metadata": dict(self.metadata)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MotionLayer":
        known = {"id", "name", "layer_type", "source", "transform", "parent_id", "in_ms", "out_ms",
                 "source_in_ms", "time_scale", "reverse", "visible", "locked", "solo", "blend_mode",
                 "effects", "masks", "behaviors", "metadata"}
        return cls(
            id=str(data.get("id") or new_motion_id("layer")),
            name=str(data.get("name") or "Layer"),
            layer_type=str(data.get("layer_type") or "shape"),
            source=SourceRef.from_dict(data.get("source")),
            transform=MotionTransform.from_dict(data.get("transform")),
            parent_id=str(data.get("parent_id") or ""),
            in_ms=_number(data, "in_ms", 0, int),
            out_ms=_number(data, "out_ms", 5000, int),
            source_in_ms=_number(data, "source_in_ms", 0, int),
            time_scale=_number(data, "time_scale", 1.0, float),
            reverse=bool(data.get("reverse", False)),
            visible=bool(data.get("visible", True)),
            locked=bool(data.get("locked", False)),
            solo=bool(data.get("solo", False)),
            blend_mode=str(data.get("blend_mode") or "normal"),
            effects=[MotionEffectRef.from_dict(item) for item in data.get("effects", []) if isinstance(item, Mapping)],
            masks=[MotionMaskRef.from_dict(item) for item in data.get("masks", []) if isinstance(item, Mapping)],
            behaviors=[MotionBehaviorRef.from_dict(item) for item in data.get("behaviors", []) if isinstance(item, Mapping)],
            metadata=_dict(data.get("metadata") if isinstance(data.get("metadata"), Mapping) else None),
            extras=_extras(data, known),
        )


@dataclass(slots=True)
class MotionComposition:
    id: str = field(default_factory=lambda: new_motion_id("composition"))
    name: str = "Motion Composition"
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    duration_ms: int = 5000
    revision: int = 1
    layers: list[MotionLayer] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=default_motion_metadata)
    schema_version: int = MOTION_SCHEMA_VERSION
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.extras,
            "schema_version": int(self.schema_version),
            "id": self.id,
            "name": self.name,
            "width": int(self.width),
            "height": int(self.height),
            "fps": float(self.fps),
            "duration_ms": int(self.duration_ms),
            "revision": int(self.revision),
            "layers": [layer.to_dict() for layer in self.layers],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MotionComposition":
        known = {
            "schema_version", "id", "name", "width", "height", "fps",
            "duration_ms", "revision", "layers", "metadata",
        }
        return cls(
            id=str(data.get("id") or new_motion_id("composition")),
            name=str(data.get("name") or "Motion Composition"),
            width=_number(data, "width", 1920, int),
            height=_number(data, "height", 1080, int),
            fps=_number(data, "fps", 30.0, float),
            duration_ms=_number(data, "duration_ms", 5000, int),
            revision=max(1, int(data.get("revision", 1) or 1)),
            layers=[MotionLayer.from_dict(item) for item in data.get("layers", []) if isinstance(item, Mapping)],
            metadata=_dict(data.get("metadata") if isinstance(data.get("metadata"), Mapping) else None),
            schema_version=int(data.get("schema_version", MOTION_SCHEMA_VERSION) or MOTION_SCHEMA_VERSION),
            extras=_extras(data, known),
        )

    def clone(self, *, new_id: bool = True, name: str | None = None) -> "MotionComposition":
        data = self.to_dict()
        if new_id:
            data["id"] = new_motion_id("composition")
        data["name"] = name or f"{self.name} Copy"
        data["revision"] = 1
        return MotionComposition.from_dict(data)
