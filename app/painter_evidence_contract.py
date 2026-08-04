"""Evidence provenance rules for Painter Painting release claims.

Passing a unit test is useful, but it is not interchangeable with a native GPU
run, a physical tablet run, an external application interoperability check, or
a real process crash.  This module keeps those evidence classes explicit.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA = "tigerstudio.painter.evidence-provenance.v1"

EVIDENCE_LEVELS = (
    "source_contract",
    "unit",
    "synthetic_integration",
    "simulated_environment",
    "native_runtime",
    "physical_hardware",
    "external_interop",
    "independent_manual",
)

# Each release claim lists evidence kinds which cannot be substituted by a
# weaker synthetic check.  Multiple rows mean all listed kinds are required.
RELEASE_CLAIM_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "numeric_control_audit_complete": ("source_contract",),
    "automated_functional_baseline": ("synthetic_integration",),
    "native_high_dpi": ("native_runtime",),
    "physical_tablet_input": ("physical_hardware",),
    "basic_stroke_gpu_path": ("native_runtime",),
    "retained_gpu_tile_display_consumption": ("native_runtime",),
    "crash_recovery": ("native_runtime",),
    "disk_full_recovery": ("native_runtime",),
    "single_native_two_hour_survival": ("native_runtime",),
    "three_run_two_hour_resource_envelope": ("native_runtime",),
    "external_psd_interop": ("external_interop",),
    "visual_product_review": ("independent_manual",),
}


def artifact_fingerprint(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    data = target.read_bytes() if target.is_file() else b""
    return {
        "path": str(target.resolve()),
        "exists": target.is_file(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest() if data else "",
    }


def evidence_record(
    evidence_id: str,
    kind: str,
    *,
    passed: bool,
    producer: str,
    claims: Iterable[str] = (),
    command: str = "",
    environment: Mapping[str, Any] | None = None,
    artifacts: Iterable[str | Path] = (),
    limitations: Iterable[str] = (),
) -> dict[str, Any]:
    normalized_kind = str(kind or "").strip()
    if normalized_kind not in EVIDENCE_LEVELS:
        raise ValueError(f"Unsupported Painter evidence kind: {kind}")
    normalized_claims = tuple(dict.fromkeys(str(row).strip() for row in claims if str(row).strip()))
    unknown_claims = [row for row in normalized_claims if row not in RELEASE_CLAIM_REQUIREMENTS]
    if unknown_claims:
        raise ValueError(f"Unsupported Painter release claim: {', '.join(unknown_claims)}")
    artifact_rows = [artifact_fingerprint(path) for path in artifacts]
    return {
        "schema": SCHEMA,
        "evidence_id": str(evidence_id or "").strip(),
        "kind": normalized_kind,
        "passed": bool(passed),
        "producer": str(producer or "").strip(),
        "claims": list(normalized_claims),
        "command": str(command or "").strip(),
        "environment": dict(environment or {}),
        "artifacts": artifact_rows,
        "limitations": [str(row) for row in limitations if str(row).strip()],
    }


def evaluate_release_claims(
    evidence: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    records = [dict(row) for row in evidence]
    valid = [
        row for row in records
        if row.get("schema") == SCHEMA
        and row.get("kind") in EVIDENCE_LEVELS
        and bool(row.get("passed"))
        and bool(str(row.get("producer") or "").strip())
    ]
    claims: dict[str, dict[str, Any]] = {}
    for claim_id, required_kinds in RELEASE_CLAIM_REQUIREMENTS.items():
        found = {
            kind: [
                row.get("evidence_id")
                for row in valid
                if row.get("kind") == kind and claim_id in tuple(row.get("claims") or ())
            ]
            for kind in required_kinds
        }
        missing = [kind for kind, rows in found.items() if not rows]
        claims[claim_id] = {
            "passed": not missing,
            "required_kinds": list(required_kinds),
            "evidence_ids": found,
            "missing": missing,
        }
    release_ready = all(row["passed"] for row in claims.values())
    return {
        "schema": "tigerstudio.painter.release-claim-audit.v1",
        "release_ready": release_ready,
        "classification": "release_evidence" if release_ready else "automated_baseline_only",
        "record_count": len(records),
        "valid_record_count": len(valid),
        "claims": claims,
    }


__all__ = [
    "EVIDENCE_LEVELS",
    "RELEASE_CLAIM_REQUIREMENTS",
    "SCHEMA",
    "artifact_fingerprint",
    "evidence_record",
    "evaluate_release_claims",
]
