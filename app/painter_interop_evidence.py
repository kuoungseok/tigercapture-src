"""Validation contract for evidence produced by an external image editor."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path) -> str:
    source = Path(path)
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_external_interop_report(
    report: dict[str, Any],
    *,
    expected_producer: str = "Adobe Photoshop",
) -> dict[str, Any]:
    """Reject internal-reader output masquerading as external interoperability proof."""
    errors: list[str] = []
    producer = str(report.get("producer") or "").strip()
    version = str(report.get("producer_version") or "").strip()
    execution = str(report.get("execution") or "").strip()
    artifacts = list(report.get("artifacts") or [])
    if producer != expected_producer:
        errors.append(f"unexpected evidence producer: {producer or '<missing>'}")
    if not version:
        errors.append("external producer version is missing")
    if execution not in {"windows_com", "photoshop_javascript"}:
        errors.append("external execution channel is not Photoshop automation")
    if not artifacts:
        errors.append("external evidence contains no artifacts")
    checked: list[dict[str, Any]] = []
    for row in artifacts:
        source = Path(str(row.get("path") or ""))
        expected_hash = str(row.get("sha256") or "")
        row_errors: list[str] = []
        if not source.is_file():
            row_errors.append("artifact missing")
        elif not expected_hash:
            row_errors.append("artifact hash missing")
        elif sha256_file(source) != expected_hash:
            row_errors.append("artifact hash mismatch")
        if not bool(row.get("opened_by_external_app", False)):
            row_errors.append("external-open observation missing")
        errors.extend(f"{source.name or '<unnamed>'}: {message}" for message in row_errors)
        checked.append({"path": str(source), "valid": not row_errors, "errors": row_errors})
    return {
        "schema": "tigerstudio.painter.external-interop-validation.v1",
        "valid": not errors,
        "producer": producer,
        "producer_version": version,
        "execution": execution,
        "artifacts": checked,
        "errors": errors,
    }


__all__ = ["sha256_file", "validate_external_interop_report"]
