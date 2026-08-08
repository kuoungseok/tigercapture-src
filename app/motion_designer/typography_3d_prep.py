"""Serializable per-character 3D preparation data for the M19 handoff."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .schema import MotionLayer
from .typography_motion import selector_units


CHARACTER_3D_PREP_CONTRACT = "tigerstudio.motion.typography.character_3d_prep.v1"


def prepare_character_3d_data(
    layer: MotionLayer,
    *,
    depth: float = 12.0,
    bevel: float = 1.5,
    z_spacing: float = 0.0,
    overrides: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Attach non-rendering glyph geometry intent consumed by the M19 renderer."""
    if layer.layer_type != "text":
        raise ValueError("per-character 3D preparation requires a text layer")
    text = str(layer.source.params.get("text") or "")
    units = selector_units(text, "character")
    if len(units) > 2048:
        raise ValueError("per-character 3D preparation is limited to 2048 glyphs")
    extrusion = max(0.0, min(10000.0, float(depth)))
    bevel_amount = max(0.0, min(extrusion * 0.5, float(bevel)))
    spacing = max(-1000.0, min(1000.0, float(z_spacing)))
    rows: list[dict[str, Any]] = []
    custom = dict(overrides or {})
    for index, unit in enumerate(units):
        key = str(index)
        values = dict(custom.get(key) or {})
        position = list(values.get("position") or [0.0, 0.0, index * spacing])
        rotation = list(values.get("rotation") or [0.0, 0.0, 0.0])
        scale = list(values.get("scale") or [1.0, 1.0, 1.0])
        if len(position) != 3 or len(rotation) != 3 or len(scale) != 3:
            raise ValueError("character 3D transforms require three components")
        rows.append({
            "index": index,
            "source_start": unit.start,
            "source_end": unit.end,
            "text": text[unit.start:unit.end],
            "position": [float(value) for value in position],
            "rotation": [float(value) for value in rotation],
            "scale": [float(value) for value in scale],
            "depth": max(0.0, float(values.get("depth", extrusion))),
            "bevel": max(0.0, float(values.get("bevel", bevel_amount))),
            "material_slot": str(values.get("material_slot") or "text"),
        })
    payload = {
        "contract": CHARACTER_3D_PREP_CONTRACT,
        "render_status": "prepared_for_m19_not_rendered_in_m16",
        "glyph_count": len(rows),
        "depth": extrusion,
        "bevel": bevel_amount,
        "z_spacing": spacing,
        "glyphs": rows,
    }
    layer.metadata["character_3d_prep"] = payload
    return payload


__all__ = ["CHARACTER_3D_PREP_CONTRACT", "prepare_character_3d_data"]
