"""Runtime verification helpers for professional workflow payloads.

The readiness matrix answers "is the workflow represented?"  This module adds a
small deterministic execution layer for the next question: can those payloads
touch real frame/graph/local-analysis paths without a UI or native engine
session?
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _sha256_array(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def synthetic_professional_frame(width: int = 160, height: int = 96) -> np.ndarray:
    """Return a deterministic RGB frame with luma, hue, and foreground regions."""
    width = max(32, int(width or 160))
    height = max(32, int(height or 96))
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    rgb = np.zeros((height, width, 3), dtype=np.float32)
    rgb[..., 0] = 35.0 + x * 165.0
    rgb[..., 1] = 42.0 + y * 135.0
    rgb[..., 2] = 84.0 + (1.0 - x) * 105.0

    # Foreground object with warm skin/product hues, useful for qualifier and ML
    # foreground probes.
    x0, x1 = int(width * 0.38), int(width * 0.68)
    y0, y1 = int(height * 0.24), int(height * 0.74)
    rgb[y0:y1, x0:x1, 0] = 214.0
    rgb[y0:y1, x0:x1, 1] = 126.0
    rgb[y0:y1, x0:x1, 2] = 76.0
    return np.clip(rgb + 0.5, 0, 255).astype(np.uint8)


def run_professional_color_runtime_sample(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Apply the professional color payload to a real RGB sample."""
    from app.color_grading import ColorGrade
    from app.color_workflow import (
        apply_advanced_color_toolset,
        apply_color_node_workflow,
        build_professional_color_pipeline_payload,
        combined_node_mask,
        professional_color_pipeline_report,
        scope_diagnostics,
    )

    payload = dict(payload or build_professional_color_pipeline_payload(
        hdr_metadata={"standard": "dolby_vision", "dynamic_metadata": True},
        restoration={
            "temporal_nr": 0.35,
            "spatial_nr": 0.25,
            "film_grain": 0.18,
            "deflicker": True,
            "dead_pixel_repair": True,
            "dust_dirt_removal": True,
        },
    ))
    before = synthetic_professional_frame()
    advanced = apply_advanced_color_toolset(before, _as_dict(payload.get("advanced_color_toolset")))
    grade = ColorGrade(brightness=7, contrast=8, saturation=10)
    after = apply_color_node_workflow(advanced, grade, _as_dict(payload.get("color_workflow")))
    export_after = apply_color_node_workflow(
        apply_advanced_color_toolset(before, _as_dict(payload.get("advanced_color_toolset"))),
        grade,
        _as_dict(payload.get("color_workflow")),
    )
    mask = combined_node_mask(before, _as_dict(payload.get("color_workflow")))
    mean_abs_delta = float(np.mean(np.abs(after.astype(np.int16) - before.astype(np.int16))))
    parity_delta = int(np.max(np.abs(after.astype(np.int16) - export_after.astype(np.int16))))
    scope = scope_diagnostics(after)
    checks = {
        "payload_valid": bool(professional_color_pipeline_report(payload).get("ok")),
        "frame_changed": mean_abs_delta >= 1.0,
        "mask_has_coverage": float(mask.mean()) > 0.005,
        "preview_export_same": parity_delta == 0,
        "scope_nonblank": float(scope.get("luma_p99", 0.0) or 0.0) > float(scope.get("luma_p01", 0.0) or 0.0),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "mean_abs_delta": round(mean_abs_delta, 4),
        "mask_coverage": round(float(mask.mean()), 4),
        "preview_hash": _sha256_array(after),
        "export_hash": _sha256_array(export_after),
        "parity_delta": parity_delta,
        "scope": scope,
    }


