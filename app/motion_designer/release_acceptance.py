"""Motion Designer render readiness and product-release evidence gate."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .color_management import settings_from_composition_metadata, validate_motion_color_settings
from .export_profiles import preflight_motion_export
from .schema import MotionComposition, MotionLayer
from .validation import validate_composition


RELEASE_ACCEPTANCE_SCHEMA = "tigercapture.motion.release_acceptance.v1"
SUPPORTED_RENDER_LAYER_TYPES = frozenset({
    "shape", "line", "text", "image", "adjustment", "group", "null", "camera", "light",
    "particle", "ar_pbr", "live2d_actor", "spine_actor", "mmd_actor", "vrm_actor",
})
GPU_LAYER_TYPES = frozenset({"ar_pbr", "live2d_actor", "spine_actor", "mmd_actor", "vrm_actor"})
REQUIRED_RELEASE_EVIDENCE = (
    "standard_exports",
    "color_alpha_golden",
    "gpu_preview_export_parity",
    "long_run_30m",
    "stress_1000_layers",
    "stress_10000_keyframes",
    "undo_autosave_recovery",
    "queue_cancel_resume_retry",
    "gpu_context_recovery",
    "project_relink_move",
    "installer_smoke",
)


def _evidence_check(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {"ok": False, "reason": "structured evidence record is required", "artifact_paths": []}
    passed = bool(value.get("ok") or str(value.get("status") or "").lower() == "pass")
    paths = value.get("artifact_paths")
    if not isinstance(paths, list):
        single = str(value.get("artifact_path") or "")
        paths = [single] if single else []
    normalized = [str(Path(path).expanduser().resolve()) for path in paths if str(path).strip()]
    missing = [path for path in normalized if not Path(path).exists()]
    empty = []
    for path in normalized:
        candidate = Path(path)
        if not candidate.exists():
            continue
        if candidate.is_file() and candidate.stat().st_size <= 0:
            empty.append(path)
        elif candidate.is_dir() and not any(candidate.iterdir()):
            empty.append(path)
    generated_at = str(value.get("generated_at") or "").strip()
    reasons: list[str] = []
    if not passed:
        reasons.append("evidence status is not pass")
    if not generated_at:
        reasons.append("generated_at is required")
    if not normalized:
        reasons.append("at least one artifact path is required")
    if missing:
        reasons.append("evidence artifact is missing")
    if empty:
        reasons.append("evidence artifact is empty")
    return {
        "ok": passed and bool(generated_at) and bool(normalized) and not missing and not empty,
        "reason": "; ".join(reasons),
        "artifact_paths": normalized,
        "missing_artifact_paths": missing,
        "empty_artifact_paths": empty,
        "generated_at": generated_at,
    }


def validate_release_evidence(evidence: Mapping[str, Any] | None) -> dict[str, Any]:
    values = dict(evidence or {})
    details = {name: _evidence_check(values.get(name)) for name in REQUIRED_RELEASE_EVIDENCE}
    checks = {name: bool(row["ok"]) for name, row in details.items()}
    missing = [name for name, passed in checks.items() if not passed]
    return {
        "ok": not missing,
        "checks": checks,
        "details": details,
        "missing": missing,
        "required": list(REQUIRED_RELEASE_EVIDENCE),
    }


def _asset_and_font_checks(layers: list[MotionLayer]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[str]]:
    missing_assets: list[dict[str, str]] = []
    missing_fonts: list[dict[str, str]] = []
    warnings: list[str] = []
    for layer in layers:
        layer_type = str(layer.layer_type or layer.source.kind).lower()
        uri = str(layer.source.uri or "")
        requires_uri = layer_type in {"image", *GPU_LAYER_TYPES}
        if requires_uri and not uri:
            missing_assets.append({"layer_id": layer.id, "kind": layer_type, "uri": ""})
        elif uri.startswith(("http://", "https://")):
            warnings.append(f"Remote source is not release-stable without a local cache: {layer.name}")
        elif uri and not Path(uri).expanduser().is_file():
            missing_assets.append({"layer_id": layer.id, "kind": layer_type, "uri": uri})
        if uri and not layer.source.metadata.get("color_space"):
            warnings.append(f"Untagged source uses the composition sRGB fallback: {layer.name}")
        if layer_type == "particle":
            particle = layer.source.params.get("particle")
            sprite = str(particle.get("sprite_uri") or "") if isinstance(particle, Mapping) else ""
            if isinstance(particle, Mapping) and str(particle.get("shape") or "") == "sprite":
                if not sprite or not Path(sprite).expanduser().is_file():
                    missing_assets.append({"layer_id": layer.id, "kind": "particle_sprite", "uri": sprite})
        if layer_type == "text":
            font_file = str(layer.source.params.get("font_file") or "")
            if layer.source.metadata.get("missing_font") or (font_file and not Path(font_file).expanduser().is_file()):
                missing_fonts.append({
                    "layer_id": layer.id,
                    "font_family": str(layer.source.params.get("font_family") or ""),
                    "font_file": font_file,
                })
    return missing_assets, missing_fonts, warnings


def _gpu_checks(layers: list[MotionLayer], diagnostics: Mapping[str, Any] | None) -> dict[str, Any]:
    required = [layer.id for layer in layers if layer.layer_type in GPU_LAYER_TYPES]
    rows = dict(diagnostics or {})
    missing = [layer_id for layer_id in required if not isinstance(rows.get(layer_id), Mapping)]
    software = []
    failed = []
    for layer_id in required:
        row = rows.get(layer_id)
        if not isinstance(row, Mapping):
            continue
        renderer = str(row.get("renderer") or row.get("backend") or "").lower()
        if "software" in renderer or bool(row.get("software_renderer")):
            software.append(layer_id)
        if row.get("ok") is False or row.get("gpu_ready") is False:
            failed.append(layer_id)
    return {
        "ok": not missing and not software and not failed,
        "required_layer_ids": required,
        "missing_diagnostics": missing,
        "software_renderer_layer_ids": software,
        "failed_layer_ids": failed,
    }


def motion_release_preflight(composition: MotionComposition, *, profile_id: str = "",
                             output_path: str = "", fps: float | None = None,
                             gpu_diagnostics: Mapping[str, Any] | None = None,
                             evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    validation = validate_composition(composition).to_dict()
    blockers = [issue["message"] for issue in validation["issues"] if issue["severity"] == "error"]
    warnings = [issue["message"] for issue in validation["issues"] if issue["severity"] != "error"]
    unsupported = [
        {"layer_id": layer.id, "layer_type": layer.layer_type}
        for layer in composition.layers if layer.layer_type not in SUPPORTED_RENDER_LAYER_TYPES
    ]
    blockers.extend(f"Unsupported Motion render layer: {row['layer_type']}" for row in unsupported)
    missing_assets, missing_fonts, source_warnings = _asset_and_font_checks(composition.layers)
    blockers.extend(f"Missing asset: {row['uri'] or row['kind']}" for row in missing_assets)
    blockers.extend(f"Missing font file: {row['font_file'] or row['font_family']}" for row in missing_fonts)
    warnings.extend(source_warnings)
    color = validate_motion_color_settings(settings_from_composition_metadata(composition.metadata))
    blockers.extend(color["errors"])
    warnings.extend(color["warnings"])
    gpu = _gpu_checks(composition.layers, gpu_diagnostics)
    if gpu["required_layer_ids"] and not gpu["ok"]:
        blockers.append("GPU-backed Motion layers require non-software runtime diagnostics")
    export = None
    if profile_id:
        export = preflight_motion_export(
            composition, profile_id, output_path=output_path, fps=fps,
        )
        blockers.extend(export["errors"])
        warnings.extend(export["warnings"])
    release_evidence = validate_release_evidence(evidence)
    render_ready = not blockers
    return {
        "schema": RELEASE_ACCEPTANCE_SCHEMA,
        "composition_id": composition.id,
        "composition_revision": composition.revision,
        "render_ready": render_ready,
        "product_release_ready": render_ready and release_evidence["ok"],
        "status": "release_ready" if render_ready and release_evidence["ok"] else (
            "render_ready_evidence_pending" if render_ready else "blocked"
        ),
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "validation": validation,
        "color": color,
        "export": export,
        "assets": {"missing": missing_assets},
        "fonts": {"missing": missing_fonts},
        "renderer_coverage": {"unsupported": unsupported},
        "gpu": gpu,
        "evidence": release_evidence,
    }


__all__ = [
    "GPU_LAYER_TYPES", "RELEASE_ACCEPTANCE_SCHEMA", "REQUIRED_RELEASE_EVIDENCE",
    "SUPPORTED_RENDER_LAYER_TYPES", "motion_release_preflight", "validate_release_evidence",
]
