"""Resilient `.tgp` document bridge for Motion Designer data."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from .schema import MotionComposition
from .validation import ValidationIssue, validate_composition


PROJECT_FORMAT_VERSION = "1.2"
PROJECT_KEY = "motion_compositions"
MOTION_PROJECT_SCHEMA = "tigerstudio.motion.project.v1"
MOTION_PROJECT_EXTENSION = ".tgmotion"
MOTION_PROJECT_FILTER = "Tiger Studio Motion Project (*.tgmotion);;JSON (*.json)"


@dataclass(slots=True)
class MotionDocumentLoad:
    compositions: list[MotionComposition] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)


def serialize_compositions(compositions: Iterable[MotionComposition | Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [item.to_dict() if isinstance(item, MotionComposition) else MotionComposition.from_dict(item).to_dict()
            for item in compositions]


def inject_motion_document(document: Mapping[str, Any], compositions: Iterable[MotionComposition | Mapping[str, Any]]) -> dict[str, Any]:
    result = dict(document)
    result["version"] = PROJECT_FORMAT_VERSION
    result[PROJECT_KEY] = serialize_compositions(compositions)
    return result


def load_motion_document(document: Mapping[str, Any]) -> MotionDocumentLoad:
    loaded = MotionDocumentLoad()
    raw_items = document.get(PROJECT_KEY, [])
    if not isinstance(raw_items, list):
        loaded.issues.append(ValidationIssue("invalid_motion_root", "motion_compositions must be an array.", PROJECT_KEY))
        return loaded
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, Mapping):
            loaded.issues.append(ValidationIssue("invalid_composition", "Composition must be an object.", f"{PROJECT_KEY}[{index}]"))
            continue
        try:
            composition = MotionComposition.from_dict(raw)
            report = validate_composition(composition)
            if report.ok:
                loaded.compositions.append(composition)
            else:
                for issue in report.issues:
                    issue.path = f"{PROJECT_KEY}[{index}].{issue.path}".rstrip(".")
                    loaded.issues.append(issue)
        except (TypeError, ValueError, IndexError) as exc:
            loaded.issues.append(ValidationIssue("invalid_composition", str(exc), f"{PROJECT_KEY}[{index}]"))
    return loaded


def save_motion_project(composition: MotionComposition, path: str | Path) -> Path:
    """Atomically save one independently editable Motion composition."""
    validation = validate_composition(composition)
    if not validation.ok:
        raise ValueError(
            f"Invalid Motion composition cannot be saved: {validation.issues[0].message}"
        )
    target = Path(path).expanduser().resolve(strict=False)
    if target.suffix.lower() not in {MOTION_PROJECT_EXTENSION, ".json"}:
        target = target.with_suffix(MOTION_PROJECT_EXTENSION)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": MOTION_PROJECT_SCHEMA,
        "format_version": 1,
        "composition": composition.to_dict(),
    }
    temporary = target.with_name(target.name + f".{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def load_motion_project(path: str | Path) -> MotionComposition:
    """Load and validate one independent `.tgmotion` document."""
    source = Path(path).expanduser().resolve(strict=False)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("schema") != MOTION_PROJECT_SCHEMA:
        raise ValueError("Unsupported Tiger Studio Motion project")
    if int(payload.get("format_version", 0) or 0) != 1:
        raise ValueError("Unsupported Tiger Studio Motion project version")
    raw = payload.get("composition")
    if not isinstance(raw, Mapping):
        raise ValueError("Motion project has no composition")
    composition = MotionComposition.from_dict(raw)
    validation = validate_composition(composition)
    if not validation.ok:
        raise ValueError(f"Invalid Motion project: {validation.issues[0].message}")
    return composition


__all__ = [
    "MOTION_PROJECT_EXTENSION",
    "MOTION_PROJECT_FILTER",
    "MOTION_PROJECT_SCHEMA",
    "MotionDocumentLoad",
    "PROJECT_FORMAT_VERSION",
    "PROJECT_KEY",
    "inject_motion_document",
    "load_motion_document",
    "load_motion_project",
    "save_motion_project",
    "serialize_compositions",
]