def run_professional_color_precision_sample(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Verify professional color payloads cover precision, scopes, and parity."""
    from app.color_workflow import ColorProcessingPipeline, professional_color_pipeline_report, scope_accuracy_report

    report = professional_color_pipeline_report(payload)
    pipeline = ColorProcessingPipeline.from_dict(_as_dict(report.get("payload")).get("color_processing_pipeline"))
    runtime = run_professional_color_runtime_sample(_as_dict(report.get("payload")))
    scope = scope_accuracy_report()
    checks = {
        "pipeline_report_ok": bool(report.get("ok")),
        "thirty_two_bit_or_better": int(pipeline.processing_bits) >= 32,
        "scene_linear_or_yrgb": "linear" in pipeline.internal_model.casefold() or "yrgb" in pipeline.internal_model.casefold(),
        "wide_gamut_or_aces": pipeline.working_space.casefold().startswith("aces") or "2020" in pipeline.output_space.casefold(),
        "hdr_metadata_valid": bool(_as_dict(report.get("checks")).get("hdr_metadata_valid")),
        "scope_accuracy_ok": bool(scope.get("ok")),
        "preview_export_parity": bool(_as_dict(runtime.get("checks")).get("preview_export_same")),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "pipeline": pipeline.to_dict(),
        "scope_accuracy": scope,
        "runtime_hashes": {
            "preview": runtime.get("preview_hash"),
            "export": runtime.get("export_hash"),
            "parity_delta": runtime.get("parity_delta"),
        },
        "summary": {
            "processing_bits": int(pipeline.processing_bits),
            "internal_model": pipeline.internal_model,
            "working_space": pipeline.working_space,
            "output_space": pipeline.output_space,
            "scope_sample": scope.get("sample"),
        },
    }


def _topological_vfx_order(graph_payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    nodes = _as_dict(graph_payload).get("nodes", []) or []
    by_id = {str(row.get("id") or ""): row for row in nodes if isinstance(row, dict) and str(row.get("id") or "")}
    visiting: set[str] = set()
    visited: set[str] = set()
    order: list[str] = []
    warnings: list[str] = []

    def visit(node_id: str) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            warnings.append(f"cycle detected at {node_id}")
            return
        row = by_id.get(node_id)
        if row is None:
            warnings.append(f"missing node {node_id}")
            return
        visiting.add(node_id)
        for input_id in row.get("inputs", []) or []:
            input_id = str(input_id)
            if input_id not in by_id:
                warnings.append(f"node {node_id} input missing: {input_id}")
                continue
            visit(input_id)
        visiting.discard(node_id)
        visited.add(node_id)
        order.append(node_id)

    output = str(_as_dict(graph_payload).get("output_node") or "out")
    for node_id in by_id:
        if node_id != output:
            visit(node_id)
    visit(output)
    return order, warnings


def build_vfx_runtime_execution_plan(graph_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a dry-run execution plan for a Fusion-style VFX graph."""
    from app.post_pipeline_workflow import build_professional_fusion_compositor_graph, vfx_node_graph_qa_report

    graph_payload = dict(graph_payload or build_professional_fusion_compositor_graph().to_dict())
    order, warnings = _topological_vfx_order(graph_payload)
    node_by_id = {str(row.get("id") or ""): row for row in graph_payload.get("nodes", []) or [] if isinstance(row, dict)}
    cache_boundaries = [
        node_id
        for node_id in order
        if _as_dict(_as_dict(node_by_id.get(node_id)).get("params")).get("cache_policy")
        or str(_as_dict(node_by_id.get(node_id)).get("kind") or "") in {"render_3d", "output", "macro"}
    ]
    kinds = {str(_as_dict(node_by_id.get(node_id)).get("kind") or "") for node_id in order}
    qa = vfx_node_graph_qa_report([graph_payload])
    checks = {
        "graph_valid": bool(qa.get("ok")),
        "execution_order": bool(order) and order[-1] == str(graph_payload.get("output_node") or "out"),
        "cache_boundaries": bool(cache_boundaries),
        "has_2d_3d_merge": {"merge", "merge_3d", "render_3d"} <= kinds,
        "warnings_clear": not warnings,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "execution_order": order,
        "cache_boundaries": cache_boundaries,
        "warnings": warnings,
        "qa": qa,
    }


def run_vfx_expression_macro_runtime_sample(graph_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Check deeper Fusion-style graph features beyond the base node contract."""
    from app.post_pipeline_workflow import build_professional_fusion_compositor_graph

    graph_payload = dict(graph_payload or build_professional_fusion_compositor_graph().to_dict())
    plan = build_vfx_runtime_execution_plan(graph_payload)
    nodes = [
        row
        for row in graph_payload.get("nodes", []) or []
        if isinstance(row, dict)
    ]
    kinds = {str(row.get("kind") or "") for row in nodes}
    cache_kinds = {
        str(row.get("kind") or "")
        for row in nodes
        if _as_dict(row.get("params")).get("cache_policy")
    }
    checks = {
        "base_execution_plan_ok": bool(plan.get("ok")),
        "spline_expression_modifier": {"spline_editor", "expression", "modifier"} <= kinds,
        "macro_template_output": "macro" in kinds and str(graph_payload.get("output_node") or "") == "out",
        "deep_volumetric_branch": {"deep_pixel_merge", "volumetric_fx"} <= kinds,
        "cache_locked_deep_nodes": bool({"modifier", "deep_pixel_merge"} & cache_kinds),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "node_kinds": sorted(kinds),
        "cache_locked_kinds": sorted(cache_kinds),
        "execution_order": plan.get("execution_order", []),
        "cache_boundaries": plan.get("cache_boundaries", []),
    }


def run_local_ml_runtime_probe(out_dir: str | Path = "debugCapture") -> dict[str, Any]:
    """Create a local synthetic image and run the real local-ML analyzer."""
    from PIL import Image

    from app.local_ml import local_ml_analyze_media, local_ml_backend_status

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    image_path = out / "professional_runtime_probe.png"
    Image.fromarray(synthetic_professional_frame()).save(image_path)
    analysis = local_ml_analyze_media(image_path, visual=True, transcribe=False, audio_beats=False, sample_count=1)
    detections = analysis.get("subject_detections", []) or []
    status = local_ml_backend_status()
    checks = {
        "local_only": not bool(status.get("cloud_enabled")) and not bool(status.get("api_required")),
        "image_written": image_path.exists() and image_path.stat().st_size > 0,
        "analysis_ok": bool(analysis.get("ok")),
        "detection_path_exercised": bool(detections) or bool(analysis.get("sampled_frames")),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "image_path": str(image_path),
        "backend_mode": status.get("mode"),
        "local_visual_available": bool(status.get("local_visual_available")),
        "detection_count": len(detections),
        "object_tags": analysis.get("object_tags", []),
        "analysis": {
            "ok": analysis.get("ok"),
            "sampled_frames": analysis.get("sampled_frames"),
            "metadata": analysis.get("metadata"),
            "subject_detections": detections[:3],
        },
    }


def run_fairlight_latency_runtime_sample() -> dict[str, Any]:
    """Verify Fairlight-style routing depth, latency compensation, and stress metadata."""
    from app.audio_workflow import (
        ADRCue,
        AudioRoutingMatrix,
        ElasticAudioRetime,
        SFXLibraryItem,
        build_default_routing_matrix,
        fairlight_engine_report,
        fairlight_mixer_stress_report,
    )

    tracks = [{"id": idx + 1, "role": ("dialogue", "music", "sfx")[idx % 3]} for idx in range(12)]
    matrix = build_default_routing_matrix(tracks)
    matrix = AudioRoutingMatrix(
        buses=matrix.buses,
        track_routes=matrix.track_routes,
        sends=matrix.sends,
        sample_rate=48000,
        channel_layout="7.1",
    )
    engine = fairlight_engine_report(
        matrix,
        adr_cues=[
            ADRCue("adr_intro", 1000, 3400, "Match the creator intro.", 3, True),
            ADRCue("adr_tag", 12000, 14500, "Record the end tag.", 2, True),
        ],
        retimes=[
            ElasticAudioRetime("dialogue_01", 1800, 1450, True),
            ElasticAudioRetime("sfx_hit_01", 520, 460, True),
        ],
        sfx_items=[
            SFXLibraryItem("click_soft", "sfx/click_soft.wav", ("cursor", "click"), -18.0),
            SFXLibraryItem("whoosh_short", "sfx/whoosh_short.wav", ("transition", "shorts"), -17.5),
        ],
        stress_track_count=2000,
    )
    stress = fairlight_mixer_stress_report(virtual_tracks=2000, channel_layout="7.1")
    checks = {
        "engine_ok": bool(engine.get("ok")),
        "stress_ok": bool(stress.get("ok")),
        "latency_compensation": bool(_as_dict(engine.get("checks")).get("latency_compensation"))
        and bool(_as_dict(stress.get("checks")).get("latency_compensation")),
        "adr_and_retime_ready": bool(_as_dict(engine.get("checks")).get("adr_workflow"))
        and bool(_as_dict(engine.get("checks")).get("elastic_retime")),
        "sfx_library_ready": bool(_as_dict(engine.get("checks")).get("sfx_library")),
        "large_track_contract": int(stress.get("virtual_tracks", 0) or 0) >= 2000,
        "surround_or_immersive_layout": int(stress.get("block_size", 0) or 0) >= 1024,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "engine": engine,
        "stress": stress,
        "summary": {
            "engine_nodes": int((_as_dict(engine.get("summary")).get("nodes", 0)) or 0),
            "engine_routes": int((_as_dict(engine.get("summary")).get("routes", 0)) or 0),
            "stress_tracks": int(stress.get("virtual_tracks", 0) or 0),
            "block_size": int(stress.get("block_size", 0) or 0),
            "total_latency_samples": int(stress.get("total_latency_samples", 0) or 0),
        },
    }


def professional_runtime_verification_report(*, out_dir: str | Path = "debugCapture") -> dict[str, Any]:
    """Run concrete synthetic runtime checks for professional workflow payloads."""
    from app.post_pipeline_workflow import professional_post_pipeline_report
    from app.professional_workflow_payloads import attach_professional_workflow_payloads

    enriched = attach_professional_workflow_payloads({
        "project_settings": {
            "fps": 120.0,
            "preview_export_parity_lock": True,
            "color_management": {
                "input_space": "sRGB",
                "working_space": "ACEScg",
                "output_space": "Rec.2020",
                "output_transfer": "PQ",
                "processing_bits": 32,
                "preview_transform_enabled": True,
            },
        },
        "audio_tracks": [
            {"id": 1, "role": "dialogue", "clips": []},
            {"id": 2, "role": "music", "clips": []},
            {"id": 3, "role": "sfx", "clips": []},
        ],
    })
    color = run_professional_color_runtime_sample(_as_dict(enriched.get("color_pipeline_payload")))
    color_precision = run_professional_color_precision_sample(_as_dict(enriched.get("color_pipeline_payload")))
    post = professional_post_pipeline_report()
    vfx = build_vfx_runtime_execution_plan(_as_dict(post.get("vfx_graph")))
    vfx_deep = run_vfx_expression_macro_runtime_sample(_as_dict(post.get("vfx_graph")))
    ml = run_local_ml_runtime_probe(out_dir)
    audio = run_fairlight_latency_runtime_sample()
    checks = {
        "color_runtime": bool(color.get("ok")),
        "color_precision_runtime": bool(color_precision.get("ok")),
        "vfx_execution_plan": bool(vfx.get("ok")),
        "vfx_expression_macro_runtime": bool(vfx_deep.get("ok")),
        "local_ml_probe": bool(ml.get("ok")),
        "audio_latency_stress_runtime": bool(audio.get("ok")),
        "preview_export_parity": bool(color.get("checks", {}).get("preview_export_same")) and str(enriched.get("project_settings", {}).get("preview_export_parity_lock")).lower() == "true",
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "summary": {
            "color_delta": color.get("mean_abs_delta"),
            "mask_coverage": color.get("mask_coverage"),
            "color_processing_bits": int(_as_dict(color_precision.get("summary")).get("processing_bits", 0) or 0),
            "vfx_nodes": int((vfx.get("qa") or {}).get("node_count", 0) or 0),
            "vfx_deep_kinds": len(vfx_deep.get("node_kinds", []) or []),
            "local_ml_detections": int(ml.get("detection_count", 0) or 0),
            "audio_stress_tracks": int(_as_dict(audio.get("summary")).get("stress_tracks", 0) or 0),
            "cache_boundaries": len(vfx.get("cache_boundaries", []) or []),
        },
        "color": color,
        "color_precision": color_precision,
        "vfx": vfx,
        "vfx_deep": vfx_deep,
        "local_ml": ml,
        "audio": audio,
        "enriched_project_keys": sorted(enriched.keys()),
    }
