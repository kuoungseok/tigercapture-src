"""Rendered template previews generated from the production composition path."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .export_renderer import MotionExportRenderer
from .templates import instantiate_template


def render_template_preview(template_id: str, output_path: str | Path, *, variant: str = "16:9",
                            controls: Mapping[str, Any] | None = None, time_ms: float | None = None) -> dict[str, Any]:
    composition = instantiate_template(template_id, variant=variant, controls=controls)
    sample_time = float(composition.duration_ms * .35 if time_ms is None else time_ms)
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    MotionExportRenderer(cache_capacity=8).save_png(composition, sample_time, output)
    return {
        "template_id": template_id, "variant": variant, "time_ms": sample_time,
        "path": str(output), "width": composition.width, "height": composition.height,
        "animated": any(layer.behaviors or any(prop.keyframes for prop in layer.transform.properties().values())
                        for layer in composition.layers),
    }


__all__ = ["render_template_preview"]
