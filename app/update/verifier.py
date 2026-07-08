"""Update artifact verification helpers."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from app.update.manifest import UpdateArtifact, normalize_sha256


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256_file(path: str | Path, expected_sha256: str) -> dict[str, Any]:
    expected = normalize_sha256(expected_sha256)
    actual = sha256_file(path)
    return {
        "ok": bool(expected and actual == expected),
        "path": str(Path(path)),
        "expected_sha256": expected,
        "actual_sha256": actual,
    }


def verify_artifact_file(path: str | Path, artifact: UpdateArtifact | Mapping[str, Any]) -> dict[str, Any]:
    parsed = artifact if isinstance(artifact, UpdateArtifact) else UpdateArtifact.from_mapping(artifact)
    report = verify_sha256_file(path, parsed.sha256)
    report["artifact_url"] = parsed.url
    report["signature_present"] = bool(parsed.signature or parsed.signature_url)
    report["signature_verified"] = False
    report["signature_policy"] = "sha256_verified_signature_slot_reserved"
    return report
