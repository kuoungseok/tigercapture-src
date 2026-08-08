"""Seam-safe native-resolution tile assembly for Glass-only Motion graphs."""
from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

from .glass_material import glass_effect
from .keyframes import evaluate_property
from .render_graph import RenderGraph, render_graph_image
from .source_frame import transparent_image


TILED_EXPORT_CONTRACT = "tigerstudio.motion.tiled_export.v1"


def _value(effect, name: str, time_ms: float, default: float) -> float:
    prop = effect.params.get(name)
    try:
        return float(
            evaluate_property(prop, time_ms)
            if prop is not None
            else default
        )
    except (TypeError, ValueError):
        return float(default)


def tiled_render_preflight(graph: RenderGraph) -> dict[str, Any]:
    issues: list[str] = []
    glass_count = 0
    if graph.effect_groups:
        issues.append("effect_group_requires_full_frame")
    for node in graph.nodes:
        if node.layer_type in {"adjustment", "precomp"}:
            issues.append(f"{node.layer_type}_requires_full_frame")
        if node.matte_layer_id:
            issues.append("track_matte_requires_full_frame")
        if node.motion_blur_samples > 1:
            issues.append("motion_blur_requires_full_frame")
        if node.cast_shadows or node.receive_shadows:
            issues.append("card_shadow_requires_full_frame")
        for effect in node.effects or ():
            if not effect.enabled:
                continue
            if effect.kind == "tiger_glass":
                glass_count += 1
            else:
                issues.append(f"effect_requires_full_frame:{effect.kind}")
    if glass_count == 0:
        issues.append("glass_material_missing")
    unique_issues = list(dict.fromkeys(issues))
    return {
        "schema": TILED_EXPORT_CONTRACT,
        "ok": not unique_issues,
        "issues": unique_issues,
        "glass_effect_count": glass_count,
        "strategy": "padded_independent_tiles",
    }


def glass_tile_padding(graph: RenderGraph) -> int:
    padding = 8.0
    for node in graph.nodes:
        effect = glass_effect(node.effects)
        if effect is None or not effect.enabled:
            continue
        blur = max(0.0, _value(effect, "blur_radius", node.local_time_ms, 4.0))
        refraction = max(0.0, _value(effect, "refraction", node.local_time_ms, 3.0))
        dispersion = max(0.0, _value(effect, "dispersion", node.local_time_ms, 0.35))
        bloom = max(0.0, _value(effect, "bloom", node.local_time_ms, 0.08))
        padding = max(
            padding,
            blur * 3.0 + refraction + dispersion + bloom * 6.0 + 8.0,
        )
    return max(8, min(512, int(math.ceil(padding))))


def render_graph_tiled(
    graph: RenderGraph,
    *,
    tile_size: int = 512,
) -> tuple[QImage, dict[str, Any]]:
    preflight = tiled_render_preflight(graph)
    if not preflight["ok"]:
        raise ValueError(
            "Motion tiled render is unavailable: "
            + "; ".join(preflight["issues"])
        )
    size = max(64, min(4096, int(tile_size)))
    padding = glass_tile_padding(graph)
    output = transparent_image(graph.width, graph.height)
    output_painter = QPainter(output)
    tile_count = 0
    largest_intermediate_pixels = 0
    for top in range(0, graph.height, size):
        for left in range(0, graph.width, size):
            tile_width = min(size, graph.width - left)
            tile_height = min(size, graph.height - top)
            padded_left = max(0, left - padding)
            padded_top = max(0, top - padding)
            padded_right = min(graph.width, left + tile_width + padding)
            padded_bottom = min(graph.height, top + tile_height + padding)
            padded_width = padded_right - padded_left
            padded_height = padded_bottom - padded_top
            region = QRectF(
                float(padded_left),
                float(padded_top),
                float(padded_width),
                float(padded_height),
            )
            rendered = render_graph_image(
                graph,
                output_size=(padded_width, padded_height),
                source_rect=region,
            )
            center = rendered.copy(
                left - padded_left,
                top - padded_top,
                tile_width,
                tile_height,
            )
            output_painter.drawImage(left, top, center)
            tile_count += 1
            largest_intermediate_pixels = max(
                largest_intermediate_pixels,
                padded_width * padded_height,
            )
    output_painter.end()
    report = {
        **preflight,
        "ok": True,
        "width": graph.width,
        "height": graph.height,
        "tile_size": size,
        "padding": padding,
        "tile_count": tile_count,
        "largest_intermediate_pixels": largest_intermediate_pixels,
        "full_frame_pixels": graph.width * graph.height,
        "full_frame_intermediate_avoided": (
            largest_intermediate_pixels < graph.width * graph.height
        ),
    }
    return output, report


__all__ = [
    "TILED_EXPORT_CONTRACT",
    "glass_tile_padding",
    "render_graph_tiled",
    "tiled_render_preflight",
]
