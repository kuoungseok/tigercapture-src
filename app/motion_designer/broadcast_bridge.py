"""Broadcast cost grading, live controls, and alpha-cache preflight."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .schema import MotionComposition, MotionLayer
from .templates import get_template
from .validation import validate_composition


BROADCAST_PREFLIGHT_SCHEMA = "tigercapture.motion.broadcast.preflight.v1"
BROADCAST_CACHE_SCHEMA = "tigercapture.motion.broadcast.alpha_cache.v1"
BROADCAST_GRADES = ("realtime", "cached", "offline_only")
_GRADE_ORDER = {grade: index for index, grade in enumerate(BROADCAST_GRADES)}
PUBLISHED_CONTROL_IDS = (
    "headline", "subtitle", "accent_color", "surface_color", "duration_ms",
)


@dataclass(slots=True)
class BroadcastCost:
    grade: str
    cost_units: float
    layer_count: int
    particle_limit: int
    layer_grades: list[dict[str, Any]] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "grade": self.grade,
            "cost_units": round(self.cost_units, 3),
            "layer_count": self.layer_count,
            "particle_limit": self.particle_limit,
            "layer_grades": list(self.layer_grades),
            "reasons": list(self.reasons),
        }


def _worse_grade(left: str, right: str) -> str:
    return max((left, right), key=lambda grade: _GRADE_ORDER.get(grade, 2))


def _layer_cost(layer: MotionLayer) -> tuple[float, str, str]:
    kind = str(layer.layer_type or layer.source.kind or "shape").lower()
    source_kind = str(layer.source.kind or kind).lower()
    if kind == "text" and source_kind in {"text", "typography"}:
        effective = "text"
    elif kind == "shape":
        effective = "shape"
    else:
        effective = source_kind if source_kind else kind
    costs = {
        "shape": 1.0, "text": 1.5, "image": 1.5, "video": 2.5,
        "adjustment": 4.0, "particle": 2.0,
        "live2d_actor": 16.0, "spine_actor": 16.0,
        "ar_pbr": 30.0, "mmd_actor": 40.0, "vrm_actor": 40.0,
    }
    cost = costs.get(effective, costs.get(kind, 3.0))
    grade = "realtime"
    reason = "native 2D realtime source"
    if effective in {"live2d_actor", "spine_actor", "ar_pbr", "mmd_actor", "vrm_actor"}:
        grade = "cached"
        reason = f"{effective} requires a prepared broadcast frame cache"
    elif effective == "particle":
        limit = max(0, int(layer.source.params.get("max_particles", 0) or 0))
        cost += limit / 500.0
        shape = str((layer.source.params.get("particle") or {}).get("shape") or "circle")
        if shape == "sprite" or limit > 4000:
            grade = "cached"
            reason = "sprite or high-count particles require alpha pre-render"
        else:
            reason = "GPU shape-particle source"
    cost += len(layer.effects) * 2.0 + len(layer.masks) * 1.0
    explicit = str(layer.metadata.get("broadcast_grade") or "").lower()
    if explicit in BROADCAST_GRADES:
        grade = _worse_grade(grade, explicit)
        reason = f"layer declares {explicit} broadcast grade"
    return cost, grade, reason


def estimate_broadcast_cost(composition: MotionComposition) -> BroadcastCost:
    grade = "realtime"
    total = 0.0
    particle_limit = 0
    rows: list[dict[str, Any]] = []
    reasons: list[str] = []
    for layer in composition.layers:
        if not layer.visible or layer.layer_type in {"group", "null", "camera", "light"}:
            continue
        cost, layer_grade, reason = _layer_cost(layer)
        total += cost
        if layer.layer_type == "particle" or layer.source.kind == "particle":
            particle_limit += max(0, int(layer.source.params.get("max_particles", 0) or 0))
        grade = _worse_grade(grade, layer_grade)
        rows.append({
            "layer_id": layer.id, "name": layer.name, "layer_type": layer.layer_type,
            "grade": layer_grade, "cost_units": round(cost, 3), "reason": reason,
        })
    template_state = composition.metadata.get("last_applied_template")
    if isinstance(template_state, Mapping):
        template_grade = str(template_state.get("realtime_grade") or "realtime")
        if template_grade in BROADCAST_GRADES:
            grade = _worse_grade(grade, template_grade)
            if template_grade != "realtime":
                reasons.append(f"template declares {template_grade} broadcast grade")
    explicit = str(composition.metadata.get("broadcast_grade") or "").lower()
    if explicit in BROADCAST_GRADES:
        grade = _worse_grade(grade, explicit)
        reasons.append(f"composition declares {explicit} broadcast grade")
    if len(rows) > 96 or total > 160 or particle_limit > 12000:
        grade = "offline_only"
        reasons.append("composition exceeds the broadcast hard budget")
    elif len(rows) > 48 or total > 48 or particle_limit > 4000:
        grade = _worse_grade(grade, "cached")
        reasons.append("composition exceeds the direct realtime budget")
    return BroadcastCost(grade, total, len(rows), particle_limit, rows, reasons)


def _cache_diagnostics(composition: MotionComposition, cache_manifest: Mapping[str, Any] | None) -> tuple[bool, list[str]]:
    manifest = dict(cache_manifest or composition.metadata.get("broadcast_cache") or {})
    reasons: list[str] = []
    if manifest.get("schema") != BROADCAST_CACHE_SCHEMA:
        reasons.append("a Motion broadcast alpha-cache manifest is required")
    if not bool(manifest.get("ready")):
        reasons.append("broadcast alpha cache is not marked ready")
    if int(manifest.get("composition_revision", -1) or -1) != composition.revision:
        reasons.append("broadcast alpha cache is stale for the current composition revision")
    composite_alpha = str(manifest.get("composite_alpha") or "")
    premultiplied = composite_alpha == "premultiplied" or bool(manifest.get("premultiplied_alpha"))
    storage_alpha = str(manifest.get("storage_alpha") or "straight")
    if not bool(manifest.get("alpha")) or not premultiplied or storage_alpha != "straight":
        reasons.append("broadcast cache must preserve premultiplied alpha")
    if int(manifest.get("frame_count", 0) or 0) < 1:
        reasons.append("broadcast alpha cache has no frames")
    path_text = str(manifest.get("path") or "")
    if not path_text or not Path(path_text).exists():
        reasons.append("broadcast alpha cache path is missing")
    return not reasons, reasons


def broadcast_preflight(composition: MotionComposition, *,
                        cache_manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    validation = validate_composition(composition)
    cost = estimate_broadcast_cost(composition)
    blockers = [issue.message for issue in validation.issues if issue.severity == "error"]
    warnings = [issue.message for issue in validation.issues if issue.severity != "error"]
    cache_ready = False
    cache_reasons: list[str] = []
    if cost.grade == "offline_only":
        blockers.append("offline_only compositions cannot enter Program Output")
    elif cost.grade == "cached":
        cache_ready, cache_reasons = _cache_diagnostics(composition, cache_manifest)
        blockers.extend(cache_reasons)
    else:
        cache_ready = True
    return {
        "schema": BROADCAST_PREFLIGHT_SCHEMA,
        "ok": not blockers,
        "composition_id": composition.id,
        "composition_revision": composition.revision,
        "grade": cost.grade,
        "cache_ready": cache_ready,
        "cost": cost.to_dict(),
        "blockers": blockers,
        "warnings": warnings,
        "program_output": {
            "source": "motion_composition",
            "performance_source_allowed": False,
            "premultiplied_alpha": True,
            "direct_playback": cost.grade == "realtime",
            "cached_playback": cost.grade == "cached" and cache_ready,
        },
    }


def apply_live_controls(composition: MotionComposition, changes: Mapping[str, Any]) -> MotionComposition:
    template_state = composition.metadata.get("last_applied_template")
    if not isinstance(template_state, Mapping):
        raise ValueError("live controls require an applied Motion template")
    template_id = str(template_state.get("template_id") or "")
    instance_id = str(template_state.get("template_instance_id") or "")
    template = get_template(template_id)
    supported = {item.id for item in template.controls}
    unknown = sorted(set(changes) - supported)
    if unknown:
        raise ValueError(f"unknown published template control: {unknown[0]}")
    candidate = MotionComposition.from_dict(composition.to_dict())
    values = dict(template_state.get("published_controls") or {})
    values.update(dict(changes))
    values["duration_ms"] = max(250, min(600000, int(values.get("duration_ms", candidate.duration_ms))))
    for key in ("headline", "subtitle", "accent_color", "surface_color"):
        values[key] = str(values.get(key, ""))
    for layer in candidate.layers:
        layer_template_id = str(layer.metadata.get("template_id") or "")
        layer_instance_id = str(layer.metadata.get("template_instance_id") or "")
        if layer_template_id != template_id:
            continue
        if instance_id and layer_instance_id != instance_id:
            continue
        role = str(layer.metadata.get("template_role") or "")
        params = deepcopy(layer.source.params)
        if role in {"headline", "subtitle"}:
            params["text"] = values[role]
        elif role == "accent":
            params["fill"] = values["accent_color"]
        elif role == "surface":
            params["fill"] = values["surface_color"]
        elif role == "particles":
            particle = dict(params.get("particle") or {})
            particle["color_start"] = values["accent_color"]
            particle["color_end"] = f"{values['accent_color'][:7]}00"
            params["particle"] = particle
        layer.source.params = params
        layer.out_ms = values["duration_ms"]
    candidate.duration_ms = values["duration_ms"]
    state = dict(candidate.metadata.get("last_applied_template") or {})
    state["published_controls"] = values
    candidate.metadata["last_applied_template"] = state
    candidate.metadata.pop("broadcast_cache", None)
    candidate.revision += 1
    return candidate


def stinger_alpha_plan(composition: MotionComposition, output_dir: str | Path, *,
                       fps: float | None = None) -> dict[str, Any]:
    frame_rate = max(1.0, min(120.0, float(fps or composition.fps)))
    frame_count = max(1, int(math.ceil(composition.duration_ms / 1000.0 * frame_rate)))
    root = Path(output_dir).expanduser().resolve()
    cache_dir = root / f"motion_{composition.id}_r{composition.revision}"
    return {
        "schema": BROADCAST_CACHE_SCHEMA,
        "composition_id": composition.id,
        "composition_revision": composition.revision,
        "path": str(cache_dir),
        "frame_pattern": str(cache_dir / "frame_%06d.png"),
        "manifest_path": str(cache_dir / "manifest.json"),
        "fps": frame_rate,
        "frame_count": frame_count,
        "alpha": True,
        "storage_alpha": "straight",
        "composite_alpha": "premultiplied",
        "premultiply_on_load": True,
        "premultiplied_alpha": True,
        "format": "png_sequence_rgba",
        "program_output_playback": "cached_alpha_sequence",
    }


def render_stinger_alpha_cache(composition: MotionComposition, output_dir: str | Path, *,
                               fps: float | None = None) -> tuple[MotionComposition, dict[str, Any]]:
    from .export_renderer import MotionExportRenderer

    candidate = MotionComposition.from_dict(composition.to_dict())
    candidate.revision += 1
    candidate.metadata.pop("broadcast_cache", None)
    plan = stinger_alpha_plan(candidate, output_dir, fps=fps)
    cache_dir = Path(plan["path"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    renderer = MotionExportRenderer(cache_capacity=4)
    for index in range(int(plan["frame_count"])):
        time_ms = index * 1000.0 / float(plan["fps"])
        frame = renderer.render_frame(candidate, time_ms, use_cache=False)
        if not frame.hasAlphaChannel() or not frame.save(str(cache_dir / f"frame_{index:06d}.png"), "PNG"):
            raise RuntimeError(f"failed to render broadcast alpha frame {index}")
    manifest = {**plan, "ready": True}
    Path(plan["manifest_path"]).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    candidate.metadata["broadcast_cache"] = manifest
    return candidate, manifest


__all__ = [
    "BROADCAST_CACHE_SCHEMA", "BROADCAST_GRADES", "BROADCAST_PREFLIGHT_SCHEMA",
    "BroadcastCost", "PUBLISHED_CONTROL_IDS", "apply_live_controls", "broadcast_preflight",
    "estimate_broadcast_cost", "render_stinger_alpha_cache", "stinger_alpha_plan",
]
