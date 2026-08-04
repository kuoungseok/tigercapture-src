from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _current_audit_inventory() -> dict:
    from app.painter_product_reapproval import ROOT

    path = ROOT / "app" / "painter_action_contract.py"
    payload = path.read_bytes()
    rows = [{
        "path": "app/painter_action_contract.py",
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }]
    encoded = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "algorithm": "sha256",
        "file_count": 1,
        "inventory_sha256": hashlib.sha256(encoded).hexdigest(),
        "files": rows,
    }


def test_reapproval_keeps_missing_physical_and_duration_evidence_blocked(tmp_path: Path) -> None:
    from app.painter_evidence_contract import evidence_record
    from app.painter_product_reapproval import aggregate_product_reapproval

    artifact = _write(tmp_path / "artifact.bin", {"ok": True})
    m8 = {"provenance": [evidence_record("m8", "synthetic_integration", passed=True, producer="qa", claims=("automated_functional_baseline",), artifacts=(artifact,))]}
    native = {
        "physical_tablet_input_captured": False,
        "provenance": [
            evidence_record("gpu", "native_runtime", passed=True, producer="qa", claims=("basic_stroke_gpu_path",), artifacts=(artifact,)),
            evidence_record("tiles", "native_runtime", passed=True, producer="qa", claims=("retained_gpu_tile_display_consumption",), artifacts=(artifact,)),
        ],
    }
    crash = {"provenance": [evidence_record("crash", "native_runtime", passed=True, producer="qa", claims=("crash_recovery",), artifacts=(artifact,))]}
    external_artifacts = []
    for index in range(4):
        item = tmp_path / f"external-{index}.psd"; item.write_bytes(b"8BPS" + bytes([index])); external_artifacts.append({"path": str(item), "sha256": hashlib.sha256(item.read_bytes()).hexdigest()})
    external = {
        "schema": "tigerstudio.painter.photoshop-interop-qa.v1", "evidence_class": "measured_external_application",
        "producer": "Adobe Photoshop", "producer_version": "26.11.6", "execution": "photoshop_javascript", "run_nonce": "fresh",
        "claims": {name: True for name in ("fresh_external_run", "all_sources_opened", "png8_is_8bit", "png_tiff_are_16bit", "icc_profile_seen", "alpha_roundtrip_preserved", "layer_order_preserved", "roundtrip_artifacts_valid")},
        "validation": {"valid": True}, "artifacts": external_artifacts,
    }
    large = {"schema": "tigerstudio.painter.large-canvas-runtime-qa.v3", "passed": True, "zoom": [{"spatially_varied": True, "source_reference_parity": {"within_tolerance": True}}], "runtime": {"display": {"source_fallbacks": 0}}, "performance_threshold_claim": False}
    audit = {
        "schema": "tigerstudio.painter.evidence-source-audit.v2",
        "generated_at_utc": "2026-08-04T00:00:00+00:00",
        "source_inventory": _current_audit_inventory(),
        "assessment": {
            "unreviewed_numeric_scale_conversions": [],
            "unreviewed_quality_decision_thresholds": [],
            "unreviewed_numeric_control_literals": [{"path": "app/example.py", "line": 1}],
            "unreviewed_capacity_policy_literals": [],
            "unreviewed_semantic_shortcut_markers": [],
            "unreviewed_suppressed_exception_sites": [],
            "advanced_brush_product_integrated": False,
        },
    }
    payloads = {"audit": audit, "m8": m8, "native": native, "crash": crash, "disk_full": {"provenance": []}, "soak": {"provenance": []}, "external": external, "large_4k": large, "large_8k": large}
    paths = {name: _write(tmp_path / f"{name}.json", payload) for name, payload in payloads.items()}
    report = aggregate_product_reapproval(paths)
    assert report["aggregation_valid"] is True
    assert report["release_ready"] is False
    assert {"numeric_control_audit_complete", "native_high_dpi", "physical_tablet_input", "disk_full_recovery", "single_native_two_hour_survival", "three_run_two_hour_resource_envelope", "visual_product_review"} <= set(report["blockers"])
    assert report["release_claims"]["claims"]["external_psd_interop"]["passed"] is True
    assert report["numeric_control_audit"]["advanced_brush_product_integrated"] is False


