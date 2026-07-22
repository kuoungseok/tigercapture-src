"""Atomic autosave and validated recovery records for Motion documents."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import MotionComposition
from .validation import validate_composition


MOTION_RECOVERY_SCHEMA = "tigercapture.motion.recovery.v1"


def default_motion_recovery_root(project_path: str | Path | None = None) -> Path:
    if project_path:
        project = Path(project_path).expanduser().resolve(strict=False)
        return project.parent / ".tigercapture_recovery" / "motion"
    local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return local / "TigerCapture" / "recovery" / "motion"


def motion_recovery_path(root: str | Path, composition_id: str) -> Path:
    safe_id = "".join(character for character in str(composition_id) if character.isalnum() or character in "-_")
    if not safe_id:
        raise ValueError("Motion recovery requires a composition id")
    return Path(root).expanduser().resolve(strict=False) / f"{safe_id}.motion-recovery.json"


def _canonical_composition_bytes(composition: MotionComposition) -> bytes:
    return json.dumps(
        composition.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _checksum(composition: MotionComposition) -> str:
    return hashlib.sha256(_canonical_composition_bytes(composition)).hexdigest()


def write_motion_recovery(composition: MotionComposition, path: str | Path, *,
                          project_path: str | Path | None = None) -> dict[str, Any]:
    validation = validate_composition(composition)
    if not validation.ok:
        raise ValueError(f"Invalid Motion composition cannot be autosaved: {validation.issues[0].message}")
    target = Path(path).expanduser().resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "schema": MOTION_RECOVERY_SCHEMA,
        "generated_at": generated_at,
        "composition_id": composition.id,
        "composition_revision": composition.revision,
        "project_path": str(Path(project_path).expanduser().resolve(strict=False)) if project_path else "",
        "checksum_sha256": _checksum(composition),
        "composition": composition.to_dict(),
    }
    temporary = target.with_name(target.name + f".{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, indent=2))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "ok": True,
        "path": str(target),
        "generated_at": generated_at,
        "composition_id": composition.id,
        "composition_revision": composition.revision,
        "checksum_sha256": payload["checksum_sha256"],
    }


def read_motion_recovery(path: str | Path, *, expected_composition_id: str = "",
                         current_revision: int | None = None, allow_other: bool = False,
                         allow_stale: bool = False) -> tuple[MotionComposition, dict[str, Any]]:
    source = Path(path).expanduser().resolve(strict=False)
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != MOTION_RECOVERY_SCHEMA:
        raise ValueError("Unsupported Motion recovery record")
    raw_composition = data.get("composition")
    if not isinstance(raw_composition, dict):
        raise ValueError("Motion recovery record has no composition")
    composition = MotionComposition.from_dict(raw_composition)
    if str(data.get("composition_id") or "") != composition.id:
        raise ValueError("Motion recovery composition id does not match its payload")
    actual_checksum = _checksum(composition)
    if str(data.get("checksum_sha256") or "") != actual_checksum:
        raise ValueError("Motion recovery checksum mismatch")
    expected = str(expected_composition_id or "")
    if expected and composition.id != expected and not allow_other:
        raise ValueError(f"Motion recovery belongs to another composition: {composition.id}")
    stale = current_revision is not None and composition.revision <= int(current_revision)
    if stale and not allow_stale:
        raise ValueError(
            f"Motion recovery revision {composition.revision} is not newer than current revision {current_revision}"
        )
    validation = validate_composition(composition)
    if not validation.ok:
        raise ValueError(f"Motion recovery composition is invalid: {validation.issues[0].message}")
    report = {
        "ok": True,
        "path": str(source),
        "generated_at": str(data.get("generated_at") or ""),
        "composition_id": composition.id,
        "composition_revision": composition.revision,
        "checksum_sha256": actual_checksum,
        "stale": stale,
        "project_path": str(data.get("project_path") or ""),
    }
    return composition, report


def list_motion_recoveries(root: str | Path) -> dict[str, Any]:
    base = Path(root).expanduser().resolve(strict=False)
    rows: list[dict[str, Any]] = []
    for path in sorted(base.glob("*.motion-recovery.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            composition, report = read_motion_recovery(path, allow_other=True, allow_stale=True)
            rows.append({**report, "name": composition.name, "valid": True})
        except Exception as exc:
            rows.append({"path": str(path), "valid": False, "error": str(exc)})
    return {"ok": True, "root": str(base), "count": len(rows), "recoveries": rows}


__all__ = [
    "MOTION_RECOVERY_SCHEMA", "default_motion_recovery_root", "list_motion_recoveries",
    "motion_recovery_path", "read_motion_recovery", "write_motion_recovery",
]
