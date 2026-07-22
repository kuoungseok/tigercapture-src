"""Deterministic cost and asset analysis for reviewable Motion AI proposals."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .broadcast_bridge import estimate_broadcast_cost
from .schema import MotionComposition, MotionLayer
from .validation import validate_composition


MOTION_AI_ANALYSIS_SCHEMA = "tigercapture.motion.ai.analysis.v1"
_CACHE_LAYER_TYPES = {"ar_pbr", "live2d_actor", "spine_actor", "mmd_actor", "vrm_actor"}


def _missing_assets(layers: Iterable[MotionLayer]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for layer in layers:
        kind = str(layer.source.kind or layer.layer_type).lower()
        uri = str(layer.source.uri or "")
        requires_uri = kind in {"image", "video", *_CACHE_LAYER_TYPES}
        if requires_uri and uri and not uri.startswith(("http://", "https://")) and not Path(uri).is_file():
            rows.append({"layer_id": layer.id, "layer_name": layer.name, "kind": kind, "uri": uri})
        if kind == "particle":
            particle = layer.source.params.get("particle") or {}
            sprite_uri = str(particle.get("sprite_uri") or "") if isinstance(particle, dict) else ""
            if str(particle.get("shape") or "") == "sprite" and (not sprite_uri or not Path(sprite_uri).is_file()):
                rows.append({
                    "layer_id": layer.id, "layer_name": layer.name,
                    "kind": "particle_sprite", "uri": sprite_uri,
                })
    return rows


def _font_warnings(layers: Iterable[MotionLayer]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for layer in layers:
        if layer.layer_type != "text":
            continue
        font_file = str(layer.source.params.get("font_file") or "")
        declared_missing = bool(layer.source.metadata.get("missing_font"))
        if declared_missing or (font_file and not Path(font_file).is_file()):
            rows.append({
                "layer_id": layer.id,
                "requested": str(layer.source.params.get("font_family") or ""),
                "font_file": font_file,
            })
    return rows


def _bake_requirements(layers: Iterable[MotionLayer], projected_grade: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for layer in layers:
        kind = str(layer.source.kind or layer.layer_type).lower()
        if kind in _CACHE_LAYER_TYPES:
            rows.append({
                "layer_id": layer.id, "kind": kind,
                "requirement": "broadcast_alpha_cache",
                "reason": f"{kind} is cache-required for Motion Program Output",
            })
        elif kind == "particle":
            particle = layer.source.params.get("particle") or {}
            maximum = int(layer.source.params.get("max_particles", 0) or 0)
            if (isinstance(particle, dict) and str(particle.get("shape") or "") == "sprite") or maximum > 4000:
                rows.append({
                    "layer_id": layer.id, "kind": kind,
                    "requirement": "particle_alpha_bake",
                    "reason": "sprite or high-count particles should be baked before broadcast",
                })
    if projected_grade == "cached" and not rows:
        rows.append({
            "layer_id": "", "kind": "composition",
            "requirement": "broadcast_alpha_cache",
            "reason": "projected composition cost exceeds the direct realtime budget",
        })
    return rows


def analyze_motion_ai_layers(composition: MotionComposition,
                             proposed_layers: Iterable[MotionLayer]) -> dict[str, Any]:
    proposed = [MotionLayer.from_dict(layer.to_dict()) for layer in proposed_layers]
    candidate = MotionComposition.from_dict(composition.to_dict())
    candidate.layers.extend(proposed)
    cost = estimate_broadcast_cost(candidate)
    missing_assets = _missing_assets(proposed)
    fonts = _font_warnings(proposed)
    bake = _bake_requirements(proposed, cost.grade)
    validation = validate_composition(candidate)
    warnings: list[str] = []
    if missing_assets:
        warnings.append(f"{len(missing_assets)} proposed asset(s) need relink before reliable rendering.")
    if fonts:
        warnings.append(f"{len(fonts)} proposed text layer(s) use fallback fonts.")
    if bake:
        warnings.append(f"{len(bake)} broadcast bake/cache requirement(s) must be satisfied.")
    if cost.grade == "offline_only":
        warnings.append("The projected composition is offline_only and cannot enter Program Output directly.")
    error_count = sum(issue.severity == "error" for issue in validation.issues)
    if error_count:
        warnings.append(f"Projected composition validation has {error_count} blocking error(s).")
    return {
        "schema": MOTION_AI_ANALYSIS_SCHEMA,
        "created_layer_count": len(proposed),
        "projected_total_layers": len(candidate.layers),
        "renderer_cost": cost.to_dict(),
        "missing_assets": missing_assets,
        "font_fallbacks": fonts,
        "bake_requirements": bake,
        "validation": validation.to_dict(),
        "warnings": warnings,
    }


__all__ = ["MOTION_AI_ANALYSIS_SCHEMA", "analyze_motion_ai_layers"]