def test_reapproval_rejects_old_large_canvas_nonblank_schema(tmp_path: Path) -> None:
    from app.painter_product_reapproval import aggregate_product_reapproval

    empty = {"provenance": []}
    paths = {}
    for name in ("m8", "native", "crash", "disk_full", "soak", "external"):
        paths[name] = _write(tmp_path / f"{name}.json", empty)
    paths["audit"] = _write(tmp_path / "audit.json", {
        "schema": "tigerstudio.painter.evidence-source-audit.v2",
        "generated_at_utc": "2026-08-04T00:00:00+00:00",
        "source_inventory": _current_audit_inventory(),
        "assessment": {
            "unreviewed_numeric_scale_conversions": [],
            "unreviewed_quality_decision_thresholds": [],
            "unreviewed_numeric_control_literals": [],
            "unreviewed_capacity_policy_literals": [],
            "unreviewed_semantic_shortcut_markers": [],
            "unreviewed_suppressed_exception_sites": [],
        },
    })
    old = {"schema": "tigerstudio.painter.large-canvas-runtime-qa.v1", "passed": True, "zoom": [{"nonblank": True}]}
    paths["large_4k"] = _write(tmp_path / "4k.json", old)
    paths["large_8k"] = _write(tmp_path / "8k.json", old)
    report = aggregate_product_reapproval(paths)
    assert report["aggregation_valid"] is False
    assert report["release_ready"] is False
    assert any("spatial large-canvas evidence" in row for row in report["errors"])


def test_independent_numeric_review_fingerprints_must_match_current_workspace() -> None:
    from app.painter_product_reapproval import ROOT, _relative_fingerprints_match

    source = ROOT / "app" / "painter_action_contract.py"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert _relative_fingerprints_match({"app/painter_action_contract.py": digest})
    assert not _relative_fingerprints_match(
        {"app/painter_action_contract.py": "0" * 64}
    )


def test_audit_source_inventory_must_match_current_workspace() -> None:
    from app.painter_product_reapproval import _audit_source_inventory_matches

    current = _current_audit_inventory()
    assert _audit_source_inventory_matches({"source_inventory": current}) is True
    stale = json.loads(json.dumps(current))
    stale["files"][0]["sha256"] = "0" * 64
    assert _audit_source_inventory_matches({"source_inventory": stale}) is False


@pytest.mark.parametrize(
    ("source_name", "optional"),
    [
        ("audit", False),
        ("independent_agent", True),
        ("independent_threshold_agent", True),
        ("independent_numeric_agent", True),
        ("soak_series", True),
    ],
)
def test_reapproval_source_decode_failures_are_typed_and_invalidate_aggregation(
    tmp_path: Path,
    source_name: str,
    optional: bool,
) -> None:
    from app.painter_product_reapproval import aggregate_product_reapproval

    required = (
        "audit", "m8", "native", "crash", "disk_full", "soak",
        "external", "large_4k", "large_8k",
    )
    paths = {name: _write(tmp_path / f"{name}.json", {}) for name in required}
    malformed = tmp_path / f"{source_name}-malformed.json"
    malformed.write_text("{", encoding="utf-8")
    paths[source_name] = malformed

    report = aggregate_product_reapproval(paths)

    assert report["aggregation_valid"] is False
    assert report["release_ready"] is False
    status = report["source_status"][source_name]
    assert status["loaded"] is False
    assert status["error"].startswith("JSONDecodeError: ")
    assert any(error.startswith(f"{source_name}: report could not be loaded") for error in report["errors"])
    assert optional is (source_name not in required)
