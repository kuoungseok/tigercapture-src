"""Resilient `.tgp` document bridge for Motion Designer data."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .schema import MotionComposition
from .validation import ValidationIssue, validate_composition


PROJECT_FORMAT_VERSION = "1.2"
PROJECT_KEY = "motion_compositions"


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
