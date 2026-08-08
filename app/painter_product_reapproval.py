"""Aggregate Painter release evidence without upgrading weaker evidence classes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from app.painter_evidence_contract import SCHEMA, evidence_record, evaluate_release_claims


REPORT_SCHEMA = "tigerstudio.painter.product-reapproval.v1"
ROOT = Path(__file__).resolve().parents[1]


def _load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _fingerprint_matches(row: Mapping[str, Any]) -> bool:
    path = Path(str(row.get("path") or ""))
    if not path.is_file() or not row.get("exists", True):
        return False
    payload = path.read_bytes()
    return (
        int(row.get("bytes", -1)) == len(payload)
        and str(row.get("sha256") or "") == hashlib.sha256(payload).hexdigest()
    )


def _relative_fingerprints_match(rows: Mapping[str, Any]) -> bool:
    if not rows:
        return False
    for relative, expected in rows.items():
        path = (ROOT / str(relative)).resolve()
        if ROOT not in path.parents or not path.is_file():
            return False
        if hashlib.sha256(path.read_bytes()).hexdigest() != str(expected):
            return False
    return True


def _audit_source_inventory_matches(report: Mapping[str, Any]) -> bool:
    inventory = report.get("source_inventory")
    if not isinstance(inventory, Mapping) or inventory.get("algorithm") != "sha256":
        return False
    files = list(inventory.get("files") or ())
    if not files or int(inventory.get("file_count") or 0) != len(files):
        return False
    verified: list[dict[str, Any]] = []
    for item in files:
        row = dict(item)
        relative = str(row.get("path") or "")
        path = (ROOT / relative).resolve()
        if ROOT not in path.parents or not path.is_file():
            return False
        payload = path.read_bytes()
        if (
            int(row.get("bytes", -1)) != len(payload)
            or str(row.get("sha256") or "") != hashlib.sha256(payload).hexdigest()
        ):
            return False
        verified.append({
            "path": relative.replace("\\", "/"),
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        })
    verified.sort(key=lambda row: row["path"])
    encoded = json.dumps(
        verified,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return str(inventory.get("inventory_sha256") or "") == hashlib.sha256(encoded).hexdigest()


def _verified_provenance(report: Mapping[str, Any], source: str) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for candidate in report.get("provenance") or ():
        row = dict(candidate)
        if row.get("schema") != SCHEMA:
            errors.append(f"{source}: unsupported provenance schema")
            continue
        artifacts = list(row.get("artifacts") or ())
        claim_bearing = bool(row.get("claims"))
        if bool(row.get("passed")) and claim_bearing and (not artifacts or not all(_fingerprint_matches(item) for item in artifacts)):
            row["passed"] = False
            row.setdefault("limitations", []).append("Artifact fingerprint validation failed during R8 aggregation.")
            errors.append(f"{source}:{row.get('evidence_id')}: artifact fingerprint mismatch")
        records.append(row)
    return records, errors


def aggregate_product_reapproval(paths: Mapping[str, str | Path]) -> dict[str, Any]:
    required = ("audit", "m8", "native", "crash", "disk_full", "soak", "external", "large_4k", "large_8k")
    loaded: dict[str, dict[str, Any]] = {}
    source_status: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for name in required:
        path = Path(paths[name])
        try:
            loaded[name] = _load(path)
            source_status[name] = {"path": str(path.resolve()), "loaded": True, "schema": loaded[name].get("schema")}
        except Exception as exc:
            loaded[name] = {}
            source_status[name] = {"path": str(path.resolve()), "loaded": False, "error": f"{type(exc).__name__}: {exc}"}
            errors.append(f"{name}: report could not be loaded")

    independent_agent: dict[str, Any] = {}
    if paths.get("independent_agent"):
        path = Path(paths["independent_agent"])
        try:
            independent_agent = _load(path)
            valid_agent_review = bool(
                independent_agent.get("schema") == "tigerstudio.painter.independent-r6-r7-qa.v1"
                and independent_agent.get("passed") is True
                and independent_agent.get("implementation_modified") is False
                and independent_agent.get("release_ready") is False
            )
            source_status["independent_agent"] = {
                "path": str(path.resolve()), "loaded": True,
                "schema": independent_agent.get("schema"), "valid": valid_agent_review,
            }
            if not valid_agent_review:
                errors.append("independent_agent: report contract did not validate")
        except Exception as exc:
            source_status["independent_agent"] = {"path": str(path.resolve()), "loaded": False, "error": f"{type(exc).__name__}: {exc}"}
            errors.append("independent_agent: report could not be loaded")

    independent_threshold_agent: dict[str, Any] = {}
    if paths.get("independent_threshold_agent"):
        path = Path(paths["independent_threshold_agent"])
        try:
            independent_threshold_agent = _load(path)
            valid_threshold_review = bool(
                independent_threshold_agent.get("schema") == "tigerstudio.painter.independent-threshold-qa.v1"
                and independent_threshold_agent.get("outcome") == "PASS"
                and independent_threshold_agent.get("implementation_modified") is False
                and independent_threshold_agent.get("release_readiness_assessed") is False
                and int(independent_threshold_agent.get("focused_tests", {}).get("failed") or 0) == 0
            )
            source_status["independent_threshold_agent"] = {
                "path": str(path.resolve()), "loaded": True,
                "schema": independent_threshold_agent.get("schema"), "valid": valid_threshold_review,
            }
            if not valid_threshold_review:
                errors.append("independent_threshold_agent: report contract did not validate")
        except Exception as exc:
            source_status["independent_threshold_agent"] = {"path": str(path.resolve()), "loaded": False, "error": f"{type(exc).__name__}: {exc}"}
            errors.append("independent_threshold_agent: report could not be loaded")

    independent_numeric_agent: dict[str, Any] = {}
    if paths.get("independent_numeric_agent"):
        path = Path(paths["independent_numeric_agent"])
        try:
            independent_numeric_agent = _load(path)
            summary = dict(independent_numeric_agent.get("summary") or {})
            valid_numeric_review = bool(
                independent_numeric_agent.get("schema")
                == "tigerstudio.painter.independent-numeric-resource-qa.v1"
                and independent_numeric_agent.get("verdict") == "PASS_WITH_LIMITATIONS"
                and independent_numeric_agent.get("implementation_files_modified_by_qa") is False
                and independent_numeric_agent.get("release_readiness_assessed") is False
                and int(summary.get("evidence_audit_unreviewed_total") or 0) == 0
                and int(summary.get("blocking_findings") or 0) == 0
                and _relative_fingerprints_match(
                    dict(independent_numeric_agent.get("sha256") or {})
                )
            )
            source_status["independent_numeric_agent"] = {
                "path": str(path.resolve()), "loaded": True,
                "schema": independent_numeric_agent.get("schema"),
                "valid": valid_numeric_review,
            }
            if not valid_numeric_review:
                errors.append("independent_numeric_agent: report contract did not validate")
        except Exception as exc:
            source_status["independent_numeric_agent"] = {
                "path": str(path.resolve()), "loaded": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            errors.append("independent_numeric_agent: report could not be loaded")

    records: list[dict[str, Any]] = []
    for name in ("m8", "native", "crash", "disk_full", "soak"):
        rows, row_errors = _verified_provenance(loaded[name], name)
        records.extend(rows)
        errors.extend(row_errors)
    if paths.get("soak_series"):
        path = Path(paths["soak_series"])
        try:
            series = _load(path)
            source_status["soak_series"] = {"path": str(path.resolve()), "loaded": True, "schema": series.get("schema")}
            rows, row_errors = _verified_provenance(series, "soak_series")
            records.extend(rows); errors.extend(row_errors)
        except Exception as exc:
            source_status["soak_series"] = {"path": str(path.resolve()), "loaded": False, "error": f"{type(exc).__name__}: {exc}"}
            errors.append("soak_series: report could not be loaded")

    audit = loaded["audit"]
    audit_assessment = dict(audit.get("assessment") or {})
    audit_inventory_current = bool(
        str(audit.get("generated_at_utc") or "").strip()
        and _audit_source_inventory_matches(audit)
    )
    source_status["audit"]["source_inventory_current"] = audit_inventory_current
    if not audit_inventory_current:
        errors.append("audit: source inventory fingerprint mismatch or provenance missing")
    audit_complete = bool(
        audit.get("schema") == "tigerstudio.painter.evidence-source-audit.v2"
        and audit_inventory_current
        and not audit_assessment.get("unreviewed_numeric_scale_conversions")
        and not audit_assessment.get("unreviewed_quality_decision_thresholds")
        and not audit_assessment.get("unreviewed_numeric_control_literals")
        and not audit_assessment.get("unreviewed_capacity_policy_literals")
        and not audit_assessment.get("unreviewed_semantic_shortcut_markers")
        and not audit_assessment.get("unreviewed_suppressed_exception_sites")
        and not audit_assessment.get("unresolved_decision_basis_rows")
        and audit_assessment.get("advanced_brush_product_integrated") is True
    )
    records.append(evidence_record(
        "painter-numeric-control-source-audit",
        "source_contract",
        passed=audit_complete,
        producer="tools/audit_painter_painting_evidence.py",
        claims=("numeric_control_audit_complete",),
        artifacts=(paths["audit"],),
        limitations=() if audit_complete else (
            "One or more numeric scale, quality-decision, control-flow, capacity-policy, semantic-shortcut, suppressed-exception, or Advanced Brush product-integration requirements remain unreviewed.",
        ),
    ))

    native = loaded["native"]
    records.append(evidence_record(
        "physical-tablet-observation",
        "physical_hardware",
        passed=bool(native.get("physical_tablet_input_captured")),
        producer="tools/qa_painter_native_environment.py",
        claims=("physical_tablet_input",),
        artifacts=(paths["native"],),
        limitations=("No physical tablet event was captured in this run.",) if not native.get("physical_tablet_input_captured") else (),
    ))

    external = loaded["external"]
    external_rows = list(external.get("artifacts") or ())
    external_artifacts = [Path(str(row.get("path") or "")) for row in external_rows]
    external_hashes_match = all(
        path.is_file()
        and str(row.get("sha256") or "") == hashlib.sha256(path.read_bytes()).hexdigest()
        for row, path in zip(external_rows, external_artifacts)
    )
    expected_external_claims = (
        "fresh_external_run", "all_sources_opened", "png8_is_8bit", "png_tiff_are_16bit",
        "icc_profile_seen", "alpha_roundtrip_preserved", "layer_order_preserved", "roundtrip_artifacts_valid",
    )
    producer = str(external.get("producer") or "")
    external_passed = bool(
        external.get("schema") == "tigerstudio.painter.photoshop-interop-qa.v1"
        and external.get("evidence_class") == "measured_external_application"
        and producer.casefold() == "adobe photoshop"
        and str(external.get("producer_version") or "").strip()
        and str(external.get("execution") or "").strip()
        and external.get("validation", {}).get("valid")
        and all(external.get("claims", {}).get(name) is True for name in expected_external_claims)
        and len(external_artifacts) == 4
        and external_hashes_match
    )
    records.append(evidence_record(
        "photoshop-external-interop",
        "external_interop",
        passed=external_passed,
        producer=f"{producer} {external.get('producer_version', '')}".strip(),
        claims=("external_psd_interop",),
        command=str(external.get("execution") or ""),
        environment={"run_nonce": external.get("run_nonce")},
        artifacts=external_artifacts,
        limitations=() if external_passed else ("External producer identity, fresh execution, claims, or artifacts did not validate.",),
    ))

    large_claims: dict[str, Any] = {}
    for name in ("large_4k", "large_8k"):
        row = loaded[name]
        spatial = all(item.get("spatially_varied") is True for item in row.get("zoom") or ())
        source_parity = all(
            item.get("source_reference_parity", {}).get("within_tolerance") is True
            for item in row.get("zoom") or ()
        )
        large_claims[name] = {
            "schema_v3": row.get("schema") == "tigerstudio.painter.large-canvas-runtime-qa.v3",
            "passed": row.get("passed") is True,
            "spatial_zoom_evidence": spatial,
            "source_reference_zoom_parity": source_parity,
            "complete_cached_layers": row.get("complete_cached_layers"),
            "layer_count": row.get("layer_count"),
            "source_fallbacks": row.get("runtime", {}).get("display", {}).get("source_fallbacks"),
            "performance_threshold_claim": row.get("performance_threshold_claim"),
        }
        if not (large_claims[name]["schema_v3"] and large_claims[name]["passed"] and spatial and source_parity):
            errors.append(f"{name}: spatial large-canvas evidence did not validate")

    release = evaluate_release_claims(records)
    blockers = [claim for claim, row in release["claims"].items() if not row["passed"]]
    return {
        "schema": REPORT_SCHEMA,
        "aggregation_valid": not errors,
        "release_ready": bool(not errors and release["release_ready"]),
        "classification": "release_evidence" if not errors and release["release_ready"] else "evidence_incomplete",
        "source_status": source_status,
        "provenance": records,
        "large_canvas": large_claims,
        "numeric_control_audit": {
            "complete": audit_complete,
            "source_inventory_current": audit_inventory_current,
            "unreviewed_numeric_scale_conversions": len(audit_assessment.get("unreviewed_numeric_scale_conversions") or ()),
            "unreviewed_quality_decision_thresholds": len(audit_assessment.get("unreviewed_quality_decision_thresholds") or ()),
            "unreviewed_numeric_control_literals": len(audit_assessment.get("unreviewed_numeric_control_literals") or ()),
            "unreviewed_capacity_policy_literals": len(audit_assessment.get("unreviewed_capacity_policy_literals") or ()),
            "unreviewed_semantic_shortcut_markers": len(audit_assessment.get("unreviewed_semantic_shortcut_markers") or ()),
            "unreviewed_suppressed_exception_sites": len(audit_assessment.get("unreviewed_suppressed_exception_sites") or ()),
            "advanced_brush_product_integrated": audit_assessment.get("advanced_brush_product_integrated") is True,
        },
        "release_claims": release,
        "blockers": blockers,
        "errors": errors,
        "independent_review": {
            "required_kind": "independent_manual",
            "agent_report_loaded": bool(independent_agent),
            "agent_outcome": independent_agent.get("outcome"),
            "agent_report": source_status.get("independent_agent"),
            "agent_review_is_human_manual": False,
            "note": "An independent QA agent review is recorded separately and cannot satisfy visual_product_review.",
            "threshold_agent_report": source_status.get("independent_threshold_agent"),
            "threshold_agent_outcome": independent_threshold_agent.get("outcome"),
            "threshold_agent_review_is_human_manual": False,
            "numeric_agent_report": source_status.get("independent_numeric_agent"),
            "numeric_agent_verdict": independent_numeric_agent.get("verdict"),
            "numeric_agent_review_is_human_manual": False,
        },
    }


__all__ = ["REPORT_SCHEMA", "aggregate_product_reapproval"]
