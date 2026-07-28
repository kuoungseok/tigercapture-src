"""Editable procedural Generator layers for Motion Designer."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from .schema import MotionLayer, SourceRef


GENERATOR_SOURCE_KIND = "generator"
GENERATOR_KINDS = (
    "solid",
    "gradient",
    "checkerboard",
    "grid",
    "noise",
    "rays",
)


def default_generator_params(
    kind: str,
    *,
    width: int,
    height: int,
) -> dict:
    normalized = str(kind or "gradient").lower()
    if normalized not in GENERATOR_KINDS:
        raise ValueError(f"Unsupported Motion generator: {kind}")
    return {
        "kind": normalized,
        "width": max(1, int(width)),
        "height": max(1, int(height)),
        "color_a": "#24677f",
        "color_b": "#111820",
        "scale": 96.0,
        "angle": 35.0,
        "offset": [0.0, 0.0],
        "seed": 17,
        "detail": 4,
        "contrast": 1.0,
        "softness": 0.0,
    }


def normalize_generator_params(
    params: Mapping | None,
    *,
    width: int,
    height: int,
) -> dict:
    source = dict(params or {})
    kind = str(source.get("kind") or "gradient").lower()
    defaults = default_generator_params(kind, width=width, height=height)
    defaults.update(deepcopy(source))
    defaults["kind"] = kind
    defaults["width"] = max(1, min(16384, int(defaults.get("width", width) or width)))
    defaults["height"] = max(1, min(16384, int(defaults.get("height", height) or height)))
    defaults["scale"] = max(2.0, min(4096.0, float(defaults.get("scale", 96.0) or 96.0)))
    defaults["angle"] = float(defaults.get("angle", 35.0) or 0.0)
    defaults["seed"] = int(defaults.get("seed", 17) or 0)
    defaults["detail"] = max(1, min(8, int(defaults.get("detail", 4) or 4)))
    defaults["contrast"] = max(0.0, min(4.0, float(defaults.get("contrast", 1.0) or 0.0)))
    defaults["softness"] = max(0.0, min(1.0, float(defaults.get("softness", 0.0) or 0.0)))
    offset = list(defaults.get("offset") or [0.0, 0.0])
    defaults["offset"] = [
        float(offset[0]) if offset else 0.0,
        float(offset[1]) if len(offset) > 1 else 0.0,
    ]
    return defaults


def create_generator_layer(
    kind: str = "gradient",
    *,
    width: int = 1920,
    height: int = 1080,
    duration_ms: int = 5000,
    name: str = "",
) -> MotionLayer:
    params = default_generator_params(kind, width=width, height=height)
    layer = MotionLayer(
        name=name or str(kind).replace("_", " ").title(),
        layer_type=GENERATOR_SOURCE_KIND,
        source=SourceRef(kind=GENERATOR_SOURCE_KIND, params=params),
        out_ms=max(1, int(duration_ms)),
    )
    layer.transform.position.default = [float(width) * 0.5, float(height) * 0.5]
    return layer


def update_generator_params(layer: MotionLayer, changes: Mapping) -> None:
    if layer.layer_type != GENERATOR_SOURCE_KIND:
        raise ValueError("Generator settings require a generator layer")
    merged = dict(layer.source.params)
    merged.update(deepcopy(dict(changes)))
    layer.source.params = normalize_generator_params(
        merged,
        width=int(merged.get("width", 1920) or 1920),
        height=int(merged.get("height", 1080) or 1080),
    )


__all__ = [
    "GENERATOR_KINDS",
    "GENERATOR_SOURCE_KIND",
    "create_generator_layer",
    "default_generator_params",
    "normalize_generator_params",
    "update_generator_params",
]
