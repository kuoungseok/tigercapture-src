"""Product-readiness contract for the Painter Painting workflow.

This module deliberately contains no UI Design-mode requirements.  It turns the
M8 evidence checklist into data which can be checked by both local QA and an
independent reviewer instead of relying on a release claim.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA = "tigerstudio.painter.painting_product_readiness.v3"


def painting_scenarios() -> tuple[dict[str, Any], ...]:
    return (
        {"id": "character", "stages": ("line", "flat", "render")},
        {"id": "background", "stages": ("thumbnail", "block_in", "detail")},
        {"id": "material_impasto", "stages": ("material_paint", "impasto")},
        {
            "id": "editing_workflow",
            "stages": ("reference", "perspective", "selection_transform", "group", "clipping", "mask"),
        },
        {"id": "exchange_recovery", "stages": ("tspaint", "recovery", "png", "tiff", "psd")},
        {
            "id": "display_input",
            "stages": (
                "offscreen_window_760x560",
                "offscreen_window_1080p",
                "simulated_high_dpi_layout",
                "4k_tile_cardinality",
                "synthetic_tablet_channel_roundtrip",
            ),
        },
        {"id": "stress", "stages": ("large_stroke_render", "bounded_tile_cache", "reopen")},
    )


def painting_support_matrix() -> dict[str, Any]:
    return {
        "native_document": {"format": ".tspaint", "editable": True, "recovery": True},
        "flat_export": {
            "PNG": {"bits": (8, 16), "alpha": True, "icc": True},
            "TIFF": {"bits": (8, 16), "alpha": True, "icc": True},
            "JPEG": {"bits": (8,), "alpha": False, "icc": True},
            "WebP": {"bits": (8,), "alpha": True, "icc": True},
        },
        "layered_exchange": {
            "PSD": {
                "editable": ("paint_layers", "groups", "visibility", "opacity", "supported_blends"),
                "policy_for_unsupported": ("blocked", "explicit_bake"),
            }
        },
        "color": {"working_space": "sRGB", "embedded_profile": True, "soft_proof": "informational"},
    }


def painting_known_limitations() -> tuple[dict[str, str], ...]:
    return (
        {"id": "scope", "text": "Approval covers Painting mode only; UI Design mode is excluded."},
        {"id": "parity", "text": "No full Photoshop, Clip Studio Paint, or Corel Painter parity is claimed."},
        {"id": "gpu_headless", "text": "Headless systems may use the verified QPainter fallback when OpenGL context creation is unavailable."},
        {"id": "psd_advanced", "text": "Adjustment layers, clipping, masks, material layers, and unsupported blend modes are blocked or explicitly baked for PSD."},
        {"id": "cmyk", "text": "CMYK document conversion is not provided; the working/output profile boundary is sRGB."},
        {"id": "abr", "text": "Proprietary ABR brush rendering is not claimed; only validated metadata interchange is supported."},
        {"id": "precision", "text": "The interactive canvas is 8-bit; validated 16-bit export accepts high-precision sources and Material Height data."},
        {"id": "tablet_hardware", "text": "Pressure, tilt, rotation, and tangential-pressure persistence is automated; physical driver/hardware compatibility remains device-specific."},
    )


def file_evidence(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    exists = target.is_file()
    data = target.read_bytes() if exists else b""
    return {
        "path": str(target.resolve()),
        "exists": exists,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest() if data else "",
    }


def evaluate_painting_readiness(
    evidence: Mapping[str, Mapping[str, Any]],
    *,
    tests_passed: bool,
    recovery_passed: bool,
    stress_passed: bool,
    evidence_records: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    required = {
        scenario["id"]: tuple(scenario["stages"])
        for scenario in painting_scenarios()
    }
    missing: list[str] = []
    for scenario_id, stages in required.items():
        row = evidence.get(scenario_id, {})
        for stage in stages:
            value = row.get(stage)
            if value is False or value is None or value == "" or value == []:
                missing.append(f"{scenario_id}.{stage}")
    passed = bool(not missing and tests_passed and recovery_passed and stress_passed)
    from app.painter_evidence_contract import evaluate_release_claims

    release_claims = evaluate_release_claims(evidence_records)
    return {
        "schema": SCHEMA,
        "scope": "painting_only",
        "passed": passed,
        "classification": (
            "release_evidence"
            if passed and release_claims["release_ready"]
            else "automated_baseline_only"
        ),
        "release_ready": bool(passed and release_claims["release_ready"]),
        "release_claims": release_claims,
        "missing": missing,
        "tests_passed": bool(tests_passed),
        "recovery_passed": bool(recovery_passed),
        "stress_passed": bool(stress_passed),
        "support_matrix": painting_support_matrix(),
        "known_limitations": list(painting_known_limitations()),
    }


__all__ = [
    "SCHEMA",
    "evaluate_painting_readiness",
    "file_evidence",
    "painting_known_limitations",
    "painting_scenarios",
    "painting_support_matrix",
]
